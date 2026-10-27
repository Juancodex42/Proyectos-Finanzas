"""
Matriz unificada de operaciones contables y prioridades intra-segundo.
Fuente única de verdad para el ordenamiento determinista de transacciones.
Referencia de diseño: docs/especificacion_fifo_prioridades.md
"""

from enum import Enum


class OperationType(str, Enum):
    COMPRA = "Compra"
    VENTA = "Venta"
    DEPOSITO = "Depósito Cripto"
    RETIRO = "Retiro Cripto"
    COMISION = "Comisión"
    SWAP = "Swap Cripto"
    INYECCION = "Inyección de Capital"
    EXTRACCION = "Extracción Personal"
    PRESTAMO = "Préstamo"
    OTRO = "Otro"


_FEE_KEYWORDS = ("comision", "comisión", "fee", "tax", "gasto")
_OUT_KEYWORDS = (
    "retiro", "envio", "envío", "withdraw", "transfer", "send",
    "egreso", "salida", "extraccion", "extracción", "pase saliente"
)
_DEP_KEYWORDS = (
    "ingreso", "deposito", "depósito", "deposit", "receive",
    "recepcion", "recepción", "incoming", "entrada", "abono",
    "acreditacion", "acreditación", "transferencia entrante", "pase entrante"
)
_BUY_KEYWORDS = ("compra", "buy", "adquisicion", "adquisición")
_SELL_KEYWORDS = ("venta", "sell", "enajenacion", "enajenación")


def get_operation_priority(op_type: str, monto_compra: float = 0.0, monto_venta: float = 0.0) -> int:
    """
    Asigna una prioridad numérica de desempate intra-segundo (1 a 5):
    1: Compras e Inflows (COMPRA, BUY)
    2: Retiros y Envíos inter-exchange (RETIRO, WITHDRAW)
    3: Depósitos e Ingresos inter-exchange (INGRESO, DEPOSIT)
    4: Comisiones y Fees (FEE, TAX)
    5: Ventas y Egresos gravados (VENTA, SELL)
    """
    top = str(op_type or "").lower().strip()
    mc = float(monto_compra or 0.0)
    mv = float(monto_venta or 0.0)

    is_fee = any(k in top for k in _FEE_KEYWORDS)
    if is_fee:
        return 4

    is_out = any(k in top for k in _OUT_KEYWORDS) and mv > 0
    if is_out:
        return 2

    is_dep = any(k in top for k in _DEP_KEYWORDS) and mc > 0
    if is_dep:
        return 3

    is_buy = any(k in top for k in _BUY_KEYWORDS) or (mc > 0 and not is_dep and mv == 0)
    if is_buy:
        return 1

    is_sell = any(k in top for k in _SELL_KEYWORDS) or (mv > 0 and not is_out and mc == 0)
    if is_sell:
        return 5

    # Para swaps mixtos (mc > 0 y mv > 0) o tipos no categorizados:
    if mc > 0 and mv == 0:
        return 1
    if mv > 0 and mc == 0:
        return 5

    return 3
