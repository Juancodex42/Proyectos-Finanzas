"""
Paquete de infraestructura central (APIs de exchanges, configuración y estado).
Exporta ConfigLoader, ProfessionalRipioAPI, BinanceAPI y StateManager.
Referencia de diseño: docs/ARQUITECTURA.md
"""

from .config_loader import ConfigLoader
from .ripio_api import ProfessionalRipioAPI
from .binance_api import BinanceAPI
from .state_manager import StateManager

__all__ = [
    "ConfigLoader",
    "ProfessionalRipioAPI",
    "BinanceAPI",
    "StateManager",
]
