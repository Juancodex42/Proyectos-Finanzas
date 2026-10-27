import math
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pandas as pd

from engine.simulators.metrics import _PRICE_EPS, compute_atr, compute_sharpe_sortino

__all__ = ['TripleBarrierSimulator']


class TripleBarrierSimulator:
    """
    Simulador Cuantitativo Institucional basado en el Método de Triple Barrera de Marcos López de Prado.
    - Barrera 1 (Stop Loss horizontal): Entry +/- (sl_atr * ATR)
    - Barrera 2 (Take Profit horizontal): Entry -/+ (tp_atr * ATR o rr_ratio * SL_dist)
    - Barrera 3 (Barrera vertical / Timeout): Cierre a precio de mercado tras max_holding velas.
    - Dimensionamiento de Posición: Calibrado al 100% del riesgo de la bala ($33.3333 o bullet_risk).
    - Métricas Clásicas: Profit Factor, Expected Value ($ y R), Sharpe Ratio, Max Drawdown.
    """

    @staticmethod
    def evaluate_single_trade(
        df: pd.DataFrame,
        entry_idx: int,
        direction: int,  # 1 for LONG/CALL, -1 for SHORT/PUT
        atr_val: float,
        sl_multiplier: float = 1.5,
        tp_multiplier: float = 3.0,
        rr_ratio: Optional[float] = None,
        max_holding: int = 20,
        bullet_risk: float = 33.3333,
        fee_pct: float = 0.0005,
        slippage_pct: float = 0.0002
    ) -> Dict[str, Any]:
        n = len(df)
        if entry_idx >= n:
            return None

        open_prices = df['open'].to_numpy(dtype=np.float64)
        high_prices = df['high'].to_numpy(dtype=np.float64)
        low_prices = df['low'].to_numpy(dtype=np.float64)
        close_prices = df['close'].to_numpy(dtype=np.float64)

        entry_raw = open_prices[entry_idx]
        entry_price = entry_raw * (1.0 + slippage_pct) if direction == 1 else entry_raw * (1.0 - slippage_pct)

        effective_atr = max(atr_val, entry_price * 0.0005)
        sl_distance = effective_atr * sl_multiplier
        if rr_ratio is not None and rr_ratio > 0:
            tp_distance = sl_distance * rr_ratio
        else:
            tp_distance = effective_atr * tp_multiplier

        sl_price = entry_price - sl_distance if direction == 1 else entry_price + sl_distance
        tp_price = entry_price + tp_distance if direction == 1 else entry_price - tp_distance

        sl_pct = sl_distance / entry_price
        total_cost_pct = (2.0 * fee_pct) + (2.0 * slippage_pct)
        loss_fraction_at_sl = max(1e-5, sl_pct + total_cost_pct)
        position_nominal = bullet_risk / loss_fraction_at_sl

        exit_idx = entry_idx
        exit_price = entry_price
        exit_reason = 'TIMEOUT'
        trade_closed = False

        end_idx = min(entry_idx + max_holding - 1, n - 1)

        for k in range(entry_idx, end_idx + 1):
            cur_high = high_prices[k]
            cur_low = low_prices[k]
            cur_open = open_prices[k]
            cur_close = close_prices[k]

            if direction == 1:  # LONG
                sl_touched = cur_low <= sl_price
                tp_touched = cur_high >= tp_price

                if sl_touched and tp_touched:
                    # --- AUDIT GUARANTEE: RESOLUCIÓN INTRA-BARRA CONSERVADORA (WORST-CASE) ---
                    # Si en una misma vela se tocan tanto TP como SL, NO se aplica heurística optimista.
                    # Se asume por rigor institucional que el SL se ejecutó primero, evitando falsos positivos de WR.
                    exit_price = sl_price
                    exit_reason = 'SL'
                    exit_idx = k
                    trade_closed = True
                    break
                elif sl_touched:
                    exit_price = sl_price
                    exit_reason = 'SL'
                    exit_idx = k
                    trade_closed = True
                    break
                elif tp_touched:
                    exit_price = tp_price
                    exit_reason = 'TP'
                    exit_idx = k
                    trade_closed = True
                    break

            else:  # SHORT
                sl_touched = cur_high >= sl_price
                tp_touched = cur_low <= tp_price

                if sl_touched and tp_touched:
                    # --- AUDIT GUARANTEE: RESOLUCIÓN INTRA-BARRA CONSERVADORA (WORST-CASE) ---
                    exit_price = sl_price
                    exit_reason = 'SL'
                    exit_idx = k
                    trade_closed = True
                    break
                elif sl_touched:
                    exit_price = sl_price
                    exit_reason = 'SL'
                    exit_idx = k
                    trade_closed = True
                    break
                elif tp_touched:
                    exit_price = tp_price
                    exit_reason = 'TP'
                    exit_idx = k
                    trade_closed = True
                    break

        if not trade_closed:
            exit_idx = end_idx
            exit_price = close_prices[end_idx]
            exit_reason = 'TIMEOUT'

        holding_candles = max(1, exit_idx - entry_idx + 1)

        if direction == 1:
            gross_return_pct = (exit_price - entry_price) / entry_price
        else:
            gross_return_pct = (entry_price - exit_price) / entry_price

        net_return_pct = gross_return_pct - total_cost_pct
        pnl_dollars = position_nominal * net_return_pct

        if exit_reason == 'SL':
            pnl_dollars = -bullet_risk
        elif exit_reason == 'TP':
            # --- AUDIT GUARANTEE: CERO FABRICACIÓN DE PNL ---
            # Si el costo por comisiones/slippage supera el beneficio bruto del TP,
            # no se inventa una ganancia artificial; se refleja fielmente la fricción real del mercado.
            pnl_dollars = max(pnl_dollars, -bullet_risk)

        r_multiple = pnl_dollars / bullet_risk if bullet_risk > 0 else 0.0
        result_label = 'WIN' if pnl_dollars > _PRICE_EPS else ('LOSS' if pnl_dollars < -_PRICE_EPS else 'TIE')

        return {
            'entry_idx': entry_idx,
            'exit_idx': exit_idx,
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_price': float(entry_price),
            'sl_price': float(sl_price),
            'tp_price': float(tp_price),
            'exit_price': float(exit_price),
            'exit_reason': exit_reason,
            'duration': int(holding_candles),
            'holding_candles': int(holding_candles),
            'gross_return_pct': float(gross_return_pct),
            'net_return_pct': float(net_return_pct),
            'r_multiple': float(r_multiple),
            'pnl': float(pnl_dollars),
            'bet_size': float(position_nominal),
            'position_size': float(position_nominal),
            'margin_used': float(bullet_risk),
            'sl_pct': float(loss_fraction_at_sl),
            'leverage': float(round(position_nominal / max(1e-5, bullet_risk), 1)),
            'result': result_label
        }

    @staticmethod
    def run_fast(
        df: pd.DataFrame,
        signals: Any,
        sl_atr: float = 1.5,
        tp_atr: float = 3.0,
        rr_ratio: Optional[float] = None,
        max_holding: int = 20,
        bullet_risk: float = 33.3333,
        initial_capital: float = 1000.0,
        fee_pct: float = 0.0005,
        slippage_pct: float = 0.0002
    ) -> Dict[str, Any]:
        if df is None or len(df) <= max_holding + 1 or signals is None:
            return {"summary": {
                "total_trades": 0, "wins": 0, "losses": 0, "ties": 0,
                "win_rate": 0.0, "win_rate_effective": 0.0, "profit_factor": 0.0,
                "expected_value_per_trade": 0.0, "expected_value_r": 0.0,
                "sharpe_ratio": 0.0, "net_pnl": 0.0, "max_drawdown": 0.0
            }}

        n = len(df)
        atr = compute_atr(df, 14)

        sig_arr = np.zeros(n, dtype=np.int8)
        if hasattr(signals, 'reindex'):
            sig_series = signals.reindex(df.index)
        else:
            sig_series = pd.Series(signals, index=df.index)

        sig_arr[(sig_series == 'CALL') | (sig_series == 'LONG') | (sig_series == 1)] = 1
        sig_arr[(sig_series == 'PUT') | (sig_series == 'SHORT') | (sig_series == -1)] = -1

        signal_indices = np.flatnonzero(sig_arr != 0)
        if len(signal_indices) == 0:
            return {"summary": {
                "total_trades": 0, "wins": 0, "losses": 0, "ties": 0,
                "win_rate": 0.0, "win_rate_effective": 0.0, "profit_factor": 0.0,
                "expected_value_per_trade": 0.0, "expected_value_r": 0.0,
                "sharpe_ratio": 0.0, "net_pnl": 0.0, "max_drawdown": 0.0
            }}

        trade_pnls = []
        trade_r = []
        wins = 0
        losses = 0
        ties = 0
        tp_count = 0
        sl_count = 0
        timeout_count = 0

        next_allowed = 0
        for s_idx in signal_indices:
            if s_idx < next_allowed or (s_idx + 1) >= n:
                continue

            sig = sig_arr[s_idx]
            trade = TripleBarrierSimulator.evaluate_single_trade(
                df=df,
                entry_idx=s_idx + 1,
                direction=sig,
                atr_val=atr[s_idx],
                sl_multiplier=sl_atr,
                tp_multiplier=tp_atr,
                rr_ratio=rr_ratio,
                max_holding=max_holding,
                bullet_risk=bullet_risk,
                fee_pct=fee_pct,
                slippage_pct=slippage_pct
            )
            if not trade:
                continue

            pnl = trade['pnl']
            trade_pnls.append(pnl)
            trade_r.append(trade['r_multiple'])

            if trade['result'] == 'WIN':
                wins += 1
            elif trade['result'] == 'LOSS':
                losses += 1
            else:
                ties += 1

            if trade['exit_reason'] == 'TP':
                tp_count += 1
            elif trade['exit_reason'] == 'SL':
                sl_count += 1
            else:
                timeout_count += 1

            next_allowed = trade['exit_idx'] + 1

        total = len(trade_pnls)
        decisive = wins + losses
        win_rate = float(wins / total) if total > 0 else 0.0
        win_rate_eff = float(wins / decisive) if decisive > 0 else 0.0

        pnl_arr = np.array(trade_pnls, dtype=np.float64) if trade_pnls else np.array([], dtype=np.float64)
        net_pnl = float(np.sum(pnl_arr)) if len(pnl_arr) > 0 else 0.0

        gross_profit = float(np.sum(pnl_arr[pnl_arr > 0])) if len(pnl_arr) > 0 else 0.0
        gross_loss = float(np.abs(np.sum(pnl_arr[pnl_arr < 0]))) if len(pnl_arr) > 0 else 0.0
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        ev_per_trade = float(np.mean(pnl_arr)) if len(pnl_arr) > 0 else 0.0
        ev_r = float(np.mean(trade_r)) if trade_r else 0.0

        sharpe_ratio, sortino_ratio = compute_sharpe_sortino(pnl_arr, initial_capital, total)

        equity_curve = initial_capital + np.cumsum(pnl_arr) if len(pnl_arr) > 0 else np.array([initial_capital])
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
                "expected_value_r": ev_r,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
                "net_pnl": net_pnl,
                "max_drawdown": max_dd,
                "tp_count": tp_count,
                "sl_count": sl_count,
                "timeout_count": timeout_count
            }
        }

    @staticmethod
    def run(
        df: pd.DataFrame,
        signals: Any,
        sl_atr: float = 1.5,
        tp_atr: float = 3.0,
        rr_ratio: Optional[float] = None,
        max_holding: int = 20,
        bullet_risk: float = 33.3333,
        initial_capital: float = 1000.0,
        mode: str = 'SIMPLE',
        n_consecutive: int = 3,
        risk_ratio: float = 0.20,
        target_ratio: float = 5.0,
        fee_pct: float = 0.0005,
        slippage_pct: float = 0.0002,
        allow_overlapping: bool = False,
        max_concurrent_trades: int = 1,
        progress_callback = None
    ) -> Dict[str, Any]:
        trades = []
        equity_curve = []

        if df is None or len(df) == 0:
            return {"trades": [], "equity_curve": [], "summary": {}}

        n = len(df)
        atr = compute_atr(df, 14)

        if 'open_time' in df.columns:
            time_col = df['open_time'].to_numpy()
        elif 'time' in df.columns:
            time_col = df['time'].to_numpy()
        else:
            time_col = np.arange(n)

        # Normalize timestamps to seconds
        first_t = int(time_col[0]) if len(time_col) > 0 else 0
        first_t_sec = int(first_t / 1000) if first_t > 2**32 else first_t

        if mode == 'BARBELL':
            arb_base = initial_capital * (1.0 - risk_ratio)
            risk_cap = initial_capital * risk_ratio
            bullet_size = risk_cap / max(1, n_consecutive * 2) if bullet_risk <= 0 else bullet_risk
            current_equity = initial_capital
            consecutive_wins = 0
            cycle_start_time = first_t_sec
            monthly_duration_sec = 30 * 86400
        else:
            current_equity = initial_capital
            bullet_size = bullet_risk if bullet_risk > 0 else (initial_capital * 0.0333)

        equity_curve.append({"index": -1, "time": first_t_sec, "equity": float(current_equity)})

        sig_arr = np.zeros(n, dtype=np.int8)
        if hasattr(signals, 'reindex'):
            sig_series = signals.reindex(df.index)
        else:
            sig_series = pd.Series(signals, index=df.index)

        sig_arr[(sig_series == 'CALL') | (sig_series == 'LONG') | (sig_series == 1)] = 1
        sig_arr[(sig_series == 'PUT') | (sig_series == 'SHORT') | (sig_series == -1)] = -1

        signal_indices = np.flatnonzero(sig_arr != 0)
        active_positions = []
        next_allowed = 0

        for idx_pos, s_idx in enumerate(signal_indices):
            if (s_idx + 1) >= n:
                continue

            s_t = int(time_col[s_idx])
            s_t_sec = int(s_t / 1000) if s_t > 2**32 else s_t

            if mode == 'BARBELL':
                # Renovación mensual por flujo de arbitraje cada 30 días calendario
                if s_t_sec >= cycle_start_time + monthly_duration_sec:
                    months_passed = max(1, int((s_t_sec - cycle_start_time) // monthly_duration_sec))
                    cycle_start_time += months_passed * monthly_duration_sec
                    risk_cap = arb_base * risk_ratio
                    bullet_size = risk_cap / max(1, n_consecutive * 2) if bullet_risk <= 0 else bullet_risk
                    current_equity = arb_base + risk_cap

                # Si las balas del mes actual están agotadas, pausar trading hasta el próximo ciclo mensual
                if risk_cap <= 0.001:
                    continue

            if progress_callback:
                progress_callback((idx_pos + 1) / max(1, len(signal_indices)))

            active_positions = [pos for pos in active_positions if pos['exit_idx'] > (s_idx + 1)]

            if not allow_overlapping or mode in ['BARBELL', 'REINVESTMENT']:
                if (s_idx + 1) < next_allowed:
                    continue
            else:
                if len(active_positions) >= max_concurrent_trades:
                    continue

            sig = sig_arr[s_idx]
            trade = TripleBarrierSimulator.evaluate_single_trade(
                df=df,
                entry_idx=s_idx + 1,
                direction=sig,
                atr_val=atr[s_idx],
                sl_multiplier=sl_atr,
                tp_multiplier=tp_atr,
                rr_ratio=rr_ratio,
                max_holding=max_holding,
                bullet_risk=bullet_size,
                fee_pct=fee_pct,
                slippage_pct=slippage_pct
            )
            if not trade:
                continue

            entry_t = int(time_col[trade['entry_idx']])
            exit_t = int(time_col[trade['exit_idx']])
            entry_t_sec = int(entry_t / 1000) if entry_t > 2**32 else entry_t
            exit_t_sec = int(exit_t / 1000) if exit_t > 2**32 else exit_t

            pnl = trade['pnl']
            if mode == 'BARBELL':
                if trade['result'] == 'WIN':
                    risk_cap += pnl
                    consecutive_wins += 1
                    if consecutive_wins >= n_consecutive or risk_cap >= (arb_base * risk_ratio * target_ratio):
                        arb_base += (risk_cap - (initial_capital * risk_ratio))
                        risk_cap = arb_base * risk_ratio
                        bullet_size = risk_cap / 6.0 if bullet_risk <= 0 else bullet_risk
                        consecutive_wins = 0
                    else:
                        # Racha compuesta asimétrica: se reinvierte el capital acumulado en la siguiente bala
                        bullet_size = min(risk_cap, bullet_size + pnl)
                    current_equity = arb_base + risk_cap
                else:
                    risk_cap += pnl
                    consecutive_wins = 0
                    bullet_size = risk_cap / 6.0 if bullet_risk <= 0 else bullet_risk
                    if risk_cap <= 0.001:
                        # Balas agotadas para el mes en curso; pausar hasta el próximo mes de arbitraje
                        risk_cap = 0.0
                    current_equity = arb_base + risk_cap

            else:
                current_equity += pnl

            current_equity = max(0.0, current_equity)

            trade_record = {
                "index": int(trade['entry_idx']),
                "time": entry_t_sec,
                "entry_time": entry_t_sec,
                "exit_idx": int(trade['exit_idx']),
                "exit_time": exit_t_sec,
                "direction": trade['direction'],
                "entry_price": float(trade['entry_price']),
                "sl_price": float(trade['sl_price']),
                "tp_price": float(trade['tp_price']),
                "exit_price": float(trade['exit_price']),
                "exit_reason": trade['exit_reason'],
                "duration": int(trade['duration']),
                "holding_candles": int(trade['duration']),
                "gross_return_pct": float(trade['gross_return_pct']),
                "net_return_pct": float(trade['net_return_pct']),
                "r_multiple": float(trade['r_multiple']),
                "pnl": float(trade['pnl']),
                "bet_size": float(trade['bet_size']),
                "position_size": float(trade['position_size']),
                "result": trade['result']
            }
            trades.append(trade_record)

            equity_curve.append({
                "index": int(trade['exit_idx']),
                "time": exit_t_sec,
                "equity": float(current_equity)
            })

            active_positions.append({"exit_idx": trade['exit_idx']})
            next_allowed = trade['exit_idx'] + 1

            if current_equity <= 0:
                break

        # Compute Summary Statistics
        wins = sum(1 for t in trades if t['result'] == 'WIN')
        losses = sum(1 for t in trades if t['result'] == 'LOSS')
        ties = sum(1 for t in trades if t['result'] == 'TIE')
        tp_count = sum(1 for t in trades if t['exit_reason'] == 'TP')
        sl_count = sum(1 for t in trades if t['exit_reason'] == 'SL')
        timeout_count = sum(1 for t in trades if t['exit_reason'] == 'TIMEOUT')
        total = len(trades)
        decisive = wins + losses

        win_rate = float(wins / total) if total > 0 else 0.0
        win_rate_eff = float(wins / decisive) if decisive > 0 else 0.0

        pnl_arr = np.array([t['pnl'] for t in trades], dtype=np.float64) if trades else np.array([])
        net_pnl = float(np.sum(pnl_arr)) if len(pnl_arr) > 0 else 0.0

        gross_profit = float(np.sum(pnl_arr[pnl_arr > 0])) if len(pnl_arr) > 0 else 0.0
        gross_loss = float(np.abs(np.sum(pnl_arr[pnl_arr < 0]))) if len(pnl_arr) > 0 else 0.0
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        ev_per_trade = float(np.mean(pnl_arr)) if len(pnl_arr) > 0 else 0.0
        r_multiples = [t['r_multiple'] for t in trades]
        ev_r = float(np.mean(r_multiples)) if r_multiples else 0.0

        sharpe_ratio, _ = compute_sharpe_sortino(pnl_arr, initial_capital, total)

        eq_vals = [e['equity'] for e in equity_curve]
        peak = initial_capital
        max_dd = 0.0
        max_dd_dollars = 0.0
        for eq in eq_vals:
            if eq > peak:
                peak = eq
            dd_dollars = peak - eq
            dd_pct = dd_dollars / peak if peak > 0 else 0.0
            if dd_pct > max_dd:
                max_dd = dd_pct
            if dd_dollars > max_dd_dollars:
                max_dd_dollars = dd_dollars

        leverages = [t['leverage'] for t in trades if 'leverage' in t]
        avg_leverage = float(np.mean(leverages)) if leverages else 1.0
        sl_pcts = [t['sl_pct'] for t in trades if 'sl_pct' in t]
        avg_sl_pct = float(np.mean(sl_pcts)) if sl_pcts else 0.02
        rec_leverage = int(round(1.0 / avg_sl_pct)) if avg_sl_pct > 0 else 50
        
        effective_rr = (tp_atr / sl_atr) if (rr_ratio is None and sl_atr > 0) else (rr_ratio or 2.0)
        trades_to_double = int(np.ceil(1000.0 / (bullet_size * effective_rr))) if (bullet_size > 0 and effective_rr > 0) else 5

        summary = {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": win_rate,
            "win_rate_effective": win_rate_eff,
            "profit_factor": profit_factor,
            "expected_value_per_trade": ev_per_trade,
            "expected_value_r": ev_r,
            "sharpe_ratio": sharpe_ratio,
            "net_pnl": net_pnl,
            "max_drawdown": max_dd,
            "max_drawdown_dollars": max_dd_dollars,
            "tp_count": tp_count,
            "sl_count": sl_count,
            "timeout_count": timeout_count,
            "average_leverage": round(avg_leverage, 1),
            "recommended_leverage": rec_leverage,
            "average_sl_pct": round(avg_sl_pct * 100.0, 2),
            "trades_to_double_patrimony": trades_to_double,
            "effective_rr_ratio": round(effective_rr, 2)
        }

        return {
            "trades": trades,
            "equity_curve": equity_curve,
            "summary": summary
        }

    @staticmethod
    def run_multi_asset(
        universe_data: Dict[str, pd.DataFrame],
        signals_by_pair: Dict[str, Any],
        sl_atr: float = 1.5,
        tp_atr: float = 3.0,
        rr_ratio: Optional[float] = None,
        max_holding: int = 20,
        bullet_risk: float = 33.3333,
        initial_capital: float = 1000.0,
        mode: str = 'BARBELL',
        n_consecutive: int = 3,
        risk_ratio: float = 0.20,
        target_ratio: float = 5.0,
        fee_pct: float = 0.0005,
        slippage_pct: float = 0.0002
    ) -> Dict[str, Any]:
        from engine.correlation import CorrelationEngine

        raw_trades = []
        for symbol, signals in signals_by_pair.items():
            df = universe_data.get(symbol)
            if df is None or len(df) == 0:
                continue

            time_col = df['open_time'] if 'open_time' in df.columns else df['time']
            if time_col.max() > 2**32:
                df_times = (time_col // 1000).tolist()
            else:
                df_times = time_col.tolist()

            time_to_idx = {t: idx for idx, t in enumerate(df_times)}
            atr = compute_atr(df, 14)

            for sig in signals:
                sig_time = sig.get('time', 0) if isinstance(sig, dict) else getattr(sig, 'time', 0)
                if sig_time > 2**32:
                    sig_time = sig_time // 1000
                if sig_time not in time_to_idx:
                    continue

                entry_idx = time_to_idx[sig_time] + 1
                if entry_idx >= len(df):
                    continue

                dir_str = sig.get('direction', 'LONG') if isinstance(sig, dict) else getattr(sig, 'direction', 'LONG')
                direction = 1 if dir_str in ['LONG', 'CALL', 1] else -1

                trade = TripleBarrierSimulator.evaluate_single_trade(
                    df=df,
                    entry_idx=entry_idx,
                    direction=direction,
                    atr_val=atr[max(0, entry_idx - 1)],
                    sl_multiplier=sl_atr,
                    tp_multiplier=tp_atr,
                    rr_ratio=rr_ratio,
                    max_holding=max_holding,
                    bullet_risk=bullet_risk,
                    fee_pct=fee_pct,
                    slippage_pct=slippage_pct
                )
                if not trade:
                    continue

                entry_time = int(df_times[trade['entry_idx']])
                exit_time = int(df_times[trade['exit_idx']])

                raw_trades.append({
                    'pair': symbol,
                    'direction': trade['direction'],
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'trade_data': trade
                })

        for idx, rt in enumerate(raw_trades):
            rt['id'] = idx

        events = []
        for rt in raw_trades:
            events.append({'type': 'entry', 'time': rt['entry_time'], 'trade': rt})
            events.append({'type': 'exit', 'time': rt['exit_time'], 'trade': rt})

        events.sort(key=lambda x: (x['time'], 0 if x['type'] == 'exit' else 1))

        trades = []
        equity_curve = []
        next_allowed_time_by_pair = {}
        classes_executed_by_day = {}

        if mode == 'BARBELL':
            safe_core = initial_capital * (1.0 - risk_ratio)
            risk_cap = initial_capital * risk_ratio
            attempts = 6
            bet_per_attempt = risk_cap / attempts if bullet_risk <= 0 else bullet_risk
            bullets = [{
                'capital': bet_per_attempt,
                'consecutive_wins': 0,
                'active_trade_id': None
            } for _ in range(attempts)]
            current_equity = initial_capital
            cycle_start_time = events[0]['time'] if events else 0
            monthly_duration_sec = 30 * 86400
        else:
            current_equity = initial_capital
            bet_per_attempt = bullet_risk

        if events:
            equity_curve.append({"time": events[0]['time'], "equity": float(current_equity)})

        for event in events:
            t = event['trade']
            pair = t['pair']
            td = t['trade_data']
            event_type = event['type']
            current_event_time = event['time']

            if mode == 'BARBELL':
                # Renovación mensual por flujo de arbitraje cada 30 días calendario
                if current_event_time >= cycle_start_time + monthly_duration_sec:
                    months_passed = max(1, int((current_event_time - cycle_start_time) // monthly_duration_sec))
                    cycle_start_time += months_passed * monthly_duration_sec
                    risk_cap = safe_core * risk_ratio
                    bet_per_attempt = risk_cap / attempts
                    for b in bullets:
                        if b['active_trade_id'] is None:
                            b['capital'] = bet_per_attempt
                            b['consecutive_wins'] = 0

            if event_type == 'entry':
                if pair in next_allowed_time_by_pair and event['time'] < next_allowed_time_by_pair[pair]:
                    continue

                trade_day = pd.to_datetime(event['time'], unit='s').strftime('%Y-%m-%d')
                pair_class = CorrelationEngine.get_asset_class(pair)
                executed_classes = classes_executed_by_day.get(trade_day, set())
                if pair_class in executed_classes:
                    continue

                if mode == 'BARBELL':
                    available_bullets = [b for b in bullets if b['active_trade_id'] is None and b['capital'] > 0]
                    if not available_bullets:
                        continue
                    available_bullets.sort(key=lambda b: b['consecutive_wins'], reverse=True)
                    bullet = available_bullets[0]
                    bullet_idx = bullets.index(bullet)
                    t['assigned_bullet_idx'] = bullet_idx
                    bullet['active_trade_id'] = t['id']
                else:
                    t['is_active'] = True

                next_allowed_time_by_pair[pair] = t['exit_time']
                if trade_day not in classes_executed_by_day:
                    classes_executed_by_day[trade_day] = set()
                classes_executed_by_day[trade_day].add(pair_class)

            elif event_type == 'exit':
                if mode == 'BARBELL' and t.get('assigned_bullet_idx') is None:
                    continue
                if mode != 'BARBELL' and not t.get('is_active', False):
                    continue

                pnl = td['pnl']
                is_win = td['result'] == 'WIN'
                is_tie = td['result'] == 'TIE'

                if mode == 'BARBELL':
                    bullet_idx = t.get('assigned_bullet_idx')
                    bullet = bullets[bullet_idx]
                    if is_win:
                        bullet['capital'] += pnl
                        bullet['consecutive_wins'] += 1
                        bullet['active_trade_id'] = None
                        if bullet['consecutive_wins'] >= n_consecutive:
                            safe_core += bullet['capital']
                            risk_cap = safe_core * risk_ratio
                            bet_per_attempt = risk_cap / attempts
                            for b in bullets:
                                b['capital'] = bet_per_attempt
                                b['consecutive_wins'] = 0
                                b['active_trade_id'] = None
                    elif is_tie:
                        bullet['active_trade_id'] = None
                    else:
                        bullet['capital'] = 0
                        bullet['consecutive_wins'] = 0
                        bullet['active_trade_id'] = None
                        all_ruined = all(b['capital'] <= 0.0001 and b['active_trade_id'] is None for b in bullets)
                        if all_ruined:
                            # Balas del mes agotadas: pausar entradas sin inyección instantánea artificial
                            pass

                    active_bullets_cap = sum(b['capital'] for b in bullets)
                    current_equity = safe_core + active_bullets_cap
                else:
                    current_equity += pnl

                current_equity = max(0.0, current_equity)

                trades.append({
                    'pair': pair,
                    'time': t['entry_time'],
                    'entry_time': t['entry_time'],
                    'exit_time': event['time'],
                    'direction': td['direction'],
                    'entry_price': td['entry_price'],
                    'sl_price': td['sl_price'],
                    'tp_price': td['tp_price'],
                    'exit_price': td['exit_price'],
                    'exit_reason': td['exit_reason'],
                    'duration': td['duration'],
                    'holding_candles': td['duration'],
                    'gross_return_pct': td['gross_return_pct'],
                    'net_return_pct': td['net_return_pct'],
                    'r_multiple': td['r_multiple'],
                    'pnl': td['pnl'],
                    'bet_size': td['bet_size'],
                    'position_size': td['position_size'],
                    'result': td['result'],
                    'index': td['entry_idx']
                })

                equity_curve.append({
                    'time': event['time'],
                    'equity': float(current_equity)
                })

                if current_equity <= 0:
                    break

        wins = sum(1 for tr in trades if tr['result'] == 'WIN')
        losses = sum(1 for tr in trades if tr['result'] == 'LOSS')
        ties = sum(1 for tr in trades if tr['result'] == 'TIE')
        tp_count = sum(1 for tr in trades if tr['exit_reason'] == 'TP')
        sl_count = sum(1 for tr in trades if tr['exit_reason'] == 'SL')
        timeout_count = sum(1 for tr in trades if tr['exit_reason'] == 'TIMEOUT')
        total = len(trades)
        decisive = wins + losses

        win_rate = float(wins / total) if total > 0 else 0.0
        win_rate_effective = float(wins / decisive) if decisive > 0 else 0.0

        pnl_arr = np.array([tr['pnl'] for tr in trades], dtype=np.float64) if trades else np.array([])
        net_pnl = float(np.sum(pnl_arr)) if len(pnl_arr) > 0 else 0.0
        gross_profit = float(np.sum(pnl_arr[pnl_arr > 0])) if len(pnl_arr) > 0 else 0.0
        gross_loss = float(np.abs(np.sum(pnl_arr[pnl_arr < 0]))) if len(pnl_arr) > 0 else 0.0
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        ev_per_trade = float(np.mean(pnl_arr)) if len(pnl_arr) > 0 else 0.0
        r_mults = [tr['r_multiple'] for tr in trades]
        ev_r = float(np.mean(r_mults)) if r_mults else 0.0

        sharpe_ratio, _ = compute_sharpe_sortino(pnl_arr, initial_capital, total)

        eq_vals = [e['equity'] for e in equity_curve]
        peak = initial_capital
        max_dd = 0.0
        max_dd_dollars = 0.0
        for eq in eq_vals:
            if eq > peak:
                peak = eq
            dd_dollars = peak - eq
            dd_pct = dd_dollars / peak if peak > 0 else 0.0
            if dd_pct > max_dd:
                max_dd = dd_pct
            if dd_dollars > max_dd_dollars:
                max_dd_dollars = dd_dollars

        summary = {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": win_rate,
            "win_rate_effective": win_rate_effective,
            "profit_factor": profit_factor,
            "expected_value_per_trade": ev_per_trade,
            "expected_value_r": ev_r,
            "sharpe_ratio": sharpe_ratio,
            "net_pnl": net_pnl,
            "max_drawdown": max_dd,
            "max_drawdown_dollars": max_dd_dollars,
            "tp_count": tp_count,
            "sl_count": sl_count,
            "timeout_count": timeout_count
        }

        return {
            "trades": trades,
            "equity_curve": equity_curve,
            "summary": summary
        }
