"""
Milestone 3 Challenger 2 Adversarial Integrity & Stress Harness
Empirical validation of DOM IDs, Form Inputs, Buttons, Tab Switching,
WebSocket Fallback, Chart Harmonization, and Micro-Interactions.
"""

import os
import re
import json
import pytest
from pathlib import Path
from html.parser import HTMLParser

BASE_DIR = Path(__file__).resolve().parent.parent
HTML_PATH = BASE_DIR / "templates" / "index.html"
APP_JS_PATH = BASE_DIR / "static" / "js" / "app.js"
CHARTS_JS_PATH = BASE_DIR / "static" / "js" / "charts.js"
PROJECT_MD_PATH = BASE_DIR / "PROJECT.md"


class DOMParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.ids = {}
        self.inputs = []
        self.buttons = []
        self.selects = []
        self.forms = []
        self.canvases = []
        self.tables = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        self.tags.append((tag, attr_dict))
        
        tag_id = attr_dict.get("id")
        if tag_id:
            tag_id_clean = tag_id.strip()
            self.ids[tag_id_clean] = {"tag": tag, "attrs": attr_dict}

        if tag == "input":
            self.inputs.append(attr_dict)
        elif tag == "button":
            self.buttons.append(attr_dict)
        elif tag == "select":
            self.selects.append(attr_dict)
        elif tag == "form":
            self.forms.append(attr_dict)
        elif tag == "canvas":
            self.canvases.append(attr_dict)
        elif tag == "table":
            self.tables.append(attr_dict)
        elif tag == "a":
            self.links.append(attr_dict)


