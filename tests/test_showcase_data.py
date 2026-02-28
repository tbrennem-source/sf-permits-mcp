"""Tests for scripts/generate_showcase_data.py.

Verifies that generate_all() returns complete, well-structured fixture data
and that the output JSON file can be written and parsed correctly.
"""

import json
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

from scripts.generate_showcase_data import generate_all, write_output, OUTPUT_FILE


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def showcase_data():
    """Generate showcase data once for the whole test module."""
    return generate_all()


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------

class TestTopLevelStructure:
    def test_returns_dict(self, showcase_data):
        assert isinstance(showcase_data, dict)

    def test_has_all_six_keys(self, showcase_data):
        expected = {
            "station_timeline",
            "stuck_permit",
            "what_if",
            "revision_risk",
            "entity_network",
            "cost_of_delay",
        }
        assert set(showcase_data.keys()) == expected

    def test_all_values_are_dicts(self, showcase_data):
        for key, value in showcase_data.items():
            assert isinstance(value, dict), f"{key} value should be a dict"


# ---------------------------------------------------------------------------
# Showcase 1: station_timeline
# ---------------------------------------------------------------------------

class TestStationTimeline:
    @pytest.fixture(autouse=True)
    def st(self, showcase_data):
        self.data = showcase_data["station_timeline"]

    def test_has_permit_number(self):
        assert self.data["permit"] == "202509155257"

    def test_has_stations_list(self):
        assert isinstance(self.data["stations"], list)
        assert len(self.data["stations"]) >= 6

    def test_stations_have_required_fields(self):
        required = {"station", "label", "arrive", "status", "addenda_number"}
        for station in self.data["stations"]:
            missing = required - set(station.keys())
            assert not missing, f"Station {station.get('station')} missing fields: {missing}"

    def test_elapsed_days_is_positive(self):
        assert isinstance(self.data["elapsed_days"], int)
        assert self.data["elapsed_days"] > 0

    def test_has_summary(self):
        summary = self.data["summary"]
        assert "total_stations" in summary
        assert "bldg_comment_rounds" in summary
        assert summary["bldg_comment_rounds"] == 3

    def test_has_estimated_cost(self):
        assert self.data["estimated_cost"] == 13000000


# ---------------------------------------------------------------------------
# Showcase 2: stuck_permit
# ---------------------------------------------------------------------------

class TestStuckPermit:
    @pytest.fixture(autouse=True)
    def sp(self, showcase_data):
        self.data = showcase_data["stuck_permit"]

    def test_has_permit_number(self):
        assert self.data["permit"] == "202412237330"

    def test_has_blocks_list(self):
        assert isinstance(self.data["blocks"], list)
        assert len(self.data["blocks"]) == 4

    def test_blocks_have_required_fields(self):
        required = {"station", "dwell_days", "status", "flags"}
        for block in self.data["blocks"]:
            missing = required - set(block.keys())
            assert not missing, f"Block {block.get('station')} missing: {missing}"

    def test_has_playbook(self):
        assert isinstance(self.data["playbook"], list)
        assert len(self.data["playbook"]) >= 3

    def test_playbook_has_urgency(self):
        urgencies = {step["urgency"] for step in self.data["playbook"]}
        assert "IMMEDIATE" in urgencies or "HIGH" in urgencies

    def test_planning_days(self):
        assert self.data["planning_days"] == 223

    def test_has_severity(self):
        assert "severity_score" in self.data
        assert "severity_tier" in self.data
        assert self.data["severity_tier"] == "HIGH"


# ---------------------------------------------------------------------------
# Showcase 3: what_if
# ---------------------------------------------------------------------------

class TestWhatIf:
    @pytest.fixture(autouse=True)
    def wi(self, showcase_data):
        self.data = showcase_data["what_if"]

    def test_has_scenario_a(self):
        assert "scenario_a" in self.data
        assert self.data["scenario_a"]["review_path"] == "OTC"

    def test_has_scenario_b(self):
        assert "scenario_b" in self.data
        assert self.data["scenario_b"]["review_path"] == "In-house"

    def test_has_comparison(self):
        assert isinstance(self.data["comparison"], list)
        assert len(self.data["comparison"]) >= 4

    def test_comparison_has_verdict(self):
        for item in self.data["comparison"]:
            assert "verdict" in item, f"Comparison item missing verdict: {item}"

    def test_scenario_a_faster_than_b(self):
        assert self.data["scenario_a"]["p50_days"] < self.data["scenario_b"]["p50_days"]

    def test_scenario_a_cheaper_than_b(self):
        assert self.data["scenario_a"]["total_fees"] < self.data["scenario_b"]["total_fees"]

    def test_has_recommendation(self):
        assert isinstance(self.data["recommendation"], str)
        assert len(self.data["recommendation"]) > 20


# ---------------------------------------------------------------------------
# Showcase 4: revision_risk
# ---------------------------------------------------------------------------

