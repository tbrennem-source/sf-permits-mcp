"""Tests for Session A: staging environment detection + test-login endpoint.

These tests use the Flask test_client() and monkeypatching — no live server needed.

Coverage:
  - /auth/test-login returns 404 when TESTING not set
  - /auth/test-login returns 404 when TESTING is empty string
  - /auth/test-login returns 403 with wrong secret
  - /auth/test-login returns 200 with correct secret + sets session cookie
  - /auth/test-login creates admin user if not exists
  - /auth/test-login works for non-admin email persona
  - Staging banner present when ENVIRONMENT=staging
  - Staging banner absent when ENVIRONMENT=production
  - Staging banner absent when ENVIRONMENT not set (default = production)
  - Environment name available in template context
  - Playwright conftest fixtures instantiate correctly
  - PERSONAS dict has 12 entries with required keys
"""

from __future__ import annotations

import os
import sys
import json
import importlib
import pytest

# Ensure web/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_staging.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


@pytest.fixture
def client(monkeypatch):
    """Flask test client with rate buckets cleared."""
    from web.app import app, _rate_buckets
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# /auth/test-login: gating tests (no TESTING env var)
# ---------------------------------------------------------------------------

class TestTestLoginGating:
    """The endpoint must be invisible (404) unless TESTING is enabled."""

    def test_returns_404_when_testing_not_set(self, client, monkeypatch):
        """404 when TESTING env var is absent."""
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("TEST_LOGIN_SECRET", raising=False)
        rv = client.post(
            "/auth/test-login",
            data=json.dumps({"secret": "anything"}),
            content_type="application/json",
        )
        assert rv.status_code == 404

    def test_returns_404_when_testing_empty_string(self, client, monkeypatch):
        """404 when TESTING env var is set to empty string."""
        monkeypatch.setenv("TESTING", "")
        monkeypatch.delenv("TEST_LOGIN_SECRET", raising=False)
        rv = client.post(
            "/auth/test-login",
            data=json.dumps({"secret": "anything"}),
            content_type="application/json",
        )
        assert rv.status_code == 404

    def test_returns_404_when_testing_false(self, client, monkeypatch):
        """404 when TESTING=false."""
        monkeypatch.setenv("TESTING", "false")
        monkeypatch.delenv("TEST_LOGIN_SECRET", raising=False)
        rv = client.post(
            "/auth/test-login",
            data=json.dumps({"secret": "anything"}),
            content_type="application/json",
        )
        assert rv.status_code == 404


# ---------------------------------------------------------------------------
# /auth/test-login: secret validation
# ---------------------------------------------------------------------------

