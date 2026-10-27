"""Formateadores de telemetría, curvas de equidad y constructores de grillas para Smart Mode.
Normaliza series temporales, marcadores de señales y perfiles de estrategias para las rutas SSE/HTTP.
Referencia de diseño: docs/ARQUITECTURA.md"""

import random as _rng
from typing import Any, Dict, List, Optional

import pandas as pd

from engine.services.runtime_context import preserve_peaks_subsample
from engine.simulator import BinarySimulator
from strategies.climax_reversal import ClimaxReversalStrategy
from strategies.daily_confluence import DailyConfluenceStrategy
from strategies.deesr import DeesrStrategy
from strategies.islg_rs import IslgRsStrategy
from strategies.volatility_squeeze_ml import VolatilitySqueezeMLStrategy


def format_equity_curve(
    raw_curve: List[Dict[str, Any]],
    max_points: int = 500,
    use_preserve_peaks: bool = True,
) -> List[Dict[str, Any]]:
    """Normalizes equity timestamps to seconds and subsamples if points exceed limit."""
    equity_curve: List[Dict[str, Any]] = []
    for ec in raw_curve:
        t = ec.get('time')
        if t is not None:
            t_val = float(t)
            if t_val > 2**32:
                t_val = t_val / 1000.0
            equity_curve.append({'time': int(t_val), 'equity': ec.get('equity', 0.0)})

    if len(equity_curve) > max_points:
        if use_preserve_peaks:
            equity_curve = preserve_peaks_subsample(equity_curve, max_points=max_points, key='equity')
        else:
            step = len(equity_curve) // max_points
            equity_curve = equity_curve[::step]

    return equity_curve


def format_trades(trades: List[Dict[str, Any]], max_trades: Optional[int] = None) -> List[Dict[str, Any]]:
    """Formats simulation trades with normalized seconds timestamps."""
    formatted_trades: List[Dict[str, Any]] = []
    for trade in trades:
        t = trade.get('time')
        t_val: Optional[int] = None
        if t is not None:
            t_float = float(t)
            if t_float > 2**32:
                t_float = t_float / 1000.0
            t_val = int(t_float)

        item = {
            'time': t_val,
            'direction': trade.get('direction'),
            'entry_price': trade.get('entry_price'),
            'exit_price': trade.get('exit_price'),
            'result': trade.get('result'),
            'pnl': trade.get('pnl'),
        }
        if 'index' in trade:
            item['index'] = trade['index']
        formatted_trades.append(item)

    if max_trades and len(formatted_trades) > max_trades:
        return formatted_trades[-max_trades:]
    return formatted_trades


def format_signal_markers(
    df: Optional[pd.DataFrame] = None,
    signals: Any = None,
    max_markers: int = 500,
) -> List[Dict[str, Any]]:
    """Extracts lightweight chart signal markers capped at max_markers."""
    signal_markers: List[Dict[str, Any]] = []

    if isinstance(signals, list):
        for sig in signals:
            t_sig = sig.get('time', 0)
            t_sig_sec = int(t_sig / 1000) if t_sig > 2**32 else int(t_sig)
            signal_markers.append({
                'time': t_sig_sec,
                'direction': sig.get('direction'),
            })
    elif df is not None and hasattr(signals, 'index'):
        for _, row in df.iterrows():
            idx = row.name
            if idx in signals.index and signals.loc[idx] is not None and signals.loc[idx] in ['CALL', 'PUT']:
                signal_markers.append({
                    'time': int(row['time']),
                    'direction': signals.loc[idx],
                    'price': float(row['close']),
                })

    if len(signal_markers) > max_markers:
        return signal_markers[-max_markers:]
    return signal_markers


def format_mc_paths(
    mc_results: Dict[str, Any],
    risk_capital: float = 1.0,
    max_paths: int = 30,
    max_points: int = 100,
) -> List[List[float]]:
    """Formats Monte Carlo trajectories for lightweight front-end chart rendering."""
    paths: List[List[float]] = []
    if 'paths' in mc_results and mc_results['paths']:
        for path in mc_results['paths'][:max_paths]:
            if risk_capital != 1.0:
                scaled_path = [p * risk_capital for p in path]
            else:
                scaled_path = path

            if len(scaled_path) > max_points:
                step = len(scaled_path) // max_points
                paths.append(scaled_path[::step])
            else:
                paths.append(scaled_path)
    return paths


