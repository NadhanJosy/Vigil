"""
Vigil Observability Module

Provides:
- Request ID middleware (X-Request-ID UUID injection)
- Structured JSON logging with request context
- Prometheus-compatible metrics (HTTP + trading-specific)
- System anomaly detection (CPU, memory)
"""

import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Prometheus Client Integration
# ---------------------------------------------------------------------------

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

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
# Prometheus Metrics Registry
# ---------------------------------------------------------------------------

# Use a dedicated registry to avoid conflicts with the default registry
REGISTRY = CollectorRegistry() if PROMETHEUS_AVAILABLE else None

# HTTP Metrics
HTTP_REQUEST_DURATION = None
HTTP_REQUESTS_TOTAL = None
HTTP_REQUEST_SIZE = None
HTTP_RESPONSE_SIZE = None

# Trading-specific Metrics
SIGNALS_GENERATED_TOTAL = None
ALERTS_DISPATCHED_TOTAL = None
SIGNAL_EDGE_SCORE = None
BACKTEST_DURATION = None
CORRELATION_COMPUTATION_DURATION = None

if PROMETHEUS_AVAILABLE and REGISTRY is not None:
    # HTTP Metrics
    HTTP_REQUEST_DURATION = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path", "status"],
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
        registry=REGISTRY,
    )
    HTTP_REQUESTS_TOTAL = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
        registry=REGISTRY,
    )
    HTTP_REQUEST_SIZE = Histogram(
        "http_request_size_bytes",
        "HTTP request size in bytes",
        ["method", "path"],
        buckets=(0, 1024, 10240, 102400, 1048576, 10485760),
        registry=REGISTRY,
    )
    HTTP_RESPONSE_SIZE = Histogram(
        "http_response_size_bytes",
        "HTTP response size in bytes",
        ["method", "path", "status"],
        buckets=(0, 1024, 10240, 102400, 1048576, 10485760),
        registry=REGISTRY,
    )

    # Trading-specific Metrics
    SIGNALS_GENERATED_TOTAL = Counter(
        "signals_generated_total",
        "Total signals generated",
        ["signal_type", "symbol"],
        registry=REGISTRY,
    )
    ALERTS_DISPATCHED_TOTAL = Counter(
        "alerts_dispatched_total",
        "Total alerts dispatched",
        ["channel", "status"],
        registry=REGISTRY,
    )
    SIGNAL_EDGE_SCORE = Gauge(
        "signal_edge_score",
        "Current signal edge score",
        ["symbol"],
        registry=REGISTRY,
    )
    BACKTEST_DURATION = Histogram(
        "backtest_duration_seconds",
        "Backtest execution duration in seconds",
        buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
        registry=REGISTRY,
    )
    CORRELATION_COMPUTATION_DURATION = Histogram(
        "correlation_matrix_computation_seconds",
        "Correlation matrix computation duration in seconds",
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
        registry=REGISTRY,
    )


# ---------------------------------------------------------------------------
# In-Memory Metrics Collector (backward compatibility)
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
            "# HELP vigil_request_latency_p50 50th percentile request latency (ms)",
            "# TYPE vigil_request_latency_p50 gauge",
            f"vigil_request_latency_p50 {summary['p50']}",
            "# HELP vigil_request_latency_p95 95th percentile request latency (ms)",
            "# TYPE vigil_request_latency_p95 gauge",
            f"vigil_request_latency_p95 {summary['p95']}",
            "# HELP vigil_request_latency_p99 99th percentile request latency (ms)",
            "# TYPE vigil_request_latency_p99 gauge",
            f"vigil_request_latency_p99 {summary['p99']}",
            "# HELP vigil_active_requests Number of active requests",
            "# TYPE vigil_active_requests gauge",
            f"vigil_active_requests {summary['active']}",
            "# HELP vigil_total_requests Total requests processed",
            "# TYPE vigil_total_requests counter",
            f"vigil_total_requests {summary['count']}",
        ]
        for key, count in summary.get("error_counts", {}).items():
            lines.append("# HELP vigil_errors_total Total errors by type")
            lines.append("# TYPE vigil_errors_total counter")
            lines.append(f'vigil_errors_total{{type="{key}"}} {count}')
        return "\n".join(lines) + "\n"


# Global metrics instance
metrics = MetricsCollector()


