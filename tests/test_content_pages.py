"""Integration tests for the QS13 content pages: /docs, /privacy, /terms, /join-beta.

Also validates SEO metadata on the landing page (og:title, JSON-LD, no noindex).
"""
import pytest

from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with a temp database for isolation."""
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
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# /docs
# ---------------------------------------------------------------------------

def test_docs_page_loads(client):
    """GET /docs → 200 with tool-catalog content."""
    resp = client.get("/docs")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8", errors="replace")
    # Page title or content must reference API/tools
    assert "api" in html.lower() or "tool" in html.lower()


def test_docs_page_contains_api_reference(client):
    """GET /docs → page mentions 'API Documentation' (as in the <title>)."""
    resp = client.get("/docs")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8", errors="replace")
    assert "API Documentation" in html or "api documentation" in html.lower()


# ---------------------------------------------------------------------------
# /privacy
# ---------------------------------------------------------------------------

def test_privacy_page_loads(client):
    """GET /privacy → 200."""
    resp = client.get("/privacy")
    assert resp.status_code == 200


def test_privacy_page_contains_privacy_header(client):
    """GET /privacy → page contains 'Privacy' heading."""
    resp = client.get("/privacy")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8", errors="replace")
    assert "Privacy" in html


def test_privacy_page_contains_data_collection_section(client):
    """GET /privacy → page discusses data collection."""
    resp = client.get("/privacy")
    html = resp.data.decode("utf-8", errors="replace").lower()
    assert "collect" in html or "data" in html


# ---------------------------------------------------------------------------
# /terms
# ---------------------------------------------------------------------------

def test_terms_page_loads(client):
    """GET /terms → 200."""
    resp = client.get("/terms")
    assert resp.status_code == 200


def test_terms_page_contains_terms_header(client):
    """GET /terms → page contains 'Terms' heading."""
    resp = client.get("/terms")
    html = resp.data.decode("utf-8", errors="replace")
    assert "Terms" in html


def test_terms_page_contains_beta_disclaimer(client):
    """GET /terms → page references beta status."""
    resp = client.get("/terms")
    html = resp.data.decode("utf-8", errors="replace").lower()
    assert "beta" in html


# ---------------------------------------------------------------------------
# /join-beta
# ---------------------------------------------------------------------------

def test_join_beta_page_loads(client):
    """GET /join-beta → 200 with form content."""
    resp = client.get("/join-beta")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8", errors="replace").lower()
    assert "beta" in html or "waitlist" in html


# ---------------------------------------------------------------------------
# Landing page (/) — SEO metadata
# ---------------------------------------------------------------------------

def test_landing_page_loads(client):
    """GET / → 200."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_landing_page_has_og_title(client):
    """Landing page has og:title meta tag for social sharing."""
    resp = client.get("/")
    html = resp.data.decode("utf-8", errors="replace")
    assert 'og:title' in html or 'property="og:title"' in html


def test_landing_page_has_json_ld(client):
    """Landing page has JSON-LD structured data (SoftwareApplication)."""
    resp = client.get("/")
    html = resp.data.decode("utf-8", errors="replace")
    assert "SoftwareApplication" in html or "application/ld+json" in html


def test_landing_page_has_no_noindex(client):
    """Landing page does NOT have noindex meta tag — must be indexable."""
    resp = client.get("/")
    html = resp.data.decode("utf-8", errors="replace")
    # We allow "noindex, nofollow" only on non-landing pages
    # The landing page should NOT have a noindex directive
    assert "noindex" not in html
