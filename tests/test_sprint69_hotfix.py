"""Regression tests for Sprint 69 Hotfix: address search resilience.

The bug: enrichment queries (inspections, contacts) that timed out on Postgres
would crash the entire /search response with 'Something went wrong'.

The fix: each enrichment section in permit_lookup() now has try/except so
a timeout in one section degrades gracefully instead of killing the response.
"""

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def client():
    """Create a Flask test client."""
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


MOCK_PERMIT_MD = """# Permit Lookup Results

Found **1** permits at **1455 Market St**.

## Permit Details

| Field | Value |
|-------|-------|
| Permit # | 202401015555 |
| Status | issued |
"""


class TestAddressSearchResilience:
    """Tests that address search works and degrades gracefully."""

    def test_address_search_returns_results(self, client):
        """Regression: address search was returning 'Something went wrong'."""
        with patch("web.routes_public.run_async", return_value=MOCK_PERMIT_MD):
            resp = client.get("/search?q=1455+Market+St")
            assert resp.status_code == 200
            assert b"Something went wrong" not in resp.data

    def test_address_search_shows_permits(self, client):
        """Address search should show permit data."""
        with patch("web.routes_public.run_async", return_value=MOCK_PERMIT_MD):
            resp = client.get("/search?q=1455+Market+St")
            html = resp.data.decode().lower()
            assert "permit" in html


class TestPermitLookupGracefulDegradation:
    """Tests that permit_lookup degrades gracefully when sub-queries fail."""

    def test_inspections_timeout_returns_fallback(self):
        """If inspections query times out, permit_lookup should still return data."""
        import asyncio
        from src.tools.permit_lookup import permit_lookup

        mock_conn = MagicMock()
        # _lookup_by_address returns one permit row (26 columns to match PERMIT_COLS)
        mock_permit_row = (
            "202401015555", "8", "otc alterations permit", "issued",
            "2024-01-01", "test permit", "2024-01-01", "2024-01-01",
            None, None, 1000.0, None, "office", "office",
            0, 0, "1455", "Market", "St", "94103",
            "South of Market", "6", "3507", "040", "N", "2024-01-01",
        )

        def mock_exec(conn, sql, params=None):
            if "FROM inspections" in sql:
                raise Exception("canceling statement due to statement timeout")
            if "FROM permits" in sql:
                return [mock_permit_row]
            if "FROM contacts" in sql:
                return []
            if "FROM addenda" in sql:
                return []
            if "FROM timeline_stats" in sql:
                return []
            return []

        with patch("src.tools.permit_lookup._exec", side_effect=mock_exec), \
             patch("src.tools.permit_lookup._exec_one", return_value=None), \
             patch("src.tools.permit_lookup.get_connection", return_value=mock_conn):
            result = asyncio.run(permit_lookup(
                street_number="1455", street_name="Market St"
            ))
            # Should return results, not crash
            assert "Permit" in result
            # Should show fallback text for inspections
            assert "temporarily unavailable" in result

    def test_contacts_timeout_returns_fallback(self):
        """If contacts query times out, permit_lookup should still return data."""
        import asyncio
        from src.tools.permit_lookup import permit_lookup

        mock_conn = MagicMock()
        mock_permit_row = (
            "202401015555", "8", "otc alterations permit", "issued",
            "2024-01-01", "test permit", "2024-01-01", "2024-01-01",
            None, None, 1000.0, None, "office", "office",
            0, 0, "1455", "Market", "St", "94103",
            "South of Market", "6", "3507", "040", "N", "2024-01-01",
        )

        def mock_exec(conn, sql, params=None):
            if "FROM contacts" in sql:
                raise Exception("canceling statement due to statement timeout")
            if "FROM permits" in sql:
                return [mock_permit_row]
            if "FROM inspections" in sql:
                return []
            if "FROM addenda" in sql:
                return []
            if "FROM timeline_stats" in sql:
                return []
            return []

        with patch("src.tools.permit_lookup._exec", side_effect=mock_exec), \
             patch("src.tools.permit_lookup._exec_one", return_value=None), \
             patch("src.tools.permit_lookup.get_connection", return_value=mock_conn):
            result = asyncio.run(permit_lookup(
                street_number="1455", street_name="Market St"
            ))
            assert "Permit" in result
            assert "temporarily unavailable" in result

    def test_all_enrichment_timeouts_still_returns_basic_data(self):
        """Even if ALL enrichment queries fail, basic permit data should appear."""
        import asyncio
        from src.tools.permit_lookup import permit_lookup

        mock_conn = MagicMock()
        mock_permit_row = (
            "202401015555", "8", "otc alterations permit", "issued",
            "2024-01-01", "test permit", "2024-01-01", "2024-01-01",
            None, None, 1000.0, None, "office", "office",
            0, 0, "1455", "Market", "St", "94103",
            "South of Market", "6", "3507", "040", "N", "2024-01-01",
        )

        call_count = {"permits": 0}

        def mock_exec(conn, sql, params=None):
            if "FROM permits" in sql:
                call_count["permits"] += 1
                # Only the first permits query (address lookup) returns data
                if call_count["permits"] <= 2:
                    return [mock_permit_row]
                return []  # related permits queries
            # All other queries fail
            raise Exception("canceling statement due to statement timeout")

        with patch("src.tools.permit_lookup._exec", side_effect=mock_exec), \
             patch("src.tools.permit_lookup._exec_one", return_value=None), \
             patch("src.tools.permit_lookup.get_connection", return_value=mock_conn):
            result = asyncio.run(permit_lookup(
                street_number="1455", street_name="Market St"
            ))
            # Core permit data should still be present
            assert "202401015555" in result
            assert "otc alterations permit" in result


