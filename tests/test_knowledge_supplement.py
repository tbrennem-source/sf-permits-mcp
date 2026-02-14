"""Tests for Phase 2.6/2.75 knowledge supplement integration (Title-24, DPH, ADA, EPR)."""

import pytest
from src.tools.knowledge_base import get_knowledge_base
from src.tools.predict_permits import predict_permits, _extract_project_types
from src.tools.required_documents import required_documents
from src.tools.estimate_fees import estimate_fees
from src.tools.revision_risk import _get_correction_frequencies


# --- KnowledgeBase loading ---

def test_knowledge_base_loads_title24():
    kb = get_knowledge_base()
    assert kb.title24
    assert kb.title24.get("sf_climate_zone") == 3
    assert "form_system" in kb.title24
    assert "residential" in kb.title24["form_system"]
    assert "nonresidential" in kb.title24["form_system"]


def test_knowledge_base_loads_dph():
    kb = get_knowledge_base()
    assert kb.dph_food
    assert "plan_submittal_requirements" in kb.dph_food
    general = kb.dph_food["plan_submittal_requirements"]["general"]
    assert len(general) == 7  # DPH-001 through DPH-007


def test_knowledge_base_loads_ada():
    kb = get_knowledge_base()
    assert kb.ada_accessibility
    threshold = kb.ada_accessibility.get("valuation_threshold", {})
    assert threshold.get("current_amount") == 203611.0
    assert "core_logic" in kb.ada_accessibility
    assert "cost_tiers" in kb.ada_accessibility["core_logic"]


def test_title24_common_corrections():
    kb = get_knowledge_base()
    corrections = kb.title24.get("common_corrections", [])
    assert len(corrections) == 6
    ids = [c["id"] for c in corrections]
    assert "T24-C01" in ids
    assert "T24-C04" in ids  # All-electric


def test_ada_common_corrections():
    kb = get_knowledge_base()
    corrections = kb.ada_accessibility.get("common_corrections", [])
    assert len(corrections) == 8
    ids = [c["id"] for c in corrections]
    assert "ADA-C01" in ids  # Missing DA-02
    assert "ADA-C07" in ids  # Cost threshold calculation


def test_dph_specific_systems():
    kb = get_knowledge_base()
    systems = kb.dph_food["plan_submittal_requirements"]["specific_systems"]
    assert "handwashing" in systems
    assert "grease_interceptor" in systems
    assert "ventilation" in systems
    assert systems["grease_interceptor"]["id"] == "DPH-012"


# --- predict_permits: all-electric, ADA threshold, DPH ---

@pytest.mark.asyncio
async def test_predict_new_construction_all_electric():
    result = await predict_permits(
        project_description="New construction 3-story mixed-use building, ground floor retail, residential above",
        estimated_cost=5000000,
    )
    assert "All-Electric" in result or "AB-112" in result or "all-electric" in result


@pytest.mark.asyncio
async def test_predict_restaurant_dph_details():
    result = await predict_permits(
        project_description="Convert retail to full-service restaurant with commercial kitchen",
        estimated_cost=300000,
    )
    assert "DPH" in result
    assert "menu" in result.lower() or "equipment schedule" in result.lower()


@pytest.mark.asyncio
async def test_predict_commercial_ti_ada_above_threshold():
    result = await predict_permits(
        project_description="Office tenant improvement, new HVAC and lighting",
        estimated_cost=250000,  # Above $203,611 threshold
    )
    assert "FULL" in result or "full" in result
    assert "DA-02" in result


@pytest.mark.asyncio
async def test_predict_commercial_ti_ada_below_threshold():
    result = await predict_permits(
        project_description="Office tenant improvement, minor alterations",
        estimated_cost=100000,  # Below $203,611 threshold
    )
    assert "20%" in result
    assert "DA-02" in result


@pytest.mark.asyncio
async def test_predict_title24_for_alterations():
    result = await predict_permits(
        project_description="Residential kitchen remodel with HVAC changes",
        estimated_cost=85000,
    )
    assert "Title-24" in result or "CF1R" in result or "energy" in result.lower()


# --- required_documents: Title-24, DPH, DA-02 ---

@pytest.mark.asyncio
async def test_required_docs_restaurant_has_dph_items():
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        agency_routing=["Planning", "DPH (Public Health)", "SFFD (Fire)"],
        project_type="restaurant",
        triggers=["change_of_use"],
    )
    assert "DPH-001" in result or "floor plan" in result.lower()
    assert "DPH-002" in result or "equipment schedule" in result.lower()
    assert "menu" in result.lower()
    assert "DPH-012" in result or "grease interceptor" in result.lower()


@pytest.mark.asyncio
async def test_required_docs_commercial_gets_da02():
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "DA-02" in result


@pytest.mark.asyncio
async def test_required_docs_has_title24_forms():
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "NRCC" in result or "Title 24" in result


@pytest.mark.asyncio
async def test_required_docs_new_construction_has_nrcc():
    result = await required_documents(
        permit_forms=["Form 1/2"],
        review_path="in_house",
        triggers=["new_construction"],
    )
    # New construction should have energy compliance form
    assert "NRCC" in result or "CF1R" in result or "Title 24" in result


@pytest.mark.asyncio
async def test_required_docs_existing_conditions_for_alterations():
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="restaurant",
    )
    assert "existing conditions" in result.lower() or "T24-C02" in result


# --- estimate_fees: ADA threshold ---

@pytest.mark.asyncio
async def test_estimate_fees_ada_above_threshold():
    result = await estimate_fees(
        permit_type="alterations",
        estimated_construction_cost=250000,
        project_type="restaurant",
    )
    assert "ADA" in result or "Accessibility" in result
    assert "ABOVE" in result or "FULL" in result


@pytest.mark.asyncio
async def test_estimate_fees_ada_below_threshold():
    result = await estimate_fees(
        permit_type="alterations",
        estimated_construction_cost=100000,
        project_type="commercial_ti",
    )
    assert "ADA" in result or "Accessibility" in result
    assert "20%" in result or "Below" in result


@pytest.mark.asyncio
async def test_estimate_fees_no_ada_for_residential():
    result = await estimate_fees(
        permit_type="alterations",
        estimated_construction_cost=85000,
        project_type="adu",
    )
    # ADU is residential — no ADA section expected
    assert "ADA/Accessibility Cost Impact" not in result


# --- revision_risk: correction frequencies ---

