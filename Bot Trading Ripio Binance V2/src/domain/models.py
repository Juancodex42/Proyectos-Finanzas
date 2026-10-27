"""
Módulo de contratos de datos y entidades tipadas del dominio cuantitativo.
Define estructuras estandarizadas para cotizaciones, señales, trades y ruteo.
Referencia de diseño: docs/ARQUITECTURA.md
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any


class _DictCompatibleMixin:
    """Permite interoperabilidad con código legado basado en diccionarios."""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


@dataclass
class TickerSnapshot(_DictCompatibleMixin):
    """Snapshot de cotización bid/ask/last para un par de mercado."""
    pair: str
    bid: float
    ask: float
    last: float
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread_abs(self) -> float:
        return self.ask - self.bid

    @property
    def spread_bps(self) -> float:
        return (self.spread_abs / self.mid) * 10000.0 if self.mid > 0 else 0.0


@dataclass
class OrderBookLevel(_DictCompatibleMixin):
    """Nivel individual de precio y volumen dentro del libro de órdenes."""
    price: float
    amount: float


@dataclass
class OrderBookSnapshot(_DictCompatibleMixin):
    """Snapshot de profundidad del libro de órdenes (Level 2)."""
    pair: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class QuotePair(_DictCompatibleMixin):
    """Par de cotizaciones óptimas Bid/Ask generadas por Avellaneda-Stoikov."""
    pair: str
    mid_price: float
    reservation_price: float
    bid_price: float
    ask_price: float
    spread_ars: float
    spread_bps: float
    inventory_penalty: float
    volatility: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ArbitrageSignal(_DictCompatibleMixin):
    """Señal cuantitativa de Arbitraje Estadístico (Pairs Trading)."""
    action: str
    z_score: float
    spread_bps: float
    confidence: float
    position_size_usd: float
    reason: str
    half_life: Optional[float] = None
    p_value: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TradeRecord(_DictCompatibleMixin):
    """Registro estandarizado de una operación cerrada o ejecutada."""
    timestamp: Any
    action: str
    price: float
    size_usd: float
    cost: float
    pnl: float
    capital: float
    gross_pnl: float = 0.0
    fee_cost: float = 0.0
    entry_price: Optional[float] = None
    strategy: str = "mean_reversion"
    pair: str = "USDT_ARS"


@dataclass
class BacktestMetrics(_DictCompatibleMixin):
    """Métricas de rendimiento y riesgo de una simulación histórica."""
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate: float
    num_trades: int
    avg_pnl_per_trade: float = 0.0
    profit_factor: float = 0.0
    annual_volatility: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    calmar_ratio: float = 0.0


@dataclass
class RouteOption(_DictCompatibleMixin):
    """Opción de ruta evaluada para transferencia o swap entre exchanges."""
    route: str
    spread_cost_usd: float
    trading_fee_usd: float
    network_fee_usd: float
    total_cost_usd: float
    execution_time_min: int
    network: Optional[str] = None


@dataclass
class RouteEvaluation(_DictCompatibleMixin):
    """Decisión final de ruteo inter-exchange con análisis costo-beneficio."""
    route_type: Any
    reason: str
    total_cost_usd: float
    expected_gain_usd: float
    min_required_gain_usd: float
    is_profitable: bool
    amount_usd: float
    spread_info: Optional[Dict[str, Any]] = None
    network: Optional[str] = None
    spread_cost_usd: float = 0.0
    trading_fee_usd: float = 0.0
    network_fee_usd: float = 0.0
    execution_time_min: int = 1
