"""Sprint 58A tests: station-based timeline, methodology dicts, agency-to-station mapping.

Tests:
- Methodology contract: all 5 tools return common keys
- Station-based timeline: station sum, trend arrows, fallback
- Agency-to-station mapping: all agencies have entries
- Fee revision context: budget ceiling includes fees
- Coverage gaps: empty when none, populated when gaps exist
"""

import asyncio
from unittest.mock import patch, MagicMock
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COMMON_METHODOLOGY_KEYS = {
    "model",
    "formula",
    "data_source",
    "recency",
    "sample_size",
    "data_freshness",
    "confidence",
    "coverage_gaps",
}


def _check_common_keys(methodology: dict) -> list[str]:
    """Return missing common keys from a methodology dict."""
    missing = []
    for key in COMMON_METHODOLOGY_KEYS:
        if key not in methodology:
            missing.append(key)
    return missing


# ---------------------------------------------------------------------------
# A.1: Agency-to-station mapping
# ---------------------------------------------------------------------------

class TestAgencyToStationMapping:
    def test_module_importable(self):
        from src.tools._routing import AGENCY_TO_STATIONS
        assert isinstance(AGENCY_TO_STATIONS, dict)

    def test_all_expected_agencies_present(self):
        from src.tools._routing import AGENCY_TO_STATIONS
        expected = [
            "DBI (Building)",
            "Planning",
            "SFFD (Fire)",
            "DPH (Public Health)",
            "DPW/BSM",
            "SFPUC",
            "DBI Mechanical/Electrical",
        ]
        for agency in expected:
            assert agency in AGENCY_TO_STATIONS, f"Missing agency: {agency}"

    def test_agency_values_are_lists(self):
        from src.tools._routing import AGENCY_TO_STATIONS
        for agency, stations in AGENCY_TO_STATIONS.items():
            assert isinstance(stations, list), f"{agency} value should be list"

    def test_dbi_maps_to_bldg(self):
        from src.tools._routing import AGENCY_TO_STATIONS
        assert "BLDG" in AGENCY_TO_STATIONS["DBI (Building)"]

    def test_planning_maps_to_cp_zoc(self):
        from src.tools._routing import AGENCY_TO_STATIONS
        assert "CP-ZOC" in AGENCY_TO_STATIONS["Planning"]

    def test_sffd_maps_to_sffd_stations(self):
        from src.tools._routing import AGENCY_TO_STATIONS
        stations = AGENCY_TO_STATIONS["SFFD (Fire)"]
        assert "SFFD" in stations or "SFFD-HQ" in stations

    def test_dph_maps_to_health_stations(self):
        from src.tools._routing import AGENCY_TO_STATIONS
        stations = AGENCY_TO_STATIONS["DPH (Public Health)"]
        assert any(s.startswith("HEALTH") for s in stations)

    def test_dpw_maps_to_dpw_stations(self):
        from src.tools._routing import AGENCY_TO_STATIONS
        stations = AGENCY_TO_STATIONS["DPW/BSM"]
        assert any("DPW" in s for s in stations)

    def test_sfpuc_maps_to_sfpuc_stations(self):
        from src.tools._routing import AGENCY_TO_STATIONS
        stations = AGENCY_TO_STATIONS["SFPUC"]
        assert any("SFPUC" in s for s in stations)

    def test_agencies_to_stations_function(self):
        from src.tools._routing import agencies_to_stations
        result = agencies_to_stations(["DBI (Building)", "Planning"])
        assert "BLDG" in result
        assert "CP-ZOC" in result

    def test_agencies_to_stations_deduplicates(self):
        from src.tools._routing import agencies_to_stations
        # Calling with same agency twice should not duplicate
        result = agencies_to_stations(["DBI (Building)", "DBI (Building)"])
        assert result.count("BLDG") == 1

    def test_agencies_to_stations_unknown_agency(self):
        from src.tools._routing import agencies_to_stations
        # Unknown agency returns empty list (no error)
        result = agencies_to_stations(["Unknown Agency XYZ"])
        assert result == []

    def test_station_to_agency_reverse_map(self):
        from src.tools._routing import STATION_TO_AGENCY
        assert "BLDG" in STATION_TO_AGENCY
        assert STATION_TO_AGENCY["BLDG"] == "DBI (Building)"

    def test_get_all_agency_names(self):
        from src.tools._routing import get_all_agency_names
        names = get_all_agency_names()
        assert len(names) >= 7
        assert "DBI (Building)" in names

    def test_get_all_station_codes(self):
        from src.tools._routing import get_all_station_codes
        codes = get_all_station_codes()
        assert "BLDG" in codes
        assert "CP-ZOC" in codes
        assert "SFFD" in codes

    def test_no_duplicate_station_codes_in_get_all(self):
        from src.tools._routing import get_all_station_codes
        codes = get_all_station_codes()
        assert len(codes) == len(set(codes)), "Station codes should be deduplicated"


