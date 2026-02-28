<!-- LAUNCH: Open a fresh CC terminal from the MAIN repo root, then tell it:
     "Read sprint-prompts/sprint-68c-cron-brief.md and execute it"
     The agent will read this file and follow the instructions below. -->

# Sprint 68-C: Cron Pipeline Hardening + Morning Brief Enhancement

You are a build agent for Sprint 68 of the sfpermits.ai project.

**DO NOT use plan mode.** This prompt IS the plan. Execute the tasks directly — read files, write code, run tests. No planning phase, no approval prompts. Work autonomously until all tasks are complete.

**FIRST:** Use EnterWorktree with name `sprint-68c` to create an isolated worktree. All work happens there.

## Context
- Repo root: `/Users/timbrenneman/AIprojects/sf-permits-mcp`
- Blueprint refactor is COMPLETE — routes live in `web/routes_*.py`, app.py is slim (~1,050 lines)
- 3,093 tests passing on main
- Always activate venv: `source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate`
- Run tests with: `pytest tests/ --ignore=tests/test_tools.py -q`

## Your Tasks

### Task 1: Cron Pipeline Hardening
**Files:** `web/routes_cron.py`

1. Read `web/routes_cron.py` to understand existing cron endpoints and the nightly pipeline orchestration
2. Add cron_log timeout sweep to the `cron_nightly` function: mark any cron_log entries with status='running' and started_at > 10 minutes ago as status='failed', error_message='auto-closed: stuck > 10min'
3. Check if `/cron/signals` and `/cron/velocity-refresh` are already in the nightly pipeline orchestration. If not, add calls to them in the nightly pipeline sequence
4. Check if fire permit address parsing in `cron_ingest_fire` already cross-references fire permits to building permits via block/lot. If not, add a post-ingest step that matches fire permits to building permits
5. Write tests for the timeout sweep and any new pipeline steps

### Task 2: Morning Brief Enhancement
**Files:** `web/brief.py`, `web/email_brief.py`, `web/templates/fragments/brief_*.html`

1. Read `web/brief.py` to understand brief data assembly
2. Fix brief DQ footer: find where DQ check results are surfaced in the brief — if they fail silently, add error handling that surfaces the failure message to users
3. Add nightly pipeline stats to morning brief: query cron_log for the most recent 'nightly' job and include `changes_inserted`, `inspections_updated` counts
4. Add change velocity breakdown: count permit_changes by change_type (status_change, new_permit, etc.) for the lookback period, add to brief data
5. Verify property_signals data populates after cron — check if `web/brief.py` already queries signals data
6. Write tests for new brief data fields

### Task 3: Vision Resilience
**Files:** `src/vision/client.py`, `src/tools/analyze_plans.py`

1. Read `src/vision/client.py` to understand the current Vision API interaction
2. Add a 30-second timeout to Vision API calls in `client.py`:
   - On timeout, return a structured error result (not an exception)
   - The error result should indicate "Vision API timed out — metadata-only analysis available"
3. Update `src/tools/analyze_plans.py` to gracefully degrade:
   - If Vision API times out, skip vision-based checks and return metadata-only results
   - Clearly mark in the output which checks were skipped due to timeout
   - The tool should never raise an unhandled exception from Vision failures
4. Write tests for timeout behavior (mock the Vision API) and degradation path

## Rules
- Work in worktree `sprint-68c`
- Run `pytest tests/ --ignore=tests/test_tools.py -q` after each task to verify no regressions
- Do NOT modify files owned by other sprint-68 agents
- Commit after each task with descriptive message
- When done, report: pipeline improvements + brief enhancements + test count

## File Ownership (Sprint 68-C ONLY)
- `web/routes_cron.py` (cron pipeline additions)
- `web/brief.py` (brief data enhancements)
- `web/email_brief.py` (brief rendering)
- `web/templates/fragments/brief_*.html` (brief templates)
- `src/vision/client.py` (timeout + resilience)
- `src/tools/analyze_plans.py` (graceful degradation)

Do NOT touch: `web/app.py`, `web/data_quality.py`, `scripts/release.py`, `src/db.py`, `web/static/`, `web/templates/` (except brief fragments), `scenarios-*.md`, `CLAUDE.md`