class TestRevisionRisk:
    @pytest.fixture(autouse=True)
    def rr(self, showcase_data):
        self.data = showcase_data["revision_risk"]

    def test_has_rate(self):
        assert self.data["rate"] == 0.246

    def test_has_sample_size(self):
        assert self.data["sample_size"] == 21596

    def test_has_triggers(self):
        assert isinstance(self.data["triggers"], list)
        assert len(self.data["triggers"]) == 5

    def test_triggers_have_rank(self):
        ranks = [t["rank"] for t in self.data["triggers"]]
        assert ranks == [1, 2, 3, 4, 5]

    def test_has_timeline_impact(self):
        assert self.data["timeline_impact_days"] == 51

    def test_has_mitigation_strategies(self):
        assert isinstance(self.data["mitigation_strategies"], list)
        assert len(self.data["mitigation_strategies"]) >= 3

    def test_risk_level_is_string(self):
        assert isinstance(self.data["risk_level"], str)
        assert self.data["risk_level"] in {"LOW", "MODERATE", "HIGH", "CRITICAL"}


# ---------------------------------------------------------------------------
# Showcase 5: entity_network
# ---------------------------------------------------------------------------

class TestEntityNetwork:
    @pytest.fixture(autouse=True)
    def en(self, showcase_data):
        self.data = showcase_data["entity_network"]

    def test_has_address(self):
        assert "1 Market" in self.data["address"]

    def test_has_permit_count(self):
        assert self.data["permits"] == 63

    def test_has_entities(self):
        assert isinstance(self.data["entities"], list)
        assert len(self.data["entities"]) >= 3

    def test_entities_have_required_fields(self):
        required = {"entity_id", "canonical_name", "entity_type", "permit_count", "shared_permits"}
        for entity in self.data["entities"]:
            missing = required - set(entity.keys())
            assert not missing, f"Entity {entity.get('canonical_name')} missing: {missing}"

    def test_arb_inc_present(self):
        names = [e["canonical_name"] for e in self.data["entities"]]
        assert "Arb Inc" in names

    def test_arb_inc_permit_count(self):
        arb = next(e for e in self.data["entities"] if e["canonical_name"] == "Arb Inc")
        assert arb["permit_count"] == 12674

    def test_has_insight(self):
        assert isinstance(self.data["insight"], str)
        assert len(self.data["insight"]) > 20


# ---------------------------------------------------------------------------
# Showcase 6: cost_of_delay
# ---------------------------------------------------------------------------

class TestCostOfDelay:
    @pytest.fixture(autouse=True)
    def cd(self, showcase_data):
        self.data = showcase_data["cost_of_delay"]

    def test_has_monthly_cost(self):
        assert self.data["monthly_cost"] == 15000

    def test_has_percentiles(self):
        percentiles = self.data["percentiles"]
        assert "p25" in percentiles
        assert "p50" in percentiles
        assert "p75" in percentiles
        assert "p90" in percentiles

    def test_percentile_costs_increase(self):
        p = self.data["percentiles"]
        assert p["p25"]["cost"] < p["p50"]["cost"]
        assert p["p50"]["cost"] < p["p75"]["cost"]
        assert p["p75"]["cost"] < p["p90"]["cost"]

    def test_has_expected(self):
        expected = self.data["expected"]
        assert "cost" in expected
        assert expected["cost"] > 0

    def test_has_bottleneck_alert(self):
        alert = self.data["bottleneck_alert"]
        assert "station" in alert
        assert alert["slowdown_pct"] == 86

    def test_has_roi_analysis(self):
        roi = self.data["roi_analysis"]
        assert "expediter_cost" in roi
        assert "net_roi" in roi


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------

class TestJsonOutput:
    def test_output_is_valid_json(self, showcase_data):
        """generate_all() output is fully JSON-serializable."""
        serialized = json.dumps(showcase_data)
        parsed = json.loads(serialized)
        assert set(parsed.keys()) == set(showcase_data.keys())

    def test_write_output_creates_file(self, showcase_data, tmp_path):
        """write_output() creates the file at the given path."""
        dest = tmp_path / "test_showcase.json"
        result_path = write_output(showcase_data, output_path=dest)
        assert result_path == dest
        assert dest.exists()

    def test_written_file_is_parseable(self, showcase_data, tmp_path):
        """Written file contains valid JSON matching the source data."""
        dest = tmp_path / "test_showcase.json"
        write_output(showcase_data, output_path=dest)
        parsed = json.loads(dest.read_text())
        assert set(parsed.keys()) == set(showcase_data.keys())

    def test_written_file_has_correct_permit_numbers(self, showcase_data, tmp_path):
        """Permit numbers survive the write/read round-trip."""
        dest = tmp_path / "test_showcase.json"
        write_output(showcase_data, output_path=dest)
        parsed = json.loads(dest.read_text())
        assert parsed["station_timeline"]["permit"] == "202509155257"
        assert parsed["stuck_permit"]["permit"] == "202412237330"

    def test_output_file_path_is_correct(self):
        """OUTPUT_FILE constant points to the expected location."""
        assert OUTPUT_FILE.name == "showcase_data.json"
        assert "web/static/data" in str(OUTPUT_FILE)

    def test_write_creates_parent_directories(self, showcase_data, tmp_path):
        """write_output() creates parent dirs if they don't exist."""
        dest = tmp_path / "nested" / "dirs" / "showcase.json"
        write_output(showcase_data, output_path=dest)
        assert dest.exists()
