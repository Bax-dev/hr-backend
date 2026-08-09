import uuid

from hr_app_backend.utils import generate_uuid4


class RequestIDMiddleware:
    header_name = "HTTP_X_REQUEST_ID"
    response_header_name = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = self._resolve_request_id(request)
        response = self.get_response(request)
        response[self.response_header_name] = request.request_id
        return response

    def _resolve_request_id(self, request):
        # Only accept a client-supplied ID if it's a well-formed UUID, so an
        # unbounded/arbitrary value can't be smuggled into logs and audit
        # records under this header.
        supplied = request.META.get(self.header_name, "")
        try:
            return str(uuid.UUID(supplied))
        except (ValueError, AttributeError, TypeError):
            return generate_uuid4()
