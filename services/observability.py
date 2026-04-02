"""
Vigil Observability Module

Provides:
- Structured JSON logging
- Prometheus-compatible metrics export
- Request latency tracking (p50, p95, p99)
- Error rate monitoring
- System anomaly detection (CPU, memory)
"""

import json
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from flask import Flask, g, request

# ---------------------------------------------------------------------------
# Structured JSON Logging
# ---------------------------------------------------------------------------


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        return json.dumps(log_entry)


def configure_structured_logging(level: int = logging.INFO) -> None:
    """Replace the default formatter with structured JSON logging."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers to avoid duplicate output
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)


# ---------------------------------------------------------------------------
# Prometheus Metrics (in-memory, no external server required)
# ---------------------------------------------------------------------------

class MetricsCollector:
    """
    Lightweight in-memory metrics collector compatible with Prometheus exposition.

    Tracks:
    - Request latency histogram buckets
    - Request counts by method/endpoint/status
    - Error counts by type
    - Active request gauge
    """

    def __init__(self) -> None:
        self._latencies: list[float] = []
        self._request_counts: dict[str, int] = {}
        self._error_counts: dict[str, int] = {}
        self._active_requests: int = 0

    # -- Public API ----------------------------------------------------------

    def observe_latency(self, method: str, endpoint: str, status: int, latency: float) -> None:
        key = f"{method}:{endpoint}:{status}"
        self._request_counts[key] = self._request_counts.get(key, 0) + 1
        self._latencies.append(latency)
        self._latencies = self._latencies[-1000:]
        if status >= 500:
            err_key = f"server_error:{endpoint}"
            self._error_counts[err_key] = self._error_counts.get(err_key, 0) + 1
        elif status >= 400:
            err_key = f"client_error:{endpoint}"
            self._error_counts[err_key] = self._error_counts.get(err_key, 0) + 1

    def inc_active(self) -> None:
        self._active_requests += 1

    def dec_active(self) -> None:
        self._active_requests = max(0, self._active_requests - 1)

    def get_summary(self) -> dict[str, Any]:
        if not self._latencies:
            return {"p50": 0, "p95": 0, "p99": 0, "count": 0, "active": self._active_requests}
        import heapq
        n = len(self._latencies)
        p50 = heapq.nsmallest(int(n * 50) + 1, self._latencies)[-1] if n > 1 else self._latencies[0]
        p95 = heapq.nsmallest(int(n * 95 // 100) + 1, self._latencies)[-1] if n > 1 else self._latencies[0]
        p99 = heapq.nsmallest(int(n * 99 // 100) + 1, self._latencies)[-1] if n > 1 else self._latencies[0]
        return {
            "p50": round(p50 * 1000, 2),
            "p95": round(p95 * 1000, 2),
            "p99": round(p99 * 1000, 2),
            "count": n,
            "active": self._active_requests,
            "request_counts": dict(self._request_counts),
            "error_counts": dict(self._error_counts),
        }

    def prometheus_format(self) -> str:
        """Return metrics in Prometheus text exposition format."""
        summary = self.get_summary()
        lines = [
            f"# HELP vigil_request_latency_p50 50th percentile request latency (ms)",
            f"# TYPE vigil_request_latency_p50 gauge",
            f"vigil_request_latency_p50 {summary['p50']}",
            f"# HELP vigil_request_latency_p95 95th percentile request latency (ms)",
            f"# TYPE vigil_request_latency_p95 gauge",
            f"vigil_request_latency_p95 {summary['p95']}",
            f"# HELP vigil_request_latency_p99 99th percentile request latency (ms)",
            f"# TYPE vigil_request_latency_p99 gauge",
            f"vigil_request_latency_p99 {summary['p99']}",
            f"# HELP vigil_active_requests Number of active requests",
            f"# TYPE vigil_active_requests gauge",
            f"vigil_active_requests {summary['active']}",
            f"# HELP vigil_total_requests Total requests processed",
            f"# TYPE vigil_total_requests counter",
            f"vigil_total_requests {summary['count']}",
        ]
        for key, count in summary.get("error_counts", {}).items():
            lines.append(f"# HELP vigil_errors_total Total errors by type")
            lines.append(f"# TYPE vigil_errors_total counter")
            lines.append(f'vigil_errors_total{{type="{key}"}} {count}')
        return "\n".join(lines) + "\n"


# Global metrics instance
metrics = MetricsCollector()


# ---------------------------------------------------------------------------
# Flask Middleware
# ---------------------------------------------------------------------------

def register_metrics_middleware(app: Flask) -> None:
    """Attach request latency tracking middleware to the Flask app."""

    @app.before_request
    def _before_request() -> None:
        g._vigil_start_time = time.time()
        metrics.inc_active()

    @app.after_request
    def _after_request(response) -> Any:  # noqa: ANN001
        if hasattr(g, "_vigil_start_time"):
            latency = time.time() - g._vigil_start_time
            metrics.dec_active()
            metrics.observe_latency(
                method=request.method,
                endpoint=request.endpoint or "unknown",
                status=response.status_code,
                latency=latency,
            )
        return response


# ---------------------------------------------------------------------------
# System Anomaly Detection
# ---------------------------------------------------------------------------

class SystemAnomalyDetector:
    """
    Detects anomalies in system metrics (CPU, memory) using rolling statistics.
    """

    def __init__(self, window_size: int = 100) -> None:
        self.window_size = window_size
        self._cpu_history: deque[float] = deque(maxlen=window_size)
        self._memory_history: deque[float] = deque(maxlen=window_size)

    def check(self) -> dict[str, Any]:
        """Run anomaly detection and return results."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory().percent
        except ImportError:
            cpu = 0.0
            memory = 0.0

        self._cpu_history.append(cpu)
        self._memory_history.append(memory)

        anomalies: list[str] = []

        if len(self._cpu_history) >= 10:
            cpu_mean = sum(self._cpu_history) / len(self._cpu_history)
            cpu_std = (sum((x - cpu_mean) ** 2 for x in self._cpu_history) / len(self._cpu_history)) ** 0.5
            if cpu_std > 0 and cpu > cpu_mean + 3 * cpu_std:
                anomalies.append(
                    f"CPU anomaly: {cpu}% (mean: {cpu_mean:.1f}%, std: {cpu_std:.1f}%)"
                )

        if memory > 85:
            anomalies.append(f"High memory usage: {memory}%")

        return {
            "anomalies": anomalies,
            "cpu": cpu,
            "memory": memory,
            "healthy": len(anomalies) == 0,
        }


# Global anomaly detector instance
anomaly_detector = SystemAnomalyDetector()
