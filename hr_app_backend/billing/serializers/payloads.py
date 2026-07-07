from decimal import Decimal, InvalidOperation

from hr_app_backend.utils.errors import ValidationError


ALLOWED_PROVIDERS = {'paystack', 'flutterwave'}
ALLOWED_PLANS = {'starter', 'professional', 'custom'}


def _value(payload, *keys, default=''):
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


def _parse_decimal(value, *, field_name):
    if value in ('', None):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f'{field_name} must be a valid amount.') from exc
    if amount <= 0:
        raise ValidationError(f'{field_name} must be greater than zero.')
    return amount.quantize(Decimal('0.01'))


def initialize_subscription_payload(payload):
    provider = str(_value(payload, 'provider')).strip().lower()
    plan = str(_value(payload, 'plan')).strip().lower()
    currency = str(_value(payload, 'currency', default='USD')).strip().upper() or 'USD'

    if provider not in ALLOWED_PROVIDERS:
        raise ValidationError('Provider must be either paystack or flutterwave.')
    if plan not in ALLOWED_PLANS:
        raise ValidationError('Plan must be starter, professional, or custom.')

    return {
        'provider': provider,
        'plan': plan,
        'currency': currency,
        'email': _value(payload, 'email'),
        'customer_name': _value(payload, 'customer_name', 'customerName'),
        'callback_url': _value(payload, 'callback_url', 'callbackUrl', 'redirect_url', 'redirectUrl'),
        'start_date': _value(payload, 'start_date', 'startDate'),
        'end_date': _value(payload, 'end_date', 'endDate'),
        'amount': _parse_decimal(_value(payload, 'amount', 'custom_amount', 'customAmount'), field_name='Amount'),
    }


def verify_subscription_payload(payload):
    reference = str(_value(payload, 'reference')).strip()
    provider = str(_value(payload, 'provider')).strip().lower()

    if not reference:
        raise ValidationError('Reference is required.')
    if provider and provider not in ALLOWED_PROVIDERS:
        raise ValidationError('Provider must be either paystack or flutterwave.')

    return {
        'reference': reference,
        'provider': provider,
    }
