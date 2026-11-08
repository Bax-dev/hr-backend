"""Emailed 6-digit one-time codes (sign-up verification, password reset).

- Generated with ``secrets`` (a CSPRNG), never ``random``.
- Stored in Redis only as an HMAC keyed with SECRET_KEY, so reading Redis does not reveal codes.
- Compared in constant time.
- Each code allows MAX_ATTEMPTS wrong guesses, then it is destroyed and a new one must be requested.
  This caps guessing per code no matter how many IPs an attacker uses.
"""

import hashlib
import hmac
import secrets

from django.conf import settings

from hr_app_backend.third_parties import get_redis_client
from hr_app_backend.utils.errors import ValidationError

CODE_DIGITS = 6
MAX_ATTEMPTS = 5
INVALID_MESSAGE = 'Invalid or expired OTP.'


def _keys(namespace, email):
    base = f"{namespace}:{hashlib.sha256(email.encode('utf-8')).hexdigest()}"
    return base, f'{base}:attempts'


def _code_hash(namespace, email, code):
    message = f'{namespace}:{email}:{code}'.encode('utf-8')
    return hmac.new(settings.SECRET_KEY.encode('utf-8'), message, hashlib.sha256).hexdigest()


def _normalise(code):
    return ''.join(ch for ch in str(code or '') if ch.isdigit())


def issue_code(namespace, email, ttl_seconds):
    """Create (or replace) the code for ``email`` and return it in plain text for emailing."""
    code = f'{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}'
    code_key, attempts_key = _keys(namespace, email)
    pipe = get_redis_client().pipeline()
    pipe.setex(code_key, ttl_seconds, _code_hash(namespace, email, code))
    pipe.delete(attempts_key)
    pipe.execute()
    return code


def check_code(namespace, email, code):
    """Raise ValidationError unless ``code`` is the live code for ``email``. Does not consume it."""
    client = get_redis_client()
    code_key, attempts_key = _keys(namespace, email)
    stored = client.get(code_key)
    if not stored:
        raise ValidationError(INVALID_MESSAGE, code='OTP_INVALID')

    candidate = _normalise(code)
    if len(candidate) == CODE_DIGITS and hmac.compare_digest(stored, _code_hash(namespace, email, candidate)):
        return True

    attempts = client.incr(attempts_key)
    if attempts == 1:
        ttl = client.ttl(code_key)
        client.expire(attempts_key, ttl if ttl and ttl > 0 else 600)
    if attempts >= MAX_ATTEMPTS:
        client.delete(code_key, attempts_key)
        raise ValidationError(
            'Too many incorrect codes. Request a new code and try again.', code='OTP_ATTEMPTS_EXCEEDED'
        )
    raise ValidationError(INVALID_MESSAGE, code='OTP_INVALID')


def discard_code(namespace, email):
    get_redis_client().delete(*_keys(namespace, email))