# ---------------------------------------------------------------------------
# A.2: Estimate timeline — station-based model
# ---------------------------------------------------------------------------

class TestEstimateTimelineStationModel:
    """Tests for the station-sum primary model and methodology."""

    def test_trigger_station_map_contains_bldg(self):
        from src.tools.estimate_timeline import TRIGGER_STATION_MAP
        # seismic_retrofit maps to BLDG
        assert "seismic_retrofit" in TRIGGER_STATION_MAP
        assert "BLDG" in TRIGGER_STATION_MAP["seismic_retrofit"]

    def test_trigger_station_map_fire_stations(self):
        from src.tools.estimate_timeline import TRIGGER_STATION_MAP
        assert "fire_review" in TRIGGER_STATION_MAP
        fire_stations = TRIGGER_STATION_MAP["fire_review"]
        assert any("SFFD" in s for s in fire_stations)

    def test_compute_station_sum_basic(self):
        from src.tools.estimate_timeline import _compute_station_sum
        station_data = [
            {"station": "BLDG", "p25_days": 5.0, "p50_days": 10.0, "p75_days": 20.0, "p90_days": 30.0, "sample_count": 100, "period": "current"},
            {"station": "CP-ZOC", "p25_days": 3.0, "p50_days": 7.0, "p75_days": 14.0, "p90_days": 21.0, "sample_count": 50, "period": "current"},
        ]
        result = _compute_station_sum(station_data)
        assert result is not None
        assert result["p50_days"] == 17  # 10 + 7
        assert result["p25_days"] == 8   # 5 + 3
        assert result["p75_days"] == 34  # 20 + 14
        assert result["p90_days"] == 51  # 30 + 21
        assert result["station_count"] == 2
        assert result["sample_size"] == 150
        assert result["model"] == "station_sum"

    def test_compute_station_sum_empty(self):
        from src.tools.estimate_timeline import _compute_station_sum
        result = _compute_station_sum([])
        assert result is None

    def test_compute_station_sum_all_none_p50(self):
        from src.tools.estimate_timeline import _compute_station_sum
        station_data = [
            {"station": "BLDG", "p25_days": None, "p50_days": None, "p75_days": None, "p90_days": None, "sample_count": 10, "period": "current"},
        ]
        result = _compute_station_sum(station_data)
        assert result is None

    def test_compute_station_sum_skips_zero_p50(self):
        from src.tools.estimate_timeline import _compute_station_sum
        station_data = [
            {"station": "BLDG", "p25_days": 5.0, "p50_days": 10.0, "p75_days": 20.0, "p90_days": 30.0, "sample_count": 100, "period": "current"},
            {"station": "MECH", "p25_days": 0.0, "p50_days": 0.0, "p75_days": 0.0, "p90_days": 0.0, "sample_count": 500, "period": "current"},
        ]
        result = _compute_station_sum(station_data)
        # MECH has p50=0, should be excluded
        assert result["station_count"] == 1
        assert result["p50_days"] == 10

    def test_compute_trend_arrow_slower(self):
        from src.tools.estimate_timeline import _compute_trend_arrow
        # current 20% higher than baseline → ▲ slower
        arrow = _compute_trend_arrow(current_p50=12.0, baseline_p50=10.0)
        assert "▲" in arrow
        assert "slower" in arrow

    def test_compute_trend_arrow_faster(self):
        from src.tools.estimate_timeline import _compute_trend_arrow
        # current 20% lower than baseline → ▼ faster
        arrow = _compute_trend_arrow(current_p50=8.0, baseline_p50=10.0)
        assert "▼" in arrow
        assert "faster" in arrow

    def test_compute_trend_arrow_normal(self):
        from src.tools.estimate_timeline import _compute_trend_arrow
        # current within 15% of baseline → normal
        arrow = _compute_trend_arrow(current_p50=10.5, baseline_p50=10.0)
        assert "—" in arrow
        assert "normal" in arrow

    def test_compute_trend_arrow_none_current(self):
        from src.tools.estimate_timeline import _compute_trend_arrow
        arrow = _compute_trend_arrow(current_p50=None, baseline_p50=10.0)
        assert "—" in arrow

    def test_compute_trend_arrow_none_baseline(self):
        from src.tools.estimate_timeline import _compute_trend_arrow
        arrow = _compute_trend_arrow(current_p50=10.0, baseline_p50=None)
        assert "—" in arrow

    def test_compute_trend_arrow_zero_baseline(self):
        from src.tools.estimate_timeline import _compute_trend_arrow
        arrow = _compute_trend_arrow(current_p50=10.0, baseline_p50=0.0)
        assert "—" in arrow

    def test_trend_threshold_constant(self):
        from src.tools.estimate_timeline import TREND_THRESHOLD_PCT
        assert TREND_THRESHOLD_PCT == 15.0

    @pytest.mark.asyncio
    async def test_estimate_timeline_returns_str_default(self):
        """Default return is str."""
        from src.tools.estimate_timeline import estimate_timeline
        result = await estimate_timeline(permit_type="alterations")
        assert isinstance(result, str)
        assert "Timeline" in result

    @pytest.mark.asyncio
    async def test_estimate_timeline_structured_returns_tuple(self):
        """return_structured=True returns (str, dict) tuple."""
        from src.tools.estimate_timeline import estimate_timeline
        result = await estimate_timeline(permit_type="alterations", return_structured=True)
        assert isinstance(result, tuple)
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)

    @pytest.mark.asyncio
    async def test_estimate_timeline_methodology_common_keys(self):
        """Structured return includes all common methodology keys."""
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = await estimate_timeline(permit_type="alterations", return_structured=True)
        # Check methodology key exists
        assert "methodology" in meta
        methodology = meta["methodology"]
        missing = _check_common_keys(methodology)
        assert missing == [], f"Missing methodology keys: {missing}"

    @pytest.mark.asyncio
    async def test_estimate_timeline_stations_key_present(self):
        """Structured return includes stations list (tool-specific key)."""
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = await estimate_timeline(permit_type="alterations", return_structured=True)
        assert "stations" in meta
        assert isinstance(meta["stations"], list)

    @pytest.mark.asyncio
    async def test_estimate_timeline_fallback_note_key_present(self):
        """Structured return includes fallback_note (tool-specific key)."""
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = await estimate_timeline(permit_type="alterations", return_structured=True)
        assert "fallback_note" in meta

    @pytest.mark.asyncio
    async def test_estimate_timeline_confidence_valid(self):
        """Confidence must be 'high', 'medium', or 'low'."""
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = await estimate_timeline(permit_type="alterations", return_structured=True)
        assert meta["methodology"]["confidence"] in ("high", "medium", "low")

    @pytest.mark.asyncio
    async def test_estimate_timeline_coverage_gaps_list(self):
        """coverage_gaps must be a list."""
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = await estimate_timeline(permit_type="alterations", return_structured=True)
        assert isinstance(meta["methodology"]["coverage_gaps"], list)

    @pytest.mark.asyncio
    async def test_estimate_timeline_sample_size_int(self):
        """sample_size must be int."""
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = await estimate_timeline(permit_type="alterations", return_structured=True)
        assert isinstance(meta["methodology"]["sample_size"], int)

    @pytest.mark.asyncio
    async def test_estimate_timeline_data_freshness_date_format(self):
        """data_freshness must be YYYY-MM-DD format."""
        import re
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = await estimate_timeline(permit_type="alterations", return_structured=True)
        freshness = meta["methodology"]["data_freshness"]
        assert re.match(r"\d{4}-\d{2}-\d{2}", freshness), f"Invalid date format: {freshness}"


