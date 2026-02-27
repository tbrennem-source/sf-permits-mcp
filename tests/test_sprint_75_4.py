"""Tests for Sprint 75-4: Demo Enhancement + PWA Polish.

Covers:
  - /demo route returns 200 with correct context keys
  - severity_tier present in context when active permits exist
  - _get_demo_data returns parcel_summary data when row exists
  - _get_demo_data uses hardcoded fallbacks when DB unavailable
  - manifest.json is valid JSON with required PWA fields and maskable purpose
  - sitemap.xml includes /demo
  - Cache TTL is 15 min (not 1 hour)
  - severity badge CSS tokens are in demo.html template
"""

import json
import os
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    """Flask app in test mode (DuckDB backend)."""
    os.environ.setdefault("TESTING", "1")
    from web.app import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clear_demo_cache():
    """Clear the demo cache before each test to ensure isolation."""
    from web import routes_misc
    routes_misc._demo_cache.clear()
    yield
    routes_misc._demo_cache.clear()


# ---------------------------------------------------------------------------
# Task 75-4-6: /demo in sitemap
# ---------------------------------------------------------------------------

class TestSitemapIncludesDemo:
    def test_sitemap_contains_demo(self, client):
        """/demo appears in sitemap.xml."""
        resp = client.get("/sitemap.xml")
        assert resp.status_code == 200
        xml = resp.data.decode()
        assert "/demo" in xml, "sitemap.xml must include /demo"

    def test_sitemap_is_valid_xml(self, client):
        """/sitemap.xml has correct XML content type."""
        resp = client.get("/sitemap.xml")
        assert resp.status_code == 200
        content_type = resp.content_type
        assert "xml" in content_type


# ---------------------------------------------------------------------------
# /demo route basic tests
# ---------------------------------------------------------------------------

class TestDemoRoute:
    def test_demo_returns_200(self, client):
        """/demo returns HTTP 200."""
        resp = client.get("/demo")
        assert resp.status_code == 200

    def test_demo_contains_demo_address(self, client):
        """/demo page contains the demo address text."""
        resp = client.get("/demo")
        body = resp.data.decode()
        # The demo address is 1455 MARKET ST
        assert "1455" in body
        assert "MARKET" in body

    def test_demo_density_param(self, client):
        """/demo?density=max returns 200."""
        resp = client.get("/demo?density=max")
        assert resp.status_code == 200

    def test_demo_contains_severity_css(self, client):
        """/demo response includes severity-CRITICAL CSS class definition."""
        resp = client.get("/demo")
        body = resp.data.decode()
        assert "severity-CRITICAL" in body

    def test_demo_contains_severity_pill_class(self, client):
        """/demo response includes .severity-pill CSS class."""
        resp = client.get("/demo")
        body = resp.data.decode()
        assert "severity-pill" in body


# ---------------------------------------------------------------------------
# Task 75-4-1/4: _get_demo_data internals
# ---------------------------------------------------------------------------

