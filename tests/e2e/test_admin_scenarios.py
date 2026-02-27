"""Playwright E2E tests for admin and security scenarios — Sprint 77-2.

Covers:
  Test 77-2-1: Admin ops page loads with tabs
  Test 77-2-2: SQL injection blocked in search
  Test 77-2-3: Directory traversal blocked
  Test 77-2-4: CSP headers present on every response
  Test 77-2-5: Anonymous user rate limiting on /search

Scenarios from scenario-design-guide.md referenced:
  SCENARIO-7  (admin ops access)
  SCENARIO-34 (CSP / security hardening)
  SCENARIO-40 (access control — non-admin blocked from admin routes)

Run standalone (recommended — avoids asyncio conflict with pytest-asyncio):
    pytest tests/e2e/test_admin_scenarios.py -v

Run against staging:
    E2E_BASE_URL=https://sfpermits-ai-staging-production.up.railway.app \\
    TEST_LOGIN_SECRET=<secret> \\
    pytest tests/e2e/test_admin_scenarios.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# ---------------------------------------------------------------------------
# Skip guard — same pattern as test_scenarios.py
# ---------------------------------------------------------------------------

_playwright_targeted = any(
    "test_admin_scenarios" in arg or "e2e" == os.path.basename(arg.rstrip("/"))
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
           "Run: pytest tests/e2e/test_admin_scenarios.py -v",
)

SCREENSHOT_DIR = Path("qa-results/screenshots/sprint77-2")


def _screenshot(page, name: str) -> None:
    """Capture a screenshot (best-effort — never fails the test)."""
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT_DIR / f"{name}.png"))
    except Exception:
        pass


# ===========================================================================
# Test 77-2-1: Admin ops page loads with tabs
# ===========================================================================


class TestAdminOpsPage:
    """SCENARIO-7: Admin ops page loads with its expected tab structure."""

    def test_admin_ops_loads(self, auth_page):
        """Admin user can load /admin/ops and sees the ops hub content."""
        pg = auth_page("admin")
        pg.goto(f"{pg._base_url}/admin/ops")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "admin-ops-hub")

        body = pg.text_content("body") or ""
        lower = body.lower()
        # The ops hub should identify itself as admin ops / pipeline / ops
        assert any(
            kw in lower for kw in ["ops", "pipeline", "admin", "quality"]
        ), "Admin ops page should have ops/pipeline/admin/quality content"

    def test_admin_ops_has_tabs(self, auth_page):
        """Admin ops page renders tab navigation elements."""
        pg = auth_page("admin")
        pg.goto(f"{pg._base_url}/admin/ops")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "admin-ops-tabs")

        # Check for tab-like elements — either <a> links or buttons labelled
        # with the known tab names (pipeline, quality, activity, feedback).
        body = pg.text_content("body") or ""
        lower = body.lower()
        tab_keywords = ["pipeline", "quality", "activity", "feedback"]
        found = [kw for kw in tab_keywords if kw in lower]
        assert len(found) >= 2, (
            f"Admin ops page should have at least 2 of the tab labels "
            f"(pipeline/quality/activity/feedback). Found: {found}"
        )

    def test_non_admin_ops_blocked(self, auth_page):
        """SCENARIO-40: A non-admin authenticated user is denied access to /admin/ops."""
        pg = auth_page("homeowner")
        resp = pg.goto(f"{pg._base_url}/admin/ops")
        _screenshot(pg, "non-admin-ops-blocked")

        current_url = pg.url
        body = pg.text_content("body") or ""
        lower = body.lower()

        # The page should NOT show ops-specific admin content to a homeowner.
        # Acceptable outcomes: redirect away, 403, or a "forbidden" message.
        is_blocked = (
            "/admin/ops" not in current_url  # redirected away
            or "forbidden" in lower
            or "403" in body
            or (resp and resp.status in (302, 403))
        )
        assert is_blocked, (
            "Non-admin user should be blocked from /admin/ops "
            f"(url={current_url}, status={resp.status if resp else 'n/a'})"
        )

    def test_anonymous_ops_redirect(self, page, live_server):
        """Anonymous visitor is redirected away from /admin/ops."""
        resp = page.goto(f"{live_server}/admin/ops")
        _screenshot(page, "anon-ops-redirect")

        current_url = page.url
        # Anonymous user should land on login page or get a non-200 status
        assert (
            "/auth/login" in current_url
            or "/login" in current_url
            or (resp and resp.status in (302, 403))
            or "login" in (page.text_content("body") or "").lower()
        ), f"Anonymous user should be redirected from /admin/ops (url={current_url})"


# ===========================================================================
# Test 77-2-2: SQL injection blocked in search
# ===========================================================================


class TestSQLInjectionSearch:
    """SCENARIO-34: SQL injection payloads in search do not cause 500 errors."""

    _INJECTION_PAYLOADS = [
        "' OR 1=1 --",
        "'; DROP TABLE permits; --",
        "' UNION SELECT NULL,NULL,NULL --",
        "1' AND '1'='1",
        "\" OR \"\"=\"",
    ]

    def test_sql_injection_no_500(self, page, live_server):
        """Primary SQL injection payload ' OR 1=1 -- must not produce a 500."""
        payload = "' OR 1=1 --"
        import urllib.parse
        encoded = urllib.parse.quote(payload)
        resp = page.goto(f"{live_server}/search?q={encoded}")
        _screenshot(page, "sql-injection-search")

        status = resp.status if resp else 0
        assert status != 500, (
            f"SQL injection payload should not produce HTTP 500 (got {status})"
        )
        # Also check the body doesn't contain a raw traceback
        body = page.text_content("body") or ""
        assert "Traceback" not in body, (
            "Server returned a Python traceback — injection may have caused an error"
        )

    def test_sql_injection_variants_no_500(self, page, live_server):
        """Multiple SQL injection variants should all be handled gracefully (no 500)."""
        import urllib.parse
        errors = []
        for payload in self._INJECTION_PAYLOADS:
            encoded = urllib.parse.quote(payload)
            resp = page.goto(f"{live_server}/search?q={encoded}")
            status = resp.status if resp else 0
            if status == 500:
                errors.append(f"Payload {payload!r} → HTTP 500")
            body = page.text_content("body") or ""
            if "Traceback" in body:
                errors.append(f"Payload {payload!r} → Python traceback in response")

        assert not errors, "SQL injection payloads caused errors:\n" + "\n".join(errors)

    def test_sql_injection_xss_combo_no_500(self, page, live_server):
        """Combined XSS + SQL payload handled gracefully."""
        import urllib.parse
        payload = "<script>alert('xss')</script>' OR 1=1 --"
        encoded = urllib.parse.quote(payload)
        resp = page.goto(f"{live_server}/search?q={encoded}")
        _screenshot(page, "sql-xss-combo")

        status = resp.status if resp else 0
        assert status != 500, f"XSS+SQL combo should not produce HTTP 500 (got {status})"
        body = page.content()
        assert "<script>alert" not in body, "XSS payload should be sanitized in rendered HTML"


