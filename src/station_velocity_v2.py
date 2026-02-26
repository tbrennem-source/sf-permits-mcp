"""Station velocity v2 — clean baselines from addenda routing data.

Data scrub filters applied:
  - Exclude pre-2018 data (sparse, inconsistent)
  - Exclude "Not Applicable" and "Administrative" review results
  - Exclude NULL stations
  - Deduplicate reassignment dupes (same permit+station+addenda_number → latest finish_date)
  - Separate initial review (addenda_number=0) from revision cycles (addenda_number>=1)

Computes p25/p50/p75/p90 per station per metric_type per period:
  - metric_type: "initial" (addenda_number=0) or "revision" (addenda_number>=1)
  - period: "all" (2018+), "2024", "2025", "2026", "recent_6mo"

Research findings (from 3.9M addenda rows, 1.06M permits):
  - 90.6% of rows have NULL review_results (intermediate routing steps)
  - "Administrative" (3.7%) and "Not Applicable" (0.3%) are pass-throughs
  - Reassignment dupes: some permits have 40+ entries at a single station
  - 95% of rows are initial review (addenda_number=0)
  - Pre-2018 data exists but is sparse (1721–2017) with garbage dates
  - Post-2018: 1.09M rows, ~226K permits for initial, ~3.3K for revisions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.db import BACKEND, get_connection, query, execute_write

logger = logging.getLogger(__name__)

# Minimum sample size for a station/period to be included
MIN_SAMPLES = 10

# Review results to exclude (pass-through / administrative routing)
EXCLUDED_RESULTS = ("Not Applicable", "Administrative")

# Periods to compute (legacy list — still used for mode='all')
PERIODS = ["all", "2024", "2025", "2026", "recent_6mo"]

# Two-period cron refresh config
VELOCITY_PERIODS = {
    'current': 90,    # rolling 90 days — primary for estimates
    'baseline': 365,  # rolling 1 year — trend comparison
}

# When 90-day sample < MIN_CURRENT_SAMPLES for a station, widen to CURRENT_WIDEN_DAYS
MIN_CURRENT_SAMPLES = 30
CURRENT_WIDEN_DAYS = 180


@dataclass
class StationVelocity:
    """Velocity stats for a station + metric_type + period."""
    station: str
    metric_type: str  # "initial" or "revision"
    p25_days: float | None = None
    p50_days: float | None = None
    p75_days: float | None = None
    p90_days: float | None = None
    sample_count: int = 0
    period: str = "all"


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


def _period_filter(period: str) -> tuple[str, list]:
    """Return SQL WHERE clause fragment and params for a period filter.

    The filter is on arrive::DATE (when the routing record arrived at station).
    """
    ph = _ph()
    if period == "all":
        return f"arrive::DATE >= {ph}", ["2018-01-01"]
    elif period == "recent_6mo":
        cutoff = (date.today() - timedelta(days=183)).isoformat()
        return f"arrive::DATE >= {ph}", [cutoff]
    elif period in ("2024", "2025", "2026"):
        return (
            f"arrive::DATE >= {ph} AND arrive::DATE < {ph}",
            [f"{period}-01-01", f"{int(period)+1}-01-01"],
        )
    else:
        return f"arrive::DATE >= {ph}", ["2018-01-01"]


def _rolling_period_filter(days: int) -> tuple[str, list]:
    """Return SQL WHERE clause fragment and params for a rolling N-day window from today."""
    ph = _ph()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return f"arrive::DATE >= {ph}", [cutoff]


def _date_diff_expr() -> str:
    """Return the SQL expression for days between arrive and finish_date."""
    if BACKEND == "postgres":
        return "EXTRACT(EPOCH FROM (finish_date::TIMESTAMP - arrive::TIMESTAMP)) / 86400.0"
    else:
        return "DATEDIFF('day', arrive::DATE, finish_date::DATE)"


def _compute_velocities_for_period(
    conn,
    period_clause: str,
    period_params: list,
    period_label: str,
) -> list[StationVelocity]:
    """Inner helper: compute velocity rows for a single (period_clause, period_label) pair."""
    results = []
    diff_expr = _date_diff_expr()

    for metric_type, addenda_filter in [
        ("initial", "addenda_number = 0"),
        ("revision", "addenda_number > 0"),
    ]:
        sql = f"""
            WITH filtered AS (
                SELECT application_number, station, addenda_number,
                       arrive, finish_date,
                       ROW_NUMBER() OVER (
                           PARTITION BY application_number, station, addenda_number
                           ORDER BY finish_date DESC NULLS LAST
                       ) as rn
                FROM addenda
                WHERE station IS NOT NULL
                  AND arrive IS NOT NULL
                  AND finish_date IS NOT NULL
                  AND {period_clause}
                  AND arrive::DATE <= CURRENT_DATE
                  AND {addenda_filter}
                  AND (review_results IS NULL
                       OR review_results NOT IN ('Not Applicable', 'Administrative'))
            ),
            durations AS (
                SELECT station, {diff_expr} AS days_in
                FROM filtered
                WHERE rn = 1
                  AND {diff_expr} BETWEEN 0 AND 365
            )
            SELECT
                station,
                COUNT(*) as n,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY days_in) as p25,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_in) as p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_in) as p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY days_in) as p90
            FROM durations
            GROUP BY station
            HAVING COUNT(*) >= {MIN_SAMPLES}
            ORDER BY station
        """

        try:
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(sql, period_params)
                    rows = cur.fetchall()
            else:
                sql_duck = sql.replace("%s", "?")
                rows = conn.execute(sql_duck, period_params).fetchall()
        except Exception:
            logger.warning(
                "_compute_velocities_for_period failed for period=%s metric=%s",
                period_label, metric_type, exc_info=True,
            )
            continue

        for row in rows:
            results.append(StationVelocity(
                station=row[0],
                metric_type=metric_type,
                p25_days=round(float(row[2]), 1) if row[2] is not None else None,
                p50_days=round(float(row[3]), 1) if row[3] is not None else None,
                p75_days=round(float(row[4]), 1) if row[4] is not None else None,
                p90_days=round(float(row[5]), 1) if row[5] is not None else None,
                sample_count=row[1],
                period=period_label,
            ))

    return results


def compute_station_velocity(
    conn=None,
    periods: list[str] | None = None,
    mode: str = 'cron',
) -> list[StationVelocity]:
    """Compute velocity baselines from addenda data.

    Args:
        conn: Optional DB connection; opened and closed internally if None.
        periods: Explicit period list. When provided, forces mode='all' behavior
                 (backward compatible with callers that pass periods=[...]).
        mode: 'cron' (default) — computes only 'current' (rolling 90d) and
              'baseline' (rolling 365d) periods for the nightly refresh.
              'all' — computes the original PERIODS list (backward compatible).
              If `periods` is explicitly passed, mode is forced to 'all'.

    Returns a list of StationVelocity objects, one per station/metric_type/period
    combination that has >= MIN_SAMPLES records.
    """
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    # If an explicit periods list was provided, always use legacy mode
    if periods is not None:
        mode = 'all'

    results = []

    try:
        if mode == 'cron':
            # Primary cron periods: 'current' (90 days) and 'baseline' (365 days)
            for period_label, days in VELOCITY_PERIODS.items():
                period_clause, period_params = _rolling_period_filter(days)
                period_results = _compute_velocities_for_period(
                    conn, period_clause, period_params, period_label
                )

                # For 'current' period: if any station has < MIN_CURRENT_SAMPLES,
                # widen that station to CURRENT_WIDEN_DAYS
                if period_label == 'current':
                    wide_clause, wide_params = _rolling_period_filter(CURRENT_WIDEN_DAYS)
                    wide_results = _compute_velocities_for_period(
                        conn, wide_clause, wide_params, 'current_wide'
                    )
                    wide_by_key = {
                        (v.station, v.metric_type): v for v in wide_results
                    }

                    final = []
                    for v in period_results:
                        if v.sample_count < MIN_CURRENT_SAMPLES:
                            wide = wide_by_key.get((v.station, v.metric_type))
                            if wide:
                                # Use wider window, but keep period label 'current'
                                final.append(StationVelocity(
                                    station=wide.station,
                                    metric_type=wide.metric_type,
                                    p25_days=wide.p25_days,
                                    p50_days=wide.p50_days,
                                    p75_days=wide.p75_days,
                                    p90_days=wide.p90_days,
                                    sample_count=wide.sample_count,
                                    period='current',
                                ))
                                continue
                        final.append(v)
                    results.extend(final)
                else:
                    results.extend(period_results)

        else:
            # mode='all' — backward-compatible: compute the original PERIODS list
            active_periods = periods if periods is not None else PERIODS
            for period in active_periods:
                period_clause, period_params = _period_filter(period)
                results.extend(
                    _compute_velocities_for_period(conn, period_clause, period_params, period)
                )

    finally:
        if close:
            conn.close()

    return results


# ── Persistence (station_velocity_v2 table) ────────────────────────


def ensure_velocity_v2_table(conn=None) -> None:
    """Create station_velocity_v2 table if it doesn't exist."""
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS station_velocity_v2 (
                        id SERIAL PRIMARY KEY,
                        station VARCHAR(30) NOT NULL,
                        metric_type VARCHAR(20) NOT NULL,
                        p25_days FLOAT,
                        p50_days FLOAT,
                        p75_days FLOAT,
                        p90_days FLOAT,
                        sample_count INTEGER NOT NULL,
                        period VARCHAR(20) NOT NULL,
                        updated_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(station, metric_type, period)
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sv2_station
                    ON station_velocity_v2(station)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sv2_period
                    ON station_velocity_v2(period)
                """)
                conn.commit()
        else:
            conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS seq_sv2_id START 1
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS station_velocity_v2 (
                    id INTEGER DEFAULT nextval('seq_sv2_id') PRIMARY KEY,
                    station VARCHAR(30) NOT NULL,
                    metric_type VARCHAR(20) NOT NULL,
                    p25_days FLOAT,
                    p50_days FLOAT,
                    p75_days FLOAT,
                    p90_days FLOAT,
                    sample_count INTEGER NOT NULL,
                    period VARCHAR(20) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(station, metric_type, period)
                )
            """)
    finally:
        if close:
            conn.close()


