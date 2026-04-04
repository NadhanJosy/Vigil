-- ============================================================================
-- Vigil Migration 003: Performance Indexes for Decision Intelligence Queries
-- ============================================================================
-- Purpose: Optimize polling-based query patterns, eliminate N+1 joins,
--          and support keyset pagination across all DI endpoints.
--
-- Date: 2026-04-03
-- Notes:
--   - All indexes use CONCURRENTLY to avoid locking tables during creation.
--   - These indexes target high-frequency query patterns identified in
--     the polling migration plan and DI architecture documentation.
-- ============================================================================

-- ============================================================================
-- Prerequisite Tables (must exist before indexes can be created)
-- ============================================================================
-- These tables support the Decision Intelligence API endpoints.
-- They are created here (rather than in a separate migration) because the
-- indexes in this file depend on them and this migration was written assuming
-- they already existed.

CREATE TABLE IF NOT EXISTS di_signals (
    id              SERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,
    confidence_score REAL,
    status          TEXT NOT NULL DEFAULT 'pending',
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    entry_price     REAL,
    target_price    REAL,
    stop_price      REAL
);

CREATE TABLE IF NOT EXISTS di_outcomes (
    id                      SERIAL PRIMARY KEY,
    signal_id               INTEGER NOT NULL REFERENCES di_signals(id) ON DELETE CASCADE,
    status                  TEXT NOT NULL DEFAULT 'pending',
    entry_price             REAL,
    current_price           REAL,
    target_price            REAL,
    stop_price              REAL,
    peak_price              REAL,
    trough_price            REAL,
    peak_drawdown_pct       REAL,
    realized_return_pct     REAL,
    time_to_resolution_hours REAL,
    next_check_at           TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at             TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS di_signal_factors (
    id              SERIAL PRIMARY KEY,
    signal_id       INTEGER NOT NULL REFERENCES di_signals(id) ON DELETE CASCADE,
    factor_name     TEXT NOT NULL,
    factor_value    REAL,
    weight          REAL NOT NULL DEFAULT 1.0,
    description     TEXT
);

CREATE TABLE IF NOT EXISTS di_regime_states (
    id              SERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    regime_type     TEXT NOT NULL,
    confidence      REAL NOT NULL,
    volatility_level REAL,
    trend_strength  REAL,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_current      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS di_explanations (
    id              SERIAL PRIMARY KEY,
    signal_id       INTEGER NOT NULL REFERENCES di_signals(id) ON DELETE CASCADE,
    primary_trigger TEXT NOT NULL,
    contributing_factors JSONB,
    confidence_grade TEXT,
    regime_context  TEXT,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Performance Indexes
-- ============================================================================

-- Index 1: Signal listing with keyset pagination support
-- Used by: GET /api/di/signals (paginated list)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signals_list_cursor
    ON di_signals (detected_at DESC, id DESC);

-- Index 2: Outcome tracking polling queries
-- Used by: outcome_tracker.py polling cycle to find pending outcomes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outcomes_polling_query 
    ON di_outcomes (status, next_check_at) 
    WHERE status IN ('PENDING', 'ACTIVE');

-- Index 3: Signal factor confluence scoring
-- Used by: scoring_engine.py batch score calculation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signal_factors_signal 
    ON di_signal_factors (signal_id, factor_name, weight);

-- Index 4: Regime state time-series queries
-- Used by: regime_detector.py and portfolio risk calculations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regime_states_timeline 
    ON di_regime_states (detected_at DESC, id DESC);

-- Index 5: Explanation lookup by signal
-- Used by: explainability.py and signal detail views
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_explanations_by_signal 
    ON di_explanations (signal_id);

-- Index 6: Outcome resolution tracking
-- Used by: outcome_tracker.py resolution queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outcomes_resolution 
    ON di_outcomes (signal_id, status, resolved_at) 
    WHERE resolved_at IS NULL;

-- Index 7: Confidence score filtering and sorting
-- Used by: signal ranking and filtering endpoints
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signals_confidence_score 
    ON di_signals (confidence_score DESC, detected_at DESC) 
    WHERE confidence_score IS NOT NULL;

-- Index 8: Multi-column index for signal filtering
-- Used by: filtered signal queries with symbol + status + date
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signals_filter_composite 
    ON di_signals (symbol, status, detected_at DESC);

-- Add comments for documentation
COMMENT ON INDEX idx_signals_list_cursor IS 'Keyset pagination cursor for signal listing';
COMMENT ON INDEX idx_outcomes_polling_query IS 'Polling query for outcome state machine updates';
COMMENT ON INDEX idx_signal_factors_signal IS 'Batch factor aggregation for scoring engine';
COMMENT ON INDEX idx_regime_states_timeline IS 'Time-series regime state queries';
COMMENT ON INDEX idx_explanations_by_signal IS 'Explanation lookup for signal detail views';
COMMENT ON INDEX idx_outcomes_resolution IS 'Resolution tracking for pending outcomes';
COMMENT ON INDEX idx_signals_confidence_score IS 'Confidence-based signal ranking';
COMMENT ON INDEX idx_signals_filter_composite IS 'Multi-filter signal queries (symbol + status + date)';
