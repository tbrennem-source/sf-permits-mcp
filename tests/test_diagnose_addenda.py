"""Tests for scripts/diagnose_addenda.py — Sprint 53 Session C.

Tests the staleness diagnostic using mocks — no live DB or SODA API needed.
"""

from __future__ import annotations

import pytest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock


# ── CronHealthSummary ─────────────────────────────────────────────


def test_cron_health_summary_dataclass():
    from scripts.diagnose_addenda import CronHealthSummary
    summary = CronHealthSummary(
        last_success_at="2026-02-20T03:00:00Z",
        last_run_at="2026-02-24T03:00:00Z",
        last_run_status="success",
        days_since_success=4.0,
        total_runs_last_7d=5,
        failed_runs_last_7d=1,
        catchup_runs_last_7d=1,
    )
    assert summary.days_since_success == 4.0
    assert summary.total_runs_last_7d == 5


def test_addenda_freshness_result_dataclass():
    from scripts.diagnose_addenda import AddenaFreshnessResult
    result = AddenaFreshnessResult(
        max_data_as_of="2026-02-19",
        max_finish_date="2026-02-19",
        total_rows=3_900_000,
        days_since_data_as_of=5,
        is_stale=True,
        stale_reason="5 days old",
    )
    assert result.is_stale is True
    assert result.total_rows == 3_900_000


def test_diagnostic_report_dataclass():
    from scripts.diagnose_addenda import DiagnosticReport
    report = DiagnosticReport(
        run_at="2026-02-24T08:00:00Z",
        db_available=True,
        cron_health=None,
        addenda_freshness=None,
        soda_check=None,
        overall_status="fresh",
        root_cause=None,
        recommendations=[],
    )
    assert report.overall_status == "fresh"
    assert report.db_available is True


# ── check_cron_health ─────────────────────────────────────────────


def test_check_cron_health_recent_success():
    """Recent success → low days_since_success."""
    recent_ts = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()

    with patch("src.db.query_one") as mock_qo, \
         patch("src.db.query") as mock_q:
        # last_success_row, last_run_row, catchup_row (3 query_one calls)
        mock_qo.side_effect = [
            (recent_ts, recent_ts),   # last success
            (recent_ts, "success"),   # last run
            (3,),                     # catchup count
        ]
        # count by status (1 query call)
        mock_q.side_effect = [
            [("success", 7)],
        ]
        from scripts.diagnose_addenda import check_cron_health
        result = check_cron_health()

    assert result.days_since_success is not None
    assert result.days_since_success < 1
    assert result.last_run_status == "success"
    assert result.total_runs_last_7d == 7


def test_check_cron_health_no_success():
    """No successful runs → days_since_success is None."""
    with patch("src.db.query_one") as mock_qo, \
         patch("src.db.query") as mock_q:
        # 3 query_one calls: last_success, last_run, catchup
        mock_qo.side_effect = [None, None, (0,)]
        # 1 query call: count by status
        mock_q.side_effect = [[]]

        from scripts.diagnose_addenda import check_cron_health
        result = check_cron_health()

    assert result.days_since_success is None
    assert result.total_runs_last_7d == 0


# ── check_addenda_freshness ───────────────────────────────────────


def test_check_addenda_freshness_fresh():
    """Recent data_as_of → not stale."""
    recent = (date.today() - timedelta(days=1)).isoformat()

    with patch("src.db.query_one") as mock_qo:
        mock_qo.side_effect = [
            (1,),         # table exists
            (recent, "2026-02-22", 3_900_000),  # max values
        ]
        from scripts.diagnose_addenda import check_addenda_freshness
        result = check_addenda_freshness()

    assert result.is_stale is False
    assert result.total_rows == 3_900_000
    assert result.days_since_data_as_of == 1


def test_check_addenda_freshness_stale():
    """Old data_as_of → stale flag set."""
    old = (date.today() - timedelta(days=7)).isoformat()

    with patch("src.db.query_one") as mock_qo:
        mock_qo.side_effect = [
            (1,),
            (old, "2026-02-16", 3_900_000),
        ]
        from scripts.diagnose_addenda import check_addenda_freshness
        result = check_addenda_freshness()

    assert result.is_stale is True
    assert "7" in (result.stale_reason or "")


def test_check_addenda_freshness_empty_table():
    """Empty table → stale, total_rows=0."""
    with patch("src.db.query_one") as mock_qo:
        mock_qo.side_effect = [
            (1,),          # table exists
            (None, None, 0),  # no rows
        ]
        from scripts.diagnose_addenda import check_addenda_freshness
        result = check_addenda_freshness()

    assert result.is_stale is True
    assert result.total_rows == 0
    assert "empty" in (result.stale_reason or "").lower()


# ── _determine_overall_status ─────────────────────────────────────


