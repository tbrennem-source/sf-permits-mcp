"""Owner Mode detection, What's Missing analysis, and Remediation Roadmap.

Owner Mode is a rendering context — same data, different framing.
Detection is based on address match or explicit toggle.
Privacy: never stores raw owner disclosures (per spec §4.8).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Street suffixes to strip during address normalization
_STREET_SUFFIXES = {
    "ST", "STREET", "AVE", "AVENUE", "BLVD", "BOULEVARD",
    "DR", "DRIVE", "CT", "COURT", "PL", "PLACE", "WAY",
    "LN", "LANE", "RD", "ROAD", "TER", "TERRACE", "CIR", "CIRCLE",
    "HWY", "HIGHWAY", "ALY", "ALLEY",
}


def _normalize_street_name(name: str) -> str:
    """Normalize a street name by stripping suffixes and uppercasing.

    Examples:
        "Polk St" -> "POLK"
        "ROBINHOOD DR" -> "ROBINHOOD"
        "16th Avenue" -> "16TH"
    """
    if not name:
        return ""
    parts = name.upper().strip().split()
    # Remove trailing suffix if present
    if len(parts) > 1 and parts[-1] in _STREET_SUFFIXES:
        parts = parts[:-1]
    return " ".join(parts)


def _parse_address(address: str) -> tuple[str, str]:
    """Parse an address string into (street_number, street_name).

    Handles formats like "75 Robinhood Dr", "1234 Polk St".
    Returns ("", "") if cannot parse.
    """
    if not address:
        return ("", "")
    parts = address.strip().split(None, 1)
    if len(parts) < 2:
        return ("", "")
    return (parts[0].strip(), parts[1].strip())


# ---------------------------------------------------------------------------
# Owner detection
# ---------------------------------------------------------------------------

def detect_owner(
    user: dict | None,
    report_address: str,
    explicit_toggle: bool = False,
) -> bool:
    """Determine if the current user is viewing their own property.

    Detection methods (priority order):
    1. Explicit toggle (?owner=1) — requires logged-in user
    2. Primary address match — user's primary_street_number + primary_street_name
       matches the report address (suffix-normalized, case-insensitive)

    Args:
        user: Current user dict from g.user (or None if anonymous)
        report_address: Full address string from the report (e.g., "75 Robinhood Dr")
        explicit_toggle: True if ?owner=1 was in the query string

    Returns:
        True if the user is determined to be the property owner.
    """
    if user is None:
        return False

    # Explicit toggle for logged-in users
    if explicit_toggle:
        return True

    # Address match
    user_number = (user.get("primary_street_number") or "").strip()
    user_street = (user.get("primary_street_name") or "").strip()

    if not user_number or not user_street:
        return False

    report_number, report_street = _parse_address(report_address)
    if not report_number:
        return False

    # Compare: number exact, street name suffix-normalized
    return (
        user_number == report_number
        and _normalize_street_name(user_street) == _normalize_street_name(report_street)
    )


# ---------------------------------------------------------------------------
# "What's Missing" cross-reference analysis (public data only)
# ---------------------------------------------------------------------------

def _parse_date(date_str: str | None) -> datetime | None:
    """Parse a date string from SODA API, returning None on failure."""
    if not date_str:
        return None
    try:
        # SODA dates come as "2025-03-27T00:00:00.000" or "2025-03-27"
        return datetime.fromisoformat(date_str.replace("T", " ").split(".")[0].strip())
    except (ValueError, TypeError):
        return None


def _check_classification_drift(permits: list[dict]) -> list[dict]:
    """Detect when existing_use changes across permits without a conversion permit.

    The most important finding in the 723 16th Ave analysis wasn't something in the data —
    it was something absent. The property had permits listing "1 family dwelling" for decades,
    then a 2025 permit declared "2 family dwelling" with no conversion permit on file.
    """
    findings = []
    uses_by_date = []

    for p in permits:
        existing_use = (p.get("existing_use") or "").strip()
        filed_date = p.get("filed_date")
        if existing_use and filed_date:
            uses_by_date.append((filed_date, existing_use, p.get("permit_number", "")))

    uses_by_date.sort(key=lambda x: x[0])

    prev_use = None
    prev_date = None
    for filed, use, pnum in uses_by_date:
        if prev_use and use.lower() != prev_use.lower():
            # Check if any permit between the two dates looks like a conversion
            has_conversion = any(
                any(kw in (p.get("description") or "").lower()
                    for kw in ("change of use", "conversion", "legalization", "adu", "accessory dwelling"))
                or any(kw in (p.get("permit_type_definition") or "").lower()
                       for kw in ("change of use", "conversion"))
                for p in permits
                if p.get("filed_date") and prev_date and prev_date <= p["filed_date"] <= filed
            )
            if not has_conversion:
                findings.append({
                    "type": "classification_drift",
                    "severity": "moderate",
                    "title": f"Use classification changed: \"{prev_use}\" \u2192 \"{use}\"",
                    "description": (
                        f"Permit {pnum} (filed {filed[:10] if filed else '?'}) declares the existing use as "
                        f"\"{use}\", but earlier permits consistently listed \"{prev_use}\". "
                        f"No conversion or change-of-use permit was found between these filings. "
                        f"This could indicate an undocumented use change."
                    ),
                    "evidence": {
                        "old_use": prev_use,
                        "new_use": use,
                        "trigger_permit": pnum,
                        "trigger_date": filed,
                    },
                    "section_ref": "permits",
                })
        prev_use = use
        prev_date = filed

    return findings


# Known equivalent use descriptions that should NOT trigger a mismatch
_USE_EQUIVALENTS = [
    # Sets of terms that are semantically equivalent
    {"1 family dwelling", "single family dwelling", "single family", "single family residential", "sfr", "one family dwelling"},
    {"2 family dwelling", "two family dwelling", "two family residential", "duplex", "2 family"},
    {"apartments", "multi-family", "multifamily"},
    {"office", "offices"},
    {"retail", "retail sales", "retail store"},
]


def _uses_equivalent(use_a: str, use_b: str) -> bool:
    """Check if two use descriptions are known equivalents."""
    a = use_a.lower().strip()
    b = use_b.lower().strip()
    if a == b:
        return True
    for equiv_set in _USE_EQUIVALENTS:
        if a in equiv_set and b in equiv_set:
            return True
    return False


def _check_assessor_mismatch(
    permits: list[dict], property_data: list[dict]
) -> list[dict]:
    """Check if assessor's use conflicts with the most recent permit's existing_use."""
    if not property_data or not permits:
        return []

    # Assessor use definition
    assessor_use = (property_data[0].get("use_definition") or "").strip()
    if not assessor_use:
        return []

    # Find most recent permit with existing_use
    recent = None
    for p in sorted(permits, key=lambda x: x.get("filed_date", ""), reverse=True):
        if (p.get("existing_use") or "").strip():
            recent = p
            break

    if not recent:
        return []

    permit_use = (recent.get("existing_use") or "").strip()
    if not permit_use:
        return []

    if not _uses_equivalent(assessor_use, permit_use):
        return [{
            "type": "assessor_mismatch",
            "severity": "low",
            "title": "Assessor vs. permit use mismatch",
            "description": (
                f"The Assessor records this property as \"{assessor_use}\" "
                f"but the most recent permit ({recent.get('permit_number', '?')}) "
                f"declares \"{permit_use}\". This may indicate an unrecorded change."
            ),
            "evidence": {
                "assessor_use": assessor_use,
                "permit_use": permit_use,
                "permit_number": recent.get("permit_number", ""),
            },
            "section_ref": "property_profile",
        }]

    return []


def _check_complaint_timing(
    permits: list[dict], complaints: list[dict]
) -> list[dict]:
    """Flag permits filed within 30 days of a complaint (reactive permitting)."""
    findings = []
    seen_pairs = set()

    for c in complaints:
        c_date = _parse_date(c.get("date_filed"))
        if not c_date:
            continue
        c_num = c.get("complaint_number", "")

        for p in permits:
            p_date = _parse_date(p.get("filed_date"))
            if not p_date:
                continue
            p_num = p.get("permit_number", "")

            pair_key = (c_num, p_num)
            if pair_key in seen_pairs:
                continue

            delta = (p_date - c_date).days
            if 0 <= delta <= 30:
                seen_pairs.add(pair_key)
                findings.append({
                    "type": "complaint_to_permit_timing",
                    "severity": "low",
                    "title": f"Permit filed {delta} days after complaint",
                    "description": (
                        f"Permit {p_num} was filed {delta} days after "
                        f"complaint #{c_num}. This may indicate reactive permitting \u2014 "
                        f"work that began before permits were obtained."
                    ),
                    "evidence": {
                        "complaint_number": c_num,
                        "permit_number": p_num,
                        "days_gap": delta,
                        "complaint_date": c.get("date_filed", ""),
                        "permit_date": p.get("filed_date", ""),
                    },
                    "section_ref": "complaints",
                })

    return findings


# Companion permit heuristics: (trigger_keywords_in_description, expected_companion_keywords)
_COMPANION_HEURISTICS = [
    (
        ["kitchen remodel", "kitchen renovation", "new kitchen", "commercial kitchen"],
        ["plumbing", "gas", "mechanical"],
        "Kitchen work typically requires companion plumbing and/or gas permits",
    ),
    (
        ["elevator", "lift installation"],
        ["elevator"],
        "Elevator installation typically requires a separate elevator permit",
    ),
]


def _check_missing_companions(permits: list[dict]) -> list[dict]:
    """Heuristic check for permits that should have triggered companion permits.

    Note: this is a best-effort heuristic. Many companion permits may exist
    under different permit numbers or may have been legitimately combined.
    """
    findings = []

    for p in permits:
        desc = (p.get("description") or "").lower()
        if not desc:
            continue

        for trigger_keywords, companion_keywords, explanation in _COMPANION_HEURISTICS:
            if not any(kw in desc for kw in trigger_keywords):
                continue

            # Check if any other permit at same address has companion keywords
            has_companion = any(
                any(ckw in (other.get("description") or "").lower() for ckw in companion_keywords)
                or any(ckw in (other.get("permit_type_definition") or "").lower() for ckw in companion_keywords)
                for other in permits
                if other.get("permit_number") != p.get("permit_number")
            )

            if not has_companion:
                findings.append({
                    "type": "missing_companion",
                    "severity": "low",
                    "title": "Possible missing companion permit",
                    "description": (
                        f"Permit {p.get('permit_number', '?')} describes "
                        f"\"{p.get('description', '')[:80]}\" \u2014 {explanation}, "
                        f"but no matching companion permit was found on this parcel."
                    ),
                    "evidence": {
                        "trigger_permit": p.get("permit_number", ""),
                        "trigger_description": desc[:120],
                    },
                    "section_ref": "permits",
                })

    return findings


def compute_whats_missing(
    permits: list[dict],
    complaints: list[dict],
    property_data: list[dict],
) -> list[dict]:
    """Run all cross-reference checks against public data.

    This always runs (not just Owner Mode) because it uses only public data
    and is valuable for all users. Per spec \u00a74.8, this is safe to cache and
    show to evaluators too.

    Returns:
        List of finding dicts, each with:
        - type: classification_drift | assessor_mismatch | complaint_to_permit_timing | missing_companion
        - severity: moderate | low
        - title: human-readable summary
        - description: detailed explanation
        - evidence: dict of supporting data
        - section_ref: which report section to reference
    """
    findings = []
    findings.extend(_check_classification_drift(permits))
    findings.extend(_check_assessor_mismatch(permits, property_data))
    findings.extend(_check_complaint_timing(permits, complaints))
    findings.extend(_check_missing_companions(permits))

    # Sort: moderate first, then low
    severity_order = {"moderate": 0, "low": 1}
    findings.sort(key=lambda f: severity_order.get(f["severity"], 99))

    return findings


# ---------------------------------------------------------------------------
# Remediation Roadmap (Owner Mode only)
# ---------------------------------------------------------------------------

def compute_remediation_roadmap(
    risk_items: list[dict],
    whats_missing: list[dict],
    remediation_templates: dict,
) -> list[dict]:
    """Build remediation cards for Moderate+ risk items.

    Only called in Owner Mode. Maps risk_type to remediation-roadmap.json templates.
    Filters to Moderate and High severity only (low risks don't get remediation cards).

    Args:
        risk_items: From _compute_risk_assessment(), now with risk_type field
        whats_missing: From compute_whats_missing()
        remediation_templates: From knowledge base remediation_roadmap["remediation_templates"]

    Returns:
        List of remediation card dicts with:
        - risk_type, severity, title
        - what_at_stake, options[], sources[]
    """
    templates = remediation_templates.get("remediation_templates", remediation_templates)
    cards = []

    # Process risk items (Moderate+ only)
    for risk in risk_items:
        severity = risk.get("severity", "")
        if severity not in ("high", "moderate"):
            continue

        risk_type = risk.get("risk_type", "")
        template = templates.get(risk_type)
        if not template:
            continue

        cards.append({
            "risk_type": risk_type,
            "severity": severity,
            "title": risk.get("title", ""),
            "what_at_stake": template.get("what_at_stake", ""),
            "options": template.get("options", []),
            "sources": template.get("sources", []),
        })

    # Process What's Missing items (Moderate+ only)
    for item in whats_missing:
        severity = item.get("severity", "")
        if severity not in ("high", "moderate"):
            continue

        item_type = item.get("type", "")
        template = templates.get(item_type)
        if not template:
            continue

        cards.append({
            "risk_type": item_type,
            "severity": severity,
            "title": item.get("title", ""),
            "what_at_stake": template.get("what_at_stake", ""),
            "options": template.get("options", []),
            "sources": template.get("sources", []),
        })

    return cards


# ---------------------------------------------------------------------------
# Extended expediter signal factors (Owner Mode)
# ---------------------------------------------------------------------------

def compute_extended_expediter_factors(
    whats_missing: list[dict],
) -> list[dict]:
    """Compute owner-context expediter signal factors.

    New factors per spec \u00a74.5:
    - Use classification mismatch detected: +2
    - Multi-agency review required: +1 (from classification drift implying dwelling unit change)

    These stack on top of the existing Part 3 factors.

    Returns:
        List of {label, points} dicts to merge with existing signal.
    """
    factors = []

    has_classification_drift = any(
        item.get("type") == "classification_drift" for item in whats_missing
    )
    if has_classification_drift:
        factors.append({
            "label": "Use classification mismatch detected",
            "points": 2,
        })
        # Classification drift involving dwelling unit change implies multi-agency review
        drift_items = [i for i in whats_missing if i.get("type") == "classification_drift"]
        for item in drift_items:
            evidence = item.get("evidence", {})
            new_use = (evidence.get("new_use") or "").lower()
            old_use = (evidence.get("old_use") or "").lower()
            # If the change involves dwelling units, it routes through multiple agencies
            if ("family" in new_use or "dwelling" in new_use) and new_use != old_use:
                factors.append({
                    "label": "Multi-agency review required (dwelling unit change)",
                    "points": 1,
                })
                break

    return factors


# ---------------------------------------------------------------------------
# Knowledge base citations
# ---------------------------------------------------------------------------

def attach_kb_citations(
    risk_items: list[dict],
    remediation_cards: list[dict],
) -> None:
    """Annotate risk items and remediation cards with KB source references.

    Mutates items in place, adding 'kb_citations' key.
    Uses a simple mapping from risk_type to relevant KB sources.
    """
    # Simple mapping: risk_type -> relevant knowledge base concepts
    _KB_CITATION_MAP = {
        "active_complaint": [
            {"concept": "complaint_resolution", "source_label": "DBI Complaint Process", "source_url": "https://sf.gov/departments/building-inspection"},
        ],
        "active_violation": [
            {"concept": "violation_resolution", "source_label": "DBI Enforcement & NOV Process", "source_url": "https://sf.gov/departments/building-inspection"},
        ],
        "high_cost_project": [
            {"concept": "fee_schedule", "source_label": "DBI Fee Schedule (G-13)", "source_url": "https://sf.gov/resource/2022/information-sheets-dbi"},
            {"concept": "plan_review", "source_label": "DBI Plan Review Process", "source_url": "https://sf.gov/departments/building-inspection/permits"},
        ],
        "moderate_cost_project": [
            {"concept": "fee_schedule", "source_label": "DBI Fee Schedule (G-13)", "source_url": "https://sf.gov/resource/2022/information-sheets-dbi"},
        ],
        "restrictive_zoning": [
            {"concept": "section_311", "source_label": "SF Planning Code \u00a7311 \u2014 Neighborhood Notification", "source_url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/0-0-0-21240"},
        ],
        "classification_drift": [
            {"concept": "use_classification", "source_label": "SF Planning Code \u00a7209.1 \u2014 Use Classifications", "source_url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/0-0-0-17837"},
            {"concept": "adu_legalization", "source_label": "SF Planning ADU Program", "source_url": "https://sfplanning.org/accessory-dwelling-units"},
        ],
        "complaint_to_permit_timing": [
            {"concept": "enforcement", "source_label": "DBI Enforcement Process", "source_url": "https://sf.gov/departments/building-inspection"},
        ],
        "multiple_active_permits": [],
        "missing_companion": [],
    }

    for item in risk_items:
        risk_type = item.get("risk_type", "")
        item["kb_citations"] = _KB_CITATION_MAP.get(risk_type, [])

    for card in remediation_cards:
        risk_type = card.get("risk_type", "")
        card["kb_citations"] = _KB_CITATION_MAP.get(risk_type, [])
