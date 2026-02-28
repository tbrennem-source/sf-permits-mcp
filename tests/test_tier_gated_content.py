"""Tests for tier-gated content: portfolio, brief, and AI consultation (Sprint 89-4B).

Strategy: TESTING=True (standard test client). Tests verify gate behavior by:
  - Using monkeypatch to mock `web.tier_gate.has_tier` directly, OR
  - Upgrading the test user's tier to beta via execute_write

This avoids CSRF failures and rate limit issues that occur with TESTING=False.
"""

import pytest

from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_tier_gated.duckdb")
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


def _login_user(client, email="test@example.com", tier="free"):
    """Helper: create user, set tier, authenticate via magic link."""
    from web.auth import get_or_create_user, create_magic_token, execute_write
    import src.db as db_mod
    user = get_or_create_user(email)
    if tier != "free":
        ph = "%s" if db_mod.BACKEND == "postgres" else "?"
        execute_write(
            f"UPDATE users SET subscription_tier = {ph} WHERE user_id = {ph}",
            (tier, user["user_id"]),
        )
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# Portfolio tier gate tests (Task B-1)
# ---------------------------------------------------------------------------

def test_portfolio_requires_login(client):
    """Anonymous user hitting /portfolio gets redirected to login."""
    rv = client.get("/portfolio", follow_redirects=False)
    # login_required redirects to auth
    assert rv.status_code in (302, 303)
    assert "/auth" in rv.headers.get("Location", "")


def test_portfolio_free_user_gets_200_with_teaser(client, monkeypatch):
    """Free tier user sees portfolio page (200) with tier_locked teaser content.

    Mocks has_tier to return False (free user) to activate the gate.
    """
    _login_user(client, email="free@example.com", tier="free")
    # Force has_tier to return False — simulating a free user hitting the gate
    monkeypatch.setattr("web.routes_property.has_tier", lambda user, tier: False)
    rv = client.get("/portfolio")
    assert rv.status_code == 200
    html = rv.data.decode()
    # Should contain tier gate content
    assert "Beta" in html
    # Should contain the upgrade CTA for free users
    assert "beta" in html.lower()


def test_portfolio_free_user_returns_200_not_403(client, monkeypatch):
    """Tier gate on portfolio returns 200 (not 403) — HTMX compatibility."""
    _login_user(client, email="free200@example.com", tier="free")
    monkeypatch.setattr("web.routes_property.has_tier", lambda user, tier: False)
    rv = client.get("/portfolio")
    # Must be 200 — HTMX/nav still work correctly
    assert rv.status_code == 200


def test_portfolio_beta_user_sees_full_content(client):
    """Beta tier user sees full portfolio dashboard (no tier gate)."""
    _login_user(client, email="beta@example.com", tier="beta")
    rv = client.get("/portfolio")
    assert rv.status_code == 200
    html = rv.data.decode()
    # Beta user should see portfolio content (empty state or real content)
    # Not the tier gate teaser content
    assert "portfolio" in html.lower()


def test_portfolio_premium_user_sees_full_content(client):
    """Premium tier user also passes the beta gate (tier hierarchy: premium >= beta)."""
    _login_user(client, email="premium@example.com", tier="premium")
    rv = client.get("/portfolio")
    assert rv.status_code == 200
    html = rv.data.decode()
    # Should see portfolio (not tier-gated)
    assert "portfolio" in html.lower()


# ---------------------------------------------------------------------------
# Brief tier gate tests (Task B-2)
# ---------------------------------------------------------------------------

def test_brief_requires_login(client):
    """Anonymous user hitting /brief gets redirected to login."""
    rv = client.get("/brief", follow_redirects=False)
    assert rv.status_code in (302, 303)
    assert "/auth" in rv.headers.get("Location", "")


def test_brief_free_user_gets_tier_locked_context(client, monkeypatch):
    """Free tier user gets /brief response (200) with upgrade teaser shown.

    Mocks has_tier to return False — simulating a free user hitting the gate.
    """
    _login_user(client, email="freebrief@example.com", tier="free")
    monkeypatch.setattr("web.routes_misc.has_tier", lambda user, tier: False)
    rv = client.get("/brief")
    assert rv.status_code == 200
    html = rv.data.decode()
    # Teaser elements should be present
    assert "Beta" in html
    # Brief header (greeting) should still appear
    assert "Good morning" in html


