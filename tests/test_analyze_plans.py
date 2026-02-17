"""Tests for tools/analyze_plans.py — Full AI plan set analysis.

All tests mock the vision API and downstream tools. No real API calls.
"""

import base64
import json
import pytest
from io import BytesIO
from unittest.mock import patch, AsyncMock, MagicMock

from pypdf import PdfWriter

from src.tools.analyze_plans import (
    analyze_plans,
    _assess_completeness,
    _get_strategic_recommendations,
    _build_report,
)
from src.tools.validate_plans import CheckResult
from src.vision.client import VisionResult


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_pdf(num_pages: int = 5) -> bytes:
    """Create a synthetic multi-page PDF."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=34 * 72, height=22 * 72)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_pdf_base64(num_pages: int = 5) -> str:
    """Create a base64-encoded synthetic PDF."""
    return base64.b64encode(_make_pdf(num_pages)).decode("ascii")


# ── analyze_plans (basic) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_plans_metadata_only():
    """Works without vision (no API key)."""
    with patch("src.vision.client.is_vision_available", return_value=False):
        result = await analyze_plans(_make_pdf(3), "test.pdf")

    assert "# Plan Set Analysis Report" in result
    assert "test.pdf" in result
    assert "EPR-006" in result  # File size check
    assert "Not available" in result  # Vision not available


@pytest.mark.asyncio
async def test_analyze_plans_base64_input():
    """Accepts base64-encoded PDF input."""
    b64 = _make_pdf_base64(2)
    with patch("src.vision.client.is_vision_available", return_value=False):
        result = await analyze_plans(b64, "encoded.pdf")

    assert "# Plan Set Analysis Report" in result
    assert "encoded.pdf" in result


@pytest.mark.asyncio
async def test_analyze_plans_empty_pdf():
    """Handles unreadable PDF gracefully."""
    result = await analyze_plans(b"not a pdf", "bad.pdf")
    assert "Cannot open PDF" in result


@pytest.mark.asyncio
async def test_analyze_plans_encrypted_pdf():
    """Stops at encryption check."""
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("password")
    buf = BytesIO()
    writer.write(buf)

    result = await analyze_plans(buf.getvalue(), "encrypted.pdf")
    assert "EPR-009" in result
    assert "encrypted" in result.lower() or "password" in result.lower()


@pytest.mark.asyncio
async def test_analyze_plans_with_vision():
    """Full analysis with mocked vision produces comprehensive report."""
    title_data = {
        "project_address": "456 Oak St",
        "sheet_number": "A1.0",
        "sheet_name": "FLOOR PLAN",
        "firm_name": "Test Architects",
        "has_professional_stamp": True,
        "has_signature": True,
        "has_2x2_blank": True,
    }
    cover_count = {"found_count": True, "stated_count": 5}
    blank_area = {"has_blank_area": True, "estimated_size": "8.5x11", "location": "upper-right"}
    hatch = {"has_dense_hatching": False, "severity": "none"}

    async def mock_analyze(b64, prompt, system_prompt=None, model=None):
        if "page count" in prompt.lower() or "sheet count" in prompt.lower():
            data = cover_count
        elif "blank" in prompt.lower() and "8.5" in prompt:
            data = blank_area
        elif "hatching" in prompt.lower():
            data = hatch
        else:
            data = title_data
        return VisionResult(True, json.dumps(data), None, 100, 50)

    with patch("src.vision.client.is_vision_available", return_value=True):
        with patch("src.vision.epr_checks.is_vision_available", return_value=True):
            with patch("src.vision.epr_checks.pdf_page_to_base64", return_value="fake"):
                with patch("src.vision.epr_checks.analyze_image", side_effect=mock_analyze):
                    result = await analyze_plans(
                        _make_pdf(5), "test.pdf",
                        project_description="Interior remodel",
                        permit_type="alterations",
                    )

    assert "# Plan Set Analysis Report" in result
    assert "AI Vision:** Enabled" in result
    assert "Sheet Index" in result
    assert "EPR-011" in result  # Cover page count
    assert "EPR-013" in result  # Address check


@pytest.mark.asyncio
async def test_analyze_plans_vision_failure_graceful():
    """Falls back to metadata-only when vision fails."""
    with patch("src.vision.client.is_vision_available", return_value=True):
        with patch(
            "src.vision.epr_checks.run_vision_epr_checks",
            AsyncMock(side_effect=Exception("Vision exploded")),
        ):
            result = await analyze_plans(_make_pdf(3), "test.pdf")

    assert "# Plan Set Analysis Report" in result
    # Should still have metadata checks
    assert "EPR-006" in result


# ── _assess_completeness ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_completeness_identifies_disciplines():
    """Identifies disciplines from sheet numbers."""
    extractions = [
        {"sheet_number": "A1.0", "sheet_name": "FLOOR PLAN"},
        {"sheet_number": "A2.0", "sheet_name": "ELEVATIONS"},
        {"sheet_number": "S1.0", "sheet_name": "FOUNDATION"},
    ]
    with patch(
        "src.tools.required_documents.required_documents",
        AsyncMock(return_value="## Documents\n- Form 8\n- Site Survey"),
    ):
        result = await _assess_completeness(
            extractions, "Interior remodel", "alterations"
        )

    assert result is not None
    assert "A1.0" in result
    assert "FLOOR PLAN" in result
    assert "Potentially Missing" in result
    # Should flag M, E, P as potentially missing
    assert "Mechanical" in result or "Electrical" in result or "Plumbing" in result


@pytest.mark.asyncio
async def test_completeness_no_extractions():
    """Returns None when no page extractions."""
    with patch(
        "src.tools.required_documents.required_documents",
        AsyncMock(return_value="## Documents"),
    ):
        result = await _assess_completeness([], "test", "alterations")
    assert result is None


# ── _get_strategic_recommendations ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_strategic_recommendations():
    """Pulls revision risk patterns."""
    mock_risk = (
        "## Common Correction Patterns\n"
        "- Missing fire sprinkler details\n"
        "- Incomplete egress calculations\n"
        "## Timeline Impact\n"
        "Typical delay: 2-4 weeks"
    )
    with patch(
        "src.tools.revision_risk.revision_risk",
        AsyncMock(return_value=mock_risk),
    ):
        result = await _get_strategic_recommendations("alterations")

    assert result is not None
    assert "Common Correction" in result
    assert "fire sprinkler" in result


@pytest.mark.asyncio
async def test_strategic_recommendations_error():
    """Returns None on revision_risk failure."""
    with patch(
        "src.tools.revision_risk.revision_risk",
        AsyncMock(side_effect=Exception("DB error")),
    ):
        result = await _get_strategic_recommendations("alterations")
    assert result is None


# ── _build_report ────────────────────────────────────────────────────────────


def test_build_report_metadata_only():
    """Report with metadata-only shows correct sections."""
    metadata = [
        CheckResult("EPR-006", "File size", "pass", "reject", "1.0 MB"),
        CheckResult("EPR-009", "No encryption", "pass", "reject", "No encryption"),
    ]
    report = _build_report(
        metadata, [], [], None, None,
        5, 1.0, "test.pdf", None,
    )
    assert "# Plan Set Analysis Report" in report
    assert "test.pdf" in report
    assert "Not available" in report
    assert "EPR-006" in report


def test_build_report_with_vision():
    """Report with vision results includes both sections."""
    metadata = [
        CheckResult("EPR-006", "File size", "pass", "reject", "1.0 MB"),
    ]
    vision = [
        CheckResult("EPR-013", "Address", "pass", "warning", "Address found"),
        CheckResult("EPR-014", "Sheet number", "fail", "warning", "Missing on 2 pages"),
    ]
    extractions = [
        {"page_number": 1, "sheet_number": "A1.0", "sheet_name": "FLOOR", "project_address": "123 Main"},
    ]
    report = _build_report(
        metadata, vision, extractions, None, None,
        5, 1.0, "test.pdf", "Interior remodel",
    )
    assert "AI Vision:** Enabled" in report
    assert "Sheet Index" in report
    assert "EPR-013" in report
    assert "EPR-014" in report
    assert "Interior remodel" in report


def test_build_report_with_completeness():
    """Report includes completeness assessment when provided."""
    metadata = [
        CheckResult("EPR-006", "File size", "pass", "reject", "1.0 MB"),
    ]
    completeness = "### Sheets Identified\n- **A1.0**: FLOOR PLAN"
    report = _build_report(
        metadata, [], [], completeness, None,
        5, 1.0, "test.pdf", "Test project",
    )
    assert "Completeness Assessment" in report
    assert "A1.0" in report


def test_build_report_with_strategic():
    """Report includes strategic recommendations when provided."""
    metadata = [
        CheckResult("EPR-006", "File size", "pass", "reject", "1.0 MB"),
    ]
    strategic = "- Missing fire sprinkler details"
    report = _build_report(
        metadata, [], [], None, strategic,
        5, 1.0, "test.pdf", None,
    )
    assert "Common Correction Patterns" in report
    assert "fire sprinkler" in report


def test_build_report_executive_summary_all_pass():
    """Executive summary reflects all-pass state."""
    metadata = [
        CheckResult("EPR-006", "File size", "pass", "reject", "1.0 MB"),
        CheckResult("EPR-009", "Encryption", "pass", "reject", "OK"),
    ]
    report = _build_report(
        metadata, [], [], None, None,
        5, 1.0, "test.pdf", None,
    )
    assert "ready for EPR submission" in report


def test_build_report_executive_summary_failures():
    """Executive summary highlights failures."""
    metadata = [
        CheckResult("EPR-006", "File size", "fail", "reject", "Too big"),
        CheckResult("EPR-009", "Encryption", "pass", "reject", "OK"),
    ]
    report = _build_report(
        metadata, [], [], None, None,
        5, 300.0, "test.pdf", None,
    )
    assert "1 critical issue" in report


# ── return_structured parameter ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_plans_return_structured_true():
    """analyze_plans with return_structured=True returns tuple (str, list[dict])."""
    title_data = {
        "project_address": "789 Pine St",
        "sheet_number": "A1.0",
        "sheet_name": "SITE PLAN",
        "firm_name": "Structured Architects",
        "has_professional_stamp": True,
        "has_signature": True,
        "has_2x2_blank": True,
    }
    cover_count = {"found_count": True, "stated_count": 3}
    blank_area = {"has_blank_area": True, "estimated_size": "8.5x11", "location": "upper-right"}
    hatch = {"has_dense_hatching": False, "severity": "none"}

    ann_data = {"annotations": [
        {"type": "code_reference", "label": "CBC 1020.1", "x": 30.0, "y": 50.0,
         "anchor": "top-right", "importance": "high"},
    ]}

    async def mock_analyze(b64, prompt, system_prompt=None, model=None, max_tokens=2048):
        if "page count" in prompt.lower() or "sheet count" in prompt.lower():
            data = cover_count
        elif "blank" in prompt.lower() and "8.5" in prompt:
            data = blank_area
        elif "hatching" in prompt.lower():
            data = hatch
        elif "annotate" in prompt.lower():
            data = ann_data
        else:
            data = title_data
        from src.vision.client import VisionResult
        import json
        return VisionResult(True, json.dumps(data), None, 100, 50)

    with patch("src.vision.client.is_vision_available", return_value=True):
        with patch("src.vision.epr_checks.is_vision_available", return_value=True):
            with patch("src.vision.epr_checks.pdf_page_to_base64", return_value="fake"):
                with patch("src.vision.epr_checks.analyze_image", side_effect=mock_analyze):
                    result = await analyze_plans(
                        _make_pdf(3), "structured.pdf",
                        return_structured=True,
                    )

    # Verify result is a tuple
    assert isinstance(result, tuple)
    assert len(result) == 3

    # First element is the markdown report
    report, extractions, annotations = result
    assert isinstance(report, str)
    assert "# Plan Set Analysis Report" in report
    assert "structured.pdf" in report

    # Second element is page_extractions list
    assert isinstance(extractions, list)
    assert len(extractions) > 0
    assert isinstance(extractions[0], dict)
    # Verify expected fields
    assert "page_number" in extractions[0]
    assert "sheet_number" in extractions[0]
    assert "project_address" in extractions[0]


@pytest.mark.asyncio
async def test_analyze_plans_return_structured_false_default():
    """analyze_plans defaults to return_structured=False, returns just string."""
    with patch("src.vision.client.is_vision_available", return_value=False):
        result = await analyze_plans(_make_pdf(2), "default.pdf")

    # Verify result is a string (not tuple)
    assert isinstance(result, str)
    assert not isinstance(result, tuple)
    assert "# Plan Set Analysis Report" in result
    assert "default.pdf" in result


@pytest.mark.asyncio
async def test_page_extractions_structure():
    """page_extractions have expected dict structure with all EPR fields."""
    title_data = {
        "project_address": "456 Oak St",
        "sheet_number": "S2.0",
        "sheet_name": "FOUNDATION PLAN",
        "firm_name": "Engineering Corp",
        "has_professional_stamp": True,
        "has_signature": False,  # Variation
        "has_2x2_blank": True,
        "architect_name": "Jane Smith PE",
        "date": "2024-02-15",
    }
    cover_count = {"found_count": True, "stated_count": 2}
    blank_area = {"has_blank_area": False, "estimated_size": None, "location": None}
    hatch = {"has_dense_hatching": True, "severity": "moderate"}

    async def mock_analyze(b64, prompt, system_prompt=None, model=None, max_tokens=2048):
        if "page count" in prompt.lower() or "sheet count" in prompt.lower():
            data = cover_count
        elif "blank" in prompt.lower() and "8.5" in prompt:
            data = blank_area
        elif "hatching" in prompt.lower():
            data = hatch
        elif "annotate" in prompt.lower():
            data = {"annotations": []}
        else:
            data = title_data
        from src.vision.client import VisionResult
        import json
        return VisionResult(True, json.dumps(data), None, 100, 50)

    with patch("src.vision.client.is_vision_available", return_value=True):
        with patch("src.vision.epr_checks.is_vision_available", return_value=True):
            with patch("src.vision.epr_checks.pdf_page_to_base64", return_value="fake"):
                with patch("src.vision.epr_checks.analyze_image", side_effect=mock_analyze):
                    _, extractions, _ = await analyze_plans(
                        _make_pdf(2), "structure.pdf",
                        return_structured=True,
                    )

    # Verify structure of extracted data
    assert len(extractions) > 0
    first = extractions[0]

    # Core fields
    assert "page_number" in first
    assert isinstance(first["page_number"], int)
    assert first["page_number"] >= 1

    assert "sheet_number" in first
    assert first["sheet_number"] == "S2.0"

    assert "sheet_name" in first
    assert first["sheet_name"] == "FOUNDATION PLAN"

    assert "project_address" in first
    assert first["project_address"] == "456 Oak St"

    # Professional stamp/signature fields
    assert "has_professional_stamp" in first
    assert first["has_professional_stamp"] is True

    assert "has_signature" in first
    assert first["has_signature"] is False  # Intentionally varied

    # Optional fields (may be present)
    if "firm_name" in first:
        assert first["firm_name"] == "Engineering Corp"
    if "architect_name" in first:
        assert first["architect_name"] == "Jane Smith PE"
    if "date" in first:
        assert first["date"] == "2024-02-15"
