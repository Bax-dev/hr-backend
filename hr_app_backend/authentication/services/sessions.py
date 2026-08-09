import json
import secrets

from django.contrib.auth import get_user_model

from hr_app_backend.third_parties import get_redis_client

from ..serializers import serialize_user

User = get_user_model()

SESSION_EXPIRY_SECONDS = 7 * 24 * 60 * 60
SESSION_NAMESPACE = 'auth:session'


def _build_session_payload(user):
    return json.dumps({'user_id': str(user.id)})


def _session_key(token):
    return f'{SESSION_NAMESPACE}:{token}'


def _user_sessions_key(user_id):
    return f'{SESSION_NAMESPACE}:user:{user_id}'


def create_session(user):
    token = secrets.token_urlsafe(32)
    client = get_redis_client()
    client.setex(_session_key(token), SESSION_EXPIRY_SECONDS, _build_session_payload(user))
    user_sessions_key = _user_sessions_key(user.id)
    client.sadd(user_sessions_key, token)
    client.expire(user_sessions_key, SESSION_EXPIRY_SECONDS)
    return token


def get_user_by_token(token):
    if not token:
        return None
    payload = get_redis_client().get(_session_key(token))
    if not payload:
        return None
    data = json.loads(payload)
    try:
        user = User.objects.select_related('profile__organization').get(id=data['user_id'])
    except User.DoesNotExist:
        return None
    # Belt-and-suspenders: a deactivated account (e.g. deleted staff/self-deleted
    # user) should fail auth immediately even if a stray session token survives.
    if not user.is_active:
        return None
    return user


def destroy_session(token):
    if not token:
        return
    client = get_redis_client()
    payload = client.get(_session_key(token))
    client.delete(_session_key(token))
    if payload:
        data = json.loads(payload)
        client.srem(_user_sessions_key(data['user_id']), token)


def destroy_all_sessions_for_user(user_id):
    client = get_redis_client()
    user_sessions_key = _user_sessions_key(user_id)
    tokens = client.smembers(user_sessions_key)
    if tokens:
        client.delete(*(_session_key(token) for token in tokens))
    client.delete(user_sessions_key)


def auth_response(user):
    token = create_session(user)
    return {
        'token': token,
        'user': serialize_user(user),
    }
