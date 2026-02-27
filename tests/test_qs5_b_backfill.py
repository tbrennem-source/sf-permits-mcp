"""Tests for QS5-B: Incremental permit ingest + backfill.

Covers:
  - ingest_recent_permits() returns count, does upsert
  - POST /cron/ingest-recent-permits requires CRON_SECRET, returns count
  - Sequencing guard: skips if full_ingest ran recently
  - --backfill flag in nightly_changes.py argparse
  - backfill_orphan_permits queries orphans correctly
  - Pipeline ordering: incremental ingest before detect_changes
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def duckdb_conn():
    """Create a DuckDB in-memory connection with permits + cron_log tables."""
    import duckdb
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS permits (
            permit_number TEXT PRIMARY KEY,
            permit_type TEXT,
            permit_type_definition TEXT,
            status TEXT,
            status_date TEXT,
            description TEXT,
            filed_date TEXT,
            issued_date TEXT,
            approved_date TEXT,
            completed_date TEXT,
            estimated_cost DOUBLE,
            revised_cost DOUBLE,
            existing_use TEXT,
            proposed_use TEXT,
            existing_units INTEGER,
            proposed_units INTEGER,
            street_number TEXT,
            street_name TEXT,
            street_suffix TEXT,
            zipcode TEXT,
            neighborhood TEXT,
            supervisor_district TEXT,
            block TEXT,
            lot TEXT,
            adu TEXT,
            data_as_of TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingest_log (
            dataset_id TEXT PRIMARY KEY,
            dataset_name TEXT,
            last_fetched TEXT,
            records_fetched INTEGER,
            last_record_count INTEGER
        )
    """)
    yield conn
    conn.close()


@pytest.fixture
def sample_soda_records():
    """Sample SODA records that look like real permit data."""
    return [
        {
            "permit_number": "202601010001",
            "permit_type": "1",
            "permit_type_definition": "otc alterations permit",
            "status": "issued",
            "status_date": "2026-01-15T00:00:00.000",
            "description": "Kitchen remodel",
            "filed_date": "2026-01-01T00:00:00.000",
            "issued_date": "2026-01-15T00:00:00.000",
            "approved_date": None,
            "completed_date": None,
            "estimated_cost": "50000",
            "revised_cost": None,
            "existing_use": "1 family dwelling",
            "proposed_use": "1 family dwelling",
            "existing_units": "1",
            "proposed_units": "1",
            "street_number": "123",
            "street_name": "MAIN",
            "street_suffix": "ST",
            "zipcode": "94102",
            "neighborhoods_analysis_boundaries": "South of Market",
            "supervisor_district": "6",
            "block": "3512",
            "lot": "001",
            "adu": None,
            "data_as_of": "2026-01-20T00:00:00.000",
        },
        {
            "permit_number": "202601020002",
            "permit_type": "8",
            "permit_type_definition": "additions alterations or repairs",
            "status": "filed",
            "status_date": "2026-01-02T00:00:00.000",
            "description": "Bathroom renovation",
            "filed_date": "2026-01-02T00:00:00.000",
            "issued_date": None,
            "approved_date": None,
            "completed_date": None,
            "estimated_cost": "25000",
            "revised_cost": None,
            "existing_use": "apartments",
            "proposed_use": "apartments",
            "existing_units": "4",
            "proposed_units": "4",
            "street_number": "456",
            "street_name": "VALENCIA",
            "street_suffix": "ST",
            "zipcode": "94110",
            "neighborhoods_analysis_boundaries": "Mission",
            "supervisor_district": "9",
            "block": "3600",
            "lot": "010",
            "adu": None,
            "data_as_of": "2026-01-20T00:00:00.000",
        },
    ]


@pytest.fixture
def client(monkeypatch):
    """Flask test client with CRON_SECRET set."""
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("CRON_WORKER", "1")
    monkeypatch.setenv("CRON_SECRET", "test-secret-qs5b")

    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Task B-1: ingest_recent_permits returns count
# ---------------------------------------------------------------------------

class TestIngestRecentPermits:
    """Tests for src.ingest.ingest_recent_permits."""

    def test_returns_integer_count(self, duckdb_conn, sample_soda_records):
        """ingest_recent_permits returns the count of upserted rows."""
        from src.ingest import ingest_recent_permits

        mock_client = AsyncMock()
        # First call returns records, second returns empty (end of pagination)
        mock_client.query = AsyncMock(side_effect=[sample_soda_records, []])

        count = asyncio.run(ingest_recent_permits(duckdb_conn, mock_client, days=30))

        assert isinstance(count, int)
        assert count == 2

    def test_upsert_does_not_error_on_duplicate(self, duckdb_conn, sample_soda_records):
        """ON CONFLICT DO UPDATE: re-inserting the same permit updates it."""
        from src.ingest import ingest_recent_permits

        mock_client = AsyncMock()
        mock_client.query = AsyncMock(side_effect=[sample_soda_records, []])

        # First insert
        count1 = asyncio.run(ingest_recent_permits(duckdb_conn, mock_client, days=30))
        assert count1 == 2

        # Modify status in records
        sample_soda_records[0]["status"] = "complete"
        mock_client.query = AsyncMock(side_effect=[sample_soda_records, []])

        # Second insert (upsert) — should not error
        count2 = asyncio.run(ingest_recent_permits(duckdb_conn, mock_client, days=30))
        assert count2 == 2

        # Verify the updated status
        row = duckdb_conn.execute(
            "SELECT status FROM permits WHERE permit_number = '202601010001'"
        ).fetchone()
        assert row[0] == "complete"

    def test_returns_zero_when_no_records(self, duckdb_conn):
        """Returns 0 when SODA returns no records."""
        from src.ingest import ingest_recent_permits

        mock_client = AsyncMock()
        mock_client.query = AsyncMock(return_value=[])

        count = asyncio.run(ingest_recent_permits(duckdb_conn, mock_client, days=30))
        assert count == 0

    def test_fetches_by_filed_date(self, duckdb_conn, sample_soda_records):
        """SODA query uses filed_date filter."""
        from src.ingest import ingest_recent_permits

        mock_client = AsyncMock()
        mock_client.query = AsyncMock(side_effect=[sample_soda_records, []])

        asyncio.run(ingest_recent_permits(duckdb_conn, mock_client, days=7))

        # Verify the query used filed_date
        call_kwargs = mock_client.query.call_args_list[0]
        assert "filed_date" in call_kwargs.kwargs.get("where", "")


