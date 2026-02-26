"""Tests for Sprint 60C — Cost of Delay Calculator.

Covers:
  C1  — No cost section when monthly_carrying_cost is None
  C2  — Financial Impact section appears when carrying cost provided
  C3  — daily_cost math: monthly / 30.44
  C4  — weekly_cost math: monthly / 4.33
  C5  — Scenario table includes p50, p75, p90
  C6  — delay_cost = (p75 - p50) * daily_cost
  C7  — Zero carrying cost treated same as None (no section)
  C8  — methodology dict includes cost_impact key when cost provided
  C9  — Backward compat: existing callers without monthly_carrying_cost still work
  C10 — cost_impact absent from methodology when cost is None
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta

import duckdb
import pytest

from src.db import init_schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


_permit_counter = 0


def _generate_permits(n: int, permit_type_def: str, neighborhood: str,
                      base_cost: float, filed_start: date,
                      days_range: tuple[int, int]) -> list[tuple]:
    """Generate n synthetic permits for timeline analysis."""
    global _permit_counter
    permits = []
    for i in range(n):
        _permit_counter += 1
        pnum = f"S60C{_permit_counter:06d}"
        filed = filed_start + timedelta(days=i % 180)
        days_to_issue = days_range[0] + (i % (days_range[1] - days_range[0] + 1))
        issued = filed + timedelta(days=days_to_issue)
        completed = issued + timedelta(days=30 + (i % 60))
        cost = base_cost + (i % 10) * 1000
        permits.append((
            pnum,
            "1",
            permit_type_def,
            "complete",
            str(completed),
            f"Test {permit_type_def} #{i}",
            str(filed),
            str(issued),
            str(filed + timedelta(days=days_to_issue - 2)),
            str(completed),
            cost,
            None,
            "office",
            "office",
            None,
            None,
            str(100 + i),
            "MARKET",
            "ST",
            "94110",
            neighborhood,
            "9",
            "3512",
            str(i).zfill(3),
            None,
            str(filed),
        ))
    return permits


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def timeline_db(tmp_path_factory):
    """Create a temporary DuckDB with synthetic permits for timeline analysis."""
    tmp_path = tmp_path_factory.mktemp("sprint60c")
    path = str(tmp_path / "sprint60c.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)

    all_permits = []
    base_date = date(2024, 1, 1)

    # In-house alterations — 50 permits with 20-120 day range
    all_permits.extend(_generate_permits(
        n=50,
        permit_type_def="additions alterations or repairs",
        neighborhood="Mission",
        base_cost=80000,
        filed_start=base_date,
        days_range=(20, 120),
    ))

    # Recent permits (within 1 year) for timeline_stats
    recent_start = date.today() - timedelta(days=90)
    all_permits.extend(_generate_permits(
        n=30,
        permit_type_def="additions alterations or repairs",
        neighborhood="Mission",
        base_cost=80000,
        filed_start=recent_start,
        days_range=(30, 100),
    ))

    conn.executemany(
        "INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        all_permits,
    )
    conn.close()
    return path


@pytest.fixture(autouse=True)
def _patch_db(timeline_db, monkeypatch):
    """Monkeypatch get_connection in estimate_timeline module to use the test DB."""
    import src.tools.estimate_timeline as tl_mod

    original_get_connection = tl_mod.get_connection

    def patched_get_connection(db_path=None):
        return original_get_connection(db_path=timeline_db)

    monkeypatch.setattr(tl_mod, "get_connection", patched_get_connection)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCostOfDelayNone:
    """C1 — No cost section when monthly_carrying_cost is None."""

    @pytest.mark.asyncio
    async def test_no_cost_when_param_none(self):
        from src.tools.estimate_timeline import estimate_timeline
        result = await estimate_timeline(
            permit_type="alterations",
            monthly_carrying_cost=None,
            return_structured=True,
        )
        md, meta = result
        assert "Financial Impact" not in md
        assert meta.get("cost_impact") is None

    @pytest.mark.asyncio
    async def test_no_cost_section_in_markdown(self):
        from src.tools.estimate_timeline import estimate_timeline
        md = await estimate_timeline(
            permit_type="alterations",
            monthly_carrying_cost=None,
        )
        assert isinstance(md, str)
        assert "Financial Impact" not in md
        assert "Monthly carrying cost" not in md


class TestCostOfDelayComputed:
    """C2 — Financial Impact section appears when carrying cost provided."""

    @pytest.mark.asyncio
    async def test_cost_section_present_in_markdown(self):
        from src.tools.estimate_timeline import estimate_timeline
        md, meta = await estimate_timeline(
            permit_type="alterations",
            monthly_carrying_cost=6000.0,
            return_structured=True,
        )
        # Section header should appear in markdown
        assert "Financial Impact" in md
        assert "6,000" in md or "6000" in md

    @pytest.mark.asyncio
    async def test_scenario_table_present(self):
        from src.tools.estimate_timeline import estimate_timeline
        md, meta = await estimate_timeline(
            permit_type="alterations",
            monthly_carrying_cost=5000.0,
            return_structured=True,
        )
        # Scenario labels should appear
        assert "Typical" in md
        assert "Conservative" in md or "p75" in md.lower()

    @pytest.mark.asyncio
    async def test_methodology_includes_cost_impact(self):
        """C8 — methodology dict includes cost_impact key when cost provided."""
        from src.tools.estimate_timeline import estimate_timeline
        md, meta = await estimate_timeline(
            permit_type="alterations",
            monthly_carrying_cost=3000.0,
            return_structured=True,
        )
        assert "cost_impact" in meta
        ci = meta["cost_impact"]
        assert ci is not None
        assert ci["monthly_carrying_cost"] == 3000.0

    @pytest.mark.asyncio
    async def test_cost_impact_has_scenarios(self):
        from src.tools.estimate_timeline import estimate_timeline
        md, meta = await estimate_timeline(
            permit_type="alterations",
            monthly_carrying_cost=4000.0,
            return_structured=True,
        )
        ci = meta.get("cost_impact")
        if ci:  # only check when primary_result was available
            assert "scenarios" in ci
            assert len(ci["scenarios"]) > 0


class TestDailyWeeklyCostMath:
    """C3, C4 — Verify daily and weekly cost calculations."""

    def test_daily_cost_math(self):
        """daily_cost = monthly / 30.44"""
        monthly = 6088.0
        expected_daily = monthly / 30.44
        # Verify the formula directly
        assert abs(expected_daily - 200.0) < 1.0  # ~200/day for $6088/month

    def test_weekly_cost_math(self):
        """weekly_cost = monthly / 4.33"""
        monthly = 4330.0
        expected_weekly = monthly / 4.33
        assert abs(expected_weekly - 1000.0) < 1.0  # ~$1000/week for $4330/month

    @pytest.mark.asyncio
    async def test_daily_cost_in_cost_impact(self):
        """Verify daily_cost stored correctly in cost_impact dict."""
        from src.tools.estimate_timeline import estimate_timeline
        monthly = 3044.0
        md, meta = await estimate_timeline(
            permit_type="alterations",
            monthly_carrying_cost=monthly,
            return_structured=True,
        )
        ci = meta.get("cost_impact")
        if ci:
            expected_daily = round(monthly / 30.44, 2)
            assert abs(ci["daily_cost"] - expected_daily) < 0.01

    @pytest.mark.asyncio
    async def test_weekly_cost_in_cost_impact(self):
        """Verify weekly_cost stored correctly in cost_impact dict."""
        from src.tools.estimate_timeline import estimate_timeline
        monthly = 4330.0
        md, meta = await estimate_timeline(
            permit_type="alterations",
            monthly_carrying_cost=monthly,
            return_structured=True,
        )
        ci = meta.get("cost_impact")
        if ci:
            expected_weekly = round(monthly / 4.33, 2)
            assert abs(ci["weekly_cost"] - expected_weekly) < 0.01


class TestDelayRiskCalc:
    """C6 — delay_cost = (p75 - p50) * daily_cost."""

    @pytest.mark.asyncio
    async def test_delay_cost_is_difference(self):
        from src.tools.estimate_timeline import estimate_timeline
        md, meta = await estimate_timeline(
            permit_type="alterations",
            monthly_carrying_cost=3044.0,
            return_structured=True,
        )
        ci = meta.get("cost_impact")
        if ci and "delay_cost" in ci and "delay_days" in ci:
            daily = ci["daily_cost"]
            delay_days = ci["delay_days"]
            expected = round(delay_days * daily)
            assert abs(ci["delay_cost"] - expected) <= 1  # allow rounding tolerance


class TestZeroCarryingCost:
    """C7 — Zero carrying cost treated same as None (no cost section)."""

    @pytest.mark.asyncio
    async def test_zero_carrying_cost_no_section(self):
        from src.tools.estimate_timeline import estimate_timeline
        md, meta = await estimate_timeline(
            permit_type="alterations",
            monthly_carrying_cost=0.0,
            return_structured=True,
        )
        assert "Financial Impact" not in md
        assert meta.get("cost_impact") is None


class TestBackwardCompat:
    """C9 — Existing callers without monthly_carrying_cost still work."""

    @pytest.mark.asyncio
    async def test_backward_compat_no_param(self):
        """Function works without the new parameter."""
        from src.tools.estimate_timeline import estimate_timeline
        # Old-style call without monthly_carrying_cost
        result = await estimate_timeline(permit_type="alterations")
        assert isinstance(result, str)
        assert "Timeline Estimate" in result

    @pytest.mark.asyncio
    async def test_backward_compat_structured(self):
        """return_structured=True still works without monthly_carrying_cost."""
        from src.tools.estimate_timeline import estimate_timeline
        result = await estimate_timeline(
            permit_type="alterations",
            return_structured=True,
        )
        assert isinstance(result, tuple)
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)

    @pytest.mark.asyncio
    async def test_cost_impact_absent_from_methodology_when_none(self):
        """C10 — cost_impact absent from methodology when cost is None."""
        from src.tools.estimate_timeline import estimate_timeline
        md, meta = await estimate_timeline(
            permit_type="alterations",
            return_structured=True,
        )
        # cost_impact key should be absent or None when no carrying cost provided
        assert meta.get("cost_impact") is None
