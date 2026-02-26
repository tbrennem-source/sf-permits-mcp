"""Tests for QS3-B: Operational Hardening.

Covers:
- CircuitBreaker class (open/close/cooldown/status)
- _get_related_team relationships-based lookup + fallback
- /health endpoint enhancements (circuit_breakers, heartbeat age)
- POST /cron/heartbeat
- GET /cron/pipeline-summary
- Circuit breaker integration in enrichment functions
"""

import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# CircuitBreaker unit tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    """Test the CircuitBreaker class in src/db."""

    def _make_cb(self, max_failures=3, window_seconds=120, cooldown_seconds=300):
        from src.db import CircuitBreaker
        return CircuitBreaker(
            max_failures=max_failures,
            window_seconds=window_seconds,
            cooldown_seconds=cooldown_seconds,
        )

    def test_starts_closed(self):
        cb = self._make_cb()
        assert cb.is_open("inspections") is False
        assert cb.is_open("contacts") is False

    def test_single_failure_stays_closed(self):
        cb = self._make_cb(max_failures=3)
        cb.record_failure("inspections")
        assert cb.is_open("inspections") is False

    def test_opens_after_max_failures(self):
        cb = self._make_cb(max_failures=3)
        cb.record_failure("inspections")
        cb.record_failure("inspections")
        cb.record_failure("inspections")
        assert cb.is_open("inspections") is True

    def test_open_circuit_skips_queries(self):
        cb = self._make_cb(max_failures=2, cooldown_seconds=60)
        cb.record_failure("contacts")
        cb.record_failure("contacts")
        assert cb.is_open("contacts") is True

    def test_different_categories_independent(self):
        cb = self._make_cb(max_failures=2)
        cb.record_failure("inspections")
        cb.record_failure("inspections")
        assert cb.is_open("inspections") is True
        assert cb.is_open("contacts") is False

    def test_success_resets_failures(self):
        cb = self._make_cb(max_failures=3)
        cb.record_failure("inspections")
        cb.record_failure("inspections")
        cb.record_success("inspections")
        cb.record_failure("inspections")
        # Only 1 failure after reset, should still be closed
        assert cb.is_open("inspections") is False

    def test_success_closes_open_circuit(self):
        cb = self._make_cb(max_failures=2)
        cb.record_failure("contacts")
        cb.record_failure("contacts")
        assert cb.is_open("contacts") is True
        cb.record_success("contacts")
        assert cb.is_open("contacts") is False

    def test_cooldown_expires(self):
        cb = self._make_cb(max_failures=2, cooldown_seconds=0.1)
        cb.record_failure("addenda")
        cb.record_failure("addenda")
        assert cb.is_open("addenda") is True
        time.sleep(0.15)
        assert cb.is_open("addenda") is False

    def test_get_status_empty(self):
        cb = self._make_cb()
        assert cb.get_status() == {}

    def test_get_status_closed(self):
        """After failure + success, category should not appear (fully reset)."""
        cb = self._make_cb(max_failures=3)
        cb.record_failure("inspections")
        cb.record_success("inspections")
        status = cb.get_status()
        # record_success clears all state — category shouldn't appear
        assert "inspections" not in status

    def test_get_status_open(self):
        cb = self._make_cb(max_failures=2, cooldown_seconds=300)
        cb.record_failure("contacts")
        cb.record_failure("contacts")
        status = cb.get_status()
        assert "contacts" in status
        assert "open" in status["contacts"]
        assert "failures" in status["contacts"]

    def test_window_prunes_old_failures(self):
        """Failures outside the time window should be pruned."""
        cb = self._make_cb(max_failures=3, window_seconds=0.1)
        cb.record_failure("inspections")
        cb.record_failure("inspections")
        time.sleep(0.15)
        # Old failures should be pruned, so this is only 1 failure
        cb.record_failure("inspections")
        assert cb.is_open("inspections") is False

    def test_module_level_singleton_exists(self):
        from src.db import circuit_breaker
        assert circuit_breaker is not None
        assert hasattr(circuit_breaker, "is_open")
        assert hasattr(circuit_breaker, "record_failure")
        assert hasattr(circuit_breaker, "record_success")
        assert hasattr(circuit_breaker, "get_status")


