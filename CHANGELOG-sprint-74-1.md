# CHANGELOG — Sprint 74-1

## Sprint 74-1: Request Metrics + /admin/perf Dashboard

**Date:** 2026-02-26
**Agent:** 74-1 (Request Metrics + Admin Perf Dashboard)

### New Features

#### Request Metrics Collection
- **`web/app.py`**: Added `import random`. Enhanced `_slow_request_log` after_request hook to sample request metrics: all requests > 200ms + 10% random sample. Inserts into `request_metrics` table via `execute_write`. Wrapped in `try/except` — never fails the response. Also added `request_metrics` DDL to `_run_startup_migrations` (Postgres).
- **`web/app.py`** (`EXPECTED_TABLES`): Added `"request_metrics"` to the expected tables list for health-check verification.

#### request_metrics DDL
- **`scripts/release.py`**: Added `CREATE TABLE IF NOT EXISTS request_metrics` block (SERIAL PK, TIMESTAMPTZ, FLOAT duration_ms) + `idx_reqmetrics_path_ts` index.
- **`src/db.py`** (`init_user_schema`): Added DuckDB DDL for `request_metrics` (INTEGER PK, TIMESTAMP not TIMESTAMPTZ per DuckDB conventions).

#### /admin/perf Dashboard
- **`web/routes_admin.py`**: Added `GET /admin/perf` route with `@admin_required`. Queries: top 10 slowest endpoints by p95 (24h), volume by path (24h), overall p50/p95/p99/total. Dual-mode (Postgres PERCENTILE_CONT + DuckDB QUANTILE_CONT). Empty data structures on exception. Renders `admin_perf.html`.
- **`web/templates/admin_perf.html`** (NEW): Obsidian design system template. Includes `head_obsidian.html`, `body class="obsidian"`, `obs-container`, 4 `stat-block` components for p50/p95/p99/total, 2 `glass-card` sections with `data-table` for slowest endpoints and volume. Duration badges color-coded by severity. Method badges (GET/POST). Empty state messages for both tables.

### Tests
- **`tests/test_sprint_74_1.py`** (NEW): 14 tests covering:
  - DDL creation in DuckDB (table exists, columns correct, insert/select works)
  - `EXPECTED_TABLES` membership
  - Metric sampling (slow triggers, fast+no-random doesn't, random sample triggers, DB error graceful)
  - Route auth (unauthenticated redirect, non-admin 403, admin access)
  - Template structure (Obsidian markers, stat-block, p50/p95/p99 display)

### Test Results
- `pytest tests/test_sprint_74_1.py`: 14 passed
- Pre-existing failure: `test_permit_lookup.py::test_permit_lookup_address_suggestions` — unrelated to Sprint 74-1 (fails on main branch too)
