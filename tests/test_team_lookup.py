"""Tests for team_lookup module.

Uses DuckDB fallback (no Postgres in test env).
Tests the lookup_entity and generate_team_profile functions
against the DuckDB entities table if available, otherwise
tests with mocked data.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.tools.team_lookup import (
    _normalize_name,
    lookup_entity,
    generate_team_profile,
)


# ----- _normalize_name -----

def test_normalize_strips_inc():
    assert _normalize_name("ABC Construction Inc.") == "ABC Construction"


def test_normalize_strips_llc():
    assert _normalize_name("Smith Design LLC") == "Smith Design"


def test_normalize_strips_corp():
    assert _normalize_name("Global Corp.") == "Global"


def test_normalize_collapses_whitespace():
    assert _normalize_name("  John   Smith  ") == "John Smith"


def test_normalize_preserves_name_without_suffix():
    assert _normalize_name("Jane Doe") == "Jane Doe"


def test_normalize_case_insensitive_suffix():
    assert _normalize_name("Test Company") == "Test"


# ----- lookup_entity (with mock) -----

@patch("src.tools.team_lookup.get_connection")
@patch("src.tools.team_lookup.BACKEND", "duckdb")
def test_lookup_empty_name(mock_conn):
    result = lookup_entity("")
    assert result == []
    mock_conn.assert_not_called()


@patch("src.tools.team_lookup.get_connection")
@patch("src.tools.team_lookup.BACKEND", "duckdb")
def test_lookup_returns_results(mock_get_conn):
    """Test that lookup_entity returns properly formatted results."""
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn
    mock_conn.execute.return_value.fetchall.return_value = [
        ("ENT-001", "John Smith", "Smith Construction", "contractor",
         "45", "89", "high"),
    ]

    results = lookup_entity("John Smith")
    assert len(results) == 1
    assert results[0]["name"] == "John Smith"
    assert results[0]["firm"] == "Smith Construction"
    assert results[0]["permit_count"] == 45


@patch("src.tools.team_lookup.get_connection")
@patch("src.tools.team_lookup.BACKEND", "duckdb")
def test_lookup_no_match(mock_get_conn):
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn
    mock_conn.execute.return_value.fetchall.return_value = []

    results = lookup_entity("Nonexistent Person XYZ")
    assert results == []


# ----- generate_team_profile -----

def test_profile_no_names():
    result = generate_team_profile()
    assert result == ""


def test_profile_empty_strings():
    result = generate_team_profile(contractor="", architect="", expediter="")
    assert result == ""


@patch("src.tools.team_lookup.lookup_entity")
@patch("src.tools.team_lookup.get_connection")
def test_profile_no_match(mock_conn, mock_lookup):
    """When no entity is found, show a 'not found' message."""
    mock_lookup.return_value = []
    mock_conn.return_value = MagicMock()

    result = generate_team_profile(contractor="Unknown Person XYZ")
    assert "Unknown Person XYZ" in result
    assert "didn't find" in result.lower()


@patch("src.tools.team_lookup._get_entity_stats")
@patch("src.tools.team_lookup.lookup_entity")
@patch("src.tools.team_lookup.get_connection")
def test_profile_with_match(mock_conn, mock_lookup, mock_stats):
    """When entity is found, show profile with stats."""
    mock_lookup.return_value = [{
        "entity_id": "ENT-001",
        "name": "John Smith",
        "firm": "Smith Construction Inc",
        "entity_type": "contractor",
        "permit_count": 47,
        "contact_count": 89,
        "confidence": "high",
        "score": 0.85,
    }]
    mock_stats.return_value = {
        "neighborhoods": ["Mission", "SoMa", "Castro"],
        "common_types": ["commercial alteration", "tenant improvement"],
        "avg_timeline_days": 78,
        "correction_rate": None,
        "last_active": "2025-11-15",
    }
    mock_conn.return_value = MagicMock()

    result = generate_team_profile(contractor="Smith Construction")
    assert "Smith Construction" in result
    assert "47" in result  # permit count
    assert "Mission" in result  # neighborhood
    assert "78 days" in result  # avg timeline


@patch("src.tools.team_lookup._get_entity_stats")
@patch("src.tools.team_lookup.lookup_entity")
@patch("src.tools.team_lookup.get_connection")
def test_profile_multiple_roles(mock_conn, mock_lookup, mock_stats):
    """Test that all three roles can be looked up."""
    mock_lookup.return_value = [{
        "entity_id": "ENT-001",
        "name": "Test Person",
        "firm": None,
        "entity_type": "unknown",
        "permit_count": 10,
        "contact_count": 15,
        "confidence": "medium",
        "score": 0.6,
    }]
    mock_stats.return_value = {
        "neighborhoods": [],
        "common_types": [],
        "avg_timeline_days": None,
        "correction_rate": None,
        "last_active": None,
    }
    mock_conn.return_value = MagicMock()

    result = generate_team_profile(
        contractor="Contractor A",
        architect="Architect B",
        expediter="Expediter C",
    )
    assert "General Contractor" in result
    assert "Architect / Engineer" in result
    assert "Permit Expediter" in result
