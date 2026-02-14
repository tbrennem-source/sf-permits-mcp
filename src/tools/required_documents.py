"""Tool: required_documents — Generate document checklist for permit submission."""

from src.tools.knowledge_base import get_knowledge_base

# Base documents by form type
BASE_DOCUMENTS = {
    "Form 1/2": [
        "Building Permit Application (Form 1/2)",
        "Construction plans (PDF for EPR)",
        "Permit Applicant Disclosure and Certification form",
        "Licensed Contractor's Statement Form",
        "Title 24 Energy compliance forms",
        "San Francisco Green Building form (GS1-GS6)",
        "Site survey / plot plan",
        "Construction cost estimate worksheet",
    ],
    "Form 3/8": [
        "Building Permit Application (Form 3/8)",
        "Construction plans (PDF for EPR)",
        "Permit Applicant Disclosure and Certification form",
        "Title 24 Energy compliance forms",
        "San Francisco Green Building form (GS1-GS6)",
        "Construction cost estimate worksheet",
    ],
    "Form 6": [
        "Demolition Permit Application (Form 6)",
        "Asbestos report (required BEFORE application)",
        "Demolition Affidavit Form",
        "BAAQMD Job Number",
        "Permit Applicant Disclosure and Certification form",
    ],
    "Form 4/7": [
        "Sign Permit Application (Form 4/7)",
        "Sign drawings with dimensions",
        "Site photos showing proposed location",
    ],
}

# Agency-specific documents
AGENCY_DOCUMENTS = {
    "Planning": [
        "Planning Department approval letter (obtain BEFORE building permit submission)",
        "Section 311 notification materials (if neighborhood notification required)",
    ],
    "DPH (Public Health)": [
        "DPH Health permit application",
        "Floor plan showing entire facility drawn to scale (DPH-001)",
        "Equipment layout with numbered equipment schedule — cross-referenced (DPH-002)",
        "Complete plumbing layout with grease interceptor location and sizing (DPH-003)",
        "Exhaust ventilation layout with hood data sheets and calculations (DPH-004)",
        "Complete finish schedule — floors, cove base, walls, ceilings by area (DPH-005)",
        "Electrical/lighting layout with foot-candle calculations (DPH-006)",
        "Complete menu including alcohol service (DPH-007)",
    ],
    "SFFD (Fire)": [
        "Fire suppression system plans",
        "Occupancy load calculations",
        "Fire flow study (new construction)",
    ],
    "SFPUC": [
        "SFPUC fixture count form",
        "Stormwater Management Plan (if 5,000+ sq ft impervious surfaces)",
    ],
    "DPW/BSM": [
        "Street space permit application",
        "Public right-of-way plans",
    ],
}

# Trigger-specific documents
TRIGGER_DOCUMENTS = {
    "change_of_use": [
        "Use change justification letter",
        "Existing and proposed occupancy documentation",
    ],
    "restaurant": [
        "Grease interceptor sizing calculations",
        "Kitchen layout with equipment schedule",
        "Type I hood specifications and fire suppression details",
        "Ventilation calculations for commercial kitchen",
        "DPH Health permit application",
    ],
    "adu": [
        "ADU pre-approval application (for detached ADUs)",
        "Fire separation details between ADU and primary dwelling",
        "Utility connection plans (separate meter requirements)",
    ],
    "seismic": [
        "Structural engineering report by licensed SE",
        "Geotechnical investigation (if required by site conditions)",
        "Seismic retrofit design drawings",
    ],
    "historic": [
        "Secretary of Interior Standards compliance documentation",
        "Historic resource evaluation",
        "Certificate of Appropriateness application (Article 10) or Permit to Alter (Article 11)",
    ],
    "new_construction": [
        "Geotechnical report",
        "Fire flow study",
        "Stormwater Management Plan",
        "Acoustical report (residential buildings)",
        "Construction Waste Management tracking setup",
    ],
    "demolition": [
        "Asbestos report (required BEFORE application)",
        "Demolition Affidavit Form",
        "BAAQMD Job Number",
        "300-foot notification letters",
    ],
    "ada": [
        "DA-02 Disabled Access Upgrade Compliance Checklist Package",
        "ADA path-of-travel documentation showing route from primary entrance to area of alteration",
        "Existing conditions survey with door widths, clearances, slopes, restroom dimensions",
        "Restroom upgrade plans per CBC Chapter 11B",
    ],
    "commercial_ti": [
        "DA-02 Disabled Access Upgrade Compliance Checklist Package (required for ALL commercial alterations)",
        "ADA path-of-travel documentation",
        "NRCC energy compliance (if altering HVAC or lighting)",
    ],
}


