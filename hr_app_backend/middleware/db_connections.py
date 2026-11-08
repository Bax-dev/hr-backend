from django.db import connections


def _close_old_connections():
    """Like ``django.db.close_old_connections`` but never closes a connection mid-transaction.

    Closing a connection that is inside an atomic block would abort that transaction
    (and breaks Django's TestCase, which wraps each test in one).
    """
    for conn in connections.all(initialized_only=True):
        if not conn.in_atomic_block:
            conn.close_if_unusable_or_obsolete()


class DatabaseConnectionCleanupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _close_old_connections()
        try:
            return self.get_response(request)
        finally:
            _close_old_connections()
