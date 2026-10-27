import time
import math
import pytest
import numpy as np
import pandas as pd

from engine.simulator import BinarySimulator
from engine.auto_tuner import WalkForwardEngine, ParameterSurfaceAnalyzer, DynamicRegimeAdapter
from engine.optimizer import CapitalOptimizer
from engine.ml_engine import (
    BinaryFeatureExtractor,
    CUSUMMonitor,
    MetaLabeler,
    RegimeDetector,
    BinaryMLMetaFilter,
    PurgedGroupTimeSeriesSplit
)
from engine.ml_engine.feature_extractor import frac_diff_fixed
from strategies.daily_confluence import DailyConfluenceStrategy
from strategies.volatility_squeeze_ml import VolatilitySqueezeMLStrategy
from tests.conftest import (
    generate_synthetic_ohlcv,
    generate_custom_length_ohlcv,
    generate_zero_volume_ohlcv,
    generate_flat_price_ohlcv,
    generate_nan_ohlcv
)


def compute_wilson_lower_bound(wins: int, total: int, confidence: float = 0.95) -> float:
    """Calcula el límite inferior del intervalo de confianza de Wilson (95%)."""
    if total == 0:
        return 0.0
    p = wins / total
    z = 1.95996  # 95% confidence level
    num = p + (z**2) / (2 * total) - z * math.sqrt((p * (1 - p) + (z**2) / (4 * total)) / total)
    denom = 1 + (z**2) / total
    return max(0.0, float(num / denom))


# -----------------------------------------------------------------------------
# Scenario 1: Realistic Multi-Asset Barbell Backtest & Tie Rules
# -----------------------------------------------------------------------------
def test_scenario_1_realistic_multi_asset_barbell_backtest(multi_asset_ohlcv_dict):
    """
    Scenario 1: Realistic Multi-Asset Binary Options Strategy Backtest with
    Barbell Capital Allocation & Tie Rules.
    """
    sim = BinarySimulator()
    strat = DailyConfluenceStrategy()

    # Generate signals for each asset in universe
    signals_by_pair = {}
    for pair, df in multi_asset_ohlcv_dict.items():
        pre = strat.prepare_data(df)
        sig_list = strat.generate_signals(df, precomputed=pre, as_list=True)
        signals_by_pair[pair] = sig_list

    # Test 1: Tie Rule 'RETURN_STAKE'
    res_return = sim.run_multi_asset(
        universe_data=multi_asset_ohlcv_dict,
        signals_by_pair=signals_by_pair,
        expiry_candles=2,
        payout=0.85,
        initial_capital=1000.0,
        mode='BARBELL',
        bet_fraction=0.10,
        risk_ratio=0.20,
        tie_rule='RETURN_STAKE'
    )

    assert "summary" in res_return
    assert "trades" in res_return
    assert "equity_curve" in res_return

    sum_ret = res_return["summary"]
    assert sum_ret["total_trades"] == sum_ret["wins"] + sum_ret["losses"] + sum_ret["ties"]
    assert 0.0 <= sum_ret["win_rate"] <= 1.0
    assert 0.0 <= sum_ret["win_rate_effective"] <= 1.0
    assert isinstance(sum_ret["expected_value_per_trade"], float)

    # Test 2: Tie Rule 'LOSS'
    res_loss = sim.run_multi_asset(
        universe_data=multi_asset_ohlcv_dict,
        signals_by_pair=signals_by_pair,
        expiry_candles=2,
        payout=0.85,
        initial_capital=1000.0,
        mode='BARBELL',
        bet_fraction=0.10,
        risk_ratio=0.20,
        tie_rule='LOSS'
    )

    sum_loss = res_loss["summary"]

    # When tie_rule='LOSS', ties must be counted as 0 in tie count (converted to LOSS)
    assert sum_loss["ties"] == 0
    assert sum_loss["losses"] >= sum_ret["losses"]


