from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError

from ..serializers import employee_payload, serialize_employee
from ..services import (
    create_employee,
    delete_employee,
    get_employee,
    list_employees,
    update_employee,
)
from .helpers import require_user


@csrf_exempt
@require_http_methods(['GET', 'POST'])
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
                'data': {'employees': [serialize_employee(employee) for employee in employees]},
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
