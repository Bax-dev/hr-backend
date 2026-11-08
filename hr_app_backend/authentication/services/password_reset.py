import logging

from django.contrib.auth import get_user_model
from django.db import transaction

from hr_app_backend.third_parties import get_email_service
from hr_app_backend.services import render_email_template
from hr_app_backend.utils.errors import ValidationError

from ..models import UserSession
from .otp import check_code, discard_code, issue_code
from .sessions import revoke_all_sessions
from .validation import normalize_email, validate_email_address, validate_passwords

logger = logging.getLogger(__name__)

User = get_user_model()

OTP_EXPIRY_SECONDS = 10 * 60
# 'v2': codes are now stored hashed; old plain-text keys simply stop matching.
OTP_NAMESPACE = 'auth:otp:v2'


def _password_reset_email_body(otp_code):
    return f'Use this OTP to reset your password: {otp_code}. It expires in 10 minutes.'


def send_password_reset_otp(email):
    """Email a reset code if the account exists.

    The response is identical whether or not the address is registered, so
    this endpoint cannot be used to discover which emails have accounts.
    """
    email = normalize_email(email)
    validate_email_address(email)
    result = {'email': email, 'expires_in': OTP_EXPIRY_SECONDS}

    user = User.objects.filter(email=email, is_active=True).first()
    if user is None:
        logger.info('Password reset requested for an unknown address.')
        return result

    otp_code = issue_code(OTP_NAMESPACE, email, OTP_EXPIRY_SECONDS)
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
    return result


def verify_password_reset_otp(email, otp):
    email = normalize_email(email)
    check_code(OTP_NAMESPACE, email, otp)
    return {'email': email, 'verified': True}


@transaction.atomic
def reset_password(email, otp, password, confirm_password):
    email = normalize_email(email)
    # Validate the new password first so a typo doesn't burn an OTP attempt.
    validate_passwords(password, confirm_password)
    verify_password_reset_otp(email, otp)

    user = User.objects.filter(email=email).first()
    if user is None:
        # Unreachable in practice (a code is only issued for real accounts),
        # but keep the message generic either way.
        raise ValidationError('Invalid or expired OTP.', code='OTP_INVALID')

    user.set_password(password)
    user.save(update_fields=['password'])
    discard_code(OTP_NAMESPACE, email)
    # Whoever triggered the reset may be recovering from a compromise: every
    # existing session stops working. The view then issues a fresh one (or an
    # MFA challenge if two-step verification is on).
    revoke_all_sessions(user, UserSession.REVOKED_PASSWORD_RESET)
    return user
