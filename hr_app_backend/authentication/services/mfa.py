"""Two-step verification: an authenticator app (TOTP, RFC 6238) plus single-use recovery codes.

Setup      POST auth/mfa/setup/   {password}        -> secret + otpauth:// URL (device pending)
           POST auth/mfa/enable/  {code}            -> recovery codes (shown once); MFA is now on
Sign-in    POST auth/login/                         -> {mfa_required, mfa_token, methods, expires_at}
           POST auth/mfa/verify/  {mfa_token, code | recovery_code} -> {token, user}
Manage     POST auth/mfa/disable/, auth/mfa/recovery-codes/  {password, code}

Security notes
- The TOTP secret is Fernet-encrypted at rest with MFA_ENCRYPTION_KEY (or a key derived from
  SECRET_KEY when that is unset). Rotating SECRET_KEY without MFA_ENCRYPTION_KEY set
  invalidates every enrolment, so set MFA_ENCRYPTION_KEY in production.
- Codes are compared in constant time, accept ±1 time-step (30 s) of clock drift, and a
  time-step that was already used can't be replayed (``last_used_counter``, under a row lock).
- Challenges are random tokens stored as sha256, valid 5 minutes, single use, 5 wrong codes
  max. Wrong codes also count towards the account's sign-in lockout (services.login).
- Recovery codes are stored as HMACs keyed with SECRET_KEY; each works once.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import timedelta
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from hr_app_backend.audit_logs.services import record_audit_event_safely
from hr_app_backend.utils.env import get_env
from hr_app_backend.utils.errors import AppError, AuthenticationError, ConflictError, ValidationError
from hr_app_backend.utils.throttles import ThrottledError

from ..models import LoginEvent, MfaChallenge, MfaDevice, MfaRecoveryCode, UserSession

DIGITS = 6
PERIOD = 30
DRIFT_STEPS = 1
CHALLENGE_TTL = timedelta(minutes=5)
MAX_CHALLENGE_ATTEMPTS = 5
RECOVERY_CODE_COUNT = 10
ISSUER = 'Workiva'
METHODS = ['totp', 'recovery_code']


# ---------------------------------------------------------------- crypto helpers


def _fernet():
    key = get_env('MFA_ENCRYPTION_KEY', '') or ''
    if not key:
        digest = hashlib.sha256(f'workiva-mfa:{settings.SECRET_KEY}'.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key)


def encrypt_secret(secret):
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token):
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:  # encryption key changed since enrolment
        raise AppError(
            'Two-step verification needs to be set up again. Contact support.',
            status_code=500,
            code='MFA_UNAVAILABLE',
        ) from exc


def generate_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def hotp(secret, counter):
    key = base64.b32decode(secret + '=' * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack('>I', digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def current_counter(at=None):
    return int((time.time() if at is None else at) // PERIOD)


def matching_counter(secret, code, at=None):
    """The time-step ``code`` belongs to (within ±DRIFT_STEPS), or None."""
    code = ''.join(ch for ch in str(code or '') if ch.isdigit())
    if len(code) != DIGITS:
        return None
    now = current_counter(at)
    found = None
    for counter in range(now - DRIFT_STEPS, now + DRIFT_STEPS + 1):
        if hmac.compare_digest(hotp(secret, counter), code):
            found = counter
    return found


def otpauth_url(secret, email):
    label = quote(f'{ISSUER}:{email}')
    query = urlencode({'secret': secret, 'issuer': ISSUER, 'algorithm': 'SHA1', 'digits': DIGITS, 'period': PERIOD})
    return f'otpauth://totp/{label}?{query}'


def _normalise_recovery(code):
    return ''.join(ch for ch in str(code or '').lower() if ch.isalnum())


def _recovery_hash(user_id, code):
    message = f'mfa-recovery:{user_id}:{_normalise_recovery(code)}'.encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _new_recovery_codes(user):
    alphabet = 'abcdefghjkmnpqrstuvwxyz23456789'  # no 0/o, 1/l/i
    codes = [
        '-'.join(''.join(secrets.choice(alphabet) for _ in range(5)) for _ in range(2))
        for _ in range(RECOVERY_CODE_COUNT)
    ]
    MfaRecoveryCode.objects.filter(user=user).delete()
    MfaRecoveryCode.objects.bulk_create(
        [MfaRecoveryCode(user=user, code_hash=_recovery_hash(user.pk, code)) for code in codes]
    )
    return codes


# ---------------------------------------------------------------- errors


def _invalid_code():
    return ValidationError(
        'That code is not right. Check your authenticator app and try again.', code='INVALID_MFA_CODE'
    )


def _wrong_password():
    return ValidationError('Your password is incorrect.', code='INVALID_PASSWORD')


def _challenge_invalid():
    return AuthenticationError('Your sign-in timed out. Sign in again.', code='MFA_CHALLENGE_INVALID')


def _audit(request, user, action, description, category='security'):
    organization = getattr(getattr(user, 'profile', None), 'organization', None)
    if organization is None:
        return
    record_audit_event_safely(
        organization=organization,
        actor=user,
        request=request,
        action=action,
        category=category,
        description=description,
        resource_type='user',
        resource_id=user.pk,
    )


# ---------------------------------------------------------------- status & enrolment


def enabled_for(user):
    return MfaDevice.objects.filter(user=user, confirmed_at__isnull=False).exists()


def status_for(user):
    device = MfaDevice.objects.filter(user=user).first()
    enabled = bool(device and device.enabled)
    remaining = MfaRecoveryCode.objects.filter(user=user, used_at__isnull=True).count() if enabled else 0
    return {
        'enabled': enabled,
        'pending_setup': bool(device and not device.enabled),
        'confirmed_at': device.confirmed_at.isoformat() if enabled else None,
        'recovery_codes_remaining': remaining,
        'methods': METHODS if enabled else [],
    }


def begin_setup(user, password):
    if not user.check_password(password or ''):
        raise _wrong_password()
    with transaction.atomic():
        device = MfaDevice.objects.select_for_update().filter(user=user).first()
        if device and device.enabled:
            raise ConflictError('Two-step verification is already on.', code='MFA_ALREADY_ENABLED')
        secret = generate_secret()
        MfaDevice.objects.update_or_create(
            user=user,
            defaults={'secret_encrypted': encrypt_secret(secret), 'confirmed_at': None, 'last_used_counter': 0},
        )
    return {'secret': secret, 'otpauth_url': otpauth_url(secret, user.email), 'digits': DIGITS, 'period': PERIOD}


def enable(request, user, code):
    with transaction.atomic():
        device = MfaDevice.objects.select_for_update().filter(user=user).first()
        if device is None:
            raise ConflictError('Start setup first.', code='MFA_SETUP_REQUIRED')
        if device.enabled:
            raise ConflictError('Two-step verification is already on.', code='MFA_ALREADY_ENABLED')
        counter = matching_counter(decrypt_secret(device.secret_encrypted), code)
        if counter is None:
            raise _invalid_code()
        device.confirmed_at = timezone.now()
        device.last_used_counter = counter
        device.save(update_fields=['confirmed_at', 'last_used_counter'])
        codes = _new_recovery_codes(user)
    _audit(request, user, 'auth.mfa_enabled', f'{user.email} turned on two-step verification.')
    return {'recovery_codes': codes, **status_for(user)}


def _check_code(user, device, *, code=None, recovery_code=None):
    """Verifies a TOTP or recovery code under the device's row lock. Returns the method used."""
    if recovery_code:
        used = MfaRecoveryCode.objects.filter(
            user=user, code_hash=_recovery_hash(user.pk, recovery_code), used_at__isnull=True
        ).update(used_at=timezone.now())
        if not used:
            raise _invalid_code()
        return 'recovery_code'
    counter = matching_counter(decrypt_secret(device.secret_encrypted), code)
    if counter is None or counter <= device.last_used_counter:
        raise _invalid_code()
    device.last_used_counter = counter
    device.save(update_fields=['last_used_counter'])
    return 'totp'


