"""Tests for estimate_fees tool."""

import pytest
from src.tools.estimate_fees import estimate_fees, _calculate_building_fee, _calculate_surcharges
from src.tools.knowledge_base import get_knowledge_base


def test_fee_calculation_small_alteration():
    """$1,000 alteration should use first tier."""
    kb = get_knowledge_base()
    result = _calculate_building_fee(1000, "alterations", kb.fee_tables)
    assert "error" not in result
    assert result["plan_review_fee"] > 0
    assert result["permit_issuance_fee"] > 0
    assert result["total_building_fee"] == result["plan_review_fee"] + result["permit_issuance_fee"]


def test_fee_calculation_medium_alteration():
    """$85,000 alteration should use $50,001-$200,000 tier."""
    kb = get_knowledge_base()
    result = _calculate_building_fee(85000, "alterations", kb.fee_tables)
    assert "error" not in result
    assert result["total_building_fee"] > 500  # Should be substantial


def test_fee_calculation_new_construction():
    """$500,000 new construction."""
    kb = get_knowledge_base()
    result = _calculate_building_fee(500000, "new_construction", kb.fee_tables)
    assert "error" not in result
    assert result["total_building_fee"] > 1000


def test_fee_calculation_no_plans():
    """$5,000 no-plans permit."""
    kb = get_knowledge_base()
    result = _calculate_building_fee(5000, "no_plans", kb.fee_tables)
    assert "error" not in result
    # no_plans has no plan_review fee
    assert result["permit_issuance_fee"] > 0


def test_surcharges():
    """CBSC and SMIP surcharges calculated."""
    kb = get_knowledge_base()
    surcharges = _calculate_surcharges(100000, kb.fee_tables)
    assert surcharges["cbsc_fee"] > 0
    assert surcharges["smip_fee"] > 0
    assert surcharges["total_surcharges"] == surcharges["cbsc_fee"] + surcharges["smip_fee"]


@pytest.mark.asyncio
async def test_estimate_fees_alterations():
    result = await estimate_fees(
        permit_type="alterations",
        estimated_construction_cost=85000,
    )
    assert "Fee Estimate" in result
    assert "Plan Review Fee" in result
    assert "Permit Issuance Fee" in result
    assert "$" in result


@pytest.mark.asyncio
async def test_estimate_fees_with_project_type():
    result = await estimate_fees(
        permit_type="alterations",
        estimated_construction_cost=250000,
        project_type="restaurant",
    )
    assert "restaurant" in result.lower() or "Plumbing" in result or "DPH" in result


@pytest.mark.asyncio
async def test_estimate_fees_includes_notes():
    result = await estimate_fees(
        permit_type="new_construction",
        estimated_construction_cost=2500000,
    )
    assert "Ord. 126-25" in result or "9/1/2025" in result
