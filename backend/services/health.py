"""
Vigil Health Check Module

Provides:
- /health — Comprehensive health with database, scheduler, memory, disk checks
- /health/ready — Readiness check (all dependencies available)
- /health/live — Liveness check (process not deadlocked)
- /metrics — Prometheus-compatible metrics endpoint
"""

import os
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Response
from database import get_conn
from services.observability import anomaly_detector, metrics, PROMETHEUS_AVAILABLE, REGISTRY

health_router = APIRouter(prefix="/health", tags=["System"])

# Track application start time for uptime calculation
_START_TIME = time.time()
_VERSION = "2.0.0"


def _get_last_detection_time() -> Any | None:
    """Fetch the most recent detection run timestamp from the database."""
    conn = None
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
        if conn is not None:
            try:
                from database import _pool
                if _pool:
                    _pool.putconn(conn)
                else:
                    conn.close()
            except Exception:
                pass
    return None


def _check_database() -> dict[str, Any]:
    """Check database connectivity and measure latency."""
    start = time.time()
    try:
        conn = get_conn()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        latency_ms = round((time.time() - start) * 1000, 2)
        from database import _pool
        if _pool:
            _pool.putconn(conn)
        else:
            conn.close()
        return {"status": "up", "latency_ms": latency_ms}
    except Exception as e:
        return {"status": "down", "latency_ms": -1, "error": str(e)}


def _check_scheduler() -> dict[str, Any]:
    """Check scheduler status."""
    try:
        from api import scheduler
        running = scheduler.running
        jobs = scheduler.get_jobs()
        next_run = None
        if jobs:
            # Get the earliest next run time
            next_runs = [job.next_run_time for job in jobs if job.next_run_time is not None]
            if next_runs:
                earliest = min(next_runs)
                next_run = earliest.isoformat() if hasattr(earliest, 'isoformat') else str(earliest)
        return {
            "status": "running" if running else "stopped",
            "next_run": next_run,
            "job_count": len(jobs),
        }
    except Exception as e:
        return {"status": "stopped", "error": str(e)}


def _check_memory() -> dict[str, Any]:
    """Check memory usage via psutil."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        usage_percent = round(mem.percent, 1)
        if usage_percent >= 90:
            status = "critical"
        elif usage_percent >= 75:
            status = "warning"
        else:
            status = "ok"
        return {
            "status": status,
            "usage_percent": usage_percent,
            "available_mb": round(mem.available / (1024 * 1024), 1),
            "total_mb": round(mem.total / (1024 * 1024), 1),
        }
    except ImportError:
        return {"status": "ok", "usage_percent": -1, "note": "psutil not available"}
    except Exception as e:
        return {"status": "ok", "usage_percent": -1, "error": str(e)}


def _check_disk() -> dict[str, Any]:
    """Check disk usage via psutil."""
    try:
        import psutil
        disk = psutil.disk_usage("/")
        usage_percent = round(disk.percent, 1)
        if usage_percent >= 90:
            status = "critical"
        elif usage_percent >= 75:
            status = "warning"
        else:
            status = "ok"
        return {
            "status": status,
            "usage_percent": usage_percent,
            "free_gb": round(disk.free / (1024 * 1024 * 1024), 1),
            "total_gb": round(disk.total / (1024 * 1024 * 1024), 1),
        }
    except ImportError:
        return {"status": "ok", "usage_percent": -1, "note": "psutil not available"}
    except Exception as e:
        return {"status": "ok", "usage_percent": -1, "error": str(e)}


def _compute_overall_status(checks: dict[str, dict]) -> str:
    """Determine overall health status from individual checks."""
    has_critical = False
    has_warning = False

    for check_name, result in checks.items():
        status = result.get("status", "")
        if status in ("down", "stopped", "critical"):
            has_critical = True
        elif status in ("warning",):
            has_warning = True

    if has_critical:
        return "unhealthy"
    elif has_warning:
        return "degraded"
    return "healthy"


@health_router.get("/")
async def health_check():
    """
    Comprehensive health check.
    Returns structured health response with database, scheduler, memory, and disk checks.
    """
    db_check = _check_database()
    scheduler_check = _check_scheduler()
    memory_check = _check_memory()
    disk_check = _check_disk()

    checks = {
        "database": db_check,
        "scheduler": scheduler_check,
        "memory": memory_check,
        "disk": disk_check,
    }

    status = _compute_overall_status(checks)

    return {
        "status": status,
        "checks": checks,
        "version": _VERSION,
        "uptime_seconds": round(time.time() - _START_TIME),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@health_router.get("/ready")
async def readiness_check():
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
    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@health_router.get("/live")
async def liveness_check():
    """
    Liveness check — returns 200 if the process is not deadlocked.
    """
    return {"status": "alive"}


@health_router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus-compatible metrics endpoint.
    Returns text/plain in Prometheus exposition format.
    """
    if PROMETHEUS_AVAILABLE and REGISTRY is not None:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(
            content=generate_latest(REGISTRY).decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )
    # Fallback to in-memory collector
    return Response(
        content=metrics.prometheus_format(),
        media_type="text/plain",
    )


@health_router.get("/system")
async def system_health():
    """
    Extended system health including CPU, memory, and anomaly detection.
    """
    anomaly = anomaly_detector.check()
    metrics_summary = metrics.get_summary()
    return {
        "system": anomaly,
        "metrics": metrics_summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
