"""Tool: analyze_plans — Full AI-powered analysis of PDF plan sets.

Combines metadata EPR validation, Claude Vision analysis, sheet
completeness assessment, and strategic recommendations into a
comprehensive pre-submission report.

Requires ``ANTHROPIC_API_KEY`` to be configured for vision features.
Falls back to metadata-only analysis if the API key is missing.
"""

import base64
import logging
from io import BytesIO

from pypdf import PdfReader

from src.tools.validate_plans import (
    CheckResult,
    _check_file_size,
    _check_encryption,
    _check_page_dimensions,
    _check_vector_vs_raster,
    _check_fonts,
    _check_bookmarks,
    _check_page_labels,
    _check_digital_signatures,
    _check_annotations,
    _check_filename,
    _check_back_check_page,
)
from src.tools.knowledge_base import format_sources

logger = logging.getLogger(__name__)


async def analyze_plans(
    pdf_bytes: bytes | str,
    filename: str = "plans.pdf",
    project_description: str | None = None,
    permit_type: str | None = None,
    return_structured: bool = False,
) -> str | tuple[str, list[dict]]:
    """Analyze a PDF plan set with AI vision and EPR compliance checking.

    Performs a comprehensive analysis combining:
    1. Metadata EPR checks (file size, encryption, dimensions, fonts, etc.)
    2. AI vision checks on sampled pages (title blocks, stamps, addresses)
    3. Sheet index extraction from cover page
    4. Completeness assessment against required documents (if project info provided)
    5. Strategic recommendations from revision risk patterns

    Args:
        pdf_bytes: Raw bytes of the uploaded PDF file (or base64-encoded string).
        filename: Original filename for convention check.
        project_description: Optional project description for completeness assessment.
        permit_type: Optional permit type (e.g., 'alterations', 'new_construction').
        return_structured: If True, returns (markdown, page_extractions) tuple.

    Returns:
        Comprehensive markdown analysis report (str).
        If return_structured=True, returns tuple of (markdown_str, page_extractions_list).
    """
    # Handle base64 input (for MCP transport)
    if isinstance(pdf_bytes, str):
        pdf_bytes = base64.b64decode(pdf_bytes)

    file_size_mb = len(pdf_bytes) / (1024 * 1024)
    report_lines: list[str] = []

    # ------------------------------------------------------------------
    # 1. Open PDF and run metadata checks
    # ------------------------------------------------------------------
    metadata_results: list[CheckResult] = []
    metadata_results.append(_check_file_size(pdf_bytes, False))

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception as e:
        metadata_results.append(CheckResult(
            epr_id="EPR-009",
            rule="PDF must be readable",
            status="fail",
            severity="reject",
            detail=f"Cannot open PDF: {e}",
        ))
        return _build_report(
            metadata_results, [], [], None, None,
            0, file_size_mb, filename, project_description,
        )

    enc_result = _check_encryption(reader)
    metadata_results.append(enc_result)
    if enc_result.status == "fail":
        return _build_report(
            metadata_results, [], [], None, None,
            0, file_size_mb, filename, project_description,
        )

    try:
        page_count = len(reader.pages)
    except Exception:
        page_count = 0

    metadata_results.extend([
        _check_page_dimensions(reader),
        _check_vector_vs_raster(reader),
        _check_fonts(reader),
        _check_bookmarks(reader),
        _check_page_labels(reader),
        _check_digital_signatures(reader),
        _check_annotations(reader),
        _check_filename(filename),
        _check_back_check_page(reader),
    ])

    # ------------------------------------------------------------------
    # 2. Vision EPR checks
    # ------------------------------------------------------------------
    vision_results: list[CheckResult] = []
    page_extractions: list[dict] = []

    try:
        from src.vision.client import is_vision_available

        if is_vision_available() and page_count > 0:
            from src.vision.epr_checks import run_vision_epr_checks

            logger.info("Running vision analysis on %s (%d pages)", filename, page_count)
            vision_results, page_extractions = await run_vision_epr_checks(
                pdf_bytes, page_count,
            )
            logger.info("Vision analysis complete: %d checks, %d page extractions",
                        len(vision_results), len(page_extractions))
        else:
            logger.info("Vision not available — metadata-only analysis for %s", filename)
    except Exception as e:
        logger.error("Vision analysis failed: %s", e)

    # ------------------------------------------------------------------
    # 3. Completeness assessment (if project info provided)
    # ------------------------------------------------------------------
    completeness_md = None
    if project_description and permit_type:
        try:
            completeness_md = await _assess_completeness(
                page_extractions, project_description, permit_type,
            )
        except Exception as e:
            logger.error("Completeness assessment failed: %s", e)

    # ------------------------------------------------------------------
    # 4. Strategic recommendations
    # ------------------------------------------------------------------
    strategic_md = None
    if permit_type:
        try:
            strategic_md = await _get_strategic_recommendations(permit_type)
        except Exception as e:
            logger.error("Strategic recommendations failed: %s", e)

    report = _build_report(
        metadata_results, vision_results, page_extractions,
        completeness_md, strategic_md,
        page_count, file_size_mb, filename, project_description,
    )

    if return_structured:
        return report, page_extractions
    return report


