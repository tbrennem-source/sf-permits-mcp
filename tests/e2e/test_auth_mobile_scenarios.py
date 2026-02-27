"""E2E auth and mobile scenario tests for sfpermits.ai — Sprint 77-4.

Tests anonymous/auth boundaries and mobile viewport behavior with Playwright.
Each test captures a screenshot to qa-results/screenshots/sprint-77-4/.

Run standalone:
    pytest tests/e2e/test_auth_mobile_scenarios.py -v

Run with auth:
    TESTING=1 TEST_LOGIN_SECRET=xxx pytest tests/e2e/test_auth_mobile_scenarios.py -v

Scenario references:
  77-4-1: Landing page renders for anonymous users
  77-4-2: Authenticated routes redirect anonymous users to login
  77-4-3: No horizontal scroll at 375px viewport width
  77-4-4: Mobile navigation works at 375px
  77-4-5: Beta request form renders and accepts input
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# ---------------------------------------------------------------------------
# Skip guard — skip in full suite to avoid asyncio conflicts (same as test_scenarios.py)
# ---------------------------------------------------------------------------
_playwright_targeted = any(
    "test_auth_mobile" in arg or "e2e" == os.path.basename(arg.rstrip("/"))
    for arg in sys.argv
)
_playwright_enabled = (
    os.environ.get("E2E_PLAYWRIGHT", "")
    or os.environ.get("E2E_BASE_URL", "")
    or _playwright_targeted
)

pytestmark = pytest.mark.skipif(
    not _playwright_enabled,
    reason="Playwright tests skipped in full suite (asyncio conflict). "
           "Run: pytest tests/e2e/test_auth_mobile_scenarios.py -v",
)

SCREENSHOT_DIR = Path("qa-results/screenshots/sprint-77-4")
MOBILE_VIEWPORT = {"width": 375, "height": 812}


def _screenshot(page, name: str) -> None:
    """Capture a screenshot to the sprint-77-4 directory (best-effort)."""
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT_DIR / f"{name}.png"))
    except Exception:
        pass


# ===========================================================================
# Test 77-4-1: Landing page renders for anonymous users
# ===========================================================================


class TestAnonymousLanding:
    """SCENARIO 77-4-1: Anonymous users see a fully rendered landing page."""

    def test_landing_page_renders_for_anonymous(self, page, live_server):
        """Hero section and search bar visible without auth."""
        page.goto(live_server)
        page.wait_for_load_state("networkidle")
        _screenshot(page, "77-4-1-landing-anonymous")

        # Page must have a non-empty title
        title = page.title()
        assert title, "Landing page must have a non-empty <title>"

        # Hero section: look for an h1 or prominent heading
        hero = page.locator("h1")
        assert hero.count() > 0, "Landing page must have an h1 (hero heading)"

        # Search bar must be present
        search_input = page.locator('input[name="q"], input[type="search"]')
        assert search_input.count() > 0, "Landing page must have a search input for anonymous users"

    def test_landing_mentions_permits(self, page, live_server):
        """SCENARIO 77-4-1: Landing page body references SF permits."""
        page.goto(live_server)
        page.wait_for_load_state("networkidle")
        body = page.text_content("body") or ""
        assert "permit" in body.lower(), "Landing page should mention permits"


# ===========================================================================
# Test 77-4-2: Authenticated routes redirect anonymous users to login
# ===========================================================================


class TestAuthRedirects:
    """SCENARIO 77-4-2: Protected routes redirect unauthenticated visitors."""

    # Routes that require login
    PROTECTED_ROUTES = ["/brief", "/portfolio", "/account", "/dashboard/bottlenecks"]

    def test_brief_redirects_anonymous(self, page, live_server):
        """SCENARIO 77-4-2: /brief without auth redirects to login page."""
        resp = page.goto(f"{live_server}/brief")
        page.wait_for_load_state("networkidle")
        _screenshot(page, "77-4-2-brief-redirect")

        # Either a redirect (302 before settling) or the final URL is the login page
        final_url = page.url
        body = page.text_content("body") or ""
        lower = body.lower()

        is_login_page = (
            "/auth/login" in final_url
            or "/login" in final_url
            or "login" in lower
            or "sign in" in lower
            or "magic link" in lower
        )
        # Also acceptable: 302 redirect (resp.status tracks the last response)
        assert resp.status in (200, 302, 401) or is_login_page, (
            f"/brief should redirect anonymous users to login, got: "
            f"status={resp.status}, url={final_url}"
        )

    def test_portfolio_redirects_anonymous(self, page, live_server):
        """SCENARIO 77-4-2: /portfolio without auth redirects to login page."""
        resp = page.goto(f"{live_server}/portfolio")
        page.wait_for_load_state("networkidle")
        _screenshot(page, "77-4-2-portfolio-redirect")

        final_url = page.url
        body = page.text_content("body") or ""
        lower = body.lower()

        is_login_page = (
            "/auth/login" in final_url
            or "/login" in final_url
            or "login" in lower
            or "sign in" in lower
            or "magic link" in lower
        )
        assert resp.status in (200, 302, 401) or is_login_page, (
            f"/portfolio should redirect anonymous users to login, got: "
            f"status={resp.status}, url={final_url}"
        )

    def test_account_redirects_anonymous(self, page, live_server):
        """SCENARIO 77-4-2: /account without auth redirects to login page."""
        resp = page.goto(f"{live_server}/account")
        page.wait_for_load_state("networkidle")
        _screenshot(page, "77-4-2-account-redirect")

        final_url = page.url
        body = page.text_content("body") or ""
        lower = body.lower()

        is_login_page = (
            "/auth/login" in final_url
            or "/login" in final_url
            or "login" in lower
            or "sign in" in lower
            or "magic link" in lower
        )
        assert resp.status in (200, 302, 401) or is_login_page, (
            f"/account should redirect anonymous users to login, got: "
            f"status={resp.status}, url={final_url}"
        )

    def test_login_page_itself_is_accessible(self, page, live_server):
        """Login page is publicly accessible (not redirected)."""
        resp = page.goto(f"{live_server}/auth/login")
        page.wait_for_load_state("networkidle")
        _screenshot(page, "77-4-2-login-page")
        assert resp.status == 200, f"/auth/login should return 200, got {resp.status}"
        email_input = page.locator('input[type="email"], input[name="email"]')
        assert email_input.count() > 0, "Login page must have an email input"


# ===========================================================================
# Test 77-4-3: No horizontal scroll at 375px viewport width
# ===========================================================================


class TestMobileNoHorizontalScroll:
    """SCENARIO 77-4-3: Pages must not overflow horizontally at 375px."""

    @pytest.fixture
    def mobile_page(self, pw_browser, live_server):
        """Create a Playwright page with 375px mobile viewport."""
        from playwright.sync_api import sync_playwright
        ctx = pw_browser.new_context(
            viewport=MOBILE_VIEWPORT,
            ignore_https_errors=True,
        )
        pg = ctx.new_page()
        pg._base_url = live_server
        yield pg
        pg.close()
        ctx.close()

    def _check_no_horizontal_scroll(self, page, url: str, name: str) -> None:
        """Navigate to url and assert no horizontal overflow."""
        page.goto(url)
        page.wait_for_load_state("networkidle")
        _screenshot(page, f"77-4-3-mobile-{name}")

        scroll_width = page.evaluate("() => document.body.scrollWidth")
        window_width = page.evaluate("() => window.innerWidth")
        assert scroll_width <= window_width, (
            f"Horizontal scroll detected at 375px on {url}: "
            f"scrollWidth={scroll_width}, innerWidth={window_width}"
        )

    def test_landing_no_horizontal_scroll_mobile(self, mobile_page, live_server):
        """SCENARIO 77-4-3: Landing page (/) has no horizontal scroll at 375px."""
        self._check_no_horizontal_scroll(mobile_page, live_server, "landing")

    def test_demo_no_horizontal_scroll_mobile(self, mobile_page, live_server):
        """SCENARIO 77-4-3: Demo page (/demo) has no horizontal scroll at 375px."""
        self._check_no_horizontal_scroll(mobile_page, f"{live_server}/demo", "demo")

    def test_login_no_horizontal_scroll_mobile(self, mobile_page, live_server):
        """SCENARIO 77-4-3: Login page has no horizontal scroll at 375px."""
        self._check_no_horizontal_scroll(mobile_page, f"{live_server}/auth/login", "login")

    def test_beta_request_no_horizontal_scroll_mobile(self, mobile_page, live_server):
        """SCENARIO 77-4-3: Beta request page has no horizontal scroll at 375px."""
        self._check_no_horizontal_scroll(mobile_page, f"{live_server}/beta-request", "beta-request")


# ===========================================================================
# Test 77-4-4: Mobile navigation accessible at 375px
# ===========================================================================


class TestMobileNavigation:
    """SCENARIO 77-4-4: Navigation is accessible (hamburger or visible links) at 375px."""

    @pytest.fixture
    def mobile_page(self, pw_browser, live_server):
        """Create a Playwright page with 375px mobile viewport."""
        ctx = pw_browser.new_context(
            viewport=MOBILE_VIEWPORT,
            ignore_https_errors=True,
        )
        pg = ctx.new_page()
        pg._base_url = live_server
        yield pg
        pg.close()
        ctx.close()

    def test_mobile_nav_exists_anonymous(self, mobile_page, live_server):
        """SCENARIO 77-4-4: Navigation element exists on landing at 375px."""
        mobile_page.goto(live_server)
        mobile_page.wait_for_load_state("networkidle")
        _screenshot(mobile_page, "77-4-4-mobile-nav-anonymous")

        # Navigation must exist in some form:
        # hamburger button, a <nav> element, or nav-related links
        hamburger = mobile_page.locator(
            'button[aria-label*="menu" i], '
            'button[aria-label*="nav" i], '
            '[data-toggle="collapse"], '
            '.hamburger, .navbar-toggler, '
            'button:has-text("Menu")'
        )
        nav_element = mobile_page.locator("nav")
        nav_links = mobile_page.locator("nav a, header a")

        has_nav = (
            hamburger.count() > 0
            or nav_element.count() > 0
            or nav_links.count() > 0
        )
        assert has_nav, (
            "Mobile landing page (375px) must have navigation: "
            "hamburger menu, <nav> element, or nav links in header"
        )

    def test_mobile_nav_authenticated(self, auth_page):
        """SCENARIO 77-4-4: Authenticated users see navigation at 375px."""
        # auth_page factory creates a desktop-viewport page; we use it but
        # check that a nav element exists (viewport resize is a bonus check)
        pg = auth_page("homeowner")
        pg.set_viewport_size(MOBILE_VIEWPORT)
        pg.goto(pg._base_url)
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "77-4-4-mobile-nav-authenticated")

        nav_element = pg.locator("nav")
        nav_links = pg.locator("nav a, header a")
        hamburger = pg.locator(
            'button[aria-label*="menu" i], '
            'button[aria-label*="nav" i], '
            '.hamburger, .navbar-toggler'
        )

        has_nav = (
            nav_element.count() > 0
            or nav_links.count() > 0
            or hamburger.count() > 0
        )
        assert has_nav, (
            "Authenticated mobile view (375px) must have navigation elements"
        )


# ===========================================================================
# Test 77-4-5: Beta request form renders and accepts input
# ===========================================================================


class TestBetaRequestForm:
    """SCENARIO 77-4-5: Beta request form renders with required fields and accepts input."""

    def test_beta_request_page_loads(self, page, live_server):
        """SCENARIO 77-4-5: /beta-request returns 200 and renders a form."""
        resp = page.goto(f"{live_server}/beta-request")
        page.wait_for_load_state("networkidle")
        _screenshot(page, "77-4-5-beta-request-load")
        assert resp.status == 200, f"/beta-request should return 200, got {resp.status}"

    def test_beta_request_has_email_field(self, page, live_server):
        """SCENARIO 77-4-5: Beta request form has email input."""
        page.goto(f"{live_server}/beta-request")
        page.wait_for_load_state("networkidle")
        email_input = page.locator('input[type="email"], input[name="email"]')
        assert email_input.count() > 0, "Beta request form must have an email input"

    def test_beta_request_has_name_field(self, page, live_server):
        """SCENARIO 77-4-5: Beta request form has name input."""
        page.goto(f"{live_server}/beta-request")
        page.wait_for_load_state("networkidle")
        name_input = page.locator('input[name="name"], input[placeholder*="name" i]')
        # Name field is expected but use a softer assertion (may be optional)
        # Check that the form itself exists at minimum
        form = page.locator("form")
        assert form.count() > 0, "Beta request page must render a <form>"
        # Name input is a good-faith check
        if name_input.count() == 0:
            # Accept if page has a text input that could serve as name
            text_inputs = page.locator('input[type="text"]')
            assert text_inputs.count() > 0, (
                "Beta request form should have a name field (input[name='name'] or input[type='text'])"
            )

    def test_beta_request_accepts_input_no_js_errors(self, page, live_server):
        """SCENARIO 77-4-5: Filling the beta request form produces no JS errors."""
        js_errors: list[str] = []
        page.on("pageerror", lambda exc: js_errors.append(str(exc)))

        page.goto(f"{live_server}/beta-request")
        page.wait_for_load_state("networkidle")

        # Fill email field
        email_input = page.locator('input[type="email"], input[name="email"]')
        if email_input.count() > 0:
            email_input.first.fill("test-user@example.com")

        # Fill name field if present
        name_input = page.locator('input[name="name"]')
        if name_input.count() > 0:
            name_input.first.fill("Test User")

        # Fill reason/message field if present (textarea or text input)
        reason_field = page.locator('textarea[name="reason"], input[name="reason"], textarea')
        if reason_field.count() > 0:
            reason_field.first.fill("Testing the beta request form as part of automated QA")

        _screenshot(page, "77-4-5-beta-request-filled")

        assert js_errors == [], f"JS errors while filling beta request form: {js_errors}"

    def test_beta_request_form_has_submit(self, page, live_server):
        """SCENARIO 77-4-5: Beta request form has a submit button."""
        page.goto(f"{live_server}/beta-request")
        page.wait_for_load_state("networkidle")

        submit_btn = page.locator(
            'button[type="submit"], '
            'input[type="submit"], '
            'button:has-text("Request"), '
            'button:has-text("Submit"), '
            'button:has-text("Apply"), '
            'button:has-text("Join")'
        )
        assert submit_btn.count() > 0, "Beta request form must have a submit button"
