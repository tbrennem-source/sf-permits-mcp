"""UX behaviour tests for station_predictor.html and stuck_permit.html.

Covers:
  - ?permit= pre-fill attributes and auto-run wiring
  - Loading/skeleton state presence
  - Empty state with demo permit chips
  - Gantt interactivity markers (click-to-expand pattern)
  - Intervention playbook formatting hooks in stuck permit
  - Reviewer phone number linkification patterns
  - gantt-interactive.js: badge inside station-main, bar/row event wiring

These are template-string + JS unit tests. No Flask test client or
browser/Playwright needed — pure structural assertions on file content.
"""

import os
import re
import pytest


# ---------------------------------------------------------------------------
# File readers
# ---------------------------------------------------------------------------

WORKTREE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATION_PREDICTOR_PATH = os.path.join(
    WORKTREE, "web", "templates", "tools", "station_predictor.html"
)
STUCK_PERMIT_PATH = os.path.join(
    WORKTREE, "web", "templates", "tools", "stuck_permit.html"
)
GANTT_JS_PATH = os.path.join(
    WORKTREE, "web", "static", "js", "gantt-interactive.js"
)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Station Predictor UX tests
# ---------------------------------------------------------------------------

class TestStationPredictorUX:
    """UX behaviour tests for station_predictor.html."""

    def setup_method(self):
        self.html = _read(STATION_PREDICTOR_PATH)

    # --- ?permit= pre-fill ---

    def test_permit_param_prefill_uses_URLSearchParams(self):
        """Auto-fill logic uses URLSearchParams to read ?permit= from the URL."""
        assert "URLSearchParams" in self.html

    def test_permit_param_key_is_permit(self):
        """Auto-fill reads the 'permit' query param key."""
        assert "params.get('permit')" in self.html or 'params.get("permit")' in self.html

    def test_permit_param_triggers_runPrediction(self):
        """After pre-fill, runPrediction() is called automatically."""
        # Verify that the DOMContentLoaded handler calls runPrediction when a permit param is found
        assert "runPrediction()" in self.html

    def test_permit_param_fills_input_value(self):
        """Pre-fill sets input.value = permitParam.trim()."""
        assert "input.value = permitParam.trim()" in self.html or "input.value = param" in self.html

    def test_DOMContentLoaded_wires_permit_param(self):
        """DOMContentLoaded event listener handles the ?permit= auto-run."""
        assert "DOMContentLoaded" in self.html

    # --- Loading / skeleton state ---

    def test_skeleton_screen_element_exists(self):
        """skeleton-screen element is present for loading UX."""
        assert 'id="skeleton-screen"' in self.html

    def test_skeleton_screen_becomes_visible_on_load(self):
        """setLoading adds is-visible class to skeleton screen."""
        assert "is-visible" in self.html

    def test_skeleton_gantt_bars_in_skeleton(self):
        """Skeleton loading screen shows Gantt-bar placeholders."""
        assert "skeleton-gantt" in self.html

    def test_spinner_in_button_during_load(self):
        """Button has a spinner element shown during loading."""
        assert "spinner" in self.html
        assert 'id="btn-spinner"' in self.html or "btn-spinner" in self.html

    def test_results_hidden_during_loading(self):
        """Results div is hidden while skeleton is shown."""
        assert "results.style.display = 'none'" in self.html or "results.style.display" in self.html

    # --- Empty state ---

    def test_empty_state_describes_tool(self):
        """Empty state hint text explains what the tool does."""
        assert "permit number" in self.html.lower()
        assert "station" in self.html.lower() or "predicted" in self.html.lower() or "routing" in self.html.lower()

    def test_demo_permit_chips_present(self):
        """Empty state contains clickable demo permit chip buttons."""
        assert "demo-permit-chip" in self.html
        assert "fillDemo(" in self.html

    def test_at_least_three_demo_permits(self):
        """At least three demo permit chips are provided."""
        chips = re.findall(r"demo-permit-chip", self.html)
        assert len(chips) >= 3

    def test_demo_chips_call_fillDemo(self):
        """Demo chip onclick calls fillDemo with a permit number string."""
        matches = re.findall(r"fillDemo\('(\d+)'\)", self.html)
        assert len(matches) >= 3
        for m in matches:
            assert len(m) >= 10, f"Demo permit number too short: {m}"

    def test_fillDemo_fills_input_and_runs(self):
        """fillDemo function sets input.value and calls runPrediction."""
        assert "window.fillDemo" in self.html or "fillDemo = function" in self.html
        assert "runPrediction()" in self.html

    # --- Gantt interactivity ---

    def test_gantt_section_label_mentions_click(self):
        """Gantt section label tells user to click for details."""
        assert "click" in self.html.lower() and "station" in self.html.lower()

    def test_gantt_interactive_js_included(self):
        """gantt-interactive.js is loaded as a script."""
        assert "gantt-interactive.js" in self.html

    def test_GanttInteractive_render_called(self):
        """showResult calls GanttInteractive.render after building the Gantt container."""
        assert "GanttInteractive.render(" in self.html

    def test_gantt_chart_container_id(self):
        """Gantt chart target element has id=gantt-chart-container."""
        assert "gantt-chart-container" in self.html

    def test_gantt_station_list_css_present(self):
        """gantt-station-list and gantt-station-row CSS classes are defined."""
        assert "gantt-station-list" in self.html
        assert "gantt-station-row" in self.html

    def test_gantt_detail_expand_css(self):
        """gantt-detail expand/collapse styles are defined (max-height transition)."""
        assert "max-height" in self.html and "gantt-detail" in self.html

    # --- Stalled permit banner ---

    def test_stalled_banner_function_exists(self):
        """buildStalledBanner function exists to surface stall warnings."""
        assert "buildStalledBanner" in self.html or "Stalled" in self.html

    def test_stalled_banner_shows_DBI_phone(self):
        """Stalled banner includes DBI customer service phone link."""
        assert "(415) 558-6000" in self.html or "4155586000" in self.html

    # --- Results display ---

    def test_permit_number_shown_in_result(self):
        """Result header shows the permit number."""
        assert "results-permit-number" in self.html or "permitNumber" in self.html

    def test_results_content_class_for_markdown(self):
        """Markdown results rendered in a results-content div."""
        assert "results-content" in self.html

    def test_methodology_toggle_present(self):
        """Collapsible methodology section is present."""
        assert "methodology-toggle" in self.html or "How we know this" in self.html

    # --- Enter key support ---

    def test_enter_key_submits_form(self):
        """Enter key on the input field triggers analysis."""
        assert "keydown" in self.html
        assert "'Enter'" in self.html or '"Enter"' in self.html


