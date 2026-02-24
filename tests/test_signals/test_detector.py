"""Tests for src.signals.detector — each detector with synthetic DuckDB fixtures.

Uses in-memory DuckDB with minimal test data to verify each detector's SQL and
signal generation logic.
"""

import pytest
import duckdb
from datetime import date, timedelta

from src.signals.detector import (
    detect_hold_comments,
    detect_hold_stalled_planning,
    detect_hold_stalled,
    detect_nov,
    detect_abatement,
    detect_expired_uninspected,
    detect_stale_with_activity,
    detect_expired_minor_activity,
    detect_expired_inconclusive,
    detect_expired_otc,
    detect_stale_no_activity,
    detect_complaint,
    ALL_DETECTORS,
)
from src.signals.types import Signal


@pytest.fixture
def conn():
    """In-memory DuckDB with base tables for all detectors."""
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


# ── ALL_DETECTORS ────────────────────────────────────────────────

class TestAllDetectors:
    def test_has_12_detectors(self):
        assert len(ALL_DETECTORS) == 12

    def test_all_callable(self):
        for d in ALL_DETECTORS:
            assert callable(d)

    def test_all_return_empty_on_empty_tables(self, conn):
        for d in ALL_DETECTORS:
            result = d(conn)
            assert isinstance(result, list), f"{d.__name__} didn't return list"
            assert len(result) == 0, f"{d.__name__} returned {len(result)} on empty tables"


# ── detect_hold_comments ─────────────────────────────────────────

