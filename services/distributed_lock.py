"""
Vigil Distributed Lock — Distributed locking for scheduled jobs.

Phase 4: Ensures only one instance runs detection jobs when deployed
behind a load balancer. Falls back to threading lock when Redis is
unavailable.
"""

import os
import time
import threading
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DistributedLock:
    """
    Distributed lock using Redis with threading lock fallback.

    Ensures only one instance executes a critical section at a time.
    """

    def __init__(self, name: str, timeout: int = 3600, redis_url: Optional[str] = None):
        self.name = f"vigil:lock:{name}"
        self.timeout = timeout
        self._redis = None
        self._thread_lock = threading.Lock()

        # Try to initialize Redis
        try:
            import redis
            url = redis_url or os.environ.get("REDIS_URL")
            if url:
                self._redis = redis.from_url(
                    url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                self._redis.ping()
                logger.info(f"Distributed lock '{name}' using Redis")
            else:
                logger.info(f"Distributed lock '{name}' using threading lock (no REDIS_URL)")
        except ImportError:
            logger.warning("redis package not installed, using threading lock")
        except Exception as e:
            logger.warning(f"Redis connection failed for lock '{name}': {e}, using threading lock")
            self._redis = None

    def acquire(self, blocking: bool = False) -> bool:
        """
        Acquire the lock.

        Args:
            blocking: If True, wait up to timeout seconds. If False, return immediately.

        Returns:
            True if lock acquired, False otherwise.
        """
        if self._redis is not None:
            return self._acquire_redis(blocking)
        else:
            return self._acquire_thread(blocking)

    def release(self) -> None:
        """Release the lock."""
        if self._redis is not None:
            self._release_redis()
        else:
            self._release_thread()

    def _acquire_redis(self, blocking: bool) -> bool:
        """Acquire lock using Redis SET NX."""
        try:
            if blocking:
                # Try to acquire with retry
                deadline = time.time() + self.timeout
                while time.time() < deadline:
                    acquired = self._redis.set(self.name, "1", nx=True, ex=self.timeout)
                    if acquired:
                        logger.debug(f"Acquired distributed lock: {self.name}")
                        return True
                    time.sleep(1)
                return False
            else:
                acquired = self._redis.set(self.name, "1", nx=True, ex=self.timeout)
                if acquired:
                    logger.debug(f"Acquired distributed lock: {self.name}")
                return acquired
        except Exception as e:
            logger.error(f"Redis lock acquire error: {e}")
            return False

    def _release_redis(self) -> None:
        """Release Redis lock."""
        try:
            self._redis.delete(self.name)
            logger.debug(f"Released distributed lock: {self.name}")
        except Exception as e:
            logger.error(f"Redis lock release error: {e}")

    def _acquire_thread(self, blocking: bool) -> bool:
        """Acquire threading lock."""
        if blocking:
            self._thread_lock.acquire()
            return True
        else:
            return self._thread_lock.acquire(blocking=False)

    def _release_thread(self) -> None:
        """Release threading lock."""
        try:
            self._thread_lock.release()
        except RuntimeError:
            pass  # Lock was not held

    @contextmanager
    def __call__(self, blocking: bool = False):
        """Context manager for lock acquisition/release."""
        acquired = self.acquire(blocking=blocking)
        if not acquired:
            raise RuntimeError(f"Failed to acquire lock: {self.name}")
        try:
            yield
        finally:
            self.release()


# Global lock for detection runs
_detection_lock: Optional[DistributedLock] = None


def get_detection_lock(timeout: int = 3600) -> DistributedLock:
    """Get or create the detection run distributed lock."""
    global _detection_lock
    if _detection_lock is None:
        _detection_lock = DistributedLock("detection", timeout=timeout)
    return _detection_lock


def run_detection_if_leader(detection_func) -> bool:
    """
    Run detection only if this instance holds the lock.

    Args:
        detection_func: Callable to execute if lock acquired.

    Returns:
        True if detection ran, False if another instance holds the lock.
    """
    lock = get_detection_lock()
    if lock.acquire(blocking=False):
        try:
            logger.info("Acquired detection lock — running detection")
            detection_func()
            return True
        finally:
            lock.release()
    else:
        logger.info("Another instance holds detection lock — skipping")
        return False
