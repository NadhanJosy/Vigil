"""
Standardized Pydantic models for Vigil Decision Intelligence API.
All API responses use these models for consistency and type safety.
"""

from datetime import datetime, date
from typing import Optional, List, Any, Dict, Generic, TypeVar
from enum import Enum
from pydantic import BaseModel, Field


# ============ Enums ============

class SignalStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    FAILED = "failed"


class SignalDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ConfidenceGrade(str, Enum):
    VERY_LOW = "very_low"       # 0-20
    LOW = "low"                 # 21-40
    MODERATE = "moderate"       # 41-60
    HIGH = "high"               # 61-80
    VERY_HIGH = "very_high"     # 81-100


class OutcomeStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    TARGET_HIT = "target_hit"
    STOP_HIT = "stop_hit"
    EXPIRED = "expired"
    PARTIAL = "partial"


class RegimeType(str, Enum):
    BULL_TREND = "bull_trend"
    BEAR_TREND = "bear_trend"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRANSITION = "transition"


class SimulationType(str, Enum):
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    HISTORICAL = "historical"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


# ============ Error Models ============

class APIError(BaseModel):
    """Standardized error response."""
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    path: Optional[str] = Field(None, description="Request path")


# Error codes
ERROR_CODES = {
    "NOT_FOUND": "Resource not found",
    "VALIDATION_ERROR": "Invalid request parameters",
    "INTERNAL_ERROR": "Internal server error",
    "RATE_LIMITED": "Rate limit exceeded",
    "DUPLICATE_SIGNAL": "Signal already exists",
    "INVALID_CURSOR": "Invalid pagination cursor",
    "SIMULATION_EXISTS": "Simulation result already exists for these parameters",
    "NO_ACTIVE_WEIGHTS": "No active weight configuration found",
}


# ============ Pagination ============

class CursorPagination(BaseModel):
    """Cursor-based pagination metadata."""
    next_cursor: Optional[str] = Field(None, description="Base64-encoded cursor for next page")
    prev_cursor: Optional[str] = Field(None, description="Base64-encoded cursor for previous page")
    has_more: bool = Field(False, description="Whether more results exist")
    has_prev: bool = Field(False, description="Whether previous results exist")
    total_count: Optional[int] = Field(None, description="Total count (only on first page)")


T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    data: List[T]
    pagination: CursorPagination


# ============ Signal Models ============

class SignalFactor(BaseModel):
    """Individual factor contributing to a signal's score."""
    factor_name: str
    factor_value: float
    weight: float
    weighted_contribution: float
    description: Optional[str] = None


class SignalExplanation(BaseModel):
    """Structured explanation for a signal."""
    signal_id: int
    primary_trigger: str
    contributing_factors: List[SignalFactor]
    confidence_grade: ConfidenceGrade
    confidence_tier_thresholds: Dict[str, float]
    regime_context: Optional[str] = None
    generated_at: datetime


class SignalResponse(BaseModel):
    """Individual signal response."""
    id: int
    symbol: str
    direction: SignalDirection
    confidence_score: Optional[float] = Field(None, ge=0, le=100)
    confidence_grade: Optional[ConfidenceGrade] = None
    status: SignalStatus
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    explanation: Optional[SignalExplanation] = None
    outcome: Optional["OutcomeResponse"] = None


class SignalListResponse(BaseModel):
    """Paginated signal list response."""
    data: List[SignalResponse]
    pagination: CursorPagination


# ============ Signal Detail Models ============

class SignalDetailResponse(BaseModel):
    """Full signal detail with all related data."""
    signal: SignalResponse
    factors: List[SignalFactor]
    explanation: Optional[SignalExplanation] = None
    outcome: Optional["OutcomeResponse"] = None
    regime_at_detection: Optional[str] = None
    historical_context: Optional[Dict[str, Any]] = None


# ============ Outcome Models ============

class OutcomeResponse(BaseModel):
    """Signal outcome tracking."""
    id: int
    signal_id: int
    status: OutcomeStatus
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    peak_price: Optional[float] = None
    trough_price: Optional[float] = None
    peak_drawdown_pct: Optional[float] = None
    realized_return_pct: Optional[float] = None
    time_to_resolution_hours: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    next_check_at: Optional[datetime] = None


# ============ Regime Models ============

class RegimeStateResponse(BaseModel):
    """Current or historical regime state."""
    id: int
    regime_type: RegimeType
    confidence: float
    volatility_level: Optional[float] = None
    trend_strength: Optional[float] = None
    detected_at: datetime
    is_current: bool


# ============ Simulation Models ============

class EquityCurvePoint(BaseModel):
    """Single point in an equity curve."""
    date: str
    equity: float
    drawdown: float


class SimulationParams(BaseModel):
    """Simulation request parameters."""
    simulation_type: SimulationType
    start_date: date
    end_date: date
    initial_capital: float = Field(100000, ge=1000)
    position_sizing: str = Field("equal_weight", description="Position sizing method")
    max_exposure_pct: float = Field(100, ge=1, le=100)
    symbols: Optional[List[str]] = None


class SimulationResultResponse(BaseModel):
    """Simulation result response."""
    id: int
    simulation_name: str
    simulation_type: SimulationType
    params: Dict[str, Any]
    total_return_pct: Optional[float] = None
    annualized_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    total_signals: Optional[int] = None
    winning_signals: Optional[int] = None
    losing_signals: Optional[int] = None
    start_date: date
    end_date: date
    equity_curve: Optional[List[EquityCurvePoint]] = None
    result_hash: Optional[str] = None
    created_at: datetime


class SimulationListResponse(BaseModel):
    """Paginated simulation list response."""
    data: List[SimulationResultResponse]
    pagination: CursorPagination


# ============ Weight History Models ============

class WeightHistoryResponse(BaseModel):
    """Weight configuration history entry."""
    id: int
    weights: Dict[str, float]
    calibration_window_days: int
    sample_size: int
    win_rate_before: Optional[float] = None
    win_rate_after: Optional[float] = None
    statistical_significance: Optional[float] = None
    trigger_reason: str
    status: str
    effective_from: datetime
    effective_until: Optional[datetime] = None
    created_at: datetime


class ActiveWeightsResponse(BaseModel):
    """Current active weight configuration."""
    weights: Dict[str, float]
    effective_from: datetime
    calibration_window_days: int
    sample_size: int
    last_calibration_date: Optional[datetime] = None


# ============ Portfolio Risk Models ============

class PortfolioExposureResponse(BaseModel):
    """Current portfolio exposure summary."""
    total_active_signals: int
    total_exposure_pct: float
    max_single_position_pct: float
    sector_concentration: Optional[Dict[str, float]] = None
    regime_adjusted_risk: Optional[float] = None
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None


# ============ Health/Status Models ============

class SystemHealthResponse(BaseModel):
    """System health check response."""
    status: str = "healthy"
    last_poll_cycle: Optional[datetime] = None
    active_signals: int = 0
    pending_outcomes: int = 0
    current_regime: Optional[str] = None
    database_connected: bool = True
    cache_hit_rate: Optional[float] = None


# Forward reference resolution
SignalResponse.update_forward_refs()
SignalDetailResponse.update_forward_refs()
