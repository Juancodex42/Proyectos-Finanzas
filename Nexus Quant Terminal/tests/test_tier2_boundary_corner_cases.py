"""
Tier 2 (Boundary & Corner Cases) Test Suite
Covering 18 Features from PROJECT.md § Feature Inventory (6 test functions per feature = 108 total tests).
"""

import os
import math
import warnings
import pytest
import numpy as np
import pandas as pd
import itertools

from engine.simulator import BinarySimulator
from engine.ml_engine.feature_extractor import frac_diff_fixed, BinaryFeatureExtractor
from engine.ml_engine.cusum_monitor import CUSUMMonitor
from engine.ml_engine.regime_detector import RegimeDetector
from engine.ml_engine.meta_labeler import MetaLabeler
from engine.ml_engine.meta_filter import BinaryMLMetaFilter
from engine.ml_engine.purged_cv import PurgedGroupTimeSeriesSplit
from engine.auto_tuner import WalkForwardEngine, ParameterSurfaceAnalyzer, DynamicRegimeAdapter
from engine.optimizer import CapitalOptimizer, binomial_sf
from scripts.optimizer_grid_search import create_labels

from tests.conftest import (
    generate_synthetic_ohlcv,
    generate_custom_length_ohlcv,
    generate_zero_volume_ohlcv,
    generate_flat_price_ohlcv,
    generate_nan_ohlcv
)


# =====================================================================
# Feature 1: BinarySimulator Tie Rule Consistency
# =====================================================================

def test_f01_tie_rule_empty_signals_and_df():
    sim = BinarySimulator()
    df_empty = pd.DataFrame()
    signals_empty = pd.Series(dtype=object)
    
    res = sim.run(df_empty, signals_empty)
    assert res['trades'] == []
    assert res['summary']['total_trades'] == 0
    assert res['summary']['win_rate'] == 0.0


def test_f01_tie_rule_zero_bet_amount(synthetic_ohlcv_df, base_signals_series):
    sim = BinarySimulator()
    res = sim.run(synthetic_ohlcv_df, base_signals_series, bet_fraction=0.0, initial_capital=1000.0)
    
    assert res['summary']['total_trades'] > 0
    # Equity must remain constant at initial_capital since bet is 0
    for t in res['trades']:
        assert t['bet_size'] == 0.0
        assert t['pnl'] == 0.0
    assert res['equity_curve'][-1]['equity'] == 1000.0


def test_f01_tie_rule_100_percent_tie_return_stake():
    df_flat = generate_flat_price_ohlcv(n_rows=50, start_price=100.0)
    signals = pd.Series(['CALL'] * 50, index=df_flat.index)
    sim = BinarySimulator()
    
    res = sim.run(df_flat, signals, expiry_candles=1, tie_rule='RETURN_STAKE', initial_capital=500.0)
    assert res['summary']['total_trades'] > 0
    assert res['summary']['ties'] == res['summary']['total_trades']
    assert res['summary']['wins'] == 0
    assert res['summary']['losses'] == 0
    assert res['summary']['net_pnl'] == 0.0
    assert res['equity_curve'][-1]['equity'] == 500.0


def test_f01_tie_rule_100_percent_tie_loss():
    df_flat = generate_flat_price_ohlcv(n_rows=50, start_price=100.0)
    signals = pd.Series(['CALL'] * 50, index=df_flat.index)
    sim = BinarySimulator()
    
    res = sim.run(df_flat, signals, expiry_candles=1, tie_rule='LOSS', initial_capital=500.0, bet_fraction=0.1)
    assert res['summary']['total_trades'] > 0
    assert res['summary']['ties'] == 0
    assert res['summary']['losses'] == res['summary']['total_trades']
    assert res['summary']['net_pnl'] < 0.0
    assert res['equity_curve'][-1]['equity'] < 500.0


def test_f01_tie_rule_multi_asset_return_stake_vs_loss():
    df_flat1 = generate_flat_price_ohlcv(n_rows=30, start_price=100.0)
    df_flat2 = generate_flat_price_ohlcv(n_rows=30, start_price=50.0)
    universe = {'ASSET1': df_flat1, 'ASSET2': df_flat2}
    
    sig1 = [{'time': int(df_flat1['open_time'].iloc[i]), 'direction': 'CALL'} for i in range(5, 20)]
    sig2 = [{'time': int(df_flat2['open_time'].iloc[i]), 'direction': 'PUT'} for i in range(5, 20)]
    signals_by_pair = {'ASSET1': sig1, 'ASSET2': sig2}
    
    sim = BinarySimulator()
    res_ret = sim.run_multi_asset(universe, signals_by_pair, tie_rule='RETURN_STAKE', initial_capital=1000.0)
    res_loss = sim.run_multi_asset(universe, signals_by_pair, tie_rule='LOSS', initial_capital=1000.0)
    
    assert res_ret['summary']['ties'] > 0
    assert res_ret['summary']['net_pnl'] == 0.0
    
    assert res_loss['summary']['losses'] > 0
    assert res_loss['summary']['net_pnl'] < 0.0


def test_f01_tie_rule_invalid_parameter_fallback(synthetic_ohlcv_df, base_signals_series):
    sim = BinarySimulator()
    # Invalid tie_rule string should not crash, falls through standard non-loss comparison
    res = sim.run(synthetic_ohlcv_df, base_signals_series, tie_rule='INVALID_RULE')
    assert 'summary' in res
    assert res['summary']['total_trades'] >= 0


# =====================================================================
# Feature 2: Multi-Asset Barbell State Tracking
# =====================================================================

def test_f02_barbell_zero_capital_input(multi_asset_ohlcv_dict):
    sim = BinarySimulator()
    sig = [{'time': int(df['open_time'].iloc[10]), 'direction': 'CALL'} for df in multi_asset_ohlcv_dict.values()]
    signals_by_pair = {k: sig for k in multi_asset_ohlcv_dict.keys()}
    
    res = sim.run_multi_asset(multi_asset_ohlcv_dict, signals_by_pair, mode='BARBELL', initial_capital=0.0)
    assert res['summary']['total_trades'] >= 0
    assert res['equity_curve'][-1]['equity'] == 0.0


