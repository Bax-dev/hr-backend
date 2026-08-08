import json

from hr_app_backend.utils.errors import BadRequestError, ValidationError


def parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError as exc:
        raise BadRequestError('Request body must be valid JSON.') from exc


def _value(payload, *keys, default=''):
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


def company_signup_payload(payload):
    return {
        'company_name': _value(payload, 'company_name', 'companyName'),
        'email': _value(payload, 'email'),
        'phone': _value(payload, 'phone'),
        'size': _value(payload, 'size', 'companySize'),
        'industry': _value(payload, 'industry'),
        'password': _value(payload, 'password'),
        'confirm_password': _value(payload, 'confirm_password', 'confirmPassword'),
    }


def individual_signup_payload(payload):
    return {
        'full_name': _value(payload, 'full_name', 'fullName'),
        'email': _value(payload, 'email'),
        'invite_code': _value(payload, 'invite_code', 'inviteCode'),
        'password': _value(payload, 'password'),
        'confirm_password': _value(payload, 'confirm_password', 'confirmPassword'),
        'plan': _value(payload, 'plan', default='free'),
    }


def login_payload(payload):
    return {
        'email': _value(payload, 'email'),
        'password': _value(payload, 'password'),
    }


def change_password_payload(payload):
    current_password = _value(payload, 'current_password', 'currentPassword')
    password = _value(payload, 'password')
    confirm_password = _value(payload, 'confirm_password', 'confirmPassword')
    if not current_password:
        raise ValidationError('Current password is required.')
    return {
        'current_password': current_password,
        'password': password,
        'confirm_password': confirm_password,
    }


def forgot_password_payload(payload):
    email = _value(payload, 'email')
    if not email:
        raise ValidationError('Email is required.')
    return {'email': email}


def verify_otp_payload(payload):
    email = _value(payload, 'email')
    otp = _value(payload, 'otp')
    if not email or not otp:
        raise ValidationError('Email and OTP are required.')
    return {'email': email, 'otp': otp}


def reset_password_payload(payload):
    email = _value(payload, 'email')
    otp = _value(payload, 'otp')
    password = _value(payload, 'password')
    confirm_password = _value(payload, 'confirm_password', 'confirmPassword')
    if not email or not otp:
        raise ValidationError('Email and OTP are required.')
    return {
        'email': email,
        'otp': otp,
        'password': password,
        'confirm_password': confirm_password,
    }
