<!-- LAUNCH: Open a fresh CC terminal from the MAIN repo root, then tell it:
     "Read sprint-prompts/sprint-68d-cleanup-docs.md and execute it"
     The agent will read this file and follow the instructions below. -->

# Sprint 68-D: Branch Cleanup + Documentation + Test Infrastructure

You are a build agent for Sprint 68 of the sfpermits.ai project.

**DO NOT use plan mode.** This prompt IS the plan. Execute the tasks directly — read files, write code, run tests. No planning phase, no approval prompts. Work autonomously until all tasks are complete.

**FIRST:** Use EnterWorktree with name `sprint-68d` to create an isolated worktree. All work happens there.

## Context
- Repo root: `/Users/timbrenneman/AIprojects/sf-permits-mcp`
- Blueprint refactor is COMPLETE — routes live in `web/routes_*.py`, app.py is slim (~1,050 lines)
- 3,093 tests passing on main
- Always activate venv: `source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate`
- Run tests with: `pytest tests/ --ignore=tests/test_tools.py -q`

## Your Tasks

### Task 1: Branch Cleanup
1. List all remote branches matching `worktree-*`, `claude/*`, and `sprint-*` patterns:
   ```
   git branch -r | grep -E 'worktree-|claude/|sprint-'
   ```
2. Verify each is fully merged into `main` using `git branch -r --merged main`
3. Delete merged remote branches: `git push origin --delete <branch>` for each
4. Delete local tracking refs: `git branch -d <branch>` for each local match
5. Check for orphaned worktree directories under `.claude/worktrees/` and remove any that don't correspond to active worktrees (`git worktree list`)
6. Report: how many branches deleted, how many remained (unmerged)

### Task 2: Timeline Estimation Documentation
**Files:** `docs/TIMELINE_ESTIMATION.md` (new)

Create `docs/TIMELINE_ESTIMATION.md` documenting the full timeline estimation strategy:
1. Read `src/tools/estimate_timeline.py` to understand the current implementation
2. Read `src/station_velocity_v2.py` for the velocity computation
3. Document:
   - Station-sum model (primary) — how it works, what data it uses
   - Aggregate fallback — when station data is unavailable
   - Delay factors and triggers (change_of_use, historic, etc.)
   - Data freshness requirements
   - Known limitations and confidence notes
4. Include a worked example: "For an alterations permit in the Mission, here's how the estimate is calculated..."

### Task 3: Knowledge Base Expansion
**Files:** `data/knowledge/tier1/` (new JSON files), `data/knowledge/GAPS.md`, `data/knowledge/SOURCES.md`

1. Read `data/knowledge/GAPS.md` to understand known gaps
2. Read `data/knowledge/SOURCES.md` for the inventory format
3. Read a few existing tier1 JSON files to understand the structure
4. Create `data/knowledge/tier1/commercial-completeness-checklist.json` — structured checklist for commercial tenant improvement permit submissions. Include: required forms, plan set requirements, agency routing triggers, common rejection reasons
5. Create `data/knowledge/tier1/school-impact-fees.json` (GAP-11) — SF school impact fee schedule, thresholds, exemptions, calculation method
6. Create `data/knowledge/tier1/special-inspection-requirements.json` (GAP-13) — when special inspections are required, types (structural, welding, concrete, etc.), who can perform them
7. Update GAPS.md to mark these gaps as resolved
8. Update SOURCES.md with new file entries
9. Write tests that verify the new JSON files are valid and have expected structure

### Task 4: E2E Test Foundation
**Files:** `tests/e2e/conftest.py`, `scripts/seed_test_personas.py` (new)

1. Read `tests/e2e/conftest.py` to understand existing e2e test setup
2. Read `web/routes_auth.py` to understand the test-login endpoint (requires `TESTING=1` env var)
3. Create `scripts/seed_test_personas.py`:
   - Define 4 test personas: anonymous, free-tier user, pro user, admin
   - Each persona has: email, display name, tier, expected permissions
   - The script should be importable as a module for use in conftest
4. Extend `tests/e2e/conftest.py` with:
   - Fixtures for each persona (logged in via test-login endpoint)
   - `TESTING=1` environment variable setup
   - Reusable page object patterns for common operations
5. Write a simple smoke test in `tests/e2e/test_smoke.py`:
   - App starts, health endpoint returns 200
   - Landing page loads for anonymous user
   - Login works for test persona
   - Admin route accessible for admin persona

## Rules
- Work in worktree `sprint-68d`
- Run `pytest tests/ --ignore=tests/test_tools.py -q` after each task to verify no regressions
- Do NOT modify files owned by other sprint-68 agents
- Commit after each task with descriptive message
- When done, report: branches cleaned + docs created + knowledge files + tests added

## File Ownership (Sprint 68-D ONLY)
- Git branches (cleanup)
- `.claude/worktrees/` (orphaned directory cleanup)
- `docs/TIMELINE_ESTIMATION.md` (new)
- `data/knowledge/tier1/` (new JSON files)
- `data/knowledge/GAPS.md` (mark gaps resolved)
- `data/knowledge/SOURCES.md` (add new entries)
- `tests/e2e/conftest.py` (extend with persona fixtures)
- `tests/e2e/test_smoke.py` (new)
- `scripts/seed_test_personas.py` (new)

Do NOT touch: `web/app.py`, `web/routes_*.py`, `web/data_quality.py`, `web/brief.py`, `scripts/release.py`, `src/db.py`, `src/vision/`, `web/static/`, `web/templates/`, `scenarios-*.md`
