"""Pipeline de streaming SSE v1 para optimización inteligente híbrida (Rust + Python).
Orquesta la evolución genética en segundo plano y evalúa perfiles de estrategia en tiempo real.
Referencia de diseño: docs/ARQUITECTURA.md"""
import os
import json
import time
import queue
import threading
import subprocess
from typing import Generator, Dict, Any, List, Optional

import pandas as pd

from config import Config
from routes.utils import (
    get_data_dir,
    get_genetic_optimizer_path,
    extract_json_from_output,
    extract_markov_params,
    load_csv_data,
    clean_json_data,
    optimizer,
    resolve_csv_filepath,
    simulator,
    stats_engine,
)
from engine.correlation import CorrelationEngine
from strategies.genetic_composite import GeneticCompositeStrategy
from .formatters import (
    format_equity_curve,
    format_trades,
    format_signal_markers,
    format_mc_paths,
    build_strategy_profiles,
    get_strat_score,
)


def stream_smart_optimize_v1(
    pair: str = 'BTCUSDT',
    interval: str = '1h',
    base_capital: float = 1000.0,
    profit_pct: float = 20.0,
    attempts: int = 2,
    payout: float = 0.85
) -> Generator[str, None, None]:
    """Generates SSE event stream for Smart Mode V1 single-pair genetic optimization."""
    try:
        filename = f"{pair}_{interval}.csv"
        filepath = resolve_csv_filepath(filename)
        if not os.path.exists(filepath):
            yield f"data: {json.dumps({'type': 'error', 'message': f'Datos no encontrados para {pair} {interval}'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'log', 'message': 'Paso [1/5]: Buscando la estrategia óptima con Algoritmo Genético en Rust...'})}\n\n"

        exe_path = get_genetic_optimizer_path()
        if not exe_path:
            yield f"data: {json.dumps({'type': 'error', 'message': 'El ejecutable del optimizador genético no está compilado.'})}\n\n"
            return

        cmd = [
            exe_path,
            "--csv", filepath,
            "--expiry", "1",
            "--min-trades", "5.0",
            "--generations", "50",
            "--population", "150"
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

        start_time = time.time()
        final_output = ""

        try:
            if process.stdout is not None:
                for line in process.stdout:
                    line_str = line.strip()
                    if line_str.startswith("PROGRESS:"):
                        parts = line_str.split(" ")[1].split("/")
                        current_gen = int(parts[0])
                        total_gens = int(parts[1])

                        progress_pct = (current_gen / total_gens) * 50.0

                        elapsed = time.time() - start_time
                        eta = (elapsed / current_gen) * (total_gens - current_gen) if current_gen > 0 else 0
                        eta += 2.0  # Buffer for next steps

                        yield f"data: {json.dumps({'type': 'progress', 'progress': progress_pct, 'eta': eta, 'log': f'Optimización genética: Gen {current_gen}/{total_gens}'})}\n\n"
                    else:
                        final_output += line

            process.wait()
        except (GeneratorExit, BaseException):
            if process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=1.0)
                except Exception:
                    pass
            raise
        finally:
            if process.poll() is None:
                try:
                    process.kill()
                except Exception:
                    pass
        if process.returncode != 0:
            yield f"data: {json.dumps({'type': 'error', 'message': 'El optimizador genético en Rust falló.'})}\n\n"
            return

        try:
            rust_json = extract_json_from_output(final_output)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Error parseando JSON Rust: {str(e)}'})}\n\n"
            return

        if 'error' in rust_json:
            yield f"data: {json.dumps({'type': 'error', 'message': rust_json['error']})}\n\n"
            return

        best_genome = rust_json.get('parameters', {})
        win_rate = float(rust_json.get('out_of_sample_win_rate', 0.55))
        in_sample_win_rate = float(rust_json.get('in_sample_win_rate', 0.60))

        yield f"data: {json.dumps({'type': 'log', 'message': 'Paso [2/5]: Cargando velas e inicializando simulación en modo BARBELL...'})}\n\n"

        df = load_csv_data(pair, interval)
        if df is None:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Datos de velas no encontrados para {pair} {interval}'})}\n\n"
            return

        strategy = GeneticCompositeStrategy()
        signals = strategy.generate_signals(df, best_genome)

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

        q: queue.Queue = queue.Queue()
        sim_start_time = time.time()

        def sim_progress_callback(progress_ratio: float) -> None:
            elapsed = time.time() - sim_start_time
            eta = (elapsed / progress_ratio) * (1.0 - progress_ratio) if progress_ratio > 0 else 0
            eta += 1.0
            mapped_progress = 50.0 + (progress_ratio * 25.0)
            q.put({
                'type': 'progress',
                'progress': mapped_progress,
                'eta': eta,
                'log': f'Simulando operaciones: {progress_ratio * 100:.1f}%'
            })

        def sim_worker() -> None:
            try:
                res = simulator.run(
                    df, signals,
                    expiry_candles=1,
                    payout=payout,
                    initial_capital=base_capital,
                    mode='BARBELL',
                    n_consecutive=optimal_n,
                    bet_fraction=bet_fraction,
                    risk_ratio=profit_pct / 100.0,
                    target_ratio=target_capital / risk_capital,
                    progress_callback=sim_progress_callback
                )
                q.put({'type': 'result', 'data': res})
            except Exception as ex:
                q.put({'type': 'error', 'message': str(ex)})

        threading.Thread(target=sim_worker, daemon=True).start()

        sim_results: Optional[Dict[str, Any]] = None
        while True:
            item = q.get()
            if item['type'] == 'progress':
                yield f"data: {json.dumps(item)}\n\n"
            elif item['type'] == 'error':
                yield f"data: {json.dumps(item)}\n\n"
                return
            elif item['type'] == 'result':
                sim_results = item['data']
                break

        if sim_results is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Simulación no completada.'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'progress', 'progress': 75.0, 'eta': 1.0, 'log': 'Paso [3/5]: Analizando métricas de operaciones y rachas...'})}\n\n"

        trades = sim_results['trades']
        stats: Dict[str, Any] = {}
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
        equity_curve = format_equity_curve(sim_results['equity_curve'], max_points=500, use_preserve_peaks=False)
        formatted_trades_display = format_trades(trades, max_trades=100)

        yield f"data: {json.dumps({'type': 'progress', 'progress': 80.0, 'eta': 0.5, 'log': 'Paso [4/5]: Simulando campaña con Monte Carlo (5,000 caminos)...'})}\n\n"

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

        yield f"data: {json.dumps({'type': 'progress', 'progress': 90.0, 'eta': 0.2, 'log': 'Simulando trayectorias de capital...'})}\n\n"

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

        top_strategies: List[Dict[str, Any]] = []
        profiles = build_strategy_profiles(best_genome)

        default_universe = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
            "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT", "DOTUSDT"
        ]
        corr_engine = CorrelationEngine(get_data_dir())
        universe_data = corr_engine.load_universe(default_universe)
        if universe_data:
            corr_matrix, _ = corr_engine.compute_correlation_matrix(universe_data)
            selected_assets = corr_engine.select_uncorrelated_assets(corr_matrix, threshold=0.65)
            corr_labels = list(corr_matrix.columns)
            corr_values = corr_matrix.values.tolist()
        else:
            selected_assets = [pair]
            corr_labels = [pair]
            corr_values = [[1.0]]

        asset_win_rates: Dict[str, Any] = {}
        for asset in selected_assets:
            asset_df = universe_data.get(asset) if universe_data else None
            if asset_df is not None and not asset_df.empty:
                gen_sigs = GeneticCompositeStrategy().generate_signals(asset_df, best_genome)
                asset_sim = simulator.run(asset_df, gen_sigs, expiry_candles=1, payout=payout)
                sum_res = asset_sim.get('summary', {})
                tot_tr = sum_res.get('total_trades', 0)
                asset_wr = sum_res.get('win_rate', 0.0) if tot_tr > 0 else 0.0
                wins_tr = sum_res.get('wins', 0)
                asset_win_rates[asset] = {
                    "win_rate": asset_wr,
                    "wins": wins_tr,
                    "trades": tot_tr,
                    "sample_type": "OOS"
                }
            else:
                asset_win_rates[asset] = {
                    "win_rate": 0.0,
                    "wins": 0,
                    "trades": 0,
                    "sample_type": "N/A"
                }

        for p in profiles:
            p_signals = GeneticCompositeStrategy().generate_signals(df, p["genome"])
            p_sim_res = simulator.run(
                df, p_signals,
                expiry_candles=1,
                payout=payout,
                initial_capital=base_capital,
                mode='BARBELL',
                n_consecutive=optimal_n,
                bet_fraction=bet_fraction,
                risk_ratio=profit_pct / 100.0,
                target_ratio=target_capital / risk_capital
            )

            p_trades = p_sim_res['trades']
            p_wr = float(p_sim_res['summary']['win_rate']) if len(p_trades) > 0 else 0.0
            p_stats = stats_engine.analyze(p_trades, df=df) if len(p_trades) > 0 else {}
            p_m_ww, p_m_wl = extract_markov_params(p_stats)

            p_plan = optimizer.calculate_streak_plan(
                win_rate=p_wr,
                payout=payout,
                risk_capital=risk_capital,
                target_capital=target_capital,
                attempts=attempts,
                base_capital=base_capital,
                p_ww=p_m_ww,
                p_wl=p_m_wl
            )
            p_opt_n = p_plan.get('best_n_for_target', optimal_n)

            p_markers = format_signal_markers(df, p_signals, max_markers=500)
            p_eq_curve = format_equity_curve(p_sim_res['equity_curve'], max_points=500, use_preserve_peaks=False)
            p_fmt_trades = format_trades(p_trades, max_trades=100)

            p_mc = optimizer.monte_carlo_discrete(
                win_rate=p_wr,
                payout=payout,
                n_consecutive=p_opt_n,
                bet_fraction=bet_fraction,
                risk_capital=risk_capital,
                target_capital=target_capital,
                num_simulations=1000,
                p_ww=p_m_ww,
                p_wl=p_m_wl
            )

            if len(p_trades) > 0 and len(selected_assets) > 0:
                p_win_emp = sum(1 for t in p_trades if t.get('result') == 'WIN') / len(p_trades)
                s_single = (p_win_emp * (p_m_ww ** (p_opt_n - 1))) if (p_m_ww and p_opt_n > 1) else (p_win_emp ** p_opt_n)
                p_parallel = float(min(0.99, max(0.0, 1.0 - ((1.0 - s_single) ** min(attempts, len(selected_assets))))))
            else:
                p_parallel = 0.0

            item_asset = selected_assets[0] if (selected_assets and len(selected_assets) > 0) else 'BTCUSDT'
            strat_item = {
                "id": p["id"],
                "name": p["name"],
                "canonical_name": f"{p['type'].upper()}_{item_asset}_1D",
                "full_display_title": f"{p['name']} · [{item_asset} · 1D]",
                "asset": item_asset,
                "target_asset": item_asset,
                "timeframe": "1D",
                "type": p["type"],
                "win_rate_oos": p_wr,
                "win_rate_is": in_sample_win_rate,
                "best_genome": p["genome"],
                "natural_description": p["description"],
                "streak_plan": p_plan,
                "mc_discrete": p_mc,
                "sim_summary": p_sim_res['summary'],
                "equity_curve": p_eq_curve,
                "trades": p_fmt_trades,
                "stats": p_stats,
                "signals": p_markers,
                "parallel_campaign_1day_prob": p_parallel,
                "sample_size_warning": len(p_trades) < 20
            }
            top_strategies.append(strat_item)

        top_strategies.sort(key=get_strat_score, reverse=True)
        for rank_i, st in enumerate(top_strategies, start=1):
            st["id"] = rank_i

        main_sim_results = {'summary': top_strategies[0].get('sim_summary', {})} if top_strategies else None
        main_streak_plan = top_strategies[0].get('streak_plan') if top_strategies else None
        main_stats = top_strategies[0].get('stats') if top_strategies else None
        main_equity_curve = top_strategies[0].get('equity_curve') if top_strategies else None
        main_signal_markers = top_strategies[0].get('signals') if top_strategies else None
        main_formatted_trades = top_strategies[0].get('trades') if top_strategies else None

        response = {
            'best_genome': best_genome,
            'win_rate_oos': win_rate,
            'win_rate_is': in_sample_win_rate,
            'streak_plan': main_streak_plan or streak_plan,
            'sim_summary': main_sim_results['summary'] if main_sim_results else sim_results['summary'],
            'equity_curve': main_equity_curve or equity_curve,
            'trades': main_formatted_trades if main_formatted_trades else formatted_trades_display,
            'stats': main_stats or stats,
            'signals': main_signal_markers or signal_markers,
            'mc_discrete': mc_results,
            'mc_paths': paths,
            'mc_summary': {
                'ruin_probability': mc_paths_results.get('ruin_probability', 0.0),
                'max_drawdowns': mc_paths_results.get('max_drawdowns', {})
            },
            'top_strategies': top_strategies,
            'selected_assets': selected_assets,
            'asset_win_rates': asset_win_rates,
            'correlation_matrix': {
                'labels': corr_labels,
                'matrix': corr_values
            },
            'parallel_campaign_1day_prob': top_strategies[0]['parallel_campaign_1day_prob'] if top_strategies else 0.0
        }

        yield f"data: {json.dumps({'type': 'result', 'data': clean_json_data(response)})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
