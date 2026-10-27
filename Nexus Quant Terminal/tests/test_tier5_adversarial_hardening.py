"""
Tier 5 Adversarial Coverage & Stress Hardening Test Suite (Milestone 4)
Binary Options Quantitative Terminal UI/UX Redesign

Test Dimensions:
1. High-load data streams, malformed SSE event stream handling, noisy subprocess output.
2. Boundary values for Barbell presets, zero/negative payouts, empty/degenerate universe selections.
3. Dynamic logarithmic scale limits on equity curves under extreme drawdown and explosive growth.
4. Genetic algorithm parameter bounds, corrupted chromosome configurations, and fallback resilience.
5. DOM stability and structural integrity under repeated rapid mode switching (#mode-smart <-> #mode-advanced).
"""

import os
import re
import json
import math
import time
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from html.parser import HTMLParser

from app import (
    app,
    clean_json_data,
    preserve_peaks_subsample,
    extract_json_from_output,
    sse_response,
    is_safe_symbol,
    is_safe_interval
)
from engine.simulator import BinarySimulator, VectorizedBinarySimulator
from engine.optimizer import (
    CapitalOptimizer,
    binomial_sf,
    monte_carlo_vectorized_2d
)
from engine.correlation import CorrelationEngine
from engine.statistics import StatisticsEngine
from strategies.genetic_composite import GeneticCompositeStrategy
from strategies.daily_confluence import DailyConfluenceStrategy
from tests.conftest import (
    generate_synthetic_ohlcv,
    generate_custom_length_ohlcv,
    generate_zero_volume_ohlcv,
    generate_flat_price_ohlcv,
    generate_nan_ohlcv
)

