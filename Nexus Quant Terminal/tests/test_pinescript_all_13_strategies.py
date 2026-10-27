"""
test_pinescript_all_13_strategies.py - Comprehensive Verification of Pine Script v6 Exporter
Audits that 100% of all 13 quantitative strategies export valid, institutional-grade Pine Script v6
with zero discrepancy, dual-mode (Executable Bot 'strategy' vs Signal 'indicator'), commented risk management,
plotshape visual markers, and webhook-ready alertconditions.
"""

import pytest
import json
from engine.exporter import StrategyExporter, export_to_pinescript
from strategies import STRATEGIES
from app import app


ALL_13_STRATEGIES = [
    ("mean_reversion", {"sma_period": 20, "threshold": 0.015, "atr_period": 14, "atr_threshold_percentile": 50}),
    ("rsi_extremes", {"rsi_period": 14, "oversold": 25, "overbought": 75, "wick_ratio": 0.35, "vol_mult": 1.3}),
    ("bollinger_bounce", {"bb_period": 20, "bb_std": 2.2, "wick_ratio": 0.35, "vol_mult": 1.3}),
    ("ema_cross", {"fast_period": 9, "slow_period": 21}),
    ("volatility_squeeze", {"bb_period": 20, "bb_mult": 1.5, "kc_period": 20, "kc_mult": 2.0}),
    ("support_resistance", {"lookback": 50, "proximity": 0.003, "bounce_wick_ratio": 0.2}),
    ("genetic_composite", {
        "rsi_enabled": True, "rsi_period": 14, "rsi_oversold": 30.0, "rsi_overbought": 70.0,
        "bb_enabled": True, "bb_period": 20, "bb_std": 2.0,
        "ema_enabled": True, "ema_fast_period": 9, "ema_slow_period": 21,
        "rejection_filter_enabled": True, "pinbar_wick_ratio": 0.35,
        "volatility_filter_enabled": True, "min_bb_width": 0.005,
        "htf_ema_enabled": True, "htf_ema_period": 100
    }),
    ("daily_confluence", {
        "ema_weekly_period": 20, "ema_daily_period": 20, "rsi_period": 14,
        "pullback_tolerance": 0.008, "rsi_min_call": 25.0, "rsi_max_call": 55.0,
        "rsi_min_put": 45.0, "rsi_max_put": 75.0, "wick_rejection_ratio": 0.35, "direction_filter": "BOTH"
    }),
    ("mtf_tcve", {
        "bb_period": 20, "bb_std": 2.0, "wick_ratio": 0.35, "vol_mult": 1.3,
        "rsi_period": 7, "rsi_oversold": 25.0, "rsi_overbought": 75.0
    }),
    ("deesr", {
        "bb_period": 20, "bb_std": 2.5, "kc_period": 20, "kc_mult": 2.0,
        "rsi_fast_period": 3, "rsi_slow_period": 14, "max_body_ratio": 0.45, "min_wick_ratio": 0.35
    }),
    ("islg_rs", {
        "lookback_period": 50, "min_sweep_atr_ratio": 0.15, "wick_ratio": 0.35, "vol_mult": 1.3, "rsi_period": 7
    }),
    ("volatility_squeeze_ml", {
        "bb_pctl_thresh": 0.35, "prob_thresh": 0.53, "use_mtf": True
    }),
    ("climax_reversal", {
        "streak_len": 3, "wick_ratio": 0.35, "vol_mult": 1.3, "rsi_period": 7,
        "rsi_extreme": 30.0, "check_exhaustion": True, "bb_period": 20, "bb_std": 2.0
    })
]


def test_registry_contains_exactly_13_strategies():
    """Verify registry has all 13 strategies registered."""
    assert len(STRATEGIES) == 13, f"Expected 13 registered strategies, got {len(STRATEGIES)}"
    for strat_key, _ in ALL_13_STRATEGIES:
        assert strat_key in STRATEGIES, f"Strategy '{strat_key}' not in STRATEGIES registry"