@pytest.fixture(scope="module")
def html_raw():
    assert HTML_PATH.exists(), f"Missing index.html at {HTML_PATH}"
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def app_js_raw():
    assert APP_JS_PATH.exists(), f"Missing app.js at {APP_JS_PATH}"
    with open(APP_JS_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def charts_js_raw():
    assert CHARTS_JS_PATH.exists(), f"Missing charts.js at {CHARTS_JS_PATH}"
    with open(CHARTS_JS_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def project_md_raw():
    assert PROJECT_MD_PATH.exists(), f"Missing PROJECT.md at {PROJECT_MD_PATH}"
    with open(PROJECT_MD_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def dom(html_raw):
    parser = DOMParser()
    parser.feed(html_raw)
    return parser


# =========================================================================
# OBJECTIVE 1.1: 105 DOM IDs VERIFICATION
# =========================================================================
class TestDOM105IDsIntegrity:
    REQUIRED_105_IDS = [
        "mode-smart", "mode-advanced", "live-badge", "live-badge-text", "btn-resultados",
        "btn-estadisticas", "btn-optimizador", "smart-dashboard", "btn-smart-run", "smart-preset-select",
        "smart-streak-length", "smart-base-capital", "smart-profit-pct", "smart-risk-capital",
        "smart-attempts", "smart-payout", "smart-generations", "smart-population", "smart-console-box",
        "smart-progress-bar-fill", "smart-console-logs", "smart-top-5-box", "smart-top-5-list",
        "smart-rec-content", "smart-ladder-content", "smart-correlation-canvas", "smart-selected-assets-table",
        "smart-selected-assets-body", "smart-equity-chart-canvas", "smart-mc-chart-canvas",
        "smart-asset-selector", "smart-tv-chart", "smart-tv-chart-empty", "smart-markov-table",
        "smart-markov-explanation", "dashboard", "pair-selector", "interval-selector", "source-selector",
        "tv-chart", "chart-loader", "backtest", "backtest-form", "sec-strategy", "strategy-selector",
        "dynamic-params", "expiry-candles", "payout", "sec-barbell", "group-n-consecutive",
        "backtest-n-consecutive", "backtest-cycle-prob", "backtest-bet-fraction", "sec-genetic",
        "gen-generations", "gen-population", "gen-min-trades", "optimize-genetic-btn",
        "genetic-progress-container", "genetic-progress-fill", "genetic-progress-text",
        "genetic-progress-eta", "genetic-feedback", "run-backtest-btn", "save-backtest-btn",
        "backtest-progress-container", "backtest-progress-fill", "backtest-progress-text",
        "backtest-progress-eta", "quick-stats", "stat-winrate", "stat-trades", "stat-pnl",
        "stat-mw", "stat-ml", "equity-chart", "trades-table", "resultados", "btn-clear-history",
        "history-list", "saved-list", "estadisticas", "autocorr-chart", "streaks-chart", "hourly-chart",
        "cond-probs", "market-state-chart", "markov-table", "optimizador", "opt-winrate", "opt-payout",
        "opt-base-capital", "opt-profit-pct", "opt-risk-capital", "opt-target-capital", "opt-attempts",
        "btn-calc-streak", "streak-progress-container", "streak-progress-fill", "streak-progress-text",
        "streak-progress-eta", "streak-recommendation-content", "bet-ladder-container",
        "streak-alternatives-table", "mc-chart"
    ]

    def test_exactly_105_unique_expected_ids(self):
        assert len(self.REQUIRED_105_IDS) == 105
        assert len(set(self.REQUIRED_105_IDS)) == 105

    def test_every_dom_id_present_in_templates_index_html(self, dom):
        missing_ids = [dom_id for dom_id in self.REQUIRED_105_IDS if dom_id not in dom.ids]
        assert not missing_ids, f"Missing {len(missing_ids)} DOM IDs in index.html: {missing_ids}"

    def test_zero_duplicate_ids_in_index_html(self, html_raw):
        from collections import Counter
        all_ids = re.findall(r'id=["\']([^"\']+)["\']', html_raw)
        counts = Counter(all_ids)
        duplicates = {k: v for k, v in counts.items() if v > 1}
        assert not duplicates, f"Duplicate DOM IDs detected in index.html: {duplicates}"

    def test_all_interactive_dom_elements_bound_in_app_js(self, app_js_raw):
        # IDs that are directly accessed via getElementById, querySelector, or dataset in app.js
        interactive_ids = [
            "mode-smart", "mode-advanced", "live-badge", "live-badge-text", "btn-smart-run",
            "smart-preset-select", "smart-streak-length", "smart-base-capital", "smart-profit-pct",
            "smart-risk-capital", "smart-attempts", "smart-payout", "smart-generations", "smart-population",
            "smart-console-box", "smart-progress-bar-fill", "smart-console-logs", "smart-top-5-box",
            "smart-top-5-list", "smart-rec-content", "smart-ladder-content", "smart-correlation-canvas",
            "smart-selected-assets-body", "smart-equity-chart-canvas",
            "smart-mc-chart-canvas", "smart-asset-selector", "smart-tv-chart", "smart-tv-chart-empty",
            "smart-markov-table", "smart-markov-explanation", "pair-selector", "interval-selector",
            "source-selector", "tv-chart", "chart-loader", "backtest-form", "strategy-selector",
            "dynamic-params", "expiry-candles", "payout", "backtest-n-consecutive", "backtest-cycle-prob",
            "backtest-bet-fraction", "gen-generations", "gen-population", "gen-min-trades",
            "optimize-genetic-btn", "genetic-progress-fill", "genetic-progress-text",
            "genetic-progress-eta", "genetic-feedback", "run-backtest-btn", "save-backtest-btn",
            "backtest-progress-fill", "backtest-progress-text", "backtest-progress-eta",
            "stat-winrate", "stat-trades", "stat-pnl", "stat-mw", "stat-ml", "equity-chart",
            "trades-table", "btn-clear-history", "history-list", "saved-list", "autocorr-chart",
            "streaks-chart", "hourly-chart", "cond-probs", "market-state-chart", "markov-table",
            "opt-winrate", "opt-payout", "opt-base-capital", "opt-profit-pct", "opt-risk-capital",
            "opt-target-capital", "opt-attempts", "btn-calc-streak", "streak-progress-fill",
            "streak-progress-text", "streak-progress-eta", "streak-recommendation-content",
            "bet-ladder-container", "streak-alternatives-table", "mc-chart"
        ]
        for dom_id in interactive_ids:
            pattern = rf"getElementById\(['\"]{dom_id}['\"]\)|querySelector\(['\"][^'\"]*#{dom_id}[^'\"]*['\"]\)|['\"]{dom_id}['\"]"
            assert re.search(pattern, app_js_raw) is not None, f"DOM ID #{dom_id} not referenced in app.js"


# =========================================================================
# OBJECTIVE 1.2: FORM INPUTS (37 INPUTS) & BUTTONS (16 BUTTONS) INTEGRITY
# =========================================================================
class TestFormControlsAndButtons:
    def test_total_input_and_select_controls_count(self, dom):
        total_controls = len(dom.inputs) + len(dom.selects)
        assert total_controls >= 37, f"Expected at least 37 form controls, found {total_controls}"

    def test_smart_universe_checkboxes_attributes(self, dom):
        universe_cbs = [i for i in dom.inputs if i.get("name") == "smart-universe"]
        assert len(universe_cbs) == 9
        expected_symbols = ["WTI", "NASDAQ", "GBPJPY", "XAUUSD", "DOGEUSDT", "ADAUSDT", "BTCUSDT", "BNBUSDT", "ETHUSDT"]
        found_symbols = [cb.get("value") for cb in universe_cbs]
        assert found_symbols == expected_symbols
        for cb in universe_cbs:
            assert cb.get("type") == "checkbox"

    def test_numeric_input_constraints_and_defaults(self, dom):
        input_map = {i.get("id"): i for i in dom.inputs if "id" in i}
        
        # smart inputs
        assert input_map["smart-streak-length"]["min"] == "1"
        assert input_map["smart-streak-length"]["max"] == "15"
        assert input_map["smart-base-capital"]["min"] == "10"
        assert input_map["smart-profit-pct"]["min"] == "1"
        assert input_map["smart-profit-pct"]["max"] == "100"
        assert "readonly" in input_map["smart-risk-capital"]
        assert input_map["smart-attempts"]["min"] == "1"
        assert input_map["smart-attempts"]["max"] == "50"
        assert input_map["smart-payout"]["step"] == "0.01"

        # backtest inputs
        assert input_map["expiry-candles"]["min"] == "1"
        assert input_map["payout"]["step"] == "0.01"
        assert input_map["backtest-n-consecutive"]["min"] == "1"
        assert input_map["gen-generations"]["min"] == "5"
        assert input_map["gen-population"]["min"] == "10"

        # optimizer inputs
        assert input_map["opt-winrate"]["step"] == "0.01"
        assert input_map["opt-payout"]["step"] == "0.01"
        assert input_map["opt-payout"]["value"] == "0.85"
        assert input_map["opt-base-capital"]["min"] == "10"
        assert input_map["opt-profit-pct"]["min"] == "1"
        assert input_map["opt-target-capital"]["min"] == "50"
        assert input_map["opt-attempts"]["min"] == "1"

    def test_button_count_and_event_binding(self, dom, app_js_raw):
        buttons = dom.buttons
        assert len(buttons) >= 15, f"Expected >= 15 buttons, found {len(buttons)}"

        # Critical action buttons
        critical_btn_ids = [
            "mode-smart", "mode-advanced", "btn-smart-run", "run-backtest-btn",
            "save-backtest-btn", "optimize-genetic-btn", "btn-clear-history", "btn-calc-streak"
        ]
        for btn_id in critical_btn_ids:
            assert btn_id in dom.ids
            pattern = rf"{btn_id}.*addEventListener|\bgetElementById\(['\"]{btn_id}['\"]\)"
            assert re.search(pattern, app_js_raw), f"Button #{btn_id} not wired in app.js"


# =========================================================================
# OBJECTIVE 1.3: SMART MODE VS ADVANCED MODE TAB SWITCHING
# =========================================================================
class TestTabAndModeSwitchingIntegrity:
    def test_mode_switch_preserves_dom_nodes(self, app_js_raw):
        assert "switchTab" in app_js_raw
        assert "mode-smart" in app_js_raw
        assert "mode-advanced" in app_js_raw

    def test_tab_switch_class_toggling_without_dom_detachment(self, app_js_raw):
        switch_tab_code = re.search(r"function switchTab\(tabId\)\s*\{(.*?)\n\}", app_js_raw, re.DOTALL)
        assert switch_tab_code is not None
        code = switch_tab_code.group(1)
        assert "removeChild" not in code
        assert "innerHTML = ''" not in code
        assert "classList.remove('active')" in code
        assert "classList.add('active')" in code

    def test_tab_switch_dispatches_chart_resizing(self, app_js_raw):
        assert "targetChart.applyOptions({ width: el.clientWidth, height: el.clientHeight })" in app_js_raw
        assert "createCorrelationHeatmap('smart-correlation-canvas'" in app_js_raw


# =========================================================================
# OBJECTIVE 1.4: WEBSOCKET FALLBACK TO REST POLLING INTEGRITY
# =========================================================================
class TestWebSocketFallbackResilience:
    def test_websocket_connect_lifecycle(self, app_js_raw):
        assert "function connectLiveStream(pair, interval)" in app_js_raw
        assert "liveWs = new WebSocket(wsUrl);" in app_js_raw
        assert "liveWs.onopen =" in app_js_raw
        assert "liveWs.onmessage =" in app_js_raw
        assert "liveWs.onerror =" in app_js_raw
        assert "liveWs.onclose =" in app_js_raw

    def test_websocket_error_and_close_fallback_to_polling(self, app_js_raw):
        err_block = re.search(r"liveWs\.onerror\s*=\s*\(err\)\s*=>\s*\{(.*?)\};", app_js_raw, re.DOTALL)
        assert err_block is not None
        assert "startFallbackPolling(pair, interval)" in err_block.group(1)

        close_block = re.search(r"liveWs\.onclose\s*=\s*\(evt\)\s*=>\s*\{(.*?)\};", app_js_raw, re.DOTALL)
        assert close_block is not None
        assert "startFallbackPolling(pair, interval)" in close_block.group(1)

    def test_websocket_instantiation_exception_guard(self, app_js_raw):
        try_catch_block = re.search(r"try\s*\{\s*liveWs = new WebSocket\(wsUrl\);.*?\}\s*catch\s*\(e\)\s*\{(.*?)\}", app_js_raw, re.DOTALL)
        assert try_catch_block is not None
        assert "startFallbackPolling(pair, interval)" in try_catch_block.group(1)

    def test_fallback_polling_implementation(self, app_js_raw):
        assert "function startFallbackPolling(pair, interval)" in app_js_raw
        assert "fetch(`https://api.binance.com/api/v3/klines?symbol=${pair}&interval=${interval}&limit=2`)" in app_js_raw
        assert "updateLiveBadge(true, 'En Vivo (Polling)')" in app_js_raw

    def test_stop_livestream_graceful_cleanup(self, app_js_raw):
        stop_fn = re.search(r"function stopLiveStream\(\)\s*\{(.*?)\n\}", app_js_raw, re.DOTALL)
        assert stop_fn is not None
        code = stop_fn.group(1)
        assert "liveWs.onclose = null;" in code
        assert "liveWs.close();" in code
        assert "clearInterval(livePollTimer);" in code
        assert "updateLiveBadge(false);" in code


# =========================================================================
# OBJECTIVE 1.5: CHART ENGINE HARMONIZATION & MICRO-INTERACTIONS
# =========================================================================
class TestChartHarmonizationAndMicroInteractions:
    def test_no_legacy_colors_in_app_and_charts(self, app_js_raw, charts_js_raw):
        forbidden_hex = ["#00f5a0", "#ff4d4d", "#58a6ff", "#30363d", "#8b949e", "#c9d1d9", "#3fb950", "#a371f7"]
        for hex_code in forbidden_hex:
            assert hex_code not in app_js_raw, f"Legacy color {hex_code} detected in app.js"
            assert hex_code not in charts_js_raw, f"Legacy color {hex_code} detected in charts.js"

    def test_highlight_trade_on_chart_uses_mainchart(self, app_js_raw):
        assert "highlightTradeOnChart(trade, tvChart, candleSeries)" not in app_js_raw
        assert "highlightTradeOnChart(trade, mainChart, candleSeries)" in app_js_raw

    def test_modal_and_toast_notifications(self, app_js_raw):
        assert "function showToast(message, type" in app_js_raw
        assert "window.togglePineScriptModal" in app_js_raw
        assert "window.copyPineScript" in app_js_raw
        assert "window.copyAIPrompt" in app_js_raw
        assert "navigator.clipboard.writeText" in app_js_raw
