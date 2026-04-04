# Polling Migration Plan

## Overview

Migrate Vigil from real-time WebSocket + APScheduler architecture to a cost-efficient polling-based architecture using feature flags, without deleting existing real-time code.

---

## 1. Current Architecture Summary

### Backend (`backend/api.py`)
- **Framework**: FastAPI with `uvicorn`
- **Scheduler**: `AsyncIOScheduler` (APScheduler) started on `startup_event()` at line 148-180
  - Job 1: `run_detection` — daily cron at 21:00 ET (line 168-174)
  - Job 2: `_get_system_stats` — keep-warm heartbeat every 10 minutes (line 178)
- **WebSocket**: `/ws` endpoint at line 221-269
  - Uses `WebSocketManager` singleton from `services/ws_manager.py`
  - Subscribes to `event_bus` for `alert`, `signal`, `regime_change` events
  - Max connections: 10 (env `WS_MAX_CONNECTIONS`)
  - Heartbeat interval: 30s (env `WS_HEARTBEAT_INTERVAL`)
- **Event Bus**: `services/event_bus.py` — simple pub/sub with synchronous callbacks
- **Existing endpoints**:
  - `GET /alerts` — fetch alerts with decay enrichment (line 274-306)
  - `POST /trigger` — manual detection trigger (line 433-444)
  - `POST /backfill` — manual backfill trigger (line 447-458)
  - `GET /stats`, `GET /regime`, `GET /watchlist`, etc.

### Frontend (`frontend/components/Dashboard.tsx`)
- **Current behavior**: Polls every 30 seconds via `setInterval` (line 10, 37)
- **No active WebSocket usage** in the current frontend — the WebSocket endpoint exists on the backend but the frontend does not connect to it
- **Components**: `Dashboard.tsx`, `SignalCard.tsx`, `AlertCard.tsx`, `FreshnessBar.tsx`, `MetricsPanel.tsx`
- **API client**: `frontend/lib/api.ts` — typed fetch wrapper

### Key Insight
The frontend is **already polling-based** (30s interval). The WebSocket code exists on the backend but is not actively consumed by the current frontend. This means the migration is primarily about:
1. Adding feature flags to conditionally disable WebSocket and scheduler
2. Adding a `since` parameter to the alerts endpoint for efficient delta polling
3. Reducing the polling interval from 30s to ~15s
4. Ensuring the `/trigger` endpoint works correctly for manual/on-demand detection

---

## 2. Target Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Dashboard.tsx                                        │   │
│  │  - Polls GET /alerts?since=<ts> every 15s            │   │
│  │  - Polls GET /stats every 60s                        │   │
│  │  - Manual trigger via POST /trigger (optional)       │   │
│  │  - Feature flag: NEXT_PUBLIC_POLLING_MODE=true       │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP REST
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                        Backend (FastAPI)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Feature Flags (env vars)                             │   │
│  │  - REALTIME_ENABLED=false  → skip WS setup           │   │
│  │  - SCHEDULER_ENABLED=false → skip APScheduler jobs   │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  GET /alerts?since=<iso_timestamp>                    │   │
│  │  - Returns only alerts created after `since`         │   │
│  │  - Falls back to full list if `since` is missing     │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  POST /trigger (existing, enhanced)                   │   │
│  │  - Triggers run_detection in background              │   │
│  │  - Returns job status + last_run timestamp           │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  GET /health/polling-status                          │   │
│  │  - Returns feature flag state + last detection run   │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  PostgreSQL (Neon)   │
              │  - alerts table      │
              │  - watchlist table   │
              └──────────────────────┘
```

---

## 3. Feature Flag Design

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REALTIME_ENABLED` | `bool` | `true` | When `false`, skip WebSocket endpoint registration and event bus subscriptions |
| `SCHEDULER_ENABLED` | `bool` | `true` | When `false`, skip APScheduler initialization and all scheduled jobs |
| `POLLING_MODE` | `bool` | `false` | When `true`, enables polling-optimized behavior (e.g., `since` parameter enforcement) |

