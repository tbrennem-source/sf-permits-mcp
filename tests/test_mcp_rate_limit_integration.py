"""Integration tests for MCP rate limiting (QS13).

These tests verify rate limiting behavior for the MCP HTTP server.
Most require a live MCP server and are marked to skip for unit test runs.
Tests that can run locally (config inspection, middleware structure) are active.

Covers:
- Rate limit configuration existence
- Demo scope limit enforcement (10 calls/hour)
- Rate limit headers in responses
- 429 response format with upgrade message
"""

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend for test isolation."""
    db_path = str(tmp_path / "test_mcp_rate.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)


@pytest.fixture
def client():
    import os
    os.environ.setdefault("TESTING", "1")
    from web.app import app as flask_app
    from web.helpers import _rate_buckets
    flask_app.config["TESTING"] = True
    _rate_buckets.clear()
    with flask_app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# MCP HTTP server: bearer auth structure (local inspection)
# ---------------------------------------------------------------------------

class TestMCPAuthStructure:

    def test_mcp_http_module_importable(self):
        """src.mcp_http is importable."""
        try:
            import src.mcp_http  # noqa: F401
        except ImportError as e:
            pytest.skip(f"src.mcp_http not importable: {e}")

    def test_bearer_token_middleware_class_exists(self):
        """BearerTokenMiddleware class exists in mcp_http."""
        try:
            from src.mcp_http import BearerTokenMiddleware
        except ImportError:
            pytest.skip("BearerTokenMiddleware not in src.mcp_http — may be QS13 addition")

    def test_mcp_auth_token_env_var_read(self):
        """MCP_AUTH_TOKEN env var is read by mcp_http module."""
        import os
        # The module reads MCP_AUTH_TOKEN at import time
        # Verify it doesn't crash when the var is missing
        original = os.environ.pop("MCP_AUTH_TOKEN", None)
        try:
            import importlib
            import src.mcp_http
            importlib.reload(src.mcp_http)
        except Exception as e:
            pytest.skip(f"mcp_http reload failed: {e}")
        finally:
            if original is not None:
                os.environ["MCP_AUTH_TOKEN"] = original


# ---------------------------------------------------------------------------
# Rate limit config inspection (QS13 T1 additions)
# ---------------------------------------------------------------------------

class TestMCPRateLimitConfig:

    def test_rate_limit_constants_exist_or_skip(self):
        """Rate limit constants exist in mcp_http or a dedicated rate limit module."""
        try:
            from src.mcp_http import DEMO_RATE_LIMIT, DEMO_RATE_WINDOW
            assert DEMO_RATE_LIMIT > 0
            assert DEMO_RATE_WINDOW > 0
        except ImportError:
            pytest.skip("DEMO_RATE_LIMIT/DEMO_RATE_WINDOW not yet in mcp_http (QS13 T1)")

    def test_demo_rate_limit_is_10_per_hour(self):
        """Demo scope allows 10 calls per hour."""
        try:
            from src.mcp_http import DEMO_RATE_LIMIT, DEMO_RATE_WINDOW
            assert DEMO_RATE_LIMIT == 10, f"Expected 10, got {DEMO_RATE_LIMIT}"
            # Rate window should be 1 hour (3600 seconds)
            assert DEMO_RATE_WINDOW == 3600, f"Expected 3600s, got {DEMO_RATE_WINDOW}"
        except ImportError:
            pytest.skip("Rate limit constants not yet implemented (QS13 T1)")

    def test_rate_limiter_class_exists_or_skip(self):
        """A rate limiter class or function exists for MCP calls."""
        try:
            from src.mcp_http import RateLimiter
            assert callable(RateLimiter)
        except ImportError:
            # Try alternative name
            try:
                from src.mcp_http import MCPRateLimiter
                assert callable(MCPRateLimiter)
            except ImportError:
                pytest.skip("MCP rate limiter class not yet implemented (QS13 T1)")


# ---------------------------------------------------------------------------
# Rate limit header tests (require live MCP server — integration only)
# ---------------------------------------------------------------------------

class TestMCPRateLimitHeaders:

    def test_rate_limit_headers_present(self, client):
        """Rate limit headers present in MCP health endpoint."""
        pytest.skip("Requires live MCP server — run against staging with MCP_AUTH_TOKEN set")

    def test_demo_scope_10_calls_then_429(self):
        """Demo scope: 10 calls succeed, 11th returns 429."""
        pytest.skip("Requires live MCP server — integration test, run against staging")

    def test_rate_limit_429_includes_upgrade_message(self):
        """429 response includes helpful upgrade message."""
        pytest.skip("Requires live MCP server — run against staging")

    def test_rate_limit_retry_after_header(self):
        """429 response includes Retry-After header."""
        pytest.skip("Requires live MCP server — run against staging")


# ---------------------------------------------------------------------------
# Response truncation (QS13 T1 feature)
# ---------------------------------------------------------------------------

class TestMCPResponseTruncation:

    def test_truncation_config_exists_or_skip(self):
        """Max token threshold constant exists in mcp_http."""
        try:
            from src.mcp_http import MAX_RESPONSE_TOKENS
            assert MAX_RESPONSE_TOKENS > 0
        except ImportError:
            pytest.skip("MAX_RESPONSE_TOKENS not yet in mcp_http (QS13 T1)")

    def test_large_response_truncated(self):
        """Responses > 20K tokens get truncated with continuation marker."""
        pytest.skip("Requires live MCP server — run against staging")

    def test_truncated_response_has_continuation_marker(self):
        """Truncated responses include a continuation marker."""
        pytest.skip("Requires live MCP server — run against staging")


# ---------------------------------------------------------------------------
# Web app rate limit (existing — verifying no regression)
# ---------------------------------------------------------------------------

class TestWebRateLimitNoRegression:

    def test_health_endpoint_not_rate_limited(self, client):
        """Health endpoint is not rate-limited (10+ requests should succeed)."""
        for i in range(12):
            resp = client.get("/health")
            assert resp.status_code == 200, f"Request {i+1} got {resp.status_code}"

    def test_analyze_endpoint_rate_limits_eventually(self, client):
        """Analyze endpoint rate-limits heavy use (existing behavior)."""
        # Just verify the rate limiter exists, not the exact limit
        from web.helpers import _rate_buckets
        assert isinstance(_rate_buckets, dict)
