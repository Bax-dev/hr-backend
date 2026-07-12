def serialize_company_profile(organization, settings):
    return {
        'company_name': organization.name,
        'owner_email': organization.email,
        'phone': organization.phone,
        'industry': organization.industry,
        'registration_number': settings.registration_number,
        'tax_id': settings.tax_id,
        'headquarters_address': settings.headquarters_address,
        'website': settings.website,
    }


def serialize_attendance_policy(settings):
    return {
        'standard_check_in': settings.standard_check_in.strftime('%H:%M'),
        'standard_check_out': settings.standard_check_out.strftime('%H:%M'),
        'grace_period_minutes': settings.grace_period_minutes,
        'late_threshold_minutes': settings.late_threshold_minutes,
        'auto_check_out': settings.auto_check_out,
        'work_days': settings.work_days or [],
    }


def serialize_security_settings(settings):
    return {
        'two_factor_required': settings.two_factor_required,
        'password_expiry_days': settings.password_expiry_days,
        'session_timeout_minutes': settings.session_timeout_minutes,
        'enforce_single_session': settings.enforce_single_session,
        'allowed_email_domain': settings.allowed_email_domain,
    }
