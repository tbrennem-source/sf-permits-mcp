"""Tests for signal detectors using synthetic DuckDB fixtures."""

from datetime import date, timedelta

import duckdb
import pytest

from src.db import init_schema
from src.signals.detector import (
    detect_hold_comments,
    detect_hold_stalled_planning,
    detect_hold_stalled,
    detect_nov,
    detect_abatement,
    detect_expired_uninspected,
    detect_stale_with_activity,
    detect_expired_minor_activity,
    detect_expired_otc,
    detect_expired_inconclusive,
    detect_stale_no_activity,
    detect_complaint,
)

TODAY = date(2026, 2, 23)

# Auto-incrementing ID counters for DuckDB tables
_next_id = {"addenda": 1, "violation": 1, "inspection": 1, "complaint": 1}


def _get_id(table):
    val = _next_id[table]
    _next_id[table] += 1
    return val


@pytest.fixture(autouse=True)
def _reset_ids():
    """Reset ID counters between tests."""
    for k in _next_id:
        _next_id[k] = 1


@pytest.fixture
def db(tmp_path):
    """Create DuckDB with full schema for signal detection tests."""
    path = str(tmp_path / "signals_test.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)
    return conn


def _insert_permit(conn, pn, status="issued", block="3512", lot="001",
                   permit_type="1", filed_days_ago=100, issued_days_ago=80,
                   status_date_days_ago=30):
    today = TODAY
    conn.execute(
        "INSERT INTO permits (permit_number, permit_type, permit_type_definition, status, "
        "status_date, description, filed_date, issued_date, approved_date, completed_date, "
        "estimated_cost, revised_cost, existing_use, proposed_use, existing_units, "
        "proposed_units, street_number, street_name, street_suffix, zipcode, neighborhood, "
        "supervisor_district, block, lot, adu, data_as_of) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [pn, permit_type, "additions alterations or repairs", status,
         str(today - timedelta(days=status_date_days_ago)),
         "test permit",
         str(today - timedelta(days=filed_days_ago)),
         str(today - timedelta(days=issued_days_ago)) if issued_days_ago else None,
         None, None,
         50000, None,
         "1 family dwelling", "1 family dwelling",
         None, None,
         "100", "MARKET", "ST", "94105",
         "SoMa", "6", block, lot, None, str(today)],
    )


def _insert_addenda(conn, app_num, station, addenda_num=1, step=1,
                    start_date=None, finish_date=None, review_results=None):
    today = TODAY
    if start_date is None:
        start_date = str(today - timedelta(days=60))
    aid = _get_id("addenda")
    conn.execute(
        "INSERT INTO addenda (id, primary_key, application_number, addenda_number, step, "
        "station, arrive, assign_date, start_date, finish_date, approved_date, "
        "plan_checked_by, review_results, hold_description, addenda_status, department, "
        "title, data_as_of) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [aid, f"{app_num}-{station}-{addenda_num}-{step}", app_num, addenda_num, step,
         station, start_date, start_date, start_date, finish_date, None,
         None, review_results, None, None, None, None, str(today)],
    )


def _insert_violation(conn, block="3512", lot="001", status="open",
                      category="Notice of Violation"):
    today = TODAY
    vid = _get_id("violation")
    conn.execute(
        "INSERT INTO violations (id, complaint_number, item_sequence_number, date_filed, "
        "block, lot, street_number, street_name, street_suffix, unit, status, "
        "receiving_division, assigned_division, nov_category_description, item, "
        "nov_item_description, neighborhood, supervisor_district, zipcode, data_as_of) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [vid, "C001", "1", str(today - timedelta(days=30)),
         block, lot, "100", "MARKET", "ST", None, status,
         None, None, category, None, None, "SoMa", "6", "94105", str(today)],
    )


def _insert_inspection(conn, ref_num, result="PASSED", desc="Rough plumbing",
                       days_ago=30):
    today = TODAY
    iid = _get_id("inspection")
    conn.execute(
        "INSERT INTO inspections (id, reference_number, reference_number_type, inspector, "
        "scheduled_date, result, inspection_description, block, lot, street_number, "
        "street_name, street_suffix, neighborhood, supervisor_district, zipcode, data_as_of) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [iid, ref_num, "PERMIT", "SMITH", str(today - timedelta(days=days_ago)),
         result, desc, "3512", "001", "100", "MARKET", "ST", "SoMa", "6", "94105",
         str(today)],
    )


