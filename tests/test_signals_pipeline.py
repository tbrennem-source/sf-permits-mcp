"""Tests for the dual-backend helpers in src.signals.pipeline and src.signals.detector.

Covers:
- _pg_execute: placeholder conversion and connection dispatch for both backends
- _pg_fetchall: placeholder conversion and row fetch for both backends
- _ensure_signal_tables: skips on postgres backend
- run_signal_pipeline: end-to-end DuckDB integration
- detector._execute: handles both backends
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call
from datetime import date, timedelta

import pytest
import duckdb

import src.signals.pipeline as pipeline_mod
import src.signals.detector as detector_mod

from src.signals.pipeline import (
    _pg_execute,
    _pg_fetchall,
    _ensure_signal_tables,
    run_signal_pipeline,
)
from src.signals.detector import _execute as detector_execute


# ── Shared DuckDB fixture ─────────────────────────────────────────

@pytest.fixture
def duck_conn():
    """In-memory DuckDB connection with the base data tables."""
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


# ── _pg_execute (DuckDB backend) ──────────────────────────────────

class TestPgExecuteDuckDB:
    def test_no_params_executes(self, duck_conn):
        """_pg_execute with no params runs the SQL on DuckDB."""
        duck_conn.execute("CREATE TABLE _test_exec (x INTEGER)")
        _pg_execute(duck_conn, "INSERT INTO _test_exec VALUES (42)")
        row = duck_conn.execute("SELECT x FROM _test_exec").fetchone()
        assert row[0] == 42

    def test_with_params_executes(self, duck_conn):
        """_pg_execute with ? params passes them through on DuckDB."""
        duck_conn.execute("CREATE TABLE _test_params (x INTEGER, y TEXT)")
        _pg_execute(duck_conn, "INSERT INTO _test_params VALUES (?, ?)", (7, "hello"))
        row = duck_conn.execute("SELECT x, y FROM _test_params").fetchone()
        assert row == (7, "hello")


# ── _pg_execute (Postgres mock backend) ──────────────────────────

class TestPgExecutePostgres:
    def test_converts_question_marks_to_percent_s(self):
        """On postgres backend, ? is replaced with %s before execution."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(pipeline_mod, "BACKEND", "postgres"):
            _pg_execute(mock_conn, "INSERT INTO t VALUES (?, ?)", ("a", "b"))

        mock_cursor.execute.assert_called_once_with(
            "INSERT INTO t VALUES (%s, %s)", ("a", "b")
        )
        mock_conn.commit.assert_called_once()

    def test_no_placeholder_no_conversion(self):
        """SQL with no ? placeholders passes through unchanged."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(pipeline_mod, "BACKEND", "postgres"):
            _pg_execute(mock_conn, "DELETE FROM signal_types", None)

        mock_cursor.execute.assert_called_once_with("DELETE FROM signal_types", None)
        mock_conn.commit.assert_called_once()

    def test_commit_called(self):
        """commit() is called after execute on postgres."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(pipeline_mod, "BACKEND", "postgres"):
            _pg_execute(mock_conn, "DELETE FROM x")

        mock_conn.commit.assert_called_once()


# ── _pg_fetchall (DuckDB backend) ────────────────────────────────

class TestPgFetchallDuckDB:
    def test_returns_rows_no_params(self, duck_conn):
        duck_conn.execute("CREATE TABLE _test_fetch (n INTEGER)")
        duck_conn.execute("INSERT INTO _test_fetch VALUES (1)")
        duck_conn.execute("INSERT INTO _test_fetch VALUES (2)")
        rows = _pg_fetchall(duck_conn, "SELECT n FROM _test_fetch ORDER BY n")
        assert rows == [(1,), (2,)]

    def test_returns_rows_with_params(self, duck_conn):
        duck_conn.execute("CREATE TABLE _test_fetch2 (n INTEGER)")
        duck_conn.execute("INSERT INTO _test_fetch2 VALUES (10)")
        duck_conn.execute("INSERT INTO _test_fetch2 VALUES (20)")
        rows = _pg_fetchall(duck_conn, "SELECT n FROM _test_fetch2 WHERE n > ?", [15])
        assert rows == [(20,)]

    def test_empty_table_returns_empty_list(self, duck_conn):
        duck_conn.execute("CREATE TABLE _test_empty (n INTEGER)")
        rows = _pg_fetchall(duck_conn, "SELECT n FROM _test_empty")
        assert rows == []


