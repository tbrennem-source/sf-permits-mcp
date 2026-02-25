"""Tool: predict_permits — Predict required permits, forms, routing, and review path."""

import json
import logging
from src.tools.knowledge_base import get_knowledge_base, format_sources

logger = logging.getLogger(__name__)

# Project type keywords mapped from semantic index concepts
# These map to special_project_types in the decision tree
PROJECT_TYPE_KEYWORDS = {
    "restaurant": ["restaurant", "food service", "commercial kitchen", "grease trap",
                    "hood", "ventilation", "dining", "food facility", "grease interceptor",
                    "type i hood", "kitchen hood"],
    "adu": ["adu", "accessory dwelling", "in-law", "granny flat", "garage conversion",
            "in-law unit", "secondary unit"],
    "seismic": ["seismic", "earthquake", "retrofit", "soft story", "foundation bolting",
                "brace and bolt", "anchor bolt", "seismic upgrade", "seismic retrofit",
                "seismic strengthening", "cripple wall", "ebb", "earthquake brace",
                "house bolting"],
    "commercial_ti": ["tenant improvement", "office buildout", "commercial alteration",
                      "ti", "buildout", "commercial interior", "office remodel",
                      "commercial renovation"],
    "adaptive_reuse": ["adaptive reuse", "conversion", "warehouse to residential",
                       "commercial to residential", "office to residential"],
    "solar": ["solar", "photovoltaic", "pv", "clean energy", "battery storage",
              "ev charging", "energy storage"],
    "demolition": ["demolition", "demolish", "tear down", "raze"],
    "change_of_use": ["change of use", "change of occupancy", "change occupancy",
                      "retail to", "office to", "residential to"],
    "historic": ["historic", "landmark", "preservation", "heritage",
                 "article 10", "article 11", "conservation district"],
    "new_construction": ["new construction", "new building", "ground up",
                         "build new", "new structure"],
    "low_rise_multifamily": ["multifamily", "multi-family", "apartment", "condo",
                              "condominium", "townhouse", "triplex", "fourplex",
                              "4-plex", "low-rise residential"],
}


def _query_ref_permit_forms(project_types: list[str]) -> dict | None:
    """Query ref_permit_forms table for form/review_path by project type.

    Returns a dict with 'form', 'review_path', 'notes' if found, or None.
    Falls back gracefully if the table is empty or the query fails.
    """
    if not project_types:
        return None
    try:
        from src.db import get_connection, BACKEND
        conn = get_connection()
        try:
            ph = "%s" if BACKEND == "postgres" else "?"
            placeholders = ", ".join([ph] * len(project_types))
            sql = (
                f"SELECT project_type, permit_form, review_path, notes"
                f" FROM ref_permit_forms"
                f" WHERE project_type IN ({placeholders})"
                f" ORDER BY id LIMIT 5"
            )
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(sql, project_types)
                    rows = cur.fetchall()
            else:
                rows = conn.execute(sql, project_types).fetchall()

            if not rows:
                return None
            # Return first matching row (most specific project type)
            r = rows[0]
            return {"form": r[1], "review_path": r[2], "notes": r[3] or ""}
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("ref_permit_forms query failed (using hardcoded): %s", exc)
        return None


def _query_ref_agency_triggers(project_types: list[str]) -> list[dict] | None:
    """Query ref_agency_triggers table for agency routing by project type keywords.

    Returns a list of dicts with 'agency', 'reason', 'adds_weeks' if found, or None.
    Falls back gracefully if the table is empty or the query fails.
    """
    if not project_types:
        return None
    try:
        from src.db import get_connection, BACKEND
        conn = get_connection()
        try:
            ph = "%s" if BACKEND == "postgres" else "?"
            placeholders = ", ".join([ph] * len(project_types))
            sql = (
                f"SELECT trigger_keyword, agency, reason, adds_weeks"
                f" FROM ref_agency_triggers"
                f" WHERE trigger_keyword IN ({placeholders})"
                f" ORDER BY agency"
            )
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(sql, project_types)
                    rows = cur.fetchall()
            else:
                rows = conn.execute(sql, project_types).fetchall()

            if not rows:
                return None
            return [
                {"trigger": r[0], "agency": r[1], "reason": r[2] or "", "adds_weeks": r[3] or 0}
                for r in rows
            ]
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("ref_agency_triggers query failed (using hardcoded): %s", exc)
        return None


