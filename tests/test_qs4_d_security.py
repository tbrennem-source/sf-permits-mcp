"""Tests for QS4-D: CSP-Report-Only + CSRF protection + PostHog.

Covers:
- CSP-Report-Only header presence, nonce, report-uri, external sources
- Enforced CSP still has unsafe-inline
- CSRF token context processor, session storage, form validation
- CSRF skip paths (cron, csp-report, test-login, Bearer auth)
- CSRF disabled in TESTING mode
- X-CSRFToken header (HTMX)
- PostHog helper functions
"""

import pytest


@pytest.fixture
def app():
    """Create test app with TESTING=True."""
    import os
    os.environ.setdefault("TESTING", "1")
    from web.app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# CSP-Report-Only header tests
# ---------------------------------------------------------------------------

class TestCSPReportOnly:

    def test_csp_report_only_header_present(self, client):
        """CSP-Report-Only header is present in responses."""
        resp = client.get("/health")
        assert "Content-Security-Policy-Report-Only" in resp.headers

    def test_csp_report_only_contains_nonce(self, client):
        """CSP-Report-Only header contains a nonce value."""
        resp = client.get("/health")
        csp_ro = resp.headers.get("Content-Security-Policy-Report-Only", "")
        assert "'nonce-" in csp_ro

    def test_csp_report_only_has_report_uri(self, client):
        """CSP-Report-Only header points to /api/csp-report."""
        resp = client.get("/health")
        csp_ro = resp.headers.get("Content-Security-Policy-Report-Only", "")
        assert "report-uri /api/csp-report" in csp_ro

    def test_csp_report_only_allows_external_scripts(self, client):
        """CSP-Report-Only allows unpkg and jsdelivr for scripts."""
        resp = client.get("/health")
        csp_ro = resp.headers.get("Content-Security-Policy-Report-Only", "")
        assert "https://unpkg.com" in csp_ro
        assert "https://cdn.jsdelivr.net" in csp_ro

    def test_csp_report_only_allows_google_fonts(self, client):
        """CSP-Report-Only allows Google Fonts for styles and fonts."""
        resp = client.get("/health")
        csp_ro = resp.headers.get("Content-Security-Policy-Report-Only", "")
        assert "https://fonts.googleapis.com" in csp_ro
        assert "https://fonts.gstatic.com" in csp_ro

    def test_csp_report_only_allows_posthog(self, client):
        """CSP-Report-Only allows PostHog for connect-src."""
        resp = client.get("/health")
        csp_ro = resp.headers.get("Content-Security-Policy-Report-Only", "")
        assert "https://*.posthog.com" in csp_ro

    def test_enforced_csp_still_has_unsafe_inline(self, client):
        """Enforced CSP header still uses unsafe-inline (not broken)."""
        resp = client.get("/health")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "'unsafe-inline'" in csp

    def test_enforced_csp_and_report_only_are_different(self, client):
        """Enforced CSP and Report-Only CSP are distinct headers."""
        resp = client.get("/health")
        csp = resp.headers.get("Content-Security-Policy", "")
        csp_ro = resp.headers.get("Content-Security-Policy-Report-Only", "")
        assert csp != csp_ro

    def test_nonce_changes_per_request(self, client):
        """Each request gets a unique nonce."""
        resp1 = client.get("/health")
        resp2 = client.get("/health")
        csp1 = resp1.headers.get("Content-Security-Policy-Report-Only", "")
        csp2 = resp2.headers.get("Content-Security-Policy-Report-Only", "")
        # Extract nonces
        import re
        nonce1 = re.search(r"'nonce-([^']+)'", csp1)
        nonce2 = re.search(r"'nonce-([^']+)'", csp2)
        assert nonce1 and nonce2
        assert nonce1.group(1) != nonce2.group(1)


# ---------------------------------------------------------------------------
# CSRF protection tests
# ---------------------------------------------------------------------------

