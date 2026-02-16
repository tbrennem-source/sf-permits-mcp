"""Tool: validate_plans — Validate PDF plan sets against SF DBI EPR requirements.

Performs metadata analysis using pypdf and optional AI vision checks via
the Claude API. Metadata checks cover:
- File size, encryption, page dimensions
- Bookmarks, page labels, fonts
- Digital signatures, annotations, filename convention
- Vector vs raster heuristic, back check page detection

When ``enable_vision=True`` and an ``ANTHROPIC_API_KEY`` is configured,
additional visual checks are run on sampled pages to verify title blocks,
addresses, stamps, blank areas, and hatching patterns.

Returns a markdown report with PASS/FAIL/WARN/SKIP per check.
"""

import base64
import logging
import re
from dataclasses import dataclass, field
from io import BytesIO

logger = logging.getLogger(__name__)

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, NameObject

from src.tools.knowledge_base import format_sources


# Points per inch (PDF standard)
PTS_PER_INCH = 72.0

# Sheet size thresholds (inches)
MIN_PLAN_WIDTH = 22.0   # Arch D minimum
MIN_PLAN_HEIGHT = 34.0
SMALL_SHEET_WIDTH = 11.0   # Cover/supplement sheets
SMALL_SHEET_HEIGHT = 17.0  # 11x17 tabloid

# File size limits (bytes)
MAX_FILE_SIZE = 250 * 1024 * 1024       # 250 MB
MAX_FILE_SIZE_ADDENDUM = 350 * 1024 * 1024  # 350 MB for site permit addenda
WARN_FILE_SIZE = 50 * 1024 * 1024       # 50 MB warning threshold

# Filename convention pattern: [prefix]-[type]-[revision] [address]
FILENAME_PATTERN = re.compile(
    r"^[\w]+-[\w]+-[\w]+\s+.+\.pdf$", re.IGNORECASE
)


@dataclass
class CheckResult:
    """Result of a single EPR check."""
    epr_id: str
    rule: str
    status: str          # pass | fail | warn | skip | info
    severity: str        # reject | warning | recommendation
    detail: str
    page_details: list[str] = field(default_factory=list)


def _check_file_size(pdf_bytes: bytes, is_addendum: bool) -> CheckResult:
    """EPR-006: File size under 250MB (350MB for site permit addenda)."""
    size_mb = len(pdf_bytes) / (1024 * 1024)
    limit = MAX_FILE_SIZE_ADDENDUM if is_addendum else MAX_FILE_SIZE
    limit_mb = limit / (1024 * 1024)

    if len(pdf_bytes) > limit:
        return CheckResult(
            epr_id="EPR-006",
            rule="File size limit",
            status="fail",
            severity="reject",
            detail=f"File is {size_mb:.1f} MB — exceeds {limit_mb:.0f} MB limit.",
        )
    elif len(pdf_bytes) > WARN_FILE_SIZE:
        return CheckResult(
            epr_id="EPR-006",
            rule="File size limit",
            status="warn",
            severity="warning",
            detail=f"File is {size_mb:.1f} MB — under {limit_mb:.0f} MB limit but large. Consider optimizing.",
        )
    else:
        return CheckResult(
            epr_id="EPR-006",
            rule="File size limit",
            status="pass",
            severity="reject",
            detail=f"File is {size_mb:.1f} MB (limit: {limit_mb:.0f} MB).",
        )


def _check_encryption(reader: PdfReader) -> CheckResult:
    """EPR-009: PDF must be unlocked, no encryption or passwords."""
    if reader.is_encrypted:
        return CheckResult(
            epr_id="EPR-009",
            rule="PDF must be unlocked",
            status="fail",
            severity="reject",
            detail="PDF is encrypted or password-protected. DBI requires unlocked PDFs for markup.",
        )
    return CheckResult(
        epr_id="EPR-009",
        rule="PDF must be unlocked",
        status="pass",
        severity="reject",
        detail="No encryption or password protection detected.",
    )


