"""
Paquete de estrategias cuantitativas del sistema.
Exporta StatisticalArbitrageStrategy y MarketMakingStrategy.
Referencia de diseño: docs/ARQUITECTURA.md
"""

from .statistical_arbitrage import StatisticalArbitrageStrategy
from .market_making import MarketMakingStrategy

__all__ = [
    "StatisticalArbitrageStrategy",
    "MarketMakingStrategy",
]
