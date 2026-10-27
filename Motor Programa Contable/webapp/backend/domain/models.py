"""
Modelos de dominio estandarizados e invariantes contables.
Define las entidades inmutables para transacciones, lotes FIFO y brechas.
Referencia de diseño: docs/contratos_io_transacciones.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

CRYPTO_DUST_EPSILON: float = 1e-12


@dataclass(frozen=True)
class Transaction:
    """Entidad inmutable que representa un evento físico/económico en un exchange o banco."""
    tx_hash: str
    fecha: datetime
    exchange: str
    exchange_root: str
    tipo_operacion: str
    moneda: str
    monto_compra_cripto: float = 0.0
    monto_venta_cripto: float = 0.0
    cotizacion_compra: float = 0.0
    cotizacion_venta: float = 0.0
    monto_ars: float = 0.0
    comentarios: str = ""
    source: str = "EXCHANGE_API"
    is_certified: int = 0
    certification_id: Optional[int] = None
    order_id: Optional[str] = None
    trade_id: Optional[str] = None
    file_row_index: Optional[int] = None

    def __post_init__(self):
        if self.monto_compra_cripto < 0 or self.monto_venta_cripto < 0 or self.monto_ars < 0:
            raise ValueError("Los importes de la transacción no pueden ser negativos.")


@dataclass
class Lot:
    """Lote de inventario para la cola de costeo FIFO."""
    lot_id: str
    fecha: datetime
    moneda: str
    quantity: float
    price_ars: float
    exchange: str
    is_certified: bool = False

    def is_dust(self) -> bool:
        return self.quantity <= CRYPTO_DUST_EPSILON


@dataclass(frozen=True)
class CostAssignment:
    """Resultado determinista de costeo FIFO asignado a una venta o fee."""
    tx_hash: str
    moneda: str
    fecha_venta: datetime
    cantidad_vendida: float
    costo_unitario_ars: float
    costo_total_ars: float
    monto_descubierto: float = 0.0
    requires_cost_audit: int = 0


@dataclass(frozen=True)
class InventoryGap:
    """Definición matemática de un descubierto o brecha en la cartera."""
    exchange: str
    origin_exchange: str
    coin: str
    date: datetime
    deficit: float
    running_deficit: float
    sold_qty: float
    available_qty: float
    mode: str = "global"
    suggested_action: Optional[str] = None