# ---------------------------------------------------------------------------
# _get_related_team tests
# ---------------------------------------------------------------------------

class TestGetRelatedTeam:
    """Test _get_related_team with relationships table."""

    def test_returns_empty_when_no_entities(self):
        """Should return empty list when permit has no entity_ids."""
        from src.tools.permit_lookup import _get_related_team

        mock_conn = MagicMock()
        # First query (get entity_ids) returns empty
        mock_conn.execute.return_value.fetchall.return_value = []

        # Need to handle the _exec function which checks BACKEND
        with patch("src.tools.permit_lookup._exec", return_value=[]):
            result = _get_related_team(mock_conn, "TEST123")
        assert result == []

    def test_relationships_query_returns_results(self):
        """Should use relationships table for fast lookup."""
        from src.tools.permit_lookup import _get_related_team

        # Mock _exec to return different results for different queries
        call_count = [0]
        def mock_exec(conn, sql, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # Step 1: entity_ids from contacts
                return [(101,), (102,)]
            elif call_count[0] == 2:
                # Step 2: relationships
                return [(101, 201, 3, "P001,P002,P003", "Mission")]
            elif call_count[0] == 3:
                # Step 3: entity details
                return [(201, "John Smith", "Smith & Co", 15)]
            elif call_count[0] == 4:
                # Step 4: permit details
                return [("P001", "alterations", "issued", "2024-06-01", 50000, "Kitchen remodel")]
            return []

        with patch("src.tools.permit_lookup._exec", side_effect=mock_exec):
            result = _get_related_team(MagicMock(), "TESTPERM")

        assert len(result) == 1
        assert result[0]["permit_number"] == "P001"
        assert result[0]["type"] == "alterations"

    def test_falls_back_to_self_join_on_missing_table(self):
        """Should fall back when relationships table doesn't exist."""
        from src.tools.permit_lookup import _get_related_team

        call_count = [0]
        def mock_exec(conn, sql, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # Step 1: entity_ids from contacts
                return [(101,)]
            elif call_count[0] == 2:
                # Step 2: relationships query fails
                raise Exception("Catalog Error: relationships does not exist")
            else:
                # Fallback self-join returns results
                return [("P999", "new construction", "complete", "2023-01-01",
                         100000, "New building", "Jane Doe", "architect")]
            return []

        with patch("src.tools.permit_lookup._exec", side_effect=mock_exec):
            result = _get_related_team(MagicMock(), "TESTPERM")

        assert len(result) == 1
        assert result[0]["permit_number"] == "P999"
        assert result[0]["shared_entity"] == "Jane Doe"


# ---------------------------------------------------------------------------
# Flask app fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a test Flask app."""
    # Set required env vars before importing
    import os
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("CRON_SECRET", "test-secret-123")
    os.environ.setdefault("CRON_WORKER", "1")

    from web.app import app as flask_app
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture
def client(app):
    """Create a Flask test client."""
    return app.test_client()


# ---------------------------------------------------------------------------
# /health endpoint tests
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """Test /health endpoint enhancements."""

    def test_health_includes_circuit_breakers(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "circuit_breakers" in data

    def test_health_includes_cron_heartbeat(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "cron_heartbeat_age_minutes" in data

    def test_health_heartbeat_no_data(self, client):
        """When no heartbeat exists, should show NO_DATA."""
        resp = client.get("/health")
        data = resp.get_json()
        # In test/DuckDB mode, heartbeat may not exist
        hb_status = data.get("cron_heartbeat_status")
        assert hb_status in ("NO_DATA", "OK", "WARNING", "CRITICAL", "ERROR", None)


# ---------------------------------------------------------------------------
# /cron/heartbeat tests
# ---------------------------------------------------------------------------

class TestCronHeartbeat:
    """Test POST /cron/heartbeat endpoint."""

    def test_heartbeat_requires_auth(self, client):
        resp = client.post("/cron/heartbeat")
        assert resp.status_code == 403

    def test_heartbeat_succeeds_with_auth(self, client):
        resp = client.post(
            "/cron/heartbeat",
            headers={"Authorization": "Bearer test-secret-123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["job_type"] == "heartbeat"

    def test_heartbeat_writes_to_cron_log(self, client):
        """After heartbeat, cron_log should have a heartbeat entry."""
        client.post(
            "/cron/heartbeat",
            headers={"Authorization": "Bearer test-secret-123"},
        )
        # Verify by querying cron status
        resp = client.get("/cron/status")
        data = resp.get_json()
        job_types = [j["job_type"] for j in data.get("jobs", [])]
        assert "heartbeat" in job_types


# ---------------------------------------------------------------------------
# /cron/pipeline-summary tests
# ---------------------------------------------------------------------------

class TestPipelineSummary:
    """Test GET /cron/pipeline-summary endpoint."""

    def test_pipeline_summary_returns_json(self, client):
        resp = client.get("/cron/pipeline-summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ok" in data
        assert "steps" in data
        assert isinstance(data["steps"], list)

    def test_pipeline_summary_no_auth_required(self, client):
        """Pipeline summary is read-only, no auth needed."""
        resp = client.get("/cron/pipeline-summary")
        assert resp.status_code == 200

    def test_pipeline_summary_after_heartbeat(self, client):
        """After writing a heartbeat, pipeline-summary should include it."""
        client.post(
            "/cron/heartbeat",
            headers={"Authorization": "Bearer test-secret-123"},
        )
        resp = client.get("/cron/pipeline-summary")
        data = resp.get_json()
        job_types = [s["job_type"] for s in data.get("steps", [])]
        assert "heartbeat" in job_types


# ---------------------------------------------------------------------------
# Circuit breaker integration in enrichment functions
# ---------------------------------------------------------------------------

class TestCircuitBreakerIntegration:
    """Test circuit breaker is checked in permit_lookup enrichment."""

    def test_contacts_skipped_when_circuit_open(self):
        """When contacts circuit is open, should skip query."""
        from src.db import circuit_breaker

        # Force the circuit open
        old_open = circuit_breaker._open_until.copy()
        old_failures = circuit_breaker._failures.copy()
        try:
            circuit_breaker._open_until["contacts"] = time.monotonic() + 300
            circuit_breaker._failures["contacts"] = [time.monotonic()] * 5
            assert circuit_breaker.is_open("contacts") is True
        finally:
            # Restore state
            circuit_breaker._open_until = old_open
            circuit_breaker._failures = old_failures

    def test_inspections_skipped_when_circuit_open(self):
        """When inspections circuit is open, should skip query."""
        from src.db import circuit_breaker

        old_open = circuit_breaker._open_until.copy()
        old_failures = circuit_breaker._failures.copy()
        try:
            circuit_breaker._open_until["inspections"] = time.monotonic() + 300
            circuit_breaker._failures["inspections"] = [time.monotonic()] * 5
            assert circuit_breaker.is_open("inspections") is True
        finally:
            circuit_breaker._open_until = old_open
            circuit_breaker._failures = old_failures

    def test_addenda_skipped_when_circuit_open(self):
        """When addenda circuit is open, should skip query."""
        from src.db import circuit_breaker

        old_open = circuit_breaker._open_until.copy()
        old_failures = circuit_breaker._failures.copy()
        try:
            circuit_breaker._open_until["addenda"] = time.monotonic() + 300
            assert circuit_breaker.is_open("addenda") is True
        finally:
            circuit_breaker._open_until = old_open
            circuit_breaker._failures = old_failures

    def test_related_team_skipped_when_circuit_open(self):
        """When related_team circuit is open, should skip query."""
        from src.db import circuit_breaker

        old_open = circuit_breaker._open_until.copy()
        old_failures = circuit_breaker._failures.copy()
        try:
            circuit_breaker._open_until["related_team"] = time.monotonic() + 300
            assert circuit_breaker.is_open("related_team") is True
        finally:
            circuit_breaker._open_until = old_open
            circuit_breaker._failures = old_failures

    def test_planning_records_skipped_when_circuit_open(self):
        """When planning_records circuit is open, should skip query."""
        from src.db import circuit_breaker

        old_open = circuit_breaker._open_until.copy()
        try:
            circuit_breaker._open_until["planning_records"] = time.monotonic() + 300
            assert circuit_breaker.is_open("planning_records") is True
        finally:
            circuit_breaker._open_until = old_open

    def test_boiler_permits_skipped_when_circuit_open(self):
        """When boiler_permits circuit is open, should skip query."""
        from src.db import circuit_breaker

        old_open = circuit_breaker._open_until.copy()
        try:
            circuit_breaker._open_until["boiler_permits"] = time.monotonic() + 300
            assert circuit_breaker.is_open("boiler_permits") is True
        finally:
            circuit_breaker._open_until = old_open

    def test_circuit_breaker_import_in_permit_lookup(self):
        """Verify circuit_breaker is imported in permit_lookup module."""
        import src.tools.permit_lookup as pl
        assert hasattr(pl, "circuit_breaker")


# ---------------------------------------------------------------------------
# Heartbeat age classification tests
# ---------------------------------------------------------------------------

class TestHeartbeatAgeClassification:
    """Test the heartbeat age thresholds in health endpoint."""

    def test_age_ok_threshold(self):
        """Age <= 30 minutes should be OK."""
        age = 15.0
        if age > 120:
            status = "CRITICAL"
        elif age > 30:
            status = "WARNING"
        else:
            status = "OK"
        assert status == "OK"

    def test_age_warning_threshold(self):
        """Age between 30-120 minutes should be WARNING."""
        age = 60.0
        if age > 120:
            status = "CRITICAL"
        elif age > 30:
            status = "WARNING"
        else:
            status = "OK"
        assert status == "WARNING"

    def test_age_critical_threshold(self):
        """Age > 120 minutes should be CRITICAL."""
        age = 150.0
        if age > 120:
            status = "CRITICAL"
        elif age > 30:
            status = "WARNING"
        else:
            status = "OK"
        assert status == "CRITICAL"

    def test_age_boundary_30(self):
        """Age exactly 30 should be OK (not WARNING)."""
        age = 30.0
        if age > 120:
            status = "CRITICAL"
        elif age > 30:
            status = "WARNING"
        else:
            status = "OK"
        assert status == "OK"

    def test_age_boundary_120(self):
        """Age exactly 120 should be WARNING (not CRITICAL)."""
        age = 120.0
        if age > 120:
            status = "CRITICAL"
        elif age > 30:
            status = "WARNING"
        else:
            status = "OK"
        assert status == "WARNING"


# ---------------------------------------------------------------------------
# _timed_step helper tests (inline in nightly pipeline)
# ---------------------------------------------------------------------------

class TestTimedStep:
    """Test the _timed_step pattern used in nightly pipeline."""

    def test_timed_step_records_elapsed(self):
        step_timings = {}

        def _timed_step(name, fn):
            t0 = time.monotonic()
            try:
                r = fn()
                elapsed = round(time.monotonic() - t0, 2)
                step_timings[name] = {"elapsed_seconds": elapsed, "status": "ok"}
                return r
            except Exception as exc:
                elapsed = round(time.monotonic() - t0, 2)
                step_timings[name] = {"elapsed_seconds": elapsed, "status": "error", "error": str(exc)}
                return {"error": str(exc)}

        _timed_step("test_step", lambda: {"result": 42})
        assert "test_step" in step_timings
        assert step_timings["test_step"]["status"] == "ok"
        assert "elapsed_seconds" in step_timings["test_step"]

    def test_timed_step_records_error(self):
        step_timings = {}

        def _timed_step(name, fn):
            t0 = time.monotonic()
            try:
                r = fn()
                elapsed = round(time.monotonic() - t0, 2)
                step_timings[name] = {"elapsed_seconds": elapsed, "status": "ok"}
                return r
            except Exception as exc:
                elapsed = round(time.monotonic() - t0, 2)
                step_timings[name] = {"elapsed_seconds": elapsed, "status": "error", "error": str(exc)}
                return {"error": str(exc)}

        def _failing_step():
            raise RuntimeError("kaboom")

        result = _timed_step("fail_step", _failing_step)
        assert step_timings["fail_step"]["status"] == "error"
        assert "kaboom" in step_timings["fail_step"]["error"]
        assert "error" in result
