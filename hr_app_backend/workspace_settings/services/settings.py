import datetime

from django.db import transaction

from hr_app_backend.utils.errors import PermissionDeniedError, ValidationError

from ..models import WorkspaceSettings

VALID_WORK_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


def _require_organization(user):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    if organization is None:
        raise PermissionDeniedError('A company account is required to manage workspace settings.')
    return organization


def _get_or_create(organization):
    settings, _ = WorkspaceSettings.objects.get_or_create(organization=organization)
    return settings


def get_settings(user):
    organization = _require_organization(user)
    return organization, _get_or_create(organization)


# ----- Company profile -------------------------------------------------------

def update_company_profile(user, data):
    organization = _require_organization(user)
    settings = _get_or_create(organization)

    if data.get('company_name') is not None:
        name = str(data['company_name']).strip()
        if not name:
            raise ValidationError('Company name is required.')
        organization.name = name
    if data.get('owner_email') is not None:
        organization.email = str(data['owner_email']).strip()
    if data.get('phone') is not None:
        organization.phone = str(data['phone']).strip()
    if data.get('industry') is not None:
        organization.industry = str(data['industry']).strip()

    if data.get('registration_number') is not None:
        settings.registration_number = str(data['registration_number']).strip()
    if data.get('tax_id') is not None:
        settings.tax_id = str(data['tax_id']).strip()
    if data.get('headquarters_address') is not None:
        settings.headquarters_address = str(data['headquarters_address']).strip()
    if data.get('website') is not None:
        settings.website = str(data['website']).strip()

    with transaction.atomic():
        organization.save()
        settings.save()
    return organization, settings


# ----- Attendance policy -----------------------------------------------------

def _clean_time(value, label):
    try:
        return datetime.datetime.strptime(str(value), '%H:%M').time()
    except ValueError as exc:
        raise ValidationError(f'{label} must be a valid time (HH:mm).') from exc


def _clean_minutes(value, label):
    try:
        minutes = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'{label} must be a number.') from exc
    if minutes < 0:
        raise ValidationError(f'{label} cannot be negative.')
    return minutes


def _clean_work_days(value):
    if not isinstance(value, list):
        raise ValidationError('Work days must be a list.')
    cleaned = []
    for day in value:
        key = str(day).strip().lower()[:3]
        if key not in VALID_WORK_DAYS:
            raise ValidationError(f'Invalid work day: {day}.')
        if key not in cleaned:
            cleaned.append(key)
    return cleaned


def update_attendance_policy(user, data):
    organization = _require_organization(user)
    settings = _get_or_create(organization)

    if data.get('standard_check_in') is not None:
        settings.standard_check_in = _clean_time(data['standard_check_in'], 'Standard check-in')
    if data.get('standard_check_out') is not None:
        settings.standard_check_out = _clean_time(data['standard_check_out'], 'Standard check-out')
    if data.get('grace_period_minutes') is not None:
        settings.grace_period_minutes = _clean_minutes(data['grace_period_minutes'], 'Grace period')
    if data.get('late_threshold_minutes') is not None:
        settings.late_threshold_minutes = _clean_minutes(data['late_threshold_minutes'], 'Late threshold')
    if data.get('auto_check_out') is not None:
        settings.auto_check_out = bool(data['auto_check_out'])
    if data.get('work_days') is not None:
        settings.work_days = _clean_work_days(data['work_days'])

    settings.save()
    return settings


# ----- Security --------------------------------------------------------------

def update_security_settings(user, data):
    organization = _require_organization(user)
    settings = _get_or_create(organization)

    if data.get('two_factor_required') is not None:
        settings.two_factor_required = bool(data['two_factor_required'])
    if data.get('enforce_single_session') is not None:
        settings.enforce_single_session = bool(data['enforce_single_session'])
    if data.get('password_expiry_days') is not None:
        settings.password_expiry_days = _clean_minutes(data['password_expiry_days'], 'Password expiry')
    if data.get('session_timeout_minutes') is not None:
        settings.session_timeout_minutes = _clean_minutes(data['session_timeout_minutes'], 'Session timeout')
    if data.get('allowed_email_domain') is not None:
        settings.allowed_email_domain = str(data['allowed_email_domain']).strip().lower()

    settings.save()
    return settings
