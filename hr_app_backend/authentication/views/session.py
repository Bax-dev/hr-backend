from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from hr_app_backend.utils.errors import AppError, AuthenticationError
from hr_app_backend.utils.throttles import throttle, throttle_view

from ..serializers import serialize_user
from ..serializers import change_password_payload, login_payload
from ..services import auth_response, change_password, destroy_session, get_user_by_token, login_user
from .helpers import error_response, load_json, token_from_request


@csrf_exempt
@require_POST
@throttle_view('auth:login:ip', '20/min')
def login_view(request):
    try:
        payload = login_payload(load_json(request))
        # The per-IP limit above does not stop credential stuffing spread across
        # many IPs, so also cap attempts against a single account.
        throttle(request, scope='auth:login:account', rate='10/min', ident=payload['email'].lower())
        user = login_user(payload)
        return JsonResponse({'success': True, 'data': auth_response(user)})
    except AppError as exc:
        return error_response(exc)


@require_GET
def me_view(request):
    token = token_from_request(request)
    user = get_user_by_token(token)
    if user is None:
        return error_response(AuthenticationError('Authentication credentials were not provided or are invalid.'))
    return JsonResponse({'success': True, 'data': {'user': serialize_user(user)}})


@csrf_exempt
@require_POST
def logout_view(request):
    destroy_session(token_from_request(request))
    return JsonResponse({'success': True, 'message': 'Logged out successfully.'})


@csrf_exempt
@require_POST
@throttle_view('auth:change-password', '10/min')
def change_password_view(request):
    try:
        token = token_from_request(request)
        user = get_user_by_token(token)
        if user is None:
            raise AuthenticationError('Authentication credentials were not provided or are invalid.')
        updated_user = change_password(user, change_password_payload(load_json(request)))
        return JsonResponse({'success': True, 'data': {'user': serialize_user(updated_user)}})
    except AppError as exc:
        return error_response(exc)
