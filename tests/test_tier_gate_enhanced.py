"""Tests for the enhanced @requires_tier decorator with teaser=True support.

Tests cover:
- teaser=False (hard gate): existing redirect/403 behavior is unchanged
- teaser=True (soft gate): g.tier_locked set, wrapped function always called
- has_tier() utility: all tier combinations
- inject_tier_gate context processor: variables injected into templates
"""

import pytest


# ---------------------------------------------------------------------------
# has_tier() — pure function, no Flask context needed
# ---------------------------------------------------------------------------

def test_has_tier_free_fails_beta():
    """Free user does not meet beta tier requirement."""
    from web.tier_gate import has_tier
    assert has_tier({"subscription_tier": "free"}, "beta") is False


def test_has_tier_free_fails_premium():
    """Free user does not meet premium tier requirement."""
    from web.tier_gate import has_tier
    assert has_tier({"subscription_tier": "free"}, "premium") is False


def test_has_tier_beta_passes_beta():
    """Beta user meets beta tier requirement."""
    from web.tier_gate import has_tier
    assert has_tier({"subscription_tier": "beta"}, "beta") is True


def test_has_tier_beta_fails_premium():
    """Beta user does not meet premium requirement."""
    from web.tier_gate import has_tier
    assert has_tier({"subscription_tier": "beta"}, "premium") is False


def test_has_tier_premium_passes_beta():
    """Premium user satisfies beta requirement (hierarchy)."""
    from web.tier_gate import has_tier
    assert has_tier({"subscription_tier": "premium"}, "beta") is True


def test_has_tier_premium_passes_premium():
    """Premium user meets premium requirement."""
    from web.tier_gate import has_tier
    assert has_tier({"subscription_tier": "premium"}, "premium") is True


def test_has_tier_missing_key_treated_as_free():
    """User without subscription_tier key defaults to free tier."""
    from web.tier_gate import has_tier
    assert has_tier({}, "beta") is False


def test_has_tier_none_value_treated_as_free():
    """User with subscription_tier=None is treated as free."""
    from web.tier_gate import has_tier
    assert has_tier({"subscription_tier": None}, "beta") is False


# ---------------------------------------------------------------------------
# requires_tier() teaser=False — hard gate (existing behavior preserved)
# Flask context via registered blueprint + test client
# ---------------------------------------------------------------------------