def _extract_project_types(description: str, scope_override: list[str] | None) -> list[str]:
    """Extract project type categories from description text."""
    if scope_override:
        return scope_override

    desc_lower = description.lower()
    matched = []
    for ptype, keywords in PROJECT_TYPE_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            matched.append(ptype)

    # Default to general alteration if nothing matched
    if not matched:
        matched.append("general_alteration")
    return matched


def _determine_form(project_types: list[str], kb, db_form: dict | None = None) -> dict:
    """Determine which permit form is needed.

    Uses DB-backed ref_permit_forms data when available, falls back to hardcoded logic.
    """
    # Use DB result if available
    if db_form:
        form_name = db_form.get("form", "Form 3/8")
        notes = db_form.get("notes", "")
        return {
            "form": form_name,
            "reason": f"Based on project type (ref_permit_forms)",
            "notes": notes,
            "source": "db",
        }

    dt = kb.decision_tree.get("steps", {}).get("step_2_which_form", {})

    if "new_construction" in project_types:
        return {"form": "Form 1/2", "reason": "New construction", "notes": "Mark Form 1 (non-wood) or Form 2 (wood frame)"}
    if "demolition" in project_types:
        return {"form": "Form 6", "reason": "Demolition", "notes": "May be paired with Form 1/2 for replacement construction"}
    # Most alterations use Form 3/8
    return {"form": "Form 3/8", "reason": "Alterations/repairs to existing building",
            "notes": "Mark Form 3 for in-house review, Form 8 for OTC-eligible projects"}


def _determine_review_path(project_types: list[str], estimated_cost: float | None, kb) -> dict:
    """Determine OTC vs in-house review path."""
    otc = kb.otc_criteria

    # Projects that are always in-house
    always_inhouse = [
        "new_construction", "demolition", "change_of_use", "adu",
        "adaptive_reuse", "historic", "restaurant",
    ]
    for pt in project_types:
        if pt in always_inhouse:
            return {
                "path": "in_house",
                "reason": f"'{pt}' projects require in-house review",
                "confidence": "high",
            }

    # Check the not-OTC list
    not_otc = otc.get("not_otc_requires_inhouse", {}).get("projects", [])
    not_otc_lower = [p.lower() if isinstance(p, str) else p.get("description", "").lower() for p in not_otc]

    # Restaurant to full restaurant is always in-house
    if "restaurant" in project_types and "change_of_use" in project_types:
        return {"path": "in_house", "reason": "Restaurant change of use requires in-house review", "confidence": "high"}

    # Simple residential scope might be OTC
    if "general_alteration" in project_types or "commercial_ti" in project_types:
        if estimated_cost and estimated_cost < 50000:
            return {
                "path": "likely_otc",
                "reason": "Small scope alteration may qualify for OTC — verify with DBI",
                "confidence": "medium",
            }
        return {
            "path": "likely_in_house",
            "reason": "Scope likely exceeds OTC one-hour review threshold",
            "confidence": "medium",
        }

    if "seismic" in project_types:
        # Voluntary brace-and-bolt can be OTC per S-09
        return {
            "path": "depends",
            "reason": "Voluntary brace/bolt (S-09) is OTC with Form 8 if prescriptive per CEBC A3 — no licensed professional required. Mandatory soft-story (AB-094/106) or engineered seismic retrofit is in-house.",
            "confidence": "medium",
        }

    if "solar" in project_types:
        return {
            "path": "likely_otc",
            "reason": "Solar/PV installations are typically OTC with plans; qualifies for priority processing",
            "confidence": "medium",
        }

    return {"path": "likely_in_house", "reason": "Default to in-house for unclassified scope", "confidence": "low"}


