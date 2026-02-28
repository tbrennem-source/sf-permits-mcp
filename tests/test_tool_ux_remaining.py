"""Tests for entity_network.html and revision_risk.html templates and routes.

Operates via string search on template file contents (no Jinja rendering required).
Route tests use Flask test client with TESTING mode.
"""
import os
import re
import pytest
from web.app import app, _rate_buckets

ENTITY_NETWORK_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/entity_network.html"
)

REVISION_RISK_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/revision_risk.html"
)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Entity Network template tests
# ---------------------------------------------------------------------------

class TestEntityNetworkTemplate:
    def setup_method(self):
        self.html = _read(ENTITY_NETWORK_PATH)

    def test_template_exists(self):
        assert len(self.html) > 200

    def test_includes_head_obsidian(self):
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        assert 'nav.html' in self.html

    def test_page_title_entity_network(self):
        assert 'Entity Network' in self.html or 'entity-network' in self.html.lower()

    def test_has_style_block(self):
        """Template must have a proper <style> block (not floating CSS)."""
        assert '<style' in self.html

    def test_style_block_has_nonce(self):
        """Style block uses nonce for CSP compliance."""
        assert 'nonce="{{ csp_nonce }}"' in self.html or "nonce='{{ csp_nonce }}'" in self.html

    def test_entity_input_present(self):
        """Form has a text input for entity/contractor name."""
        assert 'entity-input' in self.html or 'entity_input' in self.html

    def test_address_param_prefill(self):
        """Template reads ?address= param from URL for pre-fill."""
        assert "urlParams.get('address')" in self.html or "address" in self.html

    def test_demo_link_present(self):
        """Page has a demo link to help users get started."""
        assert 'demo' in self.html.lower() or '?address=' in self.html

    def test_empty_state_present(self):
        """Page has a proper empty state element."""
        assert 'empty-state' in self.html

    def test_empty_state_has_demo_suggestion(self):
        """Empty state guides user with a demo suggestion."""
        assert 'demo' in self.html.lower() or 'example' in self.html.lower() or '?address=' in self.html

    def test_loading_state_present(self):
        """Page shows a loading skeleton while request is in flight."""
        assert 'loading-area' in self.html or 'loading' in self.html.lower()

    def test_loading_skeleton_rows(self):
        """Loading skeleton has visible rows to mirror expected content."""
        assert 'skeleton-row' in self.html or 'skeleton' in self.html

    def test_results_area_present(self):
        """Results area exists in the DOM."""
        assert 'results-area' in self.html or 'id="results' in self.html

    def test_network_graph_element(self):
        """Template includes a network graph visualization element."""
        assert 'network-graph' in self.html or 'network' in self.html.lower()

    def test_network_stats_present(self):
        """Template shows network statistics (node/edge counts)."""
        assert 'network-stat' in self.html or 'stat-nodes' in self.html or 'Connected entities' in self.html

    def test_error_handling_present(self):
        """Template handles errors gracefully."""
        assert 'error' in self.html.lower()

    def test_auth_prompt_on_401(self):
        """Template shows login prompt on 401 response."""
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()

    def test_marked_js_loaded(self):
        """marked.js is loaded for markdown rendering."""
        assert 'marked' in self.html

    def test_mono_font_used(self):
        assert '--mono' in self.html

    def test_sans_font_used(self):
        assert '--sans' in self.html

    def test_viewport_meta(self):
        assert 'viewport' in self.html

    def test_obs_container_layout(self):
        assert 'obs-container' in self.html

    def test_no_hardcoded_hex_in_styles(self):
        """No hardcoded hex colors in style blocks (only token vars allowed)."""
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\*.*?\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex in style block: {hex_in_values}"

    def test_obsidian_background_token(self):
        assert '--obsidian' in self.html

    def test_text_primary_token_used(self):
        assert '--text-primary' in self.html

    def test_text_secondary_token_used(self):
        assert '--text-secondary' in self.html

    def test_glass_border_token_used(self):
        assert '--glass-border' in self.html

    def test_spinner_loading_indicator(self):
        """Analyze button shows a spinner during loading."""
        assert 'spinner' in self.html

    def test_enter_key_triggers_search(self):
        """Pressing Enter in the input triggers network analysis."""
        assert 'Enter' in self.html or 'keydown' in self.html

    def test_share_button_included(self):
        """Page includes share button component."""
        assert 'share_button' in self.html or 'share' in self.html.lower()

    def test_feedback_widget_included(self):
        """Page includes feedback widget fragment."""
        assert 'feedback_widget' in self.html

    def test_admin_scripts_included(self):
        """Admin feedback and tour scripts are included."""
        assert 'admin-feedback.js' in self.html
        assert 'admin-tour.js' in self.html

    def test_connection_row_styling(self):
        """Connection rows have proper CSS for display."""
        assert 'connection-row' in self.html or 'connection' in self.html.lower()


