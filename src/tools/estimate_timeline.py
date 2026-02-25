"""Tool: estimate_timeline — Estimate permit processing timelines from historical data.

v2 integration: reads station-level velocity from station_velocity_v2 table
(computed from cleaned addenda routing data — deduped, post-2018, excluding
Administrative/Not Applicable pass-throughs). Falls back to v1 timeline_stats
if v2 data is unavailable.
"""

import logging

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

# Map trigger keywords to station codes for v2 station velocity lookups
TRIGGER_STATION_MAP = {
    "planning_review": ["CP-ZOC", "PPC", "CP-NP"],
    "dph_review": ["HEALTH", "HEALTH-FD"],
    "fire_review": ["SFFD", "SFFD-HQ"],
    "historic": ["HIS"],
    "multi_agency": ["DPW-BSM", "SFPUC"],
}


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


def _query_station_velocity_v2(conn, stations: list[str] | None = None) -> list[dict]:
    """Query station_velocity_v2 for station-level plan review timelines.

    Returns list of dicts with station velocity data, preferring recent_6mo
    and falling back to 'all' period.
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

    results = []
    # Query top stations by median days (initial review, recent_6mo first, fallback to all)
    for period in ["recent_6mo", "all"]:
        if stations:
            placeholders = ", ".join([ph] * len(stations))
            sql = f"""
                SELECT station, metric_type, p25_days, p50_days, p75_days, p90_days,
                       sample_count, period
                FROM station_velocity_v2
                WHERE metric_type = 'initial'
                  AND period = {ph}
                  AND station IN ({placeholders})
                ORDER BY p50_days DESC NULLS LAST
            """
            params = [period] + stations
        else:
            sql = f"""
                SELECT station, metric_type, p25_days, p50_days, p75_days, p90_days,
                       sample_count, period
                FROM station_velocity_v2
                WHERE metric_type = 'initial'
                  AND period = {ph}
                  AND p50_days > 0
                ORDER BY p50_days DESC NULLS LAST
                LIMIT 15
            """
            params = [period]

        try:
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()
            else:
                rows = conn.execute(
                    sql.replace("%s", "?"), params
                ).fetchall()
        except Exception:
            continue

        for row in rows:
            station_name = row[0]
            # Skip if already have this station from a more recent period
            if any(r["station"] == station_name for r in results):
                continue
            results.append({
                "station": station_name,
                "metric_type": row[1],
                "p25_days": float(row[2]) if row[2] is not None else None,
                "p50_days": float(row[3]) if row[3] is not None else None,
                "p75_days": float(row[4]) if row[4] is not None else None,
                "p90_days": float(row[5]) if row[5] is not None else None,
                "sample_count": row[6],
                "period": row[7],
            })

    return results


def _format_station_velocity(station_data: list[dict]) -> list[str]:
    """Format station velocity data as markdown lines."""
    if not station_data:
        return []

    lines = ["\n## Station-Level Plan Review Velocity\n"]
    lines.append("| Station | Typical (p25-p75) | Median | Worst Case (p90) | Samples |")
    lines.append("|---------|-------------------|--------|------------------|---------|")

    for s in station_data:
        p25 = s["p25_days"]
        p50 = s["p50_days"]
        p75 = s["p75_days"]
        p90 = s["p90_days"]
        n = s["sample_count"]

        range_str = f"{_format_days(p25)}–{_format_days(p75)}" if p25 is not None and p75 is not None else "—"
        median_str = _format_days(p50) if p50 is not None else "—"
        worst_str = _format_days(p90) if p90 is not None else "—"

        lines.append(f"| {s['station']} | {range_str} | {median_str} | {worst_str} | {n:,} |")

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
) -> str:
    """Estimate permit processing timeline using historical data + station velocity.

    Queries 1.1M+ historical permits to compute percentile-based timeline
    estimates (p25/p50/p75/p90) for filing-to-issuance and issuance-to-completion.
    Enriches with station-level plan review velocity from cleaned addenda data (v2).

    Args:
        permit_type: Type of permit (e.g., 'alterations', 'new_construction', 'demolition', 'otc')
        neighborhood: SF neighborhood name (e.g., 'Mission', 'Noe Valley')
        review_path: 'otc' or 'in_house' — if not provided, will estimate both
        estimated_cost: Construction cost for cost bracket matching
        triggers: Additional delay factors to include (e.g., ['change_of_use', 'historic'])

    Returns:
        Formatted timeline estimate with percentiles, station velocity, trend, and delay factors.
    """
    bracket = _cost_bracket(estimated_cost)

    # Try DuckDB for historical data — gracefully degrade if unavailable
    result = None
    completion = None
    trend = None
    station_velocity = []
    widened = False
    db_available = False
    v2_available = False

    try:
        conn = get_connection()
        try:
            _ensure_timeline_stats(conn)
            db_available = True

            # Try specific query first, then widen
            result = _query_timeline(conn, review_path, neighborhood, bracket, permit_type)

            if not result and neighborhood:
                result = _query_timeline(conn, review_path, None, bracket, permit_type)
                widened = True

            if not result and bracket:
                result = _query_timeline(conn, review_path, None, None, permit_type)
                widened = True

            if not result:
                result = _query_timeline(conn, review_path, None, None, None)
                widened = True

            # Completion timeline
            if result:
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

            # v2 station velocity — look up relevant stations based on triggers
            relevant_stations = None
            if triggers:
                relevant_stations = []
                for t in triggers:
                    if t in TRIGGER_STATION_MAP:
                        relevant_stations.extend(TRIGGER_STATION_MAP[t])
                if not relevant_stations:
                    relevant_stations = None

            station_velocity = _query_station_velocity_v2(conn, relevant_stations)
            if station_velocity:
                v2_available = True

        finally:
            conn.close()
    except Exception as e:
        logger.warning("DB connection failed in estimate_timeline: %s", e)

    # Applicable delay factors
    delay_factors = []
    if triggers:
        for t in triggers:
            if t in DELAY_FACTORS:
                delay_factors.append({"trigger": t, "impact": DELAY_FACTORS[t]})

    # Format output
    lines = ["# Timeline Estimate\n"]
    lines.append(f"**Permit Type:** {permit_type}")
    if neighborhood:
        lines.append(f"**Neighborhood:** {neighborhood}")
    if review_path:
        lines.append(f"**Review Path:** {review_path}")
    if estimated_cost:
        lines.append(f"**Cost Bracket:** {bracket}")

    if result:
        lines.append(f"\n## Filing to Issuance\n")
        lines.append(f"| Percentile | Days |")
        lines.append(f"|-----------|------|")
        lines.append(f"| 25th (optimistic) | {result['p25_days']} |")
        lines.append(f"| 50th (typical) | {result['p50_days']} |")
        lines.append(f"| 75th (conservative) | {result['p75_days']} |")
        lines.append(f"| 90th (worst case) | {result['p90_days']} |")
        lines.append(f"\n*Sample size: {result['sample_size']:,} permits*")
        if widened:
            lines.append("*Note: query widened beyond specified filters for sufficient sample size*")
    else:
        # Knowledge-based fallback ranges
        lines.append("\n## Estimated Timeline Ranges\n")
        if not db_available:
            lines.append("*Historical permit database not available — using LUCK-based estimates*\n")
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

    # Station velocity (v2)
    lines.extend(_format_station_velocity(station_velocity))

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

    confidence = "high" if result and result["sample_size"] >= 100 and not widened else \
                 "medium" if result and result["sample_size"] >= 10 else "low"
    lines.append(f"\n**Confidence:** {confidence}")

    # Data quality note
    if v2_available:
        lines.append(
            "\n*Station velocity data: cleaned addenda records (post-2018), "
            "deduped per permit+station, excludes administrative pass-throughs. "
            "Initial review cycle shown (addenda #0).*"
        )

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

    return "\n".join(lines)
