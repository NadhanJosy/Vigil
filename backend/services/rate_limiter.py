import logging
import time
import threading

logger = logging.getLogger(__name__)


class ChannelRateLimit:
    def __init__(self, max_per_window: int = 10, window_seconds: int = 3600):
        self.max_per_window = max_per_window
        self.window_seconds = window_seconds


class _LocalRateLimiter:
    """In-memory fallback rate limiter when database is unavailable."""

    def __init__(self):
        self._counts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, channel: str, max_per_window: int, window_seconds: int) -> bool:
        now = time.time()
        with self._lock:
            # Clean up expired entries
            if channel in self._counts:
                self._counts[channel] = [
                    t for t in self._counts[channel] if now - t < window_seconds
                ]
            else:
                self._counts[channel] = []

            current_count = len(self._counts[channel])
            if current_count < max_per_window:
                self._counts[channel].append(now)
                return True
            return False


_local_limiter = _LocalRateLimiter()


class ChannelRateLimiter:
    def __init__(self):
        self.limits: dict[str, ChannelRateLimit] = {
            "webhook": ChannelRateLimit(30, 3600),
            "slack": ChannelRateLimit(20, 3600),
            "email": ChannelRateLimit(10, 3600),
            "sms": ChannelRateLimit(5, 3600),
        }

    def allow(self, channel: str) -> bool:
        limit = self.limits.get(channel, ChannelRateLimit(10, 3600))
        try:
            from database import get_conn, _pool

            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM alert_deliveries WHERE channel=%s AND status='sent' AND sent_at>NOW()-%s::interval",
                        (channel, f"{limit.window_seconds} seconds"),
                    )
                    count = cur.fetchone()[0]
            finally:
                if _pool:
                    _pool.putconn(conn)
                else:
                    conn.close()
            return count < limit.max_per_window
        except Exception:
            # Fail closed: use local in-memory rate limiter as fallback
            logger.error(
                "Database unavailable for rate limiting on '%s', using local fallback",
                channel,
            )
            return _local_limiter.allow(channel, limit.max_per_window, limit.window_seconds)


channel_rate_limiter = ChannelRateLimiter()
