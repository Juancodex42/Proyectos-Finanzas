"""
Capa de Dominio Pura para el Bot de Trading Cuantitativo V2.0.
Exporta modelos de datos tipados y algoritmos matemáticos deterministas.
Referencia de diseño: docs/ARQUITECTURA.md
"""

from .models import (
    TickerSnapshot,
    OrderBookLevel,
    OrderBookSnapshot,
    QuotePair,
    ArbitrageSignal,
    TradeRecord,
    BacktestMetrics,
    RouteOption,
    RouteEvaluation,
)
from .quant_math import (
    calculate_z_score,
    calculate_spread_bps,
    half_life,
    test_cointegration,
    inventory_skew,
    reservation_price,
    optimal_spread,
    sharpe_ratio,
    sortino_ratio,
    max_drawdown,
    permutation_test_signals,
)

__all__ = [
    "TickerSnapshot",
    "OrderBookLevel",
    "OrderBookSnapshot",
    "QuotePair",
    "ArbitrageSignal",
    "TradeRecord",
    "BacktestMetrics",
    "RouteOption",
    "RouteEvaluation",
    "calculate_z_score",
    "calculate_spread_bps",
    "half_life",
    "test_cointegration",
    "inventory_skew",
    "reservation_price",
    "optimal_spread",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "permutation_test_signals",
]
