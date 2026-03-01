"""Tests for SEO meta tags and admin beta funnel routes (QS13-1C)."""
import os
import pytest


LANDING_HTML_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'web', 'templates', 'landing.html'
)
INDEX_HTML_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'web', 'templates', 'index.html'
)
BETA_FUNNEL_HTML_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'web', 'templates', 'admin', 'beta_funnel.html'
)


# ---------------------------------------------------------------------------
# Static file checks — no Flask app needed
# ---------------------------------------------------------------------------

def test_landing_has_og_title():
    """landing.html contains og:title meta tag."""
    with open(LANDING_HTML_PATH) as f:
        content = f.read()
    assert 'og:title' in content, "landing.html should have og:title"


def test_landing_has_og_image():
    """landing.html contains og:image meta tag."""
    with open(LANDING_HTML_PATH) as f:
        content = f.read()
    assert 'og:image' in content, "landing.html should have og:image"


def test_landing_has_og_description():
    """landing.html contains og:description meta tag."""
    with open(LANDING_HTML_PATH) as f:
        content = f.read()
    assert 'og:description' in content, "landing.html should have og:description"


def test_landing_has_og_type():
    """landing.html contains og:type meta tag."""
    with open(LANDING_HTML_PATH) as f:
        content = f.read()
    assert 'og:type' in content, "landing.html should have og:type"


def test_landing_has_json_ld():
    """landing.html contains JSON-LD structured data."""
    with open(LANDING_HTML_PATH) as f:
        content = f.read()
    assert 'application/ld+json' in content, "landing.html should have JSON-LD"


def test_landing_has_twitter_card():
    """landing.html contains Twitter Card meta tag."""
    with open(LANDING_HTML_PATH) as f:
        content = f.read()
    assert 'twitter:card' in content, "landing.html should have twitter:card"


def test_landing_has_twitter_image():
    """landing.html contains Twitter image meta tag."""
    with open(LANDING_HTML_PATH) as f:
        content = f.read()
    assert 'twitter:image' in content, "landing.html should have twitter:image"


def test_index_no_noindex():
    """index.html does NOT contain noindex directive."""
    if not os.path.isfile(INDEX_HTML_PATH):
        pytest.skip("index.html not found")
    with open(INDEX_HTML_PATH) as f:
        content = f.read()
    assert 'noindex' not in content, "index.html should not have noindex"


def test_beta_funnel_template_exists():
    """admin/beta_funnel.html template file exists."""
    assert os.path.isfile(BETA_FUNNEL_HTML_PATH), \
        f"Template not found: {BETA_FUNNEL_HTML_PATH}"


def test_beta_funnel_template_has_export_link():
    """admin/beta_funnel.html contains the export CSV link."""
    with open(BETA_FUNNEL_HTML_PATH) as f:
        content = f.read()
    assert 'beta-funnel/export' in content, \
        "beta_funnel.html should have export CSV link"


def test_beta_funnel_template_uses_token_classes():
    """admin/beta_funnel.html uses design token classes."""
    with open(BETA_FUNNEL_HTML_PATH) as f:
        content = f.read()
    assert 'glass-card' in content, "beta_funnel.html should use glass-card token class"


# ---------------------------------------------------------------------------
# Route tests — require Flask app
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client with temp DuckDB for isolation."""
    db_path = str(tmp_path / "test_seo_funnel.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()

    from web.app import app, _rate_buckets
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login_admin(client, email="admin_funnel@example.com"):
    """Create admin user and establish session via magic-link flow."""
    import web.auth as auth_mod
    orig_admin = auth_mod.ADMIN_EMAIL
    auth_mod.ADMIN_EMAIL = email
    user = auth_mod.get_or_create_user(email)
    token = auth_mod.create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    auth_mod.ADMIN_EMAIL = orig_admin
    return user


def test_beta_funnel_requires_auth(client):
    """GET /admin/beta-funnel redirects or 403s for anonymous users."""
    resp = client.get('/admin/beta-funnel', follow_redirects=False)
    assert resp.status_code in (302, 401, 403), \
        f"Expected redirect/auth error, got {resp.status_code}"


def test_beta_funnel_accessible_for_admin(client):
    """GET /admin/beta-funnel returns 200 for admin users."""
    _login_admin(client)
    resp = client.get('/admin/beta-funnel', follow_redirects=True)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


def test_beta_funnel_export_requires_auth(client):
    """GET /admin/beta-funnel/export redirects or 403s for anonymous users."""
    resp = client.get('/admin/beta-funnel/export', follow_redirects=False)
    assert resp.status_code in (302, 401, 403), \
        f"Expected redirect/auth error, got {resp.status_code}"


def test_beta_funnel_export_csv_for_admin(client):
    """GET /admin/beta-funnel/export returns CSV for admin users."""
    _login_admin(client)
    resp = client.get('/admin/beta-funnel/export', follow_redirects=True)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert 'csv' in resp.content_type.lower(), \
        f"Expected CSV content-type, got {resp.content_type}"


def test_beta_funnel_route_registered():
    """Route /admin/beta-funnel is registered in the Flask app."""
    from web.app import app as flask_app
    rules = {r.rule for r in flask_app.url_map.iter_rules()}
    assert '/admin/beta-funnel' in rules, "/admin/beta-funnel route not registered"


def test_beta_funnel_export_route_registered():
    """Route /admin/beta-funnel/export is registered in the Flask app."""
    from web.app import app as flask_app
    rules = {r.rule for r in flask_app.url_map.iter_rules()}
    assert '/admin/beta-funnel/export' in rules, "/admin/beta-funnel/export route not registered"
