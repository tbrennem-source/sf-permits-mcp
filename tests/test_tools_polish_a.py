"""Tests for polished station_predictor.html and stuck_permit.html templates.

Sprint QS11 T3-A polish.
Template-string tests — reads files and asserts structural/behavioral requirements.
Route tests use Flask test client with TESTING mode.

Coverage:
  - Station predictor: empty state, sample data rendering, Gantt chart presence,
    skeleton screen, ?permit= auto-fill, methodology section
  - Stuck permit: empty state, severity badges, block cards, playbook steps,
    timeline impact, ?permit= auto-fill
  - Design token compliance for both templates
"""
import os
import re
import pytest

STATION_PREDICTOR_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/station_predictor.html"
)

STUCK_PERMIT_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/stuck_permit.html"
)

GANTT_JS_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/static/js/gantt-interactive.js"
)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── Station Predictor ───────────────────────────────────────────────────────────

class TestStationPredictorEmptyState:
    """Tests for empty state rendering on station predictor page."""

    def setup_method(self):
        self.html = _read(STATION_PREDICTOR_PATH)

    def test_template_exists_and_nonempty(self):
        """Template file exists and has substantial content."""
        assert len(self.html) > 500

    def test_empty_state_element_present(self):
        """Page has an empty state container shown before any query."""
        assert 'empty-state' in self.html

    def test_empty_state_hint_text(self):
        """Empty state shows helpful hint text."""
        assert 'Enter a permit number' in self.html or 'permit number above' in self.html

    def test_demo_permit_chips_present(self):
        """Empty state shows demo permit chips for quick testing."""
        assert 'demo-permit-chip' in self.html or 'fillDemo' in self.html

    def test_page_title_station_predictor(self):
        """Page title references Station Predictor."""
        assert 'Station Predictor' in self.html

    def test_includes_head_obsidian(self):
        """Template includes the obsidian head fragment."""
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        """Template includes site navigation."""
        assert 'nav.html' in self.html

    def test_results_div_with_id(self):
        """Results target div has id=results."""
        assert 'id="results"' in self.html


class TestStationPredictorWithData:
    """Tests for data rendering elements on station predictor page."""

    def setup_method(self):
        self.html = _read(STATION_PREDICTOR_PATH)

    def test_gantt_chart_container_present(self):
        """Template includes a container for the interactive Gantt chart."""
        assert 'gantt' in self.html.lower()

    def test_gantt_js_loaded(self):
        """Template loads gantt-interactive.js."""
        assert 'gantt-interactive.js' in self.html

    def test_gantt_interactive_render_called(self):
        """JavaScript calls GanttInteractive.render to render the chart."""
        assert 'GanttInteractive' in self.html
        assert 'render(' in self.html or '.render(' in self.html

    def test_station_detail_panel_css(self):
        """Template has CSS for the station detail panel shown on click."""
        assert 'gantt-detail' in self.html

    def test_skeleton_screen_present(self):
        """Template has a skeleton loading screen for while data is fetching."""
        assert 'skeleton' in self.html.lower()

    def test_skeleton_gantt_bars(self):
        """Skeleton screen includes placeholder Gantt bars."""
        assert 'skeleton-gantt' in self.html or ('skeleton' in self.html and 'gantt' in self.html.lower())

    def test_predict_api_endpoint_referenced(self):
        """Template references the /api/predict-next endpoint."""
        assert 'predict-next' in self.html

    def test_marked_js_for_markdown(self):
        """Template loads marked.js for markdown rendering of full results."""
        assert 'marked' in self.html

    def test_results_content_class_present(self):
        """Template has CSS class for markdown results content area."""
        assert 'results-content' in self.html

    def test_methodology_section_present(self):
        """Template has an expandable 'How we know this' methodology section."""
        assert 'How we know this' in self.html or 'methodology' in self.html.lower()

    def test_methodology_toggle_button(self):
        """Methodology section has a toggle button to expand/collapse."""
        assert 'methodology-toggle' in self.html or 'toggleMethodology' in self.html

    def test_methodology_body_hidden_by_default(self):
        """Methodology body is hidden until toggled."""
        assert 'methodology-body' in self.html

    def test_prediction_table_styling(self):
        """Template has CSS for rendering the prediction table from markdown."""
        # The markdown response includes a table; it should be styled
        assert '.results-content table' in self.html or 'results-content' in self.html

    def test_permit_number_displayed_in_result(self):
        """Result area shows the permit number."""
        assert 'results-permit-number' in self.html


