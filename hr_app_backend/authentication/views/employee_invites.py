from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from hr_app_backend.utils.errors import AppError
from hr_app_backend.utils.throttles import throttle_view

from ..services import accept_employee_invite, auth_response, employee_invite_details
from .helpers import error_response, load_json


@require_GET
@throttle_view('auth:employee-invite:read', '30/min')
def employee_invite_view(request):
    try:
        return JsonResponse({'success': True, 'data': employee_invite_details(request.GET.get('token', ''))})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:employee-invite:accept', '10/min')
def accept_employee_invite_view(request):
    try:
        user = accept_employee_invite(load_json(request))
        return JsonResponse({'success': True, 'data': auth_response(user)})
    except AppError as exc:
        return error_response(exc)