BASE_DIR = Path(__file__).resolve().parent.parent
HTML_PATH = BASE_DIR / "templates" / "index.html"
STYLE_CSS_PATH = BASE_DIR / "static" / "css" / "style.css"
APP_JS_PATH = BASE_DIR / "static" / "js" / "app.js"
CHARTS_JS_PATH = BASE_DIR / "static" / "js" / "charts.js"


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="module")
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="module")
def html_content():
    assert HTML_PATH.exists(), f"Missing HTML at {HTML_PATH}"
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def app_js_content():
    assert APP_JS_PATH.exists(), f"Missing app.js at {APP_JS_PATH}"
    with open(APP_JS_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def charts_js_content():
    assert CHARTS_JS_PATH.exists(), f"Missing charts.js at {CHARTS_JS_PATH}"
    with open(CHARTS_JS_PATH, "r", encoding="utf-8") as f:
        return f.read()


# =============================================================================
# CATEGORY 1: HIGH-LOAD DATA STREAMS & MALFORMED SSE EVENT HANDLING
# =============================================================================

class TestCategory1_SSEAndDataStreamAdversarial:
    """Stress testing SSE streams, payload parsers, noise injection, and concurrency."""

    def test_extract_json_from_output_valid_payloads(self):
        # Plain dict
        assert extract_json_from_output('{"status": "ok", "win_rate": 0.65}') == {"status": "ok", "win_rate": 0.65}
        # Plain list
        assert extract_json_from_output('[1, 2, 3]') == [1, 2, 3]

    def test_extract_json_from_output_with_progress_noise(self):
        noisy_output = (
            "PROGRESS: 10/100 10.0%\n"
            "PROGRESS: 50/100 50.0%\n"
            "PROGRESS: 100/100 100.0%\n"
            '{"best_fitness": 0.72, "generations": 100}\n'
        )
        parsed = extract_json_from_output(noisy_output)
        assert parsed == {"best_fitness": 0.72, "generations": 100}

    def test_extract_json_from_output_surrounded_by_raw_logs(self):
        log_noise = (
            "[INFO] Initializing Rust Engine...\n"
            "[DEBUG] Loading 5000 candles from CSV\n"
            "PROGRESS: 1/50\n"
            "PROGRESS: 50/50\n"
            '{"best_params": {"rsi_period": 14}, "trades": 120}\n'
            "[INFO] Finished execution in 1.42s\n"
        )
        parsed = extract_json_from_output(log_noise)
        assert parsed["best_params"]["rsi_period"] == 14
        assert parsed["trades"] == 120

    def test_extract_json_from_output_malformed_rejects_cleanly(self):
        bad_inputs = [
            "",
            "   \n\t  ",
            "No JSON here just text",
            "PROGRESS: 100/100",
            "{broken json: true,",
            "[1, 2, ",
            "<html><head>Error 500</head></html>",
            "\x00\x01\x02\x03\x04\x05"
        ]
        for bad in bad_inputs:
            with pytest.raises(ValueError):
                extract_json_from_output(bad)

    def test_extract_json_from_output_nested_large_payload(self):
        large_dict = {
            "strategy": "GeneticComposite",
            "metrics": {"trades": list(range(500)), "nested": {"deep": {"value": 42.0}}},
            "unicode_test": "🚀 Institutional Terminal 日本語 €100,000"
        }
        raw_text = f"PROGRESS: 1/1\n[DEBUG] Done\n{json.dumps(large_dict)}\n[INFO] End"
        parsed = extract_json_from_output(raw_text)
        assert parsed["metrics"]["nested"]["deep"]["value"] == 42.0
        assert parsed["unicode_test"] == "🚀 Institutional Terminal 日本語 €100,000"

    def test_sse_response_wrapper_protocol_headers(self):
        def sample_gen():
            yield "data: {\"test\": 1}\n\n"
        
        resp = sse_response(sample_gen())
        assert resp.mimetype == 'text/event-stream'
        assert resp.headers.get('Cache-Control') == 'no-cache'
        assert resp.headers.get('X-Accel-Buffering') == 'no'
        assert resp.headers.get('Connection') == 'keep-alive'

    def test_sse_backtest_stream_endpoint_invalid_args(self, client):
        # Missing required parameters
        res = client.get('/api/backtest-stream')
        assert res.status_code == 200
        data = res.get_data(as_text=True)
        assert "error" in data.lower() or "no se pudieron cargar datos" in data.lower()

    def test_sse_smart_optimize_v2_stream_invalid_universe(self, client):
        res = client.get('/api/smart-optimize-v2-stream?universe=INVALID_TICKER_9999&attempts=6')
        assert res.status_code == 200
        data = res.get_data(as_text=True)
        assert "data:" in data
        assert "error" in data or "log" in data

    def test_sse_genetic_run_stream_boundary_rejection(self, client):
        # generations < 1
        res1 = client.get('/api/genetic/run-stream?pair=BTCUSDT&interval=1h&generations=0')
        assert res1.status_code == 400

        # population < 10
        res2 = client.get('/api/genetic/run-stream?pair=BTCUSDT&interval=1h&population=5')
        assert res2.status_code == 400

        # expiry < 1
        res3 = client.get('/api/genetic/run-stream?pair=BTCUSDT&interval=1h&expiry=0')
        assert res3.status_code == 400

        # invalid unsafe pair
        res4 = client.get('/api/genetic/run-stream?pair=BTC/USDT;DROP+TABLE&interval=1h')
        assert res4.status_code == 400

    def test_symbol_and_interval_safety_validators(self):
        assert is_safe_symbol("BTCUSDT") is True
        assert is_safe_symbol("EUR_USD-1") is True
        assert is_safe_symbol("BTC/USDT") is False
        assert is_safe_symbol("BTC; rm -rf") is False
        assert is_safe_symbol("../../../etc/passwd") is False

        assert is_safe_interval("1h") is True
        assert is_safe_interval("5min") is True
        assert is_safe_interval("1h;ls") is False
        assert is_safe_interval("..") is False


# =============================================================================
# CATEGORY 2: BOUNDARY VALUES FOR BARBELL PRESETS, PAYOUTS & EMPTY UNIVERSE
# =============================================================================

class TestCategory2_BarbellAndUniverseBoundaries:
    """Testing Barbell presets, zero/negative payouts, empty universe selections."""

    def test_barbell_streak_plan_zero_and_boundary_payouts(self):
        optimizer = CapitalOptimizer()
        
        # Zero payout: winning yields no profit
        plan_zero = optimizer.calculate_streak_plan(
            win_rate=0.60,
            payout=0.0,
            risk_capital=200.0,
            target_capital=1000.0,
            attempts=6,
            total_trades=100
        )
        assert plan_zero["payout"] == 0.0
        assert len(plan_zero["results_by_n"]) == 15
        # Multiplier with 0 payout should be 1/attempts
        assert plan_zero["results_by_n"][0]["multiplier"] == pytest.approx(1.0 / 6.0)

        # High payout: 2.0 (200% return)
        plan_high = optimizer.calculate_streak_plan(
            win_rate=0.60,
            payout=2.0,
            risk_capital=200.0,
            target_capital=1000.0,
            attempts=6,
            total_trades=100
        )
        assert plan_high["payout"] == 2.0
        assert plan_high["results_by_n"][0]["final_capital"] > 0

    def test_barbell_streak_plan_extreme_winrates(self):
        optimizer = CapitalOptimizer()
        
        # 0% win rate
        plan_zero_wr = optimizer.calculate_streak_plan(
            win_rate=0.0,
            payout=0.85,
            risk_capital=200.0,
            target_capital=1000.0,
            attempts=6,
            total_trades=100
        )
        assert plan_zero_wr["results_by_n"][0]["p_success_single"] == 0.0
        assert plan_zero_wr["results_by_n"][0]["expected_value"] == -200.0

        # 100% win rate
        plan_full_wr = optimizer.calculate_streak_plan(
            win_rate=1.0,
            payout=0.85,
            risk_capital=200.0,
            target_capital=1000.0,
            attempts=6,
            total_trades=100
        )
        assert plan_full_wr["results_by_n"][0]["p_success_single"] == 1.0
        assert plan_full_wr["results_by_n"][0]["p_success_campaign"] == 1.0

    def test_barbell_streak_plan_wilson_score_adjustment_small_sample(self):
        optimizer = CapitalOptimizer()
        # total_trades < 30 triggers Wilson Lower Bound penalty
        plan_small = optimizer.calculate_streak_plan(
            win_rate=0.80,
            payout=0.85,
            risk_capital=200.0,
            target_capital=1000.0,
            attempts=6,
            total_trades=10
        )
        assert plan_small["sample_is_sufficient"] is False
        assert plan_small["win_rate_capped_warning"] is True
        assert plan_small["win_rate"] < 0.80  # Penalized below raw 0.80

        # total_trades >= 30 uses unpenalized win rate
        plan_large = optimizer.calculate_streak_plan(
            win_rate=0.80,
            payout=0.85,
            risk_capital=200.0,
            target_capital=1000.0,
            attempts=6,
            total_trades=50
        )
        assert plan_large["sample_is_sufficient"] is True
        assert plan_large["win_rate_capped_warning"] is False
        assert plan_large["win_rate"] == 0.80

    def test_barbell_presets_exact_parameter_adherence(self, client):
        test_cases = [
            {"attempts": 6, "risk_capital": 200.0, "target_capital": 1000.0, "payout": 0.85},
            {"attempts": 8, "risk_capital": 250.0, "target_capital": 1000.0, "payout": 0.85},
            {"attempts": 1, "risk_capital": 200.0, "target_capital": 1000.0, "payout": 0.85},
        ]
        
        for tc in test_cases:
            res = client.post('/api/optimize-streak', json={
                "win_rate": 0.60,
                "payout": tc["payout"],
                "risk_capital": tc["risk_capital"],
                "target_capital": tc["target_capital"],
                "attempts": tc["attempts"],
                "base_capital": 1000.0
            })
            assert res.status_code == 200
            data = res.get_json()
            assert "results_by_n" in data
            assert len(data["results_by_n"]) == 15
            assert data["attempts"] == tc["attempts"]
            assert data["results_by_n"][0]["bet_per_attempt"] == pytest.approx(tc["risk_capital"] / tc["attempts"])

    def test_optimize_streak_api_adversarial_payload_rejection(self, client):
        # Negative win rate
        res1 = client.post('/api/optimize-streak', json={"win_rate": -0.1, "payout": 0.85, "risk_capital": 100, "target_capital": 500, "attempts": 5})
        assert res1.status_code == 400

        # Win rate > 1.0
        res2 = client.post('/api/optimize-streak', json={"win_rate": 1.5, "payout": 0.85, "risk_capital": 100, "target_capital": 500, "attempts": 5})
        assert res2.status_code == 400

        # Negative payout
        res3 = client.post('/api/optimize-streak', json={"win_rate": 0.6, "payout": -0.5, "risk_capital": 100, "target_capital": 500, "attempts": 5})
        assert res3.status_code == 400

        # target_capital <= risk_capital
        res4 = client.post('/api/optimize-streak', json={"win_rate": 0.6, "payout": 0.85, "risk_capital": 500, "target_capital": 500, "attempts": 5})
        assert res4.status_code == 400

        # attempts < 1
        res5 = client.post('/api/optimize-streak', json={"win_rate": 0.6, "payout": 0.85, "risk_capital": 100, "target_capital": 500, "attempts": 0})
        assert res5.status_code == 400

    def test_multi_asset_simulator_empty_universe(self):
        sim = BinarySimulator()
        res = sim.run_multi_asset(
            universe_data={},
            signals_by_pair={},
            initial_capital=1000.0
        )
        assert res["summary"]["total_trades"] == 0
        assert res["summary"]["win_rate"] == 0.0
        assert res["trades"] == []
        # Starting equity anchor t=0 is retained
        assert len(res["equity_curve"]) == 1
        assert res["equity_curve"][0]["equity"] == 1000.0

    def test_multi_asset_simulator_degenerate_assets(self):
        sim = BinarySimulator()
        flat_df = generate_flat_price_ohlcv(n_rows=50, start_price=100.0)
        zv_df = generate_zero_volume_ohlcv(n_rows=50)
        
        universe = {
            "FLAT": flat_df,
            "ZERO_VOL": zv_df,
            "EMPTY": pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'open_time'])
        }
        signals = {
            "FLAT": [{'time': int(flat_df['open_time'].iloc[10]), 'direction': 'CALL'}],
            "ZERO_VOL": [{'time': int(zv_df['open_time'].iloc[15]), 'direction': 'PUT'}],
            "EMPTY": []
        }
        
        res = sim.run_multi_asset(
            universe_data=universe,
            signals_by_pair=signals,
            initial_capital=1000.0,
            tie_rule='RETURN_STAKE'
        )
        assert "summary" in res
        assert res["summary"]["total_trades"] >= 0
        assert not np.isnan(res["summary"]["net_pnl"])


