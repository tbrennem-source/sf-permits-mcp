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


# ── SF Zoning Knowledge ─────────────────────────────────────────────────────

SF_ZONING_INFO: dict[str, dict] = {
    "RH-1": {"name": "Residential, House — One Family", "max_units": 1,
             "description": "Single-family residential"},
    "RH-1(D)": {"name": "Residential, House — One Family (Detached)",
                 "max_units": 1, "description": "Detached single-family"},
    "RH-1(S)": {"name": "Residential, House — One Family (Secondary Unit)",
                 "max_units": 1, "description": "Single-family with ADU potential"},
    "RH-2": {"name": "Residential, House — Two Family", "max_units": 2,
             "description": "Two-family residential (duplex)"},
    "RH-3": {"name": "Residential, House — Three Family", "max_units": 3,
             "description": "Three-family residential (triplex)"},
    "RM-1": {"name": "Residential, Mixed — Low Density",
             "description": "Low-density mixed residential (~1 unit per 800 sq ft lot area)"},
    "RM-2": {"name": "Residential, Mixed — Moderate Density",
             "description": "Moderate-density mixed residential (~1 unit per 600 sq ft)"},
    "RM-3": {"name": "Residential, Mixed — Medium Density",
             "description": "Medium-density mixed residential"},
    "RM-4": {"name": "Residential, Mixed — High Density",
             "description": "High-density mixed residential"},
    "RC-3": {"name": "Residential-Commercial — Medium Density",
             "description": "Mixed-use residential and commercial"},
    "RC-4": {"name": "Residential-Commercial — High Density",
             "description": "High-density mixed-use"},
    "NC-1": {"name": "Neighborhood Commercial — Small Scale",
             "description": "Small-scale neighborhood retail, residential above"},
    "NC-2": {"name": "Neighborhood Commercial — Moderate Scale",
             "description": "Moderate-scale neighborhood commercial"},
    "NC-3": {"name": "Neighborhood Commercial — Moderate Scale",
             "description": "Moderate-scale neighborhood commercial, broader uses"},
    "C-2": {"name": "Community Business",
            "description": "General commercial, retail, office, residential"},
    "C-3-O": {"name": "Downtown Office",
              "description": "Downtown office district"},
    "C-3-R": {"name": "Downtown Retail",
              "description": "Downtown retail district"},
    "P": {"name": "Public",
          "description": "Public use district"},
    "M-1": {"name": "Light Industrial",
            "description": "Light industrial, limited residential"},
    "M-2": {"name": "Heavy Industrial",
            "description": "Heavy industrial, no residential"},
    "PDR-1-G": {"name": "Production, Distribution, Repair — General",
                "description": "PDR uses, limited office"},
}

SF_HEIGHT_INFO: dict[str, str] = {
    "40-X": "40 ft max height",
    "45-X": "45 ft max height",
    "50-X": "50 ft max height",
    "55-X": "55 ft max height",
    "65-A": "65 ft max height (bulk controls apply)",
    "65-B": "65 ft max height (stricter bulk controls)",
    "80-A": "80 ft max height (bulk controls)",
    "85-X": "85 ft max height",
    "105-X": "105 ft max height",
    "120-X": "120 ft max height",
    "130-E": "130 ft max height",
    "160-F": "160 ft max height (FAR bonus)",
    "200-S": "200 ft max height (setback required)",
    "OS": "Open space — height varies",
}


def _escape_soql(value: str) -> str:
    """Escape a string for SoQL WHERE clauses."""
    return value.replace("'", "''").replace("\\", "\\\\")


def _get_consensus_address(page_extractions: list[dict]) -> str | None:
    """Return the most common non-empty address from page extractions."""
    from collections import Counter

    addresses = [
        pe.get("project_address", "").strip()
        for pe in page_extractions
        if pe.get("project_address", "").strip()
    ]
    if not addresses:
        return None
    return Counter(addresses).most_common(1)[0][0]


