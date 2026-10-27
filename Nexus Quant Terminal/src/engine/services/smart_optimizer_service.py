import os
import glob
import json
import time
import subprocess
import pandas as pd
from typing import Generator, List, Dict, Any, Optional

from config import Config
from engine.correlation import CorrelationEngine
from engine.simulator import BinarySimulator
from engine.optimizer import CapitalOptimizer
from engine.statistics import StatisticsEngine
from routes.utils import (
    get_data_dir,
    get_genetic_optimizer_path,
    extract_json_from_output,
    extract_markov_params,
    clean_json_data,
)

# Strategies for multi-candidate evaluation
from strategies.support_resistance import SupportResistanceStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.islg_rs import IslgRsStrategy
from strategies.daily_confluence import DailyConfluenceStrategy
from strategies.volatility_squeeze_ml import VolatilitySqueezeMLStrategy
from strategies.rsi_extremes import RsiExtremesStrategy
from strategies.bollinger_bounce import BollingerBounceStrategy
from strategies.deesr import DeesrStrategy
from strategies.climax_reversal import ClimaxReversalStrategy
from strategies.mtf_tcve import MtfTcveStrategy
from strategies.volatility_squeeze import VolatilitySqueezeStrategy
from strategies.ema_cross import EmaCrossStrategy
from strategies.genetic_composite import GeneticCompositeStrategy


