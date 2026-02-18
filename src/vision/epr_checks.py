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
from io import BytesIO

from pypdf import PdfReader

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


def _select_compliance_pages(total_pages: int) -> list[int]:
    """Select minimal pages for compliance mode.

    Fewer pages = fewer API calls = faster turnaround.
    Strategy: cover + first interior + middle (3 pages max).
    """
    if total_pages <= 2:
        return list(range(total_pages))

    pages = [0]  # Cover

    if total_pages >= 2:
        pages.append(1)  # First interior

    mid = total_pages // 2
    if mid not in pages and total_pages >= 4:
        pages.append(mid)

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


def _normalize_address(addr: str) -> str:
    """Normalize an address for fuzzy comparison.

    Handles common variations: 'Street' vs 'St', extra whitespace,
    punctuation, city/state suffixes.
    """
    import re as _re

    addr = addr.lower().strip()
    addr = _re.sub(r"\s+", " ", addr)
    addr = addr.replace(".", "").replace(",", "")
    for old, new in {
        " street": " st", " avenue": " ave", " boulevard": " blvd",
        " drive": " dr", " lane": " ln", " road": " rd",
        " place": " pl", " court": " ct", " circle": " cir",
        " san francisco ca": "", " san francisco": "", " sf": "",
    }.items():
        addr = addr.replace(old, new)
    return addr.strip()


def _find_sheet_number_gaps(
    sheet_numbers: list[str],
) -> tuple[list[str], list[str]]:
    """Detect gaps and duplicates in sheet numbering.

    Parses sheet numbers like A1.0, A1.1, A2.0 and groups by prefix.
    Within each prefix group, checks for sequential gaps and duplicates.

    Returns:
        (gaps, duplicates) — each a list of descriptive strings.
    """
    import re as _re

    gaps: list[str] = []
    duplicates: list[str] = []

    groups: dict[str, list[tuple[str, float]]] = {}
    for sn in sheet_numbers:
        match = _re.match(r"^([A-Za-z]+)([\d.]+)$", sn.strip())
        if not match:
            continue
        prefix = match.group(1).upper()
        try:
            num_val = float(match.group(2))
        except ValueError:
            continue
        groups.setdefault(prefix, []).append((sn, num_val))

    for prefix, items in groups.items():
        nums = [n for _, n in items]
        seen: set[float] = set()
        for sn, n in items:
            if n in seen:
                duplicates.append(sn)
            seen.add(n)

        int_parts = sorted(set(int(n) for _, n in items))
        if len(int_parts) >= 2:
            for i in range(len(int_parts) - 1):
                if int_parts[i + 1] - int_parts[i] > 1:
                    gaps.append(
                        f"{prefix}{int_parts[i]}.x \u2192 {prefix}{int_parts[i + 1]}.x (gap)"
                    )

    return gaps, duplicates


