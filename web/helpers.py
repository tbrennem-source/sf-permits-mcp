"""Shared utilities used across Flask Blueprint modules.

Extracted from web/app.py during Phase 0 Blueprint refactor (Sprint 64).
"""

import asyncio
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps

import markdown
from flask import g, abort, redirect, url_for, session


# ---------------------------------------------------------------------------
# PostHog analytics (no-op without POSTHOG_API_KEY)
# ---------------------------------------------------------------------------

_POSTHOG_KEY = os.environ.get("POSTHOG_API_KEY")
_POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com")


def posthog_enabled() -> bool:
    return bool(_POSTHOG_KEY)


def posthog_track(event: str, properties: dict = None, user_id: str = None):
    """Track server-side event. No-op if POSTHOG_API_KEY not set."""
    if not _POSTHOG_KEY:
        return
    try:
        import posthog
        posthog.api_key = _POSTHOG_KEY
        posthog.host = _POSTHOG_HOST
        posthog.capture(
            distinct_id=user_id or "anonymous",
            event=event,
            properties=properties or {},
        )
    except Exception:
        pass  # Never let analytics break the app


def posthog_get_flags(user_id: str) -> dict:
    """Get feature flags for a user. Returns {} if PostHog not configured."""
    if not _POSTHOG_KEY:
        return {}
    try:
        import posthog
        posthog.api_key = _POSTHOG_KEY
        posthog.host = _POSTHOG_HOST
        flags = posthog.get_all_flags(user_id)
        return flags or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Brand / white-label config (env-overridable)
# ---------------------------------------------------------------------------
BRAND_CONFIG = {
    "name": os.environ.get("BRAND_NAME", "sfpermits.ai"),
    "persona": os.environ.get("BRAND_PERSONA", "our knowledge base"),
    "answer_header": os.environ.get("BRAND_ANSWER_HEADER", "Here's what I found"),
    "draft_header": os.environ.get("BRAND_DRAFT_HEADER", "Draft reply"),
}


# Knowledge quiz — curated questions from data/knowledge/GAPS.md
QUIZ_QUESTIONS = [
    "Walk me through how you decide whether a project qualifies for OTC vs in-house review.",
    "What's your mental checklist when a new client describes their project? What questions do you ask first?",
    "What are the top 5 reasons building permit applications get rejected or sent back?",
    "How do you estimate timelines for clients? What's the range for a typical residential remodel vs commercial TI vs new construction?",
    "How do you calculate/estimate permit fees for a client before they apply?",
    "What unexpected fees catch clients off guard?",
    "Which agency reviews cause the most delays? Planning? Fire?",
    "For what types of projects do you NOT need Planning review?",
    "How does the OCII routing work in practice? How often do you deal with it?",
    "What are the 5 most common project types you help clients with?",
    "What's the most confusing part of the process for first-time applicants?",
    "Are there any 'gotchas' in the process that aren't well documented?",
    "Can you validate this form selection logic for common permit types?",
    "Can you validate this agency routing for a kitchen remodel?",
    "Is the 11-step in-house review process on sf.gov accurate and complete?",
]


# Neighborhood list for the dropdown (from DuckDB top neighborhoods)
NEIGHBORHOODS = [
    "", "Bayview Hunters Point", "Bernal Heights", "Castro/Upper Market",
    "Chinatown", "Crocker Amazon", "Diamond Heights", "Excelsior",
    "Financial District/South Beach", "Glen Park", "Golden Gate Park",
    "Haight Ashbury", "Hayes Valley", "Inner Richmond", "Inner Sunset",
    "Japantown", "Lakeshore", "Lincoln Park", "Lone Mountain/USF",
    "Marina", "McLaren Park", "Mission", "Mission Bay", "Nob Hill",
    "Noe Valley", "North Beach", "Oceanview/Merced/Ingleside",
    "Outer Mission", "Outer Richmond", "Pacific Heights",
    "Portola", "Potrero Hill", "Presidio", "Presidio Heights",
    "Russian Hill", "Seacliff", "South of Market", "Sunset/Parkside",
    "Tenderloin", "Treasure Island", "Twin Peaks",
    "Visitacion Valley", "West of Twin Peaks", "Western Addition",
]