def _check_page_dimensions(reader: PdfReader) -> CheckResult:
    """EPR-005: Minimum sheet size 22" x 34" (Arch D)."""
    page_details = []
    undersized_pages = []
    total = len(reader.pages)

    for i, page in enumerate(reader.pages):
        try:
            box = page.mediabox
            width_in = float(box.width) / PTS_PER_INCH
            height_in = float(box.height) / PTS_PER_INCH
            # Normalize to landscape (wider dimension first)
            w, h = max(width_in, height_in), min(width_in, height_in)

            page_details.append(f"Page {i + 1}: {w:.1f}\" x {h:.1f}\"")

            # Allow small sheets for first page (cover) and last page (back check)
            is_edge_page = (i == 0 or i == total - 1)
            is_small_sheet = (w <= SMALL_SHEET_WIDTH + 0.5 and h <= SMALL_SHEET_HEIGHT + 0.5)

            if is_edge_page and is_small_sheet:
                continue  # Cover or back check page — exempt

            if w < MIN_PLAN_HEIGHT - 0.5 or h < MIN_PLAN_WIDTH - 0.5:
                undersized_pages.append(i + 1)
        except Exception:
            page_details.append(f"Page {i + 1}: Unable to read dimensions")

    if undersized_pages:
        pages_str = ", ".join(str(p) for p in undersized_pages[:10])
        suffix = f" (+{len(undersized_pages) - 10} more)" if len(undersized_pages) > 10 else ""
        return CheckResult(
            epr_id="EPR-005",
            rule=f"Minimum sheet size {MIN_PLAN_WIDTH}\" x {MIN_PLAN_HEIGHT}\"",
            status="fail",
            severity="reject",
            detail=f"{len(undersized_pages)} of {total} pages are undersized. Pages: {pages_str}{suffix}",
            page_details=page_details[:10],
        )

    return CheckResult(
        epr_id="EPR-005",
        rule=f"Minimum sheet size {MIN_PLAN_WIDTH}\" x {MIN_PLAN_HEIGHT}\"",
        status="pass",
        severity="reject",
        detail=f"All {total} pages meet minimum size requirements.",
        page_details=page_details[:5],
    )


def _check_bookmarks(reader: PdfReader) -> CheckResult:
    """EPR-007: Bookmarks with page number and sheet name."""
    try:
        outline = reader.outline
        if not outline:
            return CheckResult(
                epr_id="EPR-007",
                rule="Bookmarks for navigation",
                status="warn",
                severity="recommendation",
                detail="No bookmarks found. DBI recommends bookmarks for each sheet (e.g., 'A0.0 - COVER SHEET').",
            )

        # Count bookmarks (flatten nested structure)
        def count_bookmarks(items):
            count = 0
            for item in items:
                if isinstance(item, list):
                    count += count_bookmarks(item)
                else:
                    count += 1
            return count

        bm_count = count_bookmarks(outline)
        page_count = len(reader.pages)

        if bm_count < page_count * 0.5:
            return CheckResult(
                epr_id="EPR-007",
                rule="Bookmarks for navigation",
                status="warn",
                severity="recommendation",
                detail=f"Found {bm_count} bookmarks for {page_count} pages. Consider adding bookmarks for all sheets.",
            )

        return CheckResult(
            epr_id="EPR-007",
            rule="Bookmarks for navigation",
            status="pass",
            severity="recommendation",
            detail=f"Found {bm_count} bookmarks for {page_count} pages.",
        )
    except Exception:
        return CheckResult(
            epr_id="EPR-007",
            rule="Bookmarks for navigation",
            status="skip",
            severity="recommendation",
            detail="Unable to read bookmark structure.",
        )