def test_correction_frequencies_commercial():
    kb = get_knowledge_base()
    corrections = _get_correction_frequencies("restaurant", kb)
    categories = [c["category"] for c in corrections]
    assert "Title-24 Energy Compliance" in categories
    assert "ADA/Accessibility (CBC 11B)" in categories
    assert "DPH Food Facility" in categories


def test_correction_frequencies_general():
    kb = get_knowledge_base()
    corrections = _get_correction_frequencies(None, kb)
    categories = [c["category"] for c in corrections]
    assert "Title-24 Energy Compliance" in categories
    # ADA should show for None (general) project type
    assert "ADA/Accessibility (CBC 11B)" in categories


def test_correction_frequencies_residential():
    kb = get_knowledge_base()
    corrections = _get_correction_frequencies("adu", kb)
    categories = [c["category"] for c in corrections]
    assert "Title-24 Energy Compliance" in categories
    # ADU is not commercial — no ADA entry expected
    assert "ADA/Accessibility (CBC 11B)" not in categories
    assert "DPH Food Facility" not in categories


# =============================================================================
# Phase 2.75 PDF-sourced enhancements
# =============================================================================

# --- EPR correction/resubmittal workflow (from CCSF EPR Applicant Procedure) ---

def test_epr_correction_workflow_loaded():
    kb = get_knowledge_base()
    epr = kb.epr_requirements
    workflow = epr.get("correction_response_workflow", {})
    assert workflow, "correction_response_workflow not found in EPR knowledge"
    steps = workflow.get("steps", [])
    assert len(steps) == 6  # EPR-023 through EPR-028
    step_ids = [s["id"] for s in steps]
    assert "EPR-023" in step_ids
    assert "EPR-028" in step_ids


def test_epr_review_statuses():
    kb = get_knowledge_base()
    epr = kb.epr_requirements
    statuses = epr.get("review_statuses", {}).get("statuses", [])
    assert len(statuses) == 4
    status_names = [s["status"] for s in statuses]
    assert "Approved" in status_names
    assert "Corrections Required" in status_names
    assert "Not Approved" in status_names


def test_epr_document_type_numbering():
    kb = get_knowledge_base()
    epr = kb.epr_requirements
    numbering = epr.get("document_type_numbering", {})
    prefixes = numbering.get("prefixes", [])
    assert len(prefixes) == 6
    prefix_vals = [p["prefix"] for p in prefixes]
    assert "1-" in prefix_vals  # Plans
    assert "6-" in prefix_vals  # Addenda


def test_epr_multi_agency_review():
    kb = get_knowledge_base()
    epr = kb.epr_requirements
    multi = epr.get("multi_agency_review", {})
    assert multi
    reviewers = multi.get("typical_reviewers", [])
    assert len(reviewers) >= 5
    tips = multi.get("coordination_tips", [])
    assert len(tips) >= 3


def test_epr_addenda_vs_corrections():
    kb = get_knowledge_base()
    epr = kb.epr_requirements
    workflow = epr.get("correction_response_workflow", {})
    addenda = workflow.get("addenda_vs_corrections", {})
    assert "correction" in addenda
    assert "addendum" in addenda


# --- Title-24 NRCI/NRCA/NRCV sub-form matrix (from M-04) ---

def test_title24_nrci_sub_forms():
    kb = get_knowledge_base()
    nrci = kb.title24["form_system"]["nonresidential"]["forms"]["NRCI"]
    sub_forms = nrci.get("sub_forms", {})
    assert "building" in sub_forms
    assert "electrical" in sub_forms
    assert "plumbing" in sub_forms
    # Check specific form codes from M-04
    building_forms = [f["form"] for f in sub_forms["building"]]
    assert "NRCI-ENV-E" in building_forms
    assert "NRCI-MCH-E" in building_forms
    electrical_forms = [f["form"] for f in sub_forms["electrical"]]
    assert "NRCI-LTI-E" in electrical_forms


def test_title24_nrca_sub_forms():
    kb = get_knowledge_base()
    nrca = kb.title24["form_system"]["nonresidential"]["forms"]["NRCA"]
    sub_forms = nrca.get("sub_forms", {})
    assert "building_mechanical" in sub_forms
    assert "electrical_lighting" in sub_forms
    # Check specific acceptance test forms
    mech_forms = [f["form"] for f in sub_forms["building_mechanical"]]
    assert "NRCA-MCH-04-A" in mech_forms  # Economizer
    lighting_forms = [f["form"] for f in sub_forms["electrical_lighting"]]
    assert "NRCA-LTI-02-A" in lighting_forms  # Daylighting controls


def test_title24_nrcv_exists():
    kb = get_knowledge_base()
    nonres = kb.title24["form_system"]["nonresidential"]["forms"]
    assert "NRCV" in nonres
    nrcv = nonres["NRCV"]
    sub_forms = nrcv.get("sub_forms", [])
    assert len(sub_forms) >= 4
    form_names = [f["form"] for f in sub_forms]
    assert "NRCV-PLB-21-H" in form_names


def test_title24_ab112_form_code():
    kb = get_knowledge_base()
    ae = kb.title24["sf_specific_rules"]["all_electric_new_construction"]
    assert ae.get("form_code") == "AEC1"


def test_title24_ab093_form_code():
    kb = get_knowledge_base()
    gb = kb.title24["sf_specific_rules"]["green_building_requirements"]
    assert gb.get("form_code") == "GBC1"


def test_title24_energy_inspection_services():
    kb = get_knowledge_base()
    eis = kb.title24["sf_specific_rules"].get("energy_inspection_services", {})
    assert eis
    assert "M-04" in eis.get("related_info_sheets", {})
    assert "M-06" in eis.get("related_info_sheets", {})


# --- ADA DA-02 form structure (from DA-02 PDF) ---

def test_ada_da02_form_structure():
    kb = get_knowledge_base()
    da02 = kb.ada_accessibility.get("da02_form_structure", {})
    assert da02, "da02_form_structure not found in ADA knowledge"
    assert "form_a" in da02
    assert "form_b" in da02
    assert "form_c" in da02


def test_ada_da02_compliance_paths():
    kb = get_knowledge_base()
    form_b = kb.ada_accessibility["da02_form_structure"]["form_b"]
    paths = form_b.get("compliance_paths", [])
    assert len(paths) == 4
    path_names = [p["path"] for p in paths]
    assert "Full compliance" in path_names
    assert "20% disproportionate cost" in path_names
    assert "Historic building exception" in path_names


