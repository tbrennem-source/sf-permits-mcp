"""Tests for HONEYPOT_MODE middleware, /join-beta routes, and scope guard.

Test isolation: uses DuckDB in-memory via the session-level _isolated_test_db
fixture (autouse, from conftest.py). App object imported from web.app.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with a temp database for isolation."""
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
    """Test client with TESTING=True and cleared rate buckets."""
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# HONEYPOT_MODE=1 redirect tests
# ---------------------------------------------------------------------------

def test_honeypot_mode_redirects_search(client, monkeypatch):
    """HONEYPOT_MODE=1: /search redirects to /join-beta."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/search", follow_redirects=False)
    assert resp.status_code in (301, 302)
    location = resp.headers.get("Location", "")
    assert "/join-beta" in location


def test_honeypot_mode_redirects_methodology(client, monkeypatch):
    """HONEYPOT_MODE=1: /methodology redirects to /join-beta."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/methodology", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/join-beta" in resp.headers.get("Location", "")


def test_honeypot_mode_allows_landing(client, monkeypatch):
    """HONEYPOT_MODE=1: / (landing page) is NOT redirected."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/", follow_redirects=False)
    # Must not redirect to /join-beta
    assert "/join-beta" not in resp.headers.get("Location", "")


def test_honeypot_mode_allows_join_beta(client, monkeypatch):
    """HONEYPOT_MODE=1: /join-beta itself is not redirected."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/join-beta", follow_redirects=False)
    assert resp.status_code == 200


def test_honeypot_mode_allows_health(client, monkeypatch):
    """HONEYPOT_MODE=1: /health is not redirected."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/health", follow_redirects=False)
    assert "/join-beta" not in resp.headers.get("Location", "")


def test_honeypot_mode_allows_demo_guided(client, monkeypatch):
    """HONEYPOT_MODE=1: /demo/guided is not redirected."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", True)
    resp = client.get("/demo/guided", follow_redirects=False)
    assert "/join-beta" not in resp.headers.get("Location", "")


def test_honeypot_mode_off_search_works(client, monkeypatch):
    """HONEYPOT_MODE=0: /search does NOT redirect to /join-beta."""
    import web.app as app_mod
    monkeypatch.setattr(app_mod, "HONEYPOT_MODE", False)
    resp = client.get("/search", follow_redirects=False)
    assert "/join-beta" not in resp.headers.get("Location", "")


# ---------------------------------------------------------------------------
# /join-beta GET
# ---------------------------------------------------------------------------

def test_join_beta_get_renders(client):
    """GET /join-beta returns 200 with form content."""
    resp = client.get("/join-beta")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8", errors="replace").lower()
    assert "beta" in html or "waitlist" in html or "launching" in html


def test_join_beta_get_with_ref(client):
    """GET /join-beta?ref=search passes ref to template."""
    resp = client.get("/join-beta?ref=search")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /join-beta POST — honeypot spam guard
# ---------------------------------------------------------------------------

def test_join_beta_honeypot_drops_bots(client):
    """POST with honeypot 'website' field filled returns 200.

    The beta DB write should NOT happen (only request_metrics write is allowed).
    We verify by checking the response status and confirming no beta INSERT was
    issued (any execute_write calls would be request_metrics, not beta_requests).
    """
    calls_made = []

    def _track_execute_write(sql, params=None, **kwargs):
        calls_made.append(sql)
        return None  # simulate success

    with patch("src.db.execute_write", side_effect=_track_execute_write):
        resp = client.post("/join-beta", data={
            "email": "bot@spam.com",
            "website": "http://spam.com",  # honeypot filled
        })
    assert resp.status_code == 200
    # No INSERT INTO beta_requests should have been issued
    beta_writes = [s for s in calls_made if "beta_requests" in s.lower()]
    assert len(beta_writes) == 0, f"Unexpected beta DB writes: {beta_writes}"


# ---------------------------------------------------------------------------
# /join-beta POST — happy path
# ---------------------------------------------------------------------------

def test_join_beta_post_valid_redirects(client):
    """POST with valid email redirects to /join-beta/thanks."""
    # execute_write and send_beta_confirmation_email are lazy-imported inside the route
    with patch("src.db.execute_write"), \
         patch("web.auth.send_beta_confirmation_email"):
        resp = client.post("/join-beta", data={
            "email": "user@example.com",
            "name": "Test User",
            "role": "homeowner",
        }, follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/join-beta/thanks" in resp.headers.get("Location", "")


def test_join_beta_post_invalid_email_shows_error(client):
    """POST with invalid email returns form with error."""
    resp = client.post("/join-beta", data={
        "email": "not-an-email",
    })
    assert resp.status_code == 200
    assert b"email" in resp.data.lower() or b"valid" in resp.data.lower()


# ---------------------------------------------------------------------------
# /join-beta/thanks
# ---------------------------------------------------------------------------

def test_join_beta_thanks_renders(client):
    """GET /join-beta/thanks shows thank-you content."""
    # query_one is lazy-imported inside the route; patch at src.db level
    with patch("src.db.query_one", return_value=(5,)):
        resp = client.get("/join-beta/thanks")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8", errors="replace").lower()
    assert "list" in html or "thanks" in html or "on the" in html


# ---------------------------------------------------------------------------
# Intent router: out_of_scope
# ---------------------------------------------------------------------------

def test_intent_out_of_scope_other_city():
    """Queries about other cities return out_of_scope intent."""
    from src.tools.intent_router import classify
    result = classify("permit in Oakland CA for kitchen remodel")
    # Oakland is in _OTHER_CITY_SIGNALS and has remodel (permit signal) — should pass through
    # Real out-of-scope: query with ONLY other city, no SF permit signal
    result2 = classify("weather forecast in Oakland California")
    assert result2.intent == "out_of_scope"


def test_intent_out_of_scope_non_permit():
    """Queries matching non-permit topics (without SF permit signals) return out_of_scope."""
    from src.tools.intent_router import classify
    # "dog license" is in _NON_PERMIT_SIGNALS; no SF permit signal present
    result = classify("how do I get a dog license in san francisco")
    assert result.intent == "out_of_scope"


def test_intent_permit_query_not_out_of_scope():
    """A real SF permit query is NOT out_of_scope."""
    from src.tools.intent_router import classify
    result = classify("remodel kitchen permit")
    assert result.intent != "out_of_scope"


def test_intent_address_query_not_out_of_scope():
    """An address query is NOT flagged as out_of_scope."""
    from src.tools.intent_router import classify
    result = classify("123 Main St")
    assert result.intent != "out_of_scope"


def test_intent_short_query_not_out_of_scope():
    """Short queries (1 word) are not flagged as out_of_scope."""
    from src.tools.intent_router import classify
    result = classify("hello")
    assert result.intent != "out_of_scope"
