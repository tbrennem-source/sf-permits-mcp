"""Tests for revision_risk tool.

Uses synthetic DuckDB fixtures so tests run without the real 3.6M-row database.
Monkeypatches get_connection so the tool connects to a temporary test database.
"""

import os
from datetime import date, timedelta
import pytest
import duckdb

from src.db import init_schema


_revision_counter_holder = [0]

def _generate_permits_with_revisions(
    n: int,
    permit_type_def: str,
    neighborhood: str,
    base_cost: float,
    filed_start: date,
    days_range: tuple[int, int],
    revision_rate: float = 0.25,
    cost_increase_pct: float = 0.15,
) -> list[tuple]:
    """Generate n synthetic permits where `revision_rate` fraction have cost increases.

    Args:
        revision_rate: Fraction of permits that get revised_cost > estimated_cost
        cost_increase_pct: How much revised_cost exceeds estimated_cost (as fraction)
    """
    permits = []
    for i in range(n):
        _revision_counter_holder[0] += 1
        pnum = f"RR{_revision_counter_holder[0]:06d}"
        filed = filed_start + timedelta(days=i % 180)
        has_revision = (i / n) < revision_rate
        # Permits with revisions take longer
        if has_revision:
            days_to_issue = days_range[1] + 20 + (i % 30)
        else:
            days_to_issue = days_range[0] + (i % (days_range[1] - days_range[0] + 1))

        issued = filed + timedelta(days=days_to_issue)
        completed = issued + timedelta(days=30 + (i % 60))
        cost = base_cost + (i % 10) * 1000
        rev_cost = cost * (1 + cost_increase_pct) if has_revision else None

        permits.append((
            pnum,                                   # permit_number
            "1" if "otc" not in permit_type_def.lower() else "8",  # permit_type
            permit_type_def,                        # permit_type_definition
            "complete",                             # status
            str(completed),                         # status_date
            f"Test {permit_type_def} #{i}",         # description
            str(filed),                             # filed_date
            str(issued),                            # issued_date
            str(filed + timedelta(days=max(days_to_issue - 2, 1))),  # approved_date
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
def revision_db(tmp_path):
    """Create a temporary DuckDB with synthetic permits that have revision patterns.

    Generates 50+ permits with controlled revision rates so the tool's
    minimum sample size requirements (>=20) are met.
    """
    path = str(tmp_path / "revision_test.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)

    all_permits = []

    # Alterations in Mission — 30 permits, 25% revision rate
    all_permits.extend(_generate_permits_with_revisions(
        n=30,
        permit_type_def="additions alterations or repairs",
        neighborhood="Mission",
        base_cost=80000,
        filed_start=date(2024, 1, 1),
        days_range=(20, 90),
        revision_rate=0.25,
        cost_increase_pct=0.15,
    ))

    # OTC — 20 permits, very low revision rate
    all_permits.extend(_generate_permits_with_revisions(
        n=20,
        permit_type_def="otc alterations permit",
        neighborhood="Mission",
        base_cost=15000,
        filed_start=date(2024, 1, 1),
        days_range=(1, 5),
        revision_rate=0.05,
        cost_increase_pct=0.05,
    ))

    # Alterations in SoMa — 25 permits, higher revision rate
    all_permits.extend(_generate_permits_with_revisions(
        n=25,
        permit_type_def="additions alterations or repairs",
        neighborhood="SoMa",
        base_cost=150000,
        filed_start=date(2024, 3, 1),
        days_range=(30, 120),
        revision_rate=0.30,
        cost_increase_pct=0.20,
    ))

    conn.executemany(
        "INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        all_permits,
    )

    conn.close()
    return path


@pytest.fixture(autouse=True)
def _patch_db_path(revision_db, monkeypatch):
    """Monkeypatch get_connection in the revision_risk module to use the test DB."""
    import src.tools.revision_risk as rr_mod

    original_get_connection = rr_mod.get_connection

    def patched_get_connection(db_path=None):
        return original_get_connection(db_path=revision_db)

    monkeypatch.setattr(rr_mod, "get_connection", patched_get_connection)


@pytest.mark.asyncio
async def test_revision_risk_basic():
    """Basic revision risk query returns structured output."""
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(permit_type="alterations")
    assert "Revision Risk" in result
    assert "Revision Rate" in result or "Insufficient data" in result


@pytest.mark.asyncio
async def test_revision_risk_with_neighborhood():
    """Revision risk with neighborhood filter returns results."""
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(
        permit_type="alterations",
        neighborhood="Mission",
    )
    assert "Revision Risk" in result
    assert "Mission" in result


@pytest.mark.asyncio
async def test_revision_risk_restaurant():
    """Restaurant project type includes domain-specific triggers."""
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(
        permit_type="alterations",
        project_type="restaurant",
    )
    # Should include restaurant-specific revision triggers
    assert "grease" in result.lower() or "hood" in result.lower() or "Common Revision" in result


@pytest.mark.asyncio
async def test_revision_risk_mitigation():
    """Output includes mitigation strategies."""
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(
        permit_type="alterations",
        project_type="adu",
    )
    assert "Mitigation" in result


@pytest.mark.asyncio
async def test_revision_risk_includes_timeline_impact():
    """Output includes timeline impact data."""
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(permit_type="alterations")
    assert "Timeline Impact" in result or "days" in result.lower()


@pytest.mark.asyncio
async def test_revision_risk_classification():
    """Risk level should be HIGH, MODERATE, or LOW."""
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(permit_type="alterations")
    assert any(level in result for level in ["HIGH", "MODERATE", "LOW"])


@pytest.mark.asyncio
async def test_revision_risk_progressive_widening():
    """Query for non-existent neighborhood should widen and still return data."""
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(
        permit_type="alterations",
        neighborhood="Outer Sunset",  # Not in our test data
    )
    assert "Revision Risk" in result
    # Should note that query was widened OR return data from broader query
    assert "widened" in result.lower() or "Revision Rate" in result or "Insufficient data" in result


@pytest.mark.asyncio
async def test_revision_risk_confidence_level():
    """Output should include a confidence indicator."""
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(permit_type="alterations")
    assert "Confidence" in result
    assert any(level in result.lower() for level in ["high", "medium", "low"])


@pytest.mark.asyncio
async def test_revision_risk_commercial_ti():
    """Commercial TI project type includes ADA/accessibility triggers."""
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(
        permit_type="alterations",
        project_type="commercial_ti",
    )
    assert "Mitigation" in result
    # Should mention DA-02 or ADA
    assert "DA-02" in result or "ADA" in result or "accessibility" in result.lower() or "access" in result.lower()


@pytest.mark.asyncio
async def test_revision_risk_correction_categories():
    """Output includes correction frequency data from knowledge base."""
    from src.tools.revision_risk import revision_risk
    result = await revision_risk(
        permit_type="alterations",
        project_type="restaurant",
    )
    # Should include correction categories from the knowledge base
    assert "Title-24" in result or "Energy" in result or "Correction" in result
