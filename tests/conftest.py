"""Root-level test conftest — fixtures shared across all test files.

Prevents cross-file contamination from in-memory state (rate buckets,
daily limit cache, etc.) that persists between test files in the same
pytest session.
"""
import pytest


@pytest.fixture(autouse=True)
def _clear_rate_state():
    """Clear rate limiter buckets and daily cache before each test.

    Without this, rate limit counters from one test file bleed into
    the next, causing 429 responses in tests that don't expect them.
    """
    try:
        from web.helpers import _rate_buckets
        _rate_buckets.clear()
    except (ImportError, Exception):
        pass

    try:
        from web.security import _daily_cache
        _daily_cache.clear()
    except (ImportError, Exception):
        pass

    yield

    # Also clear after, in case test intentionally triggered limits
    try:
        from web.helpers import _rate_buckets
        _rate_buckets.clear()
    except (ImportError, Exception):
        pass

    try:
        from web.security import _daily_cache
        _daily_cache.clear()
    except (ImportError, Exception):
        pass
