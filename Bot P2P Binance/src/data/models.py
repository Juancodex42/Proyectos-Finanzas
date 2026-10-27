"""
Modelos de datos (dataclasses) canónicos para el bot P2P Binance.
Referencia de diseño: docs/ARQUITECTURA.md
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json

from config.settings import WAR_ESCALATION_THRESHOLD


@dataclass
class AdInfo:
    """Información de un anuncio P2P (propio o ajeno)."""

    adv_no: str
    asset: str
    fiat_unit: str
    trade_type: str  # BUY o SELL
    price: float
    surplus_amount: float  # Cantidad disponible
    min_single_trans_amount: float
    max_single_trans_amount: float
    payment_methods: list[str]  # ["BANK", "Mercadopago", ...]
    payment_method_details: list[dict] = field(default_factory=list)
    status: int = 1  # 1=online, 3=offline
    auto_reply_msg: str = ""

    # Advertiser info (para anuncios ajenos)
    advertiser_no: str = ""
    advertiser_nickname: str = ""
    advertiser_completion_rate: float = 0.0
    advertiser_order_count: int = 0

    @classmethod
    def from_search_response(cls, item: dict) -> "AdInfo":
        """Parsea un item del response de ads/search."""
        adv = item.get("adv") or item  # Puede venir wrapeado en {adv: {}, advertiser: {}}
        advertiser = item.get("advertiser") or {}

        methods = []
        method_details = []
        for m in (adv.get("tradeMethods") or []):
            identifier = m.get("identifier", m.get("payType", ""))
            if identifier:
                methods.append(identifier)
            method_details.append(m)

        return cls(
            adv_no=adv.get("advNo") or "",
            asset=adv.get("asset") or "",
            fiat_unit=adv.get("fiatUnit") or "ARS",
            trade_type=adv.get("tradeType") or "",
            price=float(adv.get("price") or 0),
            surplus_amount=float(adv.get("surplusAmount") or 0),
            min_single_trans_amount=float(
                adv.get("minSingleTransAmount") or 0
            ),
            max_single_trans_amount=float(
                adv.get("maxSingleTransAmount") or adv.get("dynamicMaxSingleTransAmount") or 0
            ),
            payment_methods=methods,
            payment_method_details=method_details,
            status=adv.get("advStatus") or 1,
            auto_reply_msg=adv.get("autoReplyMsg") or "",
            advertiser_no=advertiser.get("userNo") or "",
            advertiser_nickname=advertiser.get("nickName") or "",
            advertiser_completion_rate=float(
                advertiser.get("monthFinishRate") or 0
            ),
            advertiser_order_count=int(
                advertiser.get("monthOrderCount") or 0
            ),
        )


@dataclass
class ExchangeRate:
    """Tipo de cambio implícito calculado para un anuncio."""

    asset: str
    payment_method: str
    price_ars: float
    spot_price_usdt: float
    tc_implicito: float  # = price_ars / spot_price_usdt
    position: int  # Posición en el ranking
    advertiser_no: str = ""
    advertiser_nickname: str = ""
    advertiser_completion_rate: float = 0.0
    advertiser_order_count: int = 0
    min_single_trans_amount: float = 0.0
    max_single_trans_amount: float = 0.0
    timestamp: Optional[datetime] = None


@dataclass
class Benchmark:
    """Benchmark de venta de USDT por método de pago."""

    payment_method: str
    avg_top_n_price: float
    individual_prices: list[float] = field(default_factory=list)
    volume_filter: float = 0.0
    timestamp: Optional[datetime] = None


@dataclass
class MyAd:
    """Un anuncio propio de compra."""

    adv_no: str
    asset: str
    ad_group: int  # 1, 2 o 3
    current_price: float
    payment_methods: list[str]
    status: int = 1
    last_repositioned: Optional[datetime] = None
    init_amount: float = 0.0
    surplus_amount: Optional[float] = None
    min_trans_amount: float = 0.0
    max_trans_amount: float = 0.0
    trade_type: str = "BUY"

    @property
    def group_index(self) -> int:
        return self.ad_group

    @property
    def min_single_trans_amount(self) -> float:
        return self.min_trans_amount

    @property
    def max_single_trans_amount(self) -> float:
        return self.max_trans_amount


@dataclass
class PriceChange:
    """Registro de un cambio de precio."""

    adv_no: str
    asset: str
    ad_group: int
    old_price: float
    new_price: float
    reason: str  # 'reposition', 'no_liquidity', 'margin_breach', 'war_detected'
    competitor_best_price: float
    competitor_no: str
    tc_implicito: float
    benchmark_by_method: dict[str, float]  # {"BANK": 960, "MP": 955}
    margin_worst: float
    liquidity_ars: float
    timestamp: Optional[datetime] = None


@dataclass
class DetectedOrder:
    """Orden detectada (solo lectura, para tracking de liquidez)."""

    order_no: str
    adv_no: str
    asset: str
    trade_type: str  # BUY o SELL
    amount_crypto: float
    amount_ars: float
    price: float
    tc_implicito: float
    payment_method: str
    counterparty: str
    status: str
    timestamp: Optional[datetime] = None
    fiwind_bid: Optional[float] = None


@dataclass
class DetectedSwap:
    """Swap spot o convert detectado para alertar en Telegram."""

    trade_id: str
    symbol: str  # ej. BTCUSDT o BTC->USDT
    side: str    # BUY / SELL / CONVERT
    base_asset: str
    quote_asset: str
    base_amount: float
    quote_amount: float
    price: float
    timestamp: Optional[datetime] = None


@dataclass
class PaymentMethodScore:
    """Score calculado para un método de pago."""

    identifier: str
    pay_id: int = 0
    sellers_count: int = 0
    buyers_count: int = 0
    spread: float = 0.0
    score: float = 0.0
    selected: bool = False
    assigned_group: int = 0  # 0 = no asignado, 1-3

    @property
    def display_name(self) -> str:
        return self.identifier


@dataclass
class WarTracker:
    """Tracker de guerra de precios con un competidor."""

    competitor_no: str
    competitor_nickname: str
    asset: str
    payment_method: str
    escalations: int = 0
    my_price_at_start: float = 0.0
    competitor_price_at_start: float = 0.0
    last_escalation: Optional[datetime] = None
    started_at: Optional[datetime] = None

    @property
    def is_war(self) -> bool:
        return self.escalations >= WAR_ESCALATION_THRESHOLD


@dataclass
class BotConfig:
    """Configuración runtime del bot (persistida en DB)."""

    margin_min: float = 10.0
    sell_margin_min: float = 5.0
    price_step: float = 0.01
    poll_interval: int = 30
    volume_ref: float = 500_000.0
    balance_ars: float = 0.0
    rescue_margin: float = 10.0
    is_paused: bool = False
    paused_assets: set[str] = field(default_factory=set)
    paused_ads: set[str] = field(default_factory=set)  # advNo's pausados
    sleep_until: Optional[datetime] = None

    def __post_init__(self):
        self.paused_assets = {
            str(x).strip() for x in (self.paused_assets or ()) if str(x).strip()
        }
        self.paused_ads = {
            str(x).strip() for x in (self.paused_ads or ()) if str(x).strip()
        }



@dataclass
class RepositionDecision:
    """Resultado de la evaluación de reposicionamiento."""

    should_update: bool = False
    new_price: float = 0.0
    reason: str = ""
    competitor_best_price: float = 0.0
    competitor_no: str = ""
    tc_implicito: float = 0.0
    benchmark_by_method: dict[str, float] = field(default_factory=dict)
    margin_worst: float = 0.0
    new_init_amount: Optional[float] = None
    new_min_trans_amount: Optional[float] = None
    new_max_trans_amount: Optional[float] = None
    should_pause: bool = False
    pause_reason: str = ""


@dataclass
class SellDecision:
    """Resultado de la evaluación y guardarraíles para un anuncio de venta P2P."""

    cluster_id: int
    title: str
    anchor_method: str
    suggested_price: float
    top1_price: float
    spread_added: float
    estimated_position: str
    wac_cost: float
    fiwind_bid: float
    is_safe: bool = True
    safety_reason: str = ""
    new_init_amount: Optional[float] = None
    new_min_trans_amount: Optional[float] = None
    new_max_trans_amount: Optional[float] = None
    should_update: bool = False
    should_pause: bool = False
    pause_reason: str = ""
    adv_no: Optional[str] = None
    status: int = 1
    methods: list[str] = field(default_factory=list)
    speed_label: str = ""
    timestamp: Optional[datetime] = None


@dataclass
class ProfitReport:
    """Informe detallado de ganancias para una fecha dada."""

    date: str
    total_profit_ars: float
    realized_profit_ars: float
    projected_profit_ars: float
    total_buy_ars: float
    total_buy_usdt: float
    avg_buy_tc: float
    total_sell_ars: float
    total_sell_usdt: float
    avg_sell_tc: float
    remaining_stock_usdt: float
    projected_sell_price: float
    projection_source: str
    buy_orders_count: int
    sell_orders_count: int
    is_mixed_state: bool


@dataclass
class ClusterAdvice:
    """Recomendación estructurada para un cluster de venta manual."""

    cluster_id: int
    title: str
    methods: list[str]
    anchor_method: str
    top1_price: float
    suggested_price: float
    spread_added: float
    estimated_position: str
    extra_profit_per_usdt: float
    estimated_extra_ticket_ars: float
    suggested_min_ars: float
    suggested_max_ars: float
    speed_label: str
    is_valid_data: bool = True
    notes: str = ""
    data_timestamp: Optional[datetime] = None


class AntiBanViolation:
    """Representa una violación o desviación de regla detectada en una decisión."""

    def __init__(self, rule_id: str, asset: str, group: Optional[int], message: str, severity: str = "CRITICAL"):
        self.rule_id = rule_id
        self.asset = asset
        self.group = group
        self.message = message
        self.severity = severity

    def __str__(self) -> str:
        grp = f" G{self.group}" if self.group is not None else ""
        return f"[{self.severity}] {self.asset}{grp} - {self.rule_id}: {self.message}"



