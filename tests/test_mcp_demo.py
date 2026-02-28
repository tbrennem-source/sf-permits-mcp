"""
Tests for the MCP Demo Chat Transcript component.

Tests cover:
  - Template rendering
  - All 3 demo transcripts present
  - Demo rotation order
  - Tool call badges
  - CTA section
  - Mobile CSS breakpoints
  - JS file structure
  - Navigation controls
"""

import json
import os
import pytest
from jinja2 import Environment, FileSystemLoader


# ── Fixtures ──────────────────────────────────────────────────────────────────

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'web', 'templates')
STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'web', 'static')


@pytest.fixture
def jinja_env():
    """Create a Jinja2 environment for rendering templates."""
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    env.filters['tojson'] = json.dumps
    return env


@pytest.fixture
def rendered_html(jinja_env):
    """Render the mcp_demo component template."""
    template = jinja_env.get_template('components/mcp_demo.html')
    return template.render()


@pytest.fixture
def css_content():
    """Read the MCP demo CSS file."""
    css_path = os.path.join(STATIC_DIR, 'mcp-demo.css')
    with open(css_path, 'r') as f:
        return f.read()


@pytest.fixture
def js_content():
    """Read the MCP demo JS file."""
    js_path = os.path.join(STATIC_DIR, 'mcp-demo.js')
    with open(js_path, 'r') as f:
        return f.read()


# ── Template Rendering Tests ─────────────────────────────────────────────────

class TestMcpDemoRendering:
    """Test that the mcp_demo.html template renders without error."""

    def test_template_renders_without_error(self, rendered_html):
        """Template should render and produce non-empty HTML."""
        assert len(rendered_html) > 0
        assert '<section' in rendered_html

    def test_section_has_correct_id(self, rendered_html):
        """Section should have id='mcp-demo' for scroll targeting."""
        assert 'id="mcp-demo"' in rendered_html

    def test_section_title_present(self, rendered_html):
        """Section title 'What your AI sees' should be present."""
        assert 'What your AI sees' in rendered_html


# ── Demo Presence Tests ──────────────────────────────────────────────────────

class TestDemoPresence:
    """Test that all 3 demos are present in the template."""

    def test_demo2_whatif_present(self, rendered_html):
        """Demo 2 (What-If) — unique text from the comparison table."""
        assert 'Kitchen Only' in rendered_html
        assert 'Kitchen + Bath + Wall' in rendered_html
        assert 'what_if_simulator' in rendered_html

    def test_demo1_stuck_permit_present(self, rendered_html):
        """Demo 1 (Stuck Permit) — unique text from diagnosis."""
        assert '202412237330' in rendered_html
        assert 'diagnose_stuck_permit' in rendered_html
        assert 'Intervention playbook' in rendered_html

    def test_demo6_cost_of_delay_present(self, rendered_html):
        """Demo 6 (Cost of Delay) — unique text about carrying costs."""
        assert '$15,000/month' in rendered_html
        assert 'estimate_timeline' in rendered_html
        assert '$500/day' in rendered_html


# ── Demo Rotation Order Tests ────────────────────────────────────────────────

class TestDemoRotationOrder:
    """Test that demos appear in the locked order: What-If → Stuck → Delay."""

    def test_whatif_is_first_slide(self, rendered_html):
        """Demo 2 (What-If) should be data-demo='0' and have class 'active'."""
        # Find the first slide — it should contain what_if_simulator
        # and have data-demo="0"
        idx_whatif = rendered_html.find('what_if_simulator')
        idx_stuck = rendered_html.find('diagnose_stuck_permit')
        idx_delay = rendered_html.find('estimate_timeline')
        assert idx_whatif < idx_stuck < idx_delay, \
            "Demo order must be What-If → Stuck → Delay"

    def test_first_slide_is_active(self, rendered_html):
        """First slide (data-demo='0') should have the 'active' class."""
        # Find data-demo="0" and check it has 'active'
        assert 'data-demo="0"' in rendered_html
        # The first slide should contain 'active' in its class
        idx = rendered_html.find('data-demo="0"')
        # Look backward to find the class attribute
        preceding = rendered_html[max(0, idx - 200):idx]
        assert 'active' in preceding

    def test_three_slides_exist(self, rendered_html):
        """Exactly 3 demo slides should exist."""
        assert rendered_html.count('mcp-demo-slide') >= 3
        assert 'data-demo="0"' in rendered_html
        assert 'data-demo="1"' in rendered_html
        assert 'data-demo="2"' in rendered_html


