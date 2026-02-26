<!-- LAUNCH: Open a fresh CC terminal from the MAIN repo root, then tell it:
     "Read sprint-prompts/sprint-66-intelligence.md and execute it"
     The agent will read this file and follow the instructions below. -->

# Sprint 66: Intelligence + Performance

You are a build agent for Sprint 66 of the sfpermits.ai project.

**FIRST:** Use EnterWorktree with name `sprint-66` to create an isolated worktree. All work happens there.

## Context
- Repo root: `/Users/timbrenneman/AIprojects/sf-permits-mcp`
- Phase 0 Blueprint refactor is COMPLETE — routes live in `web/routes_*.py`, app.py is slim
- 3,093 tests passing on main at commit `5ba4a6d`
- Always activate venv: `source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate`
- Run tests with: `pytest tests/ --ignore=tests/test_tools.py -q`

## Your 4 Tasks (do them sequentially)

### Task 66-A: Neighborhood-Stratified Station Velocity
**Files:** `src/station_velocity_v2.py`, `src/tools/estimate_timeline.py` (`_query_station_velocity_v2` function ONLY)

1. Read `src/station_velocity_v2.py` to understand the current velocity computation
2. Read `src/tools/estimate_timeline.py` to understand how `_query_station_velocity_v2` is called
3. Extend `station_velocity_v2` computation to optionally include a `neighborhood` column:
   - Add a `compute_neighborhood_velocity()` function that computes per-(station, neighborhood) baselines
   - Only publish baselines where sample count >= 10
4. Modify `_query_station_velocity_v2` in `estimate_timeline.py` to try (station, neighborhood) first, fall back to station-only if no neighborhood data exists
5. Update tool output to show "Neighborhood-specific" when neighborhood data is used
6. Write tests for neighborhood-stratified queries and fallback behavior

**Interface contract with Sprint 65:** Sprint 65-B adds `_query_dbi_metrics` (new function, appended below velocity). You modify `_query_station_velocity_v2` (existing function). Non-overlapping.

### Task 66-B: Query Optimization + Indexes
**Files:** `scripts/release.py` (new index DDL), `src/db.py` (query logging)

1. Read `scripts/release.py` to understand the migration system
2. Add composite index DDL to `scripts/release.py`:
   - `CREATE INDEX IF NOT EXISTS idx_addenda_app_finish ON addenda(application_number, finish_date)` — speeds up velocity refresh
   - `CREATE INDEX IF NOT EXISTS idx_permits_block_lot_status ON permits(block, lot, status)` — speeds up property lookups
3. In `src/db.py`, add slow query logging: if a query takes more than 5 seconds, log it with `EXPLAIN ANALYZE` output (PostgreSQL only, skip for DuckDB)
4. Write tests for the new index DDL (verify it's valid SQL) and query logging behavior

### Task 66-C: Vision Resilience + Plan Analysis
**Files:** `src/vision/client.py`, `src/tools/analyze_plans.py`, `src/vision/pdf_to_images.py`, `src/vision/epr_checks.py`

1. Read `src/vision/client.py` to understand the Anthropic Vision API wrapper
2. Add a 30-second timeout to Vision API calls with graceful degradation:
   - If the API times out, fall back to metadata-only analysis (no vision checks)
   - Log a warning but don't fail the analysis
3. In `src/vision/pdf_to_images.py`, add an option for higher DPI (300+) for browser display. Add a `dpi` parameter defaulting to the current value, with option to request 300
4. Write tests for timeout handling and fallback behavior (mock the API client)

### Task 66-D: Severity Scoring + Trend Alerts
**Files:** `web/data_quality.py` (new trend function ONLY), `src/signals/aggregator.py` (if exists), `docs/TIMELINE_ESTIMATION.md` (new)

1. In `web/data_quality.py`, add a new function `_check_velocity_trends()`:
   - Compare current week's station_velocity_v2 p50 values to the prior 4-week rolling average
   - Flag any station where p50 is >15% slower than the rolling average
   - Return as a DQ check result with severity "warning"
2. If `src/signals/aggregator.py` exists, improve property-level signal aggregation to weight signals by recency
3. Create `docs/TIMELINE_ESTIMATION.md` documenting the full estimation strategy:
   - Station-sum model (primary)
   - DBI metrics (secondary)
   - Neighborhood stratification
   - Delay factors and triggers
   - Confidence levels and limitations
4. Write tests for velocity trend detection

## Rules
- Work in worktree `sprint-66` (use EnterWorktree)
- Run `pytest tests/ --ignore=tests/test_tools.py -q` after each task
- Do NOT modify files owned by other sprints
- Commit after each task with descriptive message
- When all 4 tasks are done, report completion with test count

## File Ownership (Sprint 66 ONLY)
- `src/station_velocity_v2.py` (66-A)
- `src/tools/estimate_timeline.py` (66-A: `_query_station_velocity_v2` function ONLY — do NOT add new functions)
- `scripts/release.py` (66-B: new index DDL only)
- `src/db.py` (66-B: query logging)
- `src/vision/client.py` (66-C)
- `src/tools/analyze_plans.py` (66-C)
- `src/vision/pdf_to_images.py` (66-C)
- `src/vision/epr_checks.py` (66-C)
- `web/data_quality.py` (66-D: new `_check_velocity_trends` function ONLY)
- `src/signals/aggregator.py` (66-D: if exists)
- `docs/TIMELINE_ESTIMATION.md` (66-D: new file)

Do NOT touch: `web/app.py`, `web/routes_*.py`, `web/brief.py`, `src/ingest.py`, `src/entities.py`, `src/graph.py`, `web/static/`, `web/templates/`, `data/knowledge/`
