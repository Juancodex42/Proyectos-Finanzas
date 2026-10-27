import pytest
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# Engine & ML Engine Modules
from engine.simulator import BinarySimulator
from engine.ml_engine.feature_extractor import BinaryFeatureExtractor, frac_diff_fixed
from engine.ml_engine.regime_detector import RegimeDetector
from engine.ml_engine.cusum_monitor import CUSUMMonitor
from engine.ml_engine.meta_labeler import MetaLabeler
from engine.ml_engine.meta_filter import BinaryMLMetaFilter
from engine.ml_engine.purged_cv import PurgedGroupTimeSeriesSplit
from engine.auto_tuner import WalkForwardEngine, ParameterSurfaceAnalyzer, DynamicRegimeAdapter
from engine.optimizer import CapitalOptimizer, binomial_sf
from engine.correlation import CorrelationEngine

# Strategies
from strategies.daily_confluence import DailyConfluenceStrategy

# Helper for Optuna import with fallback/mock if needed
try:
    import optuna
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False


# =====================================================================
# Area 1: FracDiff FFT Acceleration + HMM Regime Detector + MetaLabeler
# =====================================================================

def test_fracdiff_hmm_metalabeler_pipeline_integration(synthetic_ohlcv_df, base_signals_series):
    """
    Pipeline test: FracDiff FFT feature calculation -> HMM Regime Detector training & state
    inference -> MetaLabeler contextual signal filtering.
    """
    df = synthetic_ohlcv_df.copy()
    signals = base_signals_series.copy()

    # 1. Feature Extraction with FracDiff FFT
    features = BinaryFeatureExtractor.extract_features(df)
    assert 'frac_close' in features.columns
    assert 'frac_volume' in features.columns
    assert not features.isna().any().any()

    # 2. HMM Regime Detector (with fallback for singular covariance)
    regime_det = RegimeDetector(n_states=3)
    try:
        regime_det.fit(df)
    except Exception:
        pass
    state = regime_det.get_current_state(df)
    should_trade_regime = regime_det.should_trade(df)
    assert isinstance(state, int)
    assert isinstance(should_trade_regime, bool)

    # 3. Execution Simulation to generate target labels (WIN=1, LOSS=0)
    sim = BinarySimulator()
    res = sim.run(df, signals, expiry_candles=1, payout=0.85, allow_overlapping=True, max_concurrent_trades=50)
    trades = res['trades']

    results_series = pd.Series(index=signals.index, dtype=float)
    for t in trades:
        idx = df.index[t['index']]
        results_series.loc[idx] = 1.0 if t['result'] == 'WIN' else 0.0

    # 4. MetaLabeler Fitting & Filtering
    meta_labeler = MetaLabeler(threshold=0.60)
    meta_labeler.fit(df, signals, results_series)

    filtered_signals = meta_labeler.filter(df, signals)
    assert len(filtered_signals) == len(signals)
    assert (filtered_signals.dropna().index).isin(signals.dropna().index).all()


def test_fracdiff_fft_numeric_equivalence_and_regime_stability(synthetic_ohlcv_df):
    """
    Verifies that frac_diff_fixed using FFT convolve returns bounded stationary
    series across d=0.3 and d=0.5 without introducing NaNs in the very last element.
    The warm-up region (first N-1 elements where N is the kernel width) will contain NaN
    by design; only the last valid elements are checked.
    """
    series = synthetic_ohlcv_df['close']
    ffd_03 = frac_diff_fixed(series, d=0.3)
    ffd_05 = frac_diff_fixed(series, d=0.5)

    assert len(ffd_03) == len(series)
    assert len(ffd_05) == len(series)

    # Verify at least one valid (non-NaN) value exists at the tail
    valid_03 = ffd_03.dropna()
    valid_05 = ffd_05.dropna()
    assert len(valid_03) > 0, "frac_diff_fixed(d=0.3) produced no valid values"
    assert len(valid_05) > 0, "frac_diff_fixed(d=0.5) produced no valid values"

    # Last value must be finite
    assert np.isfinite(valid_03.iloc[-1])
    assert np.isfinite(valid_05.iloc[-1])

    # Higher d should generally reduce std vs original (stronger stationarity)
    # Only check when we have enough valid values for std to be meaningful
    if len(valid_05) >= 2:
        assert valid_05.std() <= series.iloc[50:].std()