def test_ada_da02_checklist_categories():
    kb = get_knowledge_base()
    form_c = kb.ada_accessibility["da02_form_structure"]["form_c"]
    categories = form_c.get("checklist_categories", [])
    assert len(categories) == 8
    cat_names = [c["category"] for c in categories]
    assert "Site Arrival" in cat_names
    assert "Entrance/Exit" in cat_names
    assert "Restrooms" in cat_names
    assert "Signage" in cat_names
    # Each category should have items and a common deficiency
    for cat in categories:
        assert "items" in cat
        assert "common_deficiency" in cat


# --- DPH construction standards (from DPH Food Facility Guide) ---

def test_dph_construction_standards_loaded():
    kb = get_knowledge_base()
    cs = kb.dph_food.get("construction_standards", {})
    assert cs, "construction_standards not found in DPH knowledge"
    assert "floors" in cs
    assert "cove_base" in cs
    assert "walls" in cs
    assert "ceilings" in cs
    assert "lighting" in cs


def test_dph_cove_base_specs():
    kb = get_knowledge_base()
    cove = kb.dph_food["construction_standards"]["cove_base"]
    assert cove["radius"] == "3/8 inch minimum"
    assert cove["height"] == "4 inches minimum up wall"


def test_dph_lighting_foot_candles():
    kb = get_knowledge_base()
    lighting = kb.dph_food["construction_standards"]["lighting"]
    fc = lighting.get("foot_candle_requirements", [])
    assert len(fc) >= 5
    # Food prep should be 50fc
    food_prep = [f for f in fc if "Food preparation" in f["area"]]
    assert food_prep
    assert food_prep[0]["minimum_fc"] == 50


def test_dph_ventilation_formulas():
    kb = get_knowledge_base()
    vent = kb.dph_food["construction_standards"].get("ventilation_formulas", {})
    assert "type_i_hood" in vent
    assert "type_ii_hood" in vent
    assert "make_up_air" in vent


def test_dph_grease_interceptor_sizing():
    kb = get_knowledge_base()
    gi = kb.dph_food["construction_standards"].get("grease_interceptor_sizing", {})
    assert gi
    sizes = gi.get("typical_sizes", [])
    assert len(sizes) >= 4


# --- Tool integration tests ---

@pytest.mark.asyncio
async def test_required_docs_inhouse_has_correction_workflow():
    """In-house review should include EPR correction workflow."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "Correction Response Workflow" in result or "EPR-023" in result
    assert "revision cloud" in result.lower() or "EPR-025" in result


@pytest.mark.asyncio
async def test_required_docs_has_file_naming():
    """Document output should include file naming convention."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "File Naming Convention" in result or "1-" in result


@pytest.mark.asyncio
async def test_required_docs_inhouse_has_review_statuses():
    """In-house review should include review status guide."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "Approved" in result
    assert "Corrections Required" in result


@pytest.mark.asyncio
async def test_required_docs_commercial_has_da02_forms():
    """Commercial project should include DA-02 Form A/B/C guidance."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "DA-02 Form A" in result or "Form A" in result
    assert "DA-02 Form B" in result or "compliance path" in result.lower()
    assert "DA-02 Form C" in result or "checklist" in result.lower()


@pytest.mark.asyncio
async def test_required_docs_new_construction_nonres_has_nrci():
    """Nonresidential new construction should reference NRCI sub-forms."""
    result = await required_documents(
        permit_forms=["Form 1/2"],
        review_path="in_house",
        project_type="restaurant",
        triggers=["new_construction"],
    )
    assert "NRCI" in result
    assert "AEC1" in result or "AB-112" in result or "All-Electric" in result


