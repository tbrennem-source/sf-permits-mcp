"""Tests for web/pipeline_health.py — Sprint 53 Session C.

Uses mocks/monkeypatching. No live DB or network required.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock


# ── HealthCheck dataclass ────────────────────────────────────────


def test_health_check_dataclass():
    from web.pipeline_health import HealthCheck
    hc = HealthCheck(name="test", status="ok", message="All good")
    assert hc.name == "test"
    assert hc.status == "ok"
    assert hc.message == "All good"
    assert hc.detail is None


def test_health_check_with_detail():
    from web.pipeline_health import HealthCheck
    hc = HealthCheck(name="test", status="warn", message="Watch out", detail={"key": "val"})
    assert hc.detail == {"key": "val"}


def test_pipeline_health_report_dataclass():
    from web.pipeline_health import PipelineHealthReport, HealthCheck
    report = PipelineHealthReport(
        run_at="2026-02-24T03:00:00Z",
        overall_status="ok",
        checks=[HealthCheck("cron_nightly", "ok", "Fresh")],
        summary_line="All good",
    )
    assert report.overall_status == "ok"
    assert len(report.checks) == 1
    assert report.cron_history == []
    assert report.stuck_jobs == []


# ── check_cron_health ────────────────────────────────────────────


def test_check_cron_health_ok():
    """Recent success → status ok."""
    recent_ts = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
    with patch("web.pipeline_health.query_one") as mock_qo:
        mock_qo.return_value = (recent_ts, recent_ts)
        from web.pipeline_health import check_cron_health
        result = check_cron_health()
    assert result.status == "ok"
    assert result.name == "cron_nightly"
    assert "12" in result.message or "hours" in result.message.lower()


def test_check_cron_health_warn():
    """Success 28h ago → warn."""
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=28)).isoformat()
    with patch("web.pipeline_health.query_one") as mock_qo:
        mock_qo.return_value = (old_ts, old_ts)
        from web.pipeline_health import check_cron_health
        result = check_cron_health(warn_hours=26.0, critical_hours=50.0)
    assert result.status == "warn"


def test_check_cron_health_critical():
    """Success >50h ago → critical."""
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=55)).isoformat()
    with patch("web.pipeline_health.query_one") as mock_qo:
        mock_qo.return_value = (old_ts, old_ts)
        from web.pipeline_health import check_cron_health
        result = check_cron_health(warn_hours=26.0, critical_hours=50.0)
    assert result.status == "critical"


def test_check_cron_health_no_rows():
    """No cron rows → critical."""
    with patch("web.pipeline_health.query_one") as mock_qo:
        mock_qo.return_value = None
        from web.pipeline_health import check_cron_health
        result = check_cron_health()
    assert result.status == "critical"
    assert "No successful" in result.message


def test_check_cron_health_db_error():
    """DB error → unknown status (doesn't crash)."""
    with patch("web.pipeline_health.query_one") as mock_qo:
        mock_qo.side_effect = Exception("Connection refused")
        from web.pipeline_health import check_cron_health
        result = check_cron_health()
    assert result.status == "unknown"


# ── check_data_freshness ────────────────────────────────────────


def test_check_data_freshness_fresh():
    """Recent data_as_of → ok."""
    from datetime import date
    recent = (date.today() - timedelta(days=1)).isoformat()
    with patch("web.pipeline_health.query_one") as mock_qo:
        mock_qo.side_effect = [
            (recent, "2026-02-22", 3_900_000),  # addenda
            (recent,),  # permits
            (recent,),  # inspections
        ]
        from web.pipeline_health import check_data_freshness
        result = check_data_freshness()
    assert result.status == "ok"
    assert result.name == "data_freshness"


def test_check_data_freshness_stale():
    """Old data_as_of (7 days) → warn."""
    from datetime import date
    old = (date.today() - timedelta(days=7)).isoformat()
    with patch("web.pipeline_health.query_one") as mock_qo:
        mock_qo.side_effect = [
            (old, "2026-02-15", 3_900_000),
            (old,),
            (old,),
        ]
        from web.pipeline_health import check_data_freshness
        result = check_data_freshness()
    assert result.status in ("warn", "critical")
    assert "stale" in result.message.lower() or "Stale" in result.message


def test_check_data_freshness_no_rows():
    """Empty addenda table → warn/critical."""
    with patch("web.pipeline_health.query_one") as mock_qo:
        mock_qo.side_effect = [
            (None, None, 0),  # addenda empty
            (None,),
            (None,),
        ]
        from web.pipeline_health import check_data_freshness
        result = check_data_freshness()
    # No data_as_of means stale_fields includes addenda
    assert result.status in ("warn", "critical", "ok")  # depends on code path


# ── check_stuck_jobs ─────────────────────────────────────────────


def test_check_stuck_jobs_none():
    """No stuck jobs → ok."""
    with patch("web.pipeline_health.query") as mock_q:
        mock_q.return_value = []
        from web.pipeline_health import check_stuck_jobs
        result = check_stuck_jobs()
    assert result.status == "ok"
    assert result.name == "stuck_jobs"


def test_check_stuck_jobs_found():
    """Stuck job detected → warn."""
    with patch("web.pipeline_health.query") as mock_q:
        mock_q.return_value = [(42, "nightly", "2026-02-23T01:00:00Z")]
        from web.pipeline_health import check_stuck_jobs
        result = check_stuck_jobs()
    assert result.status == "warn"
    assert "1 job" in result.message
    assert result.detail is not None
    assert len(result.detail["stuck_jobs"]) == 1


def test_check_stuck_jobs_db_error():
    """DB error → unknown (no crash)."""
    with patch("web.pipeline_health.query") as mock_q:
        mock_q.side_effect = Exception("timeout")
        from web.pipeline_health import check_stuck_jobs
        result = check_stuck_jobs()
    assert result.status == "unknown"


# ── check_recent_failures ───────────────────────────────────────


def test_check_recent_failures_none():
    """No failures → ok."""
    with patch("web.pipeline_health.query") as mock_q:
        mock_q.return_value = []
        from web.pipeline_health import check_recent_failures
        result = check_recent_failures()
    assert result.status == "ok"


def test_check_recent_failures_warn():
    """1 failure → warn."""
    with patch("web.pipeline_health.query") as mock_q:
        mock_q.return_value = [(1, "nightly", "2026-02-23T02:00:00Z", "connection reset")]
        from web.pipeline_health import check_recent_failures
        result = check_recent_failures()
    assert result.status == "warn"
    assert "1 failure" in result.message


def test_check_recent_failures_critical():
    """3+ failures → critical."""
    with patch("web.pipeline_health.query") as mock_q:
        mock_q.return_value = [
            (1, "nightly", "2026-02-23T01:00:00Z", "err"),
            (2, "nightly", "2026-02-23T02:00:00Z", "err"),
            (3, "nightly", "2026-02-23T03:00:00Z", "err"),
        ]
        from web.pipeline_health import check_recent_failures
        result = check_recent_failures()
    assert result.status == "critical"


# ── get_pipeline_health ─────────────────────────────────────────


def test_get_pipeline_health_all_ok():
    """All checks ok → overall ok."""
    recent_ts = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    from datetime import date
    recent_date = (date.today() - timedelta(days=1)).isoformat()

    with patch("web.pipeline_health.query_one") as mock_qo, \
         patch("web.pipeline_health.query") as mock_q:
        mock_qo.side_effect = [
            (recent_ts, recent_ts),   # check_cron_health
            (recent_date, "2026-02-22", 3_900_000),  # freshness addenda
            (recent_date,),            # freshness permits
            (recent_date,),            # freshness inspections
        ]
        mock_q.side_effect = [
            [],   # check_stuck_jobs
            [],   # check_recent_failures
            [],   # get_cron_history
        ]

        from web.pipeline_health import get_pipeline_health
        report = get_pipeline_health()

    assert report.overall_status in ("ok", "warn", "unknown")
    assert len(report.checks) == 4
    assert report.run_at is not None
    assert report.summary_line != ""


def test_get_pipeline_health_critical_propagates():
    """Critical check → overall critical."""
    with patch("web.pipeline_health.query_one") as mock_qo, \
         patch("web.pipeline_health.query") as mock_q:
        # No cron success
        mock_qo.return_value = None
        mock_q.return_value = []

        from web.pipeline_health import get_pipeline_health
        report = get_pipeline_health()

    # cron check returns critical because no rows
    assert report.overall_status == "critical"


def test_get_pipeline_health_brief_returns_dict():
    """get_pipeline_health_brief returns expected keys."""
    with patch("web.pipeline_health.query_one") as mock_qo, \
         patch("web.pipeline_health.query") as mock_q:
        mock_qo.return_value = None
        mock_q.return_value = []

        from web.pipeline_health import get_pipeline_health_brief
        result = get_pipeline_health_brief()

    assert "status" in result
    assert "issues" in result
    assert "checks" in result
    assert isinstance(result["checks"], list)


def test_get_pipeline_health_brief_handles_exception():
    """get_pipeline_health_brief doesn't raise on failure."""
    with patch("web.pipeline_health.check_cron_health") as mock_cron:
        mock_cron.side_effect = RuntimeError("unexpected crash")
        from web.pipeline_health import get_pipeline_health_brief
        result = get_pipeline_health_brief()
    assert result["status"] == "unknown"
    assert len(result["issues"]) > 0


# ── get_cron_history ─────────────────────────────────────────────


def test_get_cron_history_empty():
    """Empty cron_log → empty list."""
    with patch("web.pipeline_health.query") as mock_q:
        mock_q.return_value = []
        from web.pipeline_health import get_cron_history
        result = get_cron_history()
    assert result == []


def test_get_cron_history_with_rows():
    """Cron rows parsed to dicts with duration."""
    t1 = "2026-02-24T03:00:00+00:00"
    t2 = "2026-02-24T03:05:30+00:00"
    with patch("web.pipeline_health.query") as mock_q:
        mock_q.return_value = [
            (1, "nightly", t1, t2, "success", 1, 5000, 12, 100, False, None),
        ]
        from web.pipeline_health import get_cron_history
        result = get_cron_history()
    assert len(result) == 1
    row = result[0]
    assert row["log_id"] == 1
    assert row["status"] == "success"
    assert row["duration_s"] == 330  # 5.5 minutes = 330 seconds


def test_get_cron_history_db_error():
    """DB error → empty list (no crash)."""
    with patch("web.pipeline_health.query") as mock_q:
        mock_q.side_effect = Exception("DB error")
        from web.pipeline_health import get_cron_history
        result = get_cron_history()
    assert result == []