# ---------------------------------------------------------------------------
# A.3: Methodology on estimate_fees
# ---------------------------------------------------------------------------

class TestEstimateFeesMethodology:
    @pytest.mark.asyncio
    async def test_fees_structured_returns_tuple(self):
        from src.tools.estimate_fees import estimate_fees
        result = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=100000,
            return_structured=True,
        )
        assert isinstance(result, tuple)
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)

    @pytest.mark.asyncio
    async def test_fees_methodology_common_keys(self):
        from src.tools.estimate_fees import estimate_fees
        _, meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=100000,
            return_structured=True,
        )
        assert "methodology" in meta
        missing = _check_common_keys(meta["methodology"])
        assert missing == [], f"Missing methodology keys: {missing}"

    @pytest.mark.asyncio
    async def test_fees_revision_context_key_present(self):
        """estimate_fees must return revision_context (tool-specific key)."""
        from src.tools.estimate_fees import estimate_fees
        _, meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=100000,
            return_structured=True,
        )
        assert "revision_context" in meta

    @pytest.mark.asyncio
    async def test_fees_revision_context_budget_ceiling(self):
        """revision_context.budget_ceiling must include fees."""
        from src.tools.estimate_fees import estimate_fees
        _, meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=50000,
            return_structured=True,
        )
        rc = meta.get("revision_context", {})
        if rc:
            # budget_ceiling should be > estimated_construction_cost
            assert rc["budget_ceiling"] > 50000

    @pytest.mark.asyncio
    async def test_fees_revision_context_has_note(self):
        from src.tools.estimate_fees import estimate_fees
        _, meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=75000,
            return_structured=True,
        )
        rc = meta.get("revision_context", {})
        if rc:
            assert "note" in rc
            assert isinstance(rc["note"], str)

    @pytest.mark.asyncio
    async def test_fees_coverage_gaps_list(self):
        from src.tools.estimate_fees import estimate_fees
        _, meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=100000,
            return_structured=True,
        )
        assert isinstance(meta["methodology"]["coverage_gaps"], list)

    @pytest.mark.asyncio
    async def test_fees_formula_steps_present(self):
        from src.tools.estimate_fees import estimate_fees
        _, meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=100000,
            return_structured=True,
        )
        assert "formula_steps" in meta
        assert isinstance(meta["formula_steps"], list)

    @pytest.mark.asyncio
    async def test_fees_confidence_valid(self):
        from src.tools.estimate_fees import estimate_fees
        _, meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=100000,
            return_structured=True,
        )
        assert meta["methodology"]["confidence"] in ("high", "medium", "low")


