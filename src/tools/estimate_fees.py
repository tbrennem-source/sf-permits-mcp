"""Tool: estimate_fees — Estimate permit fees using fee tables + DuckDB statistics."""

import math
from src.tools.knowledge_base import get_knowledge_base
from src.db import get_connection


def _calculate_building_fee(valuation: float, category: str, fee_tables: dict) -> dict:
    """Apply Table 1A-A fee schedule to construction valuation.

    Args:
        valuation: Estimated construction cost
        category: 'new_construction', 'alterations', or 'no_plans'
    """
    tiers = fee_tables.get("table_1A_A", {}).get("valuation_tiers", [])
    if not tiers:
        return {"error": "Fee table 1A-A not loaded"}

    for tier in tiers:
        min_val = tier.get("min_valuation", 0)
        max_val = tier.get("max_valuation")

        if max_val is None:
            in_range = valuation >= min_val
        else:
            in_range = min_val <= valuation <= max_val

        if not in_range:
            continue

        cat_data = tier.get(category, {})
        if not cat_data:
            # Fall back to alterations if category not found
            cat_data = tier.get("alterations", {})

        plan_review_fee = 0.0
        permit_issuance_fee = 0.0

        # Plan review
        pr = cat_data.get("plan_review", {})
        if pr:
            base = pr.get("base_fee", 0)
            per_inc = pr.get("per_increment", 0)
            inc_size = pr.get("increment_size", 1000)
            if per_inc and valuation > min_val:
                excess = valuation - min_val
                units = math.ceil(excess / inc_size)
                plan_review_fee = base + (units * per_inc)
            else:
                plan_review_fee = base

        # Permit issuance
        pi = cat_data.get("permit_issuance", {})
        if pi:
            base = pi.get("base_fee", 0)
            per_inc = pi.get("per_increment", 0)
            inc_size = pi.get("increment_size", 1000)
            if per_inc and valuation > min_val:
                excess = valuation - min_val
                units = math.ceil(excess / inc_size)
                permit_issuance_fee = base + (units * per_inc)
            else:
                permit_issuance_fee = base

        # Minimum fee
        minimum = tier.get("minimum_fee", 100)
        plan_review_fee = max(plan_review_fee, minimum) if plan_review_fee > 0 else 0
        permit_issuance_fee = max(permit_issuance_fee, minimum)

        return {
            "plan_review_fee": round(plan_review_fee, 2),
            "permit_issuance_fee": round(permit_issuance_fee, 2),
            "total_building_fee": round(plan_review_fee + permit_issuance_fee, 2),
            "tier": tier.get("range", "unknown"),
            "category": category,
        }

    return {"error": f"No matching tier for valuation ${valuation:,.0f}"}


def _calculate_surcharges(valuation: float, fee_tables: dict) -> dict:
    """Calculate state-mandated surcharges from Table 1A-J."""
    misc = fee_tables.get("table_1A_J", {}).get("fees", [])

    cbsc_fee = 0.0
    smip_fee = 0.0

    for item in misc:
        if "California Building Standards" in item.get("description", ""):
            # $4 per $100,000 in valuation
            cbsc_fee = max(1, (valuation / 100000) * 4)

        if "Strong Motion Instrumentation" in item.get("description", ""):
            # Use residential rate (0.00013) as default; commercial uses 0.00024
            sub_items = item.get("sub_items", [])
            if sub_items:
                # Default to residential 3-story-or-less rate
                smip_fee = max(1.60, valuation * 0.00013)

    return {
        "cbsc_fee": round(cbsc_fee, 2),
        "smip_fee": round(smip_fee, 2),
        "total_surcharges": round(cbsc_fee + smip_fee, 2),
    }


