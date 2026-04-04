# Vigil Forensic Production Audit V2

**Auditor:** Principal Systems Architect
**Date:** 2026-04-03
**Scope:** Full-stack audit of Vigil trading intelligence system (backend + frontend)
**Methodology:** Zero-trust code review across 10 domains, 40+ source files examined

---

## FINDINGS

---

SEVERITY: CRITICAL
Title: SQL Injection via Unvalidated `sort_by` and `sort_dir` Parameters in `list_signals()`
Location: `backend/services/di_router.py:314-477` — `list_signals()` endpoint
Root Cause: The `sort_by` and `sort_dir` query parameters are directly interpolated into a raw SQL query string via f-string at line 405 (`ORDER BY {sort_by} {sort_dir}`). Neither parameter is validated against a whitelist of allowed column names or sort directions before interpolation. An attacker controlling these parameters can inject arbitrary SQL.
Real-World Impact: Complete database compromise — data exfiltration, modification, or deletion of alerts, outcomes, weight calibrations, and simulation results. In a production environment with API key authentication, any authenticated user can exploit this.
Trigger Conditions: Any HTTP request to `GET /api/di/signals` with a crafted `sort_by` parameter (e.g., `sort_by=id; DROP TABLE alerts;--`).
Remediation: Replace dynamic SQL interpolation with a whitelist validation:
```python
ALLOWED_SORT_COLUMNS = {"detected_at", "id", "confidence_score", "symbol", "status"}
ALLOWED_SORT_DIRS = {"asc", "desc"}
if sort_by not in ALLOWED_SORT_COLUMNS:
    raise HTTPException(400, "Invalid sort_by parameter")
if sort_dir not in ALLOWED_SORT_DIRS:
    raise HTTPException(400, "Invalid sort_dir parameter")
```
Then use parameterized query with `sql.SQL` and `sql.Identifier` from asyncpg/psycopg2, or use the validated values directly in the f-string.

---

SEVERITY: CRITICAL
Title: Event Loop Collision in `_run_async()` Causes Silent Detection Failures
Location: `backend/data.py:405-421` — `_run_async()` helper
Root Cause: The `_run_async()` function creates a new event loop via `asyncio.new_event_loop()` and calls `run_until_complete()` on every invocation. When called from within an already-running async context (e.g., FastAPI request handler, APScheduler async job), this raises `RuntimeError: This event loop is already running` or creates a nested loop that cannot access the parent's resources (database connections, HTTP sessions). The function is called from `run_detection()` which may be invoked from both sync (scheduler) and async (API trigger) contexts.
Real-World Impact: Signal detection silently fails when triggered via the `/trigger` API endpoint (async context), producing zero alerts for that run. The detection run appears to complete successfully in logs because the error is caught by a broad `except Exception` at line 563-844 and logged but not propagated.
Trigger Conditions: Calling `run_detection()` from any async context — specifically the `POST /trigger` endpoint or any APScheduler job that runs in async mode.
Remediation: Replace `_run_async()` with a context-aware dispatcher:
```python
def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
        # Already in async context — this is a bug, caller should use await directly
        raise RuntimeError("_run_async called from async context; use await instead")
    except RuntimeError:
        return asyncio.new_event_loop().run_until_complete(coro)
```
Better: Refactor `run_detection()` to be fully async and use `await` directly, eliminating the need for `_run_async()` entirely.

---

