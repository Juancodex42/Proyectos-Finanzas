"""Endpoints de optimización multi-activo y filtrado de correlación para Nexus Quant Terminal.
Coordina búsqueda paramétrica en grilla, selección de carteras no correlacionadas y streaming SSE.
Referencia de diseño: docs/ARQUITECTURA.md"""
import json
import traceback
from typing import List, Dict, Any
import pandas as pd
from flask import Blueprint, jsonify, request

from routes.utils import (
    optimizer,
    clean_json_data,
    is_safe_symbol,
    is_safe_interval,
    get_data_dir,
    extract_markov_params,
    sse_response,
)
from engine.correlation import CorrelationEngine
from engine.simulator import BinarySimulator
from engine.optimizer import CapitalOptimizer
from engine.statistics import StatisticsEngine
from engine.services.smart_optimizer_service import stream_smart_optimize_v2
from .stream_v1 import stream_smart_optimize_v1
from .formatters import (
    build_parameter_grids,
    build_strategy_candidates,
    format_equity_curve,
    format_signal_markers,
    format_mc_paths,
    generate_multi_asset_signals,
    tune_strategy_on_in_sample,
    compute_is_oos_trades_metrics,
)

optimizer_bp = Blueprint('smart_optimizer', __name__)


@optimizer_bp.route('/api/optimize', methods=['POST'])
@optimizer_bp.route('/api/smart/optimize', methods=['POST'])
def run_optimize():
    """Runs parameter sweep to find optimal consecutive streak length N."""
    try:
        req = request.json or {}
        win_rate = float(req.get('win_rate', 0.5))
        payout = float(req.get('payout', 0.92))
        max_n = int(req.get('max_n', 15))

        if not (0.0 <= win_rate <= 1.0):
            return jsonify({'error': 'win_rate debe estar entre 0.0 y 1.0.'}), 400
        if payout < 0.0 or payout > 2.0:
            return jsonify({'error': 'payout debe estar entre 0.0 y 2.0.'}), 400
        if max_n < 1 or max_n > 50:
            return jsonify({'error': 'max_n debe estar entre 1 y 50.'}), 400

        result = optimizer.find_optimal_n(win_rate, payout, max_n)
        if isinstance(result, dict) and 'error' in result:
            return jsonify(clean_json_data(result)), 400
        return jsonify(clean_json_data(result))

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@optimizer_bp.route('/api/smart-optimize-v2', methods=['POST'])
@optimizer_bp.route('/api/smart/smart-optimize-v2', methods=['POST'])
@optimizer_bp.route('/api/smart/optimize-v2', methods=['POST'])
def run_smart_optimize_v2():
    """Executes Smart Mode V2 multi-asset correlation filtering, strategy tuning, and ranking."""
    try:
        req = request.json or {}
        base_capital = float(req.get('base_capital', 1000.0))
        profit_pct = float(req.get('profit_pct', 20.0))
        attempts = int(req.get('attempts', 6))
        payout = float(req.get('payout', 0.85))
        streak_length = int(req.get('streak_length', 3))
        generations = int(req.get('generations', 50))
        population = int(req.get('population', 150))

        if base_capital <= 0:
            return jsonify({'error': 'base_capital debe ser mayor a 0.'}), 400
        if not (0.0 < profit_pct <= 100.0):
            return jsonify({'error': 'profit_pct debe estar entre 0.0 y 100.0.'}), 400
        if attempts < 1 or attempts > 100:
            return jsonify({'error': 'attempts debe estar entre 1 y 100.'}), 400
        if payout < 0.0 or payout > 2.0:
            return jsonify({'error': 'payout debe estar entre 0.0 y 2.0.'}), 400
        if streak_length < 1 or streak_length > 50:
            return jsonify({'error': 'streak_length debe estar entre 1 y 50.'}), 400

        default_universe = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
            "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT", "DOTUSDT"
        ]
        universe = req.get('universe', default_universe)
        if isinstance(universe, str):
            universe = [s.strip() for s in universe.split(',') if s.strip()]
        if not universe or len(universe) == 0:
            universe = default_universe

        for symbol in universe:
            if not is_safe_symbol(symbol):
                return jsonify({'error': f'Activo no válido en el universo: {symbol}'}), 400

        # 1. Cargar datos del universo
        corr_engine = CorrelationEngine(get_data_dir())
        universe_data = corr_engine.load_universe(universe)
        if not universe_data:
            return jsonify({'error': 'No se pudieron cargar datos para ningún activo del universo.'}), 400

        # 2. Matriz de correlación y filtro de activos In-Sample (70%) para evitar data leakage
        is_universe_data = {
            symbol: df.iloc[:int(len(df) * 0.7)].copy()
            for symbol, df in universe_data.items()
            if len(df) > 0
        }
        corr_matrix, _ = corr_engine.compute_correlation_matrix(is_universe_data)
        selected_assets = corr_engine.select_uncorrelated_assets(corr_matrix, threshold=0.65)
        if not selected_assets:
            selected_assets = list(universe_data.keys())

        filtered_universe_data = {s: universe_data[s] for s in selected_assets if s in universe_data}

        # 3. Afinación paramétrica de las 5 Estrategias Cuánticas
        grids = build_parameter_grids(population, generations)
        strategy_candidates = build_strategy_candidates(grids)

        evaluated_strategies: List[Dict[str, Any]] = []
        sim_inst = BinarySimulator()
        is_universe = {s: df.iloc[:int(len(df) * 0.7)].copy() for s, df in filtered_universe_data.items() if len(df) > 0}

        for cand in strategy_candidates:
            strat_obj = cand['strategy_obj']
            best_params = tune_strategy_on_in_sample(
                strat_obj=strat_obj,
                param_grid=cand['param_grid'],
                expiry=cand['expiry'],
                is_universe=is_universe,
                sim_inst=sim_inst,
                payout=payout,
                base_capital=base_capital
            )

            sigs_by_pair = generate_multi_asset_signals(strat_obj, filtered_universe_data, best_params)
            sim_res = sim_inst.run_multi_asset(
                universe_data=filtered_universe_data,
                signals_by_pair=sigs_by_pair,
                expiry_candles=cand['expiry'],
                payout=payout,
                initial_capital=base_capital,
                mode='BARBELL',
                n_consecutive=streak_length,
                bet_fraction=(1.0 / attempts),
                risk_ratio=(profit_pct / 100.0),
                target_ratio=(base_capital / (base_capital * (profit_pct / 100.0)))
            )

            c_trades = sim_res['trades']
            c_wr_is, c_wr_oos, c_trades_oos = compute_is_oos_trades_metrics(c_trades)

            evaluated_strategies.append({
                'name': cand['name'],
                'display_name': cand['display_name'],
                'description': cand['description'],
                'win_rate_oos': float(c_wr_oos),
                'win_rate_is': float(c_wr_is),
                'win_rate': float(c_wr_oos),
                'trades_count': len(c_trades_oos),
                'params': best_params,
                'sim_results': sim_res,
                'trades_oos': c_trades_oos,
                'signals_by_pair': sigs_by_pair
            })

        evaluated_strategies.sort(key=lambda s: s['win_rate_oos'], reverse=True)
        best_strategy = evaluated_strategies[0]

        sim_results = best_strategy['sim_results']
        trades_oos = best_strategy['trades_oos']
        win_rate_oos = best_strategy['win_rate_oos']
        win_rate_is = best_strategy['win_rate_is']
        signals_by_pair = best_strategy['signals_by_pair']

        stats_engine_inst = StatisticsEngine()
        stats: Dict[str, Any] = {}
        if len(trades_oos) > 0:
            formatted_trades_oos = [
                {
                    'index': t['index'],
                    'time': int(t['time']),
                    'direction': t['direction'],
                    'entry_price': t['entry_price'],
                    'exit_price': t['exit_price'],
                    'result': t['result'],
                    'pnl': t['pnl']
                }
                for t in trades_oos
            ]
            stats = stats_engine_inst.analyze(formatted_trades_oos)
        p_ww, p_wl = extract_markov_params(stats)

        cap_optimizer = CapitalOptimizer()
        risk_capital = base_capital * (profit_pct / 100.0)
        target_capital = base_capital

        streak_plan = cap_optimizer.calculate_streak_plan(
            win_rate=win_rate_oos,
            payout=payout,
            risk_capital=risk_capital,
            target_capital=target_capital,
            attempts=attempts,
            base_capital=base_capital,
            p_ww=p_ww,
            p_wl=p_wl
        )

        mc_results = cap_optimizer.monte_carlo_campaign(
            win_rate=win_rate_oos,
            payout=payout,
            n_streak=streak_length,
            k_attempts=attempts,
            bet_per_attempt=(risk_capital / attempts),
            num_simulations=5000,
            p_ww=p_ww,
            p_wl=p_wl
        )

        equity_curve = format_equity_curve(sim_results['equity_curve'], max_points=500, use_preserve_peaks=False)
        first_asset = selected_assets[0] if len(selected_assets) > 0 else 'BTCUSDT'
        signal_markers = format_signal_markers(signals=signals_by_pair.get(first_asset, []), max_markers=500)

        if selected_assets and all(a in corr_matrix.columns for a in selected_assets):
            sub_corr = corr_matrix.loc[selected_assets, selected_assets]
            corr_labels = list(sub_corr.columns)
            corr_values = sub_corr.values.tolist()
        else:
            corr_labels = list(corr_matrix.columns)
            corr_values = corr_matrix.values.tolist()

        paths = format_mc_paths(mc_results, risk_capital=1.0, max_paths=30, max_points=100)

        asset_win_rates: Dict[str, float] = {}
        for asset in selected_assets:
            asset_trades_oos = [t for t in trades_oos if t.get('pair') == asset]
            if len(asset_trades_oos) > 0:
                asset_win_rates[asset] = sum(1 for t in asset_trades_oos if t['result'] == 'WIN') / len(asset_trades_oos)
            else:
                asset_trades_all = [t for t in sim_results['trades'] if t.get('pair') == asset]
                if len(asset_trades_all) > 0:
                    asset_win_rates[asset] = sum(1 for t in asset_trades_all if t['result'] == 'WIN') / len(asset_trades_all)
                else:
                    asset_win_rates[asset] = win_rate_oos

        top_strategies = [
            {
                'name': s['name'],
                'display_name': s['display_name'],
                'canonical_name': f"{s['name'].upper()}_{first_asset}_1D",
                'full_display_title': f"{s['display_name']} · [{first_asset} · 1D]",
                'asset': first_asset,
                'target_asset': first_asset,
                'timeframe': '1D',
                'description': s['description'],
                'win_rate_oos': s['win_rate_oos'],
                'win_rate': s['win_rate'],
                'trades_count': s['trades_count'],
                'params': s['params']
            }
            for s in evaluated_strategies
        ]

        response = {
            'win_rate_oos': win_rate_oos,
            'win_rate_is': win_rate_is,
            'top_strategies': top_strategies,
            'asset_win_rates': asset_win_rates,
            'selected_assets': selected_assets,
            'correlation_matrix': {
                'labels': corr_labels,
                'matrix': corr_values
            },
            'streak_plan': streak_plan,
            'sim_summary': sim_results['summary'],
            'equity_curve': equity_curve,
            'trades': trades_oos,
            'stats': stats,
            'signals': signal_markers,
            'mc_discrete': {
                'success_probability': mc_results['success_probability'],
                'ruin_probability': mc_results['ruin_probability'],
                'expected_value': mc_results['expected_value'],
                'mean_final_capital': mc_results['mean_final_capital']
            },
            'mc_paths': paths
        }
        return jsonify(clean_json_data(response))

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@optimizer_bp.route('/api/smart-optimize-v2-stream', methods=['GET'])
@optimizer_bp.route('/api/smart/smart-optimize-v2-stream', methods=['GET'])
@optimizer_bp.route('/api/smart/optimize-v2-stream', methods=['GET'])
def run_smart_optimize_v2_stream():
    """Streams Server-Sent Events (SSE) for Smart Mode V2 portfolio optimization."""
    try:
        base_capital = float(request.args.get('base_capital', 1000.0))
        profit_pct = float(request.args.get('profit_pct', 20.0))
        attempts = int(request.args.get('attempts', 6))
        payout = float(request.args.get('payout', 2.0))
        streak_length = int(request.args.get('streak_length', 3))
        population = int(request.args.get('population', 150))
        generations = int(request.args.get('generations', 50))
    except (ValueError, TypeError) as err:
        return jsonify({'error': f'Parámetros numéricos inválidos: {err}'}), 400

    if base_capital <= 0:
        return jsonify({'error': 'base_capital debe ser mayor que 0'}), 400
    if profit_pct <= 0:
        return jsonify({'error': 'profit_pct debe ser mayor que 0'}), 400
    if attempts < 1:
        return jsonify({'error': 'attempts debe ser al menos 1'}), 400
    if streak_length < 1:
        streak_length = 1

    population = max(10, min(1000, population))
    generations = max(5, min(500, generations))

    raw_universe = request.args.get('universe', '')
    default_universe = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
        "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT", "DOTUSDT"
    ]
    if raw_universe:
        try:
            universe = json.loads(raw_universe)
        except Exception:
            universe = [u.strip() for u in raw_universe.split(',') if u.strip()]
    else:
        universe = default_universe

    if not isinstance(universe, list) or not universe:
        return jsonify({'error': 'Formato de universo inválido.'}), 400
    for symbol in universe:
        if not is_safe_symbol(str(symbol)):
            return jsonify({'error': f'Activo no válido en el universo: {symbol}'}), 400

    generator = stream_smart_optimize_v2(
        base_capital=base_capital,
        profit_pct=profit_pct,
        attempts=attempts,
        payout=payout,
        streak_length=streak_length,
        population=population,
        generations=generations,
        universe=universe
    )
    return sse_response(generator)


