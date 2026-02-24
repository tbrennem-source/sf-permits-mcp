"""Signal detectors — one function per signal type.

Each detect_* function takes a DB connection and returns list[Signal].
SQL uses %s placeholders (Postgres). For DuckDB, the pipeline converts them.

"Real inspections" = result IN ('PASSED', 'FAILED', 'DISAPPROVED').
"""

from __future__ import annotations

import logging
from src.signals.types import Signal, SIGNAL_CATALOG

logger = logging.getLogger(__name__)

PLANNING_STATIONS = ("PPC", "CP-ZOC", "CPB")
REAL_INSPECTION_RESULTS = ("PASSED", "FAILED", "DISAPPROVED")


def _exec(conn, sql, params=None, *, backend="postgres"):
    """Execute SQL, returning list of tuples. Handles Postgres vs DuckDB."""
    if backend == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    else:
        if params:
            sql = sql.replace("%s", "?")
        return conn.execute(sql, params or []).fetchall()


def _block_lot(block, lot):
    """Combine block+lot into a single key."""
    return f"{(block or '').strip()}/{(lot or '').strip()}"


# ── Addenda-based signals ─────────────────────────────────────────

def detect_hold_comments(conn, backend="postgres") -> list[Signal]:
    """Latest addenda record per (permit, station) where review_results = 'Issued Comments'
    and no subsequent record at same station with a different result."""
    sql = """
        WITH ranked AS (
            SELECT
                a.application_number,
                a.station,
                a.review_results,
                a.start_date,
                p.block,
                p.lot,
                ROW_NUMBER() OVER (
                    PARTITION BY a.application_number, a.station
                    ORDER BY a.addenda_number DESC, a.step DESC
                ) AS rn
            FROM addenda a
            JOIN permits p ON p.permit_number = a.application_number
            WHERE a.station IS NOT NULL
              AND a.review_results IS NOT NULL
        )
        SELECT application_number, station, block, lot
        FROM ranked
        WHERE rn = 1
          AND review_results = 'Issued Comments'
    """
    rows = _exec(conn, sql, backend=backend)
    severity = SIGNAL_CATALOG["hold_comments"].default_severity
    signals = []
    for app_num, station, block, lot in rows:
        signals.append(Signal(
            signal_type="hold_comments",
            severity=severity,
            permit_number=app_num,
            block_lot=_block_lot(block, lot),
            detail=f"Issued Comments at {station}",
        ))
    return signals


def detect_hold_stalled_planning(conn, backend="postgres") -> list[Signal]:
    """Station IN planning list, no finish_date, no review_results,
    start_date < NOW() - 1 year."""
    placeholders = ", ".join(["%s"] * len(PLANNING_STATIONS))
    sql = f"""
        WITH latest AS (
            SELECT
                a.application_number,
                a.station,
                a.start_date,
                a.finish_date,
                a.review_results,
                p.block,
                p.lot,
                ROW_NUMBER() OVER (
                    PARTITION BY a.application_number, a.station
                    ORDER BY a.addenda_number DESC, a.step DESC
                ) AS rn
            FROM addenda a
            JOIN permits p ON p.permit_number = a.application_number
            WHERE a.station IN ({placeholders})
        )
        SELECT application_number, station, block, lot
        FROM latest
        WHERE rn = 1
          AND finish_date IS NULL
          AND review_results IS NULL
          AND start_date IS NOT NULL
          AND start_date::date < CURRENT_DATE - INTERVAL '1 year'
    """
    rows = _exec(conn, sql, list(PLANNING_STATIONS), backend=backend)
    severity = SIGNAL_CATALOG["hold_stalled_planning"].default_severity
    signals = []
    for app_num, station, block, lot in rows:
        signals.append(Signal(
            signal_type="hold_stalled_planning",
            severity=severity,
            permit_number=app_num,
            block_lot=_block_lot(block, lot),
            detail=f"Stalled at {station} for 1yr+",
        ))
    return signals


def detect_hold_stalled(conn, backend="postgres") -> list[Signal]:
    """Non-planning station, no finish_date, no review_results,
    arrived >= 2020-01-01, start_date between 30d and 1yr ago."""
    placeholders = ", ".join(["%s"] * len(PLANNING_STATIONS))
    sql = f"""
        WITH latest AS (
            SELECT
                a.application_number,
                a.station,
                a.start_date,
                a.finish_date,
                a.review_results,
                p.block,
                p.lot,
                ROW_NUMBER() OVER (
                    PARTITION BY a.application_number, a.station
                    ORDER BY a.addenda_number DESC, a.step DESC
                ) AS rn
            FROM addenda a
            JOIN permits p ON p.permit_number = a.application_number
            WHERE a.station IS NOT NULL
              AND a.station NOT IN ({placeholders})
        )
        SELECT application_number, station, block, lot
        FROM latest
        WHERE rn = 1
          AND finish_date IS NULL
          AND review_results IS NULL
          AND start_date IS NOT NULL
          AND start_date::date >= '2020-01-01'
          AND start_date::date < CURRENT_DATE - INTERVAL '30 days'
          AND start_date::date >= CURRENT_DATE - INTERVAL '1 year'
    """
    rows = _exec(conn, sql, list(PLANNING_STATIONS), backend=backend)
    severity = SIGNAL_CATALOG["hold_stalled"].default_severity
    signals = []
    for app_num, station, block, lot in rows:
        signals.append(Signal(
            signal_type="hold_stalled",
            severity=severity,
            permit_number=app_num,
            block_lot=_block_lot(block, lot),
            detail=f"Stalled at {station} (30d-1yr dwell)",
        ))
    return signals