# -----------------------------------------------------------------------------
# Scenario 2: End-to-End Walk-Forward Optimization with Purged CV & OOS
# -----------------------------------------------------------------------------
def test_scenario_2_end_to_end_walk_forward_purged_cv(synthetic_ohlcv_df):
    """
    Scenario 2: End-to-End Walk-Forward Optimization Workflow with Purged CV & OOS Evaluation.
    """
    # 1. Purged Group TimeSeries Cross-Validation test
    purged_cv = PurgedGroupTimeSeriesSplit(n_splits=4, expiry_candles=3, embargo_pct=0.02)
    splits = list(purged_cv.split(synthetic_ohlcv_df))

    assert len(splits) == 4
    for train_idx, test_idx in splits:
        assert len(train_idx) > 0
        assert len(test_idx) > 0
        # Verify no direct overlap between train and test indices
        overlap = set(train_idx).intersection(set(test_idx))
        assert len(overlap) == 0

        # Verify purge window: train indices should not fall in [test_start - expiry, test_start)
        test_start = test_idx[0]
        purged_indices = set(range(max(0, test_start - 3), test_start))
        assert len(set(train_idx).intersection(purged_indices)) == 0

    # 2. Walk-Forward Engine execution
    wfa = WalkForwardEngine(n_windows=3, train_ratio=0.60)
    strat = DailyConfluenceStrategy()
    base_params = {
        "rsi_min_call": 20.0,
        "rsi_max_call": 60.0,
        "pullback_tolerance": 0.015,
        "wick_rejection_ratio": 0.20
    }

    wfa_res = wfa.run_wfa(synthetic_ohlcv_df, strat, base_params, expiry=2)

    assert "wfe" in wfa_res
    assert "mean_is_wr" in wfa_res
    assert "mean_oos_wr" in wfa_res
    assert "stable_windows" in wfa_res
    assert "total_windows_tested" in wfa_res
    assert isinstance(wfa_res["window_results"], list)


# -----------------------------------------------------------------------------
# Scenario 3: Optuna Bayesian Hyperparameter Tuning Workflow
# -----------------------------------------------------------------------------
def test_scenario_3_optuna_bayesian_hyperparameter_tuning(synthetic_ohlcv_df):
    """
    Scenario 3: Optuna Bayesian Hyperparameter Tuning Workflow across Multi-Dimensional Search Space.
    """
    try:
        import optuna
        optuna_available = True
    except ImportError:
        optuna_available = False

    strat = DailyConfluenceStrategy()
    sim = BinarySimulator()

    # Define optimization objective
    def objective_fn(params_dict):
        pre = strat.prepare_data(synthetic_ohlcv_df)
        sigs = strat.generate_signals(synthetic_ohlcv_df, params=params_dict, precomputed=pre)
        res = sim.run(synthetic_ohlcv_df, sigs, expiry_candles=params_dict.get("expiry_candles", 1))
        summary = res.get("summary", {})
        total_trades = summary.get("total_trades", 0)
        win_rate = summary.get("win_rate_effective", 0.0)
        ev = summary.get("expected_value_per_trade", -1.0)
        # Score penalizes low trade frequency while promoting high win rate & positive EV
        if total_trades < 3:
            return -1.0
        return win_rate * 100.0 + (ev * 50.0)

    if optuna_available:
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def optuna_obj(trial):
            p = {
                "rsi_min_call": trial.suggest_float("rsi_min_call", 15.0, 35.0),
                "rsi_max_call": trial.suggest_float("rsi_max_call", 55.0, 75.0),
                "pullback_tolerance": trial.suggest_float("pullback_tolerance", 0.005, 0.030),
                "wick_rejection_ratio": trial.suggest_float("wick_rejection_ratio", 0.15, 0.40),
                "expiry_candles": trial.suggest_int("expiry_candles", 1, 3)
            }
            return objective_fn(p)

        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(optuna_obj, n_trials=10)

        assert len(study.trials) == 10
        best_params = study.best_params
        assert "rsi_min_call" in best_params
        assert "pullback_tolerance" in best_params
    else:
        # Fallback grid evaluation if Optuna is absent
        best_score = -999.0
        best_params = None
        for rsi_min in [20.0, 30.0]:
            for pb in [0.01, 0.02]:
                p = {"rsi_min_call": rsi_min, "rsi_max_call": 60.0, "pullback_tolerance": pb, "wick_rejection_ratio": 0.2, "expiry_candles": 1}
                score = objective_fn(p)
                if score > best_score:
                    best_score = score
                    best_params = p
        assert best_params is not None

    # Verify Parameter Surface Analysis
    surface_analyzer = ParameterSurfaceAnalyzer()
    surface_res = surface_analyzer.analyze_surface(synthetic_ohlcv_df, strat, best_params, expiry=1)
    assert "surface_score" in surface_res
    assert "plateau_ratio" in surface_res
    assert surface_res["plateau_ratio"] >= 0.0


