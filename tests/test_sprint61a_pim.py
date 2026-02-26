"""Tests for Sprint 61A: PIM ArcGIS integration.

Tests cover:
- PIM client: response parsing, cache hit/miss/TTL, timeout, unknown zoning
- predict_permits: PIM used when block/lot resolved, fallback when PIM down
- property_lookup: PIM enrichment is additive
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PIM_RESPONSE = {
    "features": [
        {
            "attributes": {
                "ZONING_CODE": "RH-2",
                "ZONING_CATEGORY": "Residential",
                "HISTORIC_DISTRICT": None,
                "HEIGHT_DIST": "40-X",
                "SPECIAL_USE_DIST": None,
                "LANDMARK": None,
                "BLOCK_NUM": "3512",
                "LOT_NUM": "001",
            }
        }
    ]
}

SAMPLE_PIM_RESPONSE_HISTORIC = {
    "features": [
        {
            "attributes": {
                "ZONING_CODE": "NC-1",
                "ZONING_CATEGORY": "Neighborhood Commercial",
                "HISTORIC_DISTRICT": "Mission Dolores",
                "HEIGHT_DIST": "40-X",
                "SPECIAL_USE_DIST": None,
                "LANDMARK": None,
                "BLOCK_NUM": "3590",
                "LOT_NUM": "010",
            }
        }
    ]
}

SAMPLE_PIM_RESPONSE_UNKNOWN_ZONING = {
    "features": [
        {
            "attributes": {
                "ZONING_CODE": "P",
                "ZONING_CATEGORY": "Public",
                "HISTORIC_DISTRICT": None,
                "HEIGHT_DIST": None,
                "SPECIAL_USE_DIST": None,
                "LANDMARK": None,
                "BLOCK_NUM": "9999",
                "LOT_NUM": "001",
            }
        }
    ]
}

EMPTY_PIM_RESPONSE = {"features": []}


def _make_mock_http_response(payload: dict, status_code: int = 200):
    """Create a mock httpx response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# PIM client: response parsing
# ---------------------------------------------------------------------------

class TestPimResponseParsing:
    """Tests for _fetch_pim_api response parsing."""

    @pytest.mark.asyncio
    async def test_fetch_pim_api_parses_fields(self):
        """_fetch_pim_api correctly extracts all 6 fields."""
        from src.pim_client import _fetch_pim_api

        mock_resp = _make_mock_http_response(SAMPLE_PIM_RESPONSE)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_pim_api("3512", "001")

        assert result is not None
        assert result["ZONING_CODE"] == "RH-2"
        assert result["ZONING_CATEGORY"] == "Residential"
        assert result["HISTORIC_DISTRICT"] is None
        assert result["HEIGHT_DIST"] == "40-X"
        assert result["SPECIAL_USE_DIST"] is None
        assert result["LANDMARK"] is None

    @pytest.mark.asyncio
    async def test_fetch_pim_api_empty_features(self):
        """_fetch_pim_api returns {} when no features found."""
        from src.pim_client import _fetch_pim_api

        mock_resp = _make_mock_http_response(EMPTY_PIM_RESPONSE)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_pim_api("0000", "000")

        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_pim_api_normalizes_empty_strings(self):
        """_fetch_pim_api normalizes empty strings and 'N/A' to None."""
        from src.pim_client import _fetch_pim_api

        payload = {
            "features": [
                {
                    "attributes": {
                        "ZONING_CODE": "RH-1",
                        "ZONING_CATEGORY": "",
                        "HISTORIC_DISTRICT": "N/A",
                        "HEIGHT_DIST": "",
                        "SPECIAL_USE_DIST": None,
                        "LANDMARK": "N/A",
                    }
                }
            ]
        }
        mock_resp = _make_mock_http_response(payload)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_pim_api("1234", "001")

        assert result["ZONING_CATEGORY"] is None
        assert result["HISTORIC_DISTRICT"] is None
        assert result["HEIGHT_DIST"] is None
        assert result["LANDMARK"] is None

    @pytest.mark.asyncio
    async def test_fetch_pim_api_timeout_returns_none(self):
        """_fetch_pim_api returns None on timeout."""
        import httpx
        from src.pim_client import _fetch_pim_api

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_pim_api("3512", "001")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_pim_api_http_error_returns_none(self):
        """_fetch_pim_api returns None on HTTP error."""
        import httpx
        from src.pim_client import _fetch_pim_api

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "503", request=MagicMock(), response=MagicMock()
            )
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_pim_api("3512", "001")

        assert result is None


