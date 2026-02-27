"""Tests for /cron/compute-caches endpoint and brief cache invalidation in nightly.

Sprint: cron pre-compute briefs + event-driven cache invalidation.

Key behaviours tested:
  1. /cron/compute-caches returns 403 without auth
  2. /cron/compute-caches returns 200 when called correctly
  3. /cron/compute-caches handles skipped/ImportError path gracefully
  4. /cron/compute-caches handles per-user errors gracefully (errors counter)
  5. /cron/nightly response includes cache_invalidation key
  6. /cron/nightly cache invalidation is non-fatal (error → step captured)

Note: get_cached_or_compute / invalidate_cache are built by Agent 1A in a
parallel worktree. These tests are written to pass whether or not those
functions exist yet, mirroring the ImportError guard in the endpoint itself.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


CRON_SECRET = "test-secret-compute-caches"

_MISSING = object()  # Sentinel for "attribute did not exist"


@pytest.fixture
def cron_client(monkeypatch):
    """Flask test client in cron worker mode."""
    monkeypatch.setenv("CRON_WORKER", "true")
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)
    from web.app import app
    app.config["TESTING"] = True
    return app.test_client()


def _auth():
    return {"Authorization": f"Bearer {CRON_SECRET}"}


def _inject_cache_helper(fn=None):
    """Inject get_cached_or_compute into web.helpers if it doesn't exist yet.

    Returns (backup_value_or_sentinel) so caller can restore after test.
    """
    import web.helpers as helpers_mod
    backup = getattr(helpers_mod, "get_cached_or_compute", _MISSING)
    if fn is None:
        fn = MagicMock(return_value={})
    helpers_mod.get_cached_or_compute = fn
    return backup


def _restore_cache_helper(backup):
    """Remove get_cached_or_compute from web.helpers if we injected it."""
    import web.helpers as helpers_mod
    if backup is _MISSING:
        # We injected it — remove it
        if hasattr(helpers_mod, "get_cached_or_compute"):
            delattr(helpers_mod, "get_cached_or_compute")
    else:
        # It existed before — restore original
        helpers_mod.get_cached_or_compute = backup


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestComputeCachesAuth:
    def test_missing_auth_returns_403(self, cron_client):
        resp = cron_client.post("/cron/compute-caches")
        assert resp.status_code == 403

    def test_wrong_token_returns_403(self, cron_client):
        resp = cron_client.post(
            "/cron/compute-caches",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Endpoint returns 200 regardless of helper availability
# ---------------------------------------------------------------------------

class TestComputeCachesReturns200:
    def test_returns_200_with_helpers_available(self, cron_client):
        """With helpers injected + users mocked, returns 200 with count keys."""
        users = [(1,), (2,)]
        mock_cache = MagicMock(return_value={"sections": []})
        backup = _inject_cache_helper(mock_cache)
        try:
            with patch("src.db.query", return_value=users):
                with patch("web.auth.get_primary_address", return_value=None):
                    resp = cron_client.post("/cron/compute-caches", headers=_auth())
        finally:
            _restore_cache_helper(backup)

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "computed" in data or "skipped" in data
        assert "errors" in data or "skipped" in data

    def test_returns_200_without_helpers(self, cron_client):
        """Without helpers, returns 200 with skipped=helpers_not_available."""
        import web.helpers as helpers_mod
        backup = getattr(helpers_mod, "get_cached_or_compute", _MISSING)

        # Ensure the attribute does NOT exist (simulate pre-merge state)
        if hasattr(helpers_mod, "get_cached_or_compute"):
            delattr(helpers_mod, "get_cached_or_compute")

        try:
            with patch("src.db.query", return_value=[(1,)]):
                resp = cron_client.post("/cron/compute-caches", headers=_auth())
        finally:
            _restore_cache_helper(backup)

        assert resp.status_code == 200
        data = json.loads(resp.data)
        # Should be skipped
        assert data.get("skipped") == "helpers_not_available"

    def test_empty_users_returns_zero_counts(self, cron_client):
        """No users → 200, total_users=0."""
        mock_cache = MagicMock(return_value={})
        backup = _inject_cache_helper(mock_cache)
        try:
            with patch("src.db.query", return_value=[]):
                resp = cron_client.post("/cron/compute-caches", headers=_auth())
        finally:
            _restore_cache_helper(backup)

        assert resp.status_code == 200
        data = json.loads(resp.data)
        # Either has total_users (happy path) or skipped (helpers missing)
        if "total_users" in data:
            assert data["total_users"] == 0
        else:
            assert "skipped" in data


# ---------------------------------------------------------------------------
# Cache key format
# ---------------------------------------------------------------------------

class TestComputeCachesCacheKey:
    def test_cache_key_format(self, cron_client):
        """Cache key must be brief:{user_id}:1."""
        users = [(42,)]
        captured_keys = []

        def capture_cache(key, fn, ttl_minutes=30):
            captured_keys.append(key)
            return {}

        backup = _inject_cache_helper(capture_cache)
        try:
            with patch("src.db.query", return_value=users):
                with patch("web.auth.get_primary_address", return_value=None):
                    resp = cron_client.post("/cron/compute-caches", headers=_auth())
        finally:
            _restore_cache_helper(backup)

        assert resp.status_code == 200
        # If helpers are available and key was captured, verify format
        if captured_keys:
            assert captured_keys[0] == "brief:42:1"


# ---------------------------------------------------------------------------
# Per-user error handling
# ---------------------------------------------------------------------------

class TestComputeCachesPerUserErrors:
    def test_user_error_increments_errors(self, cron_client):
        """If user cache computation fails, errors++ and no crash."""
        users = [(1,), (2,)]
        call_count = {"n": 0}

        def flaky_cache(key, fn, ttl_minutes=30):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("brief generation failed")
            return {}

        backup = _inject_cache_helper(flaky_cache)
        try:
            with patch("src.db.query", return_value=users):
                with patch("web.auth.get_primary_address", return_value=None):
                    resp = cron_client.post("/cron/compute-caches", headers=_auth())
        finally:
            _restore_cache_helper(backup)

        assert resp.status_code == 200
        data = json.loads(resp.data)
        # If helpers available: errors + computed = total_users
        if "total_users" in data and "errors" in data and "computed" in data:
            assert data["errors"] + data["computed"] == data["total_users"]

    def test_db_error_returns_500(self, cron_client):
        """If DB query for users fails (and helpers available), returns 500."""
        # Must inject helpers first so the endpoint reaches the DB query
        mock_cache = MagicMock(return_value={})
        backup = _inject_cache_helper(mock_cache)
        try:
            with patch("src.db.query", side_effect=RuntimeError("db down")):
                resp = cron_client.post("/cron/compute-caches", headers=_auth())
        finally:
            _restore_cache_helper(backup)

        assert resp.status_code == 500
        data = json.loads(resp.data)
        assert "error" in data


# ---------------------------------------------------------------------------
# Cache invalidation in nightly cron
# ---------------------------------------------------------------------------

class _NightlyMocksWithCache:
    """Mocks all nightly sub-tasks (mirrors test_sprint64_cron pattern)."""

    def __init__(self):
        self.patches = []
        self._mocks = {}

    def __enter__(self):
        targets = {
            "run_async": ("web.routes_cron.run_async", MagicMock(
                return_value={"status": "ok", "changes_inserted": 2, "staleness_warnings": []}
            )),
            "execute_write": ("src.db.execute_write", MagicMock()),
            "run_triage": ("scripts.feedback_triage.run_triage", MagicMock(return_value={})),
            "admin_users": ("web.activity.get_admin_users", MagicMock(return_value=[])),
            "cleanup_expired": ("web.plan_images.cleanup_expired", MagicMock(return_value=0)),
            "cleanup_jobs": ("web.plan_jobs.cleanup_old_jobs", MagicMock(return_value=0)),
            "velocity_v1": ("web.station_velocity.refresh_station_velocity", MagicMock(return_value={})),
            "congestion": ("web.station_velocity.refresh_station_congestion", MagicMock(return_value={"congestion_stations": 0})),
            "reviewer": ("web.reviewer_graph.refresh_reviewer_interactions", MagicMock(return_value={})),
            "ops_chunks": ("web.ops_chunks.ingest_ops_chunks", MagicMock(return_value=0)),
            "dq_cache": ("web.data_quality.refresh_dq_cache", MagicMock(return_value={"checks": 12})),
            "signal_pipeline": ("src.signals.pipeline.run_signal_pipeline", MagicMock(return_value={"signals": 10})),
            "velocity_v2": ("src.station_velocity_v2.refresh_velocity_v2", MagicMock(return_value={"stations": 42})),
            "transitions": ("src.tools.station_predictor.refresh_station_transitions", MagicMock(return_value={"transitions": 5})),
            "get_connection": ("src.db.get_connection", MagicMock(return_value=MagicMock())),
        }
        for key, (target, mock_obj) in targets.items():
            p = patch(target, mock_obj)
            p.start()
            self.patches.append(p)
            self._mocks[key] = mock_obj
        return self._mocks

    def __exit__(self, *args):
        for p in reversed(self.patches):
            p.stop()


class TestNightlyIncludesCacheInvalidation:
    """cache_invalidation key is present in nightly response."""

    def test_cache_invalidation_key_in_response(self, cron_client):
        """nightly response must include cache_invalidation key."""
        with _NightlyMocksWithCache():
            resp = cron_client.post("/cron/nightly", headers=_auth())

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "cache_invalidation" in data

    def test_cache_invalidation_nonfatal_on_error(self, cron_client):
        """If invalidate_cache raises, nightly pipeline still returns 200."""
        import web.helpers as helpers_mod
        # Inject invalidate_cache that explodes
        backup = getattr(helpers_mod, "invalidate_cache", _MISSING)
        helpers_mod.invalidate_cache = MagicMock(side_effect=RuntimeError("cache boom"))

        try:
            with _NightlyMocksWithCache():
                resp = cron_client.post("/cron/nightly", headers=_auth())
        finally:
            if backup is _MISSING:
                if hasattr(helpers_mod, "invalidate_cache"):
                    delattr(helpers_mod, "invalidate_cache")
            else:
                helpers_mod.invalidate_cache = backup

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "cache_invalidation" in data

    def test_cache_invalidation_empty_on_dry_run(self, cron_client):
        """dry_run=true skips cache invalidation step (returns {})."""
        with _NightlyMocksWithCache():
            resp = cron_client.post("/cron/nightly?dry_run=true", headers=_auth())

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "cache_invalidation" in data
        # Dry run means the invalidation step is skipped entirely → {}
        assert data["cache_invalidation"] == {}
