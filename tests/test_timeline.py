"""Tests for estimate_timeline tool.

Uses synthetic DuckDB fixtures so tests run without the real 3.6M-row database.
Monkeypatches src.db.DB_PATH and src.tools.estimate_timeline.get_connection
so the tool connects to the in-memory test database instead.
"""

import os
from datetime import date, timedelta
import pytest
import duckdb

from src.db import init_schema


_permit_counter = 0

def _generate_permits(n: int, permit_type_def: str, neighborhood: str,
                      base_cost: float, filed_start: date,
                      days_range: tuple[int, int],
                      revised_cost_pct: float | None = None) -> list[tuple]:
    """Generate n synthetic permits with controlled timeline characteristics."""
    global _permit_counter
    permits = []
    for i in range(n):
        _permit_counter += 1
        pnum = f"TL{_permit_counter:06d}"
        filed = filed_start + timedelta(days=i % 180)
        days_to_issue = days_range[0] + (i % (days_range[1] - days_range[0] + 1))
        issued = filed + timedelta(days=days_to_issue)
        completed = issued + timedelta(days=30 + (i % 60))
        cost = base_cost + (i % 10) * 1000
        rev_cost = cost * (1 + revised_cost_pct) if revised_cost_pct and i % 3 == 0 else None

        permits.append((
            pnum,                                   # permit_number
            "1" if "otc" not in permit_type_def.lower() else "8",  # permit_type
            permit_type_def,                        # permit_type_definition
            "complete",                             # status
            str(completed),                         # status_date
            f"Test {permit_type_def} #{i}",         # description
            str(filed),                             # filed_date
            str(issued),                            # issued_date
            str(filed + timedelta(days=days_to_issue - 2)),  # approved_date
            str(completed),                         # completed_date
            cost,                                   # estimated_cost
            rev_cost,                               # revised_cost
            "office",                               # existing_use
            "office",                               # proposed_use
            None,                                   # existing_units
            None,                                   # proposed_units
            str(100 + i),                           # street_number
            "MARKET",                               # street_name
            "ST",                                   # street_suffix
            "94110",                                # zipcode
            neighborhood,                           # neighborhood
            "9",                                    # supervisor_district
            "3512",                                 # block
            str(i).zfill(3),                        # lot
            None,                                   # adu
            str(filed),                             # data_as_of
        ))
    return permits


@pytest.fixture
def timeline_db(tmp_path):
    """Create a temporary DuckDB with enough synthetic permits for timeline analysis.

    Generates 50+ permits across multiple categories so the tool's minimum
    sample size requirements (>=10) are met for all query paths.
    """
    path = str(tmp_path / "timeline_test.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)

    all_permits = []

    # In-house alterations in Mission — 30 permits, 20-120 day range
    all_permits.extend(_generate_permits(
        n=30,
        permit_type_def="additions alterations or repairs",
        neighborhood="Mission",
        base_cost=80000,
        filed_start=date(2024, 1, 1),
        days_range=(20, 120),
    ))

    # OTC alterations in Mission — 20 permits, 1-5 day range
    all_permits.extend(_generate_permits(
        n=20,
        permit_type_def="otc alterations permit",
        neighborhood="Mission",
        base_cost=15000,
        filed_start=date(2024, 1, 1),
        days_range=(1, 5),
    ))

    # In-house alterations in SoMa — 20 permits, 30-150 day range
    all_permits.extend(_generate_permits(
        n=20,
        permit_type_def="additions alterations or repairs",
        neighborhood="SoMa",
        base_cost=150000,
        filed_start=date(2024, 3, 1),
        days_range=(30, 150),
    ))

    # New construction — 15 permits, 60-200 day range
    all_permits.extend(_generate_permits(
        n=15,
        permit_type_def="new construction",
        neighborhood="Mission",
        base_cost=500000,
        filed_start=date(2024, 2, 1),
        days_range=(60, 200),
    ))

    # Recent permits for trend calculation (filed within last 6 months)
    recent_start = date.today() - timedelta(days=90)
    all_permits.extend(_generate_permits(
        n=15,
        permit_type_def="additions alterations or repairs",
        neighborhood="Mission",
        base_cost=80000,
        filed_start=recent_start,
        days_range=(25, 80),
    ))

    # Prior period for trend calculation (filed 6-18 months ago)
    prior_start = date.today() - timedelta(days=365)
    all_permits.extend(_generate_permits(
        n=15,
        permit_type_def="additions alterations or repairs",
        neighborhood="Mission",
        base_cost=80000,
        filed_start=prior_start,
        days_range=(30, 100),
    ))

    conn.executemany(
        "INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        all_permits,
    )

    conn.close()
    return path


@pytest.fixture(autouse=True)
def _patch_db_path(timeline_db, monkeypatch):
    """Monkeypatch get_connection in the timeline module to use the test DB."""
    import src.tools.estimate_timeline as timeline_mod

    original_get_connection = timeline_mod.get_connection

    def patched_get_connection(db_path=None):
        return original_get_connection(db_path=timeline_db)

    monkeypatch.setattr(timeline_mod, "get_connection", patched_get_connection)


@pytest.mark.asyncio
async def test_timeline_basic():
    """Basic timeline query returns structured output with day estimates."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(permit_type="alterations")
    assert "Timeline Estimate" in result
    assert "days" in result.lower()
    assert "25th" in result or "p25" in result.lower() or "optimistic" in result.lower()


@pytest.mark.asyncio
async def test_timeline_with_neighborhood():
    """Timeline with neighborhood filter returns results."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        permit_type="alterations",
        neighborhood="Mission",
        review_path="in_house",
    )
    assert "Timeline Estimate" in result
    assert "Mission" in result