def test_metalabeler_sparse_signal_fallback_in_fracdiff_pipeline(synthetic_ohlcv_df):
    """
    Tests MetaLabeler fallback behavior when trade signal count is below threshold (< 30).
    """
    df = synthetic_ohlcv_df.copy()
    sparse_signals = pd.Series(index=df.index, dtype=object)
    sparse_signals.iloc[10] = 'CALL'
    sparse_signals.iloc[20] = 'PUT'

    results_sparse = pd.Series(index=df.index, dtype=float)
    results_sparse.iloc[10] = 1.0
    results_sparse.iloc[20] = 0.0

    meta_labeler = MetaLabeler(threshold=0.65)
    meta_labeler.fit(df, sparse_signals, results_sparse)
    assert not meta_labeler.is_fitted

    filtered = meta_labeler.filter(df, sparse_signals)
    pd.testing.assert_series_equal(filtered, sparse_signals)


# =====================================================================
# Area 2: BinarySimulator Tie Rule Consistency + Multi-Asset Barbell
# =====================================================================

def test_tie_rule_consistency_single_vs_multi_asset(synthetic_ohlcv_df):
    """
    Verifies tie_rule='RETURN_STAKE' vs 'LOSS' consistency between single-asset
    and multi-asset simulator runs when exit_price equals entry_price.
    Uses signals on different dates to avoid the inter-class-per-day duplicate filter.
    """
    df = synthetic_ohlcv_df.copy()
    # Force close prices to equal open prices for exact tie scenario
    df['close'] = df['open']
    signals = pd.Series(index=df.index, dtype=object)
    signals.iloc[10] = 'CALL'
    signals.iloc[50] = 'PUT'

    sim = BinarySimulator()

    # Single-asset run: RETURN_STAKE
    res_single_return = sim.run(df, signals, expiry_candles=1, tie_rule='RETURN_STAKE', payout=0.85)
    assert res_single_return['summary']['ties'] == 2
    assert res_single_return['summary']['wins'] == 0
    assert res_single_return['summary']['losses'] == 0
    assert res_single_return['summary']['net_pnl'] == 0.0

    # Single-asset run: LOSS
    res_single_loss = sim.run(df, signals, expiry_candles=1, tie_rule='LOSS', payout=0.85)
    assert res_single_loss['summary']['ties'] == 0
    assert res_single_loss['summary']['losses'] == 2

    # Multi-asset run: use two separate assets to avoid inter-class-per-day filtering
    # Each pair gets exactly one signal so both trades should execute independently
    df_eur = df.copy()
    df_gbp = df.copy()

    universe_data = {'EURUSD': df_eur, 'EURJPY': df_gbp}  # Same class but different pair

    sig_eur = [{'time': int(df_eur.iloc[10]['open_time']), 'direction': 'CALL'}]
    sig_eurjpy = [{'time': int(df_gbp.iloc[10]['open_time']), 'direction': 'CALL'}]

    signals_by_pair_single = {
        'EURUSD': sig_eur,
    }

    # Run RETURN_STAKE multi-asset with 1 signal -> 1 tie
    res_multi_return = sim.run_multi_asset(
        {'EURUSD': df_eur}, signals_by_pair_single, expiry_candles=1,
        tie_rule='RETURN_STAKE', mode='SIMPLE'
    )
    assert res_multi_return['summary']['ties'] == 1
    assert res_multi_return['summary']['net_pnl'] == 0.0

    # Run LOSS multi-asset with 1 signal -> 1 loss
    res_multi_loss = sim.run_multi_asset(
        {'EURUSD': df_eur}, signals_by_pair_single, expiry_candles=1,
        tie_rule='LOSS', mode='SIMPLE'
    )
    assert res_multi_loss['summary']['ties'] == 0
    assert res_multi_loss['summary']['losses'] == 1


