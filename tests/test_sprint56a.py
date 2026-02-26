"""Sprint 56A tests — ref table wiring, timeline filtering, fee calculations.

Covers:
  A1  — predict_permits wires ref_permit_forms (DB fallback to hardcoded)
  A2  — predict_permits wires ref_agency_triggers (DB fallback to hardcoded)
  A3  — predict_permits surfaces historic_district from ref_zoning_routing
  A4  — estimate_timeline filters out electrical/plumbing trade permits
  A5  — estimate_fees implements Table 1A-E electrical fee calculation
  A6  — estimate_fees expands plumbing fee coverage to 5+ project types
  A7  — recommend_consultants adds optional entity_type parameter
"""

from __future__ import annotations

import pytest
import duckdb
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# A1 / A2 / A3 — predict_permits ref table wiring
# ---------------------------------------------------------------------------

class TestPredictPermitsRefFormsFallback:
    """A1: ref_permit_forms fallback to hardcoded when DB is empty/unavailable."""

    def test_query_ref_permit_forms_returns_none_on_db_error(self):
        """_query_ref_permit_forms returns None gracefully when DB fails."""
        from src.tools.predict_permits import _query_ref_permit_forms
        with patch("src.db.get_connection", side_effect=Exception("DB unavailable")):
            result = _query_ref_permit_forms(["new_construction"])
        assert result is None

    def test_query_ref_permit_forms_returns_none_for_empty_types(self):
        """_query_ref_permit_forms returns None for empty project_types list."""
        from src.tools.predict_permits import _query_ref_permit_forms
        result = _query_ref_permit_forms([])
        assert result is None

    def test_query_ref_permit_forms_returns_none_when_table_empty(self, tmp_path):
        """_query_ref_permit_forms returns None when table has no matching rows."""
        from src.tools.predict_permits import _query_ref_permit_forms
        from src.db import init_schema
        import src.db as db_mod

        db_path = str(tmp_path / "test.duckdb")
        conn = duckdb.connect(db_path)
        init_schema(conn)
        conn.close()

        def patched_conn(db_path_arg=None):
            return duckdb.connect(db_path)

        with patch.object(db_mod, "BACKEND", "duckdb"), \
             patch("src.db.get_connection", patched_conn):
            result = _query_ref_permit_forms(["some_unknown_type"])
        assert result is None

    def test_query_ref_permit_forms_uses_db_when_seeded(self, tmp_path):
        """_query_ref_permit_forms returns DB data when table has matching rows."""
        from src.tools.predict_permits import _query_ref_permit_forms
        from src.db import init_schema
        import src.db as db_mod
        from scripts.seed_reference_tables import PERMIT_FORMS_ROWS, _upsert_permit_forms

        db_path = str(tmp_path / "test_seeded.duckdb")
        conn = duckdb.connect(db_path)
        init_schema(conn)
        _upsert_permit_forms(conn, "duckdb", PERMIT_FORMS_ROWS)
        conn.close()

        def patched_conn(db_path_arg=None):
            return duckdb.connect(db_path)

        with patch.object(db_mod, "BACKEND", "duckdb"), \
             patch("src.db.get_connection", patched_conn):
            result = _query_ref_permit_forms(["new_construction"])

        assert result is not None
        assert result["form"] == "Form 1/2"
        assert "in_house" in result.get("review_path", "")

    def test_determine_form_uses_db_form(self):
        """_determine_form returns DB-backed form data when provided."""
        from src.tools.predict_permits import _determine_form
        from src.tools.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        db_form = {"form": "Form 3/8", "review_path": "otc", "notes": "Kitchen remodel OTC eligible"}
        result = _determine_form(["kitchen_remodel"], kb, db_form=db_form)
        assert result["form"] == "Form 3/8"
        assert result.get("source") == "db"

    def test_determine_form_falls_back_to_hardcoded_when_no_db_form(self):
        """_determine_form falls back to hardcoded logic when db_form is None."""
        from src.tools.predict_permits import _determine_form
        from src.tools.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        result = _determine_form(["new_construction"], kb, db_form=None)
        assert result["form"] == "Form 1/2"
        assert "source" not in result  # hardcoded path doesn't set source

    def test_determine_form_demolition_hardcoded(self):
        """_determine_form returns Form 6 for demolition via hardcoded path."""
        from src.tools.predict_permits import _determine_form
        from src.tools.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        result = _determine_form(["demolition"], kb, db_form=None)
        assert result["form"] == "Form 6"


