# CHANGELOG — Sprint 76-1: Station Routing Sequence Model

## Sprint 76-1 (Agent 76-1) — 2026-02-26

### Added

**`estimate_sequence_timeline(permit_number, conn=None)` in `src/tools/estimate_timeline.py`**
- New function that builds a permit-specific timeline from its actual addenda routing history
- Queries addenda table for the permit's station sequence ordered by first arrival time
- Looks up p50/p25/p75/p90 velocity for each station from `station_velocity_v2` (prefers 'current' period, falls back to 'baseline')
- Detects parallel review: stations with identical first-arrive dates use `max(p50)` instead of `sum(p50)`
- Station status classification: `done` (has finish_date), `stalled` (arrive but no finish), `pending` (no velocity)
- Skips stations with no velocity data, includes them in `skipped_stations` list with a note
- Returns `None` when permit has no addenda (no routing data)
- Confidence scoring: `high` (≥80% station coverage), `medium` (≥50%), `low` (<50%)
- Structured return: `{permit_number, stations, total_estimate_days, confidence}`

**`GET /api/timeline/<permit_number>` in `web/routes_api.py`**
- New public JSON endpoint returning the sequence timeline for a permit
- Rate limited at 60 req/min per IP (reuses existing `_is_rate_limited` helper)
- Returns 404 with `{"error": "no addenda found"}` when permit has no routing data
- Returns 500 on internal errors with `{"error": "internal error"}`
- No auth required — permit numbers are public data

**`tests/test_sprint_76_1.py`** (new file — 15 tests)
- 11 unit tests for `estimate_sequence_timeline`: no addenda, structure, single station, sequential sum, parallel max, missing velocity, status classification, no velocity table, confidence levels
- 4 API tests for `/api/timeline/<permit_number>`: 404 case, 200 with data, JSON content-type, 500 on error
- All 15 tests pass

### Technical Notes
- DuckDB uses `?` placeholders; Postgres uses `%s` — handled via `BACKEND` check (same pattern as rest of codebase)
- Parallel detection uses date-portion string comparison (`str(arrive)[:10]`) for both datetime and date types
- The function is sync (not async) since it does only DB reads, no network I/O
