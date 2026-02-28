"""
tests/test_migration_property.py

Sprint 91 — T2 migration verification tests.
Checks that the three property/tool templates comply with the Obsidian design system
(head_obsidian.html, token CSS vars, no legacy font vars).
"""
import os
import re
import pytest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEMPLATES = {
    "report": "web/templates/report.html",
    "station_predictor": "web/templates/tools/station_predictor.html",
    "stuck_permit": "web/templates/tools/stuck_permit.html",
}


def _read(rel_path: str) -> str:
    full = os.path.join(REPO_ROOT, rel_path)
    with open(full, "r", encoding="utf-8") as f:
        return f.read()


# ────────────────────────────────────────────────────────────────────────────
# 1. Templates exist and are non-empty
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,path", list(TEMPLATES.items()))
def test_template_exists_and_nonempty(name, path):
    """Each migrated template file exists and contains HTML."""
    full_path = os.path.join(REPO_ROOT, path)
    assert os.path.isfile(full_path), f"Template not found: {path}"
    content = _read(path)
    assert len(content) > 500, f"{name}: template seems empty or truncated"
    assert "<!DOCTYPE html>" in content or "{% include" in content, \
        f"{name}: does not appear to be a valid HTML template"


# ────────────────────────────────────────────────────────────────────────────
# 2. All templates include head_obsidian.html
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,path", list(TEMPLATES.items()))
def test_includes_head_obsidian(name, path):
    """Each template must include the shared Obsidian head fragment."""
    content = _read(path)
    assert 'fragments/head_obsidian.html' in content, \
        f"{name}: missing include for fragments/head_obsidian.html"


# ────────────────────────────────────────────────────────────────────────────
# 3. No legacy font vars (--font-body, --font-display)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,path", list(TEMPLATES.items()))
def test_no_legacy_font_vars(name, path):
    """Templates must not use --font-body or --font-display (legacy design-system.css vars).
    The token system uses --mono and --sans exclusively."""
    content = _read(path)
    bad_vars = ["--font-body", "--font-display"]
    for var in bad_vars:
        assert var not in content, \
            f"{name}: found legacy font var '{var}' — use --mono or --sans instead"


# ────────────────────────────────────────────────────────────────────────────
# 4. Token font vars are used correctly
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,path", list(TEMPLATES.items()))
def test_uses_token_font_vars(name, path):
    """Templates with font-family declarations must use var(--mono) or var(--sans)."""
    content = _read(path)
    # Find all font-family declarations
    font_decls = re.findall(r"font-family\s*:\s*([^;}{]+)", content)
    for decl in font_decls:
        decl = decl.strip()
        # Must contain a token var reference
        assert "var(--mono)" in decl or "var(--sans)" in decl or "--mono" in decl or "--sans" in decl, \
            f"{name}: font-family declaration not using token var: '{decl[:80]}'"


# ────────────────────────────────────────────────────────────────────────────
# 5. No raw hex colors outside the allowed palette
# ────────────────────────────────────────────────────────────────────────────

ALLOWED_HEX = {
    "#0a0a0f", "#12121a", "#1a1a26",
    "#5eead4",
    "#34d399", "#fbbf24", "#f87171", "#60a5fa",
    "#22c55e", "#f59e0b", "#ef4444",
    "#fff", "#000",
}

@pytest.mark.parametrize("name,path", list(TEMPLATES.items()))
def test_no_non_token_hex_colors(name, path):
    """Templates must not use hex colors outside the design token palette."""
    content = _read(path)
    hex_re = re.compile(r"#([0-9a-fA-F]{3,8})\b")
    violations = []
    for i, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("{#") or stripped.startswith("<!--") or stripped.startswith("//"):
            continue
        for match in hex_re.finditer(line):
            hex_val = f"#{match.group(1).lower()}"
            if hex_val in ALLOWED_HEX:
                continue
            context = line[max(0, match.start() - 30):match.end() + 10]
            if "var(--" in context:
                continue
            if "stroke=" in context or "fill=" in context or "stop-color=" in context:
                continue
            if "data:image" in line:
                continue
            violations.append(f"Line {i}: {hex_val}")
    assert not violations, \
        f"{name}: non-token hex colors found:\n" + "\n".join(violations[:10])


# ────────────────────────────────────────────────────────────────────────────
# 6. report.html has report-specific components
# ────────────────────────────────────────────────────────────────────────────

