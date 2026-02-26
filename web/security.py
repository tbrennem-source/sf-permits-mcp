"""Security middleware for sfpermits.ai.

Provides:
  - Security response headers (CSP, HSTS, X-Frame-Options, etc.)
  - User-agent blocking for bots/scrapers
  - Daily request limit checking
"""
from __future__ import annotations

import logging
import os
import time

from src.db import BACKEND, query

logger = logging.getLogger(__name__)


def add_security_headers(response):
    """Add security headers to every response.

    CSP uses 'unsafe-inline' for script-src and style-src because:
    - HTMX requires inline event handlers
    - Many templates use inline styles
    - Future sprint can migrate to nonce-based CSP
    """
    # Content Security Policy
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    # HSTS only in production (when HTTPS is guaranteed)
    is_prod = os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("BASE_URL", "").startswith("https")
    if is_prod:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


# Blocked user agents (case-insensitive substring match)
_BLOCKED_UA_PATTERNS = [
    "python-requests",
    "scrapy",
    "wget",
    "go-http-client",
    "bot",
    "spider",
    "crawler",
]

# Allowed user agents that contain blocked patterns (e.g., "Googlebot" shouldn't be blocked
# if we ever allow it, but for now all bots are blocked in beta)
_ALLOWED_UA_OVERRIDES = []


def is_blocked_user_agent(ua: str | None) -> bool:
    """Check if user agent should be blocked.

    Returns True for known scrapers/bots. Returns False for:
    - None/empty user agent (could be legitimate health checks)
    - curl (used for health checks and cron endpoints)
    """
    if not ua:
        return False
    ua_lower = ua.lower()

    # curl is used for health checks and cron endpoints
    if "curl" in ua_lower:
        return False

    for pattern in _BLOCKED_UA_PATTERNS:
        if pattern in ua_lower:
            return True
    return False


# Daily limit cache: {user_key: (count, cache_time)}
_daily_cache: dict[str, tuple[int, float]] = {}
_DAILY_CACHE_TTL = 60  # seconds


def check_daily_limit(user_id: int | None, ip: str | None, limit: int | None = None) -> bool:
    """Check if user has exceeded daily request limit.

    Returns True if OVER the limit (should be blocked).

    Limits:
      - Authenticated users: 200/day
      - Anonymous users: 50/day

    Cached for 60s to avoid hammering the DB.
    """
    if limit is None:
        limit = 200 if user_id else 50

    cache_key = f"user_{user_id}" if user_id else f"ip_{ip}"
    now = time.monotonic()

    # Check cache
    cached = _daily_cache.get(cache_key)
    if cached and (now - cached[1]) < _DAILY_CACHE_TTL:
        return cached[0] >= limit

    # Query DB
    try:
        if BACKEND == "postgres":
            date_filter = "created_at >= CURRENT_DATE"
        else:
            date_filter = "created_at >= DATE_TRUNC('day', CURRENT_TIMESTAMP)"

        if user_id:
            rows = query(
                f"SELECT COUNT(*) FROM activity_log WHERE user_id = %s AND {date_filter}",
                (user_id,)
            )
        else:
            import hashlib
            ip_hash = hashlib.sha256((ip or "").encode()).hexdigest()[:16]
            rows = query(
                f"SELECT COUNT(*) FROM activity_log WHERE ip_hash = %s AND {date_filter}",
                (ip_hash,)
            )

        count = rows[0][0] if rows else 0
        _daily_cache[cache_key] = (count, now)
        return count >= limit
    except Exception:
        logger.debug("Daily limit check failed (non-fatal)", exc_info=True)
        return False  # Fail open


# Extended blocked paths (vulnerability scanners)
EXTENDED_BLOCKED_PATHS = {
    "/api/v1", "/graphql", "/console", "/.aws",
    "/debug", "/metrics", "/actuator/health",
}