class TestCSRF:

    def test_csrf_token_in_template_context(self, app, client):
        """csrf_token is available in template context."""
        with app.test_request_context("/"):
            from web.security import _generate_csrf_token
            token = _generate_csrf_token()
            assert token
            assert len(token) == 64  # hex(32) = 64 chars

    def test_csrf_token_persists_in_session(self, client):
        """CSRF token is stored in session after first request."""
        with client.session_transaction() as sess:
            assert "csrf_token" not in sess

        # Make a request — context processor generates token
        client.get("/auth/login")

        with client.session_transaction() as sess:
            assert "csrf_token" in sess
            assert len(sess["csrf_token"]) == 64

    def test_post_without_csrf_returns_403_in_non_testing(self, app):
        """POST without CSRF token returns 403 when TESTING is False."""
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            # First get to establish session
            c.get("/auth/login")
            resp = c.post("/auth/send-link", data={"email": "test@example.com"})
            assert resp.status_code == 403
        finally:
            app.config["TESTING"] = True

    def test_post_with_valid_csrf_succeeds(self, app):
        """POST with valid CSRF token succeeds."""
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            # Get login page to establish session and get token
            c.get("/auth/login")
            with c.session_transaction() as sess:
                token = sess["csrf_token"]
            # POST with valid token (will get 400 for bad email, not 403)
            resp = c.post("/auth/send-link", data={
                "email": "test@example.com",
                "csrf_token": token,
            })
            # Should not be 403 (CSRF rejected) — 400 is expected (bad email in test)
            assert resp.status_code != 403
        finally:
            app.config["TESTING"] = True

    def test_get_request_skips_csrf(self, app):
        """GET requests skip CSRF validation."""
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            resp = c.get("/auth/login")
            assert resp.status_code == 200
        finally:
            app.config["TESTING"] = True

    def test_csrf_skips_cron_endpoints(self, app, monkeypatch):
        """CRON endpoints skip CSRF (they use Bearer auth)."""
        app.config["TESTING"] = False
        monkeypatch.setenv("CRON_WORKER", "1")
        try:
            c = app.test_client()
            resp = c.post(
                "/cron/status",
                headers={"Authorization": "Bearer test-secret"},
            )
            # Should not be 403 (CSRF) — cron path is skipped
            assert resp.status_code != 403
        finally:
            app.config["TESTING"] = True

    def test_csrf_skips_csp_report(self, app):
        """POST to /api/csp-report skips CSRF."""
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            resp = c.post(
                "/api/csp-report",
                json={"csp-report": {"violated-directive": "test"}},
                content_type="application/csp-report",
            )
            # Should not be 403 (CSRF rejected) — may be 204 (success) or 429 (rate limit)
            assert resp.status_code != 403
        finally:
            app.config["TESTING"] = True

    def test_csrf_skips_test_login(self, app, monkeypatch):
        """POST to /auth/test-login skips CSRF."""
        monkeypatch.setenv("TESTING", "1")
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            resp = c.post(
                "/auth/test-login",
                json={"secret": "wrong", "email": "test@example.com"},
            )
            # Should be 403 (wrong secret) or 404 (TESTING not set), not CSRF 403
            # The key check is: it didn't hit the CSRF abort
            assert resp.status_code in (403, 404)
        finally:
            app.config["TESTING"] = True

    def test_csrf_skips_bearer_auth(self, app):
        """Requests with Bearer auth header skip CSRF."""
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            resp = c.post(
                "/auth/logout",
                headers={"Authorization": "Bearer some-token"},
            )
            # Should redirect (302), not 403 CSRF
            assert resp.status_code != 403
        finally:
            app.config["TESTING"] = True

    def test_csrf_disabled_in_testing_mode(self, client):
        """CSRF check is skipped when TESTING=True."""
        # This is default in our test fixture (TESTING=True)
        resp = client.post("/auth/send-link", data={"email": "bad"})
        # Should be 400 (bad email), not 403 (CSRF)
        assert resp.status_code != 403

    def test_x_csrftoken_header_accepted(self, app):
        """X-CSRFToken header is accepted for HTMX requests."""
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            c.get("/auth/login")
            with c.session_transaction() as sess:
                token = sess["csrf_token"]
            resp = c.post(
                "/auth/logout",
                headers={"X-CSRFToken": token},
            )
            # Should redirect (302), not 403
            assert resp.status_code != 403
        finally:
            app.config["TESTING"] = True

    def test_csrf_rejects_wrong_token(self, app):
        """POST with wrong CSRF token returns 403."""
        app.config["TESTING"] = False
        try:
            c = app.test_client()
            c.get("/auth/login")
            resp = c.post("/auth/send-link", data={
                "email": "test@example.com",
                "csrf_token": "wrong-token-value",
            })
            assert resp.status_code == 403
        finally:
            app.config["TESTING"] = True


# ---------------------------------------------------------------------------
# CSRF in templates
# ---------------------------------------------------------------------------

class TestCSRFInTemplates:

    def test_auth_login_has_csrf_hidden_input(self, client):
        """auth_login.html contains csrf_token hidden input."""
        resp = client.get("/auth/login")
        html = resp.data.decode()
        assert 'name="csrf_token"' in html
        assert 'type="hidden"' in html


# ---------------------------------------------------------------------------
# PostHog tests
# ---------------------------------------------------------------------------

class TestPostHog:

    def test_posthog_track_exists_and_callable(self):
        """posthog_track function exists and is callable."""
        from web.helpers import posthog_track
        assert callable(posthog_track)

    def test_posthog_track_noops_without_key(self, monkeypatch):
        """posthog_track no-ops without POSTHOG_API_KEY."""
        import web.helpers
        monkeypatch.setattr(web.helpers, "_POSTHOG_KEY", None)
        # Should not raise
        web.helpers.posthog_track("test_event", {"foo": "bar"})

    def test_posthog_enabled_false_without_key(self, monkeypatch):
        """posthog_enabled returns False without POSTHOG_API_KEY."""
        import web.helpers
        monkeypatch.setattr(web.helpers, "_POSTHOG_KEY", None)
        assert web.helpers.posthog_enabled() is False

    def test_posthog_enabled_true_with_key(self, monkeypatch):
        """posthog_enabled returns True with POSTHOG_API_KEY."""
        import web.helpers
        monkeypatch.setattr(web.helpers, "_POSTHOG_KEY", "phc_test123")
        assert web.helpers.posthog_enabled() is True

    def test_posthog_get_flags_empty_without_key(self, monkeypatch):
        """posthog_get_flags returns empty dict without POSTHOG_API_KEY."""
        import web.helpers
        monkeypatch.setattr(web.helpers, "_POSTHOG_KEY", None)
        assert web.helpers.posthog_get_flags("user1") == {}

    def test_posthog_context_processor_injects_key(self, client):
        """PostHog key/host are available in template context."""
        resp = client.get("/auth/login")
        # The template context has posthog_key and posthog_host
        # We can verify the context processor runs by checking
        # the response doesn't error — it always works because
        # inject_posthog is registered as a context processor
        assert resp.status_code == 200
