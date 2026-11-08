"""Password sign-in with account lockout, sign-in history and the two-step verification hand-off.

Lockout: MAX_FAILED_LOGINS wrong passwords or wrong two-step codes within LOCKOUT_WINDOW
(counted from the last successful sign-in, if more recent) lock the account for the rest of
the window. Unknown addresses get the same treatment via a cache counter, so the response
never reveals whether an account exists.

Every code path that hands out a session for an existing account goes through
``complete_sign_in`` so two-step verification can't be skipped (e.g. via password reset).
"""

import hashlib
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from hr_app_backend.utils.errors import AuthenticationError, PermissionDeniedError, ValidationError
from hr_app_backend.utils.throttles import ThrottledError

from ..models import LoginEvent, Organization
from . import mfa
from .devices import client_info
from .sessions import auth_response
from .validation import normalize_email

logger = logging.getLogger(__name__)
User = get_user_model()

MAX_FAILED_LOGINS = 5
LOCKOUT_WINDOW = timedelta(minutes=15)
LOCKOUT_SECONDS = int(LOCKOUT_WINDOW.total_seconds())
LOGIN_HISTORY_LIMIT = 50


def record_login(user, request, success, reason=''):
    info = client_info(request)
    LoginEvent.objects.create(
        user=user,
        success=success,
        reason=reason,
        device=info['device'],
        browser=info['browser'],
        ip_address=info['ip_address'],
    )


def _too_many_attempts():
    return ThrottledError(
        'Too many failed sign-in attempts. Try again in 15 minutes or reset your password.',
        code='TOO_MANY_ATTEMPTS',
        extra={'retry_after': LOCKOUT_SECONDS},
    )


def _invalid_credentials():
    return AuthenticationError('Invalid email or password.', code='INVALID_CREDENTIALS')


def _unknown_email_failures(email):
    key = f'auth:loginfail:{hashlib.sha256(email.encode()).hexdigest()}'
    cache.add(key, 0, LOCKOUT_SECONDS)
    try:
        return cache.incr(key) or 0
    except ValueError:  # expired between add and incr
        cache.set(key, 1, LOCKOUT_SECONDS)
        return 1


def recent_failures(user, now=None):
    now = now or timezone.now()
    since = now - LOCKOUT_WINDOW
    last_success = (
        user.login_events.filter(success=True, created_at__gte=since).values_list('created_at', flat=True).first()
    )
    return user.login_events.filter(
        success=False,
        reason__in=[LoginEvent.REASON_WRONG_PASSWORD, LoginEvent.REASON_WRONG_MFA],
        created_at__gte=last_success or since,
    ).count()


def ensure_organization_active(user):
    """Members of a suspended company can't sign in (checked after the password, so it leaks nothing)."""
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    if organization is not None and organization.status == Organization.STATUS_SUSPENDED:
        message = (
            f'Your company account has been suspended. Reason: {organization.suspended_reason}'
            if organization.suspended_reason
            else 'Your company account has been suspended.'
        )
        raise PermissionDeniedError(message, code='ORGANIZATION_SUSPENDED')


def complete_sign_in(user, request):
    """A session, or an MFA challenge when the account has two-step verification on."""
    ensure_organization_active(user)
    if mfa.enabled_for(user):
        return mfa.create_challenge(user)
    return auth_response(user, request)


def login(request, data):
    """Returns ``(user, result)``. ``result`` is a session or an MFA challenge (``mfa_required``)."""
    email = normalize_email(data.get('email'))
    password = data.get('password') or ''
    if not email or not password:
        raise ValidationError('Email and password are required.')

    user = User.objects.filter(email=email).first()
    if user is None:
        make_password(password)  # spend the same time as a real check so timing doesn't reveal the account
        if _unknown_email_failures(email) > MAX_FAILED_LOGINS:
            raise _too_many_attempts()
        raise _invalid_credentials()

    outcome = None
    with transaction.atomic():
        # Serialise sign-ins per account so parallel guesses can't slip past the lockout count.
        user = User.objects.select_for_update().get(pk=user.pk)
        if recent_failures(user) >= MAX_FAILED_LOGINS:
            outcome = LoginEvent.REASON_LOCKED
        elif not user.check_password(password):
            outcome = LoginEvent.REASON_WRONG_PASSWORD
        elif not user.is_active:
            outcome = LoginEvent.REASON_DISABLED
        needs_mfa = outcome is None and mfa.enabled_for(user)
        # With two-step verification the sign-in only counts once the code is checked.
        if not needs_mfa:
            record_login(user, request, outcome is None, outcome or '')

    if outcome == LoginEvent.REASON_LOCKED:
        logger.info('login_locked_out user=%s', user.pk)
        raise _too_many_attempts()
    if outcome is not None:
        # Wrong password and disabled accounts look the same from outside.
        raise _invalid_credentials()

    user = User.objects.select_related('profile__organization').get(pk=user.pk)
    ensure_organization_active(user)
    if needs_mfa:
        return user, mfa.create_challenge(user)
    return user, auth_response(user, request)


def serialize_login_event(event):
    return {
        'id': str(event.pk),
        'created_at': event.created_at.isoformat(),
        'success': event.success,
        'reason': event.reason,
        'device': event.device,
        'browser': event.browser,
        'ip_address': event.ip_address,
    }


def login_history(user, limit=LOGIN_HISTORY_LIMIT):
    return [serialize_login_event(event) for event in user.login_events.all()[:limit]]
