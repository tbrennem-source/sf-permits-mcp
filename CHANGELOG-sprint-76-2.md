# CHANGELOG — Sprint 76-2: Cost Tracking Middleware Wiring

## Summary

Wired the cost tracking infrastructure (built in Sprint 74-76) into the Flask middleware layer so API usage is automatically logged, rate-limited via the kill switch, and rolled up into daily summaries.

## Changes

### web/app.py

**New: `_log_api_usage` after_request hook**
- Checks `g.api_usage` dict after each request
- If present and non-empty, calls `cost_tracking.log_api_call()` with endpoint, model, token counts
- Wrapped in try/except — never fails the response
- Enables any route to set `g.api_usage = {...}` and have usage logged automatically

**New: `_kill_switch_guard` before_request hook**
- Checks `is_kill_switch_active()` on every request
- If active, blocks AI routes (`/ask`, `/analyze`, `/lookup/intel-preview`) with 503 JSON
- Returns `{"error": "...", "kill_switch": True}` for API-friendly error handling
- Skips when `app.config["TESTING"]` is True (tests not affected)
- Does NOT block health, root, static, admin, or non-AI routes

### web/cost_tracking.py

**New: `aggregate_daily_usage(target_date=None)` function**
- Aggregates `api_usage` rows into `api_daily_summary` for a given date (default: yesterday)
- Uses INSERT ON CONFLICT DO UPDATE (Postgres) / INSERT OR REPLACE (DuckDB) for idempotency
- Includes per-endpoint breakdown as JSON
- Handles missing table gracefully (try/except, logs warning, returns `inserted=False`)
- Returns dict: `{summary_date, total_calls, total_cost_usd, inserted}`

### web/routes_public.py

**Updated: `/analyze-preview` route**
- Added `@_rate_limited_ai` decorator for per-user rate limiting and kill switch integration
- Previously only had IP-based rate limiting via `_is_rate_limited()`
- Legacy IP rate limit check retained as extra protection layer

### web/routes_cron.py

**New: `POST /cron/aggregate-api-usage` endpoint**
- CRON_SECRET bearer token authentication (same pattern as all other cron endpoints)
- Calls `aggregate_daily_usage()` for yesterday by default
- Accepts optional `?date=YYYY-MM-DD` query param for back-filling historical dates
- Returns JSON: `{ok, summary_date, total_calls, total_cost_usd, inserted}`
- 400 on invalid date param, 403 on missing/wrong auth

### web/routes_admin.py

**Confirmed: `/admin/costs/kill-switch` endpoint already exists** — no changes needed.

### tests/test_sprint_76_2.py (NEW)

22 tests covering:
- `_log_api_usage` after_request hook: logs when `g.api_usage` set, skips when absent/empty, survives exceptions
- `_kill_switch_guard`: blocks `/ask` + `/analyze` at path level, passes `/health` + `/`, JSON response format
- `aggregate_daily_usage`: returns expected keys, handles DB errors gracefully, respects target_date
- `/cron/aggregate-api-usage`: requires CRON_SECRET, accepts valid date param, rejects invalid date
- Rate limiter: allows initial calls, blocks excess calls

## Scope Notes

- `routes_property.py` audit confirmed: no direct Claude API calls. No changes needed.
- Kill switch before_request works alongside the existing `rate_limited()` decorator — decorator still handles its own kill switch check for HTMX fragment routes that return HTML error messages. The before_request returns JSON (better for programmatic clients).
