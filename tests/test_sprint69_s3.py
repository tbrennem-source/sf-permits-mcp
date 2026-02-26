"""Tests for Sprint 69 Session 3: Methodology + About the Data + Demo pages."""

import re

import pytest


@pytest.fixture
def client():
    """Create a Flask test client."""
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# /methodology
# ---------------------------------------------------------------------------

class TestMethodology:
    def test_methodology_returns_200(self, client):
        resp = client.get("/methodology")
        assert resp.status_code == 200

    def test_methodology_has_entity_resolution_section(self, client):
        resp = client.get("/methodology")
        html = resp.data.decode()
        assert "Entity Resolution" in html

    def test_methodology_has_timeline_estimation_section(self, client):
        resp = client.get("/methodology")
        html = resp.data.decode()
        assert "Timeline Estimation" in html

    def test_methodology_has_fee_estimation_section(self, client):
        resp = client.get("/methodology")
        html = resp.data.decode()
        assert "Fee Estimation" in html

    def test_methodology_has_data_provenance_table(self, client):
        resp = client.get("/methodology")
        html = resp.data.decode()
        assert "Data Provenance" in html
        # Should contain at least a few data source entries
        assert "Building Permits" in html
        assert "Building Inspections" in html
        assert "Plan Review Routing" in html

    def test_methodology_has_substantial_content(self, client):
        """Page must have >2000 words of real content."""
        resp = client.get("/methodology")
        html = resp.data.decode()
        # Strip HTML tags to get text content
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        words = text.split()
        assert len(words) > 2000, f"Only {len(words)} words (need >2000)"

    def test_methodology_has_obsidian_design_tokens(self, client):
        resp = client.get("/methodology")
        html = resp.data.decode()
        assert "--bg-deep" in html
        assert "--signal-cyan" in html
        assert "--font-display" in html

    def test_methodology_has_google_fonts(self, client):
        resp = client.get("/methodology")
        html = resp.data.decode()
        assert "fonts.googleapis.com" in html
        assert "JetBrains+Mono" in html or "JetBrains Mono" in html
        assert "IBM+Plex+Sans" in html or "IBM Plex Sans" in html

    def test_methodology_has_ai_plan_analysis_section(self, client):
        resp = client.get("/methodology")
        html = resp.data.decode()
        assert "AI Plan Analysis" in html

    def test_methodology_has_revision_risk_section(self, client):
        resp = client.get("/methodology")
        html = resp.data.decode()
        assert "Revision Risk" in html

    def test_methodology_has_limitations_section(self, client):
        resp = client.get("/methodology")
        html = resp.data.decode()
        assert "Limitations" in html


# ---------------------------------------------------------------------------
# /about-data
# ---------------------------------------------------------------------------

class TestAboutData:
    def test_about_data_returns_200(self, client):
        resp = client.get("/about-data")
        assert resp.status_code == 200

    def test_about_data_has_data_inventory_table(self, client):
        resp = client.get("/about-data")
        html = resp.data.decode()
        assert "Data Inventory" in html
        assert "Building Permits" in html

    def test_about_data_mentions_nightly_pipeline(self, client):
        resp = client.get("/about-data")
        html = resp.data.decode()
        assert "Nightly Pipeline" in html or "Pipeline" in html

    def test_about_data_has_knowledge_base_section(self, client):
        resp = client.get("/about-data")
        html = resp.data.decode()
        assert "Knowledge Base" in html
        assert "Tier 1" in html

    def test_about_data_has_quality_assurance_section(self, client):
        resp = client.get("/about-data")
        html = resp.data.decode()
        assert "Quality Assurance" in html

    def test_about_data_has_obsidian_design_tokens(self, client):
        resp = client.get("/about-data")
        html = resp.data.decode()
        assert "--bg-deep" in html
        assert "--signal-cyan" in html

    def test_about_data_has_google_fonts(self, client):
        resp = client.get("/about-data")
        html = resp.data.decode()
        assert "fonts.googleapis.com" in html


# ---------------------------------------------------------------------------
# /demo
# ---------------------------------------------------------------------------

class TestDemo:
    def test_demo_returns_200(self, client):
        resp = client.get("/demo")
        assert resp.status_code == 200

    def test_demo_has_noindex_meta_tag(self, client):
        resp = client.get("/demo")
        html = resp.data.decode()
        assert 'name="robots" content="noindex"' in html

    def test_demo_contains_permit_data(self, client):
        resp = client.get("/demo")
        html = resp.data.decode()
        # Should have the demo address and at least the template structure
        assert "Property Intelligence" in html
        assert "Permit History" in html

    def test_demo_has_annotation_callouts(self, client):
        resp = client.get("/demo")
        html = resp.data.decode()
        assert "callout" in html
        assert "SODA API" in html or "routing data" in html or "entity resolution" in html

    def test_demo_has_obsidian_design_tokens(self, client):
        resp = client.get("/demo")
        html = resp.data.decode()
        assert "--bg-deep" in html
        assert "--signal-cyan" in html

    def test_demo_has_google_fonts(self, client):
        resp = client.get("/demo")
        html = resp.data.decode()
        assert "fonts.googleapis.com" in html

    def test_demo_density_param(self, client):
        resp = client.get("/demo?density=max")
        assert resp.status_code == 200

    def test_demo_has_routing_section(self, client):
        resp = client.get("/demo")
        html = resp.data.decode()
        assert "Routing Progress" in html

    def test_demo_has_timeline_section(self, client):
        resp = client.get("/demo")
        html = resp.data.decode()
        assert "Timeline Estimate" in html

    def test_demo_has_entity_section(self, client):
        resp = client.get("/demo")
        html = resp.data.decode()
        assert "Connected Entities" in html


# ---------------------------------------------------------------------------
# Sitemap update
# ---------------------------------------------------------------------------

class TestSitemap:
    def test_sitemap_includes_methodology(self, client):
        resp = client.get("/sitemap.xml")
        assert resp.status_code == 200
        assert "/methodology" in resp.data.decode()

    def test_sitemap_includes_about_data(self, client):
        resp = client.get("/sitemap.xml")
        assert "/about-data" in resp.data.decode()

    def test_sitemap_does_not_include_demo(self, client):
        resp = client.get("/sitemap.xml")
        assert "/demo" not in resp.data.decode()
