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

def get_dashboard_data() -> dict:
    """Assemble all data for the bottleneck heatmap dashboard."""
    baselines = get_station_baselines()

    # Annotate each baseline with health tier
    annotated = []
    for b in baselines:
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
            "tier": _health_tier(b.median_days),
            "tier_label": TIER_LABELS.get(_health_tier(b.median_days), ""),
            "tier_css": TIER_CSS.get(_health_tier(b.median_days), ""),
        })

    stalled = _get_stalled_permits(limit=30)
    dept_rollup = _get_department_rollup(baselines)
    station_load = _get_station_load()

    # Summary stats
    total_stations = len(annotated)
    severe_stations = [s for s in annotated if s["tier"] in ("critical", "severe")]
    total_stalled = len(stalled)
    held_count = sum(1 for s in stalled if s.is_held)

    # Build load map for quick lookup in template
    load_map = {s.station: s for s in station_load}

    return {
        "baselines": annotated,
        "stalled_permits": stalled,
        "dept_rollup": dept_rollup,
        "station_load": station_load,
        "load_map": load_map,
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