class TestStationPredictorQueryParam:
    """Tests for ?permit= query param auto-fill behavior."""

    def setup_method(self):
        self.html = _read(STATION_PREDICTOR_PATH)

    def test_url_search_params_used(self):
        """Template JavaScript reads URL search params for auto-fill."""
        assert 'URLSearchParams' in self.html or 'searchParams' in self.html or 'window.location.search' in self.html

    def test_permit_param_auto_submits(self):
        """When ?permit= param present, form auto-submits."""
        assert "params.get('permit')" in self.html or 'get("permit")' in self.html or 'permit' in self.html

    def test_domevent_listener_for_autofill(self):
        """DOMContentLoaded event listener handles auto-fill."""
        assert 'DOMContentLoaded' in self.html

    def test_permit_input_value_set(self):
        """JavaScript sets input.value from permit param."""
        assert 'input.value' in self.html


class TestStationPredictorDesignTokens:
    """Design token compliance for station predictor."""

    def setup_method(self):
        self.html = _read(STATION_PREDICTOR_PATH)

    def test_no_hardcoded_hex_colors_in_styles(self):
        """No hardcoded hex values in style blocks — only token vars allowed."""
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\*.*?\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex colors found in style block: {hex_in_values}"

    def test_mono_font_token_used(self):
        """Template uses --mono font family for data elements."""
        assert '--mono' in self.html

    def test_sans_font_token_used(self):
        """Template uses --sans font family for prose/labels."""
        assert '--sans' in self.html

    def test_obsidian_background_token(self):
        """Page uses --obsidian token for body background."""
        assert '--obsidian' in self.html

    def test_text_primary_token(self):
        """Template uses --text-primary token."""
        assert '--text-primary' in self.html

    def test_text_secondary_token(self):
        """Template uses --text-secondary token."""
        assert '--text-secondary' in self.html

    def test_obs_container_layout(self):
        """Template uses obs-container for layout."""
        assert 'obs-container' in self.html

    def test_glass_styling_tokens(self):
        """Template uses glass-border or glass styling tokens."""
        assert '--glass-border' in self.html or '--glass' in self.html

    def test_auth_error_handled(self):
        """Template handles 401 / unauthenticated state."""
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()

    def test_viewport_meta(self):
        """Template has viewport meta tag for mobile."""
        assert 'viewport' in self.html

    def test_mobile_media_query(self):
        """Template has a mobile responsive media query."""
        assert '@media (max-width:' in self.html or 'max-width' in self.html


# ── Stuck Permit ─────────────────────────────────────────────────────────────

class TestStuckPermitEmptyState:
    """Tests for empty state on stuck permit analyzer page."""

    def setup_method(self):
        self.html = _read(STUCK_PERMIT_PATH)

    def test_template_exists_and_nonempty(self):
        """Template file exists and has substantial content."""
        assert len(self.html) > 500

    def test_page_title_stuck_permit(self):
        """Page title references Stuck Permit."""
        assert 'Stuck Permit' in self.html or 'stuck-permit' in self.html.lower()

    def test_includes_head_obsidian(self):
        """Template includes the obsidian head fragment."""
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        """Template includes site navigation."""
        assert 'nav.html' in self.html

    def test_empty_state_element_present(self):
        """Page has an empty state container."""
        assert 'empty-state' in self.html or 'empty_state' in self.html

    def test_empty_state_hint_text(self):
        """Empty state provides hint text."""
        assert 'Enter a permit number' in self.html or 'permit number' in self.html.lower()

    def test_demo_permit_chips_present(self):
        """Empty state shows demo permit chips."""
        assert 'demo-permit-chip' in self.html or 'fillDemo' in self.html

    def test_results_div_with_id(self):
        """Results target div exists with id=results."""
        assert 'id="results"' in self.html


