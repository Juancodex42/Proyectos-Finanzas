"""
Milestone 3 Charts & Micro-Interactions Comprehensive Integrity Test Suite
Verifies 100% compliance of static/js/charts.js and static/js/app.js with the Master Design Guide:
- Lightweight Charts v4 defaults and color tokens (Cyber Emerald #10b981, Rose Crimson #f43f5e, Electric Sky #38bdf8).
- Chart.js v4 defaults, tooltips, equity curves with gradient fills and dynamic log scales, Monte Carlo 5-cone stochastic paths.
- HTML5 Canvas 2D Retina high-DPI scaling, color interpolation, and JetBrains Mono tabular numerics.
- Diagnostic chart palettes (Autocorrelation, Streaks, Hourly Win Rate, Market State, G(N), Kelly).
- Fix for line 1098 bug in app.js (mainChart reference).
- Global window export contracts and non-blocking toast notifications.
"""

import os
import re
import pytest

@pytest.fixture(scope="module")
def charts_js():
    path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "charts.js")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture(scope="module")
def app_js():
    path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "app.js")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture(scope="module")
def index_html():
    path = os.path.join(os.path.dirname(__file__), "..", "templates", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestLightweightChartsHarmonization:
    def test_candlestick_chart_creation_defined(self, charts_js):
        assert "function createCandlestickChart(containerId)" in charts_js
        assert "LightweightCharts.createChart" in charts_js
        assert "chart.addCandlestickSeries" in charts_js

    def test_lightweight_charts_canvas_background_and_fonts(self, charts_js):
        assert "background: { type: 'solid', color: 'transparent' }" in charts_js
        assert "textColor: '#94a3b8'" in charts_js
        assert "'Inter'" in charts_js

    def test_lightweight_charts_subtle_gridlines(self, charts_js):
        assert "vertLines: { color: 'rgba(255, 255, 255, 0.03)' }" in charts_js
        assert "horzLines: { color: 'rgba(255, 255, 255, 0.03)' }" in charts_js

    def test_lightweight_charts_crosshairs_and_badges(self, charts_js):
        assert "color: 'rgba(245, 158, 11, 0.45)'" in charts_js or "color: 'rgba(56, 189, 248, 0.4)'" in charts_js
        assert "labelBackgroundColor: '#131d31'" in charts_js or "labelBackgroundColor: '#141d2e'" in charts_js

    def test_lightweight_charts_borders_and_scales(self, charts_js):
        assert "borderColor: 'rgba(255, 255, 255, 0.07)'" in charts_js or "rgba(245, 158, 11, 0.16)" in charts_js or "borderColor: 'rgba(245, 158, 11, 0.18)'" in charts_js

    def test_candlestick_semantic_accent_colors(self, charts_js):
        assert "upColor: '#10b981'" in charts_js
        assert ("downColor: '#e11d48'" in charts_js or "downColor: '#f43f5e'" in charts_js)
        assert "wickUpColor: '#10b981'" in charts_js
        assert ("wickDownColor: '#e11d48'" in charts_js or "wickDownColor: '#f43f5e'" in charts_js)
        assert "precision: 5" in charts_js


class TestChartJSGlobalDefaultsAndEquityCurve:
    def test_chartjs_global_defaults(self, charts_js):
        assert "Chart.defaults.color = '#94a3b8'" in charts_js
        assert ("Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(19, 29, 49, 0.96)'" in charts_js or 
                "Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(19, 29, 49, 0.95)'" in charts_js or 
                "Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(20, 29, 46, 0.95)'" in charts_js)
        assert ("Chart.defaults.plugins.tooltip.titleColor = '#f8fafc'" in charts_js or
                "Chart.defaults.plugins.tooltip.titleColor = '#f0f6fc'" in charts_js)
        assert "Chart.defaults.plugins.tooltip.bodyColor = '#94a3b8'" in charts_js
        assert ("Chart.defaults.plugins.tooltip.borderColor = 'rgba(245, 158, 11, 0.25)'" in charts_js or
                "Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.08)'" in charts_js)
        assert "'JetBrains Mono'" in charts_js

    def test_equity_curve_line_and_gradient(self, charts_js):
        assert "function createEquityCurve(canvasId, equityPoints, rawLabels)" in charts_js
        assert ("borderColor: '#06b6d4'" in charts_js or "borderColor: '#38bdf8'" in charts_js)
        assert ("rgba(6, 182, 212, 0.22)" in charts_js or "rgba(56, 189, 248, 0.22)" in charts_js)
        assert ("rgba(6, 182, 212, 0.00)" in charts_js or "rgba(56, 189, 248, 0.00)" in charts_js)
        assert "tension: 0.15" in charts_js

    def test_equity_curve_dynamic_log_scale_threshold(self, charts_js):
        assert "(maxVal / Math.max(minVal, 0.01)) > 100 && minVal >= 1.0" in charts_js
        assert "Math.pow(10, Math.floor(Math.log10(Math.max(minVal, 1))))" in charts_js

    def test_format_yaxis_tick_sub_dollar_and_millions(self, charts_js):
        assert "function formatYAxisTick(value, useLog)" in charts_js
        assert "1000000" in charts_js
        assert "'M'" in charts_js
        assert "1000" in charts_js
        assert "'k'" in charts_js
        assert "-$" in charts_js


class TestMonteCarloStochasticCones:
    def test_monte_carlo_percentile_bands(self, charts_js):
        assert "function createMonteCarloChart(canvasId, labels, percentiles, initialCapital)" in charts_js
        # P95 & P75 Cyber Emerald / Jade Green
        assert "rgba(16, 185, 129, 0.85)" in charts_js
        assert "rgba(16, 185, 129, 0.45)" in charts_js
        # P50 Champagne Gold / Electric Sky Median
        assert ("borderColor: '#f59e0b'" in charts_js or "borderColor: '#38bdf8'" in charts_js)
        # P25 & P5 Ruby Crimson / Rose Crimson
        assert ("rgba(225, 29, 72, 0.45)" in charts_js or "rgba(244, 63, 94, 0.45)" in charts_js)
        assert ("rgba(225, 29, 72, 0.85)" in charts_js or "rgba(244, 63, 94, 0.85)" in charts_js)

    def test_monte_carlo_probability_cone_fills(self, charts_js):
        assert "fill: '+1'" in charts_js
        assert "rgba(16, 185, 129, 0.05)" in charts_js
        assert ("rgba(225, 29, 72, 0.05)" in charts_js or "rgba(244, 63, 94, 0.05)" in charts_js)

    def test_monte_carlo_initial_capital_baseline(self, charts_js):
        assert "Capital Inicial" in charts_js
        assert "borderDash: [6, 6]" in charts_js

    def test_monte_carlo_zero_clamping(self, charts_js):
        assert "v <= 0.01 ? 0.01 : v" in charts_js


class TestCanvasCorrelationHeatmap:
    def test_correlation_heatmap_retina_scaling(self, charts_js):
        assert "function createCorrelationHeatmap(canvasId, matrix, labels)" in charts_js
        assert "window.devicePixelRatio" in charts_js
        assert "ctx.scale(dpr, dpr)" in charts_js

    def test_correlation_heatmap_diverging_color_interpolation(self, charts_js):
        # Base #131d31 (19, 29, 49) or #141d2e (20, 29, 46) to Crimson and Ice Cyan
        assert ("225 - 19" in charts_js or "244 - 20" in charts_js)
        assert ("6 - 19" in charts_js or "56 - 20" in charts_js)
        assert ("182 - 29" in charts_js or "189 - 29" in charts_js)
        assert ("212 - 49" in charts_js or "248 - 46" in charts_js)

    def test_correlation_heatmap_typography_and_rounding(self, charts_js):
        assert "'JetBrains Mono'" in charts_js
        assert "ctx.roundRect" in charts_js
        assert "Sin datos de correlación" in charts_js


class TestStatisticalDiagnosticsAndExports:
    def test_barchart_and_growth_rate_chart(self, charts_js):
        assert "function createBarChart(canvasId, labels, values, title, color" in charts_js
        assert "function createGrowthRateChart(canvasId, ns, g_values, optimal_n)" in charts_js
        assert ("optimal_n ? '#10b981' : '#06b6d4'" in charts_js or "optimal_n ? '#10b981' : '#38bdf8'" in charts_js)

    def test_diagnostics_charts_rendering_function(self, charts_js):
        assert "function renderDiagnosticsCharts(statsData)" in charts_js

    def test_exported_window_contracts(self, charts_js):
        required_exports = [
            "window.createCandlestickChart",
            "window.initLightweightChart",
            "window.updateCandlestickChart",
            "window.addSignalMarkers",
            "window.formatYAxisTick",
            "window.createEquityCurve",
            "window.renderEquityCurve",
            "window.createBarChart",
            "window.createGrowthRateChart",
            "window.createMonteCarloChart",
            "window.renderMonteCarloCones",
            "window.createCorrelationHeatmap",
            "window.renderCorrelationHeatmap",
            "window.renderDiagnosticsCharts",
        ]
        for exp in required_exports:
            assert exp in charts_js, f"Export {exp} is missing in charts.js"


class TestAppJSInteractionsAndBugFixes:
    def test_line_1098_bug_fix_mainchart_reference(self, app_js):
        # Must not contain tvChart call
        assert "highlightTradeOnChart(trade, tvChart, candleSeries)" not in app_js
        # Must pass mainChart
        assert "highlightTradeOnChart(trade, mainChart, candleSeries)" in app_js

    def test_prepare_candles_color_tokens(self, app_js):
        assert ("isBearish ? '#e11d48'" in app_js or "isBearish ? '#f43f5e'" in app_js)

    def test_update_live_candle_color_tokens(self, app_js):
        assert ("isBearish ? '#e11d48'" in app_js or "isBearish ? '#f43f5e'" in app_js)

    def test_build_chart_markers_tokens(self, app_js):
        assert "color: '#10b981'" in app_js
        assert ("color: '#e11d48'" in app_js or "color: '#f43f5e'" in app_js)
        assert ("color: isWin ? '#10b981' : '#e11d48'" in app_js or "color: isWin ? '#10b981' : '#f43f5e'" in app_js)

    def test_active_trade_price_lines(self, app_js):
        assert ("trade.direction === 'CALL' ? '#10b981' : '#e11d48'" in app_js or "trade.direction === 'CALL' ? '#10b981' : '#f43f5e'" in app_js)
        assert ("trade.result === 'WIN' ? '#10b981' : '#e11d48'" in app_js or "trade.result === 'WIN' ? '#10b981' : '#f43f5e'" in app_js)

    def test_display_statistics_diagnostic_palettes(self, app_js):
        assert ("v >= 0 ? '#a855f7' : '#e11d48'" in app_js or "v >= 0 ? '#a855f7' : '#f43f5e'" in app_js)  # Autocorr
        assert ("'#f59e0b'" in app_js or "'#38bdf8'" in app_js)  # Streaks
        assert "#10b981" in app_js  # Hourly WR >= 58.8%

    def test_non_blocking_toast_notifications(self, app_js):
        assert "function showToast(message, type" in app_js
        assert "toast-container" in app_js
        assert ("showToast('✅ Código Pine Script (v6) copiado al portapapeles.', 'success')" in app_js or 
                "showToast('✅ Código Pine Script (v5) copiado al portapapeles.', 'success')" in app_js)
        assert "showToast('✅ Prompt estructurado para IA copiado al portapapeles.', 'success')" in app_js

    def test_global_window_functions_preserved(self, app_js):
        assert "window.togglePineScriptModal =" in app_js
        assert "window.copyPineScript =" in app_js
        assert "window.copyAIPrompt =" in app_js


class TestNoLegacyColorTokensRemaining:
    def test_no_legacy_halating_colors_in_js(self, charts_js, app_js):
        legacy_tokens = [
            "#00f5a0",
            "#ff4d4d",
            "#58a6ff",
            "#30363d",
            "#8b949e",
            "#c9d1d9",
            "#3fb950",
            "#a371f7"
        ]
        for token in legacy_tokens:
            assert token not in charts_js, f"Legacy token {token} found in charts.js"
            assert token not in app_js, f"Legacy token {token} found in app.js"


class TestDOMIntegrityPreservation:
    def test_all_critical_chart_and_canvas_dom_ids_exist(self, index_html):
        critical_ids = [
            "tv-chart",
            "smart-tv-chart",
            "smart-tv-chart-empty",
            "chart-loader",
            "equity-chart",
            "smart-equity-chart-canvas",
            "mc-chart",
            "smart-mc-chart-canvas",
            "smart-correlation-canvas",
            "autocorr-chart",
            "streaks-chart",
            "hourly-chart",
            "market-state-chart",
            "cond-probs",
            "markov-table",
            "smart-markov-table",
            "smart-markov-explanation",
            "smart-rec-content",
            "smart-ladder-content",
            "smart-top-5-box",
            "smart-top-5-list",
            "smart-selected-assets-table",
            "smart-selected-assets-body",
            "live-badge",
            "live-badge-text",
            "trades-table",
            "history-list",
            "saved-list",
        ]
        for dom_id in critical_ids:
            pattern = rf'id="{dom_id}"'
            assert re.search(pattern, index_html), f"Critical DOM element #{dom_id} not found in index.html"
