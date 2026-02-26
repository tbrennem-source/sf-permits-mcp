"""Tests for Sprint 69 Session 1: Design System + Landing Page + /api/stats."""

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_s69.duckdb")
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
# Design System CSS
# ---------------------------------------------------------------------------

class TestDesignSystem:
    """Tests for design-system.css loading and content."""

    def test_design_system_css_serves_200(self, client):
        """design-system.css returns 200."""
        resp = client.get("/static/design-system.css")
        assert resp.status_code == 200

    def test_design_system_css_contains_tokens(self, client):
        """design-system.css contains Obsidian token definitions."""
        resp = client.get("/static/design-system.css")
        text = resp.data.decode()
        assert "--bg-deep:" in text
        assert "--signal-cyan:" in text
        assert "--font-display:" in text

    def test_design_system_css_contains_glass_card(self, client):
        """design-system.css defines the .glass-card component."""
        resp = client.get("/static/design-system.css")
        text = resp.data.decode()
        assert ".glass-card" in text

    def test_design_system_css_contains_obsidian_btn(self, client):
        """design-system.css defines button component classes."""
        resp = client.get("/static/design-system.css")
        text = resp.data.decode()
        assert ".obsidian-btn-primary" in text
        assert ".obsidian-btn-outline" in text

    def test_design_system_css_contains_obsidian_input(self, client):
        """design-system.css defines .obsidian-input."""
        resp = client.get("/static/design-system.css")
        text = resp.data.decode()
        assert ".obsidian-input" in text

    def test_design_system_css_contains_stat_block(self, client):
        """design-system.css defines .stat-block."""
        resp = client.get("/static/design-system.css")
        text = resp.data.decode()
        assert ".stat-block" in text

    def test_design_system_css_contains_google_fonts(self, client):
        """design-system.css imports Google Fonts."""
        resp = client.get("/static/design-system.css")
        text = resp.data.decode()
        assert "fonts.googleapis.com" in text
        assert "JetBrains+Mono" in text
        assert "IBM+Plex+Sans" in text

    def test_design_system_css_scoped_to_obsidian(self, client):
        """Component classes are scoped under body.obsidian."""
        resp = client.get("/static/design-system.css")
        text = resp.data.decode()
        assert "body.obsidian .glass-card" in text

    def test_design_system_css_contains_print_styles(self, client):
        """design-system.css includes print media query."""
        resp = client.get("/static/design-system.css")
        text = resp.data.decode()
        assert "@media print" in text

    def test_design_system_css_status_dots(self, client):
        """design-system.css defines status dot variants."""
        resp = client.get("/static/design-system.css")
        text = resp.data.decode()
        assert ".status-success" in text
        assert ".status-warning" in text
        assert ".status-danger" in text


# ---------------------------------------------------------------------------
# Landing Page
# ---------------------------------------------------------------------------

class TestLandingPage:
    """Tests for the rewritten landing page."""

    def test_landing_page_renders_200(self, client):
        """Anonymous GET / returns 200."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_landing_page_has_obsidian_body_class(self, client):
        """Landing page uses body class='obsidian'."""
        resp = client.get("/")
        text = resp.data.decode()
        assert 'class="obsidian"' in text

    def test_landing_page_has_search_form(self, client):
        """Landing page contains a search form pointing to /search."""
        resp = client.get("/")
        text = resp.data.decode()
        assert 'action="/search"' in text
        assert 'name="q"' in text

    def test_landing_page_has_glass_card_class(self, client):
        """Landing page uses .glass-card from design system."""
        resp = client.get("/")
        text = resp.data.decode()
        assert "glass-card" in text

    def test_landing_page_has_google_fonts_link(self, client):
        """Landing page includes Google Fonts (via design-system.css import)."""
        resp = client.get("/")
        text = resp.data.decode()
        assert "design-system.css" in text

    def test_landing_page_has_viewport_meta(self, client):
        """Landing page includes mobile viewport meta tag."""
        resp = client.get("/")
        text = resp.data.decode()
        assert 'name="viewport"' in text

    def test_landing_page_has_stats_numbers(self, client):
        """Landing page contains stat numbers (fallback values in HTML)."""
        resp = client.get("/")
        text = resp.data.decode()
        assert "1,137,816" in text or "1.1M" in text

    def test_landing_page_has_capability_cards(self, client):
        """Landing page has at least 4 capability cards."""
        resp = client.get("/")
        text = resp.data.decode()
        assert text.count("capability-card") >= 4

    def test_landing_page_has_data_pulse(self, client):
        """Landing page has the Live Data Pulse panel."""
        resp = client.get("/")
        text = resp.data.decode()
        assert "data-pulse" in text
        assert "Live Data Pulse" in text

    def test_landing_page_has_homeowner_funnel(self, client):
        """Landing page has the homeowner funnel section."""
        resp = client.get("/")
        text = resp.data.decode()
        assert "Planning a project?" in text
        assert "Notice of Violation" in text

    def test_landing_page_has_credibility_section(self, client):
        """Landing page has the credibility footer."""
        resp = client.get("/")
        text = resp.data.decode()
        assert "22 SF government data sources" in text
        assert "automated tests" in text

    def test_landing_page_has_cta(self, client):
        """Landing page has CTA section."""
        resp = client.get("/")
        text = resp.data.decode()
        assert "Get more from your permit data" in text
        assert "Create free account" in text

    def test_landing_page_has_system_status_link(self, client):
        """Landing page footer links to /health."""
        resp = client.get("/")
        text = resp.data.decode()
        assert '/health' in text
        assert "System status" in text


# ---------------------------------------------------------------------------
# /api/stats
# ---------------------------------------------------------------------------

class TestApiStats:
    """Tests for the /api/stats endpoint."""

    def test_api_stats_returns_json(self, client):
        """/api/stats returns JSON with expected keys."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "permits" in data
        assert "routing_records" in data
        assert "entities" in data
        assert "inspections" in data

    def test_api_stats_permits_is_number(self, client):
        """permits value is an integer."""
        resp = client.get("/api/stats")
        data = resp.get_json()
        assert isinstance(data["permits"], int)

    def test_api_stats_caching(self, client):
        """Second call uses cached data (same results)."""
        resp1 = client.get("/api/stats")
        data1 = resp1.get_json()
        resp2 = client.get("/api/stats")
        data2 = resp2.get_json()
        assert data1["permits"] == data2["permits"]
        assert data1["entities"] == data2["entities"]

    def test_api_stats_no_auth_required(self, client):
        """/api/stats is accessible without auth."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200

    def test_api_stats_has_today_changes(self, client):
        """Response includes today_changes field."""
        resp = client.get("/api/stats")
        data = resp.get_json()
        assert "today_changes" in data

    def test_api_stats_has_last_refresh(self, client):
        """Response includes last_refresh field."""
        resp = client.get("/api/stats")
        data = resp.get_json()
        assert "last_refresh" in data


# ---------------------------------------------------------------------------
# Existing Pages Not Broken
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    """Verify design system doesn't break existing pages."""

    def test_style_css_still_loads(self, client):
        """style.css returns 200."""
        resp = client.get("/static/style.css")
        assert resp.status_code == 200

    def test_mobile_css_still_loads(self, client):
        """mobile.css returns 200."""
        resp = client.get("/static/mobile.css")
        assert resp.status_code == 200

    def test_style_css_has_import(self, client):
        """style.css includes @import for design-system.css."""
        resp = client.get("/static/style.css")
        text = resp.data.decode()
        assert "design-system.css" in text

    def test_health_endpoint_still_works(self, client):
        """/health endpoint still returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200
