"""Tests for Sprint 56B: new tier1 knowledge files and semantic index concepts.

Covers:
- trade-permits.json structure and content
- street-use-permits.json structure and content
- housing-development.json structure and content
- reference-tables.json structure and content
- semantic-index.json new concepts (15+)
- KnowledgeBase loading of all 4 new files
- JSON validity for all new files
- Semantic concept matching for new aliases
"""

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TIER1_DIR = Path(__file__).parent.parent / "data" / "knowledge" / "tier1"


def load_json(filename: str) -> dict:
    """Load a tier1 JSON file and return parsed dict."""
    path = TIER1_DIR / filename
    with open(path, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# JSON Validity Tests (fail fast if file is broken)
# ---------------------------------------------------------------------------

class TestJsonValidity:
    """Verify all 4 new files are valid JSON."""

    def test_trade_permits_valid_json(self):
        """trade-permits.json is parseable valid JSON."""
        data = load_json("trade-permits.json")
        assert isinstance(data, dict)

    def test_street_use_permits_valid_json(self):
        """street-use-permits.json is parseable valid JSON."""
        data = load_json("street-use-permits.json")
        assert isinstance(data, dict)

    def test_housing_development_valid_json(self):
        """housing-development.json is parseable valid JSON."""
        data = load_json("housing-development.json")
        assert isinstance(data, dict)

    def test_reference_tables_valid_json(self):
        """reference-tables.json is parseable valid JSON."""
        data = load_json("reference-tables.json")
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Trade Permits Structure Tests
# ---------------------------------------------------------------------------

class TestTradePermits:
    """Verify trade-permits.json structure and key content."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.data = load_json("trade-permits.json")

    def test_has_metadata(self):
        assert "metadata" in self.data
        assert self.data["metadata"]["title"]

    def test_has_electrical_permits(self):
        assert "electrical_permits" in self.data
        elec = self.data["electrical_permits"]
        assert "permit_types" in elec
        assert len(elec["permit_types"]) >= 3

    def test_electrical_has_ev_charger(self):
        """EV charger is included as an electrical permit type."""
        elec_types = self.data["electrical_permits"]["permit_types"]
        ids = [pt["id"] for pt in elec_types]
        assert "ELEC-02" in ids, "EV Charger permit type ELEC-02 should exist"

    def test_electrical_has_solar_permit(self):
        """Solar PV permit is included."""
        elec_types = self.data["electrical_permits"]["permit_types"]
        ids = [pt["id"] for pt in elec_types]
        assert "ELEC-03" in ids, "Solar permit type ELEC-03 should exist"

    def test_has_plumbing_permits(self):
        assert "plumbing_permits" in self.data
        plmb = self.data["plumbing_permits"]
        assert "permit_types" in plmb
        assert len(plmb["permit_types"]) >= 3

    def test_plumbing_has_sewer_lateral(self):
        """Sewer lateral is a plumbing permit type."""
        plmb_types = self.data["plumbing_permits"]["permit_types"]
        ids = [pt["id"] for pt in plmb_types]
        assert "PLMB-02" in ids, "Sewer lateral permit PLMB-02 should exist"

    def test_has_mechanical_permits(self):
        assert "mechanical_permits" in self.data
        mech = self.data["mechanical_permits"]
        assert "permit_types" in mech
        assert len(mech["permit_types"]) >= 2

    def test_mechanical_has_boiler(self):
        """Boiler permit is included in mechanical permits."""
        mech_types = self.data["mechanical_permits"]["permit_types"]
        ids = [pt["id"] for pt in mech_types]
        assert "MECH-02" in ids, "Boiler permit type MECH-02 should exist"

    def test_has_trade_relationships(self):
        """trade_permit_relationships section exists with bundling info."""
        assert "trade_permit_relationships" in self.data
        rel = self.data["trade_permit_relationships"]
        assert "key_rules" in rel
        assert "bundling_by_project_type" in rel

    def test_bundling_covers_kitchen_remodel(self):
        """Kitchen remodel bundling info exists."""
        bundling = self.data["trade_permit_relationships"]["bundling_by_project_type"]
        assert "kitchen_remodel" in bundling

    def test_bundling_covers_adu(self):
        """ADU bundling info exists."""
        bundling = self.data["trade_permit_relationships"]["bundling_by_project_type"]
        assert "adu_addition" in bundling

    def test_has_fee_reference(self):
        """Electrical fee table reference is present."""
        fee_ref = self.data["electrical_permits"]["fee_reference"]
        assert fee_ref["table"] == "1A-E"

    def test_inspection_requirements_present(self):
        """All three trades have inspection requirements."""
        assert len(self.data["electrical_permits"]["inspection_requirements"]) >= 2
        assert len(self.data["plumbing_permits"]["inspection_requirements"]) >= 2
        assert len(self.data["mechanical_permits"]["inspection_requirements"]) >= 1


# ---------------------------------------------------------------------------
# Street Use Permits Structure Tests
# ---------------------------------------------------------------------------

class TestStreetUsePermits:
    """Verify street-use-permits.json structure and key content."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.data = load_json("street-use-permits.json")

    def test_has_metadata(self):
        assert "metadata" in self.data
        assert self.data["metadata"]["title"]

    def test_has_jurisdiction_section(self):
        assert "jurisdiction" in self.data
        assert "dpw_bsm" in self.data["jurisdiction"]
        assert "sfmta" in self.data["jurisdiction"]

    def test_has_permit_types(self):
        assert "permit_types" in self.data
        assert len(self.data["permit_types"]) >= 5

    def test_has_excavation_permit(self):
        """Excavation permit (SU-01) is included."""
        ids = [pt["id"] for pt in self.data["permit_types"]]
        assert "SU-01" in ids, "Excavation permit SU-01 should exist"

    def test_has_construction_occupancy_permit(self):
        """Construction Occupancy/Staging permit (SU-02) is included."""
        ids = [pt["id"] for pt in self.data["permit_types"]]
        assert "SU-02" in ids, "Construction Occupancy permit SU-02 should exist"

    def test_has_curb_cut_permit(self):
        """Curb cut/driveway permit (SU-04) is included."""
        ids = [pt["id"] for pt in self.data["permit_types"]]
        assert "SU-04" in ids, "Curb cut permit SU-04 should exist"

    def test_excavation_has_requirements(self):
        """Excavation permit has requirements listed."""
        su01 = next(pt for pt in self.data["permit_types"] if pt["id"] == "SU-01")
        assert "requirements" in su01
        assert len(su01["requirements"]) >= 3

    def test_has_relationship_to_building_permits(self):
        """Relationship to building permits section exists."""
        assert "relationship_to_building_permits" in self.data
        rel = self.data["relationship_to_building_permits"]
        assert "when_both_required" in rel

    def test_has_duration_and_renewal(self):
        """Duration limits and renewal info is present."""
        assert "duration_limits_and_renewals" in self.data

    def test_has_common_mistakes(self):
        """Common mistakes section exists for user guidance."""
        assert "common_mistakes" in self.data
        assert len(self.data["common_mistakes"]) >= 3

    def test_parklet_permit_included(self):
        """Parklet permit (SU-06) is included."""
        ids = [pt["id"] for pt in self.data["permit_types"]]
        assert "SU-06" in ids, "Parklet permit SU-06 should exist"


# ---------------------------------------------------------------------------
# Housing Development Structure Tests
# ---------------------------------------------------------------------------

class TestHousingDevelopment:
    """Verify housing-development.json structure and key content."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.data = load_json("housing-development.json")

    def test_has_metadata(self):
        assert "metadata" in self.data
        assert self.data["metadata"]["title"]

    def test_has_adu_programs(self):
        assert "adu_programs" in self.data
        adu = self.data["adu_programs"]
        assert "program_types" in adu
        assert len(adu["program_types"]) >= 4

    def test_adu_has_attached_type(self):
        """Attached ADU type exists."""
        types = self.data["adu_programs"]["program_types"]
        ids = [t["id"] for t in types]
        assert "ADU-01" in ids, "Attached ADU type ADU-01 should exist"

    def test_adu_has_jadu(self):
        """Junior ADU (JADU) type exists."""
        types = self.data["adu_programs"]["program_types"]
        ids = [t["id"] for t in types]
        assert "ADU-03" in ids, "JADU type ADU-03 should exist"

    def test_adu_has_state_preemption_rules(self):
        """State law protections for ADUs are documented."""
        assert "state_preemption_rules" in self.data["adu_programs"]
        preemption = self.data["adu_programs"]["state_preemption_rules"]
        assert "key_limits" in preemption
        assert len(preemption["key_limits"]) >= 3

    def test_has_inclusionary_housing(self):
        assert "inclusionary_housing" in self.data
        incl = self.data["inclusionary_housing"]
        assert "applicability" in incl
        assert "requirement_options" in incl

    def test_inclusionary_threshold_is_10_units(self):
        """Inclusionary housing applies to 10+ unit projects."""
        threshold = self.data["inclusionary_housing"]["applicability"]["threshold"]
        assert "10" in threshold

    def test_has_density_bonus_programs(self):
        assert "density_bonus_programs" in self.data
        db = self.data["density_bonus_programs"]
        assert "state_density_bonus" in db
        assert "sf_local_programs" in db

    def test_density_bonus_has_tiers(self):
        """State density bonus has multiple affordability tiers."""
        tiers = self.data["density_bonus_programs"]["state_density_bonus"]["bonus_tiers"]
        assert len(tiers) >= 4

    def test_has_development_pipeline(self):
        assert "development_pipeline" in self.data
        pipeline = self.data["development_pipeline"]
        assert "tracking_stages" in pipeline
        assert len(pipeline["tracking_stages"]) >= 5

    def test_has_permit_process(self):
        assert "permit_process_for_housing" in self.data

    def test_adu_legalization_includes_fee_waiver_note(self):
        """ADU legalization entry mentions plan review fee waiver."""
        types = self.data["adu_programs"]["program_types"]
        adu05 = next(t for t in types if t["id"] == "ADU-05")
        special_rules_str = str(adu05.get("special_rules", []))
        assert "fee" in special_rules_str.lower() or "waiv" in special_rules_str.lower()


# ---------------------------------------------------------------------------
# Reference Tables Knowledge Structure Tests
# ---------------------------------------------------------------------------

class TestReferenceTablesKnowledge:
    """Verify reference-tables.json structure and key content."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.data = load_json("reference-tables.json")

    def test_has_metadata(self):
        assert "metadata" in self.data
        assert self.data["metadata"]["title"]

    def test_has_ref_zoning_routing(self):
        assert "ref_zoning_routing" in self.data
        zr = self.data["ref_zoning_routing"]
        assert "description" in zr
        assert "table_schema" in zr
        assert "key_zoning_codes" in zr

    def test_zoning_schema_has_required_columns(self):
        """ref_zoning_routing schema has all 8 expected columns."""
        schema = self.data["ref_zoning_routing"]["table_schema"]
        required_cols = {
            "zoning_code", "zoning_category", "planning_review_required",
            "fire_review_required", "health_review_required",
            "historic_district", "height_limit", "notes"
        }
        for col in required_cols:
            assert col in schema, f"Missing column '{col}' in ref_zoning_routing schema"

    def test_has_common_zoning_codes(self):
        """Key SF zoning codes are documented."""
        codes_data = self.data["ref_zoning_routing"]["key_zoning_codes"]
        all_codes = set()
        for category, entries in codes_data.items():
            for entry in entries:
                all_codes.add(entry["code"])
        expected = {"RH-1", "RC-4", "C-3-O", "PDR-1-G"}
        missing = expected - all_codes
        assert not missing, f"Missing expected zoning codes: {missing}"

    def test_has_ref_permit_forms(self):
        assert "ref_permit_forms" in self.data
        pf = self.data["ref_permit_forms"]
        assert "common_mappings" in pf
        assert "form_reference" in pf

    def test_permit_forms_covers_key_project_types(self):
        """ref_permit_forms covers kitchen_remodel, adu, new_construction, restaurant, demolition."""
        mappings = self.data["ref_permit_forms"]["common_mappings"]
        project_types = {m["project_type"] for m in mappings}
        required = {"kitchen_remodel", "adu", "new_construction", "restaurant", "demolition"}
        missing = required - project_types
        assert not missing, f"Missing project types: {missing}"

    def test_new_construction_is_inhouse(self):
        """new_construction uses in_house review path."""
        mappings = self.data["ref_permit_forms"]["common_mappings"]
        nc = next(m for m in mappings if m["project_type"] == "new_construction")
        assert nc["review_path"] == "in_house"

    def test_has_ref_agency_triggers(self):
        assert "ref_agency_triggers" in self.data
        at = self.data["ref_agency_triggers"]
        assert "key_triggers" in at

    def test_agency_triggers_cover_key_agencies(self):
        """ref_agency_triggers documents planning, fire, and health triggers."""
        triggers = self.data["ref_agency_triggers"]["key_triggers"]
        assert "planning_triggers" in triggers
        assert "fire_triggers" in triggers
        assert "health_triggers" in triggers

    def test_restaurant_triggers_dph(self):
        """restaurant keyword triggers DPH review."""
        health_triggers = self.data["ref_agency_triggers"]["key_triggers"]["health_triggers"]
        keywords = [t["keyword"] for t in health_triggers]
        assert "restaurant" in keywords, "restaurant should trigger DPH health review"

    def test_has_tool_workflow_docs(self):
        """how_tables_power_prediction_tools section exists."""
        assert "how_tables_power_prediction_tools" in self.data

    def test_has_data_maintenance_section(self):
        """data_maintenance section describes seeding."""
        assert "data_maintenance" in self.data
        dm = self.data["data_maintenance"]
        assert "seeding" in dm


# ---------------------------------------------------------------------------
# KnowledgeBase Loading Tests
# ---------------------------------------------------------------------------

class TestKnowledgeBaseLoading:
    """Verify KnowledgeBase loads all 4 new files correctly."""

    @pytest.fixture(autouse=True)
    def kb(self):
        from src.tools.knowledge_base import get_knowledge_base
        # Clear cache to ensure fresh load with worktree files
        get_knowledge_base.cache_clear()
        self._kb = get_knowledge_base()

    def test_loads_trade_permits(self):
        """KnowledgeBase.trade_permits is loaded and non-empty."""
        assert self._kb.trade_permits
        assert "electrical_permits" in self._kb.trade_permits

    def test_loads_street_use_permits(self):
        """KnowledgeBase.street_use_permits is loaded and non-empty."""
        assert self._kb.street_use_permits
        assert "permit_types" in self._kb.street_use_permits

    def test_loads_housing_development(self):
        """KnowledgeBase.housing_development is loaded and non-empty."""
        assert self._kb.housing_development
        assert "adu_programs" in self._kb.housing_development

    def test_loads_reference_tables_knowledge(self):
        """KnowledgeBase.reference_tables_knowledge is loaded and non-empty."""
        assert self._kb.reference_tables_knowledge
        assert "ref_zoning_routing" in self._kb.reference_tables_knowledge


# ---------------------------------------------------------------------------
# Semantic Index Concept Tests
# ---------------------------------------------------------------------------

class TestSemanticIndexNewConcepts:
    """Verify the 15 new concepts are in semantic-index.json."""

    @pytest.fixture(autouse=True)
    def load(self):
        data = load_json("semantic-index.json")
        self.concepts = data.get("concepts", {})
        self.total_concepts = data.get("metadata", {}).get("total_concepts", 0)

    REQUIRED_NEW_CONCEPTS = [
        "electrical_permit",
        "plumbing_permit",
        "mechanical_permit",
        "street_use_permit",
        "construction_staging",
        "sewer_lateral",
        "adu",
        "housing_development",
        "inclusionary_housing",
        "density_bonus",
        "plumbing_inspection",
        "reference_tables",
        "review_metrics",
        "permit_bundling",
    ]

    def test_all_new_concepts_present(self):
        """All 14 new required concepts exist in semantic-index.json."""
        missing = [c for c in self.REQUIRED_NEW_CONCEPTS if c not in self.concepts]
        assert not missing, f"Missing concepts: {missing}"

    def test_total_concepts_updated(self):
        """total_concepts metadata reflects the addition of new concepts."""
        assert self.total_concepts >= 113, (
            f"total_concepts should be >= 113 after adding new concepts; got {self.total_concepts}"
        )

    def test_electrical_permit_has_aliases(self):
        """electrical_permit concept has meaningful aliases."""
        concept = self.concepts["electrical_permit"]
        aliases = concept["aliases"]
        assert len(aliases) >= 5
        assert any("panel" in a.lower() or "electrical" in a.lower() for a in aliases)

    def test_plumbing_permit_has_aliases(self):
        """plumbing_permit concept has meaningful aliases."""
        concept = self.concepts["plumbing_permit"]
        aliases = concept["aliases"]
        assert len(aliases) >= 5
        assert any("plumb" in a.lower() or "sewer" in a.lower() for a in aliases)

    def test_street_use_permit_has_aliases(self):
        """street_use_permit concept has meaningful aliases."""
        concept = self.concepts["street_use_permit"]
        aliases = concept["aliases"]
        assert len(aliases) >= 6
        assert any("excavation" in a.lower() or "sidewalk" in a.lower() for a in aliases)

    def test_adu_concept_has_aliases(self):
        """adu concept has meaningful aliases."""
        concept = self.concepts["adu"]
        aliases = concept["aliases"]
        assert len(aliases) >= 5
        assert "ADU" in aliases or "adu" in [a.lower() for a in aliases]

    def test_housing_development_has_inclusionary_aliases(self):
        """housing_development concept covers inclusionary housing aliases."""
        concept = self.concepts["housing_development"]
        aliases = concept["aliases"]
        alias_str = " ".join(aliases).lower()
        assert "inclusionary" in alias_str or "affordable" in alias_str

    def test_all_new_concepts_have_description(self):
        """All new concepts have a non-empty description."""
        for concept_name in self.REQUIRED_NEW_CONCEPTS:
            if concept_name in self.concepts:
                concept = self.concepts[concept_name]
                assert concept.get("description"), f"Concept '{concept_name}' missing description"

    def test_all_new_concepts_have_authoritative_sources(self):
        """All new concepts have at least one authoritative source."""
        for concept_name in self.REQUIRED_NEW_CONCEPTS:
            if concept_name in self.concepts:
                concept = self.concepts[concept_name]
                sources = concept.get("authoritative_sources", [])
                assert len(sources) >= 1, (
                    f"Concept '{concept_name}' should have at least 1 authoritative source"
                )

    def test_all_new_concepts_have_related_concepts(self):
        """All new concepts have related_concepts field (may be empty list)."""
        for concept_name in self.REQUIRED_NEW_CONCEPTS:
            if concept_name in self.concepts:
                concept = self.concepts[concept_name]
                assert "related_concepts" in concept, (
                    f"Concept '{concept_name}' missing related_concepts field"
                )


# ---------------------------------------------------------------------------
# Semantic Matching Tests
# ---------------------------------------------------------------------------

class TestSemanticMatching:
    """Verify match_concepts works correctly for new concepts."""

    @pytest.fixture(autouse=True)
    def kb(self):
        from src.tools.knowledge_base import get_knowledge_base
        get_knowledge_base.cache_clear()
        self._kb = get_knowledge_base()

    def test_matches_electrical_work(self):
        """'panel upgrade' matches electrical_permit concept."""
        matches = self._kb.match_concepts("I need a panel upgrade for my EV charger")
        assert "electrical_permit" in matches, (
            f"'panel upgrade' should match electrical_permit, got: {matches[:5]}"
        )

    def test_matches_sewer_lateral(self):
        """'sewer lateral' matches plumbing_permit or sewer_lateral concept."""
        matches = self._kb.match_concepts("my sewer lateral is broken")
        assert any(c in matches for c in ["plumbing_permit", "sewer_lateral"]), (
            f"'sewer lateral' should match plumbing or sewer concept, got: {matches[:5]}"
        )

    def test_matches_excavation(self):
        """'sidewalk excavation' matches street_use_permit concept."""
        matches = self._kb.match_concepts("sidewalk excavation for sewer lateral work")
        assert "street_use_permit" in matches, (
            f"'sidewalk excavation' should match street_use_permit, got: {matches[:5]}"
        )

    def test_matches_adu(self):
        """'ADU' matches adu concept."""
        matches = self._kb.match_concepts("I want to build an ADU in my backyard")
        assert "adu" in matches, (
            f"'ADU' should match adu concept, got: {matches[:5]}"
        )

    def test_matches_inclusionary_housing(self):
        """'inclusionary housing' matches inclusionary_housing concept."""
        matches = self._kb.match_concepts("what are the inclusionary housing requirements")
        assert "inclusionary_housing" in matches, (
            f"'inclusionary housing' should match, got: {matches[:5]}"
        )

    def test_matches_hvac(self):
        """'HVAC permit' matches mechanical_permit concept."""
        matches = self._kb.match_concepts("I need an HVAC permit for a new furnace")
        assert "mechanical_permit" in matches, (
            f"'HVAC permit' should match mechanical_permit, got: {matches[:5]}"
        )
