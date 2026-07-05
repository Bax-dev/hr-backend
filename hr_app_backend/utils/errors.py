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
    default_message = 'Submitted data is invalid.'


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