def test_determine_overall_status_all_ok():
    """Recent cron + fresh addenda → fresh."""
    from scripts.diagnose_addenda import (
        _determine_overall_status, CronHealthSummary, AddenaFreshnessResult
    )
    cron = CronHealthSummary(
        last_success_at="2026-02-24T03:00:00Z",
        last_run_at="2026-02-24T03:00:00Z",
        last_run_status="success",
        days_since_success=0.5,
        total_runs_last_7d=7,
        failed_runs_last_7d=0,
        catchup_runs_last_7d=0,
    )
    freshness = AddenaFreshnessResult(
        max_data_as_of="2026-02-23",
        max_finish_date="2026-02-23",
        total_rows=3_900_000,
        days_since_data_as_of=1,
        is_stale=False,
        stale_reason=None,
    )
    status, root_cause, recs = _determine_overall_status(cron, freshness, None)
    assert status == "fresh"
    assert root_cause is None


def test_determine_overall_status_stale_addenda():
    """Stale addenda → stale status."""
    from scripts.diagnose_addenda import (
        _determine_overall_status, CronHealthSummary, AddenaFreshnessResult
    )
    cron = CronHealthSummary(
        last_success_at="2026-02-24T03:00:00Z",
        last_run_at=None,
        last_run_status=None,
        days_since_success=0.5,
        total_runs_last_7d=7,
        failed_runs_last_7d=0,
        catchup_runs_last_7d=0,
    )
    freshness = AddenaFreshnessResult(
        max_data_as_of="2026-02-19",
        max_finish_date="2026-02-19",
        total_rows=3_900_000,
        days_since_data_as_of=5,
        is_stale=True,
        stale_reason="5 days old",
    )
    status, root_cause, recs = _determine_overall_status(cron, freshness, None)
    assert status in ("stale", "critical")
    assert root_cause is not None


def test_determine_overall_status_no_cron_success():
    """No cron success → critical."""
    from scripts.diagnose_addenda import (
        _determine_overall_status, CronHealthSummary, AddenaFreshnessResult
    )
    cron = CronHealthSummary(
        last_success_at=None,
        last_run_at=None,
        last_run_status=None,
        days_since_success=None,
        total_runs_last_7d=0,
        failed_runs_last_7d=0,
        catchup_runs_last_7d=0,
    )
    freshness = AddenaFreshnessResult(
        max_data_as_of="2026-02-19",
        max_finish_date=None,
        total_rows=3_900_000,
        days_since_data_as_of=5,
        is_stale=True,
        stale_reason="old",
    )
    status, root_cause, recs = _determine_overall_status(cron, freshness, None)
    assert status == "critical"
    assert root_cause is not None


def test_determine_overall_status_db_unavailable():
    """No cron AND no freshness → unknown."""
    from scripts.diagnose_addenda import _determine_overall_status
    status, root_cause, recs = _determine_overall_status(None, None, None)
    assert status == "unknown"
    assert root_cause is not None
    assert len(recs) > 0


# ── run_diagnostic ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_diagnostic_no_db():
    """run_diagnostic handles DB unavailability gracefully."""
    with patch("scripts.diagnose_addenda._get_db_connection", return_value=(None, None)):
        from scripts.diagnose_addenda import run_diagnostic
        report = await run_diagnostic(check_soda=False)

    assert report.db_available is False
    assert report.overall_status in ("unknown", "critical")
    assert report.run_at is not None


@pytest.mark.asyncio
async def test_run_diagnostic_with_mocked_db():
    """run_diagnostic returns correct structure when DB is available."""
    mock_conn = MagicMock()
    recent_ts = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    recent_date = (date.today() - timedelta(days=1)).isoformat()

    with patch("scripts.diagnose_addenda._get_db_connection", return_value=(mock_conn, "postgres")), \
         patch("scripts.diagnose_addenda.check_cron_health") as mock_cron, \
         patch("scripts.diagnose_addenda.check_addenda_freshness") as mock_fresh:

        from scripts.diagnose_addenda import CronHealthSummary, AddenaFreshnessResult

        mock_cron.return_value = CronHealthSummary(
            last_success_at=recent_ts,
            last_run_at=recent_ts,
            last_run_status="success",
            days_since_success=0.4,
            total_runs_last_7d=7,
            failed_runs_last_7d=0,
            catchup_runs_last_7d=0,
        )
        mock_fresh.return_value = AddenaFreshnessResult(
            max_data_as_of=recent_date,
            max_finish_date=recent_date,
            total_rows=3_900_000,
            days_since_data_as_of=1,
            is_stale=False,
            stale_reason=None,
        )
        mock_conn.close = MagicMock()

        from scripts.diagnose_addenda import run_diagnostic
        report = await run_diagnostic(check_soda=False)

    assert report.db_available is True
    assert report.overall_status == "fresh"
    assert report.cron_health is not None
    assert report.addenda_freshness is not None
    assert report.soda_check is None


# ── SodaCheckResult ───────────────────────────────────────────────


def test_soda_check_result_dataclass():
    from scripts.diagnose_addenda import SodaCheckResult
    result = SodaCheckResult(
        reachable=True,
        recent_record_count=15,
        api_max_data_as_of="2026-02-24",
        error=None,
    )
    assert result.reachable is True
    assert result.recent_record_count == 15
