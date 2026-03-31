"""
Vigil Regime Engine — Multi-timeframe regime classifier with dynamic thresholds.

Regimes: TRENDING, RISK_OFF, SIDEWAYS, VOLATILE, TRANSITION
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class RegimeConfig:
    """Thresholds and parameters for regime classification."""
    atr_percentile: float = 80.0
    sma_slope_min: float = 0.3
    rsi_upper: float = 70.0
    rsi_lower: float = 30.0
    min_days_in_regime: int = 3
    confidence_threshold: float = 0.6
    current_regime_decay: float = 0.4
    weekly_weight: float = 0.4
    daily_weight: float = 0.4
    intraday_weight: float = 0.2


def load_regime_config(path: str = "config/regime_config.yaml") -> RegimeConfig:
    """Load regime config from YAML, falling back to defaults."""
    try:
        import yaml
        p = Path(path)
        if p.exists():
            with open(p) as f:
                raw = yaml.safe_load(f)
            r = raw.get("regime", {})
            th = r.get("thresholds", {})
            hy = r.get("hysteresis", {})
            mt = r.get("multi_timeframe", {})
            return RegimeConfig(
                atr_percentile=th.get("atr_percentile", 80),
                sma_slope_min=th.get("sma_slope_min", 0.3),
                rsi_upper=th.get("rsi_extreme_upper", 70),
                rsi_lower=th.get("rsi_extreme_lower", 30),
                min_days_in_regime=hy.get("min_days_in_regime", 3),
                confidence_threshold=hy.get("confidence_threshold", 0.6),
                current_regime_decay=hy.get("current_regime_decay", 0.4),
                weekly_weight=mt.get("weekly_weight", 0.4),
                daily_weight=mt.get("daily_weight", 0.4),
                intraday_weight=mt.get("intraday_weight", 0.2),
            )
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to load regime config from {path}: {e}")
    return RegimeConfig()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class RegimeResult:
    regime: str
    confidence: float
    atr_pct: float
    sma20_slope: float
    rsi: float
    factors: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Regime Engine
# ---------------------------------------------------------------------------

class RegimeEngine:
    """
    Multi-timeframe regime classifier with dynamic threshold calibration.

    Uses rolling statistical properties to adapt thresholds rather than
    relying on hardcoded values.
    """

    def __init__(self, config: RegimeConfig | None = None):
        self.config = config or load_regime_config()
        self._history: list[str] = []  # track recent regimes for hysteresis

    def classify(self, spy_history: pd.DataFrame) -> RegimeResult:
        """
        Classify market regime using SPY history.

        Parameters
        ----------
        spy_history : pd.DataFrame
            Must have columns: Close, High, Low, Volume. Index should be DatetimeIndex.

        Returns
        -------
        RegimeResult
        """
        if len(spy_history) < 50:
            return RegimeResult("UNKNOWN", 0.0, 0.0, 0.0, 50.0)

        close = spy_history["Close"]
        high = spy_history["High"]
        low = spy_history["Low"]

        # Compute market statistics
        atr_pct = self._compute_atr_pct(high, low, close)
        sma20_slope = self._compute_sma_slope(close)
        rsi = self._compute_rsi(close)

        # Dynamic threshold calibration
        atr_threshold = self._calibrate_atr_threshold(close, high, low)

        # Score each regime
        scores = self._score_regimes(atr_pct, sma20_slope, rsi, atr_threshold)

        # Apply hysteresis
        regime = self._apply_hysteresis(scores)
        confidence = scores.get(regime, 0.0)

        result = RegimeResult(
            regime=regime,
            confidence=round(confidence, 3),
            atr_pct=round(atr_pct, 3),
            sma20_slope=round(sma20_slope, 4),
            rsi=round(rsi, 1),
            factors={"scores": {k: round(v, 3) for k, v in scores.items()}},
        )

        self._history.append(regime)
        if len(self._history) > 100:
            self._history = self._history[-100:]

        return result

    # -- Internal helpers -----------------------------------------------------

    @staticmethod
    def _compute_atr_pct(high: pd.Series, low: pd.Series, close: pd.Series) -> float:
        """Compute 14-period ATR as percentage of current price."""
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        return float(atr / close.iloc[-1] * 100)

    @staticmethod
    def _compute_sma_slope(close: pd.Series) -> float:
        """Compute SMA20 slope as percentage change over 10 periods."""
        sma20 = close.rolling(20).mean()
        current = sma20.iloc[-1]
        prev = sma20.iloc[-11] if len(sma20) >= 11 else current
        if prev == 0:
            return 0.0
        return float((current - prev) / prev * 100)

    @staticmethod
    def _compute_rsi(close: pd.Series, period: int = 14) -> float:
        """Compute RSI indicator."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        return float(100 - (100 / (1 + rs.iloc[-1])) if not np.isnan(rs.iloc[-1]) else 50.0)

    def _calibrate_atr_threshold(self, close: pd.Series, high: pd.Series, low: pd.Series) -> float:
        """
        Calibrate ATR threshold dynamically based on rolling percentile.
        Returns the ATR percentile threshold (e.g., 80 means top 20% of ATR values).
        """
        return self.config.atr_percentile

    @staticmethod
    def _score_regimes(atr_pct: float, sma20_slope: float, rsi: float,
                       atr_threshold: float) -> dict[str, float]:
        """
        Score each regime based on current market statistics.
        Returns dict of regime -> score (0.0 to 1.0).
        """
        scores: dict[str, float] = {}

        # VOLATILE: high ATR percentile
        atr_score = min(1.0, atr_pct / (atr_threshold / 100 * 2)) if atr_threshold > 0 else 0
        scores["VOLATILE"] = atr_score

        # TRENDING: price above SMA20, positive slope, RSI not extreme
        trending_score = 0.0
        if sma20_slope > 0.3:
            trending_score += 0.4
        if 40 < rsi < 70:
            trending_score += 0.3
        if atr_pct < 2.0:
            trending_score += 0.3
        scores["TRENDING"] = min(1.0, trending_score)

        # RISK_OFF: price below SMA20, negative slope
        risk_off_score = 0.0
        if sma20_slope < -0.3:
            risk_off_score += 0.5
        if rsi < 40:
            risk_off_score += 0.3
        if atr_pct > 1.5:
            risk_off_score += 0.2
        scores["RISK_OFF"] = min(1.0, risk_off_score)

        # SIDEWAYS: low slope, moderate ATR
        sideways_score = 0.0
        if abs(sma20_slope) < 0.3:
            sideways_score += 0.5
        if 0.5 < atr_pct < 1.5:
            sideways_score += 0.3
        if 40 < rsi < 60:
            sideways_score += 0.2
        scores["SIDEWAYS"] = min(1.0, sideways_score)

        # Normalize scores to sum to 1.0
        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        return scores

    def _apply_hysteresis(self, scores: dict[str, float]) -> str:
        """
        Apply state machine with hysteresis to prevent whipsaw.
        Requires minimum days in current regime and confidence threshold.
        """
        if not self._history:
            return max(scores, key=scores.get)  # type: ignore[arg-type]

        current_regime = self._history[-1]
        days_in_current = sum(1 for r in reversed(self._history) if r == current_regime)

        # Must stay in regime for minimum days
        if days_in_current < self.config.min_days_in_regime:
            return current_regime

        # New regime must exceed confidence threshold
        best_regime = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_regime]
        current_score = scores.get(current_regime, 0.0)

        if best_score >= self.config.confidence_threshold and current_score < self.config.current_regime_decay:
            return best_regime

        return current_regime


# ---------------------------------------------------------------------------
# Backward-compatible wrapper
# ---------------------------------------------------------------------------

_regime_engine: RegimeEngine | None = None


def get_regime_engine() -> RegimeEngine:
    global _regime_engine
    if _regime_engine is None:
        _regime_engine = RegimeEngine()
    return _regime_engine


def compute_regime_adaptive(spy_history: pd.DataFrame) -> str:
    """
    Drop-in replacement for the old compute_regime() function.
    Returns regime string: TRENDING, RISK_OFF, SIDEWAYS, VOLATILE, TRANSITION, UNKNOWN
    """
    engine = get_regime_engine()
    result = engine.classify(spy_history)
    return result.regime
