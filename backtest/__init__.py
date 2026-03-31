# Vigil Backtesting Module
"""
Event-driven backtesting engine with simulated broker and performance metrics.
"""

from .engine import BacktestEngine
from .broker import SimulatedBroker, Trade
from .metrics import compute_metrics, PerformanceMetrics

__all__ = ["BacktestEngine", "SimulatedBroker", "Trade", "compute_metrics", "PerformanceMetrics"]
