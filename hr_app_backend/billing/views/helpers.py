from hr_app_backend.authentication.services import get_user_by_token
from hr_app_backend.authentication.views.helpers import error_response, load_json, token_from_request
from hr_app_backend.utils.errors import AuthenticationError


__all__ = [
    'error_response',
    'load_json',
    'require_authenticated_user',
]


def require_authenticated_user(request):
    user = get_user_by_token(token_from_request(request))
    if user is None:
        raise AuthenticationError('Authentication credentials were not provided or are invalid.')
    return user