def _determine_agency_routing(project_types: list[str], kb, db_triggers: list[dict] | None = None) -> list[dict]:
    """Determine which agencies must review the permit.

    Uses DB-backed ref_agency_triggers data when available to supplement hardcoded logic.
    """
    agencies = []

    # Almost everything goes to BLDG
    agencies.append({"agency": "DBI (Building)", "required": True, "reason": "All permitted work"})

    # If DB triggers are available, use them to add agencies not already in the list
    if db_triggers:
        seen_agencies = {"DBI (Building)"}
        for trigger in db_triggers:
            agency_name = trigger["agency"]
            if agency_name not in seen_agencies and agency_name != "DBI (Building)":
                agencies.append({
                    "agency": agency_name,
                    "required": True,
                    "reason": trigger["reason"] or f"Triggered by {trigger['trigger']}",
                    "source": "db",
                })
                seen_agencies.add(agency_name)
        # If we got DB results, return early (DB is authoritative when populated)
        if len(agencies) > 1:
            return agencies

    # Planning triggers
    planning_triggers = ["change_of_use", "new_construction", "demolition", "adu",
                         "adaptive_reuse", "historic", "restaurant"]
    if any(pt in project_types for pt in planning_triggers):
        agencies.append({"agency": "Planning", "required": True,
                         "reason": "Change of use, new construction, demolition, exterior changes, or historic resource"})

    # SFFD triggers
    fire_triggers = ["restaurant", "new_construction", "change_of_use", "historic"]
    if any(pt in project_types for pt in fire_triggers):
        agencies.append({"agency": "SFFD (Fire)", "required": True,
                         "reason": "Fire code review — restaurant hood/suppression, new construction, or occupancy change"})

    # DPH triggers (food service)
    if "restaurant" in project_types:
        agencies.append({"agency": "DPH (Public Health)", "required": True,
                         "reason": "Health permit for food service — parallel review with DBI. DPH must approve before permit issuance."})

    # MECH/MECH-E for commercial work
    if any(pt in project_types for pt in ["commercial_ti", "restaurant", "new_construction"]):
        agencies.append({"agency": "DBI Mechanical/Electrical", "required": True,
                         "reason": "HVAC, electrical, or commercial kitchen systems"})

    # PUC for new plumbing
    if any(pt in project_types for pt in ["restaurant", "adu", "new_construction"]):
        agencies.append({"agency": "SFPUC", "conditional": True,
                         "reason": "New plumbing fixtures or water service"})

    # BSM for exterior/ROW work
    if any(pt in project_types for pt in ["new_construction", "restaurant", "demolition"]):
        agencies.append({"agency": "DPW/BSM", "conditional": True,
                         "reason": "Work in or adjacent to public right-of-way"})

    return agencies


