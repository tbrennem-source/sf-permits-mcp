"""Tool: estimate_fees — Estimate permit fees using fee tables + historical statistics."""

import math
import re
from src.tools.knowledge_base import get_knowledge_base, format_sources
from src.db import get_connection, BACKEND


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


def _calculate_sffd_fees(valuation: float, project_type: str | None, fire_code: dict) -> dict:
    """Calculate SFFD plan review + field inspection fees from Table 107-B/107-C.

    Uses fee data from fire-code-key-sections.json.
    """
    ch1 = fire_code.get("chapter_1_administration", {}).get("key_provisions", {})
    result = {"plan_review": 0.0, "field_inspection": 0.0, "system_fees": [],
              "operational_permits": [], "details": []}

    # Table 107-B plan review fees
    plan_fees = ch1.get("construction_permit_fees", {}).get("fee_examples", [])
    for tier in plan_fees:
        val_range = tier.get("valuation", "")
        fee_str = tier.get("fee", "")
        # Parse the base fee from the fee string (e.g., "$892.04 base + ...")
        base_fee = 0.0
        if "$" in fee_str:
            import re
            match = re.search(r'\$([\d,]+\.?\d*)', fee_str)
            if match:
                base_fee = float(match.group(1).replace(",", ""))

        # Match valuation to tier
        if "Over" in val_range or "over" in val_range:
            # Extract threshold from range like "Over $5,000,000"
            threshold_match = re.search(r'\$([\d,]+)', val_range)
            if threshold_match and valuation >= float(threshold_match.group(1).replace(",", "")):
                result["plan_review"] = base_fee
                # Calculate additional from "per additional $1,000" if present
                per_match = re.search(r'\$([\d.]+)\s+per\s+additional\s+\$1,000', fee_str)
                if per_match:
                    per_1k = float(per_match.group(1))
                    threshold = float(threshold_match.group(1).replace(",", ""))
                    excess = valuation - threshold
                    result["plan_review"] = base_fee + (math.ceil(excess / 1000) * per_1k)
                break
        else:
            # Parse range like "$50,001-$200,000"
            range_match = re.findall(r'\$([\d,]+)', val_range)
            if len(range_match) >= 2:
                low = float(range_match[0].replace(",", ""))
                high = float(range_match[1].replace(",", ""))
                if low <= valuation <= high:
                    result["plan_review"] = base_fee
                    per_match = re.search(r'\$([\d.]+)\s+per\s+additional\s+\$1,000', fee_str)
                    if per_match:
                        per_1k = float(per_match.group(1))
                        excess = valuation - low
                        result["plan_review"] = base_fee + (math.ceil(excess / 1000) * per_1k)
                    break

    # Table 107-C field inspection fees
    insp_fees = ch1.get("field_inspection_fees", {}).get("fees", [])
    for tier in insp_fees:
        val_range = tier.get("valuation_range", "")
        fee_str = tier.get("fee", "$0")
        fee_val = float(fee_str.replace("$", "").replace(",", ""))

        if "Over" in val_range or "over" in val_range:
            import re
            threshold_match = re.search(r'\$([\d,]+)', val_range)
            if threshold_match and valuation >= float(threshold_match.group(1).replace(",", "")):
                result["field_inspection"] = fee_val
                break
        else:
            range_match = re.findall(r'[\d,]+', val_range.replace("$", ""))
            if len(range_match) >= 2:
                low = float(range_match[0].replace(",", ""))
                high = float(range_match[1].replace(",", ""))
                if low <= valuation <= high:
                    result["field_inspection"] = fee_val
                    break

    # System-specific fees
    system_fees = ch1.get("field_inspection_fees", {}).get("system_specific_fees", [])
    if project_type == "restaurant":
        # Restaurants typically need hood suppression — similar to gaseous suppression
        for sf in system_fees:
            if "sprinkler" in sf.get("system", "").lower():
                result["system_fees"].append({"system": sf["system"], "fee": float(sf["fee"].replace("$", "").replace(",", ""))})

    # Operational permits
    if project_type == "restaurant":
        result["operational_permits"].append({"permit": "Place of Assembly (if >50 occupants)", "fee": 387})

    result["plan_review"] = round(result["plan_review"], 2)
    result["field_inspection"] = round(result["field_inspection"], 2)
    result["total_sffd"] = round(
        result["plan_review"] + result["field_inspection"] +
        sum(s["fee"] for s in result["system_fees"]) +
        sum(p["fee"] for p in result["operational_permits"]),
        2
    )
    return result


