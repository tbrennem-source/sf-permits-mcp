"""Signal detectors — one function per signal type.

Each detector takes a DB connection and returns list[Signal].
Detection rules are derived from the v2 severity spec (validated Session 50).

All SQL uses DuckDB syntax. For Postgres deployment, the pipeline module
handles the backend switch.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from src.db import BACKEND
from src.signals.types import Signal, SIGNAL_CATALOG

logger = logging.getLogger(__name__)

# "Real" inspection results (not placeholders)
REAL_INSPECTION_RESULTS = ("PASSED", "FAILED", "DISAPPROVED")

# Planning stations where 1yr+ dwell = genuine planning block
PLANNING_STATIONS = ("PPC", "CP-ZOC", "CPB")


def _execute(conn, sql: str, params=None) -> list:
    """Execute SQL and return all rows. Works with DuckDB and Postgres."""
    if BACKEND == "postgres":
        sql = sql.replace("?", "%s")
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    if params:
        return conn.execute(sql, params).fetchall()
    return conn.execute(sql).fetchall()


def detect_hold_comments(conn) -> list[Signal]:
    """Detect permits where the latest addenda record at a station has review_results='Issued Comments'
    and no subsequent record at the same station with a different result."""
    sql = """
        WITH latest_per_station AS (
            SELECT application_number, station, review_results,
                   ROW_NUMBER() OVER (
                       PARTITION BY application_number, station
                       ORDER BY COALESCE(finish_date, '9999-12-31') DESC,
                              COALESCE(start_date, '9999-12-31') DESC, id DESC
                   ) as rn
            FROM addenda
            WHERE station IS NOT NULL
              AND review_results IS NOT NULL
              AND review_results != ''
        )
        SELECT DISTINCT l.application_number,
               COALESCE(p.block || '/' || p.lot, '') as block_lot,
               l.station
        FROM latest_per_station l
        LEFT JOIN permits p ON p.permit_number = l.application_number
        WHERE l.rn = 1
          AND l.review_results = 'Issued Comments'
    """
    rows = _execute(conn, sql)
    catalog = SIGNAL_CATALOG["hold_comments"]
    return [
        Signal(
            signal_type="hold_comments",
            severity=catalog.default_severity,
            permit_number=r[0],
            block_lot=r[1] or "",
            detail=f"Issued Comments at station {r[2]}",
        )
        for r in rows
    ]


def detect_hold_stalled_planning(conn) -> list[Signal]:
    """Detect permits stalled 1yr+ at planning stations (PPC, CP-ZOC, CPB)."""
    one_year_ago = (date.today() - timedelta(days=365)).isoformat()
    sql = """
        SELECT DISTINCT a.application_number,
               COALESCE(p.block || '/' || p.lot, '') as block_lot,
               a.station,
               a.start_date
        FROM addenda a
        LEFT JOIN permits p ON p.permit_number = a.application_number
        WHERE a.station IN ('PPC', 'CP-ZOC', 'CPB')
          AND a.finish_date IS NULL
          AND (a.review_results IS NULL OR a.review_results = '')
          AND a.start_date IS NOT NULL
          AND a.start_date::DATE < ?
    """
    rows = _execute(conn, sql, [one_year_ago])
    catalog = SIGNAL_CATALOG["hold_stalled_planning"]
    return [
        Signal(
            signal_type="hold_stalled_planning",
            severity=catalog.default_severity,
            permit_number=r[0],
            block_lot=r[1] or "",
            detail=f"Stalled at {r[2]} since {str(r[3])[:10] if r[3] else 'unknown'}",
        )
        for r in rows
    ]


def detect_hold_stalled(conn) -> list[Signal]:
    """Detect permits stalled 30d-1yr at non-planning stations.
    Recency filter: arrived >= 2020-01-01 to exclude data import artifacts."""
    thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
    one_year_ago = (date.today() - timedelta(days=365)).isoformat()
    sql = """
        SELECT DISTINCT a.application_number,
               COALESCE(p.block || '/' || p.lot, '') as block_lot,
               a.station,
               a.start_date
        FROM addenda a
        LEFT JOIN permits p ON p.permit_number = a.application_number
        WHERE a.station IS NOT NULL
          AND a.station NOT IN ('PPC', 'CP-ZOC', 'CPB')
          AND a.finish_date IS NULL
          AND (a.review_results IS NULL OR a.review_results = '')
          AND a.start_date IS NOT NULL
          AND a.start_date::DATE >= '2020-01-01'
          AND a.start_date::DATE < ?
          AND a.start_date::DATE >= ?
    """
    rows = _execute(conn, sql, [thirty_days_ago, one_year_ago])
    catalog = SIGNAL_CATALOG["hold_stalled"]
    return [
        Signal(
            signal_type="hold_stalled",
            severity=catalog.default_severity,
            permit_number=r[0],
            block_lot=r[1] or "",
            detail=f"Stalled at {r[2]} since {str(r[3])[:10] if r[3] else 'unknown'}",
        )
        for r in rows
    ]


def detect_nov(conn) -> list[Signal]:
    """Detect open Notices of Violation, grouped by block+lot."""
    sql = """
        SELECT block || '/' || lot as block_lot,
               COUNT(*) as nov_count
        FROM violations
        WHERE status NOT IN ('closed', 'complied', 'abated', 'Closed', 'Complied', 'Abated')
          AND block IS NOT NULL AND lot IS NOT NULL
        GROUP BY block, lot
    """
    rows = _execute(conn, sql)
    catalog = SIGNAL_CATALOG["nov"]
    return [
        Signal(
            signal_type="nov",
            severity=catalog.default_severity,
            permit_number=None,
            block_lot=r[0],
            detail=f"{r[1]} open NOV(s)",
        )
        for r in rows
    ]


def detect_abatement(conn) -> list[Signal]:
    """Detect violations with abatement/hearing category."""
    sql = """
        SELECT block || '/' || lot as block_lot,
               COUNT(*) as cnt
        FROM violations
        WHERE (LOWER(nov_category_description) LIKE '%abatement%'
               OR LOWER(nov_category_description) LIKE '%hearing%'
               OR LOWER(nov_category_description) LIKE '%director%')
          AND status NOT IN ('closed', 'complied', 'abated', 'Closed', 'Complied', 'Abated')
          AND block IS NOT NULL AND lot IS NOT NULL
        GROUP BY block, lot
    """
    rows = _execute(conn, sql)
    catalog = SIGNAL_CATALOG["abatement"]
    return [
        Signal(
            signal_type="abatement",
            severity=catalog.default_severity,
            permit_number=None,
            block_lot=r[0],
            detail=f"{r[1]} abatement/hearing order(s)",
        )
        for r in rows
    ]


def detect_expired_uninspected(conn) -> list[Signal]:
    """Detect expired permits with 4+ real inspections but no final inspection."""
    sql = """
        SELECT p.permit_number,
               COALESCE(p.block || '/' || p.lot, '') as block_lot,
               COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) as real_insp,
               SUM(CASE WHEN LOWER(i.inspection_description) LIKE '%final%' THEN 1 ELSE 0 END) as finals
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'expired'
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) >= 4
           AND SUM(CASE WHEN LOWER(i.inspection_description) LIKE '%final%' THEN 1 ELSE 0 END) = 0
    """
    rows = _execute(conn, sql)
    catalog = SIGNAL_CATALOG["expired_uninspected"]
    return [
        Signal(
            signal_type="expired_uninspected",
            severity=catalog.default_severity,
            permit_number=r[0],
            block_lot=r[1] or "",
            detail=f"Expired with {r[2]} real inspections, no final",
        )
        for r in rows
    ]


def detect_stale_with_activity(conn) -> list[Signal]:
    """Detect issued permits open 2yr+ with recent inspection activity.
    Criteria: issued 2yr+, latest real inspection within 5yr, 2+ real inspections."""
    two_years_ago = (date.today() - timedelta(days=730)).isoformat()
    five_years_ago = (date.today() - timedelta(days=1825)).isoformat()
    sql = """
        SELECT p.permit_number,
               COALESCE(p.block || '/' || p.lot, '') as block_lot,
               COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) as real_insp,
               MAX(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED')
                        THEN i.scheduled_date END) as latest_real
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'issued'
          AND p.issued_date IS NOT NULL
          AND p.issued_date::DATE < ?
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) >= 2
           AND MAX(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED')
                        THEN i.scheduled_date END) >= ?
    """
    rows = _execute(conn, sql, [two_years_ago, five_years_ago])
    catalog = SIGNAL_CATALOG["stale_with_activity"]
    return [
        Signal(
            signal_type="stale_with_activity",
            severity=catalog.default_severity,
            permit_number=r[0],
            block_lot=r[1] or "",
            detail=f"Issued 2yr+, {r[2]} real inspections, latest {str(r[3])[:10] if r[3] else 'unknown'}",
        )
        for r in rows
    ]


def detect_expired_minor_activity(conn) -> list[Signal]:
    """Detect expired permits with 1-3 real inspections."""
    sql = """
        SELECT p.permit_number,
               COALESCE(p.block || '/' || p.lot, '') as block_lot,
               COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) as real_insp
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'expired'
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) BETWEEN 1 AND 3
    """
    rows = _execute(conn, sql)
    catalog = SIGNAL_CATALOG["expired_minor_activity"]
    return [
        Signal(
            signal_type="expired_minor_activity",
            severity=catalog.default_severity,
            permit_number=r[0],
            block_lot=r[1] or "",
            detail=f"Expired with {r[2]} real inspections",
        )
        for r in rows
    ]


def detect_expired_inconclusive(conn) -> list[Signal]:
    """Detect expired permits with zero real inspections and non-OTC type."""
    sql = """
        SELECT p.permit_number,
               COALESCE(p.block || '/' || p.lot, '') as block_lot
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'expired'
          AND p.permit_type != '8'
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) = 0
    """
    rows = _execute(conn, sql)
    catalog = SIGNAL_CATALOG["expired_inconclusive"]
    return [
        Signal(
            signal_type="expired_inconclusive",
            severity=catalog.default_severity,
            permit_number=r[0],
            block_lot=r[1] or "",
            detail="Expired, zero real inspections, non-OTC",
        )
        for r in rows
    ]


def detect_expired_otc(conn) -> list[Signal]:
    """Detect expired OTC permits with zero real inspections."""
    sql = """
        SELECT p.permit_number,
               COALESCE(p.block || '/' || p.lot, '') as block_lot
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'expired'
          AND p.permit_type = '8'
        GROUP BY p.permit_number, p.block, p.lot
        HAVING COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) = 0
    """
    rows = _execute(conn, sql)
    catalog = SIGNAL_CATALOG["expired_otc"]
    return [
        Signal(
            signal_type="expired_otc",
            severity=catalog.default_severity,
            permit_number=r[0],
            block_lot=r[1] or "",
            detail="Expired OTC, zero real inspections",
        )
        for r in rows
    ]


def detect_stale_no_activity(conn) -> list[Signal]:
    """Detect stale issued permits without meaningful recent inspections.
    Issued 2yr+ AND NOT matching stale_with_activity criteria."""
    two_years_ago = (date.today() - timedelta(days=730)).isoformat()
    five_years_ago = (date.today() - timedelta(days=1825)).isoformat()
    sql = """
        SELECT p.permit_number,
               COALESCE(p.block || '/' || p.lot, '') as block_lot,
               COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) as real_insp,
               MAX(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED')
                        THEN i.scheduled_date END) as latest_real
        FROM permits p
        LEFT JOIN inspections i ON i.reference_number = p.permit_number
        WHERE LOWER(p.status) = 'issued'
          AND p.issued_date IS NOT NULL
          AND p.issued_date::DATE < ?
        GROUP BY p.permit_number, p.block, p.lot
        HAVING NOT (
            COUNT(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED') THEN 1 END) >= 2
            AND MAX(CASE WHEN i.result IN ('PASSED', 'FAILED', 'DISAPPROVED')
                         THEN i.scheduled_date END) >= ?
        )
    """
    rows = _execute(conn, sql, [two_years_ago, five_years_ago])
    catalog = SIGNAL_CATALOG["stale_no_activity"]
    return [
        Signal(
            signal_type="stale_no_activity",
            severity=catalog.default_severity,
            permit_number=r[0],
            block_lot=r[1] or "",
            detail=f"Stale issued, {r[2]} real inspections" + (
                f", latest {str(r[3])[:10]}" if r[3] else ", none recent"
            ),
        )
        for r in rows
    ]


def detect_complaint(conn) -> list[Signal]:
    """Detect open complaints not associated with any NOV on the same block_lot."""
    sql = """
        SELECT c.block || '/' || c.lot as block_lot,
               COUNT(*) as cnt
        FROM complaints c
        WHERE LOWER(c.status) NOT IN ('closed', 'abated')
          AND c.block IS NOT NULL AND c.lot IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM violations v
              WHERE v.block = c.block AND v.lot = c.lot
                AND v.status NOT IN ('closed', 'complied', 'abated', 'Closed', 'Complied', 'Abated')
          )
        GROUP BY c.block, c.lot
    """
    rows = _execute(conn, sql)
    catalog = SIGNAL_CATALOG["complaint"]
    return [
        Signal(
            signal_type="complaint",
            severity=catalog.default_severity,
            permit_number=None,
            block_lot=r[0],
            detail=f"{r[1]} open complaint(s), no associated NOV",
        )
        for r in rows
    ]


# All detectors in execution order
ALL_DETECTORS = [
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
]
