"""
Comprehensive Test Suite for Milestone 2:
Institutional HTML5 Workspace Architecture & Template Refactor Integrity.
"""

import os
import re
import pytest
from pathlib import Path
from html.parser import HTMLParser

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
HTML_PATH = WORKSPACE_DIR / "templates" / "index.html"
CSS_PATH = WORKSPACE_DIR / "static" / "css" / "style.css"
JS_APP_PATH = WORKSPACE_DIR / "static" / "js" / "app.js"


def read_file(path: Path) -> str:
    assert path.exists(), f"Target file does not exist: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class FullHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.ids = set()
        self.classes = set()
        self.inputs = []
        self.selects = []
        self.buttons = []
        self.canvases = []
        self.tables = []
        
    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        self.tags.append((tag, attr_dict))
        
        if "id" in attr_dict:
            self.ids.add(attr_dict["id"].strip())
        if "class" in attr_dict:
            for c in attr_dict["class"].split():
                self.classes.add(c)
        if tag == "input":
            self.inputs.append(attr_dict)
        elif tag == "select":
            self.selects.append(attr_dict)
        elif tag == "button":
            self.buttons.append(attr_dict)
        elif tag == "canvas":
            self.canvases.append(attr_dict)
        elif tag == "table":
            self.tables.append(attr_dict)


@pytest.fixture(scope="module")
def html_content():
    return read_file(HTML_PATH)


@pytest.fixture(scope="module")
def parsed_html(html_content):
    parser = FullHTMLParser()
    parser.feed(html_content)
    return parser


# =========================================================================
# 1. HEAD & METADATA TESTS
# =========================================================================

class TestHeadMetadata:
    def test_doctype_and_html_lang(self, html_content):
        assert "<!DOCTYPE html>" in html_content
        assert '<html lang="es">' in html_content

    def test_google_fonts_preconnect_and_families(self, html_content):
        assert 'rel="preconnect" href="https://fonts.googleapis.com"' in html_content
        assert 'rel="preconnect" href="https://fonts.gstatic.com"' in html_content
        # Inter + JetBrains Mono fonts linked
        assert "family=Inter:wght@300;400;500;600;700" in html_content
        assert "family=JetBrains+Mono:wght@400;500;600;700" in html_content

    def test_stylesheets_and_scripts_in_head(self, html_content):
        assert 'href="/static/css/style.css"' in html_content
        assert "lightweight-charts" in html_content
        assert "chart.js" in html_content

    def test_favicons_present(self, html_content):
        assert 'href="/static/favicon.ico"' in html_content
        assert 'href="/static/favicon.png"' in html_content


# =========================================================================
# 2. 100% INVIOLABLE DOM ID PRESERVATION (105 IDs)
# =========================================================================

class TestDOMIdPreservation:
    EXPECTED_105_IDS = [
        "mode-smart", "mode-advanced", "live-badge", "live-badge-text", "btn-resultados", "btn-estadisticas", "btn-optimizador",
        "smart-dashboard", "btn-smart-run", "smart-preset-select", "smart-streak-length", "smart-base-capital", "smart-profit-pct",
        "smart-risk-capital", "smart-attempts", "smart-payout", "smart-generations", "smart-population", "smart-console-box",
        "smart-progress-bar-fill", "smart-console-logs", "smart-top-5-box", "smart-top-5-list", "smart-rec-content",
        "smart-ladder-content", "smart-correlation-canvas", "smart-selected-assets-table", "smart-selected-assets-body",
        "smart-equity-chart-canvas", "smart-mc-chart-canvas", "smart-asset-selector", "smart-tv-chart", "smart-tv-chart-empty",
        "smart-markov-table", "smart-markov-explanation", "dashboard", "pair-selector", "interval-selector", "source-selector",
        "tv-chart", "chart-loader", "backtest", "backtest-form", "sec-strategy", "strategy-selector", "dynamic-params",
        "expiry-candles", "payout", "sec-barbell", "group-n-consecutive", "backtest-n-consecutive", "backtest-cycle-prob",
        "backtest-bet-fraction", "sec-genetic", "gen-generations", "gen-population", "gen-min-trades", "optimize-genetic-btn",
        "genetic-progress-container", "genetic-progress-fill", "genetic-progress-text", "genetic-progress-eta", "genetic-feedback",
        "run-backtest-btn", "save-backtest-btn", "backtest-progress-container", "backtest-progress-fill", "backtest-progress-text",
        "backtest-progress-eta", "quick-stats", "stat-winrate", "stat-trades", "stat-pnl", "stat-mw", "stat-ml", "equity-chart",
        "trades-table", "resultados", "btn-clear-history", "history-list", "saved-list", "estadisticas", "autocorr-chart",
        "streaks-chart", "hourly-chart", "cond-probs", "market-state-chart", "markov-table", "optimizador", "opt-winrate",
        "opt-payout", "opt-base-capital", "opt-profit-pct", "opt-risk-capital", "opt-target-capital", "opt-attempts",
        "btn-calc-streak", "streak-progress-container", "streak-progress-fill", "streak-progress-text", "streak-progress-eta",
        "streak-recommendation-content", "bet-ladder-container", "streak-alternatives-table", "mc-chart"
    ]

    def test_all_105_ids_exist(self, parsed_html):
        missing = [i for i in self.EXPECTED_105_IDS if i not in parsed_html.ids]
        assert not missing, f"Missing {len(missing)} required DOM IDs: {missing}"

    def test_total_ids_count_at_least_105(self, parsed_html):
        matched = set(self.EXPECTED_105_IDS).intersection(parsed_html.ids)
        assert len(matched) == 105, f"Expected 105 matched IDs, found {len(matched)}"