def _check_page_labels(reader: PdfReader) -> CheckResult:
    """EPR-008: Page labels matching sheet names in Thumbnails tab."""
    try:
        labels = reader.page_labels
        if not labels:
            return CheckResult(
                epr_id="EPR-008",
                rule="Page labels for thumbnails",
                status="warn",
                severity="recommendation",
                detail="No custom page labels found. Pages use default numeric labels.",
            )

        # Check if labels are just sequential numbers (default, not useful)
        is_default = all(
            label == str(i + 1) or label == str(i)
            for i, label in enumerate(labels)
        )

        if is_default:
            return CheckResult(
                epr_id="EPR-008",
                rule="Page labels for thumbnails",
                status="warn",
                severity="recommendation",
                detail="Page labels are default sequential numbers. Consider using sheet numbers (e.g., A0.0, S1.1).",
            )

        return CheckResult(
            epr_id="EPR-008",
            rule="Page labels for thumbnails",
            status="pass",
            severity="recommendation",
            detail=f"Custom page labels found: {', '.join(list(labels)[:5])}{'...' if len(labels) > 5 else ''}",
        )
    except Exception:
        return CheckResult(
            epr_id="EPR-008",
            rule="Page labels for thumbnails",
            status="skip",
            severity="recommendation",
            detail="Unable to read page labels.",
        )


def _check_fonts(reader: PdfReader) -> CheckResult:
    """EPR-002: TrueType or OpenType fonts for searchable text."""
    problematic_fonts = []
    all_fonts = set()

    for i, page in enumerate(reader.pages):
        try:
            resources = page.get("/Resources")
            if not resources:
                continue
            fonts = resources.get("/Font")
            if not fonts:
                continue

            if isinstance(fonts, DictionaryObject):
                for font_name in fonts:
                    try:
                        font_obj = fonts[font_name]
                        if hasattr(font_obj, "get_object"):
                            font_obj = font_obj.get_object()
                        subtype = font_obj.get("/Subtype", "")
                        base_font = font_obj.get("/BaseFont", font_name)
                        all_fonts.add(str(base_font))

                        # Type3 fonts are bitmap/SHX — flag
                        if str(subtype) == "/Type3":
                            problematic_fonts.append(
                                f"Page {i + 1}: {base_font} (Type3/bitmap — may not be searchable)"
                            )
                    except Exception:
                        pass
        except Exception:
            pass

    if problematic_fonts:
        return CheckResult(
            epr_id="EPR-002",
            rule="TrueType/OpenType fonts required",
            status="warn",
            severity="warning",
            detail=f"Found {len(problematic_fonts)} potentially problematic font(s). SHX/Type3 fonts are not searchable.",
            page_details=problematic_fonts[:5],
        )

    if not all_fonts:
        return CheckResult(
            epr_id="EPR-002",
            rule="TrueType/OpenType fonts required",
            status="skip",
            severity="warning",
            detail="No embedded fonts detected. Pages may be image-only.",
        )

    return CheckResult(
        epr_id="EPR-002",
        rule="TrueType/OpenType fonts required",
        status="pass",
        severity="warning",
        detail=f"Found {len(all_fonts)} font(s). No Type3/bitmap fonts detected.",
    )


def _check_digital_signatures(reader: PdfReader) -> CheckResult:
    """EPR-010: No certificate-type digital signatures."""
    try:
        catalog = reader.trailer.get("/Root", {})
        if hasattr(catalog, "get_object"):
            catalog = catalog.get_object()

        acroform = catalog.get("/AcroForm")
        if acroform:
            if hasattr(acroform, "get_object"):
                acroform = acroform.get_object()
            sig_flags = acroform.get("/SigFlags", 0)
            if sig_flags:
                return CheckResult(
                    epr_id="EPR-010",
                    rule="No certificate digital signatures",
                    status="fail",
                    severity="reject",
                    detail="Certificate-type digital signatures detected. Use scanned graphic signatures instead.",
                )

            # Also check individual fields for /Sig type
            fields = acroform.get("/Fields", [])
            if hasattr(fields, "get_object"):
                fields = fields.get_object()
            for f in fields if isinstance(fields, (list, ArrayObject)) else []:
                try:
                    fobj = f.get_object() if hasattr(f, "get_object") else f
                    ft = fobj.get("/FT", "")
                    if str(ft) == "/Sig":
                        return CheckResult(
                            epr_id="EPR-010",
                            rule="No certificate digital signatures",
                            status="fail",
                            severity="reject",
                            detail="Signature form field detected. Use scanned graphic signatures instead.",
                        )
                except Exception:
                    pass

        return CheckResult(
            epr_id="EPR-010",
            rule="No certificate digital signatures",
            status="pass",
            severity="reject",
            detail="No certificate-type digital signatures found.",
        )
    except Exception:
        return CheckResult(
            epr_id="EPR-010",
            rule="No certificate digital signatures",
            status="skip",
            severity="reject",
            detail="Unable to inspect document catalog for signatures.",
        )