def _insert_complaint(conn, block="3512", lot="001", status="open"):
    today = TODAY
    cid = _get_id("complaint")
    conn.execute(
        "INSERT INTO complaints (id, complaint_number, date_filed, date_abated, "
        "block, lot, parcel_number, street_number, street_name, street_suffix, unit, "
        "zip_code, complaint_description, status, nov_type, receiving_division, "
        "assigned_division, data_as_of) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [cid, "COMP001", str(today - timedelta(days=10)), None,
         block, lot, None, "100", "MARKET", "ST", None,
         "94105", "Test complaint", status, None, None, None, str(today)],
    )


# ── Hold detectors ───────────────────────────────────────────────

class TestDetectHoldComments:
    def test_finds_issued_comments(self, db):
        _insert_permit(db, "P001")
        _insert_addenda(db, "P001", "BLDG", review_results="Issued Comments")
        signals = detect_hold_comments(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "hold_comments"
        assert signals[0].severity == "at_risk"
        assert signals[0].permit_number == "P001"

    def test_ignores_approved(self, db):
        _insert_permit(db, "P001")
        _insert_addenda(db, "P001", "BLDG", addenda_num=1, review_results="Issued Comments")
        _insert_addenda(db, "P001", "BLDG", addenda_num=2, review_results="Approved")
        signals = detect_hold_comments(db, backend="duckdb")
        assert len(signals) == 0

    def test_multiple_stations(self, db):
        _insert_permit(db, "P001")
        _insert_addenda(db, "P001", "BLDG", review_results="Issued Comments")
        _insert_addenda(db, "P001", "ELEC", review_results="Issued Comments")
        signals = detect_hold_comments(db, backend="duckdb")
        assert len(signals) == 2

    def test_no_addenda(self, db):
        _insert_permit(db, "P001")
        signals = detect_hold_comments(db, backend="duckdb")
        assert len(signals) == 0


class TestDetectHoldStalledPlanning:
    def test_finds_planning_stall(self, db):
        _insert_permit(db, "P001")
        _insert_addenda(db, "P001", "PPC",
                        start_date=str(TODAY - timedelta(days=400)))
        signals = detect_hold_stalled_planning(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "hold_stalled_planning"

    def test_ignores_recent(self, db):
        _insert_permit(db, "P001")
        _insert_addenda(db, "P001", "PPC",
                        start_date=str(TODAY - timedelta(days=200)))
        signals = detect_hold_stalled_planning(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_finished(self, db):
        _insert_permit(db, "P001")
        _insert_addenda(db, "P001", "PPC",
                        start_date=str(TODAY - timedelta(days=400)),
                        finish_date=str(TODAY - timedelta(days=10)))
        signals = detect_hold_stalled_planning(db, backend="duckdb")
        assert len(signals) == 0

    def test_all_planning_stations(self, db):
        for i, station in enumerate(["PPC", "CP-ZOC", "CPB"]):
            _insert_permit(db, f"P{i}", block=str(3512 + i))
            _insert_addenda(db, f"P{i}", station,
                            start_date=str(TODAY - timedelta(days=500)))
        signals = detect_hold_stalled_planning(db, backend="duckdb")
        assert len(signals) == 3


class TestDetectHoldStalled:
    def test_finds_stalled_nonplanning(self, db):
        _insert_permit(db, "P001")
        _insert_addenda(db, "P001", "BLDG",
                        start_date=str(TODAY - timedelta(days=60)))
        signals = detect_hold_stalled(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "hold_stalled"
        assert signals[0].severity == "behind"

    def test_ignores_too_recent(self, db):
        _insert_permit(db, "P001")
        _insert_addenda(db, "P001", "BLDG",
                        start_date=str(TODAY - timedelta(days=15)))
        signals = detect_hold_stalled(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_too_old(self, db):
        _insert_permit(db, "P001")
        _insert_addenda(db, "P001", "BLDG",
                        start_date=str(TODAY - timedelta(days=400)))
        signals = detect_hold_stalled(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_pre_2020(self, db):
        _insert_permit(db, "P001")
        _insert_addenda(db, "P001", "BLDG", start_date="2019-06-15")
        signals = detect_hold_stalled(db, backend="duckdb")
        assert len(signals) == 0


# ── Violation detectors ──────────────────────────────────────────

class TestDetectNov:
    def test_finds_open_nov(self, db):
        _insert_violation(db, status="open")
        signals = detect_nov(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "nov"
        assert signals[0].severity == "at_risk"

    def test_ignores_closed(self, db):
        _insert_violation(db, status="closed")
        signals = detect_nov(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_complied(self, db):
        _insert_violation(db, status="complied")
        signals = detect_nov(db, backend="duckdb")
        assert len(signals) == 0

    def test_groups_by_block_lot(self, db):
        _insert_violation(db, block="3512", lot="001")
        _insert_violation(db, block="3512", lot="001")
        signals = detect_nov(db, backend="duckdb")
        assert len(signals) == 1
        assert "2" in signals[0].detail


class TestDetectAbatement:
    def test_finds_abatement(self, db):
        _insert_violation(db, category="Order of Abatement")
        signals = detect_abatement(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "abatement"

    def test_finds_hearing(self, db):
        _insert_violation(db, category="Director's Hearing")
        signals = detect_abatement(db, backend="duckdb")
        assert len(signals) == 1

    def test_ignores_regular_nov(self, db):
        _insert_violation(db, category="Notice of Violation")
        signals = detect_abatement(db, backend="duckdb")
        assert len(signals) == 0


# ── Permit + inspection detectors ─────────────────────────────────

class TestDetectExpiredUninspected:
    def test_finds_expired_with_4_inspections_no_final(self, db):
        _insert_permit(db, "P001", status="expired")
        for i in range(4):
            _insert_inspection(db, "P001", result="PASSED", desc=f"Check {i}", days_ago=30 + i)
        signals = detect_expired_uninspected(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "expired_uninspected"

    def test_ignores_with_final_inspection(self, db):
        _insert_permit(db, "P001", status="expired")
        for i in range(4):
            _insert_inspection(db, "P001", result="PASSED", desc=f"Check {i}", days_ago=30 + i)
        _insert_inspection(db, "P001", result="PASSED", desc="Final inspection", days_ago=5)
        signals = detect_expired_uninspected(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_fewer_than_4_inspections(self, db):
        _insert_permit(db, "P001", status="expired")
        for i in range(3):
            _insert_inspection(db, "P001", result="PASSED", days_ago=30 + i)
        signals = detect_expired_uninspected(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_issued_permits(self, db):
        _insert_permit(db, "P001", status="issued")
        for i in range(5):
            _insert_inspection(db, "P001", result="PASSED", days_ago=30 + i)
        signals = detect_expired_uninspected(db, backend="duckdb")
        assert len(signals) == 0


class TestDetectStaleWithActivity:
    def test_finds_stale_with_recent_inspections(self, db):
        _insert_permit(db, "P001", status="issued", status_date_days_ago=800)
        _insert_inspection(db, "P001", result="PASSED", days_ago=100)
        _insert_inspection(db, "P001", result="FAILED", days_ago=200)
        signals = detect_stale_with_activity(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "stale_with_activity"

    def test_ignores_recent_permit(self, db):
        _insert_permit(db, "P001", status="issued", status_date_days_ago=300)
        _insert_inspection(db, "P001", result="PASSED", days_ago=100)
        _insert_inspection(db, "P001", result="FAILED", days_ago=200)
        signals = detect_stale_with_activity(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_old_inspections(self, db):
        _insert_permit(db, "P001", status="issued", status_date_days_ago=800)
        _insert_inspection(db, "P001", result="PASSED", days_ago=2000)
        _insert_inspection(db, "P001", result="FAILED", days_ago=2100)
        signals = detect_stale_with_activity(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_single_inspection(self, db):
        _insert_permit(db, "P001", status="issued", status_date_days_ago=800)
        _insert_inspection(db, "P001", result="PASSED", days_ago=100)
        signals = detect_stale_with_activity(db, backend="duckdb")
        assert len(signals) == 0


class TestDetectExpiredMinorActivity:
    def test_finds_expired_with_2_inspections(self, db):
        _insert_permit(db, "P001", status="expired")
        _insert_inspection(db, "P001", result="PASSED", days_ago=30)
        _insert_inspection(db, "P001", result="FAILED", days_ago=60)
        signals = detect_expired_minor_activity(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "expired_minor_activity"

    def test_ignores_4_plus_inspections(self, db):
        _insert_permit(db, "P001", status="expired")
        for i in range(4):
            _insert_inspection(db, "P001", result="PASSED", days_ago=30 + i)
        signals = detect_expired_minor_activity(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_zero_inspections(self, db):
        _insert_permit(db, "P001", status="expired")
        signals = detect_expired_minor_activity(db, backend="duckdb")
        assert len(signals) == 0


class TestDetectExpiredOtc:
    def test_finds_expired_otc_no_inspections(self, db):
        _insert_permit(db, "P001", status="expired", permit_type="8")
        signals = detect_expired_otc(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "expired_otc"
        assert signals[0].severity == "slower"

    def test_ignores_non_otc(self, db):
        _insert_permit(db, "P001", status="expired", permit_type="1")
        signals = detect_expired_otc(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_with_inspections(self, db):
        _insert_permit(db, "P001", status="expired", permit_type="8")
        _insert_inspection(db, "P001", result="PASSED", days_ago=30)
        signals = detect_expired_otc(db, backend="duckdb")
        assert len(signals) == 0


class TestDetectExpiredInconclusive:
    def test_finds_expired_non_otc_no_inspections(self, db):
        _insert_permit(db, "P001", status="expired", permit_type="1")
        signals = detect_expired_inconclusive(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "expired_inconclusive"
        assert signals[0].severity == "behind"

    def test_ignores_otc(self, db):
        _insert_permit(db, "P001", status="expired", permit_type="8")
        signals = detect_expired_inconclusive(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_with_inspections(self, db):
        _insert_permit(db, "P001", status="expired", permit_type="1")
        _insert_inspection(db, "P001", result="PASSED", days_ago=30)
        signals = detect_expired_inconclusive(db, backend="duckdb")
        assert len(signals) == 0


class TestDetectStaleNoActivity:
    def test_finds_stale_no_inspections(self, db):
        _insert_permit(db, "P001", status="issued", status_date_days_ago=800)
        signals = detect_stale_no_activity(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "stale_no_activity"
        assert signals[0].severity == "slower"

    def test_finds_stale_old_inspections(self, db):
        _insert_permit(db, "P001", status="issued", status_date_days_ago=800)
        _insert_inspection(db, "P001", result="PASSED", days_ago=2000)
        _insert_inspection(db, "P001", result="PASSED", days_ago=2100)
        signals = detect_stale_no_activity(db, backend="duckdb")
        assert len(signals) == 1

    def test_ignores_active_permit(self, db):
        _insert_permit(db, "P001", status="issued", status_date_days_ago=800)
        _insert_inspection(db, "P001", result="PASSED", days_ago=100)
        _insert_inspection(db, "P001", result="FAILED", days_ago=200)
        signals = detect_stale_no_activity(db, backend="duckdb")
        assert len(signals) == 0


# ── Complaint detectors ──────────────────────────────────────────

class TestDetectComplaint:
    def test_finds_open_complaint_no_nov(self, db):
        _insert_complaint(db)
        signals = detect_complaint(db, backend="duckdb")
        assert len(signals) == 1
        assert signals[0].signal_type == "complaint"
        assert signals[0].severity == "slower"

    def test_excludes_complaint_with_nov(self, db):
        _insert_complaint(db, block="3512", lot="001")
        _insert_violation(db, block="3512", lot="001", status="open")
        signals = detect_complaint(db, backend="duckdb")
        assert len(signals) == 0

    def test_ignores_closed_complaint(self, db):
        _insert_complaint(db, status="closed")
        signals = detect_complaint(db, backend="duckdb")
        assert len(signals) == 0