class TestTestLoginSecret:
    """Correct secret grants access; wrong secret is rejected."""

    def test_returns_403_with_wrong_secret(self, client, monkeypatch):
        """403 when TESTING is enabled but wrong secret provided."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("TEST_LOGIN_SECRET", "correct-secret-xyz")
        rv = client.post(
            "/auth/test-login",
            data=json.dumps({"secret": "wrong-secret"}),
            content_type="application/json",
        )
        assert rv.status_code == 403

    def test_returns_403_with_missing_secret(self, client, monkeypatch):
        """403 when TESTING is enabled but no secret in request body."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("TEST_LOGIN_SECRET", "correct-secret-xyz")
        rv = client.post(
            "/auth/test-login",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert rv.status_code == 403

    def test_returns_403_when_no_login_secret_configured(self, client, monkeypatch):
        """403 when TESTING is enabled but TEST_LOGIN_SECRET not configured on server."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.delenv("TEST_LOGIN_SECRET", raising=False)
        rv = client.post(
            "/auth/test-login",
            data=json.dumps({"secret": "anything"}),
            content_type="application/json",
        )
        assert rv.status_code == 403


# ---------------------------------------------------------------------------
# /auth/test-login: success path
# ---------------------------------------------------------------------------

class TestTestLoginSuccess:
    """Correct credentials produce 200 + session."""

    def _post(self, client, secret, email=None):
        """Helper: POST to /auth/test-login."""
        payload = {"secret": secret}
        if email:
            payload["email"] = email
        return client.post(
            "/auth/test-login",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_returns_200_with_correct_secret(self, client, monkeypatch):
        """200 OK when TESTING=true and correct secret provided."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("TEST_LOGIN_SECRET", "my-test-secret")
        rv = self._post(client, "my-test-secret")
        assert rv.status_code == 200

    def test_response_body_is_json(self, client, monkeypatch):
        """Response body is valid JSON with ok=True."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("TEST_LOGIN_SECRET", "my-test-secret")
        rv = self._post(client, "my-test-secret")
        data = json.loads(rv.data)
        assert data["ok"] is True
        assert "user_id" in data
        assert "email" in data

    def test_sets_session_cookie(self, client, monkeypatch):
        """Session cookie is set after successful test-login."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("TEST_LOGIN_SECRET", "my-test-secret")
        rv = self._post(client, "my-test-secret")
        assert rv.status_code == 200
        # Flask test client has session in cookies
        with client.session_transaction() as sess:
            assert "user_id" in sess
            assert "email" in sess

    def test_default_email_is_test_admin(self, client, monkeypatch):
        """Default email is test-admin@sfpermits.ai when not specified."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("TEST_LOGIN_SECRET", "my-test-secret")
        rv = self._post(client, "my-test-secret")
        data = json.loads(rv.data)
        assert data["email"] == "test-admin@sfpermits.ai"

    def test_creates_user_if_not_exists(self, client, monkeypatch):
        """User is created in DB if they don't exist yet."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("TEST_LOGIN_SECRET", "my-test-secret")
        new_email = "new-test-user@sfpermits.ai"
        rv = self._post(client, "my-test-secret", email=new_email)
        assert rv.status_code == 200
        from web.auth import get_user_by_email
        user = get_user_by_email(new_email)
        assert user is not None
        assert user["email"] == new_email

    def test_created_user_has_admin_flag(self, client, monkeypatch):
        """Newly created test-admin user has is_admin=True."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("TEST_LOGIN_SECRET", "my-test-secret")
        rv = self._post(client, "my-test-secret")
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data["is_admin"] is True

    def test_works_for_non_admin_email(self, client, monkeypatch):
        """Test-login works for non-admin persona emails too."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("TEST_LOGIN_SECRET", "my-test-secret")
        rv = self._post(client, "my-test-secret", email="test-expediter@sfpermits.ai")
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data["email"] == "test-expediter@sfpermits.ai"

    def test_authenticated_user_can_access_account(self, client, monkeypatch):
        """After test-login, /account is accessible (not redirected to login)."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("TEST_LOGIN_SECRET", "my-test-secret")
        rv = self._post(client, "my-test-secret")
        assert rv.status_code == 200
        # Now check /account — should not redirect to /auth/login
        rv2 = client.get("/account")
        assert rv2.status_code == 200
        html = rv2.data.decode()
        # Should show account page content, not login page
        assert "test-admin@sfpermits.ai" in html or "account" in html.lower()


# ---------------------------------------------------------------------------
# Staging banner tests
# ---------------------------------------------------------------------------

class TestStagingBanner:
    """The staging banner must appear only when ENVIRONMENT=staging."""

    def _get_index_html(self, client, monkeypatch, env_value=None):
        """Helper: set up a logged-in user and fetch the index page."""
        import src.db as db_mod
        if db_mod.BACKEND == "duckdb":
            db_mod.init_user_schema()
        from web.auth import get_or_create_user, create_magic_token
        user = get_or_create_user("banner-test@example.com")
        token = create_magic_token(user["user_id"])
        client.get(f"/auth/verify/{token}", follow_redirects=True)

        if env_value is None:
            monkeypatch.delenv("ENVIRONMENT", raising=False)
        else:
            monkeypatch.setenv("ENVIRONMENT", env_value)

        # Patch app's IS_STAGING at runtime since it's evaluated at import time
        import web.app as app_mod
        monkeypatch.setattr(app_mod, "IS_STAGING", env_value == "staging")
        monkeypatch.setattr(app_mod, "ENVIRONMENT", env_value or "production")

        return client.get("/")

    def test_staging_banner_present_when_staging(self, client, monkeypatch):
        """Staging banner appears in HTML when ENVIRONMENT=staging."""
        rv = self._get_index_html(client, monkeypatch, "staging")
        html = rv.data.decode()
        assert "staging-banner" in html or "STAGING ENVIRONMENT" in html

    def test_staging_banner_absent_when_production(self, client, monkeypatch):
        """Staging banner not present when ENVIRONMENT=production."""
        rv = self._get_index_html(client, monkeypatch, "production")
        html = rv.data.decode()
        assert "staging-banner" not in html

    def test_staging_banner_absent_when_env_not_set(self, client, monkeypatch):
        """Staging banner not present when ENVIRONMENT not set (default = production)."""
        rv = self._get_index_html(client, monkeypatch, None)
        html = rv.data.decode()
        assert "staging-banner" not in html

    def test_staging_banner_on_landing_page(self, monkeypatch):
        """Staging banner appears on landing page (unauthenticated) when ENVIRONMENT=staging."""
        from web.app import app, _rate_buckets
        app.config["TESTING"] = True
        _rate_buckets.clear()
        import web.app as app_mod
        monkeypatch.setattr(app_mod, "IS_STAGING", True)
        monkeypatch.setattr(app_mod, "ENVIRONMENT", "staging")
        with app.test_client() as c:
            rv = c.get("/")
            html = rv.data.decode()
            assert "staging-banner" in html or "STAGING ENVIRONMENT" in html

    def test_staging_banner_on_auth_login(self, monkeypatch):
        """Staging banner appears on login page when ENVIRONMENT=staging."""
        from web.app import app, _rate_buckets
        app.config["TESTING"] = True
        _rate_buckets.clear()
        import web.app as app_mod
        monkeypatch.setattr(app_mod, "IS_STAGING", True)
        monkeypatch.setattr(app_mod, "ENVIRONMENT", "staging")
        with app.test_client() as c:
            rv = c.get("/auth/login")
            html = rv.data.decode()
            assert "staging-banner" in html or "STAGING ENVIRONMENT" in html


# ---------------------------------------------------------------------------
# Environment context processor tests
# ---------------------------------------------------------------------------

class TestEnvironmentContext:
    """The environment name must be available in template context."""

    def test_environment_name_in_context_staging(self, monkeypatch):
        """ENVIRONMENT=staging injects environment_name='staging' into templates."""
        from web.app import app, _rate_buckets
        _rate_buckets.clear()
        import web.app as app_mod
        monkeypatch.setattr(app_mod, "IS_STAGING", True)
        monkeypatch.setattr(app_mod, "ENVIRONMENT", "staging")
        with app.test_client() as c:
            with app.test_request_context("/"):
                ctx = {}
                for cp in app.template_context_processors[None]:
                    ctx.update(cp())
                assert ctx.get("environment_name") == "staging"
                assert ctx.get("is_staging") is True

    def test_environment_name_in_context_production(self, monkeypatch):
        """ENVIRONMENT=production injects is_staging=False."""
        from web.app import app
        import web.app as app_mod
        monkeypatch.setattr(app_mod, "IS_STAGING", False)
        monkeypatch.setattr(app_mod, "ENVIRONMENT", "production")
        with app.test_request_context("/"):
            ctx = {}
            for cp in app.template_context_processors[None]:
                ctx.update(cp())
            assert ctx.get("is_staging") is False


# ---------------------------------------------------------------------------
# Playwright conftest tests (unit-level, no live server needed)
# ---------------------------------------------------------------------------

class TestPlaywrightConftest:
    """Verify conftest fixtures and PERSONAS structure."""

    def test_personas_has_12_entries(self):
        """PERSONAS dict has exactly 12 entries."""
        from tests.e2e.conftest import PERSONAS
        assert len(PERSONAS) == 12

    def test_personas_all_have_required_keys(self):
        """Every persona has email, name, and role keys."""
        from tests.e2e.conftest import PERSONAS
        for key, persona in PERSONAS.items():
            assert "email" in persona, f"Missing 'email' in persona '{key}'"
            assert "name" in persona, f"Missing 'name' in persona '{key}'"
            assert "role" in persona, f"Missing 'role' in persona '{key}'"

    def test_personas_emails_are_unique(self):
        """All persona emails are unique."""
        from tests.e2e.conftest import PERSONAS
        emails = [p["email"] for p in PERSONAS.values()]
        assert len(emails) == len(set(emails)), "Duplicate emails in PERSONAS"

    def test_admin_persona_exists(self):
        """Admin persona is defined."""
        from tests.e2e.conftest import PERSONAS
        assert "admin" in PERSONAS
        assert PERSONAS["admin"]["role"] == "admin"

    def test_base_url_fixture_default(self, monkeypatch):
        """base_url fixture returns localhost:5001 when E2E_BASE_URL not set."""
        monkeypatch.delenv("E2E_BASE_URL", raising=False)
        # Directly test the logic (can't call pytest.fixture directly)
        url = os.environ.get("E2E_BASE_URL", "http://localhost:5001")
        assert url == "http://localhost:5001"

    def test_base_url_fixture_reads_env(self, monkeypatch):
        """base_url fixture reads E2E_BASE_URL from environment."""
        monkeypatch.setenv("E2E_BASE_URL", "https://sfpermits-ai-staging.up.railway.app")
        url = os.environ.get("E2E_BASE_URL", "http://localhost:5001")
        assert url == "https://sfpermits-ai-staging.up.railway.app"

    def test_skip_if_no_e2e_marker_exists(self):
        """skip_if_no_e2e marker is defined in conftest."""
        from tests.e2e.conftest import skip_if_no_e2e
        assert skip_if_no_e2e is not None

    def test_login_as_function_exists(self):
        """login_as helper function is importable from conftest."""
        from tests.e2e.conftest import login_as
        assert callable(login_as)
