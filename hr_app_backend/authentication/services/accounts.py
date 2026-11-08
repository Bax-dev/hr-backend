from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction

from ..models import Organization, UserProfile, UserSession
from hr_app_backend.utils.errors import AuthenticationError, ConflictError, PermissionDeniedError, ValidationError
from .sessions import current_session_id, destroy_all_sessions_for_user, revoke_all_sessions
from .signup_otp import send_signup_otp
from .validation import normalize_email, validate_email_address, validate_passwords

User = get_user_model()


def _check_password_input(data, password_hash):
    """Validate a raw password, unless a pre-validated hash is supplied.

    The paid-signup flow validates the password up front, then keeps only its
    hash while the payment is pending, so it never stores plaintext.
    """
    if password_hash:
        return
    validate_passwords(data.get('password') or '', data.get('confirm_password') or '')


def _create_user(*, email, password, password_hash, **fields):
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=email, email=email, password=password or None, **fields)
            if password_hash:
                user.password = password_hash
                user.save(update_fields=['password'])
            return user
    except IntegrityError as exc:
        # Two concurrent signups for one address: the unique username wins the
        # race that the ``exists()`` pre-check cannot.
        raise ConflictError('An account with this email already exists.') from exc


@transaction.atomic
def register_company(data, *, password_hash=None):
    company_name = (data.get('company_name') or '').strip()
    email = normalize_email(data.get('email'))
    phone = (data.get('phone') or '').strip()
    size = (data.get('size') or '').strip()
    industry = (data.get('industry') or '').strip()
    password = data.get('password') or ''

    if not company_name:
        raise ValidationError('Company name is required.')
    if not phone:
        raise ValidationError('Phone number is required.')
    validate_email_address(email)
    _check_password_input(data, password_hash)

    if User.objects.filter(email=email).exists():
        raise ConflictError('An account with this email already exists.')
    if Organization.objects.filter(email=email).exists():
        raise ConflictError('An organization with this email already exists.')

    try:
        with transaction.atomic():
            organization = Organization.objects.create(
                name=company_name,
                email=email,
                phone=phone,
                size=size,
                industry=industry,
            )
    except IntegrityError as exc:
        raise ConflictError('An organization with this email already exists.') from exc
    user = _create_user(
        email=email,
        password=password,
        password_hash=password_hash,
        first_name=company_name,
    )
    UserProfile.objects.create(
        user=user,
        account_type=UserProfile.ACCOUNT_TYPE_COMPANY,
        full_name=company_name,
        phone=phone,
        organization=organization,
    )
    send_signup_otp(user)
    return user


@transaction.atomic
def change_password(user, data):
    current_password = data.get('current_password') or ''
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not check_password(current_password, user.password):
        raise AuthenticationError('Current password is incorrect.')

    validate_passwords(password, confirm_password)
    if password == current_password:
        raise ValidationError('Choose a new password that is different from your current one.')
    user.password = make_password(password)
    user.save(update_fields=['password'])
    # Keep this device signed in; every other session has to sign in with the new password.
    user.sessions_revoked = revoke_all_sessions(
        user, UserSession.REVOKED_PASSWORD_CHANGED, except_session_id=current_session_id(user)
    )

    profile = getattr(user, 'profile', None)
    if profile and profile.must_change_password:
        profile.must_change_password = False
        profile.save(update_fields=['must_change_password'])

    return user


@transaction.atomic
def delete_account(user, data):
    """Soft-delete the signed-in user's own account: deactivate the login,
    detach it from its organization, and kill every active session.

    Company (org admin) accounts can't self-delete since there's no owner
    transfer flow yet; that would orphan the organization and its employees.
    The linked Employee HR record (if any) is left untouched — it belongs to
    the org, not to the user deleting their own account access.
    """
    password = data.get('password') or ''
    if not check_password(password, user.password):
        raise AuthenticationError('Incorrect password.')

    profile = getattr(user, 'profile', None)
    if profile and profile.account_type == UserProfile.ACCOUNT_TYPE_COMPANY:
        raise PermissionDeniedError(
            'Company accounts cannot delete themselves. Contact support to close your organization.'
        )

    user.is_active = False
    user.email = f'deleted-{user.id}-{user.email}'[:254]
    user.username = f'deleted-{user.id}-{user.username}'[:150]
    user.save(update_fields=['is_active', 'email', 'username'])

    if profile is not None:
        profile.organization = None
        profile.save(update_fields=['organization', 'updated_at'])

    destroy_all_sessions_for_user(user.id)
    return user
