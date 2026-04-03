"""
Vigil Database Layer — Dual-Pool Architecture
==============================================

This module manages TWO connection pools to PostgreSQL:

1. ASYNCG POOL (Primary — recommended for Neon serverless)
   - Functions: get_pool(), close_pool(), get_prepared_statement()
   - Async, modern, optimized for Neon's serverless wake-up behavior.
   - Prepared statement caching reduces repeated query overhead.
   - All NEW code should use this pool.

2. PSYCOPG2 POOL (Legacy — kept for backward compatibility)
   - Functions: get_conn(), get_db_cursor()
   - Synchronous, thread-based pool. Used by most existing functions.
   - DEPRECATED: These functions emit a runtime warning on first use.
   - Migrate callers to asyncpg equivalents when feasible.

LEGACY PSYCOPG2 FUNCTIONS (all use get_db_cursor or get_conn internally):
   init_db, add_to_watchlist, remove_from_watchlist, get_watchlist,
   get_recent_alert_for_ticker, get_recent_alert_by_action, get_latest_regime,
   save_alert, get_alerts, evaluate_outcomes, get_system_metrics,
   save_backtest_run, save_backtest_results, get_backtest_runs,
   get_backtest_results, save_correlation_matrix, get_latest_correlation

ASYNC ASYNCG FUNCTIONS:
   get_pool, close_pool, get_prepared_statement, _parse_neon_url,
   _retry_on_disconnect

MIGRATION NOTE:
   When migrating a function from psycopg2 to asyncpg, replace:
     with get_db_cursor() as cursor:
         cursor.execute("SELECT ...", (param,))
         rows = cursor.fetchall()
   With:
       pool = await get_pool()
       async with pool.acquire() as conn:
           rows = await conn.fetch("SELECT ...", param)
"""

import os
import json
import threading
import asyncio
import time
import logging
import warnings
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as psycopg2_pool
from psycopg2.extras import Json, RealDictCursor

import asyncpg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Legacy psycopg2 pool (kept for backward compatibility)
# ---------------------------------------------------------------------------
_pool = None
_pool_lock = threading.Lock()

# ---------------------------------------------------------------------------
# asyncpg connection pool (Neon-optimized)
# ---------------------------------------------------------------------------
_async_pool: asyncpg.Pool | None = None
_async_pool_lock = asyncio.Lock()

# Prepared statement cache: {name: str} -> SQL query string
_prepared_statements: dict[str, str] = {}

# Connection retry configuration for Neon serverless wake-up
NEON_RETRY_ATTEMPTS = 3
NEON_RETRY_BACKOFF_BASE = 1.0  # seconds: 1s, 2s, 4s
NEON_CONNECTION_TIMEOUT = 30.0  # seconds
NEON_STATEMENT_TIMEOUT = 10.0  # seconds
NEON_POOL_MIN_SIZE = 5
NEON_POOL_MAX_SIZE = 20


# ---------------------------------------------------------------------------
# Deprecation tracking for legacy psycopg2 pool
# ---------------------------------------------------------------------------
_legacy_pool_warning_emitted = False


def _warn_legacy_pool_usage():
    """Emit a one-time deprecation warning when the legacy psycopg2 pool is used."""
    global _legacy_pool_warning_emitted
    if not _legacy_pool_warning_emitted:
        _legacy_pool_warning_emitted = True
        warnings.warn(
            "Using legacy psycopg2 database pool (get_conn/get_db_cursor). "
            "Consider migrating to asyncpg via get_pool() for Neon serverless compatibility.",
            DeprecationWarning,
            stacklevel=3,
        )
        logger.warning(
            "Legacy psycopg2 pool accessed — migrate to asyncpg get_pool() when possible"
        )


