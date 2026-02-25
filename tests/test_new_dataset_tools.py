"""Tests for Sprint 55C: planning_records, boiler_permits, tax_rolls, dev_pipeline
wired into permit_lookup, property_lookup, and predict_permits MCP tools."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_conn_duckdb(rows_by_query=None):
    """Return a mock DuckDB-style connection that returns preset rows."""
    rows_by_query = rows_by_query or {}

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return self._rows[0] if self._rows else None

    def _execute(sql, params=None):
        for key, rows in rows_by_query.items():
            if key in sql:
                return FakeResult(rows)
        return FakeResult([])

    conn = MagicMock()
    conn.execute = _execute
    conn.close = MagicMock()
    return conn


def make_conn_postgres(rows_by_query=None):
    """Return a mock psycopg2-style connection whose cursor returns preset rows by keyword."""
    rows_by_query = rows_by_query or {}
    call_order = list(rows_by_query.items())  # ordered list for sequential calls
    call_idx = [0]

    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)

    def _execute(sql, params=None):
        # Try keyword match first
        for key, rows in rows_by_query.items():
            if key in sql:
                cursor.fetchone.return_value = rows[0] if rows else None
                cursor.fetchall.return_value = rows
                return
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []

    cursor.execute = _execute
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.close = MagicMock()
    return conn


# ---------------------------------------------------------------------------
# permit_lookup — planning_records
# ---------------------------------------------------------------------------

class TestPermitLookupPlanningRecords:
    """Tests for _get_planning_records() helper."""

    def test_returns_planning_records_when_found(self):
        from src.tools.permit_lookup import _get_planning_records
        row = ("ENV-2022-001", "Environmental Review", "Approved",
               "Mixed use project", "Jane Smith", "2022-01-15", True)
        with patch("src.tools.permit_lookup.BACKEND", "duckdb"):
            conn = make_conn_duckdb({"planning_records": [row]})
            result = _get_planning_records(conn, "3512", "001")
        assert len(result) == 1
        assert result[0]["record_id"] == "ENV-2022-001"
        assert result[0]["record_type"] == "Environmental Review"
        assert result[0]["record_status"] == "Approved"
        assert result[0]["assigned_planner"] == "Jane Smith"
        assert result[0]["is_project"] is True

    def test_returns_empty_when_no_block_lot(self):
        from src.tools.permit_lookup import _get_planning_records
        conn = MagicMock()
        result = _get_planning_records(conn, None, None)
        assert result == []
        conn.execute.assert_not_called()

    def test_returns_empty_when_missing_block(self):
        from src.tools.permit_lookup import _get_planning_records
        conn = MagicMock()
        result = _get_planning_records(conn, "3512", None)
        assert result == []

    def test_returns_empty_when_missing_lot(self):
        from src.tools.permit_lookup import _get_planning_records
        conn = MagicMock()
        result = _get_planning_records(conn, None, "001")
        assert result == []

    def test_returns_empty_on_exception(self):
        from src.tools.permit_lookup import _get_planning_records
        conn = MagicMock()
        conn.execute.side_effect = Exception("Table does not exist")
        with patch("src.tools.permit_lookup.BACKEND", "duckdb"):
            result = _get_planning_records(conn, "3512", "001")
        assert result == []

    def test_returns_empty_when_no_records_found(self):
        from src.tools.permit_lookup import _get_planning_records
        with patch("src.tools.permit_lookup.BACKEND", "duckdb"):
            conn = make_conn_duckdb({"planning_records": []})
            result = _get_planning_records(conn, "9999", "999")
        assert result == []


# ---------------------------------------------------------------------------
# permit_lookup — boiler_permits
# ---------------------------------------------------------------------------

class TestPermitLookupBoilerPermits:
    """Tests for _get_boiler_permits() helper."""

    def test_returns_boiler_permits_when_found(self):
        from src.tools.permit_lookup import _get_boiler_permits
        row = ("BP-2023-100", "Steam Boiler", "Active", "2025-12-31", "100HP boiler")
        with patch("src.tools.permit_lookup.BACKEND", "duckdb"):
            conn = make_conn_duckdb({"boiler_permits": [row]})
            result = _get_boiler_permits(conn, "3512", "001")
        assert len(result) == 1
        assert result[0]["permit_number"] == "BP-2023-100"
        assert result[0]["boiler_type"] == "Steam Boiler"
        assert result[0]["status"] == "Active"
        assert result[0]["expiration_date"] == "2025-12-31"

    def test_returns_empty_when_no_block_lot(self):
        from src.tools.permit_lookup import _get_boiler_permits
        conn = MagicMock()
        result = _get_boiler_permits(conn, None, None)
        assert result == []
        conn.execute.assert_not_called()

    def test_returns_empty_on_exception(self):
        from src.tools.permit_lookup import _get_boiler_permits
        conn = MagicMock()
        conn.execute.side_effect = RuntimeError("DB error")
        with patch("src.tools.permit_lookup.BACKEND", "duckdb"):
            result = _get_boiler_permits(conn, "3512", "001")
        assert result == []

    def test_returns_empty_when_no_boilers(self):
        from src.tools.permit_lookup import _get_boiler_permits
        with patch("src.tools.permit_lookup.BACKEND", "duckdb"):
            conn = make_conn_duckdb({"boiler_permits": []})
            result = _get_boiler_permits(conn, "9999", "999")
        assert result == []


# ---------------------------------------------------------------------------
# permit_lookup — development_pipeline
# ---------------------------------------------------------------------------

class TestPermitLookupDevPipeline:
    """Tests for _get_dev_pipeline() helper."""

    def test_returns_pipeline_data_when_found(self):
        from src.tools.permit_lookup import _get_dev_pipeline
        row = ("2022-001", "100 Main St", "BP Filed", 24, 24, "RH-2")
        with patch("src.tools.permit_lookup.BACKEND", "duckdb"):
            conn = make_conn_duckdb({"development_pipeline": [row]})
            result = _get_dev_pipeline(conn, "3512", "001")
        assert len(result) == 1
        assert result[0]["record_id"] == "2022-001"
        assert result[0]["current_status"] == "BP Filed"
        assert result[0]["proposed_units"] == 24
        assert result[0]["zoning_district"] == "RH-2"

    def test_returns_empty_when_no_block_lot(self):
        from src.tools.permit_lookup import _get_dev_pipeline
        conn = MagicMock()
        result = _get_dev_pipeline(conn, None, None)
        assert result == []
        conn.execute.assert_not_called()

    def test_returns_empty_on_exception_table_missing(self):
        from src.tools.permit_lookup import _get_dev_pipeline
        conn = MagicMock()
        conn.execute.side_effect = Exception("relation development_pipeline does not exist")
        with patch("src.tools.permit_lookup.BACKEND", "duckdb"):
            result = _get_dev_pipeline(conn, "3512", "001")
        assert result == []

    def test_returns_empty_when_no_pipeline_entries(self):
        from src.tools.permit_lookup import _get_dev_pipeline
        with patch("src.tools.permit_lookup.BACKEND", "duckdb"):
            conn = make_conn_duckdb({"development_pipeline": []})
            result = _get_dev_pipeline(conn, "9999", "999")
        assert result == []


# ---------------------------------------------------------------------------
# permit_lookup — formatters
# ---------------------------------------------------------------------------

class TestPermitLookupFormatters:
    """Tests for the new _format_* functions."""

    def test_format_planning_records_returns_markdown_table(self):
        from src.tools.permit_lookup import _format_planning_records
        records = [
            {"record_id": "ENV-001", "record_type": "EIR", "record_status": "Active",
             "open_date": "2022-01-01", "assigned_planner": "Smith", "description": "New building"},
        ]
        result = _format_planning_records(records)
        assert "ENV-001" in result
        assert "EIR" in result
        assert "Smith" in result

    def test_format_planning_records_empty_returns_empty_string(self):
        from src.tools.permit_lookup import _format_planning_records
        assert _format_planning_records([]) == ""

    def test_format_boiler_permits_returns_markdown_table(self):
        from src.tools.permit_lookup import _format_boiler_permits
        boilers = [
            {"permit_number": "BP-001", "boiler_type": "Steam", "status": "Active",
             "expiration_date": "2025-01-01", "description": "100HP unit"},
        ]
        result = _format_boiler_permits(boilers)
        assert "BP-001" in result
        assert "Steam" in result
        assert "Active" in result

    def test_format_boiler_permits_empty_returns_empty_string(self):
        from src.tools.permit_lookup import _format_boiler_permits
        assert _format_boiler_permits([]) == ""

    def test_format_dev_pipeline_returns_markdown_table(self):
        from src.tools.permit_lookup import _format_dev_pipeline
        pipeline = [
            {"record_id": "2022-001", "name_address": "100 Main", "current_status": "BP Filed",
             "proposed_units": 10, "net_pipeline_units": 10, "zoning_district": "RH-2"},
        ]
        result = _format_dev_pipeline(pipeline)
        assert "2022-001" in result
        assert "BP Filed" in result
        assert "RH-2" in result

    def test_format_dev_pipeline_empty_returns_empty_string(self):
        from src.tools.permit_lookup import _format_dev_pipeline
        assert _format_dev_pipeline([]) == ""


# ---------------------------------------------------------------------------
# property_lookup — format_tax_roll_local (sync, no DB needed)
# ---------------------------------------------------------------------------

class TestPropertyLookupLocalFormatter:
    """Tests for property_lookup local tax_rolls formatter."""

    def test_format_tax_roll_local_includes_all_fields(self):
        from src.tools.property_lookup import _format_tax_roll_local
        row = (
            "NC-3", "Neighborhood Commercial", 3, 6,
            4000.0, 5400.0, 1200000.0, 800000.0,
            "2023", "Mission", "456 VALENCIA ST", "3601015",
        )
        result = _format_tax_roll_local(row)
        assert "NC-3" in result
        assert "Neighborhood Commercial" in result
        assert "Mission" in result
        assert "1,200,000" in result
        assert "2,000,000" in result  # total (land + improvements)

    def test_format_tax_roll_local_handles_missing_values(self):
        from src.tools.property_lookup import _format_tax_roll_local
        row = (
            None, None, None, None,
            None, None, None, None,
            "2023", None, None, None,
        )
        # Should not raise
        result = _format_tax_roll_local(row)
        assert "2023" in result


# ---------------------------------------------------------------------------
# property_lookup — DB fallback via src.db patching
# ---------------------------------------------------------------------------

class TestPropertyLookupDbFallback:
    """Tests for property_lookup local DB → SODA fallback chain."""

    @pytest.mark.asyncio
    async def test_uses_local_db_when_block_and_lot_provided(self):
        """When block+lot are provided and local DB has data, return local result."""
        row = (
            "RH-2", "Single Family Dwelling", 2, 1,
            2500.0, 1800.0, 500000.0, 300000.0,
            "2023", "Noe Valley", "123 MAIN ST", "3512001",
        )
        mock_conn = make_conn_duckdb({"tax_rolls": [row]})

        # property_lookup imports get_connection and BACKEND locally from src.db
        with patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.BACKEND", "duckdb"):
            from src.tools.property_lookup import property_lookup
            result = await property_lookup(block="3512", lot="001")

        assert "RH-2" in result
        assert "Single Family Dwelling" in result
        assert "Noe Valley" in result
        assert "500,000" in result  # land value formatted

    @pytest.mark.asyncio
    async def test_falls_back_to_soda_when_local_empty(self):
        """When local DB returns no row, falls through to SODA call."""
        mock_conn = make_conn_duckdb({"tax_rolls": []})  # Empty

        with patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.BACKEND", "duckdb"), \
             patch("src.tools.property_lookup.SODAClient") as mock_soda_cls, \
             patch("src.tools.property_lookup.format_property", return_value="SODA result"):
            mock_soda = AsyncMock()
            mock_soda.query = AsyncMock(return_value=[{"property_location": "123 MAIN"}])
            mock_soda.close = AsyncMock()
            mock_soda_cls.return_value = mock_soda

            from src.tools.property_lookup import property_lookup
            result = await property_lookup(block="3512", lot="001")

        assert result == "SODA result"

    @pytest.mark.asyncio
    async def test_falls_back_to_soda_on_db_exception(self):
        """When local DB raises an exception, falls through to SODA."""
        with patch("src.db.get_connection", side_effect=Exception("DB unavailable")), \
             patch("src.db.BACKEND", "duckdb"), \
             patch("src.tools.property_lookup.SODAClient") as mock_soda_cls, \
             patch("src.tools.property_lookup.format_property", return_value="SODA fallback"):
            mock_soda = AsyncMock()
            mock_soda.query = AsyncMock(return_value=[{"property_location": "123 MAIN"}])
            mock_soda.close = AsyncMock()
            mock_soda_cls.return_value = mock_soda

            from src.tools.property_lookup import property_lookup
            result = await property_lookup(block="3512", lot="001")

        assert result == "SODA fallback"

    @pytest.mark.asyncio
    async def test_returns_error_when_no_params(self):
        from src.tools.property_lookup import property_lookup
        result = await property_lookup()
        assert "Please provide" in result


# ---------------------------------------------------------------------------
# predict_permits — zoning_info enrichment via src.db patching
# ---------------------------------------------------------------------------

class TestPredictPermitsZoningContext:
    """Tests for predict_permits zoning context DB lookup."""

    @pytest.mark.asyncio
    async def test_predict_permits_works_without_address(self):
        """predict_permits works normally when no address — no DB query needed."""
        from src.tools.predict_permits import predict_permits
        result = await predict_permits(
            project_description="kitchen remodel in residential home",
        )
        assert "Permit Prediction" in result
        # No zoning context without address
        assert "Zoning Context" not in result

    @pytest.mark.asyncio
    async def test_predict_permits_graceful_when_db_fails(self):
        """predict_permits still returns valid output when DB query fails."""
        with patch("src.db.get_connection", side_effect=Exception("DB down")):
            from src.tools.predict_permits import predict_permits
            result = await predict_permits(
                project_description="restaurant build-out with kitchen and dining room",
                address="456 Valencia St",
            )
        # Should still return a valid prediction, just without zoning context
        assert "Permit Prediction" in result
        assert "Zoning Context" not in result

    @pytest.mark.asyncio
    async def test_predict_permits_graceful_when_ref_table_empty(self):
        """predict_permits works when ref_zoning_routing has no matching row."""
        mock_conn = make_conn_duckdb({})  # Returns empty for all queries

        with patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.BACKEND", "duckdb"):
            from src.tools.predict_permits import predict_permits
            result = await predict_permits(
                project_description="new adu construction in backyard",
                address="789 Market St",
            )

        assert "Permit Prediction" in result
        # No zoning context since all queries returned empty
        assert "Zoning Context" not in result

    @pytest.mark.asyncio
    async def test_predict_permits_queries_ref_zoning_when_address_and_data_present(self):
        """predict_permits includes zoning context when DB lookup chain succeeds."""
        # Set up DuckDB mock: permits → block/lot, tax_rolls → zoning, ref_zoning_routing → details
        call_results = {
            "permits": [("3512", "001")],
            "tax_rolls": [("RH-2",)],
            "ref_zoning_routing": [("RH-2", "Residential", False, False, False)],
        }
        mock_conn = make_conn_duckdb(call_results)

        with patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.BACKEND", "duckdb"):
            from src.tools.predict_permits import predict_permits
            result = await predict_permits(
                project_description="kitchen remodel",
                address="123 Main St",
            )

        assert "Permit Prediction" in result
        assert "Zoning Context" in result
        assert "RH-2" in result
        assert "Residential" in result