@pytest.mark.asyncio
async def test_required_docs_restaurant_has_dph_construction():
    """Restaurant should include DPH construction standard details."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        agency_routing=["DPH (Public Health)"],
        project_type="restaurant",
    )
    assert "cove base" in result.lower() or "DPH-005" in result
    assert "foot-candle" in result.lower() or "50fc" in result


@pytest.mark.asyncio
async def test_predict_restaurant_has_construction_standards():
    """predict_permits for restaurant should mention DPH construction standards."""
    result = await predict_permits(
        project_description="Convert retail to full-service restaurant with commercial kitchen",
        estimated_cost=300000,
    )
    assert "construction standards" in result.lower() or "cove base" in result.lower()


@pytest.mark.asyncio
async def test_predict_nonres_new_construction_has_nrci_detail():
    """Nonresidential new construction should reference M-04 sub-forms."""
    result = await predict_permits(
        project_description="New construction 3-story office building, ground floor retail",
        estimated_cost=5000000,
        scope_keywords=["new_construction", "commercial_ti"],
    )
    assert "NRCI" in result
    assert "AEC1" in result or "all-electric" in result.lower()
    assert "GBC1" in result or "green building" in result.lower()


# =============================================================================
# Phase 2.75b — Second PDF batch enhancements (M-03, M-08, DPH Appendices, Exhibit F, HPWH)
# =============================================================================

# --- M-03 Residential Title-24 DBI Checklist ---

def test_title24_residential_dbi_checklist():
    """M-03 single-family checklist should be loaded."""
    kb = get_knowledge_base()
    res = kb.title24["form_system"]["residential"]
    assert res.get("dbi_info_sheet") == "M-03 (Single-Family Residential Title-24 Energy Checklist)"
    attachments = res.get("dbi_checklist_attachments", {})
    assert "attachment_1_building" in attachments
    assert "attachment_2_mechanical" in attachments
    assert "attachment_3_electrical" in attachments


def test_title24_hers_triggers():
    """HERS trigger conditions should be documented."""
    kb = get_knowledge_base()
    hers = kb.title24["form_system"]["residential"].get("hers_triggers", {})
    assert hers
    triggers = hers.get("triggers", [])
    assert len(triggers) >= 4
    # Key trigger: duct replacement >25 ft
    assert any("duct" in t.lower() and "25" in t for t in triggers)


def test_title24_climate_zone_3_prescriptive():
    """Climate Zone 3 prescriptive values should be present."""
    kb = get_knowledge_base()
    cz3 = kb.title24["form_system"]["residential"].get("climate_zone_3_prescriptive", {})
    assert cz3
    assert cz3.get("ceiling_insulation") == "R-38"
    assert cz3.get("fenestration_u_factor") == 0.30
    assert cz3.get("fenestration_shgc") == 0.23


# --- M-08 Low-Rise Multifamily LMCC/LMCI/LMCV ---

def test_title24_low_rise_multifamily_exists():
    """Low-rise multifamily form system should exist."""
    kb = get_knowledge_base()
    lrm = kb.title24["form_system"].get("low_rise_multifamily", {})
    assert lrm, "low_rise_multifamily not found in form_system"
    assert "LMCC" in lrm.get("forms", {})
    assert "LMCI" in lrm.get("forms", {})
    assert "LMCV" in lrm.get("forms", {})


def test_title24_lmcc_variants():
    """LMCC should have form variants like CF1R."""
    kb = get_knowledge_base()
    lmcc = kb.title24["form_system"]["low_rise_multifamily"]["forms"]["LMCC"]
    variants = lmcc.get("variants", {})
    assert "LMCC-PRF-01" in variants
    assert "LMCC-ALT-05" in variants


def test_title24_lmci_variants():
    """LMCI should have installation certificate variants."""
    kb = get_knowledge_base()
    lmci = kb.title24["form_system"]["low_rise_multifamily"]["forms"]["LMCI"]
    variants = lmci.get("variants", {})
    assert "LMCI-PVB-01" in variants  # Solar PV
    assert "LMCI-ELC-01" in variants  # Electric ready


def test_title24_building_type_boundary():
    """Building type boundary rules should be documented."""
    kb = get_knowledge_base()
    boundary = kb.title24["form_system"]["low_rise_multifamily"].get("building_type_boundary", {})
    assert boundary
    assert "low_rise_multifamily" in boundary
    assert "high_rise_residential" in boundary
    assert "mixed_use_note" in boundary


def test_title24_multifamily_triggers():
    """Triggers should include low-rise multifamily path."""
    kb = get_knowledge_base()
    triggers = kb.title24["triggers_by_project_type"]
    assert "low_rise_multifamily" in triggers["new_construction"]
    assert "low_rise_multifamily" in triggers["additions"]


def test_title24_info_sheets_include_m03_m08():
    """Related info sheets should include M-03 and M-08."""
    kb = get_knowledge_base()
    sheets = kb.title24["sf_specific_rules"]["energy_inspection_services"]["related_info_sheets"]
    assert "M-03" in sheets
    assert "M-08" in sheets


# --- DPH Equipment Schedule Template (Appendix C) ---

def test_dph_equipment_schedule_template():
    """Equipment schedule template should be loaded with required columns."""
    kb = get_knowledge_base()
    tmpl = kb.dph_food.get("equipment_schedule_template", {})
    assert tmpl, "equipment_schedule_template not found"
    cols = tmpl.get("required_columns", [])
    assert len(cols) >= 8
    col_names = [c["column"] for c in cols]
    assert "Item #" in col_names
    assert "NSF/ANSI Certified" in col_names
    assert "BTU/kW Rating" in col_names


def test_dph_equipment_schedule_special_notes():
    """Equipment template should have special notes for specific equipment types."""
    kb = get_knowledge_base()
    tmpl = kb.dph_food["equipment_schedule_template"]
    notes = tmpl.get("special_equipment_notes", {})
    assert "refrigeration" in notes
    assert "exhaust_hoods" in notes
    assert "dishwashers" in notes


# --- DPH Room Finish Schedule Template (Appendix D) ---

def test_dph_room_finish_schedule_template():
    """Room finish schedule template should be loaded."""
    kb = get_knowledge_base()
    tmpl = kb.dph_food.get("room_finish_schedule_template", {})
    assert tmpl, "room_finish_schedule_template not found"
    cols = tmpl.get("required_columns", [])
    assert len(cols) >= 6
    col_names = [c["column"] for c in cols]
    assert "Cove Base" in col_names
    assert "Ceiling Finish" in col_names
    rooms = tmpl.get("standard_rooms_to_include", [])
    assert len(rooms) >= 10


# --- DPH Flooring Installation Details (Appendix E) ---

def test_dph_flooring_installation_details():
    """Flooring installation details should supplement existing floors section."""
    kb = get_knowledge_base()
    floors = kb.dph_food["construction_standards"]["floors"]
    install = floors.get("installation_details", {})
    assert install, "installation_details not found in floors"
    assert "slope_to_drain" in install
    assert "quarry_tile" in install
    assert "equipment_base" in install


# --- DPH Floor Plan Required Callouts ---

def test_dph_floor_plan_callouts():
    """Floor plan required callouts should be documented."""
    kb = get_knowledge_base()
    callouts = kb.dph_food.get("floor_plan_required_callouts", {})
    assert callouts, "floor_plan_required_callouts not found"
    required = callouts.get("required_callouts", [])
    assert len(required) >= 10
    # Should mention equipment numbers, handwash, grease interceptor
    combined = " ".join(required).lower()
    assert "equipment" in combined
    assert "handwash" in combined or "hw" in combined
    assert "grease" in combined


# --- HPWH Food Facility Requirements ---

def test_dph_hpwh_requirements():
    """HPWH food facility requirements should be loaded."""
    kb = get_knowledge_base()
    hpwh = kb.dph_food.get("hpwh_food_facility_requirements", {})
    assert hpwh, "hpwh_food_facility_requirements not found"
    temps = hpwh.get("hot_water_temperature_requirements", {})
    assert temps.get("general_use") == "120°F minimum at fixtures"
    assert "180" in temps.get("dishwasher_high_temp_sanitizing", "")


def test_dph_hpwh_sizing_and_installation():
    """HPWH should have sizing and installation guidance."""
    kb = get_knowledge_base()
    hpwh = kb.dph_food["hpwh_food_facility_requirements"]
    assert len(hpwh.get("sizing_considerations", [])) >= 4
    assert len(hpwh.get("installation_requirements", [])) >= 4
    assert len(hpwh.get("dph_plan_review_requirements", [])) >= 4


def test_dph_hpwh_gas_exemptions():
    """HPWH should document when gas is still allowed."""
    kb = get_knowledge_base()
    hpwh = kb.dph_food["hpwh_food_facility_requirements"]
    exemptions = hpwh.get("exemptions_for_gas", {})
    assert exemptions
    conditions = exemptions.get("conditions", [])
    assert len(conditions) >= 2


# --- EPR Exhibit F Supplementary Details ---

def test_epr_exhibit_f_bookmark_hierarchy():
    """Exhibit F should add bookmark hierarchy detail."""
    kb = get_knowledge_base()
    exhibit_f = kb.epr_requirements.get("exhibit_f_supplementary", {})
    assert exhibit_f, "exhibit_f_supplementary not found"
    bookmarks = exhibit_f.get("bookmark_hierarchy", {})
    assert bookmarks
    hierarchy = bookmarks.get("hierarchy_example", [])
    assert len(hierarchy) >= 8


def test_epr_exhibit_f_sheet_numbering():
    """Exhibit F should define sheet numbering convention."""
    kb = get_knowledge_base()
    exhibit_f = kb.epr_requirements["exhibit_f_supplementary"]
    numbering = exhibit_f.get("sheet_numbering_convention", {})
    assert numbering
    prefixes = numbering.get("prefixes", [])
    assert len(prefixes) >= 6
    prefix_letters = [p["prefix"] for p in prefixes]
    assert "A" in prefix_letters  # Architectural
    assert "S" in prefix_letters  # Structural
    assert "M" in prefix_letters  # Mechanical
    assert "E" in prefix_letters  # Electrical
    assert "P" in prefix_letters  # Plumbing


def test_epr_exhibit_f_file_size_guidance():
    """Exhibit F should have file size guidance."""
    kb = get_knowledge_base()
    exhibit_f = kb.epr_requirements["exhibit_f_supplementary"]
    size = exhibit_f.get("file_size_guidance", {})
    assert size
    assert "250MB" in size.get("maximum_per_upload", "")


def test_epr_exhibit_f_security_requirements():
    """Exhibit F should detail PDF security requirements."""
    kb = get_knowledge_base()
    exhibit_f = kb.epr_requirements["exhibit_f_supplementary"]
    security = exhibit_f.get("pdf_security_requirements", {})
    assert security
    must_not = security.get("must_not_have", [])
    assert len(must_not) >= 4


def test_epr_exhibit_f_batch_ocr():
    """Exhibit F should have batch OCR instructions for SHX fonts."""
    kb = get_knowledge_base()
    exhibit_f = kb.epr_requirements["exhibit_f_supplementary"]
    ocr = exhibit_f.get("batch_ocr_instructions", {})
    assert ocr
    steps = ocr.get("steps", [])
    assert len(steps) >= 3


# --- Tool integration tests for new knowledge ---

@pytest.mark.asyncio
async def test_required_docs_multifamily_new_construction_has_lmcc():
    """Low-rise multifamily new construction should reference LMCC forms."""
    result = await required_documents(
        permit_forms=["Form 1/2"],
        review_path="in_house",
        project_type="low_rise_multifamily",
        triggers=["new_construction"],
    )
    assert "LMCC" in result
    assert "M-08" in result or "multifamily" in result.lower()


@pytest.mark.asyncio
async def test_required_docs_restaurant_has_equipment_template():
    """Restaurant docs should reference equipment schedule template columns."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        agency_routing=["DPH (Public Health)"],
        project_type="restaurant",
    )
    assert "Appendix C" in result or "NSF" in result
    assert "BTU" in result or "equipment schedule" in result.lower()


