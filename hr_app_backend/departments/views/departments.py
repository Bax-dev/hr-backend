from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError

from ..serializers import department_payload, serialize_department
from ..services import (
    create_department,
    delete_department,
    get_department,
    list_departments,
    update_department,
)
from .helpers import require_user


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def departments_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            departments, counts = list_departments(user)
            return JsonResponse([
                serialize_department(department, counts.get(department.name.strip().lower(), 0))
                for department in departments
            ], safe=False)

        payload = department_payload(parse_json_body(request))
        department = create_department(user, payload)
        return JsonResponse(serialize_department(department, 0), status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def department_detail_view(request, department_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            department = get_department(user, department_pk)
            return JsonResponse(serialize_department(department, 0))

        if request.method == 'DELETE':
            delete_department(user, department_pk)
            return JsonResponse(None, safe=False, status=204)

        payload = department_payload(parse_json_body(request), partial=True)
        department = update_department(user, department_pk, payload)
        return JsonResponse(serialize_department(department, 0))
    except AppError as exc:
        return error_response(exc)
