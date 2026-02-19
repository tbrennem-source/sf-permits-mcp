"""Station velocity baselines — rolling averages of plan review turnaround.

Computes and caches per-station velocity metrics (avg/median/p75/p90 days
from arrive to finish_date) using rolling 90-day windows. Used by:
- Intelligence engine (stall detection relative to baseline)
- Property report (expected wait time for pending stations)
- Morning brief (bottleneck alerts)
- RAG operational chunks (station-specific guidance)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from src.db import BACKEND, query, execute_write

logger = logging.getLogger(__name__)


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


@dataclass
class StationBaseline:
    """Velocity baseline for a single station."""
    station: str
    samples: int = 0
    avg_days: float | None = None
    median_days: float | None = None
    p75_days: float | None = None
    p90_days: float | None = None
    min_days: float | None = None
    max_days: float | None = None
    computed_date: str | None = None

    @property
    def label(self) -> str:
        """Human-readable turnaround label."""
        if self.median_days is None:
            return "unknown"
        d = self.median_days
        if d < 1:
            return "same day"
        elif d < 7:
            return f"~{d:.0f} days"
        elif d < 30:
            weeks = d / 7
            return f"~{weeks:.0f} weeks"
        else:
            months = d / 30
            return f"~{months:.1f} months"


def _ensure_velocity_table() -> None:
    """Create station_velocity table if it doesn't exist."""
    if BACKEND == "postgres":
        execute_write("""
            CREATE TABLE IF NOT EXISTS station_velocity (
                station         TEXT NOT NULL,
                baseline_date   DATE NOT NULL DEFAULT CURRENT_DATE,
                lookback_days   INTEGER NOT NULL DEFAULT 90,
                samples         INTEGER NOT NULL DEFAULT 0,
                avg_days        NUMERIC(8,2),
                median_days     NUMERIC(8,2),
                p75_days        NUMERIC(8,2),
                p90_days        NUMERIC(8,2),
                min_days        NUMERIC(8,2),
                max_days        NUMERIC(8,2),
                computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (station, baseline_date)
            )
        """)
    # DuckDB: create in-memory during refresh; no persistent table needed


def refresh_station_velocity(lookback_days: int = 90) -> dict:
    """Recompute station velocity baselines from addenda table.

    Returns dict with station count and row count for logging.
    """
    _ensure_velocity_table()
    today = date.today()
    cutoff = today - timedelta(days=lookback_days)
    ph = _ph()

    if BACKEND == "postgres":
        # Use PostgreSQL percentile functions
        sql = f"""
            INSERT INTO station_velocity
                (station, baseline_date, lookback_days, samples,
                 avg_days, median_days, p75_days, p90_days, min_days, max_days)
            SELECT
                station,
                CURRENT_DATE,
                {lookback_days},
                COUNT(*),
                ROUND(AVG(days_in)::NUMERIC, 2),
                ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_in)::NUMERIC, 2),
                ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_in)::NUMERIC, 2),
                ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY days_in)::NUMERIC, 2),
                ROUND(MIN(days_in)::NUMERIC, 2),
                ROUND(MAX(days_in)::NUMERIC, 2)
            FROM (
                SELECT
                    station,
                    EXTRACT(EPOCH FROM (finish_date::TIMESTAMP - arrive::TIMESTAMP)) / 86400.0 AS days_in
                FROM addenda
                WHERE station IS NOT NULL
                  AND finish_date IS NOT NULL
                  AND arrive IS NOT NULL
                  AND finish_date::DATE >= {ph}
                  AND finish_date::DATE < CURRENT_DATE
                  AND EXTRACT(EPOCH FROM (finish_date::TIMESTAMP - arrive::TIMESTAMP)) / 86400.0
                      BETWEEN 0 AND 365
            ) sub
            GROUP BY station
            HAVING COUNT(*) >= 5
            ON CONFLICT (station, baseline_date) DO UPDATE SET
                samples = EXCLUDED.samples,
                avg_days = EXCLUDED.avg_days,
                median_days = EXCLUDED.median_days,
                p75_days = EXCLUDED.p75_days,
                p90_days = EXCLUDED.p90_days,
                min_days = EXCLUDED.min_days,
                max_days = EXCLUDED.max_days,
                computed_at = NOW()
        """
        execute_write(sql, (str(cutoff),))

        # Get stats
        rows = query(
            "SELECT COUNT(*), SUM(samples) FROM station_velocity "
            f"WHERE baseline_date = CURRENT_DATE"
        )
        station_count = rows[0][0] if rows else 0
        total_samples = rows[0][1] if rows else 0
        return {"stations": station_count, "samples": total_samples}

    else:
        # DuckDB fallback — compute on-the-fly, no persistent storage
        logger.info("Station velocity refresh skipped (DuckDB — compute on demand)")
        return {"stations": 0, "samples": 0}


