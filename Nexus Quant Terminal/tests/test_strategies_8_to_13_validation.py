import os
import sys
import glob
import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.simulator import BinarySimulator
from strategies.daily_confluence import DailyConfluenceStrategy
from strategies.mtf_tcve import MtfTcveStrategy
from strategies.deesr import DeesrStrategy
from strategies.islg_rs import IslgRsStrategy
from strategies.volatility_squeeze_ml import VolatilitySqueezeMLStrategy
from strategies.climax_reversal import ClimaxReversalStrategy

STRATEGIES_8_TO_13 = {
    "daily_confluence": DailyConfluenceStrategy,
    "mtf_tcve": MtfTcveStrategy,
    "deesr": DeesrStrategy,
    "islg_rs": IslgRsStrategy,
    "volatility_squeeze_ml": VolatilitySqueezeMLStrategy,
    "climax_reversal": ClimaxReversalStrategy
}

def load_test_dataset():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not csv_files:
        # Fallback to local data dir if run from root
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    dfs = {}
    for f in csv_files[:5]:
        name = os.path.basename(f)
        try:
            df = pd.read_csv(f)
            if 'close' in df.columns and len(df) >= 100:
                dfs[name] = df
        except Exception:
            pass
    return dfs

def test_all_strategies_generate_trades_and_stats():
    datasets = load_test_dataset()
    assert len(datasets) > 0, "No CSV datasets found for validation"
    
    sim = BinarySimulator()
    results = {}
    
    for strat_key, strat_cls in STRATEGIES_8_TO_13.items():
        strategy = strat_cls()
        results[strat_key] = []
        
        for ds_name, df in datasets.items():
            # Test 1: Direct df signals
            signals_df = strategy.generate_signals(df=df)
            assert isinstance(signals_df, pd.Series), f"{strat_key} did not return a Series"
            assert len(signals_df) == len(df), f"{strat_key} signal length mismatch"
            
            # Test 2: Precomputed signals with df=None
            precomputed = strategy.prepare_data(df)
            signals_pre = strategy.generate_signals(df=None, precomputed=precomputed)
            assert isinstance(signals_pre, pd.Series), f"{strat_key} failed with df=None + precomputed"
            assert len(signals_pre) == len(df), f"{strat_key} precomputed signal length mismatch"
            
            # Test 3: Simulation and stats calculation
            sim_res = sim.run(df, signals_df, expiry_candles=3, payout=0.85)
            summary = sim_res['summary']
            
            total_trades = summary.get('total_trades', 0)
            win_rate = summary.get('win_rate', 0.0)
            ev = summary.get('expected_value_per_trade', 0.0)
            
            results[strat_key].append({
                'dataset': ds_name,
                'trades': total_trades,
                'win_rate': win_rate,
                'ev': ev
            })
            
    # Verify every strategy generates > 0 trades across the evaluated datasets
    for strat_key, runs in results.items():
        total_trades_strat = sum(r['trades'] for r in runs)
        print(f"\n[Validation] Strategy '{strat_key}': Total trades across datasets = {total_trades_strat}")
        for r in runs:
            print(f"   -> Dataset {r['dataset']}: trades={r['trades']}, WR={r['win_rate']*100:.1f}%, EV={r['ev']:.4f}")
        assert total_trades_strat > 0, f"Strategy {strat_key} produced 0 trades across all datasets!"

def test_daily_confluence_params_and_list():
    strat = DailyConfluenceStrategy()
    df = next(iter(load_test_dataset().values()))
    custom_params = {
        "pullback_tolerance": 0.015,
        "rsi_min_call": 30.0,
        "rsi_max_call": 60.0,
        "rsi_min_put": 40.0,
        "rsi_max_put": 70.0,
        "wick_rejection_ratio": 0.20
    }
    signals_list = strat.generate_signals_list(df_daily=df, params=custom_params)
    assert isinstance(signals_list, list)
    for sig in signals_list:
        assert 'direction' in sig and sig['direction'] in ['CALL', 'PUT']
        assert 'price' in sig
        assert 'time' in sig

def test_mtf_tcve_precomputed_robustness():
    strat = MtfTcveStrategy()
    df = next(iter(load_test_dataset().values()))
    pre = strat.prepare_data(df)
    signals = strat.generate_signals(df=None, params={"vol_mult": 1.2, "rsi_oversold": 30.0}, precomputed=pre)
    assert isinstance(signals, pd.Series)
    assert signals.notna().sum() > 0

def test_deesr_precomputed_price_preservation():
    strat = DeesrStrategy()
    df = next(iter(load_test_dataset().values()))
    pre = strat.prepare_data(df)
    assert not np.array_equal(pre['close'], pre['bb_sma'])
    signals = strat.generate_signals(df=None, precomputed=pre)
    assert isinstance(signals, pd.Series)
    assert signals.notna().sum() > 0

def test_islg_rs_ms_and_sec_timestamps():
    strat = IslgRsStrategy()
    df = next(iter(load_test_dataset().values())).copy()
    
    # Test with seconds
    df_sec = df.copy()
    df_sec['open_time'] = 1700000000 + np.arange(len(df_sec)) * 3600
    pre_sec = strat.prepare_data(df_sec)
    assert pre_sec['hours'] is not None and not pre_sec['hours'].isna().all()
    
    # Test with milliseconds
    df_ms = df.copy()
    df_ms['open_time'] = (1700000000 + np.arange(len(df_ms)) * 3600) * 1000
    pre_ms = strat.prepare_data(df_ms)
    assert pre_ms['hours'] is not None and not pre_ms['hours'].isna().all()

def test_volatility_squeeze_ml_short_dataset():
    strat = VolatilitySqueezeMLStrategy()
    df = next(iter(load_test_dataset().values())).iloc[:50].copy()
    pre = strat.prepare_data(df)
    assert 'features' in pre
    signals = strat.generate_signals(df=None, params={"prob_thresh": 0.52}, precomputed=pre)
    assert isinstance(signals, pd.Series)
    assert len(signals) == len(df)

def test_climax_reversal_param_aliases():
    strat = ClimaxReversalStrategy()
    df = next(iter(load_test_dataset().values()))
    # Test with standard names
    sig1 = strat.generate_signals(df, {"streak_len": 3, "wick_ratio": 0.30, "vol_mult": 1.2})
    # Test with legacy/alias names
    sig2 = strat.generate_signals(df, {"min_streak": 3, "min_wick_ratio": 0.30, "volume_mult": 1.2})
    assert isinstance(sig1, pd.Series) and sig1.notna().sum() > 0
    assert isinstance(sig2, pd.Series) and sig2.notna().sum() > 0
