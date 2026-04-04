# Decision Intelligence Architecture

## 1. Architecture Overview

### Component Interaction Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Next.js Frontend                             │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  ┌────────────┐ │
│  │SignalCard│  │RegimeDashboard│  │PortfolioSim   │  │ExplainPanel│ │
│  └────┬─────┘  └──────┬───────┘  └──────┬────────┘  └─────┬──────┘ │
│       │               │                 │                  │         │
│  ┌────▼───────────────▼─────────────────▼──────────────────▼──────┐ │
│  │              React Query Polling Hooks                          │ │
│  └────────────────────────┬────────────────────────────────────────┘ │
└───────────────────────────┼─────────────────────────────────────────┘
                            │ HTTP Polling (no WebSockets)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI (api.py)                              │
│                                                                      │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │/di/score   │  │/di/outcome   │  │/di/evaluate  │  │/di/regime │ │
│  │   (POST)   │  │   (POST)     │  │   (POST)     │  │  (GET)    │ │
│  └─────┬──────┘  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│        │                │                 │                 │        │
│  ┌─────▼────────────────▼─────────────────▼─────────────────▼─────┐ │
│  │                    Service Layer                                │ │
│  │  ┌─────────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────┐ │ │
│  │  │SignalScorer │ │OutcomeTracker│ │SelfEval    │ │RegimeDet │ │ │
│  │  └──────┬──────┘ └──────┬───────┘ └─────┬──────┘ └────┬─────┘ │ │
│  │         │               │               │              │        │ │
│  │  ┌──────▼───────────────▼───────────────▼──────────────▼─────┐ │ │
│  │  │              LRU Cache (services/di_cache.py)             │ │ │
│  │  │  Key: (symbol, timeframe, regime) → TTL 300s, max 512    │ │ │
│  │  └────────────────────────┬──────────────────────────────────┘ │ │
│  └───────────────────────────┼─────────────────────────────────────┘ │
│                              │                                        │
│  ┌───────────────────────────▼─────────────────────────────────────┐ │
│  │              Portfolio Simulator (stateless)                     │ │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │ │
│  │  │KellySizer    │  │CorrelationFilter │  │EquitySimulator   │  │ │
│  │  └──────────────┘  └──────────────────┘  └──────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ asyncpg pool
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PostgreSQL 13+ (Neon)                           │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  ┌────────────┐ │
│  │alerts    │  │signal_scores │  │signal_outcomes│  │regime_cache│ │
│  │(existing)│  │              │  │               │  │            │ │
│  └──────────┘  └──────────────┘  └───────────────┘  └────────────┘ │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐ │
│  │weight_calibrations│  │evaluation_cohorts│  │Composite Indexes │ │
│  │                  │  │                  │  │Partial Indexes    │ │
│  └──────────────────┘  └──────────────────┘  └───────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Polling Trigger Sequence Per Module

| Module | Trigger Mechanism | Polling Flow |
|--------|------------------|--------------|
| **Signal Scoring** | `POST /di/score` — client polls `GET /di/score/{signal_id}` for result | Client triggers scoring, polls every 2s until `status=complete` |
| **Outcome Tracking** | `POST /di/outcome/update` — idempotent update per signal | Client polls `GET /di/outcome/{signal_id}` for lifecycle state |
| **Self-Evaluation** | `POST /di/evaluate` — on-demand analysis, returns synchronously | Single request, completes within 10s, returns full report |
| **Regime Detection** | `GET /di/regime/{symbol}` — regime vector lookup | Client polls every 60s; cached result returned in <50ms |
| **Explainability** | `GET /di/explain/{signal_id}` — deterministic breakdown | Single GET, composed from score + regime + weight data |
| **Portfolio Simulation** | `POST /di/portfolio/simulate` — stateless computation | Single POST, returns metrics synchronously |

### Statelessness Enforcement Strategy

1. **No background workers**: All computation executes within the HTTP request lifecycle. APScheduler is used only for legacy detection jobs; new DI modules have zero scheduled tasks.
2. **No in-process state**: The `LRUCache` class is the only in-memory state, bounded to 512 entries with LRU eviction. It is a cache, not a data store — all ground truth lives in PostgreSQL.
3. **Idempotent endpoints**: Every `POST` endpoint accepts an `idempotency_key` field. Duplicate requests with the same key return the cached response without re-computation.
4. **No WebSockets for DI**: The existing `/ws` endpoint remains for legacy alerts. All DI modules use HTTP polling exclusively.
5. **Memory-bounded operations**: Portfolio simulation and self-evaluation use streaming aggregations and `LIMIT` clauses to prevent unbounded memory growth.

---

## 2. Database Schema Migrations

File: `backend/migrations/002_decision_intelligence.sql`

