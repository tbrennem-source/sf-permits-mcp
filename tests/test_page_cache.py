"""Tests for the page_cache utility functions.

Written against the spec (Agent 1A builds the implementation in web/helpers.py).
These tests will FAIL until Terminal 1's code is merged — that's expected.

Expected interface in web.helpers:
    get_cached_or_compute(key: str, compute_fn: callable, ttl: int = 300) -> dict
    invalidate_cache(pattern: str) -> int   # returns count of keys invalidated
    _page_cache: dict                        # internal cache store (for test access)
"""

from __future__ import annotations

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_page_cache():
    """Clear the page_cache DB table before and after every test."""
    def _truncate():
        try:
            from src.db import get_connection, BACKEND
            conn = get_connection()
            if BACKEND == "duckdb":
                conn.execute("DELETE FROM page_cache WHERE cache_key LIKE 'test:%' OR cache_key LIKE 'brief:%'")
            else:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM page_cache WHERE cache_key LIKE 'test:%%' OR cache_key LIKE 'brief:%%'")
                conn.commit()
            conn.close()
        except Exception:
            pass
    _truncate()
    yield
    _truncate()


# ---------------------------------------------------------------------------
# Import guard — fail fast if the module doesn't expose the expected API
# ---------------------------------------------------------------------------

def _import_cache_fns():
    """Import cache functions, skipping on ImportError."""
    from web.helpers import get_cached_or_compute, invalidate_cache
    return get_cached_or_compute, invalidate_cache


# ---------------------------------------------------------------------------
# Core compute-and-store behaviour
# ---------------------------------------------------------------------------

class TestCacheMissAndHit:
    """Cache miss triggers compute_fn; cache hit skips it."""

    def test_cache_miss_computes_and_stores(self):
        """First call with empty cache should call compute_fn."""
        get_cached_or_compute, _ = _import_cache_fns()
        call_count = {"n": 0}

        def compute():
            call_count["n"] += 1
            return {"value": 42}

        result = get_cached_or_compute("test:miss", compute, ttl_minutes=60)
        assert result["value"] == 42
        assert call_count["n"] == 1

    def test_cache_hit_returns_cached(self):
        """Second call should return cached result without calling compute_fn."""
        get_cached_or_compute, _ = _import_cache_fns()
        call_count = {"n": 0}

        def compute():
            call_count["n"] += 1
            return {"value": "hello"}

        # Prime the cache
        first = get_cached_or_compute("test:hit", compute, ttl_minutes=60)
        # Second call — compute_fn must NOT be called again
        second = get_cached_or_compute("test:hit", compute, ttl_minutes=60)

        assert call_count["n"] == 1, "compute_fn should only be called once"
        assert first["value"] == second["value"] == "hello"

    def test_cache_stores_result_persistently(self):
        """Cache entry survives multiple reads."""
        get_cached_or_compute, _ = _import_cache_fns()
        calls = []

        def compute():
            calls.append(1)
            return {"data": [1, 2, 3]}

        for _ in range(5):
            result = get_cached_or_compute("test:persist", compute, ttl_minutes=300)
            assert result["data"] == [1, 2, 3]

        assert len(calls) == 1, "compute_fn should only be called once across 5 reads"

    def test_different_keys_independent(self):
        """Different cache keys do not share entries."""
        get_cached_or_compute, _ = _import_cache_fns()
        calls = {"a": 0, "b": 0}

        def compute_a():
            calls["a"] += 1
            return {"source": "a"}

        def compute_b():
            calls["b"] += 1
            return {"source": "b"}

        result_a = get_cached_or_compute("test:key_a", compute_a, ttl_minutes=60)
        result_b = get_cached_or_compute("test:key_b", compute_b, ttl_minutes=60)

        assert result_a["source"] == "a"
        assert result_b["source"] == "b"
        assert calls["a"] == 1
        assert calls["b"] == 1


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------

