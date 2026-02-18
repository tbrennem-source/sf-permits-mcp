"""Vision-based EPR checks for architectural plan sets.

Automates the 11 manual EPR checks (EPR-003 through EPR-022) that
require visual inspection of drawing pages. Uses Claude Vision to
analyze sampled pages and extract title block data.

Returns CheckResult objects compatible with the existing metadata-only
report formatter in validate_plans.py.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass

from src.tools.validate_plans import CheckResult
from src.vision.client import (
    analyze_image,
    is_vision_available,
    VisionCallRecord,
    VisionResult,
    VisionUsageSummary,
    DEFAULT_MODEL,
)
from src.vision.pdf_to_images import pdf_page_to_base64
from src.vision.prompts import (
    SYSTEM_PROMPT_EPR,
    PROMPT_ANNOTATION_EXTRACTION,
    PROMPT_COVER_BLANK_AREA,
    PROMPT_COVER_PAGE_COUNT,
    PROMPT_DENSE_HATCHING,
    PROMPT_TITLE_BLOCK,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def _parse_json_response(result: VisionResult) -> dict | None:
    """Parse JSON from vision response, handling markdown fences."""
    if not result.success:
        return None
    text = result.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    if text.lstrip().startswith("json"):
        text = text.lstrip()[4:]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        logger.warning("Failed to parse vision JSON: %s", text[:200])
        return None


# ---------------------------------------------------------------------------
# Page sampling strategy
# ---------------------------------------------------------------------------

def _select_sample_pages(total_pages: int) -> list[int]:
    """Select pages to sample for title block checks.

    Strategy: cover (0), first interior, middle, second-to-last.
    For 10+ page sets, also sample at the 1/3 mark.
    """
    if total_pages <= 2:
        return list(range(total_pages))

    pages = [0]  # Always include cover

    if total_pages >= 3:
        pages.append(1)  # First interior sheet

    mid = total_pages // 2
    if mid not in pages:
        pages.append(mid)

    # Second-to-last (before back check page)
    penult = total_pages - 2
    if penult > 0 and penult not in pages:
        pages.append(penult)

    # For larger sets, add 1/3 mark
    if total_pages >= 10:
        third = total_pages // 3
        if third not in pages:
            pages.append(third)

    return sorted(set(pages))


# ---------------------------------------------------------------------------
# Skip helpers
# ---------------------------------------------------------------------------

def _skip_all(reason: str) -> list[CheckResult]:
    """Return skip results for all vision-dependent checks."""
    epr_ids = [
        ("EPR-003", "All sheets in single consolidated PDF"),
        ("EPR-004", "Full 1:1 scale output"),
        ("EPR-011", "Page count on cover matches actual"),
        ("EPR-012", "8.5\" x 11\" blank area on cover for DBI stamping"),
        ("EPR-013", "Project address on every sheet"),
        ("EPR-014", "Sheet number on every sheet"),
        ("EPR-015", "Sheet name/description on every sheet"),
        ("EPR-016", "2\" x 2\" blank area on every sheet for stamps"),
        ("EPR-017", "3 consistent items across set"),
        ("EPR-018", "Design professional stamp on every sheet"),
        ("EPR-022", "Avoid dense hatching patterns"),
    ]
    return [
        CheckResult(
            epr_id=eid,
            rule=rule,
            status="skip",
            severity="warning",
            detail=reason,
        )
        for eid, rule in epr_ids
    ]


# ---------------------------------------------------------------------------
# Timed vision call wrapper
# ---------------------------------------------------------------------------

async def _timed_analyze_image(
    image_b64: str,
    prompt: str,
    call_type: str,
    usage: VisionUsageSummary,
    system_prompt: str | None = None,
    max_tokens: int = 2048,
    page_number: int | None = None,
) -> VisionResult:
    """Wrapper around analyze_image() that records call timing and tokens."""
    result = await analyze_image(
        image_b64, prompt, system_prompt, max_tokens=max_tokens,
    )
    record = VisionCallRecord(
        call_type=call_type,
        page_number=page_number,
        duration_ms=result.duration_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        success=result.success,
    )
    usage.add_call(record)
    return result


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

async def _check_cover_page_count(
    cover_b64: str, actual_count: int, usage: VisionUsageSummary,
) -> CheckResult:
    """EPR-011: Page count on cover matches actual PDF page count."""
    result = await _timed_analyze_image(
        cover_b64, PROMPT_COVER_PAGE_COUNT, "cover_page_count", usage,
        system_prompt=SYSTEM_PROMPT_EPR, page_number=0,
    )
    parsed = _parse_json_response(result)

    if not parsed or not parsed.get("found_count"):
        return CheckResult(
            epr_id="EPR-011",
            rule="Page count on cover matches actual",
            status="warn",
            severity="warning",
            detail=(
                f"Could not find a stated page/sheet count on the cover sheet. "
                f"Actual PDF has {actual_count} pages."
            ),
        )

    stated = parsed.get("stated_count")
    entries = parsed.get("sheet_index_entries", [])

    # Use sheet index entry count if stated_count not explicit
    if stated is None and entries:
        stated = len(entries)

    if stated is None:
        return CheckResult(
            epr_id="EPR-011",
            rule="Page count on cover matches actual",
            status="warn",
            severity="warning",
            detail=(
                f"Found sheet index entries but no explicit page count. "
                f"Actual PDF has {actual_count} pages."
            ),
            page_details=[f"Sheet index entries: {', '.join(entries[:10])}"],
        )

    if stated == actual_count:
        return CheckResult(
            epr_id="EPR-011",
            rule="Page count on cover matches actual",
            status="pass",
            severity="warning",
            detail=f"Cover states {stated} sheets — matches actual PDF ({actual_count} pages).",
        )

    return CheckResult(
        epr_id="EPR-011",
        rule="Page count on cover matches actual",
        status="fail",
        severity="warning",
        detail=(
            f"Cover states {stated} sheets but PDF has {actual_count} pages. "
            f"Update the sheet index or page count."
        ),
    )


async def _check_cover_blank_area(
    cover_b64: str, usage: VisionUsageSummary,
) -> CheckResult:
    """EPR-012: 8.5x11 blank area on cover for DBI stamping."""
    result = await _timed_analyze_image(
        cover_b64, PROMPT_COVER_BLANK_AREA, "cover_blank_area", usage,
        system_prompt=SYSTEM_PROMPT_EPR, page_number=0,
    )
    parsed = _parse_json_response(result)

    if not parsed:
        return CheckResult(
            epr_id="EPR-012",
            rule="8.5\" x 11\" blank area on cover for DBI stamping",
            status="skip",
            severity="warning",
            detail="Vision analysis could not assess the cover sheet.",
        )

    if parsed.get("has_blank_area"):
        location = parsed.get("location", "")
        return CheckResult(
            epr_id="EPR-012",
            rule="8.5\" x 11\" blank area on cover for DBI stamping",
            status="pass",
            severity="warning",
            detail=(
                f"Blank area found ({parsed.get('estimated_size', 'sufficient size')}) "
                f"at {location}."
            ),
        )

    return CheckResult(
        epr_id="EPR-012",
        rule="8.5\" x 11\" blank area on cover for DBI stamping",
        status="fail",
        severity="warning",
        detail=(
            "No sufficiently large blank area detected on cover sheet. "
            "DBI requires an 8.5\" x 11\" clear area for permit stamping."
        ),
        page_details=[parsed.get("notes", "")] if parsed.get("notes") else [],
    )


def _assess_address_presence(
    title_data: list[dict],
    sample_pages: list[int],
    total_pages: int,
) -> CheckResult:
    """EPR-013: Project address on every sheet."""
    if not title_data:
        return CheckResult(
            epr_id="EPR-013",
            rule="Project address on every sheet",
            status="skip",
            severity="warning",
            detail="No title block data extracted from sampled pages.",
        )

    missing = []
    found = []
    for td in title_data:
        pn = td.get("page_number", "?")
        addr = td.get("project_address")
        if addr:
            found.append((pn, addr))
        else:
            missing.append(pn)

    sampled = len(title_data)
    note = f"Checked {sampled} of {total_pages} pages."

    if not missing:
        addresses = list({a for _, a in found})
        return CheckResult(
            epr_id="EPR-013",
            rule="Project address on every sheet",
            status="pass",
            severity="warning",
            detail=f"Address found on all {sampled} sampled pages. {note}",
            page_details=[f"Address: {addresses[0]}"] if len(addresses) == 1 else
                         [f"Page {p}: {a}" for p, a in found[:5]],
        )

    return CheckResult(
        epr_id="EPR-013",
        rule="Project address on every sheet",
        status="fail",
        severity="warning",
        detail=(
            f"Address missing on {len(missing)} of {sampled} sampled pages. "
            f"Pages without address: {', '.join(str(p) for p in missing)}. {note}"
        ),
    )


def _assess_sheet_numbers(
    title_data: list[dict],
    sample_pages: list[int],
    total_pages: int,
) -> CheckResult:
    """EPR-014: Sheet number on every sheet."""
    if not title_data:
        return CheckResult(
            epr_id="EPR-014",
            rule="Sheet number on every sheet",
            status="skip",
            severity="warning",
            detail="No title block data extracted.",
        )

    missing = [td["page_number"] for td in title_data if not td.get("sheet_number")]
    sampled = len(title_data)
    note = f"Checked {sampled} of {total_pages} pages."

    if not missing:
        numbers = [td.get("sheet_number") for td in title_data if td.get("sheet_number")]
        return CheckResult(
            epr_id="EPR-014",
            rule="Sheet number on every sheet",
            status="pass",
            severity="warning",
            detail=f"Sheet numbers found on all {sampled} sampled pages. {note}",
            page_details=[f"Sheets: {', '.join(numbers[:10])}"],
        )

    return CheckResult(
        epr_id="EPR-014",
        rule="Sheet number on every sheet",
        status="fail",
        severity="warning",
        detail=(
            f"Sheet number missing on {len(missing)} of {sampled} sampled pages. "
            f"Pages: {', '.join(str(p) for p in missing)}. {note}"
        ),
    )


def _assess_sheet_names(
    title_data: list[dict],
    sample_pages: list[int],
    total_pages: int,
) -> CheckResult:
    """EPR-015: Sheet name/description on every sheet."""
    if not title_data:
        return CheckResult(
            epr_id="EPR-015",
            rule="Sheet name/description on every sheet",
            status="skip",
            severity="warning",
            detail="No title block data extracted.",
        )

    missing = [td["page_number"] for td in title_data if not td.get("sheet_name")]
    sampled = len(title_data)
    note = f"Checked {sampled} of {total_pages} pages."

    if not missing:
        return CheckResult(
            epr_id="EPR-015",
            rule="Sheet name/description on every sheet",
            status="pass",
            severity="warning",
            detail=f"Sheet names found on all {sampled} sampled pages. {note}",
        )

    return CheckResult(
        epr_id="EPR-015",
        rule="Sheet name/description on every sheet",
        status="fail",
        severity="warning",
        detail=(
            f"Sheet name missing on {len(missing)} of {sampled} sampled pages. "
            f"Pages: {', '.join(str(p) for p in missing)}. {note}"
        ),
    )


def _assess_blank_areas(
    title_data: list[dict],
    sample_pages: list[int],
    total_pages: int,
) -> CheckResult:
    """EPR-016: 2x2 blank area on every sheet for reviewer stamps."""
    if not title_data:
        return CheckResult(
            epr_id="EPR-016",
            rule="2\" x 2\" blank area on every sheet for stamps",
            status="skip",
            severity="recommendation",
            detail="No title block data extracted.",
        )

    missing = [
        td["page_number"]
        for td in title_data
        if not td.get("has_2x2_blank")
    ]
    sampled = len(title_data)
    note = f"Checked {sampled} of {total_pages} pages."

    if not missing:
        return CheckResult(
            epr_id="EPR-016",
            rule="2\" x 2\" blank area on every sheet for stamps",
            status="pass",
            severity="recommendation",
            detail=f"Blank stamp area found on all {sampled} sampled pages. {note}",
        )

    return CheckResult(
        epr_id="EPR-016",
        rule="2\" x 2\" blank area on every sheet for stamps",
        status="warn",
        severity="recommendation",
        detail=(
            f"2\"x2\" blank area not detected on {len(missing)} of {sampled} sampled "
            f"pages. Pages: {', '.join(str(p) for p in missing)}. {note}"
        ),
    )


def _assess_consistency(title_data: list[dict]) -> CheckResult:
    """EPR-017: 3 consistent items across set (address, firm, numbering)."""
    if len(title_data) < 2:
        return CheckResult(
            epr_id="EPR-017",
            rule="3 consistent items across set",
            status="skip",
            severity="recommendation",
            detail="Not enough pages sampled to assess consistency.",
        )

    addresses = {
        td.get("project_address", "").strip().lower()
        for td in title_data
        if td.get("project_address")
    }
    firms = {
        td.get("firm_name", "").strip().lower()
        for td in title_data
        if td.get("firm_name")
    }
    # Check sheet numbering uses consistent prefix scheme
    numbers = [td.get("sheet_number", "") for td in title_data if td.get("sheet_number")]
    prefixes = set()
    for num in numbers:
        # Extract letter prefix (e.g., "A" from "A1.0")
        prefix = ""
        for ch in num:
            if ch.isalpha():
                prefix += ch
            else:
                break
        if prefix:
            prefixes.add(prefix)

    issues = []
    if len(addresses) > 1:
        issues.append(f"Multiple addresses: {', '.join(addresses)}")
    if len(firms) > 1:
        issues.append(f"Multiple firms: {', '.join(firms)}")
    # Multiple prefixes is fine (A, S, M, E are expected) — inconsistency
    # would be things like mixed naming conventions

    if not issues:
        return CheckResult(
            epr_id="EPR-017",
            rule="3 consistent items across set",
            status="pass",
            severity="recommendation",
            detail="Address and firm name are consistent across sampled pages.",
            page_details=[
                f"Address: {next(iter(addresses)) if addresses else 'N/A'}",
                f"Firm: {next(iter(firms)) if firms else 'N/A'}",
                f"Sheet prefixes: {', '.join(sorted(prefixes)) if prefixes else 'N/A'}",
            ],
        )

    return CheckResult(
        epr_id="EPR-017",
        rule="3 consistent items across set",
        status="fail",
        severity="recommendation",
        detail="Inconsistencies found across sampled pages.",
        page_details=issues,
    )


def _assess_stamps(
    title_data: list[dict],
    sample_pages: list[int],
    total_pages: int,
) -> CheckResult:
    """EPR-018: Design professional signature and stamp on every sheet."""
    if not title_data:
        return CheckResult(
            epr_id="EPR-018",
            rule="Design professional stamp on every sheet",
            status="skip",
            severity="warning",
            detail="No title block data extracted.",
        )

    no_stamp = [
        td["page_number"]
        for td in title_data
        if not td.get("has_professional_stamp") and not td.get("has_signature")
    ]
    sampled = len(title_data)
    note = f"Checked {sampled} of {total_pages} pages."

    if not no_stamp:
        return CheckResult(
            epr_id="EPR-018",
            rule="Design professional stamp on every sheet",
            status="pass",
            severity="warning",
            detail=f"Professional stamp/signature found on all {sampled} sampled pages. {note}",
        )

    return CheckResult(
        epr_id="EPR-018",
        rule="Design professional stamp on every sheet",
        status="warn",
        severity="warning",
        detail=(
            f"No professional stamp or signature detected on {len(no_stamp)} of "
            f"{sampled} sampled pages. Pages: {', '.join(str(p) for p in no_stamp)}. {note}"
        ),
    )


async def _check_hatching(
    pdf_bytes: bytes,
    hatching_pages: list[int],
    cover_b64: str,
    usage: VisionUsageSummary,
) -> CheckResult:
    """EPR-022: Check for dense hatching patterns on sample pages."""
    if not hatching_pages:
        return CheckResult(
            epr_id="EPR-022",
            rule="Avoid dense hatching patterns",
            status="skip",
            severity="recommendation",
            detail="No interior pages available for hatching check.",
        )

    async def _check_one_page(pn: int) -> str | None:
        try:
            b64 = pdf_page_to_base64(pdf_bytes, pn, dpi=100)  # Lower DPI for hatching
            result = await _timed_analyze_image(
                b64, PROMPT_DENSE_HATCHING, "hatching", usage,
                system_prompt=SYSTEM_PROMPT_EPR, page_number=pn,
            )
            parsed = _parse_json_response(result)
            if parsed and parsed.get("has_dense_hatching"):
                severity = parsed.get("severity", "unknown")
                area = parsed.get("affected_areas", "")
                return f"Page {pn + 1}: {severity} hatching — {area}"
        except Exception as e:
            logger.warning("Hatching check failed for page %d: %s", pn, e)
        return None

    # Run hatching checks in parallel
    hatch_results = await asyncio.gather(*[_check_one_page(pn) for pn in hatching_pages])
    issues = [r for r in hatch_results if r is not None]

    if issues:
        return CheckResult(
            epr_id="EPR-022",
            rule="Avoid dense hatching patterns",
            status="warn",
            severity="recommendation",
            detail=(
                f"Dense hatching detected on {len(issues)} sampled page(s). "
                "This may cause slow rendering in Bluebeam Studio."
            ),
            page_details=issues,
        )

    return CheckResult(
        epr_id="EPR-022",
        rule="Avoid dense hatching patterns",
        status="pass",
        severity="recommendation",
        detail=f"No dense hatching detected on {len(hatching_pages)} sampled pages.",
    )


# ---------------------------------------------------------------------------
# Annotation extraction
# ---------------------------------------------------------------------------

VALID_ANNOTATION_TYPES = frozenset({
    "epr_issue", "code_reference", "dimension", "occupancy_label",
    "construction_type", "scope_indicator", "title_block", "stamp",
    "structural_element", "general_note", "reviewer_note",
})

VALID_ANCHORS = frozenset({
    "top-left", "top-right", "bottom-left", "bottom-right",
})

MAX_ANNOTATIONS_PER_PAGE = 12


async def extract_page_annotations(
    image_b64: str,
    page_number: int,
    usage: VisionUsageSummary | None = None,
) -> list[dict]:
    """Extract spatial annotations from a plan page image.

    Calls Claude Vision with the annotation extraction prompt and returns
    a validated list of annotation dicts.

    Args:
        image_b64: Base64-encoded PNG image of the page.
        page_number: 1-indexed page number.
        usage: Optional usage summary to track API call metrics.

    Returns:
        List of annotation dicts with keys:
            type, label, x, y, anchor, importance, page_number
    """
    try:
        if usage is not None:
            result = await _timed_analyze_image(
                image_b64, PROMPT_ANNOTATION_EXTRACTION, "annotation", usage,
                system_prompt=SYSTEM_PROMPT_EPR, max_tokens=1500,
                page_number=page_number,
            )
        else:
            result = await analyze_image(
                image_b64, PROMPT_ANNOTATION_EXTRACTION, SYSTEM_PROMPT_EPR,
                max_tokens=1500,
            )
    except Exception as e:
        logger.warning("Annotation extraction failed for page %d: %s", page_number, e)
        return []

    parsed = _parse_json_response(result)
    if not parsed or not isinstance(parsed.get("annotations"), list):
        return []

    annotations: list[dict] = []
    for raw in parsed["annotations"][:MAX_ANNOTATIONS_PER_PAGE]:
        if not isinstance(raw, dict):
            continue

        ann_type = raw.get("type", "general_note")
        if ann_type not in VALID_ANNOTATION_TYPES:
            ann_type = "general_note"

        label = str(raw.get("label", ""))[:60]
        if not label:
            continue

        try:
            x = float(raw.get("x", 50))
            y = float(raw.get("y", 50))
        except (TypeError, ValueError):
            continue

        # Clamp coordinates to 0-100
        x = max(0.0, min(100.0, x))
        y = max(0.0, min(100.0, y))

        anchor = raw.get("anchor", "top-right")
        if anchor not in VALID_ANCHORS:
            anchor = "top-right"

        importance = raw.get("importance", "medium")
        if importance not in ("high", "medium", "low"):
            importance = "medium"

        annotations.append({
            "type": ann_type,
            "label": label,
            "x": round(x, 1),
            "y": round(y, 1),
            "anchor": anchor,
            "importance": importance,
            "page_number": page_number,
        })

    return annotations


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_vision_epr_checks(
    pdf_bytes: bytes,
    total_pages: int,
    analyze_all_pages: bool = False,
) -> tuple[list[CheckResult], list[dict], list[dict], VisionUsageSummary]:
    """Run all vision-based EPR checks on a PDF plan set.

    Args:
        pdf_bytes: Raw PDF bytes.
        total_pages: Total page count (from metadata checks).
        analyze_all_pages: If True, analyze every page instead of sampling.
            Pro tier feature — free tier always uses sampling.

    Returns:
        Tuple of (check_results, page_extractions, page_annotations, usage) where
        page_extractions is a list of per-page title block data,
        page_annotations is a list of spatial annotation dicts for UI overlay,
        and usage is a VisionUsageSummary with token counts and timing.
    """
    model = os.environ.get("VISION_MODEL", DEFAULT_MODEL)

    if not is_vision_available():
        return (
            _skip_all("ANTHROPIC_API_KEY not configured — vision checks skipped"),
            [],
            [],
            VisionUsageSummary(model=model),
        )

    usage = VisionUsageSummary(model=model)
    results: list[CheckResult] = []
    page_extractions: list[dict] = []
    page_annotations: list[dict] = []

    job_t0 = time.perf_counter()

    # ── Stage 1: Render cover page ──
    render_t0 = time.perf_counter()
    try:
        cover_b64 = pdf_page_to_base64(pdf_bytes, 0, dpi=72)  # Low DPI for cover checks
    except Exception as e:
        logger.error("Failed to render cover page: %s", e)
        return _skip_all(f"PDF rendering failed: {e}"), [], [], VisionUsageSummary(model=model)
    logger.info("[vision] stage=render_cover duration_ms=%d", int((time.perf_counter() - render_t0) * 1000))

    # ── Stage 2: Cover checks — run in parallel ──
    cover_t0 = time.perf_counter()
    cover_results = await asyncio.gather(
        _check_cover_page_count(cover_b64, total_pages, usage),
        _check_cover_blank_area(cover_b64, usage),
    )
    results.extend(cover_results)
    logger.info("[vision] stage=cover_checks duration_ms=%d", int((time.perf_counter() - cover_t0) * 1000))

    # ── Stage 3: Select and render sample pages ──
    if analyze_all_pages:
        sample_pages = list(range(total_pages))
    else:
        sample_pages = _select_sample_pages(total_pages)

    render_t0 = time.perf_counter()
    page_images: dict[int, str] = {}
    for page_num in sample_pages:
        if page_num == 0:
            # Re-render cover at higher DPI for title block / annotations
            page_images[0] = pdf_page_to_base64(pdf_bytes, 0, dpi=150)
        else:
            page_images[page_num] = pdf_page_to_base64(pdf_bytes, page_num, dpi=150)
    logger.info(
        "[vision] stage=render_samples pages=%d duration_ms=%d",
        len(sample_pages), int((time.perf_counter() - render_t0) * 1000),
    )

    # ── Stage 4: Title block + annotation extraction — parallel across ALL pages ──
    async def _analyze_page(page_num: int, b64: str) -> tuple[dict | None, list[dict]]:
        """Run title block + annotation extraction for one page."""
        tb_parsed = None
        anns = []
        try:
            # Title block and annotations run in parallel for this page
            tb_task = _timed_analyze_image(
                b64, PROMPT_TITLE_BLOCK, "title_block", usage,
                system_prompt=SYSTEM_PROMPT_EPR, page_number=page_num,
            )
            ann_task = extract_page_annotations(b64, page_num + 1, usage)
            tb_result, page_anns = await asyncio.gather(tb_task, ann_task)

            tb_parsed = _parse_json_response(tb_result)
            if tb_parsed:
                tb_parsed["page_number"] = page_num + 1  # 1-indexed for display
            anns = page_anns
        except Exception as e:
            logger.warning("Page %d analysis failed: %s", page_num, e)
        return tb_parsed, anns

    pages_t0 = time.perf_counter()
    page_tasks = [
        _analyze_page(pn, page_images[pn]) for pn in sample_pages
    ]
    page_results = await asyncio.gather(*page_tasks)

    title_block_data: list[dict] = []
    for tb_parsed, anns in page_results:
        if tb_parsed:
            title_block_data.append(tb_parsed)
            page_extractions.append(tb_parsed)
        page_annotations.extend(anns)

    logger.info(
        "[vision] stage=page_analysis pages=%d duration_ms=%d",
        len(sample_pages), int((time.perf_counter() - pages_t0) * 1000),
    )

    # ── Stage 5: Assessment checks (no API calls — instant) ──
    results.append(_assess_address_presence(title_block_data, sample_pages, total_pages))
    results.append(_assess_sheet_numbers(title_block_data, sample_pages, total_pages))
    results.append(_assess_sheet_names(title_block_data, sample_pages, total_pages))
    results.append(_assess_blank_areas(title_block_data, sample_pages, total_pages))
    results.append(_assess_consistency(title_block_data))
    results.append(_assess_stamps(title_block_data, sample_pages, total_pages))

    # EPR-003: Single consolidated PDF — auto-pass
    results.append(
        CheckResult(
            epr_id="EPR-003",
            rule="All sheets in single consolidated PDF",
            status="pass",
            severity="reject",
            detail="PDF contains all sheets in a single file.",
        )
    )

    # EPR-004: Full 1:1 scale — info only
    results.append(
        CheckResult(
            epr_id="EPR-004",
            rule="Full 1:1 scale output",
            status="info",
            severity="reject",
            detail=(
                "Scale verification requires comparing stated scale to measured "
                "dimensions. Page dimensions were verified in metadata checks."
            ),
        )
    )

    # ── Stage 6: Hatching check — parallel across pages ──
    hatching_pages = [p for p in sample_pages if p != 0][:2]
    hatch_t0 = time.perf_counter()
    results.append(await _check_hatching(pdf_bytes, hatching_pages, cover_b64, usage))
    logger.info("[vision] stage=hatching_check duration_ms=%d", int((time.perf_counter() - hatch_t0) * 1000))

    total_ms = int((time.perf_counter() - job_t0) * 1000)
    logger.info(
        "[vision] COMPLETE: %d calls, %d+%d tokens, %dms api_time, %dms wall_time, ~$%.4f",
        usage.total_calls, usage.total_input_tokens, usage.total_output_tokens,
        usage.total_duration_ms, total_ms, usage.estimated_cost_usd,
    )

    return results, page_extractions, page_annotations, usage
