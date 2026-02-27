#!/usr/bin/env python3
"""
Load test script for SF Permits web app.

Runs concurrent HTTP requests against configurable scenarios and reports
latency percentiles, error counts, and throughput.

Usage:
    python scripts/load_test.py --url https://staging.example.com
    python scripts/load_test.py --url http://localhost:5000 --scenario health --concurrency 5 --duration 10
    python scripts/load_test.py --url https://sfpermits-ai-staging-production.up.railway.app --scenario all --concurrency 20 --duration 60

Scenarios:
    health    GET /health
    search    GET /search?q=valencia
    demo      GET /demo
    landing   GET /
    sitemap   GET /sitemap.xml
    all       Run all scenarios equally distributed
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict] = {
    "health": {
        "name": "Health Check",
        "method": "GET",
        "path": "/health",
        "description": "App health endpoint — fast, no DB needed",
    },
    "search": {
        "name": "Search",
        "method": "GET",
        "path": "/search?q=valencia",
        "description": "Public search results for 'valencia'",
    },
    "demo": {
        "name": "Demo Page",
        "method": "GET",
        "path": "/demo",
        "description": "Anonymous demo path",
    },
    "landing": {
        "name": "Landing Page",
        "method": "GET",
        "path": "/",
        "description": "Landing page (public)",
    },
    "sitemap": {
        "name": "Sitemap",
        "method": "GET",
        "path": "/sitemap.xml",
        "description": "XML sitemap — static, fast",
    },
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RequestResult:
    scenario: str
    status_code: Optional[int]
    elapsed_ms: float
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and self.status_code is not None and self.status_code < 500


@dataclass
class ScenarioStats:
    scenario: str
    name: str
    total_requests: int
    error_count: int
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return self.total_requests - self.error_count

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests

    def percentile(self, p: float) -> float:
        """Return the p-th percentile of latencies (e.g. p=50 → median)."""
        if not self.latencies_ms:
            return 0.0
        sorted_lats = sorted(self.latencies_ms)
        idx = math.ceil((p / 100) * len(sorted_lats)) - 1
        return sorted_lats[max(0, idx)]

    @property
    def p50(self) -> float:
        return self.percentile(50)

    @property
    def p95(self) -> float:
        return self.percentile(95)

    @property
    def p99(self) -> float:
        return self.percentile(99)

    @property
    def mean(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return statistics.mean(self.latencies_ms)

    @property
    def min_latency(self) -> float:
        return min(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def max_latency(self) -> float:
        return max(self.latencies_ms) if self.latencies_ms else 0.0

    def to_dict(self, duration_seconds: float) -> dict:
        rps = self.total_requests / duration_seconds if duration_seconds > 0 else 0.0
        return {
            "scenario": self.scenario,
            "name": self.name,
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 4),
            "requests_per_second": round(rps, 2),
            "latency_ms": {
                "p50": round(self.p50, 1),
                "p95": round(self.p95, 1),
                "p99": round(self.p99, 1),
                "mean": round(self.mean, 1),
                "min": round(self.min_latency, 1),
                "max": round(self.max_latency, 1),
            },
        }


# ---------------------------------------------------------------------------
# HTTP worker
# ---------------------------------------------------------------------------

def make_request(base_url: str, scenario_key: str, timeout: float = 10.0) -> RequestResult:
    """Send a single HTTP request for the given scenario. Thread-safe."""
    scenario = SCENARIOS[scenario_key]
    url = urljoin(base_url.rstrip("/") + "/", scenario["path"].lstrip("/"))
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.request(scenario["method"], url)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return RequestResult(
            scenario=scenario_key,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )
    except httpx.TimeoutException as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return RequestResult(
            scenario=scenario_key,
            status_code=None,
            elapsed_ms=elapsed_ms,
            error=f"Timeout: {exc}",
        )
    except httpx.RequestError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return RequestResult(
            scenario=scenario_key,
            status_code=None,
            elapsed_ms=elapsed_ms,
            error=f"RequestError: {exc}",
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return RequestResult(
            scenario=scenario_key,
            status_code=None,
            elapsed_ms=elapsed_ms,
            error=f"UnexpectedError: {exc}",
        )


# ---------------------------------------------------------------------------
# Run loop
# ---------------------------------------------------------------------------

def run_load_test(
    base_url: str,
    scenarios: list[str],
    concurrency: int,
    duration: int,
    request_timeout: float = 10.0,
) -> tuple[dict[str, ScenarioStats], float]:
    """
    Run the load test for `duration` seconds using `concurrency` threads.

    Submits new requests as threads become available, cycling through
    scenarios in round-robin order. Returns (stats_by_scenario, actual_duration).
    """
    stats: dict[str, ScenarioStats] = {
        key: ScenarioStats(scenario=key, name=SCENARIOS[key]["name"], total_requests=0, error_count=0)
        for key in scenarios
    }

    scenario_cycle = scenarios  # round-robin index tracked below
    scenario_idx = 0
    results: list[RequestResult] = []

    print(f"  Target: {base_url}", file=sys.stderr)
    print(f"  Scenarios: {', '.join(scenarios)}", file=sys.stderr)
    print(f"  Concurrency: {concurrency} threads | Duration: {duration}s", file=sys.stderr)
    print(f"  Request timeout: {request_timeout}s", file=sys.stderr)
    print("", file=sys.stderr)

    deadline = time.perf_counter() + duration
    actual_start = time.perf_counter()
    in_flight = 0
    total_submitted = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {}
        # Seed initial batch
        while len(futures) < concurrency and time.perf_counter() < deadline:
            key = scenario_cycle[scenario_idx % len(scenario_cycle)]
            scenario_idx += 1
            fut = executor.submit(make_request, base_url, key, request_timeout)
            futures[fut] = key
            total_submitted += 1

        while futures and time.perf_counter() < deadline:
            done = []
            for fut in list(futures):
                if fut.done():
                    done.append(fut)

            for fut in done:
                result = fut.result()
                results.append(result)
                del futures[fut]

                # Submit next request if still within deadline
                if time.perf_counter() < deadline:
                    key = scenario_cycle[scenario_idx % len(scenario_cycle)]
                    scenario_idx += 1
                    new_fut = executor.submit(make_request, base_url, key, request_timeout)
                    futures[new_fut] = key
                    total_submitted += 1

            if not done:
                time.sleep(0.01)  # brief yield to avoid busy-spin

        # Collect any remaining in-flight requests (they started before deadline)
        for fut in list(futures):
            try:
                result = fut.result(timeout=request_timeout + 1)
                results.append(result)
            except Exception:
                pass

    actual_duration = time.perf_counter() - actual_start

    # Aggregate into stats
    for result in results:
        s = stats[result.scenario]
        s.total_requests += 1
        s.latencies_ms.append(result.elapsed_ms)
        if not result.success:
            s.error_count += 1

    return stats, actual_duration


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_summary_table(stats: dict[str, ScenarioStats], duration: float) -> None:
    """Write a human-readable summary table to stderr."""
    col_w = [20, 8, 8, 8, 8, 8, 8, 7, 7]
    header = (
        f"{'Scenario':<{col_w[0]}} "
        f"{'Reqs':>{col_w[1]}} "
        f"{'Errors':>{col_w[2]}} "
        f"{'RPS':>{col_w[3]}} "
        f"{'p50ms':>{col_w[4]}} "
        f"{'p95ms':>{col_w[5]}} "
        f"{'p99ms':>{col_w[6]}} "
        f"{'min':>{col_w[7]}} "
        f"{'max':>{col_w[8]}}"
    )
    sep = "-" * len(header)

    print("", file=sys.stderr)
    print("LOAD TEST RESULTS", file=sys.stderr)
    print(sep, file=sys.stderr)
    print(header, file=sys.stderr)
    print(sep, file=sys.stderr)

    for key, s in stats.items():
        rps = s.total_requests / duration if duration > 0 else 0.0
        err_str = f"{s.error_count}" if s.error_count == 0 else f"{s.error_count} ({s.error_rate:.0%})"
        row = (
            f"{s.name:<{col_w[0]}} "
            f"{s.total_requests:>{col_w[1]}} "
            f"{err_str:>{col_w[2]}} "
            f"{rps:>{col_w[3]}.1f} "
            f"{s.p50:>{col_w[4]}.0f} "
            f"{s.p95:>{col_w[5]}.0f} "
            f"{s.p99:>{col_w[6]}.0f} "
            f"{s.min_latency:>{col_w[7]}.0f} "
            f"{s.max_latency:>{col_w[8]}.0f}"
        )
        print(row, file=sys.stderr)

    print(sep, file=sys.stderr)
    total = sum(s.total_requests for s in stats.values())
    total_errors = sum(s.error_count for s in stats.values())
    overall_rps = total / duration if duration > 0 else 0.0
    print(
        f"{'TOTAL':<{col_w[0]}} {total:>{col_w[1]}} {total_errors:>{col_w[2]}} "
        f"{overall_rps:>{col_w[3]}.1f}",
        file=sys.stderr,
    )
    print(sep, file=sys.stderr)
    print(f"  Duration: {duration:.1f}s | Total requests: {total} | Errors: {total_errors}", file=sys.stderr)


def build_json_output(
    stats: dict[str, ScenarioStats],
    duration: float,
    base_url: str,
    scenarios: list[str],
    concurrency: int,
) -> dict:
    return {
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "base_url": base_url,
            "scenarios": scenarios,
            "concurrency": concurrency,
            "duration_seconds": round(duration, 2),
        },
        "results": {key: s.to_dict(duration) for key, s in stats.items()},
        "summary": {
            "total_requests": sum(s.total_requests for s in stats.values()),
            "total_errors": sum(s.error_count for s in stats.values()),
            "overall_rps": round(sum(s.total_requests for s in stats.values()) / duration, 2) if duration > 0 else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load test the SF Permits web app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url", required=True, help="Base URL to test (e.g. https://sfpermits-ai-staging-production.up.railway.app)")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent threads (default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Test duration in seconds (default: 30)",
    )
    parser.add_argument(
        "--scenario",
        default="all",
        choices=list(SCENARIOS.keys()) + ["all"],
        help="Scenario to run (default: all)",
    )
    parser.add_argument(
        "--output",
        default="load-test-results.json",
        help="Path to save JSON results (default: load-test-results.json)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds (default: 10)",
    )
    return parser


def resolve_scenarios(scenario_arg: str) -> list[str]:
    if scenario_arg == "all":
        return list(SCENARIOS.keys())
    return [scenario_arg]


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    scenarios = resolve_scenarios(args.scenario)

    print(f"Starting load test...", file=sys.stderr)
    stats, actual_duration = run_load_test(
        base_url=args.url,
        scenarios=scenarios,
        concurrency=args.concurrency,
        duration=args.duration,
        request_timeout=args.timeout,
    )

    print_summary_table(stats, actual_duration)

    output = build_json_output(
        stats=stats,
        duration=actual_duration,
        base_url=args.url,
        scenarios=scenarios,
        concurrency=args.concurrency,
    )

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved to: {output_path.resolve()}", file=sys.stderr)

    # Print JSON to stdout for piping
    print(json.dumps(output, indent=2))

    # Exit 1 if any scenario had errors above 5%
    any_high_errors = any(s.error_rate > 0.05 for s in stats.values() if s.total_requests > 0)
    return 1 if any_high_errors else 0


if __name__ == "__main__":
    sys.exit(main())
