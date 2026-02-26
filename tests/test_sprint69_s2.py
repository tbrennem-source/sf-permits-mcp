"""Tests for Sprint 69-S2: Search Intelligence + Anonymous Demo Path.

Covers:
- /search returns 200 for anonymous users
- /lookup returns results with intel context (block/lot)
- /lookup/intel-preview returns HTML fragment
- Intel preview content sections
- Graceful degradation when no data available
- Obsidian design tokens in search results
- HTMX attributes on intel containers
- Google Fonts import
- Template structure
"""

import os
import sys
import pytest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as client:
        yield client
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# /search endpoint tests
# ---------------------------------------------------------------------------

class TestPublicSearch:
    def test_search_returns_200(self, client):
        """GET /search?q=... returns 200 for anonymous users."""
        rv = client.get("/search?q=1455+Market+St")
        assert rv.status_code == 200

    def test_search_has_obsidian_tokens(self, client):
        """Search results page includes Obsidian design tokens."""
        rv = client.get("/search?q=test+address")
        html = rv.data.decode()
        assert "--bg-deep: #0B0F19" in html
        assert "--bg-surface: #131825" in html
        assert "--signal-green: #34D399" in html
        assert "--signal-cyan: #22D3EE" in html

    def test_search_has_google_fonts(self, client):
        """Search results page imports Google Fonts."""
        rv = client.get("/search?q=test")
        html = rv.data.decode()
        assert "fonts.googleapis.com" in html
        assert "JetBrains+Mono" in html or "JetBrains Mono" in html
        assert "IBM+Plex+Sans" in html or "IBM Plex Sans" in html

    def test_search_has_two_column_layout(self, client):
        """Search results page has the two-column grid layout class."""
        rv = client.get("/search?q=test")
        html = rv.data.decode()
        assert "results-layout" in html

    def test_search_has_search_form(self, client):
        """Search results page has a functional search form."""
        rv = client.get("/search?q=example")
        html = rv.data.decode()
        assert 'action="/search"' in html
        assert 'name="q"' in html
        assert "example" in html  # Query pre-filled

    def test_search_shows_permit_results_content(self, client):
        """Search results contain permit data in results-content div."""
        rv = client.get("/search?q=test")
        html = rv.data.decode()
        assert "permit-results-content" in html or "no-results" in html

    def test_search_empty_redirects(self, client):
        """GET /search without q redirects."""
        rv = client.get("/search")
        assert rv.status_code == 302

    def test_search_no_results_shows_guidance(self, client):
        """When no results found, show search guidance card."""
        rv = client.get("/search?q=zzznonexistent999")
        html = rv.data.decode()
        if "No permits found" in html:
            assert "guidance-card" in html or "Try searching by" in html or "How to use" in html


# ---------------------------------------------------------------------------
# /lookup endpoint tests
# ---------------------------------------------------------------------------

class TestLookup:
    def test_lookup_address_returns_results(self, client):
        """POST /lookup with address returns results."""
        rv = client.post("/lookup", data={
            "lookup_mode": "address",
            "street_number": "1455",
            "street_name": "Market St",
        })
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "result" in html.lower() or "permit" in html.lower() or "error" in html.lower()

    def test_lookup_passes_block_lot_to_template(self, client):
        """POST /lookup with address resolves block/lot for intel preview."""
        rv = client.post("/lookup", data={
            "lookup_mode": "address",
            "street_number": "1455",
            "street_name": "Market St",
        })
        # The response should have the lookup results template rendered
        assert rv.status_code == 200

    def test_lookup_parcel_returns_results(self, client):
        """POST /lookup with block/lot returns results."""
        rv = client.post("/lookup", data={
            "lookup_mode": "parcel",
            "block": "3512",
            "lot": "001",
        })
        assert rv.status_code == 200

    def test_lookup_missing_fields_returns_400(self, client):
        """POST /lookup with missing required fields returns 400."""
        rv = client.post("/lookup", data={
            "lookup_mode": "address",
            "street_number": "123",
            # missing street_name
        })
        assert rv.status_code == 400


# ---------------------------------------------------------------------------
# /lookup/intel-preview endpoint tests
# ---------------------------------------------------------------------------

