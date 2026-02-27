# CHANGELOG — Sprint 76-3: Severity UI Integration + Caching

## Added

### severity_cache Table
- **scripts/release.py**: Added `# === Sprint 76-3 ===` section with `CREATE TABLE IF NOT EXISTS severity_cache` DDL for Postgres (JSONB drivers column, TIMESTAMPTZ computed_at) and `CREATE INDEX IF NOT EXISTS idx_severity_cache_tier`
- **src/db.py**: Added DuckDB equivalent DDL inside `init_user_schema` (VARCHAR drivers column, TIMESTAMP computed_at)
- **web/app.py**: Added `"severity_cache"` to `EXPECTED_TABLES` list so `/health` endpoint verifies its existence

### Severity Badge Fragment
- **web/templates/fragments/severity_badge.html**: New Jinja2 fragment rendering a colored pill badge when `severity_tier` context variable is set
  - Uses Obsidian design system tokens: `var(--signal-red)` for CRITICAL, `var(--signal-blue)` for LOW, `var(--signal-green)` for GREEN
  - Renders nothing (no `<span>`) when `severity_tier` is falsy
  - Includes inline `<style>` scoped CSS for five tiers: critical/high/medium/low/green

### Severity Cache Helper + Search Enrichment
- **web/routes_search.py**: Added `_get_severity_for_permit(permit_number)` helper
  - Checks `severity_cache` first (cache hit returns immediately)
  - On cache miss: fetches permit row + inspection count from DB, calls `score_permit()`, upserts result to cache
  - Wrapped in `try/except` — severity failures never break search
- Modified `_ask_permit_lookup()` to call `_get_severity_for_permit` and pass `severity_score`/`severity_tier` to template context

### Cron Endpoint
- **web/routes_cron.py**: Added `POST /cron/refresh-severity-cache` endpoint
  - CRON_SECRET bearer token auth (uses existing `_check_api_auth()`)
  - Fetches up to 500 active permits (status: filed/issued/approved) ordered by most recent
  - Bulk-fetches inspection counts in a single query for efficiency
  - Scores each permit with `score_permit()`, upserts to `severity_cache`
  - Per-row errors counted separately, do not abort the batch
  - Returns JSON: `{ok, permits_scored, errors, elapsed_s}`
  - Both Postgres and DuckDB compatible

### Tests
- **tests/test_sprint_76_3.py**: 23 new tests across 6 test classes
  - `TestSeverityCacheDDL`: DDL creates table, correct columns, idempotent, `init_user_schema` integration
  - `TestExpectedTables`: `EXPECTED_TABLES` includes `severity_cache`
  - `TestSeverityCacheHitMiss`: insert/select, upsert on conflict, miss returns None
  - `TestSeverityBadgeRendering`: badge renders for all 5 tiers, absent when tier is None/empty
  - `TestCronRefreshSeverityCache`: auth required (403 without token), 403 with wrong token, passes with correct token
  - `TestSeverityScoringModel`: score returns valid result, critical permit scores high, green permit scores low, handles None dates, dimensions are JSON-serializable

## Notes
- Pre-existing test failure: `tests/test_permit_lookup.py::test_permit_lookup_address_suggestions` — mock misalignment unrelated to Sprint 76-3 changes (permit_lookup output format changed in QS5, test mocks not updated)
- `severity_badge.html` is ready to include in `search_results.html` — pass `severity_tier` from template context. Template rendering hook already in place via `_ask_permit_lookup`.