def _check_vector_vs_raster(reader: PdfReader) -> CheckResult:
    """EPR-001: Vector-based lines (heuristic — detect scan-like pages)."""
    raster_pages = []

    for i, page in enumerate(reader.pages):
        try:
            resources = page.get("/Resources")
            if not resources:
                continue

            # Check for XObject images
            xobjects = resources.get("/XObject")
            has_large_image = False
            if xobjects:
                if hasattr(xobjects, "get_object"):
                    xobjects = xobjects.get_object()
                if isinstance(xobjects, DictionaryObject):
                    for name in xobjects:
                        try:
                            xobj = xobjects[name]
                            if hasattr(xobj, "get_object"):
                                xobj = xobj.get_object()
                            subtype = xobj.get("/Subtype", "")
                            if str(subtype) == "/Image":
                                # Check if image is large relative to page
                                img_w = int(xobj.get("/Width", 0))
                                img_h = int(xobj.get("/Height", 0))
                                if img_w > 1000 and img_h > 1000:
                                    has_large_image = True
                        except Exception:
                            pass

            # Check for vector content (fonts indicate text drawing)
            fonts = resources.get("/Font")
            has_fonts = bool(fonts)

            # Heuristic: large image + no fonts = likely scanned
            if has_large_image and not has_fonts:
                raster_pages.append(i + 1)
        except Exception:
            pass

    if raster_pages:
        pages_str = ", ".join(str(p) for p in raster_pages[:10])
        return CheckResult(
            epr_id="EPR-001",
            rule="Vector-based lines required",
            status="warn",
            severity="reject",
            detail=f"{len(raster_pages)} page(s) appear to be scanned/raster images: {pages_str}. "
                   f"DBI requires vector-based PDF from CAD/BIM software.",
        )

    return CheckResult(
        epr_id="EPR-001",
        rule="Vector-based lines required",
        status="pass",
        severity="reject",
        detail="No scan-like raster-only pages detected.",
    )


def _check_annotations(reader: PdfReader) -> CheckResult:
    """EPR-019: Check for unflattened annotations (stamps/markup)."""
    pages_with_annotations = []

    for i, page in enumerate(reader.pages):
        try:
            annots = page.get("/Annots")
            if annots:
                if hasattr(annots, "get_object"):
                    annots = annots.get_object()
                if isinstance(annots, (list, ArrayObject)) and len(annots) > 0:
                    pages_with_annotations.append((i + 1, len(annots)))
        except Exception:
            pass

    if pages_with_annotations:
        total_annots = sum(count for _, count in pages_with_annotations)
        detail_lines = [f"Page {p}: {c} annotation(s)" for p, c in pages_with_annotations[:5]]
        return CheckResult(
            epr_id="EPR-019",
            rule="Flatten PDF after adding signatures",
            status="warn",
            severity="warning",
            detail=f"Found {total_annots} annotation(s) across {len(pages_with_annotations)} page(s). "
                   f"Flatten the PDF to prevent accidental modification of stamps/signatures.",
            page_details=detail_lines,
        )

    return CheckResult(
        epr_id="EPR-019",
        rule="Flatten PDF after adding signatures",
        status="pass",
        severity="warning",
        detail="No unflattened annotations detected.",
    )


def _check_filename(filename: str) -> CheckResult:
    """EPR-020: Document naming convention."""
    if FILENAME_PATTERN.match(filename):
        return CheckResult(
            epr_id="EPR-020",
            rule="File naming convention",
            status="pass",
            severity="warning",
            detail=f"Filename '{filename}' follows the expected pattern.",
        )

    return CheckResult(
        epr_id="EPR-020",
        rule="File naming convention",
        status="warn",
        severity="warning",
        detail=f"Filename '{filename}' may not follow DBI convention: "
               f"[Number Prefix]-[Document type]-[Revision] [Address].pdf",
    )


