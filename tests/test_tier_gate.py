"""Tests for the @requires_tier decorator and has_tier utility (Sprint 89-4A)."""

import pytest
import functools


# ---------------------------------------------------------------------------
# has_tier() unit tests — pure function, no Flask context needed
# ---------------------------------------------------------------------------

def test_has_tier_free_user_fails_beta_check():
    """Free user does not have beta tier access."""
    from web.tier_gate import has_tier
    user = {"subscription_tier": "free"}
    assert has_tier(user, "beta") is False


def test_has_tier_free_user_fails_premium_check():
    """Free user does not have premium tier access."""
    from web.tier_gate import has_tier
    user = {"subscription_tier": "free"}
    assert has_tier(user, "premium") is False


def test_has_tier_beta_user_passes_beta_check():
    """Beta user passes beta tier check."""
    from web.tier_gate import has_tier
    user = {"subscription_tier": "beta"}
    assert has_tier(user, "beta") is True


def test_has_tier_beta_user_fails_premium_check():
    """Beta user does not have premium tier access."""
    from web.tier_gate import has_tier
    user = {"subscription_tier": "beta"}
    assert has_tier(user, "premium") is False


def test_has_tier_premium_user_passes_beta_check():
    """Premium user meets beta tier requirement (tier hierarchy)."""
    from web.tier_gate import has_tier
    user = {"subscription_tier": "premium"}
    assert has_tier(user, "beta") is True


def test_has_tier_premium_user_passes_premium_check():
    """Premium user passes premium tier check."""
    from web.tier_gate import has_tier
    user = {"subscription_tier": "premium"}
    assert has_tier(user, "premium") is True


def test_has_tier_missing_tier_field_treated_as_free():
    """User dict without subscription_tier is treated as free."""
    from web.tier_gate import has_tier
    user = {}
    assert has_tier(user, "beta") is False


def test_has_tier_none_tier_treated_as_free():
    """User dict with subscription_tier=None is treated as free."""
    from web.tier_gate import has_tier
    user = {"subscription_tier": None}
    assert has_tier(user, "beta") is False


def test_has_tier_unknown_tier_treated_as_free():
    """Unknown tier value defaults to free (level 0)."""
    from web.tier_gate import has_tier
    user = {"subscription_tier": "enterprise"}
    # Not in the tier levels map → falls back to level 0 (free behavior)
    # enterprise is not >= beta (level 1) since unknown = 0
    assert has_tier(user, "beta") is False


# ---------------------------------------------------------------------------
# requires_tier() — decorator behavior via Flask test client
# ---------------------------------------------------------------------------

from web.app import app, _rate_buckets


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_tier_gate.duckdb")
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
    """Helper: create user, authenticate, then set subscription_tier."""
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


# ---------------------------------------------------------------------------
# Flask integration tests using a registered test route
#
# Blueprint registration is done once at module import time to avoid
# scope conflicts between function-scoped db fixtures and app setup.
# ---------------------------------------------------------------------------

def _ensure_test_blueprint():
    """Register test blueprint once on the app if not already registered."""
    if "_test_tier_gate" not in app.blueprints:
        from web.tier_gate import requires_tier
        from web.helpers import login_required
        from flask import Blueprint

        bp = Blueprint("_test_tier_gate", __name__)

        @bp.route("/_test_tier/beta-route")
        @login_required
        @requires_tier("beta")
        def _beta_route():
            return "beta content OK", 200

        app.register_blueprint(bp)


# Register immediately at module load (before any fixture scope issues)
_ensure_test_blueprint()


@pytest.fixture
def gated_client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def test_requires_tier_anonymous_redirects_to_login(gated_client):
    """Unauthenticated user accessing @requires_tier route is redirected to login."""
    rv = gated_client.get("/_test_tier/beta-route", follow_redirects=False)
    # login_required fires first, redirects to login
    assert rv.status_code == 302
    assert "/auth/login" in rv.headers.get("Location", "")


def test_requires_tier_free_user_gets_403_teaser(gated_client):
    """Free user hitting @requires_tier('beta') route gets 403 with teaser content."""
    _login_user_with_tier(gated_client, "free_gated@example.com", "free")
    rv = gated_client.get("/_test_tier/beta-route")
    assert rv.status_code == 403
    html = rv.data.decode()
    assert "beta" in html.lower()


def test_requires_tier_beta_user_sees_content(gated_client):
    """Beta user hitting @requires_tier('beta') route gets full content."""
    _login_user_with_tier(gated_client, "beta_gated@example.com", "beta")
    rv = gated_client.get("/_test_tier/beta-route")
    assert rv.status_code == 200
    assert b"beta content OK" in rv.data


def test_requires_tier_premium_user_sees_beta_content(gated_client):
    """Premium user also passes @requires_tier('beta') — tier hierarchy applies."""
    _login_user_with_tier(gated_client, "premium_gated@example.com", "premium")
    rv = gated_client.get("/_test_tier/beta-route")
    assert rv.status_code == 200
    assert b"beta content OK" in rv.data


def test_requires_tier_decorator_preserves_function_name():
    """@requires_tier preserves the wrapped function's __name__ via functools.wraps."""
    from web.tier_gate import requires_tier

    @requires_tier("beta")
    def my_view_function():
        pass

    assert my_view_function.__name__ == "my_view_function"
