"""
Vigil Regime Detector — Multi-vector regime detection extending RegimeEngine.

Outputs structured RegimeVector that modulates signal scoring weights.

Detection flow:
1. Check LRU cache for non-expired entry
2. If miss, check regime_cache DB table
3. If miss, compute via RegimeEngine + additional vectors:
   - Trend slope (linear regression on close)
   - Momentum strength (ROC(14)/ATR)
   - Volatility percentile (20-day rolling)
   - Breadth score (advance/decline proxy)
4. Persist to regime_cache with expires_at = NOW() + 5min
5. Return RegimeVector

Cache results with 5-minute TTL.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import numpy as np

from services.lru_cache import LRUCache, get_di_cache
from services.regime_engine import get_regime_engine, RegimeEngine

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class RegimeVector:
    """Structured regime detection output."""
    symbol: str
    timeframe: str
    regime: str
    confidence: float
    vector: dict[str, float]  # trend_slope, momentum_strength, volatility_percentile, breadth
    factors: dict[str, Any]  # raw factor values
    cached: bool
    computed_at: str


class RegimeDetector:
    """
    Multi-vector regime detection extending the existing RegimeEngine.
    Outputs structured RegimeVector that modulates signal scoring weights.

    All methods are stateless except the LRU cache reference.
    """

    def __init__(
        self,
        pool,
        cache: Optional[LRUCache] = None,
        engine: Optional[RegimeEngine] = None,
    ):
        """
        Initialize the RegimeDetector.

        Args:
            pool: asyncpg connection pool from database.get_pool().
            cache: Optional LRU cache instance. Falls back to singleton.
            engine: Optional RegimeEngine instance. Falls back to singleton.
        """
        self._pool = pool
        self._cache = cache or get_di_cache()
        self._engine = engine or get_regime_engine()

    async def detect_regime(
        self,
        symbol: str,
        timeframe: str,
        ohlcv_data: Optional[list[dict]] = None,
    ) -> RegimeVector:
        """
        Compute regime vector for symbol/timeframe.

        Flow:
        1. Check LRU cache for non-expired entry
        2. If miss, check regime_cache DB table
        3. If miss, compute via RegimeEngine + additional vectors
        4. Persist to regime_cache with expires_at = NOW() + 5min
        5. Return RegimeVector

        Args:
            symbol: Ticker symbol (e.g., "SPY").
            timeframe: Timeframe string (e.g., "1D", "4H").
            ohlcv_data: Optional OHLCV data. If None, fetches from DB.

        Returns:
            RegimeVector with regime classification and factor breakdown.
        """
        # Check LRU cache first
        cache_key = f"regime:{symbol}:{timeframe}"
        cached = self._cache.get(cache_key)
        if cached:
            # FIX 7: Data freshness check — compare latest candle timestamp
            # against cache timestamp. If market data is newer, force recalc.
            if not self._is_cache_stale(cached, ohlcv_data):
                cached["cached"] = True
                return RegimeVector(**cached)

        # Check DB cache
        db_cached = await self._get_cached_regime(symbol, timeframe)
        if db_cached:
            # FIX 7: Same data freshness check for DB cache
            if not self._is_cache_stale(db_cached, ohlcv_data):
                result = RegimeVector(**db_cached)
                # Populate LRU cache
                self._cache.set(cache_key, db_cached, ttl=CACHE_TTL_SECONDS)
                return result

        # Compute fresh regime
        if ohlcv_data is None:
            ohlcv_data = await self._fetch_ohlcv(symbol, timeframe)

        vector = self._compute_regime_vector(symbol, timeframe, ohlcv_data)

        # Persist to DB cache
        await self._persist_regime(symbol, timeframe, vector)

        # Populate LRU cache
        self._cache.set(cache_key, self._vector_to_dict(vector), ttl=CACHE_TTL_SECONDS)

        return vector

    async def get_cached_regime(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[RegimeVector]:
        """
        Get cached regime vector. Checks LRU cache first, then DB.

        Args:
            symbol: Ticker symbol.
            timeframe: Timeframe string.

        Returns:
            RegimeVector if cached, None otherwise.
        """
        # Check LRU cache
        cache_key = f"regime:{symbol}:{timeframe}"
        cached = self._cache.get(cache_key)
        if cached:
            cached["cached"] = True
            return RegimeVector(**cached)

        # Check DB
        db_cached = await self._get_cached_regime(symbol, timeframe)
        if db_cached:
            result = RegimeVector(**db_cached)
            # Populate LRU cache
            self._cache.set(cache_key, db_cached, ttl=CACHE_TTL_SECONDS)
            return result

        return None

    @staticmethod
    def regime_alignment_score(
        signal_type: str,
        regime_vector: dict,
    ) -> float:
        """
        Returns 0-1 alignment score.

        Bullish signals score higher in uptrend regimes.
        Bearish signals score higher in downtrend regimes.
        Neutral signals score based on regime confidence.

        Args:
            signal_type: Signal direction (e.g., "BULLISH", "BEARISH", "VOLUME_SPIKE_UP").
            regime_vector: Dict with regime, confidence, trend_slope.

        Returns:
            Float 0-1 alignment score.
        """
        regime = regime_vector.get("regime", "")
        confidence = regime_vector.get("confidence", 0.5)
        trend_slope = regime_vector.get("trend_slope", 0)

        # Determine signal direction
        is_bullish = any(
            kw in signal_type.upper()
            for kw in ["BULL", "UP", "LONG", "ACCUMULATION", "BREAKOUT"]
        )
        is_bearish = any(
            kw in signal_type.upper()
            for kw in ["BEAR", "DOWN", "SHORT", "DISTRIBUTION", "BREAKDOWN"]
        )

        # Base alignment
        if is_bullish:
            # Bullish signals align with positive trend
            alignment = 0.5 + (trend_slope * 0.5)
        elif is_bearish:
            # Bearish signals align with negative trend
            alignment = 0.5 - (trend_slope * 0.5)
        else:
            # Neutral signals: moderate alignment
            alignment = 0.5

        # Scale by confidence
        alignment = 0.5 + (alignment - 0.5) * confidence

        # Regime-specific adjustments
        if regime == "TRENDING" and (is_bullish or is_bearish):
            alignment = min(1.0, alignment + 0.15)  # Trending favors directional signals
        elif regime == "SIDEWAYS" and not is_bullish and not is_bearish:
            alignment = min(1.0, alignment + 0.10)  # Sideways favors neutral signals
        elif regime == "VOLATILE":
            alignment = max(0.0, alignment - 0.10)  # Volatile reduces all signal confidence

        return round(max(0.0, min(1.0, alignment)), 4)

    # -- Internal methods -----------------------------------------------------

    @staticmethod
    def _is_cache_stale(cached_regime: dict, ohlcv_data: Optional[list[dict]]) -> bool:
        """
        FIX 7: Check if cached regime is stale compared to latest market data.

        Market hours awareness:
        - During US market hours (9:30-16:00 ET), cache TTL is 15 minutes
          because regime can change rapidly with new price data.
        - Outside market hours, cache TTL is 4 hours since no new data arrives.

        Returns True if the cache is stale, forcing recalculation.
        """
        if not ohlcv_data:
            return False  # No data to compare, treat cache as valid

        # Get the latest candle timestamp from OHLCV data
        latest_candle_time = ohlcv_data[-1].get("Date") or ohlcv_data[-1].get("date")
        if latest_candle_time is None:
            return False  # Can't determine freshness

        # Parse candle timestamp (assume ISO format or similar)
        try:
            if isinstance(latest_candle_time, str):
                latest_dt = datetime.fromisoformat(latest_candle_time)
            elif hasattr(latest_candle_time, "isoformat"):
                latest_dt = latest_candle_time
            else:
                return False

            # Get cache timestamp
            cache_time_str = cached_regime.get("computed_at", "")
            if not cache_time_str:
                return True  # No cache time, force recalc

            cache_dt = datetime.fromisoformat(cache_time_str)

            # FIX 7: Check if current time is within US market hours (9:30-16:00 ET)
            now_utc = datetime.now(timezone.utc)
            # ET is UTC-5 (standard) or UTC-4 (DST). Approximate with UTC-4 for safety.
            now_et = now_utc  # Use UTC as proxy; refine if timezone info available
            hour_utc = now_utc.hour
            minute_utc = now_utc.minute
            # US market hours in UTC: 14:30-21:00 (EST, UTC-5) or 13:30-20:00 (EDT, UTC-4)
            # Use the wider window to be safe: 13:30-21:00 UTC covers both
            is_market_hours = (
                (hour_utc == 13 and minute_utc >= 30) or
                (14 <= hour_utc <= 20) or
                (hour_utc == 21 and minute_utc == 0)
            )

            # FIX 7: Set TTL based on market hours
            if is_market_hours:
                ttl_seconds = 15 * 60  # 15 minutes during market hours
            else:
                ttl_seconds = 4 * 3600  # 4 hours outside market hours

            # Check if cache has expired
            cache_age = (now_utc - cache_dt).total_seconds()
            if cache_age > ttl_seconds:
                logger.debug(
                    f"Regime cache expired: age={cache_age:.0f}s > TTL={ttl_seconds}s "
                    f"(market_hours={is_market_hours})"
                )
                return True

            # If market data is newer than cache, cache is stale
            if latest_dt > cache_dt:
                logger.debug(
                    f"Regime cache stale: market data {latest_dt} > cache {cache_dt}"
                )
                return True
        except (ValueError, TypeError) as e:
            logger.warning(f"Cache freshness check failed: {e}")
            return False  # On error, don't invalidate cache

        return False

    async def _get_cached_regime(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[dict]:
        """Fetch regime from DB cache if not expired."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT symbol, timeframe, regime_vector, confidence,
                       computed_at, expires_at
                FROM regime_cache
                WHERE symbol = $1 AND timeframe = $2
                  AND expires_at > NOW()
                """,
                symbol,
                timeframe,
            )
            if row:
                vector = row["regime_vector"]
                return {
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "regime": vector.get("regime", "UNKNOWN"),
                    "confidence": row["confidence"],
                    "vector": vector.get("components", {}),
                    "factors": vector.get("factors", {}),
                    "cached": True,
                    "computed_at": row["computed_at"].isoformat()
                    if row.get("computed_at")
                    else "",
                }
        return None

    async def _fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
    ) -> list[dict]:
        """
        Fetch OHLCV data from alerts table.

        In production, this would query a dedicated ohlcv table.
        For now, returns empty list (caller should provide data).
        """
        # Placeholder: in production, fetch from price data table
        return []

    def _compute_regime_vector(
        self,
        symbol: str,
        timeframe: str,
        ohlcv_data: list[dict],
    ) -> RegimeVector:
        """
        Compute regime vector from OHLCV data.

        Uses RegimeEngine for base classification, then adds:
        - Trend slope (linear regression on close)
        - Momentum strength (ROC(14)/ATR)
        - Volatility percentile (20-day rolling)
        - Breadth score (advance/decline proxy)
        """
        # Use RegimeEngine for base classification if we have enough data
        if ohlcv_data:
            import pandas as pd
            df = pd.DataFrame(ohlcv_data)
            if "Close" in df.columns and len(df) >= 50:
                regime_result = self._engine.classify(df)
                regime = regime_result.regime
                base_confidence = regime_result.confidence
                factors = regime_result.factors
            else:
                regime = "UNKNOWN"
                base_confidence = 0.3
                factors = {"error": "insufficient_data"}
        else:
            regime = "UNKNOWN"
            base_confidence = 0.3
            factors = {"error": "no_data"}

        # Compute additional vectors
        trend_slope = self._compute_trend_slope(ohlcv_data)
        momentum_strength = self._compute_momentum_strength(ohlcv_data)
        volatility_pct = self._compute_volatility_percentile(ohlcv_data)
        breadth_score = self._compute_breadth_score(ohlcv_data)

        vector = {
            "trend_slope": trend_slope,
            "momentum_strength": momentum_strength,
            "volatility_percentile": volatility_pct,
            "breadth": breadth_score,
        }

        computed_at = datetime.now(timezone.utc).isoformat()

        return RegimeVector(
            symbol=symbol,
            timeframe=timeframe,
            regime=regime,
            confidence=round(base_confidence, 4),
            vector=vector,
            factors=factors,
            cached=False,
            computed_at=computed_at,
        )

    @staticmethod
    def _compute_trend_slope(ohlcv_data: list[dict]) -> float:
        """
        Compute trend slope via linear regression on close prices.

        Returns normalized slope (-1 to 1).
        """
        if not ohlcv_data or len(ohlcv_data) < 10:
            return 0.0

        closes = np.array([d.get("Close", 0) for d in ohlcv_data if d.get("Close")])
        if len(closes) < 10:
            return 0.0

        # Linear regression: y = mx + b
        x = np.arange(len(closes))
        coeffs = np.polyfit(x, closes, 1)
        slope = coeffs[0]

        # Normalize by mean price to get relative slope
        mean_price = np.mean(closes)
        if mean_price == 0:
            return 0.0

        normalized_slope = slope / mean_price
        # Clamp to -1 to 1
        return round(max(-1.0, min(1.0, normalized_slope * 100)), 4)

    @staticmethod
    def _compute_momentum_strength(ohlcv_data: list[dict]) -> float:
        """
        Compute momentum strength as ROC(14) / ATR.

        Returns normalized 0-1 score.
        """
        if not ohlcv_data or len(ohlcv_data) < 15:
            return 0.5  # Neutral

        closes = [d.get("Close", 0) for d in ohlcv_data if d.get("Close")]
        highs = [d.get("High", 0) for d in ohlcv_data if d.get("High")]
        lows = [d.get("Low", 0) for d in ohlcv_data if d.get("Low")]

        if len(closes) < 15:
            return 0.5

        # ROC(14)
        roc = (closes[-1] - closes[-15]) / closes[-15] * 100 if closes[-15] else 0

        # ATR(14)
        atr_values = []
        for i in range(1, min(15, len(closes))):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]) if i > 0 else 0,
                abs(lows[i] - closes[i - 1]) if i > 0 else 0,
            )
            atr_values.append(tr)
        atr = sum(atr_values) / len(atr_values) if atr_values else 1

        if atr == 0:
            return 0.5

        # Momentum strength = ROC / ATR (normalized)
        momentum = roc / atr
        # Normalize to 0-1 via sigmoid
        strength = 1 / (1 + math.exp(-momentum))
        return round(strength, 4)

    @staticmethod
    def _compute_volatility_percentile(ohlcv_data: list[dict]) -> float:
        """
        Compute volatility percentile from 20-day rolling ATR.

        Returns 0-1 percentile score.
        """
        if not ohlcv_data or len(ohlcv_data) < 20:
            return 0.5  # Neutral

        # Compute daily ranges
        ranges = []
        for d in ohlcv_data:
            high = d.get("High", 0)
            low = d.get("Low", 0)
            close = d.get("Close", 1)
            if close > 0:
                ranges.append((high - low) / close * 100)

        if len(ranges) < 20:
            return 0.5

        # Current range vs historical
        current = ranges[-1]
        percentile = sum(1 for r in ranges[:-1] if r <= current) / len(ranges)
        return round(percentile, 4)

    @staticmethod
    def _compute_breadth_score(ohlcv_data: list[dict]) -> float:
        """
        Compute breadth score as advance/decline proxy.

        Uses ratio of up days to total days in recent period.
        Returns 0-1 score (0.5 = neutral).
        """
        if not ohlcv_data or len(ohlcv_data) < 10:
            return 0.5

        closes = [d.get("Close", 0) for d in ohlcv_data if d.get("Close")]
        if len(closes) < 10:
            return 0.5

        # Count up days in last 10 periods
        recent = closes[-10:]
        up_days = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
        return round(up_days / (len(recent) - 1), 4)

    async def _persist_regime(
        self,
        symbol: str,
        timeframe: str,
        vector: RegimeVector,
    ) -> None:
        """Persist regime vector to regime_cache table."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=CACHE_TTL_SECONDS)

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO regime_cache (
                    symbol, timeframe, regime_vector, confidence,
                    computed_at, expires_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (symbol, timeframe) DO UPDATE SET
                    regime_vector = EXCLUDED.regime_vector,
                    confidence = EXCLUDED.confidence,
                    computed_at = EXCLUDED.computed_at,
                    expires_at = EXCLUDED.expires_at
                """,
                symbol,
                timeframe,
                {
                    "regime": vector.regime,
                    "components": vector.vector,
                    "factors": vector.factors,
                },
                vector.confidence,
                vector.computed_at,
                expires_at,
            )

    @staticmethod
    def _vector_to_dict(vector: RegimeVector) -> dict:
        """Convert RegimeVector to dict for caching."""
        return {
            "symbol": vector.symbol,
            "timeframe": vector.timeframe,
            "regime": vector.regime,
            "confidence": vector.confidence,
            "vector": vector.vector,
            "factors": vector.factors,
            "cached": vector.cached,
            "computed_at": vector.computed_at,
        }


# Module-level singleton
_detector: Optional[RegimeDetector] = None
_detector_lock = threading.Lock()


def get_regime_detector(pool=None) -> RegimeDetector:
    """Get or create the RegimeDetector singleton."""
    global _detector
    if _detector is None:
        with _detector_lock:
            if _detector is None:
                if pool is None:
                    raise ValueError("pool must be provided for first initialization")
                _detector = RegimeDetector(pool=pool)
    return _detector
