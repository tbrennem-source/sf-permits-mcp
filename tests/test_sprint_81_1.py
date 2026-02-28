"""Tests for Sprint 81 QS8-T3-A: Multi-step onboarding wizard + PREMIUM tier + feature flags."""

import os
import pytest

from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_81_1.duckdb")
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


@pytest.fixture
def auth_client(client):
    """Client with an authenticated test user session."""
    from web.auth import create_user, get_user_by_email
    create_user("onboarding-test@sfpermits.ai")
    user = get_user_by_email("onboarding-test@sfpermits.ai")
    with client.session_transaction() as sess:
        sess["user_id"] = user["user_id"]
        sess["email"] = user["email"]
        sess["is_admin"] = user["is_admin"]
    return client


# ---------------------------------------------------------------------------
# A-1: Onboarding wizard — rendering
# ---------------------------------------------------------------------------

class TestOnboardingStep1:
    """Step 1 renders and accepts role selection."""

    def test_onboarding_step1_renders(self, auth_client):
        """GET /onboarding/step/1 returns 200 for authenticated user."""
        resp = auth_client.get("/onboarding/step/1")
        assert resp.status_code == 200
        text = resp.data.decode()
        assert "Welcome to" in text
        assert "homeowner" in text
        assert "architect" in text
        assert "expediter" in text
        assert "contractor" in text

    def test_onboarding_redirects_unauthenticated(self, client):
        """GET /onboarding/step/1 redirects anonymous users to login."""
        resp = client.get("/onboarding/step/1")
        assert resp.status_code in (302, 401)

    def test_onboarding_saves_role(self, auth_client):
        """POST /onboarding/step/1/save with valid role redirects to step 2."""
        resp = auth_client.post(
            "/onboarding/step/1/save",
            data={"role": "expediter"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/onboarding/step/2" in resp.headers["Location"]

    def test_onboarding_step1_rejects_invalid_role(self, auth_client):
        """POST with an invalid role re-renders step 1 with error."""
        resp = auth_client.post(
            "/onboarding/step/1/save",
            data={"role": "pirate"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        text = resp.data.decode()
        # Should stay on step 1 and show an error
        assert "Please select a role" in text

    def test_onboarding_saves_role_in_db(self, auth_client):
        """Role persisted to user table after step 1 save."""
        from web.auth import get_user_by_email
        auth_client.post(
            "/onboarding/step/1/save",
            data={"role": "architect"},
            follow_redirects=False,
        )
        user = get_user_by_email("onboarding-test@sfpermits.ai")
        assert user["role"] == "architect"


class TestOnboardingStep2:
    """Step 2 renders the demo property and creates a watch item."""

    def test_onboarding_step2_renders(self, auth_client):
        """GET /onboarding/step/2 returns 200 with demo property."""
        resp = auth_client.get("/onboarding/step/2")
        assert resp.status_code == 200
        text = resp.data.decode()
        assert "1455 Market St" in text
        assert "portfolio" in text.lower() or "watch" in text.lower()

    def test_onboarding_step2_creates_watch_item(self, auth_client):
        """POST /onboarding/step/2/save with action=add creates a watch item."""
        from web.auth import get_watches, get_user_by_email
        resp = auth_client.post(
            "/onboarding/step/2/save",
            data={"action": "add"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/onboarding/step/3" in resp.headers["Location"]

        user = get_user_by_email("onboarding-test@sfpermits.ai")
        watches = get_watches(user["user_id"])
        watch_addresses = [
            f"{w.get('street_number', '')} {w.get('street_name', '')}".strip()
            for w in watches
        ]
        assert any("1455" in addr for addr in watch_addresses)

    def test_onboarding_step2_skip_advances_without_watch(self, auth_client):
        """POST /onboarding/step/2/save with action=skip advances to step 3 without adding watch."""
        from web.auth import get_watches, get_user_by_email
        resp = auth_client.post(
            "/onboarding/step/2/save",
            data={"action": "skip"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/onboarding/step/3" in resp.headers["Location"]

        user = get_user_by_email("onboarding-test@sfpermits.ai")
        watches = get_watches(user["user_id"])
        assert len(watches) == 0


class TestOnboardingStep3:
    """Step 3 renders sample brief and completes onboarding."""

    def test_onboarding_step3_renders(self, auth_client):
        """GET /onboarding/step/3 returns 200 with sample brief content."""
        resp = auth_client.get("/onboarding/step/3")
        assert resp.status_code == 200
        text = resp.data.decode()
        assert "morning brief" in text.lower() or "Morning Brief" in text
        assert "Dashboard" in text

    def test_onboarding_complete_marks_db(self, auth_client):
        """POST /onboarding/step/3/complete sets onboarding_complete = True."""
        from web.auth import get_user_by_email
        resp = auth_client.post(
            "/onboarding/step/3/complete",
            follow_redirects=False,
        )
        assert resp.status_code == 302

        user = get_user_by_email("onboarding-test@sfpermits.ai")
        assert user.get("onboarding_complete") is True


# ---------------------------------------------------------------------------
# A-2: PREMIUM tier
# ---------------------------------------------------------------------------

class TestPremiumTier:
    """PREMIUM tier exists in FeatureTier enum and has correct ordering."""

    def test_premium_tier_exists(self):
        """FeatureTier.PREMIUM exists and has value 'premium'."""
        from web.feature_gate import FeatureTier
        assert hasattr(FeatureTier, "PREMIUM")
        assert FeatureTier.PREMIUM.value == "premium"

    def test_premium_tier_between_authenticated_and_admin(self):
        """PREMIUM tier rank is between AUTHENTICATED and ADMIN."""
        from web.feature_gate import _TIER_ORDER, FeatureTier
        assert _TIER_ORDER[FeatureTier.AUTHENTICATED] < _TIER_ORDER[FeatureTier.PREMIUM]
        assert _TIER_ORDER[FeatureTier.PREMIUM] < _TIER_ORDER[FeatureTier.ADMIN]

    def test_admin_user_gets_admin_tier(self):
        """Admin users always get ADMIN tier, not PREMIUM."""
        from web.feature_gate import FeatureTier, get_user_tier
        user = {"is_admin": True, "invite_code": None, "subscription_tier": "free"}
        assert get_user_tier(user) == FeatureTier.ADMIN

    def test_beta_invite_code_grants_premium(self):
        """Users with sfp-beta- invite code prefix get PREMIUM tier."""
        from web.feature_gate import FeatureTier, get_user_tier
        user = {
            "is_admin": False,
            "invite_code": "sfp-beta-abc123",
            "subscription_tier": "free",
        }
        assert get_user_tier(user) == FeatureTier.PREMIUM

    def test_amy_invite_code_grants_premium(self):
        """Users with sfp-amy- invite code prefix get PREMIUM tier."""
        from web.feature_gate import FeatureTier, get_user_tier
        user = {
            "is_admin": False,
            "invite_code": "sfp-amy-22204097",
            "subscription_tier": "free",
        }
        assert get_user_tier(user) == FeatureTier.PREMIUM

    def test_subscription_tier_premium_grants_premium(self):
        """Users with subscription_tier='premium' in DB get PREMIUM tier."""
        from web.feature_gate import FeatureTier, get_user_tier
        user = {
            "is_admin": False,
            "invite_code": None,
            "subscription_tier": "premium",
        }
        assert get_user_tier(user) == FeatureTier.PREMIUM

    def test_regular_user_gets_authenticated_tier(self):
        """Regular authenticated users without premium invite get AUTHENTICATED tier."""
        from web.feature_gate import FeatureTier, get_user_tier
        user = {
            "is_admin": False,
            "invite_code": "some-other-code",
            "subscription_tier": "free",
        }
        assert get_user_tier(user) == FeatureTier.AUTHENTICATED

    def test_gate_context_includes_is_premium(self):
        """gate_context() returns is_premium flag."""
        from web.feature_gate import gate_context
        user = {
            "is_admin": False,
            "invite_code": "sfp-beta-xyz",
            "subscription_tier": "free",
        }
        ctx = gate_context(user)
        assert "is_premium" in ctx
        assert ctx["is_premium"] is True

    def test_gate_context_is_premium_false_for_regular(self):
        """gate_context() returns is_premium=False for regular users."""
        from web.feature_gate import gate_context
        user = {
            "is_admin": False,
            "invite_code": None,
            "subscription_tier": "free",
        }
        ctx = gate_context(user)
        assert ctx["is_premium"] is False


# ---------------------------------------------------------------------------
# A-3: Feature flag expansion — 5 new features
# ---------------------------------------------------------------------------

class TestFeatureFlags:
    """5 new PREMIUM-target feature flags exist in FEATURE_REGISTRY."""

    PREMIUM_FEATURES = [
        "plan_analysis_full",
        "entity_deep_dive",
        "export_pdf",
        "api_access",
        "priority_support",
    ]

    def test_feature_flags_registered(self):
        """All 5 new features exist in FEATURE_REGISTRY."""
        from web.feature_gate import FEATURE_REGISTRY
        for feature in self.PREMIUM_FEATURES:
            assert feature in FEATURE_REGISTRY, (
                f"Feature '{feature}' not found in FEATURE_REGISTRY"
            )

    def test_new_features_accessible_during_beta(self):
        """All 5 new features are accessible to authenticated users (beta = everyone gets everything)."""
        from web.feature_gate import can_access
        user = {"is_admin": False, "invite_code": None, "subscription_tier": "free"}
        for feature in self.PREMIUM_FEATURES:
            assert can_access(feature, user) is True, (
                f"Feature '{feature}' should be accessible during beta"
            )

    def test_new_features_accessible_to_anonymous(self):
        """New premium features require auth — anonymous users cannot access them."""
        from web.feature_gate import can_access
        # They are set to AUTHENTICATED, not FREE, so anonymous cannot access
        for feature in self.PREMIUM_FEATURES:
            assert can_access(feature, None) is False, (
                f"Feature '{feature}' should require authentication"
            )

    def test_can_flags_in_gate_context(self):
        """gate_context includes can_* flags for all 5 new features."""
        from web.feature_gate import gate_context
        user = {"is_admin": False, "invite_code": None, "subscription_tier": "free"}
        ctx = gate_context(user)
        for feature in self.PREMIUM_FEATURES:
            flag = f"can_{feature}"
            assert flag in ctx, f"gate_context missing '{flag}'"
            assert ctx[flag] is True
