"""Tool: revision_risk — Estimate revision probability and impact from permit data patterns."""

from src.db import get_connection

# Common revision triggers by project type
REVISION_TRIGGERS = {
    "restaurant": [
        "Incomplete grease interceptor sizing calculations",
        "Missing Type I hood fire suppression details",
        "DPH health permit requirements not addressed in initial plans",
        "Inadequate ventilation calculations for commercial kitchen",
        "ADA path-of-travel calculations missing or insufficient",
    ],
    "adu": [
        "Fire separation between ADU and primary dwelling insufficient",
        "Parking requirements not addressed (or waiver not obtained)",
        "Setback violations in proposed design",
        "Missing utility connection plans (separate meter)",
        "Planning Department conditions not reflected in plans",
    ],
    "seismic": [
        "Structural calculations missing or insufficient for retrofit scope",
        "Geotechnical report not referenced in structural design",
        "Foundation details inconsistent with soil conditions",
    ],
    "commercial_ti": [
        "Disabled access compliance checklist incomplete",
        "ADA path-of-travel calculations missing",
        "HVAC load calculations not provided",
        "Fire separation between tenants not addressed",
    ],
    "new_construction": [
        "Stormwater management plan incomplete",
        "Fire flow study not referenced in sprinkler design",
        "Geotechnical recommendations not incorporated",
        "Green building documentation gaps",
        "Title 24 energy compliance documentation incomplete",
    ],
    "general": [
        "Incomplete Title-24 energy compliance documentation",
        "Missing ADA path-of-travel calculations",
        "Structural calculations missing or insufficient",
        "Site plan discrepancies with existing conditions",
        "Plans not matching permit application description",
    ],
}


def _query_revision_stats(conn, permit_type: str | None, neighborhood: str | None,
                          review_path: str | None) -> dict | None:
    """Query DuckDB for revision indicators using revised_cost as proxy."""
    conditions = [
        "filed_date IS NOT NULL",
        "issued_date IS NOT NULL",
        "estimated_cost > 0",
    ]
    params = []

    if permit_type:
        conditions.append("permit_type_definition ILIKE ?")
        params.append(f"%{permit_type}%")
    if neighborhood:
        conditions.append("neighborhood = ?")
        params.append(neighborhood)
    if review_path:
        if review_path == "otc":
            conditions.append("permit_type_definition ILIKE '%otc%'")
        else:
            conditions.append("permit_type_definition NOT ILIKE '%otc%'")

    where = " AND ".join(conditions)

    result = conn.execute(f"""
        SELECT
            COUNT(*) as total_permits,
            COUNT(CASE WHEN revised_cost > estimated_cost THEN 1 END) as permits_with_cost_increase,
            ROUND(
                COUNT(CASE WHEN revised_cost > estimated_cost THEN 1 END)::FLOAT
                / NULLIF(COUNT(*), 0), 3
            ) as revision_proxy_rate,
            AVG(CASE WHEN revised_cost > estimated_cost
                THEN (revised_cost - estimated_cost) / NULLIF(estimated_cost, 0) * 100
            END) as avg_cost_increase_pct,
            -- Timeline comparison: permits with vs without cost changes
            AVG(CASE WHEN revised_cost IS NULL OR revised_cost = estimated_cost
                THEN DATE_DIFF('day', filed_date::DATE, issued_date::DATE) END) as avg_days_no_change,
            AVG(CASE WHEN revised_cost > estimated_cost
                THEN DATE_DIFF('day', filed_date::DATE, issued_date::DATE) END) as avg_days_with_change,
            -- P90 timeline outlier detection
            PERCENTILE_CONT(0.90) WITHIN GROUP (
                ORDER BY DATE_DIFF('day', filed_date::DATE, issued_date::DATE)
            ) as p90_days
        FROM permits
        WHERE {where}
            AND filed_date::DATE < issued_date::DATE
            AND DATE_DIFF('day', filed_date::DATE, issued_date::DATE) BETWEEN 1 AND 1000
    """, params).fetchone()

    if result and result[0] >= 20:
        return {
            "total_permits": result[0],
            "permits_with_cost_increase": result[1],
            "revision_proxy_rate": result[2],
            "avg_cost_increase_pct": round(result[3], 1) if result[3] else None,
            "avg_days_no_change": round(result[4]) if result[4] else None,
            "avg_days_with_change": round(result[5]) if result[5] else None,
            "p90_days": round(result[6]) if result[6] else None,
        }
    return None


