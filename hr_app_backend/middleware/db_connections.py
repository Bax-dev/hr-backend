from django.db import close_old_connections


class DatabaseConnectionCleanupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        close_old_connections()
        try:
            response = self.get_response(request)
            close_old_connections()
            return response
        except Exception:
            close_old_connections()
            raise