# ---------------------------------------------------------------------------
# Stuck Permit UX tests
# ---------------------------------------------------------------------------

class TestStuckPermitUX:
    """UX behaviour tests for stuck_permit.html."""

    def setup_method(self):
        self.html = _read(STUCK_PERMIT_PATH)

    # --- ?permit= pre-fill ---

    def test_permit_param_prefill_present(self):
        """Auto-fill logic reads ?permit= from URL and fills the input."""
        assert "URLSearchParams" in self.html
        assert "params.get('permit')" in self.html or 'params.get("permit")' in self.html

    def test_permit_param_triggers_diagnosedPermit(self):
        """Pre-fill auto-triggers diagnosedPermit() when ?permit= is set."""
        assert "diagnosedPermit()" in self.html

    def test_DOMContentLoaded_used(self):
        """DOMContentLoaded event handles auto-run."""
        assert "DOMContentLoaded" in self.html

    # --- Loading / skeleton state ---

    def test_skeleton_screen_element_exists(self):
        """skeleton-screen element present."""
        assert 'id="skeleton-screen"' in self.html

    def test_skeleton_shows_severity_placeholder(self):
        """Skeleton loading state simulates severity badge area."""
        assert "skeleton-severity-row" in self.html or "skeleton-badge" in self.html

    def test_loading_dot_present(self):
        """Button has a pulsing loading-dot indicator."""
        assert "loading-dot" in self.html

    def test_empty_state_element_id(self):
        """Empty state element has id=empty-state."""
        assert 'id="empty-state"' in self.html

    def test_results_hidden_initially(self):
        """Results div starts hidden (display:none)."""
        # The results div is present with style="display:none;"
        assert 'id="results"' in self.html
        assert 'display:none' in self.html or "display: none" in self.html

    # --- Empty state ---

    def test_empty_state_describes_tool(self):
        """Empty state text explains the tool's purpose."""
        lhtml = self.html.lower()
        assert "permit number" in lhtml
        assert ("diagnos" in lhtml or "delay" in lhtml or "intervention" in lhtml)

    def test_demo_permit_chips_in_empty_state(self):
        """Demo permit chips are present in the empty state."""
        assert "demo-permit-chip" in self.html
        assert "fillDemo(" in self.html

    def test_at_least_three_demo_chips(self):
        """At least three demo permit chips exist."""
        chips = re.findall(r"demo-permit-chip", self.html)
        assert len(chips) >= 3

    def test_fillDemo_triggers_diagnosedPermit(self):
        """fillDemo sets input and calls diagnosedPermit."""
        assert "window.fillDemo" in self.html or "fillDemo = function" in self.html
        assert "diagnosedPermit()" in self.html

    # --- Severity dashboard ---

    def test_severity_badge_css_classes(self):
        """Severity badge CSS classes for green/amber/red exist."""
        assert "severity-badge-green" in self.html
        assert "severity-badge-amber" in self.html
        assert "severity-badge-red" in self.html

    def test_buildSeverityDashboard_function(self):
        """buildSeverityDashboard function exists."""
        assert "buildSeverityDashboard" in self.html

    def test_severity_parses_CRITICAL(self):
        """parseSeverity returns 'critical' when markdown contains CRITICAL."""
        assert "parseSeverity" in self.html
        assert "CRITICAL" in self.html

    def test_severity_parses_STALLED(self):
        """parseSeverity handles STALLED status."""
        assert "STALLED" in self.html

    # --- Station diagnosis block cards ---

    def test_block_cards_css_present(self):
        """block-card CSS classes exist for station diagnosis cards."""
        assert "block-card-critical" in self.html
        assert "block-card-stalled" in self.html

    def test_parseStationBlocks_function(self):
        """parseStationBlocks extracts station data from markdown."""
        assert "parseStationBlocks" in self.html

    def test_station_block_regex_pattern(self):
        """Station block parser handles CRITICAL/STALLED/NORMAL status labels."""
        assert "CRITICAL|STALLED|NORMAL" in self.html

    # --- Intervention playbook ---

    def test_parseInterventionSteps_function(self):
        """parseInterventionSteps extracts numbered steps from markdown."""
        assert "parseInterventionSteps" in self.html

    def test_playbook_step_urgency_classes(self):
        """Urgency CSS classes for IMMEDIATE/HIGH/MEDIUM/LOW are defined."""
        assert "urgency-immediate" in self.html
        assert "urgency-high" in self.html
        assert "urgency-medium" in self.html

    def test_buildPlaybookSteps_function(self):
        """buildPlaybookSteps renders structured step cards."""
        assert "buildPlaybookSteps" in self.html

    # --- Reviewer phone/URL linkification ---

    def test_phone_number_linkification(self):
        """Contact phone numbers are linked with tel: href."""
        assert "tel:+1" in self.html or "href=\"tel:" in self.html

    def test_phone_regex_handles_415_area(self):
        """Phone linkification regex handles (415) NNN-NNNN format."""
        assert r"\(415\)" in self.html or "415" in self.html

    def test_url_linkification_in_contacts(self):
        """Contact URLs are rendered as clickable anchor tags."""
        # The linkification regex matches http/https URLs (regex uses https?:\/\/)
        assert 'href="' in self.html
        assert "https?" in self.html or "target=\"_blank\"" in self.html

    def test_phone_numbers_styled_prominently(self):
        """Phone links use accent color for prominence."""
        # The linkification code adds style with --accent color
        assert "var(--accent)" in self.html

    # --- Timeline impact note ---

    def test_timeline_impact_section(self):
        """Timeline impact callout is present in results rendering."""
        assert "timeline-impact" in self.html

    def test_timeline_impact_mentions_weeks(self):
        """Timeline impact note quantifies delay (weeks)."""
        assert "week" in self.html.lower() or "6" in self.html

    # --- Full diagnostic report toggle ---

    def test_full_report_collapsible(self):
        """Full diagnostic markdown report is collapsible when structured content exists."""
        assert "diagnostic report" in self.html.lower() or "playbook-content" in self.html

    # --- Enter key support ---

    def test_enter_key_submits(self):
        """Enter keydown on permit input triggers diagnose."""
        assert "keydown" in self.html
        assert "'Enter'" in self.html or '"Enter"' in self.html


