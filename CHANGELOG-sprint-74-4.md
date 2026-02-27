# CHANGELOG — Sprint 74-4: Connection Pool Tuning

## Summary
Added configurable connection pool parameters via environment variables and a new `get_pool_health()` function for operational visibility.

## Changes

### src/db.py

**_get_pool() — Task 74-4-1 + 74-4-2**
- Added `DB_POOL_MIN` env var (default `2`) — controls `minconn` parameter
- Added `DB_CONNECT_TIMEOUT` env var (default `10`) — controls `connect_timeout` parameter
- Updated startup log message to include all three values

**get_pool_health() — Task 74-4-5 (NEW FUNCTION)**
- Returns `{"healthy": bool, "min": int, "max": int, "in_use": int, "available": int}`
- `healthy=False` when pool is None or closed
- `available` is computed as `pool_size - in_use`, floored at 0

**get_pool_stats() — Task 74-4-6**
- Now includes `"health"` key containing the dict from `get_pool_health()`
- Used by `/health` endpoint for operational dashboards

**get_connection() — Task 74-4-3 + 74-4-4**
- `DB_STATEMENT_TIMEOUT` env var (default `"30s"`) replaces hardcoded `'30s'`
- Statement timeout now passed as SQL parameter (`%s`) rather than string interpolation
- Added `except psycopg2.pool.PoolError` handler that logs WARNING with pool stats before re-raising
- `import psycopg2.pool` moved to top of function for exception class access

### tests/test_sprint_74_4.py (NEW — 13 tests)
- `test_pool_min_default` / `test_pool_min_custom` — DB_POOL_MIN env var
- `test_connect_timeout_default` / `test_connect_timeout_custom` — DB_CONNECT_TIMEOUT env var
- `test_statement_timeout_applied_default` / `test_statement_timeout_custom` — DB_STATEMENT_TIMEOUT
- `test_statement_timeout_skipped_for_cron_worker` — CRON_WORKER bypass
- `test_pool_exhaustion_logs_warning` — WARNING on PoolError
- `test_get_pool_health_no_pool` / `test_get_pool_health_with_pool` / `test_get_pool_health_closed_pool`
- `test_get_pool_stats_includes_health` / `test_get_pool_stats_no_pool_no_health_key`

### tests/test_db_pool.py (2 tests updated)
- `TestStatementTimeout::test_statement_timeout_set_for_web` — updated assertion for parameterized timeout
- `TestPoolErrorHandling::test_pool_creation_error_propagates` — use `patch.object` on real module to avoid MagicMock exception-class issues

## New Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DB_POOL_MIN` | `2` | Minimum idle connections in pool |
| `DB_CONNECT_TIMEOUT` | `10` | TCP connection timeout (seconds) |
| `DB_STATEMENT_TIMEOUT` | `30s` | Per-statement kill timeout (Postgres syntax, e.g. `30s`, `1min`) |

## No Breaking Changes
- All defaults match previous hardcoded values
- Health endpoint gains new `health` sub-dict in pool stats (additive)
