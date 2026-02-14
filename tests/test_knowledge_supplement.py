"""Tests for Phase 2.6 knowledge supplement integration (Title-24, DPH, ADA)."""

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
    assert threshold.get("current_amount") == 195358.0
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
        estimated_cost=250000,  # Above $195,358 threshold
    )
    assert "FULL" in result or "full" in result
    assert "DA-02" in result


@pytest.mark.asyncio
async def test_predict_commercial_ti_ada_below_threshold():
    result = await predict_permits(
        project_description="Office tenant improvement, minor alterations",
        estimated_cost=100000,  # Below $195,358 threshold
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
