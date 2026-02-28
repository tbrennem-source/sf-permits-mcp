## QS8-T1-B: Brief Pipeline Stats + Signals/Velocity Cron Endpoints

**Files changed:** `web/brief.py`, `web/routes_cron.py`, `tests/test_sprint_79_3.py`

### Task B-1: Pipeline stats in get_morning_brief()

Added `_get_pipeline_stats()` function to `web/brief.py`:
- Queries `cron_log` for the last 5 nightly job runs (elapsed time, status)
- Computes average duration across completed jobs
- Counts success/failed jobs in the last 24 hours
- Returns dict with: `recent_jobs`, `avg_duration_seconds`, `last_24h_success`,
  `last_24h_failed`, `last_24h_jobs`
- Non-fatal: returns `{}` on any DB error
- Included in `get_morning_brief()` return dict under key `"pipeline_stats"`

### Task B-2: /cron/signals — cron_log observability

Enhanced the existing `POST /cron/signals` endpoint in `web/routes_cron.py`:
- Logs job start to `cron_log` with `status='running'` before pipeline executes
- Logs completion with `status='success'` or `status='failed'` + elapsed time
- Response now includes: `ok`, `status`, `elapsed_seconds` alongside pipeline stats
- Error handling: pipeline failure returns `ok=False, status='failed'` (HTTP 500)

### Task B-3: /cron/velocity-refresh — cron_log observability

Enhanced the existing `POST /cron/velocity-refresh` endpoint in `web/routes_cron.py`:
- Same cron_log start/completion logging pattern as signals endpoint
- Preserves existing station transitions + congestion refresh (non-fatal sub-steps)
- Response now includes: `ok`, `status`, `elapsed_seconds` alongside refresh stats

### Tests

Added `tests/test_sprint_79_3.py` with 11 tests:
- `test_pipeline_stats_included_in_brief` — brief dict has pipeline_stats key
- `test_pipeline_stats_empty_on_db_error` — non-fatal, returns {} on failure
- `test_cron_signals_requires_auth` — 403 without token
- `test_cron_signals_requires_auth_bad_token` — 403 with wrong token
- `test_cron_signals_runs_severity` — pipeline invoked, ok=True response
- `test_cron_signals_returns_error_on_pipeline_failure` — ok=False on error
- `test_cron_velocity_refresh_requires_auth` — 403 without token
- `test_cron_velocity_refresh_requires_auth_bad_token` — 403 with wrong token
- `test_cron_velocity_refresh_runs` — refresh + transitions invoked, ok=True
- `test_cron_velocity_refresh_returns_error_on_failure` — ok=False on error
- `test_cron_velocity_refresh_transitions_failure_non_fatal` — partial failure ok