def _check_back_check_page(reader: PdfReader) -> CheckResult:
    """EPR-021: Back Check page as last page (heuristic)."""
    if len(reader.pages) == 0:
        return CheckResult(
            epr_id="EPR-021",
            rule="DBI Back Check page",
            status="skip",
            severity="warning",
            detail="No pages in PDF.",
        )

    last_page = reader.pages[-1]
    try:
        box = last_page.mediabox
        width_in = float(box.width) / PTS_PER_INCH
        height_in = float(box.height) / PTS_PER_INCH
        w, h = max(width_in, height_in), min(width_in, height_in)

        # Back check page is typically letter size (8.5 x 11) or tabloid (11 x 17)
        is_small = w <= 11.5 and h <= 8.75
        is_tabloid = (10.5 <= w <= 11.5) and (16.5 <= h <= 17.5)

        if is_small or is_tabloid:
            return CheckResult(
                epr_id="EPR-021",
                rule="DBI Back Check page",
                status="pass",
                severity="warning",
                detail=f"Last page is {w:.1f}\" x {h:.1f}\" — consistent with Back Check page.",
            )
        else:
            return CheckResult(
                epr_id="EPR-021",
                rule="DBI Back Check page",
                status="warn",
                severity="warning",
                detail=f"Last page is {w:.1f}\" x {h:.1f}\" — Back Check page typically 8.5\"x11\" or 11\"x17\". "
                       f"Append the DBI Back Check form as the last page.",
            )
    except Exception:
        return CheckResult(
            epr_id="EPR-021",
            rule="DBI Back Check page",
            status="skip",
            severity="warning",
            detail="Unable to read last page dimensions.",
        )


# Checks that require OCR/vision — listed for manual review
MANUAL_CHECKS = [
    ("EPR-003", "All sheets in single consolidated PDF (not individual files)"),
    ("EPR-004", "Full 1:1 scale output (not 'scale to fit')"),
    ("EPR-011", "Total page count on cover matches actual PDF page count"),
    ("EPR-012", "8.5\" x 11\" blank area on cover sheet for DBI stamping"),
    ("EPR-013", "Project address on every sheet"),
    ("EPR-014", "Sheet number on every sheet"),
    ("EPR-015", "Sheet name/description on every sheet"),
    ("EPR-016", "2\" x 2\" blank area on every sheet for reviewer stamps"),
    ("EPR-017", "3 consistent items across set (address, firm, sheet numbering)"),
    ("EPR-018", "Design professional signature and stamp on every sheet"),
    ("EPR-022", "Avoid dense hatching patterns (Bluebeam performance)"),
]