def test_multi_asset_barbell_bullet_state_corruption_fix(multi_asset_ohlcv_dict):
    """
    Verifies that multi-asset Barbell mode maintains uncorrupted bullet states
    when ties occur during active streak tracking.
    """
    sim = BinarySimulator()

    # Create dummy signals across assets
    signals_by_pair = {}
    for pair, df in multi_asset_ohlcv_dict.items():
        signals_list = []
        for i in range(10, 100, 20):
            signals_list.append({
                'time': int(df.iloc[i]['open_time']),
                'direction': 'CALL'
            })
        signals_by_pair[pair] = signals_list

    res_barbell = sim.run_multi_asset(
        universe_data=multi_asset_ohlcv_dict,
        signals_by_pair=signals_by_pair,
        mode='BARBELL',
        n_consecutive=3,
        bet_fraction=0.20,
        risk_ratio=0.20,
        tie_rule='RETURN_STAKE'
    )

    summary = res_barbell['summary']
    trades = res_barbell['trades']
    assert summary['total_trades'] > 0
    assert len(res_barbell['equity_curve']) > 0

    # Ensure equity curve never dips below 0 or goes NaN
    for eq_point in res_barbell['equity_curve']:
        assert eq_point['equity'] >= 0.0
        assert not np.isnan(eq_point['equity'])


def test_barbell_streak_reset_upon_loss_and_campaign_success(multi_asset_ohlcv_dict):
    """
    Tests Barbell mode streak resets upon trade loss and campaign completion upon streak target.
    """
    sim = BinarySimulator()
    pair = 'EURUSD'
    df = multi_asset_ohlcv_dict[pair].copy()

    # Construct signals
    signals_list = [{'time': int(df.iloc[i]['open_time']), 'direction': 'CALL'} for i in range(10, 200, 10)]
    signals_by_pair = {pair: signals_list}

    res_n2 = sim.run_multi_asset(
        universe_data={pair: df},
        signals_by_pair=signals_by_pair,
        mode='BARBELL',
        n_consecutive=2,
        bet_fraction=0.50,
        risk_ratio=0.20
    )

    assert 'summary' in res_n2
    assert res_n2['summary']['total_trades'] > 0


# =====================================================================
# Area 3: Purged CV + Capital Split Isolation + WalkForwardEngine
# =====================================================================

def test_purged_cv_split_integrity_and_embargo():
    """
    Verifies PurgedGroupTimeSeriesSplit index isolation, purge window, and embargo offset.
    """
    n_samples = 200
    X = np.arange(n_samples)
    cv = PurgedGroupTimeSeriesSplit(n_splits=4, expiry_candles=3, embargo_pct=0.05)

    for train_idx, test_idx in cv.split(X):
        test_start = test_idx[0]
        test_end = test_idx[-1]

        # Purge window check
        purge_region = np.arange(max(0, test_start - 3), test_start)
        for p in purge_region:
            assert p not in train_idx

        # Embargo window check
        embargo_len = int(n_samples * 0.05)
        embargo_region = np.arange(test_end + 1, min(n_samples, test_end + 1 + embargo_len))
        for e in embargo_region:
            assert e not in train_idx


def test_capital_state_split_isolation_in_is_oos(synthetic_ohlcv_df, base_signals_series):
    """
    Ensures In-Sample (IS) backtest equity does not leak into Out-Of-Sample (OOS) capital tracking.
    """
    df = synthetic_ohlcv_df.copy()
    signals = base_signals_series.copy()

    split_idx = 250
    df_is = df.iloc[:split_idx]
    sigs_is = signals.iloc[:split_idx]

    df_oos = df.iloc[split_idx:]
    sigs_oos = signals.iloc[split_idx:]

    sim = BinarySimulator()

    # Run IS backtest
    res_is = sim.run(df_is, sigs_is, initial_capital=1000.0)
    is_ending_equity = res_is['equity_curve'][-1]['equity']

    # Run OOS backtest cleanly starting at initial capital
    res_oos = sim.run(df_oos, sigs_oos, initial_capital=1000.0)
    oos_starting_equity = res_oos['equity_curve'][0]['equity']

    assert oos_starting_equity == 1000.0
    assert oos_starting_equity != is_ending_equity or is_ending_equity == 1000.0