SEVERITY: CRITICAL
Title: Race Condition in Outcome State Machine — SELECT-then-UPDATE Window
Location: `backend/services/outcome_tracker.py:213-339` — `_update_single_outcome()`
Root Cause: The method first reads the current outcome row with a SELECT query (line 232), evaluates state transitions in Python, then issues an UPDATE with `WHERE state = $10` (optimistic locking). However, between the SELECT and UPDATE, another concurrent process (e.g., a second polling cycle or manual resolution) can modify the same row. The optimistic lock prevents overwriting but does not prevent the second process from also reading the same stale state and making a conflicting transition. This creates a window where two processes can both believe they successfully transitioned the outcome.
Real-World Impact: Duplicate state transitions — an outcome can be marked as TARGET_HIT by two concurrent processes, potentially double-recording PnL or corrupting the `resolved_at` timestamp. In a multi-instance deployment behind a load balancer, this occurs on every polling cycle.
Trigger Conditions: Two or more concurrent calls to `update_outcomes()` or `resolve_outcome()` for the same `signal_id` within the same polling window (typically 5-15 minutes).
Remediation: Use a single atomic UPDATE with a CASE expression or a PostgreSQL advisory lock per signal_id:
```sql
UPDATE signal_outcomes
SET state = $1, exit_price = $2, outcome_pct = $3,
    final_pnl_state = $4, resolved_at = NOW()
WHERE signal_id = $5 AND state = $6
RETURNING id;
```
Check the RETURNING result — if zero rows, another process already transitioned the state.

---

SEVERITY: CRITICAL
Title: Dual-Pool Database Inconsistency — asyncpg Writes Invisible to psycopg2 Reads
Location: `backend/database.py` — `get_pool()` (asyncpg, line 195) vs `get_conn()` (psycopg2, line 104)
Root Cause: The system maintains two independent PostgreSQL connection pools: an asyncpg pool for DI endpoints and a psycopg2 pool for legacy endpoints (`save_alert`, `get_alerts`, `evaluate_outcomes`, etc.). These pools operate in separate transactional contexts. When `save_alert()` writes via psycopg2, the asyncpg pool may not see the data immediately due to transaction isolation (READ COMMITTED default means it will see it on next query, but connection-level caching or prepared statements can delay visibility). Conversely, DI endpoints writing via asyncpg are invisible to legacy psycopg2 queries until the asyncpg transaction commits and the psycopg2 connection re-queries.
Real-World Impact: Signals scored by the DI scoring engine (asyncpg) are not visible to the legacy `/alerts` endpoint (psycopg2), causing the frontend to show stale or missing signals. Outcome tracking updates (asyncpg) are not reflected in the legacy `evaluate_outcomes()` function, causing incorrect PnL calculations.
Trigger Conditions: Any write via one pool followed by a read via the other pool within the same polling cycle. Most visible under load when DI endpoints and legacy endpoints are called concurrently.
Remediation: Migrate all legacy psycopg2 functions to use the asyncpg pool. The `get_conn()` function and all `with get_db_cursor()` usages should be replaced with `async with (await get_pool()).acquire() as conn:`. This is a large migration but critical for data consistency. As an interim fix, add `await conn.reset()` after acquiring asyncpg connections to clear any cached state.

---

SEVERITY: HIGH
Title: Deterministic Simulation Masquerading as Probabilistic — False Confidence in Backtest Results
Location: `backend/services/portfolio_risk.py:374-385` — `simulate_portfolio()` win/loss determination
Root Cause: The simulation determines trade outcomes deterministically using `win_rate` thresholds: `if i / total_signals < win_rate: result = "win"`. This means the first N trades are always wins and the remaining are always losses, where N = total_signals * win_rate. A true simulation would use random sampling (e.g., `random.random() < win_rate`) to produce variable outcomes across runs. The current implementation produces identical results for identical inputs, which is correct for reproducibility but the function is named `simulate_portfolio` and presented as a "simulation" to users who expect probabilistic outcomes.
Real-World Impact: Users running the same simulation parameters multiple times get identical equity curves, creating false confidence in the strategy's predictability. The deterministic ordering (all wins first, then all losses) also produces an artificially smooth equity curve that does not reflect real-world drawdown patterns.
Trigger Conditions: Any call to `POST /di/simulate` or `POST /api/di/simulations/run`.
Remediation: Add a `seed` parameter for reproducibility and use probabilistic outcome determination:
```python
import random
rng = random.Random(seed)
for i in range(total_signals):
    if rng.random() < win_rate:
        result = "win"
    else:
        result = "loss"
```
Document that results are probabilistic and vary by seed.

---

