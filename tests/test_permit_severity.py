"""Integration tests for permit_severity MCP tool.

Uses synthetic DuckDB fixtures (same pattern as test_revision_risk.py).
Monkeypatches get_connection so the tool connects to a temporary test database.
"""

from datetime import date, timedelta

import duckdb
import pytest

from src.db import init_schema


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def severity_db(tmp_path):
    """Create a temporary DuckDB with synthetic permits + inspections."""
    path = str(tmp_path / "severity_test.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)

    today = date(2026, 2, 23)

    # Permit 1: Old, expired, seismic, no inspections → should be CRITICAL
    permits = [
        (
            "SEV001", "1", "additions alterations or repairs", "issued",
            str(today - timedelta(days=300)),
            "seismic retrofit of soft story building",
            str(today - timedelta(days=1500)),  # filed 1500d ago
            str(today - timedelta(days=400)),   # issued 400d ago (expired for $50k)
            str(today - timedelta(days=410)),
            None,  # not completed
            50000, None,
            "apartments", "apartments",
            None, None,
            "100", "MARKET", "ST", "94105",
            "SoMa", "6", "3512", "001", None, str(today),
        ),
        # Permit 2: Fresh, low-cost, just filed → should be GREEN
        (
            "SEV002", "8", "otc alterations permit", "filed",
            str(today - timedelta(days=5)),
            "replace window in bedroom",
            str(today - timedelta(days=5)),  # filed 5d ago
            None, None, None,
            5000, None,
            "1 family dwelling", "1 family dwelling",
            None, None,
            "200", "VALENCIA", "ST", "94110",
            "Mission", "9", "3600", "010", None, str(today),
        ),
        # Permit 3: Issued, medium age, some inspections → should be MEDIUM or LOW
        (
            "SEV003", "1", "additions alterations or repairs", "issued",
            str(today - timedelta(days=30)),
            "kitchen remodel with new cabinets and counters",
            str(today - timedelta(days=200)),
            str(today - timedelta(days=60)),
            str(today - timedelta(days=65)),
            None,
            120000, None,
            "1 family dwelling", "1 family dwelling",
            None, None,
            "300", "CASTRO", "ST", "94114",
            "Castro/Upper Market", "8", "3700", "020", None, str(today),
        ),
    ]

    conn.executemany(
        "INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        permits,
    )

    # Inspections for SEV003 (kitchen remodel — 2 inspections)
    inspections = [
        (1, "SEV003", "PERMIT", "SMITH J", str(today - timedelta(days=20)),
         "approved", "Rough plumbing",
         "3700", "020", "300", "CASTRO", "ST", "Castro/Upper Market", "8", "94114",
         str(today), "building"),
        (2, "SEV003", "PERMIT", "JONES K", str(today - timedelta(days=10)),
         "approved", "Rough electrical",
         "3700", "020", "300", "CASTRO", "ST", "Castro/Upper Market", "8", "94114",
         str(today), "building"),
    ]

    conn.executemany(
        "INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        inspections,
    )

    conn.close()
    return path


@pytest.fixture(autouse=True)
def _patch_db_path(severity_db, monkeypatch):
    """Monkeypatch get_connection in permit_severity module to use the test DB."""
    import src.tools.permit_severity as sev_mod

    original_get_connection = sev_mod.get_connection

    def patched_get_connection(db_path=None):
        return original_get_connection(db_path=severity_db)

    monkeypatch.setattr(sev_mod, "get_connection", patched_get_connection)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_severity_by_permit_number():
    """Scoring by permit number returns structured markdown."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(permit_number="SEV001")
    assert "Severity Score" in result
    assert "SEV001" in result
    assert "CRITICAL" in result or "HIGH" in result


@pytest.mark.asyncio
async def test_severity_critical_permit():
    """Expired, old, life-safety permit should be CRITICAL."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(permit_number="SEV001")
    assert "CRITICAL" in result
    assert "Dimension Breakdown" in result


@pytest.mark.asyncio
async def test_severity_green_permit():
    """Fresh, low-cost, just-filed permit should be GREEN."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(permit_number="SEV002")
    assert "GREEN" in result


@pytest.mark.asyncio
async def test_severity_by_address():
    """Scoring by address returns results."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(street_number="200", street_name="VALENCIA")
    assert "Severity Score" in result
    assert "SEV002" in result


@pytest.mark.asyncio
async def test_severity_by_block_lot():
    """Scoring by block/lot returns results."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(block="3700", lot="020")
    assert "Severity Score" in result
    assert "SEV003" in result


@pytest.mark.asyncio
async def test_severity_not_found():
    """Non-existent permit returns helpful message."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(permit_number="NONEXISTENT")
    assert "No permit found" in result


@pytest.mark.asyncio
async def test_severity_no_input():
    """No input returns usage message."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity()
    assert "Please provide" in result


@pytest.mark.asyncio
async def test_severity_includes_dimensions():
    """Output includes the dimension breakdown table."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(permit_number="SEV001")
    assert "Inspection Activity" in result
    assert "Age / Staleness" in result
    assert "Expiration Proximity" in result
    assert "Cost Tier" in result
    assert "Category Risk" in result


@pytest.mark.asyncio
async def test_severity_includes_recommendations():
    """Output includes recommendations section."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(permit_number="SEV001")
    assert "Recommendations" in result


@pytest.mark.asyncio
async def test_severity_includes_confidence():
    """Output includes confidence level."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(permit_number="SEV003")
    assert "Confidence" in result


@pytest.mark.asyncio
async def test_severity_with_inspections():
    """Permit with inspections reflects them in the score."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(permit_number="SEV003")
    assert "Inspections:** 2" in result


@pytest.mark.asyncio
async def test_severity_markdown_format():
    """Output is valid markdown with headers and tables."""
    from src.tools.permit_severity import permit_severity
    result = await permit_severity(permit_number="SEV001")
    assert result.startswith("# ")
    assert "| Dimension |" in result
    assert "|-----------|" in result


@pytest.mark.asyncio
async def test_severity_db_unavailable(monkeypatch):
    """When DB is unavailable, returns graceful error."""
    import src.tools.permit_severity as sev_mod

    def broken_connection(db_path=None):
        raise ConnectionError("DB is down")

    monkeypatch.setattr(sev_mod, "get_connection", broken_connection)

    from src.tools.permit_severity import permit_severity
    result = await permit_severity(permit_number="SEV001")
    assert "unavailable" in result.lower()
