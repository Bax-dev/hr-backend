from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError
from hr_app_backend.utils.throttles import throttle_view

from ..serializers import serialize_s3_config
from ..services import get_s3_settings, test_s3_connection, update_s3_settings
from .helpers import require_user


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'PATCH'])
def s3_settings_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            config = get_s3_settings(user)
        else:
            config = update_s3_settings(user, parse_json_body(request), request=request)
        return JsonResponse(serialize_s3_config(config))
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['POST'])
@throttle_view('file_management:s3-test', '10/min')
def s3_settings_test_view(request):
    try:
        user = require_user(request)
        test_s3_connection(user)
        return JsonResponse({'success': True, 'data': {'connected': True}})
    except AppError as exc:
        return error_response(exc)
