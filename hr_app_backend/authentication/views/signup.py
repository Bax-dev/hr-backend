from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from hr_app_backend.utils.errors import AppError
from hr_app_backend.utils.idempotency import idempotent
from hr_app_backend.utils.throttles import throttle, throttle_view

from ..serializers import company_signup_payload, forgot_password_payload, individual_signup_payload, verify_otp_payload
from ..services import auth_response, register_company, register_individual, resend_signup_otp, verify_signup_otp
from .helpers import error_response, load_json


@csrf_exempt
@require_POST
@throttle_view('auth:signup', '5/min')
@idempotent('auth:signup:company')
def signup_company_view(request):
    try:
        user = register_company(company_signup_payload(load_json(request)))
        return JsonResponse({'success': True, 'data': {'email': user.email, 'expires_in': 600}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:signup', '5/min')
@idempotent('auth:signup:individual')
def signup_individual_view(request):
    try:
        user = register_individual(individual_signup_payload(load_json(request)))
        return JsonResponse({'success': True, 'data': {'email': user.email, 'expires_in': 600}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:verify-signup-otp:ip', '20/min')
def verify_signup_otp_view(request):
    try:
        payload = verify_otp_payload(load_json(request))
        # A short OTP is guessable, so the per-account limit is the real control.
        throttle(request, scope='auth:verify-signup-otp:account', rate='5/min', ident=payload['email'].lower())
        user = verify_signup_otp(payload['email'], payload['otp'])
        return JsonResponse({'success': True, 'data': auth_response(user)})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:resend-signup-otp:ip', '5/min')
def resend_signup_otp_view(request):
    try:
        payload = forgot_password_payload(load_json(request))
        throttle(request, scope='auth:resend-signup-otp:account', rate='3/min', ident=payload['email'].lower())
        result = resend_signup_otp(payload['email'])
        return JsonResponse({'success': True, 'data': result})
    except AppError as exc:
        return error_response(exc)
