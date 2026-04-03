"""
Vigil Portfolio Risk — Portfolio-level risk analytics.

Phase 4: Computes Value at Risk (VaR), Expected Shortfall (CVaR),
beta, and other portfolio risk metrics.
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PortfolioRiskResult:
    """Portfolio risk analytics result."""
    total_value: float
    daily_var_95: float
    daily_var_99: float
    cvar_95: float
    cvar_99: float
    annualized_volatility: float
    beta: Optional[float]
    sharpe_ratio: float
    max_drawdown: float
    daily_returns: list[float]


class PortfolioRiskAnalyzer:
    """
    Portfolio-level risk analytics engine.

    Computes VaR, CVaR, volatility, beta, and drawdown metrics.
    """

    def __init__(self, confidence_levels: tuple = (0.95, 0.99)):
        self.confidence_levels = confidence_levels

    def compute_portfolio_risk(
        self,
        positions: dict[str, dict],
        ticker_histories: dict[str, pd.DataFrame],
        benchmark_history: Optional[pd.DataFrame] = None,
        risk_free_rate: float = 0.04,
    ) -> PortfolioRiskResult:
        """
        Compute portfolio risk metrics.

        Args:
            positions: Dict of ticker -> {quantity, avg_cost}
            ticker_histories: Dict of ticker -> OHLCV DataFrame
            benchmark_history: Optional benchmark (SPY) DataFrame
            risk_free_rate: Annual risk-free rate for Sharpe calculation.

        Returns:
            PortfolioRiskResult with all risk metrics.
        """
        if not positions or not ticker_histories:
            return PortfolioRiskResult(
                total_value=0,
                daily_var_95=0,
                daily_var_99=0,
                cvar_95=0,
                cvar_99=0,
                annualized_volatility=0,
                beta=None,
                sharpe_ratio=0,
                max_drawdown=0,
                daily_returns=[],
            )

        # Compute portfolio weights and returns
        weights = {}
        total_value = 0.0
        for ticker, pos in positions.items():
            hist = ticker_histories.get(ticker)
            if hist is None or len(hist) == 0:
                continue
            price = float(hist["Close"].iloc[-1])
            value = pos.get("quantity", 0) * price
            weights[ticker] = value
            total_value += value

        if total_value == 0:
            return PortfolioRiskResult(
                total_value=0,
                daily_var_95=0,
                daily_var_99=0,
                cvar_95=0,
                cvar_99=0,
                annualized_volatility=0,
                beta=None,
                sharpe_ratio=0,
                max_drawdown=0,
                daily_returns=[],
            )

        # Normalize weights
        w = {t: v / total_value for t, v in weights.items()}

        # Compute individual asset returns
        returns = {}
        for ticker in w:
            hist = ticker_histories.get(ticker)
            if hist is not None and len(hist) > 1:
                returns[ticker] = hist["Close"].astype(float).pct_change().dropna()

        if not returns:
            return PortfolioRiskResult(
                total_value=total_value,
                daily_var_95=0,
                daily_var_99=0,
                cvar_95=0,
                cvar_99=0,
                annualized_volatility=0,
                beta=None,
                sharpe_ratio=0,
                max_drawdown=0,
                daily_returns=[],
            )

        returns_df = pd.DataFrame(returns).dropna()
        tickers = list(returns_df.columns)
        weight_vec = np.array([w.get(t, 0) for t in tickers])
        weight_vec = weight_vec / weight_vec.sum() if weight_vec.sum() > 0 else weight_vec

        # Portfolio returns
        portfolio_returns = (returns_df * weight_vec).sum(axis=1)

        # VaR (Historical method)
        var_95 = float(np.percentile(portfolio_returns, 5))
        var_99 = float(np.percentile(portfolio_returns, 1))

        # CVaR (Expected Shortfall)
        cvar_95 = float(portfolio_returns[portfolio_returns <= var_95].mean()) if (portfolio_returns <= var_95).any() else var_95
        cvar_99 = float(portfolio_returns[portfolio_returns <= var_99].mean()) if (portfolio_returns <= var_99).any() else var_99

        # Annualized volatility
        daily_vol = float(portfolio_returns.std())
        annual_vol = daily_vol * np.sqrt(252)

        # Beta (if benchmark provided)
        beta = None
        if benchmark_history is not None and len(benchmark_history) > 1:
            bench_returns = benchmark_history["Close"].astype(float).pct_change().dropna()
            # Align dates
            common_idx = portfolio_returns.index.intersection(bench_returns.index)
            if len(common_idx) > 10:
                port_aligned = portfolio_returns.loc[common_idx]
                bench_aligned = bench_returns.loc[common_idx]
                cov_matrix = np.cov(port_aligned, bench_aligned)
                if cov_matrix[1, 1] > 0:
                    beta = round(float(cov_matrix[0, 1] / cov_matrix[1, 1]), 4)

        # Sharpe ratio (annualized)
        mean_daily_return = float(portfolio_returns.mean())
        daily_sharpe = (mean_daily_return - risk_free_rate / 252) / daily_vol if daily_vol > 0 else 0
        annual_sharpe = daily_sharpe * np.sqrt(252)

        # Max drawdown
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.cummax()
        drawdowns = (cumulative - running_max) / running_max
        max_dd = float(drawdowns.min())

        return PortfolioRiskResult(
            total_value=round(total_value, 2),
            daily_var_95=round(var_95, 6),
            daily_var_99=round(var_99, 6),
            cvar_95=round(cvar_95, 6),
            cvar_99=round(cvar_99, 6),
            annualized_volatility=round(annual_vol, 6),
            beta=beta,
            sharpe_ratio=round(annual_sharpe, 4),
            max_drawdown=round(max_dd, 6),
            daily_returns=[round(r, 6) for r in portfolio_returns.tail(60).tolist()],
        )

    def compute_position_risk(
        self,
        positions: dict[str, dict],
        ticker_histories: dict[str, pd.DataFrame],
    ) -> list[dict]:
        """
        Compute per-position risk metrics.

        Returns list of dicts with ticker, value, weight, volatility, var_95.
        """
        results = []
        for ticker, pos in positions.items():
            hist = ticker_histories.get(ticker)
            if hist is None or len(hist) < 10:
                continue
            price = float(hist["Close"].iloc[-1])
            value = pos.get("quantity", 0) * price
            returns = hist["Close"].astype(float).pct_change().dropna()
            if len(returns) < 5:
                continue
            vol = float(returns.std()) * np.sqrt(252)
            var_95 = float(np.percentile(returns, 5))
            results.append({
                "ticker": ticker,
                "quantity": pos.get("quantity", 0),
                "avg_cost": pos.get("avg_cost", 0),
                "current_price": round(price, 2),
                "value": round(value, 2),
                "annualized_volatility": round(vol, 4),
                "daily_var_95": round(var_95, 6),
            })
        return results


# Module-level singleton
_risk_analyzer: Optional[PortfolioRiskAnalyzer] = None


def get_risk_analyzer() -> PortfolioRiskAnalyzer:
    """Get or create the portfolio risk analyzer singleton."""
    global _risk_analyzer
    if _risk_analyzer is None:
        _risk_analyzer = PortfolioRiskAnalyzer()
    return _risk_analyzer
