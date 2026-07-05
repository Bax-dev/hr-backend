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


def create_session(user):
    token = secrets.token_urlsafe(32)
    get_redis_client().setex(_session_key(token), SESSION_EXPIRY_SECONDS, _build_session_payload(user))
    return token


def get_user_by_token(token):
    if not token:
        return None
    payload = get_redis_client().get(_session_key(token))
    if not payload:
        return None
    data = json.loads(payload)
    try:
        return User.objects.select_related('profile__organization').get(id=data['user_id'])
    except User.DoesNotExist:
        return None


def destroy_session(token):
    if token:
        get_redis_client().delete(_session_key(token))


def auth_response(user):
    token = create_session(user)
    return {
        'token': token,
        'user': serialize_user(user),
    }