def test_report_has_intel_grid():
    """report.html should have the intel-grid summary stats section."""
    content = _read(TEMPLATES["report"])
    assert "intel-grid" in content, "report.html missing intel-grid component"
    assert "intel-card" in content, "report.html missing intel-card component"


def test_report_has_risk_assessment():
    """report.html should have the risk assessment section."""
    content = _read(TEMPLATES["report"])
    assert "risk-item" in content, "report.html missing risk-item component"
    assert "severity-chip" in content, "report.html missing severity-chip component"


def test_report_has_permit_list():
    """report.html should have the permit list section."""
    content = _read(TEMPLATES["report"])
    assert "permit-item" in content, "report.html missing permit-item component"
    assert "status-chip" in content, "report.html missing status-chip component"


# ────────────────────────────────────────────────────────────────────────────
# 7. Tool templates have correct structure
# ────────────────────────────────────────────────────────────────────────────

def test_station_predictor_has_form():
    """station_predictor.html should have a permit input and predict button."""
    content = _read(TEMPLATES["station_predictor"])
    assert "permit-number-input" in content, "station_predictor.html missing permit number input"
    assert "predict-btn" in content or "predict_btn" in content or "Predict" in content, \
        "station_predictor.html missing predict button"


def test_stuck_permit_has_form():
    """stuck_permit.html should have a permit input and diagnose button."""
    content = _read(TEMPLATES["stuck_permit"])
    assert "permit-number-input" in content, "stuck_permit.html missing permit number input"
    assert "diagnose" in content.lower(), "stuck_permit.html missing diagnose element"


def test_stuck_permit_no_external_htmx():
    """stuck_permit.html must not load HTMX from an external CDN — use local /static/htmx.min.js."""
    content = _read(TEMPLATES["stuck_permit"])
    assert "unpkg.com/htmx" not in content, \
        "stuck_permit.html loads HTMX from external CDN — use /static/htmx.min.js instead"
    # Verify local HTMX is loaded
    assert "htmx.min.js" in content, \
        "stuck_permit.html should load local /static/htmx.min.js"


# ────────────────────────────────────────────────────────────────────────────
# 8. Templates use obs-container for layout
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,path", list(TEMPLATES.items()))
def test_uses_obs_container(name, path):
    """Each template should use .obs-container for page layout."""
    content = _read(path)
    assert "obs-container" in content, \
        f"{name}: missing obs-container class — use for page layout"


# ────────────────────────────────────────────────────────────────────────────
# 9. No inline style attributes with hardcoded pixel font sizes
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,path", list(TEMPLATES.items()))
def test_no_hardcoded_px_font_sizes_in_inline_styles(name, path):
    """Inline styles should not use raw pixel font-sizes — use token vars."""
    content = _read(path)
    # Find inline style attributes that use font-size with px values but NOT token vars
    inline_style_re = re.compile(r'style\s*=\s*"([^"]*)"')
    violations = []
    for i, line in enumerate(content.split("\n"), 1):
        for match in inline_style_re.finditer(line):
            style_val = match.group(1)
            if "font-size" in style_val and "px" in style_val and "var(--" not in style_val:
                violations.append(f"Line {i}: {style_val[:100]}")
    assert not violations, \
        f"{name}: inline styles with hardcoded px font-size (use var(--text-*)):\n" + "\n".join(violations[:5])


# ────────────────────────────────────────────────────────────────────────────
# 10. Templates have nonce on all script and style tags
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,path", list(TEMPLATES.items()))
def test_script_and_style_tags_have_nonce(name, path):
    """All <script> and <style> tags in the template itself must have nonce attribute."""
    content = _read(path)
    # Check <script> tags (excluding head_obsidian include and external CDN scripts that already have nonce)
    script_re = re.compile(r"<script\b([^>]*)>", re.IGNORECASE)
    style_re = re.compile(r"<style\b([^>]*)>", re.IGNORECASE)
    violations = []
    for match in script_re.finditer(content):
        attrs = match.group(1)
        if "nonce" not in attrs:
            violations.append(f"<script> missing nonce: {attrs[:80]}")
    for match in style_re.finditer(content):
        attrs = match.group(1)
        if "nonce" not in attrs:
            violations.append(f"<style> missing nonce: {attrs[:80]}")
    assert not violations, \
        f"{name}: script/style tags missing nonce:\n" + "\n".join(violations[:5])
