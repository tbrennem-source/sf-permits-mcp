# Sprint 74-1 QA Results — Request Metrics + /admin/perf Dashboard

**Session:** Sprint 74-1 (Agent 74-1)
**Date:** 2026-02-26
**Method:** CLI-only QA (no browser needed — admin-only page, DB-level verification)

---

## QA Checks

### 1. DDL: request_metrics table in DuckDB
PASS — `init_user_schema()` creates `request_metrics` with id, path, method, status_code, duration_ms, recorded_at columns. Index `idx_reqmetrics_path_ts` on (path, recorded_at) created.

### 2. DDL: request_metrics in scripts/release.py (Postgres)
PASS — `run_release_migrations()` includes `CREATE TABLE IF NOT EXISTS request_metrics` with SERIAL PK, TIMESTAMPTZ.

### 3. DDL: request_metrics in web/app.py _run_startup_migrations
PASS — DDL block added after parcel_summary. Both startup and release paths create the table.

### 4. EXPECTED_TABLES includes request_metrics
PASS — `from web.app import EXPECTED_TABLES; 'request_metrics' in EXPECTED_TABLES` → True

### 5. /admin/perf route registered
PASS — `/admin/perf` in `app.url_map.iter_rules()` → True

### 6. Metric insert triggered for slow requests (> 200ms)
PASS — `_slow_request_log` with 300ms simulated elapsed time calls `execute_write` with INSERT into request_metrics.

### 7. Metric insert NOT triggered for fast non-sampled requests
PASS — 50ms request with random.random() = 0.9 (no sample trigger) → `execute_write` NOT called.

### 8. Random 10% sampling works
PASS — 50ms request with random.random() = 0.05 (sample trigger) → `execute_write` called.

### 9. Metric DB error gracefully handled
PASS — `execute_write` raising Exception does not propagate; response returned normally.

### 10. Non-admin access rejected
PASS — Non-admin user gets 403 from `/admin/perf`.

### 11. Unauthenticated access redirected
PASS — Unauthenticated GET `/admin/perf` returns 302 redirect.

### 12. Template Obsidian design markers
PASS — 6 matches of head_obsidian|obsidian|obs-container|glass-card (requirement: >= 4)

### 13. Template has stat blocks (p50/p95/p99)
PASS — `stat-block`, `glass-card`, `data-table` all present. p50/p95/p99 labels present.

### 14. Full test suite (14 tests)
PASS — `pytest tests/test_sprint_74_1.py` → 14 passed in 0.37s

---

## Scope Changes
None.

## Waiting On
Nothing — all tasks delivered.

## Visual QA Checklist (for DeskRelay spot-check)
- [ ] /admin/perf renders with Obsidian dark theme (obs-container centered, glass-card sections)
- [ ] Stat blocks for p50/p95/p99/total show 0ms on empty DB (fresh deploy state)
- [ ] Empty state messages visible in both tables on empty DB
- [ ] Method badges (GET/POST) display correctly in colored pill style
- [ ] Duration badges color-coded: green < 200ms, blue < 1s, amber < 3s, red >= 3s
