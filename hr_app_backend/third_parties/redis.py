import redis

from hr_app_backend.utils import get_env


REDIS_URL_ENV = "REDIS_URL"
DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/1"


def get_redis_url(default=DEFAULT_REDIS_URL):
    return get_env(REDIS_URL_ENV, default)


def build_django_cache_config(url=None, key_prefix="hr_app_backend"):
    location = url or get_redis_url()
    return {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": location,
        "KEY_PREFIX": key_prefix,
        "TIMEOUT": 300,
    }


def get_redis_client(url=None):
    return redis.Redis.from_url(url or get_redis_url(), decode_responses=True)
