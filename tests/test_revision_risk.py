"""Tests for revision_risk tool.

These tests require the DuckDB database at data/sf_permits.duckdb.
Tests are skipped if the database is not available.
"""

import os
import pytest

DB_PATH = os.environ.get(
    "SF_PERMITS_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "sf_permits.duckdb"),
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(DB_PATH),
    reason="DuckDB database not available"
)


@pytest.mark.asyncio
async def test_revision_risk_basic():
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(permit_type="alterations")
    assert "Revision Risk" in result
    assert "Revision Rate" in result or "Insufficient data" in result


@pytest.mark.asyncio
async def test_revision_risk_with_neighborhood():
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(
        permit_type="alterations",
        neighborhood="Mission",
    )
    assert "Revision Risk" in result


@pytest.mark.asyncio
async def test_revision_risk_restaurant():
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(
        permit_type="alterations",
        project_type="restaurant",
    )
    assert "grease" in result.lower() or "hood" in result.lower() or "Common Revision" in result


@pytest.mark.asyncio
async def test_revision_risk_mitigation():
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(
        permit_type="alterations",
        project_type="adu",
    )
    assert "Mitigation" in result


@pytest.mark.asyncio
async def test_revision_risk_includes_timeline_impact():
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(permit_type="alterations")
    assert "Timeline Impact" in result or "days" in result.lower()
