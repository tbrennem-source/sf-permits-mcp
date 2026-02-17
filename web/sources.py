"""Knowledge source inventory — auto-generated from tier1 JSON files.

Scans every .json file in data/knowledge/tier1/, extracts metadata,
and builds a structured inventory for the admin sources page.
Also parses GAPS.md to show known gaps alongside the inventory.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path


def _knowledge_dir() -> Path:
    """Locate the data/knowledge directory relative to the project root."""
    # Walk up from web/ to project root
    here = Path(__file__).resolve().parent
    for candidate in [here.parent, here.parent.parent]:
        kd = candidate / "data" / "knowledge"
        if kd.is_dir():
            return kd
    raise FileNotFoundError("Cannot find data/knowledge directory")


# ── Category classification ──────────────────────────────────────

_CATEGORIES: dict[str, dict] = {
    "building_code": {
        "label": "Building Code (SFBC)",
        "description": "San Francisco Building & Housing Inspection Codes — permits, inspections, enforcement",
        "lifecycle_stages": ["Application", "Issuance", "Inspections", "Completion", "Enforcement"],
    },
    "planning_code": {
        "label": "Planning Code & Zoning",
        "description": "Planning review, Section 311 notifications, conditional use, historic preservation",
        "lifecycle_stages": ["Pre-Application", "Agency Routing"],
    },
    "dbi_info_sheets": {
        "label": "DBI Info Sheets & Guides",
        "description": "Department of Building Inspection reference documents, forms, and procedures",
        "lifecycle_stages": ["Application", "Review", "Issuance"],
    },
    "compliance": {
        "label": "Compliance & Specialty Codes",
        "description": "Title 24 energy, fire code, accessibility, food facilities, seismic",
        "lifecycle_stages": ["Review", "Inspections"],
    },
    "data_sources": {
        "label": "Data & Analytics",
        "description": "Open data APIs, entity resolution, semantic index",
        "lifecycle_stages": [],
    },
    "tools": {
        "label": "Decision Tools",
        "description": "Decision tree, remediation roadmap, gap analysis",
        "lifecycle_stages": [],
    },
}

# Map filename (stem) -> category
_FILE_CATEGORY: dict[str, str] = {
    # Building Code
    "permit-expiration-rules": "building_code",
    "permit-requirements": "building_code",
    "inspections-process": "building_code",
    "certificates-occupancy": "building_code",
    "enforcement-process": "building_code",
    "appeals-bodies": "building_code",
    "fee-tables": "building_code",
    # Planning
    "planning-code-key-sections": "planning_code",
    # DBI Info Sheets
    "G-20-routing": "dbi_info_sheets",
    "G-20-tables": "dbi_info_sheets",
    "otc-criteria": "dbi_info_sheets",
    "completeness-checklist": "dbi_info_sheets",
    "permit-forms-taxonomy": "dbi_info_sheets",
    "inhouse-review-process": "dbi_info_sheets",
    "epr-requirements": "dbi_info_sheets",
    "plan-signature-requirements": "dbi_info_sheets",
    "restaurant-permit-guide": "dbi_info_sheets",
    "earthquake-brace-bolt": "dbi_info_sheets",
    "administrative-bulletins-index": "dbi_info_sheets",
    "permit-consultants-registry": "dbi_info_sheets",
    # Compliance
    "fire-code-key-sections": "compliance",
    "title24-energy-compliance": "compliance",
    "green-building-requirements": "compliance",
    "ada-accessibility-requirements": "compliance",
    "dph-food-facility-requirements": "compliance",
    "nrcc-commissioning": "compliance",
    "nrcc-process-systems": "compliance",
    # Data / Tools
    "semantic-index": "data_sources",
    "decision-tree-gaps": "tools",
    "remediation-roadmap": "tools",
}

# Known source URLs for files — used when metadata doesn't include one
_FALLBACK_URLS: dict[str, str] = {
    "G-20-routing": "https://sf.gov/resource/2022/information-sheets-dbi",
    "G-20-tables": "https://sf.gov/resource/2022/information-sheets-dbi",
    "otc-criteria": "https://sf.gov/information--projects-eligible-over-counter-otc-permit",
    "completeness-checklist": "https://sf.gov/sites/default/files/2022-07/Residential%20Pre-Plan%20Check%20Checklist.pdf",
    "permit-forms-taxonomy": "https://sf.gov/resource/2022/building-permit-application-forms",
    "inhouse-review-process": "https://sf.gov/step-by-step--get-building-permit-house-review",
    "epr-requirements": "https://sf.gov/departments/building-inspection/permits",
    "plan-signature-requirements": "https://sf.gov/resource/2022/information-sheets-dbi",
    "restaurant-permit-guide": "https://sf.gov/resource/2022/information-sheets-dbi",
    "earthquake-brace-bolt": "https://sf.gov/resource/2022/information-sheets-dbi",
    "administrative-bulletins-index": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    "fee-tables": "https://sf.gov/resource/2022/information-sheets-dbi",
    "fire-code-key-sections": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_fire/0-0-0-2",
    "planning-code-key-sections": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/",
    "permit-expiration-rules": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    "permit-requirements": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    "inspections-process": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    "certificates-occupancy": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    "enforcement-process": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    "appeals-bodies": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    "title24-energy-compliance": "https://sf.gov/resource/2022/information-sheets-dbi",
    "green-building-requirements": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-89498",
    "ada-accessibility-requirements": "https://sf.gov/resource/2022/information-sheets-dbi",
    "dph-food-facility-requirements": "https://www.sfdph.org/dph/EH/Food/default.asp",
    "permit-consultants-registry": "https://sfethics.org/compliance/city-officers/permit-consultant-disclosure",
    "semantic-index": None,
    "decision-tree-gaps": None,
    "remediation-roadmap": "https://sfpermits-ai-production.up.railway.app/report",
    "nrcc-commissioning": "https://sf.gov/resource/2022/information-sheets-dbi",
    "nrcc-process-systems": "https://sf.gov/resource/2022/information-sheets-dbi",
}


# ── Source inventory builder ─────────────────────────────────────

def _extract_metadata(filepath: Path) -> dict:
    """Extract normalized metadata from a tier1 JSON file."""
    try:
        with open(filepath) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"error": f"Could not parse {filepath.name}"}

    stem = filepath.stem
    meta = {}

    # Handle files that are raw arrays (e.g., G-20-tables.json)
    if isinstance(data, list):
        data = {"_raw_array": data}

    # Try various metadata key conventions
    raw_meta = (
        data.get("metadata")
        or data.get("meta")
        or data.get("_metadata")
        or {}
    )

    # Title — try metadata, then top-level, then derive from filename
    meta["title"] = (
        raw_meta.get("title")
        or data.get("title")
        or stem.replace("-", " ").title()
    )

    # Source description
    meta["source"] = (
        raw_meta.get("source")
        or raw_meta.get("source_description")
        or data.get("summary")
        or None
    )

    # Authority
    meta["authority"] = raw_meta.get("authority") or None

    # URL(s) — check multiple field names
    urls = []
    for url_field in ("source_url", "source_urls", "url", "api_endpoint"):
        val = raw_meta.get(url_field) or data.get(url_field)
        if val:
            if isinstance(val, list):
                urls.extend(val)
            elif isinstance(val, str):
                urls.append(val)
    # Add fallback URL if none found
    if not urls and stem in _FALLBACK_URLS and _FALLBACK_URLS[stem]:
        urls.append(_FALLBACK_URLS[stem])
    meta["urls"] = urls

    # Last updated / verified date — check multiple field names
    date_val = None
    for date_field in ("last_verified", "last_updated", "date_structured",
                       "extraction_date", "date_scraped", "date_indexed",
                       "date_fetched", "ingested_date", "last_reviewed"):
        val = raw_meta.get(date_field) or data.get(date_field)
        if val:
            date_val = str(val)[:10]
            break
    if not date_val:
        # Fall back to created/version date
        for date_field in ("created", "created_date", "validated_date"):
            val = raw_meta.get(date_field)
            if val:
                date_val = str(val)[:10]
                break
    meta["last_updated"] = date_val

    # Freshness — how stale is this source?
    if date_val:
        try:
            d = date.fromisoformat(date_val)
            age_days = (date.today() - d).days
            meta["age_days"] = age_days
            if age_days <= 180:
                meta["freshness"] = "fresh"       # ≤ 6 months
            elif age_days <= 365:
                meta["freshness"] = "aging"        # 6–12 months
            else:
                meta["freshness"] = "stale"        # > 12 months
        except (ValueError, TypeError):
            meta["age_days"] = None
            meta["freshness"] = "unknown"
    else:
        meta["age_days"] = None
        meta["freshness"] = "unknown"              # no date at all

    # Confidence
    meta["confidence"] = raw_meta.get("confidence") or None

    # Notes
    notes = raw_meta.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]
    meta["notes"] = notes

    # File size
    meta["file_size_kb"] = round(filepath.stat().st_size / 1024, 1)

    # Count data points (heuristic — count top-level keys or list items)
    data_points = 0
    for key, val in data.items():
        if key in ("metadata", "meta", "_metadata"):
            continue
        if isinstance(val, list):
            data_points += len(val)
        elif isinstance(val, dict):
            data_points += len(val)
    meta["data_points"] = data_points

    # Category
    meta["category"] = _FILE_CATEGORY.get(stem, "tools")

    meta["filename"] = filepath.name
    meta["stem"] = stem

    return meta


def get_source_inventory() -> dict:
    """Build the complete source inventory from tier1 files.

    Returns a dict with:
        - files: list of file metadata dicts
        - categories: dict of category_id -> {label, description, files}
        - stats: summary statistics
        - gaps: list of parsed knowledge gaps
        - lifecycle: permit lifecycle coverage matrix
    """
    kd = _knowledge_dir()
    tier1 = kd / "tier1"

    # Scan all JSON files
    files = []
    for fp in sorted(tier1.glob("*.json")):
        meta = _extract_metadata(fp)
        files.append(meta)

    # Group by category
    categories = {}
    for cat_id, cat_info in _CATEGORIES.items():
        cat_files = [f for f in files if f.get("category") == cat_id]
        categories[cat_id] = {
            **cat_info,
            "files": cat_files,
            "count": len(cat_files),
        }

    # Parse gaps
    gaps = _parse_gaps(kd / "GAPS.md")

    # Build lifecycle coverage matrix
    lifecycle = _build_lifecycle_matrix(files)

    # Stats
    total_size = sum(f.get("file_size_kb", 0) for f in files)
    total_data_points = sum(f.get("data_points", 0) for f in files)
    files_with_urls = sum(1 for f in files if f.get("urls"))
    files_with_dates = sum(1 for f in files if f.get("last_updated"))
    open_gaps = [g for g in gaps if not g.get("resolved")]

    # Freshness counts
    fresh_count = sum(1 for f in files if f.get("freshness") == "fresh")
    aging_count = sum(1 for f in files if f.get("freshness") == "aging")
    stale_count = sum(1 for f in files if f.get("freshness") == "stale")
    unknown_count = sum(1 for f in files if f.get("freshness") == "unknown")

    return {
        "files": files,
        "categories": categories,
        "stats": {
            "total_files": len(files),
            "total_size_kb": round(total_size, 1),
            "total_data_points": total_data_points,
            "files_with_urls": files_with_urls,
            "files_with_dates": files_with_dates,
            "fresh_count": fresh_count,
            "aging_count": aging_count,
            "stale_count": stale_count,
            "unknown_freshness_count": unknown_count,
            "open_gaps": len(open_gaps),
            "resolved_gaps": len(gaps) - len(open_gaps),
            "generated_at": date.today().isoformat(),
        },
        "gaps": gaps,
        "lifecycle": lifecycle,
    }


# ── Gap parser ───────────────────────────────────────────────────

def _parse_gaps(gaps_path: Path) -> list[dict]:
    """Parse GAPS.md into structured gap records."""
    gaps = []
    if not gaps_path.exists():
        return gaps

    text = gaps_path.read_text()
    # Match ### GAP-N: Title — STATUS patterns
    gap_pattern = re.compile(
        r"###\s+GAP-(\d+):\s+(.+?)(?:\s*—\s*(.+?))?\s*\n(.*?)(?=###\s+GAP-|\Z)",
        re.DOTALL,
    )

    for m in gap_pattern.finditer(text):
        gap_id = int(m.group(1))
        title = m.group(2).strip()
        status_hint = (m.group(3) or "").strip()
        body = m.group(4).strip()

        resolved = "RESOLVED" in status_hint.upper() if status_hint else False

        # Extract impact line
        impact = ""
        for line in body.splitlines():
            if line.startswith("**Impact**:"):
                impact = line.replace("**Impact**:", "").strip()
                break

        # Extract "Ask Amy" line
        ask_amy = ""
        for line in body.splitlines():
            if "Ask Amy" in line:
                ask_amy = line.replace("**Ask Amy**:", "").strip()
                ask_amy = ask_amy.strip('"')
                break

        # Determine severity from section header context
        # (Critical, Significant, Minor based on position in GAPS.md)
        severity = "minor"
        # Check which section this gap falls under by looking at preceding text
        gap_start = m.start()
        preceding = text[:gap_start]
        if "## Critical Gaps" in preceding and "## Significant Gaps" not in preceding:
            severity = "critical"
        elif "## Significant Gaps" in preceding and "## Minor Gaps" not in preceding:
            severity = "significant"

        gaps.append({
            "gap_id": gap_id,
            "title": title,
            "resolved": resolved,
            "status_hint": status_hint,
            "severity": severity,
            "impact": impact,
            "ask_amy": ask_amy,
        })

    return gaps


# ── Lifecycle matrix ─────────────────────────────────────────────

_LIFECYCLE_STAGES = [
    ("Pre-Application", "What permits are needed? Planning review? Zoning check?"),
    ("Application", "Forms, fees, completeness checklist, OTC vs in-house routing"),
    ("Agency Routing", "DBI, Planning, Fire, DPH, SFPUC routing rules"),
    ("Review", "Plan review, EPR, in-house process, revisions"),
    ("Issuance", "Permit issuance, conditions, expiration rules"),
    ("Inspections", "Required inspections, scheduling, reinspection"),
    ("Completion", "Certificate of occupancy, final sign-off"),
    ("Enforcement", "NOVs, stop-work, penalties, appeals"),
]

# Map lifecycle stage -> which file stems cover it
_STAGE_COVERAGE: dict[str, list[str]] = {
    "Pre-Application": [
        "planning-code-key-sections", "permit-requirements", "otc-criteria",
    ],
    "Application": [
        "permit-forms-taxonomy", "completeness-checklist", "fee-tables",
        "G-20-routing", "otc-criteria", "permit-requirements",
    ],
    "Agency Routing": [
        "G-20-routing", "G-20-tables", "planning-code-key-sections",
        "fire-code-key-sections", "dph-food-facility-requirements",
    ],
    "Review": [
        "inhouse-review-process", "epr-requirements", "plan-signature-requirements",
        "title24-energy-compliance", "ada-accessibility-requirements",
        "nrcc-commissioning", "nrcc-process-systems",
    ],
    "Issuance": [
        "permit-expiration-rules",
    ],
    "Inspections": [
        "inspections-process",
    ],
    "Completion": [
        "certificates-occupancy",
    ],
    "Enforcement": [
        "enforcement-process", "appeals-bodies",
    ],
}


def _build_lifecycle_matrix(files: list[dict]) -> list[dict]:
    """Build a lifecycle coverage matrix showing which stages have data."""
    file_stems = {f["stem"] for f in files if "stem" in f}
    matrix = []
    for stage_name, stage_desc in _LIFECYCLE_STAGES:
        covered_stems = _STAGE_COVERAGE.get(stage_name, [])
        covered_files = [s for s in covered_stems if s in file_stems]
        matrix.append({
            "stage": stage_name,
            "description": stage_desc,
            "file_count": len(covered_files),
            "files": covered_files,
            "coverage": "strong" if len(covered_files) >= 3 else "moderate" if len(covered_files) >= 1 else "gap",
        })
    return matrix
