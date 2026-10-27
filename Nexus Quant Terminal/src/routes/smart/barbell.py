"""Endpoints de asignación asimétrica Barbell y optimización de rachas para Nexus Quant Terminal.
Implementa preservación de capital (80% bóveda segura, 20% riesgo dividido en bullets con Markov).
Referencia de diseño: docs/ARQUITECTURA.md"""
import os
import subprocess
import traceback
from flask import Blueprint, jsonify, request

from config import Config
from routes.utils import (
    optimizer,
    simulator,
    stats_engine,
    clean_json_data,
    extract_markov_params,
    is_safe_symbol,
    is_safe_interval,
    get_genetic_optimizer_path,
    extract_json_from_output,
    load_csv_data,
    get_data_dir,
    resolve_csv_filepath,
)
from strategies.genetic_composite import GeneticCompositeStrategy
from strategies.islg_rs import IslgRsStrategy
from strategies.deesr import DeesrStrategy
from strategies.climax_reversal import ClimaxReversalStrategy
from .formatters import (
    format_equity_curve,
    format_trades,
    format_signal_markers,
    format_mc_paths,
)

barbell_bp = Blueprint('smart_barbell', __name__)


@barbell_bp.route('/api/optimize-streak', methods=['POST'])
@barbell_bp.route('/api/smart/optimize-streak', methods=['POST'])
def run_optimize_streak():
    """Calculates mathematical streak ladder and Kelly bullet allocation for Barbell mode."""
    try:
        req = request.json or {}
        win_rate = float(req.get('win_rate', 0.55))
        payout = float(req.get('payout', 0.85))
        risk_capital = float(req.get('risk_capital', 200.0))
        target_capital = float(req.get('target_capital', 1000.0))
        attempts = int(req.get('attempts', 5))
        p_ww = float(req['p_ww']) if req.get('p_ww') is not None else None
        p_wl = float(req['p_wl']) if req.get('p_wl') is not None else None

        if not (0.0 <= win_rate <= 1.0):
            return jsonify({'error': 'win_rate debe estar entre 0.0 y 1.0.'}), 400
        if payout < 0.0 or payout > 2.0:
            return jsonify({'error': 'payout debe estar entre 0.0 y 2.0.'}), 400
        if risk_capital <= 0 or target_capital <= 0:
            return jsonify({'error': 'El capital de riesgo y el capital objetivo deben ser mayores a 0.'}), 400
        if target_capital <= risk_capital:
            return jsonify({'error': 'El capital objetivo debe ser mayor que el capital de riesgo.'}), 400
        if attempts < 1 or attempts > 100:
            return jsonify({'error': 'El número de intentos debe estar entre 1 y 100.'}), 400

        base_capital = float(req.get('base_capital', target_capital))
        result = optimizer.calculate_streak_plan(
            win_rate=win_rate,
            payout=payout,
            risk_capital=risk_capital,
            target_capital=target_capital,
            attempts=attempts,
            base_capital=base_capital,
            p_ww=p_ww,
            p_wl=p_wl
        )
        return jsonify(clean_json_data(result))

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@barbell_bp.route('/api/smart-optimize', methods=['POST'])
@barbell_bp.route('/api/smart/smart-optimize', methods=['POST'])
@barbell_bp.route('/api/smart/optimize-barbell', methods=['POST'])
def run_smart_optimize():
    """Runs synchronous single-pair Barbell optimization with Rust genetic search."""
    try:
        req = request.json or {}
        pair = req.get('pair', 'BTCUSDT')
        interval = req.get('interval', '1h')
        if not is_safe_symbol(pair) or not is_safe_interval(interval):
            return jsonify({'error': 'Par o intervalo no válido.'}), 400
        base_capital = float(req.get('base_capital', 1000.0))
        profit_pct = float(req.get('profit_pct', 20.0))
        attempts = int(req.get('attempts', 2))
        payout = float(req.get('payout', 0.85))

        if base_capital <= 0:
            return jsonify({'error': 'base_capital debe ser mayor a 0.'}), 400
        if not (0.0 < profit_pct <= 100.0):
            return jsonify({'error': 'profit_pct debe estar entre 0.0 y 100.0.'}), 400
        if attempts < 1 or attempts > 100:
            return jsonify({'error': 'attempts debe estar entre 1 y 100.'}), 400
        if payout < 0.0 or payout > 2.0:
            return jsonify({'error': 'payout debe estar entre 0.0 y 2.0.'}), 400

        # 1. Run the Rust genetic optimizer in the background to find the best strategy
        filename = f"{pair}_{interval}.csv"
        filepath = resolve_csv_filepath(filename)
        if not os.path.exists(filepath):
            return jsonify({'error': f'Datos no encontrados para {pair} {interval}'}), 404

        exe_path = get_genetic_optimizer_path()
        if not exe_path:
            return jsonify({'error': 'El ejecutable del optimizador genetico en Rust no ha sido compilado.'}), 500

        expiry_req = int(req.get('expiry', 1))
        min_trades_req = float(req.get('min_trades', 5.0))
        generations_req = int(req.get('generations', 60))
        population_req = int(req.get('population', 250))

        cmd = [
            exe_path,
            "--csv", filepath,
            "--expiry", str(expiry_req),
            "--min-trades", str(min_trades_req),
            "--generations", str(generations_req),
            "--population", str(population_req)
        ]

        result_rust = subprocess.run(cmd, capture_output=True, text=True, check=True)

        try:
            output_json = extract_json_from_output(result_rust.stdout)
        except Exception as json_err:
            return jsonify({
                'error': 'Error al parsear el JSON retornado por el optimizador genético.',
                'details': result_rust.stdout,
                'stderr': result_rust.stderr,
                'exception': str(json_err)
            }), 500

        if 'error' in output_json:
            return jsonify({'error': output_json['error']}), 500

        best_genome = output_json.get('parameters', {})
        win_rate = float(output_json.get('out_of_sample_win_rate', 0.55))
        in_sample_win_rate = float(output_json.get('in_sample_win_rate', 0.60))

        # 2. Run multi-strategy evaluation in python to pick the highest Win Rate strategy
        df = load_csv_data(pair, interval)
        if df is None:
            return jsonify({'error': f'Datos de velas no encontrados para {pair} {interval}'}), 404

        candidates = []

        # Candidate 1: Genetic Composite
        gen_strat = GeneticCompositeStrategy()
        gen_signals = gen_strat.generate_signals(df, best_genome)
        gen_res = simulator.run(df, gen_signals, expiry_candles=1, allow_overlapping=True)
        gen_wr = gen_res['summary']['win_rate_effective']
        candidates.append({
            'strategy_name': 'genetic_composite',
            'display_name': 'Optimizador Genético Rust',
            'strategy_obj': gen_strat,
            'expiry_candles': 1,
            'signals': gen_signals,
            'win_rate': gen_wr if gen_res['summary']['total_trades'] >= 5 else win_rate,
            'params': best_genome
        })

        # Candidate 2: ISLG Sweeps
        islg_strat = IslgRsStrategy()
        islg_params = {"lookback_period": 25, "min_sweep_atr_ratio": 0.10, "wick_ratio": 0.35, "vol_mult": 1.3, "rsi_period": 7}
        islg_signals = islg_strat.generate_signals(df, islg_params)
        islg_res = simulator.run(df, islg_signals, expiry_candles=1, allow_overlapping=True)
        if islg_res['summary']['total_trades'] >= 3:
            candidates.append({
                'strategy_name': 'islg_rs',
                'display_name': 'Barridos de Liquidez Institucional (ISLG)',
                'strategy_obj': islg_strat,
                'expiry_candles': 1,
                'signals': islg_signals,
                'win_rate': islg_res['summary']['win_rate_effective'],
                'params': islg_params
            })

        # Candidate 3: DEESR Extreme Reversal
        deesr_strat = DeesrStrategy()
        deesr_params = {"bb_period": 20, "bb_std": 2.0, "kc_period": 20, "kc_mult": 1.5, "rsi_fast_period": 3, "rsi_slow_period": 14, "max_body_ratio": 0.55, "min_wick_ratio": 0.30}
        deesr_signals = deesr_strat.generate_signals(df, deesr_params)
        deesr_res = simulator.run(df, deesr_signals, expiry_candles=1, allow_overlapping=True)
        if deesr_res['summary']['total_trades'] >= 3:
            candidates.append({
                'strategy_name': 'deesr',
                'display_name': 'Doble Envoltura Extrema (DEESR)',
                'strategy_obj': deesr_strat,
                'expiry_candles': 1,
                'signals': deesr_signals,
                'win_rate': deesr_res['summary']['win_rate_effective'],
                'params': deesr_params
            })

        # Candidate 4: Climax Reversal
        climax_strat = ClimaxReversalStrategy()
        climax_params = {"streak_len": 3, "wick_ratio": 0.35, "vol_mult": 1.3, "rsi_period": 7}
        climax_signals = climax_strat.generate_signals(df, climax_params)
        climax_res = simulator.run(df, climax_signals, expiry_candles=3, allow_overlapping=True)
        if climax_res['summary']['total_trades'] >= 3:
            candidates.append({
                'strategy_name': 'climax_reversal',
                'display_name': 'Agotamiento Clímax por Rachas',
                'strategy_obj': climax_strat,
                'expiry_candles': 3,
                'signals': climax_signals,
                'win_rate': climax_res['summary']['win_rate_effective'],
                'params': climax_params
            })

        best_cand = max(candidates, key=lambda c: c['win_rate'])
        expiry_candles = best_cand.get('expiry_candles', 1)
        signals = best_cand['signals']
        win_rate = float(best_cand['win_rate'])
        best_genome = best_cand['params']

        risk_capital = base_capital * (profit_pct / 100.0)
        target_capital = base_capital
        bet_fraction = 1.0 / attempts

        streak_plan = optimizer.calculate_streak_plan(
            win_rate=win_rate,
            payout=payout,
            risk_capital=risk_capital,
            target_capital=target_capital,
            attempts=attempts,
            base_capital=base_capital
        )
        optimal_n = streak_plan.get('best_n_for_target', 4)

        sim_results = simulator.run(
            df, signals,
            expiry_candles=expiry_candles,
            payout=payout,
            initial_capital=base_capital,
            mode='BARBELL',
            n_consecutive=optimal_n,
            bet_fraction=bet_fraction,
            risk_ratio=profit_pct / 100.0,
            target_ratio=target_capital / risk_capital
        )

        trades = sim_results['trades']
        stats = {}
        if len(trades) > 0:
            stats = stats_engine.analyze(trades, df=df)
        p_ww, p_wl = extract_markov_params(stats)
        if p_ww and p_wl:
            streak_plan = optimizer.calculate_streak_plan(
                win_rate=win_rate,
                payout=payout,
                risk_capital=risk_capital,
                target_capital=target_capital,
                attempts=attempts,
                base_capital=base_capital,
                p_ww=p_ww,
                p_wl=p_wl
            )

        signal_markers = format_signal_markers(df, signals, max_markers=500)
        equity_curve = format_equity_curve(sim_results['equity_curve'], max_points=500, use_preserve_peaks=True)
        formatted_trades_display = format_trades(trades)

        mc_results = optimizer.monte_carlo_discrete(
            win_rate=win_rate,
            payout=payout,
            n_consecutive=optimal_n,
            bet_fraction=bet_fraction,
            risk_capital=risk_capital,
            target_capital=target_capital,
            num_simulations=5000,
            p_ww=p_ww,
            p_wl=p_wl
        )

        mc_paths_results = optimizer.monte_carlo(
            win_rate=win_rate,
            payout=payout,
            n=optimal_n,
            kelly_f=bet_fraction,
            num_simulations=1000,
            num_cycles=200,
            p_ww=p_ww,
            p_wl=p_wl
        )

        paths = format_mc_paths(mc_paths_results, risk_capital=risk_capital, max_paths=30, max_points=100)

        s_single = (win_rate * (p_ww ** (optimal_n - 1))) if (p_ww and optimal_n > 1) else (win_rate ** optimal_n)
        p_campaign_parallel_1day = 1.0 - (1.0 - s_single) ** attempts if s_single < 1.0 else 1.0
        p_formatted = round(p_campaign_parallel_1day * 100, 1)

        response = {
            'best_genome': best_genome,
            'win_rate_oos': win_rate,
            'win_rate_is': in_sample_win_rate,
            'high_performance_pool': Config.HIGH_PERFORMANCE_PAIRS,
            'parallel_campaign_1day_prob': p_campaign_parallel_1day,
            'parallel_note': f'Al ejecutar los {attempts} intentos de forma simultánea en paralelo sobre activos del Pool, la probabilidad calculada en tiempo real es del {p_formatted}% con efecto de retorno convexo.',
            'streak_plan': streak_plan,
            'sim_summary': sim_results['summary'],
            'equity_curve': equity_curve,
            'trades': formatted_trades_display,
            'stats': stats,
            'signals': signal_markers,
            'mc_discrete': mc_results,
            'mc_paths': paths,
            'mc_summary': {
                'ruin_probability': mc_paths_results.get('ruin_probability', 0.0),
                'max_drawdowns': mc_paths_results.get('max_drawdowns', {})
            }
        }
        return jsonify(clean_json_data(response))

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
