"""Tests for addenda routing integration.

Tests:
- _normalize_addenda() field extraction
- _format_addenda() markdown output
- search_addenda() input validation
- _get_addenda() enrichment in permit_lookup
- DBI permit details link generation
- Brief plan_reviews key
"""

import pytest
from unittest.mock import patch, MagicMock


# ── Normalization tests ──────────────────────────────────────────


def test_normalize_addenda_basic():
    from src.ingest import _normalize_addenda
    record = {
        "primary_key": "PK001",
        "application_number": "202509155257",
        "addenda_number": "0",
        "step": "3",
        "station": "BLDG",
        "arrive": "2025-09-15T00:00:00.000",
        "assign_date": "2025-09-20T00:00:00.000",
        "start_date": "2025-09-25T00:00:00.000",
        "finish_date": "2025-10-01T00:00:00.000",
        "approved_date": None,
        "plan_checked_by": "SMITH JOHN",
        "review_results": "Approved",
        "hold_description": None,
        "addenda_status": "filed",
        "department": "DBI",
        "title": "full",
        "data_as_of": "2026-02-18",
    }
    result = _normalize_addenda(record, 1)
    assert result[0] == 1  # row_id
    assert result[1] == "PK001"  # primary_key
    assert result[2] == "202509155257"  # application_number
    assert result[3] == 0  # addenda_number (int)
    assert result[4] == 3  # step (int)
    assert result[5] == "BLDG"  # station
    assert result[11] == "SMITH JOHN"  # plan_checked_by
    assert result[12] == "Approved"  # review_results
    assert result[14] == "filed"  # addenda_status
    assert result[15] == "DBI"  # department
    assert result[16] == "full"  # title


def test_normalize_addenda_null_fields():
    from src.ingest import _normalize_addenda
    record = {"application_number": "P001"}
    result = _normalize_addenda(record, 1)
    assert result[2] == "P001"
    assert result[3] is None  # addenda_number
    assert result[4] is None  # step
    assert result[5] is None  # station
    assert result[11] is None  # plan_checked_by
    assert result[12] is None  # review_results


def test_normalize_addenda_strips_whitespace():
    from src.ingest import _normalize_addenda
    record = {
        "application_number": "P001",
        "station": "  BLDG  ",
        "plan_checked_by": "  SMITH JOHN  ",
        "review_results": "  Approved  ",
    }
    result = _normalize_addenda(record, 1)
    assert result[5] == "BLDG"
    assert result[11] == "SMITH JOHN"
    assert result[12] == "Approved"


def test_normalize_addenda_empty_string_to_none():
    from src.ingest import _normalize_addenda
    record = {
        "application_number": "P001",
        "station": "",
        "plan_checked_by": "",
    }
    result = _normalize_addenda(record, 1)
    assert result[5] is None  # empty string → None
    assert result[11] is None


# ── Format tests ─────────────────────────────────────────────────


def test_format_addenda_empty():
    from src.tools.permit_lookup import _format_addenda
    result = _format_addenda([])
    assert "No plan review routing" in result


def test_format_addenda_basic():
    from src.tools.permit_lookup import _format_addenda
    addenda = [{
        "addenda_number": 0,
        "step": 1,
        "station": "BLDG",
        "reviewer": "SOENKSEN RICHARD",
        "result": "Approved",
        "finish_date": "2026-02-17T00:00:00",
        "notes": "Approved REV#2 in BB session",
        "department": "DBI",
        "arrive": "2025-09-15",
        "start_date": "2025-09-20",
    }]
    md = _format_addenda(addenda)
    assert "BLDG" in md
    assert "SOENKSEN RICHARD" in md
    assert "Approved" in md
    assert "1 routing steps" in md
    assert "1 stations" in md
    assert "1 completed" in md
    assert "0 pending" in md


def test_format_addenda_with_pending():
    from src.tools.permit_lookup import _format_addenda
    addenda = [
        {
            "addenda_number": 0, "step": 1, "station": "BLDG",
            "reviewer": "SMITH J", "result": "Approved",
            "finish_date": "2025-10-01", "notes": None,
            "department": "DBI", "arrive": None, "start_date": None,
        },
        {
            "addenda_number": 1, "step": 2, "station": "MECH",
            "reviewer": "JONES K", "result": None,
            "finish_date": None, "notes": None,
            "department": "DBI", "arrive": "2025-10-05", "start_date": None,
        },
    ]
    md = _format_addenda(addenda)
    assert "2 routing steps" in md
    assert "1 completed" in md
    assert "1 pending" in md