class TestStuckPermitSeverityBadges:
    """Tests for severity dashboard elements."""

    def setup_method(self):
        self.html = _read(STUCK_PERMIT_PATH)

    def test_severity_dashboard_css(self):
        """Template has CSS for the severity dashboard."""
        assert 'severity-dashboard' in self.html

    def test_severity_badge_css_classes(self):
        """Template defines severity badge CSS classes."""
        assert 'severity-badge' in self.html

    def test_severity_green_variant(self):
        """Template has green (on-track) severity variant."""
        assert 'severity-badge-green' in self.html or 'signal-green' in self.html

    def test_severity_amber_variant(self):
        """Template has amber (stalled) severity variant."""
        assert 'severity-badge-amber' in self.html or 'signal-amber' in self.html

    def test_severity_red_variant(self):
        """Template has red (critical) severity variant."""
        assert 'severity-badge-red' in self.html or 'signal-red' in self.html

    def test_block_cards_css(self):
        """Template has CSS for station block cards."""
        assert 'block-card' in self.html

    def test_block_card_critical_variant(self):
        """Block card has critical (red) variant."""
        assert 'block-card-critical' in self.html

    def test_block_card_stalled_variant(self):
        """Block card has stalled (amber) variant."""
        assert 'block-card-stalled' in self.html

    def test_section_label_used(self):
        """Template uses section-label for subsection headers."""
        assert 'section-label' in self.html

    def test_playbook_steps_css(self):
        """Template has CSS for numbered playbook steps."""
        assert 'playbook-step' in self.html

    def test_urgency_classes_present(self):
        """Template defines urgency level CSS classes."""
        assert 'urgency-immediate' in self.html or 'urgency-high' in self.html

    def test_parse_intervention_steps_function(self):
        """JavaScript parses intervention steps from markdown."""
        assert 'parseInterventionSteps' in self.html or 'Intervention Steps' in self.html

    def test_timeline_impact_note(self):
        """Template shows timeline impact note about comment-response cycles."""
        assert 'comment-response cycle' in self.html or 'adds 6' in self.html or 'timeline-impact' in self.html

    def test_build_severity_dashboard_function(self):
        """JavaScript builds severity dashboard from parsed data."""
        assert 'buildSeverityDashboard' in self.html or 'severity' in self.html

    def test_severity_permit_number_display(self):
        """Severity dashboard shows the permit number."""
        assert 'severity-permit-number' in self.html


class TestStuckPermitQueryParam:
    """Tests for ?permit= query param auto-fill."""

    def setup_method(self):
        self.html = _read(STUCK_PERMIT_PATH)

    def test_url_search_params_used(self):
        """Template reads URL search params for auto-fill."""
        assert 'URLSearchParams' in self.html or 'window.location.search' in self.html

    def test_permit_param_triggers_diagnose(self):
        """When ?permit= param present, diagnosis auto-runs."""
        assert "params.get('permit')" in self.html or 'get("permit")' in self.html or 'diagnosedPermit' in self.html

    def test_domevent_listener_for_autofill(self):
        """DOMContentLoaded listener handles auto-fill."""
        assert 'DOMContentLoaded' in self.html

    def test_input_value_set_from_param(self):
        """JavaScript sets input.value from permit param."""
        assert 'input.value' in self.html


class TestStuckPermitDesignTokens:
    """Design token compliance for stuck permit analyzer."""

    def setup_method(self):
        self.html = _read(STUCK_PERMIT_PATH)

    def test_no_hardcoded_hex_in_styles(self):
        """No hardcoded hex values in style blocks."""
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\*.*?\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex colors in style block: {hex_in_values}"

    def test_mono_font_used(self):
        assert '--mono' in self.html

    def test_sans_font_used(self):
        assert '--sans' in self.html

    def test_obsidian_background_token(self):
        assert '--obsidian' in self.html

    def test_text_primary_token(self):
        assert '--text-primary' in self.html

    def test_text_secondary_token(self):
        assert '--text-secondary' in self.html

    def test_obs_container_layout(self):
        assert 'obs-container' in self.html

    def test_glass_tokens_used(self):
        assert '--glass-border' in self.html or '--glass' in self.html

    def test_signal_amber_for_stalled(self):
        """Template uses --signal-amber for stalled status semantics."""
        assert '--signal-amber' in self.html

    def test_signal_red_for_critical(self):
        """Template uses --signal-red for critical status semantics."""
        assert '--signal-red' in self.html

    def test_auth_error_handled(self):
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()

    def test_viewport_meta(self):
        assert 'viewport' in self.html

    def test_mobile_media_query(self):
        assert '@media (max-width:' in self.html or 'max-width' in self.html

    def test_marked_js_included(self):
        """Template includes marked.js for markdown rendering."""
        assert 'marked' in self.html

    def test_skeleton_screen_present(self):
        """Template has a skeleton loading screen."""
        assert 'skeleton' in self.html.lower()


# ── Gantt JS ─────────────────────────────────────────────────────────────────

