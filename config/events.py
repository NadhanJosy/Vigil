from datetime import datetime, timezone


class EventType:
    NEW_ALERT = "new_alert"
    REGIME_SHIFT = "regime_shift"
    DETECTION_COMPLETE = "detection_complete"
    SYSTEM_ERROR = "system_error"


def build_alert_payload(alert_data: dict) -> dict:
    return {
        "event_type": EventType.NEW_ALERT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": alert_data,
    }


def build_regime_payload(old_regime: str, new_regime: str) -> dict:
    return {
        "event_type": EventType.REGIME_SHIFT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {"old": old_regime, "new": new_regime},
    }
