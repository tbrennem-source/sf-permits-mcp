"""Tests for QS4-C Obsidian design migration — head fragment, index, brief."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


@pytest.fixture
def auth_client(client):
    """Authenticated test client."""
    import src.db as db_mod
    if db_mod.BACKEND == "duckdb":
        db_mod.init_user_schema()
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user("qs4c-test@test.com")
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return client


# ── Fragment Existence ────────────────────────────────────────────────────

def test_head_obsidian_fragment_exists():
    """head_obsidian.html fragment file exists."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "fragments", "head_obsidian.html")
    assert os.path.isfile(path), "fragments/head_obsidian.html not found"


def test_head_obsidian_contains_google_fonts():
    """Fragment includes Google Fonts link."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "fragments", "head_obsidian.html")
    content = open(path).read()
    assert "fonts.googleapis.com" in content


def test_head_obsidian_contains_manifest():
    """Fragment includes PWA manifest link."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "fragments", "head_obsidian.html")
    content = open(path).read()
    assert "manifest.json" in content


def test_head_obsidian_contains_theme_color():
    """Fragment includes theme-color meta tag."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "fragments", "head_obsidian.html")
    content = open(path).read()
    assert 'name="theme-color"' in content
    assert "#22D3EE" in content


def test_head_obsidian_contains_legacy_aliases():
    """Fragment includes legacy alias CSS variables for nav.html compatibility."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "fragments", "head_obsidian.html")
    content = open(path).read()
    assert "--bg: var(--bg-deep)" in content
    assert "--surface: var(--bg-surface)" in content
    assert "--accent: var(--signal-cyan)" in content
    assert "--success: var(--signal-green)" in content
    assert "--warning: var(--signal-amber)" in content
    assert "--error: var(--signal-red)" in content


def test_head_obsidian_contains_design_system_css():
    """Fragment links to design-system.css."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "fragments", "head_obsidian.html")
    content = open(path).read()
    assert "design-system.css" in content


# ── index.html Template Checks ───────────────────────────────────────────

def test_index_includes_head_obsidian():
    """index.html includes the shared head fragment."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "index.html")
    content = open(path).read()
    assert 'include "fragments/head_obsidian.html"' in content


def test_index_body_has_obsidian_class():
    """index.html body tag has class='obsidian'."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "index.html")
    content = open(path).read()
    assert 'class="obsidian"' in content


def test_index_no_inline_google_fonts():
    """index.html does not have duplicate inline Google Fonts link."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "index.html")
    content = open(path).read()
    # The fragment provides fonts — index should not have its own link
    # Count occurrences: should only appear via include, not as literal <link> in template
    direct_links = content.count('href="https://fonts.googleapis.com')
    assert direct_links == 0, f"Found {direct_links} direct Google Fonts links in index.html"


def test_index_no_legacy_root_vars():
    """index.html does not have inline legacy :root CSS variable block."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "index.html")
    content = open(path).read()
    assert "--bg: #0f1117" not in content, "Legacy :root vars still present"


def test_index_renders_200_authenticated(auth_client):
    """Authenticated user gets 200 on index page."""
    rv = auth_client.get("/")
    assert rv.status_code == 200


def test_index_has_design_system_css_link(auth_client):
    """Rendered index page includes design-system.css."""
    rv = auth_client.get("/")
    html = rv.data.decode()
    assert "design-system.css" in html


def test_index_has_obsidian_body(auth_client):
    """Rendered index page has body.obsidian class."""
    rv = auth_client.get("/")
    html = rv.data.decode()
    assert 'class="obsidian"' in html


def test_index_nav_renders(auth_client):
    """Nav badges are visible on authenticated index page."""
    rv = auth_client.get("/")
    html = rv.data.decode()
    assert "Search" in html
    assert "Brief" in html
    assert "sfpermits" in html


def test_index_has_font_display():
    """index.html uses font-display CSS variable for headings."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "index.html")
    content = open(path).read()
    assert "var(--font-display)" in content


def test_index_has_card_shadow():
    """index.html uses Obsidian card shadow pattern."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "index.html")
    content = open(path).read()
    assert "var(--card-shadow" in content


# ── brief.html Template Checks ───────────────────────────────────────────

def test_brief_includes_head_obsidian():
    """brief.html includes the shared head fragment."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "brief.html")
    content = open(path).read()
    assert 'include "fragments/head_obsidian.html"' in content


def test_brief_body_has_obsidian_class():
    """brief.html body tag has class='obsidian'."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "brief.html")
    content = open(path).read()
    assert 'class="obsidian"' in content


def test_brief_no_inline_google_fonts():
    """brief.html does not have duplicate inline Google Fonts link."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "brief.html")
    content = open(path).read()
    direct_links = content.count('href="https://fonts.googleapis.com')
    assert direct_links == 0, f"Found {direct_links} direct Google Fonts links in brief.html"


def test_brief_no_legacy_root_vars():
    """brief.html does not have inline legacy :root CSS variable block."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "brief.html")
    content = open(path).read()
    assert "--bg: #0f1117" not in content, "Legacy :root vars still present"


def test_brief_renders_200_authenticated(auth_client):
    """Authenticated user gets 200 on brief page."""
    rv = auth_client.get("/brief")
    assert rv.status_code == 200


def test_brief_has_design_system_css_link(auth_client):
    """Rendered brief page includes design-system.css."""
    rv = auth_client.get("/brief")
    html = rv.data.decode()
    assert "design-system.css" in html


def test_brief_has_obsidian_body(auth_client):
    """Rendered brief page has body.obsidian class."""
    rv = auth_client.get("/brief")
    html = rv.data.decode()
    assert 'class="obsidian"' in html


def test_brief_nav_renders(auth_client):
    """Nav badges are visible on brief page."""
    rv = auth_client.get("/brief")
    html = rv.data.decode()
    assert "Search" in html
    assert "Brief" in html
    assert "sfpermits" in html


def test_brief_signal_colors_in_template():
    """brief.html health indicators use signal color CSS vars."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "brief.html")
    content = open(path).read()
    # Health status classes use --success (→ signal-green), --warning (→ signal-amber), --error (→ signal-red)
    assert "var(--success)" in content
    assert "var(--warning)" in content
    assert "var(--error)" in content


def test_brief_has_font_display():
    """brief.html uses font-display CSS variable for headings/labels."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "brief.html")
    content = open(path).read()
    assert "var(--font-display)" in content


def test_brief_has_card_shadow():
    """brief.html uses Obsidian card shadow pattern."""
    path = os.path.join(os.path.dirname(__file__), "..", "web", "templates",
                        "brief.html")
    content = open(path).read()
    assert "var(--card-shadow" in content
