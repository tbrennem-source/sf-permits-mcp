"""Tests for intelligence integration in property reports.

Covers:
  - get_property_report() return structure (keys present)
  - After QS14, an 'intelligence' key may be added — tested defensively
  - Existing known keys always present (block, lot, risk_assessment, etc.)

Uses mocking to avoid live DB / SODA calls.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_conn():
    """Return a MagicMock that mimics a DuckDB/psycopg2 connection context manager."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.close = MagicMock()
    return mock_conn


# ---------------------------------------------------------------------------
# Tests: get_property_report() return structure
# ---------------------------------------------------------------------------

class TestReportStructure:
    """get_property_report() must always return a dict with required keys."""

    @patch("web.report._lookup_by_block_lot", return_value=[])
    @patch("web.report._get_contacts_batch", return_value={})
    @patch("web.report._get_inspections_batch", return_value={})
    @patch("web.report._get_nearby_activity", return_value=[])
    @patch("web.report._get_parcel_summary", return_value=None)
    @patch("web.report._fetch_complaints", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_violations", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_property", new_callable=AsyncMock, return_value=[])
    @patch("web.report.get_routing_progress_batch", return_value={})
    @patch("web.report.get_connection")
    def test_report_returns_required_keys(
        self,
        mock_get_conn,
        mock_routing,
        mock_fetch_property,
        mock_fetch_violations,
        mock_fetch_complaints,
        mock_parcel_summary,
        mock_nearby,
        mock_inspections,
        mock_contacts,
        mock_lookup,
    ):
        """get_property_report always returns required keys."""
        mock_get_conn.return_value = _make_mock_conn()

        from web.report import get_property_report
        result = get_property_report("2991", "012")

        assert isinstance(result, dict)
        assert "block" in result
        assert "lot" in result
        assert result["block"] == "2991"
        assert result["lot"] == "012"
        assert "permits" in result
        assert "risk_assessment" in result
        assert "consultant_signal" in result
        assert "links" in result

    @patch("web.report._lookup_by_block_lot", return_value=[])
    @patch("web.report._get_contacts_batch", return_value={})
    @patch("web.report._get_inspections_batch", return_value={})
    @patch("web.report._get_nearby_activity", return_value=[])
    @patch("web.report._get_parcel_summary", return_value=None)
    @patch("web.report._fetch_complaints", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_violations", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_property", new_callable=AsyncMock, return_value=[])
    @patch("web.report.get_routing_progress_batch", return_value={})
    @patch("web.report.get_connection")
    def test_report_returns_is_owner_key(
        self,
        mock_get_conn,
        mock_routing,
        mock_fetch_property,
        mock_fetch_violations,
        mock_fetch_complaints,
        mock_parcel_summary,
        mock_nearby,
        mock_inspections,
        mock_contacts,
        mock_lookup,
    ):
        """is_owner key reflects argument passed to get_property_report."""
        mock_get_conn.return_value = _make_mock_conn()

        from web.report import get_property_report
        result = get_property_report("2991", "012", is_owner=False)
        assert result["is_owner"] is False

    @patch("web.report._lookup_by_block_lot", return_value=[])
    @patch("web.report._get_contacts_batch", return_value={})
    @patch("web.report._get_inspections_batch", return_value={})
    @patch("web.report._get_nearby_activity", return_value=[])
    @patch("web.report._get_parcel_summary", return_value=None)
    @patch("web.report._fetch_complaints", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_violations", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_property", new_callable=AsyncMock, return_value=[])
    @patch("web.report.get_routing_progress_batch", return_value={})
    @patch("web.report.get_connection")
    def test_report_intelligence_key_if_present(
        self,
        mock_get_conn,
        mock_routing,
        mock_fetch_property,
        mock_fetch_violations,
        mock_fetch_complaints,
        mock_parcel_summary,
        mock_nearby,
        mock_inspections,
        mock_contacts,
        mock_lookup,
    ):
        """If 'intelligence' key is added (QS14+), it must be a dict."""
        mock_get_conn.return_value = _make_mock_conn()

        from web.report import get_property_report
        result = get_property_report("2991", "012")

        # Defensive: if intelligence key exists, validate its type
        if "intelligence" in result:
            assert isinstance(result["intelligence"], dict)

    @patch("web.report._lookup_by_block_lot", return_value=[])
    @patch("web.report._get_contacts_batch", return_value={})
    @patch("web.report._get_inspections_batch", return_value={})
    @patch("web.report._get_nearby_activity", return_value=[])
    @patch("web.report._get_parcel_summary", return_value=None)
    @patch("web.report._fetch_complaints", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_violations", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_property", new_callable=AsyncMock, return_value=[])
    @patch("web.report.get_routing_progress_batch", return_value={})
    @patch("web.report.get_connection")
    def test_report_whats_missing_key(
        self,
        mock_get_conn,
        mock_routing,
        mock_fetch_property,
        mock_fetch_violations,
        mock_fetch_complaints,
        mock_parcel_summary,
        mock_nearby,
        mock_inspections,
        mock_contacts,
        mock_lookup,
    ):
        """whats_missing key is always present in the report dict."""
        mock_get_conn.return_value = _make_mock_conn()

        from web.report import get_property_report
        result = get_property_report("2991", "012")
        assert "whats_missing" in result

    @patch("web.report._lookup_by_block_lot", return_value=[])
    @patch("web.report._get_contacts_batch", return_value={})
    @patch("web.report._get_inspections_batch", return_value={})
    @patch("web.report._get_nearby_activity", return_value=[])
    @patch("web.report._get_parcel_summary", return_value=None)
    @patch("web.report._fetch_complaints", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_violations", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_property", new_callable=AsyncMock, return_value=[])
    @patch("web.report.get_routing_progress_batch", return_value={})
    @patch("web.report.get_connection")
    def test_report_empty_parcel_has_empty_permits(
        self,
        mock_get_conn,
        mock_routing,
        mock_fetch_property,
        mock_fetch_violations,
        mock_fetch_complaints,
        mock_parcel_summary,
        mock_nearby,
        mock_inspections,
        mock_contacts,
        mock_lookup,
    ):
        """Empty block/lot returns empty permits list, not None."""
        mock_get_conn.return_value = _make_mock_conn()

        from web.report import get_property_report
        result = get_property_report("9999", "999")
        assert isinstance(result["permits"], list)
        assert len(result["permits"]) == 0

    @patch("web.report._lookup_by_block_lot", return_value=[])
    @patch("web.report._get_contacts_batch", return_value={})
    @patch("web.report._get_inspections_batch", return_value={})
    @patch("web.report._get_nearby_activity", return_value=[])
    @patch("web.report._get_parcel_summary", return_value=None)
    @patch("web.report._fetch_complaints", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_violations", new_callable=AsyncMock, return_value=[])
    @patch("web.report._fetch_property", new_callable=AsyncMock, return_value=[])
    @patch("web.report.get_routing_progress_batch", return_value={})
    @patch("web.report.get_connection")
    def test_report_no_risk_for_empty_parcel(
        self,
        mock_get_conn,
        mock_routing,
        mock_fetch_property,
        mock_fetch_violations,
        mock_fetch_complaints,
        mock_parcel_summary,
        mock_nearby,
        mock_inspections,
        mock_contacts,
        mock_lookup,
    ):
        """Empty parcel with no complaints/violations returns empty risk_assessment."""
        mock_get_conn.return_value = _make_mock_conn()

        from web.report import get_property_report
        result = get_property_report("9999", "999")
        assert isinstance(result["risk_assessment"], list)
        assert len(result["risk_assessment"]) == 0


# ---------------------------------------------------------------------------
# Tests: _compute_risk_assessment integration with intelligence keys
# ---------------------------------------------------------------------------

class TestRiskAssessmentIntelligenceIntegration:
    """Verify risk assessment behavior relevant to intelligence display."""

    def test_risk_items_always_have_severity(self):
        """Every risk item produced by _compute_risk_assessment has severity key."""
        from web.report import _compute_risk_assessment
        risks = _compute_risk_assessment(
            permits=[{"estimated_cost": 600000, "permit_number": "P1",
                      "status": "ISSUED", "description": "big reno"}],
            complaints=[{"status": "OPEN", "complaint_number": "C1",
                         "description": "noise"}],
            violations=[],
            property_data=[],
        )
        for risk in risks:
            assert "severity" in risk

    def test_consultant_signal_has_required_keys(self):
        """_compute_consultant_signal always returns dict with score and signal keys."""
        from web.report import _compute_consultant_signal
        result = _compute_consultant_signal(
            complaints=[], violations=[], permits=[], property_data=[]
        )
        assert "score" in result
        assert "signal" in result
        assert isinstance(result["score"], (int, float))
        assert isinstance(result["signal"], str)
