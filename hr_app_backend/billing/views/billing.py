from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from hr_app_backend.utils.errors import AppError

from ..serializers import initialize_subscription_payload, serialize_subscription, verify_subscription_payload
from ..services import initialize_subscription_payment, verify_subscription_payment
from .helpers import error_response, load_json, require_authenticated_user


@csrf_exempt
@require_POST
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
