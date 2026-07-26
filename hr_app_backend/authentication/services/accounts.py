from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction

from ..models import Organization, UserProfile
from hr_app_backend.utils.errors import AuthenticationError, ConflictError, ValidationError
from .signup_otp import send_signup_otp
from .validation import normalize_email, validate_email_address, validate_passwords

User = get_user_model()


@transaction.atomic
def register_company(data):
    company_name = (data.get('company_name') or '').strip()
    email = normalize_email(data.get('email'))
    phone = (data.get('phone') or '').strip()
    size = (data.get('size') or '').strip()
    industry = (data.get('industry') or '').strip()
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not company_name:
        raise ValidationError('Company name is required.')
    if not phone:
        raise ValidationError('Phone number is required.')
    validate_email_address(email)
    validate_passwords(password, confirm_password)

    if User.objects.filter(email=email).exists():
        raise ConflictError('An account with this email already exists.')
    if Organization.objects.filter(email=email).exists():
        raise ConflictError('An organization with this email already exists.')

    organization = Organization.objects.create(
        name=company_name,
        email=email,
        phone=phone,
        size=size,
        industry=industry,
    )
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
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
def register_individual(data):
    full_name = (data.get('full_name') or '').strip()
    email = normalize_email(data.get('email'))
    invite_code = (data.get('invite_code') or '').strip()
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not full_name:
        raise ValidationError('Full name is required.')
    validate_email_address(email)
    validate_passwords(password, confirm_password)

    if User.objects.filter(email=email).exists():
        raise ConflictError('An account with this email already exists.')

    first_name, _, last_name = full_name.partition(' ')
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    UserProfile.objects.create(
        user=user,
        account_type=UserProfile.ACCOUNT_TYPE_INDIVIDUAL,
        full_name=full_name,
        invite_code=invite_code,
    )
    send_signup_otp(user)
    return user


def login_user(data):
    email = normalize_email(data.get('email'))
    password = data.get('password') or ''
    if not email or not password:
        raise ValidationError('Email and password are required.')

    user = authenticate(username=email, password=password)
    if user is None:
        raise AuthenticationError('Invalid email or password.')
    return user


@transaction.atomic
def change_password(user, data):
    current_password = data.get('current_password') or ''
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not check_password(current_password, user.password):
        raise AuthenticationError('Current password is incorrect.')

    validate_passwords(password, confirm_password)
    user.password = make_password(password)
    user.save(update_fields=['password'])

    profile = getattr(user, 'profile', None)
    if profile and profile.must_change_password:
        profile.must_change_password = False
        profile.save(update_fields=['must_change_password'])

    return user