def _looks_like_totp(code):
    value = str(code or '').strip()
    return len(value) == DIGITS and value.isdigit()


def _reauthenticate(user, password, code):
    """Password plus a current code (TOTP or recovery) for sensitive changes. Returns the locked device."""
    if not user.check_password(password or ''):
        raise _wrong_password()
    device = MfaDevice.objects.select_for_update().filter(user=user, confirmed_at__isnull=False).first()
    if device is None:
        raise ConflictError('Two-step verification is off.', code='MFA_NOT_ENABLED')
    if _looks_like_totp(code):
        _check_code(user, device, code=code)
    else:
        _check_code(user, device, recovery_code=code)
    return device


def disable(request, user, password, code):
    from .sessions import current_session_id, revoke_all_sessions

    with transaction.atomic():
        device = _reauthenticate(user, password, code)
        device.delete()
        MfaRecoveryCode.objects.filter(user=user).delete()
        MfaChallenge.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        # Other devices signed in under MFA's protection; make them sign in again.
        revoke_all_sessions(user, UserSession.REVOKED_MFA_DISABLED, except_session_id=current_session_id(user))
    _audit(request, user, 'auth.mfa_disabled', f'{user.email} turned off two-step verification.')
    return status_for(user)


def regenerate_recovery_codes(request, user, password, code):
    with transaction.atomic():
        _reauthenticate(user, password, code)
        codes = _new_recovery_codes(user)
    _audit(
        request, user, 'auth.mfa_recovery_codes_regenerated', f'{user.email} generated new recovery codes.'
    )
    return {'recovery_codes': codes, **status_for(user)}