def _query_fee_stats(conn, permit_type: str, neighborhood: str | None,
                     cost_min: float, cost_max: float) -> dict | None:
    """Query DuckDB for statistical fee data from actual permits."""
    conditions = [
        "estimated_cost BETWEEN ? AND ?",
        "filed_date IS NOT NULL",
    ]
    params: list = [cost_min, cost_max]

    if permit_type:
        conditions.append("permit_type_definition ILIKE ?")
        params.append(f"%{permit_type}%")

    if neighborhood:
        conditions.append("neighborhood = ?")
        params.append(neighborhood)

    where = " AND ".join(conditions)
    result = conn.execute(f"""
        SELECT
            COUNT(*) as sample_size,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY estimated_cost) as p25,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY estimated_cost) as p50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY estimated_cost) as p75,
            AVG(estimated_cost) as avg_cost
        FROM permits
        WHERE {where}
    """, params).fetchone()

    if result and result[0] >= 5:
        return {
            "sample_size": result[0],
            "p25_cost": round(result[1], 2) if result[1] else None,
            "p50_cost": round(result[2], 2) if result[2] else None,
            "p75_cost": round(result[3], 2) if result[3] else None,
            "avg_cost": round(result[4], 2) if result[4] else None,
        }
    return None


async def estimate_fees(
    permit_type: str,
    estimated_construction_cost: float,
    square_footage: float | None = None,
    neighborhood: str | None = None,
    project_type: str | None = None,
) -> str:
    """Estimate permit fees using the DBI fee schedule + historical data.

    Combines formula-based fee calculation from Table 1A-A through 1A-S
    with statistical comparison against actual permit costs in DuckDB.

    Args:
        permit_type: 'alterations', 'new_construction', or 'no_plans'
        estimated_construction_cost: Project valuation in dollars
        square_footage: Optional project area for per-sqft analysis
        neighborhood: Optional SF neighborhood for statistical comparison
        project_type: Optional specific type (e.g., 'restaurant', 'adu') for additional fees

    Returns:
        Formatted fee estimate with formula breakdown and statistical context.
    """
    kb = get_knowledge_base()
    fee_tables = kb.fee_tables

    # Map permit_type to fee table category
    category_map = {
        "alterations": "alterations",
        "new_construction": "new_construction",
        "no_plans": "no_plans",
        "otc": "no_plans",
    }
    category = category_map.get(permit_type, "alterations")

    # Calculate formula-based fees
    building_fee = _calculate_building_fee(estimated_construction_cost, category, fee_tables)
    surcharges = _calculate_surcharges(estimated_construction_cost, fee_tables)

    # Additional fees based on project type
    additional_fees = []
    if project_type == "restaurant":
        additional_fees.append({"fee": "Plumbing permit (Category 6PA/6PB)", "estimate": "$543-$1,525"})
        additional_fees.append({"fee": "DPH health permit", "estimate": "varies"})
        additional_fees.append({"fee": "SFFD plan review", "estimate": "per Table 107-B"})
    if project_type == "adu":
        additional_fees.append({"fee": "Plumbing permit (Category 2PA/2PB)", "estimate": "$483-$701"})
        additional_fees.append({"fee": "Electrical permit", "estimate": "per Category 1 tiers"})
    if project_type in ("new_construction", "commercial_ti"):
        additional_fees.append({"fee": "School Impact Fee (SFUSD)", "estimate": "varies by floor area increase"})

    # ADA / accessibility cost analysis for commercial projects
    ada_analysis = None
    is_commercial = project_type in ("restaurant", "commercial_ti", "change_of_use", "adaptive_reuse")
    if is_commercial:
        ada = kb.ada_accessibility
        threshold = ada.get("valuation_threshold", {}).get("current_amount", 195358)
        if estimated_construction_cost > threshold:
            ada_analysis = {
                "threshold": threshold,
                "above_threshold": True,
                "rule": "FULL path-of-travel compliance required (CBC 11B)",
                "note": f"Construction cost ${estimated_construction_cost:,.0f} exceeds ${threshold:,.0f} threshold",
            }
        else:
            pct20 = estimated_construction_cost * 0.20
            ada_analysis = {
                "threshold": threshold,
                "above_threshold": False,
                "rule": "Path-of-travel compliance limited to 20% of construction cost",
                "max_accessibility_spend": round(pct20, 2),
                "note": f"Budget up to ${pct20:,.0f} for accessibility upgrades (20% of ${estimated_construction_cost:,.0f})",
            }

    # Statistical comparison from DuckDB
    stat_data = None
    try:
        conn = get_connection()
        cost_min = estimated_construction_cost * 0.5
        cost_max = estimated_construction_cost * 2.0
        stat_data = _query_fee_stats(conn, permit_type, neighborhood, cost_min, cost_max)
        conn.close()
    except Exception:
        pass  # DuckDB not available — formula-only estimate

    # Total formula estimate
    total_dbi = 0.0
    if "error" not in building_fee:
        total_dbi = building_fee["total_building_fee"] + surcharges["total_surcharges"]

    # Format output
    lines = ["# Fee Estimate\n"]
    lines.append(f"**Construction Valuation:** ${estimated_construction_cost:,.0f}")
    lines.append(f"**Permit Category:** {category}")
    if square_footage:
        lines.append(f"**Square Footage:** {square_footage:,.0f}")

    lines.append(f"\n## DBI Building Permit Fees (Table 1A-A)\n")
    if "error" not in building_fee:
        lines.append(f"| Fee Component | Amount |")
        lines.append(f"|--------------|--------|")
        lines.append(f"| Plan Review Fee | ${building_fee['plan_review_fee']:,.2f} |")
        lines.append(f"| Permit Issuance Fee | ${building_fee['permit_issuance_fee']:,.2f} |")
        lines.append(f"| CBSC Fee | ${surcharges['cbsc_fee']:,.2f} |")
        lines.append(f"| SMIP Fee | ${surcharges['smip_fee']:,.2f} |")
        lines.append(f"| **Total DBI Fees** | **${total_dbi:,.2f}** |")
        lines.append(f"\n*Fee tier: {building_fee['tier']}*")
    else:
        lines.append(f"Error: {building_fee['error']}")

    if additional_fees:
        lines.append(f"\n## Additional Fees (estimated)\n")
        for af in additional_fees:
            lines.append(f"- {af['fee']}: {af['estimate']}")

    if stat_data:
        lines.append(f"\n## Statistical Context (DuckDB)\n")
        lines.append(f"Similar permits ({stat_data['sample_size']:,} in database):")
        lines.append(f"- 25th percentile cost: ${stat_data['p25_cost']:,.0f}")
        lines.append(f"- Median cost: ${stat_data['p50_cost']:,.0f}")
        lines.append(f"- 75th percentile cost: ${stat_data['p75_cost']:,.0f}")
        if neighborhood:
            lines.append(f"- Filtered to: {neighborhood}")

    if ada_analysis:
        lines.append(f"\n## ADA/Accessibility Cost Impact\n")
        lines.append(f"**Valuation Threshold:** ${ada_analysis['threshold']:,.0f}")
        if ada_analysis["above_threshold"]:
            lines.append(f"**Status:** ABOVE threshold — {ada_analysis['rule']}")
        else:
            lines.append(f"**Status:** Below threshold — {ada_analysis['rule']}")
            lines.append(f"**Maximum Accessibility Spend:** ${ada_analysis['max_accessibility_spend']:,.2f}")
        lines.append(f"*{ada_analysis['note']}*")
        lines.append("- Submit DA-02 Disabled Access Compliance Checklist with permit application")

    lines.append(f"\n## Notes\n")
    lines.append("- Fee schedule effective 9/1/2025 (Ord. 126-25)")
    lines.append("- DBI may adjust valuation per DBI Cost Schedule")
    lines.append("- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total")
    lines.append("- Fees subject to periodic update — verify against current DBI schedule")

    confidence = "high" if "error" not in building_fee else "low"
    lines.append(f"\n**Confidence:** {confidence}")

    return "\n".join(lines)
