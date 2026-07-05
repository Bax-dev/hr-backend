from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from hr_app_backend.utils.errors import AppError

from ..serializers import company_signup_payload, individual_signup_payload
from ..services import auth_response, register_company, register_individual
from .helpers import error_response, load_json


@csrf_exempt
@require_POST
def signup_company_view(request):
    try:
        user = register_company(company_signup_payload(load_json(request)))
        return JsonResponse({'success': True, 'data': auth_response(user)}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
def signup_individual_view(request):
    try:
        user = register_individual(individual_signup_payload(load_json(request)))
        return JsonResponse({'success': True, 'data': auth_response(user)}, status=201)
    except AppError as exc:
        return error_response(exc)
