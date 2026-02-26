"""Tests for Sprint 57 methodology metadata — dual return pattern, coverage disclaimers, revision probability.

Covers all 5 tools:
- estimate_fees (+ revision probability)
- estimate_timeline
- predict_permits
- required_documents
- revision_risk
"""

import asyncio
from unittest.mock import patch, MagicMock

import pytest


def run(coro):
    """Helper to run async tool functions synchronously in tests."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_db():
    """Mock database connections for all tests."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    with patch("src.tools.estimate_fees.get_connection", return_value=mock_conn), \
         patch("src.tools.estimate_timeline.get_connection", return_value=mock_conn), \
         patch("src.tools.revision_risk.get_connection", return_value=mock_conn), \
         patch("src.tools.estimate_fees.BACKEND", "duckdb"), \
         patch("src.tools.estimate_timeline.BACKEND", "duckdb"), \
         patch("src.tools.revision_risk.BACKEND", "duckdb"):
        yield mock_conn


# ===========================================================================
# 1. return_structured=False returns str (one per tool)
# ===========================================================================

class TestReturnString:
    """Default return_structured=False returns a plain string."""

    def test_estimate_fees_returns_str(self):
        from src.tools.estimate_fees import estimate_fees
        result = run(estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=50000,
        ))
        assert isinstance(result, str)
        assert "Fee Estimate" in result

    def test_estimate_timeline_returns_str(self):
        from src.tools.estimate_timeline import estimate_timeline
        result = run(estimate_timeline(permit_type="alterations"))
        assert isinstance(result, str)
        assert "Timeline" in result

    def test_predict_permits_returns_str(self):
        from src.tools.predict_permits import predict_permits
        result = run(predict_permits(
            project_description="Kitchen remodel in existing single-family home",
        ))
        assert isinstance(result, str)
        assert "Permit Prediction" in result

    def test_required_documents_returns_str(self):
        from src.tools.required_documents import required_documents
        result = run(required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
        ))
        assert isinstance(result, str)
        assert "Required Documents" in result

    def test_revision_risk_returns_str(self):
        from src.tools.revision_risk import revision_risk
        result = run(revision_risk(permit_type="alterations"))
        assert isinstance(result, str)
        assert "Revision Risk" in result


# ===========================================================================
# 2. return_structured=True returns (str, dict) tuple
# ===========================================================================

class TestReturnTuple:
    """return_structured=True returns (markdown_str, methodology_dict)."""

    def test_estimate_fees_returns_tuple(self):
        from src.tools.estimate_fees import estimate_fees
        result = run(estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=50000,
            return_structured=True,
        ))
        assert isinstance(result, tuple)
        assert len(result) == 2
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)

    def test_estimate_timeline_returns_tuple(self):
        from src.tools.estimate_timeline import estimate_timeline
        result = run(estimate_timeline(
            permit_type="alterations",
            return_structured=True,
        ))
        assert isinstance(result, tuple)
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)

    def test_predict_permits_returns_tuple(self):
        from src.tools.predict_permits import predict_permits
        result = run(predict_permits(
            project_description="Restaurant buildout in commercial space",
            return_structured=True,
        ))
        assert isinstance(result, tuple)
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)

    def test_required_documents_returns_tuple(self):
        from src.tools.required_documents import required_documents
        result = run(required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            return_structured=True,
        ))
        assert isinstance(result, tuple)
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)

    def test_revision_risk_returns_tuple(self):
        from src.tools.revision_risk import revision_risk
        result = run(revision_risk(
            permit_type="alterations",
            return_structured=True,
        ))
        assert isinstance(result, tuple)
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)


# ===========================================================================
# 3. Methodology dict has required keys
# ===========================================================================

REQUIRED_KEYS = {"tool", "headline", "formula_steps", "data_sources",
                 "sample_size", "data_freshness", "confidence", "coverage_gaps"}