# ── Violation/enforcement-based signals ───────────────────────────

def detect_nov(conn, backend="postgres") -> list[Signal]:
    """Open NOVs — status NOT IN closed/complied/abated."""
    sql = """
        SELECT block, lot, COUNT(*) as cnt
        FROM violations
        WHERE LOWER(status) NOT IN ('closed', 'complied', 'abated')
          AND block IS NOT NULL AND lot IS NOT NULL
        GROUP BY block, lot
    """
    rows = _exec(conn, sql, backend=backend)
    severity = SIGNAL_CATALOG["nov"].default_severity
    signals = []
    for block, lot, cnt in rows:
        signals.append(Signal(
            signal_type="nov",
            severity=severity,
            permit_number=None,
            block_lot=_block_lot(block, lot),
            detail=f"{cnt} open NOV(s)",
        ))
    return signals


def detect_abatement(conn, backend="postgres") -> list[Signal]:
    """Violations with abatement/hearing category."""
    sql = """
        SELECT block, lot, COUNT(*) as cnt
        FROM violations
        WHERE LOWER(status) NOT IN ('closed', 'complied', 'abated')
          AND (LOWER(nov_category_description) LIKE '%abatement%'
               OR LOWER(nov_category_description) LIKE '%hearing%'
               OR LOWER(nov_category_description) LIKE '%director%')
          AND block IS NOT NULL AND lot IS NOT NULL
        GROUP BY block, lot
    """
    rows = _exec(conn, sql, backend=backend)
    severity = SIGNAL_CATALOG["abatement"].default_severity
    signals = []
    for block, lot, cnt in rows:
        signals.append(Signal(
            signal_type="abatement",
            severity=severity,
            permit_number=None,
            block_lot=_block_lot(block, lot),
            detail=f"{cnt} abatement/hearing action(s)",
        ))
    return signals


# ── Permit + inspection-based signals ─────────────────────────────

def detect_expired_uninspected(conn, backend="postgres") -> list[Signal]:
    """Expired permits with 4+ real inspections but no final."""
    sql = """
        SELECT p.permit_number, p.block, p.lot,
               COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) as real_cnt,
               COUNT(CASE WHEN LOWER(i.inspection_description) LIKE '%final%' THEN 1 END) as final_cnt
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'expired'
          AND p.block IS NOT NULL AND p.lot IS NOT NULL
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) >= 4
           AND COUNT(CASE WHEN LOWER(i.inspection_description) LIKE '%final%' THEN 1 END) = 0
    """
    rows = _exec(conn, sql, backend=backend)
    severity = SIGNAL_CATALOG["expired_uninspected"].default_severity
    signals = []
    for pn, block, lot, real_cnt, _final_cnt in rows:
        signals.append(Signal(
            signal_type="expired_uninspected",
            severity=severity,
            permit_number=pn,
            block_lot=_block_lot(block, lot),
            detail=f"Expired with {real_cnt} real inspections, no final",
        ))
    return signals


def detect_stale_with_activity(conn, backend="postgres") -> list[Signal]:
    """Issued 2yr+, latest real inspection within 5yr, 2+ real inspections."""
    sql = """
        SELECT p.permit_number, p.block, p.lot,
               COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) as real_cnt,
               MAX(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED')
                   THEN i.scheduled_date END) as latest_real
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'issued'
          AND p.status_date IS NOT NULL
          AND p.status_date::date < CURRENT_DATE - INTERVAL '2 years'
          AND p.block IS NOT NULL AND p.lot IS NOT NULL
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) >= 2
           AND MAX(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED')
                   THEN i.scheduled_date END)::date >= CURRENT_DATE - INTERVAL '5 years'
    """
    rows = _exec(conn, sql, backend=backend)
    severity = SIGNAL_CATALOG["stale_with_activity"].default_severity
    signals = []
    for pn, block, lot, real_cnt, latest_real in rows:
        signals.append(Signal(
            signal_type="stale_with_activity",
            severity=severity,
            permit_number=pn,
            block_lot=_block_lot(block, lot),
            detail=f"Issued 2yr+, {real_cnt} real inspections, last: {latest_real}",
        ))
    return signals