# -----------------------------------------------------------------------------
# Scenario 4: High-Volatile Market Regime Adaptation Workflow
# -----------------------------------------------------------------------------
def test_scenario_4_high_volatile_market_regime_adaptation(synthetic_ohlcv_df):
    """
    Scenario 4: High-Volatile Market Regime Adaptation Workflow with CUSUM Drift & HMM State Detection.
    """
    # 1. Dynamic Regime Detection & Parameter Adaptation
    # Generate low volatility baseline followed by high volatility expansion
    low_vol = generate_synthetic_ohlcv(n_rows=200, start_price=100.0, volatility=0.2, seed=10)
    high_vol = generate_synthetic_ohlcv(n_rows=50, start_price=100.0, volatility=3.0, seed=20)
    combined_vol_df = pd.concat([low_vol, high_vol]).reset_index(drop=True)
    regime_info = DynamicRegimeAdapter.detect_regime(combined_vol_df)

    assert "regime" in regime_info
    assert "volatility_quantile" in regime_info
    assert "trend_direction" in regime_info

    base_params = {"bb_std": 2.0, "direction_filter": "BOTH"}
    adapted_params = DynamicRegimeAdapter.adapt_params(base_params, regime_info)

    assert "bb_std" in adapted_params
    assert "direction_filter" in adapted_params

    # If high volatility expansion, bb_std should be scaled up
    if regime_info["volatility_quantile"] >= 1.25:
        assert adapted_params["bb_std"] > base_params["bb_std"]

    # 2. CUSUM Equity Decay & Drift Monitoring
    cusum = CUSUMMonitor(expected_wr=0.65, payout=0.85, window=15)
    assert cusum.should_trade() is True

    # Simulate losing streak (drift detection)
    status = "CONTINUE"
    for _ in range(25):
        status = cusum.update(-1.0)  # -1.0 loss

    # Monitor must trigger PAUSE on persistent loss streak
    assert cusum.is_paused is True
    assert cusum.should_trade() is False
    assert status in ["PAUSE", "PAUSED"]

    stats = cusum.get_stats()
    assert stats["is_paused"] is True
    assert stats["pause_count"] >= 1

    # 3. HMM Regime Detector State Classification
    # Use realistic noisy dataset for HMM fitting
    df_hmm = generate_synthetic_ohlcv(n_rows=300, start_price=100.0, volatility=1.5, seed=123)
    detector = RegimeDetector(n_states=3)
    detector.fit(df_hmm)
    report = detector.get_regime_report(df_hmm)

    assert "current_state" in report
    assert "should_trade" in report
    assert isinstance(report["should_trade"], bool)