```sql
-- ============================================================================
-- Vigil Migration 002: Decision Intelligence Schema
-- ============================================================================
-- Purpose: Add tables for signal scoring, outcome tracking, regime caching,
--          weight calibration, and evaluation cohorts.
--
-- Notes:
--   - All indexes use CONCURRENTLY to avoid locking tables during creation.
--   - All tables are additive — no existing columns or tables are mutated.
--   - Foreign keys reference alerts(id) for deterministic signal linkage.
--   - PostgreSQL 13+ compatible.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Table: signal_scores
-- Purpose: Stores 0-100 confidence scores for each signal, computed from
--          weighted composite of hit rate, regime alignment, volatility
--          percentiles, and technical factor confluence.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signal_scores (
    id              SERIAL PRIMARY KEY,
    signal_id       INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    score           SMALLINT NOT NULL CHECK (score >= 0 AND score <= 100),
    hit_rate_weight REAL NOT NULL DEFAULT 0.30,
    regime_weight   REAL NOT NULL DEFAULT 0.25,
    volatility_weight REAL NOT NULL DEFAULT 0.20,
    confluence_weight REAL NOT NULL DEFAULT 0.25,
    hit_rate_component   REAL,
    regime_component     REAL,
    volatility_component REAL,
    confluence_component REAL,
    regime_tag      TEXT,
    computed_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(signal_id, computed_at)
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scores_signal
    ON signal_scores (signal_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scores_score_desc
    ON signal_scores (score DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scores_computed
    ON signal_scores (computed_at DESC);

-- ---------------------------------------------------------------------------
-- Table: signal_outcomes
-- Purpose: Tracks every signal from inception through resolution:
--          target reach, stop violation, time-in-trade, max unfavorable
--          excursion, max favorable excursion, final PnL state.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id                      SERIAL PRIMARY KEY,
    signal_id               INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    state                   TEXT NOT NULL DEFAULT 'PENDING'
                                CHECK (state IN ('PENDING', 'ACTIVE', 'TARGET_HIT', 'STOP_HIT', 'TIME_EXPIRED', 'CLOSED')),
    entry_price             REAL,
    target_price            REAL,
    stop_price              REAL,
    exit_price              REAL,
    outcome_pct             REAL,
    max_adverse_excursion   REAL,
    max_favorable_excursion REAL,
    time_in_trade_bars      INTEGER,
    final_pnl_state         TEXT CHECK (final_pnl_state IN ('WIN', 'LOSS', 'BREAKEVEN', 'UNRESOLVED')),
    resolved_at             TIMESTAMPTZ,
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(signal_id)
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outcomes_state
    ON signal_outcomes (state) WHERE state != 'CLOSED';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outcomes_pnl
    ON signal_outcomes (final_pnl_state) WHERE final_pnl_state IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outcomes_updated
    ON signal_outcomes (updated_at DESC);

-- ---------------------------------------------------------------------------
-- Table: regime_cache
-- Purpose: Caches regime detection results per symbol and timeframe
--          to avoid redundant compute on repeated polling requests.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regime_cache (
    id              SERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL DEFAULT '1D',
    regime_vector   JSONB NOT NULL,
    confidence      REAL NOT NULL,
    computed_at     TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    UNIQUE(symbol, timeframe)
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regime_expires
    ON regime_cache (expires_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regime_symbol_tf
    ON regime_cache (symbol, timeframe);

-- ---------------------------------------------------------------------------
-- Table: weight_calibrations
-- Purpose: Stores adaptive weight calibration derived from historical
--          signal performance. Updated by the self-evaluation loop.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weight_calibrations (
    id                  SERIAL PRIMARY KEY,
    signal_type         TEXT NOT NULL,
    regime              TEXT,
    hit_rate_weight     REAL NOT NULL DEFAULT 0.30,
    regime_weight       REAL NOT NULL DEFAULT 0.25,
    volatility_weight   REAL NOT NULL DEFAULT 0.20,
    confluence_weight   REAL NOT NULL DEFAULT 0.25,
    confidence_threshold SMALLINT NOT NULL DEFAULT 50,
    is_degraded         BOOLEAN NOT NULL DEFAULT FALSE,
    calibrated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(signal_type, regime)
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_weights_type_regime
    ON weight_calibrations (signal_type, regime);

-- ---------------------------------------------------------------------------
-- Table: evaluation_cohorts
-- Purpose: Stores results of self-evaluation runs: decay patterns,
--          regime-specific failure modes, feature importance rankings.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evaluation_cohorts (
    id                  SERIAL PRIMARY KEY,
    cohort_key          TEXT NOT NULL,
    signal_type         TEXT,
    regime              TEXT,
    sample_size         INTEGER NOT NULL,
    win_rate            REAL,
    avg_pnl             REAL,
    decay_half_life     REAL,
    failure_mode        TEXT,
    feature_importance  JSONB,
    evaluated_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(cohort_key)
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cohorts_type_regime
    ON evaluation_cohorts (signal_type, regime);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cohorts_evaluated
    ON evaluation_cohorts (evaluated_at DESC);

-- ---------------------------------------------------------------------------
-- Partial index: active signals awaiting outcome resolution
-- ---------------------------------------------------------------------------
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outcomes_pending
    ON signal_outcomes (signal_id) WHERE state = 'PENDING';

-- ---------------------------------------------------------------------------
-- Composite index: fast lookup of scores by signal and regime
-- ---------------------------------------------------------------------------
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scores_signal_regime
    ON signal_scores (signal_id, regime_tag) WHERE regime_tag IS NOT NULL;

-- ============================================================================
-- Migration complete.
-- ============================================================================
```

---

## 3. FastAPI Implementation

### 3.1 Router Definitions

New router file: `backend/services/di_router.py`