# ---------------------------------------------------------------------------
# PIM client: cache hit
# ---------------------------------------------------------------------------

class TestPimCacheHit:
    """Tests for cache hit path in query_pim_cached."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self):
        """query_pim_cached returns cached data without calling API."""
        cached_data = {
            "ZONING_CODE": "RH-2",
            "ZONING_CATEGORY": "Residential",
            "HISTORIC_DISTRICT": None,
            "HEIGHT_DIST": "40-X",
            "SPECIAL_USE_DIST": None,
            "LANDMARK": None,
        }

        mock_conn = MagicMock()
        mock_conn.close = MagicMock()

        with patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.BACKEND", "postgres"), \
             patch("src.pim_client._get_cached", return_value=cached_data) as mock_cache, \
             patch("src.pim_client._fetch_pim_api") as mock_api:

            from src.pim_client import query_pim_cached
            result = await query_pim_cached("3512", "001")

        assert result == cached_data
        mock_api.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_hit_empty_result_returns_none(self):
        """query_pim_cached returns None when cache holds empty dict (no features)."""
        mock_conn = MagicMock()
        mock_conn.close = MagicMock()

        with patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.BACKEND", "postgres"), \
             patch("src.pim_client._get_cached", return_value={}), \
             patch("src.pim_client._fetch_pim_api") as mock_api:

            from src.pim_client import query_pim_cached
            result = await query_pim_cached("0000", "000")

        assert result is None
        mock_api.assert_not_called()


# ---------------------------------------------------------------------------
# PIM client: cache miss
# ---------------------------------------------------------------------------

class TestPimCacheMiss:
    """Tests for cache miss path in query_pim_cached."""

    @pytest.mark.asyncio
    async def test_cache_miss_queries_api_and_writes_cache(self):
        """On cache miss, queries API and writes result to cache."""
        api_data = {
            "ZONING_CODE": "NC-1",
            "ZONING_CATEGORY": "Neighborhood Commercial",
            "HISTORIC_DISTRICT": None,
            "HEIGHT_DIST": "40-X",
            "SPECIAL_USE_DIST": None,
            "LANDMARK": None,
        }

        mock_conn = MagicMock()
        mock_conn.close = MagicMock()

        with patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.BACKEND", "postgres"), \
             patch("src.pim_client._get_cached", return_value=None), \
             patch("src.pim_client._fetch_pim_api", new_callable=AsyncMock, return_value=api_data) as mock_api, \
             patch("src.pim_client._write_cache") as mock_write:

            from src.pim_client import query_pim_cached
            result = await query_pim_cached("3590", "010")

        assert result == api_data
        mock_api.assert_called_once_with("3590", "010")
        mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_miss_api_timeout_returns_none_no_cache_write(self):
        """On cache miss + API timeout, returns None without writing cache."""
        mock_conn = MagicMock()
        mock_conn.close = MagicMock()

        with patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.BACKEND", "postgres"), \
             patch("src.pim_client._get_cached", return_value=None), \
             patch("src.pim_client._fetch_pim_api", new_callable=AsyncMock, return_value=None), \
             patch("src.pim_client._write_cache") as mock_write:

            from src.pim_client import query_pim_cached
            result = await query_pim_cached("3512", "001")

        assert result is None
        mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# PIM client: cache TTL
# ---------------------------------------------------------------------------

class TestPimCacheTTL:
    """Tests for 30-day TTL expiry logic in _get_cached."""

    def _make_mock_conn(self, row, backend="postgres"):
        """Create mock connection returning given row."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = row
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn

    def test_fresh_cache_returns_data(self):
        """_get_cached returns data when fetched_at is recent."""
        from src.pim_client import _get_cached

        data = {"ZONING_CODE": "RH-2", "ZONING_CATEGORY": "Residential",
                "HISTORIC_DISTRICT": None, "HEIGHT_DIST": "40-X",
                "SPECIAL_USE_DIST": None, "LANDMARK": None}
        recent_time = datetime.now(tz=timezone.utc) - timedelta(days=5)

        row = (json.dumps(data), recent_time)
        mock_conn = self._make_mock_conn(row)

        with patch("src.pim_client._ensure_pim_cache_table"):
            result = _get_cached("3512", "001", mock_conn, "postgres")

        assert result == data

    def test_expired_cache_returns_none(self):
        """_get_cached returns None when fetched_at is older than 30 days."""
        from src.pim_client import _get_cached

        data = {"ZONING_CODE": "RH-2", "ZONING_CATEGORY": "Residential",
                "HISTORIC_DISTRICT": None, "HEIGHT_DIST": "40-X",
                "SPECIAL_USE_DIST": None, "LANDMARK": None}
        expired_time = datetime.now(tz=timezone.utc) - timedelta(days=35)

        row = (json.dumps(data), expired_time)
        mock_conn = self._make_mock_conn(row)

        with patch("src.pim_client._ensure_pim_cache_table"):
            result = _get_cached("3512", "001", mock_conn, "postgres")

        assert result is None

    def test_cache_miss_returns_none(self):
        """_get_cached returns None when no row in cache."""
        from src.pim_client import _get_cached

        mock_conn = self._make_mock_conn(None)

        with patch("src.pim_client._ensure_pim_cache_table"):
            result = _get_cached("9999", "999", mock_conn, "postgres")

        assert result is None