def _calculate_electrical_fee(
    project_type: str | None,
    square_footage: float | None,
    fee_tables: dict,
    outlet_count: int | None = None,
) -> dict | None:
    """Calculate electrical permit fee from Table 1A-E.

    A5: Implements real calculation based on Table 1A-E fee schedule.

    Uses category_1 (residential up to 10,000 sq ft) or category_2
    (nonresidential / residential over 10,000 sq ft) based on project type
    and square footage. Falls back to an informational note if no data available.

    Args:
        project_type: Project classification (e.g., 'restaurant', 'adu', 'new_construction')
        square_footage: Optional project area in sq ft (affects category selection)
        fee_tables: Knowledge base fee tables dict
        outlet_count: Optional outlet/device count for category_1 tiering

    Returns:
        Dict with 'estimate', 'category', 'fee', 'details', or None if not applicable.
    """
    table_1ae = fee_tables.get("table_1A_E", {})
    if not table_1ae:
        return None

    # Determine which category applies
    # Residential projects (adu, seismic on residential, general_alteration on residential)
    # use category_1 unless building > 10,000 sq ft.
    # Commercial / nonresidential use category_2.
    nonresidential_types = {"restaurant", "commercial_ti", "new_construction", "change_of_use",
                             "adaptive_reuse"}
    is_nonresidential = project_type in nonresidential_types
    is_large_residential = square_footage and square_footage > 10000

    if is_nonresidential or is_large_residential:
        cat = table_1ae.get("category_2", {})
        cat_name = "Category 2 (Nonresidential / Large Residential)"
        tiers = cat.get("tiers", [])

        # Select tier based on square footage
        if square_footage:
            selected_tier = None
            for tier in tiers:
                desc = tier.get("description", "").lower()
                # Parse sq ft ranges from tier description
                if "up to 2,500" in desc and square_footage <= 2500:
                    selected_tier = tier
                    break
                elif "2,501 to 5,000" in desc and 2501 <= square_footage <= 5000:
                    selected_tier = tier
                    break
                elif "5,001 to 10,000" in desc and 5001 <= square_footage <= 10000:
                    selected_tier = tier
                    break
                elif "10,001 to 30,000" in desc and 10001 <= square_footage <= 30000:
                    selected_tier = tier
                    break
                elif "30,001 to 50,000" in desc and 30001 <= square_footage <= 50000:
                    selected_tier = tier
                    break
                elif "50,001 to 100,000" in desc and 50001 <= square_footage <= 100000:
                    selected_tier = tier
                    break
                elif "100,001 to 500,000" in desc and 100001 <= square_footage <= 500000:
                    selected_tier = tier
                    break
                elif "500,001 to 1,000,000" in desc and 500001 <= square_footage <= 1000000:
                    selected_tier = tier
                    break
                elif "more than 1,000,000" in desc and square_footage > 1000000:
                    selected_tier = tier
                    break

            if selected_tier:
                fee = selected_tier["fee"]
                return {
                    "estimate": f"${fee:,}",
                    "fee": fee,
                    "category": cat_name,
                    "tier": selected_tier["description"],
                    "details": [{"category": "2", "description": selected_tier["description"], "fee": fee}],
                    "note": "Includes Category 3 & 4 for new/major remodel (marked with *)",
                }

        # No sq ft provided — return range for nonresidential
        if tiers:
            low = tiers[0]["fee"]
            high = tiers[-1]["fee"]
            return {
                "estimate": f"${low:,}–${high:,}",
                "category": cat_name,
                "details": tiers[:3],  # Show first 3 tiers as examples
                "note": "Provide square footage for a precise tier estimate",
            }

    else:
        # Residential category_1
        cat = table_1ae.get("category_1", {})
        cat_name = "Category 1 (Residential up to 10,000 sq ft)"
        tiers = cat.get("tiers", [])

        # Select tier based on outlet count or project type hints
        if outlet_count is not None:
            for tier in tiers:
                desc = tier.get("description", "").lower()
                if "up to 10" in desc and outlet_count <= 10:
                    fee = tier["fee"]
                    return {
                        "estimate": f"${fee:,}",
                        "fee": fee,
                        "category": cat_name,
                        "tier": tier["description"],
                        "details": [{"category": "1", "description": tier["description"], "fee": fee}],
                    }
                elif "11 to 20" in desc and 11 <= outlet_count <= 20:
                    fee = tier["fee"]
                    return {
                        "estimate": f"${fee:,}",
                        "fee": fee,
                        "category": cat_name,
                        "tier": tier["description"],
                        "details": [{"category": "1", "description": tier["description"], "fee": fee}],
                    }
                elif "up to 40" in desc and 21 <= outlet_count <= 40:
                    fee = tier["fee"]
                    return {
                        "estimate": f"${fee:,}",
                        "fee": fee,
                        "category": cat_name,
                        "tier": tier["description"],
                        "details": [{"category": "1", "description": tier["description"], "fee": fee}],
                    }
                elif "more than 40" in desc and outlet_count > 40:
                    fee = tier["fee"]
                    return {
                        "estimate": f"${fee:,}",
                        "fee": fee,
                        "category": cat_name,
                        "tier": tier["description"],
                        "details": [{"category": "1", "description": tier["description"], "fee": fee}],
                    }

        # No outlet count — apply sq ft heuristic or return typical residential tier
        if square_footage and square_footage >= 5000:
            # Large residential building tier
            for tier in tiers:
                if "5,000 to 10,000" in tier.get("description", ""):
                    fee = tier["fee"]
                    return {
                        "estimate": f"${fee:,}",
                        "fee": fee,
                        "category": cat_name,
                        "tier": tier["description"],
                        "details": [{"category": "1", "description": tier["description"], "fee": fee}],
                    }

        # Default: return range across category 1
        if tiers:
            low = tiers[0]["fee"]
            high = tiers[-1]["fee"]
            return {
                "estimate": f"${low:,}–${high:,}",
                "category": cat_name,
                "details": tiers,
                "note": "Range depends on outlet/device count. Provide outlet count for precise estimate.",
            }

    return None


