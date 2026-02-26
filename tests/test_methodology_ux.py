"""Tests for Sprint 57D: Methodology cards in web templates.

Validates that /analyze route passes methodology dicts to templates
and that the HTML output contains methodology card markup.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def client():
    """Flask test client."""
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("DATABASE_URL", "")
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def mock_tools():
    """Mock all 5 tool functions to return structured results."""
    # Each tool with return_structured=True returns (str, dict)
    predict_meta = {
        "tool": "predict_permits",
        "headline": "Form 3/8 — in_house",
        "formula_steps": ["Form: Form 3/8 (Alterations)", "Review Path: in_house"],
        "data_sources": ["SF permit decision tree"],
        "sample_size": 0,
        "data_freshness": "2026-02-25",
        "confidence": "medium",
        "coverage_gaps": ["Zoning-specific routing unavailable"],
    }
    fees_meta = {
        "tool": "estimate_fees",
        "headline": "$4,847",
        "formula_steps": ["Plan Review Fee: $2,156.50", "Permit Issuance Fee: $2,690.50"],
        "data_sources": ["DBI Table 1A-A fee schedule", "1.1M permit records"],
        "sample_size": 127,
        "data_freshness": "2026-02-25",
        "confidence": "high",
        "coverage_gaps": ["Planning fees not included"],
    }
    timeline_meta = {
        "tool": "estimate_timeline",
        "headline": "45 days typical",
        "formula_steps": ["p50 (typical): 45 days"],
        "data_sources": ["1.1M+ historical permits"],
        "sample_size": 500,
        "data_freshness": "2026-02-25",
        "confidence": "high",
        "coverage_gaps": [],
    }
    docs_meta = {
        "tool": "required_documents",
        "headline": "12 documents required",
        "formula_steps": ["Base documents: 6", "Agency documents: 3", "Project-specific: 3"],
        "data_sources": ["DBI completeness checklist"],
        "sample_size": 0,
        "data_freshness": "2026-02-25",
        "confidence": "high",
        "coverage_gaps": ["Based on standard DBI requirements"],
    }
    risk_meta = {
        "tool": "revision_risk",
        "headline": "MODERATE risk",
        "formula_steps": ["Revision rate: 15.0%"],
        "data_sources": ["1.1M+ historical permits"],
        "sample_size": 1000,
        "data_freshness": "2026-02-25",
        "confidence": "high",
        "coverage_gaps": ["Based on cost revision proxy"],
    }

    async def mock_predict(**kw):
        return ("# Permit Prediction\n**Project:** test\n**Detected Project Types:** general_alteration", predict_meta)

    async def mock_fees(**kw):
        return ("# Fee Estimate\n**Total DBI Fees** $4,847", fees_meta)

    async def mock_timeline(**kw):
        return ("# Timeline Estimate\n**Typical:** 45 days", timeline_meta)

    async def mock_docs(**kw):
        return ("# Required Documents Checklist\n1. Form 3/8", docs_meta)

    async def mock_risk(**kw):
        return ("# Revision Risk Assessment\n**Risk Level:** MODERATE", risk_meta)

    with patch("web.app.predict_permits", side_effect=mock_predict), \
         patch("web.app.estimate_fees", side_effect=mock_fees), \
         patch("web.app.estimate_timeline", side_effect=mock_timeline), \
         patch("web.app.required_documents", side_effect=mock_docs), \
         patch("web.app.revision_risk", side_effect=mock_risk), \
         patch("web.app.generate_team_profile", return_value=""), \
         patch("web.app.extract_triggers", return_value=[]), \
         patch("web.app.enhance_description", side_effect=lambda d, *a, **kw: d), \
         patch("web.app.reorder_sections", return_value=None):
        yield {
            "predict": predict_meta,
            "fees": fees_meta,
            "timeline": timeline_meta,
            "docs": docs_meta,
            "risk": risk_meta,
        }


# ===========================================================================
# Tests
# ===========================================================================

class TestAnalyzeRouteMethodology:
    """POST /analyze returns methodology cards in HTML."""

    def test_analyze_returns_200(self, client, mock_tools):
        resp = client.post("/analyze", data={
            "description": "Kitchen remodel",
            "cost": "50000",
        })
        assert resp.status_code == 200

    def test_methodology_card_present(self, client, mock_tools):
        resp = client.post("/analyze", data={
            "description": "Kitchen remodel",
            "cost": "50000",
        })
        html = resp.data.decode()
        assert 'class="methodology-card"' in html

    def test_methodology_card_for_each_tool(self, client, mock_tools):
        resp = client.post("/analyze", data={
            "description": "Kitchen remodel",
            "cost": "50000",
        })
        html = resp.data.decode()
        # Should have multiple methodology cards (one per tool)
        assert html.count('class="methodology-card"') >= 3

    def test_methodology_card_has_details_tag(self, client, mock_tools):
        resp = client.post("/analyze", data={
            "description": "Kitchen remodel",
            "cost": "50000",
        })
        html = resp.data.decode()
        assert "<details" in html
        assert "How we calculated this" in html

    def test_methodology_card_contains_data_sources(self, client, mock_tools):
        resp = client.post("/analyze", data={
            "description": "Kitchen remodel",
            "cost": "50000",
        })
        html = resp.data.decode()
        assert "methodology-sources" in html
        # At least one data source should appear
        assert "DBI Table 1A-A" in html or "permit decision tree" in html or "historical permits" in html

    def test_methodology_card_shows_coverage_gaps(self, client, mock_tools):
        resp = client.post("/analyze", data={
            "description": "Kitchen remodel",
            "cost": "50000",
        })
        html = resp.data.decode()
        assert "methodology-gaps" in html
        assert "Planning fees not included" in html

    def test_methodology_cards_default_collapsed(self, client, mock_tools):
        resp = client.post("/analyze", data={
            "description": "Kitchen remodel",
            "cost": "50000",
        })
        html = resp.data.decode()
        # Cards should be collapsed by default (no 'open' attribute on <details>)
        assert '<details class="methodology-card" open' not in html

    def test_methodology_card_has_formula_steps(self, client, mock_tools):
        resp = client.post("/analyze", data={
            "description": "Kitchen remodel",
            "cost": "50000",
        })
        html = resp.data.decode()
        # Fee formula steps should appear
        assert "Plan Review Fee" in html or "Form 3/8" in html

    def test_methodology_style_block_present(self, client, mock_tools):
        resp = client.post("/analyze", data={
            "description": "Kitchen remodel",
            "cost": "50000",
        })
        html = resp.data.decode()
        assert ".methodology-card" in html
        assert ".methodology-sources" in html
        assert ".methodology-gaps" in html


class TestAnalyzeWithoutCost:
    """When no cost provided, fees tool is skipped but others still have methodology."""

    def test_no_cost_still_has_methodology(self, client, mock_tools):
        resp = client.post("/analyze", data={
            "description": "Bathroom renovation",
        })
        assert resp.status_code == 200
        html = resp.data.decode()
        # At minimum predict should have a methodology card
        assert 'class="methodology-card"' in html


class TestSharedAnalysisMethodology:
    """analysis_shared.html template includes methodology card styles."""

    def test_shared_template_has_methodology_styles(self):
        """Check that analysis_shared.html has methodology card CSS."""
        import os
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "templates", "analysis_shared.html"
        )
        with open(template_path) as f:
            content = f.read()
        assert ".methodology-card" in content
        assert ".methodology-sources" in content
        assert ".methodology-gaps" in content

    def test_shared_template_has_methodology_card_markup(self):
        """Check that analysis_shared.html renders methodology cards."""
        import os
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "templates", "analysis_shared.html"
        )
        with open(template_path) as f:
            content = f.read()
        assert 'class="methodology-card"' in content
        assert "How we calculated this" in content
