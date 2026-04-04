"""
Vigil Explainability Engine — Deterministic explainability layer.

For each scored signal, outputs:
- Trigger conditions (what caused the signal)
- Contributing factor weights (numeric breakdown)
- Regime impact (how regime modulated the score)
- Explicit reasoning (human-readable string)

All output is strict JSON serializable with no dynamic keys.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExplainabilityResult:
    """Result of signal explainability analysis."""
    signal_id: int
    score: int
    breakdown: dict[str, Any]
    human_readable: str
    regime_impact: dict[str, Any]
    generated_at: str


class ExplainabilityEngine:
    """
    Deterministic explainability layer.
    For each scored signal, outputs structured breakdown with reasoning.

    All methods are stateless — no class-level mutable state.
    """

    def __init__(self, pool):
        """
        Initialize the ExplainabilityEngine.

        Args:
            pool: asyncpg connection pool from database.get_pool().
        """
        self._pool = pool

    async def explain_signal(
        self,
        alert_id: int,
        score_data: Optional[dict] = None,
        regime_vector: Optional[dict] = None,
    ) -> ExplainabilityResult:
        """
        Return machine-readable and human-readable breakdown of a signal's score.

        Flow:
        1. Fetch signal_scores record
        2. Fetch original alert record
        3. Fetch regime_cache entry
        4. Compose breakdown JSON with all factor contributions
        5. Generate human-readable reasoning string
        6. Return ExplainabilityResult

        Args:
            alert_id: The alert ID to explain.
            score_data: Optional pre-computed score data.
            regime_vector: Optional pre-computed regime vector.

        Returns:
            ExplainabilityResult with full breakdown.
        """
        # Fetch score data if not provided
        if score_data is None:
            score_data = await self._fetch_score(alert_id)

        # Fetch alert data
        alert = await self._fetch_alert(alert_id)
        if alert is None:
            raise ValueError(f"Alert {alert_id} not found")

        # Fetch regime data if not provided
        if regime_vector is None:
            regime_vector = await self._fetch_regime(alert.get("ticker"))

        # Build breakdown
        breakdown = self._build_breakdown(alert, score_data, regime_vector)

        # Build regime impact
        regime_impact = self._build_regime_impact(alert, score_data, regime_vector)

        # Generate human-readable reasoning
        human_readable = self._generate_reasoning(alert, score_data, regime_vector)

        generated_at = datetime.now(timezone.utc).isoformat()

        return ExplainabilityResult(
            signal_id=alert_id,
            score=score_data.get("score", 0) if score_data else 0,
            breakdown=breakdown,
            human_readable=human_readable,
            regime_impact=regime_impact,
            generated_at=generated_at,
        )

    @staticmethod
    def format_for_ui(explainability_data: dict) -> dict:
        """
        Transform explainability data to UI-friendly format.

        Adds labels, colors, and progress bar values.

        Args:
            explainability_data: Raw explainability breakdown dict.

        Returns:
            UI-friendly dict with labels, colors, and progress values.
        """
        factors = explainability_data.get("factors", {})
        ui_factors = {}

        color_map = {
            "hit_rate": {"label": "Historical Win Rate", "color": "#3B82F6"},
            "regime": {"label": "Regime Alignment", "color": "#10B981"},
            "volatility": {"label": "Volatility Score", "color": "#F59E0B"},
            "confluence": {"label": "Technical Confluence", "color": "#8B5CF6"},
        }

        for key, factor in factors.items():
            meta = color_map.get(key, {"label": key, "color": "#6B7280"})
            score = factor.get("score", 0)
            contribution = factor.get("contribution", 0)

            ui_factors[key] = {
                "label": meta["label"],
                "color": meta["color"],
                "score": score,
                "weight": factor.get("weight", 0),
                "contribution": contribution,
                "progress_pct": score,  # For progress bar
                "grade": _score_grade(score),
            }

        return {
            "score": explainability_data.get("score", 0),
            "score_grade": _score_grade(explainability_data.get("score", 0)),
            "factors": ui_factors,
            "regime_impact": explainability_data.get("regime_impact", {}),
            "reasoning": explainability_data.get("human_readable", ""),
        }

    # -- Internal methods -----------------------------------------------------

    async def _fetch_score(self, alert_id: int) -> Optional[dict]:
        """Fetch latest score from signal_scores table."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT score, hit_rate_weight, regime_weight,
                       volatility_weight, confluence_weight,
                       hit_rate_component, regime_component,
                       volatility_component, confluence_component,
                       regime_tag, computed_at
                FROM signal_scores
                WHERE signal_id = $1
                ORDER BY computed_at DESC LIMIT 1
                """,
                alert_id,
            )
            if row:
                return dict(row)
        return None

    async def _fetch_alert(self, alert_id: int) -> Optional[dict]:
        """Fetch alert record."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, ticker, signal_type, regime, adx_strength,
                       momentum_score, mtf_alignment, sector_gate,
                       edge_score, volume_ratio, change_pct, summary
                FROM alerts WHERE id = $1
                """,
                alert_id,
            )
            return dict(row) if row else None

    async def _fetch_regime(self, ticker: Optional[str]) -> Optional[dict]:
        """Fetch cached regime for ticker."""
        if not ticker:
            return None

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT regime_vector, confidence, computed_at
                FROM regime_cache
                WHERE symbol = $1 AND expires_at > NOW()
                ORDER BY computed_at DESC LIMIT 1
                """,
                ticker,
            )
            if row:
                return {
                    "regime_vector": row["regime_vector"],
                    "confidence": row["confidence"],
                    "computed_at": row["computed_at"].isoformat()
                    if row.get("computed_at")
                    else None,
                }
        return None

    def _build_breakdown(
        self,
        alert: dict,
        score_data: Optional[dict],
        regime_vector: Optional[dict],
    ) -> dict[str, Any]:
        """Build machine-readable breakdown dict."""
        # Trigger conditions
        trigger = {
            "signal_type": alert.get("signal_type", "UNKNOWN"),
            "ticker": alert.get("ticker", "UNKNOWN"),
            "volume_ratio": alert.get("volume_ratio"),
            "change_pct": alert.get("change_pct"),
        }

        # Factor weights and scores
        factors = {}
        if score_data:
            factors["hit_rate"] = {
                "weight": score_data.get("hit_rate_weight", 0.30),
                "score": score_data.get("hit_rate_component", 50) or 50,
                "contribution": round(
                    (score_data.get("hit_rate_component", 50) or 50)
                    * score_data.get("hit_rate_weight", 0.30),
                    2,
                ),
            }
            factors["regime"] = {
                "weight": score_data.get("regime_weight", 0.25),
                "score": score_data.get("regime_component", 50) or 50,
                "contribution": round(
                    (score_data.get("regime_component", 50) or 50)
                    * score_data.get("regime_weight", 0.25),
                    2,
                ),
            }
            factors["volatility"] = {
                "weight": score_data.get("volatility_weight", 0.20),
                "score": score_data.get("volatility_component", 50) or 50,
                "contribution": round(
                    (score_data.get("volatility_component", 50) or 50)
                    * score_data.get("volatility_weight", 0.20),
                    2,
                ),
            }
            factors["confluence"] = {
                "weight": score_data.get("confluence_weight", 0.25),
                "score": score_data.get("confluence_component", 50) or 50,
                "contribution": round(
                    (score_data.get("confluence_component", 50) or 50)
                    * score_data.get("confluence_weight", 0.25),
                    2,
                ),
            }
        else:
            # Default factors
            for key in ["hit_rate", "regime", "volatility", "confluence"]:
                factors[key] = {
                    "weight": 0.25,
                    "score": 50,
                    "contribution": 12.5,
                }

        return {
            "trigger": trigger,
            "factors": factors,
            "regime_impact": self._build_regime_impact(alert, score_data, regime_vector),
        }

    def _build_regime_impact(
        self,
        alert: dict,
        score_data: Optional[dict],
        regime_vector: Optional[dict],
    ) -> dict[str, Any]:
        """Build regime impact dict."""
        alert_regime = alert.get("regime", "UNKNOWN")
        current_regime = "UNKNOWN"

        if regime_vector and regime_vector.get("regime_vector"):
            rv = regime_vector["regime_vector"]
            current_regime = rv.get("regime", "UNKNOWN")

        alignment = "MATCH" if alert_regime == current_regime else "MISMATCH"
        bonus = 10 if alignment == "MATCH" else -10

        return {
            "current_regime": current_regime,
            "signal_regime": alert_regime,
            "alignment": alignment,
            "bonus_points": bonus,
            "weight_overrides": {
                "regime_weight": score_data.get("regime_weight", 0.25)
                if score_data
                else 0.25
            },
        }

    def _generate_reasoning(
        self,
        alert: dict,
        score_data: Optional[dict],
        regime_vector: Optional[dict],
    ) -> str:
        """Generate human-readable reasoning string."""
        signal_type = alert.get("signal_type", "UNKNOWN")
        ticker = alert.get("ticker", "UNKNOWN")
        score = score_data.get("score", 0) if score_data else 0
        regime = alert.get("regime", "UNKNOWN")

        parts = [f"Score {score}/100: {signal_type} signal for {ticker}"]

        # Regime alignment
        if regime != "UNKNOWN":
            parts.append(f"in {regime} regime")

        # Hit rate
        if score_data and score_data.get("hit_rate_component"):
            hr = score_data["hit_rate_component"]
            parts.append(f"Historical hit rate {hr:.0f}%")

        # Volatility
        if score_data and score_data.get("volatility_component"):
            vol = score_data["volatility_component"]
            if vol > 70:
                parts.append("High volatility environment")
            elif vol < 30:
                parts.append("Low volatility environment — favorable for entry")
            else:
                parts.append("Moderate volatility — acceptable for entry")

        # Confluence
        if score_data and score_data.get("confluence_component"):
            conf = score_data["confluence_component"]
            aligned_factors = int(conf / 25)
            parts.append(f"{aligned_factors} of 4 technical factors aligned")

        # ADX
        adx = alert.get("adx_strength")
        if adx is not None:
            if adx > 25:
                parts.append(f"Strong trend (ADX {adx:.1f})")
            else:
                parts.append(f"Weak trend (ADX {adx:.1f})")

        # Momentum
        momentum = alert.get("momentum_score")
        if momentum is not None:
            direction = "positive" if momentum > 0 else "negative"
            parts.append(f"{direction.capitalize()} momentum ({momentum:.2f})")

        return ". ".join(parts) + "."


def _score_grade(score: float) -> str:
    """Convert score to letter grade for UI display."""
    if score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 50:
        return "D"
    else:
        return "F"


# Module-level singleton
_engine: Optional[ExplainabilityEngine] = None
_engine_lock = threading.Lock()


def get_explainability_engine(pool=None) -> ExplainabilityEngine:
    """Get or create the ExplainabilityEngine singleton."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                if pool is None:
                    raise ValueError("pool must be provided for first initialization")
                _engine = ExplainabilityEngine(pool=pool)
    return _engine
