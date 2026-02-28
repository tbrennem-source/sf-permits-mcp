"""Tests for the beta invite flow and onboarding wizard routes (Sprint 89-4A)."""

import pytest

from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_onboarding.duckdb")
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


def _login_user(client, email="test@example.com"):
    """Helper: create user and authenticate via magic link."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _set_invite_codes(monkeypatch, codes=None):
    """Helper: patch INVITE_CODES in web.auth to a known set."""
    import web.auth as auth_mod
    code_set = set(codes) if codes else {"test-invite-code-123"}
    monkeypatch.setattr(auth_mod, "INVITE_CODES", code_set)


# ---------------------------------------------------------------------------
# /beta/join — invalid code
# ---------------------------------------------------------------------------

def test_beta_join_invalid_code_returns_400(client, monkeypatch):
    """Invalid or missing invite code returns 400 with error message."""
    _set_invite_codes(monkeypatch, codes={"valid-code-only"})
    rv = client.get("/beta/join?code=bad-code")
    assert rv.status_code == 400
    html = rv.data.decode()
    assert "invalid" in html.lower() or "expired" in html.lower()


def test_beta_join_missing_code_returns_400(client, monkeypatch):
    """Missing code param returns 400."""
    _set_invite_codes(monkeypatch, codes={"valid-code-only"})
    rv = client.get("/beta/join")
    assert rv.status_code == 400


def test_beta_join_unauthenticated_redirects_to_login(client, monkeypatch):
    """Valid code + unauthenticated user redirects to /auth/login with code preserved."""
    _set_invite_codes(monkeypatch)
    rv = client.get("/beta/join?code=test-invite-code-123", follow_redirects=False)
    assert rv.status_code == 302
    location = rv.headers.get("Location", "")
    assert "/auth/login" in location
    assert "invite_code=test-invite-code-123" in location


def test_beta_join_valid_code_upgrades_tier(client, monkeypatch):
    """Valid code + authenticated free user upgrades tier to beta and redirects to welcome."""
    _set_invite_codes(monkeypatch)
    user = _login_user(client, "free@example.com")

    # Verify user starts as free
    from web.auth import get_user_by_id
    fresh = get_user_by_id(user["user_id"])
    assert fresh["subscription_tier"] == "free"

    rv = client.get("/beta/join?code=test-invite-code-123", follow_redirects=False)
    assert rv.status_code == 302
    location = rv.headers.get("Location", "")
    assert "beta/onboarding/welcome" in location

    # Verify tier upgraded in DB
    upgraded = get_user_by_id(user["user_id"])
    assert upgraded["subscription_tier"] == "beta"


def test_beta_join_already_beta_redirects_to_dashboard(client, monkeypatch):
    """Valid code + already-beta user redirects to dashboard without double-upgrade."""
    _set_invite_codes(monkeypatch)
    user = _login_user(client, "beta@example.com")

    # Pre-set user to beta tier
    from src.db import execute_write
    execute_write(
        "UPDATE users SET subscription_tier = 'beta' WHERE user_id = ?",
        (user["user_id"],),
    )

    rv = client.get("/beta/join?code=test-invite-code-123", follow_redirects=False)
    assert rv.status_code == 302
    location = rv.headers.get("Location", "")
    # Should go to index, not onboarding
    assert "beta/onboarding" not in location


def test_beta_join_already_premium_redirects_to_dashboard(client, monkeypatch):
    """Valid code + premium user redirects to dashboard without downgrade."""
    _set_invite_codes(monkeypatch)
    user = _login_user(client, "premium@example.com")

    from src.db import execute_write
    execute_write(
        "UPDATE users SET subscription_tier = 'premium' WHERE user_id = ?",
        (user["user_id"],),
    )

    rv = client.get("/beta/join?code=test-invite-code-123", follow_redirects=False)
    assert rv.status_code == 302
    location = rv.headers.get("Location", "")
    assert "beta/onboarding" not in location


# ---------------------------------------------------------------------------
# /beta/onboarding/* — auth required
# ---------------------------------------------------------------------------

def test_beta_onboarding_welcome_requires_auth(client):
    """Unauthenticated request to /beta/onboarding/welcome redirects to login."""
    rv = client.get("/beta/onboarding/welcome", follow_redirects=False)
    assert rv.status_code == 302
    assert "/auth/login" in rv.headers.get("Location", "")


def test_beta_onboarding_add_property_requires_auth(client):
    """Unauthenticated request to /beta/onboarding/add-property redirects to login."""
    rv = client.get("/beta/onboarding/add-property", follow_redirects=False)
    assert rv.status_code == 302
    assert "/auth/login" in rv.headers.get("Location", "")


def test_beta_onboarding_severity_preview_requires_auth(client):
    """Unauthenticated request to /beta/onboarding/severity-preview redirects to login."""
    rv = client.get("/beta/onboarding/severity-preview", follow_redirects=False)
    assert rv.status_code == 302
    assert "/auth/login" in rv.headers.get("Location", "")


# ---------------------------------------------------------------------------
# /beta/onboarding/* — authenticated renders
# ---------------------------------------------------------------------------

def test_beta_onboarding_welcome_renders(client):
    """Authenticated request to /beta/onboarding/welcome returns 200."""
    _login_user(client, "beta_welcome@example.com")
    rv = client.get("/beta/onboarding/welcome")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "beta" in html.lower()


def test_beta_onboarding_add_property_renders(client):
    """Authenticated request to /beta/onboarding/add-property returns 200 with form."""
    _login_user(client, "beta_addprop@example.com")
    rv = client.get("/beta/onboarding/add-property")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "street_number" in html or "property" in html.lower()


def test_beta_onboarding_severity_preview_renders(client):
    """Authenticated request to /beta/onboarding/severity-preview returns 200 with 3 cards."""
    _login_user(client, "beta_severity@example.com")
    rv = client.get("/beta/onboarding/severity-preview")
    assert rv.status_code == 200
    html = rv.data.decode()
    # Should have 3 signal categories
    assert "inspection" in html.lower()
    assert "complaint" in html.lower()
    assert "permit" in html.lower()
