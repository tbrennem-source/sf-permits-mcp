"""Intent router — classify free-text queries and extract entities.

Rule-based intent classification with priority ordering. No LLM calls.
Used by the /ask endpoint to route conversational search box queries.

Intents (priority order):
  1. lookup_permit   — permit number detected
  2. search_parcel   — block/lot pattern
  3. validate_plans  — validation keywords
  4. search_address  — street address pattern
  5. search_person   — person/company name search
  6. analyze_project — project description with action verbs
  7. general_question — fallback
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import get_close_matches


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: str
    confidence: float
    entities: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Priority 1: Permit numbers (9–15 digits, or letter + 6+ digits)
PERMIT_NUMBER_RE = re.compile(
    r'\b(\d{9,15})\b'
    r'|'
    r'\b([A-Z]\d{6,})\b',
    re.IGNORECASE,
)

# Priority 2: Block/lot
BLOCK_LOT_RE = re.compile(
    r'block\s*(\d{3,5})\s*[,/]?\s*lot\s*(\d{1,4})',
    re.IGNORECASE,
)

# Priority 2: Complaint/enforcement keywords
# Use regex for word-boundary matching to avoid false positives
# (e.g., "nov" matching inside "renovate")
COMPLAINT_KEYWORDS_RE = re.compile(
    r'\b(?:complaints?|violations?|enforcement|cited|abated|'
    r'code\s+violations?|building\s+complaints?|notice\s+of\s+violations?|'
    r'inspection\s+results?|failed\s+inspections?|nov)\b',
    re.IGNORECASE,
)

# Complaint number pattern: 9 digits starting with year (20XXXXXXX)
COMPLAINT_NUMBER_RE = re.compile(r'\b(20\d{7})\b')

# Priority 3.5: Validate keywords
VALIDATE_KEYWORDS = [
    "validate", "check my plans", "check plans", "epr compliance",
    "plan set", "upload pdf", "validate pdf", "check pdf",
    "epr check", "plan review compliance",
]

# Priority 4: Address pattern
# Two-pass approach: try with suffix first (greedy name), then bare number+name
# NOTE: Street names can start with digits (e.g., "16th Ave", "3rd St", "22nd Blvd")
ADDRESS_WITH_SUFFIX_RE = re.compile(
    r'(\d{1,5})\s+'
    r'(\d{0,3}(?:st|nd|rd|th)\s+|[A-Za-z][A-Za-z\s]{1,30}?)\s*'
    r'(St(?:reet)?|Ave(?:nue)?|Blvd|Boulevard|Rd|Road|Dr(?:ive)?'
    r'|Way|Ct|Court|Ln|Lane|Pl(?:ace)?|Ter(?:race)?)\.?\b',
    re.IGNORECASE,
)
# Bare address: number + word, excluding measurement words
# Also support numbered streets (e.g., "723 16th")
ADDRESS_BARE_RE = re.compile(
    r'(\d{1,5})\s+([A-Za-z][A-Za-z]{2,20}|\d{1,3}(?:st|nd|rd|th))',
    re.IGNORECASE,
)
# Words that look like addresses but aren't
_NOT_STREET_NAMES = {
    "sqft", "sq", "square", "feet", "budget", "cost", "dollars",
    "units", "unit", "stories", "story", "floors", "floor",
    "rooms", "room", "baths", "bath", "beds", "bed",
    "year", "years", "month", "months", "day", "days",
    "percent", "people", "seats", "per",
}

# Address-intent signal phrases
ADDRESS_SIGNALS = [
    "permits at", "permits for", "find permits", "search permits",
    "what's happening at", "what's going on at", "look up",
    "what's at", "show me", "anything at",
]

# Pattern to strip city/state/zip/country tail from pasted mailing addresses
# e.g., "146 Lake St 1425 San Francisco, CA 94118 US"  →  "146 Lake St 1425"
_MAILING_TAIL_RE = re.compile(
    r',?\s*(?:San\s+Francisco|SF)\s*'       # city
    r'(?:,?\s*CA(?:lifornia)?)?\s*'          # state
    r'(?:\d{5}(?:-\d{4})?)?\s*'              # zip
    r'(?:US|USA|United\s+States)?\s*$',      # country
    re.IGNORECASE,
)

# Unit / apt / suite / # numbers that can appear after the street suffix
_UNIT_RE = re.compile(
    r'\s+(?:#|apt\.?|suite|ste\.?|unit|fl(?:oor)?\.?)\s*\w+',
    re.IGNORECASE,
)
# Bare trailing 3-5 digit numbers after a street suffix (e.g., "146 Lake St 1425")
_TRAILING_UNIT_RE = re.compile(
    r'((?:St(?:reet)?|Ave(?:nue)?|Blvd|Boulevard|Rd|Road|Dr(?:ive)?'
    r'|Way|Ct|Court|Ln|Lane|Pl(?:ace)?|Ter(?:race)?)\.?)'
    r'\s+(\d{1,5})\s*$',
    re.IGNORECASE,
)

# Priority 5: Person search patterns
PERSON_PATTERNS = [
    # "projects by John Smith" / "permits for Amy Lee"
    re.compile(r"(?:projects?|permits?|work|portfolio)\s+(?:by|for|of)\s+(.+)", re.IGNORECASE),
    # "find contractor Bob" / "search architect Jane" / "show expediter Tom"
    re.compile(r"(?:find|search|show|look\s*up)\s+(?:contractor|architect|engineer|consultant|expediter|owner)?\s*(.+)", re.IGNORECASE),
    # "Amy Lee's projects" / "Smith Construction's permits"
    re.compile(r"(.+?)(?:'s)\s+(?:projects?|permits?|work|portfolio|jobs?)", re.IGNORECASE),
    # "who is John Smith" / "tell me about Amy Lee"
    re.compile(r"(?:who\s+is|tell\s+me\s+about|info\s+on|details?\s+(?:on|for))\s+(.+)", re.IGNORECASE),
]

# Roles that can appear in person search queries
PERSON_ROLES = ["contractor", "architect", "engineer", "consultant", "owner", "designer"]

# Common misspellings of roles — map to canonical form
_ROLE_TYPOS = {
    "expiditer": "consultant", "expeditor": "consultant", "expiditor": "consultant",
    "expediter": "consultant",  # old term maps to new canonical
    "architech": "architect", "architecht": "architect",
    "enginnier": "engineer", "enginner": "engineer",
    "contractr": "contractor", "contracter": "contractor",
    "desinger": "designer", "desginer": "designer",
}

# Words to strip from the start/end of extracted person names
_NAME_NOISE_LEADING = re.compile(
    r'^(?:me|the|a|an|all|my|about|info\s+on|details?\s+on)\s+', re.IGNORECASE,
)
_NAME_NOISE_TRAILING = re.compile(
    r"\s+(?:projects?|permits?|work|portfolio|jobs?|details?|info)$", re.IGNORECASE,
)

# Priority 6: Analyze project signals
ANALYZE_SIGNALS = [
    "renovate", "remodel", "build", "construct", "convert",
    "install", "add", "replace", "retrofit", "upgrade",
    "i want to", "planning to", "how much will", "what permits do i need",
    "kitchen", "bathroom", "adu", "garage", "basement",
    "commercial", "restaurant", "tenant improvement",
    "new construction", "demolition", "addition",
    "solar", "seismic", "sprinkler", "elevator",
]

# Entity extraction patterns
COST_RE = re.compile(r'\$\s*([\d,]+)\s*([kK])?')
SQFT_RE = re.compile(r'(\d[\d,]*)\s*(?:sq\.?\s*ft\.?|square\s*feet|sqft|sf)\b', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

def classify(text: str, neighborhoods: list[str] | None = None) -> IntentResult:
    """Classify a free-text query into an intent with extracted entities.

    Args:
        text: Raw user input from the search box.
        neighborhoods: Optional list of valid neighborhood names for fuzzy matching.

    Returns:
        IntentResult with intent name, confidence, and extracted entities.
    """
    text = text.strip()
    if not text:
        return IntentResult(intent="general_question", confidence=0.0,
                            entities={"query": ""})

    text_lower = text.lower()

    # --- Priority 1: Permit number ---
    m = PERMIT_NUMBER_RE.search(text)
    if m:
        permit_num = m.group(1) or m.group(2)
        return IntentResult(
            intent="lookup_permit",
            confidence=0.95,
            entities={"permit_number": permit_num},
        )

    # --- Priority 2: Complaint / enforcement search ---
    # Check before block/lot so "violations on block 2920 lot 020" routes to complaints
    has_complaint_keyword = bool(COMPLAINT_KEYWORDS_RE.search(text_lower))
    complaint_num_match = COMPLAINT_NUMBER_RE.search(text)
    if has_complaint_keyword:
        complaint_entities: dict = {}
        if complaint_num_match:
            complaint_entities["complaint_number"] = complaint_num_match.group(1)
        # Try to extract address for complaint search
        addr_suffix_m = ADDRESS_WITH_SUFFIX_RE.search(text)
        addr_m = addr_suffix_m or ADDRESS_BARE_RE.search(text)
        if addr_m:
            sn = addr_m.group(1)
            if sn:
                complaint_entities["street_number"] = sn
            street = addr_m.group(2).strip()
            # Include suffix (Dr, Ave, St, etc.) when available
            if addr_suffix_m and addr_m is addr_suffix_m:
                suffix = addr_m.group(3)
                if suffix:
                    street = f"{street} {suffix}"
            if street and street.lower() not in _NOT_STREET_NAMES:
                complaint_entities["street_name"] = street
        # Try block/lot
        bl_m = BLOCK_LOT_RE.search(text)
        if bl_m:
            complaint_entities["block"] = bl_m.group(1)
            complaint_entities["lot"] = bl_m.group(2)
        return IntentResult(
            intent="search_complaint",
            confidence=0.9,
            entities=complaint_entities,
        )

    # --- Priority 3: Block/lot ---
    m = BLOCK_LOT_RE.search(text)
    if m:
        return IntentResult(
            intent="search_parcel",
            confidence=0.9,
            entities={"block": m.group(1), "lot": m.group(2)},
        )

    # --- Priority 3.5: Validate plans ---
    if any(kw in text_lower for kw in VALIDATE_KEYWORDS):
        return IntentResult(
            intent="validate_plans",
            confidence=0.85,
            entities={},
        )

    # --- Priority 4: Address search ---
    has_address_signal = any(sig in text_lower for sig in ADDRESS_SIGNALS)
    is_short = len(text.split()) <= 8

    # Pre-clean: strip mailing address tails and unit numbers so
    # "146 Lake St 1425 San Francisco, CA 94118 US" → "146 Lake St"
    addr_text = _MAILING_TAIL_RE.sub('', text).strip()
    addr_text = _UNIT_RE.sub('', addr_text).strip()
    m_trailing = _TRAILING_UNIT_RE.search(addr_text)
    if m_trailing:
        # Remove bare trailing unit number after suffix: "Lake St 1425" → "Lake St"
        addr_text = addr_text[:m_trailing.start(2)].strip()

    # Try with suffix first (e.g., "123 Main St").
    # A street suffix IS a signal — no need for word-count or signal-phrase gates.
    has_suffix = ADDRESS_WITH_SUFFIX_RE.search(addr_text)

    # Bare address (e.g., "456 Market") still needs a gate.
    m = has_suffix or (
        ADDRESS_BARE_RE.search(addr_text) if (has_address_signal or is_short) else None
    )
    if m and (has_suffix or has_address_signal or is_short):
        street_number = m.group(1)
        street_name = m.group(2).strip()
        # Reject measurement words that look like street names
        if street_name.lower() in _NOT_STREET_NAMES:
            m = None
    if m and (has_suffix or has_address_signal or is_short):
        street_number = m.group(1)
        street_name = m.group(2).strip()
        # Append the street suffix (Dr, Ave, St, etc.) when matched by
        # ADDRESS_WITH_SUFFIX_RE so primary address saves the full name.
        # group(3) only exists on the suffix regex, not ADDRESS_BARE_RE.
        if has_suffix and m is has_suffix:
            suffix = m.group(3)
            if suffix:
                street_name = f"{street_name} {suffix}"
        # Clean trailing prepositions/articles
        street_name = re.sub(
            r'\s+(?:in|at|for|near|of|the|and|or|with)$', '',
            street_name, flags=re.IGNORECASE,
        )
        street_name = street_name.strip()
        if street_name and len(street_name) >= 2:
            return IntentResult(
                intent="search_address",
                confidence=0.85,
                entities={"street_number": street_number, "street_name": street_name},
            )

    # --- Priority 5: Person search ---
    for pattern in PERSON_PATTERNS:
        m = pattern.search(text)
        if m:
            name = m.group(1).strip()
            # Extract optional role (check canonical + misspellings)
            role = None
            for r in PERSON_ROLES:
                if r in text_lower:
                    role = r
                    name = re.sub(r'\b' + r + r'\b', '', name, flags=re.IGNORECASE).strip()
                    break
            if role is None:
                for typo, canonical in _ROLE_TYPOS.items():
                    if typo in text_lower:
                        role = canonical
                        name = re.sub(r'\b' + typo + r'\b', '', name, flags=re.IGNORECASE).strip()
                        break
            # Strip leading/trailing noise words
            name = _NAME_NOISE_LEADING.sub('', name)
            name = _NAME_NOISE_TRAILING.sub('', name)
            # Clean trailing punctuation and possessives
            name = name.rstrip(".,;:!?")
            name = re.sub(r"'s$", '', name).strip()
            if name and len(name) >= 2:
                return IntentResult(
                    intent="search_person",
                    confidence=0.8,
                    entities={"person_name": name, "role": role},
                )

    # --- Priority 6: Analyze project ---
    analyze_score = sum(1 for sig in ANALYZE_SIGNALS if sig in text_lower)
    if analyze_score >= 1 and len(text.split()) >= 4:
        entities = _extract_project_entities(text, neighborhoods)
        return IntentResult(
            intent="analyze_project",
            confidence=min(0.5 + analyze_score * 0.1, 0.9),
            entities=entities,
        )

    # --- Priority 7: General question ---
    return IntentResult(
        intent="general_question",
        confidence=0.5,
        entities={"query": text},
    )


# ---------------------------------------------------------------------------
# Entity extraction helpers
# ---------------------------------------------------------------------------

def _extract_project_entities(text: str, neighborhoods: list[str] | None = None) -> dict:
    """Extract structured fields from a project description."""
    entities: dict = {"description": text}

    # Cost
    m = COST_RE.search(text)
    if m:
        cost_str = m.group(1).replace(",", "")
        cost = float(cost_str)
        if m.group(2):  # k/K suffix
            cost *= 1000
        entities["estimated_cost"] = cost

    # Square footage
    m = SQFT_RE.search(text)
    if m:
        entities["square_footage"] = float(m.group(1).replace(",", ""))

    # Neighborhood
    if neighborhoods:
        entities["neighborhood"] = _match_neighborhood(text, neighborhoods)

    return entities


def _match_neighborhood(text: str, neighborhoods: list[str]) -> str | None:
    """Fuzzy match a neighborhood name from text.

    First tries direct substring match (case-insensitive), then falls back
    to difflib fuzzy matching on individual words.
    """
    text_lower = text.lower()

    # Direct substring match (longest first to avoid "Mission" matching before "Mission Bay")
    sorted_hoods = sorted(
        [n for n in neighborhoods if n],
        key=len, reverse=True,
    )
    for n in sorted_hoods:
        if n.lower() in text_lower:
            return n

    # Fuzzy match on words (for "Noe" -> "Noe Valley", etc.)
    words = text.split()
    hood_lowers = [n.lower() for n in neighborhoods if n]
    for word in words:
        if len(word) < 3:
            continue
        matches = get_close_matches(word.lower(), hood_lowers, n=1, cutoff=0.8)
        if matches:
            for n in neighborhoods:
                if n and n.lower() == matches[0]:
                    return n

    return None
