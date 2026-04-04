"""
Vigil Feature Flags — Control real-time vs polling behavior via environment variables.
"""
import os


def is_realtime_enabled() -> bool:
    """When False, WebSocket endpoint and event bus subscriptions are skipped."""
    return os.environ.get("REALTIME_ENABLED", "true").lower() != "false"


def is_scheduler_enabled() -> bool:
    """When False, APScheduler is not started and no scheduled jobs run."""
    return os.environ.get("SCHEDULER_ENABLED", "true").lower() != "false"


def is_polling_mode() -> bool:
    """When True, enables polling-optimized behavior."""
    return os.environ.get("POLLING_MODE", "false").lower() == "true"
