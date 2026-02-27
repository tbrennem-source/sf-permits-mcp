"""Integration tests for scripts/design_lint.py.

Tests the individual check functions and scoring logic directly,
using tempfile-backed templates so no real filesystem state is needed.
"""
import os
import sys
import tempfile
import pytest

# Ensure scripts/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from design_lint import (
    check_hex_colors,
    check_font_families,
    check_inline_styles,
    check_tertiary_misuse,
    lint_file,
    score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_template(content: str) -> str:
    """Write content to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    )
    f.write(content)
    f.close()
    return f.name


def _lint(content: str):
    """Lint inline content; return (violations, score)."""
    path = _make_template(content)
    try:
        violations = lint_file(path)
        s = score(violations)
        return violations, s
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# test_clean_template_scores_5
# ---------------------------------------------------------------------------

def test_clean_template_scores_5():
    """A template that uses only token classes and token vars should score 5."""
    content = """<!DOCTYPE html>
<html>
<head>
  <style>
    .obs-container { color: var(--text-primary); font-family: var(--mono); }
  </style>
</head>
<body>
  <div class="glass-card">
    <span class="status-dot status-dot--green"></span>
    <a class="ghost-cta" href="/search">Search</a>
    <table class="obs-table"><tr><td class="obs-table__mono">123</td></tr></table>
  </div>
