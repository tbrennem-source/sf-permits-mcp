"""Security middleware for sfpermits.ai.

Provides:
  - Security response headers (CSP, HSTS, X-Frame-Options, etc.)
  - CSRF protection for POST/PUT/PATCH/DELETE requests
  - User-agent blocking for bots/scrapers
  - Daily request limit checking
"""
from __future__ import annotations

import logging
import os
import secrets
import time

from flask import abort, request, session
from src.db import BACKEND, query

logger = logging.getLogger(__name__)


def add_security_headers(response):
    """Add security headers to every response.

    CSP uses 'unsafe-inline' for script-src and style-src because:
    - HTMX requires inline event handlers
    - Many templates use inline styles

    Additionally sends a CSP-Report-Only header with nonce-based policy.
    This logs violations without blocking anything, allowing gradual
    migration to nonce-based CSP.
    """
    from flask import g

    # Content Security Policy (enforced — keeps unsafe-inline as fallback)
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

    # CSP Report-Only — nonce-based policy for monitoring violations.
    # Includes 'unsafe-inline' as fallback so browsers that don't support nonces
    # still work. When a nonce is present, browsers ignore 'unsafe-inline'.
    # Violations are logged to /api/csp-report for analysis.
    # Once violations reach zero, swap this to the enforced header.
    nonce = getattr(g, "csp_nonce", "")
    if nonce:
        csp_ro = (
            f"default-src 'self'; "
            f"script-src 'nonce-{nonce}' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
            f"style-src 'nonce-{nonce}' 'unsafe-inline' https://fonts.googleapis.com; "
            f"font-src 'self' https://fonts.gstatic.com; "
            f"img-src 'self' data: blob: https:; "
            f"connect-src 'self' https://*.posthog.com; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self'; "
            f"form-action 'self'; "
            f"report-uri /api/csp-report"
        )
        response.headers["Content-Security-Policy-Report-Only"] = csp_ro
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


# ---------------------------------------------------------------------------
# CSRF Protection (QS4-D)
# ---------------------------------------------------------------------------

def _generate_csrf_token():
    """Generate or retrieve CSRF token for the current session."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


# Paths that use their own auth and skip CSRF validation
_CSRF_SKIP_PREFIXES = ("/api/csp-report", "/auth/test-login", "/cron/")


def _csrf_protect():
    """Validate CSRF token on state-changing requests.

    Checks form field 'csrf_token' or header 'X-CSRFToken'.
    Skips: GET/HEAD/OPTIONS, CRON_SECRET-authenticated endpoints,
    /api/csp-report, /auth/test-login, /cron/*.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # Skip endpoints that use their own auth mechanisms
    if any(request.path.startswith(p) for p in _CSRF_SKIP_PREFIXES):
        return

    # Skip Bearer-authenticated requests (cron jobs, API clients)
    if request.headers.get("Authorization", "").startswith("Bearer "):
        return

    token = (
        request.form.get("csrf_token")
        or request.headers.get("X-CSRFToken")
        or ""
    )
    expected = session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(token, expected):
        abort(403)


def init_security(app):
    """Register CSRF protection with a Flask app.

    Adds:
    - csrf_token context processor (available in all templates)
    - before_request CSRF check (skipped in TESTING mode)
    """
    @app.context_processor
    def csrf_context():
        return {"csrf_token": _generate_csrf_token()}

    @app.before_request
    def csrf_check():
        if app.config.get("TESTING"):
            return
        _csrf_protect()
