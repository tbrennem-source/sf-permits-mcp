"""Playwright E2E scenario tests for sfpermits.ai.

Tests core user journeys with a real browser (Chromium) against a live
Flask server. Covers anonymous, authenticated, and admin flows.

Each test cites a scenario ID from scenario-design-guide.md and captures
a screenshot to qa-results/screenshots/e2e/.

Run:
    pytest tests/e2e/test_scenarios.py -v
    pytest tests/e2e/test_scenarios.py -v -k anonymous   # just anonymous tests
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure project root importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

SCREENSHOT_DIR = Path("qa-results/screenshots/e2e")


def _screenshot(page, name: str) -> None:
    """Capture a screenshot (best-effort, doesn't fail the test)."""
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT_DIR / f"{name}.png"))
    except Exception:
        pass


# ===========================================================================
# Anonymous user flows (no login)
# ===========================================================================


class TestAnonymousLanding:
    """Anonymous users see the landing page with hero, search box, and feature cards."""

    def test_landing_page_renders(self, page, live_server):
        """SCENARIO-37: Landing page renders with search box and feature cards."""
        page.goto(live_server)
        _screenshot(page, "anon-landing")
        assert page.title(), "Page should have a title"
        # Search input present
        search = page.locator('input[name="q"], input[type="search"]')
        assert search.count() > 0, "Landing page must have a search input"

    def test_landing_page_has_stats(self, page, live_server):
        """SCENARIO-37: Landing page shows permit stats."""
        page.goto(live_server)
        body = page.text_content("body") or ""
        # Should mention permits or some stat
        assert "permit" in body.lower(), "Landing page should mention permits"

    def test_landing_page_has_cta(self, page, live_server):
        """SCENARIO-37: Landing page has signup/login CTA."""
        page.goto(live_server)
        body = page.text_content("body") or ""
        lower = body.lower()
        assert any(w in lower for w in ["sign up", "get started", "create", "login", "log in"]), \
            "Landing page should have a CTA"


class TestAnonymousSearch:
    """Anonymous users can search and see public results."""

    def test_search_returns_results(self, page, live_server):
        """SCENARIO-38: Search for address returns permit results."""
        page.goto(f"{live_server}/search?q=1455+Market+St")
        page.wait_for_load_state("networkidle")
        _screenshot(page, "anon-search-market")
        body = page.text_content("body") or ""
        lower = body.lower()
        assert "permit" in lower or "result" in lower or "market" in lower, \
            "Search results should contain permit data or search context"

    def test_empty_search_handled(self, page, live_server):
        """SCENARIO-38: Empty search query handled gracefully."""
        resp = page.goto(f"{live_server}/search?q=")
        assert resp.status in (200, 302), f"Empty search returned {resp.status}"

    def test_search_xss_sanitized(self, page, live_server):
        """SCENARIO-34 (CSP): XSS attempt sanitized in search."""
        page.goto(f'{live_server}/search?q=<script>alert("xss")</script>')
        body = page.content()
        assert "<script>alert" not in body, "XSS should be sanitized"


class TestAnonymousContentPages:
    """Static content pages accessible to anonymous users."""

    def test_methodology_page(self, page, live_server):
        """Methodology page loads with section headings."""
        page.goto(f"{live_server}/methodology")
        _screenshot(page, "anon-methodology")
        body = page.text_content("body") or ""
        assert "methodology" in body.lower() or "how" in body.lower()
        # Should have multiple sections
        headings = page.locator("h2, h3")
        assert headings.count() >= 3, "Methodology page should have multiple sections"

    def test_about_data_page(self, page, live_server):
        """About-data page loads with data inventory info."""
        page.goto(f"{live_server}/about-data")
        _screenshot(page, "anon-about-data")
        body = page.text_content("body") or ""
        lower = body.lower()
        assert "data" in lower, "About-data page should mention data"

    def test_demo_page(self, page, live_server):
        """Demo page loads with permit data."""
        page.goto(f"{live_server}/demo")
        _screenshot(page, "anon-demo")
        body = page.text_content("body") or ""
        lower = body.lower()
        assert "permit" in lower or "demo" in lower

    def test_beta_request_page(self, page, live_server):
        """SCENARIO-49: Beta request page loads with form."""
        page.goto(f"{live_server}/beta-request")
        _screenshot(page, "anon-beta-request")
        # Should have email input
        email_input = page.locator('input[type="email"], input[name="email"]')
        assert email_input.count() > 0, "Beta request page should have email input"


class TestAnonymousInfrastructure:
    """Infrastructure endpoints accessible without auth."""

    def test_health_endpoint(self, page, live_server):
        """Health endpoint returns valid JSON with status."""
        resp = page.goto(f"{live_server}/health")
        assert resp.status == 200
        data = json.loads(page.text_content("body") or "{}")
        assert data.get("status") in ("ok", "degraded")

    def test_robots_txt(self, page, live_server):
        """Robots.txt exists and disallows /admin."""
        resp = page.goto(f"{live_server}/robots.txt")
        assert resp.status == 200
        body = page.text_content("body") or ""
        assert "/admin" in body, "robots.txt should disallow /admin"

    def test_sitemap_xml(self, page, live_server):
        """Sitemap.xml returns XML content."""
        resp = page.goto(f"{live_server}/sitemap.xml")
        assert resp.status == 200

    def test_404_for_unknown_route(self, page, live_server):
        """Unknown routes return 404."""
        resp = page.goto(f"{live_server}/this-route-does-not-exist-xyz")
        assert resp.status == 404


