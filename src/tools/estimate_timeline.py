"""Tool: estimate_timeline — Estimate permit processing timelines from DuckDB historical data."""

import duckdb
from src.db import get_connection, DB_PATH

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


def _ensure_timeline_stats(conn: duckdb.DuckDBPyConnection) -> None:
    """Create timeline_stats materialized view if it doesn't exist."""
    try:
        conn.execute("SELECT 1 FROM timeline_stats LIMIT 1")
        return  # Already exists
    except duckdb.CatalogException:
        pass

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
    """)


def _query_timeline(conn, review_path: str | None, neighborhood: str | None,
                    cost_bracket: str | None, permit_type: str | None) -> dict | None:
    """Query timeline percentiles with progressive widening."""
    conditions = ["1=1"]
    params = []

    if review_path:
        conditions.append("review_path = ?")
        params.append(review_path)
    if neighborhood:
        conditions.append("neighborhood = ?")
        params.append(neighborhood)
    if cost_bracket:
        conditions.append("cost_bracket = ?")
        params.append(cost_bracket)
    if permit_type:
        conditions.append("permit_type_definition ILIKE ?")
        params.append(f"%{permit_type}%")

    where = " AND ".join(conditions)
    result = conn.execute(f"""
        SELECT
            COUNT(*) as sample_size,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY days_to_issuance) as p25,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_to_issuance) as p50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_to_issuance) as p75,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY days_to_issuance) as p90
        FROM timeline_stats
        WHERE {where}
    """, params).fetchone()

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
    conditions_recent = ["filed > CURRENT_DATE - INTERVAL '6 months'"]
    conditions_prior = [
        "filed BETWEEN CURRENT_DATE - INTERVAL '18 months' AND CURRENT_DATE - INTERVAL '6 months'"
    ]
    params_recent = []
    params_prior = []

    if neighborhood:
        conditions_recent.append("neighborhood = ?")
        conditions_prior.append("neighborhood = ?")
        params_recent.append(neighborhood)
        params_prior.append(neighborhood)
    if review_path:
        conditions_recent.append("review_path = ?")
        conditions_prior.append("review_path = ?")
        params_recent.append(review_path)
        params_prior.append(review_path)

    recent = conn.execute(f"""
        SELECT AVG(days_to_issuance), COUNT(*)
        FROM timeline_stats WHERE {' AND '.join(conditions_recent)}
    """, params_recent).fetchone()

    prior = conn.execute(f"""
        SELECT AVG(days_to_issuance), COUNT(*)
        FROM timeline_stats WHERE {' AND '.join(conditions_prior)}
    """, params_prior).fetchone()

    if recent and prior and recent[0] and prior[0] and recent[1] >= 10 and prior[1] >= 10:
        change_pct = ((recent[0] - prior[0]) / prior[0]) * 100
        direction = "faster" if change_pct < -5 else "slower" if change_pct > 5 else "stable"
        return {
            "recent_avg_days": round(recent[0]),
            "prior_avg_days": round(prior[0]),
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


async def estimate_timeline(
    permit_type: str,
    neighborhood: str | None = None,
    review_path: str | None = None,
    estimated_cost: float | None = None,
    triggers: list[str] | None = None,
) -> str:
    """Estimate permit processing timeline using historical DuckDB data.

    Queries 1.1M+ historical permits to compute percentile-based timeline
    estimates (p25/p50/p75/p90) for filing-to-issuance and issuance-to-completion.

    Args:
        permit_type: Type of permit (e.g., 'alterations', 'new_construction', 'demolition', 'otc')
        neighborhood: SF neighborhood name (e.g., 'Mission', 'Noe Valley')
        review_path: 'otc' or 'in_house' — if not provided, will estimate both
        estimated_cost: Construction cost for cost bracket matching
        triggers: Additional delay factors to include (e.g., ['change_of_use', 'historic'])

    Returns:
        Formatted timeline estimate with percentiles, trend, and delay factors.
    """
    conn = get_connection()
    try:
        _ensure_timeline_stats(conn)

        bracket = _cost_bracket(estimated_cost)

        # Try specific query first, then widen
        result = _query_timeline(conn, review_path, neighborhood, bracket, permit_type)
        widened = False

        if not result and neighborhood:
            # Drop neighborhood constraint
            result = _query_timeline(conn, review_path, None, bracket, permit_type)
            widened = True

        if not result and bracket:
            # Drop cost bracket too
            result = _query_timeline(conn, review_path, None, None, permit_type)
            widened = True

        if not result:
            # Broadest query — just review path
            result = _query_timeline(conn, review_path, None, None, None)
            widened = True

        # Completion timeline
        completion = None
        if result:
            comp = conn.execute("""
                SELECT
                    COUNT(*) as n,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_to_completion) as p50,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_to_completion) as p75
                FROM timeline_stats
                WHERE days_to_completion BETWEEN 1 AND 1000
                    AND review_path = COALESCE(?, review_path)
            """, [review_path]).fetchone()
            if comp and comp[0] >= 10:
                completion = {"p50_days": round(comp[1]), "p75_days": round(comp[2]), "sample": comp[0]}

        # Trend
        trend = _query_trend(conn, neighborhood, review_path)

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
            lines.append("\n**Insufficient data** for timeline estimate with given filters.")

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

        return "\n".join(lines)
    finally:
        conn.close()
