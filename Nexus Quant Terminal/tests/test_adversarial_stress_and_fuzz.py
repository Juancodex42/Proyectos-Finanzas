"""
tests/test_adversarial_stress_and_fuzz.py - Automated Adversarial Fuzzing Test Suite
Verifies all 13 quantitative strategy archetypes, the Pine Script v6 exporter,
capital & Markov optimization engines, and export Web APIs against pathological
market datasets, extreme parameters, NaN/Inf injections, and malformed inputs.
"""

import pytest
import numpy as np
import pandas as pd
from strategies import STRATEGIES
from engine.exporter import StrategyExporter
from engine.optimizers.capital import CapitalOptimizer
from app import app


@pytest.fixture
def pathological_datasets():
    return {
        "Empty DataFrame": pd.DataFrame(),
        "Empty with OHLCV columns": pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'open_time', 'datetime']),
        "1 Candle": pd.DataFrame({
            'open': [100.0], 'high': [105.0], 'low': [95.0], 'close': [102.0], 'volume': [1000.0],
            'open_time': [1700000000], 'datetime': [pd.Timestamp('2024-01-01')]
        }),
        "2 Candles": pd.DataFrame({
            'open': [100.0, 102.0], 'high': [105.0, 106.0], 'low': [95.0, 101.0], 'close': [102.0, 104.0], 'volume': [1000.0, 1200.0],
            'open_time': [1700000000, 1700086400], 'datetime': [pd.Timestamp('2024-01-01'), pd.Timestamp('2024-01-02')]
        }),
        "5 Candles (Short)": pd.DataFrame({
            'open': [100.0, 102.0, 104.0, 103.0, 105.0],
            'high': [105.0, 106.0, 108.0, 107.0, 109.0],
            'low': [95.0, 101.0, 102.0, 100.0, 103.0],
            'close': [102.0, 104.0, 103.0, 105.0, 108.0],
            'volume': [1000.0, 1200.0, 800.0, 1500.0, 2000.0],
            'open_time': np.arange(5) * 86400 + 1700000000,
            'datetime': pd.date_range('2024-01-01', periods=5, freq='D')
        }),
        "Flat Prices (Zero Volatility)": pd.DataFrame({
            'open': [100.0] * 50, 'high': [100.0] * 50, 'low': [100.0] * 50, 'close': [100.0] * 50, 'volume': [0.0] * 50,
            'open_time': np.arange(50) * 86400 + 1700000000, 'datetime': pd.date_range('2024-01-01', periods=50, freq='D')
        }),
        "Zero Volume Dataset": pd.DataFrame({
            'open': np.linspace(100, 150, 60), 'high': np.linspace(102, 155, 60),
            'low': np.linspace(98, 148, 60), 'close': np.linspace(101, 152, 60), 'volume': [0.0] * 60,
            'open_time': np.arange(60) * 86400 + 1700000000, 'datetime': pd.date_range('2024-01-01', periods=60, freq='D')
        }),
        "Negative Prices": pd.DataFrame({
            'open': [-100.0, -102.0, -104.0, -101.0] * 10,
            'high': [-95.0, -98.0, -100.0, -96.0] * 10,
            'low': [-108.0, -109.0, -110.0, -107.0] * 10,
            'close': [-102.0, -104.0, -101.0, -99.0] * 10,
            'volume': [500.0] * 40,
            'open_time': np.arange(40) * 86400 + 1700000000,
            'datetime': pd.date_range('2024-01-01', periods=40, freq='D')
        }),
        "Extreme Price Spikes (10,000x)": pd.DataFrame({
            'open': [100.0, 100.0, 1000000.0, 0.0001, 100.0] * 10,
            'high': [105.0, 105.0, 2000000.0, 100.0, 105.0] * 10,
            'low': [95.0, 95.0, 50.0, 0.00001, 95.0] * 10,
            'close': [100.0, 1000000.0, 0.0001, 100.0, 100.0] * 10,
            'volume': [1000.0] * 50,
            'open_time': np.arange(50) * 86400 + 1700000000,
            'datetime': pd.date_range('2024-01-01', periods=50, freq='D')
        }),
        "Sprinkled NaNs and Infs": pd.DataFrame({
            'open': [100.0, np.nan, 102.0, np.inf, 105.0] * 10,
            'high': [105.0, 106.0, np.nan, 110.0, -np.inf] * 10,
            'low': [95.0, np.nan, 98.0, 99.0, 100.0] * 10,
            'close': [102.0, 104.0, np.nan, 105.0, 108.0] * 10,
            'volume': [1000.0, np.nan, 0.0, np.inf, 2000.0] * 10,
            'open_time': np.arange(50) * 86400 + 1700000000,
            'datetime': pd.date_range('2024-01-01', periods=50, freq='D')
        })
    }


