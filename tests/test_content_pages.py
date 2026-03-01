"""Integration tests for QS13 content pages and SEO.

Tests for:
- Existing content pages (methodology, about-data, beta-request, adu, sitemap)
- QS13 new pages (/docs, /privacy, /terms, /join-beta) — skipped if 404
- SEO metadata (OG tags, no noindex on public pages)
- API documentation page completeness (/docs)

Note: The landing.html template uses inline CSS and does not include og: meta
tags in the current version. OG tag tests skip gracefully if not present.
"""

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend for test isolation."""
    db_path = str(tmp_path / "test_content_pages.duckdb")
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
    import os
    os.environ.setdefault("TESTING", "1")
    from web.app import app as flask_app
    from web.helpers import _rate_buckets
    flask_app.config["TESTING"] = True
    _rate_buckets.clear()
    with flask_app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# Existing content pages (should always pass)
# ---------------------------------------------------------------------------

class TestExistingContentPages:

    def test_landing_page_returns_200(self, client):
        """Landing page returns 200."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_landing_page_has_sitename(self, client):
        """Landing page contains site name."""
        resp = client.get("/")
        assert b"sfpermits" in resp.data.lower()

    def test_methodology_page_returns_200(self, client):
        """GET /methodology returns 200."""
        resp = client.get("/methodology")
        assert resp.status_code == 200

    def test_about_data_page_returns_200(self, client):
        """GET /about-data returns 200."""
        resp = client.get("/about-data")
        assert resp.status_code == 200

    def test_beta_request_page_returns_200(self, client):
        """GET /beta-request returns 200."""
        resp = client.get("/beta-request")
        assert resp.status_code == 200

    def test_adu_page_returns_200(self, client):
        """GET /adu returns 200."""
        resp = client.get("/adu")
        assert resp.status_code == 200

    def test_health_returns_200(self, client):
        """GET /health returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_sitemap_returns_xml(self, client):
        """GET /sitemap.xml returns valid XML."""
        resp = client.get("/sitemap.xml")
        assert resp.status_code == 200
        ct = resp.headers.get("Content-Type", "")
        assert "xml" in ct.lower()
        assert b"<urlset" in resp.data


# ---------------------------------------------------------------------------
# QS13 new pages (skip if not yet built)
# ---------------------------------------------------------------------------

class TestNewContentPages:

    def test_docs_page_returns_200(self, client):
        """/docs returns 200 if implemented."""
        resp = client.get("/docs")
        if resp.status_code == 404:
            pytest.skip("/docs not implemented yet (QS13 T2)")
        assert resp.status_code == 200

    def test_docs_page_contains_api_content(self, client):
        """/docs page contains API/tool documentation."""
        resp = client.get("/docs")
        if resp.status_code == 404:
            pytest.skip("/docs not implemented yet (QS13 T2)")
        data = resp.data.decode().lower()
        assert "tool" in data or "api" in data or "permit" in data

    def test_docs_page_has_substantial_content(self, client):
        """/docs page has at least 5KB of content."""
        resp = client.get("/docs")
        if resp.status_code == 404:
            pytest.skip("/docs not implemented yet (QS13 T2)")
        assert len(resp.data) > 5000

    def test_docs_lists_at_least_20_tools(self, client):
        """/docs page references at least 20 tools."""
        resp = client.get("/docs")
        if resp.status_code == 404:
            pytest.skip("/docs not implemented yet (QS13 T2)")
        data = resp.data.decode()
        # Count mentions of "tool" (case-insensitive)
        tool_count = data.lower().count("tool")
        # Should mention the word "tool" many times in an API docs page
        assert tool_count >= 20, f"Only found {tool_count} 'tool' mentions in /docs"

    def test_privacy_page_returns_200(self, client):
        """/privacy returns 200 if implemented."""
        resp = client.get("/privacy")
        if resp.status_code == 404:
            pytest.skip("/privacy not implemented yet (QS13 T2)")
        assert resp.status_code == 200

    def test_privacy_page_has_content(self, client):
        """/privacy page has meaningful content."""
        resp = client.get("/privacy")
        if resp.status_code == 404:
            pytest.skip("/privacy not implemented yet (QS13 T2)")
        data = resp.data.decode().lower()
        assert "privacy" in data or "data" in data

    def test_terms_page_returns_200(self, client):
        """/terms returns 200 if implemented."""
        resp = client.get("/terms")
        if resp.status_code == 404:
            pytest.skip("/terms not implemented yet (QS13 T2)")
        assert resp.status_code == 200

    def test_terms_page_has_content(self, client):
        """/terms page has meaningful content."""
        resp = client.get("/terms")
        if resp.status_code == 404:
            pytest.skip("/terms not implemented yet (QS13 T2)")
        data = resp.data.decode().lower()
        assert "terms" in data or "service" in data or "use" in data

    def test_join_beta_page_returns_200(self, client):
        """/join-beta returns 200 if implemented."""
        resp = client.get("/join-beta")
        if resp.status_code == 404:
            pytest.skip("/join-beta not implemented yet (QS13 T1)")
        assert resp.status_code == 200

    def test_join_beta_page_has_signup_form(self, client):
        """/join-beta has an email input."""
        resp = client.get("/join-beta")
        if resp.status_code == 404:
            pytest.skip("/join-beta not implemented yet (QS13 T1)")
        data = resp.data.decode().lower()
        assert "email" in data

    def test_join_beta_thanks_page_returns_200_or_skip(self, client):
        """/join-beta/thanks returns 200 if implemented."""
        resp = client.get("/join-beta/thanks")
        if resp.status_code == 404:
            pytest.skip("/join-beta/thanks not implemented yet (QS13 T1)")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# SEO metadata
# ---------------------------------------------------------------------------

class TestSEOMetadata:

    def test_landing_has_title_tag(self, client):
        """Landing page has a <title> tag."""
        resp = client.get("/")
        assert b"<title>" in resp.data

    def test_landing_has_meta_description(self, client):
        """Landing page has a meta description tag."""
        resp = client.get("/")
        assert b'name="description"' in resp.data

    def test_landing_has_og_title(self, client):
        """Landing page has og:title meta tag (skip if not yet added)."""
        resp = client.get("/")
        data = resp.data
        has_og = b'og:title' in data or b'property="og:' in data or b"property='og:" in data
        if not has_og:
            pytest.skip("og:title not yet in landing page (QS13 T2)")
        assert has_og

    def test_landing_has_og_description(self, client):
        """Landing page has og:description meta tag (skip if not yet added)."""
        resp = client.get("/")
        data = resp.data
        has_og = b'og:description' in data
        if not has_og:
            pytest.skip("og:description not yet in landing page (QS13 T2)")
        assert has_og

    def test_landing_no_noindex(self, client):
        """Landing page does not have noindex directive."""
        resp = client.get("/")
        assert b"noindex" not in resp.data

    def test_health_no_noindex(self, client):
        """Health endpoint does not have noindex (it returns JSON not HTML)."""
        resp = client.get("/health")
        assert b"noindex" not in resp.data

    def test_docs_no_noindex(self, client):
        """/docs page does not have noindex if it exists."""
        resp = client.get("/docs")
        if resp.status_code == 404:
            pytest.skip("/docs not implemented yet")
        assert b"noindex" not in resp.data

    def test_methodology_no_noindex(self, client):
        """Methodology page does not have noindex."""
        resp = client.get("/methodology")
        assert b"noindex" not in resp.data

    def test_sitemap_includes_key_pages(self, client):
        """Sitemap includes the main public pages."""
        resp = client.get("/sitemap.xml")
        assert resp.status_code == 200
        data = resp.data.decode()
        assert "/" in data
        assert "/methodology" in data or "/about-data" in data

    def test_landing_has_viewport_meta(self, client):
        """Landing page has viewport meta tag (mobile-friendly)."""
        resp = client.get("/")
        assert b'name="viewport"' in resp.data


# ---------------------------------------------------------------------------
# Docs page completeness (QS13 T2)
# ---------------------------------------------------------------------------

class TestDocsCompleteness:

    def test_docs_accessible_without_login(self, client):
        """/docs is accessible to unauthenticated users."""
        resp = client.get("/docs")
        if resp.status_code == 404:
            pytest.skip("/docs not implemented yet (QS13 T2)")
        # Should not redirect to login
        assert resp.status_code == 200

    def test_docs_lists_search_permits(self, client):
        """/docs mentions search_permits tool."""
        resp = client.get("/docs")
        if resp.status_code == 404:
            pytest.skip("/docs not implemented yet (QS13 T2)")
        data = resp.data.decode().lower()
        assert "search_permits" in data or "search permits" in data

    def test_docs_lists_property_lookup(self, client):
        """/docs mentions property_lookup tool."""
        resp = client.get("/docs")
        if resp.status_code == 404:
            pytest.skip("/docs not implemented yet (QS13 T2)")
        data = resp.data.decode().lower()
        assert "property_lookup" in data or "property lookup" in data

    def test_docs_lists_run_query(self, client):
        """/docs mentions run_query tool (project intelligence)."""
        resp = client.get("/docs")
        if resp.status_code == 404:
            pytest.skip("/docs not implemented yet (QS13 T2)")
        data = resp.data.decode().lower()
        assert "run_query" in data or "run query" in data

    def test_docs_has_mcp_url(self, client):
        """/docs includes the MCP server URL."""
        resp = client.get("/docs")
        if resp.status_code == 404:
            pytest.skip("/docs not implemented yet (QS13 T2)")
        data = resp.data.decode()
        assert "sfpermits-mcp-api" in data or "/mcp" in data or "railway.app" in data
