"""Tool: estimate_timeline — Estimate permit processing timelines from historical data.

v2 integration: reads station-level velocity from station_velocity_v2 table
(computed from cleaned addenda routing data — deduped, post-2018, excluding
Administrative/Not Applicable pass-throughs). Falls back to v1 timeline_stats
if v2 data is unavailable.

Sprint 58A: Station-sum model is now PRIMARY. Aggregate timeline_stats is
used as fallback only when no station_velocity_v2 data matches.
"""

import logging
from datetime import date as _date

from src.db import get_connection, BACKEND
from src.tools.knowledge_base import format_sources

logger = logging.getLogger(__name__)

DELAY_FACTORS = {
    "change_of_use": "+30 days minimum: Section 311 neighborhood notification",
    "planning_review": "+2-6 weeks: Planning Department review",
    "dph_review": "+2-4 weeks: DPH health permit review (food service)",
    "fire_review": "+1-3 weeks: Fire Department plan review",
    "historic": "+4-12 weeks: Historic preservation review (HPC)",
    "ceqa": "+3-12 months: CEQA environmental review (if triggered)",
    "multi_agency": "+1-2 weeks per additional reviewing agency",
    "conditional_use": "+3+ months: Planning Commission CU hearing",
}

# Map trigger keywords to station codes for v2 station velocity lookups.
# Station codes validated against station_velocity_v2 (2026-02-26).
TRIGGER_STATION_MAP = {
    "planning_review": ["CP-ZOC"],
    "dph_review": ["HEALTH", "HEALTH-FD", "HEALTH-HM", "HEALTH-MH"],
    "fire_review": ["SFFD", "SFFD-HQ"],
    "historic": ["HIS"],
    "multi_agency": ["DPW-BSM", "DPW-BUF", "SFPUC", "SFPUC-PRG"],
    # legacy aliases
    "dph_food_facility": ["HEALTH", "HEALTH-FD"],
    "fire_suppression": ["SFFD", "SFFD-HQ"],
    "historic_preservation": ["HIS"],
    "seismic_retrofit": ["BLDG"],
    "adu_specific": ["BLDG", "CP-ZOC"],
    "ada_path_of_travel": ["PW-DAC"],
    "title24": ["BLDG"],
}

# Trend threshold: ±15% deviation from baseline = flagged
TREND_THRESHOLD_PCT = 15.0


def _ensure_timeline_stats(conn) -> None:
    """Create timeline_stats table if it doesn't exist.

    On Postgres (production): table is pre-loaded by migration script.
    On DuckDB (local dev): creates it from the permits table.
    """
    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM timeline_stats LIMIT 1")
        else:
            conn.execute("SELECT 1 FROM timeline_stats LIMIT 1")
        return  # Already exists
    except Exception:
        pass

    if BACKEND == "postgres":
        # On Postgres, timeline_stats should be pre-loaded by migration.
        # If it's missing, we can't create it from permits (TEXT dates).
        # Raise so the caller falls back to knowledge-only.
        raise RuntimeError("timeline_stats table missing in Postgres")

    # DuckDB: create from permits
    # A4: Exclude electrical, plumbing, and mechanical trade permits to prevent
    # contamination of building permit timeline statistics.
    conn.execute("""
        CREATE TABLE timeline_stats AS
        SELECT
            permit_number,
            permit_type_definition,
            CASE WHEN permit_type_definition ILIKE '%otc%' THEN 'otc' ELSE 'in_house' END as review_path,
            neighborhood,
            estimated_cost,
            revised_cost,
            CASE
                WHEN estimated_cost < 50000 THEN 'under_50k'
                WHEN estimated_cost < 150000 THEN '50k_150k'
                WHEN estimated_cost < 500000 THEN '150k_500k'
                ELSE 'over_500k'
            END as cost_bracket,
            filed_date::DATE as filed,
            issued_date::DATE as issued,
            completed_date::DATE as completed,
            DATE_DIFF('day', filed_date::DATE, issued_date::DATE) as days_to_issuance,
            DATE_DIFF('day', issued_date::DATE, completed_date::DATE) as days_to_completion,
            supervisor_district
        FROM permits
        WHERE filed_date IS NOT NULL
            AND issued_date IS NOT NULL
            AND filed_date::DATE < issued_date::DATE
            AND DATE_DIFF('day', filed_date::DATE, issued_date::DATE) BETWEEN 1 AND 1000
            AND estimated_cost > 0
            AND permit_type_definition NOT ILIKE '%electrical%'
            AND permit_type_definition NOT ILIKE '%plumbing%'
            AND permit_type_definition NOT ILIKE '%mechanical%'
    """)


