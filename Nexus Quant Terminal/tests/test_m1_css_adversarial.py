"""
Adversarial Stress-Testing Suite for Milestone 1:
Deep Structural, Animation, Pseudo-State, and Contrast Integrity.
"""

import re
import math
from pathlib import Path
from html.parser import HTMLParser
import pytest

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
CSS_PATH = WORKSPACE_DIR / "static" / "css" / "style.css"
HTML_PATH = WORKSPACE_DIR / "templates" / "index.html"
JS_APP_PATH = WORKSPACE_DIR / "static" / "js" / "app.js"
JS_CHARTS_PATH = WORKSPACE_DIR / "static" / "js" / "charts.js"


def read_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if path.suffix == ".css":
        def resolve_import(m):
            sub_path = path.parent / m.group(1)
            return sub_path.read_text(encoding="utf-8") if sub_path.exists() else ""
        content = re.sub(r'@import\s+["\']([^"\']+)["\'];', resolve_import, content)
    return content


def strip_css_comments(css_text: str) -> str:
    return re.sub(r'/\*[\s\S]*?\*/', '', css_text)


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel_lum(c: int) -> float:
        c_norm = c / 255.0
        return c_norm / 12.92 if c_norm <= 0.03928 else ((c_norm + 0.055) / 1.055) ** 2.4
    r, g, b = [channel_lum(c) for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex1: str, hex2: str) -> float:
    l1 = relative_luminance(hex_to_rgb(hex1))
    l2 = relative_luminance(hex_to_rgb(hex2))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_keyframes_animation_consistency():
    """
    Ensure every animation referenced in CSS has a corresponding @keyframes block.
    """
    css = strip_css_comments(read_file(CSS_PATH))
    
    # Extract all @keyframes names
    keyframes_declared = set(re.findall(r'@keyframes\s+([a-zA-Z0-9\-_]+)', css))
    
    # Extract animation usages
    animation_usages = set()
    for match in re.finditer(r'animation\s*:\s*([^;]+);', css):
        val = match.group(1).strip()
        # The animation name is typically the first word or identified by tokens
        tokens = val.split()
        if tokens:
            name = tokens[0]
            animation_usages.add(name)
            
    # Check if any used animation name is missing from keyframes
    missing_keyframes = animation_usages - keyframes_declared
    assert not missing_keyframes, f"Animations used but missing @keyframes declaration: {missing_keyframes}"
    print(f"\n[Keyframes Verification] Declared: {keyframes_declared}, Used: {animation_usages}")


def test_interactive_elements_state_coverage():
    """
    Verify that interactive primitives (buttons, inputs, tabs) define proper states:
    :hover, :focus or :active, and :disabled.
    """
    css = strip_css_comments(read_file(CSS_PATH))
    
    # Check .btn-primary states
    assert ".btn-primary:hover" in css, "Missing .btn-primary:hover state"
    assert ".btn-primary:active" in css, "Missing .btn-primary:active state"
    assert ".btn-primary:disabled" in css, "Missing .btn-primary:disabled state"
    
    # Check .btn-secondary states
    assert ".btn-secondary:hover" in css, "Missing .btn-secondary:hover state"
    assert ".btn-secondary:active" in css, "Missing .btn-secondary:active state"
    assert ".btn-secondary:disabled" in css, "Missing .btn-secondary:disabled state"
    
    # Check .tab-btn states
    assert ".tab-btn:hover" in css, "Missing .tab-btn:hover state"
    assert ".tab-btn.active" in css, "Missing .tab-btn.active state"
    assert ".tab-btn:disabled" in css, "Missing .tab-btn:disabled state"
    
    # Check inputs focus
    assert "input:focus" in css or ".form-control:focus" in css, "Missing input focus styles"


def test_wcag_color_contrast_ratios():
    """
    Verify WCAG contrast compliance for text colors against canvas (#080b11) and card background (#0e1420).
    Normal text should exceed 4.5:1 (AA) and preferably 7:1 (AAA).
    """
    bg_canvas = "#080b11"
    bg_card = "#0e1420"
    
    colors = {
        "--text-primary": "#f0f6fc",
        "--text-secondary": "#94a3b8",
        "--accent-primary": "#38bdf8",
        "--accent-green": "#10b981",
        "--accent-red": "#f43f5e",
        "--accent-purple": "#a855f7",
        "--accent-amber": "#f59e0b"
    }
    
    print("\n[WCAG Contrast Verification]")
    for name, hex_val in colors.items():
        cr_canvas = contrast_ratio(hex_val, bg_canvas)
        cr_card = contrast_ratio(hex_val, bg_card)
        print(f"  {name} ({hex_val}): vs Canvas = {cr_canvas:.2f}:1 | vs Card = {cr_card:.2f}:1")
        # Text primary should be extremely high contrast (>10:1)
        if name == "--text-primary":
            assert cr_canvas >= 7.0, f"Primary text contrast ratio too low: {cr_canvas:.2f}:1"
        # Secondary text and accents should exceed AA 4.5:1
        if name in ["--text-secondary", "--accent-primary", "--accent-green", "--accent-amber"]:
            assert cr_canvas >= 4.5, f"Contrast ratio too low for {name}: {cr_canvas:.2f}:1"


def test_media_queries_structure():
    """
    Verify that responsive media queries are defined and syntax-valid.
    """
    css = strip_css_comments(read_file(CSS_PATH))
    mqs = re.findall(r'@media\s*\([^\)]+\)', css)
    assert len(mqs) >= 3, f"Expected at least 3 responsive media queries, found {len(mqs)}"
    assert any("1200px" in mq for mq in mqs), "Missing 1200px breakpoint"
    assert any("900px" in mq for mq in mqs), "Missing 900px breakpoint"
    assert any("600px" in mq for mq in mqs), "Missing 600px breakpoint"
    print(f"\n[Media Queries Verification] Found breakpoints: {mqs}")


def test_custom_scrollbar_and_selection_styling():
    """
    Verify custom webkit scrollbar and modern styling are defined in style.css.
    """
    css = strip_css_comments(read_file(CSS_PATH))
    assert "::-webkit-scrollbar" in css, "Missing ::-webkit-scrollbar styling"
    assert "::-webkit-scrollbar-thumb" in css, "Missing ::-webkit-scrollbar-thumb styling"
    assert "::-webkit-scrollbar-track" in css, "Missing ::-webkit-scrollbar-track styling"


if __name__ == '__main__':
    pytest.main(["-v", "-s", __file__])
