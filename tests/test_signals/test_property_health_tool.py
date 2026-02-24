"""Tests for src.tools.property_health — MCP tool for pre-computed health lookup."""

import json
import pytest
import duckdb
from unittest.mock import patch

from src.tools.property_health import property_health


@pytest.fixture
def health_db():
    """In-memory DuckDB with permits and property_health tables."""
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE permits (
            permit_number VARCHAR(30) PRIMARY KEY,
            status VARCHAR(20),
            block VARCHAR(10),
            lot VARCHAR(10),
            street_number VARCHAR(10),
            street_name VARCHAR(50)
        )
    """)
    c.execute("""
        CREATE TABLE property_health (
            block_lot VARCHAR(20) PRIMARY KEY,
            tier VARCHAR(20) NOT NULL,
            signal_count INTEGER DEFAULT 0,
            at_risk_count INTEGER DEFAULT 0,
            signals_json TEXT,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    yield c
    c.close()


def _seed(conn, block_lot="3512/001", tier="at_risk", signal_count=2, at_risk_count=1, signals=None):
    """Insert a property_health row."""
    sigs = signals or [{"type": "nov", "severity": "at_risk", "permit": None, "detail": "2 open NOVs"}]
    conn.execute(
        "INSERT INTO property_health (block_lot, tier, signal_count, at_risk_count, signals_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (block_lot, tier, signal_count, at_risk_count, json.dumps(sigs)),
    )


def _seed_permit(conn, permit_number="P001", block="3512", lot="001", snum="100", sname="Market"):
    conn.execute(
        "INSERT INTO permits (permit_number, status, block, lot, street_number, street_name) "
        "VALUES (?, 'filed', ?, ?, ?, ?)",
        (permit_number, block, lot, snum, sname),
    )


# ── Input validation ─────────────────────────────────────────────

class TestInputValidation:
    @pytest.mark.asyncio
    async def test_no_params_returns_help(self):
        result = await property_health()
        assert "Please provide" in result

    @pytest.mark.asyncio
    async def test_blank_block_lot_returns_help(self):
        result = await property_health(block="", lot="")
        assert "Please provide" in result

    @pytest.mark.asyncio
    async def test_block_without_lot_returns_help(self):
        result = await property_health(block="3512", lot="")
        assert "Please provide" in result

    @pytest.mark.asyncio
    async def test_street_number_without_name_returns_help(self):
        result = await property_health(street_number="100", street_name="")
        assert "Please provide" in result


# ── Block/lot lookup ─────────────────────────────────────────────

class TestBlockLotLookup:
    @pytest.mark.asyncio
    async def test_found(self, health_db):
        _seed(health_db)
        with patch("src.tools.property_health.get_connection", return_value=health_db):
            with patch("src.tools.property_health.BACKEND", "duckdb"):
                result = await property_health(block="3512", lot="001")
        assert "3512/001" in result
        assert "AT RISK" in result

    @pytest.mark.asyncio
    async def test_not_found(self, health_db):
        with patch("src.tools.property_health.get_connection", return_value=health_db):
            with patch("src.tools.property_health.BACKEND", "duckdb"):
                result = await property_health(block="9999", lot="999")
        assert "No health data" in result

    @pytest.mark.asyncio
    async def test_high_risk_tier(self, health_db):
        _seed(health_db, tier="high_risk", signal_count=4, at_risk_count=3, signals=[
            {"type": "hold_comments", "severity": "at_risk", "permit": "P001", "detail": "test"},
            {"type": "nov", "severity": "at_risk", "permit": None, "detail": "test2"},
        ])
        with patch("src.tools.property_health.get_connection", return_value=health_db):
            with patch("src.tools.property_health.BACKEND", "duckdb"):
                result = await property_health(block="3512", lot="001")
        assert "HIGH RISK" in result
        assert "Immediate review" in result

    @pytest.mark.asyncio
    async def test_on_track_tier(self, health_db):
        _seed(health_db, tier="on_track", signal_count=0, at_risk_count=0, signals=[])
        with patch("src.tools.property_health.get_connection", return_value=health_db):
            with patch("src.tools.property_health.BACKEND", "duckdb"):
                result = await property_health(block="3512", lot="001")
        assert "ON TRACK" in result
        assert "No negative signals" in result

    @pytest.mark.asyncio
    async def test_behind_tier(self, health_db):
        _seed(health_db, tier="behind", signal_count=1, at_risk_count=0, signals=[
            {"type": "hold_stalled", "severity": "behind", "permit": "P001", "detail": "stalled"},
        ])
        with patch("src.tools.property_health.get_connection", return_value=health_db):
            with patch("src.tools.property_health.BACKEND", "duckdb"):
                result = await property_health(block="3512", lot="001")
        assert "BEHIND" in result
        assert "Monitor" in result

    @pytest.mark.asyncio
    async def test_slower_tier(self, health_db):
        _seed(health_db, tier="slower", signal_count=1, at_risk_count=0, signals=[
            {"type": "complaint", "severity": "slower", "permit": None, "detail": "test"},
        ])
        with patch("src.tools.property_health.get_connection", return_value=health_db):
            with patch("src.tools.property_health.BACKEND", "duckdb"):
                result = await property_health(block="3512", lot="001")
        assert "SLOWER" in result
        assert "quarterly" in result

    @pytest.mark.asyncio
    async def test_signals_table_rendered(self, health_db):
        _seed(health_db, signals=[
            {"type": "nov", "severity": "at_risk", "permit": None, "detail": "2 open NOVs"},
            {"type": "hold_comments", "severity": "at_risk", "permit": "P001", "detail": "CPC"},
        ])
        with patch("src.tools.property_health.get_connection", return_value=health_db):
            with patch("src.tools.property_health.BACKEND", "duckdb"):
                result = await property_health(block="3512", lot="001")
        assert "| nov |" in result
        assert "| hold_comments |" in result
        assert "## Signals" in result


# ── Address lookup ───────────────────────────────────────────────

class TestAddressLookup:
    @pytest.mark.asyncio
    async def test_address_resolves_to_block_lot(self, health_db):
        _seed_permit(health_db)
        _seed(health_db)
        with patch("src.tools.property_health.get_connection", return_value=health_db):
            with patch("src.tools.property_health.BACKEND", "duckdb"):
                result = await property_health(street_number="100", street_name="Market")
        assert "3512/001" in result
        assert "AT RISK" in result

    @pytest.mark.asyncio
    async def test_address_not_found(self, health_db):
        with patch("src.tools.property_health.get_connection", return_value=health_db):
            with patch("src.tools.property_health.BACKEND", "duckdb"):
                result = await property_health(street_number="999", street_name="Nowhere")
        assert "No property found" in result

    @pytest.mark.asyncio
    async def test_address_case_insensitive(self, health_db):
        _seed_permit(health_db)
        _seed(health_db)
        with patch("src.tools.property_health.get_connection", return_value=health_db):
            with patch("src.tools.property_health.BACKEND", "duckdb"):
                result = await property_health(street_number="100", street_name="market")
        assert "3512/001" in result


# ── DB unavailable ───────────────────────────────────────────────

class TestDbUnavailable:
    @pytest.mark.asyncio
    async def test_db_unavailable(self):
        with patch("src.tools.property_health.get_connection", side_effect=Exception("no db")):
            result = await property_health(block="3512", lot="001")
        assert "Database unavailable" in result
