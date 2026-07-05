from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError

from ..serializers import punch_payload, serialize_attendance_record, serialize_office_location
from ..services import check_in, check_out, list_attendance, list_locations
from .helpers import require_user


@csrf_exempt
@require_http_methods(['GET'])
def attendance_view(request):
    try:
        user = require_user(request)
        records = list_attendance(
            user,
            date=request.GET.get('date'),
            status=request.GET.get('status'),
            employee_id=request.GET.get('employee_id') or request.GET.get('employeeId'),
        )
        return JsonResponse(
            {'success': True, 'data': {'records': [serialize_attendance_record(record) for record in records]}}
        )
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET'])
def locations_view(request):
    try:
        user = require_user(request)
        locations = list_locations(user)
        return JsonResponse(
            {'success': True, 'data': {'locations': [serialize_office_location(location) for location in locations]}}
        )
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['POST'])
def check_in_view(request):
    try:
        user = require_user(request)
        record = check_in(user, punch_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'record': serialize_attendance_record(record)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['POST'])
def check_out_view(request):
    try:
        user = require_user(request)
        record = check_out(user, punch_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'record': serialize_attendance_record(record)}})
    except AppError as exc:
        return error_response(exc)