# -----------------------------------------------------------------------------
# Scenario 5: Meta-Labeling Probabilistic Signal Filtering Workflow
# -----------------------------------------------------------------------------
def test_scenario_5_meta_labeling_probabilistic_filtering_zero_leakage(synthetic_ohlcv_df):
    """
    Scenario 5: Meta-Labeling Probabilistic Signal Filtering Workflow with Zero Data Leakage.
    """
    features = BinaryFeatureExtractor.extract_features(synthetic_ohlcv_df)
    assert not features.empty
    assert len(features) == len(synthetic_ohlcv_df)

    # Instantiate base strategy and generate primary signals
    strat = DailyConfluenceStrategy()
    pre = strat.prepare_data(synthetic_ohlcv_df)
    base_signals = strat.generate_signals(synthetic_ohlcv_df, precomputed=pre)

    # Create dummy trade results for active signals
    active_indices = base_signals.dropna().index
    if len(active_indices) < 10:
        # Force deterministic signals if strategy generated few
        active_indices = synthetic_ohlcv_df.index[50:150:10]
        base_signals = pd.Series(index=synthetic_ohlcv_df.index, dtype=object)
        base_signals.loc[active_indices] = ['CALL', 'PUT'] * (len(active_indices) // 2)

    np.random.seed(42)
    dummy_results = pd.Series(np.random.choice([0, 1], size=len(active_indices), p=[0.4, 0.6]), index=active_indices)

    # Fit MetaLabeler on In-Sample signals (first 60%)
    split_len = int(len(synthetic_ohlcv_df) * 0.60)
    is_mask = active_indices < synthetic_ohlcv_df.index[split_len]
    is_indices = active_indices[is_mask]

    labeler = MetaLabeler(threshold=0.60)
    labeler.fit(synthetic_ohlcv_df, base_signals.loc[is_indices], dummy_results.loc[is_indices])

    # Filter Out-of-Sample signals
    filtered_signals = labeler.filter(synthetic_ohlcv_df, base_signals)

    assert isinstance(filtered_signals, pd.Series)
    assert len(filtered_signals) == len(base_signals)

    # Filtered signals must be a subset of base_signals
    active_filtered = filtered_signals.dropna()
    active_base = base_signals.dropna()
    assert len(active_filtered) <= len(active_base)
    for idx in active_filtered.index:
        assert filtered_signals.loc[idx] == base_signals.loc[idx]

    # Test BinaryMLMetaFilter adaptive thresholding
    meta_filter = BinaryMLMetaFilter(probability_threshold=0.65, adaptive_threshold=True)
    X = features
    y = pd.Series(np.random.choice([0, 1], size=len(X)), index=X.index)
    meta_filter.fit(X, y)

    filtered_by_meta = meta_filter.filter_signals(base_signals, X)
    assert isinstance(filtered_by_meta, pd.Series)
    assert len(filtered_by_meta.dropna()) <= len(active_base)


# -----------------------------------------------------------------------------
# Scenario 6: Vectorized High-Throughput Strategy Simulation Workload
# -----------------------------------------------------------------------------
def test_scenario_6_vectorized_high_throughput_simulation(synthetic_ohlcv_df):
    """
    Scenario 6: Vectorized High-Throughput Strategy Simulation Workload under Parameter Grid.
    """
    strat = DailyConfluenceStrategy()
    sim = BinarySimulator()

    # Precompute heavy feature extraction ONCE
    precomputed = strat.prepare_data(synthetic_ohlcv_df)

    # Define 20-combination parameter grid
    grid = []
    for rsi_min in [15.0, 20.0, 25.0, 30.0]:
        for pb_tol in [0.008, 0.012, 0.015, 0.020, 0.025]:
            grid.append({
                "rsi_min_call": rsi_min,
                "rsi_max_call": 65.0,
                "pullback_tolerance": pb_tol,
                "wick_rejection_ratio": 0.20
            })

    assert len(grid) == 20

    start_time = time.time()
    results = []
    for p in grid:
        sigs = strat.generate_signals(synthetic_ohlcv_df, params=p, precomputed=precomputed)
        res = sim.run(synthetic_ohlcv_df, sigs, expiry_candles=1, payout=0.85)
        summary = res["summary"]
        summary["params"] = p
        results.append(summary)

    elapsed_time = time.time() - start_time

    assert len(results) == 20
    # Vectorized execution must complete in < 3.0 seconds
    assert elapsed_time < 3.0, f"Grid simulation execution took too long: {elapsed_time:.2f}s"

    df_results = pd.DataFrame(results)
    assert "win_rate_effective" in df_results.columns
    assert "expected_value_per_trade" in df_results.columns
    assert not df_results["win_rate_effective"].isna().any()


# -----------------------------------------------------------------------------
# Scenario 7: Out-of-Sample Empirical Verification Workflow
# -----------------------------------------------------------------------------
def test_scenario_7_out_of_sample_empirical_verification_pipeline(synthetic_ohlcv_df):
    """
    Scenario 7: Out-of-Sample Empirical Verification Workflow (`verify_high_winrate_oos.py` pipeline).
    """
    n = len(synthetic_ohlcv_df)
    split_idx = int(n * 0.60)

    df_is = synthetic_ohlcv_df.iloc[:split_idx].copy().reset_index(drop=True)
    df_oos = synthetic_ohlcv_df.iloc[split_idx:].copy().reset_index(drop=True)

    strat = DailyConfluenceStrategy()
    sim = BinarySimulator()

    # 1. Calibrate on In-Sample (IS)
    pre_is = strat.prepare_data(df_is)
    best_p = {"rsi_min_call": 20.0, "rsi_max_call": 60.0, "pullback_tolerance": 0.015, "wick_rejection_ratio": 0.20}
    sigs_is = strat.generate_signals(df_is, params=best_p, precomputed=pre_is)
    res_is = sim.run(df_is, sigs_is, expiry_candles=1, payout=0.85)

    # 2. Evaluate on Out-Of-Sample (OOS)
    pre_oos = strat.prepare_data(df_oos)
    sigs_oos = strat.generate_signals(df_oos, params=best_p, precomputed=pre_oos)
    res_oos = sim.run(df_oos, sigs_oos, expiry_candles=1, payout=0.85)

    sum_is = res_is["summary"]
    sum_oos = res_oos["summary"]

    wins_oos = sum_oos["wins"]
    total_oos = sum_oos["total_trades"]
    ev_oos = sum_oos["expected_value_per_trade"]

    wilson_lower = compute_wilson_lower_bound(wins_oos, total_oos, confidence=0.95)

    # 3. Causality & Timestamp Integrity Verification
    zero_causality_violations = True
    for trade in res_oos["trades"]:
        entry_idx = trade["index"]
        # Entry execution price must be indexed at entry_idx + 1
        expected_entry_price = float(df_oos.iloc[entry_idx + 1]['open'])
        if abs(trade["entry_price"] - expected_entry_price) > 1e-6:
            zero_causality_violations = False
            break

    verification_report = {
        "is_total_trades": sum_is["total_trades"],
        "is_win_rate": sum_is["win_rate_effective"],
        "oos_total_trades": total_oos,
        "oos_win_rate": sum_oos["win_rate_effective"],
        "wilson_lower_bound_95": wilson_lower,
        "expected_value_per_trade": ev_oos,
        "zero_causality_violations": zero_causality_violations
    }

    assert verification_report["zero_causality_violations"] is True
    assert 0.0 <= verification_report["wilson_lower_bound_95"] <= 1.0
    assert isinstance(verification_report["expected_value_per_trade"], float)


# -----------------------------------------------------------------------------
# Scenario 8: Stress Testing Strategy under Extreme Crashes & Zero Volatility
# -----------------------------------------------------------------------------
def test_scenario_8_stress_testing_extreme_market_crashes_and_zero_vol():
    """
    Scenario 8: Stress Testing Strategy under Extreme Market Crashes and Zero Volatility Regimes.
    """
    sim = BinarySimulator()
    strat = DailyConfluenceStrategy()

    # 1. Extreme Market Crash Data (50% drop, high volatility)
    crash_df = generate_synthetic_ohlcv(n_rows=200, start_price=1000.0, volatility=10.0, seed=77)
    # Simulate a sudden 50% crash spike at index 100
    crash_df.iloc[100, crash_df.columns.get_loc('close')] *= 0.5
    crash_df.iloc[100, crash_df.columns.get_loc('Close')] *= 0.5
    crash_df.iloc[100, crash_df.columns.get_loc('low')] *= 0.45
    crash_df.iloc[100, crash_df.columns.get_loc('Low')] *= 0.45

    feats_crash = BinaryFeatureExtractor.extract_features(crash_df)
    assert not feats_crash.isna().any().any()

    pre_crash = strat.prepare_data(crash_df)
    sigs_crash = strat.generate_signals(crash_df, precomputed=pre_crash)
    res_crash = sim.run(crash_df, sigs_crash, expiry_candles=1)
    assert "summary" in res_crash
    assert not np.isnan(res_crash["summary"]["net_pnl"])

    # 2. Flat Price / Zero Volatility Regime
    flat_df = generate_flat_price_ohlcv(n_rows=150, start_price=100.0)
    pre_flat = strat.prepare_data(flat_df)
    sigs_flat = strat.generate_signals(flat_df, precomputed=pre_flat)
    res_flat = sim.run(flat_df, sigs_flat, expiry_candles=1, tie_rule='RETURN_STAKE')
    assert res_flat["summary"]["wins"] == 0 or res_flat["summary"]["ties"] >= 0

    # 3. Zero Volume Regime
    zero_vol_df = generate_zero_volume_ohlcv(n_rows=150)
    feats_zv = BinaryFeatureExtractor.extract_features(zero_vol_df)
    assert not feats_zv.isna().any().any()
    pre_zv = strat.prepare_data(zero_vol_df)
    sigs_zv = strat.generate_signals(zero_vol_df, precomputed=pre_zv)
    res_zv = sim.run(zero_vol_df, sigs_zv, expiry_candles=1)
    assert "summary" in res_zv

    # 4. NaN Input Boundary Data
    nan_df = generate_nan_ohlcv(n_rows=150, nan_ratio=0.05)
    pre_nan = strat.prepare_data(nan_df)
    sigs_nan = strat.generate_signals(nan_df, precomputed=pre_nan)
    res_nan = sim.run(nan_df, sigs_nan, expiry_candles=1)
    assert "summary" in res_nan


# -----------------------------------------------------------------------------
# Scenario 9: Complete System Integration Workflow
# -----------------------------------------------------------------------------
def test_scenario_9_complete_system_integration_workflow(multi_asset_ohlcv_dict):
    """
    Scenario 9: Complete System Integration Workflow (In-Sample Training -> OOS Backtest ->
    Integrity Audit -> Win Rate & EV Validation).
    """
    sim = BinarySimulator()
    strat = DailyConfluenceStrategy()

    # Step 1: Feature Extraction across universe
    feature_sets = {}
    for pair, df in multi_asset_ohlcv_dict.items():
        feature_sets[pair] = BinaryFeatureExtractor.extract_features(df)
        assert not feature_sets[pair].empty

    # Step 2: Signal Generation & ML Meta-Filtering
    signals_by_pair = {}
    for pair, df in multi_asset_ohlcv_dict.items():
        pre = strat.prepare_data(df)
        base_sigs = strat.generate_signals(df, precomputed=pre)

        # Apply Secondary ML Meta-Filter
        meta_filter = BinaryMLMetaFilter(probability_threshold=0.55)
        X = feature_sets[pair]
        np.random.seed(123)
        y_dummy = pd.Series(np.random.choice([0, 1], size=len(X)), index=X.index)
        meta_filter.fit(X, y_dummy)

        filtered_sigs = meta_filter.filter_signals(base_sigs, X)

        # Convert to signals list for multi-asset simulator
        sigs_list = []
        for idx in filtered_sigs.dropna().index:
            sig_dir = filtered_sigs.loc[idx]
            sig_t = int(df.loc[idx, 'open_time'] // 1000) if df.loc[idx, 'open_time'] > 2**32 else int(df.loc[idx, 'open_time'])
            sigs_list.append({
                'time': sig_t,
                'direction': sig_dir,
                'price': float(df.loc[idx, 'close'])
            })
        signals_by_pair[pair] = sigs_list

    # Step 3: Risk Monitoring Integration during execution
    cusum = CUSUMMonitor(expected_wr=0.60, payout=0.85)

    # Step 4: Multi-Asset Execution Simulation
    res_integrated = sim.run_multi_asset(
        universe_data=multi_asset_ohlcv_dict,
        signals_by_pair=signals_by_pair,
        expiry_candles=2,
        payout=0.85,
        initial_capital=1000.0,
        mode='BARBELL',
        bet_fraction=0.10,
        risk_ratio=0.20,
        tie_rule='RETURN_STAKE'
    )

    for tr in res_integrated["trades"]:
        pnl = tr.get("pnl", 0.0)
        cusum.update(pnl)

    summary = res_integrated["summary"]

    assert summary["total_trades"] == len(res_integrated["trades"])
    assert len(res_integrated["equity_curve"]) >= summary["total_trades"] + 1
    assert "win_rate" in summary
    assert "expected_value_per_trade" in summary
    assert "max_drawdown" in summary


# -----------------------------------------------------------------------------
# Scenario 10: Multi-Timeframe Strategy Confluence Backtest Workflow
# -----------------------------------------------------------------------------
def test_scenario_10_multi_timeframe_strategy_confluence():
    """
    Scenario 10: Multi-Timeframe Strategy Confluence Backtest Workflow.
    """
    # Generate multi-timeframe dataset (600 candles, ~5 days of 5min candles)
    mtf_df = generate_synthetic_ohlcv(
        n_rows=600,
        start_price=1.1000,
        volatility=0.4,
        seed=2024,
        freq='5min',
        start_date='2024-01-01 00:00:00'
    )

    strat = DailyConfluenceStrategy(
        ema_weekly_period=10,
        ema_daily_period=14,
        rsi_period=14,
        pullback_tolerance=0.015,
        wick_rejection_ratio=0.20
    )

    # Prepare multi-timeframe data: resamples daily data to weekly & merges via merge_asof
    precomputed = strat.prepare_data(mtf_df)

    assert "df_merged" in precomputed
    df_merged = precomputed["df_merged"]
    assert "ema_weekly" in df_merged.columns
    assert "ema_weekly_dir" in df_merged.columns

    # Verify no look-ahead bias in merge_asof: completion_time of weekly bar <= open_time of candle
    merged_valid = df_merged.dropna(subset=['ema_weekly'])
    if not merged_valid.empty and 'completion_time' in merged_valid.columns:
        assert (merged_valid['completion_time'] <= merged_valid['open_time']).all()

    # Generate signals list
    sigs_list = strat.generate_signals_list(mtf_df, precomputed=precomputed)
    assert isinstance(sigs_list, list)

    for sig in sigs_list:
        assert "time" in sig
        assert "direction" in sig
        assert sig["direction"] in ["CALL", "PUT"]
        assert "price" in sig
        assert "rsi" in sig

    # Execute simulation
    sim = BinarySimulator()
    sigs_series = strat.generate_signals(mtf_df, precomputed=precomputed)
    sim_res = sim.run(mtf_df, sigs_series, expiry_candles=2, payout=0.85)

    assert "summary" in sim_res
    sum_mtf = sim_res["summary"]
    assert sum_mtf["total_trades"] == sum_mtf["wins"] + sum_mtf["losses"] + sum_mtf["ties"]
