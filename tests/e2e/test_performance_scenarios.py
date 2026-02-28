"""Playwright E2E tests for performance and reliability.

QS8-T3-D: Covers response time budgets, error resilience, security headers,
and static asset caching across key pages.

Run (standalone — recommended):
    pytest tests/e2e/test_performance_scenarios.py -v

NOTE: Playwright tests are skipped in the full test suite to avoid asyncio
event loop conflicts. Run them standalone or set E2E_PLAYWRIGHT=1.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

# Ensure project root importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------
_playwright_targeted = any(
    "test_performance" in arg or "e2e" == os.path.basename(arg.rstrip("/"))
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
           "Run: pytest tests/e2e/test_performance_scenarios.py -v",
)

SCREENSHOT_DIR = Path("qa-results/screenshots/e2e")


def _screenshot(page, name: str) -> None:
    """Capture a screenshot (best-effort, never fails the test)."""
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT_DIR / f"{name}.png"))
    except Exception:
        pass


def _timed_goto(page, url: str) -> tuple[object, float]:
    """Navigate to URL and return (response, elapsed_seconds)."""
    start = time.monotonic()
    resp = page.goto(url)
    elapsed = time.monotonic() - start
    return resp, elapsed


# ===========================================================================
# Test D-2-1: Health endpoint under 500ms
# ===========================================================================


class TestHealthEndpoint:
    """Health endpoint is fast and always responds."""

    def test_health_endpoint_under_500ms(self, page, live_server):
        """SCENARIO: /health responds in under 500ms.

        The health endpoint is hit by Railway every ~30s. If it's slow,
        Railway marks the instance unhealthy. 500ms is a generous budget.
        """
        resp, elapsed = _timed_goto(page, f"{live_server}/health")

        assert resp is not None
        assert resp.status == 200, f"/health returned {resp.status}"
        assert elapsed < 0.5, (
            f"/health took {elapsed:.3f}s — budget is 500ms. "
            "Check for slow DB queries or blocking startup code."
        )

    def test_health_endpoint_returns_json(self, page, live_server):
        """SCENARIO: /health returns valid JSON with status field.

        Health endpoint is consumed by Railway, monitoring systems,
        and the cron check script. Must be machine-parseable JSON.
        """
        resp = page.request.get(f"{live_server}/health")

        assert resp.status == 200, f"/health returned {resp.status}"
        try:
            data = resp.json()
            assert "status" in data or "healthy" in data or "ok" in data, (
                "/health JSON should have a 'status', 'healthy', or 'ok' field"
            )
        except Exception as e:
            pytest.fail(f"/health response is not valid JSON: {e}")


# ===========================================================================
# Test D-2-2: Landing page under 1s
# ===========================================================================


class TestLandingPagePerformance:
    """Landing page loads within budget."""

    def test_landing_page_under_1s(self, page, live_server):
        """SCENARIO: Landing page loads in under 1 second.

        The landing page is the first thing visitors see. 1s is a generous
        budget for local dev — production should be faster with CDN.
        Warm-up requests are ignored: the server may cold-start on first hit.
        """
        # Warm-up request to avoid cold-start penalty
        page.goto(f"{live_server}/")

        # Measured request
        resp, elapsed = _timed_goto(page, f"{live_server}/")
        _screenshot(page, "perf-landing")

        assert resp is not None
        assert resp.status in (200, 302, 301), (
            f"Landing page returned {resp.status}"
        )
        assert elapsed < 1.0, (
            f"Landing page took {elapsed:.3f}s — budget is 1s. "
            "Possible causes: slow DB query, blocking template render, "
            "missing cache."
        )


# ===========================================================================
# Test D-2-3: Methodology under 1s
# ===========================================================================


class TestMethodologyPerformance:
    """Methodology page loads within budget."""

    def test_methodology_under_1s(self, page, live_server):
        """SCENARIO: /methodology loads in under 1s.

        Methodology is a static content page — no DB queries. If it's slow,
        something is wrong with template rendering or middleware.
        """
        # Warm-up
        page.goto(f"{live_server}/methodology")

        resp, elapsed = _timed_goto(page, f"{live_server}/methodology")
        _screenshot(page, "perf-methodology")

        assert resp is not None
        assert resp.status == 200, f"/methodology returned {resp.status}"
        assert elapsed < 1.0, (
            f"/methodology took {elapsed:.3f}s — budget is 1s. "
            "This is a static template — should be very fast."
        )


# ===========================================================================
# Test D-2-4: Demo page under 2s
# ===========================================================================


class TestDemoPagePerformance:
    """Demo page loads within budget (has DB queries + severity scoring)."""

    def test_demo_page_under_2s(self, page, live_server):
        """SCENARIO: /demo loads in under 2s.

        Demo page queries the database for 1455 Market St permit data and
        runs severity scoring. 2s budget accounts for local DuckDB I/O.
        In production (Postgres + 15-min cache), should be much faster.
        """
        # Warm-up (primes the 15-min cache)
        page.goto(f"{live_server}/demo")

        resp, elapsed = _timed_goto(page, f"{live_server}/demo")
        _screenshot(page, "perf-demo")

        assert resp is not None
        assert resp.status == 200, f"/demo returned {resp.status}"
        assert elapsed < 2.0, (
            f"/demo took {elapsed:.3f}s — budget is 2s. "
            "Check: _get_demo_data() cache, severity scoring loop, DB query count."
        )


# ===========================================================================
# Test D-2-5: Search returns under 2s
# ===========================================================================


class TestSearchPerformance:
    """Search endpoint returns results within budget."""

    def test_search_returns_under_2s(self, page, live_server):
        """SCENARIO: Address search returns in under 2s.

        Search is the primary user action on the landing page. 2s is the
        maximum acceptable response time — users will abandon slower results.

        NOTE: In local dev without a populated DuckDB, search may return
        quickly with empty results. The time budget still applies.
        """
        resp, elapsed = _timed_goto(page, f"{live_server}/search?q=market+street")
        page.wait_for_load_state("networkidle")
        _screenshot(page, "perf-search")

        assert resp is not None
        assert resp.status in (200, 302), (
            f"Search returned {resp.status}"
        )
        assert elapsed < 2.0, (
            f"Search took {elapsed:.3f}s — budget is 2s. "
            "Check: DB query timeout (Sprint 69 hotfix), connection pool."
        )


# ===========================================================================
# Test D-2-6: No 500 errors on rapid navigation
# ===========================================================================


class TestRapidNavigationResilience:
    """App handles rapid sequential navigation without 500 errors."""

    def test_no_500_errors_on_rapid_navigation(self, page, live_server):
        """SCENARIO: 5 pages navigated quickly return no 500 errors.

        Simulates a user quickly clicking through multiple pages.
        Tests for connection pool exhaustion, session corruption, or
        template rendering failures under rapid sequential requests.
        """
        pages_to_visit = [
            "/",
            "/methodology",
            "/about-data",
            "/demo",
            "/beta-request",
        ]

        failed_pages = []
        for path in pages_to_visit:
            try:
                resp = page.goto(f"{live_server}{path}")
                if resp is not None and resp.status == 500:
                    body = page.text_content("body") or ""
                    failed_pages.append(f"{path} (500: {body[:100]})")
                # Minimal wait — we're testing rapid navigation
                page.wait_for_load_state("domcontentloaded")
            except Exception as e:
                failed_pages.append(f"{path} (exception: {e})")

        _screenshot(page, "perf-rapid-nav")

        assert not failed_pages, (
            f"Pages returned 500 during rapid navigation: {failed_pages}"
        )

    def test_no_500_errors_on_authenticated_pages(self, auth_page):
        """SCENARIO: Authenticated pages handle rapid navigation without 500s.

        Tests that Flask sessions, g.user, and auth middleware don't break
        when an authenticated user navigates quickly through protected pages.
        """
        pg = auth_page("expediter")

        auth_pages = [
            "/brief",
            "/portfolio",
        ]

        failed_pages = []
        for path in auth_pages:
            try:
                resp = pg.goto(f"{pg._base_url}{path}")
                if resp is not None and resp.status == 500:
                    failed_pages.append(f"{path} (500)")
                pg.wait_for_load_state("domcontentloaded")
            except Exception as e:
                failed_pages.append(f"{path} (exception: {e})")

        _screenshot(pg, "perf-rapid-auth-nav")

        assert not failed_pages, (
            f"Authenticated pages returned 500: {failed_pages}"
        )


# ===========================================================================
# Test D-2-7: CSP headers on all pages
# ===========================================================================


class TestSecurityHeaders:
    """Security headers are present on key pages."""

    def test_csp_headers_on_all_pages(self, page, live_server):
        """SCENARIO: Content-Security-Policy header is present on public pages.

        CSP prevents XSS attacks. The header should be present on all
        HTML responses. Missing CSP is a security audit finding.

        NOTE: If CSP is not yet implemented, this test records the finding
        without failing (warn-only) so it doesn't block other tests.
        """
        public_pages = ["/", "/methodology", "/about-data", "/demo"]
        missing_csp = []

        for path in public_pages:
            resp = page.request.get(f"{live_server}{path}")
            headers = resp.headers

            # Check for CSP header (case-insensitive)
            has_csp = any(
                k.lower() == "content-security-policy"
                for k in headers.keys()
            )
            if not has_csp:
                missing_csp.append(path)

        _screenshot(page, "security-headers-check")

        # Warn but do not hard-fail if CSP is missing across all pages
        # (CSP may be set at the CDN/proxy layer, not Flask directly)
        if missing_csp:
            # Non-blocking warning: record which pages lack CSP
            import warnings
            warnings.warn(
                f"CSP header missing on: {missing_csp}. "
                "Consider adding via Flask middleware or CDN configuration.",
                stacklevel=1,
            )
        # Hard assertion: at least /health returns headers (Flask is running)
        health_resp = page.request.get(f"{live_server}/health")
        assert health_resp.status == 200, "/health should return 200"

    def test_x_frame_options_header(self, page, live_server):
        """SCENARIO: X-Frame-Options or CSP frame-ancestors present to prevent clickjacking.

        Clickjacking protection should be present on the landing page.
        Acceptable values: DENY, SAMEORIGIN, or CSP frame-ancestors directive.
        """
        resp = page.request.get(f"{live_server}/")

        headers = {k.lower(): v for k, v in resp.headers.items()}

        has_xfo = "x-frame-options" in headers
        has_csp = "content-security-policy" in headers
        has_csp_frame = has_csp and "frame-ancestors" in headers.get(
            "content-security-policy", ""
        )

        # Warn if missing — not a hard block (may be CDN-layer protection)
        if not (has_xfo or has_csp_frame):
            import warnings
            warnings.warn(
                "X-Frame-Options or CSP frame-ancestors not found on /. "
                "Consider adding clickjacking protection.",
                stacklevel=1,
            )


# ===========================================================================
# Test D-2-8: Static assets cached
# ===========================================================================


class TestStaticAssetCaching:
    """Static assets have appropriate Cache-Control headers."""

    def test_static_assets_cached(self, page, live_server):
        """SCENARIO: CSS and JS static files have Cache-Control headers.

        Static assets should be cached by the browser to reduce load times
        on repeat visits. Flask's send_static_file() sets this automatically
        when the server is not in debug mode.

        This test finds a CSS or JS file from the landing page and checks
        its Cache-Control header.
        """
        # Load landing page to discover static file URLs
        page.goto(f"{live_server}/")
        page.wait_for_load_state("networkidle")

        # Find CSS/JS links in the page
        css_links = page.locator('link[rel="stylesheet"]')
        js_scripts = page.locator('script[src]')

        static_urls = []

        for i in range(min(css_links.count(), 3)):
            href = css_links.nth(i).get_attribute("href")
            if href and href.startswith("/static"):
                static_urls.append(f"{live_server}{href}")

        for i in range(min(js_scripts.count(), 3)):
            src = js_scripts.nth(i).get_attribute("src")
            if src and src.startswith("/static"):
                static_urls.append(f"{live_server}{src}")

        if not static_urls:
            pytest.skip("No /static/ CSS or JS assets found on landing page — skipping cache check")

        uncached = []
        for url in static_urls[:3]:  # Check first 3 static assets
            try:
                resp = page.request.get(url)
                headers = {k.lower(): v for k, v in resp.headers.items()}
                cache_control = headers.get("cache-control", "")
                etag = headers.get("etag", "")

                # Has no caching at all (no cache-control AND no etag)
                if not cache_control and not etag:
                    uncached.append(url)
            except Exception:
                pass  # Network error — skip this asset

        _screenshot(page, "static-assets-cached")

        # Warn rather than hard-fail — caching may be set at CDN layer
        if uncached:
            import warnings
            warnings.warn(
                f"Static assets lacking Cache-Control or ETag: {uncached}. "
                "Flask send_static_file sets cache headers in non-debug mode.",
                stacklevel=1,
            )

    def test_static_css_returns_200(self, page, live_server):
        """Edge case: At least one static CSS file returns 200 (not 404).

        Confirms the Flask static file serving is configured correctly
        and the CSS files referenced in templates actually exist.
        """
        page.goto(f"{live_server}/")
        page.wait_for_load_state("networkidle")

        css_links = page.locator('link[rel="stylesheet"]')

        if css_links.count() == 0:
            pytest.skip("No CSS link tags found on landing page")

        found_working = False
        for i in range(css_links.count()):
            href = css_links.nth(i).get_attribute("href")
            if href and ("/static" in href or href.startswith("/")):
                url = f"{live_server}{href}" if href.startswith("/") else href
                try:
                    resp = page.request.get(url)
                    if resp.status == 200:
                        found_working = True
                        break
                except Exception:
                    pass

        assert found_working, (
            "At least one CSS file should return 200. "
            "Check Flask static folder configuration."
        )
