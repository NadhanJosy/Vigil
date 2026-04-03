"""
Vigil Cache — Redis caching layer with decorator support.

Phase 4: Provides a Redis-backed cache with graceful fallback to
in-memory caching when Redis is unavailable.
"""

import os
import json
import time
import hashlib
import logging
import functools
from typing import Any, Optional

logger = logging.getLogger(__name__)

# In-memory fallback cache
_memory_cache: dict[str, tuple[Any, float]] = {}
_MEMORY_TTL = 300  # 5 minutes default


class CacheBackend:
    """Cache backend interface with Redis and in-memory implementations."""

    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError


class RedisCache(CacheBackend):
    """Redis-backed cache with graceful degradation."""

    def __init__(self, url: Optional[str] = None):
        self._redis = None
        try:
            import redis
            redis_url = url or os.environ.get("REDIS_URL")
            if redis_url:
                self._redis = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                self._redis.ping()
                logger.info("Redis cache backend initialized")
            else:
                logger.info("REDIS_URL not set, using in-memory cache")
        except ImportError:
            logger.warning("redis package not installed, using in-memory cache")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using in-memory cache")

    @property
    def available(self) -> bool:
        return self._redis is not None

    def get(self, key: str) -> Optional[Any]:
        if not self.available:
            return _memory_cache.get(key, (None, 0))[0]
        try:
            val = self._redis.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning(f"Redis GET error: {e}")
            return _memory_cache.get(key, (None, 0))[0]

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if not self.available:
            _memory_cache[key] = (value, time.time() + ttl)
            return
        try:
            self._redis.setex(key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.warning(f"Redis SET error: {e}")
            _memory_cache[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> None:
        if self.available:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        _memory_cache.pop(key, None)

    def clear(self) -> None:
        if self.available:
            try:
                self._redis.flushdb()
            except Exception:
                pass
        _memory_cache.clear()


class MemoryCache(CacheBackend):
    """Simple in-memory cache with TTL."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expiry = self._store[key]
            if time.time() < expiry:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        self._store[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


# Global cache instance
_cache: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    """Get the global cache instance (Redis if available, else memory)."""
    global _cache
    if _cache is None:
        redis_cache = RedisCache()
        _cache = redis_cache if redis_cache.available else MemoryCache()
    return _cache


def cache_result(key_prefix: str, ttl: int = 300):
    """
    Decorator to cache function results.

    Args:
        key_prefix: Prefix for cache keys.
        ttl: Time-to-live in seconds.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name + args
            key_parts = [key_prefix, func.__name__]
            if args:
                key_parts.append(hashlib.md5(str(args).encode()).hexdigest()[:8])
            if kwargs:
                key_parts.append(hashlib.md5(str(sorted(kwargs.items())).encode()).hexdigest()[:8])
            cache_key = ":".join(key_parts)

            # Check cache
            cached = get_cache().get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached

            # Compute and cache
            result = func(*args, **kwargs)
            get_cache().set(cache_key, result, ttl=ttl)
            logger.debug(f"Cache miss: {cache_key}")
            return result
        return wrapper
    return decorator


def invalidate_cache(key_prefix: str) -> None:
    """Invalidate all cache entries with a given prefix."""
    cache = get_cache()
    if isinstance(cache, MemoryCache):
        keys_to_delete = [k for k in cache._store if k.startswith(key_prefix)]
        for k in keys_to_delete:
            del cache._store[k]
    elif isinstance(cache, RedisCache) and cache.available:
        try:
            for key in cache._redis.scan_iter(f"{key_prefix}*"):
                cache._redis.delete(key)
        except Exception:
            pass
    else:
        keys_to_delete = [k for k in _memory_cache if k.startswith(key_prefix)]
        for k in keys_to_delete:
            _memory_cache.pop(k, None)
