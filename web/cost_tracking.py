"""Cost tracking, rate limiting, and kill switch for Claude API usage.

Tables:
  api_usage          — per-call log (user_id, model, endpoint, tokens, cost, ts)
  api_daily_summary  — daily rollup (date, total_calls, total_cost, breakdown_json)

Kill switch:
  Reads KILL_SWITCH_ENABLED env var at startup. Can be overridden at runtime
  via set_kill_switch(). Admin dashboard toggles via POST /admin/costs/kill-switch.

Rate limiting:
  Per-user rate limits stored in memory (same pattern as existing _rate_buckets).
  @rate_limited("ai") — wraps routes that call Claude API
  @rate_limited("lookup") — wraps lightweight search routes (unchanged from existing)

Alert thresholds (env vars, USD/day):
  COST_WARN_THRESHOLD  — default $5.00  (WARNING logged, shown in dashboard)
  COST_KILL_THRESHOLD  — default $20.00 (kill switch auto-activates)
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from functools import wraps

from flask import abort, g, jsonify, request

logger = logging.getLogger(__name__)

# ── Pricing (claude-sonnet-4-20250514, as of 2025-05) ─────────────────────────
_INPUT_COST_PER_MTOK = float(os.environ.get("CLAUDE_INPUT_COST_PER_MTOK", "3.00"))
_OUTPUT_COST_PER_MTOK = float(os.environ.get("CLAUDE_OUTPUT_COST_PER_MTOK", "15.00"))

# ── Alert thresholds ───────────────────────────────────────────────────────────
COST_WARN_THRESHOLD = float(os.environ.get("COST_WARN_THRESHOLD", "5.00"))
COST_KILL_THRESHOLD = float(os.environ.get("COST_KILL_THRESHOLD", "20.00"))

# ── Kill switch ────────────────────────────────────────────────────────────────
# Runtime state: starts from env var, can be toggled via admin API.
_kill_switch_active: bool = os.environ.get("KILL_SWITCH_ENABLED", "").lower() in (
    "1", "true", "yes"
)


def is_kill_switch_active() -> bool:
    """Return True if the API kill switch is currently active."""
    return _kill_switch_active


def set_kill_switch(active: bool) -> None:
    """Toggle the kill switch at runtime (admin use only)."""
    global _kill_switch_active
    _kill_switch_active = active
    logger.warning(
        "Kill switch %s by admin", "ACTIVATED" if active else "deactivated"
    )


# ── Per-user in-memory rate buckets ───────────────────────────────────────────
# key: (user_id_or_ip, rate_type) → list of timestamps
_user_rate_buckets: dict[tuple, list[float]] = defaultdict(list)

# Rate limits per window (RATE_LIMIT_WINDOW seconds)
RATE_LIMIT_WINDOW = 60  # seconds

# Per-user limits (stricter than IP-level limits)
RATE_LIMITS = {
    "ai": int(os.environ.get("RATE_LIMIT_AI", "5")),           # AI synthesis calls
    "analyze": int(os.environ.get("RATE_LIMIT_ANALYZE", "10")),   # /analyze (tool calls)
    "lookup": int(os.environ.get("RATE_LIMIT_LOOKUP", "20")),     # /lookup, /search
    "plans": int(os.environ.get("RATE_LIMIT_PLANS", "3")),        # /analyze-plans (vision)
}


def _get_user_key() -> str:
    """Return user_id if logged in, else IP address for rate limiting."""
    if hasattr(g, "user") and g.user:
        return f"user:{g.user['user_id']}"
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    return f"ip:{ip.split(',')[0].strip()}"


def check_rate_limit(rate_type: str) -> bool:
    """Check if current user/IP is rate-limited for the given type.

    Returns True if rate-limited (request should be rejected).
    Adds current timestamp to bucket if not limited.
    """
    key = (_get_user_key(), rate_type)
    max_requests = RATE_LIMITS.get(rate_type, 10)
    now = time.monotonic()
    bucket = _user_rate_buckets[key]
    # Prune old entries
    _user_rate_buckets[key] = [t for t in bucket if now - t < RATE_LIMIT_WINDOW]
    if len(_user_rate_buckets[key]) >= max_requests:
        return True
    _user_rate_buckets[key].append(now)
    return False


def rate_limited(rate_type: str):
    """Decorator factory: check rate limit + kill switch before entering the view.

    Usage:
        @app.route("/ask", methods=["POST"])
        @rate_limited("ai")
        def ask():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Kill switch check (only blocks AI-heavy endpoints)
            if rate_type in ("ai", "plans", "analyze") and is_kill_switch_active():
                return (
                    '<div class="error rate-limit-error">'
                    "AI features are temporarily unavailable (cost protection). "
                    "Please try again later.</div>",
                    503,
                )
            # Rate limit check
            if check_rate_limit(rate_type):
                return (
                    '<div class="error rate-limit-error">'
                    "Rate limit exceeded. Please wait a minute.</div>",
                    429,
                )
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── Cost calculation ──────────────────────────────────────────────────────────