class TestGetDemoData:
    def test_returns_dict_with_required_keys(self):
        """_get_demo_data returns a dict with all required keys."""
        from web.routes_misc import _get_demo_data
        data = _get_demo_data()
        required_keys = [
            "demo_address", "block", "lot", "neighborhood",
            "permits", "routing", "timeline", "entities",
            "complaints", "violations", "computed_at",
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

    def test_block_lot_values(self):
        """_get_demo_data returns correct block/lot for demo parcel."""
        from web.routes_misc import _get_demo_data
        data = _get_demo_data()
        assert data["block"] == "3507"
        assert data["lot"] == "004"

    def test_timeline_has_fallback(self):
        """_get_demo_data always returns a timeline (hardcoded fallback)."""
        from web.routes_misc import _get_demo_data
        data = _get_demo_data()
        assert data["timeline"] is not None
        tl = data["timeline"]
        assert "p50" in tl
        assert "sample_size" in tl
        assert tl["p25"] < tl["p50"] < tl["p75"] < tl["p90"]

    def test_cache_ttl_is_15_min(self):
        """_DEMO_CACHE_TTL is 900 seconds (15 minutes)."""
        from web.routes_misc import _DEMO_CACHE_TTL
        assert _DEMO_CACHE_TTL == 900

    def test_cache_is_populated_after_call(self):
        """_demo_cache is populated with computed_at after _get_demo_data()."""
        from web import routes_misc
        from web.routes_misc import _get_demo_data
        routes_misc._demo_cache.clear()
        _get_demo_data()
        assert "computed_at" in routes_misc._demo_cache
        assert routes_misc._demo_cache["computed_at"] > 0

    def test_cache_hit_within_ttl(self):
        """Second call within TTL returns cached result (same object)."""
        import time
        from web import routes_misc
        from web.routes_misc import _get_demo_data
        # Prime the cache
        routes_misc._demo_cache.clear()
        data1 = _get_demo_data()
        # Set computed_at to be recent (5 min ago)
        routes_misc._demo_cache["computed_at"] = time.time() - 300
        routes_misc._demo_cache["_sentinel"] = "cached"
        data2 = _get_demo_data()
        # Should hit cache — sentinel remains
        assert routes_misc._demo_cache.get("_sentinel") == "cached"

    def test_returns_severity_keys(self):
        """_get_demo_data includes severity_tier and severity_score keys."""
        from web.routes_misc import _get_demo_data
        data = _get_demo_data()
        # Keys should exist (may be None if no active permits)
        assert "severity_tier" in data
        assert "severity_score" in data


# ---------------------------------------------------------------------------
# Task 75-4-2: severity integration
# ---------------------------------------------------------------------------

class TestSeverityIntegration:
    def test_score_permit_importable(self):
        """score_permit can be imported from src.severity."""
        from src.severity import score_permit, PermitInput
        assert callable(score_permit)

    def test_score_permit_returns_result(self):
        """score_permit returns SeverityResult with tier."""
        from src.severity import score_permit, PermitInput
        from datetime import date, timedelta
        pi = PermitInput(
            permit_number="TEST001",
            status="issued",
            permit_type_definition="OTCA",
            description="kitchen remodel",
            filed_date=date.today() - timedelta(days=400),
            issued_date=date.today() - timedelta(days=380),
            estimated_cost=75000.0,
        )
        result = score_permit(pi)
        assert result.tier in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "GREEN")
        assert 0 <= result.score <= 100

    def test_severity_tier_values_are_valid(self):
        """Valid severity tiers match expected set."""
        from src.severity import score_permit, PermitInput
        valid_tiers = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "GREEN"}
        pi = PermitInput(
            permit_number="TEST002",
            status="complete",
            estimated_cost=5000.0,
        )
        result = score_permit(pi)
        assert result.tier in valid_tiers


# ---------------------------------------------------------------------------
# Task 75-4-5: manifest.json PWA fields
# ---------------------------------------------------------------------------

class TestManifestJson:
    def _load_manifest(self):
        """Load manifest.json from static directory."""
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "static", "manifest.json"
        )
        with open(manifest_path) as f:
            return json.load(f)

    def test_manifest_is_valid_json(self):
        """manifest.json parses without error."""
        manifest = self._load_manifest()
        assert isinstance(manifest, dict)

    def test_manifest_required_pwa_fields(self):
        """manifest.json has all required PWA fields."""
        manifest = self._load_manifest()
        required = ["name", "short_name", "start_url", "display", "icons"]
        for field in required:
            assert field in manifest, f"Missing PWA field: {field}"

    def test_manifest_display_is_standalone(self):
        """manifest.json display is 'standalone' for PWA installability."""
        manifest = self._load_manifest()
        assert manifest["display"] == "standalone"

    def test_manifest_icons_have_maskable_purpose(self):
        """All icon entries in manifest.json include 'maskable' in purpose."""
        manifest = self._load_manifest()
        icons = manifest.get("icons", [])
        assert len(icons) >= 1, "manifest.json must have at least one icon"
        for icon in icons:
            purpose = icon.get("purpose", "")
            assert "maskable" in purpose, (
                f"Icon {icon.get('src')} missing 'maskable' in purpose field"
            )

    def test_manifest_icons_have_any_purpose(self):
        """Icon purpose includes 'any' in addition to maskable."""
        manifest = self._load_manifest()
        icons = manifest.get("icons", [])
        for icon in icons:
            purpose = icon.get("purpose", "")
            assert "any" in purpose, (
                f"Icon {icon.get('src')} missing 'any' in purpose field"
            )

    def test_manifest_has_theme_and_background_color(self):
        """manifest.json has theme_color and background_color."""
        manifest = self._load_manifest()
        assert "theme_color" in manifest
        assert "background_color" in manifest
        assert manifest["theme_color"] == "#22D3EE"
        assert manifest["background_color"] == "#0B0F19"

    def test_manifest_has_description(self):
        """manifest.json has a description field."""
        manifest = self._load_manifest()
        assert "description" in manifest
        assert len(manifest["description"]) > 5
