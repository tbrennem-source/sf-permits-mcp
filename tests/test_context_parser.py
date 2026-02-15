"""Tests for context_parser keyword extraction and section ordering."""

from src.tools.context_parser import (
    extract_triggers,
    enhance_description,
    reorder_sections,
)


# ----- extract_triggers -----

def test_extract_empty():
    assert extract_triggers("") == []
    assert extract_triggers(None) == []


def test_extract_single_trigger():
    result = extract_triggers("This is a historic building renovation")
    assert "historic" in result


def test_extract_multiple_triggers():
    result = extract_triggers(
        "Seismic retrofit of a restaurant with fire alarm upgrades"
    )
    assert "seismic" in result
    assert "restaurant" in result
    assert "fire" in result


def test_extract_case_insensitive():
    result = extract_triggers("LEED certification required for this project")
    assert "green_building" in result


def test_extract_urgency():
    result = extract_triggers("Need this ASAP, tight deadline")
    assert "urgency" in result


def test_extract_adu():
    result = extract_triggers("Converting garage to accessory dwelling unit")
    assert "adu" in result


def test_extract_no_false_positives():
    result = extract_triggers("Simple residential painting project, no structural work")
    assert len(result) == 0


def test_extract_change_of_use():
    result = extract_triggers("Convert retail to restaurant, change of occupancy")
    assert "change_of_use" in result
    assert "restaurant" in result


def test_extract_budget_concern():
    result = extract_triggers("Need to minimize cost, tight budget")
    assert "budget" in result


def test_extract_accessibility():
    result = extract_triggers("ADA path of travel upgrades required")
    assert "accessibility" in result


def test_extract_violation():
    result = extract_triggers("There's a notice of violation on the property")
    assert "violation" in result


# ----- enhance_description -----

def test_enhance_basic():
    result = enhance_description("Kitchen remodel")
    assert result == "Kitchen remodel"


def test_enhance_with_context():
    result = enhance_description("Kitchen remodel", "Historic building")
    assert "Kitchen remodel" in result
    assert "Historic building" in result


def test_enhance_with_triggers():
    result = enhance_description(
        "Office renovation",
        None,
        ["seismic", "fire"],
    )
    assert "Office renovation" in result
    assert "seismic" in result


def test_enhance_no_duplicate_triggers():
    """Triggers already present in description shouldn't be appended."""
    result = enhance_description(
        "Seismic retrofit project",
        None,
        ["seismic"],
    )
    # "seismic" is already in the description, so no [Context: ...] block needed
    assert "[Context:" not in result


def test_enhance_empty_context_ignored():
    result = enhance_description("Kitchen remodel", "  ", [])
    assert result == "Kitchen remodel"


# ----- reorder_sections -----

def test_reorder_default():
    result = reorder_sections([])
    assert result == ["predict", "timeline", "fees", "docs", "risk"]


def test_reorder_timeline_first():
    result = reorder_sections(["timeline"])
    assert result[0] == "timeline"
    assert len(result) == 5  # all sections present


def test_reorder_cost_and_corrections():
    result = reorder_sections(["cost", "corrections"])
    assert result[0] == "fees"
    assert result[1] == "risk"
    assert len(result) == 5


def test_reorder_exploring():
    result = reorder_sections(["exploring"])
    assert result[0] == "predict"


def test_reorder_all_priorities():
    result = reorder_sections(["timeline", "cost", "corrections", "requirements", "exploring"])
    assert result == ["timeline", "fees", "risk", "docs", "predict"]


def test_reorder_no_duplicates():
    result = reorder_sections(["timeline", "timeline"])
    assert result.count("timeline") == 1
    assert len(result) == 5