# ---------------------------------------------------------------- sign-in challenge


def create_challenge(user):
    token = secrets.token_urlsafe(32)
    challenge = MfaChallenge.objects.create(
        user=user,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=timezone.now() + CHALLENGE_TTL,
    )
    return {
        'mfa_required': True,
        'mfa_token': token,
        'methods': METHODS,
        'expires_at': challenge.expires_at.isoformat(),
    }


def verify_challenge(request, token, *, code=None, recovery_code=None):
    """Exchanges a challenge plus a valid code for a session. Wrong codes are recorded even though we raise."""
    from .login import ensure_organization_active, record_login
    from .sessions import auth_response

    if not (code or recovery_code):
        raise ValidationError('Enter the code from your authenticator app.', code='VALIDATION_ERROR')
    failure = None
    with transaction.atomic():
        challenge = (
            MfaChallenge.objects.select_for_update()
            .select_related('user')
            .filter(token_hash=hashlib.sha256(str(token or '').encode()).hexdigest())
            .first()
        )
        if challenge is None or challenge.used_at is not None or challenge.expires_at <= timezone.now():
            raise _challenge_invalid()
        user = challenge.user
        if not user.is_active:
            raise _challenge_invalid()
        ensure_organization_active(user)
        device = MfaDevice.objects.select_for_update().filter(user=user, confirmed_at__isnull=False).first()
        if device is None:
            # MFA was turned off after the password step; the password already proved it's them.
            method = 'none'
        else:
            try:
                with transaction.atomic():
                    method = _check_code(user, device, code=code, recovery_code=recovery_code)
            except AppError as exc:
                failure = exc
        if failure is not None:
            challenge.attempts += 1
            if challenge.attempts >= MAX_CHALLENGE_ATTEMPTS:
                challenge.used_at = timezone.now()
            challenge.save(update_fields=['attempts', 'used_at'])
            record_login(user, request, False, LoginEvent.REASON_WRONG_MFA)
        else:
            challenge.used_at = timezone.now()
            challenge.save(update_fields=['used_at'])
            record_login(user, request, True)
            result = auth_response(user, request)
            result['recovery_codes_remaining'] = MfaRecoveryCode.objects.filter(
                user=user, used_at__isnull=True
            ).count()
            result['method'] = method
    if failure is None:
        if method == 'recovery_code':
            _audit(request, user, 'auth.mfa_recovery_code_used', f'{user.email} signed in with a recovery code.')
        return user, result
    if challenge.used_at is not None:
        raise ThrottledError('Too many wrong codes. Sign in again.', code='TOO_MANY_ATTEMPTS')
    raise failure
