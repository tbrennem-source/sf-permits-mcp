"""Integration tests for SF Permits MCP tools.

These tests run against the live SODA API at data.sfgov.org.
They require network access but no authentication (app token optional).
"""

import pytest
from src.soda_client import SODAClient


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
