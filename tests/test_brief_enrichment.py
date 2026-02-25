"""Tests for Sprint 55D morning brief enrichment.

Covers:
- Planning context section (D1)
- Compliance calendar section (D2)
- Data quality footer (D3)
- Nightly planning change detection (D4)
- Nightly boiler change detection (D5)
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock, call


# ---------------------------------------------------------------------------
# D1: _get_planning_context
# ---------------------------------------------------------------------------

class TestGetPlanningContext:

    def test_returns_empty_when_no_parcel_watches(self):
        """Returns empty list when user has no parcel watches."""
        with patch("web.brief.query") as mock_q:
            mock_q.return_value = []  # no watches
            from web.brief import _get_planning_context
            result = _get_planning_context(user_id=1)
        assert result == []

    def test_returns_planning_records_for_watched_parcel(self):
        """Returns planning records for a watched block/lot parcel."""
        watch_rows = [("3512", "001", "My Parcel")]
        planning_rows = [
            ("PR-001", "CONDITIONAL USE", "Restaurant conversion", "2025-01-15", "active")
        ]
        tax_row = ("RC-4",)

        with patch("web.brief.query") as mock_q, \
             patch("web.brief.query_one") as mock_qo:
            mock_q.side_effect = [watch_rows, planning_rows]
            mock_qo.return_value = tax_row

            from web.brief import _get_planning_context
            result = _get_planning_context(user_id=1)

        assert len(result) == 1
        assert result[0]["block_lot"] == "3512-001"
        assert result[0]["zoning_code"] == "RC-4"
        assert len(result[0]["planning_records"]) == 1
        assert result[0]["planning_records"][0]["record_id"] == "PR-001"
        assert result[0]["planning_records"][0]["record_type"] == "CONDITIONAL USE"

    def test_excludes_withdrawn_and_closed_records(self):
        """Planning records with withdrawn/closed status are filtered by the query."""
        # The function relies on SQL to exclude withdrawn/closed — if no active records
        # and no zoning, the parcel is skipped
        watch_rows = [("3512", "001", "Label")]
        with patch("web.brief.query") as mock_q, \
             patch("web.brief.query_one") as mock_qo:
            mock_q.side_effect = [watch_rows, []]  # empty planning records
            mock_qo.return_value = None  # no zoning

            from web.brief import _get_planning_context
            result = _get_planning_context(user_id=1)

        # Parcel skipped — no records, no zoning
        assert result == []

    def test_includes_parcel_with_zoning_but_no_planning_records(self):
        """Returns parcel entry when zoning code exists even if no planning records."""
        watch_rows = [("3512", "001", "My Parcel")]
        with patch("web.brief.query") as mock_q, \
             patch("web.brief.query_one") as mock_qo:
            mock_q.side_effect = [watch_rows, []]  # no planning records
            mock_qo.return_value = ("RH-2",)  # has zoning

            from web.brief import _get_planning_context
            result = _get_planning_context(user_id=1)

        assert len(result) == 1
        assert result[0]["zoning_code"] == "RH-2"
        assert result[0]["planning_records"] == []

    def test_handles_watch_query_failure_gracefully(self):
        """Returns empty list when watch_items query raises an exception."""
        with patch("web.brief.query", side_effect=Exception("DB offline")):
            from web.brief import _get_planning_context
            result = _get_planning_context(user_id=1)
        assert result == []

    def test_handles_planning_query_failure_per_parcel(self):
        """Skips parcel gracefully when planning_records query fails."""
        watch_rows = [("3512", "001", None)]
        with patch("web.brief.query") as mock_q, \
             patch("web.brief.query_one") as mock_qo:
            # First call: watch rows. Second call: raise for planning records
            mock_q.side_effect = [watch_rows, Exception("planning table missing")]
            mock_qo.return_value = ("NC-3",)

            from web.brief import _get_planning_context
            result = _get_planning_context(user_id=1)

        # zoning found even if planning query failed — parcel included
        assert len(result) == 1
        assert result[0]["zoning_code"] == "NC-3"
        assert result[0]["planning_records"] == []

    def test_multiple_parcels_returned(self):
        """Handles multiple watched parcels correctly."""
        watch_rows = [("1000", "001", "Parcel A"), ("2000", "010", "Parcel B")]
        planning_a = [("PA-001", "Variance", "ADU permit", "2025-03-01", "open")]
        planning_b = []

        with patch("web.brief.query") as mock_q, \
             patch("web.brief.query_one") as mock_qo:
            mock_q.side_effect = [watch_rows, planning_a, planning_b]
            mock_qo.side_effect = [("RH-1",), ("RM-4",)]

            from web.brief import _get_planning_context
            result = _get_planning_context(user_id=1)

        assert len(result) == 2
        block_lots = [r["block_lot"] for r in result]
        assert "1000-001" in block_lots
        assert "2000-010" in block_lots


# ---------------------------------------------------------------------------
# D2: _get_compliance_calendar
# ---------------------------------------------------------------------------

class TestGetComplianceCalendar:

    def test_returns_empty_when_no_parcel_watches(self):
        """Returns empty list when user has no parcel watches."""
        with patch("web.brief.query") as mock_q:
            mock_q.return_value = []
            from web.brief import _get_compliance_calendar
            result = _get_compliance_calendar(user_id=1)
        assert result == []

    def test_finds_expiring_boiler_permits(self):
        """Returns boiler permits expiring within 90 days."""
        watch_rows = [("3512", "001")]
        today = date.today()
        expiring_in_30 = (today + timedelta(days=30)).isoformat()
        boiler_rows = [("BP-001", "low_pressure", expiring_in_30)]

        with patch("web.brief.query") as mock_q:
            mock_q.side_effect = [watch_rows, boiler_rows]
            from web.brief import _get_compliance_calendar
            result = _get_compliance_calendar(user_id=1)

        assert len(result) == 1
        assert result[0]["permit_number"] == "BP-001"
        assert result[0]["boiler_type"] == "low_pressure"
        assert result[0]["days_until"] == 30
        assert result[0]["is_expired"] is False

    def test_excludes_permits_expiring_beyond_90_days(self):
        """Does not return permits with more than 90 days until expiration."""
        watch_rows = [("3512", "001")]
        today = date.today()
        far_future = (today + timedelta(days=120)).isoformat()
        boiler_rows = [("BP-002", "high_pressure", far_future)]

        with patch("web.brief.query") as mock_q:
            mock_q.side_effect = [watch_rows, boiler_rows]
            from web.brief import _get_compliance_calendar
            result = _get_compliance_calendar(user_id=1)

        assert result == []

    def test_includes_already_expired_permits(self):
        """Already-expired permits (days_until < 0) are included and flagged."""
        watch_rows = [("3512", "001")]
        today = date.today()
        expired_date = (today - timedelta(days=10)).isoformat()
        boiler_rows = [("BP-003", "heating", expired_date)]

        with patch("web.brief.query") as mock_q:
            mock_q.side_effect = [watch_rows, boiler_rows]
            from web.brief import _get_compliance_calendar
            result = _get_compliance_calendar(user_id=1)

        assert len(result) == 1
        assert result[0]["is_expired"] is True
        assert result[0]["days_until"] == -10

    def test_returns_empty_when_no_boiler_permits(self):
        """Returns empty list when watched parcel has no boiler permits."""
        watch_rows = [("3512", "001")]
        with patch("web.brief.query") as mock_q:
            mock_q.side_effect = [watch_rows, []]
            from web.brief import _get_compliance_calendar
            result = _get_compliance_calendar(user_id=1)
        assert result == []

    def test_sorted_by_days_until_ascending(self):
        """Results sorted soonest to expire first."""
        watch_rows = [("3512", "001")]
        today = date.today()
        boiler_rows = [
            ("BP-010", "low", (today + timedelta(days=60)).isoformat()),
            ("BP-011", "high", (today + timedelta(days=10)).isoformat()),
            ("BP-012", "mid", (today - timedelta(days=5)).isoformat()),  # expired
        ]

        with patch("web.brief.query") as mock_q:
            mock_q.side_effect = [watch_rows, boiler_rows]
            from web.brief import _get_compliance_calendar
            result = _get_compliance_calendar(user_id=1)

        assert len(result) == 3
        assert result[0]["days_until"] == -5  # expired first
        assert result[1]["days_until"] == 10
        assert result[2]["days_until"] == 60

    def test_handles_watch_query_failure_gracefully(self):
        """Returns empty list when watch_items query raises."""
        with patch("web.brief.query", side_effect=Exception("DB error")):
            from web.brief import _get_compliance_calendar
            result = _get_compliance_calendar(user_id=1)
        assert result == []


# ---------------------------------------------------------------------------
# D3: _get_data_quality
# ---------------------------------------------------------------------------

class TestGetDataQuality:

    def test_returns_match_percentages(self):
        """Computes planning, tax, and boiler match percentages."""
        mock_conn = MagicMock()
        # DuckDB path: conn.execute(...).fetchone()
        mock_conn.execute.return_value.fetchone.side_effect = [
            (800,),   # planning_matched
            (1000,),  # total_planning
            (500,),   # tax_matched
            (700,),   # total_tax
            (200,),   # boiler_matched
            (250,),   # total_boiler
        ]

        with patch("web.brief.get_connection", return_value=mock_conn), \
             patch("web.brief.BACKEND", "duckdb"):
            from web.brief import _get_data_quality
            result = _get_data_quality()

        assert result["planning_match_pct"] == 80.0
        assert result["planning_matched"] == 800
        assert result["total_planning"] == 1000
        assert result["tax_match_pct"] == pytest.approx(71.4, abs=0.1)
        assert result["boiler_match_pct"] == 80.0
        assert result["warnings"] == []

    def test_warns_when_match_rate_below_threshold(self):
        """Adds warning when any match rate is below 5%."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.side_effect = [
            (2,),     # planning_matched — very low
            (1000,),  # total_planning
            (500,),   # tax_matched
            (700,),   # total_tax
            (200,),   # boiler_matched
            (250,),   # total_boiler
        ]

        with patch("web.brief.get_connection", return_value=mock_conn), \
             patch("web.brief.BACKEND", "duckdb"):
            from web.brief import _get_data_quality
            result = _get_data_quality()

        assert len(result["warnings"]) >= 1
        assert any("Planning match rate low" in w for w in result["warnings"])

    def test_handles_zero_totals_gracefully(self):
        """Returns 0% when totals are zero (no division by zero)."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.side_effect = [
            (0,), (0,),  # planning: 0/0
            (0,), (0,),  # tax: 0/0
            (0,), (0,),  # boiler: 0/0
        ]

        with patch("web.brief.get_connection", return_value=mock_conn), \
             patch("web.brief.BACKEND", "duckdb"):
            from web.brief import _get_data_quality
            result = _get_data_quality()

        assert result["planning_match_pct"] == 0.0
        assert result["tax_match_pct"] == 0.0
        assert result["boiler_match_pct"] == 0.0
        # No warnings for zero totals (nothing to match against)
        assert result["warnings"] == []

    def test_returns_empty_dict_on_db_error(self):
        """Returns empty dict if database query raises."""
        with patch("web.brief.get_connection", side_effect=Exception("No DB")):
            from web.brief import _get_data_quality
            result = _get_data_quality()
        assert result == {}


# ---------------------------------------------------------------------------
# D4: detect_planning_changes
# ---------------------------------------------------------------------------

class TestDetectPlanningChanges:

    def test_inserts_new_planning_record(self):
        """Inserts a new planning record not yet in DB."""
        records = [{
            "record_id": "CU-2025-001",
            "status": "active",
            "open_date": "2025-01-15",
            "block": "3512",
            "lot": "001",
            "record_type": "CONDITIONAL USE",
            "description": "Restaurant conversion",
        }]

        with patch("scripts.nightly_changes.query_one", return_value=None), \
             patch("scripts.nightly_changes.BACKEND", "postgres"), \
             patch("scripts.nightly_changes.execute_write") as mock_write:

            from scripts.nightly_changes import detect_planning_changes
            count = detect_planning_changes(records, dry_run=False, source="nightly")

        assert count == 1
        assert mock_write.called

    def test_detects_status_change_on_existing_record(self):
        """Detects status change on an existing planning record."""
        records = [{
            "record_id": "CU-2025-002",
            "status": "approved",
            "open_date": "2025-02-01",
            "block": "1234",
            "lot": "010",
            "record_type": "VARIANCE",
            "description": "Side setback variance",
        }]

        existing_row = ("pending",)  # old status
        with patch("scripts.nightly_changes.query_one", return_value=existing_row), \
             patch("scripts.nightly_changes.BACKEND", "postgres"), \
             patch("scripts.nightly_changes.execute_write") as mock_write:

            from scripts.nightly_changes import detect_planning_changes
            count = detect_planning_changes(records, dry_run=False, source="nightly")

        assert count == 1
        assert mock_write.called

    def test_skips_unchanged_records(self):
        """Skips planning records where status has not changed."""
        records = [{
            "record_id": "CU-2025-003",
            "status": "active",
            "open_date": "2025-03-01",
            "record_type": "EX",
            "description": "",
        }]

        existing_row = ("active",)  # same status
        with patch("scripts.nightly_changes.query_one", return_value=existing_row), \
             patch("scripts.nightly_changes.execute_write") as mock_write:

            from scripts.nightly_changes import detect_planning_changes
            count = detect_planning_changes(records)

        assert count == 0
        mock_write.assert_not_called()

    def test_skips_records_without_record_id(self):
        """Skips records that have no record_id or case_no."""
        records = [{"status": "active", "open_date": "2025-01-01"}]

        with patch("scripts.nightly_changes.query_one") as mock_qo, \
             patch("scripts.nightly_changes.execute_write") as mock_write:

            from scripts.nightly_changes import detect_planning_changes
            count = detect_planning_changes(records)

        assert count == 0
        mock_qo.assert_not_called()
        mock_write.assert_not_called()

    def test_dry_run_counts_without_writing(self):
        """Dry run counts changes without inserting into DB."""
        records = [
            {"record_id": "PR-1", "status": "filed", "open_date": "2025-01-01",
             "record_type": "CU", "description": ""},
        ]

        with patch("scripts.nightly_changes.query_one", return_value=None), \
             patch("scripts.nightly_changes.execute_write") as mock_write:

            from scripts.nightly_changes import detect_planning_changes
            count = detect_planning_changes(records, dry_run=True)

        assert count == 1
        mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# D5: detect_boiler_changes
# ---------------------------------------------------------------------------

class TestDetectBoilerChanges:

    def test_inserts_new_boiler_permit(self):
        """Inserts a new boiler permit not yet in DB."""
        records = [{
            "permit_number": "BLR-2025-001",
            "status": "active",
            "issue_date": "2025-01-20",
            "block": "3512",
            "lot": "001",
            "boiler_type": "low_pressure_steam",
        }]

        with patch("scripts.nightly_changes.query_one", return_value=None), \
             patch("scripts.nightly_changes.BACKEND", "postgres"), \
             patch("scripts.nightly_changes.execute_write") as mock_write:

            from scripts.nightly_changes import detect_boiler_changes
            count = detect_boiler_changes(records, dry_run=False)

        assert count == 1
        assert mock_write.called

    def test_detects_status_change_on_existing_boiler_permit(self):
        """Detects status change on an existing boiler permit."""
        records = [{
            "permit_number": "BLR-2025-002",
            "status": "expired",
            "issue_date": "2024-01-01",
            "block": "2020",
            "lot": "005",
            "boiler_type": "high_pressure",
        }]

        existing_row = ("active",)  # was active, now expired
        with patch("scripts.nightly_changes.query_one", return_value=existing_row), \
             patch("scripts.nightly_changes.BACKEND", "postgres"), \
             patch("scripts.nightly_changes.execute_write") as mock_write:

            from scripts.nightly_changes import detect_boiler_changes
            count = detect_boiler_changes(records)

        assert count == 1
        assert mock_write.called

    def test_skips_unchanged_boiler_permits(self):
        """Does not insert when boiler permit status has not changed."""
        records = [{
            "permit_number": "BLR-2025-003",
            "status": "active",
            "issue_date": "2025-02-01",
            "boiler_type": "steam",
        }]

        existing_row = ("active",)
        with patch("scripts.nightly_changes.query_one", return_value=existing_row), \
             patch("scripts.nightly_changes.execute_write") as mock_write:

            from scripts.nightly_changes import detect_boiler_changes
            count = detect_boiler_changes(records)

        assert count == 0
        mock_write.assert_not_called()

    def test_skips_records_without_permit_number(self):
        """Skips records with no permit_number or boiler_permit_number."""
        records = [{"status": "active", "issue_date": "2025-01-01"}]

        with patch("scripts.nightly_changes.query_one") as mock_qo, \
             patch("scripts.nightly_changes.execute_write") as mock_write:

            from scripts.nightly_changes import detect_boiler_changes
            count = detect_boiler_changes(records)

        assert count == 0
        mock_qo.assert_not_called()
        mock_write.assert_not_called()

    def test_dry_run_counts_without_writing(self):
        """Dry run previews boiler changes without DB writes."""
        records = [{
            "permit_number": "BLR-2025-004",
            "status": "active",
            "issue_date": "2025-01-01",
            "boiler_type": "water",
        }]

        with patch("scripts.nightly_changes.query_one", return_value=None), \
             patch("scripts.nightly_changes.execute_write") as mock_write:

            from scripts.nightly_changes import detect_boiler_changes
            count = detect_boiler_changes(records, dry_run=True)

        assert count == 1
        mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: get_morning_brief includes new keys
# ---------------------------------------------------------------------------

class TestMorningBriefIncludesNewSections:

    def test_brief_includes_planning_context_key(self):
        """get_morning_brief result includes 'planning_context' key."""
        with patch("web.brief.query") as mock_q, \
             patch("web.brief.query_one") as mock_qo, \
             patch("web.brief.get_pipeline_health_for_brief") as mock_ph, \
             patch("web.brief._get_planning_context") as mock_pc, \
             patch("web.brief._get_compliance_calendar") as mock_cc, \
             patch("web.brief._get_data_quality") as mock_dq:

            mock_q.return_value = []
            mock_qo.return_value = None
            mock_ph.return_value = {"status": "ok", "issues": [], "checks": []}
            mock_pc.return_value = []
            mock_cc.return_value = []
            mock_dq.return_value = {}

            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1, lookback_days=1)

        assert "planning_context" in result
        assert "compliance_calendar" in result
        assert "data_quality" in result

    def test_brief_summary_includes_new_counts(self):
        """Brief summary includes planning_context_count and compliance_calendar_count."""
        with patch("web.brief.query") as mock_q, \
             patch("web.brief.query_one") as mock_qo, \
             patch("web.brief.get_pipeline_health_for_brief") as mock_ph, \
             patch("web.brief._get_planning_context") as mock_pc, \
             patch("web.brief._get_compliance_calendar") as mock_cc, \
             patch("web.brief._get_data_quality") as mock_dq:

            mock_q.return_value = []
            mock_qo.return_value = None
            mock_ph.return_value = {"status": "ok", "issues": [], "checks": []}
            mock_pc.return_value = [{"block_lot": "1234-001"}]
            mock_cc.return_value = [{"permit_number": "BP-1"}]
            mock_dq.return_value = {}

            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1, lookback_days=1)

        assert result["summary"]["planning_context_count"] == 1
        assert result["summary"]["compliance_calendar_count"] == 1
