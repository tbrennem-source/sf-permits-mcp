"""Tests for required_documents tool."""

import pytest
from src.tools.required_documents import required_documents


@pytest.mark.asyncio
async def test_basic_form3_documents():
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
    )
    assert "Building Permit Application" in result
    assert "Construction plans" in result
    assert "Title 24" in result


@pytest.mark.asyncio
async def test_demolition_documents():
    result = await required_documents(
        permit_forms=["Form 6"],
        review_path="in_house",
        triggers=["demolition"],
    )
    assert "Asbestos" in result
    assert "Demolition Affidavit" in result


@pytest.mark.asyncio
async def test_restaurant_documents():
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        agency_routing=["Planning", "SFFD (Fire)", "DPH (Public Health)"],
        project_type="restaurant",
        triggers=["change_of_use"],
    )
    assert "Grease interceptor" in result
    assert "Health permit" in result
    assert "Planning" in result
    assert "Use change" in result


@pytest.mark.asyncio
async def test_epr_requirements_included():
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
    )
    assert "Electronic Plan Review" in result or "EPR" in result
    assert "PDF" in result


@pytest.mark.asyncio
async def test_otc_pro_tips():
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="otc",
    )
    assert "counter" in result.lower() or "1 hour" in result.lower() or "OTC" in result


@pytest.mark.asyncio
async def test_commercial_ti_ada():
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        project_type="commercial_ti",
    )
    assert "Disabled Access" in result or "ADA" in result


@pytest.mark.asyncio
async def test_historic_documents():
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        triggers=["historic"],
    )
    assert "Secretary of Interior" in result or "Historic" in result
