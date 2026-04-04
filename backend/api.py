"""
Vigil API — High-Performance FastAPI Implementation
"""

import os
import json
import logging
import asyncio
from typing import List, Optional, Any
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks, Request, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Internal imports
from database import (
    get_alerts, get_watchlist, add_to_watchlist, remove_from_watchlist,
    get_system_metrics, save_backtest_run, save_backtest_results,
    get_backtest_runs, get_backtest_results, get_latest_correlation,
    save_correlation_matrix, init_db, get_pool, close_pool, get_latest_regime,
)
from data import run_detection, run_backfill
from services.regime_engine import compute_regime_adaptive
from services.security import generate_jwt, get_allowed_origins
from services.health import health_router
from services.observability import (
    configure_structured_logging,
    RequestIDMiddleware,
    LoggingMiddleware,
    PrometheusMiddleware,
    RequestIDFilter,
    PROMETHEUS_AVAILABLE,
    REGISTRY,
    metrics,
)
from services.event_bus import event_bus
from services.ws_manager import ws_manager
from services.distributed_lock import DistributedLock
from services.feature_flags import is_realtime_enabled, is_scheduler_enabled, is_polling_mode
from services.di_router import di_router

logger = logging.getLogger(__name__)


# --- Distributed Lock Wrapper for Scheduled Jobs ---

def with_distributed_lock(key: str, ttl: int = 300):
    """
    Decorator that wraps a scheduled job with a distributed lock.

    Prevents duplicate detection runs when multiple instances are deployed.
    Falls back to a threading lock when Redis is unavailable.

    Args:
        key: Unique lock key (e.g., "detection", "keep_warm").
        ttl: Lock timeout in seconds (prevents stale locks if a job crashes).
    """
    _lock: Optional[DistributedLock] = None

    def decorator(func):
        def wrapper(*args, **kwargs):
            nonlocal _lock
            if _lock is None:
                _lock = DistributedLock(key, timeout=ttl)

            owner_token = _lock.acquire(blocking=False)
            if not owner_token:
                logger.info(f"Skipping scheduled job '{key}' — another instance holds the lock")
                return None
            try:
                logger.info(f"Acquired lock '{key}' — running scheduled job")
                return func(*args, **kwargs)
            finally:
                _lock.release(owner_token)
        return wrapper
    return decorator

# --- Pydantic Models for CV-Grade Type Safety ---
class AlertResponse(BaseModel):
    id: int
    ticker: str
    signal_type: str
    edge_score: float
    action: str
    regime: str
    decay: Optional[dict] = Field(default_factory=lambda: {"pct": 0, "status": "UNKNOWN", "hours_old": 0})
    summary: str
    created_at: datetime

class WatchlistRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)


class BacktestRequest(BaseModel):
    name: Optional[str] = None
    start_date: str = Field(..., min_length=1)
    end_date: str = Field(..., min_length=1)
    tickers: List[str] = Field(..., min_items=1)
    capital: float = Field(default=100000.0, gt=0)


class TriggerRequest(BaseModel):
    tickers: Optional[List[str]] = None


class BackfillRequest(BaseModel):
    tickers: Optional[List[str]] = None
    days: Optional[int] = Field(default=60, gt=0)


class CorrelationResponse(BaseModel):
    tickers: Optional[List[str]] = None
    matrix: Optional[List[List[float]]] = None
    period: Optional[str] = None
    method: Optional[str] = None
    stored_at: Optional[str] = None

app = FastAPI(
    title="Vigil Quant API",
    description="Institutional-grade market surveillance engine",
    version="2.0.0"
)

# --- Observability & Logging ---
configure_structured_logging()

# Add RequestIDFilter to root logger so all log entries include request_id
_root_logger = logging.getLogger()
_request_id_filter = RequestIDFilter()
_root_logger.addFilter(_request_id_filter)