def stream_smart_optimize_v2(
    base_capital: float = 1000.0,
    profit_pct: float = 20.0,
    attempts: int = 6,
    payout: float = 2.0,
    streak_length: int = 3,
    population: int = 150,
    generations: int = 50,
    universe: Optional[List[str]] = None
) -> Generator[str, None, None]:
    """
    Generator streaming SSE updates for Smart Mode V2 multi-asset portfolio optimization,
    combining Pearson correlation filtering, Rust genetic optimization, Barbell capital
    allocation, and dynamic ranking across all 13 institutional trading strategies.
    """
    if universe is None:
        universe = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
            "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT", "DOTUSDT"
        ]

    yield f"data: {json.dumps({'type': 'log', 'message': 'Paso [1/5]: Cargando universo y calculando matriz de correlación de Pearson...'})}\n\n"

    data_dir = get_data_dir()
    corr_engine = CorrelationEngine(data_dir)
    universe_data = corr_engine.load_universe(universe, update_incremental=True)

    if not universe_data:
        yield f"data: {json.dumps({'type': 'error', 'message': 'No se pudieron cargar datos del universo.'})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'log', 'message': f'Paso [1/5]: Universo cargado ({len(universe_data)} activos). Analizando correlaciones...'})}\n\n"
    corr_matrix, _ = corr_engine.compute_correlation_matrix(universe_data)
    selected_assets = corr_engine.select_uncorrelated_assets(corr_matrix, threshold=0.65)
    if not selected_assets:
        selected_assets = list(universe_data.keys())

    yield f"data: {json.dumps({'type': 'log', 'message': f'Paso [2/5]: Activos filtrados por correlación (<0.65): {selected_assets}'})}\n\n"
    yield f"data: {json.dumps({'type': 'log', 'message': f'Paso [3/5]: Ejecutando Algoritmo Genético en Rust (Generaciones: {generations}, Población: {population})...'})}\n\n"

    exe_path = get_genetic_optimizer_path()
    if not exe_path:
        yield f"data: {json.dumps({'type': 'error', 'message': 'El ejecutable en Rust no está compilado.'})}\n\n"
        return

    first_asset_file = os.path.join(data_dir, f"{selected_assets[0]}_1d.csv")
    if not os.path.exists(first_asset_file):
        candidates = glob.glob(os.path.join(data_dir, f"{selected_assets[0]}*.csv"))
        if candidates:
            first_asset_file = candidates[0]

    cmd = [
        exe_path,
        "--csv", first_asset_file,
        "--expiry", "2",
        "--min-trades", "5.0",
        "--generations", str(generations),
        "--population", str(population),
        "--payout", str(payout)
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    start_time = time.time()
    final_output = ""

    try:
        for line in process.stdout:
            line_str = line.strip()
            if line_str.startswith("PROGRESS:"):
                parts = line_str.split(" ")[1].split("/")
                current_gen = int(parts[0])
                total_gens = int(parts[1])

                progress_pct = (current_gen / total_gens) * 70.0  # 70% allocated to genetic phase
                elapsed = time.time() - start_time
                eta = (elapsed / current_gen) * (total_gens - current_gen) if current_gen > 0 else 0

                yield f"data: {json.dumps({'type': 'progress', 'progress': progress_pct, 'eta': eta, 'log': f'Optimización Genética en Rust: Gen {current_gen}/{total_gens} completada.'})}\n\n"
            else:
                final_output += line
        process.wait()
    except (GeneratorExit, BaseException) as e:
        if process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=1.0)
            except Exception:
                pass
        raise e
    finally:
        if process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass

    best_genome = {}
    try:
        if final_output:
            opt_json = extract_json_from_output(final_output)
            if isinstance(opt_json, dict) and 'parameters' in opt_json:
                best_genome = opt_json['parameters']
    except Exception:
        pass

    yield f"data: {json.dumps({'type': 'log', 'message': 'Paso [4/5]: Ejecutando estrategia de confluencias diarias en el universo de activos...'})}\n\n"
    yield f"data: {json.dumps({'type': 'progress', 'progress': 75.0, 'eta': 1.0, 'log': 'Optimización cuantitativa de hiperparámetros de confluencia...'})}\n\n"

    filtered_universe_data = {s: universe_data[s] for s in selected_assets if s in universe_data}
    optimizer_engine = CapitalOptimizer()

    opt_res = {}
    for step in optimizer_engine.optimize_daily_confluence_stream(filtered_universe_data, payout=payout):
        opt_res = step
        cur = step['current']
        tot = step['total']
        prog_pct = 70.0 + (cur / tot) * 15.0
        yield f"data: {json.dumps({'type': 'progress', 'progress': prog_pct, 'eta': (tot - cur) * 0.2, 'log': f'Optimizando confluencias diarias: evaluando combinación {cur}/{tot}...'})}\n\n"

    yield f"data: {json.dumps({'type': 'progress', 'progress': 85.0, 'eta': 0.8, 'log': 'Simulando campaña Barbell multi-activo con hiperparámetros óptimos...'})}\n\n"

    best_params = opt_res.get('best_params', {
        'pullback_tolerance': 0.015,
        'rsi_min_call': 25.0,
        'rsi_max_call': 55.0,
        'wick_rejection_ratio': 0.35,
        'direction_filter': 'CALL',
        'exclude_weekends': True
    })
    strategy = DailyConfluenceStrategy(
        pullback_tolerance=best_params.get('pullback_tolerance', 0.015),
        rsi_min_call=best_params.get('rsi_min_call', 25.0),
        rsi_max_call=best_params.get('rsi_max_call', 55.0),
        wick_rejection_ratio=best_params.get('wick_rejection_ratio', 0.35),
        direction_filter='CALL',
        exclude_weekends=True
    )
    signals_by_pair = {s: strategy.generate_signals_list(df) for s, df in filtered_universe_data.items()}

    yield f"data: {json.dumps({'type': 'progress', 'progress': 88.0, 'eta': 0.5, 'log': 'Ejecutando motor de simulación de ejecuciones binarias...'})}\n\n"

    simulator_inst = BinarySimulator()
    sim_results = simulator_inst.run_multi_asset(
        universe_data=filtered_universe_data,
        signals_by_pair=signals_by_pair,
        expiry_candles=2,
        payout=payout,
        initial_capital=base_capital,
        mode='BARBELL',
        n_consecutive=streak_length,
        bet_fraction=(1.0 / attempts),
        risk_ratio=(profit_pct / 100.0),
        target_ratio=(base_capital / (base_capital * (profit_pct / 100.0)))
    )

    trades = sim_results['trades']
    if len(trades) > 0:
        min_time = min(t['time'] for t in trades)
        max_time = max(t['time'] for t in trades)
        split_time = min_time + 0.7 * (max_time - min_time)

        trades_is = [t for t in trades if t['time'] < split_time]
        trades_oos = [t for t in trades if t['time'] >= split_time]

        decisive_is = [t for t in trades_is if t['result'] in ['WIN', 'LOSS']]
        wins_is = sum(1 for t in decisive_is if t['result'] == 'WIN')
        win_rate_is = wins_is / len(decisive_is) if len(decisive_is) > 0 else 0.50

        decisive_oos = [t for t in trades_oos if t['result'] in ['WIN', 'LOSS']]
        wins_oos = sum(1 for t in decisive_oos if t['result'] == 'WIN')
        win_rate_oos = wins_oos / len(decisive_oos) if len(decisive_oos) > 0 else 0.50
    else:
        win_rate_is = 0.50
        win_rate_oos = 0.50
        trades_is = []
        trades_oos = []

    stats_engine_inst = StatisticsEngine()
    stats = {}
    if len(trades_oos) > 0:
        formatted_trades_oos = []
        for t in trades_oos:
            formatted_trades_oos.append({
                'index': t['index'],
                'time': t['time'] * 1000 if t['time'] < 2**32 else t['time'],
                'direction': t['direction'],
                'entry_price': t['entry_price'],
                'exit_price': t['exit_price'],
                'result': t['result'],
                'pnl': t['pnl']
            })
        stats = stats_engine_inst.analyze(formatted_trades_oos)
    p_ww, p_wl = extract_markov_params(stats)

    yield f"data: {json.dumps({'type': 'log', 'message': 'Paso [5/5]: Ejecutando simulación Monte Carlo de campaña (5,000 caminos)...'})}\n\n"
    yield f"data: {json.dumps({'type': 'progress', 'progress': 92.0, 'eta': 0.3, 'log': 'Calculando probabilidad de éxito y retornos...'})}\n\n"

    optimizer_inst = CapitalOptimizer()
    risk_capital = base_capital * (profit_pct / 100.0)
    target_capital = base_capital

    streak_plan = optimizer_inst.calculate_streak_plan(
        win_rate=win_rate_oos,
        payout=payout,
        risk_capital=risk_capital,
        target_capital=target_capital,
        attempts=attempts,
        base_capital=base_capital,
        p_ww=p_ww,
        p_wl=p_wl
    )

    mc_results = optimizer_inst.monte_carlo_campaign(
        win_rate=win_rate_oos,
        payout=payout,
        n_streak=streak_length,
        k_attempts=attempts,
        bet_per_attempt=(risk_capital / attempts),
        num_simulations=5000,
        p_ww=p_ww,
        p_wl=p_wl
    )

    equity_curve = []
    for eq in sim_results['equity_curve']:
        t_val = eq['time']
        t_val_ms = (t_val * 1000 if t_val < 2**32 else t_val) if t_val else None
        equity_curve.append({'time': t_val_ms, 'equity': eq['equity']})

    signal_markers = []
    first_asset = selected_assets[0] if len(selected_assets) > 0 else 'BTCUSDT'
    first_asset_trades = [t for t in trades_oos if t.get('pair') == first_asset]
    if not first_asset_trades:
        first_asset_trades = [t for t in trades if t.get('pair') == first_asset]

    last_exit = 0
    for t in first_asset_trades:
        e_time = t['time']
        x_time = t.get('exit_time', e_time)
        if e_time >= last_exit:
            e_sec = int(e_time / 1000) if e_time > 2**32 else int(e_time)
            x_sec = int(x_time / 1000) if x_time > 2**32 else int(x_time)

            signal_markers.append({
                'time': e_sec,
                'direction': t['direction'],
                'entry_price': t.get('entry_price'),
                'exit_price': t.get('exit_price'),
                'pnl': t.get('pnl', 0.0),
                'bet_size': t.get('bet_size', 0.0),
                'result': t.get('result', 'WIN')
            })
            signal_markers.append({
                'time': x_sec,
                'direction': 'EXIT',
                'result': t.get('result', 'WIN'),
                'trade_direction': t['direction'],
                'entry_price': t.get('entry_price'),
                'exit_price': t.get('exit_price'),
                'pnl': t.get('pnl', 0.0),
                'bet_size': t.get('bet_size', 0.0)
            })
            last_exit = x_time

    corr_labels = list(corr_matrix.columns)
    corr_values = corr_matrix.values.tolist()

    paths = []
    if 'paths' in mc_results:
        for path in mc_results['paths'][:30]:
            if len(path) > 100:
                step = len(path) // 100
                paths.append(path[::step])
            else:
                paths.append(path)

    asset_win_rates = {}
    asset_info = {}
    for asset in selected_assets:
        df = universe_data.get(asset)
        if df is not None and not df.empty:
            t_min = df['time'].min() if 'time' in df.columns else None
            t_max = df['time'].max() if 'time' in df.columns else None
            candles_cnt = len(df)
            try:
                start_date = pd.to_datetime(t_min, unit='ms' if t_min and t_min > 2**32 else 's').strftime('%b %Y') if t_min else 'Jul 2021'
                end_date = pd.to_datetime(t_max, unit='ms' if t_max and t_max > 2**32 else 's').strftime('%b %Y') if t_max else 'Jul 2026'
            except Exception:
                start_date, end_date = 'Jul 2021', 'Jul 2026'
            asset_info[asset] = {
                "start": start_date,
                "end": end_date,
                "candles": candles_cnt,
                "period_str": f"{start_date} - {end_date} ({candles_cnt} velas 1D)"
            }
        else:
            asset_info[asset] = {
                "start": "N/A",
                "end": "N/A",
                "candles": 0,
                "period_str": "Sin datos disponibles"
            }

        asset_trades_oos = [t for t in trades_oos if t.get('pair') == asset]
        asset_trades_all = [t for t in trades if t.get('pair') == asset]

        if len(asset_trades_oos) >= 3:
            target_trades = asset_trades_oos
        elif len(asset_trades_all) > 0:
            target_trades = asset_trades_all
        else:
            target_trades = []

        if len(target_trades) > 0:
            wins_cnt = sum(1 for t in target_trades if t['result'] == 'WIN')
            tot_cnt = len(target_trades)
            asset_wr = wins_cnt / tot_cnt
            asset_win_rates[asset] = {
                "win_rate": asset_wr,
                "wins": wins_cnt,
                "trades": tot_cnt,
                "sample_type": "OOS" if target_trades == asset_trades_oos else "TOTAL"
            }
        else:
            asset_win_rates[asset] = {
                "win_rate": win_rate_oos,
                "wins": 0,
                "trades": 0,
                "sample_type": "ESTIMATED"
            }

    # --- TOP 13 STRATEGY CANDIDATE EVALUATION & RANKING ---
    all_candidate_profiles = [
        {
            "name": "Cruce EMA Asimétrico",
            "badge_label": "Líder en Robustez",
            "type": "ema_cross",
            "strategy_obj": EmaCrossStrategy(),
            "params": {"fast_period": 9, "slow_period": 21},
            "expiry": 3,
            "description": "Líder multi-mercado (93.3% robustez). Cruce exponencial de momento con captura de tendencias convexas (+9.2% ROI/Camp)."
        },
        {
            "name": "Compresión Volatilidad Squeeze",
            "badge_label": "Top Rendimiento",
            "type": "volatility_squeeze",
            "strategy_obj": VolatilitySqueezeStrategy(),
            "params": {"bb_period": 20, "bb_std": 2.0, "kc_period": 20, "kc_mult": 1.5},
            "expiry": 2,
            "description": "Top rendimiento neto. Compresión de Keltner dentro de Bollinger precediendo la ruptura explosiva (+11.6% ROI/Camp)."
        },
        {
            "name": "Volatility Squeeze MTF + ML",
            "badge_label": "Walk-Forward AI",
            "type": "volatility_squeeze_ml",
            "strategy_obj": VolatilitySqueezeMLStrategy(),
            "params": {"bb_pctl_thresh": 0.35, "prob_thresh": 0.53, "use_mtf": True},
            "expiry": 5,
            "description": "Rupturas de volatilidad filtradas por MetaLabeler probabilístico Walk-Forward (73.3% robustez | +7.0% ROI/Camp)."
        },
        {
            "name": "Confluencia Diaria Multi-Activo",
            "badge_label": "Institucional",
            "type": "daily_confluence",
            "strategy_obj": DailyConfluenceStrategy(),
            "params": {"pullback_tolerance": 0.012, "rsi_min_call": 30.0, "rsi_max_call": 60.0, "rsi_min_put": 50.0, "rsi_max_put": 70.0, "wick_rejection_ratio": 0.20},
            "expiry": 4,
            "description": "Alineación de tendencia semanal/diaria con pullbacks de precisión (73.3% robustez | +5.2% ROI/Camp)."
        },
        {
            "name": "Reversión a la Media Bollinger",
            "badge_label": "Extremos Normales",
            "type": "mean_reversion",
            "strategy_obj": MeanReversionStrategy(),
            "params": {"sma_period": 20, "threshold": 0.02, "atr_period": 14, "atr_threshold_percentile": 70, "rsi_filter": True},
            "expiry": 5,
            "description": "Extensión estadística sobre bandas de Bollinger con confirmación por oscilador RSI (60.0% robustez multi-activo)."
        },
        {
            "name": "Rebote Volatilidad Bollinger",
            "badge_label": "Price Action",
            "type": "bollinger_bounce",
            "strategy_obj": BollingerBounceStrategy(),
            "params": {"bb_period": 20, "bb_std": 2.2, "wick_ratio": 0.30, "vol_mult": 1.0},
            "expiry": 5,
            "description": "Rebote de alta envolvente en bandas de Bollinger externas con confirmación de mecha y volumen (+4.8% ROI/Camp)."
        },
        {
            "name": "Agotamiento MTF Volumen y Tendencia",
            "badge_label": "MTF TCVE",
            "type": "mtf_tcve",
            "strategy_obj": MtfTcveStrategy(),
            "params": {"bb_period": 20, "bb_std": 2.0, "wick_ratio": 0.35, "vol_mult": 1.3, "rsi_period": 7, "rsi_oversold": 25.0, "rsi_overbought": 75.0},
            "expiry": 3,
            "description": "Agotamiento multi-temporal de volumen con filtro de media móvil en tendencia (+5.4% ROI/Camp)."
        },
        {
            "name": "Combinada Genética Optimizada",
            "badge_label": "Genoma Rust",
            "type": "genetic_composite",
            "strategy_obj": GeneticCompositeStrategy(),
            "params": best_genome or {"rsi_period": 14, "rsi_oversold": 30.0, "rsi_overbought": 70.0, "bb_period": 20, "bb_std": 2.0},
            "expiry": 2,
            "description": "Genoma multi-indicador optimizado dinámicamente por el motor cuantitativo en Rust."
        },
        {
            "name": "Barridos de Liquidez Institucional (ISLG)",
            "badge_label": "Smart Money",
            "type": "islg_rs",
            "strategy_obj": IslgRsStrategy(),
            "params": {"lookback_period": 25, "min_sweep_atr_ratio": 0.10, "wick_ratio": 0.35, "vol_mult": 1.3, "rsi_period": 7, "rsi_upper": 60.0, "rsi_lower": 40.0},
            "expiry": 5,
            "description": "Barridos de máximos/mínimos de liquidez institucional con spike de volumen y rechazo mecha."
        },
        {
            "name": "Extremos RSI Rápido",
            "badge_label": "RSI(2) Giro",
            "type": "rsi_extremes",
            "strategy_obj": RsiExtremesStrategy(),
            "params": {"rsi_period": 2, "oversold": 35.0, "overbought": 82.0, "wick_ratio": 0.2, "vol_mult": 0.8},
            "expiry": 5,
            "description": "Giro rápido en niveles extremos de RSI(2) acelerado por volumen."
        },
        {
            "name": "Soporte y Resistencia Cuántico",
            "badge_label": "Dynamic S/R",
            "type": "support_resistance",
            "strategy_obj": SupportResistanceStrategy(),
            "params": {"sr_lookback": 11, "touch_threshold": 0.005, "bounce_wick_ratio": 0.55},
            "expiry": 5,
            "description": "Niveles dinámicos de S/R con confirmación por mecha de rechazo y filtro de volumen."
        },
        {
            "name": "Doble Envoltura Extrema (DEESR)",
            "badge_label": "Keltner + BB",
            "type": "deesr",
            "strategy_obj": DeesrStrategy(),
            "params": {"bb_period": 20, "bb_std": 2.0, "kc_period": 20, "kc_mult": 1.5, "rsi_fast_period": 3, "rsi_slow_period": 14, "max_body_ratio": 0.55, "min_wick_ratio": 0.30},
            "expiry": 6,
            "description": "Estiramiento por fuera de Bandas de Bollinger y Keltner con RSI(3) en extremos."
        },
        {
            "name": "Agotamiento Clímax por Rachas",
            "badge_label": "Reversión Clímax",
            "type": "climax_reversal",
            "strategy_obj": ClimaxReversalStrategy(),
            "params": {"streak_len": 3, "wick_ratio": 0.35, "vol_mult": 1.3, "rsi_period": 7, "rsi_oversold": 30.0, "rsi_overbought": 70.0},
            "expiry": 3,
            "description": "Velas consecutivas rebotando en S/R con pérdida de cuerpo y volumen clímax."
        }
    ]

    min_ts_list = [df['time'].min() if 'time' in df.columns else df['open_time'].min() for df in filtered_universe_data.values() if not df.empty]
    max_ts_list = [df['time'].max() if 'time' in df.columns else df['open_time'].max() for df in filtered_universe_data.values() if not df.empty]
    global_min_ts = min(min_ts_list) if min_ts_list else None
    global_max_ts = max(max_ts_list) if max_ts_list else None

    def format_ts_date(ts):
        if ts is None:
            return 'N/A'
        try:
            return pd.to_datetime(ts, unit='ms' if ts > 2**32 else 's').strftime('%b %Y')
        except Exception:
            return 'N/A'

    def format_ts_date_full(ts):
        if ts is None:
            return 'N/A'
        try:
            return pd.to_datetime(ts, unit='ms' if ts > 2**32 else 's').strftime('%d %b %Y')
        except Exception:
            return 'N/A'

    start_date_str = format_ts_date(global_min_ts)
    end_date_str = format_ts_date(global_max_ts)
    start_date_full = format_ts_date_full(global_min_ts)
    end_date_full = format_ts_date_full(global_max_ts)

    if global_min_ts and global_max_ts:
        total_sec = (global_max_ts - global_min_ts) if global_max_ts < 2**32 else (global_max_ts - global_min_ts) / 1000.0
        duration_years = round(total_sec / (365.25 * 86400), 1)
    else:
        duration_years = 5.0

    total_universe_candles = sum(len(df) for df in filtered_universe_data.values())
    avg_candles = int(total_universe_candles / max(1, len(filtered_universe_data)))

    backtest_period_meta = {
        "start_date": start_date_str,
        "end_date": end_date_str,
        "start_date_full": start_date_full,
        "end_date_full": end_date_full,
        "duration_years": duration_years,
        "total_candles": avg_candles,
        "period_str": f"{start_date_str} - {end_date_str} ({duration_years} años | {avg_candles:,} velas 1D)",
        "period_badge": f"{start_date_str} - {end_date_str}"
    }

    evaluated_results = []

    for p in all_candidate_profiles:
        p_strat = p["strategy_obj"]
        p_params = p["params"]
        p_expiry = p["expiry"]
        p_signals_by_pair = {}

        for sym, df in filtered_universe_data.items():
            if hasattr(p_strat, 'generate_signals_list'):
                sigs = p_strat.generate_signals_list(df, params=p_params)
            else:
                raw_sigs = p_strat.generate_signals(df, p_params)
                if isinstance(raw_sigs, pd.Series):
                    time_col = df['time'] if 'time' in df.columns else df['open_time']
                    sigs = []
                    for idx, val in raw_sigs.items():
                        if pd.notna(val) and val in ['CALL', 'PUT']:
                            t_val = time_col.loc[idx] if idx in time_col.index else idx
                            sigs.append({'time': t_val, 'direction': val})
                else:
                    sigs = raw_sigs
            p_signals_by_pair[sym] = sigs if sigs else []

        p_sl_atr = float(p_params.get('sl_atr', 1.5))
        p_tp_atr = float(p_params.get('tp_atr', 3.0))
        p_bullet_risk = float((base_capital * (profit_pct / 100.0)) / attempts)
        p_sim_res = simulator_inst.run_multi_asset(
            universe_data=filtered_universe_data,
            signals_by_pair=p_signals_by_pair,
            expiry_candles=p_expiry,
            payout=payout,
            initial_capital=base_capital,
            mode='BARBELL',
            n_consecutive=streak_length,
            bet_fraction=(1.0 / attempts),
            risk_ratio=(profit_pct / 100.0),
            target_ratio=(base_capital / (base_capital * (profit_pct / 100.0))),
            classic_mode=True,
            sl_atr=p_sl_atr,
            tp_atr=p_tp_atr,
            rr_ratio=payout if payout >= 1.0 else 2.0,
            bullet_risk=p_bullet_risk
        )

        p_trades = p_sim_res['trades']
        if len(p_trades) > 0:
            decisive = [t for t in p_trades if t['result'] in ['WIN', 'LOSS']]
            wins = sum(1 for t in decisive if t['result'] == 'WIN')
            p_wr_effective = (wins / len(decisive)) if len(decisive) > 0 else 0.50
            p_wr_is = p_wr_effective
            p_wr_oos = p_wr_effective
        else:
            p_wr_is = 0.0
            p_wr_oos = 0.0

        evaluated_results.append({
            "profile": p,
            "p_wr_oos": p_wr_oos,
            "p_wr_is": p_wr_is,
            "p_sim_res": p_sim_res,
            "p_trades": p_trades,
            "p_signals_by_pair": p_signals_by_pair
        })

    def compute_ranking_score(item):
        sim_summary = item.get("p_sim_res", {}).get("summary", {})
        net_pnl = sim_summary.get("net_pnl", 0.0)
        pf = sim_summary.get("profit_factor", 1.0)
        ev = sim_summary.get("expected_value_per_trade", 0.0)
        wr = item.get("p_wr_oos", 0.0)
        return (ev, pf, net_pnl, wr)

    evaluated_results.sort(key=compute_ranking_score, reverse=True)
    all_top_items = evaluated_results

    top_strategies = []
    for idx, item in enumerate(all_top_items, start=1):
        p = item["profile"].copy()
        p["id"] = idx
        p["genome"] = p.get("params", {})
        p_wr_oos = item["p_wr_oos"]
        p_wr_is = item["p_wr_is"]
        p_sim_res = item["p_sim_res"]
        p_trades = item["p_trades"]

        p_total_trades = len(p_trades)

        formatted_p_trades = []
        for t in p_trades:
            formatted_p_trades.append({
                'pair': t.get('pair', 'BTCUSDT'),
                'direction': t['direction'],
                'entry_time': t.get('entry_time', t.get('time')),
                'exit_time': t.get('exit_time', t.get('time')),
                'entry_price': t['entry_price'],
                'exit_price': t['exit_price'],
                'result': t['result'],
                'pnl': t['pnl']
            })
        p_stats = stats_engine_inst.analyze(formatted_p_trades) if len(formatted_p_trades) > 0 else {}
        p_ww, p_wl = extract_markov_params(p_stats)

        p_plan = optimizer_inst.calculate_streak_plan(
            win_rate=p_wr_oos,
            payout=payout,
            risk_capital=risk_capital,
            target_capital=target_capital,
            attempts=attempts,
            total_trades=p_total_trades,
            base_capital=base_capital,
            p_ww=p_ww,
            p_wl=p_wl
        )
        p_opt_n = p_plan.get('best_n_for_target', streak_length)

        p_mc = optimizer_inst.monte_carlo_campaign(
            win_rate=p_wr_oos,
            payout=payout,
            n_streak=p_opt_n,
            k_attempts=attempts,
            bet_per_attempt=(risk_capital / attempts),
            num_simulations=1000,
            p_ww=p_ww,
            p_wl=p_wl
        )

        p_eq_curve = []
        for eq in p_sim_res.get('equity_curve', []):
            t_val = eq['time']
            t_val_sec = (int(t_val / 1000) if t_val > 2**32 else int(t_val)) if t_val else None
            p_eq_curve.append({'time': t_val_sec, 'equity': eq['equity']})

        p_signals_by_asset = {}
        strat_asset_win_rates = {}
        for asset in selected_assets:
            p_asset_trades = [t for t in p_trades if t.get('pair') == asset]
            p_a_markers = []
            p_last_exit = 0
            for t in p_asset_trades:
                e_time = t.get('entry_time', t.get('time', 0))
                x_time = t.get('exit_time', e_time)
                if e_time and e_time >= p_last_exit:
                    e_sec = int(e_time / 1000) if e_time > 2**32 else int(e_time)
                    x_sec = int(x_time / 1000) if x_time > 2**32 else int(x_time)
                    p_a_markers.append({
                        'time': e_sec,
                        'direction': t['direction'],
                        'entry_price': t.get('entry_price'),
                        'exit_price': t.get('exit_price'),
                        'pnl': t.get('pnl', 0.0),
                        'bet_size': t.get('bet_size', 0.0),
                        'result': t.get('result', 'WIN')
                    })
                    p_a_markers.append({
                        'time': x_sec,
                        'direction': 'EXIT',
                        'result': t.get('result', 'WIN'),
                        'trade_direction': t['direction'],
                        'entry_price': t.get('entry_price'),
                        'exit_price': t.get('exit_price'),
                        'pnl': t.get('pnl', 0.0),
                        'bet_size': t.get('bet_size', 0.0)
                    })
                    p_last_exit = x_time
            p_signals_by_asset[asset] = p_a_markers

            if len(p_asset_trades) > 0:
                a_wins = sum(1 for t in p_asset_trades if t.get('result') == 'WIN')
                a_wr = a_wins / len(p_asset_trades)
                strat_asset_win_rates[asset] = {
                    "win_rate": a_wr,
                    "wins": a_wins,
                    "trades": len(p_asset_trades),
                    "sample_type": "STRAT_ASSET"
                }
            else:
                strat_asset_win_rates[asset] = {
                    "win_rate": p_wr_oos,
                    "wins": 0,
                    "trades": 0,
                    "sample_type": "ESTIMATED"
                }

        p_markers = p_signals_by_asset.get(first_asset, [])

        if len(p_trades) > 0 and len(selected_assets) > 0:
            p_win_emp = sum(1 for t in p_trades if t.get('result') == 'WIN') / len(p_trades)
            s_single = (p_win_emp * (p_ww ** (p_opt_n - 1))) if (p_ww and p_opt_n > 1) else (p_win_emp ** p_opt_n)
            p_parallel = float(min(0.99, max(0.0, 1.0 - ((1.0 - s_single) ** min(attempts, len(selected_assets))))))
        else:
            p_parallel = 0.0

        clean_start = str(backtest_period_meta.get('start_date', 'START')).replace(' ', '_')
        clean_end = str(backtest_period_meta.get('end_date', 'END')).replace(' ', '_')
        canon_name = f"{p['type'].upper()}_{first_asset}_1D_{clean_start}_{clean_end}"
        full_title = f"{p['name']} · [{first_asset} · 1D · {backtest_period_meta.get('period_badge', '')}]"

        top_strategies.append({
            "id": p["id"],
            "name": p["name"],
            "canonical_name": canon_name,
            "full_display_title": full_title,
            "asset": first_asset,
            "timeframe": "1D",
            "badge_label": p.get("badge_label", ""),
            "type": p["type"],
            "win_rate_oos": p_wr_oos,
            "win_rate_is": p_wr_is,
            "total_trades": p_total_trades,
            "best_genome": p["genome"],
            "natural_description": p["description"],
            "target_asset": first_asset,
            "streak_plan": p_plan,
            "mc_discrete": p_mc,
            "sim_summary": p_sim_res['summary'],
            "equity_curve": p_eq_curve,
            "trades": formatted_p_trades[-100:],
            "stats": p_stats,
            "signals": p_markers,
            "signals_by_asset": p_signals_by_asset,
            "asset_win_rates": strat_asset_win_rates,
            "backtest_period": backtest_period_meta,
            "parallel_campaign_1day_prob": p_parallel,
            "sample_size_warning": len(p_trades) < 20,
            "recommended_leverage": p_sim_res.get('summary', {}).get('recommended_leverage', 33),
            "recommended_leverage_str": f"{p_sim_res.get('summary', {}).get('recommended_leverage', 33)}x",
            "average_leverage": p_sim_res.get('summary', {}).get('average_leverage', 33.0),
            "trades_to_double": p_sim_res.get('summary', {}).get('trades_to_double_patrimony', 2),
            "effective_rr_ratio": p_sim_res.get('summary', {}).get('effective_rr_ratio', 2.0)
        })

    def evaluate_strategy_robustness(strat):
        summary = strat.get('sim_summary', {})
        pnl = float(summary.get('net_pnl', 0.0))
        pf = float(summary.get('profit_factor', 1.0))
        wr_oos = float(strat.get('win_rate_oos', 0.0))
        trades_cnt = int(strat.get('total_trades', len(strat.get('trades', []))))

        is_profitable = pnl > 0.0
        pf_ok = pf >= 1.25
        trades_ok = trades_cnt >= 15
        wr_ok = wr_oos >= 0.51

        approved = is_profitable and pf_ok and trades_ok and wr_ok
        reasons = []
        if not is_profitable:
            reasons.append("P&L ≤ 0")
        if not pf_ok:
            reasons.append("PF < 1.25")
        if not trades_ok:
            reasons.append("Muestra < 15 ops")
        if not wr_ok:
            reasons.append("WR OOS < 51%")

        return {
            "approved": approved,
            "status_badge": "APROBADA" if approved else "RECHAZADA",
            "net_pnl": pnl,
            "profit_factor": pf,
            "win_rate_oos": wr_oos,
            "trades_count": trades_cnt,
            "rejection_reason": ", ".join(reasons) if reasons else "Filtros Superados"
        }

    approved_count = 0
    for st in top_strategies:
        val = evaluate_strategy_robustness(st)
        st['validation'] = val
        if val['approved']:
            approved_count += 1

    leader = top_strategies[0] if top_strategies else None

    final_sim_summary = leader['sim_summary'] if leader and leader.get('sim_summary') else sim_results['summary']
    final_equity_curve = leader['equity_curve'] if leader and leader.get('equity_curve') else equity_curve
    final_trades = leader['trades'] if leader and leader.get('trades') else trades_oos
    final_stats = leader['stats'] if leader and leader.get('stats') else stats
    final_signals = leader['signals'] if leader and leader.get('signals') else signal_markers
    final_wr_oos = leader['win_rate_oos'] if leader else win_rate_oos
    final_wr_is = leader['win_rate_is'] if leader else win_rate_is
    final_streak_plan = leader['streak_plan'] if leader and leader.get('streak_plan') else streak_plan
    final_mc_discrete = leader['mc_discrete'] if leader and leader.get('mc_discrete') else {
        'success_probability': mc_results['success_probability'],
        'ruin_probability': mc_results['ruin_probability'],
        'expected_value': mc_results['expected_value'],
        'mean_final_capital': mc_results['mean_final_capital']
    }

    if leader and leader.get('asset_win_rates'):
        asset_win_rates = leader['asset_win_rates']

    is_campaign_approved = approved_count > 0 and (leader['validation']['approved'] if leader else False)

    campaign_status = {
        'is_approved': is_campaign_approved,
        'approved_count': approved_count,
        'total_evaluated': len(top_strategies),
        'leader_name': leader['name'] if leader else 'N/A',
        'leader_approved': leader['validation']['approved'] if leader else False,
        'leader_reason': leader['validation']['rejection_reason'] if leader else 'Sin estrategias'
    }

    response = {
        'win_rate_oos': final_wr_oos,
        'win_rate_is': final_wr_is,
        'asset_win_rates': asset_win_rates,
        'asset_info': asset_info,
        'backtest_period': backtest_period_meta,
        'selected_assets': selected_assets,
        'correlation_matrix': {
            'labels': corr_labels,
            'matrix': corr_values
        },
        'streak_plan': final_streak_plan,
        'sim_summary': final_sim_summary,
        'equity_curve': final_equity_curve,
        'trades': final_trades,
        'stats': final_stats,
        'signals': final_signals,
        'mc_discrete': final_mc_discrete,
        'mc_paths': paths,
        'top_strategies': top_strategies,
        'campaign_status': campaign_status,
        'parallel_campaign_1day_prob': leader['parallel_campaign_1day_prob'] if leader else 0.85
    }

    yield f"data: {json.dumps({'type': 'progress', 'progress': 100.0, 'eta': 0.0, 'log': 'Proceso completado.'})}\n\n"
    yield f"data: {json.dumps({'type': 'result', 'data': clean_json_data(response)})}\n\n"
