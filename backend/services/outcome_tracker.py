"""
Vigil Outcome Tracker — Signal lifecycle tracking from inception to resolution.

Tracks signal outcomes through a state machine:
  PENDING -> ACTIVE (when entry_price is set)
  ACTIVE -> TARGET_HIT (when high >= target_price)
  ACTIVE -> STOP_HIT (when low <= stop_price)
  ACTIVE -> TIME_EXPIRED (when bars_elapsed > max_bars)
  ACTIVE -> CLOSED (manual close via exit_price)

All operations are idempotent — calling update() with the same data
produces no side effects.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class OutcomeState:
    """Represents the current state of a signal outcome."""
    signal_id: int
    state: str  # PENDING, ACTIVE, TARGET_HIT, STOP_HIT, TIME_EXPIRED, CLOSED
    entry_price: Optional[float]
    exit_price: Optional[float]
    target_price: Optional[float]
    stop_price: Optional[float]
    outcome_pct: Optional[float]
    max_adverse_excursion: Optional[float]
    max_favorable_excursion: Optional[float]
    time_in_trade_bars: Optional[int]
    final_pnl_state: Optional[str]  # WIN, LOSS, BREAKEVEN, UNRESOLVED
    updated_at: str


class OutcomeTracker:
    """
    Tracks signal lifecycle from PENDING through resolution.
    Idempotent: calling update() with the same data produces no side effects.

    Quantitative rationale:
    - Tracking MAE/MFE enables optimal stop/target placement analysis
    - Time-in-trade measurement identifies signal decay patterns
    - State machine ensures consistent outcome classification
    """

    def __init__(self, pool, max_bars: int = 20):
        """
        Initialize the OutcomeTracker.

        Args:
            pool: asyncpg connection pool from database.get_pool().
            max_bars: Maximum bars before signal is considered expired.
                      Default 20 bars (e.g., 20 trading days for daily).
        """
        self._pool = pool
        self._max_bars = max_bars

    async def track_signal(
        self,
        alert_id: int,
        entry_price: float,
        target_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> OutcomeState:
        """
        Create initial outcome record for a new signal.

        Args:
            alert_id: The alert ID to track (references alerts.id).
            entry_price: Price at which the signal was entered.
            target_price: Optional profit target price.
            stop_price: Optional stop-loss price.

        Returns:
            OutcomeState with PENDING state.
        """
        async with self._pool.acquire() as conn:
            # Check if outcome already exists (idempotent)
            existing = await conn.fetchrow(
                "SELECT * FROM signal_outcomes WHERE signal_id = $1",
                alert_id,
            )
            if existing:
                return self._row_to_outcome(existing)

            # Create new outcome record
            row = await conn.fetchrow(
                """
                INSERT INTO signal_outcomes (
                    signal_id, state, entry_price, target_price, stop_price,
                    max_adverse_excursion, max_favorable_excursion
                ) VALUES ($1, 'PENDING', $2, $3, $4, 0, 0)
                RETURNING *
                """,
                alert_id,
                entry_price,
                target_price,
                stop_price,
            )
            return self._row_to_outcome(row)

    async def update_outcomes(self, closed_candle_data: list[dict]) -> int:
        """
        Idempotent update based on closed candles.

        For each active signal, checks if the candle data triggers a state
        transition (target hit, stop hit, time expired).

        Args:
            closed_candle_data: List of dicts with keys:
                - signal_id: int
                - high: float (candle high)
                - low: float (candle low)
                - close: float (candle close)
                - bars_elapsed: int (optional, bars since entry)

        Returns:
            Count of signals updated.
        """
        updated_count = 0

        for candle in closed_candle_data:
            signal_id = candle.get("signal_id")
            if signal_id is None:
                continue

            high = candle.get("high")
            low = candle.get("low")
            close = candle.get("close")
            bars_elapsed = candle.get("bars_elapsed")

            try:
                result = await self._update_single_outcome(
                    signal_id=signal_id,
                    current_high=high,
                    current_low=low,
                    current_price=close,
                    bars_elapsed=bars_elapsed,
                )
                if result:
                    updated_count += 1
            except Exception as e:
                logger.error(f"Error updating outcome for signal {signal_id}: {e}")

        return updated_count

    async def get_outcome(self, alert_id: int) -> Optional[OutcomeState]:
        """
        Fetch outcome for a specific signal.

        Args:
            alert_id: The alert ID to look up.

        Returns:
            OutcomeState if found, None otherwise.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM signal_outcomes WHERE signal_id = $1",
                alert_id,
            )
            if row:
                return self._row_to_outcome(row)
        return None

    async def get_active_outcomes(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> list[OutcomeState]:
        """
        Fetch all unresolved signals, optionally filtered by symbol/timeframe.

        Args:
            symbol: Optional ticker filter.
            timeframe: Optional timeframe filter.

        Returns:
            List of OutcomeState for active signals.
        """
        async with self._pool.acquire() as conn:
            if symbol:
                rows = await conn.fetch(
                    """
                    SELECT so.* FROM signal_outcomes so
                    JOIN alerts a ON a.id = so.signal_id
                    WHERE so.state IN ('PENDING', 'ACTIVE')
                      AND a.ticker = $1
                    ORDER BY so.updated_at DESC
                    """,
                    symbol,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM signal_outcomes
                    WHERE state IN ('PENDING', 'ACTIVE')
                    ORDER BY updated_at DESC
                    """
                )
            return [self._row_to_outcome(r) for r in rows]

    # -- Internal methods -----------------------------------------------------

    async def _update_single_outcome(
        self,
        signal_id: int,
        current_price: Optional[float] = None,
        current_high: Optional[float] = None,
        current_low: Optional[float] = None,
        bars_elapsed: Optional[int] = None,
    ) -> Optional[OutcomeState]:
        """
        Update a single outcome based on current market data.

        State machine transitions:
        - PENDING -> ACTIVE (when price data arrives)
        - ACTIVE -> TARGET_HIT (when high >= target_price)
        - ACTIVE -> STOP_HIT (when low <= stop_price)
        - ACTIVE -> TIME_EXPIRED (when bars_elapsed > max_bars)

        Returns updated OutcomeState or None if signal not found.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM signal_outcomes WHERE signal_id = $1",
                signal_id,
            )
            if not row:
                return None

            state = row["state"]
            if state in ("TARGET_HIT", "STOP_HIT", "TIME_EXPIRED", "CLOSED"):
                return self._row_to_outcome(row)  # Already resolved

            entry_price = row["entry_price"]
            target_price = row["target_price"]
            stop_price = row["stop_price"]
            max_adverse = row["max_adverse_excursion"] or 0
            max_favorable = row["max_favorable_excursion"] or 0

            # Update MAE/MFE
            if current_price and entry_price:
                excursion = ((current_price - entry_price) / entry_price) * 100
                if excursion < max_adverse:
                    max_adverse = excursion
                if excursion > max_favorable:
                    max_favorable = excursion

            # Determine new state
            new_state = state
            final_pnl = row["final_pnl_state"]
            exit_price = row["exit_price"]
            outcome_pct = row["outcome_pct"]

            # Transition PENDING -> ACTIVE
            if state == "PENDING" and current_price:
                new_state = "ACTIVE"

            # Check for target hit (bullish: high >= target, bearish: low <= target)
            if state == "ACTIVE" and target_price and current_high:
                if current_high >= target_price:
                    new_state = "TARGET_HIT"
                    exit_price = target_price
                    outcome_pct = ((target_price - entry_price) / entry_price) * 100
                    final_pnl = "WIN" if outcome_pct > 0 else "LOSS"

            # Check for stop hit
            if state == "ACTIVE" and stop_price and current_low:
                if current_low <= stop_price:
                    new_state = "STOP_HIT"
                    exit_price = stop_price
                    outcome_pct = ((stop_price - entry_price) / entry_price) * 100
                    final_pnl = "LOSS" if outcome_pct < 0 else "WIN"

            # Check for time expiry
            if state == "ACTIVE" and bars_elapsed and bars_elapsed >= self._max_bars:
                new_state = "TIME_EXPIRED"
                if current_price and entry_price:
                    outcome_pct = ((current_price - entry_price) / entry_price) * 100
                    exit_price = current_price
                    if abs(outcome_pct) < 0.5:
                        final_pnl = "BREAKEVEN"
                    else:
                        final_pnl = "WIN" if outcome_pct > 0 else "LOSS"

            # Update database with optimistic locking on current state
            # WHERE state = $10 prevents race conditions: only one polling cycle
            # can transition from the current state. RETURNING id confirms success.
            resolved_at = datetime.now(timezone.utc) if new_state != state else None
            row_updated = await conn.fetchrow(
                """
                UPDATE signal_outcomes
                SET state = $1,
                    exit_price = $2,
                    outcome_pct = $3,
                    max_adverse_excursion = $4,
                    max_favorable_excursion = $5,
                    time_in_trade_bars = $6,
                    final_pnl_state = $7,
                    resolved_at = COALESCE($8, resolved_at),
                    updated_at = NOW()
                WHERE signal_id = $9 AND state = $10
                RETURNING id
                """,
                new_state,
                exit_price,
                outcome_pct,
                max_adverse,
                max_favorable,
                bars_elapsed,
                final_pnl,
                resolved_at,
                signal_id,
                state,
            )

            # If zero rows affected, another cycle already processed this signal
            if row_updated is None:
                logger.debug(
                    f"Outcome for signal {signal_id} already updated by another cycle "
                    f"(expected state: {state})"
                )
                return None

            # Fetch updated row
            updated_row = await conn.fetchrow(
                "SELECT * FROM signal_outcomes WHERE signal_id = $1",
                signal_id,
            )
            return self._row_to_outcome(updated_row)

    def _row_to_outcome(self, row: Any) -> OutcomeState:
        """Convert a database row to OutcomeState."""
        d = dict(row)
        return OutcomeState(
            signal_id=d["signal_id"],
            state=d["state"],
            entry_price=d.get("entry_price"),
            exit_price=d.get("exit_price"),
            target_price=d.get("target_price"),
            stop_price=d.get("stop_price"),
            outcome_pct=d.get("outcome_pct"),
            max_adverse_excursion=d.get("max_adverse_excursion"),
            max_favorable_excursion=d.get("max_favorable_excursion"),
            time_in_trade_bars=d.get("time_in_trade_bars"),
            final_pnl_state=d.get("final_pnl_state"),
            updated_at=d["updated_at"].isoformat() if d.get("updated_at") else "",
        )


# Module-level singleton
_tracker: Optional[OutcomeTracker] = None
_tracker_lock = threading.Lock()


def get_outcome_tracker(pool=None) -> OutcomeTracker:
    """Get or create the OutcomeTracker singleton."""
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                if pool is None:
                    raise ValueError("pool must be provided for first initialization")
                _tracker = OutcomeTracker(pool=pool)
    return _tracker
