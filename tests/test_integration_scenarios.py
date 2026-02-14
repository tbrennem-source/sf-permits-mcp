"""Integration test scenarios — 5 Amy stress test cases.

These run the full predict_permits → structure validation chain.
DuckDB-dependent tests (timeline, fees with stats, revision_risk) are
skipped if the database is not available.
"""

import os
import pytest

DB_PATH = os.environ.get(
    "SF_PERMITS_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "sf_permits.duckdb"),
)

# --- Scenario A: Residential Kitchen Remodel ---

@pytest.mark.asyncio
async def test_scenario_a_predict():
    from src.tools.predict_permits import predict_permits
    result = await predict_permits(
        project_description="Gut renovation of residential kitchen in Noe Valley, "
        "removing a non-bearing wall, relocating gas line, new electrical panel. Budget $85K.",
        estimated_cost=85000,
    )
    assert "Form 3/8" in result
    assert "Confidence" in result


@pytest.mark.asyncio
async def test_scenario_a_fees():
    from src.tools.estimate_fees import estimate_fees
    result = await estimate_fees(
        permit_type="alterations",
        estimated_construction_cost=85000,
    )
    assert "Fee Estimate" in result
    assert "$" in result


@pytest.mark.asyncio
async def test_scenario_a_docs():
    from src.tools.required_documents import required_documents
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
    )
    assert "Title 24" in result


# --- Scenario B: ADU Over Garage ---

@pytest.mark.asyncio
async def test_scenario_b_predict():
    from src.tools.predict_permits import predict_permits
    result = await predict_permits(
        project_description="Convert detached garage to ADU in the Sunset, 450 sq ft, "
        "new plumbing and electrical, fire sprinkler required.",
        estimated_cost=180000,
        square_footage=450,
    )
    assert "adu" in result.lower()
    assert "in_house" in result.lower() or "in-house" in result.lower()


# --- Scenario C: Commercial TI ---

@pytest.mark.asyncio
async def test_scenario_c_predict():
    from src.tools.predict_permits import predict_permits
    result = await predict_permits(
        project_description="3,000 sq ft office-to-office tenant improvement in Financial District, "
        "new HVAC, ADA bathroom upgrades, no change of use.",
        estimated_cost=350000,
        square_footage=3000,
    )
    assert "commercial_ti" in result.lower() or "tenant improvement" in result.lower()


# --- Scenario D: Restaurant Conversion ---

@pytest.mark.asyncio
async def test_scenario_d_predict():
    from src.tools.predict_permits import predict_permits
    result = await predict_permits(
        project_description="Convert 1,500 sq ft retail space to restaurant in the Mission. "
        "Need grease trap, hood ventilation, ADA compliance, new signage.",
        estimated_cost=250000,
        square_footage=1500,
    )
    assert "restaurant" in result.lower()
    assert "Planning" in result
    assert "DPH" in result or "Health" in result
    assert "SFFD" in result or "Fire" in result


@pytest.mark.asyncio
async def test_scenario_d_docs():
    from src.tools.required_documents import required_documents
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        agency_routing=["Planning", "SFFD (Fire)", "DPH (Public Health)"],
        project_type="restaurant",
        triggers=["change_of_use"],
    )
    assert "Grease interceptor" in result
    assert "Hood" in result or "hood" in result


# --- Scenario E: Historic Building Renovation ---

@pytest.mark.asyncio
async def test_scenario_e_predict():
    from src.tools.predict_permits import predict_permits
    result = await predict_permits(
        project_description="Major renovation of a 1906 building in Pacific Heights, "
        "historic district. Seismic retrofit, all new mechanical/electrical/plumbing systems, "
        "adding an elevator.",
        estimated_cost=2500000,
        square_footage=5000,
    )
    assert "historic" in result.lower()
    assert "seismic" in result.lower()
    assert "in_house" in result.lower() or "in-house" in result.lower()
    assert "Planning" in result


@pytest.mark.asyncio
async def test_scenario_e_docs():
    from src.tools.required_documents import required_documents
    result = await required_documents(
        permit_forms=["Form 3/8"],
        review_path="in_house",
        agency_routing=["Planning", "SFFD (Fire)"],
        triggers=["historic", "seismic"],
    )
    assert "Secretary of Interior" in result or "Historic" in result
    assert "Structural engineering" in result or "structural" in result.lower()
