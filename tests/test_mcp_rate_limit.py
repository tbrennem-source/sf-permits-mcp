import pytest
from unittest.mock import patch


def test_demo_allows_10_calls():
    from src.mcp_rate_limiter import RateLimiter
    rl = RateLimiter()
    for i in range(10):
        allowed, headers = rl.check_and_increment("test-token", "demo")
        assert allowed, f"Call {i+1} should be allowed"
    # 11th call blocked
    allowed, headers = rl.check_and_increment("test-token", "demo")
    assert not allowed
    assert headers["X-RateLimit-Remaining"] == "0"


def test_anonymous_allows_5_calls():
    from src.mcp_rate_limiter import RateLimiter
    rl = RateLimiter()
    for i in range(5):
        allowed, _ = rl.check_and_increment("ip:1.2.3.4", None)
        assert allowed
    allowed, _ = rl.check_and_increment("ip:1.2.3.4", None)
    assert not allowed


def test_unlimited_never_blocks():
    from src.mcp_rate_limiter import RateLimiter
    rl = RateLimiter()
    for i in range(10000):
        allowed, headers = rl.check_and_increment("power-user", "unlimited")
        assert allowed
    assert "unlimited" in headers.get("X-RateLimit-Limit", "").lower()


def test_rate_limit_reset_on_new_window():
    """Simulate reset by injecting expired bucket."""
    import time
    from src.mcp_rate_limiter import RateLimiter
    rl = RateLimiter()
    # Fill up the bucket
    for _ in range(10):
        rl.check_and_increment("test-key", "demo")
    # Manually expire the bucket
    rl._buckets["test-key"]["reset_at"] = time.time() - 1
    # Next call should reset and allow
    allowed, headers = rl.check_and_increment("test-key", "demo")
    assert allowed
    assert headers["X-RateLimit-Remaining"] == "9"


def test_response_truncation():
    from src.mcp_rate_limiter import truncate_if_needed, TRUNCATION_SUFFIX
    short = "hello world"
    assert truncate_if_needed(short) == short
    # Create text that exceeds 20K tokens (~80K chars)
    long_text = "x" * 100_000
    result = truncate_if_needed(long_text)
    assert result.endswith(TRUNCATION_SUFFIX)
    assert len(result) < len(long_text)


def test_rate_limit_headers_present():
    from src.mcp_rate_limiter import RateLimiter
    rl = RateLimiter()
    allowed, headers = rl.check_and_increment("test", "demo")
    assert "X-RateLimit-Limit" in headers
    assert "X-RateLimit-Remaining" in headers
    assert "X-RateLimit-Reset" in headers


def test_professional_allows_1000():
    from src.mcp_rate_limiter import RateLimiter
    rl = RateLimiter()
    for i in range(1000):
        allowed, _ = rl.check_and_increment("pro-token", "professional")
        assert allowed, f"Call {i+1} should be allowed"
    allowed, _ = rl.check_and_increment("pro-token", "professional")
    assert not allowed
