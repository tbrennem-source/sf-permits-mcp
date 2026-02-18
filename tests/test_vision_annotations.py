"""Tests for vision annotation extraction (spatial markup).

Tests extract_page_annotations() — the function that calls Claude Vision
to get spatially-located annotations for plan page overlay rendering.

All tests mock the vision API. No real API calls.
"""

import json
import pytest
from unittest.mock import patch, AsyncMock

from src.vision.client import VisionResult
from src.vision.epr_checks import (
    extract_page_annotations,
    VALID_ANNOTATION_TYPES,
    VALID_ANCHORS,
    MAX_ANNOTATIONS_PER_PAGE,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_vision_result(data: dict) -> VisionResult:
    """Create a successful VisionResult with JSON text."""
    return VisionResult(
        success=True,
        text=json.dumps(data),
        input_tokens=100,
        output_tokens=50,
    )


def _make_failed_result(error: str = "API error") -> VisionResult:
    """Create a failed VisionResult."""
    return VisionResult(
        success=False,
        text="",
        error=error,
    )


# ── Basic extraction ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_annotations_basic():
    """Extracts annotations with valid data."""
    data = {
        "annotations": [
            {
                "type": "code_reference",
                "label": "CBC 1020.1 — Corridor width",
                "x": 35.2,
                "y": 48.7,
                "anchor": "top-right",
                "importance": "high",
            },
            {
                "type": "occupancy_label",
                "label": "Group B Occupancy",
                "x": 52.0,
                "y": 30.1,
                "anchor": "bottom-left",
                "importance": "medium",
            },
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert len(result) == 2
    assert result[0]["type"] == "code_reference"
    assert result[0]["label"] == "CBC 1020.1 — Corridor width"
    assert result[0]["x"] == 35.2
    assert result[0]["y"] == 48.7
    assert result[0]["anchor"] == "top-right"
    assert result[0]["importance"] == "high"
    assert result[0]["page_number"] == 1

    assert result[1]["type"] == "occupancy_label"
    assert result[1]["page_number"] == 1


@pytest.mark.asyncio
async def test_extract_annotations_page_number_propagated():
    """Page number is set on each annotation."""
    data = {
        "annotations": [
            {"type": "stamp", "label": "PE Stamp", "x": 80, "y": 90,
             "anchor": "top-left", "importance": "low"},
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 5)

    assert len(result) == 1
    assert result[0]["page_number"] == 5


# ── Validation ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clamps_coordinates():
    """Coordinates are clamped to 0-100 range."""
    data = {
        "annotations": [
            {"type": "dimension", "label": "Room A", "x": -10, "y": 150,
             "anchor": "top-right", "importance": "medium"},
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert result[0]["x"] == 0.0
    assert result[0]["y"] == 100.0


@pytest.mark.asyncio
async def test_invalid_type_falls_back_to_general_note():
    """Unknown annotation type defaults to general_note."""
    data = {
        "annotations": [
            {"type": "unknown_type", "label": "Something", "x": 50, "y": 50,
             "anchor": "top-right", "importance": "medium"},
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert result[0]["type"] == "general_note"


@pytest.mark.asyncio
async def test_invalid_anchor_falls_back():
    """Unknown anchor defaults to top-right."""
    data = {
        "annotations": [
            {"type": "dimension", "label": "Width", "x": 50, "y": 50,
             "anchor": "center", "importance": "medium"},
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert result[0]["anchor"] == "top-right"


@pytest.mark.asyncio
async def test_invalid_importance_falls_back():
    """Unknown importance defaults to medium."""
    data = {
        "annotations": [
            {"type": "dimension", "label": "Height", "x": 50, "y": 50,
             "anchor": "top-right", "importance": "critical"},
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert result[0]["importance"] == "medium"


@pytest.mark.asyncio
async def test_label_truncation():
    """Labels longer than 60 chars are truncated."""
    long_label = "A" * 100
    data = {
        "annotations": [
            {"type": "general_note", "label": long_label, "x": 50, "y": 50,
             "anchor": "top-right", "importance": "low"},
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert len(result[0]["label"]) == 60


@pytest.mark.asyncio
async def test_empty_label_skipped():
    """Annotations with empty labels are skipped."""
    data = {
        "annotations": [
            {"type": "dimension", "label": "", "x": 50, "y": 50,
             "anchor": "top-right", "importance": "medium"},
            {"type": "dimension", "label": "Valid", "x": 60, "y": 60,
             "anchor": "top-right", "importance": "medium"},
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert len(result) == 1
    assert result[0]["label"] == "Valid"


@pytest.mark.asyncio
async def test_max_annotations_cap():
    """Caps at MAX_ANNOTATIONS_PER_PAGE annotations."""
    annotations = [
        {"type": "general_note", "label": f"Note {i}", "x": i * 5, "y": i * 5,
         "anchor": "top-right", "importance": "low"}
        for i in range(20)
    ]
    data = {"annotations": annotations}

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert len(result) == MAX_ANNOTATIONS_PER_PAGE


@pytest.mark.asyncio
async def test_invalid_coordinates_skipped():
    """Annotations with non-numeric coordinates are skipped."""
    data = {
        "annotations": [
            {"type": "dimension", "label": "Bad coords", "x": "abc", "y": "def",
             "anchor": "top-right", "importance": "medium"},
            {"type": "dimension", "label": "Good coords", "x": 50, "y": 50,
             "anchor": "top-right", "importance": "medium"},
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert len(result) == 1
    assert result[0]["label"] == "Good coords"


@pytest.mark.asyncio
async def test_coordinates_rounded():
    """Coordinates are rounded to 1 decimal place."""
    data = {
        "annotations": [
            {"type": "stamp", "label": "Stamp", "x": 33.33333, "y": 66.66666,
             "anchor": "top-right", "importance": "low"},
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert result[0]["x"] == 33.3
    assert result[0]["y"] == 66.7


# ── Failure modes ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vision_api_failure_returns_empty():
    """Returns empty list when vision API call fails."""
    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_failed_result("rate limited"),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert result == []


@pytest.mark.asyncio
async def test_vision_api_exception_returns_empty():
    """Returns empty list when vision API raises exception."""
    with patch(
        "src.vision.epr_checks.analyze_image",
        side_effect=Exception("connection error"),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert result == []


@pytest.mark.asyncio
async def test_unparseable_json_returns_empty():
    """Returns empty list when vision returns non-JSON."""
    result = VisionResult(
        success=True,
        text="This is not JSON at all",
        input_tokens=100,
        output_tokens=50,
    )

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=result,
    ):
        annotations = await extract_page_annotations("fake_b64", 1)

    assert annotations == []


@pytest.mark.asyncio
async def test_missing_annotations_key_returns_empty():
    """Returns empty list when response lacks 'annotations' key."""
    data = {"items": [{"label": "test"}]}

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert result == []


@pytest.mark.asyncio
async def test_annotations_not_list_returns_empty():
    """Returns empty list when annotations value is not a list."""
    data = {"annotations": "not a list"}

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert result == []


@pytest.mark.asyncio
async def test_non_dict_items_skipped():
    """Non-dict items in annotations list are skipped."""
    data = {
        "annotations": [
            "not a dict",
            42,
            {"type": "stamp", "label": "Valid", "x": 50, "y": 50,
             "anchor": "top-right", "importance": "low"},
        ]
    }

    with patch(
        "src.vision.epr_checks.analyze_image",
        return_value=_make_vision_result(data),
    ):
        result = await extract_page_annotations("fake_b64", 1)

    assert len(result) == 1
    assert result[0]["label"] == "Valid"


# ── Constants ────────────────────────────────────────────────────────────────


def test_valid_annotation_types():
    """VALID_ANNOTATION_TYPES contains expected types."""
    expected = {
        "epr_issue", "code_reference", "dimension", "occupancy_label",
        "construction_type", "scope_indicator", "title_block", "stamp",
        "structural_element", "general_note", "reviewer_note",
        "ai_reviewer_response",
    }
    assert VALID_ANNOTATION_TYPES == expected


def test_valid_anchors():
    """VALID_ANCHORS contains expected directions."""
    assert VALID_ANCHORS == {"top-left", "top-right", "bottom-left", "bottom-right"}


def test_max_annotations_per_page():
    """MAX_ANNOTATIONS_PER_PAGE is 15."""
    assert MAX_ANNOTATIONS_PER_PAGE == 15