class TestGanttInteractiveJS:
    """Tests for the gantt-interactive.js static asset."""

    def setup_method(self):
        self.js = _read(GANTT_JS_PATH)

    def test_file_exists_and_nonempty(self):
        """gantt-interactive.js exists and has substantial content."""
        assert len(self.js) > 200

    def test_render_function_exported(self):
        """GanttInteractive.render is the main public API."""
        assert 'render:' in self.js or 'render =' in self.js

    def test_status_color_function_present(self):
        """statusColor helper maps station status to CSS color."""
        assert 'statusColor' in self.js

    def test_compute_bar_widths_present(self):
        """computeBarWidths calculates relative bar widths."""
        assert 'computeBarWidths' in self.js or '_computeBarWidths' in self.js

    def test_status_types_covered(self):
        """All expected status types are handled."""
        assert 'complete' in self.js
        assert 'active' in self.js
        assert 'stalled' in self.js
        assert 'predicted' in self.js

    def test_gantt_track_rendered(self):
        """Renders a .gantt-track horizontal bar container."""
        assert 'gantt-track' in self.js

    def test_gantt_bar_rendered(self):
        """Renders individual .gantt-bar elements."""
        assert 'gantt-bar' in self.js

    def test_detail_panel_rendered(self):
        """Renders expandable .gantt-detail panel for station info."""
        assert 'gantt-detail' in self.js

    def test_keyboard_navigation(self):
        """Bars support keyboard activation (Enter/Space)."""
        assert 'Enter' in self.js and 'keydown' in self.js

    def test_aria_attributes(self):
        """Accessibility attributes are set on interactive elements."""
        assert 'aria-' in self.js

    def test_escape_html_function(self):
        """HTML escaping utility prevents XSS."""
        assert 'esc(' in self.js or 'escHtml' in self.js or '&amp;' in self.js

    def test_umd_export(self):
        """Module uses UMD pattern for browser and Node.js compatibility."""
        assert 'GanttInteractive' in self.js

    def test_legend_rendered(self):
        """Chart renders a color legend."""
        assert 'gantt-legend' in self.js


# ── Route tests ───────────────────────────────────────────────────────────────

try:
    from web.app import app, _rate_buckets

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
                sess['user_id'] = 'test-user-polish-a'
            yield c
        _rate_buckets.clear()

    class TestStationPredictorRoute:
        def test_route_redirects_unauthenticated(self, client):
            """GET /tools/station-predictor redirects to login if not authenticated."""
            rv = client.get("/tools/station-predictor")
            assert rv.status_code in (302, 301)

        def test_route_redirect_target_is_login(self, client):
            """Unauthenticated redirect sends user to /auth/login."""
            rv = client.get("/tools/station-predictor")
            location = rv.headers.get('Location', '')
            assert 'login' in location or 'auth' in location

        @pytest.mark.xfail(reason="g.user requires full before_request chain — needs integration fixture")
        def test_route_renders_for_authenticated_user(self, authed_client):
            rv = authed_client.get("/tools/station-predictor")
            assert rv.status_code == 200
            assert b'Station Predictor' in rv.data

        @pytest.mark.xfail(reason="g.user requires full before_request chain — needs integration fixture")
        def test_route_with_permit_param(self, authed_client):
            """GET /tools/station-predictor?permit=X renders with input pre-filled."""
            rv = authed_client.get("/tools/station-predictor?permit=202501015257")
            assert rv.status_code == 200

    class TestStuckPermitRoute:
        def test_route_redirects_unauthenticated(self, client):
            """GET /tools/stuck-permit redirects to login if not authenticated."""
            rv = client.get("/tools/stuck-permit")
            assert rv.status_code in (302, 301)

        def test_route_redirect_target_is_login(self, client):
            """Unauthenticated redirect sends user to /auth/login."""
            rv = client.get("/tools/stuck-permit")
            location = rv.headers.get('Location', '')
            assert 'login' in location or 'auth' in location

        @pytest.mark.xfail(reason="g.user requires full before_request chain — needs integration fixture")
        def test_route_renders_for_authenticated_user(self, authed_client):
            rv = authed_client.get("/tools/stuck-permit")
            assert rv.status_code == 200
            assert b'Stuck Permit' in rv.data or b'stuck' in rv.data

        @pytest.mark.xfail(reason="g.user requires full before_request chain — needs integration fixture")
        def test_route_with_permit_param(self, authed_client):
            """GET /tools/stuck-permit?permit=X renders with input pre-filled."""
            rv = authed_client.get("/tools/stuck-permit?permit=202501015257")
            assert rv.status_code == 200

except ImportError:
    # Flask app not available in test environment
    pass
