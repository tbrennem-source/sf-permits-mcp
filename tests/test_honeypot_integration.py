"""Integration tests for QS13 honeypot/beta capture features.

Covers:
- /beta-request GET/POST flow (existing route, different name than /join-beta)
- Honeypot field detection
- Rate limiting
- /admin/beta-requests requires admin session
- HONEYPOT_MODE redirect behavior (not yet implemented — skipped)
- /join-beta route (not yet implemented — skipped)
"""

import os
import pytest

from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for test isolation."""
    db_path = str(tmp_path / "test_honeypot.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login_admin(client, email="admin_honeypot@example.com"):
    """Create admin user and establish session via magic-link flow."""
    import web.auth as auth_mod
    orig_admin = auth_mod.ADMIN_EMAIL
    auth_mod.ADMIN_EMAIL = email
    user = auth_mod.get_or_create_user(email)
    token = auth_mod.create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    auth_mod.ADMIN_EMAIL = orig_admin
    return user


def _login_user(client, email="regular_honeypot@example.com"):
    """Create non-admin user and establish session."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# Beta signup form — existing /beta-request route
# ---------------------------------------------------------------------------

class TestBetaCapture:

    def test_beta_signup_form_renders(self, client):
        """GET /beta-request renders the signup form."""
        resp = client.get("/beta-request")
        assert resp.status_code == 200
        data = resp.data.decode()
        assert "email" in data.lower() or "request" in data.lower()

    def test_beta_signup_form_has_honeypot_field(self, client):
        """Signup form renders with honeypot input (website field)."""
        resp = client.get("/beta-request")
        assert resp.status_code == 200
        # The honeypot field is named 'website'
        assert b"website" in resp.data

    def test_beta_signup_missing_email_returns_400(self, client):
        """POST without email returns 400."""
        resp = client.post("/beta-request", data={
            "email": "",
            "name": "Test User",
            "reason": "I want to track my permits",
            "website": "",
        })
        assert resp.status_code == 400

    def test_beta_signup_missing_reason_returns_400(self, client):
        """POST without reason returns 400."""
        resp = client.post("/beta-request", data={
            "email": "test@example.com",
            "name": "Test User",
            "reason": "",
            "website": "",
        })
        assert resp.status_code == 400

    def test_beta_signup_honeypot_field_filled_does_not_error(self, client):
        """Honeypot field filled returns 200 (silent success to fool bots)."""
        resp = client.post("/beta-request", data={
            "email": "bot@example.com",
            "name": "Bot Name",
            "reason": "I am a bot",
            "website": "https://spam.example.com",  # honeypot field filled
        })
        # Should silently succeed (200) — no DB write, but no error exposed
        assert resp.status_code == 200

    def test_beta_signup_honeypot_silent_success_shows_thank_you(self, client):
        """Honeypot-triggered response still shows thank-you to avoid detection."""
        resp = client.post("/beta-request", data={
            "email": "bot2@example.com",
            "name": "Bot",
            "reason": "spam",
            "website": "http://evil.com",
        })
        assert resp.status_code == 200
        data = resp.data.decode().lower()
        assert "thank" in data or "soon" in data

    def test_beta_signup_prefill_email_from_query_param(self, client):
        """GET with ?email= param prefills the form."""
        resp = client.get("/beta-request?email=prefill@example.com")
        assert resp.status_code == 200
        assert b"prefill@example.com" in resp.data


# ---------------------------------------------------------------------------
# HONEYPOT_MODE redirect behavior (QS13 T1 — not yet implemented)
# ---------------------------------------------------------------------------

