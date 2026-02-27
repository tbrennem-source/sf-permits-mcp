<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs5-c-bridges.md and execute it" -->

# Quad Sprint 5 — Session C: Trade Permit Bridge + Orphan Inspections

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs5-c
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs5-c before any code changes.
MERGE RULE: Do NOT merge your branch to main. Commit to worktree branch only. The orchestrator (Tab 0) merges all branches.
CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files. If you encounter a conflict, stop and report it.
APPEND FILES:
  - scenarios-pending-review-qs5-c.md (per-agent, for merge safety)
  - scenarios-pending-review.md (shared, append only — for stop hook compliance)
  - CHANGELOG-qs5-c.md (per-agent)
TEST FIXUP EXCEPTION: If your code changes cause tests in files you don't own to fail, you MAY fix those tests. Limit fixes to assertion updates that reflect your intentional changes. Do NOT refactor or rewrite tests beyond what's needed. Document any cross-file test fixes in your CHANGELOG.
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
   Use EnterWorktree with name `qs5-c`

If worktree exists: `git worktree remove .claude/worktrees/qs5-c --force 2>/dev/null; true`

4. **Safety tag:** `git tag pre-qs5-c`

---

## PHASE 1: READ

Read these files before writing any code:
1. `CLAUDE.md` — project structure, deployment, rules
2. `web/data_quality.py` — existing DQ check patterns
3. `web/app.py` lines 700-780 — `_run_startup_migrations()` + EXPECTED_TABLES
4. `src/db.py` lines 1036-1080 — boiler_permits + fire_permits DDL
5. `src/ingest.py` — `ingest_boiler_permits()`, `ingest_fire_permits()` functions
6. `scenario-design-guide.md` — for scenario-keyed QA

**Architecture notes:**
- boiler_permits: 151K rows on prod, has block/lot columns
- fire_permits: 84K rows on prod, NO block/lot columns — can't join to parcel graph
- electrical/plumbing already land in shared `permits` table — no gap there
- 44K orphan inspections have year-prefixed permit numbers (e.g., `2023xxxx`) that may not match code-prefixed building permits (e.g., `EW20xxxx`)
- Orphan inspections = rows in `inspections` where `permit_number NOT IN (SELECT permit_number FROM permits)`

**Investigation is TIME-BOXED to 30 minutes.** If root cause analysis is inconclusive, document findings and proceed with DQ checks. Do not block the session.

**TEMPLATE RENDERING WARNING:** If you add context processors or before_request hooks that depend on `request`, verify that email template rendering still works: `pytest tests/ -k "email" -v`. Email templates are rendered outside request context. Your context processor must handle `has_request_context() == False` gracefully.

---

## PHASE 2: BUILD

### Task C-1: Investigation — Orphan inspection root cause (~30 min MAX)
**No files modified — read-only investigation.**

Query the DuckDB database to understand orphan inspections:
```sql
-- Count orphans
SELECT COUNT(*) FROM inspections
WHERE permit_number NOT IN (SELECT permit_number FROM permits);

-- Sample orphan permit number formats
SELECT DISTINCT LEFT(permit_number, 4) as prefix, COUNT(*) as cnt
FROM inspections
WHERE permit_number NOT IN (SELECT permit_number FROM permits)
GROUP BY LEFT(permit_number, 4)
ORDER BY cnt DESC
LIMIT 20;

-- Check if orphans match boiler/fire permits
SELECT COUNT(*) FROM inspections i
WHERE i.permit_number NOT IN (SELECT permit_number FROM permits)
AND i.permit_number IN (SELECT permit_number FROM boiler_permits);

SELECT COUNT(*) FROM inspections i
WHERE i.permit_number NOT IN (SELECT permit_number FROM permits)
AND i.permit_number IN (SELECT permit_number FROM fire_permits);
```

Document findings in `CHANGELOG-qs5-c.md` under an "Investigation" section.

If orphans match trade permits → note which table and count.
If orphans are from an un-ingested dataset → document as BLOCKED-EXTERNAL with specifics.
If inconclusive at 30 min → proceed to Task C-2.

### Task C-2: Orphan inspection DQ check (~10 min)
**Files:** `web/data_quality.py` (append)

Add `_check_orphan_inspections()`:
- Count inspections where permit_number NOT IN permits table
- Calculate orphan percentage
- Thresholds: green < 5%, yellow 5-15%, red > 15%
- Return structured DQ result matching existing check patterns

### Task C-3: Trade permit count DQ check (~5 min)
**Files:** `web/data_quality.py` (append)