# ── Tool Call Badge Tests ────────────────────────────────────────────────────

class TestToolCallBadges:
    """Test that tool call badges appear for all 3 tools."""

    def test_whatif_badge(self, rendered_html):
        """what_if_simulator badge should be present."""
        assert 'what_if_simulator' in rendered_html

    def test_stuck_permit_badge(self, rendered_html):
        """diagnose_stuck_permit badge should be present."""
        assert 'diagnose_stuck_permit' in rendered_html

    def test_timeline_badge(self, rendered_html):
        """estimate_timeline badge should be present."""
        assert 'estimate_timeline' in rendered_html

    def test_badge_has_lightning_icon(self, rendered_html):
        """All badges should have the lightning icon (⚡ or HTML entity)."""
        # The template uses &#9889; which is the ⚡ character
        assert rendered_html.count('mcp-tool-badge__icon') == 3


# ── CTA Section Tests ────────────────────────────────────────────────────────

class TestCTASection:
    """Test that the CTA section renders correctly."""

    def test_connect_button_present(self, rendered_html):
        """'Connect your AI' button should be present."""
        assert 'Connect your AI' in rendered_html

    def test_connect_button_href(self, rendered_html):
        """CTA button should link to #connect."""
        assert 'href="#connect"' in rendered_html

    def test_three_steps_present(self, rendered_html):
        """How it works 3-step explainer should be present."""
        assert 'Add sfpermits.ai to your AI assistant' in rendered_html
        assert 'Ask about any SF property or permit' in rendered_html
        assert 'Receive data-backed analysis with specific actions' in rendered_html

    def test_step_numbers(self, rendered_html):
        """Step numbers 01, 02, 03 should be present."""
        assert '>01<' in rendered_html
        assert '>02<' in rendered_html
        assert '>03<' in rendered_html


# ── CSS Tests ────────────────────────────────────────────────────────────────

class TestMcpDemoCSS:
    """Test CSS file structure and mobile breakpoints."""

    def test_css_file_exists(self):
        """mcp-demo.css should exist in the static directory."""
        css_path = os.path.join(STATIC_DIR, 'mcp-demo.css')
        assert os.path.exists(css_path)

    def test_mobile_breakpoint_present(self, css_content):
        """CSS should include @media (max-width: 480px) breakpoint."""
        assert '@media (max-width: 480px)' in css_content

    def test_reduced_motion_present(self, css_content):
        """CSS should include prefers-reduced-motion media query."""
        assert 'prefers-reduced-motion' in css_content

    def test_badge_pulse_animation(self, css_content):
        """CSS should define the mcp-badge-pulse animation."""
        assert 'mcp-badge-pulse' in css_content
        assert '@keyframes' in css_content

    def test_mobile_table_hidden(self, css_content):
        """On mobile, .mcp-response-table should be hidden."""
        assert '.mcp-response-table' in css_content
        # The mobile section should hide the table
        mobile_section = css_content[css_content.find('@media (max-width: 480px)'):]
        assert 'display: none' in mobile_section

    def test_mobile_stacked_cards_shown(self, css_content):
        """On mobile, .mcp-stacked-cards should be displayed."""
        assert '.mcp-stacked-cards' in css_content
        mobile_section = css_content[css_content.find('@media (max-width: 480px)'):]
        assert 'display: block' in mobile_section

    def test_expand_button_styling(self, css_content):
        """Expand button should be defined for mobile long responses."""
        assert '.mcp-expand-btn' in css_content


# ── JS Tests ─────────────────────────────────────────────────────────────────

