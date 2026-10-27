"""
Módulo de simuladores para BinSim.
Contiene simuladores clásicos de triple barrera, vectorizados y binarios estándar.
"""
from engine.simulators.metrics import (
    _PRICE_EPS,
    compute_atr,
    compute_sharpe_sortino,
)
from engine.simulators.triple_barrier import TripleBarrierSimulator
from engine.simulators.vectorized import VectorizedBinarySimulator
from engine.simulators.binary import BinarySimulator

__all__ = [
    "_PRICE_EPS",
    "compute_atr",
    "compute_sharpe_sortino",
    "TripleBarrierSimulator",
    "VectorizedBinarySimulator",
    "BinarySimulator",
]
