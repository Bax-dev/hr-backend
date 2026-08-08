import hashlib
import random

from django.contrib.auth import get_user_model

from hr_app_backend.third_parties import get_email_service, get_redis_client
from hr_app_backend.services import render_email_template
from hr_app_backend.utils.errors import NotFoundError, ValidationError

from .validation import normalize_email

User = get_user_model()

SIGNUP_OTP_EXPIRY_SECONDS = 10 * 60
SIGNUP_OTP_NAMESPACE = 'auth:signup-otp'


def _otp_key(email):
    digest = hashlib.sha256(email.encode('utf-8')).hexdigest()
    return f'{SIGNUP_OTP_NAMESPACE}:{digest}'


def send_signup_otp(user):
    """Generate and email a fresh signup-verification OTP for ``user``."""
    otp_code = f'{random.randint(0, 999999):06d}'
    get_redis_client().setex(_otp_key(user.email), SIGNUP_OTP_EXPIRY_SECONDS, otp_code)

    get_email_service().send_mail(
        subject='Verify your email address',
        body=f'Use this code to verify your email address: {otp_code}. It expires in 10 minutes.',
        to_emails=[user.email],
        html_body=render_email_template(
            'emails/signup_otp.html',
            {
                'email_title': 'Verify your Workiva account',
                'email_eyebrow': 'Email verification',
                'email_heading': 'Verify your email',
                'email_intro': (
                    "You're almost set up. Enter this code to confirm your email address "
                    'and activate your account.'
                ),
                'otp_code': otp_code,
                'expiry_minutes': SIGNUP_OTP_EXPIRY_SECONDS // 60,
                'recipient_email': user.email,
            },
        ),
    )
    return {'email': user.email, 'expires_in': SIGNUP_OTP_EXPIRY_SECONDS}


def resend_signup_otp(email):
    email = normalize_email(email)
    try:
        user = User.objects.select_related('profile').get(email=email)
    except User.DoesNotExist as exc:
        raise NotFoundError('No account was found for this email address.') from exc

    # A previous verification may have committed successfully while its HTTP
    # response failed. Sending a fresh code lets the owner recover that signup
    # session without bypassing proof of access to the email inbox.
    return send_signup_otp(user)


def verify_signup_otp(email, otp):
    email = normalize_email(email)
    stored = get_redis_client().get(_otp_key(email))
    if not stored or stored != str(otp).strip():
        raise ValidationError('Invalid or expired OTP.')

    try:
        user = User.objects.select_related('profile').get(email=email)
    except User.DoesNotExist as exc:
        raise NotFoundError('No account was found for this email address.') from exc

    profile = getattr(user, 'profile', None)
    if profile is not None and not profile.email_verified:
        profile.email_verified = True
        profile.save(update_fields=['email_verified', 'updated_at'])

    get_redis_client().delete(_otp_key(email))
    return user
