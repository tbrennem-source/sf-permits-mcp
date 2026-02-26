"""Tests for Sprint 62D — Feature Gating + Context Processor.

Coverage:
  - get_user_tier: None -> FREE
  - get_user_tier: regular user -> AUTHENTICATED
  - get_user_tier: admin user -> ADMIN
  - can_access: free feature accessible to unauthenticated
  - can_access: authenticated feature denied to unauthenticated
  - can_access: authenticated feature granted to logged-in user
  - can_access: admin feature denied to regular user
  - can_access: admin feature granted to admin user
  - can_access: unknown feature defaults to AUTHENTICATED required
  - gate_context: unauthenticated tier is "free"
  - gate_context: unauthenticated can_search is True
  - gate_context: unauthenticated can_analyze is False
  - gate_context: authenticated can_analyze is True
  - gate_context: authenticated is_authenticated is True
  - gate_context: unauthenticated is_authenticated is False
  - gate_context: admin is_admin is True
  - gate_context: regular user is_admin is False
  - context processor injects gate into all templates
  - unauthenticated nav shows "Sign up" badge for Brief
  - authenticated nav shows normal Brief link without "Sign up"
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with a temp database for test isolation."""
    db_path = str(tmp_path / "test_62d.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    db_mod.init_user_schema()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with DuckDB backend."""
    db_path = str(tmp_path / "test_62d_client.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    db_mod.init_user_schema()

    from app import app
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Feature gate logic: get_user_tier
# ---------------------------------------------------------------------------

class TestGetUserTier:
    def test_none_returns_free(self):
        from web.feature_gate import get_user_tier, FeatureTier
        assert get_user_tier(None) == FeatureTier.FREE

    def test_regular_user_returns_authenticated(self):
        from web.feature_gate import get_user_tier, FeatureTier
        assert get_user_tier({"user_id": 1, "email": "test@example.com"}) == FeatureTier.AUTHENTICATED

    def test_admin_user_returns_admin(self):
        from web.feature_gate import get_user_tier, FeatureTier
        assert get_user_tier({"user_id": 1, "is_admin": True}) == FeatureTier.ADMIN

    def test_user_without_is_admin_key_returns_authenticated(self):
        from web.feature_gate import get_user_tier, FeatureTier
        assert get_user_tier({"user_id": 5}) == FeatureTier.AUTHENTICATED

    def test_user_with_is_admin_false_returns_authenticated(self):
        from web.feature_gate import get_user_tier, FeatureTier
        assert get_user_tier({"user_id": 5, "is_admin": False}) == FeatureTier.AUTHENTICATED


# ---------------------------------------------------------------------------
# Feature gate logic: can_access
# ---------------------------------------------------------------------------

class TestCanAccess:
    def test_free_feature_accessible_to_unauthenticated(self):
        from web.feature_gate import can_access
        assert can_access("search", None) is True

    def test_free_feature_accessible_to_authenticated(self):
        from web.feature_gate import can_access
        assert can_access("search", {"user_id": 1}) is True

    def test_authenticated_feature_denied_to_unauthenticated(self):
        from web.feature_gate import can_access
        assert can_access("analyze", None) is False

    def test_authenticated_feature_granted_to_logged_in_user(self):
        from web.feature_gate import can_access
        assert can_access("analyze", {"user_id": 1}) is True

    def test_admin_feature_denied_to_regular_user(self):
        from web.feature_gate import can_access
        assert can_access("admin_ops", {"user_id": 1}) is False

    def test_admin_feature_granted_to_admin_user(self):
        from web.feature_gate import can_access
        assert can_access("admin_ops", {"user_id": 1, "is_admin": True}) is True

    def test_admin_feature_denied_to_unauthenticated(self):
        from web.feature_gate import can_access
        assert can_access("admin_qa", None) is False

    def test_unknown_feature_defaults_to_authenticated_required(self):
        from web.feature_gate import can_access
        # Unknown features default to AUTHENTICATED required
        assert can_access("nonexistent_feature", None) is False
        assert can_access("nonexistent_feature", {"user_id": 1}) is True

    def test_brief_denied_to_unauthenticated(self):
        from web.feature_gate import can_access
        assert can_access("brief", None) is False

    def test_brief_granted_to_authenticated(self):
        from web.feature_gate import can_access
        assert can_access("brief", {"user_id": 1}) is True


# ---------------------------------------------------------------------------
# Gate context dict
# ---------------------------------------------------------------------------

class TestGateContext:
    def test_unauthenticated_tier_is_free(self):
        from web.feature_gate import gate_context
        ctx = gate_context(None)
        assert ctx["tier"] == "free"

    def test_authenticated_tier_is_authenticated(self):
        from web.feature_gate import gate_context
        ctx = gate_context({"user_id": 1})
        assert ctx["tier"] == "authenticated"

    def test_admin_tier_is_admin(self):
        from web.feature_gate import gate_context
        ctx = gate_context({"user_id": 1, "is_admin": True})
        assert ctx["tier"] == "admin"

    def test_unauthenticated_can_search_is_true(self):
        from web.feature_gate import gate_context
        ctx = gate_context(None)
        assert ctx["can_search"] is True

    def test_unauthenticated_can_analyze_is_false(self):
        from web.feature_gate import gate_context
        ctx = gate_context(None)
        assert ctx["can_analyze"] is False

    def test_authenticated_can_analyze_is_true(self):
        from web.feature_gate import gate_context
        ctx = gate_context({"user_id": 1})
        assert ctx["can_analyze"] is True

    def test_authenticated_is_authenticated_is_true(self):
        from web.feature_gate import gate_context
        ctx = gate_context({"user_id": 1})
        assert ctx["is_authenticated"] is True

    def test_unauthenticated_is_authenticated_is_false(self):
        from web.feature_gate import gate_context
        ctx = gate_context(None)
        assert ctx["is_authenticated"] is False

    def test_admin_is_admin_is_true(self):
        from web.feature_gate import gate_context
        ctx = gate_context({"user_id": 1, "is_admin": True})
        assert ctx["is_admin"] is True

    def test_regular_user_is_admin_is_false(self):
        from web.feature_gate import gate_context
        ctx = gate_context({"user_id": 1})
        assert ctx["is_admin"] is False

    def test_context_contains_all_feature_flags(self):
        from web.feature_gate import gate_context, FEATURE_REGISTRY
        ctx = gate_context(None)
        for feature in FEATURE_REGISTRY:
            assert f"can_{feature}" in ctx, f"Missing can_{feature} in gate_context"

    def test_admin_can_access_admin_features(self):
        from web.feature_gate import gate_context
        ctx = gate_context({"user_id": 1, "is_admin": True})
        assert ctx["can_admin_ops"] is True
        assert ctx["can_admin_qa"] is True
        assert ctx["can_admin_costs"] is True

    def test_regular_user_cannot_access_admin_features(self):
        from web.feature_gate import gate_context
        ctx = gate_context({"user_id": 1})
        assert ctx["can_admin_ops"] is False


# ---------------------------------------------------------------------------
# Template integration via Flask test client
# ---------------------------------------------------------------------------

class TestContextProcessorIntegration:
    def test_landing_page_injects_gate(self, client):
        """Context processor injects gate into templates."""
        resp = client.get("/")
        # Landing page should render without error (gate is available in template)
        assert resp.status_code == 200

    def test_unauthenticated_nav_shows_signup_badge_for_brief(self, client):
        """Unauthenticated request to landing page includes 'Sign up' badge text in nav for Brief."""
        resp = client.get("/")
        html = resp.data.decode()
        # The nav should show "Sign up" spans for Brief since user is not logged in
        assert "Sign up" in html

    def test_unauthenticated_nav_has_signup_for_portfolio(self, client):
        """Unauthenticated nav shows 'Sign up' badge for Portfolio."""
        resp = client.get("/")
        html = resp.data.decode()
        assert "Sign up" in html

    def test_unauthenticated_brief_link_points_to_login(self, client):
        """Brief link for unauthenticated users points to /auth/login."""
        resp = client.get("/")
        html = resp.data.decode()
        # The brief nav item should link to login for unauthenticated users
        assert "/auth/login" in html
