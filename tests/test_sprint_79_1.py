"""Tests for QS8-T1-A: batch contacts/inspections + SODA response caching.

Covers:
  - _get_contacts_batch: groups contacts by permit_number in one query
  - _get_inspections_batch: groups inspections by permit_number in one query
  - SODA cache hit: second call returns cached data without hitting the API
  - SODA cache expired: stale cache triggers a new API call
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import duckdb
import pytest


# ---------------------------------------------------------------------------
# Fixtures — in-memory DuckDB with contacts + inspections tables
# ---------------------------------------------------------------------------


@pytest.fixture
def duck_contacts():
    """In-memory DuckDB with contacts and entities tables for batch tests."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE entities (
            entity_id TEXT PRIMARY KEY,
            canonical_name TEXT,
            canonical_firm TEXT,
            permit_count INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE contacts (
            permit_number TEXT,
            role TEXT,
            name TEXT,
            firm_name TEXT,
            entity_id TEXT
        )
    """)

    # Seed: 2 permits, multiple contacts each
    conn.execute("""
        INSERT INTO entities VALUES
            ('E1', 'Alice Smith', 'Smith Co', 42),
            ('E2', 'Bob Jones', 'Jones LLC', 15)
    """)
    conn.execute("""
        INSERT INTO contacts VALUES
            ('PA-001', 'applicant', 'Alice Smith', 'Smith Co', 'E1'),
            ('PA-001', 'contractor', 'Bob Jones', 'Jones LLC', 'E2'),
            ('PA-002', 'applicant', 'Alice Smith', 'Smith Co', 'E1')
    """)
    yield conn
    conn.close()


@pytest.fixture
def duck_inspections():
    """In-memory DuckDB with inspections table for batch tests."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE inspections (
            reference_number TEXT,
            scheduled_date TEXT,
            inspector TEXT,
            result TEXT,
            inspection_description TEXT
        )
    """)

    # Seed: 2 permits, multiple inspections each
    conn.execute("""
        INSERT INTO inspections VALUES
            ('PA-001', '2024-01-15', 'Inspector A', 'PASS', 'Framing'),
            ('PA-001', '2024-01-10', 'Inspector B', 'FAIL', 'Foundation'),
            ('PA-002', '2024-02-20', 'Inspector C', 'PASS', 'Electrical')
    """)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Tests: _get_contacts_batch
# ---------------------------------------------------------------------------


def test_get_contacts_batch_returns_grouped_dict(duck_contacts):
    """_get_contacts_batch returns a dict keyed by permit_number."""
    import importlib
    import src.db as db_mod

    # Ensure _exec uses DuckDB path
    original_backend = db_mod.BACKEND
    db_mod.BACKEND = "duckdb"

    # Patch the module-level _PH inside web.report for correct placeholders
    with patch("web.report._PH", "?"), patch("web.report.BACKEND", "duckdb"):
        from web.report import _get_contacts_batch

        result = _get_contacts_batch(duck_contacts, ["PA-001", "PA-002"])

    db_mod.BACKEND = original_backend

    # PA-001 has 2 contacts, PA-002 has 1
    assert "PA-001" in result
    assert "PA-002" in result
    assert len(result["PA-001"]) == 2
    assert len(result["PA-002"]) == 1

    # Check field structure
    contact = result["PA-001"][0]
    assert "role" in contact
    assert "name" in contact
    assert "canonical_name" in contact
    assert "permit_count" in contact


def test_get_contacts_batch_empty_list():
    """_get_contacts_batch returns empty dict for empty permit list."""
    with patch("web.report._PH", "?"), patch("web.report.BACKEND", "duckdb"):
        from web.report import _get_contacts_batch

        result = _get_contacts_batch(MagicMock(), [])

    assert result == {}


def test_get_contacts_batch_unknown_permit(duck_contacts):
    """_get_contacts_batch returns empty list for permit with no contacts."""
    with patch("web.report._PH", "?"), patch("web.report.BACKEND", "duckdb"):
        from web.report import _get_contacts_batch

        result = _get_contacts_batch(duck_contacts, ["PA-UNKNOWN"])

    assert result.get("PA-UNKNOWN", []) == []


def test_get_contacts_batch_role_ordering(duck_contacts):
    """Contacts for a permit are ordered by role priority (applicant first)."""
    with patch("web.report._PH", "?"), patch("web.report.BACKEND", "duckdb"):
        from web.report import _get_contacts_batch

        result = _get_contacts_batch(duck_contacts, ["PA-001"])

    contacts = result["PA-001"]
    # applicant should come before contractor
    roles = [c["role"] for c in contacts]
    assert roles.index("applicant") < roles.index("contractor")


# ---------------------------------------------------------------------------
# Tests: _get_inspections_batch
# ---------------------------------------------------------------------------


def test_get_inspections_batch_returns_grouped_dict(duck_inspections):
    """_get_inspections_batch returns a dict keyed by permit_number."""
    with patch("web.report._PH", "?"), patch("web.report.BACKEND", "duckdb"):
        from web.report import _get_inspections_batch

        result = _get_inspections_batch(duck_inspections, ["PA-001", "PA-002"])

    assert "PA-001" in result
    assert "PA-002" in result
    assert len(result["PA-001"]) == 2
    assert len(result["PA-002"]) == 1

    inspection = result["PA-001"][0]
    assert "scheduled_date" in inspection
    assert "inspector" in inspection
    assert "result" in inspection
    assert "description" in inspection


def test_get_inspections_batch_empty_list():
    """_get_inspections_batch returns empty dict for empty permit list."""
    with patch("web.report._PH", "?"), patch("web.report.BACKEND", "duckdb"):
        from web.report import _get_inspections_batch

        result = _get_inspections_batch(MagicMock(), [])

    assert result == {}


def test_get_inspections_batch_unknown_permit(duck_inspections):
    """_get_inspections_batch returns empty list for permit with no inspections."""
    with patch("web.report._PH", "?"), patch("web.report.BACKEND", "duckdb"):
        from web.report import _get_inspections_batch

        result = _get_inspections_batch(duck_inspections, ["PA-NONE"])

    assert result.get("PA-NONE", []) == []


# ---------------------------------------------------------------------------
# Tests: SODA response cache
# ---------------------------------------------------------------------------


def test_soda_cache_hit_skips_api_call():
    """Second call to _fetch_complaints within TTL returns cached data without API call."""
    import web.report as report_mod

    # Clear the cache first
    report_mod._soda_cache.clear()

    call_count = 0

    async def run():
        nonlocal call_count

        async def fake_query(**kwargs):
            nonlocal call_count
            call_count += 1
            return [{"complaint_number": "C1", "status": "OPEN"}]

        mock_client = MagicMock()
        mock_client.query = fake_query

        # First call — populates cache
        result1 = await report_mod._fetch_complaints(mock_client, "2991", "012")
        # Second call — should hit cache
        result2 = await report_mod._fetch_complaints(mock_client, "2991", "012")
        return result1, result2

    result1, result2 = asyncio.run(run())

    assert call_count == 1, "API should only be called once; second call must use cache"
    assert result1 == result2
    assert result1[0]["complaint_number"] == "C1"

    # Cleanup
    report_mod._soda_cache.clear()


def test_soda_cache_expired_makes_new_api_call():
    """Expired cache entry triggers a fresh API call."""
    import web.report as report_mod

    # Clear and pre-populate with an expired entry
    report_mod._soda_cache.clear()
    cache_key = "gm2e-bten:2991:012"
    stale_ts = time.monotonic() - report_mod._SODA_CACHE_TTL - 1  # expired 1s ago
    report_mod._soda_cache[cache_key] = (stale_ts, [{"complaint_number": "OLD"}])

    call_count = 0

    async def run():
        nonlocal call_count

        async def fake_query(**kwargs):
            nonlocal call_count
            call_count += 1
            return [{"complaint_number": "NEW"}]

        mock_client = MagicMock()
        mock_client.query = fake_query

        result = await report_mod._fetch_complaints(mock_client, "2991", "012")
        return result

    result = asyncio.run(run())

    assert call_count == 1, "Expired cache should trigger new API call"
    assert result[0]["complaint_number"] == "NEW"

    # Cleanup
    report_mod._soda_cache.clear()


def test_soda_cache_violations_hit_skips_api_call():
    """Cache hit works for violations endpoint too."""
    import web.report as report_mod

    report_mod._soda_cache.clear()

    call_count = 0

    async def run():
        nonlocal call_count

        async def fake_query(**kwargs):
            nonlocal call_count
            call_count += 1
            return [{"violation_type": "V1"}]

        mock_client = MagicMock()
        mock_client.query = fake_query

        await report_mod._fetch_violations(mock_client, "1234", "005")
        await report_mod._fetch_violations(mock_client, "1234", "005")

    asyncio.run(run())

    assert call_count == 1

    report_mod._soda_cache.clear()


def test_soda_cache_property_hit_skips_api_call():
    """Cache hit works for property endpoint too."""
    import web.report as report_mod

    report_mod._soda_cache.clear()

    call_count = 0

    async def run():
        nonlocal call_count

        async def fake_query(**kwargs):
            nonlocal call_count
            call_count += 1
            return [{"zoning_code": "RH-1"}]

        mock_client = MagicMock()
        mock_client.query = fake_query

        await report_mod._fetch_property(mock_client, "3001", "010")
        await report_mod._fetch_property(mock_client, "3001", "010")

    asyncio.run(run())

    assert call_count == 1

    report_mod._soda_cache.clear()
