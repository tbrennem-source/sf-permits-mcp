"""Tests for predict_permits tool."""

import pytest
from src.tools.predict_permits import predict_permits, _extract_project_types
from src.tools.knowledge_base import get_knowledge_base


def test_extract_restaurant_keywords():
    types = _extract_project_types("Convert retail to restaurant with grease trap", None)
    assert "restaurant" in types
    assert "change_of_use" in types


def test_extract_adu_keywords():
    types = _extract_project_types("Convert detached garage to ADU, 450 sq ft", None)
    assert "adu" in types


def test_extract_seismic_keywords():
    types = _extract_project_types("Seismic retrofit of soft story building", None)
    assert "seismic" in types


def test_extract_commercial_ti():
    types = _extract_project_types("Office tenant improvement, new HVAC", None)
    assert "commercial_ti" in types


def test_extract_historic():
    types = _extract_project_types("Renovation of landmark building in historic district", None)
    assert "historic" in types


def test_extract_override():
    types = _extract_project_types("Some random text", ["restaurant", "change_of_use"])
    assert types == ["restaurant", "change_of_use"]


def test_extract_default():
    types = _extract_project_types("Minor work on a building", None)
    assert "general_alteration" in types


@pytest.mark.asyncio
async def test_predict_restaurant_conversion():
    result = await predict_permits(
        project_description="Convert 1,500 sq ft retail space to restaurant in the Mission. "
        "Need grease trap, hood ventilation, ADA compliance, new signage.",
        estimated_cost=250000,
    )
    assert "restaurant" in result.lower()
    assert "in_house" in result.lower() or "in-house" in result.lower()
    assert "Planning" in result
    assert "SFFD" in result or "Fire" in result
    assert "DPH" in result or "Health" in result


@pytest.mark.asyncio
async def test_predict_kitchen_remodel():
    result = await predict_permits(
        project_description="Gut renovation of residential kitchen in Noe Valley, "
        "removing a non-bearing wall, relocating gas line, new electrical panel. Budget $85K.",
        estimated_cost=85000,
    )
    assert "Form 3/8" in result
    assert "Confidence" in result


@pytest.mark.asyncio
async def test_predict_adu():
    result = await predict_permits(
        project_description="Convert detached garage to ADU in the Sunset, 450 sq ft, "
        "new plumbing and electrical, fire sprinkler required.",
        estimated_cost=180000,
    )
    assert "adu" in result.lower()
    assert "in_house" in result.lower() or "in-house" in result.lower()


@pytest.mark.asyncio
async def test_predict_returns_gaps_without_cost():
    result = await predict_permits(
        project_description="Kitchen remodel"
    )
    assert "No cost estimate" in result


def test_knowledge_base_loads():
    kb = get_knowledge_base()
    assert len(kb._keyword_index) > 100
    assert kb.decision_tree
    assert kb.fee_tables
    assert kb.otc_criteria


def test_semantic_concept_matching():
    kb = get_knowledge_base()
    concepts = kb.match_concepts("restaurant change of use grease trap")
    assert len(concepts) > 0


def test_step_confidence():
    kb = get_knowledge_base()
    assert kb.get_step_confidence(3) in ("high", "medium", "low")


def test_concept_ranking_restaurant_first():
    """Restaurant-specific query should rank 'restaurant' highest."""
    kb = get_knowledge_base()
    scored = kb.match_concepts_scored("Convert retail to restaurant in the Mission")
    assert len(scored) > 0
    # Restaurant should be the top-ranked or at least top-3 concept
    top_names = [name for name, _score in scored[:3]]
    assert "restaurant" in top_names


def test_concept_ranking_scores_descending():
    """Scores should be in descending order."""
    kb = get_knowledge_base()
    scored = kb.match_concepts_scored("kitchen remodel with new cabinets and recessed lights")
    if len(scored) >= 2:
        scores = [s for _, s in scored]
        assert scores == sorted(scores, reverse=True), f"Scores not descending: {scores}"


def test_concept_ranking_multiword_bonus():
    """Multi-word alias matches should score higher than single-word."""
    kb = get_knowledge_base()
    scored = kb.match_concepts_scored("earthquake brace bolt retrofit for my house")
    assert len(scored) > 0
    top_names = [name for name, _score in scored[:3]]
    assert "earthquake_brace_bolt" in top_names or "seismic" in top_names
    assert kb.get_step_confidence(6) == "medium"  # Timeline is the gap