class TestDetectHoldComments:
    def test_detects_issued_comments(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute("INSERT INTO addenda VALUES (1, 'P001', 'CPC', 'Issued Comments', '2024-06-01', '2024-06-15')")
        result = detect_hold_comments(conn)
        assert len(result) == 1
        assert result[0].signal_type == "hold_comments"
        assert result[0].severity == "at_risk"
        assert result[0].permit_number == "P001"
        assert "CPC" in result[0].detail

    def test_ignores_approved_stations(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute("INSERT INTO addenda VALUES (1, 'P001', 'CPC', 'Approved', '2024-06-01', '2024-06-15')")
        result = detect_hold_comments(conn)
        assert len(result) == 0

    def test_latest_record_wins(self, conn):
        """If the latest record at a station is Approved, no signal."""
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute("INSERT INTO addenda VALUES (1, 'P001', 'CPC', 'Issued Comments', '2024-01-01', '2024-01-15')")
        conn.execute("INSERT INTO addenda VALUES (2, 'P001', 'CPC', 'Approved', '2024-06-01', '2024-06-15')")
        result = detect_hold_comments(conn)
        assert len(result) == 0

    def test_block_lot_populated(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '3512', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute("INSERT INTO addenda VALUES (1, 'P001', 'CPC', 'Issued Comments', '2024-06-01', '2024-06-15')")
        result = detect_hold_comments(conn)
        assert result[0].block_lot == "3512/001"


# ── detect_hold_stalled_planning ─────────────────────────────────

class TestDetectHoldStalledPlanning:
    def test_detects_stalled_at_ppc(self, conn):
        old_date = (date.today() - timedelta(days=400)).isoformat()
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO addenda VALUES (1, 'P001', 'PPC', NULL, '{old_date}', NULL)")
        result = detect_hold_stalled_planning(conn)
        assert len(result) == 1
        assert result[0].signal_type == "hold_stalled_planning"
        assert "PPC" in result[0].detail

    def test_ignores_recent_start(self, conn):
        recent = (date.today() - timedelta(days=30)).isoformat()
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO addenda VALUES (1, 'P001', 'PPC', NULL, '{recent}', NULL)")
        result = detect_hold_stalled_planning(conn)
        assert len(result) == 0

    def test_ignores_finished(self, conn):
        old_date = (date.today() - timedelta(days=400)).isoformat()
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO addenda VALUES (1, 'P001', 'PPC', 'Approved', '{old_date}', '2024-06-01')")
        result = detect_hold_stalled_planning(conn)
        assert len(result) == 0

    def test_cpzoc_station(self, conn):
        old_date = (date.today() - timedelta(days=400)).isoformat()
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO addenda VALUES (1, 'P001', 'CP-ZOC', NULL, '{old_date}', NULL)")
        result = detect_hold_stalled_planning(conn)
        assert len(result) == 1

    def test_cpb_station(self, conn):
        old_date = (date.today() - timedelta(days=400)).isoformat()
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO addenda VALUES (1, 'P001', 'CPB', NULL, '{old_date}', NULL)")
        result = detect_hold_stalled_planning(conn)
        assert len(result) == 1


# ── detect_hold_stalled ──────────────────────────────────────────

class TestDetectHoldStalled:
    def test_detects_stalled_non_planning(self, conn):
        stall_date = (date.today() - timedelta(days=60)).isoformat()
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO addenda VALUES (1, 'P001', 'BFS', NULL, '{stall_date}', NULL)")
        result = detect_hold_stalled(conn)
        assert len(result) == 1
        assert result[0].signal_type == "hold_stalled"
        assert result[0].severity == "behind"

    def test_ignores_planning_stations(self, conn):
        stall_date = (date.today() - timedelta(days=60)).isoformat()
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO addenda VALUES (1, 'P001', 'PPC', NULL, '{stall_date}', NULL)")
        result = detect_hold_stalled(conn)
        assert len(result) == 0

    def test_ignores_too_recent(self, conn):
        recent = (date.today() - timedelta(days=10)).isoformat()
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO addenda VALUES (1, 'P001', 'BFS', NULL, '{recent}', NULL)")
        result = detect_hold_stalled(conn)
        assert len(result) == 0

    def test_ignores_too_old(self, conn):
        very_old = (date.today() - timedelta(days=500)).isoformat()
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO addenda VALUES (1, 'P001', 'BFS', NULL, '{very_old}', NULL)")
        result = detect_hold_stalled(conn)
        assert len(result) == 0

    def test_ignores_pre_2020(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'filed', '1', 'New Building', '0001', '001', '100', 'Market', '2024-01-01', NULL, '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute("INSERT INTO addenda VALUES (1, 'P001', 'BFS', NULL, '2019-06-01', NULL)")
        result = detect_hold_stalled(conn)
        assert len(result) == 0


# ── detect_nov ───────────────────────────────────────────────────

class TestDetectNov:
    def test_detects_open_violations(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'Building without permit')")
        result = detect_nov(conn)
        assert len(result) == 1
        assert result[0].signal_type == "nov"
        assert result[0].block_lot == "0001/001"
        assert "1 open NOV" in result[0].detail

    def test_ignores_closed(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'closed', 'test')")
        result = detect_nov(conn)
        assert len(result) == 0

    def test_ignores_complied(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'complied', 'test')")
        result = detect_nov(conn)
        assert len(result) == 0

    def test_groups_by_block_lot(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test1')")
        conn.execute("INSERT INTO violations VALUES (2, '0001', '001', 'open', 'test2')")
        result = detect_nov(conn)
        assert len(result) == 1
        assert "2 open NOV" in result[0].detail

    def test_separate_block_lots(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'test')")
        conn.execute("INSERT INTO violations VALUES (2, '0002', '002', 'open', 'test')")
        result = detect_nov(conn)
        assert len(result) == 2


# ── detect_abatement ─────────────────────────────────────────────

class TestDetectAbatement:
    def test_detects_abatement(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'Abatement order issued')")
        result = detect_abatement(conn)
        assert len(result) == 1
        assert result[0].signal_type == "abatement"

    def test_detects_hearing(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'Hearing scheduled')")
        result = detect_abatement(conn)
        assert len(result) == 1

    def test_detects_director(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'Director determination')")
        result = detect_abatement(conn)
        assert len(result) == 1

    def test_ignores_closed_abatement(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'closed', 'Abatement order issued')")
        result = detect_abatement(conn)
        assert len(result) == 0

    def test_ignores_non_abatement(self, conn):
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'Building without permit')")
        result = detect_abatement(conn)
        assert len(result) == 0


# ── detect_expired_uninspected ───────────────────────────────────

class TestDetectExpiredUninspected:
    def test_detects_expired_with_4_real_no_final(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        for i in range(4):
            conn.execute(f"INSERT INTO inspections VALUES ({i}, 'P001', 'PASSED', 'Rough plumbing', '2021-0{i+1}-01')")
        result = detect_expired_uninspected(conn)
        assert len(result) == 1
        assert result[0].signal_type == "expired_uninspected"
        assert "4 real inspections" in result[0].detail

    def test_ignores_with_final(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        for i in range(3):
            conn.execute(f"INSERT INTO inspections VALUES ({i}, 'P001', 'PASSED', 'Rough plumbing', '2021-0{i+1}-01')")
        conn.execute("INSERT INTO inspections VALUES (4, 'P001', 'PASSED', 'Final inspection', '2021-06-01')")
        result = detect_expired_uninspected(conn)
        assert len(result) == 0

    def test_ignores_fewer_than_4(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        for i in range(3):
            conn.execute(f"INSERT INTO inspections VALUES ({i}, 'P001', 'PASSED', 'Rough plumbing', '2021-0{i+1}-01')")
        result = detect_expired_uninspected(conn)
        assert len(result) == 0

    def test_ignores_issued_status(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'issued', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        for i in range(4):
            conn.execute(f"INSERT INTO inspections VALUES ({i}, 'P001', 'PASSED', 'Rough plumbing', '2021-0{i+1}-01')")
        result = detect_expired_uninspected(conn)
        assert len(result) == 0


# ── detect_stale_with_activity ───────────────────────────────────

class TestDetectStaleWithActivity:
    def test_detects_issued_2yr_with_recent_activity(self, conn):
        old_issued = (date.today() - timedelta(days=800)).isoformat()
        recent_insp = (date.today() - timedelta(days=30)).isoformat()
        conn.execute(f"INSERT INTO permits VALUES ('P001', 'issued', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '{old_issued}', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO inspections VALUES (1, 'P001', 'PASSED', 'Rough plumbing', '{recent_insp}')")
        conn.execute(f"INSERT INTO inspections VALUES (2, 'P001', 'FAILED', 'Electrical', '{recent_insp}')")
        result = detect_stale_with_activity(conn)
        assert len(result) == 1
        assert result[0].signal_type == "stale_with_activity"

    def test_ignores_recent_issued(self, conn):
        recent = (date.today() - timedelta(days=100)).isoformat()
        conn.execute(f"INSERT INTO permits VALUES ('P001', 'issued', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '{recent}', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute(f"INSERT INTO inspections VALUES (1, 'P001', 'PASSED', 'test', '{recent}')")
        conn.execute(f"INSERT INTO inspections VALUES (2, 'P001', 'PASSED', 'test2', '{recent}')")
        result = detect_stale_with_activity(conn)
        assert len(result) == 0


# ── detect_expired_minor_activity ────────────────────────────────

class TestDetectExpiredMinorActivity:
    def test_detects_1_to_3_real_inspections(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute("INSERT INTO inspections VALUES (1, 'P001', 'PASSED', 'Rough plumbing', '2021-01-01')")
        conn.execute("INSERT INTO inspections VALUES (2, 'P001', 'FAILED', 'Electrical', '2021-02-01')")
        result = detect_expired_minor_activity(conn)
        assert len(result) == 1
        assert "2 real inspections" in result[0].detail

    def test_ignores_4_or_more(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        for i in range(4):
            conn.execute(f"INSERT INTO inspections VALUES ({i}, 'P001', 'PASSED', 'test', '2021-0{i+1}-01')")
        result = detect_expired_minor_activity(conn)
        assert len(result) == 0


# ── detect_expired_inconclusive ──────────────────────────────────

class TestDetectExpiredInconclusive:
    def test_detects_expired_no_inspections_non_otc(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        result = detect_expired_inconclusive(conn)
        assert len(result) == 1
        assert result[0].signal_type == "expired_inconclusive"

    def test_ignores_otc(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '8', 'OTC', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        result = detect_expired_inconclusive(conn)
        assert len(result) == 0

    def test_ignores_with_real_inspections(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute("INSERT INTO inspections VALUES (1, 'P001', 'PASSED', 'test', '2021-01-01')")
        result = detect_expired_inconclusive(conn)
        assert len(result) == 0


# ── detect_expired_otc ───────────────────────────────────────────

class TestDetectExpiredOtc:
    def test_detects_expired_otc_no_inspections(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '8', 'OTC', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        result = detect_expired_otc(conn)
        assert len(result) == 1
        assert result[0].signal_type == "expired_otc"

    def test_ignores_non_otc(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        result = detect_expired_otc(conn)
        assert len(result) == 0

    def test_ignores_with_real_inspections(self, conn):
        conn.execute("INSERT INTO permits VALUES ('P001', 'expired', '8', 'OTC', '0001', '001', '100', 'Market', '2020-01-01', '2020-06-01', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        conn.execute("INSERT INTO inspections VALUES (1, 'P001', 'PASSED', 'test', '2021-01-01')")
        result = detect_expired_otc(conn)
        assert len(result) == 0


# ── detect_stale_no_activity ─────────────────────────────────────

class TestDetectStaleNoActivity:
    def test_detects_stale_issued_no_recent_inspection(self, conn):
        old_issued = (date.today() - timedelta(days=800)).isoformat()
        conn.execute(f"INSERT INTO permits VALUES ('P001', 'issued', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '{old_issued}', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        result = detect_stale_no_activity(conn)
        assert len(result) == 1
        assert result[0].signal_type == "stale_no_activity"

    def test_ignores_recent_issued(self, conn):
        recent = (date.today() - timedelta(days=100)).isoformat()
        conn.execute(f"INSERT INTO permits VALUES ('P001', 'issued', '1', 'New Building', '0001', '001', '100', 'Market', '2020-01-01', '{recent}', '2024-01-01', 1000, NULL, '', '', 'SoMa')")
        result = detect_stale_no_activity(conn)
        assert len(result) == 0


# ── detect_complaint ─────────────────────────────────────────────

class TestDetectComplaint:
    def test_detects_open_complaint_no_nov(self, conn):
        conn.execute("INSERT INTO complaints VALUES (1, '0001', '001', 'open', 'Noise complaint')")
        result = detect_complaint(conn)
        assert len(result) == 1
        assert result[0].signal_type == "complaint"
        assert result[0].block_lot == "0001/001"

    def test_ignores_closed_complaint(self, conn):
        conn.execute("INSERT INTO complaints VALUES (1, '0001', '001', 'closed', 'test')")
        result = detect_complaint(conn)
        assert len(result) == 0

    def test_ignores_complaint_with_nov(self, conn):
        """Complaint suppressed when property has an open NOV."""
        conn.execute("INSERT INTO complaints VALUES (1, '0001', '001', 'open', 'test')")
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'open', 'Building without permit')")
        result = detect_complaint(conn)
        assert len(result) == 0

    def test_complaint_not_suppressed_by_closed_nov(self, conn):
        """Closed NOV doesn't suppress open complaint."""
        conn.execute("INSERT INTO complaints VALUES (1, '0001', '001', 'open', 'test')")
        conn.execute("INSERT INTO violations VALUES (1, '0001', '001', 'closed', 'Building without permit')")
        result = detect_complaint(conn)
        assert len(result) == 1

    def test_groups_by_block_lot(self, conn):
        conn.execute("INSERT INTO complaints VALUES (1, '0001', '001', 'open', 'test1')")
        conn.execute("INSERT INTO complaints VALUES (2, '0001', '001', 'open', 'test2')")
        result = detect_complaint(conn)
        assert len(result) == 1
        assert "2 open complaint" in result[0].detail
