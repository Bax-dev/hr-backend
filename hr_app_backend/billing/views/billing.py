from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from hr_app_backend.utils.errors import AppError
from hr_app_backend.utils.idempotency import idempotent
from hr_app_backend.utils.throttles import throttle_view

from ..serializers import initialize_subscription_payload, serialize_subscription, verify_subscription_payload
from ..services import (
    initialize_paid_signup_checkout,
    initialize_subscription_payment,
    verify_paid_signup_checkout,
    verify_subscription_payment,
)
from hr_app_backend.authentication.views.helpers import set_session_cookie

from .helpers import error_response, load_json, require_authenticated_user


@csrf_exempt
@require_POST
@throttle_view('billing:initialize', '20/min')
# A retried checkout must not open a second payment session. Flip this to
# required=True once every client is known to send the header — doing so now
# would reject in-flight builds that predate it.
@idempotent('billing:initialize')
def initialize_subscription_payment_view(request):
    try:
        user = require_authenticated_user(request)
        payload = initialize_subscription_payload(load_json(request))
        subscription = initialize_subscription_payment(user, payload)
        return JsonResponse(
            {
                'success': True,
                'data': {
                    'subscription': serialize_subscription(subscription),
                    'checkout_url': subscription.payment_url,
                    'access_code': subscription.access_code,
                },
            },
            status=201,
        )
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('billing:verify', '30/min')
@idempotent('billing:verify')
def verify_subscription_payment_view(request):
    try:
        user = require_authenticated_user(request)
        payload = verify_subscription_payload(load_json(request))
        subscription, provider_response, paid = verify_subscription_payment(user, payload)
        return JsonResponse(
            {
                'success': True,
                'data': {
                    'subscription': serialize_subscription(subscription),
                    'payment_verified': paid,
                    'provider_response': provider_response,
                },
            }
        )
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('billing:signup-initialize', '10/min')
def initialize_paid_signup_checkout_view(request):
    try:
        result = initialize_paid_signup_checkout(load_json(request))
        return JsonResponse({'success': True, 'data': result}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('billing:signup-verify', '20/min')
def verify_paid_signup_checkout_view(request):
    try:
        reference = str(load_json(request).get('reference') or '').strip()
        if not reference:
            from hr_app_backend.utils.errors import ValidationError
            raise ValidationError('Reference is required.')
        subscription, session, provider_response = verify_paid_signup_checkout(reference)
        session = dict(session)
        token = session.pop('token', None)
        response = JsonResponse({
            'success': True,
            'data': {
                'subscription': serialize_subscription(subscription),
                'payment_verified': True,
                'session': session,
                'provider_response': provider_response,
            },
        })
        if token:
            set_session_cookie(response, token)
        return response
    except AppError as exc:
        return error_response(exc)
