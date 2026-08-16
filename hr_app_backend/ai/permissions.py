from hr_app_backend.authentication.models import UserProfile
from hr_app_backend.utils.errors import PermissionDeniedError


def require_organization(user):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    if organization is None:
        raise PermissionDeniedError('A company account is required to use the HR Copilot.')
    return organization


def is_company_admin(user):
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.account_type == UserProfile.ACCOUNT_TYPE_COMPANY)


def require_company_admin(user):
    organization = require_organization(user)
    if not is_company_admin(user):
        raise PermissionDeniedError('Only company administrators can run this HR Copilot action.')
    return organization