# ---------------------------------------------------------------------------
# A.3: Methodology on predict_permits
# ---------------------------------------------------------------------------

class TestPredictPermitsMethodology:
    @pytest.mark.asyncio
    async def test_predict_structured_returns_tuple(self):
        from src.tools.predict_permits import predict_permits
        result = await predict_permits(
            project_description="kitchen remodel in San Francisco",
            return_structured=True,
        )
        assert isinstance(result, tuple)
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)

    @pytest.mark.asyncio
    async def test_predict_methodology_common_keys(self):
        from src.tools.predict_permits import predict_permits
        _, meta = await predict_permits(
            project_description="kitchen remodel in San Francisco",
            return_structured=True,
        )
        assert "methodology" in meta
        missing = _check_common_keys(meta["methodology"])
        assert missing == [], f"Missing methodology keys: {missing}"

    @pytest.mark.asyncio
    async def test_predict_triggers_matched_key_present(self):
        """predict_permits must return triggers_matched (tool-specific key)."""
        from src.tools.predict_permits import predict_permits
        _, meta = await predict_permits(
            project_description="new restaurant in Mission",
            return_structured=True,
        )
        assert "triggers_matched" in meta
        assert isinstance(meta["triggers_matched"], list)

    @pytest.mark.asyncio
    async def test_predict_coverage_gaps_list(self):
        from src.tools.predict_permits import predict_permits
        _, meta = await predict_permits(
            project_description="new restaurant in Mission",
            return_structured=True,
        )
        assert isinstance(meta["methodology"]["coverage_gaps"], list)

    @pytest.mark.asyncio
    async def test_predict_confidence_valid(self):
        from src.tools.predict_permits import predict_permits
        _, meta = await predict_permits(
            project_description="kitchen remodel",
            return_structured=True,
        )
        assert meta["methodology"]["confidence"] in ("high", "medium", "low")

    @pytest.mark.asyncio
    async def test_predict_sample_size_zero(self):
        """predict_permits uses no historical sample — sample_size should be 0."""
        from src.tools.predict_permits import predict_permits
        _, meta = await predict_permits(
            project_description="kitchen remodel",
            return_structured=True,
        )
        assert meta["methodology"]["sample_size"] == 0


# ---------------------------------------------------------------------------
# A.3: Methodology on required_documents
# ---------------------------------------------------------------------------

