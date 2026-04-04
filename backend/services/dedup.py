import hashlib
import logging

logger = logging.getLogger(__name__)


class DeduplicationStore:
    def __init__(self):
        self._seen: set[str] = set()

    def fingerprint(self, ticker: str, signal_type: str, date: str) -> str:
        return hashlib.sha256(f"{ticker}:{signal_type}:{date}".encode()).hexdigest()

    def is_duplicate(self, fingerprint: str) -> bool:
        """Check if a signal fingerprint has been seen before.

        Returns True if duplicate, False if new. Logs warnings on duplicates.
        """
        if fingerprint in self._seen:
            logger.warning("Duplicate signal suppressed: %s", fingerprint[:16])
            return True
        self._seen.add(fingerprint)
        return False

    def exists(self, fingerprint: str) -> bool:
        try:
            from database import get_conn, _pool

            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM alert_dedup WHERE fingerprint=%s AND expires_at>NOW()",
                        (fingerprint,),
                    )
                    result = cur.fetchone() is not None
            finally:
                if _pool:
                    _pool.putconn(conn)
                else:
                    conn.close()
            return result
        except Exception:
            return False

    def record(self, fingerprint: str, alert_id: int = None) -> None:
        try:
            from database import get_conn, _pool

            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO alert_dedup (fingerprint, alert_id, expires_at) VALUES (%s,%s,NOW()+INTERVAL '24 hours') "
                        "ON CONFLICT (fingerprint) DO UPDATE SET expires_at=NOW()+INTERVAL '24 hours'",
                        (fingerprint, alert_id),
                    )
                conn.commit()
            finally:
                if _pool:
                    _pool.putconn(conn)
                else:
                    conn.close()
        except Exception as e:
            logger.error("Dedup record error: %s", e)


dedup = DeduplicationStore()
