"""Tests for permit_lookup module.

Uses mock-based tests (same pattern as test_team_lookup.py).
Tests input validation, all 3 lookup modes, enrichment formatting,
and the main permit_lookup() entry point.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.tools.permit_lookup import (
    _row_to_dict,
    _format_permit_detail,
    _format_contacts,
    _format_inspections,
    _format_related,
    _format_permit_list,
    _lookup_by_number,
    _lookup_by_address,
    _lookup_by_block_lot,
    _find_historical_lots,
    _get_contacts,
    _get_inspections,
    _get_timeline,
    _get_related_location,
    _get_related_team,
    permit_lookup,
    PERMIT_COLS,
)


# ---------------------------------------------------------------------------
# _row_to_dict
# ---------------------------------------------------------------------------

def test_row_to_dict_basic():
    row = ("P001", "1", "alterations", "issued", "2024-01-15",
           "Kitchen remodel", "2023-06-01", "2024-01-10", "2024-01-09",
           None, 85000.0, None, "office", "office", 1, 1,
           "123", "Main", "St", "94110", "Mission",
           "9", "3512", "001", None, "2024-12-01")
    d = _row_to_dict(row)
    assert d["permit_number"] == "P001"
    assert d["status"] == "issued"
    assert d["estimated_cost"] == 85000.0
    assert d["block"] == "3512"
    assert d["lot"] == "001"


def test_row_to_dict_short_row():
    """If row is shorter than cols, only maps available columns."""
    row = ("P002", "2", "new_construction")
    d = _row_to_dict(row)
    assert d["permit_number"] == "P002"
    assert d["permit_type_definition"] == "new_construction"
    assert len(d) == 3


# ---------------------------------------------------------------------------
# _format_permit_detail
# ---------------------------------------------------------------------------

def test_format_detail_basic():
    p = {
        "permit_number": "202301015555",
        "permit_type": "1",
        "permit_type_definition": "otc alterations permit",
        "status": "issued",
        "status_date": "2024-03-15",
        "description": "Remodel kitchen",
        "filed_date": "2023-06-01",
        "issued_date": "2024-03-15",
        "approved_date": None,
        "completed_date": None,
        "estimated_cost": 85000.0,
        "revised_cost": None,
        "existing_use": "apartments",
        "proposed_use": "apartments",
        "existing_units": 1,
        "proposed_units": 1,
        "street_number": "123",
        "street_name": "Main",
        "street_suffix": "St",
        "zipcode": "94110",
        "neighborhood": "Mission",
        "supervisor_district": "9",
        "block": "3512",
        "lot": "001",
        "adu": None,
        "data_as_of": "2024-12-01",
    }
    md = _format_permit_detail(p)
    assert "202301015555" in md
    assert "otc alterations permit" in md
    assert "issued" in md
    assert "$85,000" in md
    assert "123 Main St" in md
    assert "Mission" in md
    assert "Block 3512" in md


def test_format_detail_long_description_truncated():
    p = {
        "permit_number": "P001",
        "permit_type_definition": "alteration",
        "status": "filed",
        "description": "x" * 300,
    }
    md = _format_permit_detail(p)
    assert "..." in md
    assert len(md) < 500  # Truncated, not full 300 chars


def test_format_detail_missing_fields():
    """Handles None/missing fields gracefully."""
    p = {
        "permit_number": "P002",
        "permit_type_definition": None,
        "permit_type": None,
        "status": None,
    }
    md = _format_permit_detail(p)
    assert "P002" in md
    assert "Unknown" in md  # Falls back for None type/status


# ---------------------------------------------------------------------------
# _format_contacts
# ---------------------------------------------------------------------------

def test_format_contacts_empty():
    assert "No team contacts" in _format_contacts([])


def test_format_contacts_basic():
    contacts = [
        {
            "role": "contractor",
            "name": "John Smith",
            "firm_name": "Smith Builders",
            "entity_id": 1,
            "canonical_name": "John Smith",
            "canonical_firm": "Smith Builders Inc",
            "permit_count": 47,
        },
        {
            "role": "architect",
            "name": "Jane Doe",
            "firm_name": None,
            "entity_id": 2,
            "canonical_name": "Jane Doe",
            "canonical_firm": None,
            "permit_count": 12,
        },
    ]
    md = _format_contacts(contacts)
    assert "John Smith" in md
    assert "Smith Builders Inc" in md
    assert "47" in md
    assert "Jane Doe" in md
    assert "12" in md


def test_format_contacts_no_entity():
    """Contacts without entity enrichment still display."""
    contacts = [{
        "role": "applicant",
        "name": "Bob Owner",
        "firm_name": None,
        "entity_id": None,
        "canonical_name": None,
        "canonical_firm": None,
        "permit_count": None,
    }]
    md = _format_contacts(contacts)
    assert "Bob Owner" in md
    assert "Applicant" in md


# ---------------------------------------------------------------------------
# _format_inspections
# ---------------------------------------------------------------------------

def test_format_inspections_empty():
    assert "No inspections" in _format_inspections([])


def test_format_inspections_basic():
    inspections = [
        {
            "scheduled_date": "2024-06-15",
            "inspector": "J. Torres",
            "result": "Approved",
            "description": "Rough plumbing inspection",
        },
        {
            "scheduled_date": "2024-07-01",
            "inspector": "M. Chen",
            "result": "Disapproved",
            "description": "Electrical wiring check — failed due to exposed junction box",
        },
    ]
    md = _format_inspections(inspections)
    assert "J. Torres" in md
    assert "Approved" in md
    assert "M. Chen" in md
    assert "Disapproved" in md
    assert "| Date |" in md  # Table header


def test_format_inspections_caps_at_30():
    """More than 30 inspections shows truncation notice."""
    inspections = [
        {"scheduled_date": f"2024-01-{i:02d}", "inspector": "X", "result": "OK", "description": "test"}
        for i in range(1, 36)
    ]
    md = _format_inspections(inspections)
    assert "Showing 30 of 35" in md


# ---------------------------------------------------------------------------
# _format_related
# ---------------------------------------------------------------------------

def test_format_related_both_empty():
    md = _format_related([], [], "3512", "001")
    assert "No other permits found" in md
    assert "No related permits found via shared team members" in md


def test_format_related_with_location():
    location = [{
        "permit_number": "P999",
        "type": "alterations",
        "status": "complete",
        "filed_date": "2023-01-01",
        "cost": 50000.0,
        "description": "Bathroom remodel",
    }]
    md = _format_related(location, [], "3512", "001")
    assert "P999" in md
    assert "1" in md  # "Found 1 other permits"
    assert "Block 3512" in md


def test_format_related_with_team():
    team = [{
        "permit_number": "P888",
        "type": "new construction",
        "status": "issued",
        "filed_date": "2024-01-01",
        "cost": 200000.0,
        "description": "New building",
        "shared_entity": "John Smith",
        "shared_role": "Contractor",
    }]
    md = _format_related([], team, None, None)
    assert "P888" in md
    assert "John Smith" in md


def test_format_related_no_block_lot():
    """No block/lot means no location section header."""
    md = _format_related([], [], None, None)
    assert "Same Location" not in md
    assert "Same Team Members" in md


# ---------------------------------------------------------------------------
# _format_permit_list
# ---------------------------------------------------------------------------

def test_format_permit_list():
    permits = [
        {
            "permit_number": "P001",
            "permit_type_definition": "alterations",
            "status": "issued",
            "filed_date": "2024-01-01",
            "estimated_cost": 100000.0,
            "description": "Test project alpha",
        },
        {
            "permit_number": "P002",
            "permit_type_definition": "demolition",
            "status": "filed",
            "filed_date": "2024-03-15",
            "estimated_cost": None,
            "description": "",
        },
    ]
    md = _format_permit_list(permits, "123 Main St")
    assert "Found **2** permits" in md
    assert "P001" in md
    assert "P002" in md
    assert "$100,000" in md


# ---------------------------------------------------------------------------
# Lookup functions (with mocks)
# ---------------------------------------------------------------------------

@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_lookup_by_number():
    mock_conn = MagicMock()
    # Return a minimal permit row (26 columns)
    row = tuple(["P001"] + [None] * 25)
    mock_conn.execute.return_value.fetchall.return_value = [row]

    result = _lookup_by_number(mock_conn, "P001")
    assert len(result) == 1
    assert result[0]["permit_number"] == "P001"


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_lookup_by_number_not_found():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []

    result = _lookup_by_number(mock_conn, "NONEXISTENT")
    assert result == []


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_lookup_by_address():
    mock_conn = MagicMock()
    row = tuple(["P001"] + [None] * 25)
    mock_conn.execute.return_value.fetchall.return_value = [row]

    result = _lookup_by_address(mock_conn, "123", "Main")
    assert len(result) == 1
    # Verify exact match params — no wildcards (prevents "BLAKE" matching "LAKE")
    call_args = mock_conn.execute.call_args
    params = call_args[0][1]
    assert "Main" in params
    assert "%Main%" not in params
    assert "Main%" not in params


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_lookup_by_block_lot():
    mock_conn = MagicMock()
    row = tuple(["P001"] + [None] * 25)
    mock_conn.execute.return_value.fetchall.side_effect = [
        # _find_historical_lots: step 1 — get address from current lot
        [("123", "MAIN")],
        # _find_historical_lots: step 2 — find all lots at that address
        [("001",)],
        # actual permit query
        [row],
    ]

    result = _lookup_by_block_lot(mock_conn, "3512", "001")
    assert len(result) == 1


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_find_historical_lots_discovers_old_lot():
    """When a condo conversion changed the lot number, find both old and new."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.side_effect = [
        # Step 1: address from current lot 069
        [("146", "LAKE")],
        # Step 2: all lots at 146 LAKE on block 1355
        [("017",), ("069",)],
    ]
    lots = _find_historical_lots(mock_conn, "1355", "069")
    assert "069" in lots
    assert "017" in lots
    assert len(lots) == 2


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_find_historical_lots_no_address():
    """When no permits exist for the lot, return just the input lot."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []
    lots = _find_historical_lots(mock_conn, "9999", "999")
    assert lots == ["999"]


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_lookup_by_block_lot_multi_lot():
    """Block/lot lookup merges permits across historical lot numbers."""
    mock_conn = MagicMock()
    old_row = tuple(["P001"] + [None] * 25)
    new_row = tuple(["P002"] + [None] * 25)
    mock_conn.execute.return_value.fetchall.side_effect = [
        # _find_historical_lots: step 1 — get address
        [("146", "LAKE")],
        # _find_historical_lots: step 2 — both lots
        [("017",), ("069",)],
        # actual permit query (IN clause with both lots)
        [old_row, new_row],
    ]

    result = _lookup_by_block_lot(mock_conn, "1355", "069")
    assert len(result) == 2
    assert result[0]["permit_number"] == "P001"
    assert result[1]["permit_number"] == "P002"


# ---------------------------------------------------------------------------
# Enrichment functions (with mocks)
# ---------------------------------------------------------------------------

@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_get_contacts():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        ("contractor", "John Smith", "Smith Co", 1, "John Smith", "Smith Co", 47),
    ]
    result = _get_contacts(mock_conn, "P001")
    assert len(result) == 1
    assert result[0]["role"] == "contractor"
    assert result[0]["permit_count"] == 47


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_get_inspections():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        ("2024-06-15", "Torres", "Approved", "Rough plumbing"),
    ]
    result = _get_inspections(mock_conn, "P001")
    assert len(result) == 1
    assert result[0]["result"] == "Approved"


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_get_timeline_found():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [(45, 120)]
    result = _get_timeline(mock_conn, "P001")
    assert result == {"days_to_issuance": 45, "days_to_completion": 120}


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_get_timeline_not_found():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []
    result = _get_timeline(mock_conn, "P001")
    assert result is None


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_get_related_location():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.side_effect = [
        # _find_historical_lots: step 1 — get address
        [("123", "MAIN")],
        # _find_historical_lots: step 2 — single lot
        [("001",)],
        # actual related location query
        [("P999", "alterations", "complete", "2023-01-01", 50000.0, "Test")],
    ]
    result = _get_related_location(mock_conn, "3512", "001", "P001")
    assert len(result) == 1
    assert result[0]["permit_number"] == "P999"


@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
def test_get_related_team():
    """Test _get_related_team — relationships-based approach with fallback."""
    mock_conn = MagicMock()

    # Mock _exec: step 1 returns entity_ids, step 2 returns relationships,
    # step 3 returns entity details, step 4 returns permits
    call_count = [0]
    def mock_exec(conn, sql, params=None):
        call_count[0] += 1
        if call_count[0] == 1:
            # Step 1: entity_ids from contacts
            return [(101,)]
        elif call_count[0] == 2:
            # Step 2: relationships
            return [(101, 201, 1, "P888", "Mission")]
        elif call_count[0] == 3:
            # Step 3: entity details for connected entity 201
            return [(201, "John Smith", "Smith Co", 10)]
        elif call_count[0] == 4:
            # Step 4: permit details
            return [("P888", "new construction", "issued", "2024-01-01", 200000.0, "New bldg")]
        return []

    with patch("src.tools.permit_lookup._exec", side_effect=mock_exec):
        result = _get_related_team(mock_conn, "P001")
    assert len(result) == 1
    assert result[0]["shared_entity"] == "John Smith"


# ---------------------------------------------------------------------------
# Main entry point: permit_lookup()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_permit_lookup_no_input():
    """No input should return validation message."""
    result = await permit_lookup()
    assert "provide" in result.lower()


@pytest.mark.asyncio
async def test_permit_lookup_empty_strings():
    """Empty strings should return validation message."""
    result = await permit_lookup(permit_number="", street_number="", street_name="")
    assert "provide" in result.lower()


@pytest.mark.asyncio
@patch("src.tools.permit_lookup.get_connection")
@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
async def test_permit_lookup_by_number_not_found(mock_get_conn):
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn
    mock_conn.execute.return_value.fetchall.return_value = []

    result = await permit_lookup(permit_number="NONEXISTENT")
    assert "No permit found" in result


@pytest.mark.asyncio
@patch("src.tools.permit_lookup.get_connection")
@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
async def test_permit_lookup_by_number_found(mock_get_conn):
    """Full flow: lookup by number returns details, team, inspections, related."""
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn

    # Build a full 26-column permit row
    permit_row = (
        "202301015555", "1", "otc alterations permit", "issued",
        "2024-03-15", "Kitchen remodel", "2023-06-01", "2024-03-15",
        None, None, 85000.0, None, "apartments", "apartments",
        1, 1, "123", "Main", "St", "94110", "Mission",
        "9", "3512", "001", None, "2024-12-01",
    )

    # Each call to execute().fetchall() returns different data
    mock_conn.execute.return_value.fetchall.side_effect = [
        # _lookup_by_number
        [permit_row],
        # _get_timeline
        [(45, 120)],
        # _get_contacts
        [("contractor", "John Smith", "Smith Co", 1, "John Smith", "Smith Co", 47)],
        # _get_inspections
        [("2024-06-15", "Torres", "Approved", "Rough plumbing")],
        # _get_addenda
        [],
        # _get_related_location → _find_historical_lots step 1 (address)
        [("123", "Main")],
        # _get_related_location → _find_historical_lots step 2 (lots)
        [("001",)],
        # _get_related_location actual query
        [("P999", "alterations", "complete", "2023-01-01", 50000.0, "Bathroom remodel")],
        # _get_related_team (QS3-B): step 1 — entity_ids from contacts
        [(101,)],
        # _get_related_team (QS3-B): step 2 — relationships
        [(101, 201, 1, "P888", "Mission")],
        # _get_related_team (QS3-B): step 3 — entity details
        [(201, "John Smith", "Smith Co", 10)],
        # _get_related_team (QS3-B): step 4 — permit details
        [("P888", "new construction", "issued", "2024-01-01", 200000.0, "New bldg")],
    ]

    result = await permit_lookup(permit_number="202301015555")

    assert "202301015555" in result
    assert "Permit Details" in result
    assert "otc alterations permit" in result
    assert "$85,000" in result
    assert "Project Team" in result
    assert "John Smith" in result
    assert "Inspection History" in result
    assert "Torres" in result
    assert "Related Permits" in result
    assert "P999" in result
    assert "P888" in result


@pytest.mark.asyncio
@patch("src.tools.permit_lookup.get_connection")
@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
async def test_permit_lookup_by_address_multiple(mock_get_conn):
    """Address search returning multiple permits shows list + detail."""
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn

    permit_row_1 = tuple(
        ["P001", "1", "alterations", "issued", "2024-06-01",
         "Kitchen remodel", "2024-01-01", "2024-06-01",
         None, None, 85000.0, None, None, None,
         None, None, "123", "Main", "St", "94110", "Mission",
         "9", "3512", "001", None, "2024-12-01"]
    )
    permit_row_2 = tuple(
        ["P002", "1", "alterations", "filed", "2024-08-01",
         "Bathroom remodel", "2024-07-01", None,
         None, None, 40000.0, None, None, None,
         None, None, "123", "Main", "St", "94110", "Mission",
         "9", "3512", "001", None, "2024-12-01"]
    )

    mock_conn.execute.return_value.fetchall.side_effect = [
        # _lookup_by_address
        [permit_row_1, permit_row_2],
        # parcel merge: _lookup_by_block_lot → _find_historical_lots step 1
        [("123", "Main")],
        # parcel merge: _lookup_by_block_lot → _find_historical_lots step 2
        [("001",)],
        # parcel merge: _lookup_by_block_lot actual query (same permits, deduped)
        [permit_row_1, permit_row_2],
        # _get_recent_addenda_activity (called from _summarize_recent_activity)
        [],
        # _get_timeline for first permit
        [],
        # _get_contacts for first permit
        [],
        # _get_inspections for first permit
        [],
        # _get_addenda for first permit
        [],
        # _get_related_location → _find_historical_lots step 1 (address)
        [("123", "Main")],
        # _get_related_location → _find_historical_lots step 2 (lots)
        [("001",)],
        # _get_related_location actual query
        [],
        # _get_related_team for first permit
        [],
    ]

    result = await permit_lookup(street_number="123", street_name="Main")

    assert "Found **2** permits" in result
    assert "P001" in result
    assert "P002" in result
    assert "123 Main" in result


@pytest.mark.asyncio
@patch("src.tools.permit_lookup.get_connection")
@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
async def test_permit_lookup_by_block_lot_not_found(mock_get_conn):
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn
    mock_conn.execute.return_value.fetchall.side_effect = [
        # _find_historical_lots: step 1 — no address found
        [],
        # actual permit query — no results
        [],
    ]

    result = await permit_lookup(block="9999", lot="999")
    assert "No permits found" in result
    assert "Block 9999" in result


@pytest.mark.asyncio
@patch("src.tools.permit_lookup.get_connection")
@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
async def test_permit_lookup_connection_closes(mock_get_conn):
    """Connection is always closed, even on success."""
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn
    mock_conn.execute.return_value.fetchall.return_value = []

    await permit_lookup(permit_number="P001")
    mock_conn.close.assert_called_once()


@pytest.mark.asyncio
@patch("src.tools.permit_lookup.get_connection")
@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
async def test_permit_lookup_address_no_match(mock_get_conn):
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn
    mock_conn.execute.return_value.fetchall.return_value = []

    result = await permit_lookup(street_number="999", street_name="Nowhere")
    assert "No permits found" in result or "No exact match" in result
    assert "999" in result and "Nowhere" in result


@pytest.mark.asyncio
@patch("src.tools.permit_lookup.get_connection")
@patch("src.tools.permit_lookup.BACKEND", "duckdb")
@patch("src.tools.permit_lookup._PH", "?")
async def test_permit_lookup_address_suggestions(mock_get_conn):
    """When exact match fails but similar streets exist, show suggestions."""
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn
    # _lookup_by_address uses two-pass strategy (pass 1 fast, pass 2 slow),
    # then _suggest_street_names runs the suggestion query.
    mock_conn.execute.return_value.fetchall.side_effect = [
        [],                                      # pass 1 (fast indexed) — empty
        [],                                      # pass 2 (UPPER fallback) — empty
        [("BLAKE", 18), ("LAKE MERCED", 7)],     # suggestion query
    ]

    result = await permit_lookup(street_number="146", street_name="Lake")
    assert "Did you mean" in result
    assert "BLAKE" in result
    assert "LAKE MERCED" in result
    assert "18 permits" in result
