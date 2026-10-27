"""Entidades de dominio (@dataclass) para señales, operaciones simuladas, métricas y bots.
Centraliza los contratos de datos entre las capas de estrategias, motor cuantitativo y rutas.
Referencia de diseño: docs/ARQUITECTURA.md"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TradeSignal:
    """Representa una señal operativa generada por una estrategia cuantitativa."""

    symbol: str
    timeframe: str
    strategy: str
    direction: str  # "LONG" ("CALL") o "SHORT" ("PUT")
    entry_price: float
    stop_loss: float
    take_profit: float
    atr_value: float = 0.0
    confidence_score: float = 0.0
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SimulatedTrade:
    """Representa una operación ejecutada dentro de los simuladores Binary o Triple-Barrier."""

    entry_time: str
    exit_time: str
    type: str  # "CALL" / "PUT"
    entry_price: float
    exit_price: float
    bet_size: float
    pnl: float
    capital_after: float
    result: str  # "WIN", "LOSS", "TIMEOUT", "SCRATCH"
    reason: str
    bars_held: int = 1
    asset: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    streak_step: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CampaignMetrics:
    """Resumen estadístico de una campaña de simulación o evaluación Walk-Forward."""

    initial_capital: float
    final_capital: float
    net_profit: float
    roi_pct: float
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    win_rate_is: float = 0.0
    win_rate_oos: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BotStateConfig:
    """Configuración validada para una instancia de bot (Paper Bot 1 o Live Bot 2)."""

    bot_id: str
    name: str
    mode: str  # "PAPER" o "LIVE"
    symbol: str = "BTCUSDT"
    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT"])
    timeframe: str = "15m"
    strategy: str = "markov"
    strategies: List[str] = field(default_factory=lambda: ["markov"])
    leverage: int = 10
    allocated_capital_usd: float = 100.0
    daily_bullet_usd: float = 10.0
    risk_per_bullet_usd: float = 10.0
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 3.0
    rr_ratio: float = 2.0
    streak_target: int = 3

    ALLOWED_UPDATE_KEYS = frozenset(
        {
            "symbol",
            "symbols",
            "timeframe",
            "strategy",
            "strategies",
            "leverage",
            "risk_per_bullet_usd",
            "daily_bullet_usd",
            "capital_allocated_usd",
            "allocated_capital_usd",
            "risk_per_trade_pct",
            "drawdown_limit_pct",
            "sl_atr_mult",
            "tp_atr_mult",
            "rr_ratio",
            "mode",
            "streak_target",
        }
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizationCandidate:
    """Candidato evaluado por el motor de optimización híbrido (Genético / Optuna)."""

    strategy_id: str
    symbol: str
    interval: str
    params: Dict[str, Any]
    win_rate_is: float
    win_rate_oos: float
    net_profit: float
    total_trades: int
    max_drawdown_pct: float
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