# ---------------------------------------------------------------------------
# Request ID Middleware
# ---------------------------------------------------------------------------

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Generates a unique X-Request-ID UUID for each request,
    injects it into response headers, and includes it in log context.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store request_id on the request state for downstream access
        request.state.request_id = request_id

        # Inject request_id into the logging context via a LogRecord filter
        _add_request_id_filter(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response


# Thread-local storage for current request_id
import contextvars

_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def _add_request_id_filter(request_id: str) -> None:
    """Set the current request_id in context for log filtering."""
    _request_id_ctx.set(request_id)


class RequestIDFilter(logging.Filter):
    """Inject request_id from context into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = _request_id_ctx.get()
        if request_id:
            record.request_id = request_id
        return True


# ---------------------------------------------------------------------------
# Structured JSON Logging Middleware
# ---------------------------------------------------------------------------

# Endpoints to exclude from logging (reduce noise)
EXCLUDED_LOG_PATHS = {"/health", "/health/", "/health/live", "/health/ready", "/metrics"}


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured JSON logging middleware.

    Log format:
    {"timestamp": "...", "method": "...", "path": "...", "status": ...,
     "duration_ms": ..., "request_id": "..."}

    Excludes health check endpoints to reduce noise.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip logging for excluded paths
        if request.url.path in EXCLUDED_LOG_PATHS:
            return await call_next(request)

        start_time = time.time()
        request_id = getattr(request.state, "request_id", None)

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }
        if request_id:
            log_entry["request_id"] = request_id

        # Log at INFO level for successful requests, WARN for 4xx, ERROR for 5xx
        if response.status_code >= 500:
            logging.getLogger("vigil.access").error(json.dumps(log_entry))
        elif response.status_code >= 400:
            logging.getLogger("vigil.access").warning(json.dumps(log_entry))
        else:
            logging.getLogger("vigil.access").info(json.dumps(log_entry))

        return response


# ---------------------------------------------------------------------------
# Prometheus Metrics Middleware
# ---------------------------------------------------------------------------

# Endpoints to exclude from Prometheus metrics
EXCLUDED_METRICS_PATHS = {"/health", "/health/", "/health/live", "/health/ready", "/metrics"}


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Prometheus metrics middleware.

    Tracks:
    - http_request_duration_seconds (Histogram)
    - http_requests_total (Counter)
    - http_request_size_bytes (Histogram)
    - http_response_size_bytes (Histogram)
    """

    async def dispatch(self, request: Request, call_next):
        # Skip metrics for excluded paths
        if request.url.path in EXCLUDED_METRICS_PATHS:
            return await call_next(request)

        start_time = time.time()

        # Capture request size
        content_length = request.headers.get("content-length")
        request_size = int(content_length) if content_length else 0

        response = await call_next(request)

        duration = time.time() - start_time
        status_code = response.status_code
        method = request.method
        path = request.url.path

        # Observe Prometheus metrics
        if PROMETHEUS_AVAILABLE and HTTP_REQUEST_DURATION is not None:
            HTTP_REQUEST_DURATION.labels(
                method=method, path=path, status=str(status_code)
            ).observe(duration)

        if PROMETHEUS_AVAILABLE and HTTP_REQUESTS_TOTAL is not None:
            HTTP_REQUESTS_TOTAL.labels(
                method=method, path=path, status=str(status_code)
            ).inc()

        if PROMETHEUS_AVAILABLE and HTTP_REQUEST_SIZE is not None:
            HTTP_REQUEST_SIZE.labels(method=method, path=path).observe(request_size)

        if PROMETHEUS_AVAILABLE and HTTP_RESPONSE_SIZE is not None:
            response_size = int(response.headers.get("content-length", 0))
            HTTP_RESPONSE_SIZE.labels(
                method=method, path=path, status=str(status_code)
            ).observe(response_size)

        # Also update in-memory collector for backward compatibility
        metrics.observe_latency(
            method=method,
            endpoint=path,
            status=status_code,
            latency=duration,
        )

        return response


# ---------------------------------------------------------------------------
# Trading-Specific Metrics Helpers
# ---------------------------------------------------------------------------

def record_signal_generated(signal_type: str, symbol: str) -> None:
    """Record a signal generation event."""
    if PROMETHEUS_AVAILABLE and SIGNALS_GENERATED_TOTAL is not None:
        SIGNALS_GENERATED_TOTAL.labels(signal_type=signal_type, symbol=symbol).inc()


def record_alert_dispatched(channel: str, status: str) -> None:
    """Record an alert dispatch event."""
    if PROMETHEUS_AVAILABLE and ALERTS_DISPATCHED_TOTAL is not None:
        ALERTS_DISPATCHED_TOTAL.labels(channel=channel, status=status).inc()


def set_signal_edge_score(symbol: str, score: float) -> None:
    """Set the current edge score for a symbol."""
    if PROMETHEUS_AVAILABLE and SIGNAL_EDGE_SCORE is not None:
        SIGNAL_EDGE_SCORE.labels(symbol=symbol).set(score)


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
