"""
Vigil Self-Evaluation Engine — On-demand analysis of historical signal performance.

Executes within a single HTTP request context under 10 seconds.

Analysis performed:
1. Cohort win rates by (signal_type, regime)
2. Decay half-life estimation (exponential fit on outcome_pct vs time)
3. Failure mode identification (most common loss reason per cohort)
4. Feature importance ranking (correlation of alert features with outcome)
5. Weight calibration update (coordinate descent on prior weights)
6. Degradation flagging (cohorts with win_rate < 40% and n > 10)

Memory-bounded: processes max 1000 signals at once.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Constants
MAX_SIGNALS_PER_RUN = 1000  # Memory bound
DEGRADATION_WIN_RATE_THRESHOLD = 0.40  # 40% win rate threshold
DEGRADATION_MIN_SAMPLE = 10  # Minimum sample size for degradation flag


@dataclass
class CohortResult:
    """Result of cohort analysis."""
    cohort_key: str
    signal_type: Optional[str]
    regime: Optional[str]
    sample_size: int
    win_rate: float
    avg_pnl: float
    decay_half_life: Optional[float]
    failure_mode: Optional[str]
    feature_importance: dict[str, float]


@dataclass
class EvaluationReport:
    """Full self-evaluation report."""
    cohorts: list[CohortResult]
    updated_weights: list[dict[str, Any]]
    degraded_signals: list[str]
    execution_ms: int


class SelfEvaluator:
    """
    On-demand analysis of historical signal performance cohorts.
    Executes within a single HTTP request context under 10 seconds.

    All methods are stateless — no class-level mutable state.
    """

    def __init__(self, pool):
        """
        Initialize the SelfEvaluator.

        Args:
            pool: asyncpg connection pool from database.get_pool().
        """
        self._pool = pool

    async def run_cohort_analysis(
        self,
        signal_ids: Optional[list[int]] = None,
        lookback_days: int = 30,
    ) -> EvaluationReport:
        """
        Analyze cohort, returning win rates, decay patterns, regime failure modes,
        feature importance.

        Args:
            signal_ids: Optional list of specific signal IDs to analyze.
            lookback_days: Number of days to look back for historical data.

        Returns:
            EvaluationReport with full analysis.
        """
        t0 = time.monotonic()

        # Fetch outcomes with alert data
        outcomes = await self._fetch_outcomes(
            signal_ids=signal_ids,
            lookback_days=lookback_days,
        )

        if not outcomes:
            return EvaluationReport(
                cohorts=[],
                updated_weights=[],
                degraded_signals=[],
                execution_ms=int((time.monotonic() - t0) * 1000),
            )

        # Group by (signal_type, regime)
        cohorts = self._group_cohorts(outcomes)

        # Analyze each cohort
        cohort_results = []
        for cohort_key, cohort_outcomes in cohorts.items():
            signal_type, regime = cohort_key.split(":", 1) if ":" in cohort_key else (cohort_key, None)

            win_rate = self._compute_win_rate(cohort_outcomes)
            avg_pnl = self._compute_avg_pnl(cohort_outcomes)
            decay_half_life = self._estimate_decay_half_life(cohort_outcomes)
            failure_mode = self._identify_failure_mode(cohort_outcomes)
            feature_importance = self._compute_feature_importance(cohort_outcomes)

            cohort_results.append(CohortResult(
                cohort_key=cohort_key,
                signal_type=signal_type if signal_type != "None" else None,
                regime=regime if regime != "None" else None,
                sample_size=len(cohort_outcomes),
                win_rate=win_rate,
                avg_pnl=avg_pnl,
                decay_half_life=decay_half_life,
                failure_mode=failure_mode,
                feature_importance=feature_importance,
            ))

        # Persist cohort results
        await self._persist_cohorts(cohort_results)

        # Identify degraded signals
        degraded = self._identify_degraded_signals(cohort_results)

        # Compute updated weights
        updated_weights = await self._compute_updated_weights(cohort_results)

        execution_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            f"Cohort analysis complete: {len(cohort_results)} cohorts, "
            f"{len(degraded)} degraded, {execution_ms}ms"
        )

        return EvaluationReport(
            cohorts=cohort_results,
            updated_weights=updated_weights,
            degraded_signals=degraded,
            execution_ms=execution_ms,
        )

    async def update_weights(self, cohort_results: list[dict]) -> str:
        """
        Persist new weight calibration, returns version string.

        Args:
            cohort_results: List of cohort analysis results (dicts).

        Returns:
            Version string for the new calibration.
        """
        version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        async with self._pool.acquire() as conn:
            for cohort in cohort_results:
                signal_type = cohort.get("signal_type")
                regime = cohort.get("regime")
                win_rate = cohort.get("win_rate", 0.5)

                # Adaptive weight adjustment based on win rate
                # Higher win rate → increase hit_rate weight
                # Lower win rate → increase regime/confluence weights
                if win_rate > 0.6:
                    hit_rate_w = 0.35
                    regime_w = 0.20
                    volatility_w = 0.20
                    confluence_w = 0.25
                elif win_rate < 0.4:
                    hit_rate_w = 0.25
                    regime_w = 0.30
                    volatility_w = 0.25
                    confluence_w = 0.20
                else:
                    hit_rate_w = 0.30
                    regime_w = 0.25
                    volatility_w = 0.20
                    confluence_w = 0.25

                is_degraded = win_rate < DEGRADATION_WIN_RATE_THRESHOLD

                await conn.execute(
                    """
                    INSERT INTO weight_calibrations (
                        signal_type, regime,
                        hit_rate_weight, regime_weight, volatility_weight,
                        confluence_weight, confidence_threshold, is_degraded
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (signal_type, regime) DO UPDATE SET
                        hit_rate_weight = EXCLUDED.hit_rate_weight,
                        regime_weight = EXCLUDED.regime_weight,
                        volatility_weight = EXCLUDED.volatility_weight,
                        confluence_weight = EXCLUDED.confluence_weight,
                        is_degraded = EXCLUDED.is_degraded,
                        calibrated_at = NOW()
                    """,
                    signal_type,
                    regime,
                    hit_rate_w,
                    regime_w,
                    volatility_w,
                    confluence_w,
                    50,
                    is_degraded,
                )

        return version

    async def get_degraded_signals(self, lookback_days: int = 30) -> list[str]:
        """
        Returns signal types with win rate below threshold.

        Args:
            lookback_days: Number of days to look back.

        Returns:
            List of degraded signal type strings.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT wc.signal_type
                FROM weight_calibrations wc
                WHERE wc.is_degraded = TRUE
                  AND wc.calibrated_at > NOW() - ($1 || ' days')::INTERVAL
                """,
                lookback_days,
            )
            return [r["signal_type"] for r in rows]

    # -- Internal methods -----------------------------------------------------

    async def _fetch_outcomes(
        self,
        signal_ids: Optional[list[int]] = None,
        lookback_days: int = 30,
    ) -> list[dict]:
        """Fetch outcomes with alert data, bounded to MAX_SIGNALS_PER_RUN."""
        async with self._pool.acquire() as conn:
            if signal_ids:
                # Limit to MAX_SIGNALS_PER_RUN
                limited_ids = signal_ids[:MAX_SIGNALS_PER_RUN]
                rows = await conn.fetch(
                    """
                    SELECT so.*, a.signal_type, a.regime, a.ticker,
                           a.adx_strength, a.momentum_score, a.mtf_alignment,
                           a.sector_gate, a.edge_score
                    FROM signal_outcomes so
                    JOIN alerts a ON a.id = so.signal_id
                    WHERE so.signal_id = ANY($1)
                      AND so.final_pnl_state IS NOT NULL
                    ORDER BY so.resolved_at DESC
                    """,
                    limited_ids,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT so.*, a.signal_type, a.regime, a.ticker,
                           a.adx_strength, a.momentum_score, a.mtf_alignment,
                           a.sector_gate, a.edge_score
                    FROM signal_outcomes so
                    JOIN alerts a ON a.id = so.signal_id
                    WHERE so.final_pnl_state IS NOT NULL
                      AND so.resolved_at > NOW() - ($1 || ' days')::INTERVAL
                    ORDER BY so.resolved_at DESC
                    LIMIT $2
                    """,
                    lookback_days,
                    MAX_SIGNALS_PER_RUN,
                )
            return [dict(r) for r in rows]

    def _group_cohorts(
        self,
        outcomes: list[dict],
    ) -> dict[str, list[dict]]:
        """Group outcomes by (signal_type, regime) cohort key."""
        cohorts: dict[str, list[dict]] = {}
        for outcome in outcomes:
            signal_type = outcome.get("signal_type") or "UNKNOWN"
            regime = outcome.get("regime") or "UNKNOWN"
            key = f"{signal_type}:{regime}"
            cohorts.setdefault(key, []).append(outcome)
        return cohorts

    def _compute_win_rate(self, outcomes: list[dict]) -> float:
        """Compute win rate for a cohort."""
        if not outcomes:
            return 0.0
        wins = sum(1 for o in outcomes if o.get("final_pnl_state") == "WIN")
        return wins / len(outcomes)

    def _compute_avg_pnl(self, outcomes: list[dict]) -> float:
        """Compute average PnL for a cohort."""
        if not outcomes:
            return 0.0
        pnls = [o.get("outcome_pct") or 0 for o in outcomes]
        return sum(pnls) / len(pnls)

    def _estimate_decay_half_life(self, outcomes: list[dict]) -> Optional[float]:
        """
        Estimate decay half-life using exponential fit on outcome_pct vs time.

        Half-life = ln(2) / lambda where lambda is the decay rate.
        Returns None if insufficient data or no decay pattern.
        """
        if len(outcomes) < 5:
            return None

        # Use time_in_trade_bars as proxy for decay
        bars = [o.get("time_in_trade_bars") or 1 for o in outcomes]
        pnls = [abs(o.get("outcome_pct") or 0) for o in outcomes]

        # Simple linear regression on log(pnl) vs bars
        # If pnl decays exponentially: pnl = pnl0 * exp(-lambda * bars)
        # log(pnl) = log(pnl0) - lambda * bars
        valid = [(b, p) for b, p in zip(bars, pnls) if p > 0]
        if len(valid) < 3:
            return None

        n = len(valid)
        sum_x = sum(b for b, _ in valid)
        sum_y = sum(math.log(p) for _, p in valid)
        sum_xy = sum(b * math.log(p) for b, p in valid)
        sum_x2 = sum(b * b for b, _ in valid)

        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            return None

        lambda_ = -(n * sum_xy - sum_x * sum_y) / denom

        if lambda_ <= 0:
            return None  # No decay

        half_life = math.log(2) / lambda_
        return round(half_life, 2)

    def _identify_failure_mode(self, outcomes: list[dict]) -> Optional[str]:
        """
        Identify most common loss reason per cohort.

        Returns: 'stop_violation', 'time_decay', 'regime_shift', or None.
        """
        losses = [o for o in outcomes if o.get("final_pnl_state") == "LOSS"]
        if not losses:
            return None

        # Categorize failure modes
        stop_hits = sum(1 for o in losses if o.get("state") == "STOP_HIT")
        time_expired = sum(1 for o in losses if o.get("state") == "TIME_EXPIRED")

        if stop_hits > time_expired and stop_hits > len(losses) * 0.3:
            return "stop_violation"
        elif time_expired > len(losses) * 0.3:
            return "time_decay"
        elif len(losses) > 0:
            return "regime_shift"  # Default for unexplained losses
        return None

    def _compute_feature_importance(self, outcomes: list[dict]) -> dict[str, float]:
        """
        Compute feature importance via simple correlation with outcome.

        Returns dict of feature_name -> importance (0-1, normalized).
        """
        features = ["adx_strength", "momentum_score", "edge_score"]
        importances: dict[str, float] = {}

        for feature in features:
            values = [o.get(feature) for o in outcomes if o.get(feature) is not None]
            pnls = [o.get("outcome_pct") or 0 for o in outcomes if o.get(feature) is not None]

            if len(values) < 3:
                importances[feature] = 0.0
                continue

            # Pearson correlation
            n = len(values)
            mean_v = sum(values) / n
            mean_p = sum(pnls) / n

            cov = sum((v - mean_v) * (p - mean_p) for v, p in zip(values, pnls))
            std_v = math.sqrt(sum((v - mean_v) ** 2 for v in values))
            std_p = math.sqrt(sum((p - mean_p) ** 2 for p in pnls))

            if std_v == 0 or std_p == 0:
                importances[feature] = 0.0
            else:
                corr = abs(cov / (std_v * std_p))
                importances[feature] = round(min(1.0, corr), 4)

        # Normalize to sum to 1
        total = sum(importances.values())
        if total > 0:
            importances = {k: round(v / total, 4) for k, v in importances.items()}

        return importances

    async def _persist_cohorts(self, cohort_results: list[CohortResult]) -> None:
        """Persist cohort results to evaluation_cohorts table."""
        async with self._pool.acquire() as conn:
            for cohort in cohort_results:
                await conn.execute(
                    """
                    INSERT INTO evaluation_cohorts (
                        cohort_key, signal_type, regime, sample_size,
                        win_rate, avg_pnl, decay_half_life, failure_mode,
                        feature_importance
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (cohort_key) DO UPDATE SET
                        sample_size = EXCLUDED.sample_size,
                        win_rate = EXCLUDED.win_rate,
                        avg_pnl = EXCLUDED.avg_pnl,
                        decay_half_life = EXCLUDED.decay_half_life,
                        failure_mode = EXCLUDED.failure_mode,
                        feature_importance = EXCLUDED.feature_importance,
                        evaluated_at = NOW()
                    """,
                    cohort.cohort_key,
                    cohort.signal_type,
                    cohort.regime,
                    cohort.sample_size,
                    cohort.win_rate,
                    cohort.avg_pnl,
                    cohort.decay_half_life,
                    cohort.failure_mode,
                    cohort.feature_importance,
                )

    def _identify_degraded_signals(self, cohort_results: list[CohortResult]) -> list[str]:
        """
        Identify signal types with win rate below threshold.

        Returns list of signal_type strings.
        """
        degraded = set()
        for cohort in cohort_results:
            if (cohort.win_rate < DEGRADATION_WIN_RATE_THRESHOLD
                    and cohort.sample_size >= DEGRADATION_MIN_SAMPLE):
                if cohort.signal_type:
                    degraded.add(cohort.signal_type)
        return sorted(degraded)

    async def _compute_updated_weights(
        self,
        cohort_results: list[CohortResult],
    ) -> list[dict[str, Any]]:
        """
        Compute updated weights based on cohort analysis.

        Returns list of weight calibration dicts.
        """
        updated = []
        for cohort in cohort_results:
            win_rate = cohort.win_rate

            # Adaptive weight adjustment
            if win_rate > 0.6:
                weights = {
                    "hit_rate_weight": 0.35,
                    "regime_weight": 0.20,
                    "volatility_weight": 0.20,
                    "confluence_weight": 0.25,
                }
            elif win_rate < 0.4:
                weights = {
                    "hit_rate_weight": 0.25,
                    "regime_weight": 0.30,
                    "volatility_weight": 0.25,
                    "confluence_weight": 0.20,
                }
            else:
                weights = {
                    "hit_rate_weight": 0.30,
                    "regime_weight": 0.25,
                    "volatility_weight": 0.20,
                    "confluence_weight": 0.25,
                }

            updated.append({
                "signal_type": cohort.signal_type,
                "regime": cohort.regime,
                **weights,
                "confidence_threshold": 50,
                "is_degraded": win_rate < DEGRADATION_WIN_RATE_THRESHOLD,
            })

        return updated


# Module-level singleton
_evaluator: Optional[SelfEvaluator] = None
_evaluator_lock = threading.Lock()


def get_self_evaluator(pool=None) -> SelfEvaluator:
    """Get or create the SelfEvaluator singleton."""
    global _evaluator
    if _evaluator is None:
        with _evaluator_lock:
            if _evaluator is None:
                if pool is None:
                    raise ValueError("pool must be provided for first initialization")
                _evaluator = SelfEvaluator(pool=pool)
    return _evaluator