@pytest.mark.asyncio
async def test_required_docs_restaurant_has_finish_schedule_template():
    """Restaurant docs should reference room finish schedule template."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        agency_routing=["DPH (Public Health)"],
        project_type="restaurant",
    )
    assert "Appendix D" in result or "room finish schedule" in result.lower()


@pytest.mark.asyncio
async def test_required_docs_new_restaurant_has_hpwh():
    """New construction restaurant should include HPWH sizing document."""
    result = await required_documents(
        permit_forms=["Form 1/2"],
        review_path="in_house",
        agency_routing=["DPH (Public Health)"],
        project_type="restaurant",
        triggers=["new_construction"],
    )
    assert "HPWH" in result or "heat pump" in result.lower()


@pytest.mark.asyncio
async def test_required_docs_has_sheet_numbering():
    """Document output should include sheet numbering convention from Exhibit F."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "Sheet Numbering" in result or "Architectural" in result


@pytest.mark.asyncio
async def test_required_docs_residential_has_m03_reference():
    """Residential alteration should reference M-03 checklist."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="otc",
        project_type="general",
        triggers=[],
    )
    assert "CF1R" in result or "M-03" in result


@pytest.mark.asyncio
async def test_predict_multifamily_detects_type():
    """predict_permits should detect low-rise multifamily from description."""
    result = await predict_permits(
        project_description="New construction 3-story apartment building, 12 units",
        estimated_cost=3000000,
    )
    assert "multifamily" in result.lower() or "LMCC" in result


@pytest.mark.asyncio
async def test_predict_new_restaurant_has_hpwh():
    """New construction restaurant should mention HPWH."""
    result = await predict_permits(
        project_description="New construction restaurant with full commercial kitchen",
        estimated_cost=2000000,
        scope_keywords=["new_construction", "restaurant"],
    )
    assert "HPWH" in result or "heat pump" in result.lower()


def test_revision_risk_restaurant_has_equipment_schedule():
    """Revision risk for restaurant should include equipment schedule correction."""
    kb = get_knowledge_base()
    corrections = _get_correction_frequencies("restaurant", kb)
    categories = [c["category"] for c in corrections]
    assert "DPH Equipment Schedule (Appendix C)" in categories


# =============================================================================
# Phase 2.75c — Third PDF batch enhancements (M-06, Back Check Page, Exhibit C, Exhibit E)
# =============================================================================

# --- M-06 Final Compliance Affidavit ---

def test_title24_final_compliance_affidavit_exists():
    """M-06 final compliance affidavit process should be loaded."""
    kb = get_knowledge_base()
    affidavit = kb.title24["sf_specific_rules"].get("final_compliance_affidavit", {})
    assert affidavit, "final_compliance_affidavit not found"
    assert "M-06" in affidavit.get("source", "")


def test_title24_affidavit_checklist_routing():
    """M-06 should map project types to correct checklist info sheets."""
    kb = get_knowledge_base()
    affidavit = kb.title24["sf_specific_rules"]["final_compliance_affidavit"]
    routing = affidavit.get("inspection_checklists_by_project_type", {})
    assert routing.get("single_family") == "M-03 — single-family residential buildings"
    assert routing.get("nonresidential") == "M-04 — non-residential, high-rise residential, and hotel/motel buildings"
    assert routing.get("low_rise_multifamily") == "M-08 — low-rise multi-family residential buildings"


def test_title24_affidavit_process():
    """M-06 affidavit process should have submittal details."""
    kb = get_knowledge_base()
    process = kb.title24["sf_specific_rules"]["final_compliance_affidavit"]["affidavit_process"]
    submittal = process.get("submittal", {})
    assert submittal.get("email") == "dbi.energyinspections@sfgov.org"
    assert "10 business days" in submittal.get("review_time", "")
    assert len(process.get("required_contents", [])) >= 5


def test_title24_energy_consultant_types():
    """M-06 should list energy consultant types with certifying bodies."""
    kb = get_knowledge_base()
    affidavit = kb.title24["sf_specific_rules"]["final_compliance_affidavit"]
    consultants = affidavit.get("energy_consultant_types", [])
    assert len(consultants) >= 4
    types = [c["type"] for c in consultants]
    assert "CEPE" in types
    assert "CEA" in types
    assert "HERS Rater" in types
    assert "ATT" in types


def test_title24_affidavit_hers_att_rules():
    """M-06 should enforce HERS/ATT affidavit submission rules."""
    kb = get_knowledge_base()
    process = kb.title24["sf_specific_rules"]["final_compliance_affidavit"]["affidavit_process"]
    assert "HERS Rater" in process.get("hers_affidavit_rule", "")
    assert "ATT" in process.get("att_affidavit_rule", "")


def test_title24_sfgbc_compliance():
    """M-06 should document SFGBC AB-093 compliance process."""
    kb = get_knowledge_base()
    sfgbc = kb.title24["sf_specific_rules"]["final_compliance_affidavit"].get("sfgbc_compliance", {})
    assert sfgbc
    assert sfgbc.get("admin_bulletin") == "AB-093"
    assert sfgbc.get("form") == "AB-093 Attachment E"
    assert "new construction" in sfgbc.get("applicability", "").lower()


def test_title24_checklist_exemption():
    """M-06 should document exemption for minor residential alterations."""
    kb = get_knowledge_base()
    affidavit = kb.title24["sf_specific_rules"]["final_compliance_affidavit"]
    exemption = affidavit.get("checklist_exemption", "")
    assert "300 sq ft" in exemption or "300" in exemption
    assert "water heater" in exemption.lower()


# --- EPR Back Check Page ---

def test_epr_back_check_page_detail():
    """Back check page detail should be loaded from Exhibit F supplementary."""
    kb = get_knowledge_base()
    exhibit_f = kb.epr_requirements.get("exhibit_f_supplementary", {})
    bcp = exhibit_f.get("back_check_page", {})
    assert bcp, "back_check_page not found"
    assert len(bcp.get("instructions", [])) >= 4
    assert "last page" in bcp.get("description", "").lower() or "LAST" in bcp.get("description", "")


# --- EPR Exhibit C (Project Folder Structure) ---

def test_epr_exhibit_c_folder_structure():
    """Exhibit C project folder structure should be loaded."""
    kb = get_knowledge_base()
    exhibit_f = kb.epr_requirements.get("exhibit_f_supplementary", {})
    exhibit_c = exhibit_f.get("exhibit_c_project_folder_structure", {})
    assert exhibit_c, "exhibit_c_project_folder_structure not found"
    folders = exhibit_c.get("folder_structure", {}).get("folders", [])
    assert len(folders) >= 2
    # Should have A (SUBMITTAL) and B (APPROVED)
    folder_names = [f["folder"] for f in folders]
    assert any("SUBMITTAL" in n for n in folder_names)
    assert any("APPROVED" in n for n in folder_names)


def test_epr_exhibit_c_submittal_subfolders():
    """Exhibit C submittal folder should have 3 subfolders."""
    kb = get_knowledge_base()
    exhibit_c = kb.epr_requirements["exhibit_f_supplementary"]["exhibit_c_project_folder_structure"]
    folders = exhibit_c["folder_structure"]["folders"]
    submittal = [f for f in folders if "SUBMITTAL" in f["folder"]][0]
    subfolders = submittal.get("subfolders", [])
    assert len(subfolders) >= 3
    subfolder_names = [s["name"] for s in subfolders]
    assert any("PERMIT FORMS" in n for n in subfolder_names)
    assert any("ROUTING" in n for n in subfolder_names)
    assert any("REVIEW" in n for n in subfolder_names)


# --- EPR Exhibit E (Studio Session Layout) ---

def test_epr_exhibit_e_studio_session():
    """Exhibit E studio session layout should be loaded."""
    kb = get_knowledge_base()
    exhibit_f = kb.epr_requirements.get("exhibit_f_supplementary", {})
    exhibit_e = exhibit_f.get("exhibit_e_studio_session_layout", {})
    assert exhibit_e, "exhibit_e_studio_session_layout not found"
    components = exhibit_e.get("session_components", {})
    assert "tool_chest" in components
    assert "markups_list" in components
    assert "attendees_panel" in components


def test_epr_exhibit_e_markup_status_workflow():
    """Exhibit E should document the markup status workflow."""
    kb = get_knowledge_base()
    exhibit_e = kb.epr_requirements["exhibit_f_supplementary"]["exhibit_e_studio_session_layout"]
    workflow = exhibit_e.get("markup_status_workflow", {})
    assert workflow
    applicant_statuses = workflow.get("applicant_response_statuses", [])
    assert len(applicant_statuses) >= 2
    reviewer_statuses = workflow.get("reviewer_back_check_statuses", [])
    assert len(reviewer_statuses) >= 2
    # Should have INCORPORATED and CLOSED
    assert any("INCORPORATED" in s["status"] for s in applicant_statuses)
    assert any("CLOSED" in s["status"] for s in reviewer_statuses)


# --- Tool integration tests for M-06 and EPR ---

@pytest.mark.asyncio
async def test_required_docs_has_final_compliance_affidavit():
    """Required docs for any Title-24 project should include M-06 affidavit."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "M-06" in result or "final compliance affidavit" in result.lower()