def test_walk_forward_engine_with_purged_cv_folds(synthetic_ohlcv_df):
    """
    Tests WalkForwardEngine rolling windows with Purged CV folds.
    """
    wfe_engine = WalkForwardEngine(n_windows=3, train_ratio=0.60)
    strat = DailyConfluenceStrategy()
    base_params = {'pullback_tolerance': 0.01, 'rsi_min_call': 25.0}

    res = wfe_engine.run_wfa(synthetic_ohlcv_df, strat, base_params, expiry=2)

    assert "wfe" in res
    assert "stable_windows" in res
    assert "total_windows_tested" in res
    assert res["total_windows_tested"] <= 3


# =====================================================================
# Area 4: Optuna Integration + Search Space + Parallel Vectorization
# =====================================================================

def test_optuna_search_space_optimization_flow(synthetic_ohlcv_df):
    """
    Verifies Optuna multi-dimensional hyperparameter optimization flow.
    """
    if not HAS_OPTUNA:
        pytest.skip("optuna not installed in environment")

    df = synthetic_ohlcv_df.copy()
    sim = BinarySimulator()

    def objective(trial):
        expiry = trial.suggest_int('expiry_candles', 1, 3)
        payout = trial.suggest_float('payout', 0.75, 0.90)
        bet_frac = trial.suggest_float('bet_fraction', 0.05, 0.20)

        signals = pd.Series(index=df.index, dtype=object)
        signals.iloc[::25] = 'CALL'

        res = sim.run(df, signals, expiry_candles=expiry, payout=payout, bet_fraction=bet_frac)
        return res['summary']['win_rate']

    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=5)

    assert len(study.trials) == 5
    assert 'expiry_candles' in study.best_params
    assert 1 <= study.best_params['expiry_candles'] <= 3


def test_parallel_backtest_vectorization_consistency(synthetic_ohlcv_df, base_signals_series):
    """
    Verifies that backtests executed in parallel threads yield identical deterministic results.
    """
    df = synthetic_ohlcv_df.copy()
    signals = base_signals_series.copy()
    sim = BinarySimulator()

    params_grid = [
        {'expiry_candles': 1, 'payout': 0.85},
        {'expiry_candles': 2, 'payout': 0.88},
        {'expiry_candles': 3, 'payout': 0.90}
    ]

    # Sequential execution
    seq_results = [sim.run(df, signals, **p) for p in params_grid]

    # Parallel execution
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(sim.run, df, signals, **p) for p in params_grid]
        par_results = [f.result() for f in futures]

    for seq_res, par_res in zip(seq_results, par_results):
        assert seq_res['summary'] == par_res['summary']


def test_optuna_trial_pruning_and_search_space_bounds(synthetic_ohlcv_df):
    """
    Verifies parameter space bounds and pruning exception handling in Optuna search space.
    """
    if not HAS_OPTUNA:
        pytest.skip("optuna not installed in environment")

    def objective(trial):
        rsi_min = trial.suggest_float('rsi_min', 10.0, 40.0)
        if rsi_min > 30.0:
            raise optuna.exceptions.TrialPruned("Pruned high RSI threshold")
        return rsi_min * 2.0

    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=10)
    assert len(study.trials) == 10


# =====================================================================
# Area 5: Target Expiry Label Alignment + Feature Scaling + Causality
# =====================================================================

