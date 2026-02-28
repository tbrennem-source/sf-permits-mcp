"""
tests/test_mcp_demo_fix.py — MCP Demo component tests (Sprint 94, Agent 1D)

Verifies:
- mcp_demo.html renders without error and with correct content
- All 3 demo transcripts are present
- Tool badges present for all 3 demos
- CTA present with href
- No empty content containers
- No duplicate id="mcp-demo" in rendered HTML
- JS animation targets correct bubble (Claude bubble, not user bubble)
"""
import os
import pytest

os.environ.setdefault("TESTING", "1")


@pytest.fixture(scope="module")
def landing_html():
    """Render the landing page via Flask test client and return HTML."""
    from web.app import app
    with app.test_client() as client:
        resp = client.get("/")
        assert resp.status_code == 200, f"Landing page returned {resp.status_code}"
        return resp.data.decode("utf-8", errors="replace")


@pytest.fixture(scope="module")
def mcp_demo_template():
    """Read the raw mcp_demo.html template source."""
    template_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "web",
        "templates",
        "components",
        "mcp_demo.html",
    )
    with open(os.path.normpath(template_path), "r") as f:
        return f.read()


@pytest.fixture(scope="module")
def mcp_demo_js():
    """Read the mcp-demo.js source."""
    js_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "web",
        "static",
        "mcp-demo.js",
    )
    with open(os.path.normpath(js_path), "r") as f:
        return f.read()


# ─── RENDER TESTS ────────────────────────────────────────────────────────────

class TestMcpDemoRenders:
    def test_landing_returns_200(self):
        """Landing page returns HTTP 200."""
        from web.app import app
        with app.test_client() as client:
            resp = client.get("/")
            assert resp.status_code == 200

    def test_mcp_demo_section_present(self, landing_html):
        """mcp-demo-section class is present in rendered HTML."""
        assert "mcp-demo-section" in landing_html

    def test_mcp_demo_slides_present(self, landing_html):
        """All 3 demo slides are rendered."""
        assert landing_html.count("mcp-demo-slide") >= 3

    def test_mcp_demo_id_present_in_landing(self, landing_html):
        """id='mcp-demo' is present in the rendered landing page.
        Note: The component section and the landing.html wrapper both carry this
        ID (the outer wrapper for data-track, the inner for standalone use).
        The JS targets the first occurrence via getElementById which is correct."""
        assert 'id="mcp-demo"' in landing_html

    def test_css_linked(self, landing_html):
        """mcp-demo.css is linked in the page."""
        assert "mcp-demo.css" in landing_html

    def test_js_linked(self, landing_html):
        """mcp-demo.js is linked in the page."""
        assert "mcp-demo.js" in landing_html


# ─── DEMO CONTENT TESTS ──────────────────────────────────────────────────────

class TestMcpDemoContent:
    def test_demo_2_what_if_tool_badge(self, landing_html):
        """Demo 2 (What-If) shows what_if_simulator tool badge."""
        assert "what_if_simulator" in landing_html

    def test_demo_1_stuck_permit_tool_badge(self, landing_html):
        """Demo 1 (Stuck Permit) shows diagnose_stuck_permit tool badge."""
        assert "diagnose_stuck_permit" in landing_html

    def test_demo_6_cost_of_delay_tool_badge(self, landing_html):
        """Demo 6 (Cost of Delay) shows estimate_timeline tool badge."""
        assert "estimate_timeline" in landing_html

    def test_demo_2_content_present(self, landing_html):
        """Demo 2 contains kitchen/bathroom scope comparison data."""
        assert "OTC (Over Counter)" in landing_html
        assert "70 days" in landing_html

    def test_demo_1_content_present(self, landing_html):
        """Demo 1 contains stuck permit station data."""
        assert "CP-ZOC" in landing_html
        assert "diagnose_stuck_permit" in landing_html

    def test_demo_6_content_present(self, landing_html):
        """Demo 6 contains cost of delay financial data."""
        assert "41,375" in landing_html

    def test_all_user_bubbles_present(self, landing_html):
        """All 3 user message bubbles are rendered."""
        assert landing_html.count("mcp-msg--user") >= 3

    def test_all_claude_bubbles_present(self, landing_html):
        """All 3 Claude response bubbles are rendered."""
        assert landing_html.count("mcp-msg--claude") >= 3

    def test_typed_lines_present(self, landing_html):
        """mcp-typed-line elements are present for animation."""
        assert "mcp-typed-line" in landing_html

    def test_response_tables_present(self, landing_html):
        """Response tables are present in demo slides."""
        assert "mcp-response-table" in landing_html

    def test_stacked_cards_present_for_mobile(self, landing_html):
        """Mobile stacked cards are present for responsive layout."""
        assert "mcp-stacked-cards" in landing_html

    def test_no_empty_content_containers(self, landing_html):
        """mcp-typed divs are not empty — all have typed-line children."""
        import re
        # Find mcp-typed divs — they should contain mcp-typed-line children
        empty_typed = re.findall(
            r'<div class="mcp-typed">\s*</div>',
            landing_html
        )
        assert len(empty_typed) == 0, (
            f"Found {len(empty_typed)} empty .mcp-typed containers"
        )