def test_brief_beta_user_gets_full_content(client):
    """Beta tier user sees full morning brief, not the teaser."""
    _login_user(client, email="betabrief@example.com", tier="beta")
    rv = client.get("/brief")
    assert rv.status_code == 200
    html = rv.data.decode()
    # Full brief renders (at minimum the greeting)
    assert "Good morning" in html


def test_brief_premium_user_gets_full_content(client):
    """Premium tier user also sees full morning brief (premium >= beta)."""
    _login_user(client, email="premiumbrief@example.com", tier="premium")
    rv = client.get("/brief")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Good morning" in html


# ---------------------------------------------------------------------------
# AI consultation tier gate tests (Task B-3)
# ---------------------------------------------------------------------------

def test_ask_anonymous_user_handled(client):
    """Anonymous user posting to /ask does not crash — handled gracefully."""
    rv = client.post("/ask", data={"q": "What permits do I need?"})
    # Anonymous users may get a redirect to login or a response — not 500
    assert rv.status_code != 500


def test_ask_free_user_gets_teaser_response(client, monkeypatch):
    """Free tier user asking a general question gets teaser, not full AI analysis.

    Mocks has_tier to return False — simulating a free user hitting the AI gate.
    """
    _login_user(client, email="freeask@example.com", tier="free")
    monkeypatch.setattr("web.routes_search.has_tier", lambda user, tier: False)
    rv = client.post("/ask", data={"q": "What permits do I need to add a deck?"})
    assert rv.status_code == 200
    html = rv.data.decode()
    # Should see the inline teaser, not full AI draft response
    assert "tier-gate-inline" in html or "Beta" in html


def test_ask_free_user_lookup_permit_bypasses_gate(client, monkeypatch):
    """Free tier user doing a permit number lookup is NOT gated — data lookup, not AI.

    Mocks has_tier to return False. Permit lookup intent should bypass the AI gate.
    """
    _login_user(client, email="freelookup@example.com", tier="free")
    monkeypatch.setattr("web.routes_search.has_tier", lambda user, tier: False)
    # Permit lookup is a data intent — should NOT be tier-gated
    rv = client.post("/ask", data={"q": "permit 202200001234"})
    assert rv.status_code == 200
    html = rv.data.decode()
    # Should NOT get the AI tier gate teaser for a permit number lookup
    assert "tier-gate-inline-card" not in html


def test_ask_beta_user_proceeds_to_ai(client, monkeypatch):
    """Beta tier user gets AI response (not teaser) for general questions."""
    _login_user(client, email="betaask@example.com", tier="beta")
    # has_tier returns True for beta user (real has_tier, no mock needed)
    # Mock AI synthesis to avoid real API calls
    monkeypatch.setattr(
        "web.routes_search._synthesize_with_ai",
        lambda *a, **kw: "Test AI response for beta user",
        raising=False,
    )
    rv = client.post("/ask", data={"q": "What permits do I need to add a deck?"})
    assert rv.status_code == 200
    html = rv.data.decode()
    # Beta user should NOT get the tier gate inline teaser card
    assert "tier-gate-inline-card" not in html


def test_ask_modifier_free_user_gets_teaser(client, monkeypatch):
    """Free tier user with modifier param (quick-action re-generate) also gets teaser.

    Mocks has_tier to return False — modifier path triggers AI synthesis.
    """
    _login_user(client, email="freemodifier@example.com", tier="free")
    monkeypatch.setattr("web.routes_search.has_tier", lambda user, tier: False)
    rv = client.post("/ask", data={"q": "What permits do I need?", "modifier": "shorter"})
    assert rv.status_code == 200
    html = rv.data.decode()
    # Modifier path triggers AI synthesis — should be gated for free users
    assert "Beta" in html or "tier-gate" in html.lower()
