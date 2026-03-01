"""Integration tests for HONEYPOT_MODE middleware — extended coverage.

Covers scenarios not in test_honeypot.py:
- Query parameter preservation on redirect
- /tools/* redirect behaviour
- /static/ and /demo/guided pass-through
- HONEYPOT_MODE=0 baseline
- Admin route pass-through
- /join-beta/thanks GET
- /admin/beta-funnel auth gate

These tests use DuckDB-in-memory via the session-level fixture and monkeypatch
web.app.HONEYPOT_MODE so no env var mutation is needed.
"""
import os
import pytest
from unittest.mock import patch

from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with a temp database for test isolation."""
    db_path = str(tmp_path / "test_honeypot_integration.duckdb")
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login_user(client, email="user@example.com"):
    """Create a non-admin user and log in via magic-link flow."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _login_admin(client, email="admin_int@example.com"):
    """Create admin user and log in."""
    import web.auth as auth_mod
    orig = auth_mod.ADMIN_EMAIL
    auth_mod.ADMIN_EMAIL = email
    user = auth_mod.get_or_create_user(email)
    token = auth_mod.create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    auth_mod.ADMIN_EMAIL = orig
    return user


# ---------------------------------------------------------------------------
# HONEYPOT_MODE=1 — redirect behaviour
# ---------------------------------------------------------------------------

def test_honeypot_redirects_search(client, monkeypatch):
    """GET /search → 302 redirect to /join-beta."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/search", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/join-beta" in resp.headers.get("Location", "")


def test_honeypot_search_preserves_query(client, monkeypatch):
    """GET /search?q=kitchen → redirect preserves q param + adds ref=search."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/search?q=kitchen", follow_redirects=False)
    assert resp.status_code in (301, 302)
    location = resp.headers.get("Location", "")
    assert "/join-beta" in location
    assert "q=kitchen" in location
    assert "ref=search" in location


def test_honeypot_redirects_station_predictor(client, monkeypatch):
    """GET /tools/station-predictor → redirect to /join-beta."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/tools/station-predictor", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/join-beta" in resp.headers.get("Location", "")


def test_honeypot_allows_landing(client, monkeypatch):
    """GET / is NOT redirected in honeypot mode."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/", follow_redirects=False)
    location = resp.headers.get("Location", "")
    assert "/join-beta" not in location


def test_honeypot_allows_health(client, monkeypatch):
    """GET /health is NOT redirected in honeypot mode."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/health", follow_redirects=False)
    assert "/join-beta" not in resp.headers.get("Location", "")


def test_honeypot_allows_static(client, monkeypatch):
    """GET /static/* is NOT redirected in honeypot mode."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    # /static/ prefix is in the allowed list — no redirect expected
    resp = client.get("/static/obsidian.css", follow_redirects=False)
    assert "/join-beta" not in resp.headers.get("Location", "")


def test_honeypot_allows_demo_guided(client, monkeypatch):
    """GET /demo/guided is NOT redirected in honeypot mode."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/demo/guided", follow_redirects=False)
    assert "/join-beta" not in resp.headers.get("Location", "")


def test_honeypot_allows_admin_prefix(client, monkeypatch):
    """GET /admin/* is NOT redirected in honeypot mode."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    # /admin/ prefix is exempt — should not get /join-beta redirect
    resp = client.get("/admin/beta-funnel", follow_redirects=False)
    location = resp.headers.get("Location", "")
    assert "/join-beta" not in location


# ---------------------------------------------------------------------------
# HONEYPOT_MODE=0 — baseline
# ---------------------------------------------------------------------------

def test_honeypot_off_search_not_redirected(client, monkeypatch):
    """HONEYPOT_MODE=0: /search is NOT redirected to /join-beta."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", False)
    resp = client.get("/search", follow_redirects=False)
    assert "/join-beta" not in resp.headers.get("Location", "")


# ---------------------------------------------------------------------------
# /join-beta POST — honeypot field guard
# ---------------------------------------------------------------------------

def test_join_beta_post_valid_redirects(client):
    """POST /join-beta with valid email → 302 to /join-beta/thanks."""
    with patch("src.db.execute_write"), \
         patch("web.auth.send_beta_confirmation_email"):
        resp = client.post("/join-beta", data={
            "email": "integration@example.com",
            "name": "Integration Test",
            "role": "homeowner",
        }, follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/join-beta/thanks" in resp.headers.get("Location", "")


def test_join_beta_post_honeypot_silently_drops(client):
    """POST /join-beta with 'website' honeypot field filled → 200, no DB write."""
    writes = []

    def _capture(sql, params=None, **kwargs):
        writes.append(sql)
        return None

    with patch("src.db.execute_write", side_effect=_capture):
        resp = client.post("/join-beta", data={
            "email": "bot@spam.example.com",
            "website": "https://spammy.example.com",
        })
    assert resp.status_code == 200
    beta_writes = [s for s in writes if "beta_requests" in s.lower()]
    assert len(beta_writes) == 0, f"Unexpected beta writes: {beta_writes}"


# ---------------------------------------------------------------------------
# /join-beta/thanks
# ---------------------------------------------------------------------------

def test_join_beta_thanks_loads(client):
    """GET /join-beta/thanks → 200 with meaningful content."""
    with patch("src.db.query_one", return_value=(42,)):
        resp = client.get("/join-beta/thanks")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8", errors="replace").lower()
    assert "thank" in html or "list" in html or "waitlist" in html


# ---------------------------------------------------------------------------
# /admin/beta-funnel — auth gate
# ---------------------------------------------------------------------------

def test_admin_beta_funnel_requires_login(client):
    """GET /admin/beta-funnel without auth → not 200 (redirect to login or 401/403)."""
    resp = client.get("/admin/beta-funnel", follow_redirects=False)
    # Must not serve the page to unauthenticated users
    assert resp.status_code != 200


def test_admin_beta_funnel_requires_admin(client):
    """GET /admin/beta-funnel with non-admin user → 403."""
    _login_user(client, "regular_int@example.com")
    resp = client.get("/admin/beta-funnel", follow_redirects=False)
    assert resp.status_code == 403


def test_admin_beta_funnel_accessible_to_admin(client):
    """GET /admin/beta-funnel with admin → 200."""
    _login_admin(client, "admin_funnel@example.com")
    resp = client.get("/admin/beta-funnel", follow_redirects=False)
    assert resp.status_code == 200
