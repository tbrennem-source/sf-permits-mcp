"""
Tests for the tier gate overlay UI components.

Covers:
  - tier_gate_overlay.html Jinja2 template (conditional rendering)
  - web/static/css/tier-gate.css (blur, mobile breakpoint)
  - web/static/js/tier-gate.js (DOM manipulation class)
"""

import os
import pytest
from jinja2 import Environment, FileSystemLoader, Undefined


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(REPO_ROOT, "web", "templates")
CSS_PATH = os.path.join(REPO_ROOT, "web", "static", "css", "tier-gate.css")
JS_PATH = os.path.join(REPO_ROOT, "web", "static", "js", "tier-gate.js")
OVERLAY_TEMPLATE = "components/tier_gate_overlay.html"


def get_jinja_env():
    """Return a Jinja2 Environment that can render the overlay template standalone."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        # Undefined variables render as empty string so the template renders without
        # Flask/Blueprint context (e.g. url_for, g.user, etc.)
        undefined=Undefined,
    )
    return env


def render_overlay(tier_locked, tier_required="beta", tier_current="free"):
    env = get_jinja_env()
    template = env.get_template(OVERLAY_TEMPLATE)
    return template.render(
        tier_locked=tier_locked,
        tier_required=tier_required,
        tier_current=tier_current,
    )


# ---------------------------------------------------------------------------
# Template tests
# ---------------------------------------------------------------------------

class TestTierGateOverlayTemplate:
    """Tests for web/templates/components/tier_gate_overlay.html"""

    def test_template_file_exists(self):
        path = os.path.join(TEMPLATE_DIR, OVERLAY_TEMPLATE)
        assert os.path.exists(path), f"Template not found: {path}"

    def test_renders_overlay_when_tier_locked_true(self):
        rendered = render_overlay(tier_locked=True)
        assert "tier-gate-overlay" in rendered

    def test_does_not_render_overlay_when_tier_locked_false(self):
        rendered = render_overlay(tier_locked=False)
        assert "tier-gate-overlay" not in rendered

    def test_overlay_contains_correct_cta_href(self):
        rendered = render_overlay(tier_locked=True)
        assert 'href="/beta/join"' in rendered

    def test_overlay_has_data_track_impression_attribute(self):
        rendered = render_overlay(tier_locked=True)
        assert 'data-track="tier-gate-impression"' in rendered

    def test_overlay_has_data_track_click_attribute_on_cta(self):
        rendered = render_overlay(tier_locked=True)
        assert 'data-track="tier-gate-click"' in rendered

    def test_overlay_has_glass_card_class(self):
        rendered = render_overlay(tier_locked=True)
        assert "glass-card" in rendered

    def test_overlay_injects_tier_required_data_attribute(self):
        rendered = render_overlay(tier_locked=True, tier_required="premium")
        assert 'data-tier-required="premium"' in rendered

    def test_overlay_injects_tier_current_data_attribute(self):
        rendered = render_overlay(tier_locked=True, tier_current="free")
        assert 'data-tier-current="free"' in rendered

    def test_overlay_has_ghost_cta_class(self):
        rendered = render_overlay(tier_locked=True)
        assert "ghost-cta" in rendered

    def test_overlay_has_tier_gate_cta_class(self):
        rendered = render_overlay(tier_locked=True)
        assert "tier-gate-cta" in rendered

    def test_empty_render_when_false_produces_minimal_output(self):
        rendered = render_overlay(tier_locked=False).strip()
        # Should be whitespace-only when not locked
        assert rendered == "", f"Expected empty render, got: {repr(rendered)}"


# ---------------------------------------------------------------------------
# CSS tests
# ---------------------------------------------------------------------------

class TestTierGateCSS:
    """Tests for web/static/css/tier-gate.css"""

    @pytest.fixture(autouse=True)
    def css_content(self):
        with open(CSS_PATH) as f:
            self._css = f.read()
        return self._css

    def test_css_file_exists(self):
        assert os.path.exists(CSS_PATH), f"CSS not found: {CSS_PATH}"

    def test_css_has_correct_blur_value(self):
        assert "blur(8px)" in self._css

    def test_css_has_tier_locked_content_class(self):
        assert ".tier-locked-content" in self._css

    def test_css_has_tier_gate_overlay_class(self):
        assert ".tier-gate-overlay" in self._css

    def test_css_overlay_is_fixed_position(self):
        assert "position: fixed" in self._css

    def test_css_has_mobile_breakpoint(self):
        assert "@media (max-width: 480px)" in self._css

    def test_css_uses_design_token_spacing(self):
        # All spacing must use --space-N tokens, not raw px values (except the blur)
        assert "--space-" in self._css

    def test_css_uses_design_token_colors(self):
        # Must reference token color variables, not raw hex
        assert "var(--text-primary)" in self._css
        assert "var(--text-secondary)" in self._css

    def test_css_pointer_events_none_on_locked_content(self):
        assert "pointer-events: none" in self._css

    def test_css_user_select_none_on_locked_content(self):
        assert "user-select: none" in self._css

    def test_css_uses_sans_font_token(self):
        assert "var(--sans)" in self._css

    def test_css_overlay_has_z_index(self):
        assert "z-index:" in self._css


# ---------------------------------------------------------------------------
# JS tests
# ---------------------------------------------------------------------------

class TestTierGateJS:
    """Tests for web/static/js/tier-gate.js"""

    @pytest.fixture(autouse=True)
    def js_content(self):
        with open(JS_PATH) as f:
            self._js = f.read()
        return self._js

    def test_js_file_exists(self):
        assert os.path.exists(JS_PATH), f"JS not found: {JS_PATH}"

    def test_js_adds_tier_locked_content_class(self):
        assert "tier-locked-content" in self._js

    def test_js_queries_tier_gate_overlay(self):
        assert ".tier-gate-overlay" in self._js

    def test_js_has_dom_content_loaded_listener(self):
        assert "DOMContentLoaded" in self._js

    def test_js_targets_main_container(self):
        # Must target at least one of the standard content containers
        assert any(sel in self._js for sel in ["main", ".obs-container", ".obs-container-wide"])

    def test_js_uses_classlist_add(self):
        assert "classList.add" in self._js

    def test_js_guards_against_missing_overlay(self):
        # Should have an early return / null check
        assert "if (!overlay)" in self._js or "if (overlay)" in self._js