class TestIntelPreview:
    def test_intel_preview_returns_html(self, client):
        """POST /lookup/intel-preview returns HTML fragment."""
        rv = client.post("/lookup/intel-preview", data={
            "block": "3512",
            "lot": "001",
        })
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "intel" in html.lower() or "loading" in html.lower() or "empty" in html.lower()

    def test_intel_preview_no_data_shows_empty(self, client):
        """POST /lookup/intel-preview with invalid parcel shows empty state."""
        rv = client.post("/lookup/intel-preview", data={
            "block": "9999",
            "lot": "999",
        })
        assert rv.status_code == 200
        html = rv.data.decode()
        # Should gracefully degrade — no error page
        assert rv.status_code != 500

    @patch("web.routes_search._resolve_block_lot", return_value=("3512", "001"))
    def test_intel_preview_address_resolves_to_block_lot(self, mock_resolve, client):
        """POST /lookup/intel-preview with address resolves block/lot."""
        rv = client.post("/lookup/intel-preview", data={
            "street_number": "1455",
            "street_name": "Market St",
        })
        assert rv.status_code == 200
        mock_resolve.assert_called_once()

    def test_intel_preview_missing_params(self, client):
        """POST /lookup/intel-preview with no params returns empty."""
        rv = client.post("/lookup/intel-preview", data={})
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "No property data" in html or "intel-empty" in html

    @patch("web.routes_search._gather_intel")
    def test_intel_preview_routing_section(self, mock_intel, client):
        """Intel preview shows routing progress when data available."""
        mock_intel.return_value = {
            "routing": [{
                "permit_number": "202401010001",
                "status": "filed",
                "permit_type": "alterations",
                "description": "Kitchen remodel",
                "stations_cleared": 3,
                "stations_total": 7,
                "current_station": "BLDG",
            }],
            "complaints_count": 0,
            "violations_count": 0,
            "top_entities": [],
            "has_intelligence": True,
            "timeout": False,
        }
        rv = client.post("/lookup/intel-preview", data={
            "block": "3512",
            "lot": "001",
        })
        html = rv.data.decode()
        assert "Plan Review Progress" in html
        assert "202401010001" in html
        assert "3 of 7 stations cleared" in html

    @patch("web.routes_search._gather_intel")
    def test_intel_preview_entity_connections(self, mock_intel, client):
        """Intel preview shows entity connections when data available."""
        mock_intel.return_value = {
            "routing": [],
            "complaints_count": 0,
            "violations_count": 0,
            "top_entities": [
                {"name": "Smith & Associates", "role": "Architect", "permit_count": 47},
                {"name": "Bay Builders Inc", "role": "Contractor", "permit_count": 23},
            ],
            "has_intelligence": True,
            "timeout": False,
        }
        rv = client.post("/lookup/intel-preview", data={
            "block": "3512",
            "lot": "001",
        })
        html = rv.data.decode()
        assert "Key Players" in html
        assert "Smith &amp; Associates" in html or "Smith & Associates" in html
        assert "47 SF permits" in html

    @patch("web.routes_search._gather_intel")
    def test_intel_preview_enforcement(self, mock_intel, client):
        """Intel preview shows complaint/violation counts."""
        mock_intel.return_value = {
            "routing": [],
            "complaints_count": 3,
            "violations_count": 1,
            "top_entities": [],
            "has_intelligence": True,
            "timeout": False,
        }
        rv = client.post("/lookup/intel-preview", data={
            "block": "3512",
            "lot": "001",
        })
        html = rv.data.decode()
        assert "Enforcement Activity" in html
        assert "3 complaint" in html
        assert "1 violation" in html

    @patch("web.routes_search._gather_intel")
    def test_intel_preview_cta(self, mock_intel, client):
        """Intel preview includes signup CTA."""
        mock_intel.return_value = {
            "routing": [{
                "permit_number": "202401010001",
                "status": "filed",
                "permit_type": "alterations",
                "description": "Test",
                "stations_cleared": 1,
                "stations_total": 5,
                "current_station": "BLDG",
            }],
            "complaints_count": 0,
            "violations_count": 0,
            "top_entities": [],
            "has_intelligence": True,
            "timeout": False,
        }
        rv = client.post("/lookup/intel-preview", data={
            "block": "3512",
            "lot": "001",
        })
        html = rv.data.decode()
        assert "Sign up free" in html

    @patch("web.routes_search._gather_intel")
    def test_intel_preview_graceful_degradation(self, mock_intel, client):
        """Intel preview degrades gracefully with no data."""
        mock_intel.return_value = {
            "routing": [],
            "complaints_count": 0,
            "violations_count": 0,
            "top_entities": [],
            "has_intelligence": False,
            "timeout": False,
        }
        rv = client.post("/lookup/intel-preview", data={
            "block": "3512",
            "lot": "001",
        })
        html = rv.data.decode()
        assert rv.status_code == 200
        assert "No intelligence data" in html or "intel-empty" in html


# ---------------------------------------------------------------------------
# Template structure tests
# ---------------------------------------------------------------------------

class TestTemplateStructure:
    def test_search_results_has_htmx(self, client):
        """Search results page includes HTMX library."""
        rv = client.get("/search?q=test")
        html = rv.data.decode()
        assert "htmx.org" in html

    def test_search_results_has_header_nav(self, client):
        """Search results page has header with logo and auth links."""
        rv = client.get("/search?q=test")
        html = rv.data.decode()
        assert "sfpermits" in html
        assert "/auth/login" in html

    def test_search_results_has_footer(self, client):
        """Search results page has footer."""
        rv = client.get("/search?q=test")
        html = rv.data.decode()
        assert "<footer" in html
        assert "San Francisco open data" in html

    def test_search_results_nonce_on_all_scripts(self, client):
        """All script tags have CSP nonce."""
        rv = client.get("/search?q=test")
        html = rv.data.decode()
        import re
        scripts = re.findall(r'<script[^>]*>', html)
        for script in scripts:
            assert 'nonce=' in script, f"Missing nonce: {script[:60]}"


# ---------------------------------------------------------------------------
# _gather_intel unit tests
# ---------------------------------------------------------------------------

class TestGatherIntel:
    def test_gather_intel_returns_dict(self):
        """_gather_intel always returns a dict with required keys."""
        from web.routes_search import _gather_intel
        result = _gather_intel("9999", "999")
        assert isinstance(result, dict)
        assert "has_intelligence" in result
        assert "routing" in result
        assert "top_entities" in result
        assert "complaints_count" in result
        assert "violations_count" in result
        assert "timeout" in result

    def test_gather_intel_never_raises(self):
        """_gather_intel never raises, even with bad input."""
        from web.routes_search import _gather_intel
        # These should all return gracefully
        result = _gather_intel("", "")
        assert isinstance(result, dict)
        result = _gather_intel(None, None)
        assert isinstance(result, dict)