# Middleware order: Request ID → Prometheus → Logging → CORS → Routes
app.add_middleware(RequestIDMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(LoggingMiddleware)
app.include_router(health_router)
app.include_router(di_router)


# --- Global Exception Handler (Standardized Error Responses) ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Format HTTPException errors using the standardized APIError model."""
    from models import APIError

    # Check if detail is already in standardized format
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        error = APIError(
            code=exc.detail["code"],
            message=exc.detail.get("message", exc.detail.get("detail", "")),
            details=exc.detail.get("details"),
            path=request.url.path,
        )
    else:
        # Convert plain string detail to standardized format
        message = exc.detail if isinstance(exc.detail, str) else "An error occurred"
        code = "INTERNAL_ERROR" if exc.status_code >= 500 else "VALIDATION_ERROR"
        error = APIError(
            code=code,
            message=message,
            path=request.url.path,
        )

    return Response(
        content=error.model_dump_json(),
        status_code=exc.status_code,
        media_type="application/json",
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unhandled exceptions."""
    from models import APIError

    logger.exception(f"Unhandled exception in request {request.url.path}: {exc}")

    error = APIError(
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        details={"error_type": type(exc).__name__},
        path=request.url.path,
    )

    return Response(
        content=error.model_dump_json(),
        status_code=500,
        media_type="application/json",
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-Process Scheduler (Free-Tier Optimization) ---
scheduler = AsyncIOScheduler()


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
        # _get_system_stats already has @with_distributed_lock decorator
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


@app.on_event("shutdown")
async def shutdown_event():
    """
    Gracefully shuts down the scheduler and closes the asyncpg connection pool.
    """
    scheduler.shutdown(wait=False)
    await close_pool()
    logger.info("Vigil shutdown complete")

# --- Logic Helpers (Restored from Flask version) ---
DECAY_PROFILES = {
    "VOLUME_SPIKE_UP": (8, 10),
    "VOLUME_SPIKE_DOWN": (8, 10),
    "ACCUMULATION_DETECTED": (36, 20),
}

def compute_decay(signal_type: str, created_at: datetime):
    half_life, min_strength = DECAY_PROFILES.get(signal_type, (8, 10))
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    hours_old = (now - created_at).total_seconds() / 3600
    strength = max(min_strength, int((0.5 ** (hours_old / half_life)) * 100))
    return {
        "pct": strength,
        "status": "FRESH" if hours_old < half_life * 0.5 else "DECAYING",
        "hours_old": round(hours_old, 1)
    }

# --- Dependency for Security ---
async def verify_api_key(api_key: str = Header(..., alias="X-API-KEY")):
    if api_key != os.environ.get("VIGIL_API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid or missing API Key in Header")
    return api_key

# --- WebSocket Endpoint ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time push of alerts, signals, and regime changes.
    Disabled when REALTIME_ENABLED=false — returns close code 1008.
    """
    if not is_realtime_enabled():
        await websocket.accept()
        await websocket.close(code=1008, reason="Real-time WebSocket is disabled (polling mode active)")
        return

    import uuid

    connection_id = str(uuid.uuid4())
    accepted = await ws_manager.connect(connection_id, websocket)

    if not accepted:
        await websocket.close(code=1008, reason="Maximum connections reached")
        return

    # Subscribe to all event types for this connection
    def _forward_event(payload: dict):
        """Synchronous callback from event bus — schedule async send."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    ws_manager.send_to(
                        connection_id,
                        {"type": "event", "event_type": payload.get("event_type", "unknown"), "data": payload},
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to forward event to WebSocket {connection_id}: {e}")

    # Subscribe to key event types
    event_types = ["alert", "signal", "regime_change"]
    for event_type in event_types:
        event_bus.subscribe(event_type, _forward_event)

    try:
        while True:
            # Keep the connection alive by waiting for messages (client can send pong)
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket {connection_id} disconnected normally")
    except Exception as e:
        logger.warning(f"WebSocket {connection_id} error: {e}")
    finally:
        # Unsubscribe from event bus
        for event_type in event_types:
            event_bus.unsubscribe(event_type, _forward_event)
        await ws_manager.disconnect(connection_id)


# --- Endpoints ---

@app.get("/alerts", response_model=List[AlertResponse])
async def fetch_alerts(
    ticker: Optional[str] = None,
    since: Optional[str] = Query(None, description="ISO 8601 timestamp — only return alerts created after this time"),
    limit: int = Query(50, gt=0, le=500),
    offset: int = 0
):
    """Fetch and enrich alerts with decay logic. Supports incremental polling via `since` parameter."""
    raw_data = get_alerts(ticker=ticker, limit=limit, offset=offset, since=since)
    
    # Column mapping - ideally get_alerts should return a list of dicts
    # Here we map based on the 31-column schema from database.py
    enriched = []
    for row in raw_data:
        try:
            created_at = row['created_at']
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
                
            enriched.append({
                "id": row['id'],
                "ticker": row['ticker'],
                "signal_type": row['signal_type'],
                "edge_score": float(row['edge_score']) if row['edge_score'] is not None else 0.0,
                "action": row['action'],
                "regime": row['regime'],
                "decay": compute_decay(row['signal_type'], created_at),
                "summary": row['summary'],
                "created_at": created_at
            })
        except (IndexError, ValueError) as e:
            continue
            
    return enriched

@app.get("/regime")
async def get_market_regime():
    def _fetch():
        import yfinance as yf
        return yf.Ticker("SPY").history(period="60d")
    
    spy = await run_in_threadpool(_fetch)
    return {"regime": compute_regime_adaptive(spy)}

@with_distributed_lock("keep_warm", ttl=60)
def _get_system_stats():
    """Standalone function for scheduler keep-warm job."""
    try:
        return get_system_metrics()
    except Exception as e:
        logger.error(f"Keep-warm stats job failed: {e}")
        return None


@app.get("/stats")
async def system_stats():
    return _get_system_stats()


@app.get("/health/polling-status")
async def polling_status():
    """
    Returns feature flag state and last detection run info for polling clients.
    """
    recent_alerts = get_alerts(limit=1)
    last_run = recent_alerts[0]['created_at'].isoformat() if recent_alerts else None

    return {
        "realtime_enabled": is_realtime_enabled(),
        "scheduler_enabled": is_scheduler_enabled(),
        "polling_mode": is_polling_mode(),
        "last_detection_run": last_run,
        "regime": get_latest_regime(),
    }

@app.post("/backtest/run")
async def run_backtest_task(req: BacktestRequest, background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    """Restored full backtesting orchestration."""
    def _execute():
        import yfinance as yf
        from database import get_alerts, save_backtest_run, save_backtest_results
        from backtest.engine import BacktestEngine, BacktestConfig

        config = BacktestConfig(
            name=req.name or f"BT_{datetime.now().strftime('%Y%m%d')}",
            start_date=req.start_date,
            end_date=req.end_date,
            tickers=req.tickers,
            initial_capital=req.capital,
        )

        # Load historical signals from alerts DB
        raw_alerts = get_alerts(limit=10000)
        signals = [
            {
                "ticker": a["ticker"],
                "date": str(a["created_at"]),
                "action": a["action"],
                "edge_score": float(a["edge_score"]) if a["edge_score"] is not None else 5.0,
                "signal_type": a["signal_type"],
            }
            for a in raw_alerts
            if a["ticker"] in req.tickers
        ]

        # Fetch price data for each ticker
        price_data = {}
        for t in req.tickers:
            try:
                price_data[t] = yf.Ticker(t).history(start=req.start_date, end=req.end_date)
            except Exception as e:
                logger.warning(f"Failed to fetch price data for {t}: {e}")

        if not signals or not price_data:
            logger.warning("Backtest skipped: no signals or price data available")
            return

        engine = BacktestEngine(config)
        result = engine.run(signals, price_data)

        # Persist results
        try:
            save_backtest_run(config.name, config.to_dict())
            save_backtest_results(config.name, {
                "metrics": {
                    "total_return_pct": result.metrics.total_return_pct,
                    "sharpe_ratio": result.metrics.sharpe_ratio,
                    "max_drawdown_pct": result.metrics.max_drawdown_pct,
                    "win_rate": result.metrics.win_rate,
                    "total_trades": result.metrics.total_trades,
                },
                "trades": [
                    {"ticker": t.ticker, "entry": t.entry_price, "exit": t.exit_price,
                     "pnl": t.pnl, "entry_date": str(t.entry_date), "exit_date": str(t.exit_date)}
                    for t in result.trades
                ],
            })
        except Exception as e:
            logger.error(f"Failed to save backtest results: {e}")

    background_tasks.add_task(_execute)
    return {"status": "backtest_started", "name": req.name or f"BT_{datetime.now().strftime('%Y%m%d')}"}

@app.get("/portfolio/risk")
async def portfolio_risk():
    def _compute():
        from services.portfolio_risk import get_risk_analyzer
        import yfinance as yf
        
        watchlist = get_watchlist()
        # Perform blocking I/O inside threadpool
        histories = {t: yf.Ticker(t).history(period="60d") for t in watchlist}
        positions = {t: {"quantity": 10, "avg_cost": 0} for t in watchlist}
        
        analyzer = get_risk_analyzer()
        return analyzer.compute_portfolio_risk(positions, histories)

    return await run_in_threadpool(_compute)

# --- Watchlist Management ---
@app.get("/watchlist")
async def list_watchlist():
    return get_watchlist()

@app.post("/watchlist")
async def update_watchlist(req: WatchlistRequest, api_key: str = Depends(verify_api_key)):
    add_to_watchlist(req.ticker)
    return {"status": "success", "added": req.ticker}

@app.delete("/watchlist")
async def delete_from_watchlist(ticker: str, api_key: str = Depends(verify_api_key)):
    remove_from_watchlist(ticker)
    return {"status": "removed", "ticker": ticker}


# --- Missing Endpoints ---

@app.post("/trigger", response_model=None)
async def trigger_detection(
    background_tasks: BackgroundTasks,
    req: Optional[TriggerRequest] = None,
    api_key: str = Depends(verify_api_key),
):
    """
    Manual signal trigger endpoint.
    Triggers the market detection run immediately.
    """
    if not is_scheduler_enabled():
        logger.info("Manual detection triggered (scheduler disabled)")

    background_tasks.add_task(run_detection)

    trigger_time = datetime.now(timezone.utc).isoformat()

    return {
        "status": "detection_triggered",
        "message": "Detection run scheduled",
        "triggered_at": trigger_time,
        "poll_after_seconds": 30,
    }


@app.post("/backfill", response_model=None)
async def trigger_backfill(
    background_tasks: BackgroundTasks,
    req: Optional[BackfillRequest] = None,
    api_key: str = Depends(verify_api_key),
):
    """
    Historical data backfill endpoint.
    Triggers the backfill process for historical data ingestion.
    """
    background_tasks.add_task(run_backfill)
    return {"status": "backfill_started", "message": "Backfill job scheduled"}


@app.get("/correlation")
async def get_correlation():
    """
    Correlation analysis endpoint.
    Returns the latest stored correlation matrix.
    """
    result = get_latest_correlation()
    if result is None:
        return {"status": "no_data", "message": "No correlation data available"}
    return result


@app.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus-compatible metrics endpoint.
    Content-Type: text/plain; version=0.0.4; charset=utf-8
    """
    if PROMETHEUS_AVAILABLE and REGISTRY is not None:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(
            content=generate_latest(REGISTRY).decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )
    # Fallback to in-memory collector
    return Response(
        content=metrics.prometheus_format(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
