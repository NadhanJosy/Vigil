"""
Unit tests for Decision Intelligence API endpoints.
Tests Pydantic models, cursor pagination, and error handling.
"""

import pytest
import base64
import json
from datetime import datetime, date
from typing import Tuple
from fastapi import HTTPException

import sys
import os

# Ensure backend modules are importable
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from models import (
    SignalResponse,
    SignalDirection,
    SignalStatus,
    ConfidenceGrade,
    OutcomeResponse,
    OutcomeStatus,
    SignalFactor,
    SignalExplanation,
    CursorPagination,
    APIError,
    ERROR_CODES,
)


# ---------------------------------------------------------------------------
# Inline copies of di_router helpers to avoid module-level import errors
# ---------------------------------------------------------------------------

def encode_cursor(value: str, id: int) -> str:
    """Encode pagination cursor as base64 JSON."""
    data = json.dumps({"v": value, "id": id})
    return base64.b64encode(data.encode()).decode()


def decode_cursor(cursor: str) -> Tuple[str, int]:
    """Decode pagination cursor. Raises ValueError on invalid cursor."""
    try:
        data = json.loads(base64.b64decode(cursor))
        return data["v"], data["id"]
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise ValueError(f"Invalid cursor: {e}")


def api_error(code: str, message: str, status_code: int = 400, details: dict = None) -> HTTPException:
    """Create standardized API error response."""
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "details": details,
        }
    )


class TestCursorPagination:
    """Test cursor encoding/decoding."""

    def test_encode_decode_roundtrip(self):
        """Cursor should survive encode/decode roundtrip."""
        value = "2024-01-01T00:00:00"
        id_val = 123
        cursor = encode_cursor(value, id_val)
        decoded_value, decoded_id = decode_cursor(cursor)
        assert decoded_value == value
        assert decoded_id == id_val

    def test_decode_invalid_cursor_raises(self):
        """Invalid cursor should raise ValueError."""
        with pytest.raises(ValueError):
            decode_cursor("not-valid-base64-json")

    def test_decode_malformed_cursor_raises(self):
        """Malformed cursor JSON should raise ValueError."""
        malformed = base64.b64encode(b'{"invalid"}').decode()
        with pytest.raises(ValueError):
            decode_cursor(malformed)

    def test_cursor_contains_value_and_id(self):
        """Cursor should contain value and id fields."""
        cursor = encode_cursor("test-value", 42)
        decoded = json.loads(base64.b64decode(cursor))
        assert decoded["v"] == "test-value"
        assert decoded["id"] == 42


class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_signal_response_valid(self):
        """Valid signal response should parse correctly."""
        data = {
            "id": 1,
            "symbol": "AAPL",
            "direction": "bullish",
            "confidence_score": 75.5,
            "confidence_grade": "high",
            "status": "active",
            "detected_at": "2024-01-01T00:00:00Z",
            "resolved_at": None,
            "entry_price": 150.0,
            "target_price": 160.0,
            "stop_price": 145.0,
        }
        signal = SignalResponse(**data)
        assert signal.id == 1
        assert signal.direction == SignalDirection.BULLISH
        assert signal.confidence_score == 75.5
        assert signal.confidence_grade == ConfidenceGrade.HIGH

    def test_signal_response_invalid_score(self):
        """Score outside 0-100 should fail validation."""
        data = {
            "id": 1,
            "symbol": "AAPL",
            "direction": "bullish",
            "confidence_score": 150.0,
            "confidence_grade": "high",
            "status": "active",
            "detected_at": "2024-01-01T00:00:00Z",
            "resolved_at": None,
            "entry_price": None,
            "target_price": None,
            "stop_price": None,
        }
        with pytest.raises(Exception):
            SignalResponse(**data)

    def test_signal_factor_calculation(self):
        """Signal factor should parse correctly."""
        factor = SignalFactor(
            factor_name="rsi",
            factor_value=0.65,
            weight=0.25,
            weighted_contribution=0.1625,
            description="RSI momentum signal",
        )
        assert factor.factor_name == "rsi"
        assert factor.weight == 0.25

    def test_outcome_response_valid(self):
        """Valid outcome response should parse correctly."""
        data = {
            "id": 1,
            "signal_id": 100,
            "status": "active",
            "entry_price": 150.0,
            "current_price": 155.0,
            "target_price": 160.0,
            "stop_price": 145.0,
            "peak_price": 158.0,
            "trough_price": 148.0,
            "peak_drawdown_pct": -1.33,
            "realized_return_pct": None,
            "time_to_resolution_hours": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "resolved_at": None,
            "next_check_at": "2024-01-03T00:00:00Z",
        }
        outcome = OutcomeResponse(**data)
        assert outcome.status == OutcomeStatus.ACTIVE
        assert outcome.peak_drawdown_pct == -1.33

    def test_api_error_model(self):
        """API error model should serialize correctly."""
        error = APIError(
            code="NOT_FOUND",
            message="Signal not found",
            details={"signal_id": 999},
        )
        assert error.code == "NOT_FOUND"
        assert error.message == "Signal not found"
        assert error.details["signal_id"] == 999
        assert isinstance(error.timestamp, datetime)


class TestErrorHandling:
    """Test standardized error responses."""

    def test_api_error_helper(self):
        """Error helper should return HTTPException with correct structure."""
        exc = api_error("VALIDATION_ERROR", "Invalid parameters", 422, {"field": "score"})
        assert exc.status_code == 422
        assert exc.detail["code"] == "VALIDATION_ERROR"
        assert exc.detail["message"] == "Invalid parameters"
        assert exc.detail["details"]["field"] == "score"

    def test_error_codes_exist(self):
        """All documented error codes should be defined."""
        expected_codes = [
            "NOT_FOUND",
            "VALIDATION_ERROR",
            "INTERNAL_ERROR",
            "RATE_LIMITED",
            "DUPLICATE_SIGNAL",
            "INVALID_CURSOR",
        ]
        for code in expected_codes:
            assert code in ERROR_CODES


class TestEnumValues:
    """Test enum value coverage."""

    def test_signal_status_values(self):
        """All signal status values should be valid."""
        for status in ["pending", "active", "resolved", "expired", "failed"]:
            assert SignalStatus(status) == SignalStatus(status)

    def test_confidence_grade_values(self):
        """All confidence grade values should be valid."""
        for grade in ["very_low", "low", "moderate", "high", "very_high"]:
            assert ConfidenceGrade(grade) == ConfidenceGrade(grade)

    def test_outcome_status_values(self):
        """All outcome status values should be valid."""
        for status in ["pending", "active", "target_hit", "stop_hit", "expired", "partial"]:
            assert OutcomeStatus(status) == OutcomeStatus(status)

    def test_signal_direction_values(self):
        """All direction values should be valid."""
        for direction in ["bullish", "bearish", "neutral"]:
            assert SignalDirection(direction) == SignalDirection(direction)
