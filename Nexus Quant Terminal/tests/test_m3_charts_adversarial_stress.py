"""
Milestone 3 Charts & Micro-Interactions Adversarial Stress Tests (Pytest Runner)
Runs the empirical Node.js harness and validates boundary conditions, edge cases,
and numerical safety in static/js/charts.js and static/js/app.js.
"""

import os
import subprocess
import pytest


def test_nodejs_adversarial_stress_suite():
    """Execute the empirical Node.js chart stress test harness."""
    js_test_path = os.path.join(os.path.dirname(__file__), "test_m3_charts_adversarial_stress.js")
    assert os.path.exists(js_test_path), f"Test file {js_test_path} must exist"

    result = subprocess.run(
        ["node", js_test_path],
        capture_output=True,
        text=True,
        check=False
    )
    
    # Assert successful execution and no uncaught exceptions
    assert result.returncode == 0, f"Node.js stress tests failed with code {result.returncode}:\n{result.stderr}\n{result.stdout}"
    assert "30/30 PASSED (100%)" in result.stdout, f"Expected 30/30 tests to pass. Output:\n{result.stdout}"


def test_charts_edge_case_code_defenses():
    """Verify specific mathematical and boundary defenses in charts.js and app.js."""
    charts_path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "charts.js")
    with open(charts_path, "r", encoding="utf-8") as f:
        charts_js = f.read()

    # 1. Log scale protection against non-positive numbers (log <= 0)
    assert "minVal >= 1.0" in charts_js
    assert "v <= 0.01 ? 0.01 : v" in charts_js

    # 2. Heatmap empty matrix / labels fallback defense
    assert "!matrix || matrix.length === 0 || !labels || labels.length === 0" in charts_js
    assert "Sin datos de correlación" in charts_js

    # 3. Correlation NaN/null checks
    assert "val !== null && val !== undefined && !isNaN(val)" in charts_js

    # 4. Candlestick try/catch safety on update
    assert "try {" in charts_js
    assert "series.update(candle)" in charts_js
    assert "console.warn('[Chart] Error updating candlestick:', e)" in charts_js


def test_app_js_markers_defense():
    """Verify signal marker building edge case defenses in app.js."""
    app_path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "app.js")
    with open(app_path, "r", encoding="utf-8") as f:
        app_js = f.read()

    # 1. Null/empty check
    assert "!signals || signals.length === 0" in app_js

    # 2. Deduplication Set
    assert "new Set()" in app_js
    assert "seenKeys.has(key)" in app_js

    # 3. PnL and Price null safety
    assert "s.pnl !== undefined && s.pnl !== null" in app_js
    assert "s.entry_price ? ` @ ${formatPrice(s.entry_price)}` : ''" in app_js