class TestMethodologyDictKeys:
    """Methodology dict has all required keys."""

    def test_estimate_fees_has_required_keys(self):
        from src.tools.estimate_fees import estimate_fees
        _, meta = run(estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=75000,
            return_structured=True,
        ))
        assert REQUIRED_KEYS.issubset(meta.keys()), f"Missing keys: {REQUIRED_KEYS - meta.keys()}"
        assert meta["tool"] == "estimate_fees"

    def test_estimate_timeline_has_required_keys(self):
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = run(estimate_timeline(
            permit_type="alterations",
            return_structured=True,
        ))
        assert REQUIRED_KEYS.issubset(meta.keys())
        assert meta["tool"] == "estimate_timeline"

    def test_predict_permits_has_required_keys(self):
        from src.tools.predict_permits import predict_permits
        _, meta = run(predict_permits(
            project_description="ADU construction in backyard",
            return_structured=True,
        ))
        assert REQUIRED_KEYS.issubset(meta.keys())
        assert meta["tool"] == "predict_permits"

    def test_required_documents_has_required_keys(self):
        from src.tools.required_documents import required_documents
        _, meta = run(required_documents(
            permit_forms=["Form 3/8"],
            review_path="otc",
            return_structured=True,
        ))
        assert REQUIRED_KEYS.issubset(meta.keys())
        assert meta["tool"] == "required_documents"

    def test_revision_risk_has_required_keys(self):
        from src.tools.revision_risk import revision_risk
        _, meta = run(revision_risk(
            permit_type="new_construction",
            return_structured=True,
        ))
        assert REQUIRED_KEYS.issubset(meta.keys())
        assert meta["tool"] == "revision_risk"


# ===========================================================================
# 4. Coverage gaps populated
# ===========================================================================

class TestCoverageGaps:
    """coverage_gaps field is populated in methodology dict."""

    def test_estimate_fees_has_coverage_gaps(self):
        from src.tools.estimate_fees import estimate_fees
        _, meta = run(estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=50000,
            return_structured=True,
        ))
        assert isinstance(meta["coverage_gaps"], list)
        assert len(meta["coverage_gaps"]) > 0
        assert any("Planning fees" in g for g in meta["coverage_gaps"])

    def test_estimate_timeline_coverage_gaps_when_no_db(self):
        from src.tools.estimate_timeline import estimate_timeline
        # DB returns no data → should note limited data
        _, meta = run(estimate_timeline(
            permit_type="alterations",
            return_structured=True,
        ))
        assert isinstance(meta["coverage_gaps"], list)

    def test_predict_permits_coverage_gaps_no_address(self):
        from src.tools.predict_permits import predict_permits
        _, meta = run(predict_permits(
            project_description="General renovation",
            return_structured=True,
        ))
        assert isinstance(meta["coverage_gaps"], list)
        assert any("address" in g.lower() or "zoning" in g.lower() for g in meta["coverage_gaps"])

    def test_required_documents_has_coverage_gaps(self):
        from src.tools.required_documents import required_documents
        _, meta = run(required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            return_structured=True,
        ))
        assert isinstance(meta["coverage_gaps"], list)
        assert any("standard DBI" in g for g in meta["coverage_gaps"])

    def test_revision_risk_has_coverage_gaps(self):
        from src.tools.revision_risk import revision_risk
        _, meta = run(revision_risk(
            permit_type="alterations",
            return_structured=True,
        ))
        assert isinstance(meta["coverage_gaps"], list)
        assert any("cost revision proxy" in g.lower() for g in meta["coverage_gaps"])


# ===========================================================================
# 5. estimate_fees revision probability by cost bracket
# ===========================================================================

class TestRevisionProbability:
    """estimate_fees includes cost revision risk section."""

    def test_revision_risk_under_5k(self):
        from src.tools.estimate_fees import estimate_fees
        result = run(estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=3000,
        ))
        assert "Cost Revision Risk" in result
        assert "22%" in result or "~22%" in result

    def test_revision_risk_25k_to_100k(self):
        from src.tools.estimate_fees import estimate_fees
        result = run(estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=50000,
        ))
        assert "Cost Revision Risk" in result
        assert "29%" in result or "~29%" in result
        assert "ceiling" in result.lower()

    def test_revision_risk_over_500k(self):
        from src.tools.estimate_fees import estimate_fees
        result = run(estimate_fees(
            permit_type="new_construction",
            estimated_construction_cost=1000000,
        ))
        assert "Cost Revision Risk" in result
        assert "20%" in result or "~20%" in result


# ===========================================================================
# 6. estimate_timeline disclaimer for small samples
# ===========================================================================