@optimizer_bp.route('/api/smart-optimize-stream', methods=['GET'])
@optimizer_bp.route('/api/smart/smart-optimize-stream', methods=['GET'])
@optimizer_bp.route('/api/smart/optimize-stream', methods=['GET'])
def run_smart_optimize_stream():
    """Streams Server-Sent Events (SSE) for legacy Smart Mode V1 single-pair optimization."""
    pair = request.args.get('pair', 'BTCUSDT')
    interval = request.args.get('interval', '1h')
    if not is_safe_symbol(pair) or not is_safe_interval(interval):
        return jsonify({'error': 'Par o intervalo no válido.'}), 400

    try:
        base_capital = float(request.args.get('base_capital', 1000.0))
        profit_pct = float(request.args.get('profit_pct', 20.0))
        attempts = int(request.args.get('attempts', 2))
        payout = float(request.args.get('payout', 0.85))
    except (ValueError, TypeError) as err:
        return jsonify({'error': f'Parámetros numéricos inválidos: {err}'}), 400

    if base_capital <= 0:
        return jsonify({'error': 'base_capital debe ser mayor a 0.'}), 400
    if not (0.0 < profit_pct <= 100.0):
        return jsonify({'error': 'profit_pct debe estar entre 0.0 y 100.0.'}), 400
    if attempts < 1 or attempts > 100:
        return jsonify({'error': 'attempts debe estar entre 1 y 100.'}), 400
    if payout < 0.0 or payout > 2.0:
        return jsonify({'error': 'payout debe estar entre 0.0 y 2.0.'}), 400

    generator = stream_smart_optimize_v1(
        pair=pair,
        interval=interval,
        base_capital=base_capital,
        profit_pct=profit_pct,
        attempts=attempts,
        payout=payout
    )
    return sse_response(generator)
