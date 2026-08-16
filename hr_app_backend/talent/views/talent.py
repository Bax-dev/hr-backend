from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.employees.views.helpers import require_user
from hr_app_backend.utils.errors import AppError

from ..serializers import (
    offboarding_payload,
    onboarding_payload,
    performance_payload,
    serialize_offboarding,
    serialize_onboarding,
    serialize_performance,
)
from ..services import (
    create_offboarding,
    create_onboarding,
    create_performance,
    delete_offboarding,
    delete_onboarding,
    delete_performance,
    get_offboarding,
    get_onboarding,
    get_performance,
    list_offboarding,
    list_onboarding,
    list_performance,
    talent_summary,
    update_offboarding,
    update_onboarding,
    update_performance,
)
from .helpers import collection_response, detail_response


@require_http_methods(['GET'])
def talent_summary_view(request):
    try:
        user = require_user(request)
        return JsonResponse({'success': True, 'data': talent_summary(user)})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def onboarding_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            return collection_response(request, 'records', list_onboarding(user, search=request.GET.get('search')), serialize_onboarding)
        record = create_onboarding(user, onboarding_payload(parse_json_body(request)))
        return detail_response('record', record, serialize_onboarding, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def onboarding_detail_view(request, record_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            return detail_response('record', get_onboarding(user, record_pk), serialize_onboarding)
        if request.method == 'DELETE':
            delete_onboarding(user, record_pk)
            return JsonResponse({'success': True, 'message': 'Onboarding plan deleted successfully.'})
        record = update_onboarding(user, record_pk, onboarding_payload(parse_json_body(request), partial=True))
        return detail_response('record', record, serialize_onboarding)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def performance_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            return collection_response(request, 'records', list_performance(user, search=request.GET.get('search')), serialize_performance)
        record = create_performance(user, performance_payload(parse_json_body(request)))
        return detail_response('record', record, serialize_performance, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def performance_detail_view(request, record_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            return detail_response('record', get_performance(user, record_pk), serialize_performance)
        if request.method == 'DELETE':
            delete_performance(user, record_pk)
            return JsonResponse({'success': True, 'message': 'Performance review deleted successfully.'})
        record = update_performance(user, record_pk, performance_payload(parse_json_body(request), partial=True))
        return detail_response('record', record, serialize_performance)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def offboarding_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            return collection_response(request, 'records', list_offboarding(user, search=request.GET.get('search')), serialize_offboarding)
        record = create_offboarding(user, offboarding_payload(parse_json_body(request)))
        return detail_response('record', record, serialize_offboarding, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def offboarding_detail_view(request, record_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            return detail_response('record', get_offboarding(user, record_pk), serialize_offboarding)
        if request.method == 'DELETE':
            delete_offboarding(user, record_pk)
            return JsonResponse({'success': True, 'message': 'Offboarding plan deleted successfully.'})
        record = update_offboarding(user, record_pk, offboarding_payload(parse_json_body(request), partial=True))
        return detail_response('record', record, serialize_offboarding)
    except AppError as exc:
        return error_response(exc)