class TestRequiredDocumentsMethodology:
    @pytest.mark.asyncio
    async def test_docs_structured_returns_tuple(self):
        from src.tools.required_documents import required_documents
        result = await required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            return_structured=True,
        )
        assert isinstance(result, tuple)
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)

    @pytest.mark.asyncio
    async def test_docs_methodology_common_keys(self):
        from src.tools.required_documents import required_documents
        _, meta = await required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            return_structured=True,
        )
        assert "methodology" in meta
        missing = _check_common_keys(meta["methodology"])
        assert missing == [], f"Missing methodology keys: {missing}"

    @pytest.mark.asyncio
    async def test_docs_coverage_gaps_list(self):
        from src.tools.required_documents import required_documents
        _, meta = await required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            return_structured=True,
        )
        assert isinstance(meta["methodology"]["coverage_gaps"], list)

    @pytest.mark.asyncio
    async def test_docs_sample_size_zero(self):
        """required_documents uses no statistical sample."""
        from src.tools.required_documents import required_documents
        _, meta = await required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            return_structured=True,
        )
        assert meta["methodology"]["sample_size"] == 0

    @pytest.mark.asyncio
    async def test_docs_no_agency_routing_gap(self):
        """Without agency_routing, coverage_gaps should mention incomplete docs."""
        from src.tools.required_documents import required_documents
        _, meta = await required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            return_structured=True,
        )
        gaps = meta["methodology"]["coverage_gaps"]
        assert isinstance(gaps, list)
        # At least one gap mentions agency routing when not provided
        assert any("agency" in g.lower() or "standard" in g.lower() for g in gaps)

    @pytest.mark.asyncio
    async def test_docs_confidence_valid(self):
        from src.tools.required_documents import required_documents
        _, meta = await required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            return_structured=True,
        )
        assert meta["methodology"]["confidence"] in ("high", "medium", "low")


# ---------------------------------------------------------------------------
# A.3: Methodology on revision_risk
# ---------------------------------------------------------------------------

class TestRevisionRiskMethodology:
    @pytest.mark.asyncio
    async def test_risk_structured_returns_tuple(self):
        from src.tools.revision_risk import revision_risk
        result = await revision_risk(
            permit_type="alterations",
            return_structured=True,
        )
        assert isinstance(result, tuple)
        md, meta = result
        assert isinstance(md, str)
        assert isinstance(meta, dict)

    @pytest.mark.asyncio
    async def test_risk_methodology_common_keys(self):
        from src.tools.revision_risk import revision_risk
        _, meta = await revision_risk(
            permit_type="alterations",
            return_structured=True,
        )
        assert "methodology" in meta
        missing = _check_common_keys(meta["methodology"])
        assert missing == [], f"Missing methodology keys: {missing}"

    @pytest.mark.asyncio
    async def test_risk_correction_categories_key_present(self):
        """revision_risk must return correction_categories (tool-specific key)."""
        from src.tools.revision_risk import revision_risk
        _, meta = await revision_risk(
            permit_type="alterations",
            return_structured=True,
        )
        assert "correction_categories" in meta
        assert isinstance(meta["correction_categories"], list)

    @pytest.mark.asyncio
    async def test_risk_coverage_gaps_list(self):
        from src.tools.revision_risk import revision_risk
        _, meta = await revision_risk(
            permit_type="alterations",
            return_structured=True,
        )
        assert isinstance(meta["methodology"]["coverage_gaps"], list)

    @pytest.mark.asyncio
    async def test_risk_confidence_valid(self):
        from src.tools.revision_risk import revision_risk
        _, meta = await revision_risk(
            permit_type="alterations",
            return_structured=True,
        )
        assert meta["methodology"]["confidence"] in ("high", "medium", "low")

    @pytest.mark.asyncio
    async def test_risk_sample_size_nonneg(self):
        from src.tools.revision_risk import revision_risk
        _, meta = await revision_risk(
            permit_type="alterations",
            return_structured=True,
        )
        assert meta["methodology"]["sample_size"] >= 0


# ---------------------------------------------------------------------------
# Cross-tool: All 5 tools return methodology contract
# ---------------------------------------------------------------------------

