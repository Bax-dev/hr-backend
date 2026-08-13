from hr_app_backend.authentication.models import UserProfile
from hr_app_backend.utils.errors import PermissionDeniedError

_LEVEL_RANK = {'view': 1, 'download': 2, 'manage': 3}


def require_organization(user):
    """Any org member (admin or employee) may use the file management module."""
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    if organization is None:
        raise PermissionDeniedError('A company account is required to manage files.')
    return organization


def require_admin(user):
    """S3 bucket configuration and org-wide file management are admin-only."""
    organization = require_organization(user)
    profile = user.profile
    if profile.account_type != UserProfile.ACCOUNT_TYPE_COMPANY:
        raise PermissionDeniedError('Only company administrators can perform this action.')
    return organization


def is_admin(user):
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.account_type == UserProfile.ACCOUNT_TYPE_COMPANY)


def _employee_for(user):
    profile = getattr(user, 'profile', None)
    return getattr(profile, 'employee', None) if profile else None


def _share_level(file_asset, user):
    employee = _employee_for(user)
    if employee is None:
        return None
    best = None
    for share in file_asset.shares.all():
        matches = share.employee_id == employee.id or (
            share.department_id is not None
            and employee.department_record_id == share.department_id
        )
        if not matches:
            continue
        rank = _LEVEL_RANK.get(share.access_level, 0)
        if best is None or rank > _LEVEL_RANK.get(best, 0):
            best = share.access_level
    return best


def user_can_access(user, file_asset, level='view'):
    """Whether ``user`` may act on ``file_asset`` at least at ``level``
    ('view' < 'download' < 'manage')."""
    organization = getattr(user.profile, 'organization', None) if hasattr(user, 'profile') else None
    if organization is None or organization.id != file_asset.organization_id:
        return False

    if is_admin(user) or file_asset.uploaded_by_id == user.id:
        return True

    required_rank = _LEVEL_RANK.get(level, 0)

    base_level = None
    if file_asset.visibility in (file_asset.VISIBILITY_ORGANIZATION, file_asset.VISIBILITY_PUBLIC):
        base_level = file_asset.default_access

    share_level = _share_level(file_asset, user)

    resolved_rank = max(
        _LEVEL_RANK.get(base_level, 0) if base_level else 0,
        _LEVEL_RANK.get(share_level, 0) if share_level else 0,
    )
    return resolved_rank >= required_rank


def highest_access_level(user, file_asset):
    """Highest of 'manage'/'download'/'view' the user holds on ``file_asset``, or None."""
    for level in ('manage', 'download', 'view'):
        if user_can_access(user, file_asset, level):
            return level
    return None


_FOLDER_LEVEL_RANK = {'view': 1, 'manage': 2}


def _folder_share_level(folder, user):
    employee = _employee_for(user)
    if employee is None:
        return None
    best = None
    for share in folder.shares.all():
        matches = share.employee_id == employee.id or (
            share.department_id is not None
            and employee.department_record_id == share.department_id
        )
        if not matches:
            continue
        rank = _FOLDER_LEVEL_RANK.get(share.access_level, 0)
        if best is None or rank > _FOLDER_LEVEL_RANK.get(best, 0):
            best = share.access_level
    return best


def user_can_access_folder(user, folder, level='view'):
    """Whether ``user`` may act on ``folder`` at least at ``level`` ('view' < 'manage').

    Private (the default) is visible only to its creator, admins, and anyone
    holding an explicit FolderShare — this is what keeps a staff member's own
    folder scoped to just them and HR/admins.
    """
    organization = getattr(user.profile, 'organization', None) if hasattr(user, 'profile') else None
    if organization is None or organization.id != folder.organization_id:
        return False

    if is_admin(user) or folder.created_by_id == user.id:
        return True

    required_rank = _FOLDER_LEVEL_RANK.get(level, 0)

    base_level = 'view' if folder.visibility == folder.VISIBILITY_ORGANIZATION else None
    share_level = _folder_share_level(folder, user)

    resolved_rank = max(
        _FOLDER_LEVEL_RANK.get(base_level, 0) if base_level else 0,
        _FOLDER_LEVEL_RANK.get(share_level, 0) if share_level else 0,
    )
    return resolved_rank >= required_rank


def highest_folder_access_level(user, folder):
    """Highest of 'manage'/'view' the user holds on ``folder``, or None."""
    for level in ('manage', 'view'):
        if user_can_access_folder(user, folder, level):
            return level
    return None
