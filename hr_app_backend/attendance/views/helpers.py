from hr_app_backend.authentication.services import get_user_by_token
from hr_app_backend.authentication.views.helpers import token_from_request
from hr_app_backend.utils.errors import AuthenticationError


def require_user(request):
    user = get_user_by_token(token_from_request(request))
    if user is None:
        raise AuthenticationError('Authentication credentials were not provided or are invalid.')
    return user