```python
"""
Vigil Decision Intelligence Router
===================================
Polling-triggered endpoints for signal scoring, outcome tracking,
self-evaluation, regime detection, explainability, and portfolio simulation.

All endpoints are stateless — no background tasks, no WebSockets.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from services.di_cache import get_di_cache
from services.signal_scorer import get_signal_scorer, ScoreResult
from services.outcome_tracker import get_outcome_tracker, OutcomeState
from services.self_evaluator import get_self_evaluator, EvaluationReport
from services.regime_detector import get_regime_detector, RegimeVector
from services.explainability import get_explainability_engine, ExplainabilityResult
from services.portfolio_simulator import get_portfolio_simulator, SimulationResult

logger = logging.getLogger(__name__)

di_router = APIRouter(prefix="/di", tags=["decision-intelligence"])


# ---------------------------------------------------------------------------
# Pydantic v2 Request/Response Models
# ---------------------------------------------------------------------------

class ScoreRequest(BaseModel):
    signal_id: int
    idempotency_key: Optional[str] = None


class ScoreResponse(BaseModel):
    signal_id: int
    score: int = Field(..., ge=0, le=100)
    components: dict[str, float]
    regime_tag: Optional[str]
    computed_at: str


class OutcomeUpdateRequest(BaseModel):
    signal_id: int
    idempotency_key: Optional[str] = None
    current_price: Optional[float] = None
    current_high: Optional[float] = None
    current_low: Optional[float] = None
    bars_elapsed: Optional[int] = None


class OutcomeResponse(BaseModel):
    signal_id: int
    state: str
    entry_price: Optional[float]
    exit_price: Optional[float]
    outcome_pct: Optional[float]
    max_adverse_excursion: Optional[float]
    max_favorable_excursion: Optional[float]
    time_in_trade_bars: Optional[int]
    final_pnl_state: Optional[str]
    updated_at: str


class EvaluateRequest(BaseModel):
    signal_types: Optional[List[str]] = None
    regimes: Optional[List[str]] = None
    lookback_days: int = Field(default=90, gt=0, le=365)


class EvaluateResponse(BaseModel):
    cohorts: List[dict[str, Any]]
    updated_weights: List[dict[str, Any]]
    degraded_signals: List[str]
    execution_ms: int


class RegimeResponse(BaseModel):
    symbol: str
    timeframe: str
    regime: str
    confidence: float
    vector: dict[str, float]
    factors: dict[str, Any]
    cached: bool
    computed_at: str


class ExplainResponse(BaseModel):
    signal_id: int
    score: int
    breakdown: dict[str, Any]
    human_readable: str
    regime_impact: dict[str, Any]
    generated_at: str


class PositionCandidate(BaseModel):
    signal_id: int
    ticker: str
    score: int = Field(..., ge=0, le=100)
    entry_price: float = Field(..., gt=0)
    stop_price: Optional[float] = None
    target_price: Optional[float] = None


class SimulateRequest(BaseModel):
    candidates: List[PositionCandidate] = Field(..., min_length=1, max_length=50)
    total_capital: float = Field(default=100000.0, gt=0)
    max_drawdown_pct: float = Field(default=10.0, gt=0, le=50)
    kelly_fraction: float = Field(default=0.25, gt=0, le=1.0)
    correlation_threshold: float = Field(default=0.7, gt=0, le=1.0)


class SimulateResponse(BaseModel):
    cumulative_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    trade_distribution: dict[str, int]
    positions: List[dict[str, Any]]
    execution_ms: int


# ---------------------------------------------------------------------------
# Endpoint: Signal Scoring
# ---------------------------------------------------------------------------

@di_router.post("/score", response_model=ScoreResponse)
async def score_signal(
    req: ScoreRequest,
    scorer=Depends(get_signal_scorer),
    cache=Depends(get_di_cache),
):
    """
    Compute 0-100 confidence score for a signal.
    Idempotent: same signal_id returns cached result within TTL.
    """
    cache_key = f"score:{req.signal_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    result: ScoreResult = scorer.score(req.signal_id)
    response = ScoreResponse(
        signal_id=result.signal_id,
        score=result.score,
        components=result.components,
        regime_tag=result.regime_tag,
        computed_at=result.computed_at.isoformat(),
    )
    cache.set(cache_key, response, ttl=300)
    return response


@di_router.get("/score/{signal_id}", response_model=ScoreResponse)
async def get_signal_score(
    signal_id: int,
    scorer=Depends(get_signal_scorer),
    cache=Depends(get_di_cache),
):
    """Retrieve a previously computed signal score."""
    cache_key = f"score:{signal_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    result: ScoreResult = scorer.score(signal_id)
    response = ScoreResponse(
        signal_id=result.signal_id,
        score=result.score,
        components=result.components,
        regime_tag=result.regime_tag,
        computed_at=result.computed_at.isoformat(),
    )
    cache.set(cache_key, response, ttl=300)
    return response


# ---------------------------------------------------------------------------
# Endpoint: Outcome Tracking
# ---------------------------------------------------------------------------

@di_router.post("/outcome/update", response_model=OutcomeResponse)
async def update_outcome(
    req: OutcomeUpdateRequest,
    tracker=Depends(get_outcome_tracker),
    cache=Depends(get_di_cache),
):
    """
    Idempotent polling endpoint that updates signal state based on
    current market data. Call repeatedly as new candles close.
    """
    cache_key = f"outcome:{req.signal_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    outcome: OutcomeState = tracker.update(
        signal_id=req.signal_id,
        current_price=req.current_price,
        current_high=req.current_high,
        current_low=req.current_low,
        bars_elapsed=req.bars_elapsed,
    )
    response = OutcomeResponse(
        signal_id=outcome.signal_id,
        state=outcome.state,
        entry_price=outcome.entry_price,
        exit_price=outcome.exit_price,
        outcome_pct=outcome.outcome_pct,
        max_adverse_excursion=outcome.max_adverse_excursion,
        max_favorable_excursion=outcome.max_favorable_excursion,
        time_in_trade_bars=outcome.time_in_trade_bars,
        final_pnl_state=outcome.final_pnl_state,
        updated_at=outcome.updated_at.isoformat(),
    )
    cache.set(cache_key, response, ttl=60)
    return response


@di_router.get("/outcome/{signal_id}", response_model=OutcomeResponse)
async def get_outcome(
    signal_id: int,
    tracker=Depends(get_outcome_tracker),
    cache=Depends(get_di_cache),
):
    """Retrieve current outcome state for a signal."""
    cache_key = f"outcome:{signal_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    outcome: OutcomeState = tracker.get(signal_id)
    response = OutcomeResponse(
        signal_id=outcome.signal_id,
        state=outcome.state,
        entry_price=outcome.entry_price,
        exit_price=outcome.exit_price,
        outcome_pct=outcome.outcome_pct,
        max_adverse_excursion=outcome.max_adverse_excursion,
        max_favorable_excursion=outcome.max_favorable_excursion,
        time_in_trade_bars=outcome.time_in_trade_bars,
        final_pnl_state=outcome.final_pnl_state,
        updated_at=outcome.updated_at.isoformat(),
    )
    cache.set(cache_key, response, ttl=60)
    return response


# ---------------------------------------------------------------------------
# Endpoint: Self-Evaluation
# ---------------------------------------------------------------------------

@di_router.post("/evaluate", response_model=EvaluateResponse)
async def run_self_evaluation(
    req: EvaluateRequest,
    evaluator=Depends(get_self_evaluator),
):
    """
    On-demand analysis of historical signal performance cohorts.
    Must complete within 10 seconds. Returns updated weights and
    flags degraded signal types.
    """
    import time
    t0 = time.monotonic()

    report: EvaluationReport = evaluator.evaluate(
        signal_types=req.signal_types,
        regimes=req.regimes,
        lookback_days=req.lookback_days,
    )

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    return EvaluateResponse(
        cohorts=report.cohorts,
        updated_weights=report.updated_weights,
        degraded_signals=report.degraded_signals,
        execution_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# Endpoint: Regime Detection
# ---------------------------------------------------------------------------

@di_router.get("/regime/{symbol}", response_model=RegimeResponse)
async def get_regime(
    symbol: str,
    timeframe: str = Query(default="1D", regex="^(1H|4H|1D|1W)$"),
    detector=Depends(get_regime_detector),
    cache=Depends(get_di_cache),
):
    """
    Get structured regime vector for a symbol/timeframe.
    Cached results returned in <50ms; fresh compute falls through to engine.
    """
    cache_key = f"regime:{symbol}:{timeframe}"
    cached = cache.get(cache_key)
    if cached:
        cached["cached"] = True
        return cached

    vector: RegimeVector = detector.detect(symbol, timeframe)
    response = RegimeResponse(
        symbol=vector.symbol,
        timeframe=vector.timeframe,
        regime=vector.regime,
        confidence=vector.confidence,
        vector=vector.vector,
        factors=vector.factors,
        cached=False,
        computed_at=vector.computed_at.isoformat(),
    )
    cache.set(cache_key, response.model_dump(), ttl=300)
    return response


# ---------------------------------------------------------------------------
# Endpoint: Explainability
# ---------------------------------------------------------------------------

@di_router.get("/explain/{signal_id}", response_model=ExplainResponse)
async def explain_signal(
    signal_id: int,
    engine=Depends(get_explainability_engine),
):
    """
    Return machine-readable and human-readable breakdown of a signal's
    score: trigger conditions, factor weights, regime impact, reasoning.
    """
    result: ExplainabilityResult = engine.explain(signal_id)
    return ExplainResponse(
        signal_id=result.signal_id,
        score=result.score,
        breakdown=result.breakdown,
        human_readable=result.human_readable,
        regime_impact=result.regime_impact,
        generated_at=result.generated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Endpoint: Portfolio Simulation
# ---------------------------------------------------------------------------

@di_router.post("/portfolio/simulate", response_model=SimulateResponse)
async def simulate_portfolio(
    req: SimulateRequest,
    simulator=Depends(get_portfolio_simulator),
):
    """
    Stateless portfolio simulation with Kelly-fractioned position sizing,
    correlation constraints, and equity progression.
    Memory-bounded: processes candidates in a single pass.
    """
    import time
    t0 = time.monotonic()

    result: SimulationResult = simulator.simulate(
        candidates=[c.model_dump() for c in req.candidates],
        total_capital=req.total_capital,
        max_drawdown_pct=req.max_drawdown_pct,
        kelly_fraction=req.kelly_fraction,
        correlation_threshold=req.correlation_threshold,
    )

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    return SimulateResponse(
        cumulative_return_pct=result.cumulative_return_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        sharpe_ratio=result.sharpe_ratio,
        trade_distribution=result.trade_distribution,
        positions=result.positions,
        execution_ms=elapsed_ms,
    )
```