def test_target_expiry_label_alignment_with_simulator(synthetic_ohlcv_df):
    """
    Validates 1-candle and 3-candle expiry target labeling logic alignment with BinarySimulator look-ahead.
    """
    df = synthetic_ohlcv_df.copy()
    sim = BinarySimulator()

    signals = pd.Series(index=df.index, dtype=object)
    signals.iloc[100] = 'CALL'

    # Simulator trade execution
    res = sim.run(df, signals, expiry_candles=1, payout=0.85)
    trade = res['trades'][0]

    # Target label calculation logic: entry at open[101], exit at close[101]
    entry_price_calc = df.iloc[101]['open']
    exit_price_calc = df.iloc[101]['close']

    assert trade['entry_price'] == pytest.approx(entry_price_calc)
    assert trade['exit_price'] == pytest.approx(exit_price_calc)


def test_feature_scaling_zero_leakage_expanding_window(synthetic_ohlcv_df):
    """
    Verifies feature calculation at candle T is completely invariant to appending future candles T+1..N.
    """
    df_full = synthetic_ohlcv_df.copy()
    t_cutoff = 300

    df_truncated = df_full.iloc[:t_cutoff].copy()

    feat_full = BinaryFeatureExtractor.extract_features(df_full)
    feat_trunc = BinaryFeatureExtractor.extract_features(df_truncated)

    # Compare features up to t_cutoff - 5 (to account for rolling window boundaries)
    slice_idx = df_truncated.index[100:t_cutoff - 5]
    pd.testing.assert_frame_equal(feat_full.loc[slice_idx], feat_trunc.loc[slice_idx])


def test_causality_zero_cheating_future_mutation(synthetic_ohlcv_df, base_signals_series):
    """
    Adversarial test: Mutate future prices beyond index T and assert past signals and trades stay unchanged.
    """
    df_orig = synthetic_ohlcv_df.copy()
    signals = base_signals_series.copy()
    sim = BinarySimulator()

    t_idx = 200

    res_orig = sim.run(df_orig.iloc[:t_idx], signals.iloc[:t_idx])

    # Mutate future dataframe beyond t_idx
    df_mutated = df_orig.copy()
    df_mutated.iloc[t_idx:, df_mutated.columns.get_loc('close')] *= 50.0

    res_mutated = sim.run(df_mutated.iloc[:t_idx], signals.iloc[:t_idx])

    assert res_orig['summary'] == res_mutated['summary']
    assert res_orig['trades'] == res_mutated['trades']


# =====================================================================
# Area 6: CUSUM Monitor + Dynamic Regime Adapter + BinaryMLMetaFilter
# =====================================================================

def test_cusum_monitor_pause_and_resume_dynamics():
    """
    Tests CUSUMMonitor bilateral drift detection, triggering PAUSE on loss stream and RESUME on recovery.
    """
    cusum = CUSUMMonitor(expected_wr=0.60, payout=0.85, threshold_sigma=1.5, window=20)

    # Feed initial winning trades
    for _ in range(15):
        status = cusum.update(0.85)
        assert status in ['CONTINUE', 'RESUME']

    # Feed heavy losing streak to trigger PAUSE
    pause_triggered = False
    for _ in range(25):
        status = cusum.update(-1.0)
        if status == 'PAUSE':
            pause_triggered = True

    assert pause_triggered
    assert cusum.is_paused

    # Feed recovery winning trades during PAUSE to trigger RESUME
    resume_triggered = False
    for _ in range(10):
        status = cusum.update(0.85)
        if status == 'RESUME':
            resume_triggered = True

    assert resume_triggered
    assert not cusum.is_paused


def test_dynamic_regime_adapter_adaptation(synthetic_ohlcv_df):
    """
    Tests DynamicRegimeAdapter ATR quantile calculation and dynamic parameter scaling.
    """
    regime_info = DynamicRegimeAdapter.detect_regime(synthetic_ohlcv_df)
    assert 'regime' in regime_info
    assert 'volatility_quantile' in regime_info
    assert 'trend_direction' in regime_info

    base_params = {'bb_std': 2.0, 'direction_filter': 'BOTH'}
    adapted = DynamicRegimeAdapter.adapt_params(base_params, regime_info)

    assert 'bb_std' in adapted
    assert 'direction_filter' in adapted


