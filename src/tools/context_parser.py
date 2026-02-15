"""Keyword extraction from free-text project context.

Scans project descriptions and additional context for domain-specific
keywords that trigger supplemental analysis in the decision tools.

Phase 1: Simple keyword matching.
Phase 2: LLM-powered intent parsing.
"""

from __future__ import annotations

# Keyword → trigger category mapping.
# Each category maps to a list of keyword patterns (lowercased).
KEYWORD_TRIGGERS: dict[str, list[str]] = {
    "historic": [
        "historic", "landmark", "preservation", "historic district",
        "article 10", "article 11", "contributing building",
    ],
    "violation": [
        "violation", "notice", "complaint", "code enforcement",
        "abatement", "notice of violation", "nov",
    ],
    "seismic": [
        "seismic", "earthquake", "soft story", "retrofit",
        "liquefaction", "unreinforced masonry", "urm",
    ],
    "restaurant": [
        "restaurant", "food service", "commercial kitchen", "bar",
        "cafe", "bakery", "brewery", "food prep", "type i hood",
        "grease interceptor",
    ],
    "fire": [
        "sprinkler", "fire alarm", "fire rating", "fire department",
        "hood system", "fire suppression", "standpipe", "fire escape",
    ],
    "solar": [
        "solar", "photovoltaic", "pv panel", "ev charger",
        "ev charging", "battery storage", "solar panel",
    ],
    "demolition": [
        "demolition", "demo permit", "tear down", "raze",
        "full demolition", "partial demo",
    ],
    "urgency": [
        "urgent", "rush", "fast", "asap", "deadline",
        "time sensitive", "time-sensitive", "expedite",
    ],
    "budget": [
        "budget", "cheap", "affordable", "cost effective",
        "minimize cost", "low cost", "save money",
    ],
    "adu": [
        "adu", "in-law", "granny flat", "accessory dwelling",
        "accessory unit", "junior adu", "jadu",
    ],
    "tenant": [
        "tenant", "lease", "landlord", "renter",
        "tenant notification", "ellis act",
    ],
    "green_building": [
        "leed", "greenpoint", "green building", "title 24",
        "energy compliance", "solar ready", "ev ready",
        "all-electric", "energy code",
    ],
    "accessibility": [
        "ada", "accessibility", "accessible", "path of travel",
        "wheelchair", "disabled access", "barrier removal",
    ],
    "change_of_use": [
        "change of use", "change of occupancy", "occupancy change",
        "convert to", "converting", "repurpose",
    ],
}


def extract_triggers(text: str) -> list[str]:
    """Scan free text for keyword triggers.

    Returns a deduplicated list of trigger category names found in the text.
    Categories are ordered by their position in KEYWORD_TRIGGERS (deterministic).
    """
    if not text:
        return []

    text_lower = text.lower()
    found: list[str] = []

    for category, keywords in KEYWORD_TRIGGERS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(category)

    return found


def enhance_description(
    description: str,
    additional_context: str | None = None,
    triggers: list[str] | None = None,
) -> str:
    """Combine project description with additional context and triggers.

    Returns an enriched description string suitable for passing to the
    decision tools.  Trigger keywords found in the additional context
    that aren't already in the description are appended as tags.
    """
    parts = [description.strip()]

    if additional_context and additional_context.strip():
        parts.append(additional_context.strip())

    # Append any explicit trigger tags not already present
    if triggers:
        desc_lower = " ".join(parts).lower()
        tag_parts: list[str] = []
        for t in triggers:
            # Only add if the trigger keyword isn't already in the combined text
            if t not in desc_lower:
                tag_parts.append(t.replace("_", " "))
        if tag_parts:
            parts.append(f"[Context: {', '.join(tag_parts)}]")

    return "\n\n".join(parts)


def reorder_sections(
    priorities: list[str],
) -> list[str]:
    """Return tool section keys in priority order.

    Maps user-facing priority labels to the internal tab keys used in
    the results template.  Unprioritized sections are appended in their
    default order.

    Priority labels: timeline, cost, corrections, requirements, exploring
    Tab keys:        predict, fees, timeline, docs, risk
    """
    PRIORITY_TO_TAB = {
        "timeline": "timeline",
        "cost": "fees",
        "corrections": "risk",
        "requirements": "docs",
        "exploring": "predict",
    }

    DEFAULT_ORDER = ["predict", "timeline", "fees", "docs", "risk"]

    ordered: list[str] = []
    for p in priorities:
        tab = PRIORITY_TO_TAB.get(p)
        if tab and tab not in ordered:
            ordered.append(tab)

    # Fill in remaining tabs in default order
    for tab in DEFAULT_ORDER:
        if tab not in ordered:
            ordered.append(tab)

    return ordered
