"""Tests for the share mechanic — Sprint QS10-T3-3D.

Covers:
- share_button.html component exists and contains required markup
- share.js exists and contains navigator.share check
- share.css exists and uses CSS custom properties (no hardcoded hex)
- All 6 tool pages include the share button partial
- All 6 tool pages link share.js
- All 6 tool pages link share.css
- /api/share endpoint returns correct JSON
- New tool page routes (entity_network, revision_risk) render correctly
"""
import os
import re
import pytest

# ── File paths ──────────────────────────────────────────────────────────────

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_TOOLS = os.path.join(REPO_ROOT, "web", "templates", "tools")
COMPONENTS_DIR = os.path.join(REPO_ROOT, "web", "templates", "components")
STATIC_JS = os.path.join(REPO_ROOT, "web", "static", "js")
STATIC_CSS = os.path.join(REPO_ROOT, "web", "static", "css")

TOOL_PAGES = [
    "station_predictor.html",
    "stuck_permit.html",
    "what_if.html",
    "cost_of_delay.html",
    "entity_network.html",
    "revision_risk.html",
]


# ── Component file tests ─────────────────────────────────────────────────────

def test_share_button_component_exists():
    """share_button.html must exist in web/templates/components/."""
    path = os.path.join(COMPONENTS_DIR, "share_button.html")
    assert os.path.isfile(path), f"Missing: {path}"


def test_share_button_has_share_btn_class():
    """share_button.html must contain an element with class share-btn."""
    path = os.path.join(COMPONENTS_DIR, "share_button.html")
    content = open(path).read()
    assert "share-btn" in content, "share_button.html must contain class 'share-btn'"


def test_share_button_has_share_container_class():
    """share_button.html must contain a share-container wrapper."""
    path = os.path.join(COMPONENTS_DIR, "share_button.html")
    content = open(path).read()
    assert "share-container" in content, "share_button.html must contain class 'share-container'"


def test_share_js_exists():
    """share.js must exist in web/static/js/."""
    path = os.path.join(STATIC_JS, "share.js")
    assert os.path.isfile(path), f"Missing: {path}"


def test_share_js_contains_navigator_share_check():
    """share.js must check for navigator.share before using it."""
    path = os.path.join(STATIC_JS, "share.js")
    content = open(path).read()
    assert "navigator.share" in content, "share.js must contain navigator.share check"


def test_share_js_contains_clipboard_fallback():
    """share.js must have a clipboard/fallback path for desktop."""
    path = os.path.join(STATIC_JS, "share.js")
    content = open(path).read()
    assert "clipboard" in content or "execCommand" in content, (
        "share.js must contain clipboard or execCommand fallback"
    )


def test_share_css_exists():
    """share.css must exist in web/static/css/."""
    path = os.path.join(STATIC_CSS, "share.css")
    assert os.path.isfile(path), f"Missing: {path}"


def test_share_css_uses_css_vars_not_hardcoded_hex():
    """share.css must not contain hardcoded hex color values.

    All colors must use CSS custom properties (var(--...)) from DESIGN_TOKENS.md.
    """
    path = os.path.join(STATIC_CSS, "share.css")
    content = open(path).read()
    # Strip comments
    content_no_comments = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    hex_pattern = re.compile(r'(?<![a-zA-Z0-9_-])#[0-9a-fA-F]{3,8}\b')
    hex_matches = hex_pattern.findall(content_no_comments)
    assert not hex_matches, (
        f"share.css contains hardcoded hex values: {hex_matches}. "
        "Use CSS custom properties (var(--...)) instead."
    )


# ── Tool page integration tests ───────────────────────────────────────────────

@pytest.mark.parametrize("page_filename", TOOL_PAGES)
def test_tool_page_includes_share_button(page_filename):
    """Each tool page must include the share_button.html component."""
    path = os.path.join(TEMPLATES_TOOLS, page_filename)
    assert os.path.isfile(path), f"Tool page does not exist: {path}"
    content = open(path).read()
    assert 'include "components/share_button.html"' in content or \
           "include 'components/share_button.html'" in content, (
        f"{page_filename} must include components/share_button.html"
    )


@pytest.mark.parametrize("page_filename", TOOL_PAGES)
def test_tool_page_links_share_js(page_filename):
    """Each tool page must link share.js."""
    path = os.path.join(TEMPLATES_TOOLS, page_filename)
    content = open(path).read()
    assert "share.js" in content, (
        f"{page_filename} must link share.js"
    )


@pytest.mark.parametrize("page_filename", TOOL_PAGES)
def test_tool_page_links_share_css(page_filename):
    """Each tool page must link share.css."""
    path = os.path.join(TEMPLATES_TOOLS, page_filename)
    content = open(path).read()
    assert "share.css" in content, (
        f"{page_filename} must link share.css"
    )


# ── Flask route + API tests ──────────────────────────────────────────────────

@pytest.fixture
def client():
    """Flask test client with TESTING mode enabled."""
    import sys
    sys.path.insert(0, REPO_ROOT)
    os.environ.setdefault("TESTING", "1")
    from web.app import app
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def test_share_api_endpoint_post(client):
    """/api/share POST returns JSON with url and shared=True."""
    resp = client.post(
        "/api/share",
        json={"url": "https://sfpermits.ai/tools/station-predictor"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("shared") is True
    assert "url" in data


def test_share_api_endpoint_no_body(client):
    """/api/share POST with no body still returns JSON with shared=True."""
    resp = client.post("/api/share", content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get("shared") is True


def test_entity_network_route_accessible(client):
    """/tools/entity-network is publicly accessible (returns 200)."""
    resp = client.get("/tools/entity-network")
    assert resp.status_code == 200, (
        f"Expected 200 for /tools/entity-network, got {resp.status_code}"
    )


def test_revision_risk_route_accessible(client):
    """/tools/revision-risk is publicly accessible (returns 200)."""
    resp = client.get("/tools/revision-risk")
    assert resp.status_code == 200, (
        f"Expected 200 for /tools/revision-risk, got {resp.status_code}"
    )
