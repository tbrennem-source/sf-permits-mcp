# CHANGELOG — Sprint 74-2 (Load Test Script)

## [Sprint 74-2] — 2026-02-26

### Added

- **`scripts/load_test.py`** — Concurrent HTTP load test script using `concurrent.futures.ThreadPoolExecutor` and `httpx` (no new dependencies).
  - CLI: `--url URL`, `--concurrency 10`, `--duration 30`, `--scenario all|health|search|demo|landing|sitemap`, `--output load-test-results.json`, `--timeout 10.0`
  - 5 built-in scenarios: `health` (GET /health), `search` (GET /search?q=valencia), `demo` (GET /demo), `landing` (GET /), `sitemap` (GET /sitemap.xml)
  - Per-scenario stats: p50, p95, p99, min, max, mean latency (ms), error_count, error_rate, requests_per_second
  - Human-readable summary table written to stderr
  - JSON results saved to `load-test-results.json` (path configurable)
  - Exit code 1 if any scenario error rate > 5%

- **`tests/test_sprint_74_2.py`** — 29 tests covering:
  - CLI argument parsing (defaults, custom args, invalid scenario rejection)
  - Scenario registry (all 5 scenarios present, required fields, path correctness)
  - Result aggregation (percentile math, mean, min/max, error rate, success count)
  - JSON output format (all required fields present, JSON-serializable)
  - HTTP request execution (mocked httpx — success, timeout, 500 error, URL construction)

### No dependencies added
Uses `httpx` (already a project dependency) and `concurrent.futures` (stdlib).