### 3.2 Core Service Function Signatures

#### Signal Scorer — `backend/services/signal_scorer.py`

```python
class SignalScorer:
    """
    Computes 0-100 confidence scores using weighted composite of:
    - Historical hit rate (from signal_outcomes)
    - Regime alignment (from regime_cache / regime_engine)
    - Volatility percentiles (from price data)
    - Technical factor confluence (from alerts columns)

    Weights are adaptively calibrated from weight_calibrations table.
    """

    def __init__(self, pool: asyncpg.Pool, cache: LRUCache):
        self._pool = pool
        self._cache = cache

    def score(self, signal_id: int) -> ScoreResult:
        """
        Score a single signal. Flow:
        1. Fetch alert record from alerts table
        2. Fetch calibrated weights for (signal_type, regime)
        3. Compute each component score (0-100)
        4. Apply weighted sum, clamp to [0, 100]
        5. Persist to signal_scores table
        6. Return ScoreResult
        """
        ...

    def _compute_hit_rate_component(self, signal_type: str, regime: str) -> float:
        """
        Historical win rate for this signal_type/regime cohort.
        SELECT COUNT(*) FILTER (WHERE final_pnl_state = 'WIN')::float /
               NULLIF(COUNT(*), 0) * 100
        FROM signal_outcomes so
        JOIN alerts a ON a.id = so.signal_id
        WHERE a.signal_type = $1 AND a.regime = $2
          AND so.final_pnl_state IS NOT NULL
        """
        ...

    def _compute_regime_component(self, alert_regime: str, current_regime: str) -> float:
        """
        Regime alignment score: 100 if regimes match, scaled down
        for regime transitions. Quantitative rationale: signals
        perform best when market regime is stable.
        """
        ...

    def _compute_volatility_component(self, ticker: str) -> float:
        """
        Volatility percentile score. Lower volatility = higher score
        for mean-reversion signals; inverse for momentum signals.
        Uses ATR percentile from the last 20 bars.
        """
        ...

    def _compute_confluence_component(self, alert: dict) -> float:
        """
        Technical factor confluence: counts how many of the following
        align with the signal direction:
        - ADX strength > 25
        - Momentum score > 0
        - MTF alignment = 'BULLISH' or 'BEARISH'
        - Sector gate alignment
        Each factor contributes 25 points to the 100-point scale.
        """
        ...
```

#### Outcome Tracker — `backend/services/outcome_tracker.py`

```python
class OutcomeTracker:
    """
    Tracks signal lifecycle from PENDING through resolution.
    Idempotent: calling update() with the same data produces no side effects.
    """

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    def update(
        self,
        signal_id: int,
        current_price: Optional[float] = None,
        current_high: Optional[float] = None,
        current_low: Optional[float] = None,
        bars_elapsed: Optional[int] = None,
    ) -> OutcomeState:
        """
        Idempotent state update based on closed-candle data.
        State machine:
          PENDING -> ACTIVE (when entry_price is set)
          ACTIVE -> TARGET_HIT (when high >= target_price)
          ACTIVE -> STOP_HIT (when low <= stop_price)
          ACTIVE -> TIME_EXPIRED (when bars_elapsed > max_bars)
          ACTIVE -> CLOSED (manual close via exit_price)

        Updates max_adverse_excursion and max_favorable_excursion
        on every call — these are running extrema, not final values.
        """
        ...

    def get(self, signal_id: int) -> OutcomeState:
        """Retrieve current outcome state without mutation."""
        ...
```

#### Self-Evaluator — `backend/services/self_evaluator.py`

```python
class SelfEvaluator:
    """
    On-demand analysis of historical signal performance cohorts.
    Executes within a single HTTP request context under 10 seconds.

    Analysis performed:
    1. Cohort win rates by (signal_type, regime)
    2. Decay half-life estimation (exponential fit on outcome_pct vs time)
    3. Failure mode identification (most common loss reason per cohort)
    4. Feature importance ranking (correlation of alert features with outcome)
    5. Weight calibration update (Bayesian update on prior weights)
    6. Degradation flagging (cohorts with win_rate < 40% and n > 10)
    """

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    def evaluate(
        self,
        signal_types: Optional[List[str]] = None,
        regimes: Optional[List[str]] = None,
        lookback_days: int = 90,
    ) -> EvaluationReport:
        """
        Runs all analyses and persists updated weights.
        Returns EvaluationReport with cohorts, updated weights, degraded signals.
        """
        ...
```

#### Regime Detector — `backend/services/regime_detector.py`

```python
class RegimeDetector:
    """
    Multi-vector regime detection extending the existing RegimeEngine.
    Outputs structured RegimeVector that modulates signal scoring weights.
    """

    def __init__(self, pool: asyncpg.Pool, cache: LRUCache):
        self._pool = pool
        self._cache = cache
        self._engine = get_regime_engine()  # reuse existing engine

    def detect(self, symbol: str, timeframe: str = "1D") -> RegimeVector:
        """
        1. Check regime_cache for non-expired entry
        2. If miss, compute via RegimeEngine + additional vectors:
           - Trend slope (SMA20/SMA50 ratio)
           - Momentum strength (RSI, MACD histogram)
           - Volatility percentile (ATR% vs 90-day distribution)
           - Breadth indicator (advance/decline ratio proxy via sector ETFs)
        3. Persist to regime_cache with expires_at = NOW() + 5min
        4. Return RegimeVector
        """
        ...
```

