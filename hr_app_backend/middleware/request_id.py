from hr_app_backend.utils import generate_uuid4


class RequestIDMiddleware:
    header_name = "HTTP_X_REQUEST_ID"
    response_header_name = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.META.get(self.header_name, generate_uuid4())
        response = self.get_response(request)
        response[self.response_header_name] = request.request_id
        return response
