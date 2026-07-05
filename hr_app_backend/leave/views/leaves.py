from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError

from ..serializers import leave_payload, serialize_leave
from ..services import create_leave, get_leave, list_leaves, update_leave
from .helpers import require_user


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def leaves_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            leaves = list_leaves(
                user,
                status=request.GET.get('status'),
                employee_id=request.GET.get('employee_id') or request.GET.get('employeeId'),
            )
            return JsonResponse({'success': True, 'data': {'leaves': [serialize_leave(leave) for leave in leaves]}})

        payload = leave_payload(parse_json_body(request))
        leave = create_leave(user, payload)
        return JsonResponse({'success': True, 'data': {'leave': serialize_leave(leave)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'PATCH'])
def leave_detail_view(request, leave_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            leave = get_leave(user, leave_pk)
            return JsonResponse({'success': True, 'data': {'leave': serialize_leave(leave)}})

        payload = leave_payload(parse_json_body(request), partial=True)
        leave = update_leave(user, leave_pk, payload)
        return JsonResponse({'success': True, 'data': {'leave': serialize_leave(leave)}})
    except AppError as exc:
        return error_response(exc)
