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
        self._owner_token: Optional[str] = None

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

    def acquire(self, blocking: bool = False) -> str:
        """
        Acquire the lock.

        Args:
            blocking: If True, wait up to timeout seconds. If False, return immediately.

        Returns:
            Owner token string if lock acquired, empty string otherwise.
        """
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

    def release(self, owner_token: str) -> bool:
        """Release the lock with mandatory owner validation.

        Args:
            owner_token: Token returned by acquire(). Required — empty strings rejected.

        Returns:
            True if lock was released, False if ownership validation failed.
        """
        if not owner_token:
            logger.warning("Lock release rejected: empty owner token for %s", self.name)
            return False
        if self._redis is not None:
            return self._release_redis(owner_token)
        else:
            return self._release_thread(owner_token)

    def _acquire_redis(self, blocking: bool) -> str:
        """Acquire lock using Redis SET NX. Returns owner token or empty string."""
        import uuid
        try:
            owner_token = str(uuid.uuid4())
            if blocking:
                deadline = time.time() + self.timeout
                while time.time() < deadline:
                    acquired = self._redis.set(self.name, owner_token, nx=True, ex=self.timeout)
                    if acquired:
                        logger.debug(f"Acquired distributed lock: {self.name}")
                        return owner_token
                    time.sleep(1)
                return ""
            else:
                acquired = self._redis.set(self.name, owner_token, nx=True, ex=self.timeout)
                if acquired:
                    logger.debug(f"Acquired distributed lock: {self.name}")
                    return owner_token
                return ""
        except Exception as e:
            logger.error(f"Redis lock acquire error: {e}")
            return ""

    def _release_redis(self, owner_token: str) -> bool:
        """Release Redis lock with owner validation via Lua script."""
        try:
            lua = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = self._redis.eval(lua, 1, self.name, owner_token)
            logger.debug(f"Released distributed lock: {self.name}")
            return bool(result)
        except Exception as e:
            logger.error(f"Redis lock release error: {e}")
            return False

    def _acquire_thread(self, blocking: bool) -> str:
        """Acquire threading lock. Returns owner token or empty string."""
        import uuid
        if blocking:
            self._thread_lock.acquire()
            self._owner_token = str(uuid.uuid4())
            return self._owner_token
        elif self._thread_lock.acquire(blocking=False):
            self._owner_token = str(uuid.uuid4())
            return self._owner_token
        return ""

    def _release_thread(self, owner_token: str) -> bool:
        """Release threading lock with owner validation."""
        if not owner_token or owner_token != self._owner_token:
            logger.warning(f"Lock release rejected: invalid owner token for {self.name}")
            return False
        try:
            self._thread_lock.release()
            self._owner_token = None
            return True
        except RuntimeError:
            self._owner_token = None
            return False  # Lock was not held

    @contextmanager
    def __call__(self, blocking: bool = False):
        """Context manager for lock acquisition/release."""
        owner_token = self.acquire(blocking=blocking)
        if not owner_token:
            raise RuntimeError(f"Failed to acquire lock: {self.name}")
        try:
            yield
        finally:
            self.release(owner_token)


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
    owner_token = lock.acquire(blocking=False)
    if owner_token:
        try:
            logger.info("Acquired detection lock — running detection")
            detection_func()
            return True
        finally:
            lock.release(owner_token)
    else:
        logger.info("Another instance holds detection lock — skipping")
        return False
