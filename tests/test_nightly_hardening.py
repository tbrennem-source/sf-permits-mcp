"""Tests for nightly_changes.py hardening — Sprint 53 Session C.

Tests fetch_with_retry, sweep_stuck_cron_jobs, and the hardened run_nightly.
No live DB or network required.
"""

from __future__ import annotations

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock, call


# ── fetch_with_retry ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_with_retry_success_first_attempt():
    """Success on first attempt — no retries needed."""
    from scripts.nightly_changes import fetch_with_retry

    async def factory():
        return [{"id": 1}, {"id": 2}]

    records, info = await fetch_with_retry(factory, step_name="test")

    assert records == [{"id": 1}, {"id": 2}]
    assert info["ok"] is True
    assert info["attempts"] == 1
    assert info["step"] == "test"
    assert info["elapsed_s"] >= 0


@pytest.mark.asyncio
async def test_fetch_with_retry_success_after_retry():
    """Fails first, succeeds on second attempt."""
    from scripts.nightly_changes import fetch_with_retry

    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Network blip")
        return [{"record": "ok"}]

    with patch("scripts.nightly_changes.asyncio") as mock_asyncio:
        # Mock asyncio.sleep to avoid actual sleeping
        mock_asyncio.sleep = AsyncMock()
        mock_asyncio.sleep.return_value = None
        # But we need real asyncio for gather/etc — patch only sleep
        pass

    # Use actual asyncio but with tiny base delay
    records, info = await fetch_with_retry(
        factory, step_name="test", max_retries=2, base_delay=0.001
    )

    assert records == [{"record": "ok"}]
    assert info["ok"] is True
    assert info["attempts"] == 2


@pytest.mark.asyncio
async def test_fetch_with_retry_all_attempts_fail():
    """All retries exhausted → returns empty list, ok=False."""
    from scripts.nightly_changes import fetch_with_retry

    async def factory():
        raise TimeoutError("Always fails")

    records, info = await fetch_with_retry(
        factory, step_name="test_fail", max_retries=2, base_delay=0.001
    )

    assert records == []
    assert info["ok"] is False
    assert info["attempts"] == 3  # 1 initial + 2 retries
    assert "error" in info
    assert "Always fails" in info["error"]


@pytest.mark.asyncio
async def test_fetch_with_retry_step_info_structure():
    """Info dict has expected keys."""
    from scripts.nightly_changes import fetch_with_retry

    async def factory():
        return []

    records, info = await fetch_with_retry(factory, step_name="myStep")

    assert "step" in info
    assert "ok" in info
    assert "attempts" in info
    assert "elapsed_s" in info
    assert "timed_out" in info
    assert info["step"] == "myStep"


@pytest.mark.asyncio
async def test_fetch_with_retry_zero_retries():
    """max_retries=0 → only one attempt total."""
    from scripts.nightly_changes import fetch_with_retry

    attempts = 0

    async def factory():
        nonlocal attempts
        attempts += 1
        raise ValueError("fail")

    records, info = await fetch_with_retry(
        factory, step_name="test", max_retries=0, base_delay=0.001
    )

    assert attempts == 1
    assert info["ok"] is False


# ── sweep_stuck_cron_jobs ────────────────────────────────────────


def test_sweep_stuck_cron_jobs_none_found():
    """No stuck jobs → returns 0."""
    with patch("scripts.nightly_changes.query") as mock_q, \
         patch("scripts.nightly_changes.execute_write") as mock_ew:
        mock_q.return_value = []
        from scripts.nightly_changes import sweep_stuck_cron_jobs
        result = sweep_stuck_cron_jobs()
    assert result == 0
    mock_ew.assert_not_called()


def test_sweep_stuck_cron_jobs_marks_failed():
    """Stuck job found → marks as failed via execute_write."""
    with patch("scripts.nightly_changes.query") as mock_q, \
         patch("scripts.nightly_changes.execute_write") as mock_ew:
        mock_q.return_value = [(99,), (100,)]
        from scripts.nightly_changes import sweep_stuck_cron_jobs
        result = sweep_stuck_cron_jobs()
    assert result == 2
    # execute_write called twice (once per stuck job)
    assert mock_ew.call_count == 2
    # Verify the update sets status='failed'
    first_call_sql = mock_ew.call_args_list[0][0][0]
    assert "failed" in first_call_sql
    assert "status" in first_call_sql


def test_sweep_stuck_cron_jobs_db_error_returns_zero():
    """DB error during sweep → returns 0, no crash."""
    with patch("scripts.nightly_changes.query") as mock_q:
        mock_q.side_effect = Exception("DB unavailable")
        from scripts.nightly_changes import sweep_stuck_cron_jobs
        result = sweep_stuck_cron_jobs()
    assert result == 0


# ── run_nightly hardened ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_nightly_returns_step_results():
    """run_nightly returns step_results dict in output."""
    with patch("scripts.nightly_changes.ensure_cron_log_table"), \
         patch("scripts.nightly_changes.sweep_stuck_cron_jobs", return_value=0), \
         patch("scripts.nightly_changes._compute_lookback", return_value=(1, False)), \
         patch("scripts.nightly_changes._log_cron_start", return_value=42), \
         patch("scripts.nightly_changes._log_cron_finish"), \
         patch("scripts.nightly_changes.SODAClient") as MockClient, \
         patch("scripts.nightly_changes.detect_changes", return_value=3), \
         patch("scripts.nightly_changes.upsert_inspections", return_value=5), \
         patch("scripts.nightly_changes.detect_addenda_changes", return_value=2), \
         patch("scripts.nightly_changes.fetch_recent_permits", new_callable=AsyncMock, return_value=[{"p": 1}]), \
         patch("scripts.nightly_changes.fetch_recent_inspections", new_callable=AsyncMock, return_value=[{"i": 1}]), \
         patch("scripts.nightly_changes.fetch_recent_addenda", new_callable=AsyncMock, return_value=[{"a": 1}]):

        # Mock client context
        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        MockClient.return_value = mock_client

        from scripts.nightly_changes import run_nightly
        result = await run_nightly(lookback_days=1, dry_run=False)

    assert "step_results" in result
    assert "swept_stuck_jobs" in result
    assert result["swept_stuck_jobs"] == 0
    assert result["changes_inserted"] == 3
    assert result["inspections_updated"] == 5
    assert result["addenda_inserted"] == 2


