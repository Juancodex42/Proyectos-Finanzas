"""
Fachada de retrocompatibilidad para el motor de simulación.

Re-exporta todos los componentes modularizados desde engine.simulators:
- _PRICE_EPS: Tolerancia de precisión de coma flotante.
- compute_atr: Cálculo del Average True Range (Wilder).
- compute_sharpe_sortino: Cálculo de ratios de Sharpe y Sortino.
- TripleBarrierSimulator: Simulador de Triple Barrera de Marcos López de Prado.
- VectorizedBinarySimulator: Simulador vectorizado de alto rendimiento.
- BinarySimulator: Simulador clásico y multiactivo de órdenes y capital.
"""
from engine.simulators import (
    _PRICE_EPS,
    compute_atr,
    compute_sharpe_sortino,
    TripleBarrierSimulator,
    VectorizedBinarySimulator,
    BinarySimulator,
)

__all__ = [
    "_PRICE_EPS",
    "compute_atr",
    "compute_sharpe_sortino",
    "TripleBarrierSimulator",
    "VectorizedBinarySimulator",
    "BinarySimulator",
]
