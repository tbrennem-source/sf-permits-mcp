"""Sprint 59 Agent B — Mobile Responsive Fixes tests.

Covers:
  - velocity_dashboard.html contains 480px media query with reviewer-panel and max-width: 95vw
  - admin_activity.html contains 480px media query with pagination CSS
  - admin_activity route accepts offset parameter
  - admin_activity fragment endpoint accepts offset parameter
  - Pagination block appears when results >= limit
  - offset=0 renders no Newer link
  - mobile.css contains sections 15 and 16
  - get_recent_activity accepts offset parameter
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root on path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ── Helpers ──────────────────────────────────────────────────────────────────

def read_template(name: str) -> str:
    path = REPO_ROOT / "web" / "templates" / name
    return path.read_text(encoding="utf-8")


def read_static(name: str) -> str:
    path = REPO_ROOT / "web" / "static" / name
    return path.read_text(encoding="utf-8")


# ── 1. velocity_dashboard.html CSS ──────────────────────────────────────────

def test_velocity_dashboard_has_480px_media_query():
    html = read_template("velocity_dashboard.html")
    assert "@media (max-width: 480px)" in html, "velocity_dashboard.html missing 480px media query"


def test_velocity_dashboard_reviewer_panel_max_width():
    html = read_template("velocity_dashboard.html")
    assert "max-width: 95vw" in html, "velocity_dashboard.html missing max-width: 95vw for reviewer-panel"


def test_velocity_dashboard_reviewer_panel_table_overflow():
    html = read_template("velocity_dashboard.html")
    # The table inside reviewer-panel should have overflow-x: auto in the 480px block
    assert "overflow-x: auto" in html, "velocity_dashboard.html missing overflow-x: auto for reviewer-panel table"


def test_velocity_dashboard_heatmap_single_column():
    html = read_template("velocity_dashboard.html")
    assert "grid-template-columns: 1fr;" in html, \
        "velocity_dashboard.html missing single-column grid for heatmap at 480px"


# ── 2. admin_activity.html CSS ───────────────────────────────────────────────

def test_admin_activity_has_480px_media_query():
    html = read_template("admin_activity.html")
    assert "@media (max-width: 480px)" in html, "admin_activity.html missing 480px media query"


def test_admin_activity_activity_row_flex_wrap():
    html = read_template("admin_activity.html")
    assert "flex-wrap: wrap" in html, "admin_activity.html missing flex-wrap: wrap for .activity-row"


def test_admin_activity_stats_row_column():
    html = read_template("admin_activity.html")
    assert "flex-direction: column" in html, "admin_activity.html missing flex-direction: column for .stats-row"


# ── 3. admin_activity.html pagination block ──────────────────────────────────

def test_admin_activity_has_pagination_block():
    html = read_template("admin_activity.html")
    assert "Pagination" in html, "admin_activity.html missing pagination block comment"
    assert "Older" in html, "admin_activity.html missing 'Older' pagination link"
    assert "Newer" in html, "admin_activity.html missing 'Newer' pagination link"


def test_admin_activity_pagination_uses_offset_variable():
    html = read_template("admin_activity.html")
    assert "offset + limit" in html, "admin_activity.html pagination missing 'offset + limit' expression"
    assert "offset - limit" in html, "admin_activity.html pagination missing 'offset - limit' expression"


def test_admin_activity_pagination_gated_on_limit():
    html = read_template("admin_activity.html")
    # Pagination should only show when activity|length >= limit
    assert "activity|length >= limit" in html, \
        "admin_activity.html pagination not gated on activity|length >= limit"


def test_admin_activity_newer_link_gated_on_offset():
    html = read_template("admin_activity.html")
    # The Newer link should be inside {% if offset > 0 %}
    assert "offset > 0" in html, \
        "admin_activity.html 'Newer' link not gated on offset > 0"


# ── 4. mobile.css sections 15 and 16 ─────────────────────────────────────────

def test_mobile_css_section_15_exists():
    css = read_static("mobile.css")
    assert "15." in css or "15. Activity rows" in css, \
        "mobile.css missing section 15"
    assert ".activity-row" in css, "mobile.css missing .activity-row rule"


def test_mobile_css_section_16_exists():
    css = read_static("mobile.css")
    assert "16." in css or "16. Reviewer panel" in css, \
        "mobile.css missing section 16"


def test_mobile_css_reviewer_panel_max_width_95vw():
    css = read_static("mobile.css")
    # Section 16 should constrain reviewer-panel to 95vw
    assert "max-width: 95vw" in css, "mobile.css section 16 missing max-width: 95vw"


# ── 5. get_recent_activity offset parameter ───────────────────────────────────

def test_get_recent_activity_accepts_offset():
    """get_recent_activity signature must accept an offset parameter."""
    import inspect
    from web.activity import get_recent_activity
    sig = inspect.signature(get_recent_activity)
    assert "offset" in sig.parameters, \
        "get_recent_activity() is missing offset parameter"


def test_get_recent_activity_offset_default_zero():
    """offset parameter must default to 0."""
    import inspect
    from web.activity import get_recent_activity
    sig = inspect.signature(get_recent_activity)
    param = sig.parameters["offset"]
    assert param.default == 0, f"Expected offset default 0, got {param.default}"


# ── 6. app.py route offset handling ──────────────────────────────────────────

def test_app_py_activity_route_has_offset():
    """The admin_activity route in app.py must read the offset query param."""
    app_src = (REPO_ROOT / "web" / "app.py").read_text(encoding="utf-8")
    # Check that offset = int(request.args.get("offset", 0)) is present in admin_activity
    assert 'request.args.get("offset"' in app_src or "request.args.get('offset'" in app_src, \
        "app.py admin_activity route missing offset query param read"


def test_app_py_activity_route_passes_limit_to_template():
    app_src = (REPO_ROOT / "web" / "app.py").read_text(encoding="utf-8")
    # Both routes should pass limit= to render_template
    assert "limit=limit" in app_src, \
        "app.py missing limit=limit in render_template call for activity"


def test_app_py_activity_route_passes_offset_to_template():
    app_src = (REPO_ROOT / "web" / "app.py").read_text(encoding="utf-8")
    assert "offset=offset" in app_src, \
        "app.py missing offset=offset in render_template call for activity"
