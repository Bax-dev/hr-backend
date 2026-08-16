def serialize_organization(organization):
    if organization is None:
        return None
    return {
        'id': organization.id,
        'name': organization.name,
        'email': organization.email,
        'phone': organization.phone,
        'size': organization.size,
        'industry': organization.industry,
    }


def serialize_user(user):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    employee = getattr(profile, 'employee', None) if profile else None
    copilot_enabled = True
    if organization is not None:
        from hr_app_backend.workspace_settings.services import is_copilot_enabled

        copilot_enabled = is_copilot_enabled(organization)
    return {
        'id': user.id,
        'email': user.email,
        'is_superuser': user.is_superuser,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': getattr(profile, 'full_name', '') or user.get_full_name(),
        'account_type': getattr(profile, 'account_type', ''),
        'phone': getattr(profile, 'phone', ''),
        'invite_code': getattr(profile, 'invite_code', ''),
        'must_change_password': getattr(profile, 'must_change_password', False),
        'email_verified': getattr(profile, 'email_verified', False),
        'gender': getattr(profile, 'gender', ''),
        'country': getattr(profile, 'country', ''),
        'date_of_birth': profile.date_of_birth.isoformat() if profile and profile.date_of_birth else '',
        'avatar': getattr(employee, 'avatar', '') or None,
        'copilot_enabled': copilot_enabled,
        'organization': serialize_organization(organization),
    }
