"""Modelos de dominio y contratos de datos tipados para Nexus Quant Terminal.
Define las estructuras inmutables/tipadas compartidas entre estrategias, simuladores y bots.
Referencia de diseño: docs/ARQUITECTURA.md"""

from domain.models import (
    BotStateConfig,
    CampaignMetrics,
    OptimizationCandidate,
    SimulatedTrade,
    TradeSignal,
)

__all__ = [
    "TradeSignal",
    "SimulatedTrade",
    "CampaignMetrics",
    "BotStateConfig",
    "OptimizationCandidate",
]
