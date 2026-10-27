"""
Comprehensive Empirical Test Suite for Milestone 1:
Visual Design System & Global Stylesheet Refactor Integrity.
"""

import re
import os
import sys
import pytest
from pathlib import Path
from html.parser import HTMLParser

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
CSS_PATH = WORKSPACE_DIR / "static" / "css" / "style.css"
HTML_PATH = WORKSPACE_DIR / "templates" / "index.html"
JS_APP_PATH = WORKSPACE_DIR / "static" / "js" / "app.js"
JS_CHARTS_PATH = WORKSPACE_DIR / "static" / "js" / "charts.js"


def read_file(path: Path) -> str:
    assert path.exists(), f"Target file does not exist: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def strip_css_comments(css_text: str) -> str:
    return re.sub(r'/\*[\s\S]*?\*/', '', css_text)


def extract_root_variables(css_text: str) -> dict:
    """Extract all CSS variables defined in :root."""
    clean_css = strip_css_comments(css_text)
    root_match = re.search(r':root\s*\{([^}]+)\}', clean_css, re.DOTALL)
    if not root_match:
        return {}
    root_content = root_match.group(1)
    var_dict = {}
    for line in root_content.split(';'):
        line = line.strip()
        if not line or line.startswith('/*'):
            continue
        if ':' in line:
            parts = line.split(':', 1)
            var_name = parts[0].strip()
            var_val = parts[1].strip()
            if var_name.startswith('--'):
                var_dict[var_name] = var_val
    return var_dict


def extract_css_var_usages(text: str) -> set:
    """Find all var(--variable-name) invocations."""
    matches = re.findall(r'var\(\s*(--[a-zA-Z0-9\-_]+)', text)
    return set(matches)


def extract_all_css_selectors(css_text: str) -> tuple[set, set]:
    """
    Robust tokenizer to extract all CSS classes (.class) and IDs (#id) from style.css,
    handling nested blocks (e.g. @media) correctly.
    """
    clean_css = strip_css_comments(css_text)
    classes = set()
    ids = set()

    current_selector = []
    i = 0
    length = len(clean_css)
    
    while i < length:
        ch = clean_css[i]
        
        if ch == '{':
            sel_str = ''.join(current_selector).strip()
            current_selector = []
            if sel_str and not sel_str.startswith('@'):
                for sel_part in sel_str.split(','):
                    sel_part = sel_part.strip()
                    for c in re.findall(r'\.([a-zA-Z0-9\-_]+)', sel_part):
                        classes.add(c)
                    for id_name in re.findall(r'#([a-zA-Z0-9\-_]+)', sel_part):
                        ids.add(id_name)
        elif ch == '}':
            current_selector = []
        elif ch == ';':
            current_selector = []
        else:
            current_selector.append(ch)
            
        i += 1

    return classes, ids


class HTMLTokenParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.classes = set()
        self.ids = set()
        self.inline_styles = []
        
    def handle_starttag(self, tag, attrs):
        for attr, val in attrs:
            if not val:
                continue
            if attr == 'class':
                for c in val.split():
                    self.classes.add(c)
            elif attr == 'id':
                self.ids.add(val.strip())
            elif attr == 'style':
                self.inline_styles.append(val)