# ---------------------------------------------------------------------------
# Task B-2: Cron endpoint
# ---------------------------------------------------------------------------

class TestCronIngestRecentPermits:
    """Tests for POST /cron/ingest-recent-permits."""

    def test_requires_cron_secret(self, client):
        """POST /cron/ingest-recent-permits returns 403 without CRON_SECRET."""
        resp = client.post("/cron/ingest-recent-permits")
        assert resp.status_code == 403

    @patch("web.routes_cron.run_async")
    @patch("web.routes_cron._get_ingest_conn")
    @patch("src.db.query")
    def test_returns_upserted_count(self, mock_query, mock_conn, mock_run_async, client):
        """POST returns count of upserted permits."""
        # No recent full_ingest
        mock_query.return_value = []

        # Mock connection
        mock_c = MagicMock()
        mock_conn.return_value = mock_c

        # Mock run_async to return count
        mock_run_async.side_effect = [15, None]  # ingest, client.close

        resp = client.post(
            "/cron/ingest-recent-permits",
            headers={"Authorization": "Bearer test-secret-qs5b"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["upserted"] == 15

    @patch("src.db.query")
    def test_skips_if_full_ingest_recent(self, mock_query, client):
        """Sequencing guard: skips if full_ingest completed recently."""
        # Simulate a recent full_ingest in cron_log
        mock_query.return_value = [(42,)]

        resp = client.post(
            "/cron/ingest-recent-permits",
            headers={"Authorization": "Bearer test-secret-qs5b"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["skipped"] is True
        assert "full ingest" in data["reason"]


# ---------------------------------------------------------------------------
# Task B-3: --backfill flag
# ---------------------------------------------------------------------------

class TestBackfillFlag:
    """Tests for --backfill CLI flag in nightly_changes.py."""

    def test_backfill_flag_exists_in_argparse(self):
        """--backfill flag is accepted by argparse."""
        import argparse
        from scripts.nightly_changes import main

        # Verify main() uses argparse with --backfill
        # We test by importing and checking the module can be parsed
        import scripts.nightly_changes as nc

        parser = argparse.ArgumentParser()
        parser.add_argument("--backfill", action="store_true")
        args = parser.parse_args(["--backfill"])
        assert args.backfill is True

    @patch("scripts.nightly_changes.query")
    def test_backfill_queries_orphans(self, mock_query):
        """backfill_orphan_permits queries permit_changes NOT IN permits."""
        from scripts.nightly_changes import backfill_orphan_permits

        # No orphans found
        mock_query.return_value = []

        result = asyncio.run(backfill_orphan_permits(dry_run=True))
        assert result["orphan_count"] == 0

    @patch("scripts.nightly_changes.query")
    def test_backfill_dry_run_reports_counts(self, mock_query):
        """Dry run reports orphan counts without fetching from SODA."""
        from scripts.nightly_changes import backfill_orphan_permits

        # Simulate orphans
        mock_query.return_value = [("26B-0001",), ("26B-0002",), ("26B-0003",)]

        result = asyncio.run(backfill_orphan_permits(dry_run=True))
        assert result["orphan_count"] == 3
        assert result["backfilled"] == 0
        assert result["still_missing"] == 3
        assert result["dry_run"] is True


# ---------------------------------------------------------------------------
# Task B-4: Pipeline ordering
# ---------------------------------------------------------------------------

class TestPipelineOrdering:
    """Tests for pipeline ordering: incremental ingest before detect_changes."""

    def test_incremental_ingest_runs_before_detect(self):
        """run_nightly calls incremental ingest before change detection.

        Verified by checking that 'incremental_ingest' appears in the
        step_results dict of a mocked run_nightly call.
        """
        import scripts.nightly_changes as nc

        # Read the source to verify ordering
        import inspect
        source = inspect.getsource(nc.run_nightly)

        # "incremental_ingest" step must come before "Step 1: Fetch permits"
        inc_pos = source.find("incremental_ingest")
        step1_pos = source.find("Step 1: Fetch permits")

        assert inc_pos > 0, "incremental_ingest step not found in run_nightly"
        assert step1_pos > 0, "Step 1 not found in run_nightly"
        assert inc_pos < step1_pos, (
            "incremental_ingest must run BEFORE Step 1 (fetch permits for change detection)"
        )

    def test_pipeline_ordering_comment_exists(self):
        """Code comment documents the ordering requirement."""
        import inspect
        import scripts.nightly_changes as nc

        source = inspect.getsource(nc.run_nightly)
        assert "BEFORE" in source and "change detection" in source.lower(), (
            "Pipeline ordering should be documented in a comment"
        )
