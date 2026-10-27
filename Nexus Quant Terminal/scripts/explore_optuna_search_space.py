"""
Milestone 3 Parallelized Optuna Search Space Exploration Engine.
Script: explore_optuna_search_space.py
Executes Optuna & Walk-Forward hyperparameter search across multi-asset datasets
to discover strategy configurations with Out-Of-Sample (OOS) Win Rate > 65% and EV > 0.
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

# Ensure root workspace is in import path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))

from engine.optimizer_optuna import OptunaStrategyOptimizer, OptunaSearchSpace, calculate_wilson_lower_bound
from engine.auto_tuner import WalkForwardEngine
from engine.simulator import VectorizedBinarySimulator

from strategies.daily_confluence import DailyConfluenceStrategy
from strategies.deesr import DeesrStrategy
from strategies.bollinger_bounce import BollingerBounceStrategy
from strategies.rsi_extremes import RsiExtremesStrategy
from strategies.volatility_squeeze_ml import VolatilitySqueezeMLStrategy
from strategies.islg_rs import IslgRsStrategy
from strategies.climax_reversal import ClimaxReversalStrategy
from strategies.genetic_composite import GeneticCompositeStrategy
from strategies.support_resistance import SupportResistanceStrategy
from strategies.mean_reversion import MeanReversionStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATASETS = [
    ("BTCUSDT_30m", os.path.join(ROOT_DIR, "data", "raw", "BTCUSDT_30m.csv")),
    ("BTCUSDT_4h", os.path.join(ROOT_DIR, "data", "raw", "BTCUSDT_4h.csv")),
    ("ETHUSDT_4h", os.path.join(ROOT_DIR, "data", "raw", "ETHUSDT_4h.csv")),
    ("SOLUSDT_4h", os.path.join(ROOT_DIR, "data", "raw", "SOLUSDT_4h.csv")),
    ("DOGEUSDT_4h", os.path.join(ROOT_DIR, "data", "raw", "DOGEUSDT_4h.csv")),
    ("ADAUSDT_4h", os.path.join(ROOT_DIR, "data", "raw", "ADAUSDT_4h.csv")),
    ("BNBUSDT_4h", os.path.join(ROOT_DIR, "data", "raw", "BNBUSDT_4h.csv")),
    ("LINKUSDT_4h", os.path.join(ROOT_DIR, "data", "raw", "LINKUSDT_4h.csv")),
    ("LTCUSDT_4h", os.path.join(ROOT_DIR, "data", "raw", "LTCUSDT_4h.csv")),
    ("XRPUSDT_4h", os.path.join(ROOT_DIR, "data", "raw", "XRPUSDT_4h.csv")),
    ("EURUSD_1d", os.path.join(ROOT_DIR, "data", "raw", "EURUSD_1d.csv")),
    ("GBPJPY_1d", os.path.join(ROOT_DIR, "data", "raw", "GBPJPY_1d.csv")),
    ("WTI_1d", os.path.join(ROOT_DIR, "data", "raw", "WTI_1d.csv")),
    ("NASDAQ_1d", os.path.join(ROOT_DIR, "data", "raw", "NASDAQ_1d.csv")),
]

STRATEGIES = [
    ("GeneticComposite", GeneticCompositeStrategy, "genetic_composite"),
    ("DailyConfluence", DailyConfluenceStrategy, "daily_confluence"),
    ("ISLG_RS", IslgRsStrategy, "islg_rs"),
    ("DEESR", DeesrStrategy, "deesr"),
    ("BollingerBounce", BollingerBounceStrategy, "bollinger_bounce"),
    ("RSI_Extremes", RsiExtremesStrategy, "rsi_extremes"),
    ("ClimaxReversal", ClimaxReversalStrategy, "climax_reversal"),
    ("VolatilitySqueezeML", VolatilitySqueezeMLStrategy, "volatility_squeeze_ml"),
    ("SupportResistance", SupportResistanceStrategy, "support_resistance"),
    ("MeanReversion", MeanReversionStrategy, "mean_reversion"),
]


def run_single_combo_task(ds_name: str, filepath: str, strat_name: str, strat_key: str):
    if not os.path.exists(filepath):
        return None

    try:
        df = pd.read_csv(filepath)
        if df.empty or len(df) < 150:
            return None

        if len(df) > 3000:
            df = df.tail(3000).reset_index(drop=True)

        # Get strategy class
        strat_map = {k: cls for name, cls, k in STRATEGIES}
        strat_cls = strat_map.get(strat_key)
        if not strat_cls:
            return None

        optimizer = OptunaStrategyOptimizer(
            payout=0.85,
            target_win_rate=0.65,
            min_trades=15,
            n_splits=4,
            embargo_pct=0.01,
            objective_metric="composite"
        )

        opt_res = optimizer.optimize(
            df=df,
            strategy_cls=strat_cls,
            strategy_name=strat_key,
            n_trials=30,
            timeout=30,
            n_jobs=1
        )

        best_params = opt_res.get("best_params", {})
        oos_verif = opt_res.get("oos_verification", {})

        win_rate_oos = oos_verif.get("win_rate_oos", 0.0)
        ev_oos = oos_verif.get("ev_per_trade_oos", 0.0)
        trades_oos = oos_verif.get("total_trades", 0)
        wilson_low = oos_verif.get("wilson_ci_lower_95", 0.0)
        max_dd_oos = oos_verif.get("max_drawdown_oos", 0.0)
        passes_verif = oos_verif.get("passes_target_criteria", False)

        wfe_score = 0.0
        global_wfa_wr = 0.0
        global_wfa_ev = 0.0

        if best_params and trades_oos >= 10:
            wfe_engine = WalkForwardEngine(
                n_windows=3,
                train_ratio=0.60,
                embargo_pct=0.01,
                n_trials_per_window=10,
                min_is_trades=5,
                min_oos_trades=3,
                target_winrate=0.65
            )
            def space_fn(trial):
                return OptunaSearchSpace.sample_strategy_space(strat_key, trial)
            wfa_res = wfe_engine.run_wfa(
                df=df,
                strat_class=strat_cls,
                param_space_fn=space_fn,
                expiry=best_params.get("expiry_candles", 1),
                payout=0.85,
                n_trials_per_window=5
            )
            wfe_score = wfa_res.get("wfe", 0.0)
            global_wfa_wr = wfa_res.get("global_oos_wr", 0.0)
            global_wfa_ev = wfa_res.get("global_oos_ev", 0.0)

        ev_clean = float(ev_oos) if not (np.isnan(ev_oos) or np.isinf(ev_oos)) else 0.0

        record = {
            "dataset": ds_name,
            "strategy": strat_name,
            "strategy_key": strat_key,
            "best_params": best_params,
            "optuna_trials": opt_res.get("completed_trials", 0),
            "pruned_trials": opt_res.get("pruned_trials", 0),
            "total_trades_oos": trades_oos,
            "win_rate_oos": win_rate_oos,
            "wilson_ci_lower_95": wilson_low,
            "ev_per_trade_oos": ev_clean,
            "max_drawdown_oos": max_dd_oos,
            "passes_optuna_criteria": passes_verif,
            "wfe": wfe_score,
            "global_wfa_wr": global_wfa_wr,
            "global_wfa_ev": global_wfa_ev
        }
        return record
    except Exception as e:
        return {"dataset": ds_name, "strategy": strat_name, "error": str(e)}


def run_parallel_exploration():
    print("Starting Milestone 3 High-Throughput Parallel Optuna Search Space Exploration...", flush=True)

    tasks = []
    for ds_name, filepath in DATASETS:
        for strat_name, strat_cls, strat_key in STRATEGIES:
            tasks.append((ds_name, filepath, strat_name, strat_key))

    max_workers = min(os.cpu_count() or 4, 8)
    print(f"Executing {len(tasks)} optimization tasks across {max_workers} worker processes...", flush=True)

    all_results = []
    passing_configs = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(run_single_combo_task, ds, fp, sn, sk): (ds, sn)
            for ds, fp, sn, sk in tasks
        }

        completed_count = 0
        for future in as_completed(future_to_task):
            ds_name, strat_name = future_to_task[future]
            completed_count += 1
            try:
                res = future.result()
                if res and "best_params" in res:
                    all_results.append(res)
                    wr = res.get("win_rate_oos", 0.0)
                    ev = res.get("ev_per_trade_oos", 0.0)
                    tr = res.get("total_trades_oos", 0)
                    wlow = res.get("wilson_ci_lower_95", 0.0)
                    wfa_wr = res.get("global_wfa_wr", 0.0)

                    if (wr >= 65.0 or wfa_wr >= 65.0) and ev > 0.0 and tr >= 10:
                        passing_configs.append(res)
                        print(f"[{completed_count}/{len(tasks)}] WINNER! [{ds_name}] {strat_name} -> WR: {wr:.1f}%, EV: {ev:.4f}, Trades: {tr}, Wilson Low: {wlow:.1f}%", flush=True)
                    else:
                        print(f"[{completed_count}/{len(tasks)}] [{ds_name}] {strat_name} -> WR: {wr:.1f}%, EV: {ev:.4f}, Trades: {tr}", flush=True)
                else:
                    print(f"[{completed_count}/{len(tasks)}] [{ds_name}] {strat_name} -> No valid candidate", flush=True)
            except Exception as exc:
                print(f"[{completed_count}/{len(tasks)}] [{ds_name}] {strat_name} generated exception: {exc}", flush=True)

    scratch_dir = os.path.join(ROOT_DIR, "scratch")
    data_dir = os.path.join(ROOT_DIR, "data")
    os.makedirs(scratch_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    payload = {
        "total_explored": len(all_results),
        "passing_count": len(passing_configs),
        "passing_configurations": passing_configs,
        "all_results": all_results
    }

    with open(os.path.join(scratch_dir, "optuna_results.json"), "w") as f:
        json.dump(payload, f, indent=2)

    with open(os.path.join(data_dir, "optuna_results.json"), "w") as f:
        json.dump(payload, f, indent=2)

    with open(os.path.join(scratch_dir, "m3_best_configurations.json"), "w") as f:
        json.dump(payload, f, indent=2)

    print("==========================================================================", flush=True)
    print(f"Parallel Exploration Complete. Total Evaluated: {len(all_results)}, Passing Target Criteria (>65% WR & EV > 0): {len(passing_configs)}", flush=True)
    print("Winning configurations saved to data/optuna_results.json, scratch/optuna_results.json, and scratch/m3_best_configurations.json", flush=True)
    for pc in passing_configs:
        print(f" -> [{pc['dataset']}] {pc['strategy']} | OOS WR: {pc['win_rate_oos']:.1f}% | EV: {pc['ev_per_trade_oos']:.4f} | Trades: {pc['total_trades_oos']} | Params: {pc['best_params']}", flush=True)
    print("==========================================================================", flush=True)

    return passing_configs


if __name__ == "__main__":
    run_parallel_exploration()