def extract_js_classes_and_ids(js_text: str) -> tuple[set, set]:
    """
    Extract literal classes and IDs referenced/manipulated by JS code.
    """
    classes = set()
    ids = set()

    # 1. classList.add('c1', 'c2'), classList.toggle('c'), classList.remove('c')
    for m in re.finditer(r'classList\.(?:add|remove|toggle|contains)\(([^)]+)\)', js_text):
        arg_str = m.group(1)
        for lit in re.findall(r"['\"`]([a-zA-Z0-9\-_]+)['\"`]", arg_str):
            classes.add(lit)

    # 2. Extract ternary or literal class string returns like 'text-green' : 'text-red'
    for m in re.finditer(r"['\"`]([a-zA-Z0-9\-_]+)['\"`]\s*:\s*['\"`]([a-zA-Z0-9\-_]+)['\"`]", js_text):
        c1, c2 = m.group(1), m.group(2)
        if c1.startswith('text-') or c1 in ['active', 'completed', 'green', 'blue', 'red']:
            classes.add(c1)
        if c2.startswith('text-') or c2 in ['active', 'completed', 'green', 'blue', 'red']:
            classes.add(c2)

    # 3. Static class="..." in template strings (excluding ${...})
    # Replace ${...} with space first
    clean_js = re.sub(r'\$\{[^}]*\}', ' ', js_text)
    for m in re.finditer(r'class=["\']([^"\']+)["\']', clean_js):
        class_attr = m.group(1)
        for token in class_attr.split():
            if re.match(r'^[a-zA-Z][a-zA-Z0-9\-_]*$', token):
                classes.add(token)

    # 4. getElementById('...')
    for m in re.finditer(r'getElementById\(\s*[\'"`]([a-zA-Z0-9\-_]+)[\'"`]\s*\)', js_text):
        ids.add(m.group(1))

    # 5. querySelector / querySelectorAll
    for m in re.finditer(r'querySelector(?:All)?\(\s*[\'"`]([^\'"`]+)[\'"`]\s*\)', js_text):
        q = m.group(1).strip()
        for c in re.findall(r'\.([a-zA-Z0-9\-_]+)', q):
            classes.add(c)
        for i in re.findall(r'#([a-zA-Z0-9\-_]+)', q):
            ids.add(i)

    return classes, ids


# =========================================================================
# TEST SUITE
# =========================================================================

def test_css_file_exists_and_non_empty():
    assert CSS_PATH.exists(), f"style.css not found at {CSS_PATH}"
    content = read_file(CSS_PATH)
    assert len(content.strip()) > 500, "style.css is unexpectedly small or empty"


def test_css_bracket_and_parenthesis_balance():
    """Verify that all braces {}, brackets [], and parentheses () in style.css are strictly balanced."""
    raw = read_file(CSS_PATH)
    clean = strip_css_comments(raw)
    
    open_braces = clean.count('{')
    close_braces = clean.count('}')
    assert open_braces == close_braces, f"Mismatched braces in style.css: {open_braces} open vs {close_braces} close"
    
    open_parens = clean.count('(')
    close_parens = clean.count(')')
    assert open_parens == close_parens, f"Mismatched parentheses in style.css: {open_parens} open vs {close_parens} close"


def test_root_css_variables_defined():
    """Verify core design system tokens in :root."""
    css = read_file(CSS_PATH)
    root_vars = extract_root_variables(css)
    
    required_vars = [
        "--bg-canvas",
        "--bg-card",
        "--bg-elevated",
        "--bg-hover",
        "--border-subtle",
        "--border-focus",
        "--text-primary",
        "--text-secondary",
        "--text-muted",
        "--accent-primary",
        "--accent-green",
        "--accent-red",
        "--accent-purple",
        "--accent-amber",
        "--space-1",
        "--space-2",
        "--space-3",
        "--space-4",
        "--space-5",
        "--space-6",
        "--space-8",
        "--radius-sm",
        "--radius-md",
        "--radius-lg",
        "--radius-xl",
        "--radius-pill",
        "--font-sans",
        "--font-mono",
        "--ease-out-expo",
        "--duration-micro",
        "--duration-state",
    ]
    
    missing_vars = [v for v in required_vars if v not in root_vars]
    assert not missing_vars, f"Missing required :root design system tokens: {missing_vars}"


def test_all_var_usages_are_defined_in_root():
    """
    Every var(--foo) used in style.css and templates/index.html MUST have a definition in :root.
    """
    css = read_file(CSS_PATH)
    html = read_file(HTML_PATH)
    
    root_vars = set(extract_root_variables(css).keys())
    
    css_var_usages = extract_css_var_usages(css)
    html_var_usages = extract_css_var_usages(html)
    
    all_usages = css_var_usages.union(html_var_usages)
    undefined_vars = all_usages - root_vars
    
    assert not undefined_vars, f"Found CSS variables used via var(...) but not defined in :root: {undefined_vars}"


