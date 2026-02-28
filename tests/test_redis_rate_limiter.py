"""Tests for the Redis-backed rate limiter in web/helpers.py.

All Redis interactions use fakeredis so no real Redis connection is required.
The in-memory fallback is tested by patching _get_redis_client to return None.
"""

import time

import fakeredis
import pytest
from unittest.mock import patch

import web.helpers as helpers_module
from web.helpers import check_rate_limit, _is_rate_limited, _rate_buckets, RATE_LIMIT_WINDOW


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_fake_redis():
    """Return a fakeredis.FakeRedis instance that is pre-pinged (ready to use)."""
    return fakeredis.FakeRedis()


def _reset_memory_buckets():
    """Clear the in-memory _rate_buckets dict between tests."""
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# Redis-backed tests
# ---------------------------------------------------------------------------

class TestRedisRateLimiter:
    """Tests that exercise the Redis code path via fakeredis."""

    def test_redis_rate_limit_counts_requests(self):
        """Each call increments the counter; requests within limit are allowed."""
        fake = _fresh_fake_redis()
        with patch("web.helpers._get_redis_client", return_value=fake):
            key = "rl:test:count"
            limit = 5
            window = 60

            results = [check_rate_limit(key, limit, window) for _ in range(5)]

        assert all(results), "All 5 requests should be allowed"

    def test_redis_rate_limit_blocks_over_threshold(self):
        """The (limit + 1)th request must be blocked."""
        fake = _fresh_fake_redis()
        with patch("web.helpers._get_redis_client", return_value=fake):
            key = "rl:test:block"
            limit = 3
            window = 60

            for _ in range(limit):
                assert check_rate_limit(key, limit, window) is True

            # This one is over the threshold
            assert check_rate_limit(key, limit, window) is False, (
                "Request beyond limit should be blocked"
            )

    def test_redis_rate_limit_resets_after_window(self):
        """After the TTL expires, the counter resets and requests are allowed again."""
        fake = _fresh_fake_redis()
        with patch("web.helpers._get_redis_client", return_value=fake):
            key = "rl:test:expire"
            limit = 2
            # Use a 1-second window so we can simulate expiry quickly
            window = 1

            # Fill the bucket
            for _ in range(limit):
                check_rate_limit(key, limit, window)

            # Verify it's blocked
            assert check_rate_limit(key, limit, window) is False

            # Manually expire the key in fakeredis to simulate TTL passing
            fake.delete(key)

            # Now requests should be allowed again
            assert check_rate_limit(key, limit, window) is True, (
                "After window expires (key deleted), requests should be allowed"
            )

    def test_redis_pipeline_executes_both_incr_and_expire(self):
        """Each allowed request must set a TTL so the key auto-expires."""
        fake = _fresh_fake_redis()
        with patch("web.helpers._get_redis_client", return_value=fake):
            key = "rl:test:ttl"
            check_rate_limit(key, 10, 60)

        ttl = fake.ttl(key)
        assert ttl > 0, f"Key should have a positive TTL, got {ttl}"


# ---------------------------------------------------------------------------
# In-memory fallback tests
# ---------------------------------------------------------------------------

class TestInMemoryFallback:
    """Tests that exercise the in-memory path when Redis is not available."""

    def setup_method(self):
        _reset_memory_buckets()

    def teardown_method(self):
        _reset_memory_buckets()

    def test_fallback_to_memory_when_no_redis(self):
        """When _get_redis_client returns None, the in-memory path is used."""
        with patch("web.helpers._get_redis_client", return_value=None):
            key = "rl:mem:basic"
            limit = 3
            window = 60

            results = [check_rate_limit(key, limit, window) for _ in range(3)]
            assert all(results), "All requests within limit should be allowed"

            # 4th request should be blocked
            assert check_rate_limit(key, limit, window) is False

    def test_fallback_to_memory_when_redis_down(self):
        """When the Redis pipeline raises an exception, fall back to in-memory."""
        class BrokenRedis:
            def pipeline(self):
                raise ConnectionError("Redis connection refused")

        with patch("web.helpers._get_redis_client", return_value=BrokenRedis()):
            key = "rl:mem:broken"
            limit = 5
            window = 60

            # Should not raise; should use in-memory instead
            result = check_rate_limit(key, limit, window)
            assert result is True, "First request should be allowed via in-memory fallback"

    def test_in_memory_counts_correctly(self):
        """In-memory bucket accumulates counts and blocks at the limit."""
        with patch("web.helpers._get_redis_client", return_value=None):
            key = "rl:mem:counts"
            limit = 4
            window = 60

            for i in range(limit):
                assert check_rate_limit(key, limit, window) is True, (
                    f"Request {i + 1} should be allowed"
                )
            assert check_rate_limit(key, limit, window) is False, (
                "Request beyond limit should be blocked"
            )


# ---------------------------------------------------------------------------
# _is_rate_limited backward-compatibility tests
# ---------------------------------------------------------------------------

class TestIsRateLimited:
    """Verify the public _is_rate_limited function still works correctly."""

    def setup_method(self):
        _reset_memory_buckets()

    def teardown_method(self):
        _reset_memory_buckets()

    def test_is_rate_limited_returns_false_when_under_limit(self):
        """_is_rate_limited returns False (= not limited) when under the max."""
        with patch("web.helpers._get_redis_client", return_value=None):
            ip = "10.0.0.1"
            assert _is_rate_limited(ip, 5) is False

    def test_is_rate_limited_returns_true_when_over_limit(self):
        """_is_rate_limited returns True (= limited) after exceeding max_requests."""
        with patch("web.helpers._get_redis_client", return_value=None):
            ip = "10.0.0.2"
            limit = 3
            for _ in range(limit):
                _is_rate_limited(ip, limit)
            # Next call should be rate limited
            assert _is_rate_limited(ip, limit) is True

    def test_is_rate_limited_uses_redis_when_available(self):
        """_is_rate_limited delegates to Redis when a client is returned."""
        fake = _fresh_fake_redis()
        with patch("web.helpers._get_redis_client", return_value=fake):
            ip = "10.0.0.3"
            limit = 2
            # First two requests allowed
            assert _is_rate_limited(ip, limit) is False
            assert _is_rate_limited(ip, limit) is False
            # Third should be limited
            assert _is_rate_limited(ip, limit) is True
