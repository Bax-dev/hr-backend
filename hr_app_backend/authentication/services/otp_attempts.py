from hr_app_backend.third_parties import get_redis_client

MAX_ATTEMPTS = 5
DEFAULT_TTL_SECONDS = 10 * 60


def _attempts_key(otp_key):
    return f'{otp_key}:attempts'


def register_failed_attempt(otp_key):
    """Count a failed guess against otp_key; delete the OTP once MAX_ATTEMPTS
    is reached so a slow/distributed guesser can't outlast the OTP's own TTL."""
    redis_client = get_redis_client()
    attempts_key = _attempts_key(otp_key)
    attempts = redis_client.incr(attempts_key)
    if attempts == 1:
        ttl = redis_client.ttl(otp_key)
        redis_client.expire(attempts_key, ttl if ttl and ttl > 0 else DEFAULT_TTL_SECONDS)
    if attempts >= MAX_ATTEMPTS:
        redis_client.delete(otp_key)
        redis_client.delete(attempts_key)


def clear_attempts(otp_key):
    get_redis_client().delete(_attempts_key(otp_key))