def _calculate_plumbing_fee(project_type: str | None, fee_tables: dict) -> dict | None:
    """Look up plumbing fee from Table 1A-C based on project type.

    A6: Expanded to cover 5+ project types (previously only 3).
    Covers: restaurant, adu, new_construction, commercial_ti, multifamily, seismic,
            general_alteration (single residential), fire_sprinkler, office.
    """
    table_1ac = fee_tables.get("table_1A_C", {})
    categories = table_1ac.get("categories", [])
    if not categories:
        return None

    # A6: Expanded category map — was only restaurant/adu/new_construction
    # Now covers 10+ project types mapped to the correct Table 1A-C codes
    category_map = {
        # Original 3
        "restaurant": ["6PA", "6PB"],
        "adu": ["2PA", "2PB"],
        "new_construction": ["1P"],
        # A6 additions
        "commercial_ti": ["5P/5M"],       # Office, mercantile & retail — per tenant/floor
        "multifamily": ["3PA", "3PB", "3PC"],  # 7-36+ dwelling units
        "low_rise_multifamily": ["2PA", "2PB"],  # Up to 6 units
        "seismic": ["1P"],                 # Residential fixture work during seismic
        "general_alteration": ["1P"],      # Single residential unit kitchen/bath work
        "bathroom_remodel": ["1P"],        # Single residential unit plumbing
        "kitchen_remodel": ["1P"],         # Single residential unit plumbing
        "boiler": ["8"],                   # New boiler installations
        "fire_sprinkler": ["4PA", "4PB"],  # Fire sprinkler systems
    }

    target_cats = category_map.get(project_type, [])
    if not target_cats:
        return None

    fees = []
    for cat in categories:
        code = cat.get("code", "")
        if code in target_cats:
            fee = cat.get("fee")
            if fee is not None:
                fees.append({"category": code, "description": cat.get("description", ""), "fee": fee})

    if fees:
        if len(fees) == 1:
            return {"estimate": f"${fees[0]['fee']:,}", "details": fees}
        else:
            low = min(f["fee"] for f in fees)
            high = max(f["fee"] for f in fees)
            return {"estimate": f"${low:,}–${high:,}", "details": fees}
    return None