def _compliance_documents(all_triggers: list[str], project_type: str | None, kb) -> list[str]:
    """Generate compliance-specific documents from Title-24, DPH, and ADA knowledge."""
    docs = []

    # Title-24 energy forms — #1 correction category
    t24 = kb.title24
    if t24 and "demolition" not in all_triggers:
        is_nonres = project_type in ("restaurant", "commercial_ti", "adaptive_reuse") or \
                    "change_of_use" in all_triggers
        is_multifamily = project_type == "low_rise_multifamily" or "low_rise_multifamily" in all_triggers
        if "new_construction" in all_triggers:
            if is_nonres:
                docs.append("NRCC — Nonresidential Certificate of Compliance (at filing)")
                docs.append("NRCI sub-forms at inspection: ENV-E (envelope), MCH-E (mechanical), LTI-E (lighting), PLB-E (plumbing)")
                docs.append("NRCA acceptance tests at inspection: MCH-04-A (economizer), LTI-02-A (daylighting controls), etc.")
                docs.append("AB-112 All-Electric compliance form (AEC1) — required for SF new construction")
                docs.append("AB-093 Green Building form (GBC1) — Attachment E")
            elif is_multifamily:
                docs.append("LMCC — Low-Rise Multifamily Certificate of Compliance (at filing, per M-08 checklist)")
                docs.append("LMCI at inspection per dwelling unit type (LMCI-PVB-01 solar PV required)")
                docs.append("LMCV HERS verification per individual dwelling unit (not sampled)")
                docs.append("AB-112 All-Electric compliance form (AEC1) — required for SF new construction")
                docs.append("AB-093 Green Building form (GBC1) — Attachment E")
            else:
                docs.append("CF1R — Residential Certificate of Compliance (at filing, per M-03 checklist)")
                docs.append("CF2R-PVB-01 — Solar PV certificate (at inspection)")
                docs.append("CF2R-ELC-01 — Electric ready requirements (heat pump readiness)")
        elif is_nonres:
            docs.append("NRCC — Nonresidential Certificate of Compliance (if altering HVAC, lighting, or envelope)")
            docs.append("NRCI/NRCA sub-forms at inspection — specific forms depend on scope (see M-04 checklist)")
        elif is_multifamily:
            docs.append("LMCC — Low-Rise Multifamily Certificate of Compliance (if altering energy systems, per M-08)")
            docs.append("LMCI at inspection for altered unit types")
        else:
            docs.append("CF1R — Residential Certificate of Compliance (for alterations touching energy systems, per M-03)")
        # Existing conditions verification for alterations
        if "new_construction" not in all_triggers:
            docs.append("Existing conditions documentation for Title-24 baseline (T24-C02 — #1 alteration correction)")

    # ADA/DA-02 — add form section guidance for commercial
    ada = kb.ada_accessibility
    if ada:
        is_commercial = project_type in ("restaurant", "commercial_ti", "change_of_use", "adaptive_reuse") or \
                        bool({"restaurant", "commercial_ti", "change_of_use", "adaptive_reuse"}.intersection(all_triggers))
        if is_commercial:
            da02 = ada.get("da02_form_structure", {})
            if da02:
                docs.append("DA-02 Form A: Building description (use, occupancy, total SF, alteration SF, year built)")
                docs.append("DA-02 Form B: Compliance path selection (full compliance vs 20% disproportionate cost)")
                docs.append("DA-02 Form C: CBC 11B checklist — entrance, restrooms, signage, counters, path of travel")

    # DPH documents — only if restaurant is a trigger
    if project_type == "restaurant" or "restaurant" in all_triggers:
        dph = kb.dph_food
        if dph:
            docs.append("DPH: Three-compartment sink or commercial dishwasher specification (DPH-011)")
            docs.append("DPH: Grease interceptor sizing per CA Plumbing Code Table 7-3 (DPH-012)")
            docs.append("DPH: Handwashing station locations and specifications (DPH-010)")
            # Construction standards from PDF guide
            construction = dph.get("construction_standards", {})
            if construction:
                docs.append("DPH: Finish schedule with approved materials — cove base min 4\" height, 3/8\" radius (DPH-005)")
                docs.append("DPH: Lighting plan with foot-candle calcs — 50fc food prep, 20fc handwash, 10fc storage (DPH-006)")
            # Equipment schedule template (Appendix C) — #1 DPH correction
            equip_tmpl = dph.get("equipment_schedule_template", {})
            if equip_tmpl:
                cols = [c["column"] for c in equip_tmpl.get("required_columns", [])[:4]]
                docs.append(f"DPH: Equipment schedule with columns: {', '.join(cols)} + NSF cert, Gas/Elec, BTU/kW (Appendix C)")
            # Room finish schedule template (Appendix D)
            finish_tmpl = dph.get("room_finish_schedule_template", {})
            if finish_tmpl:
                docs.append("DPH: Room finish schedule — room-by-room: floor, cove base, walls (lower/upper), ceiling (Appendix D)")
            # HPWH requirements for new construction restaurants
            hpwh = dph.get("hpwh_food_facility_requirements", {})
            if hpwh and "new_construction" in all_triggers:
                docs.append("DPH: HPWH sizing calculation — first-hour rating, recovery rate, booster heater spec if high-temp sanitizing")

    return docs


