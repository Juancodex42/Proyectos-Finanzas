"""
Paquete de analítica cuantitativa, backtesting y gestión de portafolio.
Exporta motores de simulación, validación estadística y carga de datos.
Referencia de diseño: docs/ARQUITECTURA.md
"""

from .backtester import (
    BacktesterEngine,
    WalkForwardAnalyzer,
    MonteCarloSimulator,
    LuckVsSkillDetector,
)
from .data_loader import DataLoader
from .reporting import BacktestReporter
from .portfolio_manager import AdvancedPortfolioManager

__all__ = [
    "BacktesterEngine",
    "WalkForwardAnalyzer",
    "MonteCarloSimulator",
    "LuckVsSkillDetector",
    "DataLoader",
    "BacktestReporter",
    "AdvancedPortfolioManager",
]