# ===========================================================================
# Test 77-2-3: Directory traversal blocked
# ===========================================================================


class TestDirectoryTraversal:
    """Directory traversal attempts must not return file contents or 500 errors."""

    _TRAVERSAL_PATHS = [
        "/report/../../../etc/passwd",
        "/report/../../etc/hosts",
        "/../etc/shadow",
        "/static/../../../etc/passwd",
    ]

    def test_traversal_report_passwd(self, page, live_server):
        """Classic path traversal via /report returns 404 or redirect, not file."""
        resp = page.goto(f"{live_server}/report/../../../etc/passwd")
        _screenshot(page, "traversal-report-passwd")

        body = page.text_content("body") or ""
        # Must NOT expose passwd file contents
        assert "root:" not in body, "Directory traversal exposed /etc/passwd"
        assert "daemon:" not in body, "Directory traversal exposed /etc/passwd"
        # Should return 404 (path not found) or redirect, not 500
        status = resp.status if resp else 0
        assert status not in (200,) or "root:" not in body, (
            f"Response {status} must not contain /etc/passwd contents"
        )
        assert status != 500, f"Traversal attempt should not produce HTTP 500 (got {status})"

    def test_traversal_paths_no_file_contents(self, page, live_server):
        """Multiple traversal paths all return safe responses (no file contents, no 500)."""
        errors = []
        for path in self._TRAVERSAL_PATHS:
            try:
                resp = page.goto(f"{live_server}{path}")
                status = resp.status if resp else 0
                body = page.text_content("body") or ""
                if "root:" in body or "daemon:" in body:
                    errors.append(f"Path {path!r} exposed /etc/passwd contents")
                if status == 500:
                    errors.append(f"Path {path!r} → HTTP 500")
            except Exception as e:
                # Navigation errors (refused connection etc.) are acceptable
                pass

        assert not errors, "Traversal paths returned unsafe responses:\n" + "\n".join(errors)

    def test_traversal_etc_passwd_direct(self, page, live_server):
        """Direct path traversal attempt from root."""
        resp = page.goto(f"{live_server}/../etc/passwd")
        _screenshot(page, "traversal-root-passwd")

        status = resp.status if resp else 0
        body = page.text_content("body") or ""
        assert "root:" not in body, "Server exposed /etc/passwd via traversal"
        assert status != 500, f"Traversal should not cause HTTP 500 (got {status})"


# ===========================================================================
# Test 77-2-4: CSP headers present on every response
# ===========================================================================