def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a Claude API call."""
    input_cost = (input_tokens / 1_000_000) * _INPUT_COST_PER_MTOK
    output_cost = (output_tokens / 1_000_000) * _OUTPUT_COST_PER_MTOK
    return round(input_cost + output_cost, 6)


# ── Database logging ──────────────────────────────────────────────────────────

def log_api_call(
    endpoint: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    user_id: int | None = None,
    extra: dict | None = None,
) -> None:
    """Log a Claude API call to api_usage table.

    Non-blocking: errors are caught and logged, never raised.

    Args:
        endpoint: Route that triggered the call (e.g. "/ask", "/analyze-plans").
        model: Model name (e.g. "claude-sonnet-4-20250514").
        input_tokens: Input token count from API response.
        output_tokens: Output token count from API response.
        user_id: Logged-in user ID, or None for anonymous.
        extra: Optional JSON-serializable dict for additional context.
    """
    try:
        cost_usd = estimate_cost_usd(input_tokens, output_tokens)
        extra_json = json.dumps(extra) if extra else None
        from src.db import execute_write
        # execute_write accepts %s placeholders and auto-converts for DuckDB
        sql = """
            INSERT INTO api_usage
                (user_id, endpoint, model, input_tokens, output_tokens, cost_usd, extra)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        execute_write(
            sql,
            (user_id, endpoint, model, input_tokens, output_tokens, cost_usd, extra_json),
        )
        # Check thresholds async (non-blocking)
        _check_cost_thresholds(cost_usd)
    except Exception as e:
        logger.warning("log_api_call failed (non-critical): %s", e)


def _check_cost_thresholds(latest_call_cost: float) -> None:
    """Check daily spend and activate kill switch if threshold exceeded."""
    try:
        today_cost = get_daily_global_cost()
        if today_cost >= COST_KILL_THRESHOLD:
            if not is_kill_switch_active():
                set_kill_switch(True)
                logger.critical(
                    "Kill switch AUTO-ACTIVATED: daily spend $%.4f >= threshold $%.2f",
                    today_cost,
                    COST_KILL_THRESHOLD,
                )
        elif today_cost >= COST_WARN_THRESHOLD:
            logger.warning(
                "Cost WARNING: daily spend $%.4f >= warn threshold $%.2f",
                today_cost,
                COST_WARN_THRESHOLD,
            )
    except Exception as e:
        logger.debug("_check_cost_thresholds failed (non-critical): %s", e)


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_daily_global_cost(target_date: date | None = None) -> float:
    """Return total USD cost for all API calls on the given date (default: today).

    Returns 0.0 if table does not exist or on error.
    """
    try:
        from src.db import query_one, BACKEND

        if target_date is None:
            target_date = date.today()
        date_str = target_date.isoformat()

        if BACKEND == "postgres":
            row = query_one(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM api_usage "
                "WHERE DATE(called_at) = %s",
                (date_str,),
            )
        else:
            row = query_one(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM api_usage "
                "WHERE DATE(called_at) = ?",
                (date_str,),
            )
        return float(row[0]) if row else 0.0
    except Exception as e:
        logger.debug("get_daily_global_cost failed: %s", e)
        return 0.0


