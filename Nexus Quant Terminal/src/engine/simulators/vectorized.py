from typing import Optional, Any
import numpy as np
import pandas as pd

from engine.simulators.metrics import _PRICE_EPS, compute_sharpe_sortino
from engine.simulators.triple_barrier import TripleBarrierSimulator

__all__ = ['VectorizedBinarySimulator']


class VectorizedBinarySimulator:
    """
    Simulador Vectorizado de Alto Rendimiento para Opciones Binarias y Trading Clásico.
    Calcula la ejecucion de trades y metricas de rendimiento utilizando operaciones matriciales NumPy.
    Acelera las simulaciones en un factor de 50x-100x respecto al bucle escalar.
    """
    @staticmethod
    def run_fast(
        df: pd.DataFrame,
        signals: pd.Series,
        expiry_candles: int = 1,
        payout: float = 0.85,
        initial_capital: float = 1000.0,
        bet_fraction: float = 0.1,
        slippage_pct: float = 0.0,
        tie_rule: str = 'RETURN_STAKE',
        sl_atr: Optional[float] = None,
        tp_atr: Optional[float] = None,
        max_holding: Optional[int] = None,
        bullet_risk: Optional[float] = None
    ) -> dict:
        if sl_atr is not None or tp_atr is not None or max_holding is not None:
            return TripleBarrierSimulator.run_fast(
                df=df,
                signals=signals,
                sl_atr=sl_atr if sl_atr is not None else 1.5,
                tp_atr=tp_atr if tp_atr is not None else 3.0,
                max_holding=max_holding if max_holding is not None else expiry_candles,
                bullet_risk=bullet_risk if bullet_risk is not None else (initial_capital * bet_fraction),
                initial_capital=initial_capital,
                slippage_pct=slippage_pct
            )

        if df is None or len(df) <= expiry_candles + 1 or signals is None:
            return {"summary": {"total_trades": 0, "wins": 0, "losses": 0, "ties": 0, "win_rate": 0.0, "win_rate_effective": 0.0, "profit_factor": 0.0, "expected_value_per_trade": 0.0, "net_pnl": 0.0, "max_drawdown": 0.0}}

        n = len(df)
        open_prices = df['open'].to_numpy(dtype=np.float64)
        close_prices = df['close'].to_numpy(dtype=np.float64)

        sig_arr = np.zeros(n, dtype=np.int8)
        if hasattr(signals, 'reindex'):
            sig_series = signals.reindex(df.index)
        else:
            sig_series = pd.Series(signals, index=df.index)

        sig_arr[(sig_series == 'CALL') | (sig_series == 'LONG') | (sig_series == 1)] = 1
        sig_arr[(sig_series == 'PUT') | (sig_series == 'SHORT') | (sig_series == -1)] = -1

        signal_indices = np.flatnonzero(sig_arr != 0)
        if len(signal_indices) == 0:
            return {"summary": {"total_trades": 0, "wins": 0, "losses": 0, "ties": 0, "win_rate": 0.0, "win_rate_effective": 0.0, "profit_factor": 0.0, "expected_value_per_trade": 0.0, "net_pnl": 0.0, "max_drawdown": 0.0}}

        valid_indices = []
        next_allowed = 0
        for idx in signal_indices:
            if idx >= next_allowed and (idx + expiry_candles) < n:
                valid_indices.append(idx)
                next_allowed = idx + expiry_candles

        if not valid_indices:
            return {"summary": {"total_trades": 0, "wins": 0, "losses": 0, "ties": 0, "win_rate": 0.0, "win_rate_effective": 0.0, "profit_factor": 0.0, "expected_value_per_trade": 0.0, "net_pnl": 0.0, "max_drawdown": 0.0}}

        idx_arr = np.array(valid_indices, dtype=np.int64)
        sig_type = sig_arr[idx_arr]

        entry_raw = open_prices[idx_arr + 1]
        exit_raw = close_prices[idx_arr + expiry_candles]

        entry_prices = np.where(sig_type == 1, entry_raw * (1.0 + slippage_pct), entry_raw * (1.0 - slippage_pct))
        price_diff = exit_raw - entry_prices

        is_tie = np.abs(price_diff) <= _PRICE_EPS
        if tie_rule == 'LOSS':
            is_win = np.where(sig_type == 1, price_diff > _PRICE_EPS, price_diff < -_PRICE_EPS)
            is_loss = ~is_win
            is_tie = np.zeros_like(is_tie, dtype=bool)
        else:
            is_win = np.where(sig_type == 1, price_diff > _PRICE_EPS, price_diff < -_PRICE_EPS)
            is_loss = ~is_win & ~is_tie

        fixed_bet = initial_capital * bet_fraction
        pnl_vector = np.where(is_win, fixed_bet * payout, np.where(is_tie, 0.0, -fixed_bet))

        # Ruin handling
        equity_curve_raw = initial_capital + np.cumsum(pnl_vector)
        ruin_idx = np.flatnonzero(equity_curve_raw <= 0)
        if len(ruin_idx) > 0:
            cut = ruin_idx[0]
            equity_before = initial_capital + (np.sum(pnl_vector[:cut]) if cut > 0 else 0.0)
            if pnl_vector[cut] < 0:
                pnl_vector[cut] = -equity_before
            elif pnl_vector[cut] > 0:
                pnl_vector[cut] = min(pnl_vector[cut], equity_before * payout)
            pnl_vector = pnl_vector[:cut + 1]
            is_win = is_win[:cut + 1]
            is_loss = is_loss[:cut + 1]
            is_tie = is_tie[:cut + 1]
            idx_arr = idx_arr[:cut + 1]

        wins = int(np.sum(is_win))
        losses = int(np.sum(is_loss))
        ties = int(np.sum(is_tie))
        total = len(idx_arr)
        decisive = wins + losses

        win_rate = float(wins / total) if total > 0 else 0.0
        win_rate_eff = float(wins / decisive) if decisive > 0 else 0.0
        p_win_total = wins / total if total > 0 else 0.0
        p_loss_total = losses / total if total > 0 else 0.0
        ev_per_trade = float((p_win_total * payout) - (p_loss_total * 1.0)) if total > 0 else 0.0

        net_pnl = float(np.sum(pnl_vector))
        gross_profit = float(np.sum(pnl_vector[pnl_vector > 0])) if len(pnl_vector) > 0 else 0.0
        gross_loss = float(np.abs(np.sum(pnl_vector[pnl_vector < 0]))) if len(pnl_vector) > 0 else 0.0
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        sharpe_ratio, _ = compute_sharpe_sortino(pnl_vector, initial_capital, total)

        equity_curve = initial_capital + np.cumsum(pnl_vector)
        equity_curve = np.insert(equity_curve, 0, initial_capital)
        peaks = np.maximum.accumulate(equity_curve)
        drawdowns = np.where(peaks > 0, (peaks - equity_curve) / peaks, 0.0)
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        return {
            "summary": {
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "win_rate": win_rate,
                "win_rate_effective": win_rate_eff,
                "profit_factor": profit_factor,
                "expected_value_per_trade": ev_per_trade,
                "expected_value_r": ev_per_trade / (fixed_bet if fixed_bet > 0 else 1.0),
                "sharpe_ratio": sharpe_ratio,
                "net_pnl": net_pnl,
                "max_drawdown": max_dd
            }
        }