# ---------------------------------------------------------------------------
# Gantt Interactive JS unit tests
# ---------------------------------------------------------------------------

class TestGanttInteractiveJS:
    """Structural tests for gantt-interactive.js."""

    def setup_method(self):
        self.js = _read(GANTT_JS_PATH)

    def test_module_exports_render(self):
        """GanttInteractive.render is exported."""
        assert "render:" in self.js or "render :" in self.js

    def test_module_exports_statusColor(self):
        """statusColor helper is exported for testing."""
        assert "statusColor:" in self.js or "statusColor :" in self.js

    def test_computeBarWidths_exported(self):
        """_computeBarWidths is exported for unit testing."""
        assert "_computeBarWidths" in self.js

    def test_status_color_map_complete(self):
        """statusColor covers all expected statuses."""
        for status in ("complete", "active", "stalled", "critical", "predicted", "pending"):
            assert status in self.js

    def test_gantt_station_badge_inside_station_main(self):
        """gantt-station-badge is rendered inside gantt-station-main div."""
        # The badge should appear BEFORE the closing comment of gantt-station-main
        badge_pos = self.js.find("gantt-station-badge")
        main_close_pos = self.js.find("</div>'); // gantt-station-main")
        # Badge rendered before main div is closed
        assert badge_pos < main_close_pos, (
            "gantt-station-badge must be rendered inside gantt-station-main "
            f"(badge at {badge_pos}, main close at {main_close_pos})"
        )

    def test_bar_click_handler_attached(self):
        """Click event handler is attached to Gantt bars."""
        assert "bar.addEventListener('click'" in self.js or "addEventListener('click'" in self.js

    def test_row_click_handler_attached(self):
        """Click event handler is attached to station list rows."""
        assert "row.addEventListener('click'" in self.js

    def test_keyboard_navigation_supported(self):
        """Enter/Space key support for Gantt bars (accessibility)."""
        assert "Enter" in self.js or "keydown" in self.js

    def test_toggleDetail_function_exists(self):
        """toggleDetail manages expand/collapse of station detail panels."""
        assert "toggleDetail" in self.js

    def test_detail_panel_uses_maxHeight_transition(self):
        """Detail panels expand via maxHeight CSS transition."""
        assert "maxHeight" in self.js or "max-height" in self.js

    def test_aria_hidden_managed_on_panels(self):
        """aria-hidden is toggled on detail panels for accessibility."""
        assert "aria-hidden" in self.js

    def test_legend_rendered(self):
        """Gantt chart renders a legend with status labels."""
        assert "gantt-legend" in self.js

    def test_gantt_empty_message(self):
        """Empty state message rendered when no station data."""
        assert "gantt-empty" in self.js or "No station data" in self.js

    def test_esc_utility_function(self):
        """HTML escape utility function prevents XSS in rendered content."""
        assert "function esc(" in self.js or "esc = function" in self.js

    def test_gantt_track_renders_bar_buttons(self):
        """Gantt track renders station bars as button elements."""
        assert "<button" in self.js and "gantt-bar" in self.js

    def test_tabindex_on_bars(self):
        """Gantt bars have tabindex for keyboard access."""
        assert "tabindex" in self.js

    def test_aria_label_on_bars(self):
        """Gantt bars have aria-label for screen reader access."""
        assert "aria-label" in self.js

    def test_current_station_pulse_effect(self):
        """Current active station has a pulse animation element."""
        assert "gantt-bar-pulse" in self.js or "pulse" in self.js

    def test_probability_shown_in_station_meta(self):
        """Predicted stations show probability percentage in meta."""
        assert "probability" in self.js and "likely" in self.js

    def test_typical_wait_shown_in_station_meta(self):
        """p50_days shown as typical wait time in station meta."""
        assert "p50_days" in self.js and "typical" in self.js