def _format_report(
    results: list[CheckResult],
    page_count: int,
    file_size_mb: float,
    filename: str,
    vision_results: list[CheckResult] | None = None,
) -> str:
    """Format all check results into markdown report."""
    all_results = results + (vision_results or [])

    lines = ["# Plan Set Validation Report\n"]
    lines.append(f"**File:** {filename}")
    lines.append(f"**Size:** {file_size_mb:.1f} MB")
    lines.append(f"**Pages:** {page_count}")
    if vision_results:
        lines.append("**AI Vision:** Enabled")

    # Summary counts
    counts: dict[str, int] = {}
    for r in all_results:
        counts[r.status] = counts.get(r.status, 0) + 1

    lines.append("\n## Summary\n")
    lines.append("| Status | Count |")
    lines.append("|--------|-------|")
    for status in ["pass", "fail", "warn", "skip", "info"]:
        if counts.get(status, 0) > 0:
            label = status.upper()
            lines.append(f"| {label} | {counts[status]} |")

    # Automated metadata checks — failures first
    lines.append("\n## Metadata Checks\n")

    for status_group in ["fail", "warn", "pass", "skip"]:
        for r in results:
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

    # Vision checks section (if enabled)
    if vision_results:
        lines.append("## AI Vision Checks\n")
        lines.append(
            "*These checks use Claude Vision to analyze sampled pages "
            "for title block data, stamps, and formatting:*\n"
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
    else:
        # Manual review checklist (when vision is NOT enabled)
        lines.append("## Checks Requiring Manual Review\n")
        lines.append(
            "*These EPR checks cannot be automated with metadata analysis. "
            "Enable AI Vision Analysis to automate them:*\n"
        )
        for epr_id, desc in MANUAL_CHECKS:
            lines.append(f"- [ ] **{epr_id}:** {desc}")

    # Source citations
    lines.append("")
    lines.append(format_sources(["epr_requirements"]))

    return "\n".join(lines)


async def validate_plans(
    pdf_bytes: bytes | str,
    filename: str = "plans.pdf",
    is_site_permit_addendum: bool = False,
    enable_vision: bool = False,
) -> str:
    """Validate a PDF plan set against SF DBI Electronic Plan Review (EPR) requirements.

    Performs metadata analysis using pypdf. When ``enable_vision=True`` and an
    ``ANTHROPIC_API_KEY`` is configured, also runs AI vision checks on sampled
    pages to verify title blocks, addresses, stamps, blank areas, and hatching.

    Args:
        pdf_bytes: Raw bytes of the uploaded PDF file (or base64-encoded string).
        filename: Original filename (used for EPR-020 naming convention check).
        is_site_permit_addendum: If True, uses 350MB file size limit instead of 250MB.
        enable_vision: If True, run Claude Vision checks on sampled pages.

    Returns:
        Formatted markdown validation report with PASS/FAIL/WARN/SKIP for each
        EPR check. When vision is enabled, manual checks are replaced with
        actual PASS/FAIL results from AI analysis.
    """
    # Handle base64 input (for MCP transport)
    if isinstance(pdf_bytes, str):
        pdf_bytes = base64.b64decode(pdf_bytes)

    results: list[CheckResult] = []
    file_size_mb = len(pdf_bytes) / (1024 * 1024)

    # EPR-006: File size
    results.append(_check_file_size(pdf_bytes, is_site_permit_addendum))

    # Try to open the PDF
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception as e:
        results.append(CheckResult(
            epr_id="EPR-009",
            rule="PDF must be readable",
            status="fail",
            severity="reject",
            detail=f"Cannot open PDF: {e}",
        ))
        return _format_report(results, 0, file_size_mb, filename)

    # EPR-009: Encryption — must check BEFORE accessing pages
    enc_result = _check_encryption(reader)
    results.append(enc_result)
    if enc_result.status == "fail":
        # Cannot perform further checks on encrypted PDF
        return _format_report(results, 0, file_size_mb, filename)

    try:
        page_count = len(reader.pages)
    except Exception:
        # Fallback for unusual PDF structures
        page_count = 0

    # EPR-005: Page dimensions
    results.append(_check_page_dimensions(reader))

    # EPR-001: Vector vs raster
    results.append(_check_vector_vs_raster(reader))

    # EPR-002: Fonts
    results.append(_check_fonts(reader))

    # EPR-007: Bookmarks
    results.append(_check_bookmarks(reader))

    # EPR-008: Page labels
    results.append(_check_page_labels(reader))

    # EPR-010: Digital signatures
    results.append(_check_digital_signatures(reader))

    # EPR-019: Annotations (unflattened)
    results.append(_check_annotations(reader))

    # EPR-020: Filename convention
    results.append(_check_filename(filename))

    # EPR-021: Back check page
    results.append(_check_back_check_page(reader))

    # Vision-based EPR checks (optional)
    vision_results = None
    if enable_vision and page_count > 0:
        try:
            from src.vision.epr_checks import run_vision_epr_checks

            logger.info("Running vision EPR checks on %s (%d pages)", filename, page_count)
            vision_results, _page_extractions = await run_vision_epr_checks(
                pdf_bytes, page_count,
            )
            logger.info(
                "Vision checks complete: %d results", len(vision_results)
            )
        except Exception as e:
            logger.error("Vision EPR checks failed: %s", e)
            # Graceful degradation — continue with metadata-only report
            vision_results = None

    return _format_report(results, page_count, file_size_mb, filename, vision_results)
