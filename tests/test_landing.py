"""Tests for public landing page + address lookup + feature gating (Session C)."""

import pytest

from web.app import app, _rate_buckets


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as client:
        yield client
    _rate_buckets.clear()


def _login(client, email="landing-test@test.com"):
    """Helper: create a user and log them in via magic link."""
    import src.db as db_mod
    if db_mod.BACKEND == "duckdb":
        db_mod.init_user_schema()
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ── Landing page (unauthenticated) ──

class TestLandingPage:
    def test_landing_page_renders(self, client):
        """Unauthenticated users see the landing page."""
        rv = client.get("/")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "Building Permit Intelligence" in html

    def test_landing_has_search_form(self, client):
        """Landing page has a search form pointing to /search."""
        rv = client.get("/")
        html = rv.data.decode()
        assert 'action="/search"' in html
        assert 'name="q"' in html

    def test_landing_has_feature_cards(self, client):
        """Landing page shows capability cards (Sprint 69 redesign: question-form layout)."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "Do I need a permit?" in html
        assert "How long will it take?" in html
        assert "Is my permit stuck?" in html

    def test_landing_has_stats(self, client):
        """Landing page shows data credibility stats."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "SF building permits" in html
        assert "City data sources" in html

    def test_landing_has_sign_in_link(self, client):
        """Landing page has sign in / get started links."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "/auth/login" in html
        assert "Sign in" in html

    def test_landing_has_search_hints(self, client):
        """Landing page shows example search queries."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "1455 Market St" in html

    def test_landing_is_mobile_responsive(self, client):
        """Landing page includes viewport meta tag."""
        rv = client.get("/")
        html = rv.data.decode()
        assert 'name="viewport"' in html
        assert "width=device-width" in html


# ── Authenticated home (index.html) ──

class TestAuthenticatedHome:
    def test_logged_in_sees_app(self, client):
        """Authenticated users see the full app, not the landing page."""
        _login(client)
        rv = client.get("/")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "Analyze Project" in html
        assert "Building Permit Intelligence" not in html

    def test_logged_in_has_search_bar(self, client):
        """Authenticated homepage has the conversational search bar."""
        _login(client)
        rv = client.get("/")
        html = rv.data.decode()
        # The HTMX search form on the authenticated page
        assert "hx-post" in html or 'action="/' in html


# ── Public search (/search) ──

class TestPublicSearch:
    def test_search_empty_query_redirects(self, client):
        """GET /search without query redirects to home."""
        rv = client.get("/search")
        assert rv.status_code == 302
        assert rv.location.endswith("/") or "index" in rv.location

    def test_search_with_query_returns_results(self, client):
        """GET /search?q=... returns public search results page."""
        rv = client.get("/search?q=1455+Market+St")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "sfpermits" in html
        # Should have the public results template structure
        assert "Sign up free" in html or "search" in html.lower()

    def test_search_shows_query_in_form(self, client):
        """Search results page pre-fills the query."""
        rv = client.get("/search?q=test+address")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "test address" in html

    def test_search_authenticated_redirects(self, client):
        """Authenticated users searching via /search get redirected to /?q=."""
        _login(client, email="search-redirect@test.com")
        rv = client.get("/search?q=123+Main+St")
        assert rv.status_code == 302
        assert "q=123" in rv.location

    def test_search_has_locked_cards(self, client):
        """Public search results show locked premium feature cards."""
        rv = client.get("/search?q=1455+Market+St")
        if rv.status_code == 200:
            html = rv.data.decode()
            # Should show sign-up CTAs for premium features
            assert "Sign up free" in html or "Sign in" in html

    def test_search_rate_limited(self, client):
        """Public search is rate limited."""
        _rate_buckets.clear()
        # Exhaust the rate limit
        for i in range(20):
            client.get(f"/search?q=address+{i}")
        rv = client.get("/search?q=one+more")
        assert rv.status_code == 429
        _rate_buckets.clear()


# ── Feature gating ──

class TestFeatureGating:
    def test_brief_requires_login(self, client):
        """Brief page redirects unauthenticated users."""
        rv = client.get("/brief")
        assert rv.status_code == 302
        assert "/auth/login" in rv.location

    def test_portfolio_requires_login(self, client):
        """Portfolio page redirects unauthenticated users."""
        rv = client.get("/portfolio")
        assert rv.status_code == 302
        assert "/auth/login" in rv.location

    def test_account_requires_login(self, client):
        """Account page redirects unauthenticated users."""
        rv = client.get("/account")
        assert rv.status_code == 302
        assert "/auth/login" in rv.location

    def test_consultants_requires_login(self, client):
        """Consultants page redirects unauthenticated users."""
        rv = client.get("/consultants")
        assert rv.status_code == 302
        assert "/auth/login" in rv.location

    def test_analyses_requires_login(self, client):
        """Analysis history requires login."""
        rv = client.get("/account/analyses")
        assert rv.status_code == 302
        assert "/auth/login" in rv.location

    def test_health_is_public(self, client):
        """Health endpoint remains public."""
        rv = client.get("/health")
        assert rv.status_code == 200

    def test_auth_login_is_public(self, client):
        """Login page remains public."""
        rv = client.get("/auth/login")
        assert rv.status_code == 200

    def test_search_is_public(self, client):
        """Public search remains accessible without login."""
        rv = client.get("/search?q=test")
        assert rv.status_code == 200