class TestAddressLookupIndexOptimization:
    """Tests that the two-pass address lookup strategy works correctly."""

    def test_fast_path_exact_match(self):
        """Pass 1 (indexed) should find permits with exact street_name match."""
        from src.tools.permit_lookup import _lookup_by_address

        mock_conn = MagicMock()
        mock_permit_row = (
            "202401015555", "8", "otc alterations permit", "issued",
            "2024-01-01", "test", "2024-01-01", None,
            None, None, 1000.0, None, "office", "office",
            0, 0, "1455", "Market", "St", "94103",
            "South of Market", "6", "3507", "040", "N", "2024-01-01",
        )

        def mock_exec(conn, sql, params=None):
            if "street_name IN" in sql:
                return [mock_permit_row]
            # UPPER fallback should NOT be called
            return []

        with patch("src.tools.permit_lookup._exec", side_effect=mock_exec):
            results = _lookup_by_address(mock_conn, "1455", "Market St")
            assert len(results) == 1
            assert results[0]["permit_number"] == "202401015555"

    def test_slow_path_fallback(self):
        """Pass 2 (UPPER) should fire when fast path returns nothing."""
        from src.tools.permit_lookup import _lookup_by_address

        mock_conn = MagicMock()
        mock_permit_row = (
            "202401015555", "8", "otc alterations permit", "issued",
            "2024-01-01", "test", "2024-01-01", None,
            None, None, 1000.0, None, "office", "office",
            0, 0, "1455", "MARKET", "ST", "94103",
            "South of Market", "6", "3507", "040", "N", "2024-01-01",
        )

        call_count = {"fast": 0, "slow": 0}

        def mock_exec(conn, sql, params=None):
            if "street_name IN" in sql:
                call_count["fast"] += 1
                return []  # Fast path finds nothing
            if "UPPER" in sql:
                call_count["slow"] += 1
                return [mock_permit_row]
            return []

        with patch("src.tools.permit_lookup._exec", side_effect=mock_exec):
            results = _lookup_by_address(mock_conn, "1455", "market st")
            assert len(results) == 1
            assert call_count["fast"] == 1
            assert call_count["slow"] == 1