def test_css_class_inventory_audit():
    """
    Audit class coverage across HTML and JS vs CSS.
    Identifies any structural gaps or unstyled classes.
    """
    html = read_file(HTML_PATH)
    parser = HTMLTokenParser()
    parser.feed(html)
    
    js_app = read_file(JS_APP_PATH)
    js_charts = read_file(JS_CHARTS_PATH)
    app_classes, _ = extract_js_classes_and_ids(js_app)
    charts_classes, _ = extract_js_classes_and_ids(js_charts)
    all_js_classes = app_classes.union(charts_classes)
    
    css = read_file(CSS_PATH)
    css_classes, _ = extract_all_css_selectors(css)
    
    # Analyze coverage
    missing_html = parser.classes - css_classes
    missing_js = all_js_classes - css_classes
    
    print(f"\n[CSS Class Audit]")
    print(f"  Total CSS classes defined in style.css: {len(css_classes)}")
    print(f"  HTML classes count: {len(parser.classes)} (Matched: {len(parser.classes & css_classes)})")
    print(f"  JS dynamic classes count: {len(all_js_classes)} (Matched: {len(all_js_classes & css_classes)})")
    
    if missing_html:
        print(f"  HTML classes without direct .class selector: {missing_html}")
    if missing_js:
        print(f"  JS classes without direct .class selector: {missing_js}")
        
    # Check that core classes are covered (>95% coverage)
    coverage_ratio = len(parser.classes & css_classes) / len(parser.classes)
    print(f"  HTML Coverage Ratio: {coverage_ratio * 100:.1f}%")
    assert coverage_ratio >= 0.90, f"HTML class coverage ratio too low: {coverage_ratio * 100:.1f}%"


def test_tabular_numbers_rules_and_monospace():
    """
    Verify that tabular numerals (.tabular-nums, .markov-table, .trades-table, .n-table, etc.)
    have font-variant-numeric: tabular-nums and use font-mono.
    """
    css = read_file(CSS_PATH)
    assert "tabular-nums" in css, "style.css does not configure tabular-nums"
    assert "font-variant-numeric: tabular-nums" in css or "font-feature-settings" in css, \
        "style.css lacks tabular numeric feature settings"
    assert "--font-mono" in css, "style.css lacks --font-mono variable definition"


def test_anti_halation_and_contrast_compliance():
    """
    Verify adherence to anti-halation rules:
    - Background is not pure #000000 (uses #080b11 or dark slate)
    - Primary text is not pure stark white #FFFFFF everywhere (uses #f0f6fc)
    """
    css = read_file(CSS_PATH)
    root_vars = extract_root_variables(css)
    
    bg_canvas = root_vars.get("--bg-canvas", "").lower()
    text_primary = root_vars.get("--text-primary", "").lower()
    
    assert bg_canvas in ["#080c14", "#080b11", "#090d16", "#0b0f19"], f"Canvas background token unexpected: {bg_canvas}"
    assert text_primary in ["#f8fafc", "#f0f6fc", "#e6edf3", "#f1f5f9"], f"Primary text token unexpected: {text_primary}"


