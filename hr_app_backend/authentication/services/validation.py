from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email

from hr_app_backend.utils.errors import ValidationError


def normalize_email(email):
    return (email or '').strip().lower()


def validate_passwords(password, confirm_password):
    if not password:
        raise ValidationError('Password is required.')
    if password != confirm_password:
        raise ValidationError('Passwords do not match.')
    try:
        validate_password(password)
    except DjangoValidationError as exc:
        raise ValidationError(exc.messages[0]) from exc


def validate_email_address(email):
    try:
        validate_email(email)
    except DjangoValidationError as exc:
        raise ValidationError('A valid email address is required.') from exc
