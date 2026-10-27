"""
Operational models and domain constants for Treasury, Bank Reconciliation,
and Continuous Stock / Merchant Collateral Ledgers.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

# Canonical Operational Transaction Types (matching C.P.N. Auditor model)
TIPO_COMPRA = 'Compra'
TIPO_VENTA = 'Venta'
TIPO_INYECCION = 'Inyección transitoria de fondos personales'
TIPO_RETIRO = 'Retiro a cuenta personal'
TIPO_PRESTAMO_RECIBIDO = 'Préstamo recibido'
TIPO_DEVOLUCION_PRESTAMO = 'Devolución préstamo'
TIPO_DEVOLUCION_PRESTAMO_USDT = 'Devolución préstamo USDT'
TIPO_BLOQUEO_BRONCE = 'Bloqueo comerciante verificado (bronce)'
TIPO_BLOQUEO_PLATA = 'Bloqueo comerciante verificado (plata, adicional)'
TIPO_RENDIMIENTO = 'Rendimiento financiero'
TIPO_GASTO_PERSONAL = 'Gasto personal'
TIPO_GASTO_ARBITRAJE = 'Gasto / Comisión operativa de arbitraje'
TIPO_PASE_PROPIO = 'Pase interno / Propio'

OPERATIONAL_NON_TAXABLE_TYPES = {
    TIPO_INYECCION,
    TIPO_RETIRO,
    TIPO_PRESTAMO_RECIBIDO,
    TIPO_DEVOLUCION_PRESTAMO,
    TIPO_DEVOLUCION_PRESTAMO_USDT,
    TIPO_BLOQUEO_BRONCE,
    TIPO_BLOQUEO_PLATA,
    TIPO_RENDIMIENTO,
    TIPO_GASTO_PERSONAL,
    TIPO_PASE_PROPIO
}

COLLATERAL_LOCK_TYPES = {
    TIPO_BLOQUEO_BRONCE: -500.0,
    TIPO_BLOQUEO_PLATA: -150.0
}

class BankTransaction(BaseModel):
    id: Optional[int] = None
    tx_hash: Optional[str] = None
    fecha: str
    banco: str
    tipo_movimiento: str  # 'CREDITO' | 'DEBITO'
    monto_ars: float
    descripcion: Optional[str] = ''
    titular_contraparte: Optional[str] = ''
    cuit_contraparte: Optional[str] = ''
    categoria: Optional[str] = 'PENDIENTE'  # 'P2P_MATCHED', 'PASE_PROPIO', 'GASTO_PERSONAL', 'GASTO_ARBITRAJE', 'INYECCION', 'RETIRO', 'PRESTAMO', 'DEVOLUCION_PRESTAMO', 'RENDIMIENTO'
    subtipo_cuenta_propia: Optional[str] = None  # 'OPERATIVA' | 'PERSONAL_EXTERNA' | 'PROPIA_SIN_ESPEJO'
    matched_tx_id: Optional[str] = None
    raw_reference: Optional[str] = None
    nota_auditoria: Optional[str] = ''

class OperationalSummary(BaseModel):
    saldo_bancos_cierre: float = 0.0
    stock_usdt_libre: float = 0.0
    stock_usdt_garantia: float = 0.0
    precio_cierre_usdt: float = 0.0
    activos_finales_ars: float = 0.0
    existencia_inicial_ars: float = 0.0
    inyecciones_capital_ars: float = 0.0
    retiros_personales_ars: float = 0.0
    prestamos_recibidos_ars: float = 0.0
    prestamos_devueltos_ars: float = 0.0
    gastos_arbitraje_ars: float = 0.0
    rendimientos_ars: float = 0.0
    capital_neto_invertido_ars: float = 0.0
    ganancia_patrimonial_neta_ars: float = 0.0
    ganancia_trading_operativa_ars: float = 0.0
    total_operaciones: int = 0
