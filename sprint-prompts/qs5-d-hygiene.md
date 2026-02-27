<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs5-d-hygiene.md and execute it" -->

# Quad Sprint 5 — Session D: Task Hygiene Diagnostic Sweep

You are a build agent following **Black Box Protocol v1.3**.

**This is a read-only investigation session. No code changes, no tests expected.**

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs5-d
SAFETY TAG: git tag pre-qs5-d before any investigation.
MERGE RULE: Do NOT merge your branch to main. Commit to worktree branch only.
CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files.
APPEND FILES:
  - scenarios-pending-review-qs5-d.md (per-agent, for merge safety)
  - scenarios-pending-review.md (shared, append only — for stop hook compliance)
  - CHANGELOG-qs5-d.md (per-agent)
OUTPUT: Chief brain state updates only (chief_add_note, chief_complete_task, chief_add_task).
NO CODE CHANGES. NO NEW TESTS. This agent produces investigation notes and Chief updates.
```

## SETUP — Session Bootstrap

1. **Navigate to main repo root:**
   ```
   cd /Users/timbrenneman/AIprojects/sf-permits-mcp
   ```
2. **Pull latest main:**
   ```
   git checkout main && git pull origin main
   ```
3. **Create worktree:**
   Use EnterWorktree with name `qs5-d`

If worktree exists: `git worktree remove .claude/worktrees/qs5-d --force 2>/dev/null; true`

4. **Safety tag:** `git tag pre-qs5-d`

---

## PHASE 1: READ

Read these files before any investigation:
1. `CLAUDE.md` — project structure
2. `CHANGELOG.md` — recent changes to understand current state

Then use `chief_get_brain_state` to read the full task list.

---

## PHASE 2: INVESTIGATE

For each item below, read the relevant code, check the current state, and decide: **CLOSE** (task done), **UPDATE** (task needs new description), or **NEW TASK** (split into focused follow-up).

### Item 1: Addenda nightly refresh (Chief #127)
- Check: does `POST /cron/refresh-addenda` exist and work?
- Read `web/routes_cron.py` for addenda-related endpoints

### Item 2: Inspections upsert PK collision (Chief #112)
- Check: does the inspections ingest still have PK collision issues?
- Read `src/ingest.py` inspections function

### Item 3: Pre-build safety tagging (Chief #159)
- Check: is this already handled by sprint prompt SAFETY TAG rule?
- If yes, close as "solved by process"

### Item 4: Cost tracking middleware (Chief #143)
- Check: what DDL exists? What routes exist? What's wired vs not?
- Read `web/cost_tracking.py`, check if middleware is active

### Item 5: Playwright test suite scope (Chief #220)
- Check: how many Playwright tests exist now?
- `find tests/ -name '*.py' -exec grep -l 'playwright\|chromium' {} \;`

### Item 6: Test persona accounts (Chief #222)
- Check: still needed? How many test accounts exist?
- Read `web/auth.py` for test user patterns

### Item 7: CRON_SECRET 403 issue (Chief #179)
- Check: is this still happening? Read cron endpoint auth code.

### Item 8: 5 failing DQ checks on prod (Chief #178)
- Check: run DQ checks or read data_quality.py to see current state

### Item 9: property_signals populating (Chief #261)
- Check: does the property_health / property_signals pipeline work?
- Read relevant cron endpoint

### Item 10: Orphaned test files (Chief #207)
- Check: are there test files that don't match any source?
- `ls tests/` and cross-reference

### Item 11: Slow test_analyze_plans (Chief #210)
- Check: is this still slow? What's the current runtime?

### Item 12: Nightly CI verified (Chief #209)
- Check: is GitHub Actions or Railway cron running nightly?

### Item 13: Summary
For each item, call the appropriate Chief tool:
- `chief_complete_task(task_id)` for items that are done
- `chief_add_task(description, priority)` for new focused follow-ups
- `chief_add_note(content, session_type="ad_hoc")` for the full investigation summary

---

## PHASE 3: TEST

No tests — this is a read-only investigation session.

---

## PHASE 4: SCENARIOS

Append 1 scenario to BOTH:
- `scenarios-pending-review-qs5-d.md` (per-agent file)
- `scenarios-pending-review.md` (shared file, append only)

1. "Admin reviews stale task inventory and sees current status for each infrastructure item"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs5-d-hygiene-qa.md`:

```
1. [NEW] All 12 Chief items investigated — PASS/FAIL
2. [NEW] chief_add_note called with summary — PASS/FAIL
3. [NEW] Stale tasks closed or updated — PASS/FAIL
4. [NEW] CHANGELOG-qs5-d.md documents findings — PASS/FAIL
```

Save results to `qa-results/qs5-d-results.md`

NOTE: QA for this session is document review, not code testing. Verify that the Chief brain state was updated and findings were documented.

---

## PHASE 5.5: VISUAL REVIEW

N/A — no UI changes.

---

## PHASE 6: CHECKCHAT

### 1. VERIFY
- All 12 items investigated
- Chief brain state updated

### 2. DOCUMENT
- Write `CHANGELOG-qs5-d.md` with investigation findings summary

### 3. CAPTURE
- 1 scenario in both files

### 4. SHIP
- Commit with: "docs: Task hygiene diagnostic sweep (QS5-D)"
- Report: tasks closed, tasks updated, new tasks created

### 5. PREP NEXT
- Note: any items that need code changes in future sprints

### 6. BLOCKED ITEMS REPORT

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Actual |
|--------|--------|
| Wall clock time | [first commit to CHECKCHAT] |
| New tests | 0 (investigation only) |
| Tasks investigated | [N of 12] |
| Tasks closed | [count] |
| Tasks updated | [count] |
| New tasks created | [count] |
| Scope changes | [count + reasons] |
| Waiting on | [count + reasons] |
| QA checks | [pass/fail/skip] |
| Scenarios proposed | [count] |
```

### Visual QA Checklist
- N/A — no UI changes

---

## File Ownership (Session D ONLY)
**Own:**
- `CHANGELOG-qs5-d.md` (NEW)
- `scenarios-pending-review-qs5-d.md` (NEW)

**Do NOT touch (Session D has NO code changes):**
- All source files — Session D is read-only investigation
- `web/app.py` (Session A + C)
- `scripts/release.py` (Session A)
- `web/routes_cron.py` (Session A + B)
- `src/ingest.py` (Session B)
- `web/data_quality.py` (Session C)