# =========================================================================
# 3. INSTITUTIONAL HEADER & NAVIGATION
# =========================================================================

class TestHeaderAndNavigation:
    def test_header_structure(self, html_content):
        assert 'class="app-header"' in html_content
        assert 'Nexus Quant Terminal' in html_content
        assert 'Institutional <span>Algorithmic Platform</span>' in html_content

    def test_mode_switcher_buttons(self, parsed_html):
        mode_btns = [b for b in parsed_html.buttons if "data-mode" in b]
        assert len(mode_btns) == 2
        assert any(b.get("id") == "mode-smart" and b.get("data-mode") == "smart" for b in mode_btns)
        assert any(b.get("id") == "mode-advanced" and b.get("data-mode") == "advanced" for b in mode_btns)

    def test_telemetry_live_badge(self, html_content):
        assert 'id="live-badge"' in html_content
        assert 'id="live-badge-text"' in html_content
        assert "pulse-dot" in html_content

    def test_tabs_nav_buttons(self, parsed_html):
        tab_btns = [b for b in parsed_html.buttons if "data-tab" in b]
        tabs = [b["data-tab"] for b in tab_btns]
        assert "smart-dashboard" in tabs
        assert "dashboard" in tabs
        assert "backtest" in tabs
        assert "resultados" in tabs
        assert "estadisticas" in tabs
        assert "optimizador" in tabs


# =========================================================================
# 4. SMART MODE WORKSPACE & CONTROLS
# =========================================================================

class TestSmartModeControls:
    def test_smart_universe_checkboxes(self, parsed_html, html_content):
        universe_checkboxes = [i for i in parsed_html.inputs if i.get("name") == "smart-universe"]
        assert len(universe_checkboxes) == 9
        values = [i.get("value") for i in universe_checkboxes]
        expected = ["WTI", "NASDAQ", "GBPJPY", "XAUUSD", "DOGEUSDT", "ADAUSDT", "BTCUSDT", "BNBUSDT", "ETHUSDT"]
        assert values == expected
        # Check WR badge spans
        assert html_content.count('class="asset-wr-badge"') == 9

    def test_smart_presets_select(self, html_content):
        assert 'id="smart-preset-select"' in html_content
        assert 'value="preset_33_6"' in html_content
        assert 'value="preset_25_8"' in html_content
        assert 'value="preset_200_1"' in html_content

    def test_smart_numeric_inputs_defaults_and_attributes(self, parsed_html):
        input_dict = {i.get("id"): i for i in parsed_html.inputs if "id" in i}
        
        # smart-streak-length
        assert input_dict["smart-streak-length"]["value"] == "3"
        assert input_dict["smart-streak-length"]["min"] == "1"
        assert input_dict["smart-streak-length"]["max"] == "15"

        # smart-base-capital
        assert input_dict["smart-base-capital"]["value"] == "1000"
        assert input_dict["smart-base-capital"]["min"] == "10"

        # smart-profit-pct
        assert input_dict["smart-profit-pct"]["value"] == "20"
        assert input_dict["smart-profit-pct"]["min"] == "1"
        assert input_dict["smart-profit-pct"]["max"] == "100"

        # smart-risk-capital (readonly)
        assert input_dict["smart-risk-capital"]["value"] == "200"
        assert "readonly" in input_dict["smart-risk-capital"]

        # smart-attempts
        assert input_dict["smart-attempts"]["value"] == "6"
        assert input_dict["smart-attempts"]["min"] == "1"
        assert input_dict["smart-attempts"]["max"] == "50"

        # smart-payout
        assert input_dict["smart-payout"]["value"] == "0.85"

        # smart-generations
        assert input_dict["smart-generations"]["value"] == "50"

        # smart-population
        assert input_dict["smart-population"]["value"] == "150"

    def test_smart_console_and_results_structure(self, parsed_html, html_content):
        assert "smart-console-box" in parsed_html.ids
        assert "smart-progress-bar-fill" in parsed_html.ids
        assert "smart-console-logs" in parsed_html.ids
        assert "smart-top-5-box" in parsed_html.ids
        assert "smart-top-5-list" in parsed_html.ids
        assert "smart-rec-content" in parsed_html.ids
        assert "smart-ladder-content" in parsed_html.ids
        assert "smart-correlation-canvas" in parsed_html.ids
        assert "smart-selected-assets-table" in parsed_html.ids
        assert "smart-selected-assets-body" in parsed_html.ids
        assert "smart-equity-chart-canvas" in parsed_html.ids
        assert "smart-mc-chart-canvas" in parsed_html.ids
        assert "smart-asset-selector" in parsed_html.ids
        assert "smart-tv-chart" in parsed_html.ids
        assert "smart-tv-chart-empty" in parsed_html.ids
        assert "smart-markov-table" in parsed_html.ids
        assert "smart-markov-explanation" in parsed_html.ids


