"""
Vigil Backtest Metrics — Performance attribution and risk metrics.

Computes: Sharpe, Sortino, Calmar ratios, profit factor, win rate, max drawdown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .broker import Trade


@dataclass
class PerformanceMetrics:
    """Performance metrics from a backtest run."""
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    total_trades: int = 0
    avg_hold_days: float = 0.0


def compute_metrics(equity_curve: list[dict[str, Any]], trades: list[Trade]) -> PerformanceMetrics:
    """
    Compute performance metrics from equity curve and trades.

    Parameters
    ----------
    equity_curve : list[dict]
        Each dict has keys: date, equity, cash, positions
    trades : list[Trade]
        Completed trades (both BUY and SELL)

    Returns
    -------
    PerformanceMetrics
    """
    metrics = PerformanceMetrics()

    if not trades:
        return metrics

    # Separate sell trades for PnL analysis
    sell_trades = [t for t in trades if t.side == "SELL"]
    if not sell_trades:
        metrics.total_trades = len(trades)
        return metrics

    metrics.total_trades = len(sell_trades)

    # PnL analysis
    pnls = [t.pnl_pct for t in sell_trades if t.pnl_pct is not None]
    if pnls:
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        metrics.win_rate = round(len(wins) / len(pnls) * 100, 1) if pnls else 0.0
        metrics.avg_win_pct = round(sum(wins) / len(wins), 2) if wins else 0.0
        metrics.avg_loss_pct = round(sum(losses) / len(losses), 2) if losses else 0.0

        # Profit factor
        total_wins = sum(wins) if wins else 0.0
        total_losses = abs(sum(losses)) if losses else 0.0
        if total_losses == 0:
            # No losses: profit factor is infinite if there are wins, else 0
            metrics.profit_factor = float('inf') if total_wins > 0 else 0.0
        else:
            metrics.profit_factor = round(total_wins / total_losses, 2)

        # Total return
        metrics.total_return_pct = round(sum(pnls), 2)

    # Drawdown analysis from equity curve
    if equity_curve:
        equities = [e.get("equity", 0) for e in equity_curve]
        if equities:
            peak = equities[0]
            max_dd = 0.0
            for eq in equities:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak * 100 if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
            metrics.max_drawdown_pct = round(max_dd, 2)

            # Calmar ratio
            if metrics.max_drawdown_pct > 0:
                metrics.calmar_ratio = round(metrics.total_return_pct / metrics.max_drawdown_pct, 2)

    # Sharpe and Sortino ratios
    if pnls and len(pnls) > 1:
        mean_return = sum(pnls) / len(pnls)
        variance = sum((p - mean_return) ** 2 for p in pnls) / (len(pnls) - 1)
        std_return = math.sqrt(variance) if variance > 0 else 0

        # Annualized Sharpe (assuming ~252 trading days)
        if std_return > 0:
            metrics.sharpe_ratio = round((mean_return / std_return) * math.sqrt(252), 2)

        # Sortino (downside deviation only)
        downside = [p for p in pnls if p < 0]
        if downside:
            downside_mean = sum(downside) / len(downside)
            downside_var = sum((p - downside_mean) ** 2 for p in downside) / len(downside)
            downside_std = math.sqrt(downside_var) if downside_var > 0 else 0
            if downside_std > 0:
                metrics.sortino_ratio = round((mean_return / downside_std) * math.sqrt(252), 2)

    # Average hold days
    hold_days = [t.hold_days for t in sell_trades if t.hold_days > 0]
    if hold_days:
        metrics.avg_hold_days = round(sum(hold_days) / len(hold_days), 1)

    # Annualized return (simplified)
    if equity_curve and len(equity_curve) > 1:
        start_equity = equity_curve[0].get("equity", 100000)
        end_equity = equity_curve[-1].get("equity", 100000)
        total_days = len(equity_curve)
        if start_equity > 0 and total_days > 0:
            total_return = (end_equity - start_equity) / start_equity
            annualized = total_return * (252 / max(1, total_days))
            metrics.annualized_return_pct = round(annualized * 100, 2)

    return metrics
