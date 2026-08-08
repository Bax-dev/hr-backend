from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction

from hr_app_backend.utils.errors import AuthenticationError, ValidationError

from .validation import validate_passwords

User = get_user_model()
INVITE_SALT = 'authentication.employee-invite'
INVITE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def create_employee_invite_token(user):
    return signing.dumps(
        {'user_id': user.pk, 'password': user.password},
        salt=INVITE_SALT,
        compress=True,
    )


def _invited_user(token):
    try:
        payload = signing.loads(token, salt=INVITE_SALT, max_age=INVITE_MAX_AGE_SECONDS)
        user = User.objects.select_related('profile__employee', 'profile__organization').get(pk=payload['user_id'])
    except (signing.BadSignature, signing.SignatureExpired, KeyError, User.DoesNotExist) as exc:
        raise AuthenticationError('This invitation link is invalid or has expired.') from exc

    profile = getattr(user, 'profile', None)
    if not profile or not profile.employee or payload.get('password') != user.password or user.has_usable_password():
        raise AuthenticationError('This invitation link has already been used or is no longer valid.')
    return user


def employee_invite_details(token):
    user = _invited_user(token)
    employee = user.profile.employee
    return {
        'email': user.email,
        'first_name': employee.first_name,
        'last_name': employee.last_name,
        'avatar': employee.avatar,
        'organization_name': employee.organization.name,
    }


def validate_employee_invite(token):
    """Return the invited user for other narrowly scoped pre-activation actions."""
    return _invited_user(token)


@transaction.atomic
def accept_employee_invite(data):
    user = _invited_user(data.get('token') or '')
    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    avatar = (data.get('avatar') or '').strip()
    if not first_name or not last_name:
        raise ValidationError('First name and last name are required.')
    validate_passwords(data.get('password') or '', data.get('confirm_password') or '')

    employee = user.profile.employee
    employee.first_name = first_name
    employee.last_name = last_name
    employee.avatar = avatar
    employee.save(update_fields=['first_name', 'last_name', 'avatar', 'updated_at'])

    user.first_name = first_name
    user.last_name = last_name
    user.set_password(data['password'])
    user.save(update_fields=['first_name', 'last_name', 'password'])

    user.profile.full_name = f'{first_name} {last_name}'
    user.profile.email_verified = True
    user.profile.save(update_fields=['full_name', 'email_verified', 'updated_at'])
    return user