def detect_expired_minor_activity(conn, backend="postgres") -> list[Signal]:
    """Expired with 1-3 real inspections."""
    sql = """
        SELECT p.permit_number, p.block, p.lot,
               COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) as real_cnt
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'expired'
          AND p.block IS NOT NULL AND p.lot IS NOT NULL
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) BETWEEN 1 AND 3
    """
    rows = _exec(conn, sql, backend=backend)
    severity = SIGNAL_CATALOG["expired_minor_activity"].default_severity
    signals = []
    for pn, block, lot, real_cnt in rows:
        signals.append(Signal(
            signal_type="expired_minor_activity",
            severity=severity,
            permit_number=pn,
            block_lot=_block_lot(block, lot),
            detail=f"Expired with {real_cnt} real inspection(s)",
        ))
    return signals


def detect_expired_otc(conn, backend="postgres") -> list[Signal]:
    """Expired + zero real inspections + OTC type (permit_type = '8')."""
    sql = """
        SELECT p.permit_number, p.block, p.lot
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'expired'
          AND p.permit_type = '8'
          AND p.block IS NOT NULL AND p.lot IS NOT NULL
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) = 0
    """
    rows = _exec(conn, sql, backend=backend)
    severity = SIGNAL_CATALOG["expired_otc"].default_severity
    signals = []
    for pn, block, lot in rows:
        signals.append(Signal(
            signal_type="expired_otc",
            severity=severity,
            permit_number=pn,
            block_lot=_block_lot(block, lot),
            detail="Expired OTC, no real inspections",
        ))
    return signals


def detect_expired_inconclusive(conn, backend="postgres") -> list[Signal]:
    """Expired + zero real inspections + non-OTC."""
    sql = """
        SELECT p.permit_number, p.block, p.lot
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'expired'
          AND p.permit_type != '8'
          AND p.block IS NOT NULL AND p.lot IS NOT NULL
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) = 0
    """
    rows = _exec(conn, sql, backend=backend)
    severity = SIGNAL_CATALOG["expired_inconclusive"].default_severity
    signals = []
    for pn, block, lot in rows:
        signals.append(Signal(
            signal_type="expired_inconclusive",
            severity=severity,
            permit_number=pn,
            block_lot=_block_lot(block, lot),
            detail="Expired, non-OTC, no real inspections",
        ))
    return signals


def detect_stale_no_activity(conn, backend="postgres") -> list[Signal]:
    """Issued 2yr+, NOT matching stale_with_activity criteria
    (no meaningful recent inspections)."""
    sql = """
        SELECT p.permit_number, p.block, p.lot,
               COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) as real_cnt,
               MAX(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED')
                   THEN i.scheduled_date END) as latest_real
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'issued'
          AND p.status_date IS NOT NULL
          AND p.status_date::date < CURRENT_DATE - INTERVAL '2 years'
          AND p.block IS NOT NULL AND p.lot IS NOT NULL
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) < 2
            OR MAX(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED')
                   THEN i.scheduled_date END) IS NULL
            OR MAX(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED')
                   THEN i.scheduled_date END)::date < CURRENT_DATE - INTERVAL '5 years'
    """
    rows = _exec(conn, sql, backend=backend)
    severity = SIGNAL_CATALOG["stale_no_activity"].default_severity
    signals = []
    for pn, block, lot, real_cnt, latest_real in rows:
        signals.append(Signal(
            signal_type="stale_no_activity",
            severity=severity,
            permit_number=pn,
            block_lot=_block_lot(block, lot),
            detail=f"Issued 2yr+, {real_cnt} real inspections" + (
                f", last: {latest_real}" if latest_real else ", none recent"
            ),
        ))
    return signals


# ── Complaint-based signals ───────────────────────────────────────

def detect_complaint(conn, backend="postgres") -> list[Signal]:
    """Open complaints NOT associated with any NOV on same block_lot."""
    sql = """
        SELECT c.block, c.lot, COUNT(*) as cnt
        FROM complaints c
        WHERE LOWER(c.status) NOT IN ('closed', 'abated')
          AND c.block IS NOT NULL AND c.lot IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM violations v
              WHERE v.block = c.block AND v.lot = c.lot
                AND LOWER(v.status) NOT IN ('closed', 'complied', 'abated')
          )
        GROUP BY c.block, c.lot
    """
    rows = _exec(conn, sql, backend=backend)
    severity = SIGNAL_CATALOG["complaint"].default_severity
    signals = []
    for block, lot, cnt in rows:
        signals.append(Signal(
            signal_type="complaint",
            severity=severity,
            permit_number=None,
            block_lot=_block_lot(block, lot),
            detail=f"{cnt} open complaint(s), no NOV",
        ))
    return signals


# ── Collect all detectors ─────────────────────────────────────────

ALL_DETECTORS = [
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
]
