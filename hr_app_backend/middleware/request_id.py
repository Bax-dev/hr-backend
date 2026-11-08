import contextvars
import logging
import re
import uuid

# Plain ``uuid`` rather than utils.generate_uuid4: this module is imported by the
# LOGGING config before Django's app registry is ready.

_request_id = contextvars.ContextVar('request_id', default='-')


def get_request_id():
    return _request_id.get()


class RequestIDMiddleware:
    """Tags each request with an id, echoed in the X-Request-ID response header and on every log line."""

    header_name = 'HTTP_X_REQUEST_ID'
    response_header_name = 'X-Request-ID'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = self._resolve_request_id(request)
        token = _request_id.set(request.request_id)
        try:
            response = self.get_response(request)
        finally:
            _request_id.reset(token)
        response[self.response_header_name] = request.request_id
        return response

    def _resolve_request_id(self, request):
        # Only accept a client-supplied ID if it's a well-formed UUID, so an
        # unbounded/arbitrary value can't be smuggled into logs and audit
        # records under this header.
        supplied = request.META.get(self.header_name, '')
        try:
            return str(uuid.UUID(supplied))
        except (ValueError, AttributeError, TypeError):
            return str(uuid.uuid4())


class RequestIdLogFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id()
        return True


_SECRET = re.compile(
    r'(?i)(password|passwd|token|secret|api[_-]?key|authorization|cookie|otp|mfa_token|recovery_code)'
    r"""(["']?\s*[:=]\s*["']?)([^\s"',}]+)"""
)


class RedactSecretsFilter(logging.Filter):
    """Masks obvious secrets (``password=...``, ``"token": "..."``) in log messages."""

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:
            return True
        redacted = _SECRET.sub(r'\1\2[REDACTED]', message)
        if redacted != message:
            record.msg, record.args = redacted, ()
        return True
