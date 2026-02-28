"""Tests for QS8-T1-D: Cache-Control headers, response timing, pool health endpoint.

Covers:
  - Cache-Control: public, max-age=3600, stale-while-revalidate=86400 on static pages
  - X-Response-Time header on every response
  - /health includes pool_stats and cache_stats
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with isolated temp database."""
    db_path = str(tmp_path / "test_sprint_79_d.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# Task D-1: Cache-Control on static content pages
# ---------------------------------------------------------------------------


def test_methodology_has_cache_control(client):
    """GET /methodology returns Cache-Control: public, max-age=3600, stale-while-revalidate=86400."""
    rv = client.get("/methodology")
    assert rv.status_code == 200
    cc = rv.headers.get("Cache-Control", "")
    assert "public" in cc, f"Expected 'public' in Cache-Control, got: {cc!r}"
    assert "max-age=3600" in cc, f"Expected 'max-age=3600' in Cache-Control, got: {cc!r}"
    assert "stale-while-revalidate=86400" in cc, (
        f"Expected 'stale-while-revalidate=86400' in Cache-Control, got: {cc!r}"
    )


def test_about_data_has_cache_control(client):
    """GET /about-data returns Cache-Control: public, max-age=3600, stale-while-revalidate=86400."""
    rv = client.get("/about-data")
    assert rv.status_code == 200
    cc = rv.headers.get("Cache-Control", "")
    assert "public" in cc, f"Expected 'public' in Cache-Control, got: {cc!r}"
    assert "max-age=3600" in cc, f"Expected 'max-age=3600' in Cache-Control, got: {cc!r}"
    assert "stale-while-revalidate=86400" in cc, (
        f"Expected 'stale-while-revalidate=86400' in Cache-Control, got: {cc!r}"
    )


def test_demo_has_cache_control(client):
    """GET /demo returns Cache-Control: public, max-age=3600, stale-while-revalidate=86400."""
    rv = client.get("/demo")
    assert rv.status_code == 200
    cc = rv.headers.get("Cache-Control", "")
    assert "public" in cc, f"Expected 'public' in Cache-Control, got: {cc!r}"
    assert "max-age=3600" in cc, f"Expected 'max-age=3600' in Cache-Control, got: {cc!r}"
    assert "stale-while-revalidate=86400" in cc, (
        f"Expected 'stale-while-revalidate=86400' in Cache-Control, got: {cc!r}"
    )


def test_non_static_page_no_cache_control(client):
    """Auth page should NOT receive the static-page Cache-Control header."""
    rv = client.get("/auth/login")
    assert rv.status_code == 200
    cc = rv.headers.get("Cache-Control", "")
    # Should not have the aggressive public cache directive
    assert "max-age=3600" not in cc, (
        f"Auth page should not have max-age=3600 cache header, got: {cc!r}"
    )


# ---------------------------------------------------------------------------
# Task D-2: X-Response-Time header on every response
# ---------------------------------------------------------------------------


def test_response_timing_header_present(client):
    """Every response includes X-Response-Time header with milliseconds value."""
    rv = client.get("/methodology")
    assert rv.status_code == 200
    timing = rv.headers.get("X-Response-Time")
    assert timing is not None, "X-Response-Time header missing from response"
    assert timing.endswith("ms"), f"X-Response-Time should end with 'ms', got: {timing!r}"
    # Value should be a valid float before 'ms'
    ms_value = timing[:-2]
    try:
        elapsed = float(ms_value)
    except ValueError:
        pytest.fail(f"X-Response-Time value {timing!r} is not a valid float+ms")
    assert elapsed >= 0, f"Response time should be non-negative, got: {elapsed}"


def test_response_timing_header_on_health(client):
    """X-Response-Time is also present on /health endpoint."""
    rv = client.get("/health")
    timing = rv.headers.get("X-Response-Time")
    assert timing is not None, "X-Response-Time header missing from /health response"
    assert timing.endswith("ms"), f"X-Response-Time should end with 'ms', got: {timing!r}"


def test_response_timing_header_on_404(client):
    """X-Response-Time is present even on 404 responses."""
    rv = client.get("/nonexistent-page-xyz-abc")
    timing = rv.headers.get("X-Response-Time")
    assert timing is not None, "X-Response-Time header missing from 404 response"


# ---------------------------------------------------------------------------
# Task D-3: /health includes pool_stats and cache_stats
# ---------------------------------------------------------------------------


def test_health_includes_pool_stats(client):
    """GET /health response JSON includes pool_stats field."""
    import json
    rv = client.get("/health")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert "pool_stats" in data or "pool" in data, (
        f"Expected pool_stats or pool in /health response, keys: {list(data.keys())}"
    )
    # pool_stats should have backend info
    pool_info = data.get("pool_stats") or data.get("pool") or {}
    assert "backend" in pool_info or "status" in pool_info, (
        f"pool_stats missing backend/status key, got: {pool_info}"
    )


def test_health_includes_cache_stats(client):
    """GET /health response JSON includes cache_stats field."""
    import json
    rv = client.get("/health")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert "cache_stats" in data, (
        f"Expected cache_stats in /health response, keys: {list(data.keys())}"
    )
    cache_info = data["cache_stats"]
    assert isinstance(cache_info, dict), f"cache_stats should be a dict, got: {type(cache_info)}"
    # Should have backend or error key
    assert "backend" in cache_info or "error" in cache_info, (
        f"cache_stats missing backend/error key, got: {cache_info}"
    )


def test_health_cache_stats_has_row_count(client):
    """cache_stats in /health includes row_count for page_cache."""
    import json
    rv = client.get("/health")
    data = json.loads(rv.data)
    cache_info = data.get("cache_stats", {})
    # If no error, should have row_count
    if "error" not in cache_info:
        assert "row_count" in cache_info, (
            f"cache_stats should have row_count, got: {cache_info}"
        )
        assert isinstance(cache_info["row_count"], int), (
            f"row_count should be int, got: {type(cache_info['row_count'])}"
        )