@pytest.mark.asyncio
async def test_required_docs_new_construction_has_ab093():
    """New construction should include AB-093 Attachment E for SFGBC."""
    result = await required_documents(
        permit_forms=["Form 1/2"],
        review_path="in_house",
        project_type="restaurant",
        triggers=["new_construction"],
    )
    assert "AB-093" in result
    assert "Attachment E" in result or "Green Building" in result


@pytest.mark.asyncio
async def test_required_docs_in_house_has_back_check_tip():
    """In-house review should include back check page pro tip."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "Back Check" in result


@pytest.mark.asyncio
async def test_required_docs_in_house_has_bluebeam_folder_tip():
    """In-house review should include Bluebeam folder structure tip."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "Bluebeam" in result or "SUBMITTAL" in result


@pytest.mark.asyncio
async def test_predict_has_final_compliance_affidavit():
    """predict_permits should mention M-06 final compliance affidavit."""
    result = await predict_permits(
        project_description="Commercial tenant improvement in existing office building",
        estimated_cost=200000,
        scope_keywords=["commercial_ti"],
    )
    assert "M-06" in result or "final compliance affidavit" in result.lower() or "dbi.energyinspections" in result


# =============================================================================
# Phase 2.75d — G-01 Signature Requirements + G-25 Restaurant Guide + SFFD Fees
# =============================================================================

