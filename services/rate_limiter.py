import logging


class ChannelRateLimit:
    def __init__(self, max_per_window: int = 10, window_seconds: int = 3600):
        self.max_per_window = max_per_window
        self.window_seconds = window_seconds


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
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM alert_deliveries WHERE channel=%s AND status='sent' AND sent_at>NOW()-%s::interval",
                    (channel, f"{limit.window_seconds} seconds"),
                )
                count = cur.fetchone()[0]
            if _pool:
                _pool.putconn(conn)
            else:
                conn.close()
            return count < limit.max_per_window
        except Exception:
            return True


channel_rate_limiter = ChannelRateLimiter()
