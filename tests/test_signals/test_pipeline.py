"""Tests for src.signals.pipeline — end-to-end signal pipeline.

Uses in-memory DuckDB with synthetic data to verify the full pipeline:
table creation, signal detection, aggregation, persistence, and stats.
"""

import json
import pytest
import duckdb
from datetime import date, timedelta

from src.signals.pipeline import (
    run_signal_pipeline,
    _ensure_signal_tables,
    _seed_signal_types,
    _truncate_signals,
)
from src.signals.types import SIGNAL_CATALOG


@pytest.fixture
def conn():
    """In-memory DuckDB with base data tables + signal pipeline tables."""
    c = duckdb.connect(":memory:")

    # Base tables
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


# ── Table creation ───────────────────────────────────────────────

class TestEnsureSignalTables:
    def test_creates_all_tables(self, conn):
        _ensure_signal_tables(conn)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        for t in ("signal_types", "permit_signals", "property_signals", "property_health"):
            assert t in tables, f"Table '{t}' not created"

    def test_idempotent(self, conn):
        _ensure_signal_tables(conn)
        _ensure_signal_tables(conn)  # Second call should not fail
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        assert "signal_types" in tables


class TestSeedSignalTypes:
    def test_seeds_all_types(self, conn):
        _ensure_signal_tables(conn)
        _seed_signal_types(conn)
        count = conn.execute("SELECT COUNT(*) FROM signal_types").fetchone()[0]
        assert count == len(SIGNAL_CATALOG)

    def test_idempotent(self, conn):
        _ensure_signal_tables(conn)
        _seed_signal_types(conn)
        _seed_signal_types(conn)  # Re-seed
        count = conn.execute("SELECT COUNT(*) FROM signal_types").fetchone()[0]
        assert count == len(SIGNAL_CATALOG)


class TestTruncateSignals:
    def test_truncates_all_signal_tables(self, conn):
        _ensure_signal_tables(conn)
        _seed_signal_types(conn)
        # Insert dummy data
        conn.execute("""
            INSERT INTO permit_signals (permit_number, signal_type, severity, detail)
            VALUES ('P001', 'nov', 'at_risk', 'test')
        """)
        conn.execute("""
            INSERT INTO property_signals (block_lot, signal_type, severity, detail, source_permit)
            VALUES ('0001/001', 'nov', 'at_risk', 'test', 'P001')
        """)
        conn.execute("""
            INSERT INTO property_health (block_lot, tier, signal_count, at_risk_count, signals_json)
            VALUES ('0001/001', 'at_risk', 1, 1, '[]')
        """)
        _truncate_signals(conn)
        for table in ("permit_signals", "property_signals", "property_health"):
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == 0, f"Table '{table}' not truncated"


# ── End-to-end pipeline ─────────────────────────────────────────

class TestRunSignalPipeline:
    def test_empty_tables_returns_zero_stats(self, conn):
        stats = run_signal_pipeline(conn)
        assert stats["total_signals"] == 0
        assert stats["properties"] == 0
        assert stats["permit_signals"] == 0
        assert stats["property_signals"] == 0

    def test_stats_has_expected_keys(self, conn):
        stats = run_signal_pipeline(conn)
        assert "total_signals" in stats
        assert "permit_signals" in stats
        assert "property_signals" in stats
        assert "properties" in stats
        assert "tier_distribution" in stats
        assert "detectors" in stats

    def test_detectors_all_reported(self, conn):
        stats = run_signal_pipeline(conn)
        assert len(stats["detectors"]) == 12

    def test_single_nov_signal(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'Building without permit')")
        stats = run_signal_pipeline(conn)
        assert stats["total_signals"] >= 1
        assert stats["properties"] >= 1
        # Verify property_health has an entry
        row = conn.execute("SELECT tier FROM property_health WHERE block_lot = '0001/001'").fetchone()
        assert row is not None
        assert row[0] == "at_risk"

    def test_high_risk_compound(self, conn):
        """Two compounding signals → high_risk in property_health."""
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute("INSERT INTO addenda VALUES (1, 'P001', 'CPC', 'Issued Comments', '2024-06-01', '2024-06-15')")
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'Building without permit')")
        stats = run_signal_pipeline(conn)
        row = conn.execute("SELECT tier FROM property_health WHERE block_lot = '0001/001'").fetchone()
        assert row is not None
        assert row[0] == "high_risk"

    def test_permit_signals_populated(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute("INSERT INTO addenda VALUES (1, 'P001', 'CPC', 'Issued Comments', '2024-06-01', '2024-06-15')")
        stats = run_signal_pipeline(conn)
        count = conn.execute("SELECT COUNT(*) FROM permit_signals").fetchone()[0]
        assert count >= 1
        assert stats["permit_signals"] >= 1

    def test_property_signals_populated(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test')")
        stats = run_signal_pipeline(conn)
        count = conn.execute("SELECT COUNT(*) FROM property_signals").fetchone()[0]
        assert count >= 1
        assert stats["property_signals"] >= 1

    def test_signals_json_valid(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test')")
        run_signal_pipeline(conn)
        row = conn.execute("SELECT signals_json FROM property_health WHERE block_lot = '0001/001'").fetchone()
        assert row is not None
        signals = json.loads(row[0])
        assert isinstance(signals, list)
        assert len(signals) >= 1
        assert "type" in signals[0]
        assert "severity" in signals[0]

    def test_tier_distribution_in_stats(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test')")
        stats = run_signal_pipeline(conn)
        assert "at_risk" in stats["tier_distribution"]

    def test_idempotent(self, conn):
        """Running twice should produce the same results (truncate + rebuild)."""
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test')")
        stats1 = run_signal_pipeline(conn)
        stats2 = run_signal_pipeline(conn)
        assert stats1["total_signals"] == stats2["total_signals"]
        assert stats1["properties"] == stats2["properties"]
        # Ensure no double-counting
        count = conn.execute("SELECT COUNT(*) FROM property_health").fetchone()[0]
        assert count == 1

    def test_multiple_properties(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test1')")
        conn.execute("INSERT INTO violations VALUES (2, '0002', '002', 'open', 'test2')")
        stats = run_signal_pipeline(conn)
        assert stats["properties"] == 2

    def test_detector_failure_doesnt_crash(self, conn):
        """If one detector fails, others should still run."""
        # This is hard to test directly without mocking, but we can verify
        # the pipeline handles empty tables gracefully
        stats = run_signal_pipeline(conn)
        # All detectors should report 0, not -1 (failure)
        for name, count in stats["detectors"].items():
            assert count >= 0, f"Detector {name} failed with count={count}"

    def test_complaint_slower_tier(self, conn):
        """Open complaint with no NOV → slower tier."""
        conn.execute("INSERT INTO complaints VALUES (1, '0001', '001', 'open', 'test')")
        stats = run_signal_pipeline(conn)
        row = conn.execute("SELECT tier FROM property_health WHERE block_lot = '0001/001'").fetchone()
        assert row is not None
        assert row[0] == "slower"

    def test_behind_tier_from_stalled(self, conn):
        """Stalled at non-planning station → behind tier."""
        stall_date = (date.today() - timedelta(days=60)).isoformat()
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO addenda VALUES (1, 'P001', 'BFS', NULL, '{stall_date}', NULL)")
        stats = run_signal_pipeline(conn)
        row = conn.execute("SELECT tier FROM property_health WHERE block_lot = '0001/001'").fetchone()
        assert row is not None
        assert row[0] == "behind"