async def revision_risk(
    permit_type: str,
    neighborhood: str | None = None,
    project_type: str | None = None,
    review_path: str | None = None,
) -> str:
    """Estimate revision probability and impact from permit data patterns.

    Analyzes historical permit data to predict:
    - Probability of revisions during review (using revised_cost as proxy)
    - Timeline impact of revisions
    - Common revision triggers by project type
    - Mitigation strategies

    Args:
        permit_type: Type of permit (e.g., 'alterations', 'new_construction')
        neighborhood: Optional SF neighborhood name
        project_type: Optional specific type (e.g., 'restaurant', 'adu', 'seismic')
        review_path: Optional 'otc' or 'in_house'

    Returns:
        Formatted revision risk assessment with data-backed probabilities.
    """
    conn = get_connection()
    try:
        stats = _query_revision_stats(conn, permit_type, neighborhood, review_path)

        # Widen if insufficient data
        widened = False
        if not stats and neighborhood:
            stats = _query_revision_stats(conn, permit_type, None, review_path)
            widened = True
        if not stats:
            stats = _query_revision_stats(conn, None, None, review_path)
            widened = True

        # Get triggers for project type
        triggers = REVISION_TRIGGERS.get(project_type, REVISION_TRIGGERS["general"])

        # Mitigation strategies
        mitigations = [
            "Engage licensed professional experienced with SF DBI requirements",
            "Use the completeness checklist (tier1/completeness-checklist.json) before submission",
            "Include a Back Check page in all plan sets",
            "Ensure Title-24 energy compliance is complete before submission",
            "Verify plan description matches permit application exactly",
        ]

        if project_type == "restaurant":
            mitigations.insert(0, "Have DPH review requirements addressed in initial plan submission")
            mitigations.insert(1, "Include complete grease interceptor calculations with first submittal")
        if project_type == "adu":
            mitigations.insert(0, "Confirm Planning conditions before finalizing plans")
        if project_type in ("seismic", "new_construction"):
            mitigations.insert(0, "Reference geotechnical report in structural calculations")

        # Format output
        lines = ["# Revision Risk Assessment\n"]
        lines.append(f"**Permit Type:** {permit_type}")
        if neighborhood:
            lines.append(f"**Neighborhood:** {neighborhood}")
        if project_type:
            lines.append(f"**Project Type:** {project_type}")
        if review_path:
            lines.append(f"**Review Path:** {review_path}")

        if stats:
            # Classify risk level
            rate = stats["revision_proxy_rate"] or 0
            if rate > 0.20:
                risk_level = "HIGH"
            elif rate > 0.10:
                risk_level = "MODERATE"
            else:
                risk_level = "LOW"

            lines.append(f"\n## Revision Probability\n")
            lines.append(f"**Risk Level:** {risk_level}")
            lines.append(f"**Revision Rate:** {rate:.1%} of permits had cost increases during review")
            lines.append(f"**Sample Size:** {stats['total_permits']:,} permits analyzed")
            if widened:
                lines.append("*Note: query widened beyond specified filters for sufficient sample size*")

            if stats["avg_cost_increase_pct"]:
                lines.append(f"\n## Cost Impact\n")
                lines.append(f"- Average cost increase when revisions occur: **{stats['avg_cost_increase_pct']:.1f}%**")
                lines.append(f"- Permits with cost increase: {stats['permits_with_cost_increase']:,}")

            lines.append(f"\n## Timeline Impact\n")
            if stats["avg_days_no_change"] and stats["avg_days_with_change"]:
                delta = stats["avg_days_with_change"] - stats["avg_days_no_change"]
                lines.append(f"- Average days to issuance (no revisions): {stats['avg_days_no_change']}")
                lines.append(f"- Average days to issuance (with revisions): {stats['avg_days_with_change']}")
                lines.append(f"- **Revision penalty: +{delta} days on average**")
            if stats["p90_days"]:
                lines.append(f"- 90th percentile (worst case): {stats['p90_days']} days")
        else:
            lines.append("\n**Insufficient data** for statistical revision risk assessment.")

        lines.append(f"\n## Common Revision Triggers\n")
        for i, t in enumerate(triggers, 1):
            lines.append(f"{i}. {t}")

        lines.append(f"\n## Mitigation Strategies\n")
        for m in mitigations:
            lines.append(f"- {m}")

        lines.append(f"\n## Questions for Expert Review\n")
        lines.append("- What are the most common plan check correction items for this project type?")
        lines.append("- Are there specific reviewers known for particular requirements?")
        lines.append("- What pre-submission meetings (if any) could reduce revision rounds?")

        confidence = "high" if stats and stats["total_permits"] >= 100 and not widened else \
                     "medium" if stats else "low"
        lines.append(f"\n**Confidence:** {confidence}")

        return "\n".join(lines)
    finally:
        conn.close()
