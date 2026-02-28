<!-- LAUNCH: Open a fresh CC terminal from the MAIN repo root, then tell it:
     "Read sprint-prompts/sprint-68a-scenario-drain.md and execute it"
     The agent will read this file and follow the instructions below. -->

# Sprint 68-A: Scenario Drain + Governance

You are a build agent for Sprint 68 of the sfpermits.ai project.

**DO NOT use plan mode.** This prompt IS the plan. Execute the tasks directly — read files, write code, run tests. No planning phase, no approval prompts. Work autonomously until all tasks are complete.

**FIRST:** Use EnterWorktree with name `sprint-68a` to create an isolated worktree. All work happens there.

## Context
- Repo root: `/Users/timbrenneman/AIprojects/sf-permits-mcp`
- Blueprint refactor is COMPLETE — routes live in `web/routes_*.py`, app.py is slim (~1,050 lines)
- 3,093 tests passing on main
- Always activate venv: `source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate`
- Run tests with: `pytest tests/ --ignore=tests/test_tools.py -q`

## Your Tasks

### Task 1: Drain the Scenario Queue

55+ scenarios have accumulated in `scenarios-pending-review.md` since Sprint 56, unreviewed. This is governance debt.

1. Read `scenarios-pending-review.md` (all entries)
2. Read `scenario-design-guide.md` (the 13 approved scenarios)
3. For each pending scenario, classify:
   - **ACCEPT** — clear behavioral requirement, testable, not a duplicate. Write into scenario design guide format.
   - **MERGE** — overlaps with an existing approved scenario. Note which one it extends and what new edge case it adds.
   - **REJECT** — too implementation-specific, untestable, duplicate, or describes internal behavior rather than user-visible outcome. Note reason.
   - **DEFER** — valid but depends on unbuilt features. Note which feature.
4. Update `scenario-design-guide.md` with accepted/merged scenarios
5. Create `scenarios-reviewed-sprint68.md` — full review log with disposition per entry
6. Clear `scenarios-pending-review.md` (leave only the header)

### Task 2: Update Key Documentation

1. Read `CLAUDE.md` and verify the "Key Numbers" section matches reality:
   - Run `pytest tests/ --ignore=tests/test_tools.py -q` — count tests
   - Check route count: `grep -r "@.*\.route\|@.*_bp\.route" web/routes_*.py web/app.py | wc -l`
   - Check table count from the health endpoint description
   - Update any stale numbers
2. Read `CHANGELOG.md` — add entries for Sprint 63 (deadlock fix) if missing
3. Read `STATUS.md` — update current state to reflect Sprint 68 foundation work
4. Verify `DEPLOYMENT_MANIFEST.yaml` is current with actual Railway service topology

### Task 3: Verify Scenario Quality

For every ACCEPT scenario in your updated `scenario-design-guide.md`:
- Verify it has: user persona, starting state, goal, expected outcome
- Verify it does NOT reference routes, CSS classes, or implementation details
- Verify it's at outcome or behavior level (not navigation or implementation level)
- Flag any that need rewording

### Quality Criteria
- Every REJECT has a one-sentence reason
- Every ACCEPT scenario follows the design guide format
- Merged scenarios incorporate the strongest formulation from both sources
- `scenarios-pending-review.md` is empty (just header) when done
- No scenario references routes, CSS classes, or implementation details

## Rules
- Work in worktree `sprint-68a`
- Run `pytest tests/ --ignore=tests/test_tools.py -q` before final commit to verify no regressions
- Commit after each task with descriptive message
- When done, report: scenarios accepted, merged, rejected, deferred + test count

## File Ownership (Sprint 68-A ONLY)
- `scenarios-pending-review.md` (drain)
- `scenario-design-guide.md` (update with accepted scenarios)
- `scenarios-reviewed-sprint68.md` (new — review log)
- `CLAUDE.md` (key numbers only)
- `CHANGELOG.md` (add missing entries)
- `STATUS.md` (update current state)
- `DEPLOYMENT_MANIFEST.yaml` (verify/update)

Do NOT touch: `web/`, `src/`, `tests/`, `scripts/`, `data/`, `web/static/`, `web/templates/`
