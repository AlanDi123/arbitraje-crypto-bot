"""Módulo de arbitraje."""

from .engine import ArbitrageEngine, ArbitrageOpportunity, Position
from .backtester import Backtester, BacktestResult
from .smart_engine import SmartArbitrageEngine, TriangularRoute, MultiExchangeRoute
from .smart_engine_fees import SmartArbitrageEngineWithFees, FeeStructure, TriangularRoute as TriangularRouteWithFees

__all__ = [
    "ArbitrageEngine",
    "ArbitrageOpportunity",
    "Position",
    "Backtester",
    "BacktestResult",
    "SmartArbitrageEngine",
    "TriangularRoute",
    "MultiExchangeRoute",
    "SmartArbitrageEngineWithFees",
    "FeeStructure",
    "TriangularRouteWithFees",
]