async def required_documents(
    permit_forms: list[str],
    review_path: str,
    agency_routing: list[str] | None = None,
    project_type: str | None = None,
    triggers: list[str] | None = None,
) -> str:
    """Generate a document checklist for permit submission.

    Assembles required documents based on permit form, review path,
    agency routing, and project-specific triggers.

    Args:
        permit_forms: Required forms (e.g., ['Form 3/8'])
        review_path: 'otc' or 'in_house'
        agency_routing: Agencies reviewing (e.g., ['Planning', 'SFFD (Fire)', 'DPH (Public Health)'])
        project_type: Specific type (e.g., 'restaurant', 'adu', 'seismic')
        triggers: Additional triggers (e.g., ['change_of_use', 'ada', 'historic'])

    Returns:
        Formatted document checklist with categories and EPR requirements.
    """
    kb = get_knowledge_base()

    # 1. Base documents
    initial_docs = []
    for form in permit_forms:
        docs = BASE_DOCUMENTS.get(form, BASE_DOCUMENTS.get("Form 3/8", []))
        initial_docs.extend(docs)

    # Deduplicate
    initial_docs = list(dict.fromkeys(initial_docs))

    # 2. Agency-specific documents
    agency_docs = []
    if agency_routing:
        for agency in agency_routing:
            docs = AGENCY_DOCUMENTS.get(agency, [])
            agency_docs.extend(docs)

    # 3. Trigger-specific documents
    trigger_docs = []
    all_triggers = list(triggers or [])
    if project_type:
        all_triggers.append(project_type)

    # Commercial projects always need disabled access (DA-02)
    commercial_types = {"commercial_ti", "restaurant", "change_of_use", "adaptive_reuse"}
    is_commercial = project_type in commercial_types or bool(commercial_types.intersection(all_triggers))
    if is_commercial and "ada" not in all_triggers and "commercial_ti" not in all_triggers:
        all_triggers.append("ada")

    for trigger in all_triggers:
        docs = TRIGGER_DOCUMENTS.get(trigger, [])
        trigger_docs.extend(docs)

    # Knowledge-driven documents from Title-24, DPH, ADA
    compliance_docs = _compliance_documents(all_triggers, project_type, kb)
    trigger_docs.extend(compliance_docs)

    # Deduplicate
    agency_docs = list(dict.fromkeys(agency_docs))
    trigger_docs = list(dict.fromkeys(trigger_docs))

    # 4. EPR requirements
    epr = kb.epr_requirements
    epr_reqs = epr.get("format_requirements", {}).get("requirements", [])
    epr_checks = epr.get("pre_submission_checks", [])

    # 5. Pro tips
    pro_tips = []
    if review_path == "in_house":
        pro_tips.append("Obtain Planning approval BEFORE submitting building permit application")
        pro_tips.append("Expect 3 rounds of completeness review — 3rd round escalates to supervisor")
        pro_tips.append("Include a Back Check page in all plan sets")
    if review_path == "otc":
        pro_tips.append("All plans reviewed at counter in ~1 hour per station")
        pro_tips.append("Have licensed professional available by phone during OTC review")
    if project_type == "restaurant":
        pro_tips.append("Visit Planning FIRST to confirm restaurant use is permitted at your site")
        pro_tips.append("Separate electrical and plumbing permits needed after building permit")
    if "historic" in all_triggers:
        pro_tips.append("HPC review happens BEFORE any other Planning approval — start early")

    # Format output
    lines = ["# Required Documents Checklist\n"]
    lines.append(f"**Forms:** {', '.join(permit_forms)}")
    lines.append(f"**Review Path:** {review_path}")
    if project_type:
        lines.append(f"**Project Type:** {project_type}")

    lines.append(f"\n## Initial Filing Documents\n")
    for i, doc in enumerate(initial_docs, 1):
        lines.append(f"{i}. [ ] {doc}")

    if agency_docs:
        lines.append(f"\n## Agency-Specific Documents\n")
        for i, doc in enumerate(agency_docs, 1):
            lines.append(f"{i}. [ ] {doc}")

    if trigger_docs:
        lines.append(f"\n## Project-Specific Requirements\n")
        for i, doc in enumerate(trigger_docs, 1):
            lines.append(f"{i}. [ ] {doc}")

    lines.append(f"\n## Electronic Plan Review (EPR) Requirements\n")
    lines.append("*All plans must be submitted electronically as of January 1, 2024*\n")
    for req in epr_reqs:
        lines.append(f"- {req.get('requirement', '')}: {req.get('details', '')}")

    if epr_checks:
        lines.append(f"\n## Pre-Submission Checklist\n")
        for check in epr_checks:
            lines.append(f"- [ ] {check}")

    # EPR correction/resubmittal workflow — critical for in-house review
    if review_path == "in_house":
        correction_workflow = epr.get("correction_response_workflow", {})
        if correction_workflow:
            lines.append(f"\n## Plan Check Correction Response Workflow\n")
            lines.append("*When corrections are required, follow this sequence:*\n")
            for step in correction_workflow.get("steps", []):
                lines.append(f"- **{step.get('id', '')}:** {step.get('step', '')} — {step.get('detail', '')}")
            addenda = correction_workflow.get("addenda_vs_corrections", {})
            if addenda:
                lines.append(f"\n**Corrections vs Addenda:**")
                lines.append(f"- *Correction:* {addenda.get('correction', '')}")
                lines.append(f"- *Addendum:* {addenda.get('addendum', '')}")

        # Review statuses
        statuses = epr.get("review_statuses", {}).get("statuses", [])
        if statuses:
            lines.append(f"\n## Review Status Guide\n")
            for s in statuses:
                lines.append(f"- **{s.get('status', '')}:** {s.get('meaning', '')} → {s.get('action', '')}")

    # Document type numbering
    doc_numbering = epr.get("document_type_numbering", {})
    if doc_numbering:
        lines.append(f"\n## File Naming Convention\n")
        lines.append(f"Format: `{doc_numbering.get('naming_format', '')}`\n")
        for prefix in doc_numbering.get("prefixes", []):
            lines.append(f"- `{prefix.get('prefix', '')}` {prefix.get('type', '')} (e.g., `{prefix.get('example', '')}`)")

    # Sheet numbering convention from Exhibit F
    exhibit_f = epr.get("exhibit_f_supplementary", {})
    sheet_numbering = exhibit_f.get("sheet_numbering_convention", {})
    if sheet_numbering:
        lines.append(f"\n## Sheet Numbering Convention\n")
        for sp in sheet_numbering.get("prefixes", []):
            lines.append(f"- `{sp.get('prefix', '')}` — {sp.get('discipline', '')}")

    if pro_tips:
        lines.append(f"\n## Pro Tips\n")
        for tip in pro_tips:
            lines.append(f"- {tip}")

    confidence = kb.get_step_confidence(5)
    lines.append(f"\n**Confidence:** {confidence}")

    return "\n".join(lines)
