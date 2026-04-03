# Vigil Architecture Migration Plan

> **Status**: Partial FastAPI migration complete. This document covers cleanup, Next.js frontend migration, Neon PostgreSQL optimization, and deployment configuration updates.
>
> **Last Updated**: 2026-04-03
>
> **Target**: Institutional-grade, zero-cost architecture

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Assessment](#2-current-state-assessment)
3. [Deliverable 1: API Endpoint Migration Plan](#3-deliverable-1-api-endpoint-migration-plan)
4. [Deliverable 2: Database Schema & Neon PostgreSQL Optimization](#4-deliverable-2-database-schema--neon-postgresql-optimization)
5. [Deliverable 3: Next.js Frontend Architecture](#5-deliverable-3-nextjs-frontend-architecture)
6. [Deliverable 4: Scheduler Migration & Cleanup](#6-deliverable-4-scheduler-migration--cleanup)
7. [Deliverable 5: Observability Completion Plan](#7-deliverable-5-observability-completion-plan)
8. [Deliverable 6: Deployment Configuration](#8-deliverable-6-deployment-configuration)
9. [Deliverable 7: Risk Assessment & Breaking Changes](#9-deliverable-7-risk-assessment--breaking-changes)
10. [Deliverable 8: Implementation Timeline](#10-deliverable-8-implementation-timeline)

---

## 1. Executive Summary

### Key Discovery: Partial FastAPI Migration Already Complete

The Vigil codebase has **already been partially migrated** from Flask to FastAPI. The [`api.py`](api.py:1) file shows:

- ✅ FastAPI app with async endpoints
- ✅ Pydantic models (`AlertResponse`, `WatchlistRequest`, `BacktestRequest`)
- ✅ `AsyncIOScheduler` integrated into startup event
- ✅ `MetricsMiddleware` for Prometheus-style observability
- ✅ Structured JSON logging configured
- ✅ CORS middleware with dynamic origins
- ✅ JWT/API key authentication

### Remaining Work

| Area | Status | Effort |
|------|--------|--------|
| Backend FastAPI routes | ✅ Complete | None |
| Flask dependency cleanup | ⚠️ Partial | Low |
| Legacy scheduler.py removal | ⚠️ Pending | Low |
| Next.js frontend | ❌ Not started | High |
| Neon PostgreSQL optimization | ❌ Not started | Medium |
| Deployment config (uvicorn) | ❌ Not started | Low |
| Observability completion | ⚠️ Partial | Medium |

### Migration Strategy

This plan follows a **phased approach**:
1. **Phase 1**: Cleanup & consolidation (remove Flask deps, update Procfile)
2. **Phase 2**: Database optimization for Neon PostgreSQL
3. **Phase 3**: Next.js frontend build
4. **Phase 4**: Observability hardening & production readiness

---

## 2. Current State Assessment

### File-by-File Analysis

| File | Current State | Migration Status |
|------|--------------|------------------|
| [`api.py`](api.py:1) | FastAPI with async endpoints, Pydantic models, AsyncIOScheduler | ✅ Migrated |
| [`database.py`](database.py:1) | psycopg2 with `ThreadedConnectionPool`, `RealDictCursor` | ⚠️ Needs Neon optimization |
| [`scheduler.py`](scheduler.py:1) | `BlockingScheduler` (standalone process) | ❌ Deprecated, remove |
| [`data.py`](data.py:1) | Synchronous yfinance, trap detection, accumulation | ✅ Keep (run via threadpool) |
| [`advanced_signals.py`](advanced_signals.py:1) | Signal analysis engine | ✅ Keep |
| [`services/alert_router.py`](services/alert_router.py:1) | Alert dispatch with retry | ✅ Keep |
| [`services/cache.py`](services/cache.py:1) | Redis + in-memory fallback | ✅ Keep |
| [`services/correlation_engine.py`](services/correlation_engine.py:1) | Pearson/Spearman correlation | ✅ Keep |
| [`services/dedup.py`](services/dedup.py:1) | SHA256 fingerprinting | ✅ Keep |
| [`services/distributed_lock.py`](services/distributed_lock.py:1) | Redis-based distributed locking | ✅ Keep |
| [`services/event_bus.py`](services/event_bus.py:1) | Simple pub/sub | ✅ Keep |
| [`services/health.py`](services/health.py:1) | FastAPI health endpoints | ✅ Migrated |
| [`services/observability.py`](services/observability.py:1) | JSON logging, Prometheus metrics | ✅ Migrated |
| [`services/portfolio_risk.py`](services/portfolio_risk.py:1) | VaR, CVaR, Sharpe calculations | ✅ Keep |
| [`services/rate_limiter.py`](services/rate_limiter.py:1) | Channel rate limiting | ✅ Keep |
| [`services/regime_engine.py`](services/regime_engine.py:1) | Multi-timeframe regime classifier | ✅ Keep |
| [`services/security.py`](services/security.py:1) | ⚠️ **Mixed Flask/FastAPI** - imports `from flask import jsonify, request` | ❌ Needs cleanup |
| [`services/channels/slack.py`](services/channels/slack.py:1) | Slack notification channel | ✅ Keep |
| [`services/channels/webhook.py`](services/channels/webhook.py:1) | Generic webhook channel | ✅ Keep |
| [`backtest/engine.py`](backtest/engine.py:1) | Event-driven backtesting | ✅ Keep |
| [`templates/dashboard.html`](templates/dashboard.html:1) | Static HTML dashboard | ❌ Replace with Next.js |
| [`static/vigil.js`](static/vigil.js:1) | Vanilla JS frontend logic | ❌ Replace with React |
| [`static/vigil.css`](static/vigil.css:1) | CSS design system | ❌ Migrate to Tailwind |
| [`requirements.txt`](requirements.txt:1) | ⚠️ Mixed Flask/FastAPI deps | ❌ Needs cleanup |
| [`Procfile`](Procfile:1) | ⚠️ Uses gunicorn + separate scheduler | ❌ Needs uvicorn update |
| [`nixpacks.toml`](nixpacks.toml:1) | ⚠️ References gunicorn | ❌ Needs update |
| [`package.json`](package.json:1) | ⚠️ Minimal (only framer-motion) | ❌ Needs Next.js deps |

---

## 3. Deliverable 1: API Endpoint Migration Plan

### 3.1 Current Endpoint Inventory

All endpoints are already implemented in FastAPI. This section documents the current state and identifies gaps.

| Method | Path | Status | Response Model | Auth | Notes |
|--------|------|--------|----------------|------|-------|
| `GET` | `/alerts` | ✅ | `List[AlertResponse]` | None | Query params: `ticker`, `limit`, `offset` |
| `GET` | `/regime` | ✅ | `dict` | None | Fetches SPY data via yfinance |
| `GET` | `/stats` | ✅ | `dict` | None | System metrics from DB |
| `POST` | `/backtest/run` | ✅ | `dict` | API Key | Background task |
| `GET` | `/portfolio/risk` | ✅ | `PortfolioRiskResult` | None | Computes VaR/CVaR |
| `GET` | `/watchlist` | ✅ | `list` | None | Returns watchlist tickers |
| `POST` | `/watchlist` | ✅ | `dict` | None | Add ticker |
| `DELETE` | `/watchlist` | ✅ | `dict` | API Key | Remove ticker |
| `GET` | `/health/` | ✅ | `dict` | None | Basic health check |
| `GET` | `/health/ready` | ✅ | `dict` | None | Readiness probe |
| `GET` | `/health/live` | ✅ | `dict` | None | Liveness probe |
| `GET` | `/health/metrics` | ✅ | `text/plain` | None | Prometheus format |
| `GET` | `/health/system` | ✅ | `dict` | None | System health |

### 3.2 Missing Endpoints (From Frontend Requirements)

The current frontend ([`static/vigil.js`](static/vigil.js:445)) calls these endpoints that need to be added or verified:

| Method | Path | Status | Notes |
|--------|------|--------|-------|
| `POST` | `/trigger` | ❌ Missing | Manual detection trigger |
| `POST` | `/backfill` | ❌ Missing | Historical data backfill |
| `GET` | `/correlation` | ❌ Missing | Correlation matrix |
| `GET` | `/correlation/clusters` | ❌ Missing | Hierarchical clusters |
| `GET` | `/backtest/runs` | ❌ Missing | List backtest runs |
| `GET` | `/backtest/results/{run_id}` | ❌ Missing | Get backtest results |
| `WS` | `/ws` | ❌ Missing | WebSocket for real-time alerts |

### 3.3 Pydantic Model Enhancements

Current models in [`api.py`](api.py:29) are minimal. Enhance with:

```python
# Enhanced models to add
class DecayProfile(BaseModel):
    pct: int
    status: str  # "FRESH" | "DECAYING" | "EXPIRED"
    hours_old: float

class AlertResponse(BaseModel):
    """Already exists - add missing fields"""
    id: int
    ticker: str
    signal_type: str
    edge_score: float
    action: str
    regime: str
    decay: DecayProfile
    summary: str
    created_at: datetime
    # Missing fields to add:
    volume_ratio: Optional[float] = None
    change_pct: Optional[float] = None
    state: Optional[str] = None
    mtf_alignment: Optional[str] = None
    trap_conviction: Optional[str] = None
    outcome_pct: Optional[float] = None

class RegimeResponse(BaseModel):
    regime: str
    confidence: float
    atr_pct: float
    sma20_slope: float
    rsi: float
    timestamp: datetime

class CorrelationResponse(BaseModel):
    tickers: List[str]
    matrix: List[List[float]]
    method: str
    period: str
    computed_at: datetime

class BacktestRunResponse(BaseModel):
    id: int
    name: str
    start_date: str
    end_date: str
    tickers: List[str]
    status: str
    created_at: datetime

class BacktestResultResponse(BaseModel):
    run_id: int
    trades: List[dict]
    metrics: dict
```

### 3.4 Endpoint Implementation Plan

Add these endpoints to [`api.py`](api.py:117):

```python
# 1. Manual detection trigger
@app.post("/trigger")
async def trigger_detection(api_key: str = Depends(verify_api_key)):
    """Manually trigger market detection run."""
    def _run():
        return run_detection()
    result = await run_in_threadpool(_run)
    return {"status": "detection_complete", "result": result}

# 2. Historical backfill
@app.post("/backfill")
async def trigger_backfill(api_key: str = Depends(verify_api_key)):
    """Trigger historical data backfill."""
    def _run():
        return run_backfill()
    background_tasks.add_task(_run)
    return {"status": "backfill_started"}

# 3. Correlation matrix
@app.get("/correlation")
async def get_correlation():
    """Get latest correlation matrix."""
    result = get_latest_correlation()
    if result is None:
        raise HTTPException(status_code=404, detail="No correlation data available")
    return result

# 4. Correlation clusters
@app.get("/correlation/clusters")
async def get_correlation_clusters():
    """Get hierarchical correlation clusters."""
    from services.correlation_engine import get_correlation_engine
    # Implementation depends on stored matrix
    ...

# 5. List backtest runs
@app.get("/backtest/runs")
async def list_backtest_runs(limit: int = Query(50, le=200)):
    """List recent backtest runs."""
    return get_backtest_runs(limit=limit)

# 6. Get backtest results
@app.get("/backtest/results/{run_id}")
async def get_backtest_result(run_id: int):
    """Get detailed backtest results."""
    result = get_backtest_results(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return result

# 7. WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time alert streaming."""
    await websocket.accept()
    # Subscribe to event bus for new alerts
    ...
```

---

## 4. Deliverable 2: Database Schema & Neon PostgreSQL Optimization

### 4.1 Current Schema Review

Current tables in [`database.py`](database.py:56):

| Table | Purpose | Columns | Indexes |
|-------|---------|---------|---------|
| `alerts` | Market surveillance alerts | 31 columns (id, ticker, date, volume_ratio, change_pct, signal_type, state, edge_score, action, regime, mtf_alignment, trap_conviction, accumulation_score, summary, created_at, outcome_pct, etc.) | None defined |
| `watchlist` | Tracked tickers | id, ticker, added_at | None defined |
| `alert_deliveries` | Delivery tracking | id, alert_id, channel, status, delivered_at, error, retry_count | None defined |
| `alert_dedup` | Deduplication fingerprints | id, fingerprint, alert_id, created_at, expires_at | None defined |
| `backtest_runs` | Backtest run metadata | id, name, config, start_date, end_date, tickers, status, created_at | None defined |
| `backtest_results` | Individual trade results | id, run_id, ticker, date, action, price, quantity, pnl | None defined |
| `backtest_metrics` | Aggregate metrics | id, run_id, metric_name, metric_value | None defined |
| `correlation_matrix` | Stored correlation data | id, tickers, matrix, period, method, computed_at | None defined |

### 4.2 Neon PostgreSQL Optimizations

Neon PostgreSQL is a serverless, branchable PostgreSQL with specific characteristics:

#### 4.2.1 Connection Pooling

**Current**: `psycopg2` with `ThreadedConnectionPool` (max 10 connections)

**Problem**: Neon has connection limits on free tier (typically 50-100). Threaded pools don't work well with serverless cold starts.

**Solution**: Use `psycopg` (v3) with async connection pool or PgBouncer proxy.

```python
# database.py - New connection pool for Neon
import psycopg_pool
from contextlib import asynccontextmanager

# Connection pool managed at application level
_pool: Optional[psycopg_pool.AsyncConnectionPool] = None

async def init_pool(dsn: str, min_size: int = 2, max_size: int = 10):
    """Initialize async connection pool for Neon."""
    global _pool
    _pool = psycopg_pool.AsyncConnectionPool(
        conninfo=dsn,
        min_size=min_size,
        max_size=max_size,
        timeout=30,
        # Neon-specific: reconnect on idle timeout
        reconnect_timeout=60,
    )
    await _pool.open()

@asynccontextmanager
async def get_db_cursor():
    """Async context manager for database operations."""
    async with _pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            yield cursor
            await conn.commit()
```

#### 4.2.2 Index Strategy

Add these indexes to [`database.py`](database.py:56) `init_db()`:

```sql
-- Alerts table indexes
CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON alerts(ticker);
CREATE INDEX IF NOT EXISTS idx_alerts_signal_type ON alerts(signal_type);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_ticker_date ON alerts(ticker, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_regime ON alerts(regime);
CREATE INDEX IF NOT EXISTS idx_alerts_edge_score ON alerts(edge_score DESC);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_alerts_ticker_signal_date ON alerts(ticker, signal_type, created_at DESC);

-- Alert deliveries indexes
CREATE INDEX IF NOT EXISTS idx_deliveries_alert_id ON alert_deliveries(alert_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_channel_status ON alert_deliveries(channel, status);
CREATE INDEX IF NOT EXISTS idx_deliveries_created_at ON alert_deliveries(created_at DESC);

-- Dedup indexes
CREATE INDEX IF NOT EXISTS idx_dedup_fingerprint ON alert_dedup(fingerprint);
CREATE INDEX IF NOT EXISTS idx_dedup_expires ON alert_dedup(expires_at);

-- Backtest indexes
CREATE INDEX IF NOT EXISTS idx_backtest_runs_status ON backtest_runs(status);
CREATE INDEX IF NOT EXISTS idx_backtest_results_run_id ON backtest_results(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_metrics_run_id ON backtest_metrics(run_id);

-- Correlation indexes
CREATE INDEX IF NOT EXISTS idx_correlation_computed ON correlation_matrix(computed_at DESC);
```

#### 4.2.3 Prepared Statements

Neon benefits from prepared statements for repeated queries:

```python
# In init_db(), prepare frequently-used queries
PREPARED_QUERIES = {
    "get_alerts_by_ticker": """
        SELECT * FROM alerts 
        WHERE ticker = $1 
        ORDER BY created_at DESC 
        LIMIT $2 OFFSET $3
    """,
    "get_latest_regime": """
        SELECT regime FROM alerts 
        ORDER BY created_at DESC 
        LIMIT 1
    """,
    "get_system_metrics": """
        SELECT 
            COUNT(*) as total_alerts,
            COUNT(CASE WHEN signal_type = 'VOLUME_SPIKE_UP' THEN 1 END) as volume_spikes_up,
            COUNT(CASE WHEN signal_type = 'ACCUMULATION_DETECTED' THEN 1 END) as accumulations,
            AVG(edge_score) as avg_edge_score
        FROM alerts
    """,
}
```

#### 4.2.4 Neon-Specific Configuration

```python
# Environment variables for Neon
NEON_DATABASE_URL = os.environ.get("NEON_DATABASE_URL")  # Serverless connection string
NEON_POOL_SIZE = int(os.environ.get("NEON_POOL_SIZE", "5"))  # Conservative for free tier
NEON_POOL_TIMEOUT = int(os.environ.get("NEON_POOL_TIMEOUT", "30"))

# Neon connection string format:
# postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
```

### 4.3 Migration Script

Create `migrations/001_neon_optimization.sql`:

```sql
-- Migration: Neon PostgreSQL Optimization
-- Date: 2026-04-03
-- Description: Add indexes and optimize for Neon serverless

BEGIN;

-- Add indexes for query performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_ticker ON alerts(ticker);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_signal_type ON alerts(signal_type);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_ticker_date ON alerts(ticker, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_regime ON alerts(regime);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_edge_score ON alerts(edge_score DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_ticker_signal_date ON alerts(ticker, signal_type, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_deliveries_alert_id ON alert_deliveries(alert_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_deliveries_channel_status ON alert_deliveries(channel, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_deliveries_created_at ON alert_deliveries(created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dedup_fingerprint ON alert_dedup(fingerprint);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dedup_expires ON alert_dedup(expires_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtest_runs_status ON backtest_runs(status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtest_results_run_id ON backtest_results(run_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtest_metrics_run_id ON backtest_metrics(run_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correlation_computed ON correlation_matrix(computed_at DESC);

-- Add missing columns if they don't exist
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS outcome_pct NUMERIC(10,4);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS mtf_alignment VARCHAR(50);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS trap_conviction VARCHAR(50);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS accumulation_score NUMERIC(10,4);

-- Add indexes on new columns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_outcome_pct ON alerts(outcome_pct);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_mtf ON alerts(mtf_alignment);

COMMIT;
```

---

## 5. Deliverable 3: Next.js Frontend Architecture

### 5.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Next.js App Router                      │
├─────────────────────────────────────────────────────────────┤
│  app/                                                        │
│  ├── layout.tsx           # Root layout with providers       │
│  ├── page.tsx             # Dashboard home                    │
│  ├── alerts/              # Alert management                  │
│  │   └── page.tsx         # Alert list with filters           │
│  ├── backtest/            # Backtesting interface             │
│  │   └── page.tsx         # Backtest config & results         │
│  ├── correlation/         # Correlation analysis              │
│  │   └── page.tsx         # Matrix visualization              │
│  └── api/                 # API routes (proxy to FastAPI)     │
│      ├── alerts/          # Proxy to /alerts                  │
│      ├── regime/          # Proxy to /regime                  │
│      └── trigger/         # Proxy to /trigger                 │
├─────────────────────────────────────────────────────────────┤
│  components/                                                   │
│  ├── ui/                # Base UI components (shadcn/ui)      │
│  ├── dashboard/         # Dashboard-specific components       │
│  │   ├── RegimeStrip.tsx    # Market regime indicator         │
│  │   ├── BentoGrid.tsx      # Stats bento layout              │
│  │   ├── AlertFeed.tsx      # Real-time alert list            │
│  │   ├── AlertCard.tsx      # Individual alert card           │
│  │   ├── MTFDots.tsx        # Multi-timeframe alignment       │
│  │   ├── EdgeBreakdown.tsx  # Edge score visualization        │
│  │   └── TrapWarning.tsx    # Trap detection warning          │
│  ├── charts/            # Chart components                    │
│  │   ├── PriceChart.tsx     # Price + volume chart            │
│  │   ├── CorrelationHeatmap.tsx                                │
│  │   └── RegimeTimeline.tsx                                    │
│  └── layout/            # Layout components                   │
│      ├── Header.tsx                                           │
│      ├── Sidebar.tsx                                          │
│      └── Footer.tsx                                           │
├─────────────────────────────────────────────────────────────┤
│  lib/                                                          │
│  ├── api.ts             # FastAPI client                      │
│  ├── websocket.ts       # WebSocket connection manager        │
│  ├── types.ts           # TypeScript type definitions         │
│  └── utils.ts           # Utility functions                   │
├─────────────────────────────────────────────────────────────┤
│  hooks/                                                        │
│  ├── useAlerts.ts       # Alert data fetching                 │
│  ├── useRegime.ts       # Regime data                         │
│  ├── useWebSocket.ts    # WebSocket hook                      │
│  └── useDecay.ts        # Signal decay tracking               │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 TypeScript Type Definitions

Create `lib/types.ts`:

```typescript
// Aligned with FastAPI Pydantic models

export interface DecayProfile {
  pct: number;
  status: "FRESH" | "DECAYING" | "EXPIRED";
  hours_old: number;
}

export interface Alert {
  id: number;
  ticker: string;
  signal_type: "VOLUME_SPIKE_UP" | "VOLUME_SPIKE_DOWN" | "ACCUMULATION_DETECTED";
  edge_score: number;
  action: string;
  regime: string;
  decay: DecayProfile;
  summary: string;
  created_at: string;
  volume_ratio?: number;
  change_pct?: number;
  state?: string;
  mtf_alignment?: string;
  trap_conviction?: string;
  outcome_pct?: number;
}

export interface RegimeResponse {
  regime: "TRENDING" | "RISK_OFF" | "SIDEWAYS" | "VOLATILE" | "TRANSITION";
  confidence: number;
  atr_pct: number;
  sma20_slope: number;
  rsi: number;
  timestamp: string;
}

export interface SystemStats {
  total_alerts: number;
  volume_spikes_up: number;
  volume_spikes_down: number;
  accumulations: number;
  avg_edge_score: number;
  last_detection: string;
}

export interface CorrelationMatrix {
  tickers: string[];
  matrix: number[][];
  method: string;
  period: string;
  computed_at: string;
}

export interface BacktestRun {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  tickers: string[];
  status: string;
  created_at: string;
}

export interface BacktestResult {
  run_id: number;
  trades: Trade[];
  metrics: BacktestMetrics;
}

export interface Trade {
  ticker: string;
  date: string;
  action: "BUY" | "SELL";
  price: number;
  quantity: number;
  pnl: number;
}

export interface BacktestMetrics {
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
}
```

### 5.3 API Client

Create `lib/api.ts`:

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-KEY": process.env.NEXT_PUBLIC_API_KEY || "",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export const api = {
  alerts: {
    list: (params?: { ticker?: string; limit?: number; offset?: number }) =>
      fetchAPI<Alert[]>(`/alerts?${new URLSearchParams(params as any)}`),
  },
  regime: {
    get: () => fetchAPI<RegimeResponse>("/regime"),
  },
  stats: {
    get: () => fetchAPI<SystemStats>("/stats"),
  },
  correlation: {
    get: () => fetchAPI<CorrelationMatrix>("/correlation"),
  },
  backtest: {
    list: (limit = 50) => fetchAPI<BacktestRun[]>(`/backtest/runs?limit=${limit}`),
    results: (runId: number) => fetchAPI<BacktestResult>(`/backtest/results/${runId}`),
    run: (config: { name?: string; start_date: string; end_date: string; tickers: string[]; capital?: number }) =>
      fetchAPI<{ status: string; name: string }>("/backtest/run", {
        method: "POST",
        body: JSON.stringify(config),
      }),
  },
  watchlist: {
    list: () => fetchAPI<string[]>("/watchlist"),
    add: (ticker: string) =>
      fetchAPI<{ status: string; added: string }>("/watchlist", {
        method: "POST",
        body: JSON.stringify({ ticker }),
      }),
    remove: (ticker: string) =>
      fetchAPI<{ status: string; ticker: string }>(`/watchlist?ticker=${ticker}`, {
        method: "DELETE",
      }),
  },
  trigger: {
    detection: () =>
      fetchAPI<{ status: string }>("/trigger", { method: "POST" }),
  },
};
```

### 5.4 WebSocket Manager

Create `lib/websocket.ts`:

```typescript
export class AlertWebSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private listeners: ((alert: Alert) => void)[] = [];

  constructor(url: string) {
    this.connect(url);
  }

  private connect(url: string) {
    this.ws = new WebSocket(url);

    this.ws.onmessage = (event) => {
      const alert = JSON.parse(event.data);
      this.listeners.forEach((fn) => fn(alert));
    };

    this.ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(url), 5000);
    };
  }

  onAlert(fn: (alert: Alert) => void) {
    this.listeners.push(fn);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== fn);
    };
  }

  disconnect() {
    this.ws?.close();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
  }
}
```

### 5.5 Key Component: AlertCard

Create `components/dashboard/AlertCard.tsx`:

```tsx
"use client";

import { Alert, DecayProfile } from "@/lib/types";
import { motion, AnimatePresence } from "framer-motion";

interface AlertCardProps {
  alert: Alert;
  expanded?: boolean;
  onToggle?: () => void;
}

const SIGNAL_COLORS: Record<string, string> = {
  VOLUME_SPIKE_UP: "text-emerald-400",
  VOLUME_SPIKE_DOWN: "text-red-400",
  ACCUMULATION_DETECTED: "text-amber-400",
};

const REGIME_COLORS: Record<string, string> = {
  TRENDING: "text-blue-400",
  RISK_OFF: "text-red-400",
  SIDEWAYS: "text-gray-400",
  VOLATILE: "text-purple-400",
  TRANSITION: "text-yellow-400",
};

function DecayBadge({ decay }: { decay: DecayProfile }) {
  const color = decay.status === "FRESH" ? "bg-emerald-500/20 text-emerald-400" 
    : decay.status === "DECAYING" ? "bg-amber-500/20 text-amber-400" 
    : "bg-gray-500/20 text-gray-400";

  return (
    <span className={`px-2 py-0.5 text-xs rounded-full ${color}`}>
      {decay.status} ({decay.hours_old}h)
    </span>
  );
}

export function AlertCard({ alert, expanded = false, onToggle }: AlertCardProps) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 cursor-pointer hover:border-gray-700 transition-colors"
      onClick={onToggle}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono font-bold text-lg">{alert.ticker}</span>
          <span className={`text-sm ${SIGNAL_COLORS[alert.signal_type]}`}>
            {alert.signal_type}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <DecayBadge decay={alert.decay} />
          <span className={`text-sm ${REGIME_COLORS[alert.regime]}`}>
            {alert.regime}
          </span>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-3 pt-3 border-t border-gray-800"
          >
            <p className="text-sm text-gray-400">{alert.summary}</p>
            <div className="grid grid-cols-3 gap-4 mt-3">
              <div>
                <span className="text-xs text-gray-500">Edge Score</span>
                <p className="font-mono">{alert.edge_score.toFixed(1)}</p>
              </div>
              {alert.volume_ratio && (
                <div>
                  <span className="text-xs text-gray-500">Volume Ratio</span>
                  <p className="font-mono">{alert.volume_ratio.toFixed(2)}x</p>
                </div>
              )}
              {alert.outcome_pct !== null && (
                <div>
                  <span className="text-xs text-gray-500">Outcome</span>
                  <p className={`font-mono ${alert.outcome_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {alert.outcome_pct >= 0 ? "+" : ""}{alert.outcome_pct?.toFixed(2)}%
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
```

### 5.6 Tailwind CSS Configuration

Create `tailwind.config.ts`:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Vigil dark theme (from static/vigil.css)
        vigil: {
          bg: "#0a0a0f",
          surface: "#12121a",
          border: "#1e1e2e",
          text: "#e0e0e8",
          muted: "#6b7280",
          accent: "#3b82f6",
          success: "#10b981",
          warning: "#f59e0b",
          danger: "#ef4444",
        },
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "blob-float": "blob-float 7s infinite",
      },
      keyframes: {
        "blob-float": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "33%": { transform: "translate(30px, -50px) scale(1.1)" },
          "66%": { transform: "translate(-20px, 20px) scale(0.9)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
```

### 5.7 package.json Dependencies

Update `package.json`:

```json
{
  "name": "vigil-dashboard",
  "version": "2.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^14.1.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "framer-motion": "^11.0.0",
    "recharts": "^2.12.0",
    "date-fns": "^3.3.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^8.56.0",
    "eslint-config-next": "^14.1.0"
  }
}
```

---

## 6. Deliverable 4: Scheduler Migration & Cleanup

### 6.1 Current State

| File | Scheduler Type | Status |
|------|---------------|--------|
| [`api.py`](api.py:70) | `AsyncIOScheduler` (in-process) | ✅ Active |
| [`scheduler.py`](scheduler.py:1) | `BlockingScheduler` (standalone) | ❌ Deprecated |

### 6.2 Migration Plan

**The AsyncIOScheduler is already implemented in [`api.py`](api.py:70).** The legacy `scheduler.py` file and its Procfile entry need to be removed.

#### Step 1: Verify AsyncIOScheduler Configuration

Current configuration in [`api.py`](api.py:72):

```python
@app.on_event("startup")
async def start_scheduler():
    await run_in_threadpool(init_db)
    scheduler.add_job(run_detection, "cron", hour=21, minute=0, timezone="America/New_York")
    scheduler.add_job(system_stats, "interval", minutes=10)
    scheduler.start()
```

**Issues to fix**:
1. `system_stats` is an endpoint function, not a scheduler job. Replace with a keep-warm function.
2. Missing shutdown handler for graceful cleanup.
3. Missing error handling for job execution.

#### Step 2: Enhanced Scheduler Configuration

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED
from apscheduler.jobstores.memory import MemoryJobStore

scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 3600,  # 1 hour grace period for free-tier spin-down
    },
)

def job_listener(event):
    """Log job execution events."""
    if event.exception:
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    elif event.retval:
        logger.info(f"Job {event.job_id} completed: {event.retval}")

scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_MISSED)

@app.on_event("startup")
async def start_scheduler():
    await run_in_threadpool(init_db)
    
    # Main market scan (daily at 9 PM ET)
    scheduler.add_job(
        run_detection,
        "cron",
        hour=21,
        minute=0,
        timezone="America/New_York",
        id="daily_detection",
        name="Daily Market Detection",
    )
    
    # Keep-warm heartbeat (every 10 minutes)
    scheduler.add_job(
        lambda: logger.info("Keep-warm heartbeat"),
        "interval",
        minutes=10,
        id="keep_warm",
        name="Keep-Warm Heartbeat",
    )
    
    # Outcome evaluation (every 6 hours)
    from data import evaluate_outcomes
    scheduler.add_job(
        lambda: run_in_threadpool(evaluate_outcomes),
        "interval",
        hours=6,
        id="outcome_eval",
        name="Outcome Evaluation",
    )
    
    scheduler.start()
    logger.info("Scheduler started")

@app.on_event("shutdown")
async def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
```

#### Step 3: Remove Legacy Files

```bash
# Files to delete
rm scheduler.py

# Update Procfile (see Section 8)
```

### 6.3 Distributed Locking for Multi-Instance

If running multiple instances, use the existing [`services/distributed_lock.py`](services/distributed_lock.py:1):

```python
from services.distributed_lock import get_detection_lock

async def run_detection_if_leader():
    """Run detection only if this instance holds the lock."""
    lock = get_detection_lock(timeout=3600)
    try:
        with lock(blocking=False):
            return run_detection()
    except RuntimeError:
        logger.info("Another instance is running detection, skipping")
        return None
```

---

## 7. Deliverable 5: Observability Completion Plan

### 7.1 Current State

| Component | File | Status |
|-----------|------|--------|
| JSON Logging | [`services/observability.py`](services/observability.py:26) | ✅ Implemented |
| Metrics Collector | [`services/observability.py`](services/observability.py:62) | ✅ In-memory |
| Metrics Middleware | [`services/observability.py`](services/observability.py:152) | ✅ FastAPI middleware |
| Anomaly Detector | [`services/observability.py`](services/observability.py:174) | ✅ Implemented |
| Health Endpoints | [`services/health.py`](services/health.py:1) | ✅ Implemented |

### 7.2 Gaps to Address

#### 7.2.1 Prometheus Metrics Export

Current `prometheus_format()` in [`services/observability.py`](services/observability.py:117) outputs text format. Enhance with:

```python
# Add to MetricsCollector
def prometheus_format(self) -> str:
    """Output metrics in Prometheus exposition format."""
    lines = []
    
    # Request count
    lines.append("# HELP http_requests_total Total HTTP requests")
    lines.append("# TYPE http_requests_total counter")
    for key, count in self.request_count.items():
        lines.append(f'http_requests_total{{method="{key[0]}",endpoint="{key[1]}",status="{key[2]}"}} {count}')
    
    # Latency histogram
    lines.append("# HELP http_request_duration_seconds Request latency")
    lines.append("# TYPE http_request_duration_seconds histogram")
    for key, latencies in self.latencies.items():
        if latencies:
            avg = sum(latencies) / len(latencies)
            lines.append(f'http_request_duration_seconds_sum{{method="{key[0]}",endpoint="{key[1]}"}} {sum(latencies):.4f}')
            lines.append(f'http_request_duration_seconds_count{{method="{key[0]}",endpoint="{key[1]}"}} {len(latencies)}')
    
    # Active requests gauge
    lines.append("# HELP http_requests_active Currently active requests")
    lines.append("# TYPE http_requests_active gauge")
    lines.append(f"http_requests_active {self.active_requests}")
    
    # Error rate
    lines.append("# HELP http_errors_total Total HTTP errors")
    lines.append("# TYPE http_errors_total counter")
    lines.append(f"http_errors_total {self.error_count}")
    
    return "\n".join(lines) + "\n"
```

#### 7.2.2 Structured Log Enhancement

Current [`JSONFormatter`](services/observability.py:26) is good. Add request ID correlation:

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

# Add to api.py
app.add_middleware(RequestIDMiddleware)

# Update JSONFormatter to include request_id
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request ID if available
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        # Add exception info
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)
```

#### 7.2.3 Alert-Specific Metrics

Add trading-specific metrics:

```python
class TradingMetricsCollector:
    """Collect trading-specific metrics."""
    
    def __init__(self):
        self.alerts_by_type: Counter[str] = Counter()
        self.alerts_by_regime: Counter[str] = Counter()
        self.edge_scores: list[float] = []
        self.outcome_pcts: list[float] = []
    
    def record_alert(self, signal_type: str, regime: str, edge_score: float):
        self.alerts_by_type[signal_type] += 1
        self.alerts_by_regime[regime] += 1
        self.edge_scores.append(edge_score)
    
    def record_outcome(self, outcome_pct: float):
        self.outcome_pcts.append(outcome_pct)
    
    def get_win_rate(self) -> float:
        if not self.outcome_pcts:
            return 0.0
        wins = sum(1 for p in self.outcome_pcts if p > 0)
        return wins / len(self.outcome_pcts)
    
    def get_avg_edge_score(self) -> float:
        if not self.edge_scores:
            return 0.0
        return sum(self.edge_scores) / len(self.edge_scores)
```

### 7.4 Monitoring Dashboard

Recommended Grafana panels:

1. **Request Rate**: `rate(http_requests_total[5m])`
2. **Latency P95**: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
3. **Error Rate**: `rate(http_errors_total[5m]) / rate(http_requests_total[5m])`
4. **Active Alerts**: `alert_count` gauge
5. **Detection Freshness**: `time() - last_detection_timestamp`
6. **Win Rate**: `win_rate` from trading metrics

---

## 8. Deliverable 6: Deployment Configuration

### 8.1 Updated Procfile

**Current**:
```
web: gunicorn --bind 0.0.0.0:$PORT --worker-class gevent --workers 1 --worker-connections 1000 --timeout 120 --access-logfile - api:app
scheduler: python scheduler.py
```

**Updated**:
```
web: uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1 --loop uvloop --http httptools --log-level info
```

**Changes**:
- Replaced `gunicorn` + `gevent` with `uvicorn`
- Removed `scheduler` process (now in-process via AsyncIOScheduler)
- Added `uvloop` and `httptools` for performance
- Single worker (free-tier optimization)

### 8.2 Updated nixpacks.toml

**Current**:
```toml
[phases.setup]
nixPkgs = ["python311"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "gunicorn --bind 0.0.0.0:$PORT --worker-class gevent --workers 1 api:app"
```

**Updated**:
```toml
[phases.setup]
nixPkgs = ["python311", "nodejs_20"]

[phases.install]
cmds = [
  "pip install -r requirements.txt",
  "npm install"
]

[phases.build]
cmds = ["npm run build"]

[start]
cmd = "uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1 --loop uvloop"
```

### 8.3 Updated requirements.txt

**Current** (with Flask deps):
```
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.6.0
flask>=3.0.0
flask-socketio>=5.3.0
flask-limiter>=3.5.0
...
gunicorn>=21.2.0
gevent>=23.9.0
gevent-websocket>=0.10.1
eventlet>=0.35.0
```

**Updated** (clean):
```
# Core Web Framework
fastapi>=0.109.0
uvicorn[standard]>=0.27.0  # Includes uvloop, httptools
pydantic>=2.6.0

# Quant & Data Science
yfinance>=0.2.36
numpy>=1.24.0
pandas>=2.0.0
PyYAML>=6.0.1

# Database & Infrastructure
psycopg2-binary>=2.9.0
apscheduler>=3.10.0
redis>=5.0.0
psutil>=5.9.0
python-dotenv>=1.0.0

# Security & Validation
pyjwt>=2.8.0

# Remove: flask, flask-socketio, flask-limiter, gunicorn, gevent, gevent-websocket, eventlet
# Remove: marshmallow (replaced by Pydantic)
```

### 8.4 Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/vigil
NEON_DATABASE_URL=postgresql://user:password@ep-xxx.region.aws.neon.tech/vigil?sslmode=require

# Security
VIGIL_API_KEY=your-api-key-here
JWT_SECRET=your-jwt-secret-here
ALLOWED_ORIGINS=https://your-domain.com,http://localhost:3000

# Redis (optional, for caching and distributed locking)
REDIS_URL=redis://localhost:6379/0

# Application
PORT=8000
LOG_LEVEL=info
ENVIRONMENT=production

# Next.js (frontend)
NEXT_PUBLIC_API_URL=https://api.your-domain.com
NEXT_PUBLIC_API_KEY=your-api-key-here
```

### 8.5 Docker Configuration (Optional)

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

---

## 9. Deliverable 7: Risk Assessment & Breaking Changes

### 9.1 Breaking Changes Analysis

| Change | Impact | Risk Level | Mitigation |
|--------|--------|------------|------------|
| Remove `scheduler.py` process | High if Procfile not updated | 🔴 High | Update Procfile before deploying |
| Remove Flask dependencies | None (not used by FastAPI routes) | 🟢 Low | Test after removal |
| Remove `marshmallow` validation | Medium if external clients use old decorators | 🟡 Medium | Replace with Pydantic validation |
| Change from gunicorn to uvicorn | Low (same WSGI/ASGI interface) | 🟢 Low | Load test before deploy |
| Database index additions | None (concurrent creation) | 🟢 Low | Use `CREATE INDEX CONCURRENTLY` |
| Remove `flask-socketio` | High if WebSocket clients depend on it | 🔴 High | Implement WebSocket endpoint before removal |
| Next.js replaces static HTML | High for existing users | 🔴 High | Deploy Next.js alongside static HTML first |

### 9.2 Alert Workflow Risk Assessment

**Current Alert Flow**:
```
run_detection() → save_alert() → WebSocket push → alert_router.dispatch() → notify_webhook()
```

**Risk Points**:
1. **WebSocket removal**: If `flask-socketio` is removed before WebSocket endpoint is implemented, real-time alerts will break.
   - **Mitigation**: Implement FastAPI WebSocket endpoint before removing Flask-SocketIO.

2. **Alert dispatch timing**: AsyncIOScheduler runs in the same process. If the web process restarts, scheduled jobs may be delayed.
   - **Mitigation**: Use `misfire_grace_time` and distributed locking.

3. **Database connection pool**: Neon serverless may have cold starts. Connection pool initialization must handle this.
   - **Mitigation**: Use connection pool with reconnect logic and health checks.

### 9.3 Data Integrity Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Duplicate alerts during migration | Medium | Low | Deduplication store already exists |
| Lost alerts during deployment | High | Low | Queue alerts in memory during restart |
| Corrupted correlation matrix | Low | Low | Atomic writes with transactions |
| Backtest data loss | Medium | Low | Persist results before returning |

### 9.4 Rollback Plan

If migration causes issues:

1. **Immediate rollback**: Revert to previous git commit
2. **Database rollback**: Index additions are safe to keep; no schema changes are destructive
3. **Frontend rollback**: Keep `templates/dashboard.html` and `static/` as fallback
4. **Scheduler rollback**: Restore `scheduler.py` and Procfile entry

### 9.5 Monitoring During Migration

Key metrics to watch:
- Alert generation rate (should remain consistent)
- Alert delivery success rate (should be >99%)
- API response latency (should not increase)
- Error rate (should remain <1%)
- Scheduler job execution (should run on schedule)

---

## 10. Deliverable 8: Implementation Timeline

### Phase 1: Cleanup & Consolidation (Week 1)

| Task | Files | Priority |
|------|-------|----------|
| Remove Flask dependencies from requirements.txt | `requirements.txt` | P0 |
| Update Procfile to use uvicorn | `Procfile` | P0 |
| Update nixpacks.toml | `nixpacks.toml` | P0 |
| Remove legacy scheduler.py | `scheduler.py` | P0 |
| Clean up services/security.py (remove Flask imports) | `services/security.py` | P1 |
| Add shutdown handler to AsyncIOScheduler | `api.py` | P1 |
| Add missing endpoints (/trigger, /backfill, /correlation) | `api.py` | P1 |

### Phase 2: Database Optimization (Week 2)

| Task | Files | Priority |
|------|-------|----------|
| Create migration script for indexes | `migrations/001_neon_optimization.sql` | P0 |
| Update database.py connection pool for Neon | `database.py` | P0 |
| Add prepared statements for frequent queries | `database.py` | P1 |
| Test with Neon PostgreSQL | - | P0 |
| Add connection health checks | `services/health.py` | P1 |

### Phase 3: Observability Hardening (Week 3)

| Task | Files | Priority |
|------|-------|----------|
| Add request ID middleware | `api.py`, `services/observability.py` | P1 |
| Enhance Prometheus metrics export | `services/observability.py` | P1 |
| Add trading-specific metrics | `services/observability.py` | P2 |
| Set up Grafana dashboard | - | P2 |
| Add anomaly detection alerts | `services/observability.py` | P2 |

### Phase 4: Next.js Frontend (Weeks 4-8)

| Task | Files | Priority |
|------|-------|----------|
| Initialize Next.js project | `app/`, `components/`, `lib/` | P0 |
| Create TypeScript type definitions | `lib/types.ts` | P0 |
| Build API client | `lib/api.ts` | P0 |
| Implement core components | `components/dashboard/` | P0 |
| Migrate CSS to Tailwind | `tailwind.config.ts` | P0 |
| Implement WebSocket client | `lib/websocket.ts` | P1 |
| Build backtest UI | `app/backtest/` | P1 |
| Build correlation UI | `app/correlation/` | P2 |
| Add charts (Recharts) | `components/charts/` | P1 |
| Deploy alongside static HTML | - | P0 |
| Switch default to Next.js | - | P0 |
| Remove static HTML | `templates/`, `static/` | P2 |

### Phase 5: Production Readiness (Week 9)

| Task | Files | Priority |
|------|-------|----------|
| Load testing | - | P0 |
| Security audit | - | P0 |
| Documentation update | `README.md` | P1 |
| Monitoring setup | - | P1 |
| Runbook creation | - | P1 |

---

## Appendix A: File Change Summary

| File | Action | Reason |
|------|--------|--------|
| `api.py` | Modify | Add missing endpoints, enhance scheduler |
| `database.py` | Modify | Neon connection pool, prepared statements |
| `scheduler.py` | **Delete** | Replaced by AsyncIOScheduler in api.py |
| `requirements.txt` | Modify | Remove Flask deps, add uvicorn[standard] |
| `Procfile` | Modify | Switch to uvicorn |
| `nixpacks.toml` | Modify | Update build/start commands |
| `services/security.py` | Modify | Remove Flask imports |
| `services/observability.py` | Modify | Add request ID, enhance metrics |
| `templates/dashboard.html` | **Delete** (Phase 4) | Replaced by Next.js |
| `static/vigil.js` | **Delete** (Phase 4) | Replaced by React components |
| `static/vigil.css` | **Delete** (Phase 4) | Replaced by Tailwind |
| `package.json` | Modify | Add Next.js dependencies |
| `migrations/001_neon_optimization.sql` | **Create** | Database indexes |
| `app/` | **Create** | Next.js app directory |
| `components/` | **Create** | React components |
| `lib/` | **Create** | TypeScript utilities |
| `hooks/` | **Create** | React hooks |
| `tailwind.config.ts` | **Create** | Tailwind configuration |

---

## Appendix B: Architecture Diagram

```mermaid
graph TB
    subgraph Frontend
        NextJS[Next.js 14 App Router]
        React[React Components]
        Tailwind[Tailwind CSS]
        WS_Client[WebSocket Client]
    end

    subgraph Backend
        FastAPI[FastAPI App]
        Uvicorn[Uvicorn ASGI Server]
        Scheduler[AsyncIOScheduler]
        Middleware[Metrics Middleware]
    end

    subgraph Services
        Regime[Regime Engine]
        Correlation[Correlation Engine]
        PortfolioRisk[Portfolio Risk]
        AlertRouter[Alert Router]
        Dedup[Dedup Store]
        Cache[Redis Cache]
        DistLock[Distributed Lock]
    end

    subgraph Data
        Neon[(Neon PostgreSQL)]
        Redis[(Redis)]
        YFinance[yfinance]
    end

    subgraph Observability
        JSONLog[JSON Logging]
        Prometheus[Prometheus Metrics]
        Health[Health Checks]
    end

    NextJS --> FastAPI
    WS_Client --> FastAPI
    FastAPI --> Uvicorn
    FastAPI --> Scheduler
    FastAPI --> Middleware
    FastAPI --> Regime
    FastAPI --> Correlation
    FastAPI --> PortfolioRisk
    FastAPI --> AlertRouter
    AlertRouter --> Dedup
    AlertRouter --> Cache
    Scheduler --> DistLock
    Regime --> YFinance
    Correlation --> YFinance
    FastAPI --> Neon
    Cache --> Redis
    Middleware --> Prometheus
    FastAPI --> JSONLog
    FastAPI --> Health
```

---

## Appendix C: Quick Reference Commands

```bash
# Development
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1 --loop uvloop

# Next.js development
npm run dev

# Next.js production build
npm run build && npm start

# Database migration
psql $DATABASE_URL -f migrations/001_neon_optimization.sql

# Health check
curl http://localhost:8000/health/ready

# Prometheus metrics
curl http://localhost:8000/health/metrics
```

---

*End of Architecture Migration Plan*
