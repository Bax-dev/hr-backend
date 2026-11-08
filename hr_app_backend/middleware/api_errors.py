import logging

from django.http import JsonResponse

from hr_app_backend.utils.errors import AppError, error_payload

logger = logging.getLogger(__name__)

API_PREFIX = '/api/'
GENERIC_MESSAGE = 'Something went wrong on our side. Please try again in a moment.'


class ApiExceptionMiddleware:
    """Return the standard JSON error envelope for unhandled exceptions on API routes.

    Without this, an uncaught exception renders Django's HTML error page (the full
    debug page when DEBUG is on), which API clients end up showing to users verbatim.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not request.path.startswith(API_PREFIX):
            return None
        if isinstance(exception, AppError):
            body = error_payload(exception)
        else:
            logger.exception('Unhandled error on %s %s', request.method, request.path)
            body = error_payload(AppError(GENERIC_MESSAGE, status_code=500))
        request_id = getattr(request, 'request_id', '')
        if request_id:
            body['requestId'] = request_id
        return JsonResponse(body, status=body['statusCode'])
