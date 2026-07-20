from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError
from hr_app_backend.utils.idempotency import idempotent
from hr_app_backend.utils.pagination import paginated_data
from hr_app_backend.utils.throttles import throttle_view

from ..serializers import (
    employee_payload,
    serialize_employee,
    serialize_my_employee_profile,
)
from ..services import (
    create_employee,
    delete_employee,
    get_employee,
    get_my_employee,
    list_employees,
    my_employee_profile,
    update_employee,
    update_my_employee,
)
from .helpers import require_user


@csrf_exempt
@require_http_methods(['GET', 'PATCH'])
def my_employee_view(request):
    """View or edit the signed-in user's own employee profile (staff self-service)."""
    try:
        user = require_user(request)
        if request.method == 'GET':
            employee = get_my_employee(user)
            profile = my_employee_profile(employee)
            return JsonResponse({'success': True, 'data': serialize_my_employee_profile(profile)})

        payload = employee_payload(parse_json_body(request), partial=True)
        employee = update_my_employee(user, payload)
        profile = my_employee_profile(employee)
        return JsonResponse({'success': True, 'data': serialize_my_employee_profile(profile)})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
@throttle_view('employees:write', '120/min')
@idempotent('employees:create')
def employees_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            employees = list_employees(
                user,
                search=request.GET.get('search'),
                department=request.GET.get('department'),
                status=request.GET.get('status'),
            )
            return JsonResponse({
                'success': True,
                'data': paginated_data(request, employees, serialize_employee, key='employees'),
            })

        payload = employee_payload(parse_json_body(request))
        employee = create_employee(user, payload)
        return JsonResponse(
            {'success': True, 'data': {'employee': serialize_employee(employee)}},
            status=201,
        )
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def employee_detail_view(request, employee_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            employee = get_employee(user, employee_pk)
            return JsonResponse({'success': True, 'data': {'employee': serialize_employee(employee)}})

        if request.method == 'DELETE':
            delete_employee(user, employee_pk)
            return JsonResponse({'success': True, 'message': 'Employee deleted successfully.'})

        payload = employee_payload(parse_json_body(request), partial=True)
        employee = update_employee(user, employee_pk, payload)
        return JsonResponse({'success': True, 'data': {'employee': serialize_employee(employee)}})
    except AppError as exc:
        return error_response(exc)
