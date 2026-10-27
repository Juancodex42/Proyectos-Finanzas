from typing import Optional, Dict, List, Any
import numpy as np
import pandas as pd

from engine.simulators.metrics import _PRICE_EPS, compute_sharpe_sortino
from engine.simulators.triple_barrier import TripleBarrierSimulator

__all__ = ['BinarySimulator']


class BinarySimulator:
    """
    Simulador Cuantitativo y Fachada de Ejecución.
    NOTA DE ARQUITECTURA: El motor primario de producción del sistema es TripleBarrierSimulator
    (Trading Clásico Asimétrico con Stop Loss y Take Profit por ATR, Forex, Cripto Spot y Futuros).
    BinarySimulator actúa como adaptador de retrocompatibilidad y benchmarking comparativo
    con la investigación histórica preliminar (Legacy Research).
    """

    def run(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        expiry_candles: int = 1,
        payout: float = 0.92,
        initial_capital: float = 1000.0,
        mode: str = 'SIMPLE',
        n_consecutive: int = 5,
        bet_fraction: float = 0.1,
        risk_ratio: float = 0.20,
        target_ratio: float = 5.0,
        slippage_pct: float = 0.0,
        allow_overlapping: bool = False,
        max_concurrent_trades: int = 1,
        tie_rule: str = 'RETURN_STAKE',
        progress_callback = None,
        sl_atr: Optional[float] = None,
        tp_atr: Optional[float] = None,
        rr_ratio: Optional[float] = None,
        max_holding: Optional[int] = None,
        bullet_risk: Optional[float] = None,
        fee_pct: float = 0.0005,
        classic_mode: bool = False
    ):
        # Si se solicitan parámetros clásicos o modo clásico (o payout >= 1.0 propio de R:R en futuros), delegar en TripleBarrierSimulator
        if classic_mode or sl_atr is not None or tp_atr is not None or (rr_ratio is not None and rr_ratio > 0) or payout >= 1.0:
            return TripleBarrierSimulator.run(
                df=df,
                signals=signals,
                sl_atr=sl_atr if sl_atr is not None else 1.5,
                tp_atr=tp_atr if tp_atr is not None else 3.0,
                rr_ratio=rr_ratio,
                max_holding=max_holding if max_holding is not None else expiry_candles,
                bullet_risk=bullet_risk if bullet_risk is not None else (initial_capital * (risk_ratio if mode == 'BARBELL' else bet_fraction)),
                initial_capital=initial_capital,
                mode=mode,
                n_consecutive=n_consecutive,
                risk_ratio=risk_ratio,
                target_ratio=target_ratio,
                fee_pct=fee_pct,
                slippage_pct=slippage_pct,
                allow_overlapping=allow_overlapping,
                max_concurrent_trades=max_concurrent_trades,
                progress_callback=progress_callback
            )

        trades = []
        equity_curve = []

        if len(df) > 1:
            candle_duration = int(df.iloc[1]['open_time'] - df.iloc[0]['open_time']) if 'open_time' in df.columns else 3600
        else:
            candle_duration = 86400

        if mode == 'BARBELL':
            arb_base = initial_capital
            risk_cap = arb_base * risk_ratio
            target_capital = risk_cap * target_ratio
            consecutive_wins = 0
            current_equity = arb_base
        else:
            current_equity = initial_capital
            base_capital = initial_capital
            consecutive_wins = 0
            fixed_bet = initial_capital * bet_fraction

        first_time = df['open_time'].iloc[0] if (len(df) and 'open_time' in df.columns) else (df['time'].iloc[0] if (len(df) and 'time' in df.columns) else 0)
        first_time_sec = int(first_time / 1000) if first_time > 2**32 else int(first_time)
        equity_curve.append({"index": -1, "time": first_time_sec, "equity": float(current_equity)})

        trade_indices = signals.dropna().index
        active_positions = []
        next_allowed_entry_idx = 0

        for idx in trade_indices:
            signal = signals.loc[idx]
            if signal not in ['CALL', 'PUT', 'LONG', 'SHORT']:
                continue

            entry_idx = df.index.get_loc(idx)
            if progress_callback:
                progress_callback(entry_idx / len(df))

            active_positions = [pos for pos in active_positions if pos['exit_idx'] > entry_idx]

            if not allow_overlapping or mode in ['REINVESTMENT', 'BARBELL']:
                if entry_idx < next_allowed_entry_idx:
                    continue
            else:
                if len(active_positions) >= max_concurrent_trades:
                    continue

            exit_idx = entry_idx + expiry_candles
            if exit_idx >= len(df):
                break

            entry_price_raw = float(df.iloc[entry_idx + 1]['open'])
            entry_time = int(df.iloc[entry_idx + 1]['open_time']) if 'open_time' in df.columns else int(df.iloc[entry_idx + 1]['time'])

            if signal in ['CALL', 'LONG']:
                entry_price = entry_price_raw * (1.0 + slippage_pct)
            else:
                entry_price = entry_price_raw * (1.0 - slippage_pct)

            exit_price = float(df.iloc[exit_idx]['close'])

            if exit_idx + 1 < len(df):
                exit_time = int(df.iloc[exit_idx + 1]['open_time']) if 'open_time' in df.columns else int(df.iloc[exit_idx + 1]['time'])
            else:
                exit_time = entry_time + candle_duration

            if mode == 'BARBELL':
                initial_cycle_risk = arb_base * risk_ratio
                bet_size = (initial_cycle_risk * bet_fraction) * ((1.0 + payout) ** consecutive_wins)
                if bet_size > risk_cap:
                    bet_size = risk_cap
            elif mode == 'REINVESTMENT':
                bet_size = (base_capital * bet_fraction) * ((1.0 + payout) ** consecutive_wins)
            else:
                bet_size = fixed_bet

            if mode != 'BARBELL' and bet_size > current_equity:
                bet_size = current_equity

            price_diff = exit_price - entry_price
            is_tie = abs(price_diff) <= _PRICE_EPS
            is_win = False

            if is_tie and tie_rule == 'LOSS':
                is_win = False
                is_tie = False
            elif not is_tie:
                if signal in ['CALL', 'LONG'] and price_diff > 0:
                    is_win = True
                elif signal in ['PUT', 'SHORT'] and price_diff < 0:
                    is_win = True

            pnl = 0
            if is_tie:
                result_label = 'TIE'
                exit_reason = 'TIMEOUT'
            elif is_win:
                pnl = bet_size * payout
                result_label = 'WIN'
                exit_reason = 'TP'
                if mode == 'BARBELL':
                    risk_cap += pnl
                    consecutive_wins += 1
                    if risk_cap >= target_capital:
                        arb_base += (risk_cap - initial_cycle_risk)
                        risk_cap = arb_base * risk_ratio
                        target_capital = risk_cap * target_ratio
                        consecutive_wins = 0
                    current_equity = arb_base + (risk_cap - (arb_base * risk_ratio))
                else:
                    current_equity += pnl
                    if mode == 'REINVESTMENT':
                        consecutive_wins += 1
                        if consecutive_wins >= n_consecutive:
                            base_capital = current_equity
                            consecutive_wins = 0
            else:
                pnl = -bet_size
                result_label = 'LOSS'
                exit_reason = 'SL'
                if mode == 'BARBELL':
                    risk_cap -= bet_size
                    consecutive_wins = 0
                    if risk_cap <= 0.0001:
                        if arb_base < initial_capital:
                            arb_base = initial_capital
                        risk_cap = arb_base * risk_ratio
                        target_capital = risk_cap * target_ratio
                        current_equity = arb_base
                    else:
                        current_equity = arb_base + (risk_cap - (arb_base * risk_ratio))
                else:
                    current_equity += pnl
                    if mode == 'REINVESTMENT':
                        consecutive_wins = 0
                        base_capital = current_equity

            if current_equity <= 0:
                current_equity = 0

            entry_sec = int(entry_time / 1000) if entry_time > 2**32 else int(entry_time)
            exit_sec = int(exit_time / 1000) if exit_time > 2**32 else int(exit_time)
            r_mult = pnl / (bet_size if bet_size > 0 else 1.0)

            trades.append({
                "index": entry_idx,
                "time": entry_sec,
                "entry_time": entry_sec,
                "exit_idx": exit_idx,
                "exit_time": exit_sec,
                "direction": 'LONG' if signal in ['CALL', 'LONG'] else 'SHORT',
                "entry_price": float(entry_price),
                "sl_price": float(entry_price * 0.99 if signal in ['CALL', 'LONG'] else entry_price * 1.01),
                "tp_price": float(entry_price * 1.02 if signal in ['CALL', 'LONG'] else entry_price * 0.98),
                "exit_price": float(exit_price),
                "exit_reason": exit_reason,
                "duration": int(expiry_candles),
                "holding_candles": int(expiry_candles),
                "gross_return_pct": float(price_diff / entry_price if signal in ['CALL', 'LONG'] else -price_diff / entry_price),
                "net_return_pct": float(pnl / (bet_size if bet_size > 0 else 1.0)),
                "r_multiple": float(r_mult),
                "result": result_label,
                "pnl": float(pnl),
                "bet_size": float(bet_size),
                "position_size": float(bet_size)
            })

            equity_curve.append({
                "index": exit_idx,
                "time": exit_sec,
                "equity": float(current_equity)
            })

            active_positions.append({"exit_idx": exit_idx})
            next_allowed_entry_idx = exit_idx

            if current_equity <= 0:
                break

        wins = sum(1 for t in trades if t['result'] == 'WIN')
        losses = sum(1 for t in trades if t['result'] == 'LOSS')
        ties = sum(1 for t in trades if t['result'] == 'TIE')
        total = len(trades)
        decisive = wins + losses

        win_rate = wins / total if total > 0 else 0
        win_rate_effective = wins / decisive if decisive > 0 else 0
        p_win_total = wins / total if total > 0 else 0
        p_loss_total = losses / total if total > 0 else 0
        expected_value_per_trade = (p_win_total * payout) - (p_loss_total * 1.0)
        net_pnl = sum(t['pnl'] for t in trades)

        pnl_arr = np.array([t['pnl'] for t in trades]) if trades else np.array([])
        gross_profit = float(np.sum(pnl_arr[pnl_arr > 0])) if len(pnl_arr) > 0 else 0.0
        gross_loss = float(np.abs(np.sum(pnl_arr[pnl_arr < 0]))) if len(pnl_arr) > 0 else 0.0
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        sharpe_ratio, _ = compute_sharpe_sortino(pnl_arr, initial_capital, total)

        eq_vals = [e['equity'] for e in equity_curve]
        peak = initial_capital
        max_dd = 0
        for eq in eq_vals:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        summary = {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": win_rate,
            "win_rate_effective": win_rate_effective,
            "profit_factor": profit_factor,
            "expected_value_per_trade": expected_value_per_trade,
            "expected_value_r": expected_value_per_trade,
            "sharpe_ratio": sharpe_ratio,
            "net_pnl": net_pnl,
            "max_drawdown": max_dd
        }

        return {
            "trades": trades,
            "equity_curve": equity_curve,
            "summary": summary
        }

    def run_multi_asset(
        self,
        universe_data: dict,
        signals_by_pair: dict,
        expiry_candles: int = 2,
        payout: float = 0.85,
        initial_capital: float = 1000.0,
        mode: str = 'SIMPLE',
        n_consecutive: int = 3,
        bet_fraction: float = 0.166,
        risk_ratio: float = 0.20,
        target_ratio: float = 5.0,
        slippage_pct: float = 0.0,
        tie_rule: str = 'RETURN_STAKE',
        sl_atr: Optional[float] = None,
        tp_atr: Optional[float] = None,
        rr_ratio: Optional[float] = None,
        max_holding: Optional[int] = None,
        bullet_risk: Optional[float] = None,
        classic_mode: bool = False
    ):
        if classic_mode or sl_atr is not None or tp_atr is not None or (rr_ratio is not None and rr_ratio > 0) or payout >= 1.0:
            return TripleBarrierSimulator.run_multi_asset(
                universe_data=universe_data,
                signals_by_pair=signals_by_pair,
                sl_atr=sl_atr if sl_atr is not None else 1.5,
                tp_atr=tp_atr if tp_atr is not None else (3.0 if (rr_ratio is None or rr_ratio <= 0) else 1.5 * rr_ratio),
                rr_ratio=rr_ratio if (rr_ratio is not None and rr_ratio > 0) else (payout if payout >= 1.0 else 2.0),
                max_holding=max_holding if max_holding is not None else expiry_candles,
                bullet_risk=bullet_risk if bullet_risk is not None else (initial_capital * (risk_ratio if mode == 'BARBELL' else bet_fraction)),
                initial_capital=initial_capital,
                mode=mode,
                n_consecutive=n_consecutive,
                risk_ratio=risk_ratio,
                target_ratio=target_ratio,
                slippage_pct=slippage_pct
            )

        # 1. Obtener la secuencia cronológica de operaciones
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

            df_open = df['open'].to_numpy()
            df_close = df['close'].to_numpy()
            df_open_time = time_col.to_numpy()
            n_df = len(df)

            if n_df > 1:
                candle_duration = int(df_open_time[1] - df_open_time[0])
            else:
                candle_duration = 86400 * 1000 if time_col.max() > 2**32 else 86400

            for sig in signals:
                sig_time = sig['time'] if isinstance(sig, dict) else getattr(sig, 'time', 0)
                if sig_time > 2**32:
                    sig_time = sig_time // 1000
                if sig_time not in time_to_idx:
                    continue

                entry_idx = time_to_idx[sig_time]
                exit_idx = entry_idx + expiry_candles

                if exit_idx >= n_df:
                    continue

                direction = sig['direction'] if isinstance(sig, dict) else getattr(sig, 'direction', 'CALL')

                entry_price_raw = float(df_open[entry_idx + 1])
                entry_time = int(df_open_time[entry_idx + 1])
                if entry_time > 2**32:
                    entry_time = entry_time // 1000

                if direction in ['CALL', 'LONG']:
                    entry_price = entry_price_raw * (1.0 + slippage_pct)
                else:
                    entry_price = entry_price_raw * (1.0 - slippage_pct)

                exit_price = float(df_close[exit_idx])

                if exit_idx + 1 < n_df:
                    exit_time = int(df_open_time[exit_idx + 1])
                else:
                    norm_duration = candle_duration // 1000 if (time_col.max() > 2**32 or candle_duration >= 1000) else candle_duration
                    exit_time = entry_time + int(expiry_candles * norm_duration)
                if exit_time > 2**32:
                    exit_time = exit_time // 1000

                price_diff = exit_price - entry_price
                is_tie = abs(price_diff) <= _PRICE_EPS
                is_win = False
                if is_tie and tie_rule == 'LOSS':
                    is_win = False
                    is_tie = False
                elif not is_tie:
                    if direction in ['CALL', 'LONG'] and price_diff > 0:
                        is_win = True
                    elif direction in ['PUT', 'SHORT'] and price_diff < 0:
                        is_win = True

                raw_trades.append({
                    'pair': symbol,
                    'direction': 'LONG' if direction in ['CALL', 'LONG'] else 'SHORT',
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'result': 'WIN' if is_win else ('TIE' if is_tie else 'LOSS'),
                    'is_win': is_win,
                    'is_tie': is_tie,
                    'index': entry_idx
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

        from engine.correlation import CorrelationEngine
        all_pairs = list(signals_by_pair.keys())

        if mode == 'BARBELL':
            safe_core = initial_capital * (1.0 - risk_ratio)
            risk_cap = initial_capital * risk_ratio
            attempts = int(round(1.0 / bet_fraction)) if bet_fraction > 0 else 1
            bet_per_attempt = risk_cap / attempts
            bullets = [{
                'capital': bet_per_attempt,
                'consecutive_wins': 0,
                'active_trade_id': None
            } for _ in range(attempts)]
            current_equity = initial_capital
            cycle_start_time = events[0]['time'] if events else 0
            if cycle_start_time > 2**32:
                cycle_start_time = int(cycle_start_time / 1000)
            monthly_duration_sec = 30 * 86400
        elif mode == 'REINVESTMENT':
            current_equity = initial_capital
            consecutive_wins_by_pair = {p: 0 for p in all_pairs}
            base_capital_by_pair = {p: initial_capital for p in all_pairs}
        else:
            current_equity = initial_capital
            fixed_bet = initial_capital * bet_fraction

        first_time = events[0]['time'] if events else None
        equity_curve.append({"time": first_time, "equity": float(current_equity)})
        classes_executed_by_day = {}

        for event in events:
            t = event['trade']
            pair = t['pair']
            event_type = event['type']
            event_t_sec = int(event['time'] / 1000) if event['time'] > 2**32 else event['time']

            if mode == 'BARBELL':
                # Renovación mensual por flujo de arbitraje cada 30 días calendario
                if event_t_sec >= cycle_start_time + monthly_duration_sec:
                    months_passed = max(1, int((event_t_sec - cycle_start_time) // monthly_duration_sec))
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

                trade_day = pd.to_datetime(event['time'], unit='s' if event['time'] < 2**32 else 'ms').strftime('%Y-%m-%d')
                pair_class = CorrelationEngine.get_asset_class(pair)
                executed_classes = classes_executed_by_day.get(trade_day, set())
                if pair_class in executed_classes:
                    continue

                if mode == 'BARBELL':
                    available_bullets = [b for b in bullets if b['active_trade_id'] is None and b['capital'] > 0]
                    if len(available_bullets) == 0:
                        continue
                    available_bullets.sort(key=lambda b: b['consecutive_wins'], reverse=True)
                    bullet = available_bullets[0]
                    bullet_idx = bullets.index(bullet)
                    t['assigned_bullet_idx'] = bullet_idx
                    bullet['active_trade_id'] = t['id']
                    bet_size = bullet['capital']
                    t['bet_size'] = bet_size
                elif mode == 'REINVESTMENT':
                    wins = consecutive_wins_by_pair.get(pair, 0)
                    base_cap = base_capital_by_pair.get(pair, current_equity)
                    bet_size = (base_cap * bet_fraction) * ((1.0 + payout) ** wins)
                    if bet_size > current_equity:
                        bet_size = current_equity
                    t['bet_size'] = bet_size
                    t['is_active'] = True
                else:
                    bet_size = fixed_bet
                    if bet_size > current_equity:
                        bet_size = current_equity
                    t['bet_size'] = bet_size
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

                pnl = 0
                is_win = t['is_win']
                is_tie = t.get('is_tie', False)
                bet_size = t.get('bet_size', 0)

                if is_tie:
                    # En empates, retorno de posición
                    current_equity = safe_core + sum(b['capital'] for b in bullets) if mode == 'BARBELL' else current_equity
                    trades.append({
                        'pair': pair,
                        'time': event['time'],
                        'entry_time': t['entry_time'],
                        'exit_time': event['time'],
                        'direction': t['direction'],
                        'entry_price': t['entry_price'],
                        'sl_price': t['entry_price'] * 0.99,
                        'tp_price': t['entry_price'] * 1.02,
                        'exit_price': t['exit_price'],
                        'exit_reason': 'TIMEOUT',
                        'duration': int(expiry_candles),
                        'holding_candles': int(expiry_candles),
                        'gross_return_pct': 0.0,
                        'net_return_pct': 0.0,
                        'r_multiple': 0.0,
                        'result': 'TIE',
                        'pnl': 0.0,
                        'bet_size': bet_size,
                        'position_size': bet_size,
                        'index': t['index']
                    })
                    equity_curve.append({'time': event['time'], 'equity': float(current_equity)})
                    continue

                if mode == 'BARBELL':
                    bullet_idx = t.get('assigned_bullet_idx')
                    bullet = bullets[bullet_idx]
                    if is_win:
                        pnl = bet_size * payout
                        bullet['capital'] += pnl
                        bullet['consecutive_wins'] += 1
                        bullet['active_trade_id'] = None
                        if bullet['consecutive_wins'] >= n_consecutive:
                            safe_core += bullet['capital']
                            risk_cap = safe_core * risk_ratio
                            bet_per_attempt = risk_cap / attempts
                            for b in bullets:
                                if b['active_trade_id'] is None:
                                    b['capital'] = bet_per_attempt
                                    b['consecutive_wins'] = 0
                                    b['pending_reset'] = False
                                else:
                                    b['pending_reset'] = True
                                    b['next_capital'] = bet_per_attempt
                    else:
                        pnl = -bet_size
                        bullet['capital'] = 0
                        bullet['consecutive_wins'] = 0
                        bullet['active_trade_id'] = None
                        all_ruined = all(b['capital'] <= 0.0001 and b['active_trade_id'] is None for b in bullets)
                        if all_ruined:
                            # Balas del mes agotadas: pausar sin inyección artificial en el mismo día
                            pass

                    if bullet.get('pending_reset'):
                        if is_win:
                            safe_core += pnl
                        bullet['capital'] = bullet.pop('next_capital', bet_per_attempt)
                        bullet['consecutive_wins'] = 0
                        bullet['pending_reset'] = False

                    active_bullets_cap = sum(b['capital'] for b in bullets if not b.get('pending_reset'))
                    current_equity = safe_core + active_bullets_cap

                elif mode == 'REINVESTMENT':
                    if is_win:
                        pnl = bet_size * payout
                        current_equity += pnl
                        consecutive_wins_by_pair[pair] += 1
                        if consecutive_wins_by_pair[pair] >= n_consecutive:
                            consecutive_wins_by_pair[pair] = 0
                            base_capital_by_pair[pair] = base_capital_by_pair[pair] + pnl
                    else:
                        pnl = -bet_size
                        current_equity += pnl
                        consecutive_wins_by_pair[pair] = 0
                        base_capital_by_pair[pair] = max(0, base_capital_by_pair[pair] + pnl)

                else:
                    if is_win:
                        pnl = bet_size * payout
                    else:
                        pnl = -bet_size
                    current_equity += pnl

                trades.append({
                    'pair': pair,
                    'time': t['entry_time'],
                    'entry_time': t['entry_time'],
                    'exit_time': event['time'],
                    'direction': t['direction'],
                    'entry_price': t['entry_price'],
                    'sl_price': t['entry_price'] * 0.99 if t['direction'] == 'LONG' else t['entry_price'] * 1.01,
                    'tp_price': t['entry_price'] * 1.02 if t['direction'] == 'LONG' else t['entry_price'] * 0.98,
                    'exit_price': t['exit_price'],
                    'exit_reason': 'TP' if is_win else 'SL',
                    'duration': int(expiry_candles),
                    'holding_candles': int(expiry_candles),
                    'gross_return_pct': float(pnl / (bet_size if bet_size > 0 else 1.0)),
                    'net_return_pct': float(pnl / (bet_size if bet_size > 0 else 1.0)),
                    'r_multiple': float(pnl / (bet_size if bet_size > 0 else 1.0)),
                    'result': 'WIN' if is_win else 'LOSS',
                    'pnl': float(pnl),
                    'bet_size': float(bet_size),
                    'position_size': float(bet_size),
                    'index': t['index']
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
        total = len(trades)
        decisive = wins + losses

        win_rate = wins / total if total > 0 else 0
        win_rate_effective = wins / decisive if decisive > 0 else 0
        p_win_total = wins / total if total > 0 else 0
        p_loss_total = losses / total if total > 0 else 0
        expected_value_per_trade = (p_win_total * payout) - (p_loss_total * 1.0)
        net_pnl = sum(tr['pnl'] for tr in trades)

        pnl_arr = np.array([tr['pnl'] for tr in trades]) if trades else np.array([])
        gross_profit = float(np.sum(pnl_arr[pnl_arr > 0])) if len(pnl_arr) > 0 else 0.0
        gross_loss = float(np.abs(np.sum(pnl_arr[pnl_arr < 0]))) if len(pnl_arr) > 0 else 0.0
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        sharpe_ratio, _ = compute_sharpe_sortino(pnl_arr, initial_capital, total)

        eq_vals = [e['equity'] for e in equity_curve]
        peak = initial_capital
        max_dd = 0
        for eq in eq_vals:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        summary = {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": win_rate,
            "win_rate_effective": win_rate_effective,
            "profit_factor": profit_factor,
            "expected_value_per_trade": expected_value_per_trade,
            "expected_value_r": expected_value_per_trade,
            "sharpe_ratio": sharpe_ratio,
            "net_pnl": net_pnl,
            "max_drawdown": max_dd
        }

        return {
            "trades": trades,
            "equity_curve": equity_curve,
            "summary": summary
        }