def _sample_grid(full_grid: List[Any], max_n: int) -> List[Any]:
    """Subsamples parameter grid if too large, preserving the first (default) entry."""
    if len(full_grid) <= max_n:
        return full_grid
    return [full_grid[0]] + _rng.sample(full_grid[1:], max_n - 1)


def build_parameter_grids(population: int, generations: int) -> Dict[str, Any]:
    """Builds search grids for all 5 complex institutional strategies scaled by budget."""
    _rng.seed(42)
    search_budget = min(population * generations // 50, 200)

    if search_budget >= 80:
        lookbacks_grid = [10, 15, 20, 25, 30, 35, 40, 50]
        wicks_grid = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
        vols_grid = [1.0, 1.2, 1.3, 1.5, 1.8]
        bb_stds_grid = [1.8, 2.0, 2.2, 2.5]
        kc_mults_grid = [1.2, 1.5, 1.8, 2.0]
        ml_thresholds_grid = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
        pullback_grid = [0.003, 0.005, 0.008, 0.010, 0.012, 0.015]
    elif search_budget >= 30:
        lookbacks_grid = [15, 25, 35, 50]
        wicks_grid = [0.35, 0.40, 0.50, 0.60]
        vols_grid = [1.0, 1.3, 1.8]
        bb_stds_grid = [2.0, 2.2, 2.5]
        kc_mults_grid = [1.5, 1.8]
        ml_thresholds_grid = [0.60, 0.65, 0.70, 0.75]
        pullback_grid = [0.005, 0.008, 0.012]
    else:
        lookbacks_grid = [25, 50]
        wicks_grid = [0.40, 0.55]
        vols_grid = [1.3, 1.8]
        bb_stds_grid = [2.0, 2.5]
        kc_mults_grid = [1.5]
        ml_thresholds_grid = [0.52, 0.55]
        pullback_grid = [0.008, 0.012]

    per_strat_budget = max(3, search_budget // 5)

    islg_full = [
        {'lookback_period': l, 'wick_ratio': w, 'vol_mult': v, 'rsi_period': 7}
        for l in lookbacks_grid for w in wicks_grid for v in vols_grid[:3]
    ]
    climax_full = [
        {'streak_len': s, 'wick_ratio': w, 'vol_mult': vm}
        for s in [3, 4] for w in wicks_grid[:4] for vm in vols_grid[:2]
    ]
    deesr_full = [
        {
            'bb_period': 20, 'bb_std': std, 'kc_period': 20, 'kc_mult': km,
            'rsi_fast_period': 3, 'rsi_slow_period': 14, 'min_wick_ratio': w,
        }
        for std in bb_stds_grid for km in kc_mults_grid for w in wicks_grid[:3]
    ]
    ml_full = [
        {'bb_pctl_thresh': bp, 'prob_thresh': pt, 'use_mtf': mtf}
        for bp in [0.25, 0.35, 0.45] for pt in ml_thresholds_grid for mtf in [True, False]
    ]
    conf_full = [{'pullback_tolerance': tol} for tol in pullback_grid]

    return {
        'islg': _sample_grid(islg_full, per_strat_budget),
        'climax': _sample_grid(climax_full, per_strat_budget),
        'deesr': _sample_grid(deesr_full, per_strat_budget),
        'ml': _sample_grid(ml_full, per_strat_budget),
        'conf': _sample_grid(conf_full, per_strat_budget),
        'per_strat_budget': per_strat_budget,
    }


def build_strategy_candidates(grids: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Returns candidate structures for the 5 quantitative institutional strategies."""
    return [
        {
            'name': 'islg_rs',
            'display_name': '🥇 Barridos de Liquidez (ISLG)',
            'description': 'Barridos institucionales de máximos/mínimos con mecha de rechazo y spike de volumen.',
            'strategy_obj': IslgRsStrategy(),
            'param_grid': grids['islg'],
            'expiry': 1,
        },
        {
            'name': 'climax_reversal',
            'display_name': '🥈 Agotamiento Clímax (Streak)',
            'description': 'Velas consecutivas rebotando en S/R con pérdida de cuerpo y volumen clímax.',
            'strategy_obj': ClimaxReversalStrategy(),
            'param_grid': grids['climax'],
            'expiry': 3,
        },
        {
            'name': 'deesr',
            'display_name': '🥉 Doble Envoltura Extrema (DEESR)',
            'description': 'Estiramiento por fuera de Bandas de Bollinger y Keltner con RSI(3) en extremos.',
            'strategy_obj': DeesrStrategy(),
            'param_grid': grids['deesr'],
            'expiry': 2,
        },
        {
            'name': 'volatility_squeeze_ml',
            'display_name': '⚡ Volatility Squeeze + ML',
            'description': 'Rupturas de volatilidad comprimida filtradas por GBDT con Walk-Forward OOS.',
            'strategy_obj': VolatilitySqueezeMLStrategy(),
            'param_grid': grids['ml'],
            'expiry': 1,
        },
        {
            'name': 'daily_confluence',
            'display_name': '🌐 Confluencia Diaria Multi-Activo',
            'description': 'Alineación multi-temporal macro con pullbacks de precisión sobre el universo no correlacionado.',
            'strategy_obj': DailyConfluenceStrategy(),
            'param_grid': grids['conf'],
            'expiry': 2,
        },
    ]


def build_strategy_profiles(best_genome: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Builds top-5 strategy profile definitions based on the best discovered genetic genome."""
    base_rsi = int(best_genome.get('rsi_period', 14)) if best_genome else 14
    base_bb = int(best_genome.get('bb_period', 20)) if best_genome else 20
    base_std = float(best_genome.get('bb_std', 2.0)) if best_genome else 2.0

    return [
        {
            "id": 1,
            "name": "🏆 Confluencia Genética Total",
            "type": "genetic_composite",
            "genome": best_genome,
            "description": f"Genoma cuantitativo hallado por el motor genético (RSI {base_rsi}, BB {base_bb}, std {base_std}).",
        },
        {
            "id": 2,
            "name": "⚡ Reversión Rápida Momentum",
            "type": "rsi_bollinger_fast",
            "genome": {
                "rsi_period": max(5, base_rsi - 4),
                "rsi_oversold": 30.0,
                "rsi_overbought": 70.0,
                "rsi_enabled": True,
                "bb_period": max(10, base_bb - 4),
                "bb_std": max(1.2, round(base_std - 0.2, 1)),
                "bb_enabled": True,
                "ema_enabled": False,
            },
            "description": f"Variante adaptativa de alta frecuencia (RSI {max(5, base_rsi - 4)}, BB {max(10, base_bb - 4)}).",
        },
        {
            "id": 3,
            "name": "📈 Seguimiento de Tendencia Macro",
            "type": "trend_following_ema",
            "genome": {
                "rsi_period": base_rsi,
                "rsi_oversold": 40.0,
                "rsi_overbought": 60.0,
                "rsi_enabled": True,
                "bb_enabled": False,
                "ema_fast_period": 9,
                "ema_slow_period": 21,
                "ema_enabled": True,
            },
            "description": "Variante tendencial macro con confirmación EMA (EMA 9/21, RSI Pullback).",
        },
        {
            "id": 4,
            "name": "🛡️ Conservadora Filtro de Rechazo",
            "type": "rejection_pinbar",
            "genome": {
                "rsi_period": base_rsi + 2,
                "rsi_oversold": 32.0,
                "rsi_overbought": 68.0,
                "rsi_enabled": True,
                "bb_enabled": False,
                "rejection_filter_enabled": True,
                "pinbar_wick_ratio": 0.35,
            },
            "description": f"Variante defensiva con filtro de rechazo mecha Pinbar (RSI {base_rsi + 2}).",
        },
        {
            "id": 5,
            "name": "💥 Breakout & Volatilidad Squeeze",
            "type": "volatility_breakout",
            "genome": {
                "rsi_enabled": False,
                "bb_period": base_bb,
                "bb_std": max(1.2, round(base_std - 0.3, 1)),
                "bb_enabled": True,
                "volatility_filter_enabled": True,
                "min_bb_width": 0.0,
            },
            "description": "Variante de ruptura de volatilidad (Squeeze) basada en compresión adaptativa de bandas.",
        },
    ]


def get_strat_score(st: Dict[str, Any]) -> tuple:
    """Computes ranking tuple (ev, pf, pnl, wr) for ordering strategies dynamically."""
    summary = st.get('sim_summary', {})
    ev = summary.get('expected_value_per_trade', 0.0)
    pf = summary.get('profit_factor', 1.0)
    pnl = summary.get('net_pnl', 0.0)
    wr = st.get('win_rate_oos', 0.0)
    return (ev, pf, pnl, wr)


def generate_multi_asset_signals(
    strat_obj: Any,
    universe_dict: Dict[str, pd.DataFrame],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Generates signals across all assets in a universe for given strategy and parameter set."""
    sigs_by_pair: Dict[str, Any] = {}
    for symbol, df in universe_dict.items():
        if hasattr(strat_obj, 'generate_signals_list'):
            sigs_by_pair[symbol] = strat_obj.generate_signals_list(df, params=params)
        else:
            raw_sigs = strat_obj.generate_signals(df, params)
            if isinstance(raw_sigs, pd.Series):
                time_col = df['time'] if 'time' in df.columns else df['open_time']
                sigs_list = []
                for idx, val in raw_sigs.items():
                    if pd.notna(val) and val in ['CALL', 'PUT']:
                        t_val = time_col.loc[idx] if idx in time_col.index else idx
                        sigs_list.append({'time': t_val, 'direction': val})
                sigs_by_pair[symbol] = sigs_list
            else:
                sigs_by_pair[symbol] = raw_sigs
    return sigs_by_pair


def tune_strategy_on_in_sample(
    strat_obj: Any,
    param_grid: List[Dict[str, Any]],
    expiry: int,
    is_universe: Dict[str, pd.DataFrame],
    sim_inst: BinarySimulator,
    payout: float,
    base_capital: float,
) -> Dict[str, Any]:
    """Sweeps parameter grid on In-Sample window (70%) to pick parameters with maximum win rate."""
    best_params = param_grid[0]
    best_is_wr = -1.0
    for p_combo in param_grid:
        sigs_is = generate_multi_asset_signals(strat_obj, is_universe, p_combo)
        sim_is = sim_inst.run_multi_asset(
            universe_data=is_universe,
            signals_by_pair=sigs_is,
            expiry_candles=expiry,
            payout=payout,
            initial_capital=base_capital,
        )
        decisive = [t for t in sim_is['trades'] if t['result'] in ['WIN', 'LOSS']]
        wr_is = sum(1 for t in decisive if t['result'] == 'WIN') / len(decisive) if len(decisive) >= 3 else 0.0
        if wr_is > best_is_wr:
            best_is_wr = wr_is
            best_params = p_combo
    return best_params


def compute_is_oos_trades_metrics(c_trades: List[Dict[str, Any]]) -> tuple:
    """Splits simulation trades into 70% In-Sample and 30% Out-of-Sample metrics."""
    if len(c_trades) > 0:
        c_min_t = min(t['time'] for t in c_trades)
        c_max_t = max(t['time'] for t in c_trades)
        c_split_t = c_min_t + 0.7 * (c_max_t - c_min_t)
        c_trades_is = [t for t in c_trades if t['time'] < c_split_t]
        c_trades_oos = [t for t in c_trades if t['time'] >= c_split_t]
        c_decisive_is = [t for t in c_trades_is if t['result'] in ['WIN', 'LOSS']]
        c_wins_is = sum(1 for t in c_decisive_is if t['result'] == 'WIN')
        c_wr_is = c_wins_is / len(c_decisive_is) if len(c_decisive_is) > 0 else 0.50
        c_decisive_oos = [t for t in c_trades_oos if t['result'] in ['WIN', 'LOSS']]
        c_wins_oos = sum(1 for t in c_decisive_oos if t['result'] == 'WIN')
        c_wr_oos = c_wins_oos / len(c_decisive_oos) if len(c_decisive_oos) > 0 else 0.50
    else:
        c_wr_is, c_wr_oos = 0.50, 0.50
        c_trades_oos = []
    return c_wr_is, c_wr_oos, c_trades_oos
