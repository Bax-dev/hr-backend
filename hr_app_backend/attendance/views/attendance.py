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
    office_location_payload,
    punch_payload,
    serialize_attendance_record,
    serialize_office_location,
)
from ..services import (
    check_in,
    check_out,
    create_location,
    deactivate_location,
    get_location,
    list_attendance,
    list_locations,
    update_location,
)
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
        return JsonResponse({
            'success': True,
            'data': paginated_data(request, records, serialize_attendance_record, key='records'),
        })
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def locations_view(request):
    try:
        user = require_user(request)
        if request.method == 'POST':
            payload = office_location_payload(parse_json_body(request))
            location = create_location(user, payload)
            return JsonResponse(
                {'success': True, 'data': {'location': serialize_office_location(location)}}, status=201
            )
        locations = list_locations(user)
        return JsonResponse(
            {'success': True, 'data': {'locations': [serialize_office_location(location) for location in locations]}}
        )
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def location_detail_view(request, location_pk):
    try:
        user = require_user(request)
        if request.method == 'DELETE':
            deactivate_location(user, location_pk)
            return JsonResponse({'success': True, 'message': 'Location removed successfully.'})
        if request.method == 'GET':
            location = get_location(user, location_pk)
        else:
            payload = office_location_payload(parse_json_body(request), partial=True)
            location = update_location(user, location_pk, payload)
        return JsonResponse({'success': True, 'data': {'location': serialize_office_location(location)}})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['POST'])
@throttle_view('attendance:punch', '30/min')
# A double-tap on a flaky connection must not create a second punch.
@idempotent('attendance:check-in')
def check_in_view(request):
    try:
        user = require_user(request)
        record = check_in(user, punch_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'record': serialize_attendance_record(record)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['POST'])
@throttle_view('attendance:punch', '30/min')
@idempotent('attendance:check-out')
def check_out_view(request):
    try:
        user = require_user(request)
        record = check_out(user, punch_payload(parse_json_body(request)))
        return JsonResponse({'success': True, 'data': {'record': serialize_attendance_record(record)}})
    except AppError as exc:
        return error_response(exc)
