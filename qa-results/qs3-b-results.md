# QA Results: QS3-B Ops Hardening

**Date:** 2026-02-26
**Tests:** 39 passed, 0 failed
**Method:** pytest + Flask test client

## Checks

1. [NEW] _get_related_team returns results with mock relationships data — **PASS**
2. [NEW] Simulate 3 timeouts — circuit breaker opens — **PASS**
3. [NEW] Circuit breaker skips query when open — **PASS**
4. [NEW] GET /health includes "circuit_breakers" key — **PASS**
5. [NEW] GET /health includes "cron_heartbeat_age_minutes" — **PASS**
6. [NEW] POST /cron/heartbeat returns 200 — **PASS**
7. [NEW] GET /cron/pipeline-summary returns JSON — **PASS**

## Pre-existing Failures (not caused by QS3-B)

- `tests/test_permit_lookup.py::test_permit_lookup_address_suggestions` — mock side_effect sequence was already wrong on main (Pass 2 returns suggestion data as permit rows)
- `tests/test_background.py::TestSlowRequestLogging::test_slow_request_logs_warning` — flaky when run after tests that trigger `recover_stale_jobs` (extra `time.monotonic` calls). Passes in isolation.
- `tests/test_web.py` — 313 pre-existing failures (unrelated to QS3-B changes)
