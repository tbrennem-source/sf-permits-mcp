"""Velocity dashboard data assembly — bottleneck heatmap for the DBI approval pipeline.

Aggregates station velocity baselines, currently stalled permits, and
department-level rollups for the /dashboard/bottlenecks page.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.db import BACKEND, query
from web.station_velocity import get_station_baselines, StationBaseline

logger = logging.getLogger(__name__)


# ── Portfolio station detection ───────────────────────────────────────────────

def get_portfolio_stations(user_id: int) -> dict:
    """Find stations where the user's watched permits are currently pending.

    Returns:
        {
          "stations": set[str],          # station codes with user's permits pending
          "permit_map": {permit: station} # which permit is at which station
          "permit_numbers": list[str],    # all watched permit numbers (any type)
        }
    """
    from web.auth import get_watches
    watches = get_watches(user_id)

    # Collect all permit numbers from watch items
    permit_numbers: list[str] = []
    for w in watches:
        if w.get("permit_number"):
            permit_numbers.append(w["permit_number"].strip())
        # For parcel/address watches, we'd need to look up permits — skip for now
        # (Most power users watch by permit number directly)

    if not permit_numbers:
        return {"stations": set(), "permit_map": {}, "permit_numbers": []}

    ph = _ph()
    placeholders = ", ".join([ph] * len(permit_numbers))

    try:
        rows = query(
            f"""
            SELECT DISTINCT application_number, station
            FROM addenda
            WHERE application_number IN ({placeholders})
              AND finish_date IS NULL
              AND arrive IS NOT NULL
            ORDER BY station
            """,
            permit_numbers,
        )
    except Exception:
        logger.debug("get_portfolio_stations query failed", exc_info=True)
        rows = []

    stations: set[str] = set()
    permit_map: dict[str, str] = {}
    for r in rows:
        pnum = r[0] or ""
        station = r[1] or ""
        if station:
            stations.add(station.upper())
        if pnum and station:
            permit_map[pnum] = station.upper()

    return {
        "stations": stations,
        "permit_map": permit_map,
        "permit_numbers": permit_numbers,
    }


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


# ── Health thresholds (in median days) ───────────────────────────────────────

def _health_tier(median_days: float | None) -> str:
    """Return color tier based on median turnaround days."""
    if median_days is None:
        return "unknown"
    if median_days < 1:
        return "fast"       # green — same day
    elif median_days < 7:
        return "normal"     # blue — within a week
    elif median_days < 30:
        return "slow"       # yellow — weeks
    elif median_days < 90:
        return "critical"   # orange — months
    else:
        return "severe"     # red — quarter+


TIER_LABELS = {
    "fast": "Same day",
    "normal": "Days",
    "slow": "Weeks",
    "critical": "Months",
    "severe": "Quarter+",
    "unknown": "No data",
}

TIER_CSS = {
    "fast": "tier-fast",
    "normal": "tier-normal",
    "slow": "tier-slow",
    "critical": "tier-critical",
    "severe": "tier-severe",
    "unknown": "tier-unknown",
}


# ── Currently stalled / held queries ─────────────────────────────────────────

@dataclass
class StalledPermit:
    permit_number: str
    station: str
    days_pending: int
    reviewer: str | None
    hold_description: str | None
    is_held: bool


def _get_stalled_permits(limit: int = 50) -> list[StalledPermit]:
    """Fetch permits currently stalled (pending >14 days, no finish_date)."""
    ph = _ph()
    try:
        if BACKEND == "postgres":
            rows = query(
                f"""
                SELECT
                    application_number,
                    station,
                    CURRENT_DATE - arrive::date AS days_pending,
                    plan_checked_by,
                    hold_description,
                    CASE WHEN hold_description IS NOT NULL AND hold_description != ''
                         THEN TRUE ELSE FALSE END AS is_held
                FROM addenda
                WHERE finish_date IS NULL
                  AND arrive IS NOT NULL
                  AND CURRENT_DATE - arrive::date > 14
                ORDER BY days_pending DESC NULLS LAST
                LIMIT {ph}
                """,
                (limit,),
            )
        else:
            rows = query(
                f"""
                SELECT
                    application_number,
                    station,
                    CAST(julianday('now') - julianday(arrive) AS INTEGER) AS days_pending,
                    plan_checked_by,
                    hold_description,
                    CASE WHEN hold_description IS NOT NULL AND hold_description != ''
                         THEN 1 ELSE 0 END AS is_held
                FROM addenda
                WHERE finish_date IS NULL
                  AND arrive IS NOT NULL
                  AND julianday('now') - julianday(arrive) > 14
                ORDER BY days_pending DESC
                LIMIT {ph}
                """,
                (limit,),
            )
    except Exception:
        logger.debug("_get_stalled_permits query failed", exc_info=True)
        return []

    return [
        StalledPermit(
            permit_number=r[0] or "",
            station=r[1] or "",
            days_pending=int(r[2]) if r[2] is not None else 0,
            reviewer=r[3] or None,
            hold_description=(r[4] or "").strip() or None,
            is_held=bool(r[5]),
        )
        for r in rows
    ]


# ── Department rollup ────────────────────────────────────────────────────────

@dataclass
class DeptRollup:
    department: str
    station_count: int
    total_samples: int
    avg_median_days: float | None
    slowest_station: str | None
    slowest_days: float | None


def _get_department_rollup(baselines: list[StationBaseline]) -> list[DeptRollup]:
    """Group station baselines by department prefix."""
    # Map station codes to departments (approximate by prefix or known codes)
    dept_map: dict[str, str] = {}
    ph = _ph()
    try:
        rows = query(
            "SELECT DISTINCT station, department FROM addenda "
            "WHERE department IS NOT NULL LIMIT 2000"
        )
        for r in rows:
            if r[0] and r[1]:
                dept_map[r[0].upper()] = r[1].upper()
    except Exception:
        logger.debug("dept_map query failed", exc_info=True)

    # Fallback: infer department from station code prefix
    def _infer_dept(station: str) -> str:
        s = station.upper()
        if s.startswith("SFFD") or s in ("FS", "FIRE"):
            return "SFFD"
        if s.startswith("CP") or s in ("PPC", "LPA", "PLANNING"):
            return "CPC"
        if s.startswith("PUC") or "UTILITIES" in s:
            return "PUC"
        if s.startswith("DPW") or s in ("TRAFFIC", "BOE"):
            return "DPW"
        if s.startswith("DPH") or "HEALTH" in s:
            return "DPH"
        return "DBI"

    dept_groups: dict[str, list[StationBaseline]] = {}
    for b in baselines:
        dept = dept_map.get(b.station.upper()) or _infer_dept(b.station)
        dept_groups.setdefault(dept, []).append(b)

    rollups = []
    for dept, stations in sorted(dept_groups.items()):
        medians = [s.median_days for s in stations if s.median_days is not None]
        samples = sum(s.samples for s in stations)
        avg_median = round(sum(medians) / len(medians), 1) if medians else None
        slowest = max(stations, key=lambda s: s.median_days or 0) if stations else None
        rollups.append(DeptRollup(
            department=dept,
            station_count=len(stations),
            total_samples=samples,
            avg_median_days=avg_median,
            slowest_station=slowest.station if slowest else None,
            slowest_days=slowest.median_days if slowest else None,
        ))

    return sorted(rollups, key=lambda d: d.avg_median_days or 0, reverse=True)


# ── Reviewer stats per station ──────────────────────────────────────────────

def get_reviewer_stats(station: str, lookback_days: int = 90) -> list[dict]:
    """Return per-reviewer velocity stats for a given station.

    Computes median turnaround per plan_checked_by reviewer over the last
    lookback_days, plus current pending count per reviewer.

    Returns list of dicts sorted by median_days asc (fastest first):
        [{"reviewer": str, "completed": int, "median_days": float|None,
          "avg_days": float|None, "pending": int}, ...]
    """
    ph = _ph()
    cutoff_clause = ""

    try:
        if BACKEND == "postgres":
            hist_rows = query(
                f"""
                SELECT
                    plan_checked_by,
                    COUNT(*) AS completed,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY (finish_date::date - arrive::date)
                    ) AS median_days,
                    AVG(finish_date::date - arrive::date) AS avg_days
                FROM addenda
                WHERE station = {ph}
                  AND plan_checked_by IS NOT NULL
                  AND plan_checked_by != ''
                  AND finish_date IS NOT NULL
                  AND arrive IS NOT NULL
                  AND (finish_date::date - arrive::date) BETWEEN 0 AND 365
                  AND finish_date::date >= CURRENT_DATE - INTERVAL '{lookback_days} days'
                GROUP BY plan_checked_by
                HAVING COUNT(*) >= 2
                ORDER BY median_days ASC
                LIMIT 20
                """,
                (station,),
            )
        else:
            # DuckDB dev mode
            from datetime import date as _date, timedelta
            cutoff = (_date.today() - timedelta(days=lookback_days)).isoformat()
            hist_rows = query(
                f"""
                SELECT
                    plan_checked_by,
                    COUNT(*) AS completed,
                    MEDIAN(DATEDIFF('day', CAST(arrive AS DATE), CAST(finish_date AS DATE))) AS median_days,
                    AVG(DATEDIFF('day', CAST(arrive AS DATE), CAST(finish_date AS DATE))) AS avg_days
                FROM addenda
                WHERE station = {ph}
                  AND plan_checked_by IS NOT NULL
                  AND plan_checked_by != ''
                  AND finish_date IS NOT NULL
                  AND arrive IS NOT NULL
                  AND DATEDIFF('day', CAST(arrive AS DATE), CAST(finish_date AS DATE)) BETWEEN 0 AND 365
                  AND CAST(finish_date AS DATE) >= {ph}
                GROUP BY plan_checked_by
                HAVING COUNT(*) >= 2
                ORDER BY median_days ASC
                LIMIT 20
                """,
                (station, cutoff),
            )
    except Exception:
        logger.debug("reviewer hist query failed for %s", station, exc_info=True)
        hist_rows = []

    # Current pending per reviewer
    pending_map: dict[str, int] = {}
    try:
        pend_rows = query(
            f"""
            SELECT plan_checked_by, COUNT(*) AS pending
            FROM addenda
            WHERE station = {ph}
              AND plan_checked_by IS NOT NULL
              AND plan_checked_by != ''
              AND finish_date IS NULL
              AND arrive IS NOT NULL
            GROUP BY plan_checked_by
            """,
            (station,),
        )
        for r in pend_rows:
            if r[0]:
                pending_map[r[0]] = int(r[1]) if r[1] else 0
    except Exception:
        logger.debug("reviewer pending query failed for %s", station, exc_info=True)

    results = []
    for r in hist_rows:
        reviewer = r[0] or ""
        completed = int(r[1]) if r[1] else 0
        median_d = round(float(r[2]), 1) if r[2] is not None else None
        avg_d = round(float(r[3]), 1) if r[3] is not None else None
        results.append({
            "reviewer": reviewer,
            "completed": completed,
            "median_days": median_d,
            "avg_days": avg_d,
            "pending": pending_map.get(reviewer, 0),
            "tier": _health_tier(median_d),
        })

    return results


# ── Volume by station (how many permits currently at each station) ──────────

@dataclass
class StationLoad:
    station: str
    pending_count: int
    held_count: int
    avg_days_waiting: float | None


def _get_station_load() -> list[StationLoad]:
    """Count permits currently pending (no finish_date) per station."""
    ph = _ph()
    try:
        if BACKEND == "postgres":
            rows = query(
                """
                SELECT
                    station,
                    COUNT(*) AS pending,
                    SUM(CASE WHEN hold_description IS NOT NULL
                             AND hold_description != '' THEN 1 ELSE 0 END) AS held,
                    AVG(CURRENT_DATE - arrive::date) AS avg_wait
                FROM addenda
                WHERE finish_date IS NULL
                  AND arrive IS NOT NULL
                GROUP BY station
                ORDER BY pending DESC
                LIMIT 30
                """
            )
        else:
            rows = query(
                """
                SELECT
                    station,
                    COUNT(*) AS pending,
                    SUM(CASE WHEN hold_description IS NOT NULL
                             AND hold_description != '' THEN 1 ELSE 0 END) AS held,
                    AVG(CAST(julianday('now') - julianday(arrive) AS INTEGER)) AS avg_wait
                FROM addenda
                WHERE finish_date IS NULL
                  AND arrive IS NOT NULL
                GROUP BY station
                ORDER BY pending DESC
                LIMIT 30
                """
            )
    except Exception:
        logger.debug("_get_station_load query failed", exc_info=True)
        return []

    return [
        StationLoad(
            station=r[0] or "UNKNOWN",
            pending_count=int(r[1]) if r[1] else 0,
            held_count=int(r[2]) if r[2] else 0,
            avg_days_waiting=round(float(r[3]), 1) if r[3] is not None else None,
        )
        for r in rows
    ]


# ── Main assembly ────────────────────────────────────────────────────────────

def get_dashboard_data(user_id: int | None = None) -> dict:
    """Assemble all data for the bottleneck heatmap dashboard.

    If user_id is given, also computes portfolio_stations so the template
    can highlight / filter to permits the user is actively watching.
    """
    baselines = get_station_baselines()

    # Portfolio stations (if user_id provided)
    portfolio: dict = {"stations": set(), "permit_map": {}, "permit_numbers": []}
    if user_id is not None:
        try:
            portfolio = get_portfolio_stations(user_id)
        except Exception:
            logger.debug("get_portfolio_stations failed", exc_info=True)

    portfolio_stations: set[str] = portfolio["stations"]

    # Build dept map from addenda for annotation
    dept_map: dict[str, str] = {}
    try:
        dept_rows = query(
            "SELECT DISTINCT station, department FROM addenda "
            "WHERE department IS NOT NULL LIMIT 2000"
        )
        for r in dept_rows:
            if r[0] and r[1]:
                dept_map[r[0].upper()] = r[1].upper()
    except Exception:
        logger.debug("dept_map pre-load failed", exc_info=True)

    def _infer_dept_for_station(station: str) -> str:
        s = station.upper()
        mapped = dept_map.get(s)
        if mapped:
            return mapped
        if s.startswith("SFFD") or s in ("FS", "FIRE"):
            return "SFFD"
        if s.startswith("CP") or s in ("PPC", "LPA", "PLANNING"):
            return "CPC"
        if s.startswith("PUC") or "UTILITIES" in s:
            return "PUC"
        if s.startswith("DPW") or s in ("TRAFFIC", "BOE"):
            return "DPW"
        if s.startswith("DPH") or "HEALTH" in s:
            return "DPH"
        return "DBI"

    # Annotate each baseline with health tier, dept, and portfolio flag
    annotated = []
    for b in baselines:
        tier = _health_tier(b.median_days)
        dept = _infer_dept_for_station(b.station)
        annotated.append({
            "station": b.station,
            "samples": b.samples,
            "avg_days": b.avg_days,
            "median_days": b.median_days,
            "p75_days": b.p75_days,
            "p90_days": b.p90_days,
            "min_days": b.min_days,
            "max_days": b.max_days,
            "label": b.label,
            "tier": tier,
            "tier_label": TIER_LABELS.get(tier, ""),
            "tier_css": TIER_CSS.get(tier, ""),
            "dept": dept,
            "in_portfolio": b.station.upper() in portfolio_stations,
        })

    stalled = _get_stalled_permits(limit=50)
    dept_rollup = _get_department_rollup(baselines)
    station_load = _get_station_load()

    # Summary stats
    total_stations = len(annotated)
    severe_stations = [s for s in annotated if s["tier"] in ("critical", "severe")]
    total_stalled = len(stalled)
    held_count = sum(1 for s in stalled if s.is_held)

    # Build load map for quick lookup in template
    load_map = {s.station: s for s in station_load}

    # Dept list for filter UI (sorted)
    dept_list = sorted({s["dept"] for s in annotated})

    return {
        "baselines": annotated,
        "stalled_permits": stalled,
        "dept_rollup": dept_rollup,
        "station_load": station_load,
        "load_map": load_map,
        "portfolio": {
            "stations": sorted(portfolio_stations),
            "permit_map": portfolio["permit_map"],
            "permit_numbers": portfolio["permit_numbers"],
            "count": len(portfolio_stations),
        },
        "dept_list": dept_list,
        "summary": {
            "total_stations": total_stations,
            "severe_stations": len(severe_stations),
            "total_stalled": total_stalled,
            "held_count": held_count,
            "fastest_station": annotated[-1]["station"] if annotated else None,
            "slowest_station": annotated[0]["station"] if annotated else None,
            "slowest_days": annotated[0]["median_days"] if annotated else None,
        },
    }