def _determine_special_requirements(project_types: list[str], estimated_cost: float | None, kb) -> list[dict]:
    """Determine special requirements based on project type and compliance knowledge."""
    reqs = []

    # --- Restaurant / food facility (enriched with G-25) ---
    if "restaurant" in project_types:
        # G-25 occupancy classification
        reqs.append({
            "requirement": "Occupancy classification (G-25)",
            "details": "Occupant load ≤50 = Group B (business). Occupant load >50 = Group A-2 (assembly) — triggers sprinklers, SFFD operational permit ($387), stricter egress and accessibility. Bars/lounges are always Group A-2.",
        })
        reqs.extend([
            {"requirement": "Planning zoning verification (G-25 Step 1)", "details": "Visit Planning FIRST — confirm restaurant use is permitted at site. CU hearing may be required depending on zoning district."},
            {"requirement": "DPH pre-application consultation (G-25 Step 2)", "details": "Contact DPH Environmental Health BEFORE design. Bring menu, floor plan concept, equipment list. DPH requirements heavily influence construction design."},
            {"requirement": "Separate permits required (G-25)", "details": "Building permit + SEPARATE plumbing permit (Cat 6PA $543 or 6PB $1,525) + SEPARATE electrical permit (Table 1A-E) + DPH health permit (separate application). SFFD operational permit if >50 occupants."},
            {"requirement": "DPH health permit application", "details": "Food preparation workflow diagram + equipment schedule"},
            {"requirement": "Type I hood fire suppression", "details": "Automatic suppression system for grease-producing equipment. Include hood data sheet with make, model, CFM, and duct sizing. UL 300 listed."},
            {"requirement": "Grease interceptor sizing", "details": "Grease trap calculations per CA Plumbing Code Table 7-3. Check SFPUC capacity charge — may require larger than code minimum."},
            {"requirement": "DPH menu submission", "details": "Full menu required — determines facility category and equipment requirements (DPH-007)"},
            {"requirement": "DPH equipment schedule", "details": "Numbered equipment schedule cross-referenced to layout — columns: Item#, Name, Manufacturer, Model, Dimensions, NSF cert, Gas/Elec, BTU/kW (Appendix C template)"},
            {"requirement": "DPH room finish schedule", "details": "Room-by-room finish schedule — floor, cove base, walls (lower/upper), ceiling per Appendix D template"},
            {"requirement": "DPH construction standards", "details": "Cove base 3/8\" radius, min 4\" height. Floors slip-resistant in cooking areas. 50fc lighting at food prep, 20fc at handwash. Physical samples may be required."},
        ])
        # HPWH for new construction restaurants (AB-112 all-electric)
        if "new_construction" in project_types:
            reqs.append({
                "requirement": "Heat Pump Water Heater (HPWH) sizing",
                "details": "SF all-electric mandate — HPWH required for new construction. Size for peak demand (1.5-2x gas equivalent). Booster heater needed for high-temp sanitizing dishwashers. HPWH must NOT be in food prep areas.",
            })

    # --- ADU ---
    if "adu" in project_types:
        reqs.extend([
            {"requirement": "ADU pre-approval application", "details": "Separate ADU application process for detached ADUs"},
            {"requirement": "Fire separation", "details": "Fire separation between ADU and primary dwelling"},
            {"requirement": "Separate utility connections", "details": "May need separate water/electric meters"},
        ])

    # --- Seismic (enriched with S-09 EBB) ---
    if "seismic" in project_types:
        reqs.extend([
            {"requirement": "Structural engineering report", "details": "Licensed structural engineer evaluation required for engineered designs. Exception: prescriptive CEBC A3 cripple wall bracing (EBB/S-09) does NOT require licensed professional (G-01 Status I exempt)."},
            {"requirement": "Priority processing eligibility", "details": "Voluntary/mandatory seismic upgrades per AB-004"},
        ])
        # S-09 EBB-specific guidance
        ebb = kb.earthquake_brace_bolt
        if ebb:
            reqs.append({
                "requirement": "Earthquake Brace+Bolt eligibility (S-09)",
                "details": "Pre-1979 wood-frame, cripple wall ≤4ft: qualifies for EBB program (up to $3K reimbursement). OTC-eligible with Form 8 if prescriptive per CEBC Appendix A3. Plans must show wall percentage calculations, anchor bolt schedule, and plywood nailing pattern.",
            })
        # DA-12 seismic accessibility for mixed-use
        ada = kb.ada_accessibility
        seismic_ada = ada.get("special_cases", {}).get("seismic_mitigation", {}) if ada else {}
        if seismic_ada.get("adjusted_cost_formula"):
            reqs.append({
                "requirement": "Seismic accessibility — mixed-use adjusted cost (DA-12)",
                "details": "Mixed-use buildings: path-of-travel obligation applies ONLY to commercial portion. Adjusted cost = (% commercial floor area) × total construction cost. 20% of adjusted cost = max accessibility spend. Residential portions exempt from Chapter 11B.",
            })

    # --- Historic ---
    if "historic" in project_types:
        reqs.extend([
            {"requirement": "Historic preservation review", "details": "Certificate of Appropriateness from HPC (Article 10) or Permit to Alter (Article 11)"},
            {"requirement": "Secretary of Interior Standards", "details": "All work must comply with SOI Standards for Treatment of Historic Properties"},
        ])

    # --- Change of use (enriched with DA-13) ---
    if "change_of_use" in project_types:
        reqs.extend([
            {"requirement": "Section 311 notification", "details": "30-day neighborhood notification period (cannot go OTC during notification)"},
            {"requirement": "Change of use = alteration for accessibility (DA-13)", "details": "Entire changed-use area must comply with current CBC 11B. If COU involves construction: 20%/threshold rules apply to actual construction cost. If COU is paperwork only ($1 permit): 20% of $1 = negligible accessibility spend."},
        ])

    # --- New construction ---
    if "new_construction" in project_types:
        reqs.extend([
            {"requirement": "Fire flow study", "details": "SFFD fire flow analysis for new construction"},
            {"requirement": "Stormwater management plan", "details": "Required if 5,000+ sq ft impervious surfaces"},
            {"requirement": "Geotechnical report", "details": "May be required depending on site conditions"},
            {"requirement": "SF All-Electric Requirement (AB-112)", "details": "New construction must be all-electric — no gas infrastructure. Title-24 docs cannot show gas consumption."},
        ])

    # --- ADA / Accessibility (commercial projects) ---
    is_commercial = any(pt in project_types for pt in [
        "restaurant", "commercial_ti", "change_of_use", "adaptive_reuse",
    ])
    if is_commercial:
        ada = kb.ada_accessibility
        threshold = ada.get("valuation_threshold", {}).get("current_amount", 203611)
        if estimated_cost and estimated_cost > threshold:
            reqs.append({
                "requirement": "ADA full path-of-travel compliance",
                "details": f"Construction cost ${estimated_cost:,.0f} exceeds threshold ${threshold:,.0f} — FULL CBC 11B compliance required",
            })
        elif estimated_cost:
            pct20 = estimated_cost * 0.20
            reqs.append({
                "requirement": "ADA path-of-travel (20% rule)",
                "details": f"Construction cost ${estimated_cost:,.0f} below threshold ${threshold:,.0f} — accessibility upgrades limited to 20% (${pct20:,.0f})",
            })
        else:
            reqs.append({
                "requirement": "ADA path-of-travel compliance",
                "details": f"Commercial alteration triggers CBC 11B. Threshold for full compliance: ${threshold:,.0f}. Provide cost estimate to determine scope.",
            })
        reqs.append({
            "requirement": "DA-02 Checklist required",
            "details": "Disabled Access Upgrade Compliance Checklist Package required for all commercial alterations",
        })

    # --- G-01 Plan Signature Requirements ---
    sigs = kb.plan_signatures
    if sigs:
        if "new_construction" in project_types:
            reqs.append({
                "requirement": "CA-licensed architect or engineer required (G-01 Status III)",
                "details": "New construction requires plans signed and sealed by CA-licensed civil engineer or architect. First sheet: original signature + seal + registration number + sheet index.",
            })
        elif "restaurant" in project_types:
            reqs.append({
                "requirement": "CA-licensed architect or engineer likely required (G-01)",
                "details": "Restaurant construction involves structural, mechanical, and fire suppression systems — typically requires licensed professional (G-01 Status III/IV). Sprinkler and hood suppression designs require SFFD-qualified professionals.",
            })
        elif any(pt in project_types for pt in ["seismic", "adaptive_reuse"]):
            reqs.append({
                "requirement": "CA-licensed structural engineer required (G-01 Status III)",
                "details": "Structural work requires licensed SE or CE. Seismic retrofit, wall removal, and structural alterations must be designed by State-licensed professional.",
            })
        elif "commercial_ti" in project_types:
            reqs.append({
                "requirement": "Plan signature — verify G-01 Status I exempt or Status III required",
                "details": "Non-highrise single-floor TI ≤$400,000 with non-structural scope may qualify for exempt status (G-01). Otherwise CA-licensed architect or engineer required.",
            })
        elif "general_alteration" in project_types:
            if estimated_cost and estimated_cost <= 150000:
                reqs.append({
                    "requirement": "Plans may qualify for G-01 exempt status",
                    "details": "Dwelling unit improvements ≤$150,000 for non-structural work (window replacement, kitchen/bath remodel, non-structural remodeling) may be prepared by unlicensed designer.",
                })

    # --- Title-24 Energy Compliance ---
    # Almost all projects trigger some form of Title-24
    non_t24_types = {"demolition"}
    if not non_t24_types.intersection(project_types):
        t24 = kb.title24
        is_multifamily = "low_rise_multifamily" in project_types
        if "new_construction" in project_types:
            if is_commercial:
                reqs.append({
                    "requirement": "Title-24 energy compliance (nonresidential new construction)",
                    "details": "NRCC at filing. NRCI sub-forms at inspection (ENV-E, MCH-E, LTI-E, PLB-E per M-04 checklist). NRCA acceptance tests required. AB-112 all-electric form (AEC1). AB-093 green building form (GBC1).",
                })
            elif is_multifamily:
                reqs.append({
                    "requirement": "Title-24 energy compliance (low-rise multifamily new construction)",
                    "details": "LMCC at filing (per M-08 checklist). LMCI per dwelling unit type at inspection. LMCV HERS verification per individual unit (not sampled). Solar PV sized by number of units (LMCI-PVB-01). Mixed-use: LMCC for residential + NRCC for commercial portions.",
                })
            else:
                reqs.append({
                    "requirement": "Title-24 energy compliance (residential new construction)",
                    "details": "CF1R at filing (per M-03 checklist). CF2R at inspection. Solar PV required (CF2R-PVB-01). Battery storage may apply (CF2R-PVB-02). HERS verification if performance approach or duct work >25ft.",
                })
        elif any(pt in project_types for pt in ["restaurant", "commercial_ti", "adaptive_reuse", "change_of_use"]):
            reqs.append({
                "requirement": "Title-24 energy compliance (nonresidential alteration)",
                "details": "NRCC required if altering HVAC, lighting, or envelope. NRCI sub-forms at inspection per DBI M-04 checklist. NRCA acceptance testing for systems >54,000 BTU/hr (MCH-04-A economizer, LTI-02-A daylighting, etc.).",
            })
        else:
            reqs.append({
                "requirement": "Title-24 energy compliance",
                "details": "CF1R or NRCC likely required depending on scope. #1 correction trigger — submit with initial application.",
            })

        # M-06 Final Compliance Affidavit — applies to ALL projects with Title-24
        affidavit = t24.get("sf_specific_rules", {}).get("final_compliance_affidavit", {})
        if affidavit:
            reqs.append({
                "requirement": "Title-24 Final Compliance Affidavit (M-06)",
                "details": "Prior to final inspection, email affidavit to dbi.energyinspections@sfgov.org. Must list all certificate form codes. Allow 10 business days for review. HERS items require certified HERS Rater; NRCA items require certified ATT.",
            })

    return reqs


