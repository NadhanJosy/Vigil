"""
Vigil Decision Intelligence Router
==================================
Polling-triggered endpoints for signal scoring, outcome tracking,
self-evaluation, regime detection, explainability, and portfolio simulation.

All endpoints are stateless — no background tasks, no WebSockets.

Standardized API contract with Pydantic models, cursor-based pagination,
and consistent error responses.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, List, Optional, Tuple
from datetime import datetime, timezone, date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models import (
    SignalResponse,
    SignalListResponse,
    SignalDetailResponse,
    SignalExplanation as SignalExplanationModel,
    SignalFactor,
    ConfidenceGrade,
    SignalStatus,
    SignalDirection,
    OutcomeResponse,
    OutcomeStatus,
    RegimeStateResponse,
    RegimeType,
    SimulationResultResponse,
    SimulationListResponse,
    SimulationType,
    SimulationParams,
    EquityCurvePoint,
    WeightHistoryResponse,
    ActiveWeightsResponse,
    PortfolioExposureResponse,
    SystemHealthResponse,
    CursorPagination,
    PaginatedResponse,
    APIError,
    ERROR_CODES,
)
from services.lru_cache import get_di_cache, LRUCache
from services.scoring_engine import get_signal_scorer, SignalScorer, ScoreResult
from services.outcome_tracker import get_outcome_tracker, OutcomeTracker, OutcomeState
from services.self_evaluation import get_self_evaluator, SelfEvaluator, EvaluationReport
from services.regime_detector import get_regime_detector, RegimeDetector, RegimeVector
from services.explainability import get_explainability_engine, ExplainabilityEngine, ExplainabilityResult
from services.portfolio_risk import get_portfolio_simulator, PortfolioSimulator, SimulationResult

logger = logging.getLogger(__name__)

di_router = APIRouter(prefix="/api/di", tags=["decision-intelligence"])

# FIX 1: Whitelist of allowed sort columns to prevent SQL injection
ALLOWED_SORT_COLUMNS = {"detected_at", "confidence_score", "symbol", "status", "id", "created_at", "ticker", "signal_type", "regime", "action", "edge_score", "outcome_state", "entry_price", "target_price", "stop_price", "outcome_pct", "resolved_at"}
ALLOWED_SORT_DIRECTIONS = {"asc", "desc"}


# ---------------------------------------------------------------------------
# Cursor Pagination Helpers
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


def build_pagination(
    items: list,
    limit: int,
    cursor_field: str = "id",
    total_count: Optional[int] = None,
) -> CursorPagination:
    """Build cursor pagination metadata from a list of items."""
    if not items:
        return CursorPagination(has_more=False, has_prev=False, total_count=total_count)

    has_more = len(items) > limit
    if has_more:
        items = items[:limit]

    next_cursor = None
    prev_cursor = None

    if items:
        last_item = items[-1]
        cursor_value = last_item.get(cursor_field) or getattr(last_item, cursor_field, None)
        if cursor_value is not None:
            next_cursor = encode_cursor(str(cursor_value), cursor_value)

    return CursorPagination(
        next_cursor=next_cursor,
        prev_cursor=prev_cursor,
        has_more=has_more,
        has_prev=False,
        total_count=total_count,
    )


# ---------------------------------------------------------------------------
# Standardized Error Helper
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# DB Helper Dependency
# ---------------------------------------------------------------------------

async def get_db_pool():
    """FastAPI dependency that yields the asyncpg pool from database.get_pool()."""
    from database import get_pool
    pool = await get_pool()
    return pool


# ---------------------------------------------------------------------------
# Existing Pydantic Models (preserved for backward compatibility)
# ---------------------------------------------------------------------------

class ScoreResponse(BaseModel):
    """Response for signal scoring endpoints."""
    alert_id: int
    score: int = Field(..., ge=0, le=100)
    components: dict[str, float]
    version: Optional[str] = None


class TrackOutcomeRequest(BaseModel):
    """Request to create initial outcome record for a signal."""
    alert_id: int
    entry_price: float = Field(..., gt=0)
    target_price: Optional[float] = None
    stop_price: Optional[float] = None


class TrackOutcomeResponse(BaseModel):
    """Response after tracking a new outcome."""
    alert_id: int
    state: str
    created_at: str


class ClosedCandle(BaseModel):
    """Single closed candle data for outcome update."""
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    timestamp: str


class UpdateOutcomesRequest(BaseModel):
    """Request for idempotent batch update of active outcomes."""
    closed_candles: List[ClosedCandle] = Field(..., min_length=1)


class OutcomeItem(BaseModel):
    """Single outcome item in response."""
    alert_id: int
    state: str
    realized_pnl: Optional[float] = None


class UpdateOutcomesResponse(BaseModel):
    """Response after batch outcome update."""
    updated_count: int
    outcomes: List[OutcomeItem]


class ActiveOutcomesResponse(BaseModel):
    """Response for active outcomes query."""
    count: int
    outcomes: List[OutcomeItem]


class DetectRegimeRequest(BaseModel):
    """Request for regime detection."""
    symbol: str
    timeframe: str = Field(default="1D")
    ohlcv: List[dict[str, Any]] = Field(..., min_length=1)


class RegimeResponse(BaseModel):
    """Response for regime detection endpoints."""
    symbol: str
    timeframe: str
    regime: str
    trend_slope: float
    momentum: float
    volatility_pct: float
    breadth: float
    alignment_scores: dict[str, float]


class EvaluateRequest(BaseModel):
    """Request for self-evaluation cohort analysis."""
    lookback_days: int = Field(default=30, gt=0, le=365)
    signal_type: Optional[str] = None


class EvaluateResponse(BaseModel):
    """Response for self-evaluation endpoint."""
    version: str
    cohort_size: int
    win_rate: float
    decay_half_life: Optional[float] = None
    failure_modes: dict[str, str] = Field(default_factory=dict)
    degraded_signals: List[str] = Field(default_factory=list)
    new_weights: dict[str, float] = Field(default_factory=dict)


class ExplainResponse(BaseModel):
    """Response for explainability endpoint."""
    alert_id: int
    score: int
    trigger_conditions: dict[str, Any]
    factor_weights: dict[str, Any]
    regime_impact: dict[str, Any]
    reasoning: str
    ui_format: dict[str, Any]


class SignalInput(BaseModel):
    """Single signal input for portfolio simulation."""
    alert_id: int
    signal_type: str
    score: int = Field(..., ge=0, le=100)
    entry_price: float = Field(..., gt=0)
    target_price: Optional[float] = None
    stop_price: Optional[float] = None


class SimulateRequest(BaseModel):
    """Request for portfolio simulation."""
    signals: List[SignalInput] = Field(..., min_length=1, max_length=50)
    account_balance: float = Field(..., gt=0)
    max_drawdown_pct: float = Field(default=0.15, gt=0, le=1.0)


class PositionSizeItem(BaseModel):
    """Position sizing result for a single signal."""
    alert_id: int
    size_pct: float
    kelly_fraction: float


class SimulateResponse(BaseModel):
    """Response for portfolio simulation endpoint."""
    cumulative_returns: float
    max_drawdown: float
    sharpe_ratio: float
    trade_distribution: dict[str, int]
    position_sizes: List[PositionSizeItem]


class CacheStatsResponse(BaseModel):
    """Response for LRU cache statistics."""
    size: int
    max_size: int
    hits: int
    misses: int
    hit_rate: float


# ---------------------------------------------------------------------------
# New Standardized Request/Response Models
# ---------------------------------------------------------------------------

class OutcomeResolveRequest(BaseModel):
    """Request for manual outcome resolution."""
    status: OutcomeStatus
    realized_return_pct: Optional[float] = None
    resolved_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/signals — Paginated signal list
# ---------------------------------------------------------------------------

@di_router.get(
    "/signals",
    response_model=SignalListResponse,
    summary="List signals",
    description="Paginated signal list with filtering and sorting.",
)
async def list_signals(
    cursor: Optional[str] = Query(None, description="Base64-encoded pagination cursor"),
    limit: int = Query(20, gt=0, le=100),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    status: Optional[str] = Query(None, description="Filter by signal status"),
    direction: Optional[str] = Query(None, description="Filter by direction (bullish/bearish/neutral)"),
    min_confidence: Optional[float] = Query(None, ge=0, le=100),
    max_confidence: Optional[float] = Query(None, ge=0, le=100),
    sort_by: str = Query("detected_at", description="Field to sort by"),
    sort_dir: str = Query("desc", description="Sort direction (asc/desc)"),
    pool=Depends(get_db_pool),
):
    """
    Fetch paginated list of signals with optional filtering and sorting.

    Uses cursor-based pagination for efficient large dataset traversal.
    """
    try:
        # Decode cursor if provided
        cursor_value = None
        cursor_id = None
        if cursor:
            try:
                cursor_value, cursor_id = decode_cursor(cursor)
            except ValueError as e:
                raise api_error("INVALID_CURSOR", str(e), status_code=400)

        # FIX 1: Validate sort_by and sort_dir against whitelists to prevent SQL injection
        if sort_by not in ALLOWED_SORT_COLUMNS:
            logger.warning(f"Invalid sort_by parameter: {sort_by}")
            sort_by = "created_at"
        if sort_dir.lower() not in ALLOWED_SORT_DIRECTIONS:
            logger.warning(f"Invalid sort_dir parameter: {sort_dir}")
            sort_dir = "desc"

        # Build query
        where_clauses = []
        params: list = []
        param_idx = 1

        if symbol:
            where_clauses.append(f"a.ticker = ${param_idx}")
            params.append(symbol.upper())
            param_idx += 1

        if status:
            where_clauses.append(f"so.state = ${param_idx}")
            params.append(status.upper())
            param_idx += 1

        if direction:
            # Map direction to signal_type filter
            direction_map = {
                "bullish": "BULLISH",
                "bearish": "BEARISH",
                "neutral": "NEUTRAL",
            }
            mapped = direction_map.get(direction.lower())
            if mapped:
                where_clauses.append(f"a.signal_type = ${param_idx}")
                params.append(mapped)
                param_idx += 1

        if min_confidence is not None:
            where_clauses.append(f"ss.score >= ${param_idx}")
            params.append(int(min_confidence))
            param_idx += 1

        if max_confidence is not None:
            where_clauses.append(f"ss.score <= ${param_idx}")
            params.append(int(max_confidence))
            param_idx += 1

        # Cursor-based pagination
        if cursor_value and cursor_id:
            if sort_dir.lower() == "desc":
                where_clauses.append(f"(a.{sort_by} < ${param_idx} OR (a.{sort_by} = ${param_idx} AND a.id < ${param_idx + 1}))")
            else:
                where_clauses.append(f"(a.{sort_by} > ${param_idx} OR (a.{sort_by} = ${param_idx} AND a.id > ${param_idx + 1}))")
            params.append(cursor_value)
            params.append(cursor_id)
            param_idx += 2

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Fetch signals with scores and outcomes
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT a.id, a.ticker, a.signal_type, a.regime, a.action,
                       a.created_at, a.edge_score,
                       ss.score as confidence_score,
                       so.state as outcome_state, so.entry_price,
                       so.target_price, so.stop_price, so.outcome_pct,
                       so.resolved_at
                FROM alerts a
                LEFT JOIN signal_scores ss ON ss.signal_id = a.id
                LEFT JOIN signal_outcomes so ON so.signal_id = a.id
                WHERE {where_sql}
                ORDER BY a.{sort_by} {sort_dir.upper()}, a.id {sort_dir.upper()}
                LIMIT ${param_idx}
                """,
                *params,
                limit + 1,  # Fetch one extra to check has_more
            )

        # Get total count (only on first page)
        total_count = None
        if cursor is None:
            async with pool.acquire() as conn:
                count_row = await conn.fetchrow(
                    f"""
                    SELECT COUNT(*) FROM alerts a
                    LEFT JOIN signal_scores ss ON ss.signal_id = a.id
                    LEFT JOIN signal_outcomes so ON so.signal_id = a.id
                    WHERE {where_sql}
                    """,
                    *params,
                )
                total_count = count_row["count"] if count_row else 0

        # Transform to response models
        signals = []
        for row in rows[:limit]:
            direction = SignalDirection.NEUTRAL
            sig_type = row["signal_type"] or ""
            if "BULL" in sig_type.upper():
                direction = SignalDirection.BULLISH
            elif "BEAR" in sig_type.upper():
                direction = SignalDirection.BEARISH

            status_val = SignalStatus.ACTIVE
            outcome_state = row.get("outcome_state")
            if outcome_state:
                state_map = {
                    "PENDING": SignalStatus.PENDING,
                    "ACTIVE": SignalStatus.ACTIVE,
                    "TARGET_HIT": SignalStatus.RESOLVED,
                    "STOP_HIT": SignalStatus.RESOLVED,
                    "TIME_EXPIRED": SignalStatus.EXPIRED,
                    "CLOSED": SignalStatus.RESOLVED,
                }
                status_val = state_map.get(outcome_state, SignalStatus.ACTIVE)

            signal = SignalResponse(
                id=row["id"],
                symbol=row["ticker"] or "UNKNOWN",
                direction=direction,
                confidence_score=float(row["confidence_score"]) if row.get("confidence_score") is not None else None,
                confidence_grade=_score_to_grade(row.get("confidence_score")),
                status=status_val,
                detected_at=row["created_at"],
                resolved_at=row.get("resolved_at"),
                entry_price=row.get("entry_price"),
                target_price=row.get("target_price"),
                stop_price=row.get("stop_price"),
            )
            signals.append(signal)

        pagination = build_pagination(
            items=[{"id": s.id} for s in signals] + ([{"id": -1}] if len(rows) > limit else []),
            limit=limit,
            total_count=total_count,
        )

        return SignalListResponse(data=signals[:limit], pagination=pagination)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing signals: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to list signals", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/signals/{signal_id} — Full signal detail
