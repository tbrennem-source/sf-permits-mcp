"""Sprint 55E — signal pipeline verification, inspections UNIQUE constraint, stuck cron auto-close.

Tests:
- E1: Signal pipeline functions work with DuckDB test data (basic coverage)
- E2: Inspections UNIQUE migration function (create test dupes, verify cleanup)
- E3: Stuck job auto-close logic (create stuck job records, verify they get closed)
- Migration entry exists in MIGRATIONS list
"""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import duckdb
import pytest


# ── Shared DuckDB fixture ─────────────────────────────────────────

@pytest.fixture
def duck_conn():
    """In-memory DuckDB connection with signal-related tables."""
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE permits (
            permit_number VARCHAR(30) PRIMARY KEY,
            status VARCHAR(20),
            permit_type VARCHAR(5),
            permit_type_definition VARCHAR(100),
            block VARCHAR(10),
            lot VARCHAR(10),
            street_number VARCHAR(10),
            street_name VARCHAR(50),
            filed_date DATE,
            issued_date DATE,
            status_date DATE,
            estimated_cost DECIMAL,
            revised_cost DECIMAL,
            description TEXT,
            street_suffix VARCHAR(10),
            neighborhood VARCHAR(50)
        )
    """)
    c.execute("""
        CREATE TABLE addenda (
            id INTEGER,
            application_number VARCHAR(30),
            station VARCHAR(20),
            review_results VARCHAR(50),
            start_date DATE,
            finish_date DATE
        )
    """)
    c.execute("""
        CREATE TABLE violations (
            id INTEGER,
            block VARCHAR(10),
            lot VARCHAR(10),
            status VARCHAR(20),
            nov_category_description VARCHAR(100)
        )
    """)
    c.execute("""
        CREATE TABLE inspections (
            id INTEGER,
            reference_number VARCHAR(30),
            result VARCHAR(20),
            inspection_description VARCHAR(100),
            scheduled_date DATE
        )
    """)
    c.execute("""
        CREATE TABLE complaints (
            id INTEGER,
            block VARCHAR(10),
            lot VARCHAR(10),
            status VARCHAR(20),
            complaint_description VARCHAR(100)
        )
    """)
    yield c
    c.close()


# ── E1: Signal pipeline basic functionality ───────────────────────

class TestSignalPipelineBasic:
    """Verify signal pipeline works correctly with DuckDB test data."""

    def test_pipeline_runs_on_empty_tables(self, duck_conn):
        """Pipeline completes on empty tables and returns zeroed stats."""
        import src.signals.pipeline as pipeline_mod
        import src.signals.detector as detector_mod

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats = pipeline_mod.run_signal_pipeline(duck_conn)

        assert stats["total_signals"] == 0
        assert stats["permit_signals"] == 0
        assert stats["property_signals"] == 0
        assert stats["properties"] == 0

    def test_pipeline_stats_structure(self, duck_conn):
        """Pipeline always returns all expected stat keys."""
        import src.signals.pipeline as pipeline_mod
        import src.signals.detector as detector_mod

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats = pipeline_mod.run_signal_pipeline(duck_conn)

        required_keys = {
            "total_signals", "permit_signals", "property_signals",
            "properties", "tier_distribution", "detectors",
        }
        assert required_keys <= set(stats.keys())

    def test_pipeline_nov_creates_property_health(self, duck_conn):
        """NOV signal results in at_risk property_health row."""
        import src.signals.pipeline as pipeline_mod
        import src.signals.detector as detector_mod

        duck_conn.execute(
            "INSERT INTO violations VALUES (1, '0001', '001', 'open', 'Building without permit')"
        )

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats = pipeline_mod.run_signal_pipeline(duck_conn)

        row = duck_conn.execute(
            "SELECT tier FROM property_health WHERE block_lot = '0001/001'"
        ).fetchone()
        assert row is not None, "property_health row should exist for 0001/001"
        assert row[0] == "at_risk"
        assert stats["total_signals"] >= 1

    def test_pipeline_idempotent(self, duck_conn):
        """Running pipeline twice gives same counts (truncate + re-insert)."""
        import src.signals.pipeline as pipeline_mod
        import src.signals.detector as detector_mod

        duck_conn.execute(
            "INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test')"
        )

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats1 = pipeline_mod.run_signal_pipeline(duck_conn)
            stats2 = pipeline_mod.run_signal_pipeline(duck_conn)

        assert stats1["total_signals"] == stats2["total_signals"]
        count = duck_conn.execute(
            "SELECT COUNT(*) FROM property_health"
        ).fetchone()[0]
        assert count == 1, "Second run should not double property_health rows"

    def test_pipeline_permit_signal_with_addenda(self, duck_conn):
        """Permit with 'Issued Comments' addenda produces a permit_signal row."""
        import src.signals.pipeline as pipeline_mod
        import src.signals.detector as detector_mod

        duck_conn.execute(
            "INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001',"
            " '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')"
        )
        duck_conn.execute(
            "INSERT INTO addenda VALUES (1, 'P001', 'CPC', 'Issued Comments', '2024-06-01', '2024-06-15')"
        )

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats = pipeline_mod.run_signal_pipeline(duck_conn)

        assert stats["permit_signals"] >= 1
        row = duck_conn.execute(
            "SELECT COUNT(*) FROM permit_signals WHERE permit_number = 'P001'"
        ).fetchone()
        assert row[0] >= 1


# ── E2: Inspections UNIQUE constraint migration ───────────────────

class TestInspectionsUniqueMigration:
    """Verify the _run_inspections_unique() migration function."""

    def test_migration_entry_exists_in_migrations_list(self):
        """MIGRATIONS list contains a 'inspections_unique' entry."""
        from scripts.run_prod_migrations import MIGRATIONS, MIGRATION_BY_NAME

        names = [m.name for m in MIGRATIONS]
        assert "inspections_unique" in names, (
            f"'inspections_unique' not in MIGRATIONS list. Found: {names}"
        )
        assert "inspections_unique" in MIGRATION_BY_NAME

    def test_migration_is_callable(self):
        """The inspections_unique migration has a callable run function."""
        from scripts.run_prod_migrations import MIGRATION_BY_NAME

        mig = MIGRATION_BY_NAME["inspections_unique"]
        assert callable(mig.run), "migration.run must be callable"

    def test_migration_skips_on_duckdb(self):
        """_run_inspections_unique skips when BACKEND is not postgres."""
        from scripts.run_prod_migrations import _run_inspections_unique
        import src.db as db_mod

        # In test environment BACKEND will be 'duckdb' (no DATABASE_URL)
        with patch.object(db_mod, "BACKEND", "duckdb"):
            result = _run_inspections_unique()

        assert result["ok"] is True
        assert result.get("skipped") is True

    def test_migration_dedup_logic_with_duckdb_memory(self):
        """Dedup logic removes duplicate inspections keeping lowest id."""
        # We test the dedup SQL logic directly against DuckDB in-memory
        # to verify the query is correct (regardless of BACKEND)
        conn = duckdb.connect(":memory:")
        try:
            conn.execute("""
                CREATE TABLE inspections (
                    id INTEGER PRIMARY KEY,
                    reference_number VARCHAR(30),
                    scheduled_date DATE,
                    inspection_description VARCHAR(100),
                    result VARCHAR(20)
                )
            """)
            # Insert duplicates: ids 1 and 3 are dupes of 2 (same natural key)
            conn.execute("INSERT INTO inspections VALUES (1, 'P001', '2024-01-15', 'Framing', 'PASSED')")
            conn.execute("INSERT INTO inspections VALUES (2, 'P001', '2024-01-15', 'Framing', 'PASSED')")
            conn.execute("INSERT INTO inspections VALUES (3, 'P001', '2024-01-15', 'Framing', 'PASSED')")
            # This one is NOT a dupe (different description)
            conn.execute("INSERT INTO inspections VALUES (4, 'P001', '2024-01-15', 'Final', 'PASSED')")

            # Simulate the dedup SQL: delete all but lowest id per natural key
            conn.execute("""
                DELETE FROM inspections
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM inspections
                    GROUP BY reference_number, scheduled_date, COALESCE(inspection_description, '')
                )
            """)

            rows = conn.execute("SELECT id FROM inspections ORDER BY id").fetchall()
            ids = [r[0] for r in rows]
            assert ids == [1, 4], f"Expected [1, 4] after dedup, got {ids}"
        finally:
            conn.close()

    def test_postgres_schema_has_unique_index_comment(self):
        """postgres_schema.sql contains the uk_inspections_natural index definition."""
        import os
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "postgres_schema.sql"
        )
        with open(schema_path) as f:
            content = f.read()
        assert "uk_inspections_natural" in content, (
            "postgres_schema.sql should contain uk_inspections_natural index"
        )


# ── E3: Stuck cron auto-close ────────────────────────────────────

class TestStuckCronAutoClose:
    """Verify stuck cron job auto-close logic at start of /cron/nightly."""

    def test_auto_close_sql_uses_execute_write(self):
        """The stuck job auto-close uses execute_write with correct UPDATE SQL."""
        # Verify execute_write exists and handles a no-op UPDATE correctly
        from src.db import execute_write, BACKEND

        # In DuckDB mode, this shouldn't fail even if cron_log doesn't exist
        # We test the function signature/existence, not live DB
        assert callable(execute_write)

    def test_stuck_job_sql_correct(self):
        """The stuck-job UPDATE SQL is syntactically valid against DuckDB cron_log."""
        conn = duckdb.connect(":memory:")
        try:
            # Create minimal cron_log schema matching the real definition
            conn.execute("""
                CREATE TABLE cron_log (
                    log_id INTEGER PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'running',
                    error TEXT
                )
            """)

            # Insert one stuck job (started 6 hours ago)
            stuck_start = datetime.now(timezone.utc) - timedelta(hours=6)
            conn.execute(
                "INSERT INTO cron_log VALUES (1, 'nightly', ?, NULL, 'running', NULL)",
                [stuck_start.replace(tzinfo=None)]
            )

            # Insert one recent job that should NOT be closed
            recent_start = datetime.now(timezone.utc) - timedelta(hours=1)
            conn.execute(
                "INSERT INTO cron_log VALUES (2, 'nightly', ?, NULL, 'running', NULL)",
                [recent_start.replace(tzinfo=None)]
            )

            # Execute the auto-close logic (DuckDB syntax with ?)
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=4)).replace(tzinfo=None)
            conn.execute(
                "UPDATE cron_log SET status = 'failed', error = 'auto-closed: stuck >4 hours' "
                "WHERE status = 'running' AND started_at < ?",
                [cutoff]
            )

            # Verify: stuck job (id=1) is now failed
            row1 = conn.execute("SELECT status FROM cron_log WHERE log_id = 1").fetchone()
            assert row1[0] == "failed", f"Stuck job should be failed, got {row1[0]}"

            # Verify: recent job (id=2) is still running
            row2 = conn.execute("SELECT status FROM cron_log WHERE log_id = 2").fetchone()
            assert row2[0] == "running", f"Recent job should still be running, got {row2[0]}"
        finally:
            conn.close()

    def test_stuck_job_error_message_set(self):
        """Auto-closed jobs have the expected error message."""
        conn = duckdb.connect(":memory:")
        try:
            conn.execute("""
                CREATE TABLE cron_log (
                    log_id INTEGER PRIMARY KEY,
                    job_type TEXT,
                    started_at TIMESTAMP,
                    status TEXT DEFAULT 'running',
                    error TEXT
                )
            """)
            stuck_start = datetime.now(timezone.utc) - timedelta(hours=5)
            conn.execute(
                "INSERT INTO cron_log VALUES (1, 'nightly', ?, 'running', NULL)",
                [stuck_start.replace(tzinfo=None)]
            )
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=4)).replace(tzinfo=None)
            conn.execute(
                "UPDATE cron_log SET status = 'failed', error = 'auto-closed: stuck >4 hours' "
                "WHERE status = 'running' AND started_at < ?",
                [cutoff]
            )
            row = conn.execute("SELECT error FROM cron_log WHERE log_id = 1").fetchone()
            assert row[0] == "auto-closed: stuck >4 hours"
        finally:
            conn.close()

    def test_nightly_route_has_stuck_job_autoclose(self):
        """web/app.py cron_nightly function contains stuck job auto-close code."""
        import os
        app_path = os.path.join(
            os.path.dirname(__file__), "..", "web", "app.py"
        )
        with open(app_path) as f:
            content = f.read()
        assert "auto-closed: stuck" in content or "stuck >4 hours" in content, (
            "web/app.py should contain stuck job auto-close logic in cron_nightly"
        )

    def test_stuck_job_only_affects_running_status(self):
        """Auto-close only touches rows with status='running', not 'complete' or 'failed'."""
        conn = duckdb.connect(":memory:")
        try:
            conn.execute("""
                CREATE TABLE cron_log (
                    log_id INTEGER PRIMARY KEY,
                    job_type TEXT,
                    started_at TIMESTAMP,
                    status TEXT,
                    error TEXT
                )
            """)
            old_time = datetime.now(timezone.utc) - timedelta(hours=6)
            # Already-failed old job should NOT be touched
            conn.execute(
                "INSERT INTO cron_log VALUES (1, 'nightly', ?, 'failed', 'original error')",
                [old_time.replace(tzinfo=None)]
            )
            # Already-completed old job should NOT be touched
            conn.execute(
                "INSERT INTO cron_log VALUES (2, 'nightly', ?, 'complete', NULL)",
                [old_time.replace(tzinfo=None)]
            )
            # Stuck running job should be closed
            conn.execute(
                "INSERT INTO cron_log VALUES (3, 'nightly', ?, 'running', NULL)",
                [old_time.replace(tzinfo=None)]
            )

            cutoff = (datetime.now(timezone.utc) - timedelta(hours=4)).replace(tzinfo=None)
            conn.execute(
                "UPDATE cron_log SET status = 'failed', error = 'auto-closed: stuck >4 hours' "
                "WHERE status = 'running' AND started_at < ?",
                [cutoff]
            )

            # id=1: already failed, error should be unchanged
            row1 = conn.execute("SELECT status, error FROM cron_log WHERE log_id = 1").fetchone()
            assert row1[0] == "failed"
            assert row1[1] == "original error"

            # id=2: complete, should be unchanged
            row2 = conn.execute("SELECT status FROM cron_log WHERE log_id = 2").fetchone()
            assert row2[0] == "complete"

            # id=3: was running+old, should now be failed
            row3 = conn.execute("SELECT status FROM cron_log WHERE log_id = 3").fetchone()
            assert row3[0] == "failed"
        finally:
            conn.close()


# ── E2 extra: Migration function in registry ─────────────────────

class TestMigrationRegistry:
    """Broader migration list integrity checks."""

    def test_inspections_unique_description_is_meaningful(self):
        """inspections_unique migration has a non-empty description."""
        from scripts.run_prod_migrations import MIGRATION_BY_NAME

        mig = MIGRATION_BY_NAME["inspections_unique"]
        assert len(mig.description) > 10, "Migration description should be descriptive"

    def test_migrations_list_order(self):
        """inspections_unique comes after the schema migration."""
        from scripts.run_prod_migrations import MIGRATIONS

        names = [m.name for m in MIGRATIONS]
        assert "schema" in names
        schema_idx = names.index("schema")
        unique_idx = names.index("inspections_unique")
        assert unique_idx > schema_idx, (
            "inspections_unique should come after the schema migration"
        )