Add `_check_trade_permit_counts()`:
- Verify boiler_permits has > 0 rows
- Verify fire_permits has > 0 rows
- Return red if either table is empty (data pipeline broken)

### Task C-4: Add trade tables to EXPECTED_TABLES (~3 min)
**Files:** `web/app.py`

- Add `boiler_permits` and `fire_permits` to the EXPECTED_TABLES list
- Do NOT add DDL to `_run_startup_migrations()` (DDL is already in `src/db.py`)

### Task C-5: Verify trade ingest through _PgConnWrapper (~5 min)
**No new code — verification only.**

Read `src/ingest.py` `ingest_boiler_permits()` and `ingest_fire_permits()`. Verify they work through the `_PgConnWrapper` correctly (proper cursor usage, commit calls). If there's a bug, fix it. If they work fine, note "verified" in CHANGELOG.

### Task C-6: Write tests (~10 min)
**Files:** `tests/test_qs5_c_bridges.py` (NEW)

- _check_orphan_inspections returns structured DQ result
- Orphan check thresholds: green/yellow/red at correct boundaries
- _check_trade_permit_counts returns green when both tables have data
- _check_trade_permit_counts returns red when a table is empty
- EXPECTED_TABLES includes boiler_permits and fire_permits
- boiler_permits has block/lot columns (schema check)
- fire_permits does NOT have block/lot columns (schema check)

**Target: 10+ tests**

### Task C-7: QA script (~3 min)

### Task C-8: Scenarios (~3 min)

### Task C-9: CHANGELOG (~2 min)

---

## PHASE 3: TEST

```bash
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py -q
```

Run after EACH task.

---

## PHASE 4: SCENARIOS

Append 2 scenarios to BOTH:
- `scenarios-pending-review-qs5-c.md` (per-agent file)
- `scenarios-pending-review.md` (shared file, append only)

1. "Data quality dashboard shows orphan inspection rate with green/yellow/red thresholds"
2. "Trade permit pipeline health check flags empty boiler_permits or fire_permits tables"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs5-c-bridges-qa.md`:

```
1. [NEW] _check_orphan_inspections returns structured DQ result — PASS/FAIL
2. [NEW] Orphan inspection thresholds match spec (green <5%, yellow 5-15%, red >15%) — PASS/FAIL
3. [NEW] _check_trade_permit_counts returns green when both tables populated — PASS/FAIL
4. [NEW] _check_trade_permit_counts returns red when a table is empty — PASS/FAIL
5. [NEW] EXPECTED_TABLES includes boiler_permits and fire_permits — PASS/FAIL
6. [NEW] Investigation findings documented in CHANGELOG — PASS/FAIL
```

Save results to `qa-results/qs5-c-results.md`

---

## PHASE 5.5: VISUAL REVIEW

No UI pages in this session — skip visual review. Note "N/A — backend only" in CHECKCHAT.

---

## PHASE 6: CHECKCHAT

### 1. VERIFY
- All QA FAILs fixed or BLOCKED
- pytest passing, no regressions

### 2. DOCUMENT
- Write `CHANGELOG-qs5-c.md` with session entry (include investigation findings)

### 3. CAPTURE
- 2 scenarios in both files

### 4. SHIP
- Commit with: "feat: Trade permit bridge + orphan inspection DQ checks (QS5-C)"
- Report: files created, test count, QA results, investigation findings

### 5. PREP NEXT
- Note: investigation findings for orphan inspections — what follow-up is needed

### 6. BLOCKED ITEMS REPORT

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Actual |
|--------|--------|
| Wall clock time | [first commit to CHECKCHAT] |
| New tests | [count] |
| Tasks completed | [N of 9] |
| Scope changes | [count + reasons] |
| Waiting on | [count + reasons] |
| QA checks | [pass/fail/skip] |
| Scenarios proposed | [count] |
```

### Visual QA Checklist
- N/A — backend only, no UI changes

---

## File Ownership (Session C ONLY)
**Own:**
- `web/data_quality.py` (append orphan inspection + trade permit DQ checks)
- `web/app.py` (add boiler_permits + fire_permits to EXPECTED_TABLES only)
- `tests/test_qs5_c_bridges.py` (NEW)
- `CHANGELOG-qs5-c.md` (NEW)
- `scenarios-pending-review-qs5-c.md` (NEW)

**Do NOT touch:**
- `scripts/release.py` (Session A)
- `web/report.py` (Session A)
- `web/routes_cron.py` (Session A + B)
- `src/ingest.py` (Session B)
- `scripts/nightly_changes.py` (Session B)
- `web/templates/` (no template changes in this session)
