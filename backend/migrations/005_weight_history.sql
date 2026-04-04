-- ============================================================================
-- Vigil Migration 005: Adaptive Weight Calibration History
-- ============================================================================
-- Purpose: Track scoring weight adjustments over time for audit,
--          rollback, and performance attribution analysis.
--
-- Date: 2026-04-03
-- Notes:
--   - Maintains full snapshots of weight configurations.
--   - Ensures only one active weight configuration exists at any time.
--   - Supports scheduled and manual recalibration triggers.
-- ============================================================================

CREATE TABLE IF NOT EXISTS di_weight_history (
    id BIGSERIAL PRIMARY KEY,
    
    -- Weight configuration (full snapshot)
    weights JSONB NOT NULL,
    
    -- Calibration metadata
    calibration_window_days INTEGER NOT NULL,
    sample_size INTEGER NOT NULL,
    win_rate_before NUMERIC(5, 4),
    win_rate_after NUMERIC(5, 4),
    statistical_significance NUMERIC(5, 4),  -- p-value if applicable
    
    -- Trigger information
    trigger_reason VARCHAR(128) NOT NULL DEFAULT 'scheduled_recalibration',
    triggered_by VARCHAR(64) DEFAULT 'system',
    
    -- Status
    status VARCHAR(32) NOT NULL DEFAULT 'active' 
        CHECK (status IN ('active', 'superseded', 'rolled_back')),
    
    -- Temporal tracking
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_calibration_window CHECK (calibration_window_days > 0),
    CONSTRAINT chk_sample_size CHECK (sample_size > 0),
    CONSTRAINT chk_effective_dates CHECK (
        effective_until IS NULL OR effective_until >= effective_from
    )
);

-- Index for active weight lookup
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_weight_history_active 
    ON di_weight_history (status) 
    WHERE status = 'active';

-- Index for weight history timeline
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_weight_history_timeline 
    ON di_weight_history (effective_from DESC);

-- Comments
COMMENT ON TABLE di_weight_history IS 'Historical record of scoring weight configurations';
COMMENT ON COLUMN di_weight_history.weights IS 'Full weight snapshot: {factor_name: weight_value}';
COMMENT ON INDEX idx_weight_history_active IS 'Ensures only one active weight configuration exists';
