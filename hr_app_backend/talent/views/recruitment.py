from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.employees.views.helpers import require_user
from hr_app_backend.utils.errors import AppError

from ..serializers import job_payload, serialize_job
from ..services import create_job, delete_job, get_public_job, list_jobs, update_job


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def jobs_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            return JsonResponse([serialize_job(job) for job in list_jobs(user)], safe=False)
        job = create_job(user, job_payload(parse_json_body(request)))
        return JsonResponse(serialize_job(job), status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['PATCH', 'DELETE'])
def job_detail_view(request, job_id):
    try:
        user = require_user(request)
        if request.method == 'DELETE':
            delete_job(user, job_id)
            return JsonResponse(None, safe=False, status=204)
        job = update_job(user, job_id, job_payload(parse_json_body(request), partial=True))
        return JsonResponse(serialize_job(job))
    except AppError as exc:
        return error_response(exc)


@require_http_methods(['GET'])
def public_job_detail_view(request, job_id):
    """Unauthenticated lookup for the public careers share link."""
    try:
        job = get_public_job(job_id)
        return JsonResponse(serialize_job(job))
    except AppError as exc:
        return error_response(exc)