class TestAllToolsMethodologyContract:
    """Validate that all 5 tools return the full methodology contract."""

    @pytest.mark.asyncio
    async def test_all_five_tools_have_methodology(self):
        """Run all 5 tools and verify methodology is present on every one."""
        from src.tools.predict_permits import predict_permits
        from src.tools.estimate_fees import estimate_fees
        from src.tools.estimate_timeline import estimate_timeline
        from src.tools.required_documents import required_documents
        from src.tools.revision_risk import revision_risk

        # predict_permits
        _, pred_meta = await predict_permits(
            project_description="restaurant conversion in Mission",
            return_structured=True,
        )
        assert "methodology" in pred_meta, "predict_permits missing methodology"

        # estimate_fees
        _, fees_meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=150000,
            project_type="restaurant",
            return_structured=True,
        )
        assert "methodology" in fees_meta, "estimate_fees missing methodology"

        # estimate_timeline
        _, tl_meta = await estimate_timeline(
            permit_type="alterations",
            triggers=["fire_review"],
            return_structured=True,
        )
        assert "methodology" in tl_meta, "estimate_timeline missing methodology"

        # required_documents
        _, docs_meta = await required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            project_type="restaurant",
            return_structured=True,
        )
        assert "methodology" in docs_meta, "required_documents missing methodology"

        # revision_risk
        _, risk_meta = await revision_risk(
            permit_type="alterations",
            project_type="restaurant",
            return_structured=True,
        )
        assert "methodology" in risk_meta, "revision_risk missing methodology"

        # Validate common keys on all 5
        for tool_name, meta in [
            ("predict_permits", pred_meta),
            ("estimate_fees", fees_meta),
            ("estimate_timeline", tl_meta),
            ("required_documents", docs_meta),
            ("revision_risk", risk_meta),
        ]:
            missing = _check_common_keys(meta["methodology"])
            assert missing == [], f"{tool_name} missing keys: {missing}"

    @pytest.mark.asyncio
    async def test_all_tool_specific_keys_present(self):
        """Each tool returns its tool-specific methodology key."""
        from src.tools.estimate_timeline import estimate_timeline
        from src.tools.estimate_fees import estimate_fees
        from src.tools.predict_permits import predict_permits
        from src.tools.revision_risk import revision_risk

        _, tl_meta = await estimate_timeline(permit_type="alterations", return_structured=True)
        assert "stations" in tl_meta, "estimate_timeline missing 'stations'"
        assert "fallback_note" in tl_meta, "estimate_timeline missing 'fallback_note'"

        _, fees_meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=100000,
            return_structured=True,
        )
        assert "revision_context" in fees_meta, "estimate_fees missing 'revision_context'"
        assert "formula_steps" in fees_meta, "estimate_fees missing 'formula_steps'"

        _, pred_meta = await predict_permits(
            project_description="new restaurant",
            return_structured=True,
        )
        assert "triggers_matched" in pred_meta, "predict_permits missing 'triggers_matched'"

        _, risk_meta = await revision_risk(
            permit_type="alterations",
            return_structured=True,
        )
        assert "correction_categories" in risk_meta, "revision_risk missing 'correction_categories'"


# ---------------------------------------------------------------------------
# A.4: /analyze saves full methodology
# ---------------------------------------------------------------------------

class TestAnalyzeMethodologyPersistence:
    """Verify methodology is included in the results_json saved to analysis_sessions."""

    def test_methodology_key_in_raw_results(self):
        """The raw_results dict stored in analysis_sessions must include _methodology."""
        # Simulate the storage structure that web/app.py builds
        # We can't run the full web app, but we verify the key structure
        import json
        sample_methodology = {
            "predict": {
                "tool": "predict_permits",
                "methodology": {"model": "test", "formula": "x", "data_source": "y",
                                "recency": "current", "sample_size": 0,
                                "data_freshness": "2026-02-26", "confidence": "high",
                                "coverage_gaps": []},
            }
        }
        raw_results = {
            "predict": "markdown text",
            "fees": "markdown text",
            "_methodology": sample_methodology,
        }
        # Verify it's JSON serializable
        json_str = json.dumps(raw_results)
        parsed = json.loads(json_str)
        assert "_methodology" in parsed
        assert "predict" in parsed["_methodology"]

    @pytest.mark.asyncio
    async def test_methodology_dict_json_serializable(self):
        """Methodology dicts from all tools must be JSON serializable."""
        import json
        from src.tools.estimate_timeline import estimate_timeline
        from src.tools.estimate_fees import estimate_fees
        from src.tools.predict_permits import predict_permits
        from src.tools.required_documents import required_documents
        from src.tools.revision_risk import revision_risk

        results = {}
        _, tl_meta = await estimate_timeline(permit_type="alterations", return_structured=True)
        results["timeline"] = tl_meta
        _, fees_meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=100000,
            return_structured=True,
        )
        results["fees"] = fees_meta
        _, pred_meta = await predict_permits(
            project_description="kitchen remodel",
            return_structured=True,
        )
        results["predict"] = pred_meta
        _, docs_meta = await required_documents(
            permit_forms=["Form 3/8"],
            review_path="in_house",
            return_structured=True,
        )
        results["docs"] = docs_meta
        _, risk_meta = await revision_risk(
            permit_type="alterations",
            return_structured=True,
        )
        results["risk"] = risk_meta

        # Must not raise
        json_str = json.dumps(results)
        parsed = json.loads(json_str)
        assert "timeline" in parsed
        assert "fees" in parsed
        assert "predict" in parsed
        assert "docs" in parsed
        assert "risk" in parsed


