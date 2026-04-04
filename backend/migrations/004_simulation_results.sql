-- ============================================================================
-- Vigil Migration 004: Portfolio Simulation Results
-- ============================================================================
-- Purpose: Store deterministic walk-forward simulation results for
--          multi-signal portfolio exposure analysis.
--
-- Date: 2026-04-03
-- Notes:
--   - Supports walk-forward, monte_carlo, and historical simulation types.
--   - Uses result_hash for deterministic deduplication.
--   - Equity curve stored as compressed JSONB array.
-- ============================================================================

CREATE TABLE IF NOT EXISTS di_simulation_results (
    id BIGSERIAL PRIMARY KEY,
    simulation_name VARCHAR(128) NOT NULL,
    simulation_type VARCHAR(32) NOT NULL CHECK (simulation_type IN ('walk_forward', 'monte_carlo', 'historical')),
    
    -- Simulation parameters (JSONB for flexibility)
    params JSONB NOT NULL DEFAULT '{}',
    
    -- Portfolio-level metrics
    total_return_pct NUMERIC(10, 4),
    annualized_return_pct NUMERIC(10, 4),
    max_drawdown_pct NUMERIC(10, 4),
    sharpe_ratio NUMERIC(8, 4),
    sortino_ratio NUMERIC(8, 4),
    calmar_ratio NUMERIC(8, 4),
    win_rate NUMERIC(5, 4),
    profit_factor NUMERIC(8, 4),
    total_signals INTEGER,
    winning_signals INTEGER,
    losing_signals INTEGER,
    
    -- Time bounds
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    
    -- Equity curve data (compressed JSONB array of {date, equity, drawdown})
    equity_curve JSONB,
    
    -- Deterministic hash for reproducibility verification
    result_hash VARCHAR(64) UNIQUE,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(64) DEFAULT 'system',
    
    -- Constraints
    CONSTRAINT chk_simulation_dates CHECK (end_date >= start_date),
    CONSTRAINT chk_return_bounds CHECK (
        total_return_pct IS NULL OR 
        (total_return_pct >= -100 AND total_return_pct <= 10000)
    ),
    CONSTRAINT chk_drawdown_bounds CHECK (
        max_drawdown_pct IS NULL OR 
        (max_drawdown_pct <= 0 AND max_drawdown_pct >= -100)
    ),
    CONSTRAINT chk_win_rate_bounds CHECK (
        win_rate IS NULL OR 
        (win_rate >= 0 AND win_rate <= 1)
    )
);

-- Index for simulation lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_simulations_name_type 
    ON di_simulation_results (simulation_name, simulation_type);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_simulations_created 
    ON di_simulation_results (created_at DESC);

-- Unique constraint for deterministic results
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_simulations_hash 
    ON di_simulation_results (result_hash) 
    WHERE result_hash IS NOT NULL;

-- Comments
COMMENT ON TABLE di_simulation_results IS 'Deterministic portfolio simulation results';
COMMENT ON COLUMN di_simulation_results.result_hash IS 'SHA-256 hash of params + start_date + end_date for deduplication';
COMMENT ON COLUMN di_simulation_results.equity_curve IS 'JSONB array of {date, equity, drawdown} points';