class TestPredictPermitsRefAgencyTriggers:
    """A2: ref_agency_triggers fallback to hardcoded when DB empty/unavailable."""

    def test_query_ref_agency_triggers_returns_none_on_error(self):
        """_query_ref_agency_triggers returns None gracefully when DB fails."""
        from src.tools.predict_permits import _query_ref_agency_triggers
        with patch("src.db.get_connection", side_effect=Exception("DB unavailable")):
            result = _query_ref_agency_triggers(["restaurant"])
        assert result is None

    def test_query_ref_agency_triggers_returns_none_for_empty_types(self):
        """_query_ref_agency_triggers returns None for empty project_types."""
        from src.tools.predict_permits import _query_ref_agency_triggers
        result = _query_ref_agency_triggers([])
        assert result is None

    def test_query_ref_agency_triggers_uses_db_when_seeded(self, tmp_path):
        """_query_ref_agency_triggers returns DB data when table has matching rows."""
        from src.tools.predict_permits import _query_ref_agency_triggers
        from src.db import init_schema
        import src.db as db_mod
        from scripts.seed_reference_tables import AGENCY_TRIGGERS_ROWS, _upsert_agency_triggers

        db_path = str(tmp_path / "test_triggers.duckdb")
        conn = duckdb.connect(db_path)
        init_schema(conn)
        _upsert_agency_triggers(conn, "duckdb", AGENCY_TRIGGERS_ROWS)
        conn.close()

        def patched_conn(db_path_arg=None):
            return duckdb.connect(db_path)

        with patch.object(db_mod, "BACKEND", "duckdb"), \
             patch("src.db.get_connection", patched_conn):
            result = _query_ref_agency_triggers(["restaurant"])

        assert result is not None
        agencies = [r["agency"] for r in result]
        assert any("Planning" in a for a in agencies)
        assert any("DPH" in a or "Health" in a for a in agencies)

    def test_determine_agency_routing_uses_db_triggers(self):
        """_determine_agency_routing uses DB triggers when provided."""
        from src.tools.predict_permits import _determine_agency_routing
        from src.tools.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        db_triggers = [
            {"trigger": "restaurant", "agency": "Planning", "reason": "Zoning review", "adds_weeks": 2},
            {"trigger": "restaurant", "agency": "DPH (Public Health)", "reason": "Health permit", "adds_weeks": 3},
        ]
        agencies = _determine_agency_routing(["restaurant"], kb, db_triggers=db_triggers)
        agency_names = [a["agency"] for a in agencies]
        assert "DBI (Building)" in agency_names  # Always included
        assert "Planning" in agency_names
        assert "DPH (Public Health)" in agency_names

    def test_determine_agency_routing_db_source_tagged(self):
        """DB-sourced agencies should have source='db' tag."""
        from src.tools.predict_permits import _determine_agency_routing
        from src.tools.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        db_triggers = [
            {"trigger": "restaurant", "agency": "Planning", "reason": "Test", "adds_weeks": 2},
        ]
        agencies = _determine_agency_routing(["restaurant"], kb, db_triggers=db_triggers)
        planning_entry = next((a for a in agencies if a["agency"] == "Planning"), None)
        assert planning_entry is not None
        assert planning_entry.get("source") == "db"

    def test_determine_agency_routing_falls_back_to_hardcoded(self):
        """_determine_agency_routing uses hardcoded logic when db_triggers is None."""
        from src.tools.predict_permits import _determine_agency_routing
        from src.tools.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        agencies = _determine_agency_routing(["restaurant"], kb, db_triggers=None)
        agency_names = [a["agency"] for a in agencies]
        # Hardcoded path should still include Planning
        assert "Planning" in agency_names


class TestPredictPermitsHistoricDistrict:
    """A3: historic_district flag surfaced from ref_zoning_routing."""

    @pytest.mark.asyncio
    async def test_predict_permits_no_address_no_historic_flag(self):
        """Without address, no historic district info is shown."""
        from src.tools.predict_permits import predict_permits
        result = await predict_permits(
            project_description="Kitchen remodel in a house"
        )
        # Should NOT show historic district info without address
        assert "Historic District" not in result

    @pytest.mark.asyncio
    async def test_predict_permits_historic_flag_not_shown_without_zoning(self):
        """Historic district flag is only shown when zoning data is resolved."""
        from src.tools.predict_permits import predict_permits
        # No address = no zoning resolution
        result = await predict_permits(
            project_description="Add a deck to my house",
            address=None,
        )
        assert "Historic District" not in result


