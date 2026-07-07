from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from hr_app_backend.billing.models import Subscription
from hr_app_backend.third_parties import (
    FlutterwaveError,
    PaystackError,
    get_flutterwave_client,
    get_paystack_client,
)
from hr_app_backend.utils import ConflictError, ValidationError, generate_uuid4, timedelta, today_local

PLAN_PRICES = {
    Subscription.PLAN_STARTER: Decimal('4.00'),
    Subscription.PLAN_PROFESSIONAL: Decimal('8.00'),
}


def _parse_date(value, *, field_name):
    if not value:
        return None
    try:
        return timezone.datetime.fromisoformat(str(value)).date()
    except ValueError as exc:
        raise ValidationError(f'{field_name} must be a valid ISO date.') from exc


def _resolve_dates(plan, payload):
    start_date = _parse_date(payload.get('start_date'), field_name='Start date') or today_local()
    end_date = _parse_date(payload.get('end_date'), field_name='End date')

    if plan == Subscription.PLAN_CUSTOM:
        if end_date is None:
            raise ValidationError('End date is required for the custom plan.')
        if end_date < start_date:
            raise ValidationError('End date cannot be earlier than start date.')
        return start_date, end_date

    if end_date is None:
        end_date = start_date + timedelta(days=30)
    if end_date < start_date:
        raise ValidationError('End date cannot be earlier than start date.')
    return start_date, end_date


def _resolve_amount(plan, payload):
    if plan in PLAN_PRICES:
        return PLAN_PRICES[plan]

    amount = payload.get('amount')
    if amount is None:
        raise ValidationError('Amount is required for the custom plan.')
    return amount


def _minor_units(amount):
    return str((amount * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _build_reference(provider):
    prefix = 'pst' if provider == Subscription.PROVIDER_PAYSTACK else 'flw'
    return f"{prefix}_{str(generate_uuid4()).replace('-', '')[:24]}"


def _subscription_metadata(subscription):
    return {
        'subscription_id': str(subscription.id),
        'organization_id': str(subscription.organization_id),
        'plan': subscription.plan,
        'start_date': subscription.start_date.isoformat(),
        'end_date': subscription.end_date.isoformat() if subscription.end_date else None,
    }


def _initialize_with_paystack(subscription, *, email, callback_url):
    response = get_paystack_client().initialize_transaction(
        email=email,
        amount=_minor_units(subscription.amount),
        reference=subscription.reference,
        callback_url=callback_url or None,
        metadata=_subscription_metadata(subscription),
        currency=subscription.currency,
    )
    data = response.get('data') or {}
    subscription.payment_url = data.get('authorization_url', '')
    subscription.access_code = data.get('access_code', '')
    subscription.provider_response = response
    subscription.save(update_fields=['payment_url', 'access_code', 'provider_response', 'updated_at'])
    return response


def _initialize_with_flutterwave(subscription, *, email, customer_name, callback_url):
    response = get_flutterwave_client().initialize_payment(
        tx_ref=subscription.reference,
        amount=str(subscription.amount),
        currency=subscription.currency,
        redirect_url=callback_url,
        customer={
            'email': email,
            'name': customer_name or subscription.organization.name,
        },
        customizations={
            'title': f'{subscription.organization.name} subscription',
            'description': f'{subscription.plan.title()} plan subscription payment',
        },
        meta=_subscription_metadata(subscription),
    )
    data = response.get('data') or {}
    subscription.payment_url = data.get('link', '')
    subscription.provider_response = response
    subscription.save(update_fields=['payment_url', 'provider_response', 'updated_at'])
    return response


def _verify_paystack(subscription):
    response = get_paystack_client().verify_transaction(subscription.reference)
    data = response.get('data') or {}
    paid = bool(response.get('status')) and data.get('status') == 'success'
    subscription.provider_response = response
    subscription.gateway_transaction_id = str(data.get('id', ''))
    subscription.status = Subscription.STATUS_ACTIVE if paid else Subscription.STATUS_FAILED
    subscription.paid_at = timezone.now() if paid else None
    subscription.save(update_fields=['provider_response', 'gateway_transaction_id', 'status', 'paid_at', 'updated_at'])
    return response, paid


def _verify_flutterwave(subscription):
    response = get_flutterwave_client().verify_transaction(subscription.reference)
    data = response.get('data') or {}
    paid = response.get('status') == 'success' and data.get('status') == 'successful'
    subscription.provider_response = response
    subscription.gateway_transaction_id = str(data.get('id', ''))
    subscription.status = Subscription.STATUS_ACTIVE if paid else Subscription.STATUS_FAILED
    subscription.paid_at = timezone.now() if paid else None
    subscription.save(update_fields=['provider_response', 'gateway_transaction_id', 'status', 'paid_at', 'updated_at'])
    return response, paid


@transaction.atomic
def initialize_subscription_payment(user, payload):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None)
    if organization is None:
        raise ValidationError('Only organization accounts can create subscriptions.')

    plan = payload['plan']
    provider = payload['provider']
    amount = _resolve_amount(plan, payload)
    start_date, end_date = _resolve_dates(plan, payload)
    email = (payload.get('email') or user.email or organization.email).strip()
    customer_name = (payload.get('customer_name') or profile.full_name or organization.name).strip()
    callback_url = (payload.get('callback_url') or '').strip()

    if not email:
        raise ValidationError('A customer email is required to initialize payment.')
    if provider == Subscription.PROVIDER_FLUTTERWAVE and not callback_url:
        raise ValidationError('Redirect URL is required for Flutterwave payments.')

    pending_subscription = Subscription.objects.filter(
        organization=organization,
        plan=plan,
        provider=provider,
        status=Subscription.STATUS_PENDING,
    ).order_by('-created_at').first()
    if pending_subscription is not None:
        raise ConflictError('There is already a pending payment for this plan and provider.')

    subscription = Subscription.objects.create(
        organization=organization,
        created_by=user,
        plan=plan,
        provider=provider,
        reference=_build_reference(provider),
        amount=amount,
        currency=payload['currency'],
        start_date=start_date,
        end_date=end_date,
    )

    try:
        if provider == Subscription.PROVIDER_PAYSTACK:
            _initialize_with_paystack(subscription, email=email, callback_url=callback_url)
        else:
            _initialize_with_flutterwave(
                subscription,
                email=email,
                customer_name=customer_name,
                callback_url=callback_url,
            )
    except (PaystackError, FlutterwaveError):
        subscription.status = Subscription.STATUS_FAILED
        subscription.save(update_fields=['status', 'updated_at'])
        raise

    return subscription


@transaction.atomic
def verify_subscription_payment(user, payload):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None)
    if organization is None:
        raise ValidationError('Only organization accounts can verify subscriptions.')

    try:
        subscription = Subscription.objects.get(reference=payload['reference'], organization=organization)
    except Subscription.DoesNotExist as exc:
        raise ValidationError('Subscription payment reference was not found.') from exc

    provider = payload.get('provider') or subscription.provider
    if provider != subscription.provider:
        raise ValidationError('Provider does not match the subscription reference.')

    if provider == Subscription.PROVIDER_PAYSTACK:
        response, paid = _verify_paystack(subscription)
    else:
        response, paid = _verify_flutterwave(subscription)

    return subscription, response, paid