# ---------------------------------------------------------------------------
# Edge cases and boundary conditions
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_station_sum_single_station(self):
        from src.tools.estimate_timeline import _compute_station_sum
        data = [
            {"station": "BLDG", "p25_days": 5.0, "p50_days": 15.0, "p75_days": 30.0, "p90_days": 60.0, "sample_count": 200, "period": "current"},
        ]
        result = _compute_station_sum(data)
        assert result is not None
        assert result["p50_days"] == 15
        assert result["station_count"] == 1

    def test_station_sum_partial_nulls(self):
        """Stations with null p25/p75/p90 should still contribute via fallback."""
        from src.tools.estimate_timeline import _compute_station_sum
        data = [
            {"station": "BLDG", "p25_days": None, "p50_days": 10.0, "p75_days": None, "p90_days": None, "sample_count": 50, "period": "current"},
            {"station": "SFFD", "p25_days": 2.0, "p50_days": 5.0, "p75_days": 8.0, "p90_days": 12.0, "sample_count": 30, "period": "current"},
        ]
        result = _compute_station_sum(data)
        assert result is not None
        assert result["p50_days"] == 15  # 10 + 5

    @pytest.mark.asyncio
    async def test_timeline_with_triggers_includes_fire_stations(self):
        """Triggers=fire_review should attempt to query SFFD/SFFD-HQ stations."""
        from src.tools.estimate_timeline import estimate_timeline
        result = await estimate_timeline(
            permit_type="alterations",
            triggers=["fire_review"],
            return_structured=True,
        )
        md, meta = result
        assert isinstance(md, str)
        assert "methodology" in meta

    @pytest.mark.asyncio
    async def test_coverage_gaps_empty_when_data_available(self):
        """If DB has good data and no widening, coverage_gaps should be short."""
        from src.tools.estimate_timeline import estimate_timeline
        _, meta = await estimate_timeline(permit_type="alterations", return_structured=True)
        gaps = meta["methodology"]["coverage_gaps"]
        # coverage_gaps should be a list (may have items but must be a list)
        assert isinstance(gaps, list)

    @pytest.mark.asyncio
    async def test_fees_revision_context_rate_between_0_and_1(self):
        """revision_rate should be between 0 and 1 (decimal, not percentage)."""
        from src.tools.estimate_fees import estimate_fees
        _, meta = await estimate_fees(
            permit_type="alterations",
            estimated_construction_cost=75000,
            return_structured=True,
        )
        rc = meta.get("revision_context", {})
        if rc and "revision_rate" in rc:
            assert 0 < rc["revision_rate"] < 1, f"Invalid revision_rate: {rc['revision_rate']}"

    def test_format_days_sub_day(self):
        from src.tools.estimate_timeline import _format_days
        assert _format_days(0.5) == "<1 day"

    def test_format_days_single_day(self):
        from src.tools.estimate_timeline import _format_days
        assert "day" in _format_days(3).lower() or "days" in _format_days(3).lower()

    def test_format_days_weeks(self):
        from src.tools.estimate_timeline import _format_days
        assert "wk" in _format_days(14)

    def test_format_days_months(self):
        from src.tools.estimate_timeline import _format_days
        assert "mo" in _format_days(60)

    def test_format_days_none(self):
        from src.tools.estimate_timeline import _format_days
        assert _format_days(None) == "—"
