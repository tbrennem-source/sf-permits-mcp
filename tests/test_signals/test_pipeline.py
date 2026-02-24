"""End-to-end tests for the signal pipeline using synthetic DuckDB."""

from datetime import date, timedelta

import duckdb
import pytest

from src.db import init_schema
from src.signals.pipeline import run_signal_pipeline

TODAY = date(2026, 2, 23)
_next_id = {"violation": 1, "complaint": 1, "inspection": 1}


def _get_id(table):
    val = _next_id[table]
    _next_id[table] += 1
    return val


@pytest.fixture(autouse=True)
def _reset_ids():
    for k in _next_id:
        _next_id[k] = 1


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "pipeline_test.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)
    return conn


def _insert_permit(conn, pn, status="issued", block="3512", lot="001",
                   permit_type="1", status_date_days_ago=30):
    today = TODAY
    conn.execute(
        "INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [pn, permit_type, "additions alterations or repairs", status,
         str(today - timedelta(days=status_date_days_ago)),
         "test", str(today - timedelta(days=100)),
         str(today - timedelta(days=80)),
         None, None, 50000, None,
         "1 family dwelling", "1 family dwelling", None, None,
         "100", "MARKET", "ST", "94105", "SoMa", "6", block, lot, None, str(today)],
    )


def _insert_violation(conn, block="3512", lot="001", status="open",
                      category="Notice of Violation"):
    today = TODAY
    vid = _get_id("violation")
    conn.execute(
        "INSERT INTO violations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [vid, "C001", "1", str(today - timedelta(days=30)),
         block, lot, "100", "MARKET", "ST", None, status,
         None, None, category, None, None, "SoMa", "6", "94105", str(today)],
    )


def _insert_complaint(conn, block="3512", lot="001", status="open"):
    today = TODAY
    cid = _get_id("complaint")
    conn.execute(
        "INSERT INTO complaints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [cid, "COMP001", str(today - timedelta(days=10)), None,
         block, lot, None, "100", "MARKET", "ST", None,
         "94105", "Test", status, None, None, None, str(today)],
    )


def _insert_inspection(conn, ref_num, result="PASSED", days_ago=30, desc="Check"):
    today = TODAY
    iid = _get_id("inspection")
    conn.execute(
        "INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [iid, ref_num, "PERMIT", "SMITH", str(today - timedelta(days=days_ago)),
         result, desc, "3512", "001", "100", "MARKET", "ST", "SoMa", "6", "94105",
         str(today)],
    )


class TestPipelineEndToEnd:
    def test_empty_database(self, db):
        stats = run_signal_pipeline(db, backend="duckdb")
        assert stats["status"] == "ok"
        assert stats["total_signals"] == 0
        assert stats["properties_scored"] == 0

    def test_single_nov(self, db):
        _insert_violation(db)
        stats = run_signal_pipeline(db, backend="duckdb")
        assert stats["total_signals"] >= 1
        assert stats["properties_scored"] >= 1

        # Check property_health table
        row = db.execute("SELECT tier FROM property_health WHERE block_lot = '3512/001'").fetchone()
        assert row is not None
        assert row[0] == "at_risk"

    def test_high_risk_compound(self, db):
        """NOV + stale_with_activity → high_risk."""
        _insert_violation(db, block="3512", lot="001")
        _insert_permit(db, "P001", status="issued", block="3512", lot="001",
                       status_date_days_ago=800)
        _insert_inspection(db, "P001", result="PASSED", days_ago=100)
        _insert_inspection(db, "P001", result="FAILED", days_ago=200)
        stats = run_signal_pipeline(db, backend="duckdb")

        row = db.execute("SELECT tier, at_risk_count FROM property_health WHERE block_lot = '3512/001'").fetchone()
        assert row is not None
        assert row[0] == "high_risk"
        assert row[1] >= 2

    def test_complaint_only_slower(self, db):
        _insert_complaint(db, block="3600", lot="010")
        stats = run_signal_pipeline(db, backend="duckdb")

        row = db.execute("SELECT tier FROM property_health WHERE block_lot = '3600/010'").fetchone()
        assert row is not None
        assert row[0] == "slower"

    def test_pipeline_truncates_on_rerun(self, db):
        _insert_violation(db)
        stats1 = run_signal_pipeline(db, backend="duckdb")
        count1 = stats1["total_signals"]

        # Rerun should produce same count (truncate + re-detect)
        stats2 = run_signal_pipeline(db, backend="duckdb")
        assert stats2["total_signals"] == count1

    def test_multiple_properties(self, db):
        _insert_violation(db, block="3512", lot="001")
        _insert_complaint(db, block="3600", lot="010")
        stats = run_signal_pipeline(db, backend="duckdb")
        assert stats["properties_scored"] >= 2

    def test_stats_contain_detector_stats(self, db):
        _insert_violation(db)
        stats = run_signal_pipeline(db, backend="duckdb")
        assert "detector_stats" in stats
        assert "detect_nov" in stats["detector_stats"]

    def test_stats_contain_tier_distribution(self, db):
        _insert_violation(db)
        stats = run_signal_pipeline(db, backend="duckdb")
        assert "tier_distribution" in stats

    def test_permit_signals_table_populated(self, db):
        _insert_permit(db, "P001", status="expired", permit_type="1")
        stats = run_signal_pipeline(db, backend="duckdb")

        rows = db.execute("SELECT COUNT(*) FROM permit_signals").fetchone()
        assert rows[0] >= 1

    def test_property_signals_table_populated(self, db):
        _insert_violation(db)
        stats = run_signal_pipeline(db, backend="duckdb")

        rows = db.execute("SELECT COUNT(*) FROM property_signals").fetchone()
        assert rows[0] >= 1

    def test_signals_json_populated(self, db):
        import json
        _insert_violation(db)
        run_signal_pipeline(db, backend="duckdb")

        row = db.execute("SELECT signals_json FROM property_health WHERE block_lot = '3512/001'").fetchone()
        assert row is not None
        signals = json.loads(row[0])
        assert len(signals) >= 1
        assert signals[0]["signal_type"] == "nov"


class TestPipelineIdempotency:
    def test_double_run_same_results(self, db):
        _insert_violation(db)
        _insert_permit(db, "P001", status="expired")
        run_signal_pipeline(db, backend="duckdb")
        count1 = db.execute("SELECT COUNT(*) FROM property_health").fetchone()[0]

        run_signal_pipeline(db, backend="duckdb")
        count2 = db.execute("SELECT COUNT(*) FROM property_health").fetchone()[0]
        assert count1 == count2