def test_format_addenda_truncates_long_notes():
    from src.tools.permit_lookup import _format_addenda
    addenda = [{
        "addenda_number": 0, "step": 1, "station": "BLDG",
        "reviewer": "SMITH J", "result": "Issued Comments",
        "finish_date": "2025-10-01", "notes": "A" * 200,
        "department": "DBI", "arrive": None, "start_date": None,
    }]
    md = _format_addenda(addenda)
    assert "..." in md


# ── search_addenda tool tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_search_addenda_no_input():
    from src.tools.search_addenda import search_addenda
    result = await search_addenda()
    assert "provide" in result.lower()


@pytest.mark.asyncio
async def test_search_addenda_by_permit():
    """Test search_addenda with a mocked database connection."""
    with patch("src.tools.search_addenda.get_connection") as mock_conn_fn:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn

        # Mock the DuckDB execute().fetchall() pattern
        mock_conn.execute.return_value.fetchall.return_value = [
            ("P001", 0, 1, "BLDG", "SMITH J", "Approved", "2025-10-01",
             "Test notes", "DBI", "2025-09-15", "2025-09-20", "filed", "full"),
        ]

        with patch("src.tools.search_addenda.BACKEND", "duckdb"), \
             patch("src.tools.search_addenda._PH", "?"):
            from src.tools.search_addenda import search_addenda
            result = await search_addenda(permit_number="P001")

        assert "P001" in result
        assert "BLDG" in result
        assert "SMITH J" in result
        mock_conn.close.assert_called_once()


# ── Report links tests ───────────────────────────────────────────


def test_dbi_permit_details_link():
    from src.report_links import ReportLinks
    url = ReportLinks.dbi_permit_details("202509155257")
    assert "dbiweb02.sfgov.org" in url
    assert "PermitDetails" in url
    assert "202509155257" in url


def test_dbi_permit_details_link_special_chars():
    from src.report_links import ReportLinks
    url = ReportLinks.dbi_permit_details("PERMIT 123")
    assert "PERMIT" in url
    # URL-encoded space
    assert "+" in url or "%20" in url


# ── permit_lookup _get_addenda test ──────────────────────────────


def test_get_addenda_returns_dicts():
    """Test _get_addenda returns properly structured dicts."""
    with patch("src.tools.permit_lookup.BACKEND", "duckdb"), \
         patch("src.tools.permit_lookup._PH", "?"):
        from src.tools.permit_lookup import _get_addenda

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            (0, 1, "BLDG", "SMITH J", "Approved", "2025-10-01",
             "Notes here", "DBI", "2025-09-15", "2025-09-20"),
        ]

        result = _get_addenda(mock_conn, "P001")
        assert len(result) == 1
        assert result[0]["station"] == "BLDG"
        assert result[0]["reviewer"] == "SMITH J"
        assert result[0]["result"] == "Approved"
        assert result[0]["addenda_number"] == 0


# ── Brief integration test ───────────────────────────────────────


def test_brief_includes_plan_reviews_key():
    """Verify get_morning_brief returns plan_reviews key."""
    with patch("web.brief.query") as mock_query, \
         patch("web.brief.query_one") as mock_query_one:
        # Mock all queries to return empty results
        mock_query.return_value = []
        mock_query_one.return_value = None

        from web.brief import get_morning_brief
        result = get_morning_brief(user_id=1, lookback_days=1)

        assert "plan_reviews" in result
        assert isinstance(result["plan_reviews"], list)
        assert "plan_reviews_count" in result["summary"]


# ── SODA API smoke test (requires network) ───────────────────────


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires network access — run manually with pytest -k test_addenda_soda")
async def test_addenda_soda_accessible():
    """Verify the addenda SODA dataset is accessible and has expected fields."""
    from src.soda_client import SODAClient
    client = SODAClient()
    try:
        records = await client.query(
            endpoint_id="87xy-gk8d",
            limit=1,
        )
        assert len(records) > 0
        record = records[0]
        # Check expected fields exist
        assert "application_number" in record
        assert "station" in record or "primary_key" in record
    finally:
        await client.close()
