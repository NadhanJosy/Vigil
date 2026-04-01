"""
Vigil Correlation Engine — Multi-asset correlation analysis.

Phase 4: Computes rolling correlation matrices, stability scoring,
and hierarchical clustering for portfolio risk analytics.
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """Result of correlation matrix computation."""
    tickers: list[str]
    matrix: list[list[float]]  # 2D list for JSON serialization
    period: str  # e.g. "60d"
    method: str  # "pearson", "spearman"
    stability_scores: dict[str, float] = field(default_factory=dict)
    computed_at: str = ""


@dataclass
class ClusterResult:
    """Result of hierarchical clustering."""
    clusters: list[dict]  # [{name, tickers, avg_correlation}]
    linkage_matrix: list[list[float]]  # For dendrogram rendering
    n_clusters: int


class CorrelationEngine:
    """
    Multi-asset correlation analysis engine.

    Computes rolling correlation matrices, stability scores,
    and hierarchical clustering for portfolio construction.
    """

    def __init__(self, lookback_days: int = 60, method: str = "pearson"):
        self.lookback_days = lookback_days
        self.method = method

    def compute_correlation_matrix(
        self, ticker_histories: dict[str, pd.DataFrame]
    ) -> Optional[CorrelationResult]:
        """
        Compute correlation matrix from ticker OHLCV histories.

        Args:
            ticker_histories: Dict mapping ticker -> DataFrame with 'Close' column.

        Returns:
            CorrelationResult or None if insufficient data.
        """
        if len(ticker_histories) < 2:
            logger.warning("Need at least 2 tickers for correlation matrix")
            return None

        # Build returns DataFrame
        returns = {}
        for ticker, hist in ticker_histories.items():
            if len(hist) < 10:
                logger.warning(f"Insufficient data for {ticker} ({len(hist)} rows)")
                continue
            close = hist["Close"].astype(float)
            returns[ticker] = close.pct_change().dropna()

        if len(returns) < 2:
            logger.warning("Insufficient valid tickers for correlation")
            return None

        returns_df = pd.DataFrame(returns).dropna()
        if len(returns_df) < 5:
            logger.warning("Insufficient overlapping returns for correlation")
            return None

        # Compute correlation matrix
        if self.method == "spearman":
            corr_matrix = returns_df.rank().corr(method="pearson")
        else:
            corr_matrix = returns_df.corr(method="pearson")

        tickers = list(corr_matrix.columns)
        matrix = corr_matrix.values.tolist()

        # Compute stability scores (rolling correlation std)
        stability = {}
        for i, t1 in enumerate(tickers):
            for j, t2 in enumerate(tickers):
                if i < j:
                    key = f"{t1}:{t2}"
                    rolling = returns_df[[t1, t2]].rolling(20).corr().dropna()
                    if len(rolling) > 0:
                        # Extract pairwise rolling correlations
                        pairwise = rolling.xs(t1, level=1)[t2] if t1 in rolling.columns.get_level_values(0) else None
                        if pairwise is not None and len(pairwise) > 0:
                            stability[key] = round(float(pairwise.std()), 4)
                        else:
                            stability[key] = 0.0
                    else:
                        stability[key] = 0.0

        return CorrelationResult(
            tickers=tickers,
            matrix=[[round(v, 4) for v in row] for row in matrix],
            period=f"{self.lookback_days}d",
            method=self.method,
            stability_scores=stability,
        )

    def compute_clusters(
        self, corr_result: CorrelationResult, threshold: float = 0.7
    ) -> ClusterResult:
        """
        Hierarchical clustering based on correlation matrix.

        Groups highly correlated assets into clusters.

        Args:
            corr_result: CorrelationResult from compute_correlation_matrix.
            threshold: Correlation threshold for clustering.

        Returns:
            ClusterResult with cluster assignments.
        """
        tickers = corr_result.tickers
        matrix = np.array(corr_result.matrix)
        n = len(tickers)

        # Simple agglomerative clustering (single linkage)
        # Distance = 1 - |correlation|
        distance = 1.0 - np.abs(matrix)
        np.fill_diagonal(distance, 0)

        # Build linkage matrix manually (simplified)
        linkage = []
        clusters = {i: [i] for i in range(n)}
        active = set(range(n))
        cluster_id = n

        while len(active) > 1:
            min_dist = float("inf")
            merge_a, merge_b = -1, -1
            active_list = sorted(active)
            for i in range(len(active_list)):
                for j in range(i + 1, len(active_list)):
                    a, b = active_list[i], active_list[j]
                    # Average linkage
                    dist = np.mean([
                        distance[ca][cb]
                        for ca in clusters.get(a, [a])
                        for cb in clusters.get(b, [b])
                    ])
                    if dist < min_dist:
                        min_dist = dist
                        merge_a, merge_b = a, b

            if merge_a < 0 or merge_b < 0:
                break

            linkage.append([float(merge_a), float(merge_b), round(min_dist, 4), len(clusters.get(merge_a, [merge_a])) + len(clusters.get(merge_b, [merge_b]))])
            new_cluster = list(clusters.get(merge_a, [merge_a])) + list(clusters.get(merge_b, [merge_b]))
            clusters[cluster_id] = new_cluster
            active.discard(merge_a)
            active.discard(merge_b)
            active.add(cluster_id)
            cluster_id += 1

        # Extract final clusters (groups with avg correlation > threshold)
        final_clusters = []
        for cid in active:
            members = clusters.get(cid, [cid])
            ticker_names = [tickers[i] for i in members if i < n]
            if len(ticker_names) >= 1:
                # Compute average intra-cluster correlation
                if len(members) > 1:
                    sub_matrix = matrix[np.ix_(members, members)]
                    np.fill_diagonal(sub_matrix, np.nan)
                    avg_corr = float(np.nanmean(sub_matrix))
                else:
                    avg_corr = 1.0
                final_clusters.append({
                    "name": f"cluster_{cid}",
                    "tickers": ticker_names,
                    "avg_correlation": round(avg_corr, 4),
                })

        return ClusterResult(
            clusters=final_clusters,
            linkage_matrix=linkage,
            n_clusters=len(final_clusters),
        )

    def compute_portfolio_correlation(
        self, ticker_histories: dict[str, pd.DataFrame], weights: Optional[dict[str, float]] = None
    ) -> dict:
        """
        Compute portfolio-level correlation statistics.

        Returns weighted average correlation and diversification ratio.

        Args:
            ticker_histories: Dict mapping ticker -> DataFrame with 'Close' column.
            weights: Optional dict of ticker -> weight (default: equal weight).

        Returns:
            Dict with portfolio correlation stats.
        """
        corr = self.compute_correlation_matrix(ticker_histories)
        if corr is None:
            return {"error": "Insufficient data for portfolio correlation"}

        tickers = corr.tickers
        n = len(tickers)

        # Equal weights if not provided
        if weights is None:
            w = np.ones(n) / n
        else:
            w = np.array([weights.get(t, 0) for t in tickers])
            total = w.sum()
            if total > 0:
                w = w / total
            else:
                w = np.ones(n) / n

        matrix = np.array(corr.matrix)

        # Portfolio variance (assuming unit volatility for simplicity)
        portfolio_corr = float(w @ matrix @ w)

        # Diversification ratio = weighted avg correlation / portfolio correlation
        avg_corr = float(np.sum(w[:, None] * w[None, :] * matrix))
        div_ratio = avg_corr / portfolio_corr if portfolio_corr > 0 else 1.0

        return {
            "portfolio_correlation": round(portfolio_corr, 4),
            "average_correlation": round(avg_corr, 4),
            "diversification_ratio": round(div_ratio, 4),
            "n_assets": n,
            "tickers": tickers,
        }


# Module-level singleton
_correlation_engine: Optional[CorrelationEngine] = None


def get_correlation_engine(
    lookback_days: int = 60, method: str = "pearson"
) -> CorrelationEngine:
    """Get or create the correlation engine singleton."""
    global _correlation_engine
    if _correlation_engine is None:
        _correlation_engine = CorrelationEngine(lookback_days=lookback_days, method=method)
    return _correlation_engine
