"""Tests for QS5-C: Trade permit bridge + orphan inspection DQ checks."""

import pytest
from unittest.mock import patch


# ── _check_orphan_inspections ──────────────────────────────────────


class TestCheckOrphanInspections:
    """Tests for the orphan inspection DQ check."""

    def test_returns_structured_dq_result(self):
        """_check_orphan_inspections returns dict with required fields."""
        from web.data_quality import _check_orphan_inspections
        result = _check_orphan_inspections()
        assert isinstance(result, dict)
        assert "name" in result
        assert "category" in result
        assert "value" in result
        assert "status" in result
        assert "detail" in result
        assert result["name"] == "Orphan Inspections"
        assert result["category"] == "completeness"

    def test_green_when_orphan_rate_below_5_pct(self):
        """Green status when orphan rate < 5%."""
        from web.data_quality import _check_orphan_inspections
        with patch("web.data_quality._timed_query") as mock_q:
            # 2 orphans out of 100 permit-type inspections = 2%
            mock_q.side_effect = [[(2,)], [(100,)]]
            result = _check_orphan_inspections()
            assert result["status"] == "green"
            assert "2.0%" in result["value"] or "2.00%" in result["value"]

    def test_yellow_when_orphan_rate_5_to_15_pct(self):
        """Yellow status when orphan rate 5-15%."""
        from web.data_quality import _check_orphan_inspections
        with patch("web.data_quality._timed_query") as mock_q:
            # 10 orphans out of 100 = 10%
            mock_q.side_effect = [[(10,)], [(100,)]]
            result = _check_orphan_inspections()
            assert result["status"] == "yellow"

    def test_red_when_orphan_rate_above_15_pct(self):
        """Red status when orphan rate > 15%."""
        from web.data_quality import _check_orphan_inspections
        with patch("web.data_quality._timed_query") as mock_q:
            # 20 orphans out of 100 = 20%
            mock_q.side_effect = [[(20,)], [(100,)]]
            result = _check_orphan_inspections()
            assert result["status"] == "red"

    def test_yellow_at_boundary_15_pct(self):
        """Yellow status at exactly 15% (boundary)."""
        from web.data_quality import _check_orphan_inspections
        with patch("web.data_quality._timed_query") as mock_q:
            # 15 orphans out of 100 = 15%
            mock_q.side_effect = [[(15,)], [(100,)]]
            result = _check_orphan_inspections()
            assert result["status"] == "yellow"

    def test_handles_query_error_gracefully(self):
        """Returns yellow on query failure."""
        from web.data_quality import _check_orphan_inspections
        with patch("web.data_quality._timed_query", side_effect=Exception("timeout")):
            result = _check_orphan_inspections()
            assert result["status"] == "yellow"
            assert "Error" in result["value"]


# ── _check_trade_permit_counts ─────────────────────────────────────


class TestCheckTradePermitCounts:
    """Tests for the trade permit count DQ check."""

    def test_returns_structured_dq_result(self):
        """_check_trade_permit_counts returns dict with required fields."""
        from web.data_quality import _check_trade_permit_counts
        result = _check_trade_permit_counts()
        assert isinstance(result, dict)
        assert "name" in result
        assert "category" in result
        assert "value" in result
        assert "status" in result
        assert "detail" in result
        assert result["name"] == "Trade Permits"

    def test_green_when_both_tables_have_data(self):
        """Green when both boiler and fire tables are populated."""
        from web.data_quality import _check_trade_permit_counts
        with patch("web.data_quality._timed_query") as mock_q:
            mock_q.side_effect = [[(151000,)], [(84000,)]]
            result = _check_trade_permit_counts()
            assert result["status"] == "green"
            assert "235,000" in result["value"]

    def test_red_when_boiler_empty(self):
        """Red when boiler_permits table is empty."""
        from web.data_quality import _check_trade_permit_counts
        with patch("web.data_quality._timed_query") as mock_q:
            mock_q.side_effect = [[(0,)], [(84000,)]]
            result = _check_trade_permit_counts()
            assert result["status"] == "red"
            assert "boiler_permits" in result["detail"]

    def test_red_when_fire_empty(self):
        """Red when fire_permits table is empty."""
        from web.data_quality import _check_trade_permit_counts
        with patch("web.data_quality._timed_query") as mock_q:
            mock_q.side_effect = [[(151000,)], [(0,)]]
            result = _check_trade_permit_counts()
            assert result["status"] == "red"
            assert "fire_permits" in result["detail"]

    def test_red_when_both_empty(self):
        """Red when both tables are empty."""
        from web.data_quality import _check_trade_permit_counts
        with patch("web.data_quality._timed_query") as mock_q:
            mock_q.side_effect = [[(0,)], [(0,)]]
            result = _check_trade_permit_counts()
            assert result["status"] == "red"
            assert "boiler_permits" in result["detail"]
            assert "fire_permits" in result["detail"]

    def test_handles_query_error_gracefully(self):
        """Returns red on query failure (pipeline broken)."""
        from web.data_quality import _check_trade_permit_counts
        with patch("web.data_quality._timed_query", side_effect=Exception("no table")):
            result = _check_trade_permit_counts()
            assert result["status"] == "red"
            assert "Error" in result["value"]


# ── EXPECTED_TABLES ────────────────────────────────────────────────


class TestExpectedTables:
    """Verify EXPECTED_TABLES includes trade permit tables."""

    def test_boiler_permits_in_expected_tables(self):
        """boiler_permits is in EXPECTED_TABLES."""
        from web.app import EXPECTED_TABLES
        assert "boiler_permits" in EXPECTED_TABLES

    def test_fire_permits_in_expected_tables(self):
        """fire_permits is in EXPECTED_TABLES."""
        from web.app import EXPECTED_TABLES
        assert "fire_permits" in EXPECTED_TABLES


# ── Schema checks ─────────────────────────────────────────────────


class TestTradePermitSchemas:
    """Verify trade permit table schemas match expectations."""

    def test_boiler_permits_has_block_lot(self):
        """boiler_permits table has block and lot columns."""
        from src.db import get_connection, init_schema
        conn = get_connection()
        init_schema(conn)
        cols = conn.execute("DESCRIBE boiler_permits").fetchall()
        col_names = [c[0] for c in cols]
        assert "block" in col_names
        assert "lot" in col_names

    def test_fire_permits_lacks_block_lot(self):
        """fire_permits table does NOT have block or lot columns."""
        from src.db import get_connection, init_schema
        conn = get_connection()
        init_schema(conn)
        cols = conn.execute("DESCRIBE fire_permits").fetchall()
        col_names = [c[0] for c in cols]
        assert "block" not in col_names
        assert "lot" not in col_names