def refresh_velocity_v2(conn=None) -> dict:
    """Full refresh: truncate station_velocity_v2 and recompute all periods.

    Returns stats dict for logging.
    """
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        ensure_velocity_v2_table(conn)

        # Truncate
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE station_velocity_v2")
            conn.commit()
        else:
            try:
                conn.execute("DELETE FROM station_velocity_v2")
            except Exception:
                pass  # Table might not exist yet in DuckDB tests

        # Compute using cron mode (current + baseline periods)
        velocities = compute_station_velocity(conn, mode='cron')

        # Insert
        inserted = 0
        for v in velocities:
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO station_velocity_v2
                           (station, metric_type, p25_days, p50_days, p75_days,
                            p90_days, sample_count, period)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (station, metric_type, period)
                           DO UPDATE SET
                               p25_days = EXCLUDED.p25_days,
                               p50_days = EXCLUDED.p50_days,
                               p75_days = EXCLUDED.p75_days,
                               p90_days = EXCLUDED.p90_days,
                               sample_count = EXCLUDED.sample_count,
                               updated_at = NOW()
                        """,
                        (v.station, v.metric_type, v.p25_days, v.p50_days,
                         v.p75_days, v.p90_days, v.sample_count, v.period),
                    )
                inserted += 1
            else:
                conn.execute(
                    """INSERT INTO station_velocity_v2
                       (station, metric_type, p25_days, p50_days, p75_days,
                        p90_days, sample_count, period)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT (station, metric_type, period)
                       DO UPDATE SET
                           p25_days = EXCLUDED.p25_days,
                           p50_days = EXCLUDED.p50_days,
                           p75_days = EXCLUDED.p75_days,
                           p90_days = EXCLUDED.p90_days,
                           sample_count = EXCLUDED.sample_count
                    """,
                    (v.station, v.metric_type, v.p25_days, v.p50_days,
                     v.p75_days, v.p90_days, v.sample_count, v.period),
                )
                inserted += 1

        if BACKEND == "postgres":
            conn.commit()

        stations = len(set(v.station for v in velocities))
        active_period_labels = list(set(v.period for v in velocities))
        logger.info(
            "velocity_v2 refresh: %d rows inserted, %d stations, periods=%s",
            inserted, stations, active_period_labels,
        )
        return {
            "rows_inserted": inserted,
            "stations": stations,
            "periods": len(active_period_labels),
            "period_labels": active_period_labels,
        }
    finally:
        if close:
            conn.close()


# ── Query helpers ───────────────────────────────────────────────────


def get_velocity_for_station(
    station: str,
    metric_type: str = "initial",
    period: str = "recent_6mo",
    conn=None,
) -> StationVelocity | None:
    """Look up pre-computed velocity for a station.

    Falls back to "all" period if the requested period has no data.
    """
    ph = _ph()
    sql = f"""
        SELECT station, metric_type, p25_days, p50_days, p75_days,
               p90_days, sample_count, period
        FROM station_velocity_v2
        WHERE station = {ph} AND metric_type = {ph} AND period = {ph}
    """

    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql, (station, metric_type, period))
                row = cur.fetchone()
        else:
            row = conn.execute(
                sql.replace("%s", "?"), (station, metric_type, period)
            ).fetchone()

        if not row and period != "all":
            # Fallback to "all" period
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(sql, (station, metric_type, "all"))
                    row = cur.fetchone()
            else:
                row = conn.execute(
                    sql.replace("%s", "?"), (station, metric_type, "all")
                ).fetchone()

        if not row:
            return None

        return StationVelocity(
            station=row[0],
            metric_type=row[1],
            p25_days=float(row[2]) if row[2] is not None else None,
            p50_days=float(row[3]) if row[3] is not None else None,
            p75_days=float(row[4]) if row[4] is not None else None,
            p90_days=float(row[5]) if row[5] is not None else None,
            sample_count=row[6],
            period=row[7],
        )
    except Exception:
        logger.debug("get_velocity_for_station(%s) failed", station, exc_info=True)
        return None
    finally:
        if close:
            conn.close()


def get_all_velocities(
    period: str = "recent_6mo",
    metric_type: str | None = None,
    conn=None,
) -> list[StationVelocity]:
    """Return all velocity rows for a period, optionally filtered by metric_type."""
    ph = _ph()
    conditions = [f"period = {ph}"]
    params: list = [period]

    if metric_type:
        conditions.append(f"metric_type = {ph}")
        params.append(metric_type)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT station, metric_type, p25_days, p50_days, p75_days,
               p90_days, sample_count, period
        FROM station_velocity_v2
        WHERE {where}
        ORDER BY p50_days DESC NULLS LAST
    """

    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        else:
            rows = conn.execute(
                sql.replace("%s", "?"), params
            ).fetchall()

        return [
            StationVelocity(
                station=r[0], metric_type=r[1],
                p25_days=float(r[2]) if r[2] is not None else None,
                p50_days=float(r[3]) if r[3] is not None else None,
                p75_days=float(r[4]) if r[4] is not None else None,
                p90_days=float(r[5]) if r[5] is not None else None,
                sample_count=r[6], period=r[7],
            )
            for r in rows
        ]
    except Exception:
        logger.debug("get_all_velocities failed", exc_info=True)
        return []
    finally:
        if close:
            conn.close()