def _assess_consistency(title_data: list[dict]) -> CheckResult:
    """EPR-017: Enhanced consistency checks across the plan set.

    Checks address, firm, stamps, signatures, blank areas, and sheet
    numbering for consistency across all sampled pages.  Returns a single
    CheckResult with a percentage-based consistency score.
    """
    if len(title_data) < 2:
        return CheckResult(
            epr_id="EPR-017",
            rule="3 consistent items across set",
            status="skip",
            severity="recommendation",
            detail="Not enough pages sampled to assess consistency.",
        )

    issues: list[str] = []
    info_items: list[str] = []
    total_checks = 0
    passed_checks = 0

    # --- 1. Address consistency ---
    total_checks += 1
    addresses = {
        td.get("project_address", "").strip().lower()
        for td in title_data
        if td.get("project_address")
    }
    if len(addresses) > 1:
        normalized = {_normalize_address(a) for a in addresses}
        if len(normalized) == 1:
            info_items.append(
                f"Address variations detected but normalize to same: "
                f"{', '.join(sorted(addresses))}"
            )
            passed_checks += 1
        else:
            issues.append(f"Multiple addresses: {', '.join(sorted(addresses))}")
    elif addresses:
        passed_checks += 1

    # --- 2. Firm name consistency ---
    total_checks += 1
    firms = {
        td.get("firm_name", "").strip().lower()
        for td in title_data
        if td.get("firm_name")
    }
    if len(firms) > 1:
        issues.append(f"Multiple firms: {', '.join(sorted(firms))}")
    elif firms:
        passed_checks += 1

    # --- 3. Sheet numbering prefix scheme ---
    numbers = [td.get("sheet_number", "") for td in title_data if td.get("sheet_number")]
    prefixes: set[str] = set()
    for num in numbers:
        prefix = ""
        for ch in num:
            if ch.isalpha():
                prefix += ch
            else:
                break
        if prefix:
            prefixes.add(prefix.upper())

    # --- 4. Stamp consistency ---
    total_checks += 1
    has_stamp = [td for td in title_data if td.get("has_professional_stamp")]
    no_stamp = [td for td in title_data if not td.get("has_professional_stamp")]
    if has_stamp and no_stamp:
        missing = [str(td.get("page_number", "?")) for td in no_stamp]
        issues.append(
            f"Professional stamp missing on page(s) {', '.join(missing)} "
            f"but present on {len(has_stamp)} other page(s)"
        )
    elif has_stamp:
        passed_checks += 1

    # --- 5. Signature consistency ---
    total_checks += 1
    has_sig = [td for td in title_data if td.get("has_signature")]
    no_sig = [td for td in title_data if not td.get("has_signature")]
    if has_sig and no_sig:
        missing = [str(td.get("page_number", "?")) for td in no_sig]
        issues.append(
            f"Signature missing on page(s) {', '.join(missing)} "
            f"but present on {len(has_sig)} other page(s)"
        )
    elif has_sig:
        passed_checks += 1

    # --- 6. 2x2 blank area consistency ---
    total_checks += 1
    has_blank = [td for td in title_data if td.get("has_2x2_blank")]
    no_blank = [td for td in title_data if not td.get("has_2x2_blank")]
    if has_blank and no_blank:
        missing = [str(td.get("page_number", "?")) for td in no_blank]
        info_items.append(
            f"2\u00d72 blank area missing on page(s) {', '.join(missing)}"
        )
    elif has_blank:
        passed_checks += 1

    # --- 7. Sheet numbering gaps ---
    total_checks += 1
    gaps, dupes = _find_sheet_number_gaps(numbers)
    if dupes:
        issues.append(f"Duplicate sheet numbers: {', '.join(dupes)}")
    elif gaps:
        info_items.append(f"Possible sheet numbering gaps: {', '.join(gaps)}")
        passed_checks += 1  # Gaps are informational, not failures
    else:
        passed_checks += 1

    # --- Build result ---
    consistency_pct = int((passed_checks / total_checks) * 100) if total_checks > 0 else 0

    if not issues:
        detail = (
            f"Consistency score: {consistency_pct}% "
            f"({passed_checks}/{total_checks} checks passed). "
            f"Address and firm name are consistent across sampled pages."
        )
        return CheckResult(
            epr_id="EPR-017",
            rule="3 consistent items across set",
            status="pass",
            severity="recommendation",
            detail=detail,
            page_details=[
                f"Address: {next(iter(addresses)) if addresses else 'N/A'}",
                f"Firm: {next(iter(firms)) if firms else 'N/A'}",
                f"Sheet prefixes: {', '.join(sorted(prefixes)) if prefixes else 'N/A'}",
            ] + info_items,
        )

    # Fail for address/firm issues, warn for stamp/signature/gap issues
    is_hard_fail = any(
        "address" in i.lower() or "firm" in i.lower() for i in issues
    )
    detail = (
        f"Consistency score: {consistency_pct}% "
        f"({passed_checks}/{total_checks} checks passed). "
        f"{len(issues)} inconsistency issue(s) found."
    )
    return CheckResult(
        epr_id="EPR-017",
        rule="3 consistent items across set",
        status="fail" if is_hard_fail else "warn",
        severity="recommendation",
        detail=detail,
        page_details=issues + info_items,
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
    "ai_reviewer_response",
})