async def _assess_completeness(
    page_extractions: list[dict],
    project_description: str,
    permit_type: str,
) -> str | None:
    """Compare extracted sheets against required documents."""
    from src.tools.required_documents import required_documents

    # Determine basic parameters from permit type
    permit_forms = ["Form 3/8"]
    review_path = "in_house"
    if permit_type == "new_construction":
        permit_forms = ["Form 1/2"]

    try:
        docs_md = await required_documents(
            permit_forms=permit_forms,
            review_path=review_path,
        )
    except Exception:
        return None

    # Extract sheet types from vision data
    extracted_types = set()
    for pe in page_extractions:
        sheet_name = pe.get("sheet_name", "") or ""
        sheet_num = pe.get("sheet_number", "") or ""
        if sheet_name:
            extracted_types.add(sheet_name.upper())
        if sheet_num:
            # Extract discipline prefix
            prefix = ""
            for ch in sheet_num:
                if ch.isalpha():
                    prefix += ch
                else:
                    break
            if prefix:
                extracted_types.add(prefix)

    if not extracted_types:
        return None

    # Build a simple comparison report
    lines = []
    lines.append("### Sheets Identified\n")

    for pe in page_extractions:
        sn = pe.get("sheet_number", "?")
        name = pe.get("sheet_name", "unknown")
        lines.append(f"- **{sn}**: {name}")

    lines.append("")
    lines.append(f"*{len(page_extractions)} sheets identified from sampled pages.*")

    # Check for common missing disciplines
    disciplines_found = set()
    for pe in page_extractions:
        num = pe.get("sheet_number", "")
        if num:
            prefix = ""
            for ch in num:
                if ch.isalpha():
                    prefix += ch.upper()
                else:
                    break
            if prefix:
                disciplines_found.add(prefix)

    common_disciplines = {"A": "Architectural", "S": "Structural",
                          "M": "Mechanical", "E": "Electrical", "P": "Plumbing"}
    missing_disciplines = []
    for code, name in common_disciplines.items():
        if code not in disciplines_found:
            missing_disciplines.append(f"{name} ({code})")

    if missing_disciplines:
        lines.append("\n### Potentially Missing Disciplines\n")
        lines.append(
            "*Note: Only sampled pages were analyzed. "
            "Missing disciplines may exist on unsampled pages.*\n"
        )
        for d in missing_disciplines:
            lines.append(f"- {d}")

    return "\n".join(lines)


async def _get_strategic_recommendations(permit_type: str) -> str | None:
    """Pull revision risk patterns for strategic overlay."""
    from src.tools.revision_risk import revision_risk

    try:
        risk_md = await revision_risk(permit_type=permit_type)
        # Extract just the key risk factors (first section)
        lines = risk_md.split("\n")
        relevant = []
        in_section = False
        for line in lines:
            if "common" in line.lower() and "correction" in line.lower():
                in_section = True
                relevant.append(line)
                continue
            if in_section:
                if line.startswith("## ") or line.startswith("# "):
                    break
                relevant.append(line)
        return "\n".join(relevant) if relevant else None
    except Exception:
        return None