# --- G-01 Knowledge File Tests ---

def test_g01_signature_file_exists():
    """G-01 plan signature requirements file should load with signature_categories."""
    kb = get_knowledge_base()
    sigs = kb.plan_signatures
    assert sigs, "plan_signatures should be loaded"
    assert "signature_categories" in sigs
    cats = sigs["signature_categories"]
    assert "exempt" in cats
    assert "licensed_contractor" in cats
    assert "registered_engineer_or_architect" in cats
    assert "special_status" in cats


def test_g01_exempt_conditions():
    """G-01 should have 9 exempt conditions."""
    kb = get_knowledge_base()
    exempt = kb.plan_signatures["signature_categories"]["exempt"]
    conditions = exempt.get("conditions", [])
    assert len(conditions) == 9, f"Expected 9 exempt conditions, got {len(conditions)}"
    ids = [c["id"] for c in conditions]
    assert "G01-EX-01" in ids  # SFD wood frame
    assert "G01-EX-06" in ids  # Tenant space improvements
    assert "G01-EX-09" in ids  # Sprinkler/fire alarm


def test_g01_exempt_tenant_threshold():
    """G-01 exempt tenant space improvement threshold should be $400,000."""
    kb = get_knowledge_base()
    conditions = kb.plan_signatures["signature_categories"]["exempt"]["conditions"]
    ex06 = next(c for c in conditions if c["id"] == "G01-EX-06")
    assert ex06["valuation_threshold"] == 400000


def test_g01_exempt_dwelling_threshold():
    """G-01 exempt dwelling unit improvement threshold should be $150,000."""
    kb = get_knowledge_base()
    conditions = kb.plan_signatures["signature_categories"]["exempt"]["conditions"]
    ex07 = next(c for c in conditions if c["id"] == "G01-EX-07")
    assert ex07["valuation_threshold"] == 150000


def test_g01_engineer_triggers():
    """G-01 Status III should list 7 triggers requiring CA-licensed architect/engineer."""
    kb = get_knowledge_base()
    eng = kb.plan_signatures["signature_categories"]["registered_engineer_or_architect"]
    triggers = eng.get("triggers", [])
    assert len(triggers) == 7
    # Check key triggers exist
    trigger_texts = " ".join(t["trigger"] for t in triggers).lower()
    assert "structural steel" in trigger_texts
    assert "clear span" in trigger_texts
    assert "wall removal" in trigger_texts


def test_g01_special_status_items():
    """G-01 Status IV should have 15 special status items."""
    kb = get_knowledge_base()
    special = kb.plan_signatures["signature_categories"]["special_status"]
    items = special.get("items", [])
    assert len(items) == 15
    # Check for fire protection items with SFFD consult flag
    sffd_items = [i for i in items if i.get("sffd_consult")]
    assert len(sffd_items) >= 5  # sprinkler, smoke detection, alarm, central control, smoke control


def test_g01_seal_requirements():
    """G-01 seal requirements should specify first sheet original + electronic OK."""
    kb = get_knowledge_base()
    seal = kb.plan_signatures.get("seal_requirements", {})
    assert "first_sheet" in seal
    assert "original" in seal["first_sheet"].get("requirement", "").lower()
    assert seal.get("electronic_signatures", {}).get("allowed") is True
    prohibited = seal.get("prohibited", [])
    assert len(prohibited) == 3


def test_g01_shop_drawings():
    """G-01 should have 3 shop drawing acceptance methods."""
    kb = get_knowledge_base()
    shop = kb.plan_signatures.get("shop_drawings", {})
    methods = shop.get("acceptance_methods", [])
    assert len(methods) == 3


# --- G-25 Knowledge File Tests ---

def test_g25_restaurant_file_exists():
    """G-25 restaurant permit guide should load with step_by_step_process."""
    kb = get_knowledge_base()
    guide = kb.restaurant_guide
    assert guide, "restaurant_guide should be loaded"
    assert "step_by_step_process" in guide
    assert "dbi_specific_requirements" in guide


def test_g25_occupancy_classification():
    """G-25 should define occupancy: ≤50 = Group B, >50 = Group A-2."""
    kb = get_knowledge_base()
    occ = kb.restaurant_guide["dbi_specific_requirements"]["occupancy_classification"]
    assert "Group B" in occ["restaurant_50_or_fewer"]["classification"]
    assert "Group A-2" in occ["restaurant_over_50"]["classification"]
    assert "Group A-2" in occ["bar_lounge"]["classification"]


def test_g25_permits_needed():
    """G-25 should list all required permits for restaurant."""
    kb = get_knowledge_base()
    permits = kb.restaurant_guide["dbi_specific_requirements"]["permits_needed"]
    assert "building_permit" in permits
    assert "plumbing_permit" in permits
    assert "electrical_permit" in permits
    assert "dph_health_permit" in permits
    assert "sffd_operational_permit" in permits
    assert "planning_approval" in permits


def test_g25_dph_coordination():
    """G-25 should note DPH parallel review and common rejections."""
    kb = get_knowledge_base()
    dph = kb.restaurant_guide["dph_coordination"]
    assert dph["parallel_review"] is True
    rejections = dph.get("common_dph_rejections", [])
    assert len(rejections) >= 5
    # Check for key rejection reasons
    rej_text = " ".join(rejections).lower()
    assert "equipment schedule" in rej_text
    assert "grease" in rej_text


def test_g25_fee_estimates():
    """G-25 should include plumbing categories and SFFD operational fee."""
    kb = get_knowledge_base()
    fees = kb.restaurant_guide["fee_estimates"]
    assert fees["plumbing_permit"]["category_6PA"]["fee"] == 543
    assert fees["plumbing_permit"]["category_6PB"]["fee"] == 1525
    assert fees["sffd_operational"]["fee"] == 387


def test_g25_timeline_expectations():
    """G-25 should have total estimate of 4-8 months."""
    kb = get_knowledge_base()
    timeline = kb.restaurant_guide["timeline_expectations"]
    assert "4-8 months" in timeline["total_estimate"]