@pytest.mark.asyncio
async def test_run_nightly_addenda_failure_is_isolated():
    """Addenda step failure doesn't fail the whole run."""
    with patch("scripts.nightly_changes.ensure_cron_log_table"), \
         patch("scripts.nightly_changes.sweep_stuck_cron_jobs", return_value=0), \
         patch("scripts.nightly_changes._compute_lookback", return_value=(1, False)), \
         patch("scripts.nightly_changes._log_cron_start", return_value=1), \
         patch("scripts.nightly_changes._log_cron_finish"), \
         patch("scripts.nightly_changes.SODAClient") as MockClient, \
         patch("scripts.nightly_changes.detect_changes", return_value=0), \
         patch("scripts.nightly_changes.upsert_inspections", return_value=0), \
         patch("scripts.nightly_changes.detect_addenda_changes", side_effect=RuntimeError("addenda DB error")), \
         patch("scripts.nightly_changes.fetch_recent_permits", new_callable=AsyncMock, return_value=[]), \
         patch("scripts.nightly_changes.fetch_recent_inspections", new_callable=AsyncMock, return_value=[]), \
         patch("scripts.nightly_changes.fetch_recent_addenda", new_callable=AsyncMock, return_value=[{"a": 1}]):

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        MockClient.return_value = mock_client

        from scripts.nightly_changes import run_nightly
        # Should NOT raise despite addenda failure
        result = await run_nightly(lookback_days=1, dry_run=False)

    # Addenda failed but run succeeded
    assert result["addenda_inserted"] == 0
    # step_results should capture the detect_addenda failure
    step_errors = {k: v for k, v in result.get("step_results", {}).items() if isinstance(v, dict) and not v.get("ok", True)}
    assert len(step_errors) > 0


@pytest.mark.asyncio
async def test_run_nightly_inspection_failure_is_isolated():
    """Inspection step failure doesn't kill the whole run."""
    with patch("scripts.nightly_changes.ensure_cron_log_table"), \
         patch("scripts.nightly_changes.sweep_stuck_cron_jobs", return_value=0), \
         patch("scripts.nightly_changes._compute_lookback", return_value=(1, False)), \
         patch("scripts.nightly_changes._log_cron_start", return_value=1), \
         patch("scripts.nightly_changes._log_cron_finish"), \
         patch("scripts.nightly_changes.SODAClient") as MockClient, \
         patch("scripts.nightly_changes.detect_changes", return_value=5), \
         patch("scripts.nightly_changes.upsert_inspections", return_value=0), \
         patch("scripts.nightly_changes.detect_addenda_changes", return_value=0), \
         patch("scripts.nightly_changes.fetch_recent_permits", new_callable=AsyncMock, return_value=[{"p": 1}]), \
         patch("scripts.nightly_changes.fetch_recent_inspections", new_callable=AsyncMock, side_effect=ConnectionError("inspection API down")), \
         patch("scripts.nightly_changes.fetch_recent_addenda", new_callable=AsyncMock, return_value=[]):

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        MockClient.return_value = mock_client

        from scripts.nightly_changes import run_nightly
        result = await run_nightly(lookback_days=1, dry_run=False)

    assert result["changes_inserted"] == 5  # permits still processed


@pytest.mark.asyncio
async def test_run_nightly_includes_swept_count():
    """swept_stuck_jobs count appears in result."""
    with patch("scripts.nightly_changes.ensure_cron_log_table"), \
         patch("scripts.nightly_changes.sweep_stuck_cron_jobs", return_value=3), \
         patch("scripts.nightly_changes._compute_lookback", return_value=(1, False)), \
         patch("scripts.nightly_changes._log_cron_start", return_value=1), \
         patch("scripts.nightly_changes._log_cron_finish"), \
         patch("scripts.nightly_changes.SODAClient") as MockClient, \
         patch("scripts.nightly_changes.detect_changes", return_value=0), \
         patch("scripts.nightly_changes.upsert_inspections", return_value=0), \
         patch("scripts.nightly_changes.detect_addenda_changes", return_value=0), \
         patch("scripts.nightly_changes.fetch_recent_permits", new_callable=AsyncMock, return_value=[]), \
         patch("scripts.nightly_changes.fetch_recent_inspections", new_callable=AsyncMock, return_value=[]), \
         patch("scripts.nightly_changes.fetch_recent_addenda", new_callable=AsyncMock, return_value=[]):

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        MockClient.return_value = mock_client

        from scripts.nightly_changes import run_nightly
        result = await run_nightly(lookback_days=1, dry_run=False)

    assert result["swept_stuck_jobs"] == 3


# ── Constants ────────────────────────────────────────────────────


def test_hardening_constants_defined():
    """Hardening constants are present and reasonable."""
    from scripts.nightly_changes import MAX_FETCH_RETRIES, RETRY_BASE_DELAY_S, STEP_TIMEOUT_S
    assert MAX_FETCH_RETRIES >= 2
    assert RETRY_BASE_DELAY_S > 0
    assert STEP_TIMEOUT_S >= 60  # at least 1 minute
