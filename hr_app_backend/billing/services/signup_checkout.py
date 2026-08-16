import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from hr_app_backend.authentication.models import Organization
from hr_app_backend.authentication.services.accounts import register_company
from hr_app_backend.authentication.services.sessions import auth_response
from hr_app_backend.authentication.services.validation import normalize_email, validate_email_address, validate_passwords
from hr_app_backend.billing.models import Subscription
from hr_app_backend.third_parties import get_paystack_client, get_redis_client
from hr_app_backend.utils import ConflictError, ValidationError, today_local, timedelta

from .billing import PLAN_PRICES, _build_reference, _minor_units

User = get_user_model()

PENDING_SIGNUP_NAMESPACE = 'billing:pending-signup'
PENDING_SIGNUP_EXPIRY_SECONDS = 60 * 60


def _pending_key(reference):
    return f'{PENDING_SIGNUP_NAMESPACE}:{reference}'


def _validate_company_signup(data):
    company_name = str(data.get('company_name') or '').strip()
    email = normalize_email(data.get('email'))
    phone = str(data.get('phone') or '').strip()
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not company_name:
        raise ValidationError('Company name is required.')
    if not phone:
        raise ValidationError('Phone number is required.')
    validate_email_address(email)
    validate_passwords(password, confirm_password)
    if User.objects.filter(email=email).exists() or Organization.objects.filter(email=email).exists():
        raise ConflictError('An account with this email already exists.')

    return {
        'company_name': company_name,
        'email': email,
        'phone': phone,
        'size': str(data.get('size') or '').strip(),
        'industry': str(data.get('industry') or '').strip(),
        'password': password,
        'confirm_password': confirm_password,
    }


def initialize_paid_signup_checkout(payload):
    account_type = str(payload.get('account_type') or 'company').strip().lower()
    if account_type != 'company':
        raise ValidationError('Paid signup is available for company accounts only.')
    signup = _validate_company_signup(payload)
    plan = str(payload.get('plan') or '').strip().lower()
    billing_cycle = str(payload.get('billing_cycle') or 'monthly').strip().lower()
    callback_url = str(payload.get('callback_url') or '').strip()

    if plan not in PLAN_PRICES:
        raise ValidationError('A paid Essential or Premium plan is required.')
    if billing_cycle not in {'monthly', 'annual'}:
        raise ValidationError('Billing cycle must be monthly or annual.')
    if not callback_url:
        raise ValidationError('Callback URL is required.')

    amount = PLAN_PRICES[plan][billing_cycle]
    reference = _build_reference(Subscription.PROVIDER_PAYSTACK)
    pending = {
        'signup': signup,
        'plan': plan,
        'billing_cycle': billing_cycle,
        'amount': str(amount),
        'currency': 'NGN',
        'account_type': 'company',
    }
    redis_client = get_redis_client()
    redis_client.setex(_pending_key(reference), PENDING_SIGNUP_EXPIRY_SECONDS, json.dumps(pending))

    try:
        response = get_paystack_client().initialize_transaction(
            email=signup['email'],
            amount=_minor_units(amount),
            reference=reference,
            callback_url=callback_url,
            metadata={'reference': reference, 'plan': plan, 'billing_cycle': billing_cycle, 'account_type': account_type},
            currency='NGN',
        )
    except Exception:
        redis_client.delete(_pending_key(reference))
        raise

    data = response.get('data') or {}
    return {
        'reference': reference,
        'checkout_url': data.get('authorization_url', ''),
        'access_code': data.get('access_code', ''),
    }


@transaction.atomic
def verify_paid_signup_checkout(reference):
    redis_client = get_redis_client()
    raw_pending = redis_client.get(_pending_key(reference))
    if not raw_pending:
        raise ValidationError('This signup checkout has expired or was already completed.')
    pending = json.loads(raw_pending)

    response = get_paystack_client().verify_transaction(reference)
    data = response.get('data') or {}
    paid = bool(response.get('status')) and data.get('status') == 'success'
    paid_amount = Decimal(str(data.get('amount', '0'))) / Decimal('100')
    expected_amount = Decimal(pending['amount'])
    if not paid or paid_amount != expected_amount or data.get('currency') != pending['currency']:
        raise ValidationError('Paystack has not confirmed the expected payment.')

    signup = pending['signup']
    if pending.get('account_type', 'company') != 'company':
        raise ValidationError('This signup checkout is no longer valid.')
    user = register_company(signup)
    start_date = today_local()
    end_date = start_date + timedelta(days=365 if pending['billing_cycle'] == 'annual' else 30)
    subscription = Subscription.objects.create(
        organization=user.profile.organization,
        created_by=user,
        plan=pending['plan'],
        provider=Subscription.PROVIDER_PAYSTACK,
        status=Subscription.STATUS_ACTIVE,
        reference=reference,
        amount=expected_amount,
        currency=pending['currency'],
        start_date=start_date,
        end_date=end_date,
        gateway_transaction_id=str(data.get('id', '')),
        paid_at=timezone.now(),
        provider_response=response,
    )
    redis_client.delete(_pending_key(reference))
    return subscription, auth_response(user), response