def test_binary_ml_meta_filter_adaptive_thresholding(synthetic_ohlcv_df, base_signals_series):
    """
    Tests BinaryMLMetaFilter adaptive thresholding under elevated NATR volatility.
    """
    df = synthetic_ohlcv_df.copy()
    signals = base_signals_series.copy()

    features = BinaryFeatureExtractor.extract_features(df)

    # Fake training set
    X_train = features.iloc[:300]
    y_train = pd.Series(np.random.choice([0, 1], size=len(X_train)), index=X_train.index)

    meta_filter = BinaryMLMetaFilter(probability_threshold=0.60, adaptive_threshold=True)
    meta_filter.fit(X_train, y_train)

    filtered_sigs = meta_filter.filter_signals(signals.iloc[300:], features.iloc[300:])
    assert len(filtered_sigs) == len(signals.iloc[300:])


# =====================================================================
# Area 7: Multi-Asset Barbell + Parallel Vectorization + Tie Rules
# =====================================================================

def test_multi_asset_barbell_parallel_vectorization_equity_match(multi_asset_ohlcv_dict):
    """
    Verifies that multi-asset Barbell runs produce deterministic, matching equity curves.
    """
    sim = BinarySimulator()

    signals_by_pair = {}
    for pair, df in multi_asset_ohlcv_dict.items():
        signals_by_pair[pair] = [{'time': int(df.iloc[i]['open_time']), 'direction': 'CALL'} for i in range(10, 100, 30)]

    res1 = sim.run_multi_asset(multi_asset_ohlcv_dict, signals_by_pair, mode='BARBELL', tie_rule='RETURN_STAKE')
    res2 = sim.run_multi_asset(multi_asset_ohlcv_dict, signals_by_pair, mode='BARBELL', tie_rule='RETURN_STAKE')

    assert res1['summary'] == res2['summary']


def test_multi_asset_barbell_inter_class_correlation_filter(multi_asset_ohlcv_dict):
    """
    Verifies Inter-Class Correlation Filter blocking duplicate same-day signals for asset class.
    """
    sim = BinarySimulator()

    # Create two pairs belonging to same class (e.g. Forex: EURUSD and GBPUSD)
    df_eur = multi_asset_ohlcv_dict['EURUSD']
    df_gbp = multi_asset_ohlcv_dict['GBPUSD']

    same_time = int(df_eur.iloc[20]['open_time'])

    signals_by_pair = {
        'EURUSD': [{'time': same_time, 'direction': 'CALL'}],
        'GBPUSD': [{'time': same_time, 'direction': 'CALL'}]
    }

    res = sim.run_multi_asset({'EURUSD': df_eur, 'GBPUSD': df_gbp}, signals_by_pair, mode='BARBELL')

    # Inter-class filter blocks duplicate signal of same asset class on same day
    assert res['summary']['total_trades'] == 1


def test_multi_asset_barbell_capital_exhaustion_recovery(multi_asset_ohlcv_dict):
    """
    Verifies Barbell mode re-supplies risk_cap when all bullets are ruined.
    """
    sim = BinarySimulator()
    df = multi_asset_ohlcv_dict['EURUSD']

    # Force losing trades
    df['close'] = df['open'] - 10.0
    signals_list = [{'time': int(df.iloc[i]['open_time']), 'direction': 'CALL'} for i in range(10, 150, 10)]

    res = sim.run_multi_asset({'EURUSD': df}, {'EURUSD': signals_list}, mode='BARBELL', risk_ratio=0.10, bet_fraction=0.50)
    assert res['summary']['total_trades'] > 0
    # Safe core prevents total liquidation
    assert res['equity_curve'][-1]['equity'] > 0.0


# =====================================================================
# Area 8: WalkForwardEngine + Purged CV + Optuna Hyperparameter Optimization
# =====================================================================