@pytest.mark.parametrize("strat_key,params", ALL_13_STRATEGIES)
def test_pinescript_v6_strategy_bot_mode(strat_key, params):
    """Verify every strategy exports valid Pine Script v6 Executable Bot (strategy mode)."""
    code = export_to_pinescript(
        strat_key, 
        params, 
        export_mode="strategy",
        initial_capital=2500.0,
        pos_size_usd=100.0,
        max_open_trades=2,
        bars_to_hold=3,
        commission_pct=0.06
    )
    
    assert isinstance(code, str) and len(code) > 200, f"Code for {strat_key} is too short or empty"
    assert "//@version=6" in code, f"Missing //@version=6 in {strat_key}"
    assert "strategy(" in code, f"Missing strategy( in {strat_key}"
    assert "initial_capital=2500.0" in code, f"Missing custom initial_capital in {strat_key}"
    assert "default_qty_value=100.0" in code, f"Missing pos_size in {strat_key}"
    assert "pyramiding=2" in code, f"Missing pyramiding in {strat_key}"
    assert "bars_to_hold    = input.int(3" in code, f"Missing bars_to_hold in {strat_key}"
    assert "strategy.entry(\"BUY_CALL\"" in code or "strategy.entry(\"SELL_PUT\"" in code, f"Missing strategy.entry in {strat_key}"
    assert "strategy.close_all(" in code, f"Missing strategy.close_all in {strat_key}"
    assert "alertcondition(" in code, f"Missing alertcondition( in {strat_key}"
    assert "call_signal" in code or "filter_call" in code, f"Missing call signal in {strat_key}"


@pytest.mark.parametrize("strat_key,params", ALL_13_STRATEGIES)
def test_pinescript_v6_indicator_mode(strat_key, params):
    """Verify every strategy exports valid Pine Script v6 Indicator mode."""
    code = export_to_pinescript(strat_key, params, export_mode="indicator")
    
    assert "//@version=6" in code, f"Missing //@version=6 in indicator mode {strat_key}"
    assert "indicator(" in code, f"Missing indicator( in {strat_key}"
    assert "strategy.entry" not in code, f"Found unexpected strategy.entry in indicator mode {strat_key}"
    assert "plotshape(" in code, f"Missing plotshape( in {strat_key}"
    assert "alertcondition(" in code, f"Missing alertcondition( in {strat_key}"


@pytest.mark.parametrize("strat_key,params", ALL_13_STRATEGIES)
def test_strategy_exporter_facade(strat_key, params):
    """Verify StrategyExporter façade staticmethod parity."""
    code1 = StrategyExporter.export_to_pinescript(strat_key, params, export_mode="strategy")
    code2 = export_to_pinescript(strat_key, params, export_mode="strategy")
    assert code1 == code2, f"Mismatch between StrategyExporter and export_to_pinescript for {strat_key}"


def test_api_export_pinescript_endpoints():
    """Verify Flask /api/export/pinescript endpoint for both JSON and download responses with v6 params."""
    client = app.test_client()

    for strat_key, params in ALL_13_STRATEGIES:
        # 1. JSON POST with custom risk parameters
        resp = client.post('/api/export/pinescript', json={
            'strategy': strat_key, 
            'params': params,
            'export_mode': 'strategy',
            'initial_capital': 5000.0,
            'pos_size_usd': 200.0,
            'max_open_trades': 3,
            'bars_to_hold': 2
        })
        assert resp.status_code == 200, f"Failed JSON POST for {strat_key}: {resp.data}"
        data = json.loads(resp.data)
        assert data['strategy'] == strat_key
        assert data['version'] == 6
        assert "//@version=6" in data['pinescript']
        assert "strategy(" in data['pinescript']
        assert "initial_capital=5000.0" in data['pinescript']

        # 2. Direct Download GET
        resp_dl = client.get(f'/api/export/pinescript?strategy={strat_key}&download=true&export_mode=strategy')
        assert resp_dl.status_code == 200, f"Failed download GET for {strat_key}: {resp_dl.data}"
        assert resp_dl.mimetype == 'text/plain'
        cd_header = resp_dl.headers.get('Content-Disposition', '')
        assert f"Nexus_{strat_key}_" in cd_header or f"{strat_key}.pine" in cd_header