class TestCSPHeaders:
    """SCENARIO-34: Content-Security-Policy header is present on all page responses."""

    _PAGES_TO_CHECK = [
        "/",
        "/search?q=test",
        "/auth/login",
        "/health",
        "/methodology",
    ]

    def test_csp_on_landing(self, page, live_server):
        """Landing page response includes Content-Security-Policy header."""
        resp = page.goto(live_server)
        _screenshot(page, "csp-landing")

        headers = resp.headers if resp else {}
        csp = headers.get("content-security-policy", "")
        assert csp, (
            "Landing page response missing Content-Security-Policy header"
        )
        # Should have at least default-src and script-src directives
        assert "default-src" in csp, "CSP must include default-src directive"

    def test_csp_on_search(self, page, live_server):
        """Search page response includes Content-Security-Policy header."""
        resp = page.goto(f"{live_server}/search?q=kitchen")
        _screenshot(page, "csp-search")

        headers = resp.headers if resp else {}
        csp = headers.get("content-security-policy", "")
        assert csp, "Search page response missing Content-Security-Policy header"

    def test_csp_on_login(self, page, live_server):
        """Login page response includes Content-Security-Policy header."""
        resp = page.goto(f"{live_server}/auth/login")
        _screenshot(page, "csp-login")

        headers = resp.headers if resp else {}
        csp = headers.get("content-security-policy", "")
        assert csp, "Login page response missing Content-Security-Policy header"

    def test_csp_blocks_framing(self, page, live_server):
        """Responses include frame-ancestors or X-Frame-Options to block framing."""
        resp = page.goto(live_server)

        headers = resp.headers if resp else {}
        csp = headers.get("content-security-policy", "")
        xfo = headers.get("x-frame-options", "")

        has_frame_ancestors = "frame-ancestors" in csp
        has_xfo = bool(xfo)
        assert has_frame_ancestors or has_xfo, (
            "Response should block framing via frame-ancestors CSP or X-Frame-Options"
        )

    def test_csp_multiple_pages(self, page, live_server):
        """CSP header is consistently present across multiple page types."""
        missing = []
        for path in self._PAGES_TO_CHECK:
            resp = page.goto(f"{live_server}{path}")
            if resp is None:
                continue
            headers = resp.headers
            csp = headers.get("content-security-policy", "")
            if not csp:
                missing.append(path)

        assert not missing, (
            f"These pages are missing Content-Security-Policy header: {missing}"
        )

    def test_security_headers_present(self, page, live_server):
        """Standard security headers (X-Content-Type-Options, Referrer-Policy) present."""
        resp = page.goto(live_server)

        headers = resp.headers if resp else {}
        xcto = headers.get("x-content-type-options", "")
        referrer = headers.get("referrer-policy", "")

        assert xcto == "nosniff", (
            f"X-Content-Type-Options should be 'nosniff' (got {xcto!r})"
        )
        assert referrer, "Referrer-Policy header should be set"


# ===========================================================================
# Test 77-2-5: Anonymous user rate limiting on /search
# ===========================================================================


class TestAnonymousRateLimiting:
    """SCENARIO-34: Anonymous users are rate-limited on /search after many rapid requests.

    The /search endpoint enforces RATE_LIMIT_MAX_LOOKUP = 15 requests per 60s window.
    Sending 20 requests in rapid succession should trigger a 429 or equivalent error.
    """

    def test_search_rate_limited_after_many_requests(self, page, live_server):
        """After 20 rapid /search requests, at least one returns 429 or rate-limit message."""
        rate_limit_triggered = False
        statuses = []

        for i in range(20):
            resp = page.goto(f"{live_server}/search?q=test{i}")
            status = resp.status if resp else 0
            statuses.append(status)
            if status == 429:
                rate_limit_triggered = True
                break
            # Also check body for rate-limit message (HTMX fragment response)
            body = page.text_content("body") or ""
            if "rate limit" in body.lower() or "wait a minute" in body.lower():
                rate_limit_triggered = True
                _screenshot(page, "rate-limit-triggered")
                break

        assert rate_limit_triggered, (
            f"Expected rate limiting after 20 rapid /search requests but none was triggered. "
            f"Status codes: {statuses}"
        )

    def test_search_rate_limit_message_is_friendly(self, page, live_server):
        """When rate-limited, the user gets a friendly message, not a raw 429 page."""
        # Exhaust the rate limit bucket
        rate_limited_response = None
        for i in range(25):
            resp = page.goto(f"{live_server}/search?q=ratelimit{i}")
            if resp and resp.status == 429:
                rate_limited_response = resp
                break
            body = page.text_content("body") or ""
            if "rate limit" in body.lower() or "wait a minute" in body.lower():
                rate_limited_response = resp
                _screenshot(page, "rate-limit-friendly-msg")
                break

        if rate_limited_response is None:
            pytest.skip(
                "Rate limit was not triggered after 25 requests — "
                "server may be resetting buckets per test session (TESTING mode)"
            )

        # The page should NOT show a raw server error
        body = page.text_content("body") or ""
        assert "Internal Server Error" not in body, (
            "Rate limit response should not show Internal Server Error"
        )
        assert "Traceback" not in body, (
            "Rate limit response should not show Python traceback"
        )
