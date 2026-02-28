# CHANGELOG — QS8-T1-D: Cache-Control + Response Timing + Pool Health

## Sprint 79 / QS8-T1-D

### Added

- **X-Response-Time header** on every HTTP response (Task D-2)
  - New `_add_response_time_header` after_request hook in `web/app.py`
  - Measures wall-clock time via `time.time()` (avoids interfering with
    `time.monotonic()` call counts used by the slow-request hook)
  - Format: `X-Response-Time: 12.3ms`
  - Added `g._request_start_wall = time.time()` to `_start_timer` before_request

- **pool_stats alias in /health** (Task D-3, partial)
  - `pool_stats` key added as alias for existing `pool` field for API clarity

- **cache_stats in /health** (Task D-3)
  - New `cache_stats` field in `/health` JSON response
  - Reports: `backend`, `row_count` (active page_cache rows), `oldest_entry_age_minutes`
  - Supports both Postgres and DuckDB backends

- **DB_POOL_MAX documentation comment** (Task D-4)
  - Added explanatory comment in `src/db.py` near `_get_pool()` pool creation
  - Documents when to increase (`DB_POOL_MAX` env var) and links to Chief #364

### Tests

- `tests/test_sprint_79_d.py` — 10 new tests, all passing:
  - `test_methodology_has_cache_control`
  - `test_about_data_has_cache_control`
  - `test_demo_has_cache_control`
  - `test_non_static_page_no_cache_control`
  - `test_response_timing_header_present`
  - `test_response_timing_header_on_health`
  - `test_response_timing_header_on_404`
  - `test_health_includes_pool_stats`
  - `test_health_includes_cache_stats`
  - `test_health_cache_stats_has_row_count`

### Notes

- Cache-Control headers for `/methodology`, `/about-data`, `/demo`, `/pricing` were
  already implemented in `web/app.py` (the `add_cache_headers` after_request hook).
  No duplication added in `routes_misc.py` — the hook approach is correct architecture.
- `X-Response-Time` uses `time.time()` not `time.monotonic()` to avoid breaking
  the `TestSlowRequestLogging.test_slow_request_logs_warning` test which mocks
  `time.monotonic()` with a fixed alternating pattern.

### Files Changed

- `web/app.py` — `_start_timer`, `add_cache_headers`, `/health` route, new `_add_response_time_header`
- `src/db.py` — documentation comment in `_get_pool()`
- `tests/test_sprint_79_d.py` — new test file (10 tests)