### Frontend Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `NEXT_PUBLIC_POLLING_MODE` | `bool` | `false` | When `true`, frontend uses polling instead of WebSocket |
| `NEXT_PUBLIC_POLL_INTERVAL_MS` | `number` | `15000` | Polling interval in milliseconds |

### Feature Flag Helper (Backend)

Create `backend/services/feature_flags.py`:

```python
import os

def is_realtime_enabled() -> bool:
    return os.environ.get("REALTIME_ENABLED", "true").lower() != "false"

def is_scheduler_enabled() -> bool:
    return os.environ.get("SCHEDULER_ENABLED", "true").lower() != "false"

def is_polling_mode() -> bool:
    return os.environ.get("POLLING_MODE", "false").lower() == "true"
```

---

## 4. Detailed Step-by-Step Implementation Plan

### Step 1: Create Feature Flag Module

**File**: `backend/services/feature_flags.py` (NEW)

```python
"""
Vigil Feature Flags — Control real-time vs polling behavior via environment variables.
"""
import os


def is_realtime_enabled() -> bool:
    """When False, WebSocket endpoint and event bus subscriptions are skipped."""
    return os.environ.get("REALTIME_ENABLED", "true").lower() != "false"


def is_scheduler_enabled() -> bool:
    """When False, APScheduler is not started and no scheduled jobs run."""
    return os.environ.get("SCHEDULER_ENABLED", "true").lower() != "false"


def is_polling_mode() -> bool:
    """When True, enables polling-optimized behavior."""
    return os.environ.get("POLLING_MODE", "false").lower() == "true"
```

**File**: `backend/services/__init__.py` — no changes needed

---

### Step 2: Modify `backend/api.py` — Conditional WebSocket + Scheduler

#### 2a. Add feature flag imports

**Location**: Line 41 (after existing imports)

Add:
```python
from services.feature_flags import is_realtime_enabled, is_scheduler_enabled, is_polling_mode
```

#### 2b. Conditionally register WebSocket endpoint

**Location**: Lines 219-269 (`@app.websocket("/ws")`)

Wrap the entire WebSocket endpoint registration in a conditional:

```python
# --- WebSocket Endpoint (conditionally registered) ---

if is_realtime_enabled():
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        # ... existing code unchanged ...
```