</body>
</html>"""
    violations, s = _lint(content)
    assert violations == [], f"Expected no violations, got: {violations}"
    assert s == 5


# ---------------------------------------------------------------------------
# test_non_token_hex_detected
# ---------------------------------------------------------------------------

def test_non_token_hex_detected():
    """A template with a non-token hex (#ff0000) should produce a violation."""
    content = """<style>
  .danger { color: #ff0000; }
</style>
<div class="danger">text</div>"""
    violations, _ = _lint(content)
    hex_violations = [v for v in violations if "ff0000" in v["issue"].lower()]
    assert len(hex_violations) >= 1, "Expected violation for #ff0000"
    # Line number should be non-zero
    assert hex_violations[0]["line"] > 0


def test_non_token_hex_has_correct_line_number():
    """Violation line number should match the actual line with the hex color."""
    content = "<!-- ok -->\n<!-- ok -->\n<style>.x { color: #abcdef; }</style>\n"
    path = _make_template(content)
    try:
        lines = content.split("\n")
        violations = check_hex_colors(path, content, lines)
        assert any(v["line"] == 3 for v in violations), (
            f"Expected violation on line 3, got lines: {[v['line'] for v in violations]}"
        )
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# test_non_token_font_detected
# ---------------------------------------------------------------------------

def test_non_token_font_detected():
    """A template with font-family: Arial should produce a high severity violation."""
    content = """<style>
  body { font-family: Arial, sans-serif; }
</style>"""
    violations, _ = _lint(content)
    font_violations = [v for v in violations if "font-family" in v["issue"].lower()]
    assert len(font_violations) >= 1, "Expected font-family violation for Arial"
    assert font_violations[0]["severity"] == "high"


def test_font_family_violation_check_function():
    """check_font_families returns high severity for non-token font-family."""
    content = "p { font-family: Georgia, serif; }"
    lines = content.split("\n")
    violations = check_font_families("test.html", content, lines)
    assert len(violations) == 1
    assert violations[0]["severity"] == "high"
    assert "Georgia" in violations[0]["issue"]


# ---------------------------------------------------------------------------
# test_tertiary_on_interactive_detected
# ---------------------------------------------------------------------------

def test_tertiary_on_interactive_detected():
    """Using --text-tertiary near an <a> tag should produce a violation."""
    content = """<div>
  <a href="/path" style="color: var(--text-tertiary)">click here</a>
</div>"""
    violations, _ = _lint(content)
    tertiary_violations = [v for v in violations if "tertiary" in v["issue"].lower()]
    assert len(tertiary_violations) >= 1, (
        "Expected violation for --text-tertiary near interactive element"
    )
    assert tertiary_violations[0]["severity"] == "high"


def test_tertiary_standalone_not_flagged():
    """Using --text-tertiary in a non-interactive context should not trigger."""
    content = """<style>
  .caption { color: var(--text-tertiary); }
</style>
<p class="caption">Just a label, no links nearby.</p>"""
    violations, _ = _lint(content)
    tertiary_violations = [v for v in violations if "tertiary" in v["issue"].lower()]
    assert tertiary_violations == [], (
        "Should NOT flag --text-tertiary when no interactive element nearby"
    )


# ---------------------------------------------------------------------------
# test_inline_style_color_detected
# ---------------------------------------------------------------------------

def test_inline_style_color_detected():
    """An inline style with color: red (no var()) should produce a violation."""
    content = '<div style="color: red; padding: 4px;">text</div>'
    violations, _ = _lint(content)
    inline_violations = [v for v in violations if "inline style" in v["issue"].lower()]
    assert len(inline_violations) >= 1, "Expected inline style color violation"


def test_inline_style_with_var_not_flagged():
    """An inline style using var(--text-primary) should NOT be flagged."""
    content = '<div style="color: var(--text-primary);">text</div>'
    violations, _ = _lint(content)
    inline_violations = [v for v in violations if "inline style" in v["issue"].lower()]
    assert inline_violations == [], (
        "Should NOT flag inline style when it uses var() token"
    )


# ---------------------------------------------------------------------------
# test_token_vars_allowed
# ---------------------------------------------------------------------------

def test_token_vars_allowed():
    """Templates using var(--accent), var(--text-primary) should have no violations."""
    content = """<style>
  .header {
    color: var(--text-primary);
    background: var(--surface-glass);
    border-color: var(--accent);
    font-family: var(--mono);
  }
</style>
<div class="obs-container">
  <h1 style="color: var(--accent);">Title</h1>
</div>"""
    violations, s = _lint(content)
    assert violations == [], f"Expected no violations when using token vars, got: {violations}"
    assert s == 5


# ---------------------------------------------------------------------------
# test_svg_hex_not_flagged
# ---------------------------------------------------------------------------

def test_svg_hex_not_flagged():
    """Hex colors inside SVG stroke= or fill= attributes should not be flagged."""
    content = """<svg width="24" height="24" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" stroke="#ff0000" fill="#00ff00" stroke-width="2"/>
  <path d="M5 12h14" stroke="#1234ab"/>
</svg>"""
    lines = content.split("\n")
    path = _make_template(content)
    try:
        violations = check_hex_colors(path, content, lines)
        assert violations == [], (
            f"SVG stroke/fill hex should NOT be flagged, got: {violations}"
        )
    finally:
        os.unlink(path)


def test_stop_color_not_flagged():
    """Hex in stop-color= SVG gradient attribute should not be flagged."""
    content = '<stop offset="0%" stop-color="#ff3300"/>'
    lines = content.split("\n")
    path = _make_template(content)
    try:
        violations = check_hex_colors(path, content, lines)
        assert violations == [], (
            f"stop-color hex should not be flagged, got: {violations}"
        )
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# test_changed_mode_no_templates
# ---------------------------------------------------------------------------

def test_score_no_violations():
    """score([]) returns 5."""
    assert score([]) == 5


def test_score_one_high_violation():
    """1 high violation → weighted=3 → ≤8 → score 3."""
    violations = [{"severity": "high"}]
    # weighted = 1*3 = 3, 3 ≤ 8 → score 3
    assert score(violations) == 3


def test_score_threshold_boundaries():
    """Weighted scoring thresholds: ≤2→4, ≤8→3, ≤20→2, >20→1."""
    # 1 low = 1 weighted → ≤2 → score 4
    assert score([{"severity": "low"}]) == 4
    # 1 medium = 2 weighted → ≤2 → score 4
    assert score([{"severity": "medium"}]) == 4
    # 1 high = 3 weighted → ≤8 → score 3
    assert score([{"severity": "high"}]) == 3
    # 3 high = 9 weighted → ≤20 → score 2
    assert score([{"severity": "high"}] * 3) == 2
    # 7 high = 21 weighted → >20 → score 1
    assert score([{"severity": "high"}] * 7) == 1


def test_score_medium_and_low():
    """Medium and low violations score appropriately."""
    # 1 low = 1 weighted → ≤2 → score 4
    assert score([{"severity": "low"}]) == 4
    # 2 medium = 4 weighted → ≤8 → score 3
    violations = [{"severity": "medium"}, {"severity": "medium"}]
    assert score(violations) == 3


# ---------------------------------------------------------------------------
# Allowed palette hex values should pass
# ---------------------------------------------------------------------------

def test_allowed_hex_values_pass():
    """Token palette colors should NOT be flagged."""
    # Test a few from ALLOWED_HEX
    for hex_color in ["#0a0a0f", "#5eead4", "#34d399", "#fbbf24", "#fff"]:
        content = f"<style>.x {{ color: {hex_color}; }}</style>"
        lines = content.split("\n")
        path = _make_template(content)
        try:
            violations = check_hex_colors(path, content, lines)
            assert violations == [], (
                f"Palette color {hex_color} should not be flagged, got: {violations}"
            )
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Comment lines should not be flagged
# ---------------------------------------------------------------------------

def test_jinja_comment_skipped():
    """Lines starting with {# should be skipped by the hex checker."""
    content = "{# This mentions #ff1234 but is a comment #}"
    lines = content.split("\n")
    path = _make_template(content)
    try:
        violations = check_hex_colors(path, content, lines)
        assert violations == [], (
            f"Jinja comment line should be skipped, got: {violations}"
        )
    finally:
        os.unlink(path)


def test_html_comment_skipped():
    """Lines starting with <!-- should be skipped by the hex checker."""
    content = "<!-- #abcdef is mentioned in this HTML comment -->"
    lines = content.split("\n")
    path = _make_template(content)
    try:
        violations = check_hex_colors(path, content, lines)
        assert violations == [], (
            f"HTML comment line should be skipped, got: {violations}"
        )
    finally:
        os.unlink(path)