def _query_timeline(conn, review_path: str | None, neighborhood: str | None,
                    cost_bracket: str | None, permit_type: str | None) -> dict | None:
    """Query timeline percentiles with progressive widening.

    A4: Excludes electrical and plumbing trade permits from in-house timeline
    estimates. These 857K+ trade permits would otherwise skew the distribution
    toward much shorter timelines that don't reflect building permit reality.
    """
    conditions = ["1=1"]
    params = []
    # Use %s for Postgres, ? for DuckDB
    ph = "%s" if BACKEND == "postgres" else "?"

    # Always exclude trade permits — their NULL neighborhoods skew aggregates
    conditions.append(
        "permit_type_definition NOT IN ('Electrical Permit', 'Plumbing Permit')"
    )

    # Recency filter — avoid ancient data skewing estimates
    conditions.append("issued >= CURRENT_DATE - INTERVAL '1 year'")

    if review_path:
        conditions.append(f"review_path = {ph}")
        params.append(review_path)
    if neighborhood:
        conditions.append(f"neighborhood = {ph}")
        params.append(neighborhood)
    if cost_bracket:
        conditions.append(f"cost_bracket = {ph}")
        params.append(cost_bracket)
    if permit_type:
        conditions.append(f"permit_type_definition ILIKE {ph}")
        params.append(f"%{permit_type}%")

    # A4: Filter out electrical and plumbing trade permits to avoid contamination
    # of building permit timeline estimates. Trade permits have very different
    # processing patterns (much faster) and would skew in-house estimates low.
    conditions.append(
        f"permit_type_definition NOT ILIKE '%electrical%'"
        f" AND permit_type_definition NOT ILIKE '%plumbing%'"
        f" AND permit_type_definition NOT ILIKE '%mechanical%'"
    )

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            COUNT(*) as sample_size,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY days_to_issuance) as p25,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_to_issuance) as p50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_to_issuance) as p75,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY days_to_issuance) as p90
        FROM timeline_stats
        WHERE {where}
    """

    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params)
            result = cur.fetchone()
    else:
        result = conn.execute(sql, params).fetchone()

    if result and result[0] >= 10:
        return {
            "sample_size": result[0],
            "p25_days": round(result[1]) if result[1] else None,
            "p50_days": round(result[2]) if result[2] else None,
            "p75_days": round(result[3]) if result[3] else None,
            "p90_days": round(result[4]) if result[4] else None,
        }
    return None


def _query_trend(conn, neighborhood: str | None, review_path: str | None) -> dict | None:
    """Compare recent 6 months vs prior 12 months."""
    ph = "%s" if BACKEND == "postgres" else "?"
    conditions_recent = ["filed > CURRENT_DATE - INTERVAL '6 months'"]
    conditions_prior = [
        "filed BETWEEN CURRENT_DATE - INTERVAL '18 months' AND CURRENT_DATE - INTERVAL '6 months'"
    ]
    params_recent = []
    params_prior = []

    if neighborhood:
        conditions_recent.append(f"neighborhood = {ph}")
        conditions_prior.append(f"neighborhood = {ph}")
        params_recent.append(neighborhood)
        params_prior.append(neighborhood)
    if review_path:
        conditions_recent.append(f"review_path = {ph}")
        conditions_prior.append(f"review_path = {ph}")
        params_recent.append(review_path)
        params_prior.append(review_path)

    sql_recent = f"""
        SELECT AVG(days_to_issuance), COUNT(*)
        FROM timeline_stats WHERE {' AND '.join(conditions_recent)}
    """
    sql_prior = f"""
        SELECT AVG(days_to_issuance), COUNT(*)
        FROM timeline_stats WHERE {' AND '.join(conditions_prior)}
    """

    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql_recent, params_recent)
            recent = cur.fetchone()
            cur.execute(sql_prior, params_prior)
            prior = cur.fetchone()
    else:
        recent = conn.execute(sql_recent, params_recent).fetchone()
        prior = conn.execute(sql_prior, params_prior).fetchone()

    if recent and prior and recent[0] and prior[0] and recent[1] >= 10 and prior[1] >= 10:
        change_pct = ((float(recent[0]) - float(prior[0])) / float(prior[0])) * 100
        direction = "faster" if change_pct < -5 else "slower" if change_pct > 5 else "stable"
        return {
            "recent_avg_days": round(float(recent[0])),
            "prior_avg_days": round(float(prior[0])),
            "change_pct": round(change_pct, 1),
            "direction": direction,
            "recent_sample": recent[1],
            "prior_sample": prior[1],
        }
    return None


def _cost_bracket(estimated_cost: float | None) -> str | None:
    if not estimated_cost:
        return None
    if estimated_cost < 50000:
        return "under_50k"
    if estimated_cost < 150000:
        return "50k_150k"
    if estimated_cost < 500000:
        return "150k_500k"
    return "over_500k"


def _query_station_velocity_v2(conn, stations: list[str] | None = None,
                               neighborhood: str | None = None) -> list[dict]:
    """Query station_velocity_v2 for station-level plan review timelines.

    Sprint 58A: Uses a single WHERE station = ANY(%s) / WHERE station IN (...)
    query for both current and baseline periods simultaneously, then deduplicates
    preferring 'current' over 'baseline'.

    Sprint 66: Tries neighborhood-stratified data first when neighborhood is
    provided. Falls back to station-only if no neighborhood-specific data exists.

    Returns list of dicts with station velocity data. Each dict includes
    "neighborhood_specific": True when neighborhood data was used.
    """
    ph = "%s" if BACKEND == "postgres" else "?"

    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM station_velocity_v2 LIMIT 1")
        else:
            conn.execute("SELECT 1 FROM station_velocity_v2 LIMIT 1")
    except Exception:
        return []

    # Sprint 66: Try neighborhood-stratified data first
    if neighborhood and stations:
        neighborhood_results = _query_neighborhood_velocity(conn, stations, neighborhood)
        if neighborhood_results:
            return neighborhood_results

    # Sprint 58A: Single query for both periods — most efficient
    if stations:
        if BACKEND == "postgres":
            sql = """
                SELECT station, metric_type, p25_days, p50_days, p75_days, p90_days,
                       sample_count, period, updated_at
                FROM station_velocity_v2
                WHERE metric_type = 'initial'
                  AND period IN ('current', 'baseline')
                  AND station = ANY(%s)
                ORDER BY
                  station,
                  CASE period WHEN 'current' THEN 0 ELSE 1 END
            """
            params = [stations]
        else:
            placeholders = ", ".join(["?"] * len(stations))
            sql = f"""
                SELECT station, metric_type, p25_days, p50_days, p75_days, p90_days,
                       sample_count, period, updated_at
                FROM station_velocity_v2
                WHERE metric_type = 'initial'
                  AND period IN ('current', 'baseline')
                  AND station IN ({placeholders})
                ORDER BY
                  station,
                  CASE period WHEN 'current' THEN 0 ELSE 1 END
            """
            params = stations
    else:
        sql = f"""
            SELECT station, metric_type, p25_days, p50_days, p75_days, p90_days,
                   sample_count, period, updated_at
            FROM station_velocity_v2
            WHERE metric_type = 'initial'
              AND period IN ('current', 'baseline')
              AND p50_days > 0
            ORDER BY
              station,
              CASE period WHEN 'current' THEN 0 ELSE 1 END
            LIMIT 60
        """
        params = []

    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        else:
            rows = conn.execute(sql, params).fetchall()
    except Exception:
        return []

    # Deduplicate: keep 'current' period if available, else 'baseline'
    seen: dict[str, dict] = {}
    for row in rows:
        station_name = row[0]
        period = row[7]
        if station_name not in seen or period == "current":
            seen[station_name] = {
                "station": station_name,
                "metric_type": row[1],
                "p25_days": float(row[2]) if row[2] is not None else None,
                "p50_days": float(row[3]) if row[3] is not None else None,
                "p75_days": float(row[4]) if row[4] is not None else None,
                "p90_days": float(row[5]) if row[5] is not None else None,
                "sample_count": row[6],
                "period": period,
                "updated_at": str(row[8]) if row[8] else None,
                "neighborhood_specific": False,
            }

    return list(seen.values())


def _query_neighborhood_velocity(conn, stations: list[str],
                                 neighborhood: str) -> list[dict]:
    """Query neighborhood-stratified velocity data.

    Returns list of dicts if neighborhood data covers at least one station,
    otherwise returns empty list to trigger fallback to station-only.
    """
    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM station_velocity_v2_neighborhood LIMIT 1")
        else:
            conn.execute("SELECT 1 FROM station_velocity_v2_neighborhood LIMIT 1")
    except Exception:
        return []

    if BACKEND == "postgres":
        sql = """
            SELECT station, neighborhood, metric_type, p25_days, p50_days, p75_days,
                   p90_days, sample_count, period
            FROM station_velocity_v2_neighborhood
            WHERE metric_type = 'initial'
              AND neighborhood = %s
              AND period IN ('current', 'baseline')
              AND station = ANY(%s)
            ORDER BY
              station,
              CASE period WHEN 'current' THEN 0 ELSE 1 END
        """
        params = [neighborhood, stations]
    else:
        placeholders = ", ".join(["?"] * len(stations))
        sql = f"""
            SELECT station, neighborhood, metric_type, p25_days, p50_days, p75_days,
                   p90_days, sample_count, period
            FROM station_velocity_v2_neighborhood
            WHERE metric_type = 'initial'
              AND neighborhood = ?
              AND period IN ('current', 'baseline')
              AND station IN ({placeholders})
            ORDER BY
              station,
              CASE period WHEN 'current' THEN 0 ELSE 1 END
        """
        params = [neighborhood] + stations

    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        else:
            rows = conn.execute(sql, params).fetchall()
    except Exception:
        return []

    if not rows:
        return []

    # Deduplicate: keep 'current' period if available
    seen: dict[str, dict] = {}
    for row in rows:
        station_name = row[0]
        period = row[8]
        if station_name not in seen or period == "current":
            seen[station_name] = {
                "station": station_name,
                "metric_type": row[2],
                "p25_days": float(row[3]) if row[3] is not None else None,
                "p50_days": float(row[4]) if row[4] is not None else None,
                "p75_days": float(row[5]) if row[5] is not None else None,
                "p90_days": float(row[6]) if row[6] is not None else None,
                "sample_count": row[7],
                "period": period,
                "neighborhood_specific": True,
            }

    return list(seen.values())


def _query_station_baseline(conn, stations: list[str]) -> dict[str, dict]:
    """Query baseline period data for trend arrow computation.

    Returns dict keyed by station with baseline p50_days.
    """
    if not stations:
        return {}

    if BACKEND == "postgres":
        sql = """
            SELECT station, p50_days
            FROM station_velocity_v2
            WHERE metric_type = 'initial'
              AND period = 'baseline'
              AND station = ANY(%s)
        """
        params = [stations]
    else:
        placeholders = ", ".join(["?"] * len(stations))
        sql = f"""
            SELECT station, p50_days
            FROM station_velocity_v2
            WHERE metric_type = 'initial'
              AND period = 'baseline'
              AND station IN ({placeholders})
        """
        params = stations

    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        else:
            rows = conn.execute(sql, params).fetchall()
    except Exception:
        return {}

    return {row[0]: {"p50_days": float(row[1]) if row[1] else None} for row in rows}


def _compute_trend_arrow(current_p50: float | None, baseline_p50: float | None) -> str:
    """Compute trend arrow for a station comparing current vs baseline.

    Returns:
        "▲ slower" if current > baseline by TREND_THRESHOLD_PCT%
        "▼ faster" if current < baseline by TREND_THRESHOLD_PCT%
        "— normal" otherwise, or when data is missing
    """
    if current_p50 is None or baseline_p50 is None or baseline_p50 == 0:
        return "— normal"
    change_pct = ((current_p50 - baseline_p50) / baseline_p50) * 100
    if change_pct > TREND_THRESHOLD_PCT:
        return f"▲ slower (+{change_pct:.0f}%)"
    if change_pct < -TREND_THRESHOLD_PCT:
        return f"▼ faster ({change_pct:.0f}%)"
    return "— normal"


def _compute_station_sum(station_data: list[dict]) -> dict | None:
    """Sum station p50 values to produce aggregate sequential estimate.

    Sprint 58A: This is the PRIMARY timeline model.

    Args:
        station_data: List of station dicts from _query_station_velocity_v2()

    Returns:
        Dict with summed p25/p50/p75/p90 and list of contributing stations,
        or None if no stations have p50 data.
    """
    stations_with_data = [s for s in station_data if s.get("p50_days") is not None and s["p50_days"] > 0]
    if not stations_with_data:
        return None

    total_p25 = sum(s["p25_days"] or 0 for s in stations_with_data)
    total_p50 = sum(s["p50_days"] for s in stations_with_data)
    total_p75 = sum(s["p75_days"] or s["p50_days"] for s in stations_with_data)
    total_p90 = sum(s["p90_days"] or s["p75_days"] or s["p50_days"] for s in stations_with_data)
    total_sample = sum(s.get("sample_count") or 0 for s in stations_with_data)

    return {
        "p25_days": round(total_p25),
        "p50_days": round(total_p50),
        "p75_days": round(total_p75),
        "p90_days": round(total_p90),
        "sample_size": total_sample,
        "station_count": len(stations_with_data),
        "stations": stations_with_data,
        "model": "station_sum",
    }


def _format_station_table(station_data: list[dict], baseline_map: dict[str, dict]) -> list[str]:
    """Format station velocity data as markdown table with trend arrows."""
    if not station_data:
        return []

    lines = ["\n## Station-Level Plan Review Velocity\n"]
    lines.append("| Station | Typical (p25-p75) | Median | Worst Case (p90) | Trend | Samples |")
    lines.append("|---------|-------------------|--------|------------------|-------|---------|")

    for s in sorted(station_data, key=lambda x: -(x.get("p50_days") or 0)):
        p25 = s.get("p25_days")
        p50 = s.get("p50_days")
        p75 = s.get("p75_days")
        p90 = s.get("p90_days")
        n = s.get("sample_count", 0)

        baseline_p50 = baseline_map.get(s["station"], {}).get("p50_days")
        trend_arrow = _compute_trend_arrow(p50, baseline_p50)

        range_str = f"{_format_days(p25)}–{_format_days(p75)}" if p25 is not None and p75 is not None else "—"
        median_str = _format_days(p50) if p50 is not None else "—"
        worst_str = _format_days(p90) if p90 is not None else "—"

        lines.append(f"| {s['station']} | {range_str} | {median_str} | {worst_str} | {trend_arrow} | {n:,} |")

    lines.append(
        "\n*Station velocity: initial plan review, deduped, post-2018, "
        "excludes Administrative/Not Applicable pass-throughs*"
    )
    return lines


def _format_days(d: float | None) -> str:
    """Format days as human-readable string."""
    if d is None:
        return "—"
    if d < 1:
        return "<1 day"
    if d < 7:
        return f"{d:.0f} days"
    if d < 30:
        weeks = d / 7
        return f"{weeks:.0f} wk"
    months = d / 30
    return f"{months:.1f} mo"


async def estimate_timeline(
    permit_type: str,
    neighborhood: str | None = None,
    review_path: str | None = None,
    estimated_cost: float | None = None,
    triggers: list[str] | None = None,
    return_structured: bool = False,
    monthly_carrying_cost: float | None = None,
) -> str | tuple[str, dict]:
    """Estimate permit processing timeline using historical data + station velocity.

    Sprint 58A: Station-sum model is PRIMARY. Queries station_velocity_v2 for
    all relevant stations in a single query, sums p50 values for sequential
    review estimate, and computes trend arrows (±15% vs baseline = flagged).
    Falls back to aggregate timeline_stats (1-year recency, excluding trade
    permits) when no station data matches.

    Args:
        permit_type: Type of permit (e.g., 'alterations', 'new_construction', 'demolition', 'otc')
        neighborhood: SF neighborhood name (e.g., 'Mission', 'Noe Valley')
        review_path: 'otc' or 'in_house' — if not provided, will estimate both
        estimated_cost: Construction cost for cost bracket matching
        triggers: Additional delay factors to include (e.g., ['change_of_use', 'historic'])
        return_structured: If True, returns (markdown_str, methodology_dict) tuple
        monthly_carrying_cost: Optional monthly carrying cost (rent, mortgage, storage)
            to compute financial impact of permit delay

    Returns:
        Formatted timeline estimate with percentiles, station velocity, trend, and delay factors.
        If return_structured=True, returns (str, dict) tuple.
    """
    bracket = _cost_bracket(estimated_cost)

    # --- DB query results ---
    aggregate_result = None
    completion = None
    trend = None
    station_velocity: list[dict] = []
    baseline_map: dict[str, dict] = {}
    station_sum_result = None
    widened = False
    db_available = False
    v2_available = False
    fallback_note = ""

    # Gather all relevant station codes from triggers + default BLDG
    relevant_stations: list[str] | None = None
    if triggers:
        station_set: list[str] = ["BLDG"]  # always include primary building station
        for t in triggers:
            if t in TRIGGER_STATION_MAP:
                for s in TRIGGER_STATION_MAP[t]:
                    if s not in station_set:
                        station_set.append(s)
        relevant_stations = station_set if len(station_set) > 1 else None

    try:
        conn = get_connection()
        try:
            _ensure_timeline_stats(conn)
            db_available = True

            # === Sprint 58A: PRIMARY MODEL — Station Sum ===
            # Sprint 66: Pass neighborhood for stratified lookup with fallback
            station_velocity = _query_station_velocity_v2(conn, relevant_stations, neighborhood)

            if station_velocity:
                v2_available = True
                # Fetch baseline for trend arrows
                station_names = [s["station"] for s in station_velocity]
                baseline_map = _query_station_baseline(conn, station_names)
                station_sum_result = _compute_station_sum(station_velocity)

            # === FALLBACK MODEL — Aggregate timeline_stats ===
            # Only used when station sum model has no data
            if not station_sum_result:
                fallback_note = "Station velocity data unavailable — using aggregate permit statistics"
                aggregate_result = _query_timeline(conn, review_path, neighborhood, bracket, permit_type)

                if not aggregate_result and neighborhood:
                    aggregate_result = _query_timeline(conn, review_path, None, bracket, permit_type)
                    widened = True

                if not aggregate_result and bracket:
                    aggregate_result = _query_timeline(conn, review_path, None, None, permit_type)
                    widened = True

                if not aggregate_result:
                    aggregate_result = _query_timeline(conn, review_path, None, None, None)
                    widened = True

            # Completion timeline (always query, independent of primary model)
            if station_sum_result or aggregate_result:
                ph = "%s" if BACKEND == "postgres" else "?"
                comp_sql = f"""
                    SELECT
                        COUNT(*) as n,
                        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_to_completion) as p50,
                        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_to_completion) as p75
                    FROM timeline_stats
                    WHERE days_to_completion BETWEEN 1 AND 1000
                        AND review_path = COALESCE({ph}, review_path)
                """
                if BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(comp_sql, [review_path])
                        comp = cur.fetchone()
                else:
                    comp = conn.execute(comp_sql, [review_path]).fetchone()
                if comp and comp[0] >= 10:
                    completion = {"p50_days": round(comp[1]), "p75_days": round(comp[2]), "sample": comp[0]}

            # Trend
            trend = _query_trend(conn, neighborhood, review_path)

        finally:
            conn.close()
    except Exception as e:
        logger.warning("DB connection failed in estimate_timeline: %s", e)

    # --- Determine which result to use ---
    using_station_sum = station_sum_result is not None
    primary_result = station_sum_result or aggregate_result

    # Applicable delay factors
    delay_factors = []
    if triggers:
        for t in triggers:
            if t in DELAY_FACTORS:
                delay_factors.append({"trigger": t, "impact": DELAY_FACTORS[t]})

    # --- Format output ---
    lines = ["# Timeline Estimate\n"]
    lines.append(f"**Permit Type:** {permit_type}")
    if neighborhood:
        lines.append(f"**Neighborhood:** {neighborhood}")
    if review_path:
        lines.append(f"**Review Path:** {review_path}")
    if estimated_cost:
        lines.append(f"**Cost Bracket:** {bracket}")

    # Sprint 66: Check if any station used neighborhood-specific data
    neighborhood_specific = any(
        s.get("neighborhood_specific") for s in station_velocity
    ) if station_velocity else False

    if using_station_sum:
        # Primary model: station-sum output
        if neighborhood_specific:
            lines.append(f"\n## Plan Review Timeline (Station-Sum Model — Neighborhood-specific)\n")
            lines.append(f"*Neighborhood-specific velocity data for {neighborhood}. "
                         "Sum of sequential station review times.*\n")
        else:
            lines.append(f"\n## Plan Review Timeline (Station-Sum Model)\n")
            lines.append("*Sum of sequential station review times — each station reviews in parallel or series.*\n")
        lines.append(f"| Percentile | Days |")
        lines.append(f"|-----------|------|")
        lines.append(f"| 25th (optimistic) | {primary_result['p25_days']} |")
        lines.append(f"| 50th (typical) | {primary_result['p50_days']} |")
        lines.append(f"| 75th (conservative) | {primary_result['p75_days']} |")
        lines.append(f"| 90th (worst case) | {primary_result['p90_days']} |")
        lines.append(f"\n*Based on {primary_result['station_count']} station(s), "
                     f"{primary_result['sample_size']:,} total routing records*")

        # Station breakdown table
        lines.extend(_format_station_table(station_velocity, baseline_map))

    elif aggregate_result:
        lines.append(f"\n## Filing to Issuance\n")
        if fallback_note:
            lines.append(f"*{fallback_note}*\n")
        lines.append(f"| Percentile | Days |")
        lines.append(f"|-----------|------|")
        lines.append(f"| 25th (optimistic) | {aggregate_result['p25_days']} |")
        lines.append(f"| 50th (typical) | {aggregate_result['p50_days']} |")
        lines.append(f"| 75th (conservative) | {aggregate_result['p75_days']} |")
        lines.append(f"| 90th (worst case) | {aggregate_result['p90_days']} |")
        lines.append(f"\n*Sample size: {aggregate_result['sample_size']:,} permits*")
        if widened:
            lines.append("*Note: query widened beyond specified filters for sufficient sample size*")
    else:
        # Knowledge-based fallback ranges
        lines.append("\n## Estimated Timeline Ranges\n")
        if not db_available:
            lines.append("*Historical permit database not available — using knowledge-based estimates*\n")
        if review_path == "otc":
            lines.append("| Phase | Estimate |")
            lines.append("|-------|----------|")
            lines.append("| Plan review (OTC) | Same day to 1 week |")
            lines.append("| Permit issuance | Immediate upon approval |")
        else:
            lines.append("| Phase | Estimate |")
            lines.append("|-------|----------|")
            lines.append("| Initial plan review | 3-8 weeks |")
            lines.append("| Corrections (if any) | 2-4 weeks per round |")
            lines.append("| Total to issuance | 2-6 months typical |")
            lines.append("| Complex projects | 6-12+ months |")

    if completion:
        lines.append(f"\n## Issuance to Completion\n")
        lines.append(f"- Typical (p50): {completion['p50_days']} days")
        lines.append(f"- Conservative (p75): {completion['p75_days']} days")

    if trend:
        lines.append(f"\n## Recent Trend\n")
        lines.append(f"- Recent 6 months: {trend['recent_avg_days']} days avg ({trend['recent_sample']:,} permits)")
        lines.append(f"- Prior 12 months: {trend['prior_avg_days']} days avg ({trend['prior_sample']:,} permits)")
        lines.append(f"- Trend: **{trend['direction']}** ({trend['change_pct']:+.1f}%)")

    if delay_factors:
        lines.append(f"\n## Additional Delay Factors\n")
        for d in delay_factors:
            lines.append(f"- **{d['trigger']}**: {d['impact']}")

    # Confidence
    if using_station_sum:
        confidence = "high" if primary_result["sample_size"] >= 100 else "medium"
    elif aggregate_result:
        sample_size = aggregate_result["sample_size"]
        confidence = "high" if sample_size >= 100 and not widened else \
                     "medium" if sample_size >= 10 else "low"
    else:
        confidence = "low"

    lines.append(f"\n**Confidence:** {confidence}")

    if v2_available:
        lines.append(
            "\n*Station velocity data: cleaned addenda records (post-2018), "
            "deduped per permit+station, excludes administrative pass-throughs. "
            "Initial review cycle shown (addenda #0). Trend arrows: ±15% vs 365-day baseline.*"
        )

    # === Sprint 60C: Cost of Delay ===
    cost_impact = None
    if monthly_carrying_cost and monthly_carrying_cost > 0 and primary_result:
        daily_cost = monthly_carrying_cost / 30.44
        weekly_cost = monthly_carrying_cost / 4.33
        p50_days = primary_result.get("p50_days")
        p75_days = primary_result.get("p75_days")
        p90_days = primary_result.get("p90_days")

        if p50_days:
            cost_impact = {
                "monthly_carrying_cost": monthly_carrying_cost,
                "daily_cost": round(daily_cost, 2),
                "weekly_cost": round(weekly_cost, 2),
                "scenarios": [],
            }

            for label, days_key, days_val in [
                ("Typical (p50)", "p50_days", p50_days),
                ("Conservative (p75)", "p75_days", p75_days),
                ("Worst Case (p90)", "p90_days", p90_days),
            ]:
                if days_val:
                    carry = round(days_val * daily_cost)
                    cost_impact["scenarios"].append({
                        "label": label,
                        "days": round(days_val),
                        "carrying_cost": carry,
                    })

            # Delay cost: difference between p75 and p50
            if p50_days and p75_days:
                delay_days = round(p75_days - p50_days)
                delay_cost = round(delay_days * daily_cost)
                cost_impact["delay_cost"] = delay_cost
                cost_impact["delay_days"] = delay_days

            # Add to markdown output
            lines.append(f"\n## Financial Impact of Delay\n")
            lines.append(f"Monthly carrying cost: ${monthly_carrying_cost:,.0f} · Weekly: ${weekly_cost:,.0f}\n")
            lines.append("| Scenario | Days | Carrying Cost |")
            lines.append("|----------|------|---------------|")
            for s in cost_impact["scenarios"]:
                lines.append(f"| {s['label']} | {s['days']} | ${s['carrying_cost']:,} |")

            if cost_impact.get("delay_cost"):
                lines.append(f"\nIf review takes {cost_impact.get('delay_days', 0) + (p50_days or 0):.0f} days instead of {p50_days:.0f}, that's ${cost_impact['delay_cost']:,} more.")
    # === END Sprint 60C ===

    # Coverage gaps
    sample_size = primary_result["sample_size"] if primary_result else 0
    coverage_gaps: list[str] = []
    if sample_size > 0 and sample_size < 20:
        coverage_gaps.append(f"Limited data for this combination ({sample_size} records)")
    if widened:
        coverage_gaps.append("Query widened beyond specified filters for sufficient sample size")
    if not db_available:
        coverage_gaps.append("Historical permit database not available — using knowledge-based estimates")
    if not v2_available:
        coverage_gaps.append("Station velocity data not available — using aggregate permit statistics")
    if fallback_note:
        coverage_gaps.append(fallback_note)

    if coverage_gaps:
        lines.append(f"\n## Data Coverage\n")
        for gap in coverage_gaps:
            lines.append(f"- {gap}")

    # Source citations
    sources = []
    if db_available:
        sources.append("duckdb_permits")
    if v2_available:
        sources.append("station_velocity_v2")
    if delay_factors:
        sources.append("routing_matrix")
    if not db_available:
        sources.append("inhouse_review")
    lines.append(format_sources(sources))

    md_output = "\n".join(lines)

    # Build methodology dict — common contract + tool-specific keys
    # Sprint 58A: methodology dict added to all returns
    today_iso = _date.today().isoformat()

    # Build station dicts for methodology
    stations_meta: list[dict] = []
    if station_velocity:
        for s in station_velocity:
            baseline_p50 = baseline_map.get(s["station"], {}).get("p50_days")
            stations_meta.append({
                "station": s["station"],
                "p25_days": s.get("p25_days"),
                "p50_days": s.get("p50_days"),
                "p75_days": s.get("p75_days"),
                "p90_days": s.get("p90_days"),
                "sample_count": s.get("sample_count"),
                "period": s.get("period"),
                "baseline_p50_days": baseline_p50,
                "trend_arrow": _compute_trend_arrow(s.get("p50_days"), baseline_p50),
            })

    if using_station_sum:
        model_name = "station-sum (primary)"
        formula_str = (
            f"Sum of p50 days across {primary_result['station_count']} station(s): "
            + " + ".join(
                f"{s['station']}({s.get('p50_days', 0):.0f}d)"
                for s in station_velocity
                if s.get("p50_days") and s["p50_days"] > 0
            )
            + f" = {primary_result['p50_days']}d typical"
        )
        recency = "90-day window (current period) for each station"
        data_source = "station_velocity_v2 (3.9M addenda routing records)"
    else:
        model_name = "aggregate-percentile (fallback)"
        formula_str = (
            f"Percentile query on timeline_stats "
            f"(1-year recency, excluding trade permits"
            + (f", widened" if widened else "")
            + ")"
        )
        recency = "1-year window (issued >= CURRENT_DATE - INTERVAL '1 year')"
        data_source = "timeline_stats (1.1M+ historical permits)"

    methodology: dict = {
        "methodology": {
            "model": model_name,
            "formula": formula_str,
            "data_source": data_source,
            "recency": recency,
            "sample_size": sample_size,
            "data_freshness": today_iso,
            "confidence": confidence,
            "coverage_gaps": coverage_gaps,
        },
        # Tool-specific keys
        "stations": stations_meta,
        "fallback_note": fallback_note if fallback_note else "",
        "neighborhood_specific": neighborhood_specific,
    }

    # Sprint 60C: cost impact in methodology
    if cost_impact:
        methodology["cost_impact"] = cost_impact

    if return_structured:
        # Legacy structured return format (for backward compat with web/app.py)
        formula_steps = []
        if primary_result:
            formula_steps.append(f"p25 (optimistic): {primary_result['p25_days']} days")
            formula_steps.append(f"p50 (typical): {primary_result['p50_days']} days")
            formula_steps.append(f"p75 (conservative): {primary_result['p75_days']} days")
            formula_steps.append(f"p90 (worst case): {primary_result['p90_days']} days")
        if using_station_sum:
            formula_steps.insert(0, f"Model: station-sum across {primary_result['station_count']} station(s)")

        data_sources = []
        if v2_available:
            data_sources.append("3.9M addenda routing records (station_velocity_v2)")
        if db_available:
            data_sources.append("1.1M+ historical permits (timeline_stats)")
        if delay_factors:
            data_sources.append("Agency routing knowledge base")
        if not db_available:
            data_sources.append("DBI knowledge base estimates")

        headline = f"{primary_result['p50_days']} days typical" if primary_result else "See ranges"

        legacy_meta = {
            "tool": "estimate_timeline",
            "headline": headline,
            "formula_steps": formula_steps,
            "data_sources": data_sources,
            "sample_size": sample_size,
            "data_freshness": today_iso,
            "confidence": confidence,
            "coverage_gaps": coverage_gaps,
            # Sprint 58A: include full methodology dict in structured return
            "methodology": methodology["methodology"],
            "stations": stations_meta,
            "fallback_note": fallback_note,
        }
        if cost_impact:
            legacy_meta["cost_impact"] = cost_impact
        return md_output, legacy_meta

    return md_output