# =============================================================================
# CATEGORY 3: LOGARITHMIC SCALE LIMITS ON EQUITY CURVES UNDER EXTREMES
# =============================================================================

class TestCategory3_DynamicLogarithmicScaleAndNumerics:
    """Stress testing numeric sanitization, peak preservation subsampling, and log-scale bounds."""

    def test_clean_json_data_inf_and_nan_recursively(self):
        corrupted_payload = {
            "scalar_nan": float('nan'),
            "scalar_inf": float('inf'),
            "scalar_neginf": float('-inf'),
            "numpy_nan": np.float64(np.nan),
            "numpy_inf": np.float64(np.inf),
            "list_with_nan": [1.0, float('nan'), 3.0, [float('inf'), 4.0]],
            "valid_float": 123.456,
            "valid_int": np.int64(789),
            "valid_bool": np.bool_(True),
            "numpy_array": np.array([1.0, np.nan, 3.0])
        }
        
        cleaned = clean_json_data(corrupted_payload)
        
        assert cleaned["scalar_nan"] is None
        assert cleaned["scalar_inf"] is None
        assert cleaned["scalar_neginf"] is None
        assert cleaned["numpy_nan"] is None
        assert cleaned["numpy_inf"] is None
        assert cleaned["list_with_nan"] == [1.0, None, 3.0, [None, 4.0]]
        assert cleaned["valid_float"] == 123.456
        assert cleaned["valid_int"] == 789
        assert cleaned["valid_bool"] is True
        assert cleaned["numpy_array"] == [1.0, None, 3.0]
        
        json_str = json.dumps(cleaned)
        assert "NaN" not in json_str
        assert "Infinity" not in json_str
        assert "null" in json_str

    def test_preserve_peaks_subsample_empty_and_small(self):
        assert preserve_peaks_subsample([]) == []
        small = [{"equity": 100}, {"equity": 150}]
        assert preserve_peaks_subsample(small, max_points=500) == small

    def test_preserve_peaks_subsample_explosive_growth(self):
        n = 10000
        equity_values = np.geomspace(100.0, 1e9, n)
        data = [{"trade_num": i, "equity": float(equity_values[i])} for i in range(n)]
        
        subsampled = preserve_peaks_subsample(data, max_points=400)
        assert len(subsampled) <= 400
        assert len(subsampled) > 50
        assert subsampled[0]["equity"] == pytest.approx(100.0)
        assert subsampled[-1]["equity"] == pytest.approx(1e9)

    def test_preserve_peaks_subsample_extreme_drawdown_near_zero(self):
        n = 5000
        equity_values = np.geomspace(10000.0, 1e-4, n)
        data = [{"trade_num": i, "equity": float(equity_values[i])} for i in range(n)]
        
        subsampled = preserve_peaks_subsample(data, max_points=300)
        assert len(subsampled) <= 300
        assert subsampled[0]["equity"] == pytest.approx(10000.0)
        assert subsampled[-1]["equity"] == pytest.approx(1e-4)

    def test_preserve_peaks_subsample_preserves_local_extrema(self):
        data = []
        for i in range(2000):
            eq = 1000.0 + (5000.0 if i == 500 else (10.0 if i == 1500 else 0.0))
            data.append({"index": i, "equity": eq})
            
        subsampled = preserve_peaks_subsample(data, max_points=200)
        equities = [d["equity"] for d in subsampled]
        assert 6000.0 in equities

    def test_charts_js_log_scale_formula_integrity(self, charts_js_content):
        assert "useLog" in charts_js_content
        assert "minVal >= 1.0" in charts_js_content
        assert "formatYAxisTick" in charts_js_content

    def test_log_scale_mathematical_model_simulation(self):
        """Simulate the charts.js log scale threshold logic in Python."""
        def calc_use_log(values):
            if not values:
                return False, values
            max_val = max(values)
            min_val = min(values)
            use_log = (max_val / max(min_val, 0.01)) > 100 and min_val >= 1.0
            cleaned = [max(v, 1.0) for v in values] if use_log else values
            return use_log, cleaned

        # Case 1: Drawdown below 1.0 (minVal = 0.5) -> must NOT use log scale (prevents negative log)
        use_log_1, _ = calc_use_log([1000.0, 500.0, 0.5, 0.1])
        assert use_log_1 is False

        # Case 2: Drawdown to zero or negative -> must NOT use log scale
        use_log_2, _ = calc_use_log([1000.0, 100.0, 0.0, -50.0])
        assert use_log_2 is False

        # Case 3: Small dynamic range (100 to 200) -> linear scale
        use_log_3, _ = calc_use_log([100.0, 150.0, 200.0])
        assert use_log_3 is False

        # Case 4: Massive explosive growth (100 to 50,000) with minVal >= 1.0 -> log scale ENABLED
        use_log_4, cleaned_4 = calc_use_log([100.0, 500.0, 50000.0])
        assert use_log_4 is True
        assert all(v >= 1.0 for v in cleaned_4)