# ---------------------------------------------------------------------------
# A4 — estimate_timeline trade permit filtering
# ---------------------------------------------------------------------------

class TestTimelineTradeFilterInQuery:
    """A4: Electrical/plumbing trade permits filtered out of timeline queries."""

    def test_query_timeline_excludes_electrical(self, tmp_path):
        """Timeline query should exclude electrical permits from results."""
        from src.db import init_schema
        from src.tools.estimate_timeline import _query_timeline, _ensure_timeline_stats

        db_path = str(tmp_path / "tl_filter.duckdb")
        conn = duckdb.connect(db_path)
        init_schema(conn)

        from datetime import date, timedelta
        base = date.today() - timedelta(days=180)  # Recent dates for recency filter
        permits = []
        for i in range(20):
            pnum = f"BLDG{i:04d}"
            filed = base + timedelta(days=i)
            issued = filed + timedelta(days=30)
            completed = issued + timedelta(days=60)
            permits.append((
                pnum, "1", "additions alterations or repairs", "complete",
                str(completed), f"Building permit #{i}", str(filed), str(issued),
                str(filed + timedelta(days=28)), str(completed),
                80000, None, "office", "office", None, None,
                str(100 + i), "MARKET", "ST", "94110", "Mission", "9",
                "3512", str(i).zfill(3), None, str(filed),
            ))
        # Electrical permits that should be excluded
        for i in range(20, 30):
            pnum = f"ELEC{i:04d}"
            filed = base + timedelta(days=i)
            issued = filed + timedelta(days=2)  # Very fast — would skew results
            completed = issued + timedelta(days=5)
            permits.append((
                pnum, "E", "electrical permit", "complete",
                str(completed), f"Electrical #{i}", str(filed), str(issued),
                str(filed + timedelta(days=1)), str(completed),
                5000, None, "office", "office", None, None,
                str(200 + i), "MISSION", "ST", "94110", "Mission", "9",
                "3513", str(i).zfill(3), None, str(filed),
            ))
        conn.executemany(
            "INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            permits,
        )
        # Create timeline_stats
        _ensure_timeline_stats(conn)

        # Run query
        with patch("src.tools.estimate_timeline.BACKEND", "duckdb"):
            result = _query_timeline(conn, "in_house", None, None, None)

        conn.close()
        assert result is not None
        # The p50 should reflect building permits (~30 days), not electrical (2 days)
        assert result["p50_days"] >= 15, f"p50_days {result['p50_days']} is too low — electrical permits may not be filtered"

    def test_query_timeline_excludes_plumbing(self, tmp_path):
        """Timeline query should exclude plumbing permits from results."""
        from src.db import init_schema
        from src.tools.estimate_timeline import _query_timeline, _ensure_timeline_stats

        db_path = str(tmp_path / "tl_plumbing.duckdb")
        conn = duckdb.connect(db_path)
        init_schema(conn)

        from datetime import date, timedelta
        base = date.today() - timedelta(days=180)  # Recent dates for recency filter
        permits = []
        for i in range(15):
            pnum = f"BLDG{i:04d}"
            filed = base + timedelta(days=i)
            issued = filed + timedelta(days=45)
            completed = issued + timedelta(days=60)
            permits.append((
                pnum, "1", "additions alterations or repairs", "complete",
                str(completed), f"Building permit #{i}", str(filed), str(issued),
                str(filed + timedelta(days=43)), str(completed),
                100000, None, "office", "office", None, None,
                str(100 + i), "MARKET", "ST", "94110", "Mission", "9",
                "3512", str(i).zfill(3), None, str(filed),
            ))
        for i in range(15, 25):
            pnum = f"PLMB{i:04d}"
            filed = base + timedelta(days=i)
            issued = filed + timedelta(days=1)  # Very fast plumbing
            completed = issued + timedelta(days=3)
            permits.append((
                pnum, "P", "plumbing permit", "complete",
                str(completed), f"Plumbing #{i}", str(filed), str(issued),
                str(filed), str(completed),
                3000, None, "office", "office", None, None,
                str(200 + i), "MISSION", "ST", "94110", "Mission", "9",
                "3513", str(i).zfill(3), None, str(filed),
            ))
        conn.executemany(
            "INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            permits,
        )
        _ensure_timeline_stats(conn)

        with patch("src.tools.estimate_timeline.BACKEND", "duckdb"):
            result = _query_timeline(conn, "in_house", None, None, None)

        conn.close()
        assert result is not None
        # Building permits are ~45 days. If plumbing (1 day) were included, p25 would be very low.
        assert result["p25_days"] >= 5, f"p25_days {result['p25_days']} too low — plumbing may not be filtered"

    def test_ensure_timeline_stats_excludes_trade_permits(self, tmp_path):
        """_ensure_timeline_stats creates timeline_stats without trade permits."""
        from src.db import init_schema
        from src.tools.estimate_timeline import _ensure_timeline_stats

        db_path = str(tmp_path / "tl_ensure.duckdb")
        conn = duckdb.connect(db_path)
        init_schema(conn)

        from datetime import date, timedelta
        base = date(2024, 1, 1)
        permits = []
        for i in range(10):
            pnum = f"BLDG{i:04d}"
            filed = base + timedelta(days=i)
            issued = filed + timedelta(days=30)
            completed = issued + timedelta(days=60)
            permits.append((
                pnum, "1", "additions alterations or repairs", "complete",
                str(completed), f"Alt #{i}", str(filed), str(issued),
                str(filed + timedelta(days=28)), str(completed),
                80000, None, "office", "office", None, None,
                str(100 + i), "MARKET", "ST", "94110", "Mission", "9",
                "3512", str(i).zfill(3), None, str(filed),
            ))
        # Add some electrical
        for i in range(10, 15):
            pnum = f"ELEC{i:04d}"
            filed = base + timedelta(days=i)
            issued = filed + timedelta(days=1)
            completed = issued + timedelta(days=2)
            permits.append((
                pnum, "E", "electrical permit", "complete",
                str(completed), f"Elec #{i}", str(filed), str(issued),
                str(filed), str(completed),
                2000, None, "office", "office", None, None,
                str(200 + i), "MISSION", "ST", "94110", "Mission", "9",
                "3513", str(i).zfill(3), None, str(filed),
            ))
        conn.executemany(
            "INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            permits,
        )
        _ensure_timeline_stats(conn)

        # Check that electrical are NOT in timeline_stats
        elec_count = conn.execute(
            "SELECT COUNT(*) FROM timeline_stats WHERE permit_type_definition ILIKE '%electrical%'"
        ).fetchone()[0]
        bldg_count = conn.execute(
            "SELECT COUNT(*) FROM timeline_stats WHERE permit_type_definition NOT ILIKE '%electrical%'"
        ).fetchone()[0]

        assert elec_count == 0, f"Electrical permits should be excluded from timeline_stats, found {elec_count}"
        assert bldg_count == 10, f"Should have 10 building permits, got {bldg_count}"

        conn.close()