VALID_ANCHORS = frozenset({
    "top-left", "top-right", "bottom-left", "bottom-right",
})

MAX_ANNOTATIONS_PER_PAGE = 15


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


async def generate_reviewer_responses(
    image_b64: str,
    reviewer_notes: list[dict],
    usage: VisionUsageSummary | None = None,
) -> list[dict]:
    """Generate AI responses to existing reviewer comments found on a page.

    Calls Claude Vision with the reviewer response prompt, passing the
    transcribed reviewer notes for substantive code-based commentary.

    Args:
        image_b64: Base64-encoded PNG image of the page (for context).
        reviewer_notes: List of reviewer_note annotation dicts from
            extract_page_annotations().
        usage: Optional usage summary for API call metrics.

    Returns:
        List of ai_reviewer_response annotation dicts positioned near
        the original reviewer notes.
    """
    from .prompts import PROMPT_REVIEWER_RESPONSE

    if not reviewer_notes:
        return []

    # Build numbered list of reviewer comments for the prompt
    notes_text = "\n".join(
        f"{i + 1}. \"{note.get('full_content', note['label'])}\" (at position x={note['x']}%, y={note['y']}%)"
        for i, note in enumerate(reviewer_notes)
    )
    prompt = PROMPT_REVIEWER_RESPONSE.format(reviewer_notes=notes_text)

    try:
        if usage is not None:
            result = await _timed_analyze_image(
                image_b64, prompt, "reviewer_response", usage,
                system_prompt=SYSTEM_PROMPT_EPR, max_tokens=2048,
                page_number=reviewer_notes[0].get("page_number"),
            )
        else:
            result = await analyze_image(
                image_b64, prompt, SYSTEM_PROMPT_EPR, max_tokens=2048,
            )
    except Exception as e:
        logger.warning("Reviewer response generation failed: %s", e)
        return []

    parsed = _parse_json_response(result)
    if not parsed or not isinstance(parsed.get("responses"), list):
        return []

    ai_annotations: list[dict] = []
    for i, resp in enumerate(parsed["responses"]):
        if not isinstance(resp, dict):
            continue

        ai_response = str(resp.get("ai_response", ""))[:120]
        code_ref = str(resp.get("code_reference", ""))[:30]
        if not ai_response:
            continue

        # Build label: code ref + brief response
        label = f"{code_ref}: {ai_response}" if code_ref else ai_response
        label = label[:60]  # Enforce max length

        # Position near the original reviewer note (offset further, alternate sides)
        source_note = reviewer_notes[i] if i < len(reviewer_notes) else reviewer_notes[-1]
        x_offset = 8.0 if (i % 2 == 0) else -8.0
        y_offset = 10.0 + (i * 3.0)  # stagger vertically per response
        x = max(2.0, min(98.0, source_note["x"] + x_offset))
        y = max(2.0, min(98.0, source_note["y"] + y_offset))

        importance = resp.get("importance", "medium")
        if importance not in ("high", "medium", "low"):
            importance = "medium"

        ai_annotations.append({
            "type": "ai_reviewer_response",
            "label": label,
            "x": round(x, 1),
            "y": round(y, 1),
            "anchor": "bottom-right",
            "importance": importance,
            "page_number": source_note.get("page_number", 1),
        })

    return ai_annotations


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_vision_epr_checks(
    pdf_bytes: bytes,
    total_pages: int,
    analyze_all_pages: bool = False,
    analysis_mode: str = "sample",
) -> tuple[list[CheckResult], list[dict], list[dict], VisionUsageSummary]:
    """Run all vision-based EPR checks on a PDF plan set.

    Args:
        pdf_bytes: Raw PDF bytes.
        total_pages: Total page count (from metadata checks).
        analyze_all_pages: If True, analyze every page instead of sampling.
            Pro tier feature — free tier always uses sampling.
        analysis_mode: One of 'compliance', 'sample', 'full'.
            - compliance: title block extraction only (no annotations, no hatching)
            - sample: title blocks + annotations + hatching on sampled pages
            - full: title blocks + annotations + hatching on ALL pages

    Returns:
        Tuple of (check_results, page_extractions, page_annotations, usage) where
        page_extractions is a list of per-page title block data,
        page_annotations is a list of spatial annotation dicts for UI overlay,
        and usage is a VisionUsageSummary with token counts and timing.
    """
    # Resolve analyze_all_pages from analysis_mode (backward compat)
    if analysis_mode == "full":
        analyze_all_pages = True
    is_compliance = (analysis_mode == "compliance")
    skip_hatching = is_compliance
    # In compliance mode, we run annotations on 1 preview page to showcase markups
    preview_annotation_page: int | None = None  # Set after sample pages are selected
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
    elif is_compliance:
        # Compliance mode: fewer sample pages (cover + 2 interior) to minimize API calls
        sample_pages = _select_compliance_pages(total_pages)
    else:
        sample_pages = _select_sample_pages(total_pages)

    # In compliance mode, pick the first interior page for annotation preview
    if is_compliance:
        interior_pages = [p for p in sample_pages if p != 0]
        if interior_pages:
            preview_annotation_page = interior_pages[0]
            logger.info("[vision] compliance preview annotation on page %d", preview_annotation_page)

    # DPI strategy: annotations need 150 for spatial precision, title-block-only pages
    # need only 100 DPI (~55% smaller payload → faster upload & model processing).
    DPI_TITLE_BLOCK = 100   # Good enough for text readability
    DPI_ANNOTATIONS = 150   # Needs spatial precision for coordinate extraction
    DPI_HATCHING = 100      # Pattern recognition, not fine detail

    render_t0 = time.perf_counter()
    page_images: dict[int, str] = {}
    for page_num in sample_pages:
        # Pages that get annotations need higher DPI
        needs_annotations = (not is_compliance) or (page_num == preview_annotation_page)
        dpi = DPI_ANNOTATIONS if needs_annotations else DPI_TITLE_BLOCK
        page_images[page_num] = pdf_page_to_base64(pdf_bytes, page_num, dpi=dpi)
    logger.info(
        "[vision] stage=render_samples pages=%d duration_ms=%d",
        len(sample_pages), int((time.perf_counter() - render_t0) * 1000),
    )

    # ── Stage 4: Title block + annotation extraction — parallel across ALL pages ──
    async def _analyze_page(page_num: int, b64: str) -> tuple[dict | None, list[dict]]:
        """Run title block + annotation extraction for one page."""
        tb_parsed = None
        anns = []
        # In compliance mode, run annotations only on the preview page
        run_annotations = (not is_compliance) or (page_num == preview_annotation_page)
        try:
            if run_annotations:
                # Title block + annotations in parallel
                tb_task = _timed_analyze_image(
                    b64, PROMPT_TITLE_BLOCK, "title_block", usage,
                    system_prompt=SYSTEM_PROMPT_EPR, page_number=page_num,
                )
                ann_task = extract_page_annotations(b64, page_num + 1, usage)
                tb_result, page_anns = await asyncio.gather(tb_task, ann_task)

                tb_parsed = _parse_json_response(tb_result)
                if tb_parsed:
                    tb_parsed["page_number"] = page_num + 1
                anns = page_anns
            else:
                # Title block only — no annotations
                tb_result = await _timed_analyze_image(
                    b64, PROMPT_TITLE_BLOCK, "title_block", usage,
                    system_prompt=SYSTEM_PROMPT_EPR, page_number=page_num,
                )
                tb_parsed = _parse_json_response(tb_result)
                if tb_parsed:
                    tb_parsed["page_number"] = page_num + 1
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

    # ── Stage 4c: Generate AI responses to reviewer notes (if any found) ──
    reviewer_notes = [a for a in page_annotations if a["type"] == "reviewer_note"]
    if reviewer_notes and not is_compliance:
        review_t0 = time.perf_counter()
        # Group reviewer notes by page
        notes_by_page: dict[int, list[dict]] = {}
        for note in reviewer_notes:
            pn = note.get("page_number", 1)
            notes_by_page.setdefault(pn, []).append(note)

        # Generate responses for each page with reviewer notes (in parallel)
        response_tasks = []
        for pn, notes in notes_by_page.items():
            # Find the page image (page_number is 1-indexed, page_images uses 0-indexed)
            img_idx = pn - 1
            if img_idx in page_images:
                response_tasks.append(
                    generate_reviewer_responses(page_images[img_idx], notes, usage)
                )
        if response_tasks:
            response_results = await asyncio.gather(*response_tasks)
            for ai_anns in response_results:
                page_annotations.extend(ai_anns)
            logger.info(
                "[vision] stage=reviewer_responses pages=%d ai_annotations=%d duration_ms=%d",
                len(response_tasks),
                sum(len(a) for a in response_results),
                int((time.perf_counter() - review_t0) * 1000),
            )

    # ── Stage 4d: Extract native PDF annotations (no API calls) ──
    native_annotations: list[dict] = []
    if not is_compliance:
        try:
            from src.tools.validate_plans import (
                extract_native_pdf_annotations,
                native_annotations_to_reviewer_notes,
            )
            native_reader = PdfReader(BytesIO(pdf_bytes))
            native_annotations = extract_native_pdf_annotations(native_reader)
            if native_annotations:
                native_reviewer_notes = native_annotations_to_reviewer_notes(
                    native_annotations
                )
                page_annotations.extend(native_reviewer_notes)
                logger.info(
                    "[vision] stage=native_annotations count=%d",
                    len(native_annotations),
                )
        except Exception as e:
            logger.warning("Native annotation extraction failed: %s", e)

    # ── Stage 4e: AI responses to native PDF reviewer notes ──
    if native_annotations and not is_compliance:
        native_notes = [
            a for a in page_annotations
            if a.get("type") == "reviewer_note" and a.get("source") == "native_pdf"
        ]
        if native_notes:
            native_t0 = time.perf_counter()
            native_by_page: dict[int, list[dict]] = {}
            for note in native_notes:
                pn = note["page_number"]
                native_by_page.setdefault(pn, []).append(note)

            native_tasks = []
            for pn, notes in native_by_page.items():
                img_idx = pn - 1
                if img_idx in page_images:
                    native_tasks.append(
                        generate_reviewer_responses(page_images[img_idx], notes, usage)
                    )
            if native_tasks:
                native_results = await asyncio.gather(*native_tasks)
                for ai_anns in native_results:
                    page_annotations.extend(ai_anns)
                logger.info(
                    "[vision] stage=native_reviewer_responses pages=%d "
                    "ai_annotations=%d duration_ms=%d",
                    len(native_tasks),
                    sum(len(a) for a in native_results),
                    int((time.perf_counter() - native_t0) * 1000),
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

    # ── Stage 6: Hatching check — parallel across pages (skipped in compliance mode) ──
    if skip_hatching:
        results.append(CheckResult(
            epr_id="EPR-022",
            rule="Avoid dense hatching patterns",
            status="skip",
            severity="recommendation",
            detail="Hatching check skipped in Compliance Check mode.",
        ))
        logger.info("[vision] stage=hatching_check SKIPPED (compliance mode)")
    else:
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