async def _lookup_zoning(address: str) -> dict | None:
    """Query SODA for zoning data at *address*.

    Queries the Assessor Property Tax Rolls (``wv5m-vpq2``) for zoning
    code, lot dimensions, and existing building info, plus the Development
    Pipeline (``6jgi-cpb4``) for the height/bulk district.

    Returns a dict with zoning fields or *None* on failure/no match.
    """
    from src.soda_client import SODAClient

    if not address or len(address.strip()) < 5:
        return None

    client = SODAClient()
    result: dict = {}

    try:
        addr_upper = _escape_soql(address.upper().strip())

        # Primary: Assessor Property Tax Rolls
        tax_records = await client.query(
            endpoint_id="wv5m-vpq2",
            where=f"upper(property_location) LIKE '%{addr_upper}%'",
            order="closed_roll_year DESC",
            limit=1,
        )
        if tax_records:
            rec = tax_records[0]
            result["zoning_code"] = rec.get("zoning_code")
            result["lot_area"] = rec.get("lot_area")
            result["lot_frontage"] = rec.get("lot_frontage")
            result["lot_depth"] = rec.get("lot_depth")
            result["number_of_stories"] = rec.get("number_of_stories")
            result["use_definition"] = rec.get("use_definition")
            result["construction_type"] = rec.get("construction_type")
            result["year_built"] = rec.get("year_property_built")
            result["property_location"] = rec.get("property_location")

        # Secondary: Development Pipeline (height district)
        try:
            pipeline = await client.query(
                endpoint_id="6jgi-cpb4",
                where=f"upper(nameaddr) LIKE '%{addr_upper}%'",
                limit=1,
            )
            if pipeline:
                prec = pipeline[0]
                result["height_district"] = prec.get("height_district")
                result["zoning_district"] = prec.get("zoning_district")
                if not result.get("zoning_code") and prec.get("zoning_district"):
                    result["zoning_code"] = prec["zoning_district"]
        except Exception as e:
            logger.debug("Pipeline zoning lookup failed: %s", e)

    except Exception as e:
        logger.warning("Zoning lookup failed for '%s': %s", address, e)
        return None
    finally:
        await client.close()

    return result if result else None