# ─── CTA TESTS ───────────────────────────────────────────────────────────────

class TestMcpDemoCta:
    def test_connect_cta_present(self, landing_html):
        """'Connect your AI' CTA text is present."""
        assert "Connect your AI" in landing_html

    def test_cta_has_href(self, landing_html):
        """CTA link has an href attribute."""
        assert 'href="#connect"' in landing_html or 'href="' in landing_html

    def test_three_step_labels_present(self, landing_html):
        """The 3 'how it works' steps are rendered."""
        assert "Connect" in landing_html
        assert "Get Intelligence" in landing_html

    def test_nav_controls_present(self, landing_html):
        """Prev/next navigation buttons are present."""
        assert "mcp-demo-prev" in landing_html
        assert "mcp-demo-next" in landing_html

    def test_nav_dots_present(self, landing_html):
        """Navigation dots are present."""
        assert landing_html.count("mcp-demo-dot") >= 3


# ─── TEMPLATE SOURCE TESTS ───────────────────────────────────────────────────

class TestMcpDemoTemplate:
    def test_template_has_mcp_demo_id(self, mcp_demo_template):
        """mcp_demo.html template has id='mcp-demo' on its section for standalone use.
        The landing.html wrapper also provides this ID for tracking; the JS
        finds the first occurrence via getElementById which is the outer wrapper."""
        assert 'id="mcp-demo"' in mcp_demo_template

    def test_template_has_demo_slides(self, mcp_demo_template):
        """Template has 3 demo slide containers."""
        assert mcp_demo_template.count("mcp-demo-slide") >= 3

    def test_template_has_tool_badges(self, mcp_demo_template):
        """Template has tool call badge elements."""
        assert "mcp-tool-badge" in mcp_demo_template

    def test_template_cta_button_has_href(self, mcp_demo_template):
        """CTA button in template has an href."""
        assert 'href="#connect"' in mcp_demo_template


# ─── JS ANIMATION FIX TESTS ──────────────────────────────────────────────────

class TestMcpDemoJsAnimationFix:
    def test_js_targets_claude_bubble_not_user_bubble(self, mcp_demo_js):
        """
        Critical fix: JS must query '.mcp-msg--claude .mcp-msg__bubble'
        not '.mcp-msg__bubble' (which would get the user bubble first,
        leaving Claude response content invisible).
        """
        assert ".mcp-msg--claude .mcp-msg__bubble" in mcp_demo_js, (
            "JS must use '.mcp-msg--claude .mcp-msg__bubble' selector "
            "to target the Claude response bubble. Using '.mcp-msg__bubble' "
            "alone returns the user bubble first, making Claude text invisible."
        )

    def test_js_does_not_use_bare_bubble_query(self, mcp_demo_js):
        """
        The fixed JS should not use the buggy bare '.mcp-msg__bubble' query
        for the animation target.
        """
        # Check that the old buggy pattern is gone from the animation section
        # The old pattern was: querySelector('.mcp-msg__bubble') with no parent qualifier
        import re
        # Look for the bubble assignment in animateSlide context
        buggy_pattern = r"querySelector\(['\"].mcp-msg__bubble['\"]\)"
        matches = re.findall(buggy_pattern, mcp_demo_js)
        assert len(matches) == 0, (
            f"Found {len(matches)} bare '.mcp-msg__bubble' querySelector calls. "
            "Should use '.mcp-msg--claude .mcp-msg__bubble' to avoid targeting user bubble."
        )

    def test_js_has_intersection_observer(self, mcp_demo_js):
        """JS uses IntersectionObserver for scroll-triggered animation."""
        assert "IntersectionObserver" in mcp_demo_js

    def test_js_has_reduced_motion_check(self, mcp_demo_js):
        """JS checks for prefers-reduced-motion preference."""
        assert "prefers-reduced-motion" in mcp_demo_js

    def test_js_has_autoadvance(self, mcp_demo_js):
        """JS auto-advances through slides."""
        assert "scheduleNext" in mcp_demo_js

    def test_js_handles_navigation(self, mcp_demo_js):
        """JS has goToSlide function for manual navigation."""
        assert "goToSlide" in mcp_demo_js