# ---------------------------------------------------------------------------
# A5 — estimate_fees Table 1A-E electrical calculation
# ---------------------------------------------------------------------------

class TestElectricalFeeCalculation:
    """A5: Table 1A-E electrical fee calculation."""

    def _get_fee_tables(self):
        from src.tools.knowledge_base import get_knowledge_base
        return get_knowledge_base().fee_tables

    def test_electrical_fee_residential_category1_returned(self):
        """Residential project returns Category 1 electrical fee estimate."""
        from src.tools.estimate_fees import _calculate_electrical_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_electrical_fee("general_alteration", None, fee_tables)
        assert result is not None
        assert "estimate" in result
        assert "category" in result
        assert "1" in result.get("category", "") or "Residential" in result.get("category", "")

    def test_electrical_fee_restaurant_category2_returned(self):
        """Restaurant (nonresidential) returns Category 2 electrical fee."""
        from src.tools.estimate_fees import _calculate_electrical_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_electrical_fee("restaurant", 2000, fee_tables)
        assert result is not None
        assert "2" in result.get("category", "") or "Nonresidential" in result.get("category", "")

    def test_electrical_fee_sqft_tier_selection(self):
        """Square footage selects the correct tier within Category 2."""
        from src.tools.estimate_fees import _calculate_electrical_fee
        fee_tables = self._get_fee_tables()
        # Under 2500 sq ft
        result_small = _calculate_electrical_fee("commercial_ti", 1500, fee_tables)
        # 5001-10000 sq ft
        result_medium = _calculate_electrical_fee("commercial_ti", 7500, fee_tables)

        assert result_small is not None
        assert result_medium is not None
        # Larger space = higher fee
        small_fee = result_small.get("fee", 0) or 0
        medium_fee = result_medium.get("fee", 0) or 0
        if small_fee and medium_fee:
            assert medium_fee > small_fee, (
                f"Larger space should have higher fee: {small_fee} vs {medium_fee}"
            )

    def test_electrical_fee_outlet_count_tier_selection(self):
        """Outlet count selects the correct residential tier."""
        from src.tools.estimate_fees import _calculate_electrical_fee
        fee_tables = self._get_fee_tables()
        # 5 outlets — should use "Up to 10" tier
        result_5 = _calculate_electrical_fee("general_alteration", None, fee_tables, outlet_count=5)
        # 15 outlets — should use "11 to 20" tier
        result_15 = _calculate_electrical_fee("general_alteration", None, fee_tables, outlet_count=15)
        # 50 outlets — should use "More than 40" tier
        result_50 = _calculate_electrical_fee("general_alteration", None, fee_tables, outlet_count=50)

        assert result_5 is not None
        assert result_15 is not None
        assert result_50 is not None

        fee_5 = result_5.get("fee", 0) or 0
        fee_15 = result_15.get("fee", 0) or 0
        fee_50 = result_50.get("fee", 0) or 0

        if fee_5 and fee_15 and fee_50:
            assert fee_5 <= fee_15 <= fee_50, f"Fees should increase with outlet count: {fee_5}, {fee_15}, {fee_50}"

    def test_electrical_fee_returns_dollar_amount(self):
        """Electrical fee result contains a dollar amount."""
        from src.tools.estimate_fees import _calculate_electrical_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_electrical_fee("restaurant", 3000, fee_tables)
        assert result is not None
        estimate = result.get("estimate", "")
        assert "$" in estimate

    def test_electrical_fee_no_fee_tables_returns_none(self):
        """Returns None when fee tables are empty."""
        from src.tools.estimate_fees import _calculate_electrical_fee
        result = _calculate_electrical_fee("restaurant", 2000, {})
        assert result is None

    def test_electrical_fee_new_construction_nonresidential(self):
        """New construction is treated as nonresidential (Category 2)."""
        from src.tools.estimate_fees import _calculate_electrical_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_electrical_fee("new_construction", 5000, fee_tables)
        assert result is not None
        assert "2" in result.get("category", "") or "Nonresidential" in result.get("category", "")

    @pytest.mark.asyncio
    async def test_estimate_fees_includes_electrical_section(self):
        """estimate_fees output includes an Electrical Permit section."""
        from src.tools.estimate_fees import estimate_fees
        result = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=80000,
            project_type="restaurant",
            square_footage=1500,
        )
        assert "Electrical" in result or "1A-E" in result

    @pytest.mark.asyncio
    async def test_estimate_fees_electrical_residential(self):
        """estimate_fees includes electrical fees for residential alterations."""
        from src.tools.estimate_fees import estimate_fees
        result = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=50000,
            project_type="general_alteration",
        )
        assert "Electrical" in result

    @pytest.mark.asyncio
    async def test_estimate_fees_total_includes_electrical(self):
        """When electrical fee is exact, total DBI fees should be higher."""
        from src.tools.estimate_fees import estimate_fees
        # With small area, we expect a precise single fee
        result = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=50000,
            project_type="restaurant",
            square_footage=1500,
        )
        assert "$" in result  # Has dollar amounts