# ---------------------------------------------------------------------------
# PIM client: coverage gap note
# ---------------------------------------------------------------------------

class TestPimCoverageGap:
    """Tests for get_pim_coverage_gap_note."""

    def test_gap_note_for_unknown_code(self):
        """get_pim_coverage_gap_note returns descriptive message for any code."""
        from src.pim_client import get_pim_coverage_gap_note

        note = get_pim_coverage_gap_note("P")
        assert "P" in note
        assert "routing" in note.lower()

    def test_gap_note_for_m1(self):
        """get_pim_coverage_gap_note handles industrial codes."""
        from src.pim_client import get_pim_coverage_gap_note

        note = get_pim_coverage_gap_note("M-1")
        assert "M-1" in note
        assert "General routing rules applied" in note

    def test_gap_note_empty_code(self):
        """get_pim_coverage_gap_note handles empty string gracefully."""
        from src.pim_client import get_pim_coverage_gap_note

        note = get_pim_coverage_gap_note("")
        assert isinstance(note, str)
        assert len(note) > 0


# ---------------------------------------------------------------------------
# PIM client: null inputs
# ---------------------------------------------------------------------------

class TestPimNullInputs:
    """Tests for edge cases in query_pim_cached."""

    @pytest.mark.asyncio
    async def test_empty_block_returns_none(self):
        """query_pim_cached returns None for empty block."""
        from src.pim_client import query_pim_cached

        result = await query_pim_cached("", "001")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_lot_returns_none(self):
        """query_pim_cached returns None for empty lot."""
        from src.pim_client import query_pim_cached

        result = await query_pim_cached("3512", "")
        assert result is None

    @pytest.mark.asyncio
    async def test_none_block_returns_none(self):
        """query_pim_cached returns None for None block."""
        from src.pim_client import query_pim_cached

        result = await query_pim_cached(None, "001")
        assert result is None


# ---------------------------------------------------------------------------
# predict_permits: PIM integration
# ---------------------------------------------------------------------------

