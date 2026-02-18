"""Tests for vision/epr_checks.py — Vision-based EPR compliance checks.

All tests mock the vision API and PDF rendering. No real API calls
or poppler dependency required.
"""

import json
import pytest
from io import BytesIO
from unittest.mock import patch, AsyncMock, MagicMock

from pypdf import PdfWriter

from src.vision.client import VisionResult, VisionUsageSummary
from src.vision.epr_checks import (
    run_vision_epr_checks,
    _parse_json_response,
    _select_sample_pages,
    _skip_all,
    _check_cover_page_count,
    _check_cover_blank_area,
    _assess_address_presence,
    _assess_sheet_numbers,
    _assess_sheet_names,
    _assess_blank_areas,
    _assess_consistency,
    _assess_stamps,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_pdf(num_pages: int = 5) -> bytes:
    """Create a synthetic multi-page PDF."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=34 * 72, height=22 * 72)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


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


# ── _parse_json_response ────────────────────────────────────────────────────


def test_parse_json_clean():
    """Parses clean JSON response."""
    result = _make_vision_result({"key": "value"})
    parsed = _parse_json_response(result)
    assert parsed == {"key": "value"}


def test_parse_json_with_fences():
    """Parses JSON wrapped in markdown code fences."""
    result = VisionResult(
        success=True,
        text='```json\n{"key": "value"}\n```',
        input_tokens=10,
        output_tokens=5,
    )
    parsed = _parse_json_response(result)
    assert parsed == {"key": "value"}


def test_parse_json_failed_result():
    """Returns None for failed API result."""
    result = _make_failed_result()
    parsed = _parse_json_response(result)
    assert parsed is None


def test_parse_json_invalid():
    """Returns None for invalid JSON."""
    result = VisionResult(
        success=True,
        text="This is not JSON at all",
        input_tokens=10,
        output_tokens=5,
    )
    parsed = _parse_json_response(result)
    assert parsed is None


# ── _select_sample_pages ─────────────────────────────────────────────────────


def test_sample_pages_single():
    """Single page: just page 0."""
    assert _select_sample_pages(1) == [0]


def test_sample_pages_two():
    """Two pages: both pages."""
    assert _select_sample_pages(2) == [0, 1]


def test_sample_pages_five():
    """Five pages: cover, first interior, middle, second-to-last."""
    pages = _select_sample_pages(5)
    assert 0 in pages  # Cover
    assert 1 in pages  # First interior
    assert 2 in pages  # Middle
    assert 3 in pages  # Second-to-last


def test_sample_pages_ten_plus():
    """Ten+ pages: includes 1/3 mark."""
    pages = _select_sample_pages(12)
    assert 0 in pages  # Cover
    assert 1 in pages  # First interior
    assert 4 in pages  # 1/3 mark (12//3)
    assert 6 in pages  # Middle (12//2)
    assert 10 in pages  # Second-to-last


def test_sample_pages_no_duplicates():
    """All page numbers are unique."""
    for total in [1, 2, 3, 5, 10, 20, 50]:
        pages = _select_sample_pages(total)
        assert len(pages) == len(set(pages))
        assert all(0 <= p < total for p in pages)


# ── _skip_all ────────────────────────────────────────────────────────────────


def test_skip_all_returns_11_results():
    """Returns skip result for all 11 vision checks."""
    results = _skip_all("test reason")
    assert len(results) == 11
    assert all(r.status == "skip" for r in results)
    assert all("test reason" in r.detail for r in results)
    epr_ids = {r.epr_id for r in results}
    assert "EPR-003" in epr_ids
    assert "EPR-022" in epr_ids


# ── _check_cover_page_count ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cover_page_count_match():
    """Pass when stated count matches actual."""
    mock_result = _make_vision_result({
        "found_count": True,
        "stated_count": 10,
        "sheet_index_entries": ["G0.0", "A1.0", "A2.0"],
    })
    with patch("src.vision.epr_checks.analyze_image", AsyncMock(return_value=mock_result)):
        check = await _check_cover_page_count("base64", 10, VisionUsageSummary())
    assert check.status == "pass"
    assert check.epr_id == "EPR-011"


@pytest.mark.asyncio
async def test_cover_page_count_mismatch():
    """Fail when stated count doesn't match actual."""
    mock_result = _make_vision_result({
        "found_count": True,
        "stated_count": 15,
    })
    with patch("src.vision.epr_checks.analyze_image", AsyncMock(return_value=mock_result)):
        check = await _check_cover_page_count("base64", 10, VisionUsageSummary())
    assert check.status == "fail"


@pytest.mark.asyncio
async def test_cover_page_count_not_found():
    """Warn when no count found on cover."""
    mock_result = _make_vision_result({
        "found_count": False,
    })
    with patch("src.vision.epr_checks.analyze_image", AsyncMock(return_value=mock_result)):
        check = await _check_cover_page_count("base64", 10, VisionUsageSummary())
    assert check.status == "warn"


# ── _check_cover_blank_area ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cover_blank_area_found():
    """Pass when blank area detected."""
    mock_result = _make_vision_result({
        "has_blank_area": True,
        "estimated_size": "approximately 8.5x11 inches",
        "location": "upper-right",
    })
    with patch("src.vision.epr_checks.analyze_image", AsyncMock(return_value=mock_result)):
        check = await _check_cover_blank_area("base64", VisionUsageSummary())
    assert check.status == "pass"
    assert check.epr_id == "EPR-012"


@pytest.mark.asyncio
async def test_cover_blank_area_not_found():
    """Fail when no blank area detected."""
    mock_result = _make_vision_result({
        "has_blank_area": False,
    })
    with patch("src.vision.epr_checks.analyze_image", AsyncMock(return_value=mock_result)):
        check = await _check_cover_blank_area("base64", VisionUsageSummary())
    assert check.status == "fail"


# ── _assess_address_presence ─────────────────────────────────────────────────


def test_address_all_found():
    """Pass when address found on all sampled pages."""
    data = [
        {"page_number": 1, "project_address": "123 Main St"},
        {"page_number": 3, "project_address": "123 Main St"},
        {"page_number": 5, "project_address": "123 Main St"},
    ]
    result = _assess_address_presence(data, [0, 2, 4], 10)
    assert result.status == "pass"
    assert result.epr_id == "EPR-013"


def test_address_some_missing():
    """Fail when address missing on some pages."""
    data = [
        {"page_number": 1, "project_address": "123 Main St"},
        {"page_number": 3, "project_address": None},
        {"page_number": 5, "project_address": "123 Main St"},
    ]
    result = _assess_address_presence(data, [0, 2, 4], 10)
    assert result.status == "fail"


def test_address_no_data():
    """Skip when no title block data available."""
    result = _assess_address_presence([], [0, 2, 4], 10)
    assert result.status == "skip"


# ── _assess_sheet_numbers ────────────────────────────────────────────────────


def test_sheet_numbers_all_found():
    """Pass when sheet numbers found on all pages."""
    data = [
        {"page_number": 1, "sheet_number": "G0.0"},
        {"page_number": 2, "sheet_number": "A1.0"},
    ]
    result = _assess_sheet_numbers(data, [0, 1], 5)
    assert result.status == "pass"
    assert result.epr_id == "EPR-014"


def test_sheet_numbers_missing():
    """Fail when sheet numbers missing."""
    data = [
        {"page_number": 1, "sheet_number": "G0.0"},
        {"page_number": 2, "sheet_number": None},
    ]
    result = _assess_sheet_numbers(data, [0, 1], 5)
    assert result.status == "fail"


# ── _assess_sheet_names ──────────────────────────────────────────────────────


def test_sheet_names_all_found():
    """Pass when sheet names found on all pages."""
    data = [
        {"page_number": 1, "sheet_name": "COVER SHEET"},
        {"page_number": 2, "sheet_name": "FLOOR PLAN"},
    ]
    result = _assess_sheet_names(data, [0, 1], 5)
    assert result.status == "pass"
    assert result.epr_id == "EPR-015"


def test_sheet_names_missing():
    """Fail when sheet names missing."""
    data = [
        {"page_number": 1, "sheet_name": "COVER"},
        {"page_number": 2, "sheet_name": None},
    ]
    result = _assess_sheet_names(data, [0, 1], 5)
    assert result.status == "fail"


# ── _assess_blank_areas ──────────────────────────────────────────────────────


def test_blank_areas_all_found():
    """Pass when blank areas found on all pages."""
    data = [
        {"page_number": 1, "has_2x2_blank": True},
        {"page_number": 2, "has_2x2_blank": True},
    ]
    result = _assess_blank_areas(data, [0, 1], 5)
    assert result.status == "pass"
    assert result.epr_id == "EPR-016"


def test_blank_areas_missing():
    """Warn when blank areas missing."""
    data = [
        {"page_number": 1, "has_2x2_blank": True},
        {"page_number": 2, "has_2x2_blank": False},
    ]
    result = _assess_blank_areas(data, [0, 1], 5)
    assert result.status == "warn"


# ── _assess_consistency ──────────────────────────────────────────────────────


def test_consistency_pass():
    """Pass when address and firm consistent."""
    data = [
        {"page_number": 1, "project_address": "123 Main", "firm_name": "Acme", "sheet_number": "A1.0"},
        {"page_number": 2, "project_address": "123 Main", "firm_name": "Acme", "sheet_number": "A2.0"},
    ]
    result = _assess_consistency(data)
    assert result.status == "pass"
    assert result.epr_id == "EPR-017"


def test_consistency_fail_different_addresses():
    """Fail when addresses differ across pages."""
    data = [
        {"page_number": 1, "project_address": "123 Main", "firm_name": "Acme"},
        {"page_number": 2, "project_address": "456 Oak", "firm_name": "Acme"},
    ]
    result = _assess_consistency(data)
    assert result.status == "fail"


def test_consistency_too_few_pages():
    """Skip when only one page sampled."""
    data = [{"page_number": 1, "project_address": "123 Main", "firm_name": "Acme"}]
    result = _assess_consistency(data)
    assert result.status == "skip"


# ── _assess_stamps ───────────────────────────────────────────────────────────


def test_stamps_all_found():
    """Pass when stamps found on all pages."""
    data = [
        {"page_number": 1, "has_professional_stamp": True, "has_signature": True},
        {"page_number": 2, "has_professional_stamp": True, "has_signature": False},
    ]
    result = _assess_stamps(data, [0, 1], 5)
    assert result.status == "pass"
    assert result.epr_id == "EPR-018"


def test_stamps_missing():
    """Warn when stamps missing on some pages."""
    data = [
        {"page_number": 1, "has_professional_stamp": True, "has_signature": True},
        {"page_number": 2, "has_professional_stamp": False, "has_signature": False},
    ]
    result = _assess_stamps(data, [0, 1], 5)
    assert result.status == "warn"


# ── run_vision_epr_checks (integration) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_run_vision_no_api_key():
    """All checks skip when API key is missing."""
    with patch("src.vision.epr_checks.is_vision_available", return_value=False):
        results, extractions, annotations, usage = await run_vision_epr_checks(_make_pdf(5), 5)
    assert len(results) == 11
    assert all(r.status == "skip" for r in results)
    assert extractions == []
    assert annotations == []
    assert usage.total_calls == 0


@pytest.mark.asyncio
async def test_run_vision_render_failure():
    """All checks skip when PDF rendering fails."""
    with patch("src.vision.epr_checks.is_vision_available", return_value=True):
        with patch(
            "src.vision.epr_checks.pdf_page_to_base64",
            side_effect=Exception("poppler not installed"),
        ):
            results, extractions, annotations, usage = await run_vision_epr_checks(_make_pdf(5), 5)
    assert len(results) == 11
    assert all(r.status == "skip" for r in results)
    assert usage.total_calls == 0


@pytest.mark.asyncio
async def test_run_vision_full_pipeline():
    """Full pipeline with mocked vision produces results for all 11 checks."""
    cover_data = {
        "found_count": True,
        "stated_count": 5,
    }
    blank_data = {
        "has_blank_area": True,
        "estimated_size": "8.5x11",
        "location": "upper-right",
    }
    title_data = {
        "project_address": "123 Main St",
        "sheet_number": "A1.0",
        "sheet_name": "FLOOR PLAN",
        "firm_name": "Test Firm",
        "has_professional_stamp": True,
        "has_signature": True,
        "has_2x2_blank": True,
    }
    hatch_data = {
        "has_dense_hatching": False,
        "severity": "none",
    }

    annotation_data = {
        "annotations": [
            {"type": "code_reference", "label": "CBC 1020.1", "x": 30.0, "y": 50.0,
             "anchor": "top-right", "importance": "high"},
        ]
    }

    call_count = 0

    async def mock_analyze(b64, prompt, system_prompt=None, model=None, max_tokens=2048):
        nonlocal call_count
        call_count += 1
        # Return appropriate data based on prompt content
        if "sheet count" in prompt.lower() or "page count" in prompt.lower():
            data = cover_data
        elif "blank" in prompt.lower() and "8.5" in prompt:
            data = blank_data
        elif "hatching" in prompt.lower():
            data = hatch_data
        elif "annotate" in prompt.lower():
            data = annotation_data
        else:
            data = title_data
        return VisionResult(
            success=True,
            text=json.dumps(data),
            input_tokens=100,
            output_tokens=50,
        )

    with patch("src.vision.epr_checks.is_vision_available", return_value=True):
        with patch("src.vision.epr_checks.pdf_page_to_base64", return_value="fake_base64"):
            with patch("src.vision.epr_checks.analyze_image", side_effect=mock_analyze):
                results, extractions, annotations, usage = await run_vision_epr_checks(_make_pdf(5), 5)

    assert len(results) == 11
    epr_ids = {r.epr_id for r in results}
    expected_ids = {
        "EPR-003", "EPR-004", "EPR-011", "EPR-012", "EPR-013",
        "EPR-014", "EPR-015", "EPR-016", "EPR-017", "EPR-018", "EPR-022",
    }
    assert epr_ids == expected_ids
    assert len(extractions) > 0
    assert len(annotations) > 0
    assert annotations[0]["type"] == "code_reference"
    assert "page_number" in annotations[0]

    # Usage tracking assertions
    assert usage.total_calls > 0
    assert usage.total_input_tokens > 0
    assert usage.total_output_tokens > 0
    assert usage.successful_calls == usage.total_calls
    assert usage.failed_calls == 0
    assert usage.estimated_cost_usd > 0


@pytest.mark.asyncio
async def test_run_vision_analyze_all_pages():
    """analyze_all_pages=True processes every page, not just the sample."""
    title_data = {
        "project_address": "100 Main",
        "sheet_number": "A1",
        "sheet_name": "PLAN",
        "firm_name": "Firm",
        "has_professional_stamp": True,
        "has_signature": True,
        "has_2x2_blank": True,
    }
    cover_data = {"found_count": True, "stated_count": 5}
    blank_data = {"has_blank_area": True, "estimated_size": "8.5x11", "location": "upper-right"}
    hatch_data = {"has_dense_hatching": False, "severity": "none"}

    async def mock_analyze(b64, prompt, system_prompt=None, model=None, max_tokens=2048):
        if "sheet count" in prompt.lower() or "page count" in prompt.lower():
            data = cover_data
        elif "blank" in prompt.lower() and "8.5" in prompt:
            data = blank_data
        elif "hatching" in prompt.lower():
            data = hatch_data
        elif "annotate" in prompt.lower():
            data = {"annotations": []}
        else:
            data = title_data
        return VisionResult(success=True, text=json.dumps(data), input_tokens=100, output_tokens=50)

    with patch("src.vision.epr_checks.is_vision_available", return_value=True):
        with patch("src.vision.epr_checks.pdf_page_to_base64", return_value="fake"):
            with patch("src.vision.epr_checks.analyze_image", side_effect=mock_analyze):
                _, extractions, _, usage = await run_vision_epr_checks(
                    _make_pdf(5), 5, analyze_all_pages=True,
                )

    # All 5 pages should have extractions (not just the 4 sampled)
    assert len(extractions) == 5


@pytest.mark.asyncio
async def test_run_vision_sample_pages_default():
    """Default analyze_all_pages=False uses sample strategy for 10-page PDF."""
    title_data = {
        "project_address": "200 Oak",
        "sheet_number": "S1",
        "sheet_name": "STRUCTURAL",
        "firm_name": "Firm",
        "has_professional_stamp": True,
        "has_signature": True,
        "has_2x2_blank": True,
    }
    cover_data = {"found_count": True, "stated_count": 10}
    blank_data = {"has_blank_area": True, "estimated_size": "8.5x11", "location": "upper-right"}
    hatch_data = {"has_dense_hatching": False, "severity": "none"}

    async def mock_analyze(b64, prompt, system_prompt=None, model=None, max_tokens=2048):
        if "sheet count" in prompt.lower() or "page count" in prompt.lower():
            data = cover_data
        elif "blank" in prompt.lower() and "8.5" in prompt:
            data = blank_data
        elif "hatching" in prompt.lower():
            data = hatch_data
        elif "annotate" in prompt.lower():
            data = {"annotations": []}
        else:
            data = title_data
        return VisionResult(success=True, text=json.dumps(data), input_tokens=100, output_tokens=50)

    with patch("src.vision.epr_checks.is_vision_available", return_value=True):
        with patch("src.vision.epr_checks.pdf_page_to_base64", return_value="fake"):
            with patch("src.vision.epr_checks.analyze_image", side_effect=mock_analyze):
                _, extractions, _, _ = await run_vision_epr_checks(
                    _make_pdf(10), 10, analyze_all_pages=False,
                )

    # Sample of 10 pages = 5 pages (cover, 1, 3, 5, 8)
    assert len(extractions) < 10
    assert len(extractions) == 5