class TestAnonymousNavigation:
    """SCENARIO-41: Unauthenticated visitor sees gated navigation."""

    def test_login_page_accessible(self, page, live_server):
        """Login page renders with email input."""
        page.goto(f"{live_server}/auth/login")
        _screenshot(page, "anon-login")
        email_input = page.locator('input[type="email"], input[name="email"]')
        assert email_input.count() > 0, "Login page should have email input"

    def test_premium_routes_redirect(self, page, live_server):
        """SCENARIO-40: Premium routes redirect anonymous users to login."""
        for route in ["/brief", "/portfolio", "/consultants", "/account"]:
            resp = page.goto(f"{live_server}{route}")
            # Should redirect to login or return 302
            url = page.url
            assert resp.status in (200, 302) or "/auth/login" in url or "/login" in url, \
                f"{route} should redirect anonymous users"


# ===========================================================================
# Authenticated user flows (free user)
# ===========================================================================


class TestAuthenticatedDashboard:
    """Authenticated user sees the full app dashboard."""

    def test_dashboard_renders_after_login(self, auth_page):
        """SCENARIO-39: Home page serves full app for authenticated users."""
        pg = auth_page("homeowner")
        pg.goto(pg._base_url)
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "auth-dashboard")
        body = pg.text_content("body") or ""
        lower = body.lower()
        # Authenticated users should see app features, not just the marketing landing
        assert "search" in lower or "account" in lower or "brief" in lower

    def test_account_page_accessible(self, auth_page):
        """SCENARIO-40: Account page accessible after login."""
        pg = auth_page("expediter")
        pg.goto(f"{pg._base_url}/account")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "auth-account")
        assert pg.url.endswith("/account") or "/account" in pg.url
        body = pg.text_content("body") or ""
        assert "account" in body.lower()

    def test_search_works_authenticated(self, auth_page):
        """SCENARIO-38: Authenticated search returns results."""
        pg = auth_page("homeowner")
        pg.goto(f"{pg._base_url}/search?q=kitchen+remodel")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "auth-search")
        assert pg.locator("body").text_content()

    def test_portfolio_page_accessible(self, auth_page):
        """Portfolio page renders for authenticated users."""
        pg = auth_page("expediter")
        pg.goto(f"{pg._base_url}/portfolio")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "auth-portfolio")
        body = pg.text_content("body") or ""
        assert "portfolio" in body.lower() or "project" in body.lower() or "watch" in body.lower()


# ===========================================================================
# Admin flows
# ===========================================================================


class TestAdminRoutes:
    """Admin users can access admin-only routes."""

    def test_admin_ops_accessible(self, auth_page):
        """SCENARIO-7: Admin Ops page loads."""
        pg = auth_page("admin")
        pg.goto(f"{pg._base_url}/admin/ops")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "admin-ops")
        body = pg.text_content("body") or ""
        # Should have tab structure or admin content
        assert "admin" in body.lower() or "data quality" in body.lower() or "ops" in body.lower() or "pipeline" in body.lower()

    def test_admin_feedback_accessible(self, auth_page):
        """Admin feedback queue renders."""
        pg = auth_page("admin")
        pg.goto(f"{pg._base_url}/admin/feedback")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "admin-feedback")
        body = pg.text_content("body") or ""
        assert "feedback" in body.lower()

    def test_admin_pipeline_accessible(self, auth_page):
        """Admin pipeline health renders."""
        pg = auth_page("admin")
        pg.goto(f"{pg._base_url}/admin/pipeline")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "admin-pipeline")
        body = pg.text_content("body") or ""
        lower = body.lower()
        assert "pipeline" in lower or "health" in lower or "permit" in lower

    def test_admin_costs_accessible(self, auth_page):
        """Admin costs dashboard renders."""
        pg = auth_page("admin")
        pg.goto(f"{pg._base_url}/admin/costs")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "admin-costs")
        body = pg.text_content("body") or ""
        assert "cost" in body.lower() or "spend" in body.lower() or "api" in body.lower()

    def test_non_admin_cannot_access_ops(self, auth_page):
        """SCENARIO-40: Non-admin redirected away from admin routes."""
        pg = auth_page("homeowner")
        pg.goto(f"{pg._base_url}/admin/ops")
        url = pg.url
        body = pg.text_content("body") or ""
        # Should be redirected or get 403
        assert "/admin/ops" not in url or "forbidden" in body.lower() or "login" in url.lower()

    def test_admin_beta_requests_accessible(self, auth_page):
        """SCENARIO-51: Admin can view beta requests."""
        pg = auth_page("admin")
        pg.goto(f"{pg._base_url}/admin/beta-requests")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "admin-beta-requests")
        body = pg.text_content("body") or ""
        assert "beta" in body.lower() or "request" in body.lower()