def _query_fee_stats(conn, permit_type: str, neighborhood: str | None,
                     cost_min: float, cost_max: float) -> dict | None:
    """Query historical permits for statistical fee data."""
    ph = "%s" if BACKEND == "postgres" else "?"
    conditions = [
        f"estimated_cost BETWEEN {ph} AND {ph}",
        "filed_date IS NOT NULL",
    ]
    params: list = [cost_min, cost_max]

    if permit_type:
        conditions.append(f"permit_type_definition ILIKE {ph}")
        params.append(f"%{permit_type}%")

    if neighborhood:
        conditions.append(f"neighborhood = {ph}")
        params.append(neighborhood)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            COUNT(*) as sample_size,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY estimated_cost) as p25,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY estimated_cost) as p50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY estimated_cost) as p75,
            AVG(estimated_cost) as avg_cost
        FROM permits
        WHERE {where}
    """

    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params)
            result = cur.fetchone()
    else:
        result = conn.execute(sql, params).fetchone()

    if result and result[0] >= 5:
        return {
            "sample_size": result[0],
            "p25_cost": round(float(result[1]), 2) if result[1] else None,
            "p50_cost": round(float(result[2]), 2) if result[2] else None,
            "p75_cost": round(float(result[3]), 2) if result[3] else None,
            "avg_cost": round(float(result[4]), 2) if result[4] else None,
        }
    return None


COST_REVISION_BRACKETS = [
    {"label": "Under $5K", "min": 0, "max": 5000, "rate": 0.217, "multiplier": "4.8x avg increase"},
    {"label": "$5K–$25K", "min": 5000, "max": 25000, "rate": 0.208, "multiplier": "+33% avg increase"},
    {"label": "$25K–$100K", "min": 25000, "max": 100000, "rate": 0.286, "multiplier": "+23% avg increase"},
    {"label": "$100K–$500K", "min": 100000, "max": 500000, "rate": 0.285, "multiplier": "+17% avg increase"},
    {"label": "Over $500K", "min": 500000, "max": float("inf"), "rate": 0.198, "multiplier": "-32% avg (cost decreases common)"},
]


def _get_cost_revision_bracket(cost: float) -> dict | None:
    """Find the cost revision bracket for a given construction cost."""
    for bracket in COST_REVISION_BRACKETS:
        if bracket["min"] <= cost < bracket["max"]:
            return bracket
    return COST_REVISION_BRACKETS[-1]  # Over $500K


async def estimate_fees(
    permit_type: str,
    estimated_construction_cost: float,
    square_footage: float | None = None,
    neighborhood: str | None = None,
    project_type: str | None = None,
    return_structured: bool = False,
) -> str | tuple[str, dict]:
    """Estimate permit fees using the DBI fee schedule + historical data.

    Combines formula-based fee calculation from Table 1A-A through 1A-S
    with statistical comparison against actual permit costs in DuckDB.

    Args:
        permit_type: 'alterations', 'new_construction', or 'no_plans'
        estimated_construction_cost: Project valuation in dollars
        square_footage: Optional project area for per-sqft analysis
        neighborhood: Optional SF neighborhood for statistical comparison
        project_type: Optional specific type (e.g., 'restaurant', 'adu') for additional fees
        return_structured: If True, returns (markdown_str, methodology_dict) tuple

    Returns:
        Formatted fee estimate with formula breakdown and statistical context.
        If return_structured=True, returns (str, dict) tuple.
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

    # SFFD fees (from fire-code-key-sections.json Table 107-B/107-C)
    sffd_fees = None
    fire_triggers = ["restaurant", "new_construction", "commercial_ti", "change_of_use"]
    if project_type in fire_triggers:
        sffd_fees = _calculate_sffd_fees(estimated_construction_cost, project_type, kb.fire_code)

    # Plumbing fees (from fee-tables.json Table 1A-C) — A6: expanded coverage
    plumbing_fees = _calculate_plumbing_fee(project_type, fee_tables)

    # A5: Electrical fees (from fee-tables.json Table 1A-E)
    electrical_triggers = ["restaurant", "commercial_ti", "new_construction", "adu",
                           "adaptive_reuse", "change_of_use", "general_alteration",
                           "kitchen_remodel", "bathroom_remodel"]
    electrical_fees = None
    if project_type in electrical_triggers or not project_type:
        electrical_fees = _calculate_electrical_fee(project_type, square_footage, fee_tables)

    # Additional fees based on project type
    additional_fees = []
    if plumbing_fees:
        additional_fees.append({"fee": "Plumbing permit", "estimate": plumbing_fees["estimate"]})
    if project_type == "restaurant":
        additional_fees.append({"fee": "DPH health permit", "estimate": "varies by facility type"})
    if project_type in ("new_construction", "commercial_ti"):
        additional_fees.append({"fee": "School Impact Fee (SFUSD)", "estimate": "varies by floor area increase"})

    # ADA / accessibility cost analysis for commercial projects
    ada_analysis = None
    is_commercial = project_type in ("restaurant", "commercial_ti", "change_of_use", "adaptive_reuse")
    if is_commercial:
        ada = kb.ada_accessibility
        threshold = ada.get("valuation_threshold", {}).get("current_amount", 203611)
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
    # Add electrical fee to total if a precise single fee was calculated
    if electrical_fees and electrical_fees.get("fee"):
        total_dbi += electrical_fees["fee"]

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

    if sffd_fees and sffd_fees["total_sffd"] > 0:
        lines.append(f"\n## SFFD Fees (Table 107-B / 107-C)\n")
        lines.append(f"| Fee Component | Amount |")
        lines.append(f"|--------------|--------|")
        lines.append(f"| SFFD Plan Review (Table 107-B) | ${sffd_fees['plan_review']:,.2f} |")
        lines.append(f"| SFFD Field Inspection (Table 107-C) | ${sffd_fees['field_inspection']:,.2f} |")
        for sf in sffd_fees.get("system_fees", []):
            lines.append(f"| {sf['system']} | ${sf['fee']:,.2f} |")
        for op in sffd_fees.get("operational_permits", []):
            lines.append(f"| {op['permit']} | ${op['fee']:,.2f} |")
        lines.append(f"| **Total SFFD Fees** | **${sffd_fees['total_sffd']:,.2f}** |")

    # A5: Electrical permit fee section
    if electrical_fees:
        lines.append(f"\n## Electrical Permit Fee (Table 1A-E)\n")
        lines.append(f"| Fee Component | Amount |")
        lines.append(f"|--------------|--------|")
        lines.append(f"| Electrical Permit ({electrical_fees.get('category', 'Table 1A-E')}) | {electrical_fees['estimate']} |")
        if electrical_fees.get("tier"):
            lines.append(f"\n*Tier: {electrical_fees['tier']}*")
        if electrical_fees.get("note"):
            lines.append(f"*{electrical_fees['note']}*")

    if plumbing_fees:
        lines.append(f"\n## Plumbing/Mechanical Permit Fee (Table 1A-C)\n")
        lines.append(f"| Fee Component | Amount |")
        lines.append(f"|--------------|--------|")
        for detail in plumbing_fees.get("details", []):
            lines.append(f"| {detail['category']} — {detail['description'][:60]} | ${detail['fee']:,} |")
        if len(plumbing_fees.get("details", [])) > 1:
            lines.append(f"| **Plumbing Permit Range** | **{plumbing_fees['estimate']}** |")
        else:
            lines.append(f"| **Plumbing Permit Total** | **{plumbing_fees['estimate']}** |")

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

    # Cost Revision Risk section
    revision_bracket = _get_cost_revision_bracket(estimated_construction_cost)
    if revision_bracket:
        budget_ceiling = estimated_construction_cost * (1 + revision_bracket["rate"])
        lines.append(f"\n## Cost Revision Risk\n")
        lines.append(f"Cost revision probability: ~{revision_bracket['rate']:.0%} for projects in the {revision_bracket['label']} range.")
        lines.append(f"Historical pattern: {revision_bracket['multiplier']}.")
        lines.append(f"Budget recommendation: plan for ${budget_ceiling:,.0f} as your ceiling.")

    lines.append(f"\n## Notes\n")
    lines.append("- Fee schedule effective 9/1/2025 (Ord. 126-25)")
    lines.append("- DBI may adjust valuation per DBI Cost Schedule")
    lines.append("- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total")
    lines.append("- Fees subject to periodic update — verify against current DBI schedule")

    confidence = "high" if "error" not in building_fee else "low"
    lines.append(f"\n**Confidence:** {confidence}")

    # Coverage disclaimer
    coverage_gaps = ["Planning fees not included", "Electrical fees estimated from Table 1A-E"]
    if not sffd_fees:
        coverage_gaps.append("SFFD fees not calculated (project type may not trigger fire review)")
    lines.append(f"\n## Data Coverage\n")
    for gap in coverage_gaps:
        lines.append(f"- {gap}")

    # Build source citations
    sources = ["fee_tables"]
    if sffd_fees:
        sources.append("fire_code")
    if ada_analysis:
        sources.append("ada_accessibility")
    if stat_data:
        sources.append("duckdb_permits")
    if electrical_fees:
        sources.append("fee_tables")  # Table 1A-E is in fee_tables
    lines.append(format_sources(sources))

    md_output = "\n".join(lines)

    if return_structured:
        from datetime import date
        # Build formula steps
        formula_steps = []
        if "error" not in building_fee:
            formula_steps.append(f"Plan Review Fee: ${building_fee['plan_review_fee']:,.2f}")
            formula_steps.append(f"Permit Issuance Fee: ${building_fee['permit_issuance_fee']:,.2f}")
            formula_steps.append(f"CBSC Fee: ${surcharges['cbsc_fee']:,.2f}")
            formula_steps.append(f"SMIP Fee: ${surcharges['smip_fee']:,.2f}")
            formula_steps.append(f"Total DBI: ${total_dbi:,.2f}")

        data_sources = ["DBI Table 1A-A fee schedule", "1.1M permit records"]
        if sffd_fees:
            data_sources.append("SFFD Table 107-B/107-C")
        if electrical_fees:
            data_sources.append("DBI Table 1A-E electrical fees")
        if plumbing_fees:
            data_sources.append("DBI Table 1A-C plumbing fees")

        methodology = {
            "tool": "estimate_fees",
            "headline": f"${total_dbi:,.0f}" if total_dbi > 0 else "See breakdown",
            "formula_steps": formula_steps,
            "data_sources": data_sources,
            "sample_size": stat_data["sample_size"] if stat_data else 0,
            "data_freshness": date.today().isoformat(),
            "confidence": confidence,
            "coverage_gaps": coverage_gaps,
        }
        return md_output, methodology

    return md_output
