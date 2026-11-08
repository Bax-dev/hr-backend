"""Bearer-token sessions.

Each sign-in creates a ``UserSession`` row. The client holds an opaque random token; only
its sha256 is stored, so a database leak does not leak usable tokens. Revoking a row
(logout, "sign out other devices", password change/reset, MFA disabled) ends that token on
its next request.

Tokens issued before sessions moved to the database live in Redis under
``auth:session:<raw token>``. They keep working: the first request that presents one
converts it into a ``UserSession`` row and deletes the Redis key, so nobody is signed out
by the deploy.
"""

import hashlib
import json
import logging
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from hr_app_backend.third_parties import get_redis_client

from ..models import UserSession
from ..serializers import serialize_user
from .devices import client_info

logger = logging.getLogger(__name__)
User = get_user_model()

SESSION_EXPIRY_SECONDS = 7 * 24 * 60 * 60
SESSION_LIFETIME = timedelta(seconds=SESSION_EXPIRY_SECONDS)
TOUCH_EVERY = timedelta(minutes=1)
LEGACY_SESSION_NAMESPACE = 'auth:session'


def _legacy_user_index_key(user_id):
    # Per-user set of legacy Redis tokens (written by the pre-database session store).
    return f'{LEGACY_SESSION_NAMESPACE}:user:{user_id}'


def hash_token(token):
    return hashlib.sha256(str(token).encode('utf-8')).hexdigest()


def create_session(user, request=None):
    token = secrets.token_urlsafe(32)
    UserSession.objects.create(
        user=user,
        token_hash=hash_token(token),
        expires_at=timezone.now() + SESSION_LIFETIME,
        **client_info(request),
    )
    return token


def _session_queryset():
    return UserSession.objects.select_related('user__profile__organization')


def _adopt_legacy_token(token):
    """Turn a pre-migration Redis session into a database session (once)."""
    key = f'{LEGACY_SESSION_NAMESPACE}:{token}'
    try:
        client = get_redis_client()
        payload = client.get(key)
        if not payload:
            return None
        ttl = client.ttl(key)
        user_id = json.loads(payload)['user_id']
    except Exception:  # Redis down or malformed payload: treat as signed out
        logger.warning('legacy session lookup failed', exc_info=True)
        return None
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return None
    remaining = timedelta(seconds=ttl) if ttl and ttl > 0 else SESSION_LIFETIME
    session, _ = UserSession.objects.get_or_create(
        token_hash=hash_token(token),
        defaults={'user': user, 'expires_at': timezone.now() + remaining, 'device': 'Unknown device'},
    )
    try:
        client.delete(key)
        client.srem(_legacy_user_index_key(user_id), token)
    except Exception:
        pass
    return _session_queryset().get(pk=session.pk)


def get_session_by_token(token):
    """The live session for ``token``, or None. Refreshes ``last_active_at`` at most once a minute."""
    if not token:
        return None
    session = _session_queryset().filter(token_hash=hash_token(token)).first()
    if session is None:
        session = _adopt_legacy_token(token)
        if session is None:
            return None
    now = timezone.now()
    if session.revoked_at is not None or session.expires_at <= now:
        return None
    if not session.user.is_active:
        revoke_all_sessions(session.user, UserSession.REVOKED_DISABLED)
        return None
    if now - session.last_active_at >= TOUCH_EVERY:
        # Conditional update so concurrent requests write at most once per minute.
        UserSession.objects.filter(pk=session.pk, last_active_at__lte=now - TOUCH_EVERY).update(last_active_at=now)
        session.last_active_at = now
    return session


def get_user_by_token(token):
    session = get_session_by_token(token)
    if session is None:
        return None
    user = session.user
    # Lets views find the session that authenticated this request (e.g. "this device").
    user.auth_session = session
    return user


def current_session_id(user):
    session = getattr(user, 'auth_session', None)
    return session.pk if session is not None else None


def destroy_session(token):
    if not token:
        return
    UserSession.objects.filter(token_hash=hash_token(token), revoked_at__isnull=True).update(
        revoked_at=timezone.now(), revoked_reason=UserSession.REVOKED_LOGOUT
    )
    try:
        get_redis_client().delete(f'{LEGACY_SESSION_NAMESPACE}:{token}')
    except Exception:
        pass


def active_sessions(user):
    return UserSession.objects.filter(user=user, revoked_at__isnull=True, expires_at__gt=timezone.now())


def revoke_all_sessions(user, reason, *, except_session_id=None):
    sessions = active_sessions(user)
    if except_session_id is not None:
        sessions = sessions.exclude(pk=except_session_id)
    return sessions.update(revoked_at=timezone.now(), revoked_reason=reason)


def destroy_all_sessions_for_user(user_id, reason=UserSession.REVOKED_DISABLED):
    """Revoke every session for a user (account deleted/deactivated), including legacy Redis tokens."""
    count = UserSession.objects.filter(user_id=user_id, revoked_at__isnull=True).update(
        revoked_at=timezone.now(), revoked_reason=reason
    )
    try:
        client = get_redis_client()
        index_key = _legacy_user_index_key(user_id)
        tokens = client.smembers(index_key)
        if tokens:
            client.delete(*(f'{LEGACY_SESSION_NAMESPACE}:{token}' for token in tokens))
        client.delete(index_key)
    except Exception:
        logger.warning('legacy session cleanup failed for user %s', user_id, exc_info=True)
    return count


def revoke_session(user, session_id, reason=UserSession.REVOKED_BY_USER):
    return active_sessions(user).filter(pk=session_id).update(revoked_at=timezone.now(), revoked_reason=reason)


def serialize_session(session, current_id=None):
    return {
        'id': str(session.pk),
        'device': session.device,
        'browser': session.browser,
        'ip_address': session.ip_address,
        'created_at': session.created_at.isoformat(),
        'last_active_at': session.last_active_at.isoformat(),
        'expires_at': session.expires_at.isoformat(),
        'current': current_id is not None and session.pk == current_id,
    }


def auth_response(user, request=None):
    token = create_session(user, request)
    return {
        'token': token,
        'user': serialize_user(user),
    }
