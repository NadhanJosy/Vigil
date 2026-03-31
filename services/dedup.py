import hashlib
import logging


class DeduplicationStore:
    def fingerprint(self, ticker: str, signal_type: str, date: str) -> str:
        return hashlib.sha256(f"{ticker}:{signal_type}:{date}".encode()).hexdigest()

    def exists(self, fingerprint: str) -> bool:
        try:
            from database import get_conn, _pool

            conn = get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM alert_dedup WHERE fingerprint=%s AND expires_at>NOW()",
                    (fingerprint,),
                )
                result = cur.fetchone() is not None
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
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO alert_dedup (fingerprint, alert_id, expires_at) VALUES (%s,%s,NOW()+INTERVAL '24 hours') "
                    "ON CONFLICT (fingerprint) DO UPDATE SET expires_at=NOW()+INTERVAL '24 hours'",
                    (fingerprint, alert_id),
                )
            conn.commit()
            if _pool:
                _pool.putconn(conn)
            else:
                conn.close()
        except Exception as e:
            logging.error(f"Dedup record error: {e}")


dedup = DeduplicationStore()
