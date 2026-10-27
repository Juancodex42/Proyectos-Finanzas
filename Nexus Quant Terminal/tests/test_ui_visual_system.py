import os
import re
import pytest

def get_relative_luminance(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c * 2 for c in hex_str])
    r, g, b = [int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
    
    def adjust(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        
    return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)

def get_contrast_ratio(hex1, hex2):
    lum1 = get_relative_luminance(hex1)
    lum2 = get_relative_luminance(hex2)
    top = max(lum1, lum2)
    bot = min(lum1, lum2)
    return (top + 0.05) / (bot + 0.05)

@pytest.fixture(scope="module")
def css_content():
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
    with open(css_path, "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture(scope="module")
def html_content():
    html_path = os.path.join(os.path.dirname(__file__), "..", "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

class TestDesignSystemTokens:
    def test_surface_tokens_defined(self, css_content):
        expected_tokens = {
            "--bg-canvas": r"(#080c14|#080b11)",
            "--bg-card": r"(#0e1626|#0e1420)",
            "--bg-elevated": r"(#131d31|#141d2e)",
            "--bg-hover": r"(#1a263e|#1c273d)",
        }
        for token, hex_pattern in expected_tokens.items():
            pattern = rf"{token}:\s*{hex_pattern}"
            assert re.search(pattern, css_content, re.IGNORECASE), f"Missing or invalid token {token}"

    def test_semantic_accent_tokens_defined(self, css_content):
        expected_accents = {
            "--accent-primary": r"(#f59e0b|#38bdf8)",
            "--accent-green": r"#10b981",
            "--accent-red": r"(#e11d48|#f43f5e)",
            "--accent-purple": r"#a855f7",
            "--accent-amber": r"#f59e0b",
        }
        for token, hex_pattern in expected_accents.items():
            pattern = rf"{token}:\s*{hex_pattern}"
            assert re.search(pattern, css_content, re.IGNORECASE), f"Missing or invalid accent {token}"

    def test_spacing_tokens_8pt_grid(self, css_content):
        expected_spacing = {
            "--space-1": "4px",
            "--space-2": "8px",
            "--space-3": "12px",
            "--space-4": "16px",
            "--space-5": "20px",
            "--space-6": "24px",
            "--space-8": "32px",
        }
        for token, px_val in expected_spacing.items():
            pattern = rf"{token}:\s*{px_val}"
            assert re.search(pattern, css_content), f"Missing or invalid spacing token {token}"

    def test_typography_tokens_defined(self, css_content):
        assert "--font-sans:" in css_content
        assert "'Inter'" in css_content
        assert "--font-mono:" in css_content
        assert "'JetBrains Mono'" in css_content

    def test_motion_tokens_defined(self, css_content):
        assert "--ease-out-expo:" in css_content
        assert "cubic-bezier(0.16, 1, 0.3, 1)" in css_content
        assert "--duration-micro:" in css_content
        assert "--duration-state:" in css_content
        assert "--duration-reveal:" in css_content

class TestTabularTypographyIntegrity:
    def test_tabular_nums_properties_enforced(self, css_content):
        assert "font-variant-numeric: tabular-nums" in css_content
        assert 'font-feature-settings: "tnum" 1' in css_content
        assert 'font-family: var(--font-mono)' in css_content

    def test_tabular_nums_selectors_coverage(self, css_content):
        required_selectors = [
            ".tabular-nums",
            ".markov-table td",
            ".markov-table th",
            ".trades-table td",
            ".trades-table th",
            ".n-table td",
            ".n-table th",
            ".stat-card p",
            ".console-body",
            ".ladder-step-amount",
            ".smart-rec-item p",
            ".recommendation-stat p",
            ".backtest-item-metrics span strong",
            ".asset-wr-badge",
            ".info-text",
            "#backtest-cycle-prob",
            ".smart-numeric-inputs input",
            ".cond-probs-grid div strong",
        ]
        for sel in required_selectors:
            assert sel in css_content, f"Selector {sel} missing from tabular numbers rule in style.css"

    def test_right_aligned_numerical_columns(self, css_content):
        assert "td.num" in css_content
        assert "th.num" in css_content
        assert "text-align: right" in css_content

class TestWCAGContrastCompliance:
    def test_primary_text_contrast_aaa_normal(self):
        # WCAG AAA for normal text requires >= 7.0:1
        bg_canvas = "#080b11"
        bg_card = "#0e1420"
        bg_elevated = "#141d2e"
        bg_hover = "#1c273d"
        text_primary = "#f0f6fc"

        assert get_contrast_ratio(text_primary, bg_canvas) >= 7.0
        assert get_contrast_ratio(text_primary, bg_card) >= 7.0
        assert get_contrast_ratio(text_primary, bg_elevated) >= 7.0
        assert get_contrast_ratio(text_primary, bg_hover) >= 7.0

    def test_secondary_text_contrast_aa_and_aaa(self):
        # Secondary text (#94a3b8)
        bg_canvas = "#080b11"
        bg_card = "#0e1420"
        bg_elevated = "#141d2e"
        text_secondary = "#94a3b8"

        # On base canvas and cards, exceeds AAA (>= 7.0)
        assert get_contrast_ratio(text_secondary, bg_canvas) >= 7.0
        assert get_contrast_ratio(text_secondary, bg_card) >= 7.0
        # On elevated surfaces, passes AA (>= 4.5)
        assert get_contrast_ratio(text_secondary, bg_elevated) >= 4.5

    def test_semantic_accents_contrast(self):
        bg_card = "#0e1420"
        sky = "#38bdf8"
        emerald = "#10b981"
        crimson = "#f43f5e"
        amethyst = "#a855f7"
        golden = "#f59e0b"

        # Electric Sky and Golden Amber exceed AAA normal (>= 7.0:1)
        assert get_contrast_ratio(sky, bg_card) >= 7.0
        assert get_contrast_ratio(golden, bg_card) >= 7.0
        assert get_contrast_ratio(emerald, bg_card) >= 7.0

        # Crimson and Amethyst exceed AA normal (>= 4.5:1) and AAA large (>= 4.5:1)
        assert get_contrast_ratio(crimson, bg_card) >= 4.5
        assert get_contrast_ratio(amethyst, bg_card) >= 4.5

    def test_action_buttons_text_contrast(self):
        dark_text = "#080b11"
        sky_start = "#38bdf8"
        emerald_start = "#10b981"

        # btn-primary text contrast
        assert get_contrast_ratio(dark_text, sky_start) >= 7.0  # AAA
        # btn-smart-run text contrast
        assert get_contrast_ratio(dark_text, emerald_start) >= 7.0  # AAA

    def test_no_pure_white_on_pure_black_halating_combos(self, css_content):
        # Canvas background is #080c14 or #080b11 (not #000000) and primary text is #f8fafc or #f0f6fc (not #ffffff)
        assert "background-color: var(--bg-canvas);" in css_content
        assert "--bg-canvas: #080c14;" in css_content or "--bg-canvas: #080b11;" in css_content
        assert "--text-primary: #f8fafc;" in css_content or "--text-primary: #f0f6fc;" in css_content

class TestResponsiveLayoutRules:
    def test_media_queries_hierarchy(self, css_content):
        assert "@media (max-width: 1200px)" in css_content
        assert "@media (max-width: 900px)" in css_content
        assert "@media (max-width: 600px)" in css_content

    def test_1200px_breakpoint_rules(self, css_content):
        idx_1200 = css_content.find("@media (max-width: 1200px)")
        assert idx_1200 != -1
        section_1200 = css_content[idx_1200:idx_1200+400]
        assert "grid-template-columns: 1fr" in section_1200
        assert "flex-direction: column" in section_1200

    def test_900px_breakpoint_rules(self, css_content):
        idx_900 = css_content.find("@media (max-width: 900px)")
        assert idx_900 != -1
        section_900 = css_content[idx_900:idx_900+400]
        assert ".app-header" in section_900
        assert "flex-direction: column" in section_900

    def test_600px_breakpoint_rules(self, css_content):
        idx_600 = css_content.find("@media (max-width: 600px)")
        assert idx_600 != -1
        section_600 = css_content[idx_600:idx_600+400]
        assert ".smart-numeric-inputs" in section_600
        assert "grid-template-columns: repeat(2, 1fr)" in section_600
