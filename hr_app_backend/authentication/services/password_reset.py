import hashlib
import random

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction

from hr_app_backend.third_parties import get_email_service, get_redis_client
from hr_app_backend.services import render_email_template
from hr_app_backend.utils.errors import NotFoundError, ValidationError

from .validation import normalize_email, validate_email_address, validate_passwords

User = get_user_model()

OTP_EXPIRY_SECONDS = 10 * 60
OTP_NAMESPACE = 'auth:otp'


def _otp_key(email):
    digest = hashlib.sha256(email.encode('utf-8')).hexdigest()
    return f'{OTP_NAMESPACE}:{digest}'


def _password_reset_email_body(otp_code):
    return f'Use this OTP to reset your password: {otp_code}. It expires in 10 minutes.'


def send_password_reset_otp(email):
    email = normalize_email(email)
    validate_email_address(email)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist as exc:
        raise NotFoundError('No account was found for this email address.') from exc

    otp_code = f'{random.randint(0, 999999):06d}'
    get_redis_client().setex(_otp_key(email), OTP_EXPIRY_SECONDS, otp_code)

    get_email_service().send_mail(
        subject='Your password reset OTP',
        body=_password_reset_email_body(otp_code),
        to_emails=[user.email],
        html_body=render_email_template(
            'emails/password_reset_otp.html',
            {
                'email_title': 'Reset your Workiva password',
                'email_eyebrow': 'Account Security',
                'email_heading': 'Reset your password',
                'email_intro': 'Use the secure code below to regain access to your dashboard and keep your HR operations moving.',
                'otp_code': otp_code,
                'expiry_minutes': OTP_EXPIRY_SECONDS // 60,
                'recipient_email': user.email,
            },
        ),
    )
    return {'email': email, 'expires_in': OTP_EXPIRY_SECONDS}


def verify_password_reset_otp(email, otp):
    email = normalize_email(email)
    stored = get_redis_client().get(_otp_key(email))
    if not stored or stored != str(otp).strip():
        raise ValidationError('Invalid or expired OTP.')
    return {'email': email, 'verified': True}


@transaction.atomic
def reset_password(email, otp, password, confirm_password):
    email = normalize_email(email)
    verify_password_reset_otp(email, otp)
    validate_passwords(password, confirm_password)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist as exc:
        raise NotFoundError('No account was found for this email address.') from exc

    user.password = make_password(password)
    user.save(update_fields=['password'])
    get_redis_client().delete(_otp_key(email))
    return user
