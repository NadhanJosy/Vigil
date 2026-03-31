"""
Vigil Health Check Module

Provides:
- /health — Basic liveness for load balancers
- /health/ready — Readiness check (all dependencies available)
- /health/live — Liveness check (process not deadlocked)
- /metrics — Prometheus-compatible metrics endpoint
"""

from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify

from database import get_conn
from services.observability import anomaly_detector, metrics

health_bp = Blueprint("health", __name__)


def _get_last_detection_time() -> Any | None:
    """Fetch the most recent detection run timestamp from the database."""
    try:
        conn = get_conn()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT MAX(created_at) FROM alerts WHERE created_at IS NOT NULL"
            )
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    finally:
        try:
            from database import _pool
            if _pool:
                _pool.putconn(conn)
            else:
                conn.close()
        except Exception:
            pass
    return None


@health_bp.route("/health")
def health_check() -> tuple:
    """
    Basic health check for load balancers.
    Returns 200 if the process is alive.
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@health_bp.route("/health/ready")
def readiness_check() -> tuple:
    """
    Readiness check — returns 200 only if all dependencies are available.
    """
    checks: dict[str, str] = {}

    # Database check
    try:
        conn = get_conn()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "healthy"
        from database import _pool
        if _pool:
            _pool.putconn(conn)
        else:
            conn.close()
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"

    # Detection freshness check (last run within 25 hours)
    try:
        last_run = _get_last_detection_time()
        if last_run:
            # Handle both aware and naive datetimes
            last_dt = last_run
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            age_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if age_seconds < 90000:  # 25 hours
                checks["detection"] = "healthy"
            else:
                checks["detection"] = f"stale ({age_seconds / 3600:.1f}h ago)"
        else:
            checks["detection"] = "no data"
    except Exception as e:
        checks["detection"] = f"error: {str(e)}"

    all_healthy = all(v == "healthy" for v in checks.values())
    status_code = 200 if all_healthy else 503

    return jsonify({
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), status_code


@health_bp.route("/health/live")
def liveness_check() -> tuple:
    """
    Liveness check — returns 200 if the process is not deadlocked.
    """
    return jsonify({"status": "alive"}), 200


@health_bp.route("/metrics")
def prometheus_metrics() -> tuple:
    """
    Prometheus-compatible metrics endpoint.
    Returns text/plain in Prometheus exposition format.
    """
    from flask import Response
    return Response(
        metrics.prometheus_format(),
        status=200,
        mimetype="text/plain",
    )


@health_bp.route("/health/system")
def system_health() -> tuple:
    """
    Extended system health including CPU, memory, and anomaly detection.
    """
    anomaly = anomaly_detector.check()
    metrics_summary = metrics.get_summary()
    return jsonify({
        "system": anomaly,
        "metrics": metrics_summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200
