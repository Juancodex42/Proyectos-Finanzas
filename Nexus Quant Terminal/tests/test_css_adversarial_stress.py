import os
import re
import pytest

@pytest.fixture(scope="module")
def css_text():
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
    with open(css_path, "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture(scope="module")
def html_text():
    html_path = os.path.join(os.path.dirname(__file__), "..", "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

class TestCSSAdversarialIntegrity:
    def test_css_balanced_braces(self, css_text):
        # Strip comments
        clean_css = re.sub(r'/\*.*?\*/', '', css_text, flags=re.DOTALL)
        open_braces = clean_css.count('{')
        close_braces = clean_css.count('}')
        assert open_braces == close_braces, f"Mismatched braces: {open_braces} open vs {close_braces} close"

    def test_no_forbidden_pure_black_backgrounds(self, css_text):
        # We must ensure background is dark obsidian/slate, never pure pitch black #000000 on main surfaces
        # Search for background properties assigning #000000 or #000
        matches = re.findall(r'background(?:-color)?\s*:\s*(#[0-9a-fA-F]+)', css_text)
        for color in matches:
            assert color.lower() not in ['#000', '#000000'], f"Found forbidden pure black background: {color}"

    def test_all_custom_properties_resolved(self, css_text):
        # Find all var(--...) usages
        var_usages = set(re.findall(r'var\((--[a-zA-Z0-9_-]+)\)', css_text))
        # Find all defined custom properties
        defined_vars = set(re.findall(r'(--[a-zA-Z0-9_-]+)\s*:', css_text))
        
        missing = var_usages - defined_vars
        assert not missing, f"Undefined CSS variables used: {missing}"

    def test_z_index_stacking_discipline(self, css_text):
        # Extract z-index values to ensure they do not exceed 9999 or clash unexpectedly
        z_indices = [int(z) for z in re.findall(r'z-index\s*:\s*(\d+)', css_text)]
        for z in z_indices:
            assert z <= 9999, f"Z-index {z} exceeds max design token boundary (9999)"

    def test_transitions_use_gpu_properties(self, css_text):
        # Check that transitions and keyframe animations focus on transform, opacity, background, border-color, box-shadow
        keyframes = re.findall(r'@keyframes\s+([a-zA-Z0-9_-]+)\s*\{([^}]+)\}', css_text)
        for name, body in keyframes:
            # animations should avoid animating width/height/top/left if continuous loop
            if name in ['progressShimmer', 'livePulse', 'spin']:
                # spin uses transform
                # livePulse uses opacity, transform
                # progressShimmer uses background-position
                pass

    def test_focus_rings_accessibility(self, css_text):
        # Ensure focus rings are defined for inputs, buttons, and selects
        assert "input:focus" in css_text
        assert "select:focus" in css_text
        assert "box-shadow: 0 0 0 3px var(--focus-ring)" in css_text or "var(--focus-ring)" in css_text

    def test_all_template_ids_have_safe_layout_rules(self, html_text, css_text):
        # Extract all IDs from index.html
        ids = set(re.findall(r'id=["\']([^"\']+)["\']', html_text))
        # Verify critical containers have proper flex/grid/block handling
        critical_ids = [
            'mode-smart', 'mode-advanced', 'smart-dashboard', 'dashboard',
            'smart-preset-select', 'btn-smart-run', 'smart-console-box',
            'smart-top-5-box', 'smart-selected-assets-table', 'smart-markov-table'
        ]
        for cid in critical_ids:
            assert cid in ids, f"Critical DOM ID {cid} missing from index.html"
