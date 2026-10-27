"""Optimizador paralelo de hiperparámetros en grilla mediante multiprocesamiento con joblib.
Evalúa combinaciones paramétricas de estrategias de forma concurrente sobre series OHLCV.
Referencia de diseño: docs/ARQUITECTURA.md"""
import os
from typing import List, Optional, Dict, Any


class ParallelOptimizer:
    """
    Optimizador Paralelo de Hiperparametros utilizando joblib (Feature 15).
    Evalua grids de parametros en paralelo sobre multiples procesadores.
    """
    def __init__(self, n_jobs: int = -1):
        self.n_jobs = n_jobs if n_jobs != -1 else (os.cpu_count() or 1)

    @staticmethod
    def _eval_single_combo(df, strat_class, params, expiry, payout):
        try:
            from engine.simulator import VectorizedBinarySimulator
            if isinstance(strat_class, type):
                try:
                    strat = strat_class(**params)
                except TypeError:
                    strat = strat_class()
            else:
                strat = strat_class
            pre = strat.prepare_data(df)
            sigs = strat.generate_signals(df, params=params, precomputed=pre)
            res = VectorizedBinarySimulator.run_fast(df, sigs, expiry_candles=expiry, payout=payout)
            s = res["summary"]
            return {
                "params": params,
                "trades": s["total_trades"],
                "win_rate": s["win_rate_effective"],
                "ev_per_trade": s["expected_value_per_trade"],
                "net_pnl": s["net_pnl"],
                "max_dd": s["max_drawdown"]
            }
        except Exception:
            return None

    def optimize_grid_parallel(
        self,
        df,
        strat_class,
        param_grid: list,
        expiry: int = 1,
        payout: float = 0.85,
        sl_atr: float = None,
        tp_atr: float = None,
        max_holding: int = None
    ) -> list:
        from joblib import Parallel, delayed
        results = Parallel(n_jobs=self.n_jobs, backend="loky")(
            delayed(self._eval_single_combo)(df, strat_class, p, expiry, payout) for p in param_grid
        )
        valid_results = [r for r in results if r is not None and r["trades"] > 0]
        valid_results.sort(key=lambda x: x["ev_per_trade"], reverse=True)
        return valid_results