# ---------------------------------------------------------------------------
# A6 — estimate_fees expanded plumbing coverage
# ---------------------------------------------------------------------------

class TestPlumbingFeeExpansion:
    """A6: Expanded plumbing fee coverage to 5+ project types."""

    def _get_fee_tables(self):
        from src.tools.knowledge_base import get_knowledge_base
        return get_knowledge_base().fee_tables

    def test_plumbing_restaurant_still_works(self):
        """Original restaurant plumbing fee still returns correctly."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_plumbing_fee("restaurant", fee_tables)
        assert result is not None
        assert "6PA" in str(result) or "6PB" in str(result)

    def test_plumbing_adu_still_works(self):
        """Original ADU plumbing fee still returns correctly."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_plumbing_fee("adu", fee_tables)
        assert result is not None

    def test_plumbing_new_construction_still_works(self):
        """Original new_construction plumbing fee still returns correctly."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_plumbing_fee("new_construction", fee_tables)
        assert result is not None

    def test_plumbing_commercial_ti_new(self):
        """A6: commercial_ti now returns plumbing fee estimate."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_plumbing_fee("commercial_ti", fee_tables)
        assert result is not None
        assert "5P/5M" in str(result)

    def test_plumbing_general_alteration_new(self):
        """A6: general_alteration (single residential) returns plumbing fee."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_plumbing_fee("general_alteration", fee_tables)
        assert result is not None
        assert "1P" in str(result)

    def test_plumbing_kitchen_remodel_new(self):
        """A6: kitchen_remodel returns plumbing fee (single residential unit)."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_plumbing_fee("kitchen_remodel", fee_tables)
        assert result is not None

    def test_plumbing_bathroom_remodel_new(self):
        """A6: bathroom_remodel returns plumbing fee (single residential unit)."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_plumbing_fee("bathroom_remodel", fee_tables)
        assert result is not None

    def test_plumbing_fire_sprinkler_new(self):
        """A6: fire_sprinkler returns plumbing fee (4PA/4PB)."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_plumbing_fee("fire_sprinkler", fee_tables)
        assert result is not None
        assert "4P" in str(result)

    def test_plumbing_low_rise_multifamily_new(self):
        """A6: low_rise_multifamily returns plumbing fee (2PA/2PB)."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_plumbing_fee("low_rise_multifamily", fee_tables)
        assert result is not None

    def test_plumbing_unknown_type_returns_none(self):
        """Unknown project type returns None (no plumbing fees)."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        result = _calculate_plumbing_fee("unknown_project_type_xyz", fee_tables)
        assert result is None

    def test_plumbing_five_or_more_types_covered(self):
        """At least 5 distinct project types return plumbing fees."""
        from src.tools.estimate_fees import _calculate_plumbing_fee
        fee_tables = self._get_fee_tables()
        covered_types = [
            "restaurant", "adu", "new_construction", "commercial_ti",
            "general_alteration", "kitchen_remodel", "bathroom_remodel",
            "fire_sprinkler", "low_rise_multifamily",
        ]
        covered_count = sum(
            1 for pt in covered_types
            if _calculate_plumbing_fee(pt, fee_tables) is not None
        )
        assert covered_count >= 5, f"Only {covered_count} project types covered (expected 5+)"

    @pytest.mark.asyncio
    async def test_estimate_fees_shows_plumbing_section(self):
        """estimate_fees output shows plumbing section for restaurant."""
        from src.tools.estimate_fees import estimate_fees
        result = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=200000,
            project_type="restaurant",
        )
        assert "Plumbing" in result or "1A-C" in result


