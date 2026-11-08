import logging

from django.contrib.auth import get_user_model

from hr_app_backend.third_parties import get_email_service
from hr_app_backend.services import render_email_template
from hr_app_backend.utils.errors import ValidationError

from .otp import check_code, discard_code, issue_code
from .validation import normalize_email

logger = logging.getLogger(__name__)

User = get_user_model()

SIGNUP_OTP_EXPIRY_SECONDS = 10 * 60
# 'v2': codes are now stored hashed; anyone mid-signup can use "resend code".
SIGNUP_OTP_NAMESPACE = 'auth:signup-otp:v2'


def send_signup_otp(user):
    """Generate and email a fresh signup-verification OTP for ``user``."""
    otp_code = issue_code(SIGNUP_OTP_NAMESPACE, user.email, SIGNUP_OTP_EXPIRY_SECONDS)

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
    result = {'email': email, 'expires_in': SIGNUP_OTP_EXPIRY_SECONDS}
    user = User.objects.select_related('profile').filter(email=email).first()
    if user is None:
        # Same response as a real resend so the endpoint can't enumerate accounts.
        logger.info('Signup OTP resend requested for an unknown address.')
        return result

    # A previous verification may have committed successfully while its HTTP
    # response failed. Sending a fresh code lets the owner recover that signup
    # session without bypassing proof of access to the email inbox.
    send_signup_otp(user)
    return result


def verify_signup_otp(email, otp):
    email = normalize_email(email)
    check_code(SIGNUP_OTP_NAMESPACE, email, otp)

    user = User.objects.select_related('profile').filter(email=email).first()
    if user is None:
        raise ValidationError('Invalid or expired OTP.', code='OTP_INVALID')

    profile = getattr(user, 'profile', None)
    if profile is not None and not profile.email_verified:
        profile.email_verified = True
        profile.save(update_fields=['email_verified', 'updated_at'])

    discard_code(SIGNUP_OTP_NAMESPACE, email)
    return user
