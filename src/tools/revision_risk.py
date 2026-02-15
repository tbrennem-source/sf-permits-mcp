"""Tool: revision_risk — Estimate revision probability and impact from permit data patterns."""

import logging

from src.db import get_connection, BACKEND
from src.tools.knowledge_base import get_knowledge_base, format_sources

logger = logging.getLogger(__name__)

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


def _get_correction_frequencies(project_type: str | None, kb) -> list[dict]:
    """Get top correction category frequencies from compliance knowledge."""
    corrections = []

    # Title-24 — #1 correction category (~45% of commercial alterations)
    t24 = kb.title24
    if t24:
        is_commercial = project_type in ("restaurant", "commercial_ti", "change_of_use", "adaptive_reuse")
        rate = "~45% of commercial alterations" if is_commercial else "common across all project types"
        corrections.append({
            "category": "Title-24 Energy Compliance",
            "rate": rate,
            "detail": "Missing or incorrect energy forms. Submit CF1R/NRCC with initial application. (T24-C01)",
        })

    # ADA — #2 correction category (~38% of commercial alterations)
    ada = kb.ada_accessibility
    if ada and project_type in ("restaurant", "commercial_ti", "change_of_use", "adaptive_reuse", None):
        corrections.append({
            "category": "ADA/Accessibility (CBC 11B)",
            "rate": "~38% of commercial alterations",
            "detail": "Missing DA-02 checklist or path-of-travel documentation. (ADA-C01)",
        })

    # DPH — restaurant-specific
    dph = kb.dph_food
    if dph and project_type == "restaurant":
        corrections.append({
            "category": "DPH Food Facility",
            "rate": "high for restaurant conversions",
            "detail": "Equipment schedule not cross-referenced to layout, or missing exhaust data sheets. (DPH-002, DPH-004)",
        })
        # Equipment schedule is the #1 DPH correction
        equip_tmpl = dph.get("equipment_schedule_template", {})
        if equip_tmpl:
            corrections.append({
                "category": "DPH Equipment Schedule (Appendix C)",
                "rate": "#1 DPH correction item",
                "detail": "Must include: Item#, Name, Manufacturer, Model, Dimensions, NSF cert, Gas/Elec, BTU/kW. Numbers must match floor plan.",
            })

    return corrections


