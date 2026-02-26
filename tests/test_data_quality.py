"""Tests for web.data_quality check functions.

Mocks _timed_query and _raw_query to test threshold logic without a live DB.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────

def _mock_raw(return_val):
    """Create a mock for _raw_query that returns *return_val*."""
    return patch("web.data_quality._raw_query", return_value=return_val)


def _mock_timed(return_val):
    """Create a mock for _timed_query that returns *return_val*."""
    return patch("web.data_quality._timed_query", return_value=return_val)


# ── _check_orphaned_contacts ─────────────────────────────────────


class TestOrphanedContacts:
    """Orphaned contacts check: contacts without resolved entities."""

    def test_green_when_below_5pct(self):
        from web.data_quality import _check_orphaned_contacts

        # 2% orphaned (20 of 1000)
        with _mock_timed([(20,)]) as mq:
            with _mock_timed([(1000,)]):
                # Need to handle two calls — first for orphans, second for total
                pass

        # Simpler: patch once, use side_effect
        with patch("web.data_quality._timed_query", side_effect=[[(20,)], [(1000,)]]):
            result = _check_orphaned_contacts()
        assert result["status"] == "green"
        assert result["name"] == "Unresolved Contacts"

    def test_yellow_between_5_and_10pct(self):
        from web.data_quality import _check_orphaned_contacts

        # 8% orphaned (80 of 1000)
        with patch("web.data_quality._timed_query", side_effect=[[(80,)], [(1000,)]]):
            result = _check_orphaned_contacts()
        assert result["status"] == "yellow"

    def test_red_above_10pct(self):
        from web.data_quality import _check_orphaned_contacts

        # 15% orphaned (150 of 1000)
        with patch("web.data_quality._timed_query", side_effect=[[(150,)], [(1000,)]]):
            result = _check_orphaned_contacts()
        assert result["status"] == "red"


# ── _check_rag_chunk_count ───────────────────────────────────────


class TestRagChunkCount:
    """RAG chunk count check: dynamic baseline from cache."""

    def test_green_stable_count(self):
        from web.data_quality import _check_rag_chunk_count

        # Count = 1050, no duplicates, no cache (uses self-baseline)
        with patch("web.data_quality._raw_query", side_effect=[
            [(1050,)],    # total count
            [(1050,)],    # distinct count
            [],           # no cache
        ]):
            result = _check_rag_chunk_count()
        assert result["status"] == "green"
        assert "1,050" in result["value"]

    def test_red_when_duplicates_exceed_50(self):
        from web.data_quality import _check_rag_chunk_count

        # 1200 total, 1100 distinct = 100 duplicates
        with patch("web.data_quality._raw_query", side_effect=[
            [(1200,)],    # total count
            [(1100,)],    # distinct count
            [],           # no cache
        ]):
            result = _check_rag_chunk_count()
        assert result["status"] == "red"
        assert "duplicates" in result["detail"]

    def test_red_when_count_drops_below_70pct(self):
        """If count drops >30% from cached baseline → red."""
        import json
        from web.data_quality import _check_rag_chunk_count

        cached = json.dumps([{"name": "RAG Chunks", "value": "1,000"}])
        with patch("web.data_quality._raw_query", side_effect=[
            [(600,)],      # total count (60% of 1000)
            [(600,)],      # distinct count
            [(cached,)],   # cache with previous value
        ]):
            result = _check_rag_chunk_count()
        assert result["status"] == "red"
        assert "data loss" in result["detail"]

    def test_zero_chunks_is_red(self):
        from web.data_quality import _check_rag_chunk_count

        with patch("web.data_quality._raw_query", side_effect=[
            [(0,)],
            [(0,)],
            [],
        ]):
            result = _check_rag_chunk_count()
        assert result["status"] == "red"


# ── _check_addenda_freshness ────────────────────────────────────


class TestAddendaFreshness:
    """Addenda freshness: age of most recent finish_date."""

    def test_green_when_recent(self):
        from web.data_quality import _check_addenda_freshness

        recent = date.today() - timedelta(days=5)
        with _mock_raw([(str(recent),)]):
            result = _check_addenda_freshness()
        assert result["status"] == "green"
        assert result["name"] == "Addenda Freshness"

    def test_yellow_30_to_60_days(self):
        from web.data_quality import _check_addenda_freshness

        old = date.today() - timedelta(days=45)
        with _mock_raw([(str(old),)]):
            result = _check_addenda_freshness()
        assert result["status"] == "yellow"

    def test_red_over_60_days(self):
        from web.data_quality import _check_addenda_freshness

        very_old = date.today() - timedelta(days=90)
        with _mock_raw([(str(very_old),)]):
            result = _check_addenda_freshness()
        assert result["status"] == "red"

    def test_table_not_exists(self):
        from web.data_quality import _check_addenda_freshness

        with patch("web.data_quality._raw_query", side_effect=Exception("relation does not exist")):
            result = _check_addenda_freshness()
        assert result["status"] == "yellow"
        assert "not available" in result["detail"]

    def test_no_data(self):
        from web.data_quality import _check_addenda_freshness

        with _mock_raw([(None,)]):
            result = _check_addenda_freshness()
        assert result["status"] == "red"


# ── _check_station_velocity_freshness ────────────────────────────


class TestStationVelocityFreshness:
    """Station velocity freshness: age of computed_at."""

    def test_green_when_recent(self):
        from web.data_quality import _check_station_velocity_freshness

        recent = date.today() - timedelta(days=2)
        with _mock_raw([(str(recent),)]):
            result = _check_station_velocity_freshness()
        assert result["status"] == "green"
        assert result["name"] == "Station Velocity"

    def test_yellow_7_to_14_days(self):
        from web.data_quality import _check_station_velocity_freshness

        old = date.today() - timedelta(days=10)
        with _mock_raw([(str(old),)]):
            result = _check_station_velocity_freshness()
        assert result["status"] == "yellow"

    def test_red_over_14_days(self):
        from web.data_quality import _check_station_velocity_freshness

        very_old = date.today() - timedelta(days=20)
        with _mock_raw([(str(very_old),)]):
            result = _check_station_velocity_freshness()
        assert result["status"] == "red"

    def test_table_not_exists(self):
        from web.data_quality import _check_station_velocity_freshness

        with patch("web.data_quality._raw_query", side_effect=Exception("relation does not exist")):
            result = _check_station_velocity_freshness()
        assert result["status"] == "yellow"
        assert "not available" in result["detail"]


# ── run_all_checks ───────────────────────────────────────────────


class TestRunAllChecks:
    """Integration test for run_all_checks."""

    def test_sorts_red_first(self):
        from web.data_quality import run_all_checks

        # Mock BACKEND to skip prod checks and mock all universal checks
        with patch("src.db.BACKEND", "duckdb"):
            with patch("web.data_quality._timed_query", return_value=[(0,)]):
                results = run_all_checks()
        # Results should be sorted: red first, yellow, green
        statuses = [r["status"] for r in results]
        status_values = {"red": 0, "yellow": 1, "green": 2}
        assert statuses == sorted(statuses, key=lambda s: status_values.get(s, 9))

    def test_check_failure_produces_error_entry(self):
        from web.data_quality import run_all_checks

        with patch("src.db.BACKEND", "duckdb"):
            with patch("web.data_quality._timed_query", side_effect=Exception("boom")):
                results = run_all_checks()
        # Should have error entries, not crash
        assert len(results) > 0
        error_results = [r for r in results if r["value"] == "Error"]
        assert len(error_results) > 0
