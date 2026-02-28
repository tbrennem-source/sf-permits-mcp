# Sprint 83-C: Cron Endpoint CRON_WORKER Env Var Audit

## Summary

Audited all test files that make HTTP requests to `/cron/*` routes to verify `CRON_WORKER=1` is set where required.

## Findings

**No changes were required.** All 29 test files containing `/cron/` references were audited:

### Files already correct (CRON_WORKER properly set)
- `tests/test_brief_cache.py` — `TestCronComputeCaches`: each test method sets `monkeypatch.setenv("CRON_WORKER", "1")` ✓
- `tests/test_sprint_79_3.py` — uses `cron_client` fixture that sets `CRON_WORKER="1"` and `CRON_SECRET` ✓
- `tests/test_sprint_76_2.py` — CRON_WORKER set in fixtures ✓
- `tests/test_sprint_76_3.py` — uses `cron_client` fixture ✓
- `tests/test_sprint64_cron.py` — CRON_WORKER set in fixture ✓
- `tests/test_sprint56c.py` — CRON_WORKER set in client fixture ✓
- `tests/test_qs3_b_ops_hardening.py` — CRON_WORKER set in fixtures ✓
- `tests/test_qs4_a_metrics.py` — CRON_WORKER set per test method ✓
- `tests/test_qs5_a_parcels.py` — CRON_WORKER set in app fixture ✓
- `tests/test_qs5_b_backfill.py` — CRON_WORKER set in client fixture ✓
- `tests/test_ingest_review_metrics.py` — CRON_WORKER set in client fixture ✓
- `tests/test_cron_compute_caches.py` — uses `cron_client` fixture ✓
- `tests/test_signals/test_cron_signals.py` — CRON_WORKER set in fixture ✓

### Files intentionally testing CRON_GUARD behavior (no CRON_WORKER — correct)
- `tests/test_station_velocity_v2.py` — `test_cron_velocity_refresh_blocked_on_web_worker` expects 404 ✓
- `tests/test_reference_tables.py` — `TestCronEndpointAuth` tests expect 404 from guard ✓
- `tests/test_db_backup.py` — `test_backup_endpoint_blocked_on_web_worker` expects 404 ✓
- `tests/test_brief.py` — `test_cron_send_briefs_blocked_on_web_worker` expects 404 ✓
- `tests/test_pipeline_routes.py` — `test_pipeline_health_post_blocked_on_web_worker` expects 404 ✓
- `tests/test_cron_guard.py` — explicitly tests guard on/off behavior ✓

### Files with non-HTTP /cron/ references (no fix needed)
- `tests/test_sprint60b.py` — reads source files, no HTTP calls ✓
- `tests/test_sprint62c.py` — GET /cron/status (allowed on web workers) ✓
- `tests/test_pipeline_routes.py` GET calls — GET /cron/pipeline-health (allowed on web workers) ✓
- `tests/test_sprint69_s4.py` — only checks robots.txt string ✓
- `tests/test_pipeline_verification.py` — checks route registration, no HTTP calls ✓
- `tests/test_discover_routes.py` — checks route manifest, no HTTP calls ✓
- `tests/test_signal_fixes.py` — docstring reference only ✓

## Test Results

```
25 passed, 1 skipped in 4.85s
```

All tests in `test_brief_cache.py` and `test_sprint_79_3.py` pass with no changes required.