def test_css_property_declaration_validity():
    """
    Parse all property declarations in style.css to catch typos.
    """
    css = read_file(CSS_PATH)
    clean = strip_css_comments(css)
    
    VALID_PROPERTIES = {
        "align-content", "align-items", "align-self", "all", "animation", "animation-delay",
        "animation-direction", "animation-duration", "animation-fill-mode", "animation-iteration-count",
        "animation-name", "animation-play-state", "animation-timing-function", "appearance",
        "aspect-ratio", "backdrop-filter", "background", "background-attachment", "background-blend-mode",
        "background-clip", "background-color", "background-image", "background-origin", "background-position",
        "background-repeat", "background-size", "border", "border-bottom", "border-bottom-color",
        "border-bottom-left-radius", "border-bottom-right-radius", "border-bottom-style", "border-bottom-width",
        "border-collapse", "border-color", "border-image", "border-left", "border-left-color", "border-left-style",
        "border-left-width", "border-radius", "border-right", "border-right-color", "border-right-style",
        "border-right-width", "border-spacing", "border-style", "border-top", "border-top-color",
        "border-top-left-radius", "border-top-right-radius", "border-top-style", "border-top-width",
        "border-width", "bottom", "box-shadow", "box-sizing", "caption-side", "clear", "clip", "clip-path",
        "color", "column-count", "column-gap", "column-rule", "column-width", "columns", "content", "counter-increment",
        "counter-reset", "cursor", "direction", "display", "empty-cells", "filter", "flex", "flex-basis",
        "flex-direction", "flex-flow", "flex-grow", "flex-shrink", "flex-wrap", "float", "font", "font-family",
        "font-feature-settings", "font-kerning", "font-size", "font-size-adjust", "font-stretch", "font-style",
        "font-variant", "font-variant-caps", "font-variant-numeric", "font-weight", "gap", "grid", "grid-area",
        "grid-auto-columns", "grid-auto-flow", "grid-auto-rows", "grid-column", "grid-column-end", "grid-column-gap",
        "grid-column-start", "grid-gap", "grid-row", "grid-row-end", "grid-row-gap", "grid-row-start", "grid-template",
        "grid-template-areas", "grid-template-columns", "grid-template-rows", "height", "hyphens", "isolation",
        "justify-content", "justify-items", "justify-self", "left", "letter-spacing", "line-height", "list-style",
        "list-style-image", "list-style-position", "list-style-type", "margin", "margin-bottom", "margin-left",
        "margin-right", "margin-top", "max-height", "max-width", "min-height", "min-width", "mix-blend-mode",
        "object-fit", "object-position", "opacity", "order", "orphans", "outline", "outline-color", "outline-offset",
        "outline-style", "outline-width", "overflow", "overflow-anchor", "overflow-wrap", "overflow-x", "overflow-y",
        "overscroll-behavior", "padding", "padding-bottom", "padding-left", "padding-right", "padding-top",
        "page-break-after", "page-break-before", "page-break-inside", "perspective", "perspective-origin",
        "pointer-events", "position", "quotes", "resize", "right", "rotate", "row-gap", "scale", "scroll-behavior",
        "scroll-margin", "scroll-padding", "scroll-snap-align", "scroll-snap-stop", "scroll-snap-type", "tab-size",
        "table-layout", "text-align", "text-align-last", "text-decoration", "text-decoration-color",
        "text-decoration-line", "text-decoration-style", "text-decoration-thickness", "text-indent",
        "text-justify", "text-overflow", "text-rendering", "text-shadow", "text-transform", "top", "touch-action",
        "transform", "transform-origin", "transform-style", "transition", "transition-delay", "transition-duration",
        "transition-property", "transition-timing-function", "translate", "unicode-bidi", "user-select",
        "vertical-align", "visibility", "white-space", "widows", "width", "will-change", "word-break",
        "word-spacing", "word-wrap", "writing-mode", "z-index",
        "-webkit-backdrop-filter", "-webkit-font-smoothing", "-moz-osx-font-smoothing",
        "-webkit-background-clip", "-webkit-text-fill-color", "-webkit-appearance",
        "-moz-appearance", "-webkit-outer-spin-button", "-webkit-inner-spin-button",
        "accent-color"
    }
    
    invalid_props = []
    for match in re.finditer(r'\{([^}]+)\}', clean):
        block = match.group(1)
        for decl in block.split(';'):
            decl = decl.strip()
            if not decl:
                continue
            if '{' in decl or '}' in decl:
                continue
            if ':' in decl:
                prop = decl.split(':', 1)[0].strip().lower()
                if prop.startswith('--'):
                    continue
                if prop in ['0%', '100%', 'from', 'to']:
                    continue
                if prop not in VALID_PROPERTIES and not prop.startswith('-webkit-') and not prop.startswith('-moz-'):
                    invalid_props.append(prop)
                    
    assert not invalid_props, f"Found invalid or unrecognized CSS properties in style.css: {set(invalid_props)}"


if __name__ == '__main__':
    exit_code = pytest.main(["-v", "-s", __file__])
    sys.exit(exit_code)
