from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from hr_app_backend.utils.errors import AppError

from ..serializers import forgot_password_payload, reset_password_payload, verify_otp_payload
from ..services import auth_response, reset_password, send_password_reset_otp, verify_password_reset_otp
from .helpers import error_response, load_json


@csrf_exempt
@require_POST
def forgot_password_view(request):
    try:
        payload = forgot_password_payload(load_json(request))
        result = send_password_reset_otp(payload['email'])
        return JsonResponse({'success': True, 'data': result})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
def verify_otp_view(request):
    try:
        payload = verify_otp_payload(load_json(request))
        result = verify_password_reset_otp(payload['email'], payload['otp'])
        return JsonResponse({'success': True, 'data': result})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
def reset_password_view(request):
    try:
        payload = reset_password_payload(load_json(request))
        user = reset_password(
            payload['email'],
            payload['otp'],
            payload['password'],
            payload['confirm_password'],
        )
        return JsonResponse({'success': True, 'data': auth_response(user)})
    except AppError as exc:
        return error_response(exc)
