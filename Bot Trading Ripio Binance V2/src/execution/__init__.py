"""
Paquete de algoritmos de ejecución inteligente y ruteo inter-exchange.
Exporta InterExchangeRouter, RouteType y NetworkType.
Referencia de diseño: docs/INTER_EXCHANGE_ROUTING.md
"""

from .inter_exchange_router import InterExchangeRouter, RouteType, NetworkType

__all__ = [
    "InterExchangeRouter",
    "RouteType",
    "NetworkType",
]