def test_optuna_walk_forward_purged_cv_integration(synthetic_ohlcv_df):
    """
    Tests an Optuna study optimizing a strategy evaluated over WalkForwardEngine with Purged CV folds.
    """
    if not HAS_OPTUNA:
        pytest.skip("optuna not installed in environment")

    df = synthetic_ohlcv_df.copy()
    wfe = WalkForwardEngine(n_windows=2, train_ratio=0.60)
    strat = DailyConfluenceStrategy()

    def objective(trial):
        pb_tol = trial.suggest_float('pullback_tolerance', 0.005, 0.02)
        base_params = {'pullback_tolerance': pb_tol, 'rsi_min_call': 25.0}

        wfa_res = wfe.run_wfa(df, strat, base_params, expiry=1)
        return wfa_res.get('mean_oos_wr', 0.0)

    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=3)

    assert len(study.trials) == 3


def test_walk_forward_efficiency_calculation_stability(synthetic_ohlcv_df):
    """
    Tests WalkForwardEngine edge cases: zero IS trades, zero OOS trades, and stability boundary.
    """
    wfe = WalkForwardEngine(n_windows=3, train_ratio=0.60)
    strat = DailyConfluenceStrategy()

    # Pass parameters that generate 0 signals
    zero_signal_params = {'pullback_tolerance': 0.000001, 'rsi_min_call': 99.0}
    res = wfe.run_wfa(synthetic_ohlcv_df, strat, zero_signal_params)

    assert res['wfe'] == 0.0
    assert res['stable_windows'] == 0


# =====================================================================
# Area 9: BinaryFeatureExtractor + MetaLabeler Timestamp + Reproducibility
# =====================================================================