class TestTimelineSmallSample:
    """estimate_timeline shows disclaimer when sample < 20."""

    def test_disclaimer_when_db_unavailable(self):
        from src.tools.estimate_timeline import estimate_timeline
        # Default mock returns no data
        result = run(estimate_timeline(permit_type="alterations"))
        # Should have some data coverage note about db or limited data
        assert "Data Coverage" in result or "not available" in result.lower()

    def test_disclaimer_mentions_limited_data(self):
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = run(estimate_timeline(
            permit_type="alterations",
            return_structured=True,
        ))
        # With no DB data, coverage gaps should mention it
        assert len(meta["coverage_gaps"]) > 0


# ===========================================================================
# 7. Coverage disclaimers appear in markdown output
# ===========================================================================

class TestCoverageDisclaimersInMarkdown:
    """Coverage disclaimer sections appear in the markdown output."""

    def test_fees_data_coverage_in_markdown(self):
        from src.tools.estimate_fees import estimate_fees
        result = run(estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=50000,
        ))
        assert "## Data Coverage" in result

    def test_predict_data_coverage_in_markdown(self):
        from src.tools.predict_permits import predict_permits
        result = run(predict_permits(
            project_description="Bathroom remodel",
        ))
        assert "## Data Coverage" in result

    def test_required_docs_data_coverage_in_markdown(self):
        from src.tools.required_documents import required_documents
        result = run(required_documents(
            permit_forms=["Form 3/8"],
            review_path="otc",
        ))
        assert "## Data Coverage" in result

    def test_revision_risk_data_coverage_in_markdown(self):
        from src.tools.revision_risk import revision_risk
        result = run(revision_risk(permit_type="alterations"))
        assert "## Data Coverage" in result


# ===========================================================================
# 8. Methodology dict type safety
# ===========================================================================

class TestMethodologyTypes:
    """Validate types of methodology dict fields."""

    def test_formula_steps_is_list(self):
        from src.tools.estimate_fees import estimate_fees
        _, meta = run(estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=50000,
            return_structured=True,
        ))
        assert isinstance(meta["formula_steps"], list)
        assert all(isinstance(s, str) for s in meta["formula_steps"])

    def test_data_sources_is_list(self):
        from src.tools.predict_permits import predict_permits
        _, meta = run(predict_permits(
            project_description="New ADU",
            return_structured=True,
        ))
        assert isinstance(meta["data_sources"], list)
        assert all(isinstance(s, str) for s in meta["data_sources"])

    def test_sample_size_is_int(self):
        from src.tools.revision_risk import revision_risk
        _, meta = run(revision_risk(
            permit_type="alterations",
            return_structured=True,
        ))
        assert isinstance(meta["sample_size"], int)

    def test_confidence_is_string(self):
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = run(estimate_timeline(
            permit_type="alterations",
            return_structured=True,
        ))
        assert meta["confidence"] in ("high", "medium", "low")

    def test_data_freshness_is_iso_date(self):
        from src.tools.required_documents import required_documents
        _, meta = run(required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            return_structured=True,
        ))
        from datetime import date
        # Should be a valid ISO date string
        parsed = date.fromisoformat(meta["data_freshness"])
        assert parsed == date.today()


# ===========================================================================
# 9. Cost revision bracket helper
# ===========================================================================

class TestCostRevisionBracket:
    """Test the _get_cost_revision_bracket helper."""

    def test_under_5k(self):
        from src.tools.estimate_fees import _get_cost_revision_bracket
        bracket = _get_cost_revision_bracket(3000)
        assert bracket["label"] == "Under $5K"
        assert bracket["rate"] == 0.217

    def test_5k_to_25k(self):
        from src.tools.estimate_fees import _get_cost_revision_bracket
        bracket = _get_cost_revision_bracket(15000)
        assert bracket["label"] == "$5K–$25K"

    def test_25k_to_100k(self):
        from src.tools.estimate_fees import _get_cost_revision_bracket
        bracket = _get_cost_revision_bracket(50000)
        assert bracket["label"] == "$25K–$100K"
        assert bracket["rate"] == 0.286

    def test_100k_to_500k(self):
        from src.tools.estimate_fees import _get_cost_revision_bracket
        bracket = _get_cost_revision_bracket(250000)
        assert bracket["label"] == "$100K–$500K"

    def test_over_500k(self):
        from src.tools.estimate_fees import _get_cost_revision_bracket
        bracket = _get_cost_revision_bracket(1000000)
        assert bracket["label"] == "Over $500K"
        assert bracket["rate"] == 0.198
