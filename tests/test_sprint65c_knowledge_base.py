"""Tests for Sprint 65-C: Knowledge base expansion — new tier1 JSON files."""

import json
from pathlib import Path

import pytest

TIER1_DIR = Path(__file__).parent.parent / "data" / "knowledge" / "tier1"


def _load_json(filename: str) -> dict:
    """Load and parse a tier1 JSON file."""
    path = TIER1_DIR / filename
    assert path.exists(), f"File not found: {path}"
    with open(path) as f:
        return json.load(f)


# ── Commercial Completeness Checklist ────────────────────────────


class TestCommercialCompletenessChecklist:
    @pytest.fixture(autouse=True)
    def load(self):
        self.data = _load_json("commercial-completeness-checklist.json")

    def test_valid_json(self):
        assert isinstance(self.data, dict)

    def test_has_metadata(self):
        assert "metadata" in self.data
        assert "title" in self.data["metadata"]
        assert "authority" in self.data["metadata"]
        assert "date_structured" in self.data["metadata"]

    def test_has_required_forms(self):
        assert "required_forms" in self.data
        forms = self.data["required_forms"]
        assert "primary" in forms
        assert "supplemental_forms" in forms
        assert len(forms["supplemental_forms"]) >= 3

    def test_has_plan_set_requirements(self):
        assert "plan_set_requirements" in self.data
        psr = self.data["plan_set_requirements"]
        assert "cover_sheet" in psr
        assert "floor_plans" in psr
        assert "site_plan" in psr

    def test_has_agency_routing_triggers(self):
        assert "agency_routing_triggers" in self.data
        triggers = self.data["agency_routing_triggers"]
        assert "planning_department" in triggers
        assert "sffd_fire_department" in triggers
        assert "dph_public_health" in triggers

    def test_has_common_rejection_reasons(self):
        assert "common_rejection_reasons" in self.data
        reasons = self.data["common_rejection_reasons"]
        assert isinstance(reasons, list)
        assert len(reasons) >= 5
        for reason in reasons:
            assert "reason" in reason
            assert "description" in reason
            assert "fix" in reason

    def test_has_otc_eligibility(self):
        assert "otc_eligibility" in self.data
        otc = self.data["otc_eligibility"]
        assert "eligible_scopes" in otc
        assert "not_eligible" in otc

    def test_metadata_scope_mentions_commercial(self):
        assert "commercial" in self.data["metadata"]["scope"].lower()


# ── School Impact Fees ───────────────────────────────────────────


class TestSchoolImpactFees:
    @pytest.fixture(autouse=True)
    def load(self):
        self.data = _load_json("school-impact-fees.json")

    def test_valid_json(self):
        assert isinstance(self.data, dict)

    def test_has_metadata(self):
        assert "metadata" in self.data
        assert self.data["metadata"]["gap_resolved"] == "GAP-11"

    def test_has_fee_schedule(self):
        assert "fee_schedule" in self.data
        rates = self.data["fee_schedule"]["rates"]
        assert "residential" in rates
        assert "commercial_industrial" in rates

    def test_residential_rate_is_numeric(self):
        rate = self.data["fee_schedule"]["rates"]["residential"]["rate_per_sqft"]
        assert isinstance(rate, (int, float))
        assert rate > 0

    def test_commercial_rate_is_numeric(self):
        rate = self.data["fee_schedule"]["rates"]["commercial_industrial"]["rate_per_sqft"]
        assert isinstance(rate, (int, float))
        assert rate > 0

    def test_residential_rate_higher_than_commercial(self):
        res = self.data["fee_schedule"]["rates"]["residential"]["rate_per_sqft"]
        com = self.data["fee_schedule"]["rates"]["commercial_industrial"]["rate_per_sqft"]
        assert res > com

    def test_has_exemptions(self):
        assert "exemptions" in self.data
        exemptions = self.data["exemptions"]
        assert "full_exemptions" in exemptions
        assert "partial_exemptions" in exemptions
        assert len(exemptions["full_exemptions"]) >= 3

    def test_has_calculation_method(self):
        assert "calculation_method" in self.data
        method = self.data["calculation_method"]
        assert "steps" in method
        assert "examples" in method
        assert len(method["steps"]) >= 3

    def test_has_payment_process(self):
        assert "payment_process" in self.data

    def test_has_state_law_context(self):
        assert "state_law_context" in self.data


# ── Special Inspection Requirements ──────────────────────────────


class TestSpecialInspectionRequirements:
    @pytest.fixture(autouse=True)
    def load(self):
        self.data = _load_json("special-inspection-requirements.json")

    def test_valid_json(self):
        assert isinstance(self.data, dict)

    def test_has_metadata(self):
        assert "metadata" in self.data
        assert self.data["metadata"]["gap_resolved"] == "GAP-13"

    def test_has_when_required(self):
        assert "when_required" in self.data
        wr = self.data["when_required"]
        assert "general_triggers" in wr
        assert len(wr["general_triggers"]) >= 5

    def test_has_inspection_types(self):
        assert "inspection_types" in self.data
        types = self.data["inspection_types"]
        assert len(types) >= 5
        # Check for key inspection types
        assert "structural_steel" in types
        assert "concrete" in types
        assert "masonry" in types
        assert "soils_and_foundations" in types

    def test_inspection_type_structure(self):
        """Each inspection type has required fields."""
        for type_key, type_data in self.data["inspection_types"].items():
            assert "category" in type_data, f"{type_key} missing category"
            assert "cbc_section" in type_data, f"{type_key} missing cbc_section"
            assert "activities_requiring_inspection" in type_data, f"{type_key} missing activities"
            assert "qualified_inspector" in type_data, f"{type_key} missing qualified_inspector"
            assert "frequency" in type_data, f"{type_key} missing frequency"

    def test_has_who_can_perform(self):
        assert "who_can_perform" in self.data
        wcp = self.data["who_can_perform"]
        assert "requirements" in wcp
        assert "common_certifications" in wcp
        assert len(wcp["common_certifications"]) >= 5

    def test_has_statement_of_special_inspections(self):
        assert "statement_of_special_inspections" in self.data
        ssi = self.data["statement_of_special_inspections"]
        assert "form" in ssi
        assert "contents" in ssi

    def test_has_sf_specific_requirements(self):
        assert "sf_specific_requirements" in self.data


# ── GAPS.md and SOURCES.md verification ──────────────────────────


class TestGapsAndSources:
    def test_gap11_marked_resolved(self):
        gaps_path = TIER1_DIR.parent / "GAPS.md"
        text = gaps_path.read_text()
        assert "GAP-11" in text
        assert "RESOLVED" in text.split("GAP-11")[1].split("\n")[0]

    def test_gap13_marked_resolved(self):
        gaps_path = TIER1_DIR.parent / "GAPS.md"
        text = gaps_path.read_text()
        assert "GAP-13" in text
        assert "RESOLVED" in text.split("GAP-13")[1].split("\n")[0]

    def test_sources_lists_commercial_checklist(self):
        sources_path = TIER1_DIR.parent / "SOURCES.md"
        text = sources_path.read_text()
        assert "commercial-completeness-checklist.json" in text

    def test_sources_lists_school_impact_fees(self):
        sources_path = TIER1_DIR.parent / "SOURCES.md"
        text = sources_path.read_text()
        assert "school-impact-fees.json" in text

    def test_sources_lists_special_inspections(self):
        sources_path = TIER1_DIR.parent / "SOURCES.md"
        text = sources_path.read_text()
        assert "special-inspection-requirements.json" in text
