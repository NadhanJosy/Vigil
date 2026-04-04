"""
Vigil Backtesting Engine — Event-driven backtesting with realistic execution.

Replays historical signals and price data to evaluate strategy performance.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from .broker import SimulatedBroker, Trade
from .metrics import PerformanceMetrics, compute_metrics

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    name: str
    start_date: str
    end_date: str
    tickers: list[str]
    initial_capital: float = 100_000.0
    slippage_bps: float = 10.0
    commission_bps: float = 10.0
    max_position_pct: float = 10.0  # max % of capital per position

    def to_dict(self) -> dict:
        """Return a dictionary representation of the config."""
        return asdict(self)


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    config: BacktestConfig
    metrics: PerformanceMetrics
    trades: list[Trade]
    equity_curve: list[dict[str, Any]]
    status: str = "complete"
    error: str | None = None


class BacktestEngine:
    """
    Event-driven backtesting engine.

    Loads historical signals and price data, then replays them
    through a simulated broker to evaluate strategy performance.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.broker = SimulatedBroker(
            initial_capital=config.initial_capital,
            slippage_bps=config.slippage_bps,
            commission_bps=config.commission_bps,
            max_position_pct=config.max_position_pct,
        )
        self._equity_curve: list[dict[str, Any]] = []

    def run(self, signals: list[dict], price_data: dict[str, pd.DataFrame]) -> BacktestResult:
        """
        Execute the backtest.

        Parameters
        ----------
        signals : list[dict]
            Historical signals with keys: ticker, date, action, edge_score, signal_type
        price_data : dict[str, pd.DataFrame]
            Price data per ticker with columns: Open, High, Low, Close, Volume

        Returns
        -------
        BacktestResult
        """
        # Sort signals by date
        sorted_signals = sorted(signals, key=lambda s: s.get("date", ""))

        # Track open positions
        open_positions: dict[str, dict] = {}

        for signal in sorted_signals:
            ticker = signal.get("ticker", "")
            action = signal.get("action", "")
            sig_date = signal.get("date", "")
            edge_score = signal.get("edge_score", 5.0)

            # Get price for this date
            prices = price_data.get(ticker)
            if prices is None or len(prices) == 0:
                continue

            # Find the bar closest to signal date
            bar = self._find_bar(prices, sig_date)
            if bar is None:
                continue

            if action == "ENTER" and ticker not in open_positions:
                # Open position
                position_size = self._compute_position_size(edge_score, bar["Close"])
                self.broker.buy(ticker, bar["Close"], position_size, bar.get("High", bar["Close"]), bar.get("Low", bar["Close"]))
                open_positions[ticker] = {
                    "entry_date": sig_date,
                    "entry_price": bar["Close"],
                    "size": position_size,
                }

            elif action in ("EXIT", "STOP") and ticker in open_positions:
                # Close position
                pos = open_positions.pop(ticker)
                self.broker.sell(ticker, bar["Close"], pos["size"], bar.get("High", bar["Close"]), bar.get("Low", bar["Close"]))

            # Record equity
            self._equity_curve.append({
                "date": sig_date,
                "equity": self.broker.equity,
                "cash": self.broker.cash,
                "positions": len(open_positions),
            })

        # Close any remaining positions at last known price
        for ticker, pos in list(open_positions.items()):
            prices = price_data.get(ticker)
            if prices is not None and len(prices) > 0:
                last_bar = prices.iloc[-1]
                self.broker.sell(ticker, float(last_bar["Close"]), pos["size"],
                                 float(last_bar.get("High", last_bar["Close"])),
                                 float(last_bar.get("Low", last_bar["Close"])))

        # Compute metrics
        metrics = compute_metrics(self._equity_curve, self.broker.trades)

        return BacktestResult(
            config=self.config,
            metrics=metrics,
            trades=self.broker.trades,
            equity_curve=self._equity_curve,
        )

    # -- Internal helpers -----------------------------------------------------

    @staticmethod
    def _find_bar(prices: pd.DataFrame, target_date: str) -> dict[str, float] | None:
        """Find the price bar strictly BEFORE target_date to prevent lookahead bias.

        CRITICAL FIX: The signal at index i must only see data from index i-1 or earlier.
        Using bars on or after the signal date introduces future data into the decision.
        """
        try:
            if isinstance(prices.index, pd.DatetimeIndex):
                target = pd.Timestamp(target_date)
                # STRICTLY use bars before the target date to prevent lookahead bias
                # Signal generated at date T can only use data from T-1 or earlier
                valid = prices[prices.index < target]
                if len(valid) > 0:
                    bar = valid.iloc[-1]
                    # Assert that the bar date is strictly before the signal date
                    assert bar.name < target, (
                        f"Lookahead bias detected: bar date {bar.name} >= signal date {target}"
                    )
                    return {
                        "Open": float(bar["Open"]),
                        "High": float(bar["High"]),
                        "Low": float(bar["Low"]),
                        "Close": float(bar["Close"]),
                    }
            return None
        except Exception:
            return None

    def _compute_position_size(self, edge_score: float, price: float) -> float:
        """Compute position size based on edge score and capital allocation."""
        if price <= 0:
            return 0.0
        # Kelly-inspired sizing: higher edge score = larger position
        kelly_fraction = max(0.01, min(0.10, edge_score / 100.0))
        allocation = self.broker.cash * kelly_fraction
        max_allocation = self.broker.initial_capital * (self.config.max_position_pct / 100.0)
        allocation = min(allocation, max_allocation)
        return allocation / price