SEVERITY: HIGH
Title: Correlation Filter Groups by Ticker Only — Misses Cross-Asset Correlation Risk
Location: `backend/services/portfolio_risk.py:439-483` — `_apply_correlation_filter()`
Root Cause: The correlation filter groups positions by ticker symbol and only limits exposure within the same ticker. It does not use the actual correlation matrix to identify highly correlated different tickers (e.g., AAPL and MSFT typically have 0.7+ correlation). Two positions in different but highly correlated assets are treated as independent risks, allowing the portfolio to exceed its intended correlation-adjusted exposure limit.
Real-World Impact: Portfolio concentration risk — the system may allocate 10% to AAPL and 10% to MSFT, treating them as independent 10% positions when their effective correlated exposure is closer to 18-20%. During market stress, correlated assets move together, amplifying drawdowns beyond the stated max_drawdown_pct limit.
Trigger Conditions: Portfolio with multiple positions in correlated assets (e.g., tech stocks, sector ETFs) where individual positions pass the correlation filter but combined correlated exposure exceeds risk limits.
Remediation: Use the `CorrelationEngine.compute_portfolio_correlation()` result to build a correlation-adjusted exposure metric. Group assets into clusters using the hierarchical clustering output and apply position limits at the cluster level, not just the ticker level.

---