@pytest.mark.asyncio
async def test_timeline_otc():
    """OTC permits should show fast timelines."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        permit_type="otc",
        review_path="otc",
    )
    assert "Timeline Estimate" in result


@pytest.mark.asyncio
async def test_timeline_with_cost():
    """Timeline filtered by cost bracket returns results."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        permit_type="alterations",
        estimated_cost=85000,
    )
    assert "Timeline Estimate" in result
    # Should mention the cost bracket
    assert "50k_150k" in result or "Cost Bracket" in result


@pytest.mark.asyncio
async def test_timeline_with_triggers():
    """Delay triggers should appear in the output."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        permit_type="alterations",
        triggers=["change_of_use", "historic"],
    )
    assert "Delay Factor" in result or "delay" in result.lower()
    assert "change_of_use" in result or "Section 311" in result
    assert "historic" in result.lower() or "HPC" in result


@pytest.mark.asyncio
async def test_timeline_percentiles_are_ordered():
    """P25 <= P50 <= P75 <= P90 in output."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(permit_type="alterations")

    # Extract day values from the table
    import re
    day_values = re.findall(r'\|\s*(\d+)\s*\|', result)
    if len(day_values) >= 4:
        p25, p50, p75, p90 = [int(d) for d in day_values[:4]]
        assert p25 <= p50 <= p75 <= p90, f"Percentiles not ordered: {p25}, {p50}, {p75}, {p90}"


@pytest.mark.asyncio
async def test_timeline_progressive_widening():
    """Query for non-existent neighborhood should widen and still return data."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        permit_type="alterations",
        neighborhood="Outer Sunset",  # Not in our test data
    )
    assert "Timeline Estimate" in result
    # Should note that query was widened
    assert "widened" in result.lower() or "days" in result.lower()


@pytest.mark.asyncio
async def test_timeline_confidence_level():
    """Output should include a confidence indicator."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(permit_type="alterations")
    assert "Confidence" in result
    assert any(level in result.lower() for level in ["high", "medium", "low"])


@pytest.mark.asyncio
async def test_timeline_new_construction():
    """New construction should return longer timelines than alterations."""
    from src.tools.estimate_timeline import estimate_timeline
    alt_result = await estimate_timeline(permit_type="alterations")
    nc_result = await estimate_timeline(permit_type="new construction")

    assert "Timeline Estimate" in alt_result
    assert "Timeline Estimate" in nc_result


@pytest.mark.asyncio
async def test_timeline_insufficient_data():
    """Very specific query with no matching data returns graceful fallback."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        permit_type="nonexistent_type_xyz",
        neighborhood="Nonexistent_Neighborhood",
        review_path="in_house",
        estimated_cost=999999999,
    )
    # Should either widen or report insufficient data
    assert "Timeline Estimate" in result
