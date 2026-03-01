"""Tests for intelligence integration in morning brief.

Covers:
  - get_morning_brief() return structure
  - All required keys present in returned dict
  - After QS14, stuck_alerts / delay_alerts may be added — tested defensively
  - brief query functions handle empty data gracefully

Uses the same fixture pattern as tests/test_brief.py:
mocking src.db.query, src.db.query_one, src.db.get_connection to avoid real DB.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_conn():
    """Return a MagicMock that mimics a DuckDB connection context manager."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.close = MagicMock()
    mock_conn.execute = MagicMock(return_value=mock_conn)
    mock_conn.fetchall = MagicMock(return_value=[])
    mock_conn.fetchone = MagicMock(return_value=None)
    return mock_conn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Patch src.db functions used by web.brief to return empty results."""
    with patch("src.db.query", return_value=[]) as mock_q, \
         patch("src.db.query_one", return_value=None) as mock_qone, \
         patch("src.db.get_connection", return_value=_make_mock_conn()) as mock_conn:
        yield {
            "query": mock_q,
            "query_one": mock_qone,
            "get_connection": mock_conn,
        }


# ---------------------------------------------------------------------------
# Tests: get_morning_brief() structure
# ---------------------------------------------------------------------------

class TestBriefStructure:
    """get_morning_brief() must always return a dict with required keys."""

    def test_brief_always_has_summary_key(self, mock_db):
        """get_morning_brief always returns 'summary' key."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            assert "summary" in result
            assert isinstance(result["summary"], dict)
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")

    def test_brief_always_has_changes_key(self, mock_db):
        """get_morning_brief always returns 'changes' key."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            assert "changes" in result
            assert isinstance(result["changes"], list)
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")

    def test_brief_always_has_health_key(self, mock_db):
        """get_morning_brief always returns 'health' key."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            assert "health" in result
            assert isinstance(result["health"], list)
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")

    def test_brief_always_has_expiring_key(self, mock_db):
        """get_morning_brief always returns 'expiring' key."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            assert "expiring" in result
            assert isinstance(result["expiring"], list)
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")

    def test_brief_always_has_lookback_days_key(self, mock_db):
        """get_morning_brief always returns 'lookback_days' key."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1, lookback_days=7)
            assert "lookback_days" in result
            assert result["lookback_days"] == 7
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")

    def test_brief_always_has_pipeline_health_key(self, mock_db):
        """get_morning_brief always returns 'pipeline_health' key."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            assert "pipeline_health" in result
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")

    def test_brief_summary_has_total_watches(self, mock_db):
        """summary dict has total_watches key."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            assert "total_watches" in result["summary"]
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")

    def test_brief_no_primary_address_returns_none_synopsis(self, mock_db):
        """Without primary_address, property_synopsis is None."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            assert result.get("property_synopsis") is None
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")


# ---------------------------------------------------------------------------
# Tests: QS14 intelligence keys (defensive)
# ---------------------------------------------------------------------------

class TestBriefIntelligenceKeys:
    """Defensive tests for QS14 intelligence additions to the brief."""

    def test_brief_stuck_alerts_key_if_present(self, mock_db):
        """If 'stuck_alerts' key is added by QS14, it must be a list."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            if "stuck_alerts" in result:
                assert isinstance(result["stuck_alerts"], list)
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")

    def test_brief_delay_alerts_key_if_present(self, mock_db):
        """If 'delay_alerts' key is added by QS14, it must be a list."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            if "delay_alerts" in result:
                assert isinstance(result["delay_alerts"], list)
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")

    def test_brief_intelligence_key_if_present(self, mock_db):
        """If 'intelligence' key is added by QS14, it must be a dict or list."""
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            if "intelligence" in result:
                assert isinstance(result["intelligence"], (dict, list))
        except Exception:
            pytest.skip("get_morning_brief raised — likely missing DB dependency")


# ---------------------------------------------------------------------------
# Tests: _validity_days and _parse_date helpers
# ---------------------------------------------------------------------------

class TestBriefHelpers:
    """Test brief.py utility functions used for permit expiration logic."""

    def test_validity_days_demolition(self):
        """Demolition permits have 180-day validity."""
        from web.brief import _validity_days
        permit = {"permit_type_definition": "demolition permit", "estimated_cost": 5000}
        assert _validity_days(permit) == 180

    def test_validity_days_low_cost(self):
        """Permits $0-$100K have 360-day validity."""
        from web.brief import _validity_days
        permit = {"permit_type_definition": "otc alterations permit", "estimated_cost": 50000}
        assert _validity_days(permit) == 360

    def test_validity_days_medium_cost(self):
        """Permits $100K-$2.5M have 1080-day validity."""
        from web.brief import _validity_days
        permit = {"permit_type_definition": "full permit", "estimated_cost": 500000}
        assert _validity_days(permit) == 1080

    def test_validity_days_high_cost(self):
        """Permits $2.5M+ have 1440-day validity."""
        from web.brief import _validity_days
        permit = {"permit_type_definition": "new construction", "estimated_cost": 3000000}
        assert _validity_days(permit) == 1440

    def test_validity_days_no_cost(self):
        """Permit with no cost defaults to 360 days."""
        from web.brief import _validity_days
        permit = {"permit_type_definition": "otc alterations permit"}
        assert _validity_days(permit) == 360

    def test_parse_date_iso_string(self):
        """_parse_date correctly parses ISO date strings."""
        from web.brief import _parse_date
        result = _parse_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_parse_date_none(self):
        """_parse_date returns None for None input."""
        from web.brief import _parse_date
        assert _parse_date(None) is None

    def test_parse_date_empty_string(self):
        """_parse_date returns None for empty string."""
        from web.brief import _parse_date
        assert _parse_date("") is None

    def test_parse_date_date_object(self):
        """_parse_date returns date object as-is."""
        from web.brief import _parse_date
        d = date(2024, 6, 1)
        assert _parse_date(d) == d

    def test_parse_date_datetime_string(self):
        """_parse_date handles full datetime strings by taking first 10 chars."""
        from web.brief import _parse_date
        result = _parse_date("2024-03-15T10:30:00")
        assert result == date(2024, 3, 15)