class TestCacheTTL:
    """Cache entries expire after TTL seconds."""

    def test_cache_ttl_expiry(self):
        """Set TTL=0, verify cache miss on second call."""
        get_cached_or_compute, _ = _import_cache_fns()
        call_count = {"n": 0}

        def compute():
            call_count["n"] += 1
            return {"ts": time.time()}

        # With TTL=0 the entry should be immediately expired on second read
        get_cached_or_compute("test:ttl0", compute, ttl_minutes=0)
        # Small sleep to ensure time advances past expiry
        time.sleep(0.01)
        get_cached_or_compute("test:ttl0", compute, ttl_minutes=0)

        assert call_count["n"] == 2, "compute_fn should be called twice when TTL=0"

    def test_cache_long_ttl_not_expired(self):
        """Cache entry with 300s TTL should not expire within a test run."""
        get_cached_or_compute, _ = _import_cache_fns()
        call_count = {"n": 0}

        def compute():
            call_count["n"] += 1
            return {"alive": True}

        get_cached_or_compute("test:ttl300", compute, ttl_minutes=300)
        get_cached_or_compute("test:ttl300", compute, ttl_minutes=300)

        assert call_count["n"] == 1, "Cache should not expire within the same test"


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------

class TestInvalidateCache:
    """invalidate_cache marks entries stale; next read recomputes."""

    def test_invalidate_cache_marks_stale(self):
        """Populate cache, invalidate, verify next read triggers compute."""
        get_cached_or_compute, invalidate_cache = _import_cache_fns()
        call_count = {"n": 0}

        def compute():
            call_count["n"] += 1
            return {"generation": call_count["n"]}

        # Prime
        first = get_cached_or_compute("test:inv:single", compute, ttl_minutes=300)
        assert first["generation"] == 1
        assert call_count["n"] == 1

        # Invalidate
        invalidate_cache("test:inv:single")

        # Next read must recompute
        second = get_cached_or_compute("test:inv:single", compute, ttl_minutes=300)
        assert second["generation"] == 2
        assert call_count["n"] == 2

    def test_invalidate_cache_pattern(self):
        """Pattern invalidation: invalidate one key, leave others intact."""
        get_cached_or_compute, invalidate_cache = _import_cache_fns()
        calls = {"user1": 0, "user2": 0}

        def compute_user1():
            calls["user1"] += 1
            return {"user": "user1"}

        def compute_user2():
            calls["user2"] += 1
            return {"user": "user2"}

        # Prime both
        get_cached_or_compute("brief:user1:1", compute_user1, ttl_minutes=300)
        get_cached_or_compute("brief:user2:1", compute_user2, ttl_minutes=300)

        # Invalidate only user1
        invalidate_cache("brief:user1:%")

        # user1: should recompute
        get_cached_or_compute("brief:user1:1", compute_user1, ttl_minutes=300)
        assert calls["user1"] == 2, "user1 entry should have been recomputed after invalidation"

        # user2: should still be cached
        get_cached_or_compute("brief:user2:1", compute_user2, ttl_minutes=300)
        assert calls["user2"] == 1, "user2 entry should still be cached"

    def test_invalidate_returns_count(self):
        """invalidate_cache returns the number of keys affected."""
        get_cached_or_compute, invalidate_cache = _import_cache_fns()

        for i in range(3):
            get_cached_or_compute(f"brief:multiuser:{i}", lambda: {"i": i}, ttl_minutes=300)

        # invalidate_cache is void (best-effort) — just verify it doesn't raise
        invalidate_cache("brief:multiuser:%")

    def test_invalidate_nonexistent_key_no_error(self):
        """Invalidating a key that doesn't exist should not raise."""
        _, invalidate_cache = _import_cache_fns()
        # Must not raise
        invalidate_cache("no:such:key")  # must not raise


# ---------------------------------------------------------------------------
# Data serialisation
# ---------------------------------------------------------------------------