def test_strategies_pathological_datasets(pathological_datasets):
    """Verifies that all 13 strategy archetypes gracefully handle extreme market datasets without throwing unhandled exceptions."""
    for strat_key, strat_cls in STRATEGIES.items():
        strat = strat_cls()
        for ds_name, df in pathological_datasets.items():
            pre = strat.prepare_data(df)
            assert isinstance(pre, dict), f"{strat_key} prepare_data failed on {ds_name}"

            sig1 = strat.generate_signals(df=df, params={})
            assert isinstance(sig1, (pd.Series, list)), f"{strat_key} generate_signals failed on {ds_name}"

            sig2 = strat.generate_signals(precomputed=pre, params={})
            assert isinstance(sig2, (pd.Series, list)), f"{strat_key} precomputed signals failed on {ds_name}"


def test_strategies_adversarial_parameters():
    """Verifies that all strategies gracefully sanitize extreme and malformed parameters."""
    np.random.seed(42)
    closes = np.cumsum(np.random.randn(100)) + 100.0
    highs = closes + np.random.uniform(0.5, 2.0, 100)
    lows = closes - np.random.uniform(0.5, 2.0, 100)
    opens = (highs + lows) / 2.0
    vols = np.random.uniform(100, 10000, 100)
    
    df_normal = pd.DataFrame({
        'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': vols,
        'open_time': np.arange(100) * 86400 + 1700000000,
        'datetime': pd.date_range('2024-01-01', periods=100, freq='D')
    })

    malicious_param_sets = [
        ("None params", None),
        ("Empty params", {}),
        ("String ints & floats", {
            "sma_period": "20", "threshold": "0.015", "bb_period": "20", "bb_std": "2.2",
            "rsi_period": "14", "oversold": "25.0", "overbought": "75.0", "wick_ratio": "0.35",
            "vol_mult": "1.3", "lookback": "50", "lookback_period": "50", "proximity": "0.003",
            "prob_thresh": "0.55", "bb_pctl_thresh": "0.35", "streak_len": "3"
        }),
        ("Zero and Negative Values", {
            "sma_period": 0, "threshold": -0.5, "bb_period": -10, "bb_std": 0.0,
            "rsi_period": 0, "oversold": -100, "overbought": -50, "wick_ratio": -1.0,
            "vol_mult": -5.0, "lookback": 0, "lookback_period": -20, "proximity": -0.05,
            "prob_thresh": -1.0, "bb_pctl_thresh": 0.0, "streak_len": 0
        }),
        ("Extreme High Values", {
            "sma_period": 100000, "threshold": 9999.0, "bb_period": 50000, "bb_std": 100.0,
            "rsi_period": 10000, "oversold": 999.0, "overbought": 1000.0, "wick_ratio": 50.0,
            "vol_mult": 10000.0, "lookback": 999999, "lookback_period": 999999, "proximity": 100.0,
            "prob_thresh": 2.0, "bb_pctl_thresh": 5.0, "streak_len": 1000
        }),
        ("Inverted Thresholds", {
            "rsi_oversold": 90.0, "rsi_overbought": 10.0, "rsi_min_call": 80.0, "rsi_max_call": 20.0
        })
    ]

    for strat_key, strat_cls in STRATEGIES.items():
        strat = strat_cls()
        for p_name, params in malicious_param_sets:
            sig = strat.generate_signals(df=df_normal, params=params)
            assert isinstance(sig, (pd.Series, list)), f"Failed for {strat_key} with {p_name}"