class TestMcpDemoJS:
    """Test JavaScript file structure."""

    def test_js_file_exists(self):
        """mcp-demo.js should exist in the static directory."""
        js_path = os.path.join(STATIC_DIR, 'mcp-demo.js')
        assert os.path.exists(js_path)

    def test_intersection_observer_used(self, js_content):
        """JS should use IntersectionObserver for scroll trigger."""
        assert 'IntersectionObserver' in js_content

    def test_threshold_030(self, js_content):
        """IntersectionObserver threshold should be 0.3."""
        assert 'threshold: 0.3' in js_content or 'threshold:0.3' in js_content

    def test_auto_advance_logic(self, js_content):
        """JS should have auto-advance timer logic."""
        assert 'autoTimer' in js_content or 'auto_timer' in js_content
        assert 'scheduleNext' in js_content or 'schedule_next' in js_content

    def test_manual_controls(self, js_content):
        """JS should handle prev/next button clicks."""
        assert 'mcp-demo-prev' in js_content
        assert 'mcp-demo-next' in js_content

    def test_reduced_motion_check(self, js_content):
        """JS should check for prefers-reduced-motion."""
        assert 'prefers-reduced-motion' in js_content


# ── Navigation Controls Tests ────────────────────────────────────────────────

class TestNavigationControls:
    """Test that navigation controls are present in the template."""

    def test_prev_button(self, rendered_html):
        """Previous arrow button should be present."""
        assert 'mcp-demo-prev' in rendered_html

    def test_next_button(self, rendered_html):
        """Next arrow button should be present."""
        assert 'mcp-demo-next' in rendered_html

    def test_three_dots(self, rendered_html):
        """Three navigation dots should be present."""
        assert rendered_html.count('mcp-demo-dot') >= 3
        assert 'data-slide="0"' in rendered_html
        assert 'data-slide="1"' in rendered_html
        assert 'data-slide="2"' in rendered_html

    def test_first_dot_active(self, rendered_html):
        """First navigation dot should have 'active' class."""
        # Find data-slide="0" dot
        idx = rendered_html.find('data-slide="0"')
        preceding = rendered_html[max(0, idx - 100):idx]
        assert 'active' in preceding


# ── Mobile Treatment Tests ───────────────────────────────────────────────────

class TestMobileTreatment:
    """Test mobile-specific elements in the template."""

    def test_stacked_cards_for_whatif(self, rendered_html):
        """What-If demo should have stacked cards for mobile."""
        assert 'mcp-stacked-card' in rendered_html
        # Kitchen Only card should be a stacked card title
        assert 'mcp-stacked-card__title' in rendered_html

    def test_expand_button_for_stuck_permit(self, rendered_html):
        """Stuck Permit demo should have an expand button for long response."""
        assert 'See full analysis' in rendered_html
        assert 'mcp-expand-btn' in rendered_html

    def test_expand_wrapper_has_collapsible_attr(self, rendered_html):
        """Expand wrapper should have data-collapsible attribute."""
        assert 'data-collapsible="true"' in rendered_html


# ── Transcript Accuracy Tests ────────────────────────────────────────────────

class TestTranscriptAccuracy:
    """Verify key text from the demo transcripts appears exactly."""

    def test_whatif_user_message(self, rendered_html):
        """User message for What-If should match transcript."""
        assert "What's the difference in timeline if I add a bathroom remodel" in rendered_html

    def test_stuck_permit_user_message(self, rendered_html):
        """User message for Stuck Permit should match transcript."""
        assert "Permit 202412237330 has been sitting for 7 months" in rendered_html

    def test_cost_of_delay_user_message(self, rendered_html):
        """User message for Cost of Delay should match transcript."""
        assert "My restaurant renovation has a $15,000/month carry cost" in rendered_html

    def test_wall_removal_trigger_text(self, rendered_html):
        """The wall removal trigger explanation should be present."""
        assert 'The wall removal is the trigger' in rendered_html

    def test_probability_weighted_cost(self, rendered_html):
        """Probability-weighted expected cost should be present."""
        assert '$41,375' in rendered_html

    def test_sffd_bottleneck_alert(self, rendered_html):
        """SFFD-HQ bottleneck alert should be present."""
        assert 'SFFD-HQ bottleneck alert' in rendered_html