#### Explainability Engine — `backend/services/explainability.py`

```python
class ExplainabilityEngine:
    """
    Deterministic explainability layer.
    For each scored signal, outputs:
    - Trigger conditions (what caused the signal)
    - Contributing factor weights (numeric breakdown)
    - Regime impact (how regime modulated the score)
    - Explicit reasoning (human-readable string)
    """

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    def explain(self, signal_id: int) -> ExplainabilityResult:
        """
        1. Fetch signal_scores record
        2. Fetch original alert record
        3. Fetch regime_cache entry
        4. Compose breakdown JSON with all factor contributions
        5. Generate human-readable reasoning string
        6. Return ExplainabilityResult
        """
        ...
```

#### Portfolio Simulator — `backend/services/portfolio_simulator.py`

```python
class PortfolioSimulator:
    """
    Stateless portfolio simulation with Kelly-fractioned logic.
    Memory-bounded: processes candidates in a single pass.
    """

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    def simulate(
        self,
        candidates: List[dict],
        total_capital: float,
        max_drawdown_pct: float,
        kelly_fraction: float,
        correlation_threshold: float,
    ) -> SimulationResult:
        """
        1. Filter candidates by correlation constraint (pairwise corr < threshold)
        2. Size positions using Kelly fraction: size = kelly_fraction * edge / odds
        3. Enforce hard drawdown cap: if cumulative drawdown > max_drawdown_pct, stop
        4. Simulate equity progression using historical win rates per signal type
        5. Return standardized metrics
        """
        ...

    def _kelly_size(self, win_rate: float, avg_win: float, avg_loss: float, kelly_fraction: float) -> float:
        """
        Kelly criterion: K = W - (1-W)/R
        Where W = win probability, R = win/loss ratio.
        Apply fractional Kelly via kelly_fraction multiplier.
        Hard cap: no single position > 10% of total capital.
        """
        ...
```

### 3.3 LRU Cache Implementation

File: `backend/services/di_cache.py`

```python
"""
Vigil DI LRU Cache — Application-level caching without external dependencies.
Simulates Redis behavior using Python's OrderedDict with LRU eviction.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """
    Thread-safe LRU cache with configurable capacity and TTL.

    Key design:
    - OrderedDict provides O(1) get/put with LRU ordering
    - TTL is checked on access, not via background thread (stateless)
    - Max capacity enforced on every put
    - No external dependencies (no Redis, no memcached)
    """

    def __init__(self, max_size: int = 512, default_ttl: int = 300):
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get value by key. Returns None if missing or expired."""
        import time
        with self._lock:
            if key not in self._store:
                return None
            value, expiry = self._store[key]
            if time.time() > expiry:
                del self._store[key]
                return None
            # Move to end (most recently used)
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value with TTL. Evicts LRU entry if at capacity."""
        import time
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, time.time() + (ttl or self._default_ttl))
            if len(self._store) > self._max_size:
                self._store.popitem(last=False)  # Evict least recently used

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if key existed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> int:
        """Clear all entries. Returns count of removed items."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        with self._lock:
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "utilization_pct": round(len(self._store) / self._max_size * 100, 1),
            }


# Module-level singleton
_di_cache: Optional[LRUCache] = None
_cache_lock = threading.Lock()


def get_di_cache() -> LRUCache:
    """Get or create the DI LRU cache singleton."""
    global _di_cache
    if _di_cache is None:
        with _cache_lock:
            if _di_cache is None:
                _di_cache = LRUCache(max_size=512, default_ttl=300)
    return _di_cache
```

### 3.4 Database Optimization Queries

Composite and partial indexes (included in migration 002):

```sql
-- Composite index: score lookup by signal and regime (partial, non-null regime)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scores_signal_regime
    ON signal_scores (signal_id, regime_tag) WHERE regime_tag IS NOT NULL;

-- Partial index: only active outcomes (excludes CLOSED, reducing index size ~60%)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outcomes_state
    ON signal_outcomes (state) WHERE state != 'CLOSED';

-- Partial index: pending signals awaiting resolution
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outcomes_pending
    ON signal_outcomes (signal_id) WHERE state = 'PENDING';

-- Composite index: regime cache by symbol + timeframe (covers cache lookup)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regime_symbol_tf
    ON regime_cache (symbol, timeframe);

-- Query pattern: paginated outcome listing with composite sort
-- Uses idx_outcomes_updated for ORDER BY, partial index for WHERE
SELECT * FROM signal_outcomes
WHERE state != 'CLOSED'
ORDER BY updated_at DESC
LIMIT 50 OFFSET 0;

-- Query pattern: score lookup with regime filter
-- Uses idx_scores_signal_regime composite index
SELECT * FROM signal_scores
WHERE signal_id = $1 AND regime_tag = $2
ORDER BY computed_at DESC LIMIT 1;
```

Connection pooling: The existing `get_pool()` asyncpg pool (min_size=5, max_size=20) is reused. No additional pool configuration needed. DI endpoints use the same pool with `async with pool.acquire() as conn:` pattern.

---

## 4. New Endpoints Register

| Method | Path | Description | Auth | Polling Interval |
|--------|------|-------------|------|-----------------|
| `POST` | `/di/score` | Compute confidence score for a signal | API Key | On-demand, poll `GET /di/score/{id}` every 2s |
| `GET` | `/di/score/{signal_id}` | Retrieve computed score | None | Every 5s while signal is active |
| `POST` | `/di/outcome/update` | Idempotent outcome state update | API Key | Every 60s (per closed candle) |
| `GET` | `/di/outcome/{signal_id}` | Get current outcome lifecycle state | None | Every 30s |
| `POST` | `/di/evaluate` | Run self-evaluation on historical cohorts | API Key | On-demand (weekly recommended) |
| `GET` | `/di/regime/{symbol}` | Get regime vector for symbol | None | Every 60s |
| `GET` | `/di/explain/{signal_id}` | Get explainability breakdown | None | On-demand |
| `POST` | `/di/portfolio/simulate` | Run portfolio simulation | API Key | On-demand |
| `GET` | `/di/cache/stats` | Get LRU cache statistics | None | Debug only |

### Request/Response Structures

#### `POST /di/score`