def get_station_baselines() -> list[StationBaseline]:
    """Get the most recent velocity baselines for all stations.

    Returns list sorted by median_days descending (slowest first).
    """
    if BACKEND != "postgres":
        return _compute_baselines_live()

    try:
        rows = query(
            "SELECT station, samples, avg_days, median_days, p75_days, "
            "       p90_days, min_days, max_days, baseline_date "
            "FROM station_velocity "
            "WHERE baseline_date = (SELECT MAX(baseline_date) FROM station_velocity) "
            "ORDER BY median_days DESC NULLS LAST"
        )
    except Exception:
        logger.debug("get_station_baselines failed", exc_info=True)
        return []

    return [
        StationBaseline(
            station=r[0],
            samples=r[1],
            avg_days=float(r[2]) if r[2] is not None else None,
            median_days=float(r[3]) if r[3] is not None else None,
            p75_days=float(r[4]) if r[4] is not None else None,
            p90_days=float(r[5]) if r[5] is not None else None,
            min_days=float(r[6]) if r[6] is not None else None,
            max_days=float(r[7]) if r[7] is not None else None,
            computed_date=str(r[8]) if r[8] else None,
        )
        for r in rows
    ]


def get_station_baseline(station: str) -> StationBaseline | None:
    """Get baseline for a specific station."""
    ph = _ph()
    if BACKEND != "postgres":
        return _compute_baseline_live(station)

    try:
        rows = query(
            f"SELECT station, samples, avg_days, median_days, p75_days, "
            f"       p90_days, min_days, max_days, baseline_date "
            f"FROM station_velocity "
            f"WHERE station = {ph} "
            f"  AND baseline_date = (SELECT MAX(baseline_date) FROM station_velocity) ",
            (station,),
        )
    except Exception:
        logger.debug("get_station_baseline(%s) failed", station, exc_info=True)
        return None

    if not rows:
        return None

    r = rows[0]
    return StationBaseline(
        station=r[0],
        samples=r[1],
        avg_days=float(r[2]) if r[2] is not None else None,
        median_days=float(r[3]) if r[3] is not None else None,
        p75_days=float(r[4]) if r[4] is not None else None,
        p90_days=float(r[5]) if r[5] is not None else None,
        min_days=float(r[6]) if r[6] is not None else None,
        max_days=float(r[7]) if r[7] is not None else None,
        computed_date=str(r[8]) if r[8] else None,
    )


def _compute_baselines_live(lookback_days: int = 90) -> list[StationBaseline]:
    """Compute baselines on-the-fly for DuckDB (dev mode)."""
    cutoff = date.today() - timedelta(days=lookback_days)
    ph = _ph()
    try:
        rows = query(
            f"SELECT station, COUNT(*) as cnt, "
            f"       AVG(days_in) as avg_d, "
            f"       MEDIAN(days_in) as med_d "
            f"FROM ("
            f"  SELECT station, "
            f"    DATEDIFF('day', CAST(arrive AS DATE), CAST(finish_date AS DATE)) as days_in "
            f"  FROM addenda "
            f"  WHERE station IS NOT NULL "
            f"    AND finish_date IS NOT NULL AND arrive IS NOT NULL "
            f"    AND CAST(finish_date AS DATE) >= {ph} "
            f"    AND DATEDIFF('day', CAST(arrive AS DATE), CAST(finish_date AS DATE)) "
            f"        BETWEEN 0 AND 365 "
            f") sub "
            f"GROUP BY station HAVING COUNT(*) >= 5 "
            f"ORDER BY med_d DESC NULLS LAST",
            (str(cutoff),),
        )
    except Exception:
        logger.debug("_compute_baselines_live failed", exc_info=True)
        return []

    return [
        StationBaseline(
            station=r[0], samples=r[1],
            avg_days=float(r[2]) if r[2] is not None else None,
            median_days=float(r[3]) if r[3] is not None else None,
        )
        for r in rows
    ]


def _compute_baseline_live(station: str, lookback_days: int = 90) -> StationBaseline | None:
    """Compute single-station baseline on-the-fly (DuckDB dev mode)."""
    cutoff = date.today() - timedelta(days=lookback_days)
    ph = _ph()
    try:
        rows = query(
            f"SELECT COUNT(*), AVG(days_in), MEDIAN(days_in) "
            f"FROM ("
            f"  SELECT DATEDIFF('day', CAST(arrive AS DATE), CAST(finish_date AS DATE)) as days_in "
            f"  FROM addenda "
            f"  WHERE station = {ph} "
            f"    AND finish_date IS NOT NULL AND arrive IS NOT NULL "
            f"    AND CAST(finish_date AS DATE) >= {ph} "
            f"    AND DATEDIFF('day', CAST(arrive AS DATE), CAST(finish_date AS DATE)) "
            f"        BETWEEN 0 AND 365 "
            f") sub",
            (station, str(cutoff)),
        )
    except Exception:
        logger.debug("_compute_baseline_live(%s) failed", station, exc_info=True)
        return None

    if not rows or not rows[0] or (rows[0][0] or 0) < 5:
        return None

    return StationBaseline(
        station=station,
        samples=rows[0][0],
        avg_days=float(rows[0][1]) if rows[0][1] is not None else None,
        median_days=float(rows[0][2]) if rows[0][2] is not None else None,
    )