# ---------------------------------------------------------------------------

@di_router.get(
    "/signals/{signal_id}",
    response_model=SignalDetailResponse,
    summary="Get signal detail",
    description="Full signal detail with all related data.",
)
async def get_signal_detail(
    signal_id: int,
    pool=Depends(get_db_pool),
):
    """Fetch full signal detail including factors, explanation, and outcome."""
    try:
        async with pool.acquire() as conn:
            alert = await conn.fetchrow(
                """
                SELECT a.*, ss.score as confidence_score
                FROM alerts a
                LEFT JOIN signal_scores ss ON ss.signal_id = a.id
                WHERE a.id = $1
                ORDER BY ss.computed_at DESC
                LIMIT 1
                """,
                signal_id,
            )

        if alert is None:
            raise api_error("NOT_FOUND", f"Signal {signal_id} not found", status_code=404)

        # Build direction
        direction = SignalDirection.NEUTRAL
        sig_type = alert.get("signal_type") or ""
        if "BULL" in sig_type.upper():
            direction = SignalDirection.BULLISH
        elif "BEAR" in sig_type.upper():
            direction = SignalDirection.BEARISH

        # Build factors from alert data
        factors = []
        if alert.get("adx_strength") is not None:
            factors.append(SignalFactor(
                factor_name="adx_strength",
                factor_value=float(alert["adx_strength"]),
                weight=0.25,
                weighted_contribution=float(alert["adx_strength"]) * 0.25,
                description="Trend strength indicator",
            ))
        if alert.get("momentum_score") is not None:
            factors.append(SignalFactor(
                factor_name="momentum_score",
                factor_value=float(alert["momentum_score"]),
                weight=0.25,
                weighted_contribution=float(alert["momentum_score"]) * 0.25,
                description="Price momentum score",
            ))

        # Build signal response
        signal = SignalResponse(
            id=alert["id"],
            symbol=alert["ticker"] or "UNKNOWN",
            direction=direction,
            confidence_score=float(alert["confidence_score"]) if alert.get("confidence_score") else None,
            confidence_grade=_score_to_grade(alert.get("confidence_score")),
            status=SignalStatus.ACTIVE,
            detected_at=alert["created_at"],
        )

        return SignalDetailResponse(
            signal=signal,
            factors=factors,
            regime_at_detection=alert.get("regime"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching signal detail {signal_id}: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to fetch signal detail", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/signals/{signal_id}/explanation
# ---------------------------------------------------------------------------

@di_router.get(
    "/signals/{signal_id}/explanation",
    response_model=SignalExplanationModel,
    summary="Get signal explanation",
    description="Structured explanation for a signal's score.",
)
async def get_signal_explanation(
    signal_id: int,
    pool=Depends(get_db_pool),
):
    """Fetch structured explanation for a signal."""
    try:
        engine = get_explainability_engine(pool=pool)
        result: ExplainabilityResult = await engine.explain_signal(signal_id)

        # Build contributing factors
        factors = []
        breakdown = result.breakdown.get("factors", {})
        for name, data in breakdown.items():
            if isinstance(data, dict):
                factors.append(SignalFactor(
                    factor_name=name,
                    factor_value=data.get("score", 0),
                    weight=data.get("weight", 0),
                    weighted_contribution=data.get("contribution", 0),
                ))

        return SignalExplanationModel(
            signal_id=result.signal_id,
            primary_trigger=result.breakdown.get("trigger", {}).get("signal_type", "unknown"),
            contributing_factors=factors,
            confidence_grade=_score_to_grade(result.score),
            confidence_tier_thresholds={
                "very_low": 0,
                "low": 20,
                "moderate": 40,
                "high": 60,
                "very_high": 80,
            },
            regime_context=result.regime_impact.get("current_regime"),
            generated_at=datetime.fromisoformat(result.generated_at) if isinstance(result.generated_at, str) else datetime.utcnow(),
        )

    except ValueError as e:
        raise api_error("NOT_FOUND", str(e), status_code=404)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error explaining signal {signal_id}: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to explain signal", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/outcomes — Outcome list with filtering
# ---------------------------------------------------------------------------

@di_router.get(
    "/outcomes",
    response_model=PaginatedResponse[OutcomeResponse],
    summary="List outcomes",
    description="Outcome list with filtering and cursor pagination.",
)
async def list_outcomes(
    cursor: Optional[str] = Query(None, description="Base64-encoded pagination cursor"),
    limit: int = Query(20, gt=0, le=100),
    status: Optional[str] = Query(None, description="Filter by outcome status"),
    signal_id: Optional[int] = Query(None, description="Filter by signal ID"),
    pool=Depends(get_db_pool),
):
    """Fetch paginated list of signal outcomes."""
    try:
        # Decode cursor
        cursor_id = None
        if cursor:
            try:
                _, cursor_id = decode_cursor(cursor)
            except ValueError as e:
                raise api_error("INVALID_CURSOR", str(e), status_code=400)

        where_clauses = []
        params: list = []
        param_idx = 1

        if status:
            where_clauses.append(f"so.state = ${param_idx}")
            params.append(status.upper())
            param_idx += 1

        if signal_id:
            where_clauses.append(f"so.signal_id = ${param_idx}")
            params.append(signal_id)
            param_idx += 1

        if cursor_id:
            where_clauses.append(f"so.id < ${param_idx}")
            params.append(cursor_id)
            param_idx += 1

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT so.*
                FROM signal_outcomes so
                WHERE {where_sql}
                ORDER BY so.id DESC
                LIMIT ${param_idx}
                """,
                *params,
                limit + 1,
            )

        outcomes = []
        for row in rows[:limit]:
            state = row.get("state", "PENDING")
            status_map = {
                "PENDING": OutcomeStatus.PENDING,
                "ACTIVE": OutcomeStatus.ACTIVE,
                "TARGET_HIT": OutcomeStatus.TARGET_HIT,
                "STOP_HIT": OutcomeStatus.STOP_HIT,
                "TIME_EXPIRED": OutcomeStatus.EXPIRED,
                "CLOSED": OutcomeStatus.PARTIAL,
            }

            # Calculate time to resolution
            time_to_resolution = None
            if row.get("resolved_at") and row.get("updated_at"):
                resolved = row["resolved_at"]
                created = row.get("updated_at") or row.get("created_at")
                if resolved and created:
                    if hasattr(resolved, 'timestamp') and hasattr(created, 'timestamp'):
                        time_to_resolution = (resolved - created).total_seconds() / 3600

            outcome = OutcomeResponse(
                id=row["id"],
                signal_id=row["signal_id"],
                status=status_map.get(state, OutcomeStatus.PENDING),
                entry_price=row.get("entry_price"),
                current_price=row.get("exit_price"),
                target_price=row.get("target_price"),
                stop_price=row.get("stop_price"),
                peak_price=row.get("max_favorable_excursion"),
                trough_price=row.get("max_adverse_excursion"),
                realized_return_pct=row.get("outcome_pct"),
                time_to_resolution_hours=time_to_resolution,
                created_at=row.get("updated_at") or datetime.utcnow(),
                updated_at=row.get("updated_at") or datetime.utcnow(),
                resolved_at=row.get("resolved_at"),
            )
            outcomes.append(outcome)

        has_more = len(rows) > limit
        pagination = build_pagination(
            items=[{"id": o.id} for o in outcomes] + ([{"id": -1}] if has_more else []),
            limit=limit,
        )

        return PaginatedResponse(data=outcomes[:limit], pagination=pagination)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing outcomes: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to list outcomes", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/outcomes/{outcome_id} — Single outcome detail
# ---------------------------------------------------------------------------

@di_router.get(
    "/outcomes/{outcome_id}",
    response_model=OutcomeResponse,
    summary="Get outcome detail",
    description="Single outcome detail.",
)
async def get_outcome_detail(
    outcome_id: int,
    pool=Depends(get_db_pool),
):
    """Fetch single outcome detail."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM signal_outcomes WHERE id = $1",
                outcome_id,
            )

        if row is None:
            raise api_error("NOT_FOUND", f"Outcome {outcome_id} not found", status_code=404)

        state = row.get("state", "PENDING")
        status_map = {
            "PENDING": OutcomeStatus.PENDING,
            "ACTIVE": OutcomeStatus.ACTIVE,
            "TARGET_HIT": OutcomeStatus.TARGET_HIT,
            "STOP_HIT": OutcomeStatus.STOP_HIT,
            "TIME_EXPIRED": OutcomeStatus.EXPIRED,
            "CLOSED": OutcomeStatus.PARTIAL,
        }

        return OutcomeResponse(
            id=row["id"],
            signal_id=row["signal_id"],
            status=status_map.get(state, OutcomeStatus.PENDING),
            entry_price=row.get("entry_price"),
            current_price=row.get("exit_price"),
            target_price=row.get("target_price"),
            stop_price=row.get("stop_price"),
            realized_return_pct=row.get("outcome_pct"),
            created_at=row.get("updated_at") or datetime.utcnow(),
            updated_at=row.get("updated_at") or datetime.utcnow(),
            resolved_at=row.get("resolved_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching outcome {outcome_id}: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to fetch outcome", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: POST /api/di/outcomes/{outcome_id}/resolve — Manual resolution
# ---------------------------------------------------------------------------

@di_router.post(
    "/outcomes/{outcome_id}/resolve",
    response_model=OutcomeResponse,
    summary="Resolve outcome",
    description="Manually resolve a signal outcome.",
)
async def resolve_outcome(
    outcome_id: int,
    req: OutcomeResolveRequest,
    pool=Depends(get_db_pool),
):
    """Manually resolve a signal outcome."""
    try:
        async with pool.acquire() as conn:
            # Check if outcome exists
            existing = await conn.fetchrow(
                "SELECT * FROM signal_outcomes WHERE id = $1",
                outcome_id,
            )
            if existing is None:
                raise api_error("NOT_FOUND", f"Outcome {outcome_id} not found", status_code=404)

            # Update outcome
            resolved_at = req.resolved_at or datetime.utcnow()
            await conn.execute(
                """
                UPDATE signal_outcomes
                SET state = $1,
                    outcome_pct = COALESCE($2, outcome_pct),
                    resolved_at = $3,
                    updated_at = NOW()
                WHERE id = $4
                """,
                req.status.value.upper(),
                req.realized_return_pct,
                resolved_at,
                outcome_id,
            )

            # Fetch updated row
            row = await conn.fetchrow(
                "SELECT * FROM signal_outcomes WHERE id = $1",
                outcome_id,
            )

        status_map = {
            "PENDING": OutcomeStatus.PENDING,
            "ACTIVE": OutcomeStatus.ACTIVE,
            "TARGET_HIT": OutcomeStatus.TARGET_HIT,
            "STOP_HIT": OutcomeStatus.STOP_HIT,
            "TIME_EXPIRED": OutcomeStatus.EXPIRED,
            "CLOSED": OutcomeStatus.PARTIAL,
        }

        return OutcomeResponse(
            id=row["id"],
            signal_id=row["signal_id"],
            status=status_map.get(row.get("state", "PENDING"), OutcomeStatus.PENDING),
            entry_price=row.get("entry_price"),
            current_price=row.get("exit_price"),
            target_price=row.get("target_price"),
            stop_price=row.get("stop_price"),
            realized_return_pct=row.get("outcome_pct"),
            created_at=row.get("updated_at") or datetime.utcnow(),
            updated_at=row.get("updated_at") or datetime.utcnow(),
            resolved_at=row.get("resolved_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving outcome {outcome_id}: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to resolve outcome", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/regimes/current — Current regime state
# ---------------------------------------------------------------------------

@di_router.get(
    "/regimes/current",
    response_model=RegimeStateResponse,
    summary="Get current regime",
    description="Current market regime state.",
)
async def get_current_regime(
    pool=Depends(get_db_pool),
):
    """Fetch current market regime state."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT rc.*, a.regime as alert_regime
                FROM regime_cache rc
                LEFT JOIN alerts a ON a.ticker = rc.symbol
                WHERE rc.expires_at > NOW()
                ORDER BY rc.computed_at DESC
                LIMIT 1
                """,
            )

        if row is None:
            # Fallback to latest alert regime
            async with pool.acquire() as conn:
                alert_row = await conn.fetchrow(
                    "SELECT regime, created_at FROM alerts WHERE regime IS NOT NULL ORDER BY created_at DESC LIMIT 1",
                )
            if alert_row is None:
                raise api_error("NOT_FOUND", "No regime data available", status_code=404)

            regime_type = alert_row["regime"].lower().replace(" ", "_")
            try:
                regime_enum = RegimeType(regime_type)
            except ValueError:
                regime_enum = RegimeType.TRANSITION

            return RegimeStateResponse(
                id=0,
                regime_type=regime_enum,
                confidence=0.5,
                detected_at=alert_row["created_at"],
                is_current=True,
            )

        regime_type = row.get("regime_vector", {}).get("regime", "transition") if row.get("regime_vector") else "transition"
        if isinstance(regime_type, str):
            regime_type = regime_type.lower().replace(" ", "_")

        try:
            regime_enum = RegimeType(regime_type)
        except ValueError:
            regime_enum = RegimeType.TRANSITION

        return RegimeStateResponse(
            id=row["id"],
            regime_type=regime_enum,
            confidence=float(row.get("confidence", 0.5)),
            detected_at=row["computed_at"],
            is_current=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching current regime: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to fetch regime", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/regimes/history — Historical regime states
# ---------------------------------------------------------------------------

@di_router.get(
    "/regimes/history",
    response_model=PaginatedResponse[RegimeStateResponse],
    summary="List regime history",
    description="Historical regime states with pagination.",
)
async def list_regimes_history(
    cursor: Optional[str] = Query(None, description="Base64-encoded pagination cursor"),
    limit: int = Query(20, gt=0, le=100),
    pool=Depends(get_db_pool),
):
    """Fetch historical regime states."""
    try:
        cursor_id = None
        if cursor:
            try:
                _, cursor_id = decode_cursor(cursor)
            except ValueError as e:
                raise api_error("INVALID_CURSOR", str(e), status_code=400)

        where_sql = "rc.id < $1" if cursor_id else "1=1"
        params = [cursor_id] if cursor_id else []

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT rc.*
                FROM regime_cache rc
                WHERE {where_sql}
                ORDER BY rc.computed_at DESC
                LIMIT ${len(params) + 1}
                """,
                *params,
                limit + 1,
            )

        regimes = []
        for row in rows[:limit]:
            regime_type = "transition"
            if row.get("regime_vector"):
                rv = row["regime_vector"]
                if isinstance(rv, dict):
                    regime_type = rv.get("regime", "transition").lower().replace(" ", "_")

            try:
                regime_enum = RegimeType(regime_type)
            except ValueError:
                regime_enum = RegimeType.TRANSITION

            regimes.append(RegimeStateResponse(
                id=row["id"],
                regime_type=regime_enum,
                confidence=float(row.get("confidence", 0.5)),
                detected_at=row["computed_at"],
                is_current=False,
            ))

        has_more = len(rows) > limit
        pagination = build_pagination(
            items=[{"id": r.id} for r in regimes] + ([{"id": -1}] if has_more else []),
            limit=limit,
        )

        return PaginatedResponse(data=regimes[:limit], pagination=pagination)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing regime history: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to list regimes", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: POST /api/di/simulations/run — Run portfolio simulation
# ---------------------------------------------------------------------------

@di_router.post(
    "/simulations/run",
    response_model=SimulationResultResponse,
    summary="Run simulation",
    description="Run portfolio simulation with specified parameters.",
)
async def run_simulation(
    req: SimulationParams,
    pool=Depends(get_db_pool),
):
    """Run a new portfolio simulation and persist results."""
    try:
        # Check for existing simulation with same params
        import hashlib
        param_hash = hashlib.sha256(
            json.dumps(req.model_dump(), sort_keys=True, default=str).encode()
        ).hexdigest()

        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM di_simulation_results WHERE result_hash = $1",
                param_hash,
            )
            if existing:
                return _simulation_row_to_response(existing)

        # Run simulation using existing portfolio simulator
        simulator = get_portfolio_simulator(pool=pool)

        # Fetch signals for the simulation period
        async with pool.acquire() as conn:
            signals = await conn.fetch(
                """
                SELECT a.id, a.ticker, a.signal_type, a.edge_score,
                       ss.score, so.entry_price, so.target_price, so.stop_price
                FROM alerts a
                LEFT JOIN signal_scores ss ON ss.signal_id = a.id
                LEFT JOIN signal_outcomes so ON so.signal_id = a.id
                WHERE a.created_at >= $1 AND a.created_at <= $2
                ORDER BY a.created_at DESC
                """,
                req.start_date,
                req.end_date,
            )

        if not signals:
            # Return empty simulation result
            result = SimulationResultResponse(
                id=0,
                simulation_name=f"sim_{req.simulation_type.value}_{req.start_date}",
                simulation_type=req.simulation_type,
                params=req.model_dump(),
                total_return_pct=0,
                annualized_return_pct=0,
                max_drawdown_pct=0,
                sharpe_ratio=0,
                sortino_ratio=0,
                calmar_ratio=0,
                win_rate=0,
                profit_factor=0,
                total_signals=0,
                winning_signals=0,
                losing_signals=0,
                start_date=req.start_date,
                end_date=req.end_date,
                created_at=datetime.utcnow(),
            )
            return result

        # Transform signals for simulator
        sim_signals = []
        for sig in signals:
            sim_signals.append({
                "signal_id": sig["id"],
                "ticker": sig["ticker"],
                "score": sig["score"] or 50,
                "entry_price": sig.get("entry_price") or 100,
                "stop_price": sig.get("stop_price"),
                "target_price": sig.get("target_price"),
            })

        # Run simulation (FIX 5: renamed to calculate_portfolio_metrics)
        sim_result = simulator.calculate_portfolio_metrics(
            signals=sim_signals,
            account_balance=req.initial_capital,
            max_drawdown_pct=req.max_exposure_pct / 100,
        )

        # Calculate win/loss counts
        winning = sum(1 for s in sim_signals if s.get("score", 50) > 50)
        losing = len(sim_signals) - winning

        # Build equity curve
        equity_curve = []
        if sim_result.equity_curve:
            for point in sim_result.equity_curve:
                equity_curve.append(EquityCurvePoint(
                    date=point.get("date", ""),
                    equity=point.get("equity", 0),
                    drawdown=point.get("drawdown", 0),
                ))

        # Persist result
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO di_simulation_results (
                    simulation_name, simulation_type, params,
                    total_return_pct, annualized_return_pct, max_drawdown_pct,
                    sharpe_ratio, sortino_ratio, calmar_ratio,
                    win_rate, profit_factor,
                    total_signals, winning_signals, losing_signals,
                    start_date, end_date, equity_curve, result_hash
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                RETURNING *
                """,
                f"sim_{req.simulation_type.value}_{req.start_date}",
                req.simulation_type.value,
                req.model_dump(),
                sim_result.cumulative_return_pct,
                None,  # annualized_return_pct
                sim_result.max_drawdown_pct,
                sim_result.sharpe_ratio,
                None,  # sortino_ratio
                None,  # calmar_ratio
                winning / len(sim_signals) if sim_signals else 0,
                None,  # profit_factor
                len(sim_signals),
                winning,
                losing,
                req.start_date,
                req.end_date,
                json.dumps([e.model_dump() for e in equity_curve]) if equity_curve else None,
                param_hash,
            )

        return _simulation_row_to_response(row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running simulation: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to run simulation", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/simulations — Simulation history
# ---------------------------------------------------------------------------

@di_router.get(
    "/simulations",
    response_model=SimulationListResponse,
    summary="List simulations",
    description="Simulation history with pagination.",
)
async def list_simulations(
    cursor: Optional[str] = Query(None, description="Base64-encoded pagination cursor"),
    limit: int = Query(20, gt=0, le=100),
    simulation_type: Optional[str] = Query(None, description="Filter by simulation type"),
    pool=Depends(get_db_pool),
):
    """Fetch paginated simulation history."""
    try:
        cursor_id = None
        if cursor:
            try:
                _, cursor_id = decode_cursor(cursor)
            except ValueError as e:
                raise api_error("INVALID_CURSOR", str(e), status_code=400)

        where_clauses = []
        params: list = []
        param_idx = 1

        if simulation_type:
            where_clauses.append(f"simulation_type = ${param_idx}")
            params.append(simulation_type)
            param_idx += 1

        if cursor_id:
            where_clauses.append(f"id < ${param_idx}")
            params.append(cursor_id)
            param_idx += 1

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT *
                FROM di_simulation_results
                WHERE {where_sql}
                ORDER BY id DESC
                LIMIT ${param_idx}
                """,
                *params,
                limit + 1,
            )

        simulations = [_simulation_row_to_response(row) for row in rows[:limit]]
        has_more = len(rows) > limit
        pagination = build_pagination(
            items=[{"id": s.id} for s in simulations] + ([{"id": -1}] if has_more else []),
            limit=limit,
        )

        return SimulationListResponse(data=simulations[:limit], pagination=pagination)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing simulations: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to list simulations", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/simulations/{simulation_id} — Single simulation
# ---------------------------------------------------------------------------

@di_router.get(
    "/simulations/{simulation_id}",
    response_model=SimulationResultResponse,
    summary="Get simulation result",
    description="Single simulation result detail.",
)
async def get_simulation_result(
    simulation_id: int,
    pool=Depends(get_db_pool),
):
    """Fetch single simulation result."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM di_simulation_results WHERE id = $1",
                simulation_id,
            )

        if row is None:
            raise api_error("NOT_FOUND", f"Simulation {simulation_id} not found", status_code=404)

        return _simulation_row_to_response(row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching simulation {simulation_id}: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to fetch simulation", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/weights/active — Current active weights
# ---------------------------------------------------------------------------

@di_router.get(
    "/weights/active",
    response_model=ActiveWeightsResponse,
    summary="Get active weights",
    description="Current active weight configuration.",
)
async def get_active_weights(
    pool=Depends(get_db_pool),
):
    """Fetch current active weight configuration."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM di_weight_history
                WHERE status = 'active'
                LIMIT 1
                """,
            )

        if row is None:
            # Fallback to default weights
            return ActiveWeightsResponse(
                weights={
                    "hit_rate": 0.30,
                    "regime_alignment": 0.25,
                    "volatility": 0.20,
                    "confluence": 0.25,
                },
                effective_from=datetime.utcnow(),
                calibration_window_days=90,
                sample_size=0,
            )

        return ActiveWeightsResponse(
            weights=row["weights"],
            effective_from=row["effective_from"],
            calibration_window_days=row["calibration_window_days"],
            sample_size=row["sample_size"],
            last_calibration_date=row.get("created_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching active weights: {e}")
        raise api_error("NO_ACTIVE_WEIGHTS", "No active weight configuration found", status_code=404)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/weights/history — Weight calibration history
# ---------------------------------------------------------------------------

@di_router.get(
    "/weights/history",
    response_model=PaginatedResponse[WeightHistoryResponse],
    summary="List weight history",
    description="Weight calibration history with pagination.",
)
async def list_weights_history(
    cursor: Optional[str] = Query(None, description="Base64-encoded pagination cursor"),
    limit: int = Query(20, gt=0, le=100),
    pool=Depends(get_db_pool),
):
    """Fetch weight calibration history."""
    try:
        cursor_id = None
        if cursor:
            try:
                _, cursor_id = decode_cursor(cursor)
            except ValueError as e:
                raise api_error("INVALID_CURSOR", str(e), status_code=400)

        where_sql = "id < $1" if cursor_id else "1=1"
        params = [cursor_id] if cursor_id else []

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT *
                FROM di_weight_history
                WHERE {where_sql}
                ORDER BY effective_from DESC
                LIMIT ${len(params) + 1}
                """,
                *params,
                limit + 1,
            )

        weights = []
        for row in rows[:limit]:
            weights.append(WeightHistoryResponse(
                id=row["id"],
                weights=row["weights"],
                calibration_window_days=row["calibration_window_days"],
                sample_size=row["sample_size"],
                win_rate_before=float(row["win_rate_before"]) if row.get("win_rate_before") else None,
                win_rate_after=float(row["win_rate_after"]) if row.get("win_rate_after") else None,
                statistical_significance=float(row["statistical_significance"]) if row.get("statistical_significance") else None,
                trigger_reason=row["trigger_reason"],
                status=row["status"],
                effective_from=row["effective_from"],
                effective_until=row.get("effective_until"),
                created_at=row["created_at"],
            ))

        has_more = len(rows) > limit
        pagination = build_pagination(
            items=[{"id": w.id} for w in weights] + ([{"id": -1}] if has_more else []),
            limit=limit,
        )

        return PaginatedResponse(data=weights[:limit], pagination=pagination)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing weight history: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to list weight history", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/portfolio/exposure — Current portfolio exposure
# ---------------------------------------------------------------------------

@di_router.get(
    "/portfolio/exposure",
    response_model=PortfolioExposureResponse,
    summary="Get portfolio exposure",
    description="Current portfolio exposure summary.",
)
async def get_portfolio_exposure(
    pool=Depends(get_db_pool),
):
    """Fetch current portfolio exposure summary."""
    try:
        async with pool.acquire() as conn:
            # Count active signals
            active_count = await conn.fetchval(
                "SELECT COUNT(*) FROM signal_outcomes WHERE state IN ('PENDING', 'ACTIVE')",
            )

            # Get active outcomes with entry prices
            active_outcomes = await conn.fetch(
                """
                SELECT so.entry_price, so.signal_id
                FROM signal_outcomes so
                WHERE so.state IN ('PENDING', 'ACTIVE')
                  AND so.entry_price IS NOT NULL
                """,
            )

        total_exposure = sum(o["entry_price"] for o in active_outcomes) if active_outcomes else 0
        max_position = max((o["entry_price"] for o in active_outcomes), default=0)

        return PortfolioExposureResponse(
            total_active_signals=active_count or 0,
            total_exposure_pct=min(total_exposure / 100000 * 100, 100) if total_exposure else 0,
            max_single_position_pct=min(max_position / 100000 * 100, 100) if max_position else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching portfolio exposure: {e}")
        raise api_error("INTERNAL_ERROR", "Failed to fetch exposure", status_code=500)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/health — System health check
# ---------------------------------------------------------------------------

@di_router.get(
    "/health",
    response_model=SystemHealthResponse,
    summary="System health check",
    description="System health and status.",
)
async def get_health(
    pool=Depends(get_db_pool),
    cache: LRUCache = Depends(get_di_cache),
):
    """Fetch system health status."""
    try:
        # Count active signals
        async with pool.acquire() as conn:
            active_signals = await conn.fetchval(
                "SELECT COUNT(*) FROM signal_outcomes WHERE state IN ('PENDING', 'ACTIVE')",
            )
            pending_outcomes = await conn.fetchval(
                "SELECT COUNT(*) FROM signal_outcomes WHERE state = 'PENDING'",
            )

        # Get cache hit rate
        cache_stats = cache.stats()
        cache_hit_rate = cache_stats.get("hit_rate_pct")

        return SystemHealthResponse(
            status="healthy",
            active_signals=active_signals or 0,
            pending_outcomes=pending_outcomes or 0,
            database_connected=True,
            cache_hit_rate=cache_hit_rate,
        )

    except Exception as e:
        logger.error(f"Error fetching health status: {e}")
        return SystemHealthResponse(
            status="degraded",
            database_connected=False,
        )


# ---------------------------------------------------------------------------
# EXISTING ENDPOINTS (preserved for backward compatibility)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Endpoint: POST /api/di/score/{alert_id}
# ---------------------------------------------------------------------------

@di_router.post(
    "/score/{alert_id}",
    response_model=ScoreResponse,
    status_code=201,
    summary="Score a signal",
    description="Computes 0-100 confidence score for a specific alert and persists to signal_scores table.",
)
async def post_score_signal(
    alert_id: int,
    pool=Depends(get_db_pool),
    cache: LRUCache = Depends(get_di_cache),
):
    """
    Score a specific alert and persist the result.

    Computes a weighted composite score from:
    - Historical hit rate
    - Regime alignment
    - Volatility percentile
    - Technical factor confluence

    Returns the score with component breakdown.
    """
    # Check cache first
    cache_key = f"di:score:{alert_id}"
    cached = cache.get(cache_key)
    if cached:
        return ScoreResponse(**cached)

    try:
        scorer = get_signal_scorer(pool=pool)
        result: ScoreResult = await scorer.score_signal(alert_id)

        response = ScoreResponse(
            alert_id=result.signal_id,
            score=result.score,
            components=result.components,
            version=None,
        )

        # Cache the response
        cache.set(cache_key, response.model_dump(), ttl=300)
        return response

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error scoring signal {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/score/{alert_id}
# ---------------------------------------------------------------------------

@di_router.get(
    "/score/{alert_id}",
    response_model=ScoreResponse,
    status_code=200,
    summary="Get signal score",
    description="Fetches existing score for an alert from the database.",
)
async def get_score_signal(
    alert_id: int,
    pool=Depends(get_db_pool),
    cache: LRUCache = Depends(get_di_cache),
):
    """
    Fetch an existing signal score.

    Returns 404 if no score has been computed for this alert.
    """
    # Check cache first
    cache_key = f"di:score:{alert_id}"
    cached = cache.get(cache_key)
    if cached:
        return ScoreResponse(**cached)

    try:
        # Fetch from database directly
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT score, hit_rate_component, regime_component,
                       volatility_component, confluence_component
                FROM signal_scores
                WHERE signal_id = $1
                ORDER BY computed_at DESC
                LIMIT 1
                """,
                alert_id,
            )

        if row is None:
            raise HTTPException(status_code=404, detail=f"No score found for alert {alert_id}")

        response = ScoreResponse(
            alert_id=alert_id,
            score=row["score"],
            components={
                "hit_rate": float(row["hit_rate_component"] or 0) / 100,
                "regime_alignment": float(row["regime_component"] or 0) / 100,
                "volatility": float(row["volatility_component"] or 0) / 100,
                "confluence": float(row["confluence_component"] or 0) / 100,
            },
            version=None,
        )

        # Cache the response
        cache.set(cache_key, response.model_dump(), ttl=300)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching score for alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Endpoint: POST /api/di/outcomes/track
# ---------------------------------------------------------------------------

@di_router.post(
    "/outcomes/track",
    response_model=TrackOutcomeResponse,
    status_code=201,
    summary="Track a new outcome",
    description="Creates initial outcome record for a signal with entry, target, and stop prices.",
)
async def post_track_outcome(
    req: TrackOutcomeRequest,
    pool=Depends(get_db_pool),
):
    """
    Create initial outcome record for a new signal.

    The signal starts in PENDING state until market data arrives.
    Idempotent: returns existing record if already tracked.
    """
    try:
        tracker = get_outcome_tracker(pool=pool)
        outcome: OutcomeState = await tracker.track_signal(
            alert_id=req.alert_id,
            entry_price=req.entry_price,
            target_price=req.target_price,
            stop_price=req.stop_price,
        )

        return TrackOutcomeResponse(
            alert_id=outcome.signal_id,
            state=outcome.state,
            created_at=outcome.updated_at,
        )

    except Exception as e:
        logger.error(f"Error tracking outcome for alert {req.alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Endpoint: POST /api/di/outcomes/update
# ---------------------------------------------------------------------------

@di_router.post(
    "/outcomes/update",
    response_model=UpdateOutcomesResponse,
    status_code=200,
    summary="Update active outcomes",
    description="Idempotent batch update of all active outcomes based on closed candle data.",
)
async def post_update_outcomes(
    req: UpdateOutcomesRequest,
    pool=Depends(get_db_pool),
):
    """
    Idempotent batch update of active outcomes.

    For each closed candle, checks if any active signal has triggered
    a state transition (target hit, stop hit, time expired).

    Returns count of updated signals and their new states.
    """
    try:
        tracker = get_outcome_tracker(pool=pool)

        # Get all active outcomes
        active = await tracker.get_active_outcomes()

        # Batch-resolve all tickers in a single query to avoid N+1
        if active:
            signal_ids = [o.signal_id for o in active]
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, ticker FROM alerts WHERE id = ANY($1)",
                    signal_ids,
                )
                ticker_map = {row["id"]: row["ticker"] for row in rows}
        else:
            ticker_map = {}

        updated_count = 0
        for outcome in active:
            ticker = ticker_map.get(outcome.signal_id)
            if ticker is None:
                continue

            # Find matching candle
            for candle in req.closed_candles:
                if candle.symbol == ticker:
                    await tracker._update_single_outcome(
                        signal_id=outcome.signal_id,
                        current_high=candle.high,
                        current_low=candle.low,
                        current_price=candle.close,
                    )
                    updated_count += 1
                    break

        # Fetch updated outcomes
        active = await tracker.get_active_outcomes()
        outcomes = []
        for outcome in active:
            realized_pnl = outcome.outcome_pct if outcome.outcome_pct is not None else None
            outcomes.append(OutcomeItem(
                alert_id=outcome.signal_id,
                state=outcome.state,
                realized_pnl=realized_pnl,
            ))

        return UpdateOutcomesResponse(
            updated_count=updated_count,
            outcomes=outcomes,
        )

    except Exception as e:
        logger.error(f"Error updating outcomes: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/outcomes/active
# ---------------------------------------------------------------------------

@di_router.get(
    "/outcomes/active",
    response_model=ActiveOutcomesResponse,
    status_code=200,
    summary="Get active outcomes",
    description="Returns all unresolved signals, optionally filtered by symbol and timeframe.",
)
async def get_active_outcomes(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    timeframe: Optional[str] = Query(None, description="Filter by timeframe"),
    pool=Depends(get_db_pool),
):
    """
    Fetch all unresolved (PENDING or ACTIVE) signal outcomes.

    Optionally filter by symbol and/or timeframe.
    """
    try:
        tracker = get_outcome_tracker(pool=pool)
        active = await tracker.get_active_outcomes(symbol=symbol, timeframe=timeframe)

        outcomes = []
        for outcome in active:
            realized_pnl = outcome.outcome_pct if outcome.outcome_pct is not None else None
            outcomes.append(OutcomeItem(
                alert_id=outcome.signal_id,
                state=outcome.state,
                realized_pnl=realized_pnl,
            ))

        return ActiveOutcomesResponse(
            count=len(outcomes),
            outcomes=outcomes,
        )

    except Exception as e:
        logger.error(f"Error fetching active outcomes: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Endpoint: POST /api/di/regime/detect
# ---------------------------------------------------------------------------

@di_router.post(
    "/regime/detect",
    response_model=RegimeResponse,
    status_code=201,
    summary="Detect market regime",
    description="Computes and caches regime vector for a symbol/timeframe using OHLCV data.",
)
async def post_detect_regime(
    req: DetectRegimeRequest,
    pool=Depends(get_db_pool),
    cache: LRUCache = Depends(get_di_cache),
):
    """
    Compute regime vector for a symbol and timeframe.

    Uses OHLCV data to detect:
    - Market regime (TRENDING, SIDEWAYS, VOLATILE, etc.)
    - Trend slope via linear regression
    - Momentum strength
    - Volatility percentile
    - Breadth score

    Results are cached for 5 minutes.
    """
    try:
        detector = get_regime_detector(pool=pool)
        vector: RegimeVector = await detector.detect_regime(
            symbol=req.symbol,
            timeframe=req.timeframe,
            ohlcv_data=req.ohlcv,
        )

        # Compute alignment scores for all signal types
        alignment_scores = {
            "bullish": detector.regime_alignment_score("BULLISH", {
                "regime": vector.regime,
                "confidence": vector.confidence,
                "trend_slope": vector.vector.get("trend_slope", 0),
            }),
            "bearish": detector.regime_alignment_score("BEARISH", {
                "regime": vector.regime,
                "confidence": vector.confidence,
                "trend_slope": vector.vector.get("trend_slope", 0),
            }),
            "neutral": 0.5,  # Neutral signals have baseline alignment
        }

        response = RegimeResponse(
            symbol=vector.symbol,
            timeframe=vector.timeframe,
            regime=vector.regime,
            trend_slope=vector.vector.get("trend_slope", 0),
            momentum=vector.vector.get("momentum_strength", 0),
            volatility_pct=vector.vector.get("volatility_percentile", 0),
            breadth=vector.vector.get("breadth", 0),
            alignment_scores=alignment_scores,
        )

        return response

    except Exception as e:
        logger.error(f"Error detecting regime for {req.symbol}/{req.timeframe}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/regime/{symbol}/{timeframe}
# ---------------------------------------------------------------------------

@di_router.get(
    "/regime/{symbol}/{timeframe}",
    response_model=RegimeResponse,
    status_code=200,
    summary="Get cached regime",
    description="Returns cached regime vector for a symbol/timeframe, or computes if cache miss.",
)
async def get_regime(
    symbol: str,
    timeframe: str,
    pool=Depends(get_db_pool),
    cache: LRUCache = Depends(get_di_cache),
):
    """
    Get cached regime vector for a symbol and timeframe.

    If not cached, computes fresh regime vector.
    """
    try:
        detector = get_regime_detector(pool=pool)

        # Try cached lookup first
        vector = await detector.get_cached_regime(symbol, timeframe)

        if vector is None:
            # Compute fresh regime (no OHLCV data available via GET)
            # Return a minimal response indicating no data
            return RegimeResponse(
                symbol=symbol,
                timeframe=timeframe,
                regime="UNKNOWN",
                trend_slope=0,
                momentum=0,
                volatility_pct=0,
                breadth=0.5,
                alignment_scores={"bullish": 0.5, "bearish": 0.5, "neutral": 0.5},
            )

        alignment_scores = {
            "bullish": detector.regime_alignment_score("BULLISH", {
                "regime": vector.regime,
                "confidence": vector.confidence,
                "trend_slope": vector.vector.get("trend_slope", 0),
            }),
            "bearish": detector.regime_alignment_score("BEARISH", {
                "regime": vector.regime,
                "confidence": vector.confidence,
                "trend_slope": vector.vector.get("trend_slope", 0),
            }),
            "neutral": 0.5,
        }

        return RegimeResponse(
            symbol=vector.symbol,
            timeframe=vector.timeframe,
            regime=vector.regime,
            trend_slope=vector.vector.get("trend_slope", 0),
            momentum=vector.vector.get("momentum_strength", 0),
            volatility_pct=vector.vector.get("volatility_percentile", 0),
            breadth=vector.vector.get("breadth", 0),
            alignment_scores=alignment_scores,
        )

    except Exception as e:
        logger.error(f"Error fetching regime for {symbol}/{timeframe}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Endpoint: POST /api/di/evaluate
# ---------------------------------------------------------------------------

@di_router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    status_code=200,
    summary="Run self-evaluation",
    description="Runs cohort analysis, updates weights, and identifies degraded signals.",
)
async def post_evaluate(
    req: EvaluateRequest,
    pool=Depends(get_db_pool),
):
    """
    Run self-evaluation cohort analysis.

    Analyzes historical signal performance to:
    - Compute win rates by (signal_type, regime) cohort
    - Estimate decay half-life
    - Identify failure modes
    - Update weight calibrations
    - Flag degraded signals

    Completes within 10 seconds for typical datasets.
    """
    try:
        evaluator = get_self_evaluator(pool=pool)

        # Run cohort analysis
        report: EvaluationReport = await evaluator.run_cohort_analysis(
            lookback_days=req.lookback_days,
        )

        # Update weights
        if report.updated_weights:
            version = await evaluator.update_weights(report.updated_weights)
        else:
            version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Aggregate failure modes
        failure_modes = {}
        for cohort in report.cohorts:
            if cohort.failure_mode:
                key = f"{cohort.signal_type or 'UNKNOWN'}:{cohort.regime or 'UNKNOWN'}"
                failure_modes[key] = cohort.failure_mode

        # Compute aggregate win rate
        total_wins = sum(c.win_rate * c.sample_size for c in report.cohorts)
        total_sample = sum(c.sample_size for c in report.cohorts)
        aggregate_win_rate = total_wins / total_sample if total_sample > 0 else 0

        # Get average decay half-life
        half_lives = [c.decay_half_life for c in report.cohorts if c.decay_half_life is not None]
        avg_half_life = sum(half_lives) / len(half_lives) if half_lives else None

        # Aggregate new weights
        new_weights = {}
        for w in report.updated_weights:
            key = f"{w.get('signal_type', 'all')}:{w.get('regime', 'all')}"
            new_weights[key] = {
                "hit_rate": w.get("hit_rate_weight", 0.30),
                "regime": w.get("regime_weight", 0.25),
                "volatility": w.get("volatility_weight", 0.20),
                "confluence": w.get("confluence_weight", 0.25),
            }

        return EvaluateResponse(
            version=version,
            cohort_size=total_sample,
            win_rate=round(aggregate_win_rate, 4),
            decay_half_life=round(avg_half_life, 2) if avg_half_life else None,
            failure_modes=failure_modes,
            degraded_signals=report.degraded_signals,
            new_weights=new_weights,
        )

    except Exception as e:
        logger.error(f"Error running evaluation: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/explain/{alert_id}
# ---------------------------------------------------------------------------

@di_router.get(
    "/explain/{alert_id}",
    response_model=ExplainResponse,
    status_code=200,
    summary="Get signal explainability",
    description="Returns explainability breakdown for a scored signal.",
)
async def get_explain(
    alert_id: int,
    pool=Depends(get_db_pool),
):
    """
    Get deterministic explainability breakdown for a scored signal.

    Returns:
    - Trigger conditions that caused the signal
    - Factor weights and scores
    - Regime impact on the score
    - Human-readable reasoning
    - UI-friendly format with labels, colors, and grades
    """
    try:
        engine = get_explainability_engine(pool=pool)
        result: ExplainabilityResult = await engine.explain_signal(alert_id)

        # Build UI format
        ui_format = ExplainabilityEngine.format_for_ui({
            "score": result.score,
            "factors": result.breakdown.get("factors", {}),
            "regime_impact": result.regime_impact,
            "human_readable": result.human_readable,
        })

        return ExplainResponse(
            alert_id=result.signal_id,
            score=result.score,
            trigger_conditions=result.breakdown.get("trigger", {}),
            factor_weights=result.breakdown.get("factors", {}),
            regime_impact=result.regime_impact,
            reasoning=result.human_readable,
            ui_format=ui_format,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error explaining signal {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Endpoint: POST /api/di/simulate
# ---------------------------------------------------------------------------

@di_router.post(
    "/simulate",
    response_model=SimulateResponse,
    status_code=200,
    summary="Simulate portfolio",
    description="Runs portfolio simulation with Kelly-fractioned position sizing.",
)
async def post_simulate(
    req: SimulateRequest,
    pool=Depends(get_db_pool),
):
    """
    Run portfolio simulation with Kelly criterion position sizing.

    Flow:
    1. Filter signals by correlation constraint
    2. Size positions using Kelly fraction
    3. Enforce drawdown cap
    4. Simulate equity progression
    5. Return metrics and position sizes

    All computation is stateless and completes within the request.
    """
    try:
        simulator = get_portfolio_simulator(pool=pool)

        # Transform signals for the simulator
        signals = []
        for sig in req.signals:
            signals.append({
                "signal_id": sig.alert_id,
                "ticker": sig.signal_type,  # Use signal_type as ticker proxy
                "score": sig.score,
                "entry_price": sig.entry_price,
                "stop_price": sig.stop_price,
                "target_price": sig.target_price,
            })

        result: SimulationResult = simulator.simulate_portfolio(
            signals=signals,
            account_balance=req.account_balance,
            max_drawdown_pct=req.max_drawdown_pct,
        )

        # Transform position sizes for response
        position_sizes = []
        for pos in result.positions:
            size_pct = (pos["allocation"] / req.account_balance * 100) if req.account_balance > 0 else 0
            position_sizes.append(PositionSizeItem(
                alert_id=pos["signal_id"],
                size_pct=round(size_pct, 2),
                kelly_fraction=pos["kelly_fraction"],
            ))

        return SimulateResponse(
            cumulative_returns=result.cumulative_return_pct,
            max_drawdown=result.max_drawdown_pct,
            sharpe_ratio=result.sharpe_ratio,
            trade_distribution=result.trade_distribution,
            position_sizes=position_sizes,
        )

    except Exception as e:
        logger.error(f"Error running portfolio simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Endpoint: GET /api/di/cache/stats
# ---------------------------------------------------------------------------

@di_router.get(
    "/cache/stats",
    response_model=CacheStatsResponse,
    status_code=200,
    summary="Get cache statistics",
    description="Returns LRU cache hit/miss rates and utilization.",
)
async def get_cache_stats(
    cache: LRUCache = Depends(get_di_cache),
):
    """
    Return LRU cache statistics.

    Includes size, max size, hit/miss counts, and hit rate percentage.
    Useful for monitoring cache effectiveness.
    """
    stats = cache.stats()

    return CacheStatsResponse(
        size=stats["size"],
        max_size=stats["max_size"],
        hits=stats["hits"],
        misses=stats["misses"],
        hit_rate=stats["hit_rate_pct"],
    )


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _score_to_grade(score: Optional[float]) -> Optional[ConfidenceGrade]:
    """Convert numeric score to confidence grade enum."""
    if score is None:
        return None
    if score >= 81:
        return ConfidenceGrade.VERY_HIGH
    elif score >= 61:
        return ConfidenceGrade.HIGH
    elif score >= 41:
        return ConfidenceGrade.MODERATE
    elif score >= 21:
        return ConfidenceGrade.LOW
    else:
        return ConfidenceGrade.VERY_LOW


def _simulation_row_to_response(row: dict) -> SimulationResultResponse:
    """Convert a database row to SimulationResultResponse."""
    equity_curve = None
    if row.get("equity_curve"):
        curve_data = row["equity_curve"]
        if isinstance(curve_data, str):
            curve_data = json.loads(curve_data)
        if isinstance(curve_data, list):
            equity_curve = [
                EquityCurvePoint(
                    date=point.get("date", ""),
                    equity=point.get("equity", 0),
                    drawdown=point.get("drawdown", 0),
                )
                for point in curve_data
            ]

    return SimulationResultResponse(
        id=row["id"],
        simulation_name=row["simulation_name"],
        simulation_type=SimulationType(row["simulation_type"]),
        params=row.get("params", {}),
        total_return_pct=float(row["total_return_pct"]) if row.get("total_return_pct") else None,
        annualized_return_pct=float(row["annualized_return_pct"]) if row.get("annualized_return_pct") else None,
        max_drawdown_pct=float(row["max_drawdown_pct"]) if row.get("max_drawdown_pct") else None,
        sharpe_ratio=float(row["sharpe_ratio"]) if row.get("sharpe_ratio") else None,
        sortino_ratio=float(row["sortino_ratio"]) if row.get("sortino_ratio") else None,
        calmar_ratio=float(row["calmar_ratio"]) if row.get("calmar_ratio") else None,
        win_rate=float(row["win_rate"]) if row.get("win_rate") else None,
        profit_factor=float(row["profit_factor"]) if row.get("profit_factor") else None,
        total_signals=row.get("total_signals"),
        winning_signals=row.get("winning_signals"),
        losing_signals=row.get("losing_signals"),
        start_date=row["start_date"] if isinstance(row["start_date"], date) else date.fromisoformat(str(row["start_date"])),
        end_date=row["end_date"] if isinstance(row["end_date"], date) else date.fromisoformat(str(row["end_date"])),
        equity_curve=equity_curve,
        result_hash=row.get("result_hash"),
        created_at=row["created_at"],
    )
