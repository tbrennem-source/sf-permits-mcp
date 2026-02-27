"""
Tests for scripts/load_test.py (Sprint 74-2).

All tests mock httpx — no real HTTP calls.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

# Add scripts/ to path so we can import load_test directly
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import load_test as lt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_response(status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    return resp


def _fake_request(scenario_key: str, status_code: int = 200, elapsed_ms: float = 50.0) -> lt.RequestResult:
    return lt.RequestResult(
        scenario=scenario_key,
        status_code=status_code,
        elapsed_ms=elapsed_ms,
    )


def _fake_error_result(scenario_key: str) -> lt.RequestResult:
    return lt.RequestResult(
        scenario=scenario_key,
        status_code=None,
        elapsed_ms=100.0,
        error="Timeout: timed out",
    )


# ---------------------------------------------------------------------------
# Task 74-2-2: CLI argument parsing
# ---------------------------------------------------------------------------

class TestArgParser:
    def test_required_url(self):
        """--url is required."""
        parser = lt.build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_defaults(self):
        """Default concurrency=10, duration=30, scenario=all."""
        parser = lt.build_arg_parser()
        args = parser.parse_args(["--url", "http://localhost:5000"])
        assert args.concurrency == 10
        assert args.duration == 30
        assert args.scenario == "all"
        assert args.output == "load-test-results.json"
        assert args.timeout == 10.0

    def test_custom_args(self):
        """All CLI args can be overridden."""
        parser = lt.build_arg_parser()
        args = parser.parse_args([
            "--url", "https://example.com",
            "--concurrency", "5",
            "--duration", "60",
            "--scenario", "health",
            "--output", "/tmp/results.json",
            "--timeout", "15.0",
        ])
        assert args.concurrency == 5
        assert args.duration == 60
        assert args.scenario == "health"
        assert args.output == "/tmp/results.json"
        assert args.timeout == 15.0

    def test_invalid_scenario_rejected(self):
        """Unknown scenario names are rejected by argparse."""
        parser = lt.build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--url", "http://localhost", "--scenario", "nonexistent"])


# ---------------------------------------------------------------------------
# Task 74-2-3: Scenario registry
# ---------------------------------------------------------------------------

class TestScenarioRegistry:
    def test_all_five_scenarios_registered(self):
        """All 5 required scenarios exist."""
        for key in ("health", "search", "demo", "landing", "sitemap"):
            assert key in lt.SCENARIOS, f"Missing scenario: {key}"

    def test_scenario_has_required_fields(self):
        """Each scenario has method, path, name, description."""
        for key, scenario in lt.SCENARIOS.items():
            assert "method" in scenario, f"{key} missing method"
            assert "path" in scenario, f"{key} missing path"
            assert "name" in scenario, f"{key} missing name"
            assert "description" in scenario, f"{key} missing description"

    def test_health_path(self):
        assert lt.SCENARIOS["health"]["path"] == "/health"

    def test_search_path(self):
        assert "q=" in lt.SCENARIOS["search"]["path"]

    def test_resolve_scenarios_all(self):
        """resolve_scenarios('all') returns all 5 keys."""
        result = lt.resolve_scenarios("all")
        assert set(result) == set(lt.SCENARIOS.keys())

    def test_resolve_scenarios_single(self):
        """resolve_scenarios('health') returns ['health']."""
        result = lt.resolve_scenarios("health")
        assert result == ["health"]


# ---------------------------------------------------------------------------
# Task 74-2-4: Result aggregation + percentile math
# ---------------------------------------------------------------------------

class TestScenarioStats:
    def _make_stats(self, latencies: list[float], error_count: int = 0) -> lt.ScenarioStats:
        s = lt.ScenarioStats(
            scenario="health",
            name="Health Check",
            total_requests=len(latencies),
            error_count=error_count,
            latencies_ms=latencies,
        )
        return s

    def test_p50_median(self):
        """p50 is the median of the latency list."""
        s = self._make_stats([10.0, 20.0, 30.0, 40.0, 50.0])
        assert s.p50 == 30.0

    def test_p95_upper_tail(self):
        """p95 is near the high end for skewed distribution."""
        lats = list(range(1, 101))  # 1..100 ms
        s = self._make_stats([float(x) for x in lats])
        assert s.p95 >= 95.0

    def test_p99(self):
        lats = [float(x) for x in range(1, 101)]
        s = self._make_stats(lats)
        assert s.p99 >= 99.0

    def test_mean(self):
        s = self._make_stats([10.0, 20.0, 30.0])
        assert abs(s.mean - 20.0) < 0.01

    def test_min_max(self):
        s = self._make_stats([5.0, 15.0, 100.0])
        assert s.min_latency == 5.0
        assert s.max_latency == 100.0

    def test_error_rate(self):
        s = self._make_stats([50.0, 50.0, 50.0, 50.0], error_count=1)
        assert abs(s.error_rate - 0.25) < 0.001

    def test_success_count(self):
        s = self._make_stats([50.0] * 10, error_count=3)
        assert s.success_count == 7

    def test_empty_latencies(self):
        """No crashes on empty latency list."""
        s = lt.ScenarioStats(scenario="health", name="Health", total_requests=0, error_count=0)
        assert s.p50 == 0.0
        assert s.mean == 0.0
        assert s.min_latency == 0.0
        assert s.max_latency == 0.0


# ---------------------------------------------------------------------------
# Task 74-2-5: JSON output format
# ---------------------------------------------------------------------------

class TestJsonOutputFormat:
    def _make_populated_stats(self) -> dict[str, lt.ScenarioStats]:
        s = lt.ScenarioStats(
            scenario="health",
            name="Health Check",
            total_requests=100,
            error_count=2,
            latencies_ms=[float(x) for x in range(10, 110)],
        )
        return {"health": s}

    def test_json_has_meta(self):
        stats = self._make_populated_stats()
        output = lt.build_json_output(stats, 30.0, "http://localhost", ["health"], 10)
        assert "meta" in output
        assert output["meta"]["base_url"] == "http://localhost"
        assert output["meta"]["concurrency"] == 10

    def test_json_has_results_per_scenario(self):
        stats = self._make_populated_stats()
        output = lt.build_json_output(stats, 30.0, "http://localhost", ["health"], 10)
        assert "results" in output
        assert "health" in output["results"]

    def test_json_result_has_latency_fields(self):
        stats = self._make_populated_stats()
        output = lt.build_json_output(stats, 30.0, "http://localhost", ["health"], 10)
        lat = output["results"]["health"]["latency_ms"]
        for key in ("p50", "p95", "p99", "mean", "min", "max"):
            assert key in lat, f"Missing latency field: {key}"

    def test_json_result_has_rps(self):
        stats = self._make_populated_stats()
        output = lt.build_json_output(stats, 30.0, "http://localhost", ["health"], 10)
        assert "requests_per_second" in output["results"]["health"]
        assert output["results"]["health"]["requests_per_second"] == pytest.approx(100 / 30.0, rel=0.01)

    def test_json_result_has_error_count(self):
        stats = self._make_populated_stats()
        output = lt.build_json_output(stats, 30.0, "http://localhost", ["health"], 10)
        assert output["results"]["health"]["error_count"] == 2

    def test_json_summary_totals(self):
        stats = self._make_populated_stats()
        output = lt.build_json_output(stats, 30.0, "http://localhost", ["health"], 10)
        assert "summary" in output
        assert output["summary"]["total_requests"] == 100
        assert output["summary"]["total_errors"] == 2

    def test_json_serializable(self):
        """The entire output dict must be JSON-serializable."""
        stats = self._make_populated_stats()
        output = lt.build_json_output(stats, 30.0, "http://localhost", ["health"], 10)
        serialized = json.dumps(output)
        parsed = json.loads(serialized)
        assert parsed["meta"]["concurrency"] == 10


# ---------------------------------------------------------------------------
# Task 74-2-1/2/3: make_request with mocked httpx
# ---------------------------------------------------------------------------

class TestMakeRequest:
    def test_successful_request_returns_status_code(self):
        """A 200 response is captured correctly."""
        with patch("load_test.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = lambda s: mock_ctx
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.return_value = make_mock_response(200)

            result = lt.make_request("http://localhost:5000", "health")

        assert result.status_code == 200
        assert result.error is None
        assert result.elapsed_ms >= 0
        assert result.success is True

    def test_timeout_returns_error(self):
        """httpx.TimeoutException produces an error result."""
        with patch("load_test.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = lambda s: mock_ctx
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.side_effect = lt.httpx.TimeoutException("timed out")

            result = lt.make_request("http://localhost:5000", "health")

        assert result.status_code is None
        assert result.error is not None
        assert "Timeout" in result.error
        assert result.success is False

    def test_500_response_is_not_success(self):
        """A 500 status code counts as failure."""
        with patch("load_test.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = lambda s: mock_ctx
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.request.return_value = make_mock_response(500)

            result = lt.make_request("http://localhost:5000", "health")

        assert result.status_code == 500
        assert result.success is False

    def test_url_construction(self):
        """URL is constructed from base_url + scenario path."""
        called_url = []

        def capture_request(method, url):
            called_url.append(url)
            return make_mock_response(200)

        with patch("load_test.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_ctx.request.side_effect = capture_request
            mock_client_cls.return_value.__enter__ = lambda s: mock_ctx
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            lt.make_request("http://myapp.com", "health")

        assert len(called_url) == 1
        assert called_url[0] == "http://myapp.com/health"