**Alternative (cleaner)**: Keep the endpoint always registered but have it immediately close with a descriptive message when `REALTIME_ENABLED=false`:

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint — disabled when REALTIME_ENABLED=false."""
    if not is_realtime_enabled():
        await websocket.accept()
        await websocket.close(code=1008, reason="Real-time WebSocket is disabled (polling mode active)")
        return
    # ... existing code unchanged ...
```

This approach is preferred because:
- The endpoint still exists (no 404 errors for clients that try to connect)
- Clients get a clean close with a reason code
- No conditional decorator complexity with FastAPI

#### 2c. Conditionally start scheduler

**Location**: Lines 151-180 (`startup_event()`)

Modify the `startup_event()` function:

```python
@app.on_event("startup")
async def startup_event():
    """
    Initializes database infrastructure, connection pool, and starts background tasks.
    Scheduler and WebSocket are conditionally started based on feature flags.
    """
    # Initialize legacy psycopg2 tables (backward compatibility)
    await run_in_threadpool(init_db)

    # Initialize asyncpg connection pool for Neon PostgreSQL
    try:
        await get_pool()
        logger.info("Neon asyncpg connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize asyncpg pool: {e}")

    # Conditionally start scheduler
    if is_scheduler_enabled():
        # 1. Main Market Scan (distributed lock prevents duplicate runs across instances)
        scheduler.add_job(
            with_distributed_lock("detection", ttl=600)(run_detection),
            "cron",
            hour=21,
            minute=0,
            timezone="America/New_York",
        )

        # 2. Keep-Warm Heartbeat (Pings every 10 mins to prevent Render/Neon sleep)
        scheduler.add_job(_get_system_stats, "interval", minutes=10)

        scheduler.start()
        logger.info("APScheduler started (scheduled jobs active)")
    else:
        logger.info("APScheduler disabled (SCHEDULER_ENABLED=false) — use POST /trigger for manual detection")

    # Log feature flag state
    logger.info(
        f"Feature flags: REALTIME_ENABLED={is_realtime_enabled()}, "
        f"SCHEDULER_ENABLED={is_scheduler_enabled()}, "
        f"POLLING_MODE={is_polling_mode()}"
    )
```

#### 2d. Add `since` parameter to `GET /alerts`

**Location**: Lines 274-306 (`fetch_alerts()`)

Modify the endpoint signature and logic:

```python
@app.get("/alerts", response_model=List[AlertResponse])
async def fetch_alerts(
    ticker: Optional[str] = None,
    since: Optional[str] = Query(None, description="ISO 8601 timestamp — only return alerts created after this time"),
    limit: int = Query(50, gt=0, le=500),
    offset: int = 0
):
    """Fetch and enrich alerts with decay logic. Supports incremental polling via `since` parameter."""
    raw_data = get_alerts(ticker=ticker, limit=limit, offset=offset, since=since)
    
    # ... existing enrichment logic unchanged ...
```

#### 2e. Add polling status endpoint

**Location**: After line 329 (after `/stats` endpoint)

Add new endpoint:

```python
@app.get("/health/polling-status")
async def polling_status():
    """
    Returns feature flag state and last detection run info for polling clients.
    """
    from database import get_latest_regime
    # Get the most recent alert to determine last scan time
    recent_alerts = get_alerts(limit=1)
    last_run = recent_alerts[0]['created_at'].isoformat() if recent_alerts else None
    
    return {
        "realtime_enabled": is_realtime_enabled(),
        "scheduler_enabled": is_scheduler_enabled(),
        "polling_mode": is_polling_mode(),
        "last_detection_run": last_run,
        "regime": get_latest_regime(),
    }
```

#### 2f. Enhance `POST /trigger` response

**Location**: Lines 433-444

Modify to return more useful information:

```python
@app.post("/trigger")
async def trigger_detection(
    req: Optional[TriggerRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    api_key: str = Depends(verify_api_key),
):
    """
    Manual signal trigger endpoint.
    Triggers the market detection run immediately.
    """
    if not is_scheduler_enabled():
        logger.info("Manual detection triggered (scheduler disabled)")
    
    background_tasks.add_task(run_detection)
    
    # Get current time as the "trigger" timestamp for polling clients
    from datetime import datetime, timezone
    trigger_time = datetime.now(timezone.utc).isoformat()
    
    return {
        "status": "detection_triggered",
        "message": "Detection run scheduled",
        "triggered_at": trigger_time,
        "poll_after_seconds": 30,  # Suggest when client should poll for results
    }
```

---

### Step 3: Modify `backend/database.py` — Add `since` Filter

**Location**: Lines 485-510 (`get_alerts()`)

Add `since` parameter support:

```python
def get_alerts(ticker=None, signal_type=None, state=None, since=None, limit=50, offset=0):
    with get_db_cursor() as cursor:
        query = """
            SELECT *
            FROM alerts
        """
        params = []
        filters = []
        if ticker:
            filters.append("ticker = %s")
            params.append(ticker.upper())
        if signal_type:
            filters.append("signal_type = %s")
            params.append(signal_type.upper())
        if state:
            filters.append("state = %s")
            params.append(state.upper())
        if since:
            # Support both ISO 8601 string and datetime object
            filters.append("created_at > %s")
            params.append(since)

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += " ORDER BY date DESC, created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        return cursor.fetchall()
```

---

### Step 4: Update `.env.example`

**Location**: End of file

Add:

```
# --- Feature Flags ---
# Set to "false" to disable WebSocket real-time connections (use polling instead)
REALTIME_ENABLED=true

# Set to "false" to disable APScheduler (no automatic detection runs)
SCHEDULER_ENABLED=true

# Set to "true" to enable polling-optimized backend behavior
POLLING_MODE=false
```

---

### Step 5: Frontend Changes

#### 5a. Update `frontend/lib/types.ts`

Add new types for polling status and trigger response:

```typescript
// Add to existing types

export interface PollingStatus {
  realtime_enabled: boolean;
  scheduler_enabled: boolean;
  polling_mode: boolean;
  last_detection_run: string | null;
  regime: string | null;
}

export interface TriggerResponse {
  status: string;
  message: string;
  triggered_at: string;
  poll_after_seconds: number;
}
```

#### 5b. Update `frontend/lib/api.ts`

Add polling status fetch function and update trigger response type:

```typescript
// Add new function

/**
 * Fetch polling status and feature flag state.
 */
export async function fetchPollingStatus(): Promise<PollingStatus> {
  return apiFetch<PollingStatus>('/health/polling-status');
}

/**
 * Fetch alerts with optional `since` timestamp for incremental polling.
 */
export async function fetchAlertsIncremental(
  params?: { ticker?: string; since?: string; limit?: number; offset?: number }
): Promise<Alert[]> {
  const searchParams = new URLSearchParams();
  if (params?.ticker) searchParams.set('ticker', params.ticker);
  if (params?.since) searchParams.set('since', params.since);
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.offset) searchParams.set('offset', String(params.offset));

  const queryString = searchParams.toString();
  return apiFetch<Alert[]>(`/alerts${queryString ? `?${queryString}` : ''}`);
}
```

#### 5c. Update `frontend/components/Dashboard.tsx`

Modify to support incremental polling with configurable interval:

```typescript
'use client';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Alert, SystemMetrics } from '@/lib/types';
import { fetchAlerts, fetchSystemMetrics, fetchPollingStatus } from '@/lib/api';
import SignalCard from './SignalCard';
import AlertCard from './AlertCard';
import MetricsPanel from './MetricsPanel';

// Configurable polling interval (default 15s, overridable via env)
const ALERT_POLL_INTERVAL_MS = parseInt(
  process.env.NEXT_PUBLIC_POLL_INTERVAL_MS || '15000',
  10
);
const METRICS_POLL_INTERVAL_MS = 60000; // Metrics every 60s (less frequent)

export default function Dashboard() {
  const [signals, setSignals] = useState<Alert[]>([]);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastAlertTimestamp, setLastAlertTimestamp] = useState<string | null>(null);
  const [isPollingMode, setIsPollingMode] = useState(true);
  
  // Use ref to track latest timestamp without causing re-renders in interval
  const lastTimestampRef = useRef<string | null>(null);

  const loadAlerts = useCallback(async (incremental = false) => {
    try {
      const since = incremental && lastTimestampRef.current ? lastTimestampRef.current : undefined;
      const alertsData = await fetchAlerts({ 
        limit: 50, 
        ...(since ? { since } : {}) 
      });
      
      if (incremental && alertsData.length > 0) {
        // Merge new alerts with existing, avoiding duplicates by ID
        setSignals(prev => {
          const existingIds = new Set(prev.map(a => a.id));
          const newAlerts = alertsData.filter(a => !existingIds.has(a.id));
          // Prepend new alerts (newest first)
          return [...newAlerts, ...prev].slice(0, 200); // Cap at 200
        });
      } else if (!incremental) {
        setSignals(alertsData);
      }
      
      // Update last timestamp ref
      if (alertsData.length > 0) {
        const newest = alertsData[0].created_at;
        lastTimestampRef.current = newest;
        setLastAlertTimestamp(newest);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load alerts';
      setError(message);
    }
  }, []);

  const loadMetrics = useCallback(async () => {
    try {
      const metricsData = await fetchSystemMetrics();
      setMetrics(metricsData);
    } catch (err) {
      // Non-fatal — metrics are optional
      console.warn('Failed to load metrics:', err);
    }
  }, []);

  const loadInitialData = useCallback(async () => {
    try {
      setError(null);
      setIsLoading(true);
      // Check polling status
      try {
        const status = await fetchPollingStatus();
        setIsPollingMode(status.polling_mode || !status.realtime_enabled);
      } catch {
        // If status endpoint doesn't exist yet, default to polling mode
        setIsPollingMode(true);
      }
      
      // Full load on initial
      await Promise.all([
        loadAlerts(false),
        loadMetrics(),
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load dashboard data';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [loadAlerts, loadMetrics]);

  useEffect(() => {
    loadInitialData();
    
    // Alert polling interval
    const alertInterval = setInterval(() => loadAlerts(true), ALERT_POLL_INTERVAL_MS);
    // Metrics polling interval (less frequent)
    const metricsInterval = setInterval(loadMetrics, METRICS_POLL_INTERVAL_MS);
    
    return () => {
      clearInterval(alertInterval);
      clearInterval(metricsInterval);
    };
  }, [loadInitialData, loadAlerts, loadMetrics]);

  // ... rest of component unchanged (render logic stays the same)
```

**Key changes**:
1. `REFRESH_INTERVAL_MS` (30s) → `ALERT_POLL_INTERVAL_MS` (15s, configurable)
2. Separate intervals for alerts (15s) and metrics (60s)
3. Incremental polling using `since` parameter
4. Merge logic to avoid duplicates when combining new + existing alerts
5. Cap signals at 200 to prevent memory issues
6. Feature flag detection via `/health/polling-status`

#### 5d. Update `frontend/.env.local` (or `.env.example`)

Add:

```
NEXT_PUBLIC_POLLING_MODE=true
NEXT_PUBLIC_POLL_INTERVAL_MS=15000
```

---

### Step 6: Update `docs/ARCHITECTURE.md`

Add a new section after the existing architecture diagram:

```markdown
---

## 🔄 Polling Mode (Cost-Optimized)

Vigil supports a **polling-based architecture** as an alternative to real-time WebSocket connections. This is ideal for:
- Free-tier deployments (Render, Railway, Vercel) where WebSocket connections are limited
- Reducing server resource consumption
- Simpler deployment without WebSocket infrastructure

### Feature Flags

| Environment Variable | Default | Effect |
|---------------------|---------|--------|
| `REALTIME_ENABLED=false` | `true` | Disables WebSocket endpoint (returns close code 1008) |
| `SCHEDULER_ENABLED=false` | `true` | Disables APScheduler (no automatic daily scans) |
| `POLLING_MODE=true` | `false` | Enables polling-optimized backend behavior |

### How Polling Works

1. Frontend polls `GET /alerts?since=<timestamp>` every 15 seconds
2. Backend returns only alerts created after the `since` timestamp
3. Frontend merges new alerts into the existing list
4. Manual detection triggered via `POST /trigger` (requires API key)
5. System status available at `GET /health/polling-status`

### Migration Guide

See [POLLING_MIGRATION_PLAN.md](./POLLING_MIGRATION_PLAN.md) for detailed implementation.
```

---

## 5. New API Endpoint Specifications

### `GET /alerts?since=<iso_timestamp>`

**Purpose**: Incremental alert fetching for polling clients.

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `since` | `string` (ISO 8601) | No | Only return alerts with `created_at > since` |
| `ticker` | `string` | No | Filter by ticker symbol |
| `limit` | `int` | No | Max results (default 50, max 500) |
| `offset` | `int` | No | Pagination offset (default 0) |

**Response**: Same as existing `AlertResponse` array.

**Behavior**:
- If `since` is provided, adds `WHERE created_at > %s` to the SQL query
- If `since` is not provided, returns full list (backward compatible)
- Results ordered by `date DESC, created_at DESC`

---

### `GET /health/polling-status`

**Purpose**: Feature flag state and system status for polling clients.

**Response**:
```json
{
  "realtime_enabled": false,
  "scheduler_enabled": false,
  "polling_mode": true,
  "last_detection_run": "2026-04-03T21:00:00Z",
  "regime": "TRENDING"
}
```

**Authentication**: None required (public endpoint).

---

### `POST /trigger` (Enhanced)

**Purpose**: Manual detection trigger (already exists, enhanced response).

**Request Body** (optional):
```json
{
  "tickers": ["TSLA", "AAPL"]
}
```

**Response**:
```json
{
  "status": "detection_triggered",
  "message": "Detection run scheduled",
  "triggered_at": "2026-04-03T19:30:00Z",
  "poll_after_seconds": 30
}
```

**Authentication**: Requires `X-API-KEY` header.

---

## 6. Frontend Polling Implementation Plan

### Polling Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Polling Loop                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  t=0s    → Full load: GET /alerts (no since)                │
│  t=15s   → Incremental: GET /alerts?since=<latest_created>  │
│  t=30s   → Incremental: GET /alerts?since=<latest_created>  │
│  t=45s   → Incremental: GET /alerts?since=<latest_created>  │
│  t=60s   → Incremental + GET /stats (metrics refresh)       │
│  ...     → Repeat                                            │
│                                                              │
│  On new alerts:                                              │
│  - Merge into existing list (dedup by ID)                    │
│  - Cap list at 200 items                                     │
│  - Update lastTimestampRef                                   │
│                                                              │
│  On error:                                                   │
│  - Show error banner                                         │
│  - Retry on next interval (no exponential backoff needed)   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Merge Logic

```typescript
// When incremental poll returns new alerts:
setSignals(prev => {
  const existingIds = new Set(prev.map(a => a.id));
  const newAlerts = alertsData.filter(a => !existingIds.has(a.id));
  return [...newAlerts, ...prev].slice(0, 200);
});
```

### Error Handling

- Network errors: Display error banner, retry on next interval
- Empty responses: No action (no new alerts)
- Stale `since` timestamp: Backend returns full list if `since` is too old (future enhancement)

---

## 7. Code Classification: Disable vs Keep vs Modify

### DISABLED (when feature flags are false)

| Component | File | Lines | Condition |
|-----------|------|-------|-----------|
| WebSocket connection handling | `backend/api.py` | Lines 221-269 | `REALTIME_ENABLED=false` → immediate close |
| APScheduler startup | `backend/api.py` | Lines 168-180 | `SCHEDULER_ENABLED=false` → skip |
| Keep-warm heartbeat job | `backend/api.py` | Line 178 | `SCHEDULER_ENABLED=false` → skip |
| Daily detection cron job | `backend/api.py` | Lines 168-174 | `SCHEDULER_ENABLED=false` → skip |

### KEPT (unchanged)

| Component | File | Reason |
|-----------|------|--------|
| `WebSocketManager` class | `backend/services/ws_manager.py` | Reusable, may be re-enabled |
| `EventBus` class | `backend/services/event_bus.py` | Used by alert routing, not just WS |
| `run_detection()` | `backend/data.py` | Core detection logic, called by trigger |
| `run_backfill()` | `backend/data.py` | Core backfill logic |
| All database functions | `backend/database.py` | Data layer, mode-agnostic |
| All signal computation | `backend/advanced_signals.py` | Pure computation, mode-agnostic |
| Alert routing | `backend/services/alert_router.py` | Works independently of WS |
| Distributed lock | `backend/services/distributed_lock.py` | Used by trigger endpoint too |
| All frontend components | `frontend/components/*.tsx` | Render logic unchanged |
| API client | `frontend/lib/api.ts` | Extended, not replaced |

### MODIFIED

| Component | File | Change |
|-----------|------|--------|
| `startup_event()` | `backend/api.py:151-180` | Conditional scheduler start |
| `websocket_endpoint()` | `backend/api.py:221-269` | Early close when disabled |
| `fetch_alerts()` | `backend/api.py:274-306` | Add `since` parameter |
| `trigger_detection()` | `backend/api.py:433-444` | Enhanced response |
| `get_alerts()` | `backend/database.py:485-510` | Add `since` filter |
| `Dashboard.tsx` | `frontend/components/Dashboard.tsx` | Incremental polling |
| `.env.example` | `.env.example` | Add feature flag vars |
| `types.ts` | `frontend/lib/types.ts` | Add `PollingStatus`, `TriggerResponse` |
| `api.ts` | `frontend/lib/api.ts` | Add `fetchPollingStatus`, `fetchAlertsIncremental` |

### NEW FILES

| File | Purpose |
|------|---------|
| `backend/services/feature_flags.py` | Feature flag helper functions |

---

## 8. Risk Assessment

### High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **`since` parameter SQL injection** | Data breach | Parameterized query (already used in `get_alerts`) — no risk if implemented correctly |
| **Duplicate alerts in frontend** | UI confusion | Dedup by `id` in merge logic |
| **Missing alerts due to clock skew** | Data loss | Use server-side `created_at` for `since` comparison, not client clock |

### Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Scheduler disabled = no daily scans** | Stale data | Document that `POST /trigger` must be called manually or via external cron (e.g., GitHub Actions, cron-job.org) |
| **Keep-warm job disabled** | Neon/Render cold starts | Document alternative keep-warm strategy (e.g., UptimeRobot, cron-job.org pinging `/health`) |
| **Increased API load from polling** | Rate limiting / cost | 15s interval = 4 req/min per client. With 10 users = 40 req/min. Monitor and adjust interval if needed |
| **Frontend state drift** | Inconsistent UI | Full refresh on error or every Nth poll (e.g., every 20th poll = full reload) |

### Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **WebSocket endpoint returns close code** | Client confusion | Code 1008 with clear reason message |
| **Feature flag defaults** | Unexpected behavior | Defaults preserve current behavior (`REALTIME_ENABLED=true`, `SCHEDULER_ENABLED=true`) |
| **Existing `/trigger` endpoint behavior change** | Breaking change | Response is extended, not modified — existing `status` and `message` fields preserved |

### Edge Cases

1. **`since` parameter with invalid format**: Backend should handle gracefully — if `since` cannot be parsed, ignore it and return full list (or return 400 with clear error)
2. **No alerts exist yet**: `GET /alerts?since=<any>` returns empty array — frontend handles this correctly
3. **Detection run fails**: `POST /trigger` returns success but detection fails — client polls and gets no new alerts (acceptable behavior)
4. **Multiple concurrent trigger calls**: Distributed lock prevents duplicate runs — second call is skipped
5. **Frontend tab backgrounded**: Browser may throttle `setInterval` — acceptable for polling (will catch up on next poll)

### Database State

- **No schema changes required** — the `since` filter uses existing `created_at` column
- **No data migration required** — existing alerts remain accessible
- **Index recommendation**: If polling becomes the primary access pattern, consider adding `CREATE INDEX idx_alerts_created_at ON alerts(created_at DESC)` for faster `since` queries

---

## 9. Implementation Order

1. **Create `backend/services/feature_flags.py`** — no dependencies
2. **Modify `backend/database.py`** — add `since` parameter to `get_alerts()`
3. **Modify `backend/api.py`** — conditional scheduler, enhanced endpoints
4. **Update `.env.example`** — document new variables
5. **Update `frontend/lib/types.ts`** — add new types
6. **Update `frontend/lib/api.ts`** — add polling functions
7. **Update `frontend/components/Dashboard.tsx`** — incremental polling
8. **Update `docs/ARCHITECTURE.md`** — document polling mode
9. **Test**: Verify feature flags, polling, and trigger endpoints

---

## 10. Testing Checklist

- [ ] `REALTIME_ENABLED=false` → WebSocket returns close code 1008
- [ ] `SCHEDULER_ENABLED=false` → No APScheduler jobs start
- [ ] `GET /alerts?since=<timestamp>` returns only newer alerts
- [ ] `GET /alerts` (no since) returns full list (backward compatible)
- [ ] `POST /trigger` returns enhanced response with `triggered_at`
- [ ] `GET /health/polling-status` returns correct feature flag state
- [ ] Frontend polls every 15s and merges new alerts
- [ ] Frontend deduplicates alerts by ID
- [ ] Frontend caps signal list at 200 items
- [ ] Feature flag defaults preserve existing behavior