from web.app import app, _rate_buckets


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for test isolation."""
    db_path = str(tmp_path / "test_tier_gate_enhanced.duckdb")
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


def _login_user_with_tier(client, email, tier):
    """Helper: create user, authenticate, set subscription_tier."""
    from web.auth import get_or_create_user, create_magic_token
    from src.db import execute_write
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    execute_write(
        "UPDATE users SET subscription_tier = ? WHERE user_id = ?",
        (tier, user["user_id"]),
    )
    return user


def _ensure_enhanced_test_blueprint():
    """Register test blueprint for enhanced tier gate tests — idempotent."""
    if "_test_tier_gate_enhanced" not in app.blueprints:
        from web.tier_gate import requires_tier
        from flask import Blueprint, g

        bp = Blueprint("_test_tier_gate_enhanced", __name__)

        # Hard gate route (teaser=False, default)
        @bp.route("/_test_tier_enhanced/hard-gate")
        @requires_tier("beta")
        def _hard_gate_route():
            return "hard gate OK", 200

        # Teaser route (teaser=True) — always calls the view
        @bp.route("/_test_tier_enhanced/teaser-gate")
        @requires_tier("beta", teaser=True)
        def _teaser_gate_route():
            locked = getattr(g, "tier_locked", None)
            current = getattr(g, "tier_current", None)
            required = getattr(g, "tier_required", None)
            return f"locked={locked} current={current} required={required}", 200

        app.register_blueprint(bp)


_ensure_enhanced_test_blueprint()


# -- Hard gate (teaser=False) tests --

def test_hard_gate_anonymous_redirects(client):
    """Without teaser=True, anonymous request still redirects to login."""
    rv = client.get("/_test_tier_enhanced/hard-gate", follow_redirects=False)
    assert rv.status_code == 302
    assert "/auth/login" in rv.headers.get("Location", "")


def test_hard_gate_free_user_gets_403(client):
    """Without teaser=True, free user still gets 403 teaser fragment."""
    _login_user_with_tier(client, "enhanced_hard_free@example.com", "free")
    rv = client.get("/_test_tier_enhanced/hard-gate")
    assert rv.status_code == 403


def test_hard_gate_beta_user_passes(client):
    """Without teaser=True, beta user gets through the hard gate."""
    _login_user_with_tier(client, "enhanced_hard_beta@example.com", "beta")
    rv = client.get("/_test_tier_enhanced/hard-gate")
    assert rv.status_code == 200
    assert b"hard gate OK" in rv.data


# -- Teaser gate (teaser=True) tests --

def test_teaser_gate_anonymous_sets_locked_true(client):
    """With teaser=True, anonymous user gets tier_locked=True (no redirect)."""
    rv = client.get("/_test_tier_enhanced/teaser-gate")
    assert rv.status_code == 200
    body = rv.data.decode()
    assert "locked=True" in body
    assert "current=anonymous" in body
    assert "required=beta" in body


def test_teaser_gate_free_user_sets_locked_true(client):
    """With teaser=True, free user gets tier_locked=True (view is still called)."""
    _login_user_with_tier(client, "enhanced_teaser_free@example.com", "free")
    rv = client.get("/_test_tier_enhanced/teaser-gate")
    assert rv.status_code == 200
    body = rv.data.decode()
    assert "locked=True" in body
    assert "current=free" in body


def test_teaser_gate_beta_user_sets_locked_false(client):
    """With teaser=True, beta user gets tier_locked=False (full access)."""
    _login_user_with_tier(client, "enhanced_teaser_beta@example.com", "beta")
    rv = client.get("/_test_tier_enhanced/teaser-gate")
    assert rv.status_code == 200
    body = rv.data.decode()
    assert "locked=False" in body
    assert "current=beta" in body


def test_teaser_gate_premium_user_sets_locked_false(client):
    """With teaser=True, premium user (meets beta requirement) gets tier_locked=False."""
    _login_user_with_tier(client, "enhanced_teaser_premium@example.com", "premium")
    rv = client.get("/_test_tier_enhanced/teaser-gate")
    assert rv.status_code == 200
    body = rv.data.decode()
    assert "locked=False" in body
    assert "current=premium" in body


# ---------------------------------------------------------------------------
# inject_tier_gate context processor
# ---------------------------------------------------------------------------

def test_context_processor_defaults_to_unlocked(client):
    """inject_tier_gate returns tier_locked=False when no teaser gate fired."""
    # Use an existing public route that does not use requires_tier(teaser=True)
    with app.test_request_context("/"):
        from flask import g
        ctx = {}
        # Simulate context processor directly
        from web.app import inject_tier_gate
        result = inject_tier_gate()
        assert result["tier_locked"] is False
        assert result["tier_required"] is None
        assert result["tier_current"] is None


def test_context_processor_reflects_g_tier_locked(client):
    """inject_tier_gate reflects g.tier_locked when it has been set."""
    with app.test_request_context("/"):
        from flask import g
        g.tier_locked = True
        g.tier_required = "beta"
        g.tier_current = "free"
        from web.app import inject_tier_gate
        result = inject_tier_gate()
        assert result["tier_locked"] is True
        assert result["tier_required"] == "beta"
        assert result["tier_current"] == "free"


# ---------------------------------------------------------------------------
# functools.wraps — function name preserved
# ---------------------------------------------------------------------------

def test_teaser_decorator_preserves_function_name():
    """@requires_tier(teaser=True) preserves the wrapped function's __name__."""
    from web.tier_gate import requires_tier

    @requires_tier("beta", teaser=True)
    def my_teaser_view():
        pass

    assert my_teaser_view.__name__ == "my_teaser_view"


def test_hard_gate_decorator_preserves_function_name():
    """@requires_tier(teaser=False) preserves the wrapped function's __name__."""
    from web.tier_gate import requires_tier

    @requires_tier("premium")
    def my_premium_view():
        pass

    assert my_premium_view.__name__ == "my_premium_view"