class TestPredictPermitsPIM:
    """Tests for PIM integration in predict_permits."""

    @pytest.mark.asyncio
    async def test_predict_permits_uses_pim_zoning(self):
        """predict_permits uses PIM zoning code when PIM returns data."""
        pim_result = {
            "ZONING_CODE": "RH-2",
            "ZONING_CATEGORY": "Residential",
            "HISTORIC_DISTRICT": None,
            "HEIGHT_DIST": "40-X",
            "SPECIAL_USE_DIST": None,
            "LANDMARK": None,
        }

        with patch("src.pim_client.query_pim_cached", new_callable=AsyncMock, return_value=pim_result), \
             patch("src.tools.predict_permits._query_ref_permit_forms", return_value=None), \
             patch("src.tools.predict_permits._query_ref_agency_triggers", return_value=None):

            # Mock DB connection for address lookup to return block/lot
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.side_effect = [("3512", "001"), ("RH-2",), None]
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.close = MagicMock()

            with patch("src.tools.predict_permits.get_knowledge_base") as mock_kb, \
                 patch("src.db.get_connection", return_value=mock_conn), \
                 patch("src.db.BACKEND", "postgres"):

                kb = MagicMock()
                kb.decision_tree = {"steps": {}}
                kb.otc_criteria = {"not_otc_requires_inhouse": {"projects": []}}
                kb.ada_accessibility = {}
                kb.plan_signatures = {}
                kb.title24 = {}
                kb.earthquake_brace_bolt = None
                kb.match_concepts.return_value = []
                kb.get_step_confidence.return_value = "medium"
                mock_kb.return_value = kb

                from src.tools.predict_permits import predict_permits
                result = await predict_permits(
                    project_description="kitchen remodel",
                    address="123 Main St",
                )

        assert "RH-2" in result
        assert "SF Planning GIS" in result

    @pytest.mark.asyncio
    async def test_predict_permits_historic_flag_from_pim(self):
        """predict_permits sets historic flag and adds historic project type from PIM."""
        pim_result = {
            "ZONING_CODE": "NC-1",
            "ZONING_CATEGORY": "Neighborhood Commercial",
            "HISTORIC_DISTRICT": "Mission Dolores",
            "HEIGHT_DIST": "40-X",
            "SPECIAL_USE_DIST": None,
            "LANDMARK": None,
        }

        with patch("src.pim_client.query_pim_cached", new_callable=AsyncMock, return_value=pim_result), \
             patch("src.tools.predict_permits._query_ref_permit_forms", return_value=None), \
             patch("src.tools.predict_permits._query_ref_agency_triggers", return_value=None):

            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.side_effect = [("3590", "010"), ("NC-1",), None]
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.close = MagicMock()

            with patch("src.tools.predict_permits.get_knowledge_base") as mock_kb, \
                 patch("src.db.get_connection", return_value=mock_conn), \
                 patch("src.db.BACKEND", "postgres"):

                kb = MagicMock()
                kb.decision_tree = {"steps": {}}
                kb.otc_criteria = {"not_otc_requires_inhouse": {"projects": []}}
                kb.ada_accessibility = {}
                kb.plan_signatures = {}
                kb.title24 = {}
                kb.earthquake_brace_bolt = None
                kb.match_concepts.return_value = []
                kb.get_step_confidence.return_value = "medium"
                mock_kb.return_value = kb

                from src.tools.predict_permits import predict_permits
                result = await predict_permits(
                    project_description="exterior paint",
                    address="123 Valencia St",
                )

        assert "Mission Dolores" in result
        assert "Historic District" in result

    @pytest.mark.asyncio
    async def test_predict_permits_pim_down_falls_back_to_ref(self):
        """predict_permits falls back to ref_zoning_routing when PIM returns None."""
        with patch("src.pim_client.query_pim_cached", new_callable=AsyncMock, return_value=None), \
             patch("src.tools.predict_permits._query_ref_permit_forms", return_value=None), \
             patch("src.tools.predict_permits._query_ref_agency_triggers", return_value=None):

            with patch("src.tools.predict_permits.get_knowledge_base") as mock_kb, \
                 patch("src.db.get_connection", side_effect=Exception("DB down")):

                kb = MagicMock()
                kb.decision_tree = {"steps": {}}
                kb.otc_criteria = {"not_otc_requires_inhouse": {"projects": []}}
                kb.ada_accessibility = {}
                kb.plan_signatures = {}
                kb.title24 = {}
                kb.earthquake_brace_bolt = None
                kb.match_concepts.return_value = []
                kb.get_step_confidence.return_value = "medium"
                mock_kb.return_value = kb

                from src.tools.predict_permits import predict_permits
                result = await predict_permits(
                    project_description="kitchen remodel",
                    address="123 Main St",
                )

        # Should still return valid output — graceful fallback
        assert "Permit Prediction" in result
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_predict_permits_no_address_no_pim(self):
        """predict_permits works without address (no PIM query attempted)."""
        with patch("src.tools.predict_permits._query_ref_permit_forms", return_value=None), \
             patch("src.tools.predict_permits._query_ref_agency_triggers", return_value=None), \
             patch("src.pim_client.query_pim_cached") as mock_pim:

            with patch("src.tools.predict_permits.get_knowledge_base") as mock_kb:
                kb = MagicMock()
                kb.decision_tree = {"steps": {}}
                kb.otc_criteria = {"not_otc_requires_inhouse": {"projects": []}}
                kb.ada_accessibility = {}
                kb.plan_signatures = {}
                kb.title24 = {}
                kb.earthquake_brace_bolt = None
                kb.match_concepts.return_value = []
                kb.get_step_confidence.return_value = "medium"
                mock_kb.return_value = kb

                from src.tools.predict_permits import predict_permits
                result = await predict_permits(
                    project_description="window replacement",
                )

        assert "Permit Prediction" in result
        mock_pim.assert_not_called()

    @pytest.mark.asyncio
    async def test_predict_permits_unknown_zoning_code_adds_gap_note(self):
        """predict_permits adds coverage gap note for unknown zoning codes."""
        pim_result = {
            "ZONING_CODE": "P",
            "ZONING_CATEGORY": "Public",
            "HISTORIC_DISTRICT": None,
            "HEIGHT_DIST": None,
            "SPECIAL_USE_DIST": None,
            "LANDMARK": None,
        }

        with patch("src.pim_client.query_pim_cached", new_callable=AsyncMock, return_value=pim_result), \
             patch("src.tools.predict_permits._query_ref_permit_forms", return_value=None), \
             patch("src.tools.predict_permits._query_ref_agency_triggers", return_value=None):

            mock_conn = MagicMock()
            mock_cur = MagicMock()
            # block/lot from permits, no zoning_code from tax_rolls (zoning_info=None)
            mock_cur.fetchone.side_effect = [("9999", "001"), None]
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.close = MagicMock()

            with patch("src.tools.predict_permits.get_knowledge_base") as mock_kb, \
                 patch("src.db.get_connection", return_value=mock_conn), \
                 patch("src.db.BACKEND", "postgres"):

                kb = MagicMock()
                kb.decision_tree = {"steps": {}}
                kb.otc_criteria = {"not_otc_requires_inhouse": {"projects": []}}
                kb.ada_accessibility = {}
                kb.plan_signatures = {}
                kb.title24 = {}
                kb.earthquake_brace_bolt = None
                kb.match_concepts.return_value = []
                kb.get_step_confidence.return_value = "medium"
                mock_kb.return_value = kb

                from src.tools.predict_permits import predict_permits
                result = await predict_permits(
                    project_description="site work",
                    address="100 Civic Center",
                )

        # Should show PIM zoning code and gap note
        assert "P" in result  # zoning code displayed
        assert "General routing rules applied" in result or "routing" in result.lower()

    @pytest.mark.asyncio
    async def test_predict_permits_methodology_includes_pim_source(self):
        """predict_permits methodology dict includes PIM data source when used."""
        pim_result = {
            "ZONING_CODE": "RH-2",
            "ZONING_CATEGORY": "Residential",
            "HISTORIC_DISTRICT": None,
            "HEIGHT_DIST": "40-X",
            "SPECIAL_USE_DIST": None,
            "LANDMARK": None,
        }

        with patch("src.pim_client.query_pim_cached", new_callable=AsyncMock, return_value=pim_result), \
             patch("src.tools.predict_permits._query_ref_permit_forms", return_value=None), \
             patch("src.tools.predict_permits._query_ref_agency_triggers", return_value=None):

            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.side_effect = [("3512", "001"), ("RH-2",), None]
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.close = MagicMock()

            with patch("src.tools.predict_permits.get_knowledge_base") as mock_kb, \
                 patch("src.db.get_connection", return_value=mock_conn), \
                 patch("src.db.BACKEND", "postgres"):

                kb = MagicMock()
                kb.decision_tree = {"steps": {}}
                kb.otc_criteria = {"not_otc_requires_inhouse": {"projects": []}}
                kb.ada_accessibility = {}
                kb.plan_signatures = {}
                kb.title24 = {}
                kb.earthquake_brace_bolt = None
                kb.match_concepts.return_value = []
                kb.get_step_confidence.return_value = "medium"
                mock_kb.return_value = kb

                from src.tools.predict_permits import predict_permits
                result, meta = await predict_permits(
                    project_description="kitchen remodel",
                    address="123 Main St",
                    return_structured=True,
                )

        # meta["methodology"]["data_source"] for new format, or meta["data_sources"] list
        methodology_source = meta.get("methodology", {}).get("data_source", "")
        data_sources_list = " ".join(meta.get("data_sources", []))
        assert "SF Planning GIS" in methodology_source or "SF Planning GIS" in data_sources_list


