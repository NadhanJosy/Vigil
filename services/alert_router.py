import logging
import time


class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0

    def backoff(self, attempt: int) -> float:
        return min(self.base_delay * (2 ** attempt), self.max_delay)


class DeliveryResult:
    def __init__(self, channel: str, status: str, error: str = None):
        self.channel = channel
        self.status = status
        self.error = error


class AlertRouter:
    def __init__(self):
        self.channels: dict[str, object] = {}
        self.retry_policy = RetryPolicy()

    def register_channel(self, name: str, channel) -> None:
        self.channels[name] = channel

    def dispatch(self, alert: dict) -> list:
        results = []
        for name, ch in self.channels.items():
            results.append(self._dispatch_one(name, ch, alert))
        return results

    def _dispatch_one(self, name: str, channel, alert: dict) -> DeliveryResult:
        last_error = None
        for attempt in range(self.retry_policy.max_attempts):
            try:
                channel.send(alert)
                self._record_delivery(alert.get("id"), name, "sent")
                return DeliveryResult(name, "sent")
            except Exception as e:
                last_error = e
                wait = self.retry_policy.backoff(attempt)
                logging.warning(
                    f"Channel {name} attempt {attempt + 1} failed: {e}. Retry in {wait}s"
                )
                time.sleep(wait)
        self._record_delivery(alert.get("id"), name, "dead_letter", str(last_error))
        return DeliveryResult(name, "dead_letter", str(last_error))

    def _record_delivery(
        self, alert_id, channel: str, status: str, error: str = None
    ) -> None:
        try:
            from database import get_conn, _pool

            conn = get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO alert_deliveries (alert_id, channel, status, error, sent_at) VALUES (%s,%s,%s,%s,NOW())",
                    (alert_id, channel, status, error),
                )
            conn.commit()
            if _pool:
                _pool.putconn(conn)
            else:
                conn.close()
        except Exception as e:
            logging.error(f"Failed to record delivery: {e}")


alert_router = AlertRouter()