# ── _pg_fetchall (Postgres mock backend) ─────────────────────────

class TestPgFetchallPostgres:
    def test_converts_placeholders_and_returns_rows(self):
        """On postgres backend, ? → %s and fetchall() result is returned."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("row1",), ("row2",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(pipeline_mod, "BACKEND", "postgres"):
            result = _pg_fetchall(mock_conn, "SELECT x FROM t WHERE y = ?", ["val"])

        mock_cursor.execute.assert_called_once_with(
            "SELECT x FROM t WHERE y = %s", ["val"]
        )
        assert result == [("row1",), ("row2",)]

    def test_no_params_passes_none(self):
        """When params=None, None is passed through to cursor.execute."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(pipeline_mod, "BACKEND", "postgres"):
            result = _pg_fetchall(mock_conn, "SELECT 1")

        mock_cursor.execute.assert_called_once_with("SELECT 1", None)
        assert result == []


# ── _ensure_signal_tables ─────────────────────────────────────────

class TestEnsureSignalTablesPostgresSkip:
    def test_skips_on_postgres(self):
        """_ensure_signal_tables returns immediately on postgres — no DDL executed."""
        mock_conn = MagicMock()

        with patch.object(pipeline_mod, "BACKEND", "postgres"):
            _ensure_signal_tables(mock_conn)

        mock_conn.execute.assert_not_called()
        mock_conn.cursor.assert_not_called()

    def test_creates_tables_on_duckdb(self, duck_conn):
        """_ensure_signal_tables creates all 4 signal tables on DuckDB."""
        with patch.object(pipeline_mod, "BACKEND", "duckdb"):
            _ensure_signal_tables(duck_conn)

        tables = [r[0] for r in duck_conn.execute("SHOW TABLES").fetchall()]
        for t in ("signal_types", "permit_signals", "property_signals", "property_health"):
            assert t in tables, f"Table '{t}' not created on DuckDB"


# ── detector._execute (both backends) ────────────────────────────

class TestDetectorExecuteDuckDB:
    def test_no_params(self, duck_conn):
        """detector._execute with no params returns rows from DuckDB."""
        duck_conn.execute("CREATE TABLE _det_test (v INTEGER)")
        duck_conn.execute("INSERT INTO _det_test VALUES (99)")

        with patch.object(detector_mod, "BACKEND", "duckdb"):
            rows = detector_execute(duck_conn, "SELECT v FROM _det_test")

        assert rows == [(99,)]

    def test_with_params(self, duck_conn):
        """detector._execute with ? params works on DuckDB."""
        duck_conn.execute("CREATE TABLE _det_test2 (v INTEGER)")
        duck_conn.execute("INSERT INTO _det_test2 VALUES (5)")
        duck_conn.execute("INSERT INTO _det_test2 VALUES (10)")

        with patch.object(detector_mod, "BACKEND", "duckdb"):
            rows = detector_execute(
                duck_conn, "SELECT v FROM _det_test2 WHERE v > ?", [7]
            )

        assert rows == [(10,)]


class TestDetectorExecutePostgres:
    def test_converts_placeholders(self):
        """detector._execute converts ? → %s and returns fetchall() result."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("result",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(detector_mod, "BACKEND", "postgres"):
            result = detector_execute(
                mock_conn, "SELECT * FROM t WHERE x = ?", ["abc"]
            )

        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM t WHERE x = %s", ["abc"]
        )
        assert result == [("result",)]

    def test_no_params_uses_empty_tuple(self):
        """detector._execute uses empty tuple when params=None on postgres."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(detector_mod, "BACKEND", "postgres"):
            result = detector_execute(mock_conn, "SELECT 1")

        mock_cursor.execute.assert_called_once_with("SELECT 1", ())
        assert result == []