# ---------------------------------------------------------------------------
# Rate limiter — Redis-backed with in-memory fallback
#
# When REDIS_URL is set (Railway production), requests are counted in Redis
# using INCR + EXPIRE so counts are shared across all Gunicorn workers.
# When REDIS_URL is not set (local dev) or Redis is unreachable, the limiter
# falls back to an in-process dict that resets on deploy.
# ---------------------------------------------------------------------------
_rate_buckets: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT_WINDOW = 60        # seconds
RATE_LIMIT_MAX_ANALYZE = 10   # /analyze requests per window
RATE_LIMIT_MAX_VALIDATE = 5   # /validate requests per window (heavier)
RATE_LIMIT_MAX_ANALYZE_PLANS = 3  # /analyze-plans requests per window (vision, costs $)
RATE_LIMIT_MAX_LOOKUP = 15    # /lookup requests per window (lightweight)
RATE_LIMIT_MAX_ASK = 20       # /ask requests per window (conversational search)
RATE_LIMIT_MAX_AUTH = 5       # /auth/send-link requests per window

# Cached Redis client — None means "not available, use in-memory"
_redis_client = None
_redis_checked = False


def _get_redis_client():
    """Return a connected Redis client, or None if unavailable.

    Result is cached after the first successful connect attempt so that the
    socket overhead is paid once per process, not per request.  If the initial
    connect or ping fails (e.g. local dev where REDIS_URL is not set) we cache
    the None so subsequent calls skip the import/connect overhead.
    """
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client

    _redis_checked = True
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        _redis_client = None
        return None

    try:
        import redis as _redis_lib
        client = _redis_lib.from_url(redis_url, socket_connect_timeout=1)
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None

    return _redis_client


