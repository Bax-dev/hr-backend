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
from hr_app_backend.utils import ValidationError, generate_uuid4, timedelta, today_local

PLAN_PRICES = {
    Subscription.PLAN_STARTER: {
        'monthly': Decimal('15000.00'),
        'annual': Decimal('150000.00'),
    },
    Subscription.PLAN_GROWTH: {
        'monthly': Decimal('35000.00'),
        'annual': Decimal('350000.00'),
    },
    Subscription.PLAN_INDIVIDUAL_ESSENTIAL: {
        'monthly': Decimal('2000.00'),
    },
    Subscription.PLAN_INDIVIDUAL_PREMIUM: {
        'monthly': Decimal('7000.00'),
    },
}

TRIAL_DURATION_DAYS = 14


def _parse_date(value, *, field_name):
    if not value:
        return None
    try:
        return timezone.datetime.fromisoformat(str(value)).date()
    except ValueError as exc:
        raise ValidationError(f'{field_name} must be a valid ISO date.') from exc


def _resolve_dates(plan, payload, *, billing_cycle):
    start_date = _parse_date(payload.get('start_date'), field_name='Start date') or today_local()
    end_date = _parse_date(payload.get('end_date'), field_name='End date')

    if plan == Subscription.PLAN_FREE_TRIAL:
        resolved_end = end_date or (start_date + timedelta(days=TRIAL_DURATION_DAYS))
        if resolved_end < start_date:
            raise ValidationError('End date cannot be earlier than start date.')
        return start_date, resolved_end

    if plan == Subscription.PLAN_ENTERPRISE:
        raise ValidationError('Enterprise plans require a demo booking, not online checkout.')

    if end_date is None:
        end_date = start_date + timedelta(days=365 if billing_cycle == 'annual' else 30)
    if end_date < start_date:
        raise ValidationError('End date cannot be earlier than start date.')
    return start_date, end_date


def _resolve_amount(plan, payload, *, billing_cycle):
    if plan == Subscription.PLAN_FREE_TRIAL:
        return Decimal('0.00')
    if plan in PLAN_PRICES:
        if billing_cycle not in {'monthly', 'annual'}:
            raise ValidationError('Billing cycle must be monthly or annual.')
        return PLAN_PRICES[plan][billing_cycle]
    raise ValidationError('Unsupported plan for online checkout.')


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
    plan = payload['plan']
    provider = payload['provider']
    billing_cycle = payload.get('billing_cycle') or 'monthly'
    is_individual = getattr(profile, 'account_type', None) == 'individual'
    individual_plans = {Subscription.PLAN_INDIVIDUAL_ESSENTIAL, Subscription.PLAN_INDIVIDUAL_PREMIUM}
    if is_individual:
        raise ValidationError('Personal subscriptions are no longer available. Use company signup to choose a plan.')
    if organization is None:
        raise ValidationError('A subscription owner is required.')
    if is_individual and plan not in individual_plans:
        raise ValidationError('Individual accounts must choose Essential or Premium.')
    if not is_individual and plan in individual_plans:
        raise ValidationError('Individual plans are not available to company accounts.')
    if is_individual and billing_cycle != 'monthly':
        raise ValidationError('Individual plans are billed monthly.')
    amount = _resolve_amount(plan, payload, billing_cycle=billing_cycle)
    start_date, end_date = _resolve_dates(plan, payload, billing_cycle=billing_cycle)
    email = (payload.get('email') or user.email or (organization.email if organization else '')).strip()
    customer_name = (payload.get('customer_name') or profile.full_name or (organization.name if organization else '')).strip()
    callback_url = (payload.get('callback_url') or '').strip()

    if not email:
        raise ValidationError('A customer email is required to initialize payment.')
    if provider != Subscription.PROVIDER_PAYSTACK:
        raise ValidationError('Only Paystack payments are supported.')
    if plan != Subscription.PLAN_FREE_TRIAL and not callback_url:
        raise ValidationError('Callback URL is required for Paystack payments.')

    if plan != Subscription.PLAN_FREE_TRIAL:
        owner_filter = {'created_by': user} if is_individual else {'organization': organization}
        pending_subscription = Subscription.objects.filter(
            **owner_filter,
            plan=plan,
            provider=provider,
            status=Subscription.STATUS_PENDING,
        ).order_by('-created_at').first()
        if pending_subscription is not None:
            if pending_subscription.payment_url:
                return pending_subscription
            pending_subscription.status = Subscription.STATUS_FAILED
            pending_subscription.save(update_fields=['status', 'updated_at'])

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

    if plan == Subscription.PLAN_FREE_TRIAL:
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.paid_at = timezone.now()
        subscription.provider_response = {
            'status': True,
            'message': 'Free trial activated.',
            'data': {
                'billing_cycle': 'trial',
            },
        }
        subscription.save(update_fields=['status', 'paid_at', 'provider_response', 'updated_at'])
        return subscription

    try:
        _initialize_with_paystack(subscription, email=email, callback_url=callback_url)
    except (PaystackError, FlutterwaveError):
        subscription.status = Subscription.STATUS_FAILED
        subscription.save(update_fields=['status', 'updated_at'])
        raise

    return subscription


@transaction.atomic
def verify_subscription_payment(user, payload):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None)
    try:
        owner_filter = {'created_by': user} if organization is None else {'organization': organization}
        subscription = Subscription.objects.get(reference=payload['reference'], **owner_filter)
    except Subscription.DoesNotExist as exc:
        raise ValidationError('Subscription payment reference was not found.') from exc

    provider = payload.get('provider') or subscription.provider
    if provider != subscription.provider:
        raise ValidationError('Provider does not match the subscription reference.')

    if provider == Subscription.PROVIDER_PAYSTACK:
        response, paid = _verify_paystack(subscription)
    else:
        response, paid = _verify_flutterwave(subscription)

    if paid and organization is None and subscription.plan in {
        Subscription.PLAN_INDIVIDUAL_ESSENTIAL,
        Subscription.PLAN_INDIVIDUAL_PREMIUM,
    }:
        profile.individual_plan = subscription.plan
        profile.save(update_fields=['individual_plan', 'updated_at'])
    return subscription, response, paid
