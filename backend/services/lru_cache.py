"""
Vigil DI LRU Cache — Application-level caching without external dependencies.
Simulates Redis behavior using Python's OrderedDict with LRU eviction.

This is a thread-safe, zero-dependency cache designed for the Decision
Intelligence layer. All ground truth lives in PostgreSQL; this cache
only reduces redundant compute on repeated polling requests.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """
    Thread-safe LRU cache with configurable capacity and TTL.

    Key design:
    - OrderedDict provides O(1) get/put with LRU ordering
    - TTL is checked on access, not via background thread (stateless)
    - Max capacity enforced on every put
    - No external dependencies (no Redis, no memcached)

    Quantitative rationale:
    - Max 512 entries bounds memory to ~50MB at typical payload sizes
    - TTL-based eviction ensures stale data is never served indefinitely
    - Thread safety via reentrant lock allows concurrent polling requests
    """

    def __init__(self, max_size: int = 512, default_ttl: int = 300):
        """
        Initialize the LRU cache.

        Args:
            max_size: Maximum number of entries before LRU eviction begins.
                      Default 512 bounds memory to ~50MB.
            default_ttl: Default time-to-live in seconds for entries.
                         Default 300s (5 minutes) balances freshness vs. compute.
        """
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        # Statistics counters
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value by key. Returns None if missing or expired.

        Args:
            key: Cache key to look up.

        Returns:
            Cached value if present and not expired, else None.
        """
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None
            value, expiry = self._store[key]
            if time.time() > expiry:
                del self._store[key]
                self._misses += 1
                return None
            # Move to end (most recently used)
            self._store.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value with TTL. Evicts LRU entry if at capacity.

        Args:
            key: Cache key to set.
            value: Value to cache (must be serializable if persistence needed).
            ttl: Time-to-live in seconds. Defaults to instance default_ttl.
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, time.time() + effective_ttl)
            if len(self._store) > self._max_size:
                self._store.popitem(last=False)  # Evict least recently used

    def delete(self, key: str) -> bool:
        """
        Delete a key. Returns True if key existed.

        Args:
            key: Cache key to delete.

        Returns:
            True if key was present and removed, False otherwise.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> int:
        """
        Clear all entries. Returns count of removed items.

        Returns:
            Number of entries that were in the cache.
        """
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def stats(self) -> dict[str, int]:
        """
        Return cache statistics including hit/miss rates.

        Returns:
            Dictionary with size, max_size, utilization_pct, hits, misses.
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = round(self._hits / total * 100, 1) if total > 0 else 0.0
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "utilization_pct": round(len(self._store) / self._max_size * 100, 1),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": hit_rate,
            }


# Module-level singleton
_di_cache: Optional[LRUCache] = None
_cache_lock = threading.Lock()


def get_di_cache() -> LRUCache:
    """Get or create the DI LRU cache singleton."""
    global _di_cache
    if _di_cache is None:
        with _cache_lock:
            if _di_cache is None:
                _di_cache = LRUCache(max_size=512, default_ttl=300)
    return _di_cache


def reset_di_cache() -> None:
    """Reset the DI LRU cache singleton. Use in tests to prevent pollution."""
    global _di_cache
    with _cache_lock:
        _di_cache = None