# =========================================================================
# 5. ADVANCED MODE PANELS & FORMS
# =========================================================================

class TestAdvancedModePanels:
    def test_dashboard_market_controls(self, parsed_html):
        assert "pair-selector" in parsed_html.ids
        assert "interval-selector" in parsed_html.ids
        assert "source-selector" in parsed_html.ids
        assert "tv-chart" in parsed_html.ids
        assert "chart-loader" in parsed_html.ids

    def test_backtest_form_subtabs(self, parsed_html):
        assert "backtest-form" in parsed_html.ids
        assert "sec-strategy" in parsed_html.ids
        assert "strategy-selector" in parsed_html.ids
        assert "dynamic-params" in parsed_html.ids
        assert "expiry-candles" in parsed_html.ids
        assert "payout" in parsed_html.ids
        assert "sec-barbell" in parsed_html.ids
        assert "group-n-consecutive" in parsed_html.ids
        assert "backtest-n-consecutive" in parsed_html.ids
        assert "backtest-cycle-prob" in parsed_html.ids
        assert "backtest-bet-fraction" in parsed_html.ids
        assert "sec-genetic" in parsed_html.ids
        assert "gen-generations" in parsed_html.ids
        assert "gen-population" in parsed_html.ids
        assert "gen-min-trades" in parsed_html.ids
        assert "optimize-genetic-btn" in parsed_html.ids
        assert "run-backtest-btn" in parsed_html.ids
        assert "save-backtest-btn" in parsed_html.ids

    def test_quick_stats_and_results_tables(self, parsed_html):
        assert "quick-stats" in parsed_html.ids
        assert "stat-winrate" in parsed_html.ids
        assert "stat-trades" in parsed_html.ids
        assert "stat-pnl" in parsed_html.ids
        assert "stat-mw" in parsed_html.ids
        assert "stat-ml" in parsed_html.ids
        assert "equity-chart" in parsed_html.ids
        assert "trades-table" in parsed_html.ids

    def test_history_and_diagnostics_panels(self, parsed_html):
        assert "btn-clear-history" in parsed_html.ids
        assert "history-list" in parsed_html.ids
        assert "saved-list" in parsed_html.ids
        assert "autocorr-chart" in parsed_html.ids
        assert "streaks-chart" in parsed_html.ids
        assert "hourly-chart" in parsed_html.ids
        assert "cond-probs" in parsed_html.ids
        assert "market-state-chart" in parsed_html.ids
        assert "markov-table" in parsed_html.ids

    def test_optimizer_controls(self, parsed_html):
        assert "opt-winrate" in parsed_html.ids
        assert "opt-payout" in parsed_html.ids
        assert "opt-base-capital" in parsed_html.ids
        assert "opt-profit-pct" in parsed_html.ids
        assert "opt-risk-capital" in parsed_html.ids
        assert "opt-target-capital" in parsed_html.ids
        assert "opt-attempts" in parsed_html.ids
        assert "btn-calc-streak" in parsed_html.ids
        assert "streak-recommendation-content" in parsed_html.ids
        assert "bet-ladder-container" in parsed_html.ids
        assert "streak-alternatives-table" in parsed_html.ids
        assert "mc-chart" in parsed_html.ids


# =========================================================================
# 6. SCRIPTS AND CLOSING TAGS
# =========================================================================

class TestScriptsAndTags:
    def test_scripts_included_at_end(self, html_content):
        assert '<script src="/static/js/charts.js"></script>' in html_content
        assert ('<script type="module" src="/static/js/app.js"></script>' in html_content or
                '<script src="/static/js/app.js"></script>' in html_content)

    def test_canvases_count(self, parsed_html):
        canvas_ids = [c.get("id") for c in parsed_html.canvases if "id" in c]
        expected_canvases = [
            "smart-correlation-canvas",
            "smart-equity-chart-canvas",
            "smart-mc-chart-canvas",
            "equity-chart",
            "autocorr-chart",
            "streaks-chart",
            "hourly-chart",
            "market-state-chart",
            "mc-chart"
        ]
        for cid in expected_canvases:
            assert cid in canvas_ids, f"Canvas ID missing: {cid}"