# ── run_signal_pipeline end-to-end (DuckDB) ──────────────────────

class TestRunSignalPipelineDuckDB:
    """Integration tests for run_signal_pipeline using real in-memory DuckDB."""

    def test_empty_returns_zero_stats(self, duck_conn):
        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats = run_signal_pipeline(duck_conn)

        assert stats["total_signals"] == 0
        assert stats["properties"] == 0
        assert stats["permit_signals"] == 0
        assert stats["property_signals"] == 0

    def test_stats_has_all_keys(self, duck_conn):
        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats = run_signal_pipeline(duck_conn)

        for key in ("total_signals", "permit_signals", "property_signals",
                    "properties", "tier_distribution", "detectors"):
            assert key in stats

    def test_nov_signal_populates_property_health(self, duck_conn):
        duck_conn.execute(
            "INSERT INTO violations VALUES (1, '0001', '001', 'open', 'Building without permit')"
        )

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats = run_signal_pipeline(duck_conn)

        assert stats["total_signals"] >= 1
        row = duck_conn.execute(
            "SELECT tier FROM property_health WHERE block_lot = '0001/001'"
        ).fetchone()
        assert row is not None
        assert row[0] == "at_risk"

    def test_idempotent_second_run_same_counts(self, duck_conn):
        duck_conn.execute(
            "INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test')"
        )

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats1 = run_signal_pipeline(duck_conn)
            stats2 = run_signal_pipeline(duck_conn)

        assert stats1["total_signals"] == stats2["total_signals"]
        assert stats1["properties"] == stats2["properties"]
        count = duck_conn.execute("SELECT COUNT(*) FROM property_health").fetchone()[0]
        assert count == 1

    def test_permit_signals_inserted(self, duck_conn):
        duck_conn.execute(
            "INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001',"
            " '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')"
        )
        duck_conn.execute(
            "INSERT INTO addenda VALUES (1, 'P001', 'CPC', 'Issued Comments', '2024-06-01', '2024-06-15')"
        )

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats = run_signal_pipeline(duck_conn)

        count = duck_conn.execute("SELECT COUNT(*) FROM permit_signals").fetchone()[0]
        assert count >= 1
        assert stats["permit_signals"] >= 1

    def test_signals_json_is_valid(self, duck_conn):
        duck_conn.execute(
            "INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test')"
        )

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            run_signal_pipeline(duck_conn)

        row = duck_conn.execute(
            "SELECT signals_json FROM property_health WHERE block_lot = '0001/001'"
        ).fetchone()
        assert row is not None
        signals = json.loads(row[0])
        assert isinstance(signals, list)
        assert len(signals) >= 1
        assert "type" in signals[0]
        assert "severity" in signals[0]

    def test_tier_distribution_included_in_stats(self, duck_conn):
        duck_conn.execute(
            "INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test')"
        )

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats = run_signal_pipeline(duck_conn)

        assert "at_risk" in stats["tier_distribution"]

    def test_multiple_properties(self, duck_conn):
        duck_conn.execute(
            "INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test1')"
        )
        duck_conn.execute(
            "INSERT INTO violations VALUES (2, '0002', '002', 'open', 'test2')"
        )

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            stats = run_signal_pipeline(duck_conn)

        assert stats["properties"] == 2

    def test_complaint_produces_slower_tier(self, duck_conn):
        duck_conn.execute(
            "INSERT INTO complaints VALUES (1, '0001', '001', 'open', 'Noise')"
        )

        with patch.object(pipeline_mod, "BACKEND", "duckdb"), \
             patch.object(detector_mod, "BACKEND", "duckdb"):
            run_signal_pipeline(duck_conn)

        row = duck_conn.execute(
            "SELECT tier FROM property_health WHERE block_lot = '0001/001'"
        ).fetchone()
        assert row is not None
        assert row[0] == "slower"