async def analyze_plans(
    pdf_bytes: bytes | str,
    filename: str = "plans.pdf",
    project_description: str | None = None,
    permit_type: str | None = None,
    return_structured: bool = False,
    analyze_all_pages: bool = False,
    analysis_mode: str = "sample",
) -> str | tuple[str, list[dict], list[dict], "VisionUsageSummary"]:
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
        return_structured: If True, returns (markdown, page_extractions, page_annotations, vision_usage) tuple.

    Returns:
        Comprehensive markdown analysis report (str).
        If return_structured=True, returns tuple of
        (markdown_str, page_extractions_list, page_annotations_list, vision_usage).
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
    from src.vision.client import VisionUsageSummary

    vision_results: list[CheckResult] = []
    page_extractions: list[dict] = []
    page_annotations: list[dict] = []
    vision_usage = VisionUsageSummary()

    try:
        from src.vision.client import is_vision_available

        if is_vision_available() and page_count > 0:
            from src.vision.epr_checks import run_vision_epr_checks

            logger.info("Running vision analysis on %s (%d pages)", filename, page_count)
            vision_results, page_extractions, page_annotations, vision_usage = (
                await run_vision_epr_checks(
                    pdf_bytes, page_count,
                    analyze_all_pages=analyze_all_pages,
                    analysis_mode=analysis_mode,
                )
            )
            logger.info(
                "Vision analysis complete: %d checks, %d page extractions, %d annotations",
                len(vision_results), len(page_extractions), len(page_annotations),
            )
        else:
            logger.info("Vision not available — metadata-only analysis for %s", filename)
    except Exception as e:
        logger.error("Vision analysis failed: %s", e)

    # ------------------------------------------------------------------
    # 2b. Extract native PDF annotations (no API calls)
    # ------------------------------------------------------------------
    native_annotations: list[dict] = []
    try:
        from src.tools.validate_plans import extract_native_pdf_annotations

        native_annotations = extract_native_pdf_annotations(reader)
        if native_annotations:
            logger.info(
                "Extracted %d native PDF annotation(s)", len(native_annotations)
            )
    except Exception as e:
        logger.warning("Native PDF annotation extraction failed: %s", e)

    # ------------------------------------------------------------------
    # 2c. Zoning cross-check (requires address from vision extractions)
    # ------------------------------------------------------------------
    zoning_data: dict | None = None
    if page_extractions:
        try:
            consensus_addr = _get_consensus_address(page_extractions)
            if consensus_addr:
                zoning_data = await _lookup_zoning(consensus_addr)
                if zoning_data:
                    logger.info("Zoning lookup succeeded for '%s'", consensus_addr)
        except Exception as e:
            logger.warning("Zoning cross-check failed: %s", e)

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
        vision_usage=vision_usage,
        native_annotations=native_annotations,
        zoning_data=zoning_data,
    )

    if return_structured:
        return report, page_extractions, page_annotations, vision_usage
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
    vision_usage: "VisionUsageSummary | None" = None,
    native_annotations: list[dict] | None = None,
    zoning_data: dict | None = None,
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
    if vision_usage and vision_usage.total_calls > 0:
        duration_s = vision_usage.total_duration_ms // 1000
        lines.append(
            f"**API Usage:** {vision_usage.total_calls} calls · "
            f"{vision_usage.total_tokens:,} tokens · "
            f"~{duration_s}s vision time"
        )
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
    # Plan Checker Comments (native PDF annotations)
    # ------------------------------------------------------------------
    if native_annotations:
        lines.append("\n## Plan Checker Comments\n")
        lines.append(
            "*Extracted from native PDF annotations (plan checker markup):*\n"
        )
        # Group by page number
        by_page: dict[int, list[dict]] = {}
        for ann in native_annotations:
            pn = ann.get("page_number", 0)
            by_page.setdefault(pn, []).append(ann)

        for pn in sorted(by_page.keys()):
            page_anns = by_page[pn]
            lines.append(f"### Page {pn + 1}\n")
            for ann in page_anns:
                content = ann.get("content", "").strip()
                author = ann.get("author")
                subtype = ann.get("subtype", "").replace("/", "")
                prefix = f"**{author}**" if author else f"*{subtype}*"
                # Truncate very long comments for readability
                if len(content) > 500:
                    content = content[:497] + "..."
                lines.append(f"- {prefix}: {content}")
            lines.append("")

        lines.append(
            f"*{len(native_annotations)} annotation(s) found across "
            f"{len(by_page)} page(s).*\n"
        )

    # ------------------------------------------------------------------
    # Zoning Context
    # ------------------------------------------------------------------
    if zoning_data:
        lines.append("\n## Zoning Context\n")
        lines.append(
            "*Property zoning data from SF Assessor records:*\n"
        )

        zc = zoning_data.get("zoning_code", "")
        hd = zoning_data.get("height_district", "")

        if zc:
            zoning_info = SF_ZONING_INFO.get(zc.upper(), {})
            zname = zoning_info.get("name", zc)
            zdesc = zoning_info.get("description", "")
            lines.append(f"**Zoning District:** {zc} — {zname}")
            if zdesc:
                lines.append(f"> {zdesc}")
            lines.append("")

        if hd:
            height_desc = SF_HEIGHT_INFO.get(hd.upper(), hd)
            lines.append(f"**Height District:** {hd} — {height_desc}")
            lines.append("")

        # Lot dimensions
        lot_parts = []
        if zoning_data.get("lot_area"):
            lot_parts.append(f"Area: {zoning_data['lot_area']:,} sq ft")
        if zoning_data.get("lot_frontage"):
            lot_parts.append(f"Frontage: {zoning_data['lot_frontage']} ft")
        if zoning_data.get("lot_depth"):
            lot_parts.append(f"Depth: {zoning_data['lot_depth']} ft")
        if lot_parts:
            lines.append(f"**Lot:** {' · '.join(lot_parts)}")

        # Existing building info
        building_parts = []
        if zoning_data.get("number_of_stories"):
            building_parts.append(
                f"{zoning_data['number_of_stories']} stories"
            )
        if zoning_data.get("use_definition"):
            building_parts.append(zoning_data["use_definition"])
        if zoning_data.get("construction_type"):
            building_parts.append(
                f"Type {zoning_data['construction_type']} construction"
            )
        if zoning_data.get("year_built"):
            building_parts.append(f"Built {zoning_data['year_built']}")
        if building_parts:
            lines.append(
                f"**Existing Building:** {' · '.join(building_parts)}"
            )

        lines.append("")

        # Cross-reference flags
        flags = []
        if page_extractions:
            sheet_names = [
                pe.get("sheet_name", "").lower()
                for pe in page_extractions
            ]
            all_names = " ".join(sheet_names)
            if "addition" in all_names or "extension" in all_names:
                if hd:
                    flags.append(
                        f"Plans include addition/extension sheets — "
                        f"verify proposed height against {hd} district limits"
                    )
            if "adu" in all_names or "accessory" in all_names:
                if zc:
                    flags.append(
                        f"ADU sheets detected — verify ADU eligibility "
                        f"in {zc} zoning district"
                    )

        if flags:
            lines.append("**⚠ Cross-Reference Flags:**\n")
            for flag in flags:
                lines.append(f"- {flag}")
            lines.append("")

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