async def predict_permits(
    project_description: str,
    address: str | None = None,
    estimated_cost: float | None = None,
    square_footage: float | None = None,
    scope_keywords: list[str] | None = None,
) -> str:
    """Predict required permits, forms, review path, and agency routing for a project.

    Walks the SF permit decision tree based on project description to predict:
    - Required permit types and forms
    - OTC vs in-house review path
    - Which city agencies must review
    - Special requirements and triggers
    - Confidence levels for each prediction

    Args:
        project_description: Natural language description of the project
        address: Optional street address for property context
        estimated_cost: Optional construction cost estimate
        square_footage: Optional project area in square feet
        scope_keywords: Optional explicit project type keywords to override auto-extraction

    Returns:
        Formatted prediction with permits, routing, requirements, and confidence.
    """
    kb = get_knowledge_base()

    # Extract project types from description
    project_types = _extract_project_types(project_description, scope_keywords)

    # Also match semantic index concepts for richer context
    concepts = kb.match_concepts(project_description)

    # A1: Query ref_permit_forms from DB (fall back to hardcoded if empty/fails)
    db_form = _query_ref_permit_forms(project_types)

    # A2: Query ref_agency_triggers from DB (fall back to hardcoded if empty/fails)
    db_triggers = _query_ref_agency_triggers(project_types)

    # Walk decision tree (DB data supplements/overrides hardcoded when available)
    form = _determine_form(project_types, kb, db_form=db_form)
    review_path = _determine_review_path(project_types, estimated_cost, kb)
    agency_routing = _determine_agency_routing(project_types, kb, db_triggers=db_triggers)
    special_requirements = _determine_special_requirements(project_types, estimated_cost, kb)

    # Database-backed zoning routing (supplements knowledge base)
    zoning_info = None
    historic_district_flag = False
    if address:
        try:
            from src.db import get_connection, BACKEND
            conn = get_connection()
            try:
                _ph = "%s" if BACKEND == "postgres" else "?"
                # Parse address into street number + name
                addr_parts = address.strip().split()
                street_num = addr_parts[0] if addr_parts else None
                street_name_part = addr_parts[1] if len(addr_parts) > 1 else None

                if street_num and street_name_part:
                    if BACKEND == "postgres":
                        with conn.cursor() as cur:
                            cur.execute(
                                f"SELECT block, lot FROM permits"
                                f" WHERE street_number = {_ph}"
                                f"   AND UPPER(street_name) LIKE UPPER({_ph})"
                                f" LIMIT 1",
                                [street_num, f"%{street_name_part}%"],
                            )
                            bl = cur.fetchone()
                            if bl:
                                cur.execute(
                                    f"SELECT zoning_code FROM tax_rolls"
                                    f" WHERE block = {_ph} AND lot = {_ph}"
                                    f" ORDER BY tax_year DESC LIMIT 1",
                                    [bl[0], bl[1]],
                                )
                                zr = cur.fetchone()
                                if zr:
                                    # A3: include historic_district flag
                                    cur.execute(
                                        f"SELECT zoning_code, zoning_category,"
                                        f"       planning_review_required,"
                                        f"       fire_review_required,"
                                        f"       health_review_required,"
                                        f"       historic_district"
                                        f" FROM ref_zoning_routing"
                                        f" WHERE zoning_code = {_ph}",
                                        [zr[0]],
                                    )
                                    zoning_info = cur.fetchone()
                    else:
                        bl = conn.execute(
                            f"SELECT block, lot FROM permits"
                            f" WHERE street_number = {_ph}"
                            f"   AND UPPER(street_name) LIKE UPPER({_ph})"
                            f" LIMIT 1",
                            [street_num, f"%{street_name_part}%"],
                        ).fetchone()
                        if bl:
                            zr = conn.execute(
                                f"SELECT zoning_code FROM tax_rolls"
                                f" WHERE block = {_ph} AND lot = {_ph}"
                                f" ORDER BY tax_year DESC LIMIT 1",
                                [bl[0], bl[1]],
                            ).fetchone()
                            if zr:
                                # A3: include historic_district flag
                                zoning_info = conn.execute(
                                    f"SELECT zoning_code, zoning_category,"
                                    f"       planning_review_required,"
                                    f"       fire_review_required,"
                                    f"       health_review_required,"
                                    f"       historic_district"
                                    f" FROM ref_zoning_routing"
                                    f" WHERE zoning_code = {_ph}",
                                    [zr[0]],
                                ).fetchone()
            finally:
                conn.close()
        except Exception:
            pass  # Graceful fallback — zoning_info stays None

    # A3: Extract historic_district flag from zoning info if available
    if zoning_info and len(zoning_info) >= 6:
        historic_district_flag = bool(zoning_info[5])

    # Build result
    result = {
        "project_description": project_description,
        "detected_project_types": project_types,
        "matched_concepts": concepts[:10],
        "permits_needed": {
            "building_permit": True,
            "form": form,
            "electrical_permit": any(pt in project_types for pt in ["restaurant", "commercial_ti", "new_construction", "adu"]),
            "plumbing_permit": any(pt in project_types for pt in ["restaurant", "adu", "new_construction"]),
            "planning_approval": "Planning" in [a["agency"] for a in agency_routing],
        },
        "review_path": review_path,
        "agency_routing": agency_routing,
        "special_requirements": special_requirements,
        "confidence_summary": {
            "overall": review_path.get("confidence", "medium"),
            "form_selection": kb.get_step_confidence(2),
            "review_path": kb.get_step_confidence(3),
            "agency_routing": kb.get_step_confidence(4),
            "documents": kb.get_step_confidence(5),
        },
        "gaps": [],
    }

    # Note any gaps
    if not estimated_cost:
        result["gaps"].append("No cost estimate provided — OTC eligibility and fee estimates less accurate")
    if not address:
        result["gaps"].append("No address provided — cannot check zoning, historic status, or neighborhood-specific rules")
    if "general_alteration" in project_types:
        result["gaps"].append("Could not classify specific project type — predictions are generalized")

    # Format output
    lines = ["# Permit Prediction\n"]
    lines.append(f"**Project:** {project_description}")
    if address:
        lines.append(f"**Address:** {address}")
    if estimated_cost:
        lines.append(f"**Estimated Cost:** ${estimated_cost:,.0f}")
    if square_footage:
        lines.append(f"**Square Footage:** {square_footage:,.0f}")
    lines.append(f"\n**Detected Project Types:** {', '.join(project_types)}")
    if concepts:
        lines.append(f"**Matched Concepts:** {', '.join(concepts[:10])}")

    lines.append(f"\n## Permit Form\n")
    lines.append(f"**Form:** {form['form']}")
    lines.append(f"**Reason:** {form['reason']}")
    lines.append(f"**Notes:** {form['notes']}")

    lines.append(f"\n## Review Path\n")
    lines.append(f"**Path:** {review_path['path']}")
    lines.append(f"**Reason:** {review_path['reason']}")
    lines.append(f"**Confidence:** {review_path['confidence']}")

    lines.append(f"\n## Agency Routing\n")
    for a in agency_routing:
        status = "Required" if a.get("required") else "Conditional"
        lines.append(f"- **{a['agency']}** ({status}): {a['reason']}")

    # Zoning context (from database lookup)
    if zoning_info:
        # A3: unpack 6-column result (added historic_district)
        if len(zoning_info) >= 6:
            zoning_code, zoning_category, planning_req, fire_req, health_req, historic_dist = zoning_info
        else:
            zoning_code, zoning_category, planning_req, fire_req, health_req = zoning_info
            historic_dist = False
        lines.append(f"\n## Zoning Context\n")
        lines.append(f"*Resolved from local tax records and reference tables.*\n")
        if zoning_code:
            lines.append(f"- **Zoning Code:** {zoning_code}")
        if zoning_category:
            lines.append(f"- **Category:** {zoning_category}")
        if planning_req:
            lines.append(f"- **Planning Review:** Required (confirmed by zoning code)")
        if fire_req:
            lines.append(f"- **Fire Review:** Required (confirmed by zoning code)")
        if health_req:
            lines.append(f"- **Health Review:** Required (confirmed by zoning code)")
        if historic_dist:
            lines.append(f"- **Historic District:** Yes — all exterior work triggers Planning Preservation review (Article 10/11)")

    if special_requirements:
        lines.append(f"\n## Special Requirements\n")
        for r in special_requirements:
            lines.append(f"- **{r['requirement']}:** {r['details']}")

    lines.append(f"\n## Confidence Summary\n")
    for k, v in result["confidence_summary"].items():
        lines.append(f"- {k}: {v}")

    if result["gaps"]:
        lines.append(f"\n## Gaps / Caveats\n")
        for g in result["gaps"]:
            lines.append(f"- {g}")

    # Build source citations based on which knowledge was used
    sources = ["decision_tree", "otc_criteria", "forms_taxonomy", "routing_matrix"]
    if "restaurant" in project_types:
        sources.extend(["restaurant_guide", "dph_food", "fire_code"])
    if "seismic" in project_types:
        sources.append("earthquake_brace_bolt")
    if any(pt in project_types for pt in ["restaurant", "commercial_ti", "change_of_use", "adaptive_reuse"]):
        sources.append("ada_accessibility")
    if kb.plan_signatures:
        sources.append("plan_signatures")
    if not {"demolition"}.intersection(project_types):
        sources.append("title24")
    if any(pt in project_types for pt in ["change_of_use", "new_construction", "demolition", "adu", "historic", "restaurant"]):
        sources.append("planning_code")
    lines.append(format_sources(sources))

    return "\n".join(lines)
