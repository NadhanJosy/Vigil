-- ============================================================================
-- Vigil Migration 001: Neon PostgreSQL Optimizations
-- ============================================================================
-- Purpose: Add indexes for common query patterns to improve dashboard and
--          signal retrieval performance on Neon's serverless PostgreSQL.
--
-- Notes:
--   - All indexes use CONCURRENTLY to avoid locking tables during creation
--     (required for Neon's serverless architecture where long-held locks
--     can cause connection drops).
--   - This migration is idempotent: safe to run multiple times.
--   - Run with: psql "$DATABASE_URL" -f migrations/001_neon_optimizations.sql
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Index: idx_alerts_symbol_timestamp
-- Purpose: Accelerates queries that filter alerts by symbol (ticker) and
--          order by recency. Used by /alerts?ticker=XYZ and dashboard
--          queries that show the latest signals per ticker.
-- ---------------------------------------------------------------------------
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_symbol_timestamp
    ON alerts (ticker, created_at DESC);

-- ---------------------------------------------------------------------------
-- Index: idx_alerts_severity
-- Purpose: Supports filtering and sorting alerts by severity/action level.
--          Used when users filter alerts by action type (e.g., BUY, SELL,
--          WATCH) or when the alert router prioritizes high-severity alerts.
-- ---------------------------------------------------------------------------
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_severity
    ON alerts (action);

-- ---------------------------------------------------------------------------
-- Index: idx_signals_symbol_timestamp
-- Purpose: Accelerates queries on the signals table (if it exists) for
--          symbol-based lookups ordered by recency. Mirrors the alerts
--          index pattern for consistency.
-- Note:    Uses IF NOT EXISTS on the table to handle environments where
--          the signals table may not yet be created.
-- ---------------------------------------------------------------------------
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signals_symbol_timestamp
--     ON signals (symbol, timestamp DESC);

-- ---------------------------------------------------------------------------
-- Index: idx_signals_edge_score
-- Purpose: Supports ranking signals by edge_score for "top signals" queries
--          and portfolio construction logic that prioritizes high-conviction
--          setups.
-- ---------------------------------------------------------------------------
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signals_edge_score
--     ON signals (edge_score DESC);

-- ---------------------------------------------------------------------------
-- Index: idx_signals_regime
-- Purpose: Accelerates regime-based filtering of signals. Used by the
--          regime engine to find signals that match the current market
--          regime (e.g., TRENDING, RANGING, HIGH_VOL).
-- ---------------------------------------------------------------------------
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signals_regime
--     ON signals (regime);

-- ---------------------------------------------------------------------------
-- Index: idx_alerts_regime
-- Purpose: Accelerates regime-based filtering of alerts. Used when
--          querying alerts that occurred under a specific market regime.
-- ---------------------------------------------------------------------------
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_regime
    ON alerts (regime) WHERE regime IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Index: idx_alerts_edge_score
-- Purpose: Supports ranking alerts by edge_score for "top alerts" queries
--          and dashboard sorting by conviction level.
-- ---------------------------------------------------------------------------
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_edge_score
    ON alerts (edge_score DESC) WHERE edge_score IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Index: idx_alerts_outcome_result
-- Purpose: Accelerates outcome evaluation queries that filter for alerts
--          awaiting outcome analysis (WHERE outcome_result IS NULL).
-- ---------------------------------------------------------------------------
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_outcome_result
    ON alerts (outcome_result) WHERE outcome_result IS NULL;

-- ---------------------------------------------------------------------------
-- Index: idx_alerts_created_at
-- Purpose: General-purpose index for time-based queries. Used by system
--          metrics, decay calculations, and any query ordering by
--          created_at.
-- ---------------------------------------------------------------------------
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_created_at
    ON alerts (created_at DESC);

-- ============================================================================
-- Migration complete.
-- To verify indexes were created, run:
--   SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'alerts';
-- ============================================================================
