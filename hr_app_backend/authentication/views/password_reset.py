from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from hr_app_backend.utils.errors import AppError
from hr_app_backend.utils.throttles import throttle, throttle_view

from ..serializers import forgot_password_payload, reset_password_payload, verify_otp_payload
from ..services import auth_response, reset_password, send_password_reset_otp, verify_password_reset_otp
from .helpers import error_response, load_json, session_json_response


@csrf_exempt
@require_POST
@throttle_view('auth:forgot-password:ip', '10/min')
def forgot_password_view(request):
    try:
        payload = forgot_password_payload(load_json(request))
        # Cap per address as well, so one inbox cannot be flooded with OTP mail
        # by an attacker rotating source IPs.
        throttle(request, scope='auth:forgot-password:account', rate='3/min', ident=payload['email'].lower())
        result = send_password_reset_otp(payload['email'])
        return JsonResponse({'success': True, 'data': result})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:verify-otp:ip', '20/min')
def verify_otp_view(request):
    try:
        payload = verify_otp_payload(load_json(request))
        # A short OTP is guessable, so the per-account limit is the real control.
        throttle(request, scope='auth:verify-otp:account', rate='5/min', ident=payload['email'].lower())
        result = verify_password_reset_otp(payload['email'], payload['otp'])
        return JsonResponse({'success': True, 'data': result})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:reset-password:ip', '20/min')
def reset_password_view(request):
    try:
        payload = reset_password_payload(load_json(request))
        throttle(request, scope='auth:reset-password:account', rate='5/min', ident=payload['email'].lower())
        user = reset_password(
            payload['email'],
            payload['otp'],
            payload['password'],
            payload['confirm_password'],
        )
        return session_json_response(auth_response(user))
    except AppError as exc:
        return error_response(exc)