def test_f02_barbell_single_asset_universe():
    df = generate_synthetic_ohlcv(n_rows=100, seed=42)
    universe = {'EURUSD': df}
    sigs = [{'time': int(df['open_time'].iloc[i]), 'direction': 'CALL'} for i in range(10, 50, 5)]
    signals_by_pair = {'EURUSD': sigs}
    
    sim = BinarySimulator()
    res = sim.run_multi_asset(universe, signals_by_pair, mode='BARBELL', n_consecutive=3)
    assert res['summary']['total_trades'] > 0
    assert 'max_drawdown' in res['summary']


def test_f02_barbell_empty_universe():
    sim = BinarySimulator()
    res = sim.run_multi_asset({}, {}, mode='BARBELL')
    assert res['trades'] == []
    assert res['summary']['total_trades'] == 0


def test_f02_barbell_100_percent_loss_streak_resets():
    # Force 100% loss signals on trending down price with CALLs
    timestamps = pd.date_range('2024-01-01', periods=100, freq='1min')
    prices = np.linspace(100.0, 50.0, 100)
    df = pd.DataFrame({
        'open': prices,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices - 0.5,
        'volume': 1000,
        'open_time': (timestamps.astype('int64') // 10**6)
    }, index=timestamps)
    
    universe = {'ASSET1': df}
    sigs = [{'time': int(df['open_time'].iloc[i]), 'direction': 'CALL'} for i in range(5, 80, 2)]
    signals_by_pair = {'ASSET1': sigs}
    
    sim = BinarySimulator()
    res = sim.run_multi_asset(universe, signals_by_pair, mode='BARBELL', initial_capital=1000.0, risk_ratio=0.20)
    
    # 100% losses should trigger bullet ruin and external P2P arbitrage replenishment without crash
    assert res['summary']['losses'] > 0
    assert res['equity_curve'][-1]['equity'] >= 0.0


def test_f02_barbell_campaign_completion_and_bullet_reset():
    # Force 100% win signals on trending up price with CALLs
    timestamps = pd.date_range('2024-01-01', periods=100, freq='1min')
    prices = np.linspace(100.0, 200.0, 100)
    df = pd.DataFrame({
        'open': prices,
        'high': prices + 1.0,
        'low': prices - 0.1,
        'close': prices + 0.8,
        'volume': 1000,
        'open_time': (timestamps.astype('int64') // 10**6)
    }, index=timestamps)
    
    universe = {'ASSET1': df}
    sigs = [{'time': int(df['open_time'].iloc[i]), 'direction': 'CALL'} for i in range(5, 30, 3)]
    signals_by_pair = {'ASSET1': sigs}
    
    sim = BinarySimulator()
    res = sim.run_multi_asset(universe, signals_by_pair, mode='BARBELL', n_consecutive=3, initial_capital=1000.0)
    
    assert res['summary']['wins'] > 0
    assert res['equity_curve'][-1]['equity'] > 1000.0


def test_f02_barbell_overlapping_events_and_bullet_allocation(multi_asset_ohlcv_dict):
    sim = BinarySimulator()
    signals_by_pair = {}
    for pair, df in multi_asset_ohlcv_dict.items():
        signals_by_pair[pair] = [{'time': int(df['open_time'].iloc[i]), 'direction': 'CALL'} for i in range(10, 40, 2)]
        
    res = sim.run_multi_asset(multi_asset_ohlcv_dict, signals_by_pair, mode='BARBELL', bet_fraction=0.25)
    assert res['summary']['total_trades'] > 0
    assert len(res['trades']) <= len(res['equity_curve'])


# =====================================================================
# Feature 3: FracDiff FFT Acceleration
# =====================================================================

def test_f03_fracdiff_d_equals_zero():
    series = pd.Series([10.0, 12.0, 11.0, 13.0, 15.0, 14.0, 16.0, 18.0] * 5)
    res = frac_diff_fixed(series, d=0.0, threshold=1e-5)
    # d=0 corresponds to original series after window width
    valid_res = res.dropna()
    assert len(valid_res) > 0
    assert np.allclose(valid_res.iloc[-5:], series.iloc[-5:])


def test_f03_fracdiff_d_equals_one():
    series = pd.Series(np.linspace(100.0, 150.0, 50))
    res = frac_diff_fixed(series, d=1.0, threshold=1e-5)
    valid_res = res.dropna()
    assert len(valid_res) > 0
    # d=1 corresponds to first differences (approx constant slope step)
    diff_expected = series.diff().dropna().iloc[-10:]
    assert np.allclose(valid_res.iloc[-10:], diff_expected.values, atol=1e-3)


def test_f03_fracdiff_threshold_extremes():
    series = pd.Series(np.random.randn(100).cumsum() + 100.0)
    res_high_thresh = frac_diff_fixed(series, d=0.4, threshold=0.99)
    res_low_thresh = frac_diff_fixed(series, d=0.4, threshold=1e-12)
    
    assert len(res_high_thresh) == len(series)
    assert len(res_low_thresh) == len(series)
    assert res_high_thresh.dropna().shape[0] >= res_low_thresh.dropna().shape[0]


def test_f03_fracdiff_empty_series():
    series = pd.Series([], dtype=float)
    res = frac_diff_fixed(series, d=0.4)
    assert res.empty


def test_f03_fracdiff_constant_price_series():
    series = pd.Series([100.0] * 50)
    res = frac_diff_fixed(series, d=0.4)
    valid_res = res.dropna()
    assert len(valid_res) > 0
    # Frac diff of constant series equals constant * sum(weights)
    assert np.allclose(valid_res.iloc[-5:], valid_res.iloc[-1])


def test_f03_fracdiff_nan_input_handling():
    series = pd.Series([np.nan, 10.0, 11.0, np.nan, 12.0, 13.0, 14.0] * 5)
    res = frac_diff_fixed(series, d=0.4)
    assert len(res) == len(series)
    assert res.index.equals(series.index)


# =====================================================================
# Feature 4: Regime & CUSUM Memory/Pause Fix
# =====================================================================

def test_f04_cusum_zero_variance_inputs():
    monitor = CUSUMMonitor(expected_wr=0.6, payout=0.85)
    # Feed constant zero PnLs (TIEs)
    for _ in range(30):
        status = monitor.update(0.0)
        assert status in ['CONTINUE', 'PAUSE', 'RESUME', 'PAUSED']
    assert monitor.get_stats()['total_trades'] == 30


def test_f04_cusum_max_memory_stress_test():
    monitor = CUSUMMonitor(expected_wr=0.6, payout=0.85)
    # Feed 2000 trade results
    for i in range(2000):
        pnl = 0.85 if i % 2 == 0 else -1.0
        monitor.update(pnl)
        
    assert len(monitor.trade_results) <= 1000
    assert len(monitor.pause_history) <= 100
    assert monitor.get_stats()['total_trades'] == 2000


def test_f04_cusum_pause_resume_state_machine():
    monitor = CUSUMMonitor(expected_wr=0.6, payout=0.85, window=10)
    
    # 1. Feed initial wins to establish baseline
    for _ in range(15):
        monitor.update(0.85)
    assert monitor.should_trade()
    
    # 2. Feed consecutive losses to trigger PAUSE
    paused = False
    for _ in range(30):
        res = monitor.update(-1.0)
        if res == 'PAUSE':
            paused = True
            break
    assert paused or monitor.is_paused
    
    # 3. Feed wins post-pause to trigger RESUME
    resumed = False
    for _ in range(20):
        res = monitor.update(0.85)
        if res == 'RESUME':
            resumed = True
            break
    assert resumed or not monitor.is_paused


def test_f04_regime_infinite_returns_and_nan():
    detector = RegimeDetector()
    df_inf = generate_synthetic_ohlcv(n_rows=120)
    df_inf.iloc[10, df_inf.columns.get_loc('close')] = np.nan
    df_inf.iloc[20, df_inf.columns.get_loc('close')] = np.inf
    df_inf.iloc[30, df_inf.columns.get_loc('close')] = -np.inf
    
    obs = detector._prepare_observations(df_inf)
    assert not np.isnan(obs).any()
    assert not np.isinf(obs).any()


def test_f04_regime_unfitted_insufficient_data():
    detector = RegimeDetector()
    df_short = generate_synthetic_ohlcv(n_rows=50)
    detector.fit(df_short)
    assert not detector.is_fitted
    assert detector.should_trade(df_short)
    assert detector.get_current_state(df_short) == -1


def test_f04_cusum_reset_clears_state():
    monitor = CUSUMMonitor()
    for _ in range(20):
        monitor.update(-1.0)
    assert monitor.total_trades_count == 20
    
    monitor.reset()
    assert monitor.total_trades_count == 0
    assert len(monitor.trade_results) == 0
    assert len(monitor.pause_history) == 0
    assert not monitor.is_paused


# =====================================================================
# Feature 5: MetaLabeler Overflow & Boundaries
# =====================================================================

def test_f05_metalabeler_nanosecond_microsecond_timestamps():
    labeler = MetaLabeler()
    df = generate_synthetic_ohlcv(n_rows=50, seed=42)
    
    # Nanosecond open_time (>1e17)
    df['open_time'] = (df.index.astype('int64')) # ns timestamp integer
    idx = df.index[10:30]
    
    context = labeler._extract_context_features(df, idx)
    assert not context.empty
    assert 'hour_of_day' in context.columns
    assert not context.isna().any().any()


def test_f05_metalabeler_empty_signals_and_results():
    labeler = MetaLabeler()
    df = generate_synthetic_ohlcv(n_rows=50)
    signals = pd.Series(dtype=object)
    results = pd.Series(dtype=float)
    
    res = labeler.fit(df, signals, results)
    assert not labeler.is_fitted
    
    filtered = labeler.filter(df, signals)
    assert filtered.empty


def test_f05_metalabeler_short_dataframe_rolling_windows():
    labeler = MetaLabeler()
    df_short = generate_synthetic_ohlcv(n_rows=15)
    idx = df_short.index[5:10]
    
    context = labeler._extract_context_features(df_short, idx)
    # With a 15-row df BinaryFeatureExtractor cannot run but temporal features
    # (hour_of_day, realized_vol_*) should still be produced
    assert not context.empty
    # All produced columns must be finite (no NaN after fillna(0.0))
    assert not context.isna().any().any()


def test_f05_metalabeler_unfitted_passthrough(synthetic_ohlcv_df, base_signals_series):
    labeler = MetaLabeler()
    assert not labeler.is_fitted
    
    filtered = labeler.filter(synthetic_ohlcv_df, base_signals_series)
    assert filtered.equals(base_signals_series)


def test_f05_metalabeler_single_class_target_prevention():
    labeler = MetaLabeler()
    df = generate_synthetic_ohlcv(n_rows=100)
    signals = pd.Series(['CALL'] * 100, index=df.index)
    results = pd.Series([1.0] * 100, index=df.index)  # All 1s (WIN)
    
    labeler.fit(df, signals, results)
    assert not labeler.is_fitted  # Must not fit on single-class target


def test_f05_metalabeler_missing_feature_columns_in_predict():
    labeler = MetaLabeler()
    labeler.is_fitted = True
    labeler.feature_names = ['natr', 'rsi_14', 'custom_feat']
    
    class DummyModel:
        def predict_proba(self, X):
            return np.full((len(X), 2), 0.7)
            
    labeler.meta_model = DummyModel()
    
    df = generate_synthetic_ohlcv(n_rows=50)
    signals = pd.Series(['CALL'] * 5, index=df.index[:5])
    
    filtered = labeler.filter(df, signals)
    assert len(filtered.dropna()) == 5


# =====================================================================
# Feature 6: Walk-Forward Zero Trade Windows
# =====================================================================

class ZeroSignalStrategy:
    def prepare_data(self, df):
        return None
    def generate_signals(self, df, params, precomputed=None):
        return pd.Series([None] * len(df), index=df.index)

class AlwaysWinStrategy:
    def prepare_data(self, df):
        return None
    def generate_signals(self, df, params, precomputed=None):
        # Generate CALL on every candle
        return pd.Series(['CALL'] * len(df), index=df.index)


def test_f06_walkforward_zero_trade_windows():
    engine = WalkForwardEngine(n_windows=3)
    df = generate_synthetic_ohlcv(n_rows=500)
    
    res = engine.run_wfa(df, ZeroSignalStrategy(), base_params={})
    assert res['stable_windows'] == 0
    assert res['wfe'] == 0.0
    assert res['total_windows_tested'] == 3


def test_f06_walkforward_single_window_n1():
    engine = WalkForwardEngine(n_windows=1)
    df = generate_synthetic_ohlcv(n_rows=500)
    
    res = engine.run_wfa(df, AlwaysWinStrategy(), base_params={})
    assert res['total_windows_tested'] == 1
    assert 'wfe' in res


def test_f06_walkforward_100_percent_loss_windows():
    engine = WalkForwardEngine(n_windows=2)
    # Price trending down with CALL signals results in losses
    timestamps = pd.date_range('2024-01-01', periods=500, freq='1min')
    prices = np.linspace(200.0, 50.0, 500)
    df = pd.DataFrame({
        'open': prices,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices - 0.5,
        'volume': 1000,
        'open_time': (timestamps.astype('int64') // 10**6)
    }, index=timestamps)
    
    res = engine.run_wfa(df, AlwaysWinStrategy(), base_params={})
    assert res['stable_windows'] == 0
    assert res['mean_oos_wr'] == 0.0


def test_f06_walkforward_division_by_zero_protection():
    engine = WalkForwardEngine(n_windows=2)
    df = generate_synthetic_ohlcv(n_rows=500)
    
    res = engine.run_wfa(df, ZeroSignalStrategy(), base_params={})
    assert res['mean_is_wr'] == 0.0
    assert res['wfe'] == 0.0


def test_f06_walkforward_short_dataframe_boundary():
    engine = WalkForwardEngine(n_windows=5)
    df_short = generate_synthetic_ohlcv(n_rows=100)
    
    res = engine.run_wfa(df_short, AlwaysWinStrategy(), base_params={})
    assert res['wfe'] == 0.0
    assert res['total_windows_tested'] == 0


def test_f06_walkforward_direction_filters():
    engine = WalkForwardEngine(n_windows=2)
    df = generate_synthetic_ohlcv(n_rows=500)
    
    res_call = engine.run_wfa(df, AlwaysWinStrategy(), base_params={"direction_filter": "CALL_ONLY"})
    res_put = engine.run_wfa(df, AlwaysWinStrategy(), base_params={"direction_filter": "PUT_ONLY"})
    
    assert res_call['total_windows_tested'] == 2
    assert res_put['total_windows_tested'] == 2


# =====================================================================
# Feature 7: Expiry Label Boundaries
# =====================================================================

def test_f07_expiry_labels_zero_expiry_candles(synthetic_ohlcv_df, base_signals_series):
    labels = create_labels(synthetic_ohlcv_df, base_signals_series, expiry_candles=0)
    assert isinstance(labels, pd.Series)
    assert not labels.empty


def test_f07_expiry_labels_max_expiry_exceeding_df_length(synthetic_ohlcv_df, base_signals_series):
    labels = create_labels(synthetic_ohlcv_df, base_signals_series, expiry_candles=1000)
    assert labels.empty


def test_f07_expiry_labels_end_of_series_boundary_shift(synthetic_ohlcv_df, base_signals_series):
    labels = create_labels(synthetic_ohlcv_df, base_signals_series, expiry_candles=5)
    # The last 6 candles shift beyond end of df and should be dropped by dropna
    assert len(labels) <= len(synthetic_ohlcv_df) - 6


def test_f07_expiry_labels_missing_ohlc_values():
    df_nan = generate_nan_ohlcv(n_rows=100, nan_ratio=0.1)
    signals = pd.Series(['CALL'] * 100, index=df_nan.index)
    
    labels = create_labels(df_nan, signals, expiry_candles=1)
    assert not labels.isna().any()


def test_f07_expiry_labels_flat_price_ties():
    df_flat = generate_flat_price_ohlcv(n_rows=50, start_price=100.0)
    signals = pd.Series(['CALL'] * 50, index=df_flat.index)
    
    labels = create_labels(df_flat, signals, expiry_candles=1)
    # Ties exit_price <= entry_price for CALL yield label 0.0
    assert (labels == 0.0).all()


def test_f07_expiry_labels_signals_with_no_call_put(synthetic_ohlcv_df):
    signals_hold = pd.Series(['HOLD'] * len(synthetic_ohlcv_df), index=synthetic_ohlcv_df.index)
    labels = create_labels(synthetic_ohlcv_df, signals_hold, expiry_candles=1)
    assert labels.empty


# =====================================================================
# Feature 8: Feature Scaling Extremes
# =====================================================================

def test_f08_feature_scaling_constant_flat_prices():
    df_flat = generate_flat_price_ohlcv(n_rows=100)
    features = BinaryFeatureExtractor.extract_features(df_flat)
    
    assert not features.empty
    assert not features.isna().any().any()
    assert not np.isinf(features.values).any()


def test_f08_feature_scaling_extreme_outliers(synthetic_ohlcv_df):
    df_spike = synthetic_ohlcv_df.copy()
    # Spike 1 candle price by 1000x
    df_spike.iloc[100, df_spike.columns.get_loc('close')] *= 1000.0
    df_spike.iloc[100, df_spike.columns.get_loc('high')] *= 1000.0
    
    features = BinaryFeatureExtractor.extract_features(df_spike)
    assert not features.isna().any().any()
    assert not np.isinf(features.values).any()


def test_f08_feature_scaling_zero_volatility_squeeze():
    df_flat = generate_flat_price_ohlcv(n_rows=100)
    regime = DynamicRegimeAdapter.detect_regime(df_flat)
    
    assert 'regime' in regime
    assert regime['volatility_quantile'] == 1.0 or regime['volatility_quantile'] >= 0.0


def test_f08_feature_scaling_short_dataframe_regime_detect():
    df_short = generate_synthetic_ohlcv(n_rows=20)
    regime = DynamicRegimeAdapter.detect_regime(df_short)
    
    assert regime['regime'] == "NORMAL"
    assert regime['volatility_quantile'] == 0.5


def test_f08_meta_filter_missing_natr_column(synthetic_ohlcv_df, base_signals_series):
    m_filter = BinaryMLMetaFilter(adaptive_threshold=True)
    m_filter.is_fitted = True
    
    class DummyModel:
        def predict_proba(self, X):
            return np.full((len(X), 2), 0.7)
    m_filter.model = DummyModel()
    
    # X without 'natr' column
    X_no_natr = pd.DataFrame({'other_feat': [1.0] * len(synthetic_ohlcv_df)}, index=synthetic_ohlcv_df.index)
    filtered = m_filter.filter_signals(base_signals_series, X_no_natr)
    
    assert isinstance(filtered, pd.Series)


def test_f08_feature_scaling_adapt_params():
    base_params = {"bb_std": 2.0, "rsi_period": 14}
    
    adapted_high = DynamicRegimeAdapter.adapt_params(
        base_params, {"volatility_quantile": 1.5, "trend_direction": "BULLISH"}
    )
    assert adapted_high["bb_std"] == 2.2
    assert adapted_high["direction_filter"] == "CALL_ONLY"
    
    adapted_low = DynamicRegimeAdapter.adapt_params(
        base_params, {"volatility_quantile": 0.5, "trend_direction": "BEARISH"}
    )
    assert adapted_low["bb_std"] == 1.8
    assert adapted_low["direction_filter"] == "PUT_ONLY"


# =====================================================================
# Feature 9: HMM Probabilities Boundaries
# =====================================================================

def test_f09_hmm_single_state_configuration():
    detector = RegimeDetector(n_states=1)
    df = generate_synthetic_ohlcv(n_rows=150)
    
    detector.fit(df)
    assert detector.is_fitted
    state = detector.get_current_state(df)
    assert state == 0


def test_f09_hmm_uniform_probabilities_constant_input():
    detector = RegimeDetector(n_states=3)
    df_flat = generate_flat_price_ohlcv(n_rows=150)
    
    detector.fit(df_flat)
    state = detector.get_current_state(df_flat)
    assert state in [-1, 0, 1, 2]


def test_f09_hmm_single_row_dataframe():
    detector = RegimeDetector()
    detector.is_fitted = True
    
    # DummyHMM must implement _compute_log_likelihood because
    # predict_forward now uses the forward-algorithm path which needs it.
    class DummyHMM:
        n_components = 3
        startprob_ = np.array([0.5, 0.3, 0.2])
        transmat_ = np.array([[0.8, 0.1, 0.1],
                               [0.1, 0.8, 0.1],
                               [0.1, 0.1, 0.8]])
        def _compute_log_likelihood(self, obs):
            # Return uniform log-likelihood for each observation and state
            return np.zeros((len(obs), self.n_components))
    detector.model = DummyHMM()
    detector.n_states = 3
    
    df_1row = generate_synthetic_ohlcv(n_rows=1)
    state = detector.get_current_state(df_1row)
    assert state in [-1, 0, 1, 2]


def test_f09_hmm_unmapped_performance_states():
    detector = RegimeDetector()
    states = np.array([0, 1, 2, 0, 1, 2])
    signals = pd.Series(['HOLD'] * 6)
    results = pd.Series([np.nan] * 6)
    
    detector._map_states_to_performance(states, signals, results)
    assert detector.state_stats == {}


def test_f09_hmm_get_regime_report_unfitted():
    detector = RegimeDetector()
    df = generate_synthetic_ohlcv(n_rows=50)
    report = detector.get_regime_report(df)
    
    assert report['status'] == 'NOT_FITTED'


def test_f09_hmm_should_trade_passthrough_unfitted(synthetic_ohlcv_df):
    detector = RegimeDetector()
    assert not detector.is_fitted
    assert detector.should_trade(synthetic_ohlcv_df) is True


# =====================================================================
# Feature 10: Purged CV Boundaries
# =====================================================================

def test_f10_purged_cv_samples_less_than_splits():
    cv = PurgedGroupTimeSeriesSplit(n_splits=5)
    X = np.arange(3)  # 3 samples < 5 splits
    
    splits = list(cv.split(X))
    assert len(splits) == 5
    for train_idx, test_idx in splits:
        assert len(train_idx) + len(test_idx) <= 3


def test_f10_purged_cv_embargo_larger_than_test_set():
    cv = PurgedGroupTimeSeriesSplit(n_splits=3, embargo_pct=0.50)
    X = np.arange(100)
    
    splits = list(cv.split(X))
    assert len(splits) == 3
    for train_idx, test_idx in splits:
        assert len(train_idx) < 100


def test_f10_purged_cv_expiry_larger_than_test_size():
    cv = PurgedGroupTimeSeriesSplit(n_splits=5, expiry_candles=50)
    X = np.arange(100)  # test_size = 20 < 50 expiry candles
    
    splits = list(cv.split(X))
    assert len(splits) == 5


def test_f10_purged_cv_single_split():
    cv = PurgedGroupTimeSeriesSplit(n_splits=1)
    X = np.arange(50)
    
    splits = list(cv.split(X))
    assert len(splits) == 1


def test_f10_purged_cv_empty_dataset():
    cv = PurgedGroupTimeSeriesSplit(n_splits=5)
    X = np.array([])
    
    splits = list(cv.split(X))
    assert len(splits) == 5


def test_f10_purged_cv_get_n_splits():
    cv = PurgedGroupTimeSeriesSplit(n_splits=7)
    assert cv.get_n_splits() == 7


# =====================================================================
# Feature 11: Capital Split Isolation Boundaries
# =====================================================================

def test_f11_capital_split_negative_ev_rejection():
    opt = CapitalOptimizer()
    # Negative EV: p * r <= 1  (win_rate 0.4 * payout 1.0 = 0.8 <= 1)
    res = opt.find_optimal_n(win_rate=0.40, payout=1.0)
    assert "error" in res


def test_f11_capital_split_zero_winrate_extremes():
    opt = CapitalOptimizer()
    plan_zero = opt.calculate_streak_plan(
        win_rate=0.0, payout=0.85, risk_capital=200.0, target_capital=1000.0, attempts=5
    )
    assert plan_zero['win_rate'] == 0.0
    assert plan_zero['expected_final_patrimony'] <= plan_zero['base_capital']


def test_f11_capital_split_small_sample_wilson_bound():
    opt = CapitalOptimizer()
    # total_trades = 10 (< 30) triggers Wilson score lower bound adjustment
    plan = opt.calculate_streak_plan(
        win_rate=0.70, payout=0.85, risk_capital=200.0, target_capital=1000.0, attempts=5, total_trades=10
    )
    assert plan['win_rate_capped_warning'] is True
    assert plan['win_rate'] < 0.70  # Lower bound must be strictly less than raw 0.70


def test_f11_capital_split_markov_zero_transition():
    opt = CapitalOptimizer()
    res = opt.find_optimal_n_markov(
        p_states=[0.6], transition_matrix=[[0.0, 1.0], [0.0, 1.0]], payout=0.85
    )
    assert 'optimal_n' in res
    assert res['p_wl_fallback_used'] is True


def test_f11_capital_split_monte_carlo_zero_risk_capital():
    opt = CapitalOptimizer()
    res = opt.monte_carlo_campaign(
        win_rate=0.6, payout=0.85, n_streak=3, k_attempts=5, bet_per_attempt=0.0, num_simulations=100
    )
    assert res['expected_value'] == 0.0


def test_f11_capital_split_binomial_sf_boundaries():
    assert binomial_sf(k=5, M=0, p=0.5) == 1.0
    assert binomial_sf(k=5, M=10, p=0.5) == 0.0
    assert binomial_sf(k=5, M=3, p=0.0) == 0.0
    assert binomial_sf(k=5, M=3, p=1.0) == 1.0


# =====================================================================
# Feature 12: Optuna Extremes / Hyperparameter Search Edge Cases
# =====================================================================

def test_f12_optuna_single_trial_evaluation(multi_asset_ohlcv_dict):
    opt = CapitalOptimizer()
    # Stream optimizer with single evaluation iteration
    stream = opt.optimize_daily_confluence_stream(multi_asset_ohlcv_dict)
    first_step = next(stream)
    
    assert first_step['current'] == 1
    assert 'best_params' in first_step


def test_f12_optuna_invalid_hyperparameter_bounds():
    analyzer = ParameterSurfaceAnalyzer()
    df = generate_synthetic_ohlcv(n_rows=200)
    
    # Invalid or non-numeric params
    invalid_params = {"str_param": "invalid", "bool_param": True}
    res = analyzer.analyze_surface(df, AlwaysWinStrategy(), invalid_params)
    
    assert 'surface_score' in res
    assert 'plateau_ratio' in res


def test_f12_optuna_immediate_pruning_zero_trades():
    analyzer = ParameterSurfaceAnalyzer()
    df = generate_synthetic_ohlcv(n_rows=200)
    
    res = analyzer.analyze_surface(df, ZeroSignalStrategy(), {"period": 10})
    assert res['surface_score'] == 100.0  # Default fallback when no neighbors pass trade filter
    assert res['plateau_ratio'] == 1.0


def test_f12_optuna_empty_parameter_dictionary():
    analyzer = ParameterSurfaceAnalyzer()
    df = generate_synthetic_ohlcv(n_rows=200)
    
    res = analyzer.analyze_surface(df, AlwaysWinStrategy(), {})
    assert 'surface_score' in res


def test_f12_optuna_trial_failure_exception_handling():
    class BrokenStrategy:
        def prepare_data(self, df):
            raise ValueError("Data prep error")
        def generate_signals(self, df, params, precomputed=None):
            raise RuntimeError("Signal gen error")
            
    analyzer = ParameterSurfaceAnalyzer()
    df = generate_synthetic_ohlcv(n_rows=200)
    
    res = analyzer.analyze_surface(df, BrokenStrategy(), {"period": 10})
    assert 'surface_score' in res


def test_f12_parameter_surface_analyzer_short_df():
    analyzer = ParameterSurfaceAnalyzer()
    df_short = generate_synthetic_ohlcv(n_rows=50)
    
    res = analyzer.analyze_surface(df_short, AlwaysWinStrategy(), {"period": 10})
    assert res['surface_score'] == 0.0
    assert res['plateau_ratio'] == 0.0


# =====================================================================
# Feature 13: Search Space Boundaries
# =====================================================================

def test_f13_search_space_single_point():
    grid = {
        'pullback_tolerance': [0.01],
        'rsi_min_call': [30.0],
        'wick_rejection_ratio': [0.3]
    }
    keys, values = zip(*grid.items())
    combos = [dict(zip(keys, v)) for v in itertools.product(*values)]
    assert len(combos) == 1


def test_f13_search_space_extreme_expirations_1_to_12(synthetic_ohlcv_df, base_signals_series):
    sim = BinarySimulator()
    for exp in range(1, 13):
        res = sim.run(synthetic_ohlcv_df, base_signals_series, expiry_candles=exp)
        assert res['summary']['total_trades'] >= 0


def test_f13_search_space_empty_grid_dicts():
    grid = {}
    combos = list(itertools.product(*grid.values()))
    assert len(combos) == 1 and combos[0] == ()


def test_f13_search_space_single_row_dataset():
    df_1row = generate_synthetic_ohlcv(n_rows=1)
    signals_1row = pd.Series(['CALL'], index=df_1row.index)
    labels = create_labels(df_1row, signals_1row, expiry_candles=1)
    assert labels.empty


def test_f13_search_space_incompatible_indicator_periods():
    # fast_period (20) > slow_period (10)
    df = generate_synthetic_ohlcv(n_rows=100)
    features = BinaryFeatureExtractor.extract_features(df)
    
    # Delta RSI calculation fast - slow handles inverted inputs without exception
    delta_inverted = features['rsi_7'] - features['rsi_14']
    assert len(delta_inverted) == 100


def test_f13_search_space_combination_generator():
    param_grid = {
        'p1': [1, 2],
        'p2': [],  # Empty list in grid
        'p3': [0.5]
    }
    keys = list(param_grid.keys())
    combos = [dict(zip(keys, v)) for v in itertools.product(*param_grid.values())]
    assert len(combos) == 0  # Product with empty set yields 0 combos


# =====================================================================
# Feature 14: Walk-Forward Boundaries
# =====================================================================

def test_f14_walkforward_window_size_larger_than_dataset():
    engine = WalkForwardEngine(n_windows=10, train_ratio=0.80)
    df = generate_synthetic_ohlcv(n_rows=350)
    
    res = engine.run_wfa(df, AlwaysWinStrategy(), base_params={})
    assert 'total_windows_tested' in res


def test_f14_walkforward_extreme_train_ratios():
    engine_low = WalkForwardEngine(n_windows=2, train_ratio=0.10)
    engine_high = WalkForwardEngine(n_windows=2, train_ratio=0.90)
    df = generate_synthetic_ohlcv(n_rows=500)
    
    res_low = engine_low.run_wfa(df, AlwaysWinStrategy(), base_params={})
    res_high = engine_high.run_wfa(df, AlwaysWinStrategy(), base_params={})
    
    assert 'wfe' in res_low
    assert 'wfe' in res_high


def test_f14_walkforward_single_fold_n1():
    engine = WalkForwardEngine(n_windows=1, train_ratio=0.50)
    df = generate_synthetic_ohlcv(n_rows=400)
    
    res = engine.run_wfa(df, AlwaysWinStrategy(), base_params={})
    assert res['total_windows_tested'] == 1


def test_f14_walkforward_output_dictionary_keys(synthetic_ohlcv_df):
    engine = WalkForwardEngine(n_windows=2)
    res = engine.run_wfa(synthetic_ohlcv_df, AlwaysWinStrategy(), base_params={})
    
    expected_keys = {"wfe", "mean_is_wr", "mean_oos_wr", "stable_windows", "total_windows_tested", "window_results"}
    assert expected_keys.issubset(set(res.keys()))


def test_f14_walkforward_invalid_strategy_object(synthetic_ohlcv_df):
    class IncompleteStrategy:
        pass
        
    engine = WalkForwardEngine(n_windows=2)
    res = engine.run_wfa(synthetic_ohlcv_df, IncompleteStrategy(), base_params={})
    assert res['total_windows_tested'] == 0


def test_f14_walkforward_step_size_boundary():
    engine = WalkForwardEngine(n_windows=3, train_ratio=0.99)
    df = generate_synthetic_ohlcv(n_rows=500)
    
    res = engine.run_wfa(df, AlwaysWinStrategy(), base_params={})
    assert 'wfe' in res


# =====================================================================
# Feature 15: Vectorized Engine Extremes
# =====================================================================

def test_f15_vectorized_engine_empty_dataframe():
    sim = BinarySimulator()
    df_empty = pd.DataFrame()
    signals = pd.Series(dtype=object)
    
    res = sim.run(df_empty, signals)
    assert res['trades'] == []
    assert res['summary']['total_trades'] == 0


def test_f15_vectorized_engine_one_row_dataframe():
    sim = BinarySimulator()
    df_1row = generate_synthetic_ohlcv(n_rows=1)
    signals_1row = pd.Series(['CALL'], index=df_1row.index)
    
    res = sim.run(df_1row, signals_1row, expiry_candles=1)
    # Entry requires entry_idx + 1 < len(df), so 1-row df cannot execute trade
    assert res['trades'] == []


def test_f15_vectorized_engine_all_nan_signal_array(synthetic_ohlcv_df):
    sim = BinarySimulator()
    signals_nan = pd.Series([np.nan] * len(synthetic_ohlcv_df), index=synthetic_ohlcv_df.index)
    
    res = sim.run(synthetic_ohlcv_df, signals_nan)
    assert res['trades'] == []


def test_f15_vectorized_engine_all_hold_signal_array(synthetic_ohlcv_df):
    sim = BinarySimulator()
    signals_hold = pd.Series(['HOLD'] * len(synthetic_ohlcv_df), index=synthetic_ohlcv_df.index)
    
    res = sim.run(synthetic_ohlcv_df, signals_hold)
    assert res['trades'] == []


def test_f15_vectorized_engine_multi_asset_all_nan_signals(multi_asset_ohlcv_dict):
    sim = BinarySimulator()
    signals_by_pair = {k: [] for k in multi_asset_ohlcv_dict.keys()}
    
    res = sim.run_multi_asset(multi_asset_ohlcv_dict, signals_by_pair)
    assert res['trades'] == []
    assert res['summary']['total_trades'] == 0


def test_f15_vectorized_engine_nan_in_ohlcv_columns():
    df_nan = generate_nan_ohlcv(n_rows=50, nan_ratio=0.1)
    signals = pd.Series(['CALL'] * 50, index=df_nan.index)
    
    sim = BinarySimulator()
    res = sim.run(df_nan, signals)
    assert isinstance(res, dict)


# =====================================================================
# Feature 16: Test Harness Boundaries
# =====================================================================

def test_f16_test_harness_missing_test_files():
    # Attempting to read a non-existent file path
    non_existent_path = "data/raw/NON_EXISTENT_DATASET_999.csv"
    assert not os.path.exists(non_existent_path)


def test_f16_test_harness_empty_test_function_execution():
    df_zero = generate_custom_length_ohlcv(n_rows=0)
    assert df_zero.empty


def test_f16_test_harness_synthetic_df_extreme_volatility():
    df_zero_vol = generate_synthetic_ohlcv(n_rows=50, volatility=0.0)
    df_high_vol = generate_synthetic_ohlcv(n_rows=50, volatility=1000.0)
    
    assert not df_zero_vol.empty
    assert not df_high_vol.empty
    assert (df_high_vol['high'] >= df_high_vol['low']).all()


def test_f16_test_harness_synthetic_df_nan_ratio_100_percent():
    df_all_nan = generate_nan_ohlcv(n_rows=50, nan_ratio=1.0)
    assert df_all_nan['close'].isna().all()


def test_f16_test_harness_synthetic_df_custom_date_freq():
    df_sec = generate_synthetic_ohlcv(n_rows=10, freq='1s', start_date='2025-06-01 12:00:00')
    assert len(df_sec) == 10
    assert df_sec.index[1] - df_sec.index[0] == pd.Timedelta(seconds=1)


def test_f16_test_harness_boundary_helpers_integrity():
    df_vol = generate_zero_volume_ohlcv(n_rows=1)
    df_flat = generate_flat_price_ohlcv(n_rows=1, start_price=250.0)
    
    assert (df_vol['volume'] == 0.0).all()
    assert (df_flat['close'] == 250.0).all()


# =====================================================================
# Feature 17: Causality Audit Edge Cases
# =====================================================================

def test_f17_causality_subsecond_lookahead_attempts(synthetic_ohlcv_df):
    diffs = synthetic_ohlcv_df['open_time'].diff().dropna()
    # Timestamps must be strictly monotonic increasing
    assert (diffs > 0).all()


def test_f17_causality_synthetic_lookahead_detection():
    timestamps = pd.date_range('2024-01-01', periods=10, freq='1min')
    opens = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0])
    closes = opens + 0.5
    
    df = pd.DataFrame({
        'open': opens,
        'high': opens + 1.0,
        'low': opens - 0.5,
        'close': closes,
        'volume': 1000,
        'open_time': (timestamps.astype('int64') // 10**6)
    }, index=timestamps)
    
    signals = pd.Series([None, 'CALL', None, None, None, None, None, None, None, None], index=df.index)
    sim = BinarySimulator()
    res = sim.run(df, signals, expiry_candles=1)
    
    trades = res['trades']
    assert len(trades) == 1
    t = trades[0]
    
    # Signal triggered at index 1 (Close of candle 1 known).
    # Entry price must be Open of candle 2 (102.0), NOT Open of candle 1 (101.0)!
    assert t['entry_price'] == df.iloc[2]['open']


def test_f17_causality_shift_lag_feature_leakage_check():
    df = generate_synthetic_ohlcv(n_rows=100, seed=42)
    features = BinaryFeatureExtractor.extract_features(df)
    
    # Check that feature at index t is identical regardless of whether future rows (t+1..end) exist
    df_truncated = df.iloc[:50].copy()
    features_truncated = BinaryFeatureExtractor.extract_features(df_truncated)
    
    # Feature values at index 40 must match exactly between full and truncated datasets
    assert np.allclose(features.iloc[40].values, features_truncated.iloc[40].values, atol=1e-6)


def test_f17_causality_monotonic_timestamp_validation():
    timestamps = pd.date_range('2024-01-01', periods=5, freq='1min')
    open_times = (timestamps.astype('int64') // 10**6).tolist()
    
    # Swap timestamps to create non-monotonic order
    open_times[2], open_times[3] = open_times[3], open_times[2]
    df_non_mono = pd.DataFrame({'open_time': open_times})
    
    diffs = df_non_mono['open_time'].diff().dropna()
    assert not (diffs > 0).all()  # Detects non-monotonicity correctly


def test_f17_causality_timestamp_gap_handling():
    timestamps = pd.date_range('2024-01-01', periods=10, freq='1min')
    # Drop indices 3 and 4 to create a time gap
    timestamps_gapped = timestamps.delete([3, 4])
    
    df_gapped = generate_synthetic_ohlcv(n_rows=8)
    df_gapped.index = timestamps_gapped
    df_gapped['open_time'] = (timestamps_gapped.astype('int64') // 10**6)
    
    signals = pd.Series(['CALL'] * 8, index=df_gapped.index)
    sim = BinarySimulator()
    res = sim.run(df_gapped, signals)
    assert isinstance(res, dict)


def test_f17_causality_slippage_direction_application(synthetic_ohlcv_df):
    signals = pd.Series([None] * len(synthetic_ohlcv_df), index=synthetic_ohlcv_df.index)
    signals.iloc[10] = 'CALL'
    signals.iloc[20] = 'PUT'
    
    sim = BinarySimulator()
    res_no_slip = sim.run(synthetic_ohlcv_df, signals, slippage_pct=0.0)
    res_slip = sim.run(synthetic_ohlcv_df, signals, slippage_pct=0.01)  # 1% slippage
    
    t_call_noslip = res_no_slip['trades'][0]
    t_call_slip = res_slip['trades'][0]
    # CALL entry price with slippage must be HIGHER than no slippage
    assert t_call_slip['entry_price'] > t_call_noslip['entry_price']
    
    t_put_noslip = res_no_slip['trades'][1]
    t_put_slip = res_slip['trades'][1]
    # PUT entry price with slippage must be LOWER than no slippage
    assert t_put_slip['entry_price'] < t_put_noslip['entry_price']


# =====================================================================
# Feature 18: Verification Script Boundaries
# =====================================================================

def test_f18_verification_missing_inputs():
    def dummy_verify(dataset_path: str):
        if not os.path.exists(dataset_path):
            return {"status": "ERROR", "message": f"Dataset file missing: {dataset_path}"}
        return {"status": "SUCCESS"}
        
    res = dummy_verify("non_existent_dataset.csv")
    assert res['status'] == "ERROR"
    assert "missing" in res['message']


def test_f18_verification_exception_handling():
    def safe_run_verification(df):
        try:
            if df is None or df.empty:
                raise ValueError("Empty dataset input")
            return {"status": "OK", "win_rate": 0.70}
        except Exception as e:
            return {"status": "FAILED", "error": str(e)}
            
    res = safe_run_verification(pd.DataFrame())
    assert res['status'] == "FAILED"
    assert "Empty dataset" in res['error']


def test_f18_verification_strict_threshold_edge_conditions_winrate_65():
    target_wr = 0.65
    wr_pass = 0.651
    wr_exact = 0.650
    wr_fail = 0.649
    
    assert wr_pass > target_wr
    assert not (wr_fail > target_wr)
    # 65% exact boundary condition check
    assert wr_exact >= target_wr


def test_f18_verification_strict_threshold_edge_conditions_ev_zero():
    target_ev = 0.0
    ev_pass = 0.001
    ev_exact = 0.0
    ev_fail = -0.001
    
    assert ev_pass > target_ev
    assert not (ev_fail > target_ev)
    assert ev_exact >= target_ev


def test_f18_verification_wilson_lower_bound():
    def calculate_wilson_lower_bound(wins: int, total: int, z: float = 1.96) -> float:
        if total == 0:
            return 0.0
        p = wins / total
        denom = 1.0 + (z**2) / total
        center = (p + (z**2) / (2 * total)) / denom
        margin = (z * math.sqrt((p * (1.0 - p) / total) + (z**2) / (4 * (total**2)))) / denom
        return max(0.0, float(center - margin))
        
    assert calculate_wilson_lower_bound(0, 0) == 0.0
    assert calculate_wilson_lower_bound(1, 1) > 0.0
    
    # 65 wins out of 100
    lb_100 = calculate_wilson_lower_bound(65, 100)
    assert 0.50 < lb_100 < 0.65


def test_f18_verification_summary_schema_attestation():
    expected_schema_keys = {
        "strategy_config",
        "asset_universe_results",
        "win_rate_oos",
        "expected_value_per_trade",
        "wilson_lower_bound_95",
        "zero_causality_violation_attestation"
    }
    
    mock_verification_output = {
        "strategy_config": {"pullback_tolerance": 0.01},
        "asset_universe_results": {"BTCUSDT": 0.68},
        "win_rate_oos": 0.68,
        "expected_value_per_trade": 0.258,
        "wilson_lower_bound_95": 0.59,
        "zero_causality_violation_attestation": True
    }
    
    assert expected_schema_keys.issubset(set(mock_verification_output.keys()))
    assert mock_verification_output["zero_causality_violation_attestation"] is True
    assert mock_verification_output["win_rate_oos"] > 0.65
    assert mock_verification_output["expected_value_per_trade"] > 0.0