```json
// Request
{
  "signal_id": 42,
  "idempotency_key": "req_abc123"
}

// Response (200)
{
  "signal_id": 42,
  "score": 73,
  "components": {
    "hit_rate": 0.65,
    "regime_alignment": 0.80,
    "volatility": 0.70,
    "confluence": 0.75
  },
  "regime_tag": "TRENDING",
  "computed_at": "2026-04-03T20:00:00Z"
}
```

#### `POST /di/outcome/update`

```json
// Request
{
  "signal_id": 42,
  "idempotency_key": "req_def456",
  "current_price": 185.50,
  "current_high": 187.00,
  "current_low": 183.20,
  "bars_elapsed": 5
}

// Response (200)
{
  "signal_id": 42,
  "state": "ACTIVE",
  "entry_price": 182.00,
  "exit_price": null,
  "outcome_pct": 1.92,
  "max_adverse_excursion": -0.55,
  "max_favorable_excursion": 2.75,
  "time_in_trade_bars": 5,
  "final_pnl_state": null,
  "updated_at": "2026-04-03T20:05:00Z"
}
```

#### `POST /di/evaluate`

```json
// Request
{
  "signal_types": ["VOLUME_SPIKE_UP", "ACCUMULATION_DETECTED"],
  "regimes": ["TRENDING", "SIDEWAYS"],
  "lookback_days": 90
}

// Response (200)
{
  "cohorts": [
    {
      "cohort_key": "VOLUME_SPIKE_UP:TRENDING",
      "signal_type": "VOLUME_SPIKE_UP",
      "regime": "TRENDING",
      "sample_size": 45,
      "win_rate": 0.62,
      "avg_pnl": 2.3,
      "decay_half_life": 12.5,
      "failure_mode": "regime_transition",
      "feature_importance": {"adx_strength": 0.35, "momentum_score": 0.28}
    }
  ],
  "updated_weights": [
    {
      "signal_type": "VOLUME_SPIKE_UP",
      "regime": "TRENDING",
      "hit_rate_weight": 0.35,
      "regime_weight": 0.20,
      "volatility_weight": 0.20,
      "confluence_weight": 0.25,
      "confidence_threshold": 55,
      "is_degraded": false
    }
  ],
  "degraded_signals": [],
  "execution_ms": 3200
}
```

#### `GET /di/regime/{symbol}`

```json
// Response (200)
{
  "symbol": "SPY",
  "timeframe": "1D",
  "regime": "TRENDING",
  "confidence": 0.78,
  "vector": {
    "trend_slope": 0.65,
    "momentum_strength": 0.72,
    "volatility_percentile": 0.35,
    "breadth": 0.60
  },
  "factors": {
    "sma20_slope_pct": 0.8,
    "rsi": 58.2,
    "atr_pct": 1.2,
    "adx": 28.5
  },
  "cached": true,
  "computed_at": "2026-04-03T19:55:00Z"
}
```

#### `GET /di/explain/{signal_id}`

```json
// Response (200)
{
  "signal_id": 42,
  "score": 73,
  "breakdown": {
    "trigger": {
      "signal_type": "VOLUME_SPIKE_UP",
      "volume_ratio": 2.3,
      "change_pct": 3.1
    },
    "factors": {
      "hit_rate": {"weight": 0.35, "score": 65, "contribution": 22.75},
      "regime": {"weight": 0.20, "score": 80, "contribution": 16.0},
      "volatility": {"weight": 0.20, "score": 70, "contribution": 14.0},
      "confluence": {"weight": 0.25, "score": 80, "contribution": 20.0}
    },
    "regime_impact": {
      "current_regime": "TRENDING",
      "signal_regime": "TRENDING",
      "alignment_bonus": 10,
      "weight_adjustment": {"regime_weight": 0.20}
    }
  },
  "human_readable": "Score 73/100: VOLUME_SPIKE_UP signal in TRENDING regime. Strong regime alignment (+10pts). Historical hit rate 65% in this regime. Volatility at 70th percentile — acceptable for momentum entry. 4 of 4 technical factors aligned (ADX 28.5, positive momentum, bullish MTF, sector aligned).",
  "regime_impact": {
    "alignment": "MATCH",
    "bonus_points": 10,
    "weight_overrides": {"regime_weight": 0.20}
  },
  "generated_at": "2026-04-03T20:00:00Z"
}
```

#### `POST /di/portfolio/simulate`

```json
// Request
{
  "candidates": [
    {"signal_id": 42, "ticker": "AAPL", "score": 73, "entry_price": 182.0, "stop_price": 178.0, "target_price": 190.0},
    {"signal_id": 43, "ticker": "MSFT", "score": 65, "entry_price": 410.0, "stop_price": 400.0, "target_price": 425.0},
    {"signal_id": 44, "ticker": "NVDA", "score": 80, "entry_price": 880.0, "stop_price": 850.0, "target_price": 920.0}
  ],
  "total_capital": 100000.0,
  "max_drawdown_pct": 10.0,
  "kelly_fraction": 0.25,
  "correlation_threshold": 0.7
}

// Response (200)
{
  "cumulative_return_pct": 4.2,
  "max_drawdown_pct": 3.8,
  "sharpe_ratio": 1.45,
  "trade_distribution": {"WIN": 2, "LOSS": 1, "BREAKEVEN": 0},
  "positions": [
    {"ticker": "NVDA", "size": 0.045, "allocation": 4500.0, "kelly_fraction": 0.20},
    {"ticker": "AAPL", "size": 0.030, "allocation": 3000.0, "kelly_fraction": 0.15},
    {"ticker": "MSFT", "size": 0.020, "allocation": 2000.0, "kelly_fraction": 0.10}
  ],
  "execution_ms": 45
}
```

### Client-Side Retry Logic

```typescript
// Recommended polling configuration
const POLL_CONFIG = {
  score: { interval: 2000, maxRetries: 15, backoff: 'linear' },     // 30s total
  outcome: { interval: 30000, maxRetries: Infinity, backoff: 'none' }, // continuous
  regime: { interval: 60000, maxRetries: Infinity, backoff: 'none' },  // continuous
  evaluate: { interval: 0, maxRetries: 0, backoff: 'none' },           // single request
  simulate: { interval: 0, maxRetries: 0, backoff: 'none' },           // single request
  explain: { interval: 0, maxRetries: 3, backoff: 'exponential' },     // on-demand
};

// Retry logic for polling endpoints
async function pollWithRetry<T>(
  fn: () => Promise<T>,
  config: { interval: number; maxRetries: number; backoff: 'linear' | 'exponential' | 'none' }
): Promise<T> {
  for (let i = 0; i < config.maxRetries; i++) {
    const result = await fn();
    if (result) return result;
    const delay = config.backoff === 'exponential'
      ? config.interval * Math.pow(2, i)
      : config.backoff === 'linear'
        ? config.interval * (i + 1)
        : config.interval;
    await new Promise(r => setTimeout(r, delay));
  }
  throw new Error('Polling timeout exceeded');
}
```