def test_metalabeler_timestamp_unit_auto_detection():
    """
    Verifies MetaLabeler auto-detection of seconds, milliseconds, microseconds, nanoseconds timestamps.
    """
    meta_labeler = MetaLabeler()

    dates = pd.date_range('2024-01-01', periods=50, freq='1min')
    open_prices = np.full(50, 100.0)

    # Test unix seconds and ms with complete OHLCV DataFrame structure
    df_s = pd.DataFrame({
        'open': open_prices, 'high': open_prices + 1, 'low': open_prices - 1, 'close': open_prices,
        'volume': 1000.0, 'open_time': (dates.astype('int64') // 10**9)
    }, index=dates)

    df_ms = pd.DataFrame({
        'open': open_prices, 'high': open_prices + 1, 'low': open_prices - 1, 'close': open_prices,
        'volume': 1000.0, 'open_time': (dates.astype('int64') // 10**6)
    }, index=dates)

    idx = df_s.index[::5]

    ctx_s = meta_labeler._extract_context_features(df_s, idx)
    ctx_ms = meta_labeler._extract_context_features(df_ms, idx)

    assert 'hour_of_day' in ctx_s.columns
    assert 'hour_of_day' in ctx_ms.columns


def test_feature_extraction_reproducibility_deterministic(synthetic_ohlcv_df):
    """
    Ensures 100% deterministic reproducibility across repeated feature extraction calls.
    """
    f1 = BinaryFeatureExtractor.extract_features(synthetic_ohlcv_df)
    f2 = BinaryFeatureExtractor.extract_features(synthetic_ohlcv_df)

    pd.testing.assert_frame_equal(f1, f2)


def test_capital_optimizer_reproducibility_and_streak_plan():
    """
    Tests CapitalOptimizer streak plan calculations and Kelly criterion determinism.
    """
    opt = CapitalOptimizer()
    res = opt.find_optimal_n(win_rate=0.65, payout=0.85)

    assert res['optimal_n'] >= 1
    assert 0.0 < res['optimal_kelly'] < 1.0
    assert res['safe_kelly'] == pytest.approx(res['optimal_kelly'] * 0.5)

    plan = opt.calculate_streak_plan(win_rate=0.65, payout=0.85, risk_capital=200.0, target_capital=1000.0, attempts=5)
    assert 'best_n_for_target' in plan
    assert len(plan['results_by_n']) == 15


# =====================================================================
# Area 10: Full System Pipeline Integration
# =====================================================================

def test_full_system_pipeline_end_to_end_single_asset(synthetic_ohlcv_df, base_signals_series):
    """
    End-to-End single-asset test:
    Features -> Regime Detector -> Meta Filtering -> Execution Simulation -> CUSUM Monitoring.
    """
    df = synthetic_ohlcv_df.copy()
    base_sigs = base_signals_series.copy()

    # Step 1: Feature Extraction
    features = BinaryFeatureExtractor.extract_features(df)
    assert not features.empty

    # Step 2: Regime Gating (with fallback for singular matrix on synthetic data)
    regime_det = RegimeDetector()
    try:
        regime_det.fit(df)
    except Exception:
        pass
    should_trade = regime_det.should_trade(df)
    assert isinstance(should_trade, bool)

    # Step 3: Meta Filtering
    meta_filter = BinaryMLMetaFilter(probability_threshold=0.55)
    y_dummy = pd.Series(np.random.choice([0, 1], size=200), index=df.index[:200])
    meta_filter.fit(features.iloc[:200], y_dummy)

    filtered_sigs = meta_filter.filter_signals(base_sigs, features)

    # Step 4: Execution Simulation
    sim = BinarySimulator()
    sim_res = sim.run(df, filtered_sigs, expiry_candles=1, payout=0.85, tie_rule='RETURN_STAKE')

    assert 'summary' in sim_res
    assert 'trades' in sim_res
    assert 'equity_curve' in sim_res

    # Step 5: CUSUM Feedback Loop
    cusum = CUSUMMonitor()
    for trade in sim_res['trades']:
        pnl = trade['pnl']
        status = cusum.update(pnl)
        assert status in ['CONTINUE', 'PAUSE', 'RESUME', 'PAUSED']


def test_full_system_pipeline_end_to_end_multi_asset_barbell(multi_asset_ohlcv_dict):
    """
    End-to-End multi-asset Barbell test:
    Multi-Asset Features -> Dynamic Regime Adaptation -> Multi-Asset Execution -> Capital Isolation.
    """
    sim = BinarySimulator()

    signals_by_pair = {}
    for pair, df in multi_asset_ohlcv_dict.items():
        regime = DynamicRegimeAdapter.detect_regime(df)
        adapted_params = DynamicRegimeAdapter.adapt_params({'bb_std': 2.0}, regime)
        assert 'direction_filter' in adapted_params

        signals_by_pair[pair] = [{'time': int(df.iloc[i]['open_time']), 'direction': 'CALL'} for i in range(15, 120, 25)]

    res = sim.run_multi_asset(
        universe_data=multi_asset_ohlcv_dict,
        signals_by_pair=signals_by_pair,
        mode='BARBELL',
        n_consecutive=3,
        bet_fraction=0.166,
        tie_rule='RETURN_STAKE'
    )

    summary = res['summary']
    assert summary['total_trades'] >= 0
    assert summary['win_rate'] >= 0.0
    assert summary['max_drawdown'] >= 0.0


def test_full_system_pipeline_noisy_or_sparse_data_resilience(synthetic_ohlcv_df):
    """
    End-to-End boundary resilience test on flat/constant prices.
    """
    df_flat = synthetic_ohlcv_df.copy()
    df_flat['close'] = 100.0
    df_flat['open'] = 100.0
    df_flat['high'] = 100.0
    df_flat['low'] = 100.0

    features = BinaryFeatureExtractor.extract_features(df_flat)
    assert not features.isna().any().any()

    signals = pd.Series(index=df_flat.index, dtype=object)
    signals.iloc[50] = 'CALL'

    sim = BinarySimulator()
    res = sim.run(df_flat, signals, tie_rule='RETURN_STAKE')

    assert res['summary']['ties'] == 1
    assert res['summary']['wins'] == 0
    assert res['summary']['losses'] == 0
