"""Integration tests for SF Permits MCP tools.

These tests run against the live SODA API at data.sfgov.org.
They require network access but no authentication (app token optional).
"""

import pytest
from src.soda_client import SODAClient

# Mark all tests in this module as network-dependent
pytestmark = pytest.mark.network


@pytest.mark.asyncio
async def test_building_permits_accessible():
    """Verify building permits dataset is accessible and has expected volume."""
    client = SODAClient()
    try:
        count = await client.count("i98e-djp9")
        assert count > 500_000, f"Expected 500K+ building permits, got {count}"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_search_permits_by_neighborhood():
    """Verify neighborhood filtering works on building permits."""
    client = SODAClient()
    try:
        results = await client.query(
            "i98e-djp9",
            where="neighborhoods_analysis_boundaries='Mission'",
            limit=5,
        )
        assert len(results) > 0, "Expected permits in Mission neighborhood"
        assert results[0]["neighborhoods_analysis_boundaries"] == "Mission"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_permit_by_number():
    """Verify single permit lookup by permit_number."""
    client = SODAClient()
    try:
        # First get any permit number
        results = await client.query("i98e-djp9", limit=1)
        assert len(results) > 0, "Expected at least one permit"
        permit_number = results[0]["permit_number"]

        # Then look it up
        detail = await client.query(
            "i98e-djp9",
            where=f"permit_number='{permit_number}'",
            limit=1,
        )
        assert len(detail) >= 1
        assert detail[0]["permit_number"] == permit_number
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_permit_stats_aggregation():
    """Verify SoQL aggregation (GROUP BY) works."""
    client = SODAClient()
    try:
        results = await client.query(
            "i98e-djp9",
            select="neighborhoods_analysis_boundaries, count(*) as total",
            group="neighborhoods_analysis_boundaries",
            order="total DESC",
            limit=10,
        )
        assert len(results) > 0, "Expected aggregation results"
        assert "total" in results[0], "Expected 'total' field in aggregation"
        assert int(results[0]["total"]) > 0
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_full_text_search():
    """Verify full-text search ($q) works."""
    client = SODAClient()
    try:
        results = await client.query(
            "i98e-djp9",
            q="solar",
            limit=10,
        )
        assert len(results) > 0, "Expected results for 'solar' search"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_business_locations_accessible():
    """Verify business locations dataset is accessible."""
    client = SODAClient()
    try:
        count = await client.count("g8m3-pdis")
        assert count > 100_000, f"Expected 100K+ businesses, got {count}"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_property_tax_rolls_accessible():
    """Verify property tax rolls dataset is accessible."""
    client = SODAClient()
    try:
        count = await client.count("wv5m-vpq2")
        assert count > 1_000_000, f"Expected 1M+ tax records, got {count}"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_schema_extraction():
    """Verify we can extract field names from a dataset."""
    client = SODAClient()
    try:
        fields = await client.schema("i98e-djp9")
        assert "permit_number" in fields
        assert "status" in fields
        assert "neighborhoods_analysis_boundaries" in fields
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cost_filtering():
    """Verify client-side cost filtering works (estimated_cost is text in SODA)."""
    from src.tools.search_permits import _filter_by_cost

    # estimated_cost is text in SODA — we filter client-side after fetching
    client = SODAClient()
    try:
        results = await client.query(
            "i98e-djp9",
            where="estimated_cost IS NOT NULL",
            order="filed_date DESC",
            limit=100,
        )
        assert len(results) > 0, "Expected permits with cost data"

        # Test client-side filtering
        filtered = _filter_by_cost(results, min_cost=100_000, max_cost=None)
        for r in filtered:
            assert float(r.get("estimated_cost", 0)) >= 100_000
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_date_filtering():
    """Verify date filtering works for filed_date."""
    client = SODAClient()
    try:
        results = await client.query(
            "i98e-djp9",
            where="filed_date >= '2026-01-01'",
            order="filed_date DESC",
            limit=5,
        )
        assert len(results) > 0, "Expected permits filed in 2026"
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Phase 1.5: DBI Enforcement datasets
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complaints_dataset_accessible():
    """Verify DBI complaints dataset is accessible and has expected volume."""
    client = SODAClient()
    try:
        count = await client.count("gm2e-bten")
        assert count > 100_000, f"Expected 100K+ complaints, got {count}"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_violations_dataset_accessible():
    """Verify NOV dataset is accessible and has expected volume."""
    client = SODAClient()
    try:
        count = await client.count("nbtm-fbw5")
        assert count > 100_000, f"Expected 100K+ violations, got {count}"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_inspections_dataset_accessible():
    """Verify inspections dataset is accessible and has expected volume."""
    client = SODAClient()
    try:
        count = await client.count("vckc-dh2h")
        assert count > 100_000, f"Expected 100K+ inspections, got {count}"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_search_complaints_by_block_lot():
    """Verify complaint filtering by block/lot returns expected fields."""
    client = SODAClient()
    try:
        results = await client.query(
            "gm2e-bten",
            where="block='0001'",
            order="date_filed DESC",
            limit=5,
        )
        assert len(results) > 0, "Expected complaints for block 0001"
        first = results[0]
        assert "complaint_number" in first
        assert "status" in first
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_search_violations_by_complaint():
    """Verify violation lookup by complaint_number returns NOV details."""
    client = SODAClient()
    try:
        # Get a complaint number that has violations
        results = await client.query(
            "nbtm-fbw5",
            order="date_filed DESC",
            limit=1,
        )
        assert len(results) > 0, "Expected at least one violation"
        first = results[0]
        assert "complaint_number" in first
        assert "status" in first

        # Look up by that complaint number
        complaint_num = first["complaint_number"]
        detail = await client.query(
            "nbtm-fbw5",
            where=f"complaint_number='{complaint_num}'",
            limit=5,
        )
        assert len(detail) >= 1
        assert detail[0]["complaint_number"] == complaint_num
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_search_inspections_by_permit():
    """Verify inspection lookup by permit reference_number returns expected fields."""
    client = SODAClient()
    try:
        results = await client.query(
            "vckc-dh2h",
            where="reference_number_type='permit'",
            order="scheduled_date DESC",
            limit=5,
        )
        assert len(results) > 0, "Expected permit-type inspections"
        first = results[0]
        assert "reference_number" in first
        assert "status" in first or "inspector" in first
    finally:
        await client.close()