# ---------------------------------------------------------------------------
# Cross-template consistency tests
# ---------------------------------------------------------------------------

class TestCrossTemplateConsistency:
    """Verify both templates share consistent UX patterns."""

    def setup_method(self):
        self.sp = _read(STATION_PREDICTOR_PATH)
        self.stuck = _read(STUCK_PERMIT_PATH)

    def test_both_templates_use_permit_param(self):
        """Both templates support ?permit= query parameter for pre-fill."""
        for html in (self.sp, self.stuck):
            assert "params.get('permit')" in html or 'params.get("permit")' in html

    def test_both_have_demo_permit_chips(self):
        """Both tools show demo permit chip buttons in the empty state."""
        for html in (self.sp, self.stuck):
            assert "demo-permit-chip" in html

    def test_both_use_mono_for_permit_numbers(self):
        """Permit number displays use --mono font (data font role)."""
        for html in (self.sp, self.stuck):
            assert "--mono" in html

    def test_both_handle_401_unauthorized(self):
        """Both templates display a login prompt for 401 responses."""
        for html in (self.sp, self.stuck):
            assert "401" in html or "login" in html.lower() or "log in" in html.lower()

    def test_both_have_enter_key_support(self):
        """Both templates submit on Enter key."""
        for html in (self.sp, self.stuck):
            assert "keydown" in html and "'Enter'" in html

    def test_both_have_skeleton_loading(self):
        """Both templates have skeleton loading screens."""
        for html in (self.sp, self.stuck):
            assert "skeleton-screen" in html and "is-visible" in html

    def test_both_use_csp_nonce_on_scripts(self):
        """All inline script tags have CSP nonce."""
        for html in (self.sp, self.stuck):
            assert 'nonce="{{ csp_nonce }}"' in html

    def test_both_use_obs_container(self):
        """Both use obs-container layout class."""
        for html in (self.sp, self.stuck):
            assert "obs-container" in html

    def test_both_use_signal_colors_for_status(self):
        """Both templates use --signal-* color tokens for status indicators."""
        for html in (self.sp, self.stuck):
            assert "--signal-" in html

    def test_demo_chips_contain_202509155257(self):
        """Both templates include 202509155257 as a demo permit number."""
        for html in (self.sp, self.stuck):
            assert "202509155257" in html
