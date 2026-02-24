"""Tests for property_health MCP tool."""

import json
from datetime import date, timedelta

import duckdb
import pytest

from src.db import init_schema
from src.signals.pipeline import run_signal_pipeline


TODAY = date(2026, 2, 23)


@pytest.fixture
def health_db(tmp_path):
    path = str(tmp_path / "health_tool_test.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)

    # Insert a violation → pipeline will produce property_health
    conn.execute(
        "INSERT INTO violations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [1, "C001", "1", str(TODAY - timedelta(days=30)),
         "3512", "001", "100", "MARKET", "ST", None, "open",
         None, None, "Notice of Violation", None, None, "SoMa", "6", "94105", str(TODAY)],
    )

    # Run pipeline to populate property_health
    run_signal_pipeline(conn, backend="duckdb")
    conn.close()
    return path


@pytest.fixture(autouse=True)
def _patch_db(health_db, monkeypatch):
    import src.tools.property_health as ph_mod

    original = ph_mod.get_connection

    def patched(db_path=None):
        return original(db_path=health_db)

    monkeypatch.setattr(ph_mod, "get_connection", patched)


@pytest.mark.asyncio
async def test_lookup_by_block_lot():
    from src.tools.property_health import property_health
    result = await property_health(block="3512", lot="001")
    assert "Property Health" in result
    assert "AT RISK" in result


@pytest.mark.asyncio
async def test_lookup_by_combined_key():
    from src.tools.property_health import property_health
    result = await property_health(block_lot="3512/001")
    assert "AT RISK" in result


@pytest.mark.asyncio
async def test_not_found():
    from src.tools.property_health import property_health
    result = await property_health(block_lot="9999/999")
    assert "No pre-computed health data" in result


@pytest.mark.asyncio
async def test_no_input():
    from src.tools.property_health import property_health
    result = await property_health()
    assert "Please provide" in result


@pytest.mark.asyncio
async def test_includes_signals_table():
    from src.tools.property_health import property_health
    result = await property_health(block_lot="3512/001")
    assert "Signals" in result
    assert "nov" in result


@pytest.mark.asyncio
async def test_db_unavailable(monkeypatch):
    import src.tools.property_health as ph_mod

    def broken(db_path=None):
        raise ConnectionError("down")

    monkeypatch.setattr(ph_mod, "get_connection", broken)

    from src.tools.property_health import property_health
    result = await property_health(block_lot="3512/001")
    assert "unavailable" in result.lower()
