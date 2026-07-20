from http import HTTPStatus


class AppError(Exception):
    status_code = 400
    default_message = 'An application error occurred.'

    def __init__(self, message=None, *, status_code=None):
        self.message = message or self.default_message
        self.status_code = status_code or self.status_code
        super().__init__(self.message)


class BadRequestError(AppError):
    default_message = 'The request is invalid.'


class ValidationError(BadRequestError):
    default_message = 'Please review the submitted information and try again.'


class AuthenticationError(AppError):
    status_code = 401
    default_message = 'Authentication failed.'


class PermissionDeniedError(AppError):
    status_code = 403
    default_message = 'You do not have permission to perform this action.'


class NotFoundError(AppError):
    status_code = 404
    default_message = 'The requested resource was not found.'


class ConflictError(AppError):
    status_code = 409
    default_message = 'The request conflicts with existing data.'


class ExternalServiceError(AppError):
    status_code = 502
    default_message = 'An external service request failed.'


def error_payload(error):
    """Build the standard error body for an :class:`AppError`.

    Kept here rather than in the auth helpers so middleware-style utilities
    (throttling, idempotency) can emit the exact same envelope as views do
    without importing from an app package.
    """
    status = int(getattr(error, 'status_code', 400) or 400)
    try:
        status_title = HTTPStatus(status).phrase
    except ValueError:
        status_title = 'Request Error'

    detail = str(
        getattr(error, 'message', '') or 'Something went wrong. Please try again.'
    ).strip()

    return {
        'success': False,
        'statusCode': status,
        'status': status_title,
        'message': detail,
        'detail': detail,
        'error': status_title.lower().replace(' ', '_'),
    }
