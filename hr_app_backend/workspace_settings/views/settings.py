from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response, token_from_request
from hr_app_backend.authentication.services import get_user_by_token
from hr_app_backend.utils.errors import AppError, AuthenticationError

from ..serializers import (
    serialize_attendance_policy,
    serialize_company_profile,
    serialize_security_settings,
)
from ..services import (
    get_settings,
    update_attendance_policy,
    update_company_profile,
    update_security_settings,
)


def _require_user(request):
    user = get_user_by_token(token_from_request(request))
    if user is None:
        raise AuthenticationError('Authentication credentials were not provided or are invalid.')
    return user


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'PATCH'])
def company_view(request):
    try:
        user = _require_user(request)
        if request.method == 'GET':
            organization, settings = get_settings(user)
        else:
            organization, settings = update_company_profile(user, parse_json_body(request))
        return JsonResponse(
            {'success': True, 'data': {'company': serialize_company_profile(organization, settings)}}
        )
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'PATCH'])
def attendance_policy_view(request):
    try:
        user = _require_user(request)
        if request.method == 'GET':
            _, settings = get_settings(user)
        else:
            settings = update_attendance_policy(user, parse_json_body(request))
        return JsonResponse(
            {'success': True, 'data': {'policy': serialize_attendance_policy(settings)}}
        )
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'PATCH'])
def security_view(request):
    try:
        user = _require_user(request)
        if request.method == 'GET':
            _, settings = get_settings(user)
        else:
            settings = update_security_settings(user, parse_json_body(request))
        return JsonResponse(
            {'success': True, 'data': {'security': serialize_security_settings(settings)}}
        )
    except AppError as exc:
        return error_response(exc)