---

## 5. Next.js Integration Points

### 5.1 React Query Hook Patterns

```typescript
// frontend/lib/di-hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type {
  SignalScore,
  OutcomeState,
  RegimeVector,
  ExplainResult,
  SimulationResult,
  EvaluationReport,
} from './di-types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// --- Signal Score Polling ---
export function useSignalScore(signalId: number, enabled = true) {
  return useQuery<SignalScore>({
    queryKey: ['di-score', signalId],
    queryFn: async () => {
      const res = await fetch(`${BASE_URL}/di/score/${signalId}`);
      if (!res.ok) throw new Error(`Score fetch failed: ${res.status}`);
      return res.json();
    },
    refetchInterval: enabled ? 5000 : false,
    staleTime: 4000,
    retry: 3,
    enabled: enabled && signalId > 0,
  });
}

// --- Outcome State Polling ---
export function useOutcomeState(signalId: number, enabled = true) {
  return useQuery<OutcomeState>({
    queryKey: ['di-outcome', signalId],
    queryFn: async () => {
      const res = await fetch(`${BASE_URL}/di/outcome/${signalId}`);
      if (!res.ok) throw new Error(`Outcome fetch failed: ${res.status}`);
      return res.json();
    },
    refetchInterval: enabled ? 30000 : false,
    staleTime: 25000,
    retry: 2,
    enabled: enabled && signalId > 0,
  });
}

// --- Regime Vector Polling ---
export function useRegimeVector(symbol: string, timeframe = '1D', enabled = true) {
  return useQuery<RegimeVector>({
    queryKey: ['di-regime', symbol, timeframe],
    queryFn: async () => {
      const res = await fetch(
        `${BASE_URL}/di/regime/${encodeURIComponent(symbol)}?timeframe=${timeframe}`
      );
      if (!res.ok) throw new Error(`Regime fetch failed: ${res.status}`);
      return res.json();
    },
    refetchInterval: enabled ? 60000 : false,
    staleTime: 55000,
    retry: 2,
    enabled: enabled && !!symbol,
  });
}

// --- Explainability (on-demand, no polling) ---
export function useExplainability(signalId: number | null) {
  return useQuery<ExplainResult>({
    queryKey: ['di-explain', signalId],
    queryFn: async () => {
      if (!signalId) throw new Error('No signal ID');
      const res = await fetch(`${BASE_URL}/di/explain/${signalId}`);
      if (!res.ok) throw new Error(`Explain fetch failed: ${res.status}`);
      return res.json();
    },
    enabled: !!signalId,
    staleTime: Infinity, // Never stale — explainability is deterministic
    retry: 1,
  });
}

// --- Portfolio Simulation (mutation, no polling) ---
export function usePortfolioSimulation() {
  const queryClient = useQueryClient();
  return useMutation<SimulationResult, Error, SimulationRequest>({
    mutationFn: async (req) => {
      const res = await fetch(`${BASE_URL}/di/portfolio/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      });
      if (!res.ok) throw new Error(`Simulation failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['di-score'] });
    },
  });
}

// --- Self-Evaluation (mutation, no polling) ---
export function useSelfEvaluation() {
  return useMutation<EvaluationReport, Error, EvaluationRequest>({
    mutationFn: async (req) => {
      const res = await fetch(`${BASE_URL}/di/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      });
      if (!res.ok) throw new Error(`Evaluation failed: ${res.status}`);
      return res.json();
    },
  });
}
```

### 5.2 Component Data Contracts

```typescript
// frontend/lib/di-types.ts

export interface SignalScore {
  signal_id: number;
  score: number;           // 0-100
  components: {            // Normalized 0-1 per component
    hit_rate: number;
    regime_alignment: number;
    volatility: number;
    confluence: number;
  };
  regime_tag: string | null;
  computed_at: string;
}

export interface OutcomeState {
  signal_id: number;
  state: 'PENDING' | 'ACTIVE' | 'TARGET_HIT' | 'STOP_HIT' | 'TIME_EXPIRED' | 'CLOSED';
  entry_price: number | null;
  exit_price: number | null;
  outcome_pct: number | null;
  max_adverse_excursion: number | null;
  max_favorable_excursion: number | null;
  time_in_trade_bars: number | null;
  final_pnl_state: 'WIN' | 'LOSS' | 'BREAKEVEN' | 'UNRESOLVED' | null;
  updated_at: string;
}

export interface RegimeVector {
  symbol: string;
  timeframe: string;
  regime: string;
  confidence: number;
  vector: {
    trend_slope: number;
    momentum_strength: number;
    volatility_percentile: number;
    breadth: number;
  };
  factors: Record<string, number>;
  cached: boolean;
  computed_at: string;
}

export interface ExplainResult {
  signal_id: number;
  score: number;
  breakdown: {
    trigger: Record<string, unknown>;
    factors: Record<string, { weight: number; score: number; contribution: number }>;
    regime_impact: Record<string, unknown>;
  };
  human_readable: string;
  regime_impact: {
    alignment: string;
    bonus_points: number;
    weight_overrides: Record<string, number>;
  };
  generated_at: string;
}

export interface SimulationResult {
  cumulative_return_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  trade_distribution: Record<string, number>;
  positions: Array<{
    ticker: string;
    size: number;
    allocation: number;
    kelly_fraction: number;
  }>;
  execution_ms: number;
}

export interface EvaluationReport {
  cohorts: Array<{
    cohort_key: string;
    signal_type: string;
    regime: string;
    sample_size: number;
    win_rate: number;
    avg_pnl: number;
    decay_half_life: number;
    failure_mode: string;
    feature_importance: Record<string, number>;
  }>;
  updated_weights: Array<{
    signal_type: string;
    regime: string;
    hit_rate_weight: number;
    regime_weight: number;
    volatility_weight: number;
    confluence_weight: number;
    confidence_threshold: number;
    is_degraded: boolean;
  }>;
  degraded_signals: string[];
  execution_ms: number;
}
```

### 5.3 Wiring Strategy for Explainability Without Over-Fetching

```typescript
// Pattern: Lazy-load explainability data only when user expands a signal card.
// The explainability response is ~2KB — small enough for inline rendering,
// but we avoid fetching it for every signal in the list.

