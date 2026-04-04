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