def get_cost_summary(days: int = 7) -> dict:
    """Return cost summary for admin dashboard.

    Returns dict with:
      - today_cost: float
      - daily_totals: list of (date_str, cost) tuples for last N days
      - top_users: list of (user_id_or_anon, cost) tuples
      - top_endpoints: list of (endpoint, cost, call_count) tuples
      - kill_switch_active: bool
      - warn_threshold: float
      - kill_threshold: float
    """
    try:
        from src.db import query, BACKEND

        if BACKEND == "postgres":
            daily_sql = """
                SELECT DATE(called_at)::text, SUM(cost_usd)
                FROM api_usage
                WHERE called_at >= NOW() - INTERVAL '%s days'
                GROUP BY DATE(called_at)
                ORDER BY DATE(called_at) DESC
            """
            user_sql = """
                SELECT COALESCE(user_id::text, 'anon'), SUM(cost_usd)
                FROM api_usage
                WHERE DATE(called_at) = CURRENT_DATE
                GROUP BY user_id
                ORDER BY SUM(cost_usd) DESC
                LIMIT 10
            """
            endpoint_sql = """
                SELECT endpoint, SUM(cost_usd), COUNT(*)
                FROM api_usage
                WHERE DATE(called_at) = CURRENT_DATE
                GROUP BY endpoint
                ORDER BY SUM(cost_usd) DESC
            """
        else:
            daily_sql = """
                SELECT CAST(called_at AS DATE), SUM(cost_usd)
                FROM api_usage
                WHERE called_at >= NOW() - INTERVAL %s DAYS
                GROUP BY CAST(called_at AS DATE)
                ORDER BY CAST(called_at AS DATE) DESC
            """
            user_sql = """
                SELECT COALESCE(CAST(user_id AS VARCHAR), 'anon'), SUM(cost_usd)
                FROM api_usage
                WHERE CAST(called_at AS DATE) = CAST(NOW() AS DATE)
                GROUP BY user_id
                ORDER BY SUM(cost_usd) DESC
                LIMIT 10
            """
            endpoint_sql = """
                SELECT endpoint, SUM(cost_usd), COUNT(*)
                FROM api_usage
                WHERE CAST(called_at AS DATE) = CAST(NOW() AS DATE)
                GROUP BY endpoint
                ORDER BY SUM(cost_usd) DESC
            """

        # Postgres needs the interval substituted differently
        if BACKEND == "postgres":
            daily_rows = query(
                f"SELECT DATE(called_at)::text, SUM(cost_usd) "
                f"FROM api_usage "
                f"WHERE called_at >= NOW() - INTERVAL '{days} days' "
                f"GROUP BY DATE(called_at) "
                f"ORDER BY DATE(called_at) DESC"
            )
        else:
            daily_rows = query(
                f"SELECT CAST(called_at AS DATE), SUM(cost_usd) "
                f"FROM api_usage "
                f"WHERE called_at >= NOW() - INTERVAL {days} DAYS "
                f"GROUP BY CAST(called_at AS DATE) "
                f"ORDER BY CAST(called_at AS DATE) DESC"
            )

        user_rows = query(user_sql)
        endpoint_rows = query(endpoint_sql)

        today_cost = get_daily_global_cost()

        return {
            "today_cost": round(today_cost, 4),
            "daily_totals": [(str(r[0]), round(float(r[1]), 4)) for r in daily_rows],
            "top_users": [(str(r[0]), round(float(r[1]), 4)) for r in user_rows],
            "top_endpoints": [
                (r[0], round(float(r[1]), 4), int(r[2])) for r in endpoint_rows
            ],
            "kill_switch_active": is_kill_switch_active(),
            "warn_threshold": COST_WARN_THRESHOLD,
            "kill_threshold": COST_KILL_THRESHOLD,
        }
    except Exception as e:
        logger.warning("get_cost_summary failed: %s", e)
        return {
            "today_cost": 0.0,
            "daily_totals": [],
            "top_users": [],
            "top_endpoints": [],
            "kill_switch_active": is_kill_switch_active(),
            "warn_threshold": COST_WARN_THRESHOLD,
            "kill_threshold": COST_KILL_THRESHOLD,
            "error": str(e),
        }


def init_cost_tracking_schema() -> None:
    """Lazily create cost tracking tables for DuckDB dev mode.

    In Postgres, tables are created by scripts/migrate_cost_tracking.py.
    This function is called on first use to ensure tables exist in DuckDB.
    """
    from src.db import BACKEND, get_connection
    if BACKEND != "duckdb":
        return
    conn = get_connection()
    try:
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS api_usage_id_seq
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER DEFAULT nextval('api_usage_id_seq') PRIMARY KEY,
                user_id INTEGER,
                endpoint VARCHAR(100) NOT NULL,
                model VARCHAR(100) NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd DOUBLE NOT NULL DEFAULT 0.0,
                extra TEXT,
                called_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS api_daily_summary_id_seq
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_daily_summary (
                id INTEGER DEFAULT nextval('api_daily_summary_id_seq') PRIMARY KEY,
                summary_date DATE NOT NULL UNIQUE,
                total_calls INTEGER NOT NULL DEFAULT 0,
                total_cost_usd DOUBLE NOT NULL DEFAULT 0.0,
                breakdown_json TEXT,
                computed_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    finally:
        conn.close()


# ── Schema init on module load for DuckDB ────────────────────────────────────
_schema_initialized = False


def ensure_schema() -> None:
    """Ensure cost tracking tables exist (idempotent)."""
    global _schema_initialized
    if _schema_initialized:
        return
    try:
        init_cost_tracking_schema()
        _schema_initialized = True
    except Exception as e:
        logger.debug("ensure_schema failed (non-critical): %s", e)