def _build_report(
    metadata_results: list[CheckResult],
    vision_results: list[CheckResult],
    page_extractions: list[dict],
    completeness_md: str | None,
    strategic_md: str | None,
    page_count: int,
    file_size_mb: float,
    filename: str,
    project_description: str | None,
) -> str:
    """Build the comprehensive analysis report."""
    all_results = metadata_results + vision_results
    lines: list[str] = []

    # Header
    lines.append("# Plan Set Analysis Report\n")
    lines.append(f"**File:** {filename}")
    lines.append(f"**Size:** {file_size_mb:.1f} MB")
    lines.append(f"**Pages:** {page_count}")
    if vision_results:
        lines.append("**AI Vision:** Enabled")
    else:
        lines.append("**AI Vision:** Not available (metadata analysis only)")
    if project_description:
        lines.append(f"**Project:** {project_description[:200]}")

    # ------------------------------------------------------------------
    # Executive Summary
    # ------------------------------------------------------------------
    lines.append("\n## Executive Summary\n")
    counts: dict[str, int] = {}
    for r in all_results:
        counts[r.status] = counts.get(r.status, 0) + 1

    fail_count = counts.get("fail", 0)
    warn_count = counts.get("warn", 0)
    pass_count = counts.get("pass", 0)

    if fail_count == 0 and warn_count == 0:
        lines.append(
            "All checks passed. This plan set appears ready for EPR submission."
        )
    elif fail_count == 0:
        lines.append(
            f"No critical issues found. {warn_count} warning(s) should be reviewed "
            "but may not block submission."
        )
    else:
        lines.append(
            f"**{fail_count} critical issue(s)** must be resolved before submission. "
            f"Additionally, {warn_count} warning(s) should be reviewed."
        )

    lines.append("\n| Status | Count |")
    lines.append("|--------|-------|")
    for status in ["pass", "fail", "warn", "skip", "info"]:
        if counts.get(status, 0) > 0:
            lines.append(f"| {status.upper()} | {counts[status]} |")

    # ------------------------------------------------------------------
    # Sheet Index (from vision extractions)
    # ------------------------------------------------------------------
    if page_extractions:
        lines.append("\n## Sheet Index\n")
        lines.append(
            "*Extracted from sampled pages via AI vision analysis:*\n"
        )
        lines.append("| Page | Sheet # | Sheet Name | Address |")
        lines.append("|------|---------|------------|---------|")
        for pe in page_extractions:
            pn = pe.get("page_number", "?")
            sn = pe.get("sheet_number", "—")
            name = pe.get("sheet_name", "—")
            addr = pe.get("project_address", "—")
            lines.append(f"| {pn} | {sn} | {name} | {addr} |")

    # ------------------------------------------------------------------
    # EPR Compliance
    # ------------------------------------------------------------------
    lines.append("\n## EPR Compliance — Metadata Checks\n")

    for status_group in ["fail", "warn", "pass", "skip"]:
        for r in metadata_results:
            if r.status != status_group:
                continue
            label = r.status.upper()
            lines.append(f"### {label} — {r.epr_id}: {r.rule}\n")
            lines.append(r.detail)
            if r.page_details:
                lines.append("")
                for pd in r.page_details:
                    lines.append(f"- {pd}")
            lines.append("")

    if vision_results:
        lines.append("## EPR Compliance — AI Vision Checks\n")
        lines.append(
            "*Checks run on sampled pages using Claude Vision:*\n"
        )
        for status_group in ["fail", "warn", "pass", "info", "skip"]:
            for r in vision_results:
                if r.status != status_group:
                    continue
                label = r.status.upper()
                lines.append(f"### {label} — {r.epr_id}: {r.rule}\n")
                lines.append(r.detail)
                if r.page_details:
                    lines.append("")
                    for pd in r.page_details:
                        lines.append(f"- {pd}")
                lines.append("")

    # ------------------------------------------------------------------
    # Completeness Assessment
    # ------------------------------------------------------------------
    if completeness_md:
        lines.append("\n## Completeness Assessment\n")
        lines.append(completeness_md)

    # ------------------------------------------------------------------
    # Strategic Recommendations
    # ------------------------------------------------------------------
    if strategic_md:
        lines.append("\n## Common Correction Patterns\n")
        lines.append(
            "*Based on historical revision data for similar permit types:*\n"
        )
        lines.append(strategic_md)

    # ------------------------------------------------------------------
    # Source citations
    # ------------------------------------------------------------------
    lines.append("")
    lines.append(format_sources(["epr_requirements"]))

    return "\n".join(lines)
