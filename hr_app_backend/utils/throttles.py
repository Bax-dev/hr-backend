from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse

from .errors import AppError, error_payload
from .request_ip import client_ip

_PERIODS = {
    'sec': 1,
    'second': 1,
    'min': 60,
    'minute': 60,
    'hour': 3600,
    'day': 86400,
}


class ThrottledError(AppError):
    status_code = 429
    default_message = 'Request was throttled. Try again later.'


def _parse_rate(rate):
    """Parse a DRF-style rate string like ``'100/min'`` into ``(limit, window)``."""
    try:
        count, period = rate.split('/')
        limit = int(count)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f'Invalid throttle rate: {rate!r}') from exc

    window = _PERIODS.get(period.strip().lower())
    if window is None:
        raise ValueError(f'Unknown throttle period: {period!r}')
    return limit, window


def client_identifier(request):
    """Identify the caller by authenticated user, falling back to client IP."""
    user = getattr(request, 'user', None)
    user_id = getattr(user, 'pk', None) if user is not None else None
    if user_id and getattr(user, 'is_authenticated', False):
        return f'user:{user_id}'

    return f'ip:{client_ip(request)}'


def throttle(request, *, scope, rate, ident=None):
    """Enforce ``rate`` for ``scope`` using the cache; raise on breach.

    Uses a fixed-window counter keyed by ``scope`` + caller identity. Raises
    :class:`ThrottledError` (HTTP 429) once the limit is exceeded. Intended to
    be called inside a view's ``try/except AppError`` block.
    """
    limit, window = _parse_rate(rate)
    ident = ident or client_identifier(request)
    key = f'throttle:{scope}:{ident}'

    # ``add`` only writes when the key is absent, starting a fresh window with
    # its own TTL; ``incr`` then bumps the counter without resetting the TTL.
    if cache.add(key, 1, window):
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:
            # Window expired between ``add`` and ``incr``; start a new one.
            cache.set(key, 1, window)
            count = 1

    if count > limit:
        raise ThrottledError()
    return count


def throttle_view(scope, rate, ident=None):
    """Decorator wrapping a function view with :func:`throttle`.

    Returns the standard error envelope with HTTP 429 when the limit is hit, so
    it can safely wrap views whose own error handling runs inside the body::

        @throttle_view('login', '10/min')
        def login_view(request): ...
    """
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            try:
                throttle(request, scope=scope, rate=rate, ident=ident)
            except ThrottledError as exc:
                return JsonResponse(error_payload(exc), status=exc.status_code)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