SEVERITY: HIGH
Title: Cache Staleness Check Ignores Market Hours — Serves Stale Regime Data During Active Trading
Location: `backend/services/regime_detector.py:228-271` — `_is_cache_stale()`
Root Cause: The staleness check compares the cached regime's `computed_at` timestamp against the latest OHLCV data timestamp. It does not check whether the market is currently open or whether new data has arrived since the cache was computed. If the cache was computed at 9:30 AM and the market is still open at 3:00 PM, the cache is served as "fresh" even though 5.5 hours of price action have occurred. The 5-minute TTL in `_get_cached_regime()` (line 273) is the only freshness guard, but the staleness check can override it if OHLCV timestamps haven't changed (e.g., during market hours when yfinance hasn't been polled).
Real-World Impact: Regime-dependent signal scoring uses outdated market regime classification during active trading hours. A regime shift from TRENDING to VOLATILE occurring mid-day is not reflected in signals scored until the next OHLCV poll, causing signals to be scored with incorrect regime alignment weights.
Trigger Conditions: Market is open, regime cache is less than 5 minutes old but OHLCV data hasn't been refreshed (yfinance polling interval), and a regime shift has occurred in the interim.
Remediation: Add a market-hours check to the staleness logic:
```python
def _is_cache_stale(cached_regime, ohlcv_data):
    # ... existing timestamp check ...
    # Also check if market is open and cache is older than N minutes
    if _is_market_open() and (datetime.now(timezone.utc) - cached_at).total_seconds() > 300:
        return True
```

---

SEVERITY: HIGH
Title: Weight Calibration is a No-Op — `_evaluate_weights()` Does Not Actually Evaluate
Location: `backend/services/scoring_engine.py:558-590` — `_evaluate_weights()`
Root Cause: The method iterates over historical outcomes and checks `outcome_pct > 0` as a proxy for "predicted win." This does not test the weights at all — it simply counts how many historical outcomes were profitable regardless of what the scoring engine predicted. The weights are never applied to historical data to see if they would have produced better scores for winning signals. The function returns the input weights unchanged because the evaluation logic is a tautology.
Real-World Impact: The `calibrate_weights()` endpoint (`POST /di/score/calibrate`) appears to perform weight optimization but actually does nothing. Weight calibrations are persisted to the database with no actual improvement, giving users false confidence that the system is self-optimizing.
Trigger Conditions: Any call to `calibrate_weights()` or the self-evaluation weight update path.
Remediation: Implement actual weight evaluation by applying candidate weights to historical signals and measuring the resulting score-outcome correlation:
```python
def _evaluate_weights(self, candidate_weights, historical_signals):
    scores = [self._compute_score(sig, candidate_weights) for sig in historical_signals]
    # Measure correlation between scores and actual outcomes
    correlation = pearson_correlation(scores, [o.outcome_pct for o in historical_signals])
    return correlation
```
Use coordinate descent to maximize this correlation.

---

SEVERITY: HIGH
Title: Deduplication Store Has In-Memory-Only Mode — Duplicates Survive Restarts
Location: `backend/services/dedup.py:7-68` — `DeduplicationStore`
Root Cause: The `is_duplicate()` method first checks the in-memory `_seen` set (line 19). If the fingerprint is not in memory, it falls back to a database query (line 26-44). However, the `record()` method (line 46-65) writes to the database but does NOT add to the in-memory `_seen` set. This means: (1) after a process restart, the in-memory set is empty and all fingerprints must be checked against the database, (2) if the database is unavailable, `record()` silently fails and the fingerprint is never persisted, (3) the in-memory set grows unbounded — there is no eviction policy.
Real-World Impact: After a server restart, duplicate signals are generated until the in-memory set is repopulated. Under database outage, all deduplication fails and every signal is treated as new, causing alert flooding to downstream consumers (Slack, webhooks).
Trigger Conditions: Server restart, database connection failure, or long-running process where the in-memory set exceeds available RAM.
Remediation: Ensure `record()` always adds to `_seen`:
```python
def record(self, fingerprint, alert_id=None):
    self._seen.add(fingerprint)  # Always add to memory first
    # ... database write with retry ...
```
Add a TTL-based eviction policy or use a bounded LRU set.

---

SEVERITY: MEDIUM
Title: `compute_decay()` Naive Datetime Fallback Causes Incorrect Freshness Calculation
Location: `backend/api.py:267-279` — `compute_decay()`
Root Cause: The function checks if `created_at` is timezone-aware (line 271: `if created_at.tzinfo is None`). If naive, it replaces with UTC. However, the `created_at` value comes from the database which stores TIMESTAMPTZ. If the database driver returns a naive datetime (possible with psycopg2 depending on configuration), the replacement is correct. But if `created_at` is already timezone-aware with a non-UTC timezone (e.g., US/Eastern), the function does not convert it to UTC before computing the difference with `datetime.now(timezone.utc)`. This produces incorrect `hours_old` values during daylight saving time transitions or for databases configured with non-UTC timezones.
Real-World Impact: Signal freshness bars in the frontend show incorrect ages — a signal that is 2 hours old may display as 6 hours old (or vice versa) during DST transitions. This affects trader decisions about whether to act on a signal.
Trigger Conditions: Database server configured with non-UTC timezone, or psycopg2 returning timezone-aware datetimes with local timezone instead of UTC.
Remediation: Always normalize to UTC:
```python
if created_at.tzinfo is None:
    created_at = created_at.replace(tzinfo=timezone.utc)
else:
    created_at = created_at.astimezone(timezone.utc)
```

---

SEVERITY: MEDIUM
Title: WebSocket Connection Leak — Heartbeat Tasks Not Cleaned on Server Shutdown
Location: `backend/services/ws_manager.py:109-129` — `_heartbeat_loop()`
Root Cause: The heartbeat loop runs as an `asyncio.Task` stored in `_heartbeat_tasks`. When the server shuts down (e.g., SIGTERM), the tasks are cancelled but the `_connections` dict is not cleared. The `disconnect()` method (line 67-79) removes from `_connections` and cancels the task, but there is no `shutdown()` method that iterates all connections and disconnects them. If the server receives a shutdown signal while WebSocket clients are connected, the tasks are orphaned and the connections dict retains stale references.
Real-World Impact: On server restart, the WebSocket manager singleton retains stale connection references. New connections may fail if `_max_connections` is reached by stale entries. Clients that were connected during shutdown must wait for the heartbeat timeout (30s default) before the server considers them disconnected.
Trigger Conditions: Server shutdown with active WebSocket connections.
Remediation: Add a `shutdown()` method and call it from the FastAPI shutdown event:
```python
async def shutdown(self):
    for conn_id in list(self._connections.keys()):
        await self.disconnect(conn_id)
```

---

SEVERITY: MEDIUM
Title: Frontend `apiFetch` URL Construction Fails in SSR Context
Location: `frontend/lib/api.ts:58` — `apiFetch()` URL construction
Root Cause: The URL is constructed using `typeof window !== 'undefined' ? window.location.origin : 'http://localhost'`. During Next.js server-side rendering (SSR), `window` is undefined, so the base URL defaults to `http://localhost`. When deployed to a production environment (e.g., Vercel, Docker), SSR requests to the API fail because `http://localhost` does not resolve to the backend server. The `BASE_URL` environment variable (`process.env.NEXT_PUBLIC_API_URL`) is prepended but the `new URL()` call still requires a valid base for relative paths.
Real-World Impact: Server-side rendered pages that fetch data from the backend API fail in production with network errors. The pages render with empty data or error states.
Trigger Conditions: Any SSR request in a production deployment where `NEXT_PUBLIC_API_URL` is not set to an absolute URL.
Remediation: Use `BASE_URL` as the origin when available:
```typescript
const origin = BASE_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
const url = new URL(path, origin);
```
Ensure `NEXT_PUBLIC_API_URL` is set to the absolute backend URL in production.

---

SEVERITY: MEDIUM
Title: `EquityCurve` Component Crashes on Single Data Point
Location: `frontend/components/EquityCurve.tsx:26-30` — SVG point calculation
Root Cause: The component calculates x-coordinates using `(i / (data.length - 1)) * chartWidth`. When `data.length === 1`, this divides by zero, producing `Infinity` for the x-coordinate. The SVG renderer then fails to render the polyline, and the component displays nothing (or crashes in strict mode).
Real-World Impact: Simulations with a single data point (e.g., a backtest that ran for one day) cause the equity curve visualization to break silently. Users see a blank chart area with no error message.
Trigger Conditions: Any simulation or backtest result with exactly one equity curve data point.
Remediation: Handle the single-point case:
```typescript
if (data.length === 1) {
    // Render a single point or return a placeholder
    return <div className="py-4 text-center text-gray-500">Insufficient data for chart</div>;
}
```

---

SEVERITY: MEDIUM
Title: `alert_router.py` Uses Synchronous psycopg2 in Async Context — Blocks Event Loop
Location: `backend/services/alert_router.py:52-76` — `_record_delivery()`
Root Cause: The `_record_delivery()` method is called from `_dispatch_one()` which is an `async def` method. However, `_record_delivery()` uses synchronous psycopg2 via `get_conn()` and `conn.cursor()`, which blocks the event loop during the database write. Under load with multiple alert dispatches, this blocks the entire async event loop, preventing other async handlers (WebSocket broadcasts, health checks, API responses) from executing.
Real-World Impact: During alert storms (e.g., market open with multiple volume spikes), the event loop is blocked for the duration of all synchronous database writes. API response latency spikes to seconds, WebSocket heartbeats fail, and health checks timeout.
Trigger Conditions: Multiple concurrent alert dispatches via the event bus or alert router.
Remediation: Make `_record_delivery()` async and use the asyncpg pool:
```python
async def _record_delivery(self, alert_id, channel, status, error=None):
    async with self._pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO alert_deliveries ...",
            alert_id, channel, status, error
        )
```

---

SEVERITY: MEDIUM
Title: `distributed_lock.py` Thread Lock Release Race — `_owner_token` Not Thread-Safe
Location: `backend/services/distributed_lock.py:136-159` — `_acquire_thread()` and `_release_thread()`
Root Cause: The `_owner_token` attribute is set in `_acquire_thread()` (line 141) and checked in `_release_thread()` (line 150) without holding the lock during the check. Between the `acquire()` call returning and the `_owner_token` being set, another thread could call `release()` with a different token and the check `owner_token != self._owner_token` could pass if `_owner_token` is still `None` from a previous release. Additionally, `_release_thread()` sets `self._owner_token = None` (line 155) after releasing the lock, creating a window where another thread could acquire the lock and set a new token before the first thread clears it.
Real-World Impact: In a multi-threaded environment (e.g., APScheduler with multiple workers), lock release can fail silently or release the wrong lock, allowing two threads to execute the critical section simultaneously.
Trigger Conditions: Concurrent scheduled jobs using the same distributed lock instance.
Remediation: Move `_owner_token` management inside the lock:
```python
def _acquire_thread(self, blocking):
    import uuid
    if blocking:
        self._thread_lock.acquire()
    elif not self._thread_lock.acquire(blocking=False):
        return ""
    token = str(uuid.uuid4())
    self._owner_token = token
    return token

def _release_thread(self, owner_token):
    if not owner_token:
        return False
    with self._thread_lock:
        if owner_token != self._owner_token:
            return False
        self._owner_token = None
    self._thread_lock.release()
    return True
```

---

SEVERITY: LOW
Title: `cache_result` Decorator Uses MD5 for Cache Keys — Collision Risk
Location: `backend/services/cache.py:151-172` — `cache_result()` decorator
Root Cause: Cache keys are built using MD5 hashes of function arguments (line 155-157). MD5 is not collision-resistant, and with 128-bit output, the birthday bound is ~2^64 inputs. While unlikely in practice, two different argument sets could produce the same cache key, causing incorrect cache hits. More practically, the MD5 truncation to 8 hex characters (32 bits) means collisions are expected after ~2^16 = 65,536 unique argument combinations.
Real-World Impact: Rare but possible incorrect cache hits where function A with arguments X returns the cached result of function A with arguments Y.
Trigger Conditions: High-cardinality function arguments (e.g., timestamps, UUIDs) passed to cached functions.
Remediation: Use SHA-256 and full hash output, or use `repr()` of arguments directly as the key suffix.

---

SEVERITY: LOW
Title: `rate_limiter.py` SQL Injection via `window_seconds` Interval String Interpolation
Location: `backend/services/rate_limiter.py:59-61` — `ChannelRateLimiter.allow()`
Root Cause: The `window_seconds` value is interpolated directly into the SQL query as a string: `f"{limit.window_seconds} seconds"`. While the value comes from a hardcoded configuration (`ChannelRateLimit`), if the configuration is ever made dynamic (e.g., from environment variables or database), this becomes a SQL injection vector.
Real-World Impact: Currently low risk due to hardcoded values, but becomes critical if rate limit configuration is externalized.
Trigger Conditions: Dynamic rate limit configuration with untrusted input.
Remediation: Use parameterized interval: `INTERVAL '1 second' * $2` instead of string interpolation.

---

SEVERITY: LOW
Title: `security.py` JWT Secret Defaults to Development Value in Production
Location: `backend/services/security.py:134` — `JWT_SECRET` default
Root Cause: The JWT secret defaults to `"dev-secret-do-not-use-in-production"` if neither `JWT_SECRET` nor `SECRET_KEY` environment variables are set. There is no runtime check or warning when the application starts with this default in a production environment.
Real-World Impact: Any user who knows the default secret can forge JWT tokens and authenticate as any user, bypassing API key authentication.
Trigger Conditions: Deployment without `JWT_SECRET` or `SECRET_KEY` environment variable set.
Remediation: Fail startup if JWT_SECRET is not set in production:
```python
JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("SECRET_KEY")
if not JWT_SECRET and os.environ.get("ENVIRONMENT") == "production":
    raise RuntimeError("JWT_SECRET must be set in production")
```

---

## SUMMARY

| Severity | Count |
|----------|-------|
| CRITICAL | 4     |
| HIGH     | 4     |
| MEDIUM   | 5     |
| LOW      | 3     |
| **Total**| **16**|

### Domain Coverage

| Domain                              | Findings |
|-------------------------------------|----------|
| Data Integrity / Temporal Precision | 2        |
| Quant Logic / Signal Validity       | 2        |
| Polling / State Synchronization     | 2        |
| Concurrency / Async Execution       | 3        |
| Database / Query Reliability        | 3        |
| Failure Modes / Recovery            | 1        |
| Frontend Resilience                 | 2        |
| API Contract / Validation           | 1        |
| Scale / Performance Limits          | 1        |
| Silent Correctness Failures         | 2        |
