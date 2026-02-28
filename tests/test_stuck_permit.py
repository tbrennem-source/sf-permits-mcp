"""Tests for src/tools/stuck_permit.py — Stuck Permit Intervention Playbook.

All tests use mocks — no live DB or network access required.

Scenarios covered:
  1. Permit not found → graceful error message
  2. Critically stalled at BLDG station (past p90)
  3. Stalled at inter-agency station (SFFD, past p75)
  4. Comments issued — resubmission needed
  5. Multiple revision cycles
  6. Healthy permit (dwell within p50 range)
  7. No addenda data (permit not yet in plan check)
  8. Cascaded failures (DB error) → graceful fallback
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock, AsyncMock


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _make_permit(
    permit_number: str = "202401234567",
    status: str = "issued",
    description: str = "kitchen remodel",
    permit_type_definition: str = "Building Permit",
    filed_date: str | None = None,
    issued_date: str | None = None,
    estimated_cost: float = 75000.0,
    street_number: str = "487",
    street_name: str = "Noe",
    street_suffix: str = "St",
    neighborhood: str = "Castro",
    status_date: str | None = None,
) -> dict:
    today = date.today()
    return {
        "permit_number": permit_number,
        "permit_type": "8",
        "permit_type_definition": permit_type_definition,
        "status": status,
        "status_date": status_date or (today - timedelta(days=60)).isoformat(),
        "description": description,
        "filed_date": filed_date or (today - timedelta(days=200)).isoformat(),
        "issued_date": issued_date or (today - timedelta(days=120)).isoformat(),
        "approved_date": None,
        "completed_date": None,
        "estimated_cost": estimated_cost,
        "revised_cost": None,
        "street_number": street_number,
        "street_name": street_name,
        "street_suffix": street_suffix,
        "zipcode": "94114",
        "neighborhood": neighborhood,
    }


def _make_station_entry(
    station: str = "BLDG",
    addenda_number: int = 0,
    arrive_days_ago: int = 90,
    finish_date=None,
    review_results: str | None = None,
) -> dict:
    today = date.today()
    arrive = (today - timedelta(days=arrive_days_ago)).isoformat()
    return {
        "station": station,
        "addenda_number": addenda_number,
        "arrive": arrive,
        "finish_date": finish_date,
        "review_results": review_results,
    }


def _make_velocity(p50: float = 15.0, p75: float = 30.0, p90: float = 60.0) -> dict:
    return {
        "p50_days": p50,
        "p75_days": p75,
        "p90_days": p90,
        "sample_count": 200,
        "period": "current",
    }


# ---------------------------------------------------------------------------
# Unit tests: helper functions (no DB, no async)
# ---------------------------------------------------------------------------

def test_parse_date_from_string():
    from src.tools.stuck_permit import _parse_date
    d = _parse_date("2025-06-15")
    assert d == date(2025, 6, 15)


def test_parse_date_from_date():
    from src.tools.stuck_permit import _parse_date
    d = _parse_date(date(2025, 6, 15))
    assert d == date(2025, 6, 15)


def test_parse_date_none():
    from src.tools.stuck_permit import _parse_date
    assert _parse_date(None) is None


def test_calc_dwell_days():
    from src.tools.stuck_permit import _calc_dwell_days
    today = date.today()
    arrive = (today - timedelta(days=45)).isoformat()
    assert _calc_dwell_days(arrive, today) == 45


def test_calc_dwell_days_none():
    from src.tools.stuck_permit import _calc_dwell_days
    assert _calc_dwell_days(None, date.today()) is None


def test_overall_status_critically_stalled():
    from src.tools.stuck_permit import _overall_status
    diags = [
        {"status": "normal"},
        {"status": "critically_stalled"},
        {"status": "stalled"},
    ]
    assert _overall_status(diags) == "critically_stalled"


def test_overall_status_stalled():
    from src.tools.stuck_permit import _overall_status
    diags = [{"status": "normal"}, {"status": "stalled"}]
    assert _overall_status(diags) == "stalled"


def test_overall_status_all_normal():
    from src.tools.stuck_permit import _overall_status
    diags = [{"status": "normal"}, {"status": "normal"}]
    assert _overall_status(diags) == "normal"


def test_severity_label():
    from src.tools.stuck_permit import _severity_label
    assert _severity_label("critically_stalled") == "CRITICAL"
    assert _severity_label("stalled") == "STALLED"
    assert _severity_label("normal") == "NORMAL"


# ---------------------------------------------------------------------------
# Unit tests: _diagnose_station
# ---------------------------------------------------------------------------

def test_diagnose_critically_stalled_bldg():
    """BLDG station at 95 days with p90=60 → critically_stalled."""
    from src.tools.stuck_permit import _diagnose_station
    entry = _make_station_entry("BLDG", arrive_days_ago=95)
    velocity = _make_velocity(p50=15, p75=30, p90=60)
    today = date.today()

    result = _diagnose_station(entry, velocity, today)

    assert result["status"] == "critically_stalled"
    assert result["is_bldg"] is True
    assert result["is_inter_agency"] is False
    assert any("p90" in f for f in result["flags"])
    assert "DBI" in result["recommendation"] or "plan check" in result["recommendation"].lower()


def test_diagnose_stalled_bldg():
    """BLDG station at 40 days with p75=30 → stalled (not critical)."""
    from src.tools.stuck_permit import _diagnose_station
    entry = _make_station_entry("BLDG", arrive_days_ago=40)
    velocity = _make_velocity(p50=15, p75=30, p90=60)
    today = date.today()

    result = _diagnose_station(entry, velocity, today)

    assert result["status"] == "stalled"
    assert any("p75" in f for f in result["flags"])


def test_diagnose_stalled_sffd_inter_agency():
    """SFFD station at 50 days with p75=30 → stalled inter-agency."""
    from src.tools.stuck_permit import _diagnose_station
    entry = _make_station_entry("SFFD", arrive_days_ago=50)
    velocity = _make_velocity(p50=10, p75=30, p90=50)
    today = date.today()

    result = _diagnose_station(entry, velocity, today)

    assert result["status"] in ("stalled", "critically_stalled")
    assert result["is_inter_agency"] is True
    assert "Fire" in result["recommendation"] or "SFFD" in result["recommendation"]


def test_diagnose_comments_issued():
    """Comments issued → stalled, resubmit recommendation."""
    from src.tools.stuck_permit import _diagnose_station
    entry = _make_station_entry(
        "BLDG", arrive_days_ago=20, review_results="Comments Issued"
    )
    today = date.today()

    result = _diagnose_station(entry, None, today)

    assert result["status"] == "stalled"
    assert any("comment" in f.lower() or "resubmission" in f.lower() for f in result["flags"])
    assert "EPR" in result["recommendation"] or "resubmit" in result["recommendation"].lower()


def test_diagnose_healthy_station():
    """Station at 10 days with p50=15 → normal status."""
    from src.tools.stuck_permit import _diagnose_station
    entry = _make_station_entry("BLDG", arrive_days_ago=10)
    velocity = _make_velocity(p50=15, p75=30, p90=60)
    today = date.today()

    result = _diagnose_station(entry, velocity, today)

    assert result["status"] == "normal"


def test_diagnose_no_velocity_long_dwell():
    """No velocity data + 100d dwell → critically_stalled (heuristic)."""
    from src.tools.stuck_permit import _diagnose_station
    entry = _make_station_entry("BLDG", arrive_days_ago=100)
    today = date.today()

    result = _diagnose_station(entry, None, today)

    assert result["status"] == "critically_stalled"
    assert any("no baseline" in f for f in result["flags"])


def test_diagnose_planning_inter_agency():
    """CP-ZOC (Planning) station → is_inter_agency=True."""
    from src.tools.stuck_permit import _diagnose_station
    entry = _make_station_entry("CP-ZOC", arrive_days_ago=40)
    velocity = _make_velocity(p50=15, p75=30, p90=55)
    today = date.today()

    result = _diagnose_station(entry, velocity, today)

    assert result["is_inter_agency"] is True
    assert "Planning" in result["recommendation"]


def test_diagnose_revision_cycle_flagged():
    """addenda_number=2 → multiple revision cycles flagged."""
    from src.tools.stuck_permit import _diagnose_station
    entry = _make_station_entry("BLDG", addenda_number=2, arrive_days_ago=15)
    velocity = _make_velocity(p50=15, p75=30, p90=60)
    today = date.today()

    result = _diagnose_station(entry, velocity, today)

    assert any("revision" in f.lower() for f in result["flags"])


# ---------------------------------------------------------------------------
# Integration-style tests: full async tool (mocked DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_diagnose_permit_not_found():
    """Permit not in DB → returns 'not found' message."""
    with patch("src.tools.stuck_permit.get_connection") as mock_conn_fn, \
         patch("src.tools.stuck_permit._fetch_permit") as mock_fetch:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        mock_fetch.return_value = None

        from src.tools.stuck_permit import diagnose_stuck_permit
        result = await diagnose_stuck_permit("BADNUMBER123")

    assert "Not Found" in result or "not found" in result.lower()
    assert "BADNUMBER123" in result


@pytest.mark.asyncio
async def test_diagnose_critically_stalled_full_playbook():
    """Full playbook for a permit critically stalled at BLDG."""
    today = date.today()
    permit = _make_permit()
    station_entry = _make_station_entry("BLDG", arrive_days_ago=95)
    velocity = _make_velocity(p50=15, p75=30, p90=60)

    with patch("src.tools.stuck_permit.get_connection") as mock_conn_fn, \
         patch("src.tools.stuck_permit._fetch_permit") as mock_permit, \
         patch("src.tools.stuck_permit._fetch_active_stations") as mock_stations, \
         patch("src.tools.stuck_permit._fetch_revision_count") as mock_revisions, \
         patch("src.tools.stuck_permit._fetch_velocity") as mock_velocity:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        mock_permit.return_value = permit
        mock_stations.return_value = [station_entry]
        mock_revisions.return_value = 0
        mock_velocity.return_value = velocity

        from src.tools.stuck_permit import diagnose_stuck_permit
        result = await diagnose_stuck_permit("202401234567")

    # Check header
    assert "Stuck Permit Playbook" in result
    assert "202401234567" in result

    # Check station diagnosis section
    assert "Station Diagnosis" in result
    assert "BLDG" in result
    assert "CRITICAL" in result

    # Check interventions
    assert "Intervention Steps" in result
    assert "DBI" in result or "plan check" in result.lower()


@pytest.mark.asyncio
async def test_diagnose_inter_agency_hold():
    """Full playbook for a permit stalled at SFFD."""
    permit = _make_permit()
    station_entry = _make_station_entry("SFFD", arrive_days_ago=50)
    velocity = _make_velocity(p50=10, p75=30, p90=45)

    with patch("src.tools.stuck_permit.get_connection") as mock_conn_fn, \
         patch("src.tools.stuck_permit._fetch_permit") as mock_permit, \
         patch("src.tools.stuck_permit._fetch_active_stations") as mock_stations, \
         patch("src.tools.stuck_permit._fetch_revision_count") as mock_revisions, \
         patch("src.tools.stuck_permit._fetch_velocity") as mock_velocity:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        mock_permit.return_value = permit
        mock_stations.return_value = [station_entry]
        mock_revisions.return_value = 0
        mock_velocity.return_value = velocity

        from src.tools.stuck_permit import diagnose_stuck_permit
        result = await diagnose_stuck_permit("202401234567")

    assert "SFFD" in result or "Fire" in result
    assert "Contact" in result


@pytest.mark.asyncio
async def test_diagnose_comments_issued_playbook():
    """Full playbook for a permit with comments issued."""
    permit = _make_permit()
    station_entry = _make_station_entry(
        "BLDG", arrive_days_ago=25, review_results="Comments Issued"
    )

    with patch("src.tools.stuck_permit.get_connection") as mock_conn_fn, \
         patch("src.tools.stuck_permit._fetch_permit") as mock_permit, \
         patch("src.tools.stuck_permit._fetch_active_stations") as mock_stations, \
         patch("src.tools.stuck_permit._fetch_revision_count") as mock_revisions, \
         patch("src.tools.stuck_permit._fetch_velocity") as mock_velocity:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        mock_permit.return_value = permit
        mock_stations.return_value = [station_entry]
        mock_revisions.return_value = 1
        mock_velocity.return_value = _make_velocity()

        from src.tools.stuck_permit import diagnose_stuck_permit
        result = await diagnose_stuck_permit("202401234567")

    # Should recommend EPR resubmission
    assert "EPR" in result or "resubmit" in result.lower()
    assert "comment" in result.lower() or "Comment" in result


@pytest.mark.asyncio
async def test_diagnose_multiple_revision_cycles():
    """3 revision cycles → specific revision history warning."""
    permit = _make_permit()
    station_entry = _make_station_entry("BLDG", addenda_number=3, arrive_days_ago=20)

    with patch("src.tools.stuck_permit.get_connection") as mock_conn_fn, \
         patch("src.tools.stuck_permit._fetch_permit") as mock_permit, \
         patch("src.tools.stuck_permit._fetch_active_stations") as mock_stations, \
         patch("src.tools.stuck_permit._fetch_revision_count") as mock_revisions, \
         patch("src.tools.stuck_permit._fetch_velocity") as mock_velocity:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        mock_permit.return_value = permit
        mock_stations.return_value = [station_entry]
        mock_revisions.return_value = 3
        mock_velocity.return_value = _make_velocity()

        from src.tools.stuck_permit import diagnose_stuck_permit
        result = await diagnose_stuck_permit("202401234567")

    assert "Revision History" in result or "revision" in result.lower()
    assert "3" in result


@pytest.mark.asyncio
async def test_diagnose_healthy_permit():
    """Healthy permit (all stations within normal range) → no urgent interventions."""
    permit = _make_permit()
    station_entry = _make_station_entry("BLDG", arrive_days_ago=10)
    velocity = _make_velocity(p50=15, p75=30, p90=60)

    with patch("src.tools.stuck_permit.get_connection") as mock_conn_fn, \
         patch("src.tools.stuck_permit._fetch_permit") as mock_permit, \
         patch("src.tools.stuck_permit._fetch_active_stations") as mock_stations, \
         patch("src.tools.stuck_permit._fetch_revision_count") as mock_revisions, \
         patch("src.tools.stuck_permit._fetch_velocity") as mock_velocity:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        mock_permit.return_value = permit
        mock_stations.return_value = [station_entry]
        mock_revisions.return_value = 0
        mock_velocity.return_value = velocity

        from src.tools.stuck_permit import diagnose_stuck_permit
        result = await diagnose_stuck_permit("202401234567")

    # Should still return a playbook
    assert "Stuck Permit Playbook" in result
    # Normal status — no CRITICAL
    assert "CRITICAL" not in result


@pytest.mark.asyncio
async def test_diagnose_no_addenda_data():
    """Permit with no addenda routing yet → graceful empty station section."""
    permit = _make_permit(status="filed")

    with patch("src.tools.stuck_permit.get_connection") as mock_conn_fn, \
         patch("src.tools.stuck_permit._fetch_permit") as mock_permit, \
         patch("src.tools.stuck_permit._fetch_active_stations") as mock_stations, \
         patch("src.tools.stuck_permit._fetch_revision_count") as mock_revisions, \
         patch("src.tools.stuck_permit._fetch_velocity") as mock_velocity:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        mock_permit.return_value = permit
        mock_stations.return_value = []  # No routing yet
        mock_revisions.return_value = 0
        mock_velocity.return_value = None

        from src.tools.stuck_permit import diagnose_stuck_permit
        result = await diagnose_stuck_permit("202401234567")

    assert "Stuck Permit Playbook" in result
    # Should note no active stations
    assert "No active routing" in result or "not yet" in result.lower() or "No active" in result


@pytest.mark.asyncio
async def test_diagnose_db_error_graceful():
    """DB error → returns formatted error message, not raw exception."""
    with patch("src.tools.stuck_permit.get_connection") as mock_conn_fn:
        mock_conn_fn.side_effect = RuntimeError("DB connection failed")

        from src.tools.stuck_permit import diagnose_stuck_permit
        result = await diagnose_stuck_permit("202401234567")

    assert "Error" in result or "error" in result.lower()
    assert "202401234567" in result


# ---------------------------------------------------------------------------
# Unit tests: contact lookup
# ---------------------------------------------------------------------------

def test_get_agency_key_sffd():
    from src.tools.stuck_permit import _get_agency_key
    assert _get_agency_key("SFFD") == "SFFD"
    assert _get_agency_key("SFFD-HQ") == "SFFD"


def test_get_agency_key_health():
    from src.tools.stuck_permit import _get_agency_key
    assert _get_agency_key("HEALTH") == "HEALTH"
    assert _get_agency_key("HEALTH-FD") == "HEALTH"


def test_get_agency_key_planning():
    from src.tools.stuck_permit import _get_agency_key
    assert _get_agency_key("CP-ZOC") == "PLANNING"
    assert _get_agency_key("PLAN") == "PLANNING"


def test_get_agency_key_dpw():
    from src.tools.stuck_permit import _get_agency_key
    assert _get_agency_key("DPW-BSM") == "DPW"


def test_get_agency_key_default_dbi():
    from src.tools.stuck_permit import _get_agency_key
    assert _get_agency_key("BLDG") == "DBI"
    assert _get_agency_key("BLDG-E") == "DBI"


# ---------------------------------------------------------------------------
# Unit tests: format_address
# ---------------------------------------------------------------------------

def test_format_address_full():
    from src.tools.stuck_permit import _format_address
    permit = {
        "street_number": "487",
        "street_name": "Noe",
        "street_suffix": "St",
        "zipcode": "94114",
    }
    addr = _format_address(permit)
    assert "487" in addr
    assert "Noe" in addr
    assert "94114" in addr


def test_format_address_missing_parts():
    from src.tools.stuck_permit import _format_address
    permit = {"street_number": None, "street_name": "Market", "street_suffix": None, "zipcode": None}
    addr = _format_address(permit)
    assert "Market" in addr


# ---------------------------------------------------------------------------
# Unit tests: INTER_AGENCY_STATIONS classification
# ---------------------------------------------------------------------------

def test_inter_agency_stations_coverage():
    """All expected inter-agency stations are classified correctly."""
    from src.tools.stuck_permit import INTER_AGENCY_STATIONS
    expected_stations = ["SFFD", "SFFD-HQ", "HEALTH", "CP-ZOC", "DPW-BSM", "HIS"]
    for station in expected_stations:
        assert station in INTER_AGENCY_STATIONS, f"{station} missing from INTER_AGENCY_STATIONS"


def test_bldg_stations_not_inter_agency():
    """BLDG stations are DBI, not inter-agency."""
    from src.tools.stuck_permit import INTER_AGENCY_STATIONS, BLDG_STATIONS
    for station in BLDG_STATIONS:
        assert station not in INTER_AGENCY_STATIONS