def test_adversarial_pinescript_exporter():
    """Verifies that Pine Script v6 exporter produces valid scripts for malformed and edge-case inputs."""
    malicious_inputs = [
        ("mean_reversion", None, None),
        ("rsi_extremes", {"rsi_period": "14", "oversold": "25.0"}, {"initial_capital": "5000", "pos_size_usd": "100"}),
        ("genetic_composite", {"rsi_period": 0, "bb_std": 0.0}, {"export_mode": "strategy", "bars_to_hold": 0, "max_open_trades": -1}),
        ("volatility_squeeze_ml", {"prob_thresh": -1.0}, {"export_mode": "indicator"}),
        ("daily_confluence", {"direction_filter": 12345}, {"commission_pct": -0.5}),
        ("unknown_archetype_xyz", {"foo": "bar"}, {"export_mode": "strategy"}),
        ("deesr\"; alert('pwned'); //", {"bb_period": 20}, {"initial_capital": 1000}),
        ("islg_rs", {"lookback_period": 50}, {"export_mode": "unknown_mode_999"})
    ]

    for strat_key, params, options in malicious_inputs:
        opts = options or {}
        code = StrategyExporter.export_to_pinescript(
            strategy_key=strat_key,
            params=params or {},
            export_mode=opts.get("export_mode", "strategy"),
            initial_capital=float(opts.get("initial_capital", 1000.0)),
            pos_size_usd=float(opts.get("pos_size_usd", 50.0)),
            max_open_trades=int(opts.get("max_open_trades", 1)),
            bars_to_hold=int(opts.get("bars_to_hold", 1)),
            commission_pct=float(opts.get("commission_pct", 0.05))
        )
        assert isinstance(code, str) and len(code) > 100
        assert "//@version=6" in code
        assert "NaN" not in code
        assert "undefined" not in code


def test_adversarial_capital_optimizer():
    """Verifies that CapitalOptimizer functions handle zero/negative parameters gracefully."""
    opt = CapitalOptimizer()

    streak_test_cases = [
        {"win_rate": 0.0, "payout": 0.85, "risk_capital": 200.0, "target_capital": 1000.0, "attempts": 5},
        {"win_rate": 1.0, "payout": 0.85, "risk_capital": 200.0, "target_capital": 1000.0, "attempts": 5},
        {"win_rate": 0.5, "payout": 0.0, "risk_capital": 200.0, "target_capital": 1000.0, "attempts": 5},
        {"win_rate": 0.6, "payout": 10.0, "risk_capital": 0.0, "target_capital": 1000.0, "attempts": 5},
        {"win_rate": 0.6, "payout": 0.85, "risk_capital": -500.0, "target_capital": 1000.0, "attempts": 5},
        {"win_rate": 0.6, "payout": 0.85, "risk_capital": 200.0, "target_capital": 0.0, "attempts": 5},
        {"win_rate": 0.6, "payout": 0.85, "risk_capital": 200.0, "target_capital": 1000.0, "attempts": 0}
    ]

    for tc in streak_test_cases:
        res = opt.calculate_streak_plan(**tc)
        assert isinstance(res, dict)

    for wr in [0.0, 0.4, 0.5, 0.55, 0.99, 1.0, -0.5, 2.5]:
        res = opt.find_optimal_n(win_rate=wr, payout=0.85)
        assert isinstance(res, dict)


def test_adversarial_api_routes():
    """Verifies that Web API endpoints gracefully handle malformed requests without unhandled 500 crashes."""
    client = app.test_client()
    test_endpoints = [
        ("POST", "/api/export/pinescript", {"strategy": "mean_reversion", "initial_capital": "invalid"}),
        ("POST", "/api/export/pinescript", {"strategy": "../../../etc/passwd", "params": {}}),
        ("POST", "/api/export/pinescript", {}),
        ("GET", "/api/export/pinescript?strategy=../../../../evil&download=true", None)
    ]

    for method, path, payload in test_endpoints:
        if method == "POST":
            resp = client.post(path, json=payload)
        else:
            resp = client.get(path)
        assert resp.status_code < 500, f"Endpoint {method} {path} threw internal server error {resp.status_code}"
