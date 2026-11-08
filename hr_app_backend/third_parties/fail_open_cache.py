"""Django Redis cache that degrades to a cache miss when Redis is unreachable.

The default cache backs the rate limits and idempotency keys. With the stock backend a
Redis outage turns every throttled request into a 500; with this one the rate limits
stop counting until Redis is back, and the request itself still works.

Things that must fail closed (OTP codes, the paid-signup checkout) use the raw Redis
client from ``get_redis_client`` instead, so they are unaffected.
"""

import functools
import logging

from django.core.cache.backends.redis import RedisCache

logger = logging.getLogger(__name__)

# Value returned per method when Redis is down.
_FALLBACKS = {
    'get': lambda args, kwargs: kwargs.get('default', args[1] if len(args) > 1 else None),
    'get_many': lambda args, kwargs: {},
    'add': lambda args, kwargs: False,
    'delete': lambda args, kwargs: False,
    'has_key': lambda args, kwargs: False,
    'touch': lambda args, kwargs: False,
    'set_many': lambda args, kwargs: [],
}


class FailOpenRedisCache(RedisCache):
    def clear(self):
        # RedisCache.clear() runs FLUSHDB, which would also wipe OTPs, sessions-in-transition
        # and checkout state sharing the database. Only delete this cache's own keys.
        if not self.key_prefix:
            logger.warning('Refusing to clear an unprefixed shared cache')
            return False
        try:
            client = self._cache.get_client(None, write=True)
            for key in client.scan_iter(match=f'{self.key_prefix}:*', count=500):
                client.delete(key)
            return True
        except Exception as exc:
            logger.warning('Cache clear failed: %s', exc)
            return False


def _fail_open(name):
    method = getattr(RedisCache, name)
    fallback = _FALLBACKS.get(name, lambda args, kwargs: None)

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except ValueError:
            # incr/decr on a missing key is a real cache answer, not an outage.
            raise
        except Exception as exc:
            logger.warning('Cache %s failed: %s', name, exc)
            return fallback(args, kwargs)

    return wrapper


for _name in ('get', 'get_many', 'set', 'set_many', 'add', 'delete', 'delete_many', 'has_key', 'touch', 'incr', 'decr'):
    setattr(FailOpenRedisCache, _name, _fail_open(_name))
