from .dates import local_now, today_local
from .env import get_bool, get_env, get_int, get_list
from .errors import (
    AppError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from .imports import date, datetime, time, timedelta, timezone, uuid
from .pagination import paginate_queryset, paginated_data
from .throttles import ThrottledError, client_identifier, throttle, throttle_view

__all__ = [
    "AppError",
    "AuthenticationError",
    "BadRequestError",
    "client_identifier",
    "ConflictError",
    "date",
    "datetime",
    "ExternalServiceError",
    "generate_uuid4",
    "get_bool",
    "get_env",
    "get_int",
    "get_list",
    "local_now",
    "NotFoundError",
    "paginate_queryset",
    "paginated_data",
    "PermissionDeniedError",
    "throttle",
    "throttle_view",
    "ThrottledError",
    "time",
    "timedelta",
    "TimeStampedModel",
    "timezone",
    "UUIDPrimaryKeyModel",
    "today_local",
    "ValidationError",
    "uuid",
]

_LAZY_IDS = {"UUIDPrimaryKeyModel", "generate_uuid4"}
_LAZY_MODELS = {"TimeStampedModel"}


def __getattr__(name):
    # .ids defines a Django model, and importing it needs the app registry.
    # This package is imported by settings (for get_env etc.) before the
    # registry exists, so the model must load lazily on first access.
    if name in _LAZY_IDS:
        from . import ids

        return getattr(ids, name)
    if name in _LAZY_MODELS:
        from . import models

        return getattr(models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