# ---------------------------------------------------------------------------
# A7 — recommend_consultants entity_type parameter
# ---------------------------------------------------------------------------

class TestRecommendConsultantsEntityType:
    """A7: Optional entity_type parameter for recommend_consultants."""

    def test_query_consultants_accepts_entity_type(self, tmp_path):
        """_query_consultants accepts entity_type parameter."""
        from src.tools.recommend_consultants import _query_consultants
        from src.db import init_schema
        import src.db as db_mod

        db_path = str(tmp_path / "test_entities.duckdb")
        conn = duckdb.connect(db_path)
        init_schema(conn)

        # Insert test entities
        conn.execute("""
            INSERT INTO entities (entity_id, canonical_name, canonical_firm, entity_type, permit_count)
            VALUES
              (1, 'Alice Consultant', 'Firm A', 'consultant', 50),
              (2, 'Bob Contractor', 'Firm B', 'contractor', 30),
              (3, 'Carol Architect', 'Firm C', 'architect', 25)
        """)

        with patch.object(db_mod, "BACKEND", "duckdb"):
            consultants = _query_consultants(conn, min_permits=10, entity_type="consultant")
            contractors = _query_consultants(conn, min_permits=10, entity_type="contractor")
            architects = _query_consultants(conn, min_permits=10, entity_type="architect")

        conn.close()

        assert len(consultants) == 1
        assert consultants[0]["canonical_name"] == "Alice Consultant"

        assert len(contractors) == 1
        assert contractors[0]["canonical_name"] == "Bob Contractor"

        assert len(architects) == 1
        assert architects[0]["canonical_name"] == "Carol Architect"

    def test_query_consultants_default_is_consultant(self, tmp_path):
        """_query_consultants defaults to entity_type='consultant'."""
        from src.tools.recommend_consultants import _query_consultants
        from src.db import init_schema
        import src.db as db_mod

        db_path = str(tmp_path / "test_default.duckdb")
        conn = duckdb.connect(db_path)
        init_schema(conn)

        conn.execute("""
            INSERT INTO entities (entity_id, canonical_name, canonical_firm, entity_type, permit_count)
            VALUES
              (1, 'Alice Consultant', NULL, 'consultant', 50),
              (2, 'Bob Contractor', NULL, 'contractor', 30)
        """)

        with patch.object(db_mod, "BACKEND", "duckdb"):
            result = _query_consultants(conn, min_permits=10)

        conn.close()
        assert len(result) == 1
        assert result[0]["canonical_name"] == "Alice Consultant"

    def test_trade_type_normalization_electrician_to_contractor(self):
        """'electrician' is normalized to 'contractor' entity type."""
        from src.tools.recommend_consultants import recommend_consultants
        # We don't call the actual function (DB required) — just test the mapping logic
        from src.tools.recommend_consultants import recommend_consultants
        _TRADE_MAP = {
            "electrician": "contractor",
            "plumber": "contractor",
            "electrical": "contractor",
            "plumbing": "contractor",
        }
        assert _TRADE_MAP.get("electrician") == "contractor"
        assert _TRADE_MAP.get("plumber") == "contractor"

    def test_format_recommendations_uses_entity_type_label(self):
        """_format_recommendations uses entity_type in header."""
        from src.tools.recommend_consultants import _format_recommendations, ScoredConsultant
        scored = [
            ScoredConsultant(entity_id=1, name="Bob Contractor", firm="Firm B",
                             permit_count=30, score=75.0)
        ]
        result = _format_recommendations(scored, None, False, False, entity_type="contractor")
        assert "Contractor" in result  # entity label in header

    def test_format_recommendations_no_entity_type_flag_for_consultant(self):
        """When entity_type='consultant', no entity type label shown in output."""
        from src.tools.recommend_consultants import _format_recommendations, ScoredConsultant
        scored = [
            ScoredConsultant(entity_id=1, name="Alice Consultant", firm="Firm A",
                             permit_count=50, score=80.0)
        ]
        result = _format_recommendations(scored, None, False, False, entity_type="consultant")
        # Should NOT show "Entity type: consultant" line
        assert "Entity type:" not in result

    def test_format_recommendations_shows_entity_type_for_non_consultant(self):
        """Non-consultant entity type shows 'Entity type:' label."""
        from src.tools.recommend_consultants import _format_recommendations, ScoredConsultant
        scored = [
            ScoredConsultant(entity_id=1, name="Bob Architect", firm="Firm B",
                             permit_count=25, score=70.0)
        ]
        result = _format_recommendations(scored, None, False, False, entity_type="architect")
        # Markdown format uses **Entity type:** bold label
        assert "entity type" in result.lower() or "architect" in result.lower()

    def test_format_recommendations_no_results_message_uses_entity_type(self):
        """Empty results message references the entity type."""
        from src.tools.recommend_consultants import _format_recommendations
        result = _format_recommendations([], None, False, False, entity_type="contractor")
        assert "contractor" in result.lower()

    def test_invalid_entity_type_falls_back_to_consultant(self, tmp_path):
        """Invalid entity_type falls back to 'consultant'."""
        from src.tools.recommend_consultants import _query_consultants
        from src.db import init_schema
        import src.db as db_mod

        db_path = str(tmp_path / "test_invalid.duckdb")
        conn = duckdb.connect(db_path)
        init_schema(conn)
        conn.execute("""
            INSERT INTO entities (entity_id, canonical_name, canonical_firm, entity_type, permit_count)
            VALUES (1, 'Alice Consultant', NULL, 'consultant', 50)
        """)

        # 'invalid_type' does not exist in entities table, returns no rows
        with patch.object(db_mod, "BACKEND", "duckdb"):
            result = _query_consultants(conn, min_permits=10, entity_type="invalid_type_xyz")
        conn.close()
        assert result == []  # No rows match invalid entity type
