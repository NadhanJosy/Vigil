"""
Vigil Simulated Broker — Realistic execution simulation.

Handles order submission, slippage modeling, commission calculation,
and position tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """A completed trade."""
    ticker: str
    side: str  # "BUY" or "SELL"
    quantity: float
    fill_price: float
    commission: float
    slippage_bps: float
    timestamp: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0
    hold_days: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class Position:
    """An open position."""
    ticker: str
    quantity: float
    entry_price: float
    entry_date: str = ""


class SimulatedBroker:
    """
    Simulated broker with realistic execution modeling.

    Features:
    - Fixed bps slippage model
    - Per-trade commission
    - Position tracking
    - Equity calculation
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        slippage_bps: float = 10.0,
        commission_bps: float = 10.0,
        max_position_pct: float = 10.0,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps
        self.max_position_pct = max_position_pct
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []

    @property
    def equity(self) -> float:
        """Current equity (cash + unrealized PnL)."""
        return self.cash  # Simplified: only track cash equity

    def buy(self, ticker: str, price: float, quantity: float, high: float, low: float) -> Trade | None:
        """
        Execute a buy order with slippage and commission.

        Parameters
        ----------
        ticker : str
        price : float — closing price of the signal bar
        quantity : float — number of shares
        high : float — bar high (for slippage modeling)
        low : float — bar low (for slippage modeling)

        Returns
        -------
        Trade or None if order rejected
        """
        if quantity <= 0 or price <= 0:
            return None

        # Apply slippage: buy at slightly worse price
        bar_range = high - low if high > low else price * 0.01
        slippage = (self.slippage_bps / 10000) * price + bar_range * 0.1
        fill_price = price + slippage

        # Calculate cost
        cost = fill_price * quantity
        commission = cost * (self.commission_bps / 10000)
        total_cost = cost + commission

        # Check if we have enough cash
        if total_cost > self.cash:
            # Reduce quantity to fit
            quantity = max(0, (self.cash - commission) / fill_price)
            if quantity <= 0:
                logger.warning(f"Insufficient cash to buy {ticker}")
                return None
            total_cost = fill_price * quantity + commission

        self.cash -= total_cost

        # Record position
        self.positions[ticker] = Position(
            ticker=ticker,
            quantity=quantity,
            entry_price=fill_price,
        )

        trade = Trade(
            ticker=ticker,
            side="BUY",
            quantity=quantity,
            fill_price=round(fill_price, 4),
            commission=round(commission, 2),
            slippage_bps=round(slippage / price * 10000, 1) if price > 0 else 0,
        )
        self.trades.append(trade)
        return trade

    def sell(self, ticker: str, price: float, quantity: float, high: float, low: float) -> Trade | None:
        """
        Execute a sell order with slippage and commission.

        Parameters
        ----------
        ticker : str
        price : float — closing price of the signal bar
        quantity : float — number of shares
        high : float — bar high (for slippage modeling)
        low : float — bar low (for slippage modeling)

        Returns
        -------
        Trade or None if no position to close
        """
        pos = self.positions.pop(ticker, None)
        if pos is None:
            return None

        # Use actual position quantity if different
        quantity = pos.quantity

        # Apply slippage: sell at slightly worse price
        bar_range = high - low if high > low else price * 0.01
        slippage = (self.slippage_bps / 10000) * price + bar_range * 0.1
        fill_price = price - slippage

        # Calculate proceeds
        proceeds = fill_price * quantity
        commission = proceeds * (self.commission_bps / 10000)
        net_proceeds = proceeds - commission

        self.cash += net_proceeds

        # Calculate PnL
        pnl = (fill_price - pos.entry_price) * quantity - commission
        pnl_pct = (fill_price - pos.entry_price) / pos.entry_price * 100 if pos.entry_price > 0 else 0

        trade = Trade(
            ticker=ticker,
            side="SELL",
            quantity=quantity,
            fill_price=round(fill_price, 4),
            commission=round(commission, 2),
            slippage_bps=round(slippage / price * 10000, 1) if price > 0 else 0,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
        )
        self.trades.append(trade)
        return trade