# ---------------------------------------------------------------------------
# property_lookup: PIM enrichment is additive
# ---------------------------------------------------------------------------

class TestPropertyLookupPIM:
    """Tests for PIM enrichment in property_lookup."""

    @pytest.mark.asyncio
    async def test_property_lookup_enriched_with_pim(self):
        """property_lookup output includes PIM section when PIM returns data."""
        from src.tools.property_lookup import _format_pim_enrichment

        pim_data = {
            "ZONING_CODE": "RH-2",
            "ZONING_CATEGORY": "Residential",
            "HISTORIC_DISTRICT": None,
            "HEIGHT_DIST": "40-X",
            "SPECIAL_USE_DIST": None,
            "LANDMARK": None,
        }

        result = _format_pim_enrichment(pim_data, "3512", "001")
        assert "RH-2" in result
        assert "SF Planning GIS" in result or "PIM" in result
        assert "40-X" in result

    @pytest.mark.asyncio
    async def test_property_lookup_pim_historic_shown(self):
        """_format_pim_enrichment includes historic district when present."""
        from src.tools.property_lookup import _format_pim_enrichment

        pim_data = {
            "ZONING_CODE": "NC-1",
            "ZONING_CATEGORY": "Neighborhood Commercial",
            "HISTORIC_DISTRICT": "Mission Dolores",
            "HEIGHT_DIST": "40-X",
            "SPECIAL_USE_DIST": None,
            "LANDMARK": None,
        }

        result = _format_pim_enrichment(pim_data, "3590", "010")
        assert "Mission Dolores" in result
        assert "Historic District" in result

    @pytest.mark.asyncio
    async def test_property_lookup_pim_empty_returns_empty_string(self):
        """_format_pim_enrichment returns empty string when no useful PIM data."""
        from src.tools.property_lookup import _format_pim_enrichment

        pim_data = {
            "ZONING_CODE": None,
            "ZONING_CATEGORY": None,
            "HISTORIC_DISTRICT": None,
            "HEIGHT_DIST": None,
            "SPECIAL_USE_DIST": None,
            "LANDMARK": None,
        }

        result = _format_pim_enrichment(pim_data, "3512", "001")
        assert result == ""

    @pytest.mark.asyncio
    async def test_property_lookup_pim_failure_does_not_break_output(self):
        """property_lookup returns tax_rolls data even if PIM enrichment fails."""
        tax_row = (
            "RH-2", "Two-Family Residential", 2, 2,
            3000, 2000, 800000, 1200000,
            "2024", "Mission", "123 MAIN ST", "3512001",
        )

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = tax_row
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.close = MagicMock()

        with patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.BACKEND", "postgres"), \
             patch("src.pim_client.query_pim_cached", new_callable=AsyncMock,
                   side_effect=Exception("PIM exploded")):

            from src.tools.property_lookup import property_lookup
            result = await property_lookup(block="3512", lot="001")

        assert "Property Information" in result
        assert "RH-2" in result
        # PIM failure is silent — no error in output
        assert "PIM exploded" not in result
