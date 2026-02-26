"""Shared utilities used across Flask Blueprint modules.

Extracted from web/app.py during Phase 0 Blueprint refactor (Sprint 64).
"""

import asyncio
import os
import time
from collections import defaultdict
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
# Simple in-memory rate limiter (per-IP, resets on deploy)
# ---------------------------------------------------------------------------
_rate_buckets: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT_WINDOW = 60        # seconds
RATE_LIMIT_MAX_ANALYZE = 10   # /analyze requests per window
RATE_LIMIT_MAX_VALIDATE = 5   # /validate requests per window (heavier)
RATE_LIMIT_MAX_ANALYZE_PLANS = 3  # /analyze-plans requests per window (vision, costs $)
RATE_LIMIT_MAX_LOOKUP = 15    # /lookup requests per window (lightweight)
RATE_LIMIT_MAX_ASK = 20       # /ask requests per window (conversational search)
RATE_LIMIT_MAX_AUTH = 5       # /auth/send-link requests per window


def _is_rate_limited(ip: str, max_requests: int) -> bool:
    """Return True if ip has exceeded max_requests in the current window."""
    now = time.monotonic()
    bucket = _rate_buckets[ip]
    # Prune old entries
    _rate_buckets[ip] = [t for t in bucket if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_buckets[ip]) >= max_requests:
        return True
    _rate_buckets[ip].append(now)
    return False


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
    """Convert markdown output from tools to HTML."""
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
    )


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
