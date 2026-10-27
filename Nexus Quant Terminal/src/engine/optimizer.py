"""
Optimizer Façade - Re-exports modular optimizers from engine.optimizers.
Maintains 100% backward compatibility with all existing imports.
"""
from engine.optimizers.math_utils import (
    calculate_wilson_lower_bound,
    binomial_sf,
    monte_carlo_vectorized_2d,
)
from engine.optimizers.parallel import ParallelOptimizer
from engine.optimizers.classic import (
    ClassicOptimizer,
    purged_embargo_cv_splits,
    optimize_sl_tp_parameters,
)
from engine.optimizers.capital import CapitalOptimizer

__all__ = [
    'calculate_wilson_lower_bound',
    'binomial_sf',
    'monte_carlo_vectorized_2d',
    'ParallelOptimizer',
    'ClassicOptimizer',
    'purged_embargo_cv_splits',
    'optimize_sl_tp_parameters',
    'CapitalOptimizer',
]
