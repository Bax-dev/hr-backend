import datetime

from hr_app_backend.authentication.models import UserProfile
from hr_app_backend.utils.errors import NotFoundError, PermissionDeniedError, ValidationError


def require_organization(user):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    if organization is None:
        raise PermissionDeniedError('A company account is required to manage talent modules.')
    if getattr(profile, 'account_type', None) != UserProfile.ACCOUNT_TYPE_COMPANY:
        raise PermissionDeniedError('Only company administrators can manage talent modules.')
    return organization


def clean_text(value):
    return (value or '').strip()


def clean_date(value, label):
    if value in (None, ''):
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError(f'{label} must be an ISO date (YYYY-MM-DD).') from exc


def clean_status(value, default='pending'):
    status = clean_text(value).lower().replace(' ', '_').replace('-', '_') or default
    valid = {'draft', 'pending', 'active', 'completed', 'approved', 'closed', 'archived', 'open'}
    if status not in valid:
        raise ValidationError(f'Status must be one of: {", ".join(sorted(valid))}.')
    return status


def clean_priority(value, default='medium'):
    priority = clean_text(value).lower() or default
    valid = {'low', 'medium', 'high', 'critical'}
    if priority not in valid:
        raise ValidationError(f'Priority must be one of: {", ".join(sorted(valid))}.')
    return priority


def clean_bool(value):
    if isinstance(value, bool):
        return value
    if value in (None, ''):
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', '1', 'yes', 'on'}:
            return True
        if normalized in {'false', '0', 'no', 'off'}:
            return False
    return bool(value)


def get_record(model, organization, record_pk, label):
    try:
        return model.objects.get(organization=organization, pk=record_pk)
    except model.DoesNotExist as exc:
        raise NotFoundError(f'{label} not found.') from exc
