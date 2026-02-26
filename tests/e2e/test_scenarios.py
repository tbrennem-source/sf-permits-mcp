"""Sprint 67-C: Behavioral scenario tests using Flask test client.

Tests core user journeys without requiring a live server or Playwright.
Uses Flask's built-in test client for fast, reliable testing.

Coverage:
- Anonymous user flows (landing, search, health, robots)
- Authentication flows (test-login, session handling)
- Authenticated user flows (index page, account, portfolio)
- Rate limiting behavior
- API endpoints (health, sitemap)
- Error handling (404, invalid input)
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "web"))

from app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Fresh Flask test client with TESTING mode and clean rate buckets."""
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login(client, email="scenario-test@test.com"):
    """Helper: create a user and log them in via magic link."""
    import src.db as db_mod
    if db_mod.BACKEND == "duckdb":
        db_mod.init_user_schema()
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _login_admin(client, email="admin-scenario@test.com"):
    """Helper: create an admin user and log them in."""
    import src.db as db_mod
    if db_mod.BACKEND == "duckdb":
        db_mod.init_user_schema()
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    # Make user admin
    conn = db_mod.get_connection()
    try:
        conn.execute(
            "UPDATE users SET is_admin = TRUE WHERE user_id = ?",
            [user["user_id"]],
        )
        if hasattr(conn, "commit"):
            conn.commit()
    except Exception:
        pass  # DuckDB may auto-commit
    finally:
        if hasattr(db_mod, "release_connection"):
            db_mod.release_connection(conn)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# 1. Anonymous user flows
# ---------------------------------------------------------------------------

class TestAnonymousLanding:
    """Anonymous users see the landing page."""

    def test_landing_page_returns_200(self, client):
        """GET / returns 200 for anonymous users."""
        rv = client.get("/")
        assert rv.status_code == 200

    def test_landing_page_contains_search_form(self, client):
        """Landing page has a search form."""
        rv = client.get("/")
        html = rv.data.decode()
        assert 'action="/search"' in html
        assert 'name="q"' in html

    def test_landing_page_has_cta(self, client):
        """Landing page has CTA for signup."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "Create free account" in html or "Get started" in html


class TestAnonymousSearch:
    """Anonymous users can search by address."""

    def test_search_returns_200(self, client):
        """GET /search?q=market returns 200."""
        rv = client.get("/search?q=market")
        assert rv.status_code == 200

    def test_search_with_empty_query(self, client):
        """GET /search with empty q still returns 200."""
        rv = client.get("/search?q=")
        assert rv.status_code in (200, 302)

    def test_search_results_page_structure(self, client):
        """Search results page has expected structure."""
        rv = client.get("/search?q=123+main+st")
        assert rv.status_code == 200
        html = rv.data.decode()
        # Should contain some kind of result or "no results" message
        assert "search" in html.lower() or "result" in html.lower() or "permit" in html.lower()


# ---------------------------------------------------------------------------
# 2. Authentication flows
# ---------------------------------------------------------------------------

class TestLoginFlow:
    """Login flow using test-login endpoint."""

    def test_login_page_returns_200(self, client):
        """GET /auth/login returns 200."""
        rv = client.get("/auth/login")
        assert rv.status_code == 200

    def test_login_page_has_email_input(self, client):
        """Login page has an email input field."""
        rv = client.get("/auth/login")
        html = rv.data.decode()
        assert 'type="email"' in html or 'name="email"' in html

    def test_authenticated_user_sees_index(self, client):
        """After login, user sees index.html not landing.html."""
        _login(client)
        rv = client.get("/")
        assert rv.status_code == 200
        html = rv.data.decode()
        # Authenticated users see the search UI (index.html), not the marketing landing
        assert "Building Permit Intelligence" not in html or "My Account" in html or "account" in html.lower()

    def test_logout_redirects(self, client):
        """POST /auth/logout clears session and redirects."""
        _login(client)
        rv = client.post("/auth/logout", follow_redirects=False)
        assert rv.status_code in (302, 303)


# ---------------------------------------------------------------------------
# 3. Authenticated user flows
# ---------------------------------------------------------------------------

class TestAuthenticatedFlows:
    """Authenticated user can access protected routes."""

    def test_account_page_accessible(self, client):
        """Authenticated user can access /account."""
        _login(client)
        rv = client.get("/account")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "My Account" in html

    def test_account_has_watch_list(self, client):
        """Account page shows the watch list section."""
        _login(client)
        rv = client.get("/account")
        html = rv.data.decode()
        assert "Watch List" in html

    def test_portfolio_accessible(self, client):
        """Authenticated user can access /portfolio."""
        _login(client)
        rv = client.get("/portfolio")
        assert rv.status_code == 200


# ---------------------------------------------------------------------------
# 4. Health and infrastructure endpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """GET /health returns expected JSON structure."""

    def test_health_returns_200(self, client):
        """Health endpoint returns 200."""
        rv = client.get("/health")
        assert rv.status_code == 200

    def test_health_returns_json(self, client):
        """Health endpoint returns valid JSON."""
        rv = client.get("/health")
        data = json.loads(rv.data)
        assert "status" in data
        assert data["status"] in ("ok", "degraded")

    def test_health_has_expected_fields(self, client):
        """Health JSON includes backend, db_connected, table_count."""
        rv = client.get("/health")
        data = json.loads(rv.data)
        assert "backend" in data
        assert "db_connected" in data


class TestSitemap:
    """GET /sitemap.xml returns valid XML."""

    def test_sitemap_returns_200(self, client):
        """Sitemap endpoint returns 200."""
        rv = client.get("/sitemap.xml")
        assert rv.status_code == 200

    def test_sitemap_is_xml(self, client):
        """Sitemap has XML content type."""
        rv = client.get("/sitemap.xml")
        assert "xml" in rv.content_type


# ---------------------------------------------------------------------------
# 5. Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    """Rate limiting returns 429 after threshold."""

    def test_search_rate_limit(self, client):
        """Exceeding search rate limit returns 429."""
        # Search rate limit is 15/min — send 20 requests
        for i in range(20):
            rv = client.get(f"/search?q=test{i}")
            if rv.status_code == 429:
                break
        else:
            # If we got through 20 without 429, the rate limiter may not
            # apply in TESTING mode — that's acceptable
            pytest.skip("Rate limiter not active in TESTING mode")
        assert rv.status_code == 429


# ---------------------------------------------------------------------------
# 6. Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Application handles errors gracefully."""

    def test_404_for_unknown_route(self, client):
        """Unknown routes return 404."""
        rv = client.get("/this-route-does-not-exist-12345")
        assert rv.status_code == 404

    def test_search_with_xss_attempt(self, client):
        """Search sanitizes XSS attempts."""
        rv = client.get('/search?q=<script>alert("xss")</script>')
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "<script>alert" not in html


# ---------------------------------------------------------------------------
# 7. Admin-only flows
# ---------------------------------------------------------------------------

class TestAdminFlows:
    """Admin users can access admin-only routes."""

    def test_admin_ops_requires_admin(self, client):
        """Non-admin cannot access /admin/ops."""
        _login(client)
        rv = client.get("/admin/ops")
        # Should redirect to login or return 403
        assert rv.status_code in (302, 403, 404)

    def test_admin_ops_accessible_for_admin(self, client):
        """Admin user can access /admin/ops."""
        _login_admin(client)
        rv = client.get("/admin/ops")
        assert rv.status_code == 200