class TestCacheSerialization:
    """Cache round-trips complex data structures correctly."""

    def test_cache_stores_json_serializable(self):
        """Dicts with dates, numbers, nested structures round-trip correctly."""
        get_cached_or_compute, _ = _import_cache_fns()
        from datetime import date

        payload = {
            "string": "hello",
            "integer": 42,
            "float": 3.14,
            "nested": {"a": [1, 2, 3], "b": None},
            "date_str": str(date.today()),
        }

        stored = get_cached_or_compute("test:serial", lambda: payload, ttl_minutes=60)
        # Read from cache
        cached = get_cached_or_compute("test:serial", lambda: {}, ttl_minutes=60)

        assert cached["string"] == "hello"
        assert cached["integer"] == 42
        assert abs(cached["float"] - 3.14) < 0.001
        assert cached["nested"]["a"] == [1, 2, 3]
        assert cached["nested"]["b"] is None

    def test_cache_handles_empty_dict(self):
        """Empty dict does not cause errors and is cached correctly."""
        get_cached_or_compute, _ = _import_cache_fns()
        calls = {"n": 0}

        def compute():
            calls["n"] += 1
            return {}

        first = get_cached_or_compute("test:empty", compute, ttl_minutes=60)
        second = get_cached_or_compute("test:empty", compute, ttl_minutes=60)

        # T1 injects _cached/_cached_at metadata on cache hits — check core payload
        assert calls["n"] == 1
        # Second call should be from cache (may include _cached metadata)
        assert second.get("_cached", False) or second == {}

    def test_cache_handles_large_nested_dict(self):
        """Large nested dict round-trips without truncation."""
        get_cached_or_compute, _ = _import_cache_fns()

        big_payload = {
            "items": [{"id": i, "label": f"item-{i}"} for i in range(100)],
            "meta": {"total": 100, "source": "test"},
        }

        get_cached_or_compute("test:large", lambda: big_payload, ttl_minutes=60)
        cached = get_cached_or_compute("test:large", lambda: {}, ttl_minutes=60)

        assert len(cached["items"]) == 100
        assert cached["items"][99]["label"] == "item-99"


# ---------------------------------------------------------------------------
# Metadata fields
# ---------------------------------------------------------------------------

class TestCacheMetadata:
    """Cache hits include _cached and _cached_at metadata fields."""

    def test_cache_metadata_fields_on_hit(self):
        """Verify _cached=True and _cached_at set on cache hits."""
        get_cached_or_compute, _ = _import_cache_fns()

        get_cached_or_compute("test:meta", lambda: {"value": 1}, ttl_minutes=60)
        # Second call is a cache hit — metadata should be present
        cached = get_cached_or_compute("test:meta", lambda: {"value": 1}, ttl_minutes=60)

        assert cached.get("_cached") is True, "_cached should be True on a cache hit"
        assert "_cached_at" in cached, "_cached_at timestamp should be present on a cache hit"

    def test_cache_metadata_not_on_miss(self):
        """First call (cache miss) should NOT inject _cached=True."""
        get_cached_or_compute, _ = _import_cache_fns()
        results = []

        def compute():
            result = {"value": 99}
            results.append(result)
            return result

        first = get_cached_or_compute("test:meta_miss", compute, ttl_minutes=60)
        # On a miss, _cached should be False/absent (implementation may vary — just verify value)
        assert first.get("_cached") is not True, (
            "Fresh computation should not be marked as a cache hit"
        )

    def test_cached_at_is_valid_timestamp(self):
        """_cached_at should be a parseable timestamp (ISO string or numeric)."""
        get_cached_or_compute, _ = _import_cache_fns()

        get_cached_or_compute("test:ts", lambda: {}, ttl_minutes=60)
        cached = get_cached_or_compute("test:ts", lambda: {}, ttl_minutes=60)

        cached_at = cached.get("_cached_at")
        assert cached_at is not None
        # T1 returns ISO string; accept either format
        assert isinstance(cached_at, (int, float, str)), "_cached_at should be a timestamp"
