"""
Capa de Dominio Puro: Modelos matemáticos, prioridades operativas y motores de cálculo.
Lógica determinista desacoplada de almacenamiento, red y frameworks web.
Referencia de diseño: docs/contratos_io_transacciones.md
"""

from .models import Transaction, Lot, CostAssignment, InventoryGap
from .operations import OperationType, get_operation_priority
from .fifo_engine import compute_fifo_lots
from .tax_engine import calculate_cedular_tax, calculate_iibb_tax

__all__ = [
    "Transaction",
    "Lot",
    "CostAssignment",
    "InventoryGap",
    "OperationType",
    "get_operation_priority",
    "compute_fifo_lots",
    "calculate_cedular_tax",
    "calculate_iibb_tax",
]
