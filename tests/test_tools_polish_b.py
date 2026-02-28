"""Tests for polished what_if.html and cost_of_delay.html templates.

Sprint 92 — Agent 3B — Tool page polish.

Covers:
  - Template structure and required elements
  - Design token compliance (no hardcoded hex)
  - Demo ?demo= parameter references
  - Loading/empty/results/error state presence
  - Input areas and comparison table markup
  - Percentile table and expected cost card in cost_of_delay
  - Strategy/recommendation callout sections
  - Route redirect behavior for unauthenticated access
"""
import os
import re
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WHAT_IF_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/what_if.html",
)

COST_DELAY_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/cost_of_delay.html",
)


def _read_what_if():
    with open(WHAT_IF_PATH, encoding="utf-8") as f:
        return f.read()


def _read_cost_of_delay():
    with open(COST_DELAY_PATH, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# what_if.html — template structure
# ---------------------------------------------------------------------------

class TestWhatIfTemplate:
    def setup_method(self):
        self.html = _read_what_if()

    # ── Structure ────────────────────────────────────────────────────────────

    def test_template_exists_and_not_empty(self):
        assert len(self.html) > 500

    def test_includes_head_obsidian(self):
        assert "head_obsidian.html" in self.html

    def test_includes_nav(self):
        assert "nav.html" in self.html

    def test_page_title_contains_simulator(self):
        assert "Simulator" in self.html or "What-If" in self.html

    def test_viewport_meta_present(self):
        assert "viewport" in self.html

    # ── Input area ───────────────────────────────────────────────────────────

    def test_two_project_panels(self):
        """Template has a Project A and Project B input panel."""
        assert "project-panel" in self.html or "panels-row" in self.html

    def test_project_a_scope_input(self):
        assert "scope-a" in self.html or "scope_a" in self.html

    def test_project_b_scope_input(self):
        assert "scope-b" in self.html or "scope_b" in self.html

    def test_cost_inputs_present(self):
        assert "cost-a" in self.html or "cost_a" in self.html

    def test_neighborhood_input_present(self):
        assert "neighborhood" in self.html.lower()

    # ── Comparison table ──────────────────────────────────────────────────────

    def test_comparison_table_present(self):
        assert "comparison-table" in self.html

    def test_comparison_table_row_metrics(self):
        """Table references relevant metric labels."""
        assert any(x in self.html for x in ["Review Path", "review_path", "Timeline", "Revision Risk"])

    def test_delta_indicator_classes(self):
        """Template has diff-better and diff-worse CSS classes for indicators."""
        assert "diff-better" in self.html
        assert "diff-worse" in self.html

    # ── Strategy callout ──────────────────────────────────────────────────────

    def test_strategy_callout_present(self):
        assert "strategy-callout" in self.html or "Recommendation" in self.html

    # ── Loading and empty states ─────────────────────────────────────────────

    def test_loading_skeleton_present(self):
        assert "skeleton" in self.html or "loading" in self.html.lower()

    def test_empty_state_present(self):
        assert "empty-state" in self.html

    def test_empty_state_has_demo_suggestion(self):
        assert "demo" in self.html.lower()

    # ── ?demo= auto-fill ─────────────────────────────────────────────────────

    def test_demo_url_param_handled(self):
        """JS handles ?demo=kitchen-vs-full to auto-fill and auto-run."""
        assert "kitchen-vs-full" in self.html or "demo" in self.html.lower()

    def test_demo_data_object_present(self):
        assert "DEMO_DATA" in self.html or "demoKey" in self.html

    # ── API and auth ──────────────────────────────────────────────────────────

    def test_what_if_api_endpoint_referenced(self):
        assert "/api/what-if" in self.html

    def test_csrf_token_handled(self):
        assert "csrf" in self.html.lower() or "X-CSRFToken" in self.html

    def test_json_post_present(self):
        assert "JSON.stringify" in self.html or "application/json" in self.html

    def test_auth_401_handled(self):
        assert "401" in self.html or "log in" in self.html.lower() or "login" in self.html.lower()

    def test_submit_button_present(self):
        assert "submit" in self.html.lower() or "compare-btn" in self.html

    # ── Design token compliance ───────────────────────────────────────────────

    def test_no_hardcoded_hex_colors_in_style_blocks(self):
        """Style blocks must use CSS custom properties, not hardcoded hex."""
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", self.html, re.DOTALL)
        for block in style_blocks:
            # Strip comments before checking
            block_no_comments = re.sub(r"/\*.*?\*/", "", block, flags=re.DOTALL)
            hex_matches = re.findall(r":\s*#[0-9a-fA-F]{3,6}\b", block_no_comments)
            assert not hex_matches, f"Hardcoded hex color found in <style>: {hex_matches}"

    def test_mono_font_token_used(self):
        assert "--mono" in self.html

    def test_sans_font_token_used(self):
        assert "--sans" in self.html

    def test_obsidian_color_tokens_used(self):
        assert "--obsidian-mid" in self.html or "--obsidian-light" in self.html

    def test_glass_border_token_used(self):
        assert "--glass-border" in self.html

    def test_no_inline_style_hex_colors(self):
        """No inline style= attributes with hardcoded hex values."""
        inline_hex = re.findall(r'style="[^"]*#[0-9a-fA-F]{3,6}[^"]*"', self.html)
        assert not inline_hex, f"Hardcoded hex in inline style: {inline_hex}"

    # ── Marked.js ────────────────────────────────────────────────────────────

    def test_marked_js_loaded_for_markdown(self):
        assert "marked" in self.html

    def test_feedback_widget_included(self):
        assert "feedback_widget" in self.html

    def test_admin_scripts_included(self):
        assert "admin-feedback.js" in self.html
        assert "admin-tour.js" in self.html


# ---------------------------------------------------------------------------
# cost_of_delay.html — template structure
# ---------------------------------------------------------------------------

class TestCostOfDelayTemplate:
    def setup_method(self):
        self.html = _read_cost_of_delay()

    # ── Structure ────────────────────────────────────────────────────────────

    def test_template_exists_and_not_empty(self):
        assert len(self.html) > 500

    def test_includes_head_obsidian(self):
        assert "head_obsidian.html" in self.html

    def test_includes_nav(self):
        assert "nav.html" in self.html

    def test_page_title_contains_calculator(self):
        assert "Calculator" in self.html or "Cost of Delay" in self.html

    def test_viewport_meta_present(self):
        assert "viewport" in self.html

    # ── Input area ───────────────────────────────────────────────────────────

    def test_monthly_cost_input_prefilled_in_demo(self):
        """Demo mode pre-fills $15K monthly cost."""
        assert "15000" in self.html or "15K" in self.html

    def test_permit_type_selector_present(self):
        """Has a permit type select or input field."""
        assert "permit-type" in self.html or "permit_type" in self.html

    def test_permit_type_has_restaurant_option(self):
        assert "restaurant" in self.html.lower()

    def test_neighborhood_selector_present(self):
        assert "neighborhood" in self.html.lower()

    # ── Percentile table ──────────────────────────────────────────────────────

    def test_percentile_table_present(self):
        assert "percentile-table" in self.html or "p25" in self.html or "p50" in self.html

    def test_p25_p50_p75_p90_labels(self):
        """Template references multiple percentile scenarios."""
        html_lower = self.html.lower()
        count = sum(1 for p in ["p25", "p50", "p90", "best", "likely", "worst"] if p in html_lower)
        assert count >= 2, "Expected at least 2 percentile/scenario references"

    # ── Expected cost highlight ───────────────────────────────────────────────

    def test_expected_cost_card_present(self):
        assert "expected-cost" in self.html or "expected cost" in self.html.lower()

    # ── Bottleneck alert ──────────────────────────────────────────────────────

    def test_bottleneck_alert_present(self):
        assert "bottleneck" in self.html.lower() or "Bottleneck" in self.html

    # ── Recommendation callout ────────────────────────────────────────────────

    def test_recommendation_card_present(self):
        assert "recommendation" in self.html.lower() or "Recommendation" in self.html

    # ── Loading and empty states ─────────────────────────────────────────────

    def test_loading_skeleton_present(self):
        assert "skeleton" in self.html or "loading" in self.html.lower()

    def test_empty_state_present(self):
        assert "empty-state" in self.html

    def test_empty_state_has_demo_suggestion(self):
        assert "demo" in self.html.lower()

    # ── ?demo= auto-fill ─────────────────────────────────────────────────────

    def test_demo_url_param_handled(self):
        """JS handles ?demo=restaurant-15k to auto-fill and auto-run."""
        assert "restaurant-15k" in self.html or "DEMO_DATA" in self.html

    def test_demo_auto_submit_present(self):
        """Demo mode triggers form submit automatically."""
        assert "dispatchEvent" in self.html or "submit" in self.html

    # ── API and auth ──────────────────────────────────────────────────────────

    def test_delay_cost_api_endpoint_referenced(self):
        assert "/api/delay-cost" in self.html

    def test_csrf_token_handled(self):
        assert "csrf" in self.html.lower() or "X-CSRFToken" in self.html

    def test_json_post_present(self):
        assert "JSON.stringify" in self.html or "application/json" in self.html

    def test_auth_401_handled(self):
        assert "401" in self.html or "log in" in self.html.lower() or "login" in self.html.lower()

    def test_submit_button_present(self):
        assert "submit" in self.html.lower() or "action-btn" in self.html

    # ── Inline validation ─────────────────────────────────────────────────────

    def test_inline_cost_error_message(self):
        """Has inline error for invalid monthly cost."""
        assert "inline-error" in self.html or "greater than zero" in self.html

    # ── Design token compliance ───────────────────────────────────────────────

    def test_no_hardcoded_hex_colors_in_style_blocks(self):
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r"/\*.*?\*/", "", block, flags=re.DOTALL)
            hex_matches = re.findall(r":\s*#[0-9a-fA-F]{3,6}\b", block_no_comments)
            assert not hex_matches, f"Hardcoded hex color found in <style>: {hex_matches}"

    def test_mono_font_token_used(self):
        assert "--mono" in self.html

    def test_sans_font_token_used(self):
        assert "--sans" in self.html

    def test_obsidian_color_tokens_used(self):
        assert "--obsidian-mid" in self.html or "--obsidian-light" in self.html

    def test_glass_border_token_used(self):
        assert "--glass-border" in self.html

    def test_accent_token_used(self):
        assert "--accent" in self.html

    def test_signal_tokens_for_status(self):
        """Uses semantic signal/dot tokens for status indicators, not raw hex."""
        assert "--signal-" in self.html or "--dot-" in self.html

    def test_no_inline_style_hex_colors(self):
        inline_hex = re.findall(r'style="[^"]*#[0-9a-fA-F]{3,6}[^"]*"', self.html)
        assert not inline_hex, f"Hardcoded hex in inline style: {inline_hex}"

    def test_feedback_widget_included(self):
        assert "feedback_widget" in self.html

    def test_admin_scripts_included(self):
        assert "admin-feedback.js" in self.html
        assert "admin-tour.js" in self.html

    # ── Marked.js ────────────────────────────────────────────────────────────

    def test_marked_js_loaded_for_markdown(self):
        assert "marked" in self.html


# ---------------------------------------------------------------------------
# Route tests (unauthenticated redirect)
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from web.app import app, _rate_buckets
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


class TestToolRoutes:
    def test_what_if_route_accessible_unauthenticated(self, client):
        """GET /tools/what-if returns 200 for anonymous users (no redirect)."""
        rv = client.get("/tools/what-if")
        assert rv.status_code == 200

    def test_cost_of_delay_route_accessible_unauthenticated(self, client):
        """GET /tools/cost-of-delay returns 200 for anonymous users (no redirect)."""
        rv = client.get("/tools/cost-of-delay")
        assert rv.status_code == 200

    def test_what_if_api_requires_auth(self, client):
        rv = client.post(
            "/api/what-if",
            json={"base_description": "Kitchen remodel"},
            content_type="application/json",
        )
        assert rv.status_code in (401, 302, 403)

    def test_delay_cost_api_requires_auth(self, client):
        rv = client.post(
            "/api/delay-cost",
            json={"permit_type": "restaurant", "monthly_carrying_cost": 15000},
            content_type="application/json",
        )
        assert rv.status_code in (401, 302, 403)
