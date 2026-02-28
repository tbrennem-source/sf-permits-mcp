<!-- LAUNCH: Open a fresh CC terminal from the MAIN repo root, then tell it:
     "Read sprint-prompts/sprint-68b-reliability.md and execute it"
     The agent will read this file and follow the instructions below. -->

# Sprint 68-B: Reliability + DQ Overhaul

You are a build agent for Sprint 68 of the sfpermits.ai project.

**DO NOT use plan mode.** This prompt IS the plan. Execute the tasks directly — read files, write code, run tests. No planning phase, no approval prompts. Work autonomously until all tasks are complete.

**FIRST:** Use EnterWorktree with name `sprint-68b` to create an isolated worktree. All work happens there.

## Context
- Repo root: `/Users/timbrenneman/AIprojects/sf-permits-mcp`
- Blueprint refactor is COMPLETE — routes live in `web/routes_*.py`, app.py is slim (~1,050 lines)
- 3,093 tests passing on main
- Always activate venv: `source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate`
- Run tests with: `pytest tests/ --ignore=tests/test_tools.py -q`

## Your Tasks

### Task 1: DQ Check Overhaul
**Files:** `web/data_quality.py`

1. Read `web/data_quality.py` thoroughly to understand all DQ checks
2. Fix orphaned contacts threshold — currently too lenient. The check should flag if orphaned contacts (contacts without matching entity_id in entities table) exceed 5% of total contacts
3. Update RAG chunk baseline: instead of a hardcoded count, query `SELECT COUNT(*) FROM knowledge_chunks` and use that as the baseline (with 10% tolerance)
4. Add `_check_addenda_freshness` DQ check: query `SELECT MAX(finish_date) FROM addenda` and warn if older than 30 days
5. Add DQ check for station_velocity data freshness: query `SELECT MAX(computed_at) FROM station_velocity_v2` (if table exists), warn if older than 7 days
6. Add `_check_velocity_trends` DQ check: compare station velocity p50 for each station this week vs last week. Flag WARNING if any station's p50 increased by >15%, CRITICAL if >30%
7. Write tests for all new/modified DQ checks

### Task 2: Migration Hardening
**Files:** `web/app.py` (migrations section only), `scripts/release.py`, `src/db.py`

1. Sync `scripts/release.py` to include `projects` and `project_members` DDL (verify it matches what's in `_run_startup_migrations()` in `web/app.py`)
2. Audit all DDL paths — verify `web/app.py` `_run_startup_migrations()`, `scripts/release.py`, and `src/db.py` all use `pg_try_advisory_lock` consistently
3. Add health check enhancement: `/health` endpoint should report `missing_expected_tables` if any EXPECTED_TABLES are absent (verify this already works after Sprint 63 fix)
4. Add slow query logging to `src/db.py`: for any query that takes >5 seconds on PostgreSQL, log the query text and elapsed time at WARNING level

### Task 3: Index Optimization
**Files:** `scripts/release.py` (append new index DDL)

1. Add composite index DDL to `scripts/release.py`:
   - `CREATE INDEX IF NOT EXISTS idx_addenda_app_finish ON addenda(application_number, finish_date)`
   - `CREATE INDEX IF NOT EXISTS idx_permits_block_lot_status ON permits(block, lot, status)`
   - `CREATE INDEX IF NOT EXISTS idx_permit_changes_permit_detected ON permit_changes(permit_number, detected_at)`
2. These are `IF NOT EXISTS` — safe to run on any environment

## Rules
- Work in worktree `sprint-68b`
- Run `pytest tests/ --ignore=tests/test_tools.py -q` after each task to verify no regressions
- Do NOT modify files owned by other sprint-68 agents
- Commit after each task with descriptive message
- When done, report: DQ checks added/modified + test count

## File Ownership (Sprint 68-B ONLY)
- `web/data_quality.py` (DQ overhaul)
- `web/app.py` (migrations section ONLY — do NOT modify routes, hooks, or Blueprint registration)
- `scripts/release.py` (DDL sync + index additions)
- `src/db.py` (slow query logging ONLY)

Do NOT touch: `web/routes_*.py`, `web/brief.py`, `web/email_brief.py`, `web/templates/`, `web/static/`, `src/tools/`, `src/vision/`, `scenarios-*.md`, `CLAUDE.md`, `data/knowledge/`