def get_conn():
    """
    Legacy psycopg2 connection from pool. Kept for backward compatibility.

    DEPRECATED: Prefer asyncpg get_pool() for new code.
    This function emits a one-time deprecation warning on first use.
    """
    _warn_legacy_pool_usage()
    global _pool
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("No DATABASE_URL found")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    if _pool is None:
        with _pool_lock:
            if _pool is None:  # Double-check after acquiring lock
                try:
                    # Create a pool with 1 min and 10 max connections
                    _pool = psycopg2_pool.ThreadedConnectionPool(1, 10, db_url)
                    logger.info("Database connection pool initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize connection pool: {e}")
                    return psycopg2.connect(db_url)

    return _pool.getconn()


@contextmanager
def get_db_cursor():
    """
    Legacy psycopg2 cursor context manager. Kept for backward compatibility.

    DEPRECATED: Prefer asyncpg pool.acquire() for new code.
    This function emits a one-time deprecation warning on first use.
    """
    global _pool
    # Warning is emitted by get_conn() — no need to duplicate here
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        if _pool:
            _pool.putconn(conn)
        else:
            conn.close()


# ---------------------------------------------------------------------------
# asyncpg Pool Management (Neon-optimized)
# ---------------------------------------------------------------------------

def _parse_neon_url(db_url: str) -> str:
    """Normalize DATABASE_URL for asyncpg compatibility."""
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return db_url


async def _retry_on_disconnect(coro, max_attempts: int = NEON_RETRY_ATTEMPTS):
    """
    Retry a coroutine on connection errors with exponential backoff.
    Handles Neon's serverless wake-up behavior.
    """
    last_exception = None
    for attempt in range(max_attempts):
        try:
            return await coro
        except (
            asyncpg.exceptions.ConnectionDoesNotExistError,
            asyncpg.exceptions.InterfaceError,
            ConnectionError,
            OSError,
        ) as e:
            last_exception = e
            backoff = NEON_RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                f"Connection attempt {attempt + 1}/{max_attempts} failed: {e}. "
                f"Retrying in {backoff}s..."
            )
            await asyncio.sleep(backoff)
    raise last_exception


async def get_pool() -> asyncpg.Pool:
    """
    Get or create the asyncpg connection pool for Neon PostgreSQL.

    Configuration:
    - min_size=5, max_size=20 connections
    - 30s connection timeout (handles Neon wake-up)
    - 10s statement timeout
    - Automatic retry on connection loss
    """
    global _async_pool

    if _async_pool is None:
        async with _async_pool_lock:
            if _async_pool is None:
                db_url = _parse_neon_url(os.environ.get("DATABASE_URL", ""))
                if not db_url:
                    raise Exception("No DATABASE_URL found")

                logger.info(
                    f"Creating asyncpg pool: min_size={NEON_POOL_MIN_SIZE}, "
                    f"max_size={NEON_POOL_MAX_SIZE}, "
                    f"connect_timeout={NEON_CONNECTION_TIMEOUT}s"
                )

                async def _create_pool():
                    return await asyncpg.create_pool(
                        dsn=db_url,
                        min_size=NEON_POOL_MIN_SIZE,
                        max_size=NEON_POOL_MAX_SIZE,
                        command_timeout=NEON_STATEMENT_TIMEOUT,
                        max_inactive_connection_lifetime=300,  # 5 min
                        server_settings={
                            "statement_timeout": str(int(NEON_STATEMENT_TIMEOUT * 1000)),
                        },
                    )

                _async_pool = await _retry_on_disconnect(_create_pool)
                logger.info("asyncpg connection pool initialized successfully")

    return _async_pool


async def close_pool():
    """Gracefully close the asyncpg connection pool."""
    global _async_pool
    if _async_pool is not None:
        await _async_pool.close()
        _async_pool = None
        logger.info("asyncpg connection pool closed")