def test_g25_step_by_step_has_8_steps():
    """G-25 should define 8 steps from planning to inspection."""
    kb = get_knowledge_base()
    steps = kb.restaurant_guide["step_by_step_process"]
    step_keys = [k for k in steps if k.startswith("step_")]
    assert len(step_keys) == 8


# --- SFFD Fee Calculation Tests ---

def test_sffd_plan_review_fee_small():
    """SFFD plan review for $5K valuation should be reasonable."""
    from src.tools.estimate_fees import _calculate_sffd_fees
    kb = get_knowledge_base()
    result = _calculate_sffd_fees(5000, "restaurant", kb.fire_code)
    assert result["plan_review"] > 0, "Should have a plan review fee"
    assert result["plan_review"] < 500, "Small project fee should be modest"


def test_sffd_plan_review_fee_medium():
    """SFFD plan review for $100K valuation should be in $800-$1200 range."""
    from src.tools.estimate_fees import _calculate_sffd_fees
    kb = get_knowledge_base()
    result = _calculate_sffd_fees(100000, "restaurant", kb.fire_code)
    assert result["plan_review"] >= 800, f"Expected ≥$800, got ${result['plan_review']}"
    assert result["plan_review"] <= 1500, f"Expected ≤$1500, got ${result['plan_review']}"


def test_sffd_field_inspection_fee():
    """SFFD field inspection for $100K valuation should be $408 (3 hours)."""
    from src.tools.estimate_fees import _calculate_sffd_fees
    kb = get_knowledge_base()
    result = _calculate_sffd_fees(100000, "restaurant", kb.fire_code)
    assert result["field_inspection"] == 408


def test_sffd_restaurant_has_system_or_operational_fees():
    """Restaurant SFFD fees should include sprinkler system fee or operational permit."""
    from src.tools.estimate_fees import _calculate_sffd_fees
    kb = get_knowledge_base()
    result = _calculate_sffd_fees(300000, "restaurant", kb.fire_code)
    has_extras = len(result["system_fees"]) > 0 or len(result["operational_permits"]) > 0
    assert has_extras, "Restaurant should have system fees or operational permits"
    # Should have Place of Assembly note
    op_texts = [p["permit"] for p in result["operational_permits"]]
    assert any("Assembly" in t for t in op_texts), "Should include Place of Assembly permit"


def test_sffd_total_includes_all_components():
    """SFFD total should be sum of plan review + inspection + system + operational."""
    from src.tools.estimate_fees import _calculate_sffd_fees
    kb = get_knowledge_base()
    result = _calculate_sffd_fees(200000, "restaurant", kb.fire_code)
    expected_total = (
        result["plan_review"] + result["field_inspection"] +
        sum(s["fee"] for s in result["system_fees"]) +
        sum(p["fee"] for p in result["operational_permits"])
    )
    assert result["total_sffd"] == round(expected_total, 2)


# --- Tool Integration Tests ---

@pytest.mark.asyncio
async def test_required_docs_has_signature_requirement():
    """Engineer-required projects should get G-01 signature note."""
    result = await required_documents(
        permit_forms=["Form 1/2"],
        review_path="in_house",
        project_type="new_construction",
        triggers=["new_construction"],
    )
    assert "G-01" in result or "architect or" in result.lower() or "engineer" in result.lower()


@pytest.mark.asyncio
async def test_required_docs_exempt_status_tip():
    """General alteration should mention G-01 exempt possibility."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="otc",
    )
    assert "exempt" in result.lower() or "G-01" in result


@pytest.mark.asyncio
async def test_predict_restaurant_always_inhouse():
    """Restaurant projects should always be in-house review."""
    result = await predict_permits(
        project_description="Restaurant tenant improvement",
        scope_keywords=["restaurant"],
    )
    # Should say in_house, not depends or likely_otc
    assert "in_house" in result


@pytest.mark.asyncio
async def test_predict_restaurant_occupancy_note():
    """Restaurant prediction should mention Group A-2 / Group B classification."""
    result = await predict_permits(
        project_description="New restaurant in existing building",
        estimated_cost=300000,
        scope_keywords=["restaurant"],
    )
    assert "Group A-2" in result or "Group B" in result or "occupancy" in result.lower()


@pytest.mark.asyncio
async def test_predict_restaurant_separate_permits():
    """Restaurant prediction should mention separate plumbing + electrical permits."""
    result = await predict_permits(
        project_description="Restaurant buildout",
        estimated_cost=250000,
        scope_keywords=["restaurant"],
    )
    assert "separate" in result.lower() or "plumbing permit" in result.lower()


@pytest.mark.asyncio
async def test_predict_restaurant_g01_signature():
    """Restaurant prediction should mention G-01 signature requirement."""
    result = await predict_permits(
        project_description="Restaurant construction",
        estimated_cost=300000,
        scope_keywords=["restaurant"],
    )
    assert "G-01" in result or "architect or engineer" in result.lower()


@pytest.mark.asyncio
async def test_estimate_fees_has_sffd_section():
    """Restaurant fee estimate should include SFFD fee section."""
    result = await estimate_fees(
        permit_type="alterations",
        estimated_construction_cost=300000,
        project_type="restaurant",
    )
    assert "SFFD" in result
    assert "107-B" in result or "Plan Review" in result


@pytest.mark.asyncio
async def test_required_docs_restaurant_has_g25_tips():
    """Restaurant required docs should include G-25 process tips."""
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        agency_routing=["Planning", "SFFD (Fire)", "DPH (Public Health)"],
        project_type="restaurant",
    )
    assert "Planning FIRST" in result or "G-25" in result
    assert "DPH" in result
    assert "separate" in result.lower() or "plumbing" in result.lower()


# --- Semantic Index Tests ---

def test_semantic_index_has_g01_concept():
    """Semantic index should include plan_signature_requirements concept."""
    kb = get_knowledge_base()
    concepts = kb.semantic_index.get("concepts", {})
    assert "plan_signature_requirements" in concepts
    aliases = concepts["plan_signature_requirements"]["aliases"]
    assert "G-01" in aliases
    assert "architect required" in aliases


def test_semantic_index_has_g25_concept():
    """Semantic index should include restaurant_permit_guide concept."""
    kb = get_knowledge_base()
    concepts = kb.semantic_index.get("concepts", {})
    assert "restaurant_permit_guide" in concepts
    aliases = concepts["restaurant_permit_guide"]["aliases"]
    assert "G-25" in aliases
    assert "restaurant permit" in aliases