def check_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Return True if the request is allowed, False if the rate limit is exceeded.

    Uses Redis INCR + EXPIRE for a sliding counter window when Redis is
    available.  Falls back to the in-memory _rate_buckets dict otherwise.

    Args:
        key: Unique key identifying the rate-limit bucket (e.g. ``"rl:ip:1.2.3.4"``).
        limit: Maximum number of requests allowed in *window_seconds*.
        window_seconds: Length of the time window in seconds.
    """
    client = _get_redis_client()
    if client is not None:
        try:
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            result = pipe.execute()
            count = result[0]
            return count <= limit
        except Exception:
            pass  # Redis error — fall through to in-memory

    # In-memory fallback (per-process, resets on deploy)
    now = time.monotonic()
    bucket = _rate_buckets[key]
    _rate_buckets[key] = [t for t in bucket if now - t < window_seconds]
    if len(_rate_buckets[key]) >= limit:
        return False
    _rate_buckets[key].append(now)
    return True


def _is_rate_limited(ip: str, max_requests: int) -> bool:
    """Return True if ip has exceeded max_requests in the current window.

    Delegates to check_rate_limit() so the Redis-backed path is used when
    available.  Existing callers pass ``(ip, max_requests)`` and receive the
    same semantics as before (True = rate limited, False = allowed).
    """
    key = f"rl:ip:{ip}"
    return not check_rate_limit(key, max_requests, RATE_LIMIT_WINDOW)


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def login_required(f):
    """Redirect to login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user:
            return redirect(url_for("auth.auth_login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Abort 403 if not admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user or not g.user.get("is_admin"):
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Cost protection rate-limit decorators (lazy import to avoid circular dep)
# ---------------------------------------------------------------------------

def _rate_limited_ai(f):
    """Lazy wrapper: apply rate_limited("ai") without circular import at module load."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        from web.cost_tracking import rate_limited as _rl
        return _rl("ai")(f)(*args, **kwargs)
    return wrapper


def _rate_limited_plans(f):
    """Lazy wrapper: apply rate_limited("plans") without circular import at module load."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        from web.cost_tracking import rate_limited as _rl
        return _rl("plans")(f)(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Async + markdown helpers
# ---------------------------------------------------------------------------

def run_async(coro):
    """Run an async function synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def md_to_html(text: str) -> str:
    """Convert markdown output from tools to HTML.

    Post-processes external links (http/https) to open in a new tab
    with rel="noopener noreferrer" for security. DBI portal links get
    an additional class for tertiary styling as secondary actions.
    """
    html = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    # Mark DBI portal links with a class for tertiary styling
    html = re.sub(
        r'<a href="(https://dbiweb02\.sfgov\.org[^"]*)"',
        r'<a href="\1" class="dbi-link" target="_blank" rel="noopener noreferrer"',
        html,
    )
    # Add target="_blank" rel="noopener noreferrer" to remaining external links
    html = re.sub(
        r'<a href="(https?://[^"]+)"(?![^>]*target=)',
        r'<a href="\1" target="_blank" rel="noopener noreferrer"',
        html,
    )
    return html


# ---------------------------------------------------------------------------
# Data helpers (used across multiple blueprints)
# ---------------------------------------------------------------------------

def _resolve_block_lot(street_number: str, street_name: str) -> tuple[str, str] | None:
    """Lightweight lookup: resolve a street address to (block, lot) from permits table."""
    from src.db import query
    from src.tools.permit_lookup import _strip_suffix
    base_name, _suffix = _strip_suffix(street_name)
    nospace_name = base_name.replace(' ', '')
    rows = query(
        "SELECT block, lot FROM permits "
        "WHERE street_number = %s "
        "  AND ("
        "    UPPER(street_name) = UPPER(%s)"
        "    OR UPPER(street_name) = UPPER(%s)"
        "    OR UPPER(COALESCE(street_name, '') || ' ' || COALESCE(street_suffix, '')) = UPPER(%s)"
        "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
        "  ) "
        "  AND block IS NOT NULL AND lot IS NOT NULL "
        "LIMIT 1",
        (street_number, base_name, street_name, street_name, nospace_name),
    )
    if rows:
        return (rows[0][0], rows[0][1])
    return None


def _is_no_results(result_md: str) -> bool:
    """Detect both 'No permits found' AND 'Please provide a permit number' as empty results."""
    if not result_md:
        return True
    lower = result_md.lower()
    return any(phrase in lower for phrase in [
        "no permits found",
        "no matching permits",
        "please provide a permit number",
        "no results",
        "0 permits found",
    ])


# ---------------------------------------------------------------------------
# NLP search query parser (Sprint 81)
# ---------------------------------------------------------------------------

# Neighborhood name aliases — common shorthand used in search queries
_NEIGHBORHOOD_ALIASES: dict[str, str] = {
    "soma": "South of Market",
    "mission": "Mission",
    "the mission": "Mission",
    "castro": "Castro/Upper Market",
    "upper market": "Castro/Upper Market",
    "noe": "Noe Valley",
    "noe valley": "Noe Valley",
    "haight": "Haight Ashbury",
    "haight ashbury": "Haight Ashbury",
    "lower haight": "Haight Ashbury",
    "marina": "Marina",
    "pacific heights": "Pacific Heights",
    "pac heights": "Pacific Heights",
    "richmond": "Inner Richmond",
    "inner richmond": "Inner Richmond",
    "outer richmond": "Outer Richmond",
    "sunset": "Sunset/Parkside",
    "inner sunset": "Inner Sunset",
    "outer sunset": "Sunset/Parkside",
    "tenderloin": "Tenderloin",
    "tl": "Tenderloin",
    "russian hill": "Russian Hill",
    "nob hill": "Nob Hill",
    "north beach": "North Beach",
    "chinatown": "Chinatown",
    "financial district": "Financial District/South Beach",
    "fintech district": "Financial District/South Beach",
    "fidi": "Financial District/South Beach",
    "bayview": "Bayview Hunters Point",
    "hunters point": "Bayview Hunters Point",
    "bernal heights": "Bernal Heights",
    "bernal": "Bernal Heights",
    "potrero hill": "Potrero Hill",
    "potrero": "Potrero Hill",
    "dogpatch": "Potrero Hill",
    "excelsior": "Excelsior",
    "portola": "Portola",
    "glen park": "Glen Park",
    "twin peaks": "Twin Peaks",
    "west portal": "West of Twin Peaks",
    "forest hill": "West of Twin Peaks",
    "diamond heights": "Diamond Heights",
    "visitacion valley": "Visitacion Valley",
    "vis valley": "Visitacion Valley",
    "crocker amazon": "Crocker Amazon",
    "mission bay": "Mission Bay",
    "japantown": "Japantown",
    "western addition": "Western Addition",
    "fillmore": "Western Addition",
    "hayes valley": "Hayes Valley",
    "hayes": "Hayes Valley",
    "lakeshore": "Lakeshore",
    "oceanview": "Oceanview/Merced/Ingleside",
    "merced": "Oceanview/Merced/Ingleside",
    "ingleside": "Oceanview/Merced/Ingleside",
    "outer mission": "Outer Mission",
    "seacliff": "Seacliff",
}

# Permit type keyword map — description phrase → canonical type label
_PERMIT_TYPE_KEYWORDS: dict[str, str] = {
    "new construction": "new construction",
    "demolition": "demolition",
    "addition": "addition",
    "adu": "adu",
    "accessory dwelling unit": "adu",
    "in-law unit": "adu",
    "kitchen remodel": "alterations",
    "bathroom remodel": "alterations",
    "remodel": "alterations",
    "renovation": "alterations",
    "alteration": "alterations",
    "alterations": "alterations",
    "tenant improvement": "tenant improvement",
    "commercial ti": "tenant improvement",
    "ti ": "tenant improvement",
    "seismic retrofit": "seismic",
    "seismic": "seismic",
    "solar": "solar",
    "solar panel": "solar",
    "electrical": "electrical",
    "plumbing": "plumbing",
    "mechanical": "mechanical",
    "roofing": "roofing",
    "roof": "roofing",
    "sign": "sign",
    "signage": "sign",
    "window": "window/door",
    "door": "window/door",
    "sprinkler": "fire protection",
    "fire suppression": "fire protection",
    "change of use": "change of use",
    "conversion": "conversion",
    "grading": "grading",
    "foundation": "foundation",
    "retaining wall": "retaining wall",
    "deck": "deck/patio",
    "patio": "deck/patio",
    "fence": "fence",
}

# Preposition phrases that precede a neighborhood name
_NEIGHBORHOOD_PREPS = re.compile(
    r'(?:in\s+(?:the\s+)?|(?:near|around|at)\s+)',
    re.IGNORECASE,
)

# Address pattern: street number + street name (with optional suffix).
# Handles both alpha street names ("Market St") and numbered streets ("6th Ave", "16th St").
# Two alternatives for street name:
#   1. Numbered street: 1-3 digits followed by ordinal suffix (st/nd/rd/th), e.g. "6th", "16th"
#   2. Alpha street: starts with a letter, 1–25 chars
_ADDR_PATTERN = re.compile(
    r'\b(\d{1,5})\s+'
    r'(\d{1,3}(?:st|nd|rd|th)|[A-Za-z][A-Za-z\s]{0,24}?)\s*'
    r'(St(?:reet)?|Ave(?:nue)?|Blvd|Boulevard|Rd|Road|Dr(?:ive)?'
    r'|Way|Ct|Court|Ln|Lane|Pl(?:ace)?|Ter(?:race)?)?'
    r'(?:\b|$)',
    re.IGNORECASE,
)

# Year pattern (2018–2030)
_YEAR_RE = re.compile(r'\b(20(?:1[89]|2[0-9]|30))\b')


def parse_search_query(q: str) -> dict:
    """Parse a natural-language search query into structured search fields.

    Returns a dict with zero or more of:
      - description_search  (str): residual description text
      - neighborhood        (str): canonical SF neighborhood name
      - street_number       (str): house/building number
      - street_name         (str): street name (may include suffix)
      - permit_type         (str): canonical permit type label
      - date_from           (str): ISO date string (YYYY-01-01) inferred from year

    Examples::
        parse_search_query("kitchen remodel in the Mission")
        # → {"description_search": "kitchen remodel", "neighborhood": "Mission"}

        parse_search_query("permits at 123 Market St")
        # → {"street_number": "123", "street_name": "Market St"}

        parse_search_query("new construction SoMa 2024")
        # → {"permit_type": "new construction", "neighborhood": "South of Market",
        #    "date_from": "2024-01-01"}
    """
    if not q or not q.strip():
        return {}

    result: dict = {}
    remaining = q.strip()

    # --- 1. Extract year → date_from FIRST (before address, so years aren't
    #        mistakenly parsed as street numbers, e.g. "kitchen remodel 2022") ---
    year_m = _YEAR_RE.search(remaining)
    if year_m:
        result["date_from"] = f"{year_m.group(1)}-01-01"
        remaining = (remaining[:year_m.start()] + remaining[year_m.end():]).strip()

    # --- 2. Extract address (number + street name) ---
    addr_m = _ADDR_PATTERN.search(remaining)
    if addr_m:
        street_number = addr_m.group(1)
        street_name_raw = addr_m.group(2).strip()
        suffix = addr_m.group(3)
        # Filter out common non-address words that look like streets
        _not_streets = {
            "sqft", "sq", "feet", "budget", "cost", "dollars", "units",
            "unit", "stories", "story", "floors", "floor", "rooms", "room",
            "year", "years", "month", "months", "day", "days",
        }
        if street_name_raw.lower().rstrip() not in _not_streets:
            result["street_number"] = street_number
            full_name = street_name_raw
            if suffix:
                full_name = f"{street_name_raw} {suffix}"
            result["street_name"] = full_name.strip()
            # Remove the matched address from remaining text
            remaining = (remaining[:addr_m.start()] + remaining[addr_m.end():]).strip()

    # --- 3. Match neighborhood (longest alias first, then full NEIGHBORHOODS list) ---
    remaining_lower = remaining.lower()
    # Try aliases (longest first to avoid partial matches like "soma" before "mission")
    sorted_aliases = sorted(_NEIGHBORHOOD_ALIASES.keys(), key=len, reverse=True)
    matched_neighborhood = None
    match_start = match_end = -1

    for alias in sorted_aliases:
        # Try with preposition prefix first: "in the Mission", "in SoMa"
        prep_pattern = re.compile(
            r'(?:in\s+(?:the\s+)?|(?:near|around|at)\s+)' + re.escape(alias) + r'\b',
            re.IGNORECASE,
        )
        pm = prep_pattern.search(remaining)
        if pm:
            matched_neighborhood = _NEIGHBORHOOD_ALIASES[alias]
            match_start, match_end = pm.start(), pm.end()
            break

        # Try bare alias
        bare_pattern = re.compile(r'(?<![a-z])' + re.escape(alias) + r'(?![a-z])', re.IGNORECASE)
        bm = bare_pattern.search(remaining)
        if bm:
            matched_neighborhood = _NEIGHBORHOOD_ALIASES[alias]
            match_start, match_end = bm.start(), bm.end()
            break

    # If no alias matched, try matching against the full NEIGHBORHOODS list directly
    if not matched_neighborhood:
        sorted_hoods = sorted([n for n in NEIGHBORHOODS if n], key=len, reverse=True)
        for hood in sorted_hoods:
            hood_pattern = re.compile(
                r'(?:in\s+(?:the\s+)?|(?:near|around|at)\s+)?' + re.escape(hood) + r'(?![a-z])',
                re.IGNORECASE,
            )
            hm = hood_pattern.search(remaining)
            if hm:
                matched_neighborhood = hood
                match_start, match_end = hm.start(), hm.end()
                break

    if matched_neighborhood:
        result["neighborhood"] = matched_neighborhood
        remaining = (remaining[:match_start] + remaining[match_end:]).strip()

    # --- 4. Match permit type keywords (longest first) ---
    remaining_lower = remaining.lower()
    sorted_permit_kws = sorted(_PERMIT_TYPE_KEYWORDS.keys(), key=len, reverse=True)
    matched_permit_type = None
    pt_match_start = pt_match_end = -1

    for kw in sorted_permit_kws:
        # Match as whole word/phrase
        kw_pattern = re.compile(r'(?<!\w)' + re.escape(kw) + r'(?!\w)', re.IGNORECASE)
        km = kw_pattern.search(remaining)
        if km:
            matched_permit_type = _PERMIT_TYPE_KEYWORDS[kw]
            pt_match_start, pt_match_end = km.start(), km.end()
            break

    if matched_permit_type:
        result["permit_type"] = matched_permit_type
        remaining = (remaining[:pt_match_start] + remaining[pt_match_end:]).strip()

    # --- 5. Residual text → description_search ---
    # Clean up leftover prepositions, articles, conjunctions, and punctuation
    cleanup_re = re.compile(
        r'^(?:in|at|for|near|of|the|and|or|with|a|an|permits?|what|show|me|find|search)\b\s*',
        re.IGNORECASE,
    )
    cleaned = remaining.strip()
    while True:
        new_cleaned = cleanup_re.sub('', cleaned).strip()
        new_cleaned = new_cleaned.strip('.,;:-/')
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned

    if cleaned and len(cleaned) >= 2:
        result["description_search"] = cleaned

    return result


def rank_search_results(results: list[dict], query: str, parsed: dict) -> list[dict]:
    """Rank search results and add match badges.

    Ranking priority:
      1. Exact address match (street_number + street_name)
      2. Permit number match (permit_number in query)
      3. Description keyword match

    Each result dict gets a 'match_badge' key added.
    Returns the re-ranked list (sorted by priority score, highest first).
    """
    if not results:
        return results

    q_lower = query.lower()
    street_number = parsed.get("street_number", "")
    street_name = parsed.get("street_name", "")

    scored = []
    for r in results:
        score = 0
        badge = "Description"

        # Address match
        r_sn = str(r.get("street_number", "") or "").strip()
        r_name = str(r.get("street_name", "") or "").strip()
        if (street_number and street_name
                and r_sn == street_number
                and street_name.lower() in r_name.lower()):
            score = 100
            badge = "Address Match"
        # Permit number match
        elif r.get("permit_number") and str(r["permit_number"]) in q_lower:
            score = 90
            badge = "Permit"
        # Description keyword overlap
        else:
            desc = (r.get("description") or "").lower()
            desc_search = (parsed.get("description_search") or "").lower()
            if desc_search and desc_search in desc:
                score = 50
                badge = "Description"

        r = dict(r)
        r["match_badge"] = badge
        r["_rank_score"] = score
        scored.append(r)

    scored.sort(key=lambda x: x["_rank_score"], reverse=True)
    # Remove internal score key
    for r in scored:
        del r["_rank_score"]
    return scored


def build_empty_result_guidance(q: str, parsed: dict) -> dict:
    """Build guidance dict shown when a search returns 0 results.

    Returns a dict with:
      - suggestions: list of {label, url, hint} dicts
      - did_you_mean: optional string suggestion
      - show_demo_link: bool
    """
    suggestions = []
    did_you_mean = None

    # If query had a neighborhood, suggest dropping it and searching bare
    if parsed.get("neighborhood") and not parsed.get("street_number"):
        suggestions.append({
            "label": "Browse all SF permits",
            "url": "/search?q=Mission+St",
            "hint": "Try searching by address: '123 Mission St'",
        })

    # If query had a permit type but no address, suggest example searches
    pt = parsed.get("permit_type")
    if pt and not parsed.get("street_number"):
        encoded_pt = pt.replace(" ", "+")
        suggestions.append({
            "label": f"Example: {pt} permit",
            "url": f"/search?q={encoded_pt}+at+123+Main+St",
            "hint": f"Add an address to find {pt} permits at a specific location.",
        })

    # If it looks like a NL query with no structure, suggest example addresses
    if not parsed.get("street_number") and not parsed.get("neighborhood"):
        suggestions.append({
            "label": "614 6th Ave — example address search",
            "url": "/search?q=614+6th+Ave",
            "hint": None,
        })
        suggestions.append({
            "label": "75 Robin Hood Dr — example address search",
            "url": "/search?q=75+Robin+Hood+Dr",
            "hint": None,
        })

    # Did-you-mean for obvious partial/typo addresses
    desc = (parsed.get("description_search") or "").strip()
    if desc and not parsed.get("street_number"):
        # Check if the description looks like an address missing a number
        if re.search(r'^[A-Za-z]', desc) and len(desc.split()) <= 3:
            did_you_mean = f"Did you mean to search for an address? Try: '123 {desc.title()}'"

    return {
        "suggestions": suggestions,
        "did_you_mean": did_you_mean,
        "show_demo_link": True,
    }


# ---------------------------------------------------------------------------
# Page cache (sub-second cached page payloads)
# ---------------------------------------------------------------------------

def get_cached_or_compute(cache_key: str, compute_fn, ttl_minutes: int = 30) -> dict:
    """Read from page_cache or compute and store. Returns dict.

    On a cache hit that is still within ttl_minutes, returns the stored payload
    with ``_cached=True`` and ``_cached_at`` fields injected.  On a miss (or
    stale/invalidated entry), calls ``compute_fn()``, stores the result, and
    returns it directly.

    All exceptions from cache reads/writes are swallowed — the function always
    returns a result even when the database is unavailable.
    """
    from src.db import get_connection, BACKEND
    conn = None
    try:
        conn = get_connection()
        sql = (
            "SELECT payload, computed_at, invalidated_at "
            "FROM page_cache WHERE cache_key = %s"
        )
        if BACKEND == "duckdb":
            sql = sql.replace("%s", "?")
            row = conn.execute(sql, (cache_key,)).fetchone()
        else:
            with conn.cursor() as cur:
                cur.execute(sql, (cache_key,))
                row = cur.fetchone()

        if row:
            payload_str, computed_at, invalidated_at = row
            if invalidated_at is None:
                # Normalise computed_at for age calculation.
                # Postgres returns TIMESTAMPTZ (UTC-aware); DuckDB returns a
                # naive local-time datetime.  We normalise: if tz-aware, compare
                # against UTC now; if naive, compare against naive local now.
                if isinstance(computed_at, str):
                    computed_at = datetime.fromisoformat(computed_at)
                if computed_at.tzinfo is not None:
                    now = datetime.now(timezone.utc)
                else:
                    now = datetime.now()
                age_minutes = (now - computed_at).total_seconds() / 60
                if age_minutes < ttl_minutes:
                    result = json.loads(payload_str)
                    result["_cached"] = True
                    result["_cached_at"] = computed_at.isoformat()
                    return result
    except Exception:
        pass  # Cache read failed — fall through to compute
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    # Cache miss or stale — compute fresh result
    result = compute_fn()

    # Persist to cache (non-fatal if write fails)
    try:
        from src.db import get_connection, BACKEND
        conn = get_connection()
        upsert_sql = (
            "INSERT INTO page_cache (cache_key, payload, computed_at, invalidated_at) "
            "VALUES (%s, %s, NOW(), NULL) "
            "ON CONFLICT (cache_key) DO UPDATE "
            "SET payload = EXCLUDED.payload, computed_at = NOW(), invalidated_at = NULL"
        )
        payload_json = json.dumps(result, default=str)
        if BACKEND == "duckdb":
            # DuckDB supports NOW() but uses ? placeholders
            upsert_sql = upsert_sql.replace("%s", "?")
            conn.execute(upsert_sql, (cache_key, payload_json))
        else:
            with conn.cursor() as cur:
                cur.execute(upsert_sql, (cache_key, payload_json))
            conn.commit()
    except Exception:
        pass  # Cache write failed — non-fatal, result still returned
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    return result


def invalidate_cache(pattern: str) -> None:
    """Invalidate cache entries whose cache_key matches a SQL LIKE pattern.

    Example: ``invalidate_cache("brief:%")`` invalidates all morning brief
    entries.  Uses ``NOW()`` / ``CURRENT_TIMESTAMP`` depending on backend.
    Exceptions are swallowed — cache invalidation is always best-effort.
    """
    from src.db import get_connection, BACKEND
    conn = None
    try:
        conn = get_connection()
        sql = (
            "UPDATE page_cache SET invalidated_at = NOW() "
            "WHERE cache_key LIKE %s"
        )
        if BACKEND == "duckdb":
            # DuckDB supports NOW() but uses ? placeholders
            sql = sql.replace("%s", "?")
            conn.execute(sql, (pattern,))
        else:
            with conn.cursor() as cur:
                cur.execute(sql, (pattern,))
            conn.commit()
    except Exception:
        pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Triage intelligence signals for search result cards
# ---------------------------------------------------------------------------

# Hardcoded station median days (p50 baseline) for when DB velocity data is
# unavailable.  These are reasonable defaults derived from known SF permit
# processing patterns.
_STATION_MEDIANS: dict[str, float] = {
    "BLDG": 30.0,
    "BLDG-E": 30.0,
    "BLDG-P": 30.0,
    "BLDG-M": 30.0,
    "BLDG-S": 30.0,
    "SFFD-HQ": 45.0,
    "SFFD": 45.0,
    "CP-ZOC": 60.0,
    "CP-ENV": 60.0,
    "PLAN": 60.0,
    "PLANNING": 60.0,
    "MECH-E": 25.0,
    "ELEC": 25.0,
    "HEALTH": 30.0,
    "DPW-BSM": 30.0,
}
_STATION_MEDIAN_DEFAULT = 30.0


def _get_station_median_db(conn, station: str, backend: str) -> float:
    """Fetch p50 days for a station from station_velocity_v2, fallback to defaults."""
    if not station:
        return _STATION_MEDIAN_DEFAULT
    try:
        _PH = "%s" if backend == "postgres" else "?"
        sql = (
            f"SELECT p50_days FROM station_velocity_v2 "
            f"WHERE station = {_PH} AND metric_type = 'initial' "
            f"AND p50_days IS NOT NULL "
            f"LIMIT 1"
        )
        if backend != "postgres":
            rows = conn.execute(sql, [station]).fetchall()
        else:
            with conn.cursor() as cur:
                cur.execute(sql, [station])
                rows = cur.fetchall()
        if rows and rows[0][0] is not None:
            return float(rows[0][0])
    except Exception:
        pass
    # Fall back to hardcoded defaults
    return _STATION_MEDIANS.get(station.upper(), _STATION_MEDIAN_DEFAULT)


def classify_days_threshold(days: int, median: float) -> str:
    """Return 'green', 'amber', or 'red' based on days vs median.

    green  = < median (on track)
    amber  = >= median and < 2x median (elevated)
    red    = >= 2x median (stuck)
    """
    if days < median:
        return "green"
    if days < median * 2:
        return "amber"
    return "red"


def compute_triage_signals(
    street_number: str | None = None,
    street_name: str | None = None,
    block: str | None = None,
    lot: str | None = None,
    permit_number: str | None = None,
    max_permits: int = 5,
) -> list[dict]:
    """Compute triage intelligence signals for search result permit cards.

    For each active permit found at the given address/parcel, returns a dict:
        permit_number    (str)
        status           (str)           — permit status
        description      (str)           — short description
        filed_date       (str|None)
        current_station  (str|None)      — most recent open station
        days_at_station  (int|None)      — days since arrive at current station
        station_median   (float|None)    — p50 baseline for that station
        threshold_class  (str|None)      — 'green', 'amber', or 'red'
        is_stuck         (bool)          — True if days > 2x median
        reviewer         (str|None)      — plan_checked_by on most recent addenda row
        station_arrive   (str|None)      — ISO date string of station arrival

    Returns [] on any error (signals are enhancements, never blockers).
    """
    from datetime import date as _date
    try:
        from src.db import get_connection, BACKEND
    except Exception:
        return []

    conn = None
    try:
        conn = get_connection()
        _PH = "%s" if BACKEND == "postgres" else "?"

        def _exec(sql: str, params=None):
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(sql, params or [])
                    return cur.fetchall()
            else:
                return conn.execute(sql, params or []).fetchall()

        # --- 1. Resolve which permits to analyse ---
        rows = []

        if permit_number:
            rows = _exec(
                f"SELECT permit_number, status, description, filed_date "
                f"FROM permits WHERE permit_number = {_PH} LIMIT 1",
                [permit_number],
            )
        elif block and lot:
            rows = _exec(
                f"SELECT permit_number, status, description, filed_date "
                f"FROM permits WHERE block = {_PH} AND lot = {_PH} "
                f"ORDER BY filed_date DESC NULLS LAST LIMIT {max_permits}",
                [block.strip(), lot.strip()],
            )
        elif street_number and street_name:
            # Match by street number + name prefix (case-insensitive)
            name_like = street_name.strip().upper().split()[0] + "%"
            rows = _exec(
                f"SELECT permit_number, status, description, filed_date "
                f"FROM permits "
                f"WHERE UPPER(street_number) = {_PH} "
                f"AND UPPER(street_name) LIKE {_PH} "
                f"ORDER BY filed_date DESC NULLS LAST LIMIT {max_permits}",
                [street_number.strip().upper(), name_like],
            )

        permits = []
        for row in rows:
            permits.append({
                "permit_number": row[0],
                "status": row[1],
                "description": row[2],
                "filed_date": str(row[3])[:10] if row[3] else None,
            })

        if not permits:
            return []

        today = _date.today()
        signals = []

        for p in permits:
            pnum = p["permit_number"]
            signal: dict = {
                "permit_number": pnum,
                "status": p.get("status"),
                "description": (p.get("description") or "")[:120],
                "filed_date": p.get("filed_date"),
                "current_station": None,
                "days_at_station": None,
                "station_median": None,
                "threshold_class": None,
                "is_stuck": False,
                "reviewer": None,
                "station_arrive": None,
            }

            # --- 2. Get most recent open station ---
            try:
                station_rows = _exec(
                    f"SELECT station, arrive, plan_checked_by "
                    f"FROM addenda "
                    f"WHERE application_number = {_PH} "
                    f"AND station IS NOT NULL "
                    f"AND finish_date IS NULL "
                    f"ORDER BY arrive DESC NULLS LAST LIMIT 1",
                    [pnum],
                )
                if station_rows:
                    station = station_rows[0][0]
                    arrive_raw = station_rows[0][1]
                    signal["reviewer"] = station_rows[0][2] or None

                    # Parse arrive date
                    arrive_date = None
                    if arrive_raw is not None:
                        try:
                            from datetime import date as _d, datetime as _dt
                            if isinstance(arrive_raw, _d) and not isinstance(arrive_raw, _dt):
                                arrive_date = arrive_raw
                            elif isinstance(arrive_raw, _dt):
                                arrive_date = arrive_raw.date()
                            else:
                                arrive_date = _d.fromisoformat(str(arrive_raw)[:10])
                        except (ValueError, TypeError):
                            arrive_date = None

                    signal["current_station"] = station
                    if arrive_date:
                        signal["station_arrive"] = arrive_date.isoformat()
                        signal["days_at_station"] = (today - arrive_date).days

                    # Get median for this station
                    if station:
                        median = _get_station_median_db(conn, station, BACKEND)
                        signal["station_median"] = median
                        if signal["days_at_station"] is not None:
                            signal["threshold_class"] = classify_days_threshold(
                                signal["days_at_station"], median
                            )
                            signal["is_stuck"] = signal["days_at_station"] >= median * 2

                else:
                    # No open station — try most recent completed station for reviewer
                    reviewer_rows = _exec(
                        f"SELECT plan_checked_by FROM addenda "
                        f"WHERE application_number = {_PH} "
                        f"AND plan_checked_by IS NOT NULL "
                        f"ORDER BY finish_date DESC NULLS LAST LIMIT 1",
                        [pnum],
                    )
                    if reviewer_rows:
                        signal["reviewer"] = reviewer_rows[0][0] or None

            except Exception:
                pass  # addenda query failed — graceful degradation

            signals.append(signal)

        return signals

    except Exception:
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