async def get_prepared_statement(pool: asyncpg.Pool, name: str, query: str):
    """
    Get or create a prepared statement, caching it for reuse.

    Prepared statements reduce parsing/planning overhead on repeated queries,
    which is especially beneficial on Neon where connection wake-up adds latency.

    Args:
        pool: The asyncpg connection pool
        name: Unique identifier for the prepared statement
        query: The SQL query to prepare

    Returns:
        asyncpg.PreparedStatement ready for execution
    """
    if name not in _prepared_statements:
        _prepared_statements[name] = query

    async with pool.acquire() as conn:
        return await conn.prepare(_prepared_statements[name])


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_db():
    """Initializes tables for alerts and watchlist."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                ticker TEXT,
                date TEXT,
                signal_type TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(ticker, date, signal_type)
            )
        """)
        for col, typedef in [
            ("volume_ratio", "REAL"), ("change_pct", "REAL"), ("state", "TEXT"),
            ("outcome_pct", "REAL"), ("outcome_days", "INTEGER"), ("outcome_result", "TEXT"),
            ("max_adverse_excursion", "REAL"), ("max_favorable_excursion", "REAL"),
            ("trap_conviction", "REAL"), ("trap_type", "TEXT"), ("trap_reasons", "TEXT"),
            ("accum_conviction", "REAL"), ("accum_days", "INTEGER"), ("accum_price_range_pct", "REAL"),
            ("mtf_weekly", "TEXT"), ("mtf_daily", "TEXT"), ("mtf_recent", "TEXT"), ("mtf_alignment", "TEXT"),
            ("signal_combination", "TEXT"), ("edge_score", "REAL"), ("days_in_state", "INTEGER"),
            ("adx_strength", "REAL"), ("momentum_score", "REAL"), ("volatility_desc", "TEXT"),
            ("sector_gate", "TEXT"), ("prev_state", "TEXT"), ("regime", "TEXT"), ("action", "TEXT"), ("summary", "TEXT")
        ]:
            cursor.execute(f"ALTER TABLE alerts ADD COLUMN IF NOT EXISTS {col} {typedef}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker TEXT PRIMARY KEY,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Optimization: Add indices for high-speed dashboard queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_ticker_date ON alerts(ticker, date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_action ON alerts(action);")

        # Phase 2: Alert delivery tracking and deduplication tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_deliveries (
                id SERIAL PRIMARY KEY, alert_id INTEGER, channel TEXT,
                status TEXT, error TEXT, sent_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_dedup (
                fingerprint TEXT PRIMARY KEY, alert_id INTEGER, expires_at TIMESTAMPTZ
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_deliveries_ch ON alert_deliveries(channel, sent_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dedup_exp ON alert_dedup(expires_at)")

        # Phase 3: Backtesting infrastructure tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id SERIAL PRIMARY KEY,
                name TEXT,
                config JSONB,
                start_date TEXT,
                end_date TEXT,
                tickers TEXT[],
                status TEXT DEFAULT 'completed',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id SERIAL PRIMARY KEY,
                run_id INTEGER REFERENCES backtest_runs(id),
                ticker TEXT,
                entry_date TEXT,
                entry_price REAL,
                exit_date TEXT,
                exit_price REAL,
                pnl REAL,
                slippage REAL,
                commission REAL,
                edge_score REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_metrics (
                id SERIAL PRIMARY KEY,
                run_id INTEGER REFERENCES backtest_runs(id),
                sharpe REAL,
                sortino REAL,
                calmar REAL,
                max_drawdown REAL,
                win_rate REAL,
                profit_factor REAL,
                total_trades INTEGER,
                avg_win_pct REAL,
                avg_loss_pct REAL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_results_run ON backtest_results(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_metrics_run ON backtest_metrics(run_id)")

        # Phase 4: Correlation matrix storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS correlation_matrix (
                id SERIAL PRIMARY KEY,
                computed_at TIMESTAMPTZ DEFAULT NOW(),
                tickers TEXT[],
                matrix JSONB,
                period TEXT,
                method TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_corr_computed ON correlation_matrix(computed_at DESC)")
    logger.info("Database initialized and optimized.")


# ---------------------------------------------------------------------------
# Watchlist Operations
# ---------------------------------------------------------------------------

def add_to_watchlist(ticker):
    with get_db_cursor() as cursor:
        cursor.execute("INSERT INTO watchlist (ticker) VALUES (%s) ON CONFLICT DO NOTHING", (ticker.upper(),))


def remove_from_watchlist(ticker):
    with get_db_cursor() as cursor:
        cursor.execute("DELETE FROM watchlist WHERE ticker = %s", (ticker.upper(),))


def get_watchlist():
    with get_db_cursor() as cursor:
        cursor.execute("SELECT ticker FROM watchlist ORDER BY ticker")
        rows = cursor.fetchall()
        return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Alert Operations
# ---------------------------------------------------------------------------

def get_recent_alert_for_ticker(ticker, signal_type, days=7):
    """Returns most recent alert of given type for ticker within N days, or None."""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, date, accum_conviction FROM alerts
            WHERE ticker = %s AND signal_type = %s AND date >= %s
            ORDER BY date DESC LIMIT 1
        """, (ticker, signal_type, cutoff))
        res = cursor.fetchone()
        return dict(res) if res else None


def get_recent_alert_by_action(ticker, action, days=2):
    """Checks if an alert with a specific action was generated recently."""
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=days)
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id FROM alerts
            WHERE ticker = %s AND action = %s AND created_at >= %s
            ORDER BY created_at DESC LIMIT 1
        """, (ticker, action, cutoff))
        return cursor.fetchone() is not None


def get_latest_regime():
    """Returns the regime from the most recent alert in the database."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT regime FROM alerts WHERE regime IS NOT NULL ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        return row['regime'] if row else None


def save_alert(ticker, date, volume_ratio, change_pct, signal_type, state,
               trap_conviction=None, trap_type=None, trap_reasons=None,
               accum_conviction=None, accum_days=None, accum_price_range_pct=None,
               mtf_weekly=None, mtf_daily=None, mtf_recent=None, mtf_alignment=None,
               signal_combination=None, edge_score=None, days_in_state=None,
               adx_strength=None, momentum_score=None, volatility_desc=None, sector_gate=None,
               prev_state=None, regime=None, action=None, summary=None):
    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO alerts (
                ticker, date, volume_ratio, change_pct, signal_type, state,
                trap_conviction, trap_type, trap_reasons,
                accum_conviction, accum_days, accum_price_range_pct,
                mtf_weekly, mtf_daily, mtf_recent, mtf_alignment,
                signal_combination, edge_score, days_in_state, 
                adx_strength, momentum_score, volatility_desc, sector_gate,
                prev_state, regime, action, summary
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (ticker, date, signal_type) DO NOTHING
        """, (
            ticker, str(date),
            float(volume_ratio) if volume_ratio is not None else None,
            float(change_pct)   if change_pct   is not None else None,
            signal_type, state,
            trap_conviction, trap_type,
            json.dumps(trap_reasons) if trap_reasons else None,
            accum_conviction, accum_days, accum_price_range_pct,
            mtf_weekly, mtf_daily, mtf_recent, mtf_alignment,
            signal_combination,
            float(edge_score)     if edge_score     is not None else None,
            int(days_in_state)    if days_in_state  is not None else None,
            float(adx_strength)   if adx_strength   is not None else None,
            float(momentum_score) if momentum_score is not None else None,
            volatility_desc, sector_gate,
            prev_state, regime, action, summary
        ))


def get_alerts(ticker=None, signal_type=None, state=None, limit=50, offset=0):
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

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += " ORDER BY date DESC, created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        return cursor.fetchall()


# ---------------------------------------------------------------------------
# Outcome Evaluation
# ---------------------------------------------------------------------------

def evaluate_outcomes():
    import yfinance as yf
    from datetime import datetime, timedelta

    # Use the context manager to prevent leaks
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id, ticker, date, signal_type FROM alerts WHERE outcome_result IS NULL")
        pending = cursor.fetchall()

    for row in pending:
        alert_id, ticker, date_str, signal_type = row['id'], row['ticker'], row['date'], row['signal_type']
        alert_date = datetime.strptime(date_str, "%Y-%m-%d")
        eval_days  = 10 if signal_type == "ACCUMULATION_DETECTED" else 5
        eval_date  = alert_date + timedelta(days=eval_days)
        if eval_date >= datetime.now():
            continue
        try:
            logger.info(f"Evaluating outcome for {ticker} from {date_str}")
            tk = yf.Ticker(ticker)
            history = tk.history(start=date_str, end=eval_date.strftime("%Y-%m-%d"))
            if len(history) < 2:
                logger.warning(f"Insufficient history to evaluate {ticker} on {date_str}")
                continue
            entry_price = float(history["Close"].iloc[0])
            exit_price  = float(history["Close"].iloc[-1])
            outcome_pct = (exit_price - entry_price) / entry_price * 100
            days = len(history)
            
            # Institutional MAE/MFE Calculation
            lows = history["Low"].astype(float)
            highs = history["High"].astype(float)
            mae = ((lows.min() - entry_price) / entry_price) * 100
            mfe = ((highs.max() - entry_price) / entry_price) * 100

            if signal_type == "ACCUMULATION_DETECTED":
                result = "WIN" if abs(outcome_pct) > 5.0 else "LOSS"
            elif signal_type == "VOLUME_SPIKE_UP":
                result = "WIN" if outcome_pct > 1.0 else "LOSS"
            else:
                result = "WIN" if outcome_pct < -1.0 else "LOSS"
            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE alerts SET outcome_pct = %s, outcome_days = %s, outcome_result = %s,
                                      max_adverse_excursion = %s, max_favorable_excursion = %s
                    WHERE id = %s
                """, (float(round(outcome_pct, 2)), int(days), result, 
                      float(round(mae, 2)), float(round(mfe, 2)), alert_id))
        except Exception as e:
            logger.error(f"Outcome eval error for {ticker}: {e}")


# ---------------------------------------------------------------------------
# System Metrics
# ---------------------------------------------------------------------------

def get_system_metrics():
    """Calculates Institutional Performance Metrics (Sharpe, Profit Factor)."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT outcome_pct, signal_type FROM alerts WHERE outcome_result IS NOT NULL")
        rows = cursor.fetchall()
        returns = [r[0] for r in rows]
        
        # Win rate by signal type
        by_type = {}
        for ret, s_type in rows:
            if s_type not in by_type: by_type[s_type] = []
            by_type[s_type].append(1 if ret > 0 else 0)
        
        win_rates_by_type = {k: round(sum(v)/len(v)*100, 1) for k, v in by_type.items() if v}

    if not returns:
        return {"sharpe": 0, "profit_factor": 0, "win_rate": 0}

    import numpy as np
    wins = [r for r in returns if r > 0]
    losses = [abs(r) for r in returns if r <= 0]
    
    win_rate = (len(wins) / len(returns)) * 100
    profit_factor = sum(wins) / sum(losses) if losses else sum(wins)
    
    # Annualized Sharpe (assuming 5-day hold periods)
    avg_ret = np.mean(returns)
    std_ret = np.std(returns)
    sharpe = (avg_ret / std_ret) * np.sqrt(252/5) if std_ret != 0 else 0

    return {
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "sharpe": round(sharpe, 2),
        "total_trades": len(returns),
        "win_rates_by_type": win_rates_by_type
    }


# ---------------------------------------------------------------------------
# Phase 3: Backtest persistence helpers
# ---------------------------------------------------------------------------

def save_backtest_run(name, config, start_date, end_date, tickers, status="completed"):
    """Insert a backtest run record and return its id."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO backtest_runs (name, config, start_date, end_date, tickers, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, json.dumps(config), start_date, end_date, tickers, status))
        row = cursor.fetchone()
        return row[0] if row else None


def save_backtest_results(run_id, results, metrics):
    """Persist individual trade results and aggregate metrics for a backtest run."""
    with get_db_cursor() as cursor:
        for trade in results:
            cursor.execute("""
                INSERT INTO backtest_results
                    (run_id, ticker, entry_date, entry_price, exit_date, exit_price,
                     pnl, slippage, commission, edge_score)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                run_id,
                trade.get("ticker"),
                trade.get("entry_date"),
                trade.get("entry_price"),
                trade.get("exit_date"),
                trade.get("exit_price"),
                trade.get("pnl"),
                trade.get("slippage"),
                trade.get("commission"),
                trade.get("edge_score"),
            ))
        cursor.execute("""
            INSERT INTO backtest_metrics
                (run_id, sharpe, sortino, calmar, max_drawdown, win_rate,
                 profit_factor, total_trades, avg_win_pct, avg_loss_pct)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            run_id,
            metrics.get("sharpe"),
            metrics.get("sortino"),
            metrics.get("calmar"),
            metrics.get("max_drawdown"),
            metrics.get("win_rate"),
            metrics.get("profit_factor"),
            metrics.get("total_trades"),
            metrics.get("avg_win_pct"),
            metrics.get("avg_loss_pct"),
        ))


def get_backtest_runs(limit=50):
    """List recent backtest runs."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, name, start_date, end_date, tickers, status, created_at
            FROM backtest_runs ORDER BY created_at DESC LIMIT %s
        """, (limit,))
        rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "start_date": r[2],
                "end_date": r[3],
                "tickers": r[4],
                "status": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ]


def get_backtest_results(run_id):
    """Get trade results and metrics for a specific backtest run."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, ticker, entry_date, entry_price, exit_date, exit_price,
                   pnl, slippage, commission, edge_score
            FROM backtest_results WHERE run_id = %s ORDER BY id
        """, (run_id,))
        trades = [
            {
                "id": r[0],
                "ticker": r[1],
                "entry_date": r[2],
                "entry_price": r[3],
                "exit_date": r[4],
                "exit_price": r[5],
                "pnl": r[6],
                "slippage": r[7],
                "commission": r[8],
                "edge_score": r[9],
            }
            for r in cursor.fetchall()
        ]
        cursor.execute("""
            SELECT sharpe, sortino, calmar, max_drawdown, win_rate,
                   profit_factor, total_trades, avg_win_pct, avg_loss_pct
            FROM backtest_metrics WHERE run_id = %s LIMIT 1
        """, (run_id,))
        row = cursor.fetchone()
        metrics = {
            "sharpe": row[0],
            "sortino": row[1],
            "calmar": row[2],
            "max_drawdown": row[3],
            "win_rate": row[4],
            "profit_factor": row[5],
            "total_trades": row[6],
            "avg_win_pct": row[7],
            "avg_loss_pct": row[8],
        } if row else {}
        return {"trades": trades, "metrics": metrics}


# ---------------------------------------------------------------------------
# Phase 4: Correlation matrix persistence
# ---------------------------------------------------------------------------

def save_correlation_matrix(tickers, matrix, period, method):
    """Persist a computed correlation matrix."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO correlation_matrix (tickers, matrix, period, method)
            VALUES (%s, %s, %s, %s)
        """, (tickers, Json(matrix), period, method))


def get_latest_correlation():
    """Get the most recent correlation matrix."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, tickers, matrix, period, method, computed_at
            FROM correlation_matrix ORDER BY computed_at DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "tickers": row[1],
            "matrix": row[2],
            "period": row[3],
            "method": row[4],
            "computed_at": row[5].isoformat() if row[5] else None,
        }
