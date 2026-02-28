"""Tests for Cache-Control headers on static assets (Sprint 84-B).

Verifies that the _add_static_cache_headers after_request hook:
  - Sets long-lived cache headers on CSS and JS responses
  - Sets long-lived cache headers on image and font responses
  - Does NOT set Cache-Control on HTML page responses
  - Only activates for /static/ path prefix
  - Does NOT set Cache-Control on non-200 responses

Tests exercise the hook function directly within a test request context to
avoid the need for static files to exist on disk.
"""

import pytest
from flask import Response as FlaskResponse


@pytest.fixture(scope="module")
def flask_app():
    """Import the Flask app and configure for testing."""
    from web.app import app
    app.config["TESTING"] = True
    return app


def _find_hook(flask_app):
    """Return the _add_static_cache_headers after_request hook from the app."""
    hooks = flask_app.after_request_funcs.get(None, [])
    hook = next(
        (f for f in hooks if f.__name__ == "_add_static_cache_headers"),
        None,
    )
    assert hook is not None, "_add_static_cache_headers hook not registered on app"
    return hook


def _run_hook(flask_app, path: str, content_type: str, status_code: int = 200) -> str | None:
    """Exercise the hook inside a fake request context; return Cache-Control value."""
    hook = _find_hook(flask_app)
    with flask_app.test_request_context(path):
        response = FlaskResponse(
            response=b"fake content",
            status=status_code,
            content_type=content_type,
        )
        result = hook(response)
        return result.headers.get("Cache-Control")


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def test_static_css_has_cache_control(flask_app):
    """CSS files served from /static/ get a 1-day cache with 7-day SWR."""
    cc = _run_hook(flask_app, "/static/style.css", "text/css; charset=utf-8")
    assert cc is not None, "Cache-Control header missing on CSS response"
    assert "public" in cc
    assert "max-age=86400" in cc
    assert "stale-while-revalidate=604800" in cc


def test_static_css_no_cache_on_non_200(flask_app):
    """Cache-Control is NOT set on CSS 404 responses."""
    cc = _run_hook(flask_app, "/static/missing.css", "text/css", status_code=404)
    assert cc is None, "Cache-Control should not be set on non-200 responses"


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

def test_static_js_has_cache_control(flask_app):
    """JS files served from /static/ get a 1-day cache with 7-day SWR."""
    cc = _run_hook(flask_app, "/static/app.js", "application/javascript; charset=utf-8")
    assert cc is not None, "Cache-Control header missing on JS response"
    assert "public" in cc
    assert "max-age=86400" in cc
    assert "stale-while-revalidate=604800" in cc


def test_static_js_text_javascript_content_type(flask_app):
    """text/javascript content-type also gets the CSS/JS cache policy."""
    cc = _run_hook(flask_app, "/static/app.js", "text/javascript")
    assert cc is not None
    assert "max-age=86400" in cc


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

def test_static_image_png_has_cache_control(flask_app):
    """PNG images get a 7-day cache."""
    cc = _run_hook(flask_app, "/static/logo.png", "image/png")
    assert cc is not None, "Cache-Control header missing on PNG response"
    assert "public" in cc
    assert "max-age=604800" in cc


def test_static_image_svg_has_cache_control(flask_app):
    """SVG files get the long-lived image cache via content-type."""
    cc = _run_hook(flask_app, "/static/icon.svg", "image/svg+xml")
    assert cc is not None
    assert "max-age=604800" in cc


def test_static_image_extension_fallback(flask_app):
    """PNG files get the cache even if content-type is generic."""
    cc = _run_hook(flask_app, "/static/icon.png", "application/octet-stream")
    assert cc is not None
    assert "max-age=604800" in cc


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

def test_static_font_woff2_by_content_type(flask_app):
    """WOFF2 fonts get the long-lived font cache via content-type."""
    cc = _run_hook(flask_app, "/static/font.woff2", "font/woff2")
    assert cc is not None, "Cache-Control header missing on WOFF2 response"
    assert "public" in cc
    assert "max-age=604800" in cc


def test_static_font_woff2_by_path_extension(flask_app):
    """WOFF2 fonts get the cache even if content-type is application/octet-stream."""
    cc = _run_hook(flask_app, "/static/font.woff2", "application/octet-stream")
    assert cc is not None
    assert "max-age=604800" in cc


# ---------------------------------------------------------------------------
# HTML pages — the static hook must be a no-op for HTML
# ---------------------------------------------------------------------------

def test_html_page_no_cache_control(flask_app):
    """HTML responses from non-/static/ paths do NOT get Cache-Control from the static hook."""
    cc = _run_hook(flask_app, "/search", "text/html; charset=utf-8")
    assert cc is None, (
        "HTML page responses must not receive Cache-Control from the static hook"
    )


def test_static_html_no_cache_control(flask_app):
    """HTML files under /static/ get no cache header (not CSS/JS/image/font)."""
    cc = _run_hook(flask_app, "/static/some.html", "text/html; charset=utf-8")
    assert cc is None, "HTML files under /static/ should not be cached by this hook"


# ---------------------------------------------------------------------------
# Non-/static/ paths — hook must be a no-op regardless of content type
# ---------------------------------------------------------------------------

def test_api_json_endpoint_no_static_cache(flask_app):
    """/api/ JSON responses are unaffected by the static cache hook."""
    cc = _run_hook(flask_app, "/api/permits", "application/json")
    assert cc is None, "/api/ paths must not be touched by the static asset cache hook"