def _query_revision_stats(conn, permit_type: str | None, neighborhood: str | None,
                          review_path: str | None) -> dict | None:
    """Query permits for revision indicators using revised_cost as proxy."""
    ph = "%s" if BACKEND == "postgres" else "?"
    conditions = [
        "filed_date IS NOT NULL",
        "issued_date IS NOT NULL",
        "estimated_cost > 0",
    ]
    params = []

    if permit_type:
        conditions.append(f"permit_type_definition ILIKE {ph}")
        params.append(f"%{permit_type}%")
    if neighborhood:
        conditions.append(f"neighborhood = {ph}")
        params.append(neighborhood)
    if review_path:
        if review_path == "otc":
            conditions.append(f"permit_type_definition ILIKE {ph}")
            params.append("%otc%")
        else:
            conditions.append(f"permit_type_definition NOT ILIKE {ph}")
            params.append("%otc%")

    where = " AND ".join(conditions)

    # DATE_DIFF is DuckDB-specific; Postgres uses (date2::date - date1::date)
    if BACKEND == "postgres":
        date_diff_expr = "(issued_date::date - filed_date::date)"
    else:
        date_diff_expr = "DATE_DIFF('day', filed_date::DATE, issued_date::DATE)"

    sql = f"""
        SELECT
            COUNT(*) as total_permits,
            COUNT(CASE WHEN revised_cost > estimated_cost THEN 1 END) as permits_with_cost_increase,
            ROUND(
                COUNT(CASE WHEN revised_cost > estimated_cost THEN 1 END)::DECIMAL
                / NULLIF(COUNT(*), 0), 3
            ) as revision_proxy_rate,
            AVG(CASE WHEN revised_cost > estimated_cost
                THEN (revised_cost - estimated_cost) / NULLIF(estimated_cost, 0) * 100
            END) as avg_cost_increase_pct,
            AVG(CASE WHEN revised_cost IS NULL OR revised_cost = estimated_cost
                THEN {date_diff_expr} END) as avg_days_no_change,
            AVG(CASE WHEN revised_cost > estimated_cost
                THEN {date_diff_expr} END) as avg_days_with_change,
            PERCENTILE_CONT(0.90) WITHIN GROUP (
                ORDER BY {date_diff_expr}
            ) as p90_days
        FROM permits
        WHERE {where}
            AND filed_date::DATE < issued_date::DATE
            AND {date_diff_expr} BETWEEN 1 AND 1000
    """

    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params)
            result = cur.fetchone()
    else:
        result = conn.execute(sql, params).fetchone()

    if result and result[0] >= 20:
        return {
            "total_permits": result[0],
            "permits_with_cost_increase": result[1],
            "revision_proxy_rate": float(result[2]) if result[2] else None,
            "avg_cost_increase_pct": round(float(result[3]), 1) if result[3] else None,
            "avg_days_no_change": round(float(result[4])) if result[4] else None,
            "avg_days_with_change": round(float(result[5])) if result[5] else None,
            "p90_days": round(float(result[6])) if result[6] else None,
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
    # Try DuckDB for statistical data — gracefully degrade if unavailable
    stats = None
    widened = False
    db_available = False

    try:
        conn = get_connection()
        try:
            stats = _query_revision_stats(conn, permit_type, neighborhood, review_path)
            db_available = True

            # Widen if insufficient data
            if not stats and neighborhood:
                stats = _query_revision_stats(conn, permit_type, None, review_path)
                widened = True
            if not stats:
                stats = _query_revision_stats(conn, None, None, review_path)
                widened = True
        finally:
            conn.close()
    except Exception as e:
        logger.warning("DB connection failed in revision_risk: %s", e)

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
        mitigations.insert(2, "Submit numbered equipment schedule cross-referenced to layout (DPH #1 correction)")
    if project_type == "adu":
        mitigations.insert(0, "Confirm Planning conditions before finalizing plans")
    if project_type in ("seismic", "new_construction"):
        mitigations.insert(0, "Reference geotechnical report in structural calculations")
    if project_type in ("restaurant", "commercial_ti", "change_of_use"):
        mitigations.append("Consider CASp (Certified Access Specialist) inspection — reduces ADA correction rate from ~38% to ~10%")
        mitigations.append("Submit DA-02 checklist with initial application (most common ADA correction is missing DA-02)")

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
        if not db_available:
            lines.append("\n*Historical permit database not available — using knowledge-based assessment*")
        lines.append("\n## Risk Assessment (knowledge-based)\n")
        lines.append("Based on SF DBI patterns, typical revision risk factors:")
        lines.append("- **In-house review:** ~15-20% of permits require corrections")
        lines.append("- **Revision penalty:** +60-120 days typical when corrections occur")
        lines.append("- **Most common cause:** Incomplete documentation at initial submittal")

    lines.append(f"\n## Common Revision Triggers\n")
    for i, t in enumerate(triggers, 1):
        lines.append(f"{i}. {t}")

    # Correction frequency data from compliance knowledge
    kb = get_knowledge_base()
    correction_data = _get_correction_frequencies(project_type, kb)
    if correction_data:
        lines.append(f"\n## Top Correction Categories (citywide data)\n")
        for cd in correction_data:
            lines.append(f"- **{cd['category']}** ({cd['rate']}): {cd['detail']}")

    # EPR resubmittal guidance from correction workflow
    epr = kb.epr_requirements
    correction_workflow = epr.get("correction_response_workflow", {})
    if correction_workflow:
        lines.append(f"\n## EPR Resubmittal Process\n")
        lines.append("*When corrections are required during plan review:*\n")
        for step in correction_workflow.get("steps", [])[:4]:  # Top 4 steps
            lines.append(f"- **{step.get('id', '')}:** {step.get('step', '')}")
            mistake = step.get("common_mistake", "")
            if mistake:
                lines.append(f"  ⚠️ Common mistake: {mistake}")

    # DA-02 checklist deficiencies for commercial
    ada = kb.ada_accessibility
    if ada and project_type in ("restaurant", "commercial_ti", "change_of_use", "adaptive_reuse"):
        da02 = ada.get("da02_form_structure", {})
        form_c = da02.get("form_c", {})
        categories = form_c.get("checklist_categories", [])
        if categories:
            lines.append(f"\n## DA-02 Common Deficiency Areas\n")
            for cat in categories:
                deficiency = cat.get("common_deficiency", "")
                if deficiency:
                    lines.append(f"- **{cat['category']}:** {deficiency}")

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

    # Source citations
    sources = []
    if db_available:
        sources.append("duckdb_permits")
    if correction_data:
        sources.append("title24")
    if project_type in ("restaurant", "commercial_ti", "change_of_use", "adaptive_reuse"):
        sources.append("ada_accessibility")
    if project_type == "restaurant":
        sources.extend(["dph_food", "restaurant_guide"])
    if epr and correction_workflow:
        sources.append("epr_requirements")
    lines.append(format_sources(sources))

    return "\n".join(lines)