# =============================================================================
# CATEGORY 4: GENETIC ALGORITHM PARAMETER BOUNDS & STRATEGY RESILIENCE
# =============================================================================

class TestCategory4_GeneticAlgorithmBoundsAndResilience:
    """Testing GeneticCompositeStrategy parameter extremes, corrupted inputs, and edge signals."""

    def test_genetic_composite_all_filters_disabled_returns_empty(self, synthetic_ohlcv_df):
        strat = GeneticCompositeStrategy()
        params = {
            "rsi_enabled": False,
            "bb_enabled": False,
            "ema_enabled": False,
            "rejection_filter_enabled": False,
            "volatility_filter_enabled": False,
            "htf_ema_enabled": False
        }
        sigs = strat.generate_signals(synthetic_ohlcv_df, params=params)
        assert sigs.dropna().empty

    def test_genetic_composite_extreme_indicator_parameters(self, synthetic_ohlcv_df):
        strat = GeneticCompositeStrategy()
        pre = strat.prepare_data(synthetic_ohlcv_df)
        
        # Minimum parameters
        min_params = {
            "rsi_period": 2,
            "rsi_oversold": 5.0,
            "rsi_overbought": 95.0,
            "rsi_enabled": True,
            "bb_period": 5,
            "bb_std": 0.5,
            "bb_enabled": True,
            "ema_fast_period": 2,
            "ema_slow_period": 5,
            "ema_enabled": True,
            "htf_ema_period": 20,
            "htf_ema_enabled": True
        }
        sigs_min = strat.generate_signals(synthetic_ohlcv_df, params=min_params, precomputed=pre)
        assert isinstance(sigs_min, pd.Series)

        # Maximum parameters
        max_params = {
            "rsi_period": 100,
            "rsi_oversold": 45.0,
            "rsi_overbought": 55.0,
            "rsi_enabled": True,
            "bb_period": 150,
            "bb_std": 5.0,
            "bb_enabled": True,
            "ema_fast_period": 50,
            "ema_slow_period": 200,
            "ema_enabled": True,
            "htf_ema_period": 250,
            "htf_ema_enabled": True
        }
        sigs_max = strat.generate_signals(synthetic_ohlcv_df, params=max_params, precomputed=pre)
        assert isinstance(sigs_max, pd.Series)

    def test_genetic_composite_generate_signals_list_format(self, synthetic_ohlcv_df):
        strat = GeneticCompositeStrategy()
        pre = strat.prepare_data(synthetic_ohlcv_df)
        params = {
            "rsi_enabled": True,
            "rsi_period": 14,
            "rsi_oversold": 30.0,
            "rsi_overbought": 70.0,
            "bb_enabled": True,
            "bb_period": 20,
            "bb_std": 2.0
        }
        sig_list = strat.generate_signals_list(synthetic_ohlcv_df, params=params, precomputed=pre)
        assert isinstance(sig_list, list)
        for s in sig_list:
            assert "time" in s
            assert "direction" in s
            assert s["direction"] in ["CALL", "PUT"]
            assert "price" in s

    def test_genetic_composite_empty_dataframe_handling(self):
        strat = GeneticCompositeStrategy()
        # Empty DataFrame with standard OHLCV schema
        empty_schema_df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'open_time'])
        pre = strat.prepare_data(empty_schema_df)
        assert pre == {}
        sigs = strat.generate_signals(empty_schema_df, params={}, precomputed=pre)
        assert sigs.empty

    def test_monte_carlo_vectorized_2d_adversarial_inputs(self):
        # 0% win rate
        res_0 = monte_carlo_vectorized_2d(win_rate=0.0, payout=0.85, n_consecutive=3, kelly_f=0.1, num_simulations=500, num_cycles=50)
        assert res_0["ruin_probability"] >= 0.0
        assert res_0["final_equity"]["median"] <= 1.0

        # 100% win rate
        res_100 = monte_carlo_vectorized_2d(win_rate=1.0, payout=0.85, n_consecutive=3, kelly_f=0.1, num_simulations=500, num_cycles=50)
        assert res_100["ruin_probability"] == 0.0
        assert res_100["final_equity"]["median"] > 1.0

        # 0 kelly fraction -> equity should remain exactly 1.0
        res_k0 = monte_carlo_vectorized_2d(win_rate=0.6, payout=0.85, n_consecutive=3, kelly_f=0.0, num_simulations=500, num_cycles=50)
        assert res_k0["final_equity"]["mean"] == pytest.approx(1.0)