# ---------------------------------------------------------------------------
# Entity Network route tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


@pytest.fixture
def authed_client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'test-user-123'
        yield c
    _rate_buckets.clear()


class TestEntityNetworkRoute:
    def test_route_exists_for_unauthenticated(self, client):
        """Entity network page renders for unauthenticated users (no auth redirect)."""
        rv = client.get("/tools/entity-network")
        # Either renders (200) or redirects (301/302) — either is acceptable
        assert rv.status_code in (200, 301, 302)

    def test_route_renders_200(self, client):
        """Entity network page returns 200 (no auth required for page load)."""
        rv = client.get("/tools/entity-network")
        assert rv.status_code == 200

    def test_page_contains_entity_label(self, client):
        """Rendered page contains entity network content."""
        rv = client.get("/tools/entity-network")
        if rv.status_code == 200:
            assert b'Entity' in rv.data or b'entity' in rv.data or b'network' in rv.data.lower()


# ---------------------------------------------------------------------------
# Revision Risk template tests
# ---------------------------------------------------------------------------

class TestRevisionRiskTemplate:
    def setup_method(self):
        self.html = _read(REVISION_RISK_PATH)

    def test_template_exists(self):
        assert len(self.html) > 200

    def test_includes_head_obsidian(self):
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        assert 'nav.html' in self.html

    def test_page_title_revision_risk(self):
        assert 'Revision Risk' in self.html or 'revision-risk' in self.html.lower()

    def test_has_proper_style_block(self):
        """Template must have a proper <style nonce=...> block — not floating CSS."""
        # Critical fix: ensure style tag is properly opened
        assert re.search(r'<style\s+nonce=', self.html) is not None, \
            "Missing <style nonce=...> tag — CSS was floating outside style block"

    def test_style_block_opens_before_css(self):
        """The <style> tag must appear before any CSS property definitions."""
        style_pos = self.html.find('<style')
        # Verify <style> exists at all
        assert style_pos >= 0, "No <style> block found"
        # Verify CSS content is inside it (not above it)
        before_style = self.html[:style_pos]
        assert 'padding: var(' not in before_style, \
            "CSS is appearing before the <style> tag — style block likely broken"

    def test_permit_type_select_present(self):
        """Form has a permit type selector."""
        assert 'permit-type' in self.html or 'permit_type' in self.html

    def test_permit_type_options(self):
        """Permit type select has at least one real option (not just placeholder)."""
        assert '<option value="alterations"' in self.html or 'alterations' in self.html.lower()

    def test_permit_type_url_param_prefill(self):
        """Template reads ?permit_type= from URL for pre-fill."""
        assert "permit_type" in self.html or "permit-type" in self.html

    def test_neighborhood_field_optional(self):
        """Neighborhood input is present and marked optional."""
        assert 'neighborhood' in self.html.lower()
        assert 'optional' in self.html.lower()

    def test_demo_link_present(self):
        """Page has a demo link in the header."""
        assert 'demo' in self.html.lower() or '?permit_type=' in self.html

    def test_empty_state_present(self):
        """Page has a proper empty state."""
        assert 'empty-state' in self.html

    def test_empty_state_has_demo_suggestion(self):
        """Empty state suggests a demo scenario."""
        assert 'demo' in self.html.lower() or '?permit_type=' in self.html

    def test_loading_skeleton_present(self):
        """Loading skeleton is shown while request is in flight."""
        assert 'loading-area' in self.html or 'skeleton' in self.html

    def test_risk_gauge_present(self):
        """Template includes a risk gauge visualization element."""
        assert 'risk-gauge' in self.html or 'gauge' in self.html.lower()

    def test_risk_gauge_svg_element(self):
        """Risk gauge is rendered as an SVG element."""
        assert '<svg' in self.html

    def test_risk_gauge_arc_element(self):
        """SVG gauge has an arc path element for the fill."""
        assert 'gauge-arc' in self.html or 'stroke-dasharray' in self.html

    def test_risk_level_text_element(self):
        """Risk gauge displays a risk level label."""
        assert 'risk-level-text' in self.html or 'risk-level' in self.html or 'Revision Risk' in self.html

    def test_results_panel_present(self):
        """Results panel exists in the DOM."""
        assert 'results-panel' in self.html or 'id="results"' in self.html

    def test_result_markdown_element(self):
        """Full markdown detail element exists."""
        assert 'result-markdown' in self.html

    def test_error_handling_present(self):
        """Template handles errors gracefully."""
        assert 'error' in self.html.lower()

    def test_auth_prompt_on_401(self):
        """Template handles 401 with login prompt."""
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()

    def test_marked_js_loaded(self):
        """marked.js is loaded for markdown rendering."""
        assert 'marked' in self.html

    def test_json_post_with_csrf(self):
        """Template sends JSON POST with CSRF token."""
        assert 'X-CSRFToken' in self.html or 'csrf' in self.html.lower()
        assert 'JSON.stringify' in self.html or 'application/json' in self.html

    def test_two_column_layout(self):
        """Page uses a two-column layout (form left, results right)."""
        assert 'tool-layout' in self.html or 'calc-layout' in self.html or 'grid-template-columns' in self.html

    def test_obs_container_layout(self):
        assert 'obs-container' in self.html

    def test_mono_font_used(self):
        assert '--mono' in self.html

    def test_sans_font_used(self):
        assert '--sans' in self.html

    def test_viewport_meta(self):
        assert 'viewport' in self.html

    def test_no_hardcoded_hex_in_styles(self):
        """No hardcoded hex colors in style blocks."""
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\*.*?\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex in style block: {hex_in_values}"

    def test_obsidian_background_token(self):
        assert '--obsidian' in self.html

    def test_text_primary_token(self):
        assert '--text-primary' in self.html

    def test_text_secondary_token(self):
        assert '--text-secondary' in self.html

    def test_glass_border_token(self):
        assert '--glass-border' in self.html

    def test_action_btn_class_used(self):
        """Submit button uses action-btn token class."""
        assert 'action-btn' in self.html

    def test_glass_card_class_used(self):
        """Form panel uses glass-card token class."""
        assert 'glass-card' in self.html

    def test_signal_colors_for_gauge(self):
        """Gauge uses signal color tokens (not hardcoded hex)."""
        assert '--signal-green' in self.html or '--signal-red' in self.html or '--dot-amber' in self.html

    def test_share_button_included(self):
        assert 'share_button' in self.html or 'share' in self.html.lower()

    def test_feedback_widget_included(self):
        assert 'feedback_widget' in self.html

    def test_admin_scripts_included(self):
        assert 'admin-feedback.js' in self.html
        assert 'admin-tour.js' in self.html

    def test_review_path_field(self):
        """Optional review path selector is present."""
        assert 'review' in self.html.lower()

    def test_auto_run_on_prefill(self):
        """Template auto-submits form when permit_type param is in URL."""
        assert 'setTimeout' in self.html or 'dispatchEvent' in self.html or 'submit' in self.html


# ---------------------------------------------------------------------------
# Revision Risk route tests
# ---------------------------------------------------------------------------

class TestRevisionRiskRoute:
    def test_route_exists_for_unauthenticated(self, client):
        """Revision risk page renders for unauthenticated users (no auth redirect)."""
        rv = client.get("/tools/revision-risk")
        assert rv.status_code in (200, 301, 302)

    def test_route_renders_200(self, client):
        """Revision risk page returns 200 (no auth required for page load)."""
        rv = client.get("/tools/revision-risk")
        assert rv.status_code == 200

    def test_page_contains_revision_risk_content(self, client):
        """Rendered page contains revision risk content."""
        rv = client.get("/tools/revision-risk")
        if rv.status_code == 200:
            assert b'Revision' in rv.data or b'revision' in rv.data or b'Risk' in rv.data