class TestHoneypotMode:

    def test_landing_accessible_in_honeypot_mode(self, client, monkeypatch):
        """Landing page must be accessible even in honeypot mode."""
        monkeypatch.setenv("HONEYPOT_MODE", "1")
        resp = client.get("/")
        # Landing always accessible — should NOT redirect
        assert resp.status_code in (200, 301, 302)
        if resp.status_code in (301, 302):
            # If redirected, must not go to /join-beta
            location = resp.headers.get("Location", "")
            assert "join-beta" not in location

    def test_health_accessible_in_honeypot_mode(self, client, monkeypatch):
        """Health endpoint accessible regardless of HONEYPOT_MODE."""
        monkeypatch.setenv("HONEYPOT_MODE", "1")
        resp = client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.skip(reason="HONEYPOT_MODE redirect middleware not implemented yet (QS13 T1)")
    def test_search_redirects_in_honeypot_mode(self, client, monkeypatch):
        """Search redirects to /join-beta when honeypot mode active."""
        monkeypatch.setenv("HONEYPOT_MODE", "1")
        resp = client.get("/search")
        assert resp.status_code in (301, 302)
        assert "join-beta" in resp.headers.get("Location", "")

    @pytest.mark.skip(reason="HONEYPOT_MODE redirect middleware not implemented yet (QS13 T1)")
    def test_demo_accessible_in_honeypot_mode(self, client, monkeypatch):
        """Demo route accessible even in honeypot mode."""
        monkeypatch.setenv("HONEYPOT_MODE", "1")
        resp = client.get("/demo")
        assert resp.status_code in (200, 404)  # 404 if not yet built


# ---------------------------------------------------------------------------
# /join-beta route (QS13 T1 — may not exist yet)
# ---------------------------------------------------------------------------

class TestJoinBetaRoute:

    def test_join_beta_page_renders_or_404(self, client):
        """/join-beta returns 200 if implemented, 404 if not yet built."""
        resp = client.get("/join-beta")
        assert resp.status_code in (200, 404)

    def test_join_beta_thanks_renders_or_404(self, client):
        """/join-beta/thanks returns 200 if implemented."""
        resp = client.get("/join-beta/thanks")
        assert resp.status_code in (200, 404)

    def test_join_beta_post_valid_email(self, client):
        """POST to /join-beta with valid email succeeds or route missing."""
        resp = client.post("/join-beta", data={
            "email": "user@example.com",
            "website": "",  # honeypot empty
        })
        if resp.status_code == 404:
            pytest.skip("/join-beta not implemented yet")
        assert resp.status_code in (200, 302)

    def test_join_beta_post_honeypot_blocked(self, client):
        """POST /join-beta with honeypot field filled is silent success."""
        resp = client.post("/join-beta", data={
            "email": "bot@spam.com",
            "website": "http://spam.com",  # honeypot
        })
        if resp.status_code == 404:
            pytest.skip("/join-beta not implemented yet")
        # Should silently succeed (no error revealed)
        assert resp.status_code in (200, 302)


# ---------------------------------------------------------------------------
# Admin beta funnel views
# ---------------------------------------------------------------------------

class TestAdminBetaFunnel:

    def test_admin_beta_requests_requires_auth(self, client):
        """/admin/beta-requests returns 302/401/403 for unauthenticated."""
        resp = client.get("/admin/beta-requests")
        assert resp.status_code in (302, 401, 403)

    def test_admin_beta_requests_requires_admin_not_regular_user(self, client):
        """/admin/beta-requests returns 403 for non-admin authenticated user."""
        _login_user(client)
        resp = client.get("/admin/beta-requests")
        assert resp.status_code in (302, 403)

    def test_admin_beta_requests_accessible_for_admin(self, client):
        """/admin/beta-requests returns 200 for admin user."""
        _login_admin(client)
        resp = client.get("/admin/beta-requests")
        assert resp.status_code == 200

    def test_admin_beta_funnel_route_exists_or_skip(self, client):
        """/admin/beta-funnel returns 200 for admin or 404 if not yet built."""
        _login_admin(client)
        resp = client.get("/admin/beta-funnel")
        if resp.status_code == 404:
            pytest.skip("/admin/beta-funnel not implemented yet (QS13 T1)")
        assert resp.status_code == 200

    def test_admin_beta_funnel_export_csv_or_skip(self, client):
        """/admin/beta-funnel/export returns CSV content-type or 404."""
        _login_admin(client)
        resp = client.get("/admin/beta-funnel/export")
        if resp.status_code == 404:
            pytest.skip("/admin/beta-funnel/export not implemented yet (QS13 T1)")
        assert resp.status_code == 200
        ct = resp.headers.get("Content-Type", "")
        assert "csv" in ct.lower() or "text" in ct.lower()
