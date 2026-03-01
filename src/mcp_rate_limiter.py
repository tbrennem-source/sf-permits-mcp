"""In-memory per-token rate limiter for MCP server.

Tiers (from oauth_models.SCOPE_RATE_LIMITS):
  None / anonymous: 5 calls/day (by IP)
  demo: 10 calls/day
  professional: 1,000 calls/day
  unlimited: no limit

Resets at midnight UTC.
"""
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Optional


class RateLimiter:
    def __init__(self):
        self._lock = Lock()
        # key -> {"count": int, "reset_at": float (unix timestamp)}
        self._buckets: dict[str, dict] = {}

    def _reset_ts(self) -> float:
        """Next midnight UTC as unix timestamp."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # If it's past midnight already today, next reset is tomorrow midnight
        if now >= midnight:
            midnight = midnight + timedelta(days=1)
        return midnight.timestamp()

    def _get_limit(self, scope: Optional[str]) -> Optional[int]:
        from src.oauth_models import SCOPE_RATE_LIMITS
        return SCOPE_RATE_LIMITS.get(scope, SCOPE_RATE_LIMITS[None])

    def check_and_increment(self, key: str, scope: Optional[str]) -> tuple[bool, dict]:
        """
        Returns (allowed: bool, headers: dict).
        headers contains X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset.
        """
        limit = self._get_limit(scope)
        if limit is None:
            return True, {"X-RateLimit-Limit": "unlimited"}

        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or now >= bucket["reset_at"]:
                reset_at = self._reset_ts()
                bucket = {"count": 0, "reset_at": reset_at}
                self._buckets[key] = bucket

            remaining = max(0, limit - bucket["count"])
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(bucket["reset_at"])),
            }

            if bucket["count"] >= limit:
                return False, headers

            bucket["count"] += 1
            headers["X-RateLimit-Remaining"] = str(remaining - 1)
            return True, headers

    def cleanup_expired(self):
        """Remove expired buckets (call periodically if needed)."""
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._buckets.items() if now >= v["reset_at"]]
            for k in expired:
                del self._buckets[k]


# Singleton
_limiter = RateLimiter()


def get_limiter() -> RateLimiter:
    return _limiter


# ── Response truncation ────────────────────────────────────────────

RESPONSE_TOKEN_LIMIT = 20_000
TRUNCATION_SUFFIX = "\n\n[Response truncated. Use more specific filters to narrow results.]"


def truncate_if_needed(text: str) -> str:
    """Truncate response if estimated token count exceeds limit."""
    estimated_tokens = len(text) / 4
    if estimated_tokens > RESPONSE_TOKEN_LIMIT:
        # Find a good cut point
        max_chars = RESPONSE_TOKEN_LIMIT * 4 - len(TRUNCATION_SUFFIX)
        return text[:max_chars] + TRUNCATION_SUFFIX
    return text
