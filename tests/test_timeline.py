"""Tests for estimate_timeline tool.

These tests require the DuckDB database at data/sf_permits.duckdb.
Tests are skipped if the database is not available.
"""

import os
import pytest
import duckdb

DB_PATH = os.environ.get(
    "SF_PERMITS_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "sf_permits.duckdb"),
)

# Skip all tests in this module if DuckDB is not available
pytestmark = pytest.mark.skipif(
    not os.path.exists(DB_PATH),
    reason="DuckDB database not available"
)


@pytest.mark.asyncio
async def test_timeline_basic():
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(permit_type="alterations")
    assert "Timeline Estimate" in result
    assert "days" in result.lower()


@pytest.mark.asyncio
async def test_timeline_with_neighborhood():
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        permit_type="alterations",
        neighborhood="Mission",
        review_path="in_house",
    )
    assert "Timeline Estimate" in result


@pytest.mark.asyncio
async def test_timeline_otc():
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        permit_type="otc",
        review_path="otc",
    )
    assert "Timeline Estimate" in result


@pytest.mark.asyncio
async def test_timeline_with_cost():
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        permit_type="alterations",
        estimated_cost=85000,
    )
    assert "Timeline Estimate" in result


@pytest.mark.asyncio
async def test_timeline_with_triggers():
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        permit_type="alterations",
        triggers=["change_of_use", "historic"],
    )
    assert "Delay Factor" in result or "delay" in result.lower()