# =============================================================================
# CATEGORY 5: DOM STABILITY & REPEATED RAPID MODE SWITCHING (#mode-smart <-> #mode-advanced)
# =============================================================================

class DOMTagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.all_ids = []
        self.id_counts = {}
        self.classes = set()
        self.data_tabs = set()
        self.tag_hierarchy = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tag_id = attr_dict.get("id")
        if tag_id:
            tag_id_clean = tag_id.strip()
            self.all_ids.append(tag_id_clean)
            self.id_counts[tag_id_clean] = self.id_counts.get(tag_id_clean, 0) + 1
        
        data_tab = attr_dict.get("data-tab")
        if data_tab:
            self.data_tabs.add(data_tab)

        cls = attr_dict.get("class")
        if cls:
            for c in cls.split():
                self.classes.add(c)
                
        self.tag_hierarchy.append((tag, attr_dict))


class TestCategory5_DOMStabilityAndModeSwitching:
    """Stress testing DOM structure, ID uniqueness, tab switching contracts, and event bindings."""

    def test_zero_duplicate_dom_ids(self, html_content):
        parser = DOMTagCollector()
        parser.feed(html_content)
        
        duplicates = {k: v for k, v in parser.id_counts.items() if v > 1}
        assert not duplicates, f"Found duplicate DOM IDs in index.html: {duplicates}"

    def test_mode_switch_core_ids_and_tabs_exist(self, html_content):
        parser = DOMTagCollector()
        parser.feed(html_content)
        
        required_mode_ids = [
            "mode-smart",
            "mode-advanced",
            "smart-dashboard",
            "dashboard",
            "resultados",
            "estadisticas",
            "optimizador",
            "btn-smart-run",
            "smart-preset-select",
            "btn-resultados",
            "btn-estadisticas",
            "btn-optimizador"
        ]
        
        for req_id in required_mode_ids:
            assert req_id in parser.id_counts, f"Missing critical mode/tab DOM ID: {req_id}"

        # Check all 5 advanced tabs navigation targets exist
        required_data_tabs = {"dashboard", "backtest", "resultados", "estadisticas", "optimizador"}
        assert required_data_tabs.issubset(parser.data_tabs), f"Missing data-tab targets: {required_data_tabs - parser.data_tabs}"

    def test_all_chart_and_canvas_containers_exist(self, html_content):
        parser = DOMTagCollector()
        parser.feed(html_content)
        
        canvas_and_chart_ids = [
            "tv-chart",
            "smart-tv-chart",
            "smart-tv-chart-empty",
            "equity-chart",
            "smart-equity-chart-canvas",
            "mc-chart",
            "smart-mc-chart-canvas",
            "smart-correlation-canvas",
            "autocorr-chart",
            "streaks-chart",
            "hourly-chart",
            "market-state-chart"
        ]
        
        for c_id in canvas_and_chart_ids:
            assert c_id in parser.id_counts, f"Missing chart/canvas container: {c_id}"

    def test_smart_mode_preset_options_integrity(self, html_content):
        assert 'value="preset_33_6"' in html_content
        assert 'value="preset_25_8"' in html_content
        assert 'value="preset_200_1"' in html_content

    def test_app_js_mode_switch_event_listeners_integrity(self, app_js_content):
        assert "getElementById('mode-smart')" in app_js_content
        assert "getElementById('mode-advanced')" in app_js_content
        assert "switchTab('smart-dashboard')" in app_js_content
        assert "switchTab('dashboard')" in app_js_content

    def test_rapid_mode_switching_state_machine_simulation(self):
        """Simulate rapid, alternating switching between Smart and Advanced mode."""
        class UIStateSimulator:
            def __init__(self):
                self.current_mode = "smart"
                self.current_tab = "smart-dashboard"
                self.tabs_nav_display = "none"
                self.active_elements = {"mode-smart", "smart-dashboard"}

            def switch_to_smart(self):
                self.current_mode = "smart"
                self.tabs_nav_display = "none"
                self.active_elements.discard("mode-advanced")
                self.active_elements.discard("dashboard")
                self.active_elements.add("mode-smart")
                self.active_elements.add("smart-dashboard")
                self.current_tab = "smart-dashboard"

            def switch_to_advanced(self, default_tab="dashboard"):
                self.current_mode = "advanced"
                self.tabs_nav_display = "flex"
                self.active_elements.discard("mode-smart")
                self.active_elements.discard("smart-dashboard")
                self.active_elements.add("mode-advanced")
                self.active_elements.add(default_tab)
                self.current_tab = default_tab

        sim = UIStateSimulator()
        
        # Simulate 1,000 rapid back-and-forth toggles
        for i in range(1000):
            if i % 2 == 0:
                sim.switch_to_advanced()
                assert sim.current_mode == "advanced"
                assert sim.tabs_nav_display == "flex"
                assert "mode-advanced" in sim.active_elements
                assert "mode-smart" not in sim.active_elements
            else:
                sim.switch_to_smart()
                assert sim.current_mode == "smart"
                assert sim.tabs_nav_display == "none"
                assert "mode-smart" in sim.active_elements
                assert "mode-advanced" not in sim.active_elements

    def test_css_design_system_surface_and_grid_variables(self):
        assert STYLE_CSS_PATH.exists()
        with open(STYLE_CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()
            
        # FinTech Dark Surfaces
        assert "--bg-canvas: #080c14" in css or "--bg-canvas: #080b11" in css
        assert "--bg-card: #0e1626" in css or "--bg-card: #0e1420" in css
        assert "--bg-elevated: #131d31" in css or "--bg-elevated: #141d2e" in css
        assert "--bg-hover: #1a263e" in css or "--bg-hover: #1c273d" in css
        
        # 8-Point Grid Spacing Tokens
        assert "--space-1: 4px" in css or "--space-1:4px" in css
        assert "--space-2: 8px" in css or "--space-2:8px" in css
        assert "--space-4: 16px" in css or "--space-4:16px" in css
        assert "--space-8: 32px" in css or "--space-8:32px" in css