// frontend/components/SignalCard.tsx (extension)
import { useState } from 'react';
import { useExplainability } from '@/lib/di-hooks';

export function SignalCardWithExplain({ alert }: { alert: Alert }) {
  const [showExplain, setShowExplain] = useState(false);
  const { data: explain, isLoading } = useExplainability(
    showExplain ? alert.id : null  // Only fetch when expanded
  );

  return (
    <div className="signal-card">
      {/* Existing alert display */}
      <button onClick={() => setShowExplain(!showExplain)}>
        {showExplain ? 'Hide Analysis' : 'Show Analysis'}
      </button>

      {showExplain && (
        <div className="explain-panel">
          {isLoading ? (
            <Skeleton />
          ) : explain ? (
            <>
              <ScoreBar score={explain.score} />
              <FactorBreakdown factors={explain.breakdown.factors} />
              <Reasoning text={explain.human_readable} />
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
```

### 5.4 Regime Dashboard Component

```typescript
// frontend/components/RegimeDashboard.tsx
import { useRegimeVector } from '@/lib/di-hooks';

export function RegimeDashboard({ symbols }: { symbols: string[] }) {
  // Poll regime for each symbol with staggered queries
  const regimeQueries = symbols.map((sym) =>
    useRegimeVector(sym, '1D', true)
  );

  return (
    <div className="regime-dashboard">
      {regimeQueries.map(({ data, isLoading }, i) => (
        <RegimeCard
          key={symbols[i]}
          symbol={symbols[i]}
          regime={data}
          loading={isLoading}
        />
      ))}
    </div>
  );
}
```

### 5.5 Portfolio Simulator Component

```typescript
// frontend/components/PortfolioSimulator.tsx
import { useState } from 'react';
import { usePortfolioSimulation } from '@/lib/di-hooks';
import type { PositionCandidate } from '@/lib/di-types';

export function PortfolioSimulator({ candidates }: { candidates: PositionCandidate[] }) {
  const [capital, setCapital] = useState(100000);
  const simulate = usePortfolioSimulation();

  const handleSimulate = () => {
    simulate.mutate({
      candidates,
      total_capital: capital,
      max_drawdown_pct: 10,
      kelly_fraction: 0.25,
      correlation_threshold: 0.7,
    });
  };

  if (simulate.isSuccess) {
    const result = simulate.data;
    return (
      <div className="simulation-results">
        <MetricCard label="Cumulative Return" value={`${result.cumulative_return_pct.toFixed(1)}%`} />
        <MetricCard label="Max Drawdown" value={`${result.max_drawdown_pct.toFixed(1)}%`} />
        <MetricCard label="Sharpe Ratio" value={result.sharpe_ratio.toFixed(2)} />
        <PositionTable positions={result.positions} />
      </div>
    );
  }

  return (
    <div className="simulator-controls">
      <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value))} />
      <button onClick={handleSimulate} disabled={simulate.isPending}>
        {simulate.isPending ? 'Simulating...' : 'Run Simulation'}
      </button>
    </div>
  );
}
```

---

## 6. Decision Quality Metrics

### Feature-to-Metric Mapping

| Feature | Measurable Improvement | Target Metric | Baseline | Target |
|---------|----------------------|---------------|----------|--------|
| **Signal Scoring (0-100)** | Filters low-confidence signals, reducing false positives | False positive rate | ~40% (binary signal/no-signal) | <25% (score <50 filtered) |
| **Adaptive Weight Calibration** | Improves score accuracy by weighting factors that actually predict outcomes in current regime | Score-to-outcome correlation (Pearson r) | N/A (no scoring) | r > 0.45 |
| **Outcome Tracking** | Enables measurement of actual signal performance vs. predicted score | Brier score (probability calibration) | N/A | <0.20 |
| **MAE/MFE Tracking** | Identifies optimal stop/target placement, reducing average loss magnitude | Average loss per losing trade | Unmeasured | -1.5% or better |
| **Self-Evaluation Loop** | Detects degraded signal types before they cause drawdowns | Time-to-detection of regime shift | Days (manual review) | <1 hour (automated) |
| **Regime Detection** | Modulates scoring weights to match current market conditions | Regime-specific win rate delta | Uniform weights | +8% win rate in matched regime vs. mismatched |
| **Explainability** | Enables human-in-the-loop validation of scoring logic | User trust score (qualitative) | N/A | >80% of explained scores accepted without override |
| **Portfolio Simulation** | Prevents over-concentration in correlated signals | Portfolio-level max drawdown | Unconstrained | <10% with correlation filter |
| **Kelly-Fractioned Sizing** | Optimizes position sizing for geometric growth | Geometric mean return per trade | Fixed sizing | +15% geometric mean vs. equal-weight |
| **LRU Caching** | Reduces redundant compute on repeated polling | p99 response time for regime endpoint | ~500ms (fresh compute) | <50ms (cached) |
| **Composite Indexes** | Accelerates score/outcome lookups on large datasets | p99 response time for /di/score/{id} | N/A | <200ms at 100K rows |

### Quantifiable Performance Targets

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Scoring accuracy** | Score >70 signals achieve >60% win rate | Cohort analysis via /di/evaluate |
| **Outcome resolution rate** | >80% of signals resolved within 10 bars | signal_outcomes.state distribution |
| **Self-evaluation latency** | <10 seconds for 90-day lookback | /di/evaluate response `execution_ms` |
| **Regime cache hit rate** | >90% for polling clients | LRUCache.stats() utilization |
| **Portfolio simulation latency** | <500ms for 50 candidates | /di/portfolio/simulate response `execution_ms` |
| **Explainability completeness** | 100% of scored signals have explainable breakdown | /di/explain/{id} returns non-null for all fields |
| **API response time (p99)** | <200ms for all GET endpoints | Prometheus histogram |
| **Memory footprint** | <50MB for LRU cache at 512 entries | LRUCache.stats() + process RSS |
| **Database query time (p99)** | <50ms for indexed lookups | EXPLAIN ANALYZE on production queries |

### False-Positive Reduction Strategy

1. **Score threshold gating**: Signals with score <50 are flagged as `LOW_CONFIDENCE` and excluded from portfolio simulation by default.
2. **Regime mismatch penalty**: If signal's historical best regime differs from current regime, score is reduced by 10-20 points.
3. **Confluence floor**: Signals with confluence score <50 (fewer than 2 of 4 technical factors aligned) are capped at score 60 regardless of other components.
4. **Degradation circuit breaker**: Self-evaluation flags signal types with win_rate <40% and sample_size >10 as `is_degraded=true`. These signals receive a -15 point score penalty until recalibration.
