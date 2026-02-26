<!-- LAUNCH: Open a fresh CC terminal from the MAIN repo root, then tell it:
     "Read sprint-prompts/sprint-64-reliability.md and execute it"
     The agent will read this file and follow the instructions below. -->

# Sprint 64: Reliability + Monitoring

You are a build agent for Sprint 64 of the sfpermits.ai project.

**DO NOT use plan mode.** This prompt IS the plan. Execute the tasks directly — read files, write code, run tests. No planning phase, no approval prompts. Work autonomously until all 4 tasks are complete.

**FIRST:** Use EnterWorktree with name `sprint-64` to create an isolated worktree. All work happens there.

## Context
- Repo root: `/Users/timbrenneman/AIprojects/sf-permits-mcp`
- Phase 0 Blueprint refactor is COMPLETE — `web/app.py` is now slim (1,050 lines), routes live in `web/routes_*.py`
- 3,093 tests passing on main at commit `5ba4a6d`
- Always activate venv: `source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate`
- Run tests with: `pytest tests/ --ignore=tests/test_tools.py -q`

## Your 4 Tasks (do them sequentially)

### Task 64-A: Migration Hardening + Cron Cleanup
**Files:** `web/app.py` (migrations section), `scripts/release.py`, `src/db.py`

1. Sync `scripts/release.py` to include `projects` and `project_members` DDL (verify it matches what's in `_run_startup_migrations()` in `web/app.py`)
2. Add cron_log timeout sweep to `web/routes_cron.py` cron_nightly: mark any cron_log entries with status='running' and started_at > 10 minutes ago as status='failed', error_message='auto-closed: stuck > 10min'
3. Audit all DDL paths — verify `web/app.py` `_run_startup_migrations()`, `scripts/release.py`, and `src/db.py` all use `pg_try_advisory_lock` consistently
4. Add health check enhancement: `/health` endpoint should report `missing_expected_tables` if any EXPECTED_TABLES are absent (already partially done — verify it works)
5. Clean up leftover worktree branches: list all `worktree-agent-*` branches with `git branch | grep worktree-agent`, delete any that are fully merged into main

### Task 64-B: DQ Check Overhaul
**Files:** `web/data_quality.py`

1. Read `web/data_quality.py` thoroughly to understand all DQ checks
2. Fix orphaned contacts threshold — currently too lenient. The check should flag if orphaned contacts (contacts without matching entity_id in entities table) exceed 5% of total contacts
3. Update RAG chunk baseline: instead of a hardcoded count, query `SELECT COUNT(*) FROM knowledge_chunks` and use that as the baseline (with 10% tolerance)
4. Add `_check_addenda_freshness` DQ check: query `SELECT MAX(finish_date) FROM addenda` and warn if older than 30 days
5. Add DQ check for station_velocity data freshness: query `SELECT MAX(computed_at) FROM station_velocity_v2` (if table exists), warn if older than 7 days
6. Write tests for all new/modified DQ checks

### Task 64-C: Morning Brief + Pipeline Alerting
**Files:** `web/brief.py`, `web/email_brief.py`, `web/templates/fragments/brief_*.html`

1. Read `web/brief.py` to understand brief data assembly
2. Fix brief DQ footer: find where DQ check results are surfaced in the brief — if they fail silently, add error handling that surfaces the failure message to users
3. Add nightly pipeline stats to morning brief: query cron_log for the most recent 'nightly' job and include `changes_inserted`, `inspections_updated` counts
4. Add change velocity breakdown: count permit_changes by change_type (status_change, new_permit, etc.) for the lookback period, add to brief data
5. Verify property_signals data populates after cron — check if `web/brief.py` already queries signals data
6. Write tests for new brief data fields

### Task 64-D: Cron Pipeline Hardening
**Files:** `web/routes_cron.py`, `src/signals/` (if exists)

1. Read `web/routes_cron.py` to understand existing cron endpoints
2. Check if `/cron/signals` and `/cron/velocity-refresh` are already in the nightly pipeline orchestration (inside `cron_nightly`). If not, add calls to them in the nightly pipeline sequence
3. Check if signals migration has run on prod schema — look for signals-related tables in EXPECTED_TABLES or migration code
4. For fire permit address parsing: check if `cron_ingest_fire` already cross-references fire permits to building permits via block/lot. If not, add a post-ingest step that matches fire permits to building permits
5. Write tests for any new functionality

## Rules
- Work in worktree `sprint-64` (use EnterWorktree)
- Run `pytest tests/ --ignore=tests/test_tools.py -q` after each task to verify no regressions
- Do NOT modify files owned by other sprints (see file ownership below)
- Commit after each task with descriptive message
- When all 4 tasks are done, report completion with test count

## File Ownership (Sprint 64 ONLY)
- `web/app.py` (migrations section only)
- `web/routes_cron.py` (cron pipeline additions)
- `scripts/release.py`
- `web/data_quality.py`
- `web/brief.py`
- `web/email_brief.py`
- `web/templates/fragments/brief_*.html`

Do NOT touch: `src/entities.py`, `src/graph.py`, `src/tools/estimate_timeline.py`, `web/routes_admin.py`, `web/routes_public.py`, `web/static/`, `web/templates/` (except brief fragments), `tests/e2e/`
