"""Replay protection for unsafe requests via the ``Idempotency-Key`` header.

A client that retries a request after a timeout cannot tell whether the
original reached the server. Sending the same ``Idempotency-Key`` on the retry
lets the server recognise the duplicate and replay the first response instead
of performing the write twice.

The flow mirrors the widely used Stripe semantics:

* The key is scoped per caller, so two users cannot collide on the same key.
* The first request to claim a key runs normally; its response is stored.
* A retry with the same key and the same body replays the stored response and
  carries an ``Idempotency-Replayed: true`` header.
* A retry that arrives while the original is still running gets HTTP 409 —
  the result is not known yet, so replaying would be a guess.
* Reusing a key with a *different* body is a client bug and gets HTTP 422,
  because silently replaying an unrelated response would be worse.

Only 2xx responses are stored. A failed write leaves no side effect to
protect, so releasing the key lets the client correct the payload and retry
with the same key.
"""

import hashlib
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

from .errors import AppError, error_payload
from .throttles import client_identifier

HEADER = 'Idempotency-Key'
META_KEY = 'HTTP_IDEMPOTENCY_KEY'
UNSAFE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})

DEFAULT_TTL = 86_400  # 24 hours
MAX_KEY_LENGTH = 255

# Sentinel stored while the original request is in flight.
_IN_FLIGHT = '__in_flight__'


class IdempotencyConflictError(AppError):
    status_code = 409
    default_message = (
        'A request with this Idempotency-Key is still in progress. '
        'Retry in a moment.'
    )


class IdempotencyKeyReuseError(AppError):
    status_code = 422
    default_message = (
        'This Idempotency-Key was already used with a different request body.'
    )


def _fingerprint(request):
    """Hash the parts of the request that must match for a replay to be valid."""
    digest = hashlib.sha256()
    digest.update(request.method.encode())
    digest.update(b'\0')
    digest.update(request.path.encode())
    digest.update(b'\0')
    digest.update(request.body or b'')
    return digest.hexdigest()


def _cache_key(scope, request, key):
    return f'idempotency:{scope}:{client_identifier(request)}:{key}'


def _serialize(response):
    """Capture a response well enough to rebuild it on replay.

    Streaming responses have no reusable body, so they are never stored.
    """
    if getattr(response, 'streaming', False):
        return None
    return {
        'status': response.status_code,
        'content_type': response.get('Content-Type', 'application/json'),
        'body': response.content.decode('utf-8'),
        'fingerprint': None,  # filled in by the caller
    }


def _replay(record):
    response = HttpResponse(
        record['body'],
        status=record['status'],
        content_type=record['content_type'],
    )
    response['Idempotency-Replayed'] = 'true'
    return response


def _error(exc):
    return JsonResponse(error_payload(exc), status=exc.status_code)


def idempotent(scope, *, ttl=DEFAULT_TTL, required=False):
    """Make an unsafe view replay-safe when the caller supplies a key.

    ``scope`` namespaces the key so the same value used against two different
    endpoints never collides. Set ``required=True`` on endpoints where a
    duplicate is expensive enough that an unkeyed request should be rejected
    outright (payment capture, payroll runs).

    Safe methods and requests without the header pass straight through::

        @idempotent('employees:create')
        def employees_view(request): ...
    """
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in UNSAFE_METHODS:
                return view(request, *args, **kwargs)

            key = (request.META.get(META_KEY) or '').strip()
            if not key:
                if required:
                    return _error(AppError(
                        f'The {HEADER} header is required for this request.',
                        status_code=400,
                    ))
                return view(request, *args, **kwargs)

            if len(key) > MAX_KEY_LENGTH:
                return _error(AppError(
                    f'{HEADER} must be at most {MAX_KEY_LENGTH} characters.',
                    status_code=400,
                ))

            cache_key = _cache_key(scope, request, key)
            fingerprint = _fingerprint(request)

            # ``add`` is atomic: exactly one concurrent request claims the key.
            claimed = cache.add(
                cache_key,
                {'state': _IN_FLIGHT, 'fingerprint': fingerprint},
                ttl,
            )

            if not claimed:
                record = cache.get(cache_key)
                if record is None:
                    # Entry expired between add and get — treat as a fresh claim.
                    cache.set(
                        cache_key,
                        {'state': _IN_FLIGHT, 'fingerprint': fingerprint},
                        ttl,
                    )
                elif record.get('fingerprint') != fingerprint:
                    return _error(IdempotencyKeyReuseError())
                elif record.get('state') == _IN_FLIGHT:
                    return _error(IdempotencyConflictError())
                else:
                    return _replay(record)

            try:
                response = view(request, *args, **kwargs)
            except Exception:
                # Never strand a key on a crash: the write may not have landed,
                # so the client must be free to retry with the same key.
                cache.delete(cache_key)
                raise

            if 200 <= response.status_code < 300:
                record = _serialize(response)
                if record is None:
                    cache.delete(cache_key)
                else:
                    record['state'] = 'complete'
                    record['fingerprint'] = fingerprint
                    cache.set(cache_key, record, ttl)
            else:
                cache.delete(cache_key)

            return response

        return wrapper

    return decorator
