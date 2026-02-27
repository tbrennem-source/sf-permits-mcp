<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs5-b-backfill.md and execute it" -->

# Quad Sprint 5 — Session B: Permit Changes Backfill

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs5-b
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs5-b before any code changes.
MERGE RULE: Do NOT merge your branch to main. Commit to worktree branch only. The orchestrator (Tab 0) merges all branches.
CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files. If you encounter a conflict, stop and report it.
APPEND FILES:
  - scenarios-pending-review-qs5-b.md (per-agent, for merge safety)
  - scenarios-pending-review.md (shared, append only — for stop hook compliance)
  - CHANGELOG-qs5-b.md (per-agent)
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
   Use EnterWorktree with name `qs5-b`

If worktree exists: `git worktree remove .claude/worktrees/qs5-b --force 2>/dev/null; true`

4. **Safety tag:** `git tag pre-qs5-b`

---

## PHASE 1: READ

Read these files before writing any code:
1. `CLAUDE.md` — project structure, deployment, rules
2. `scripts/nightly_changes.py` — current change detection pipeline, `detect_nightly_changes()`, `fetch_recent_boiler_permits()`
3. `src/ingest.py` — `run_ingestion()` pipeline, existing ingest patterns
4. `web/routes_cron.py` — existing cron endpoints, CRON_SECRET auth pattern
5. `src/db.py` lines 1-50 — BACKEND detection, get_connection()
6. `scenario-design-guide.md` — for scenario-keyed QA

**Architecture notes:**
- permit_changes: 2,764 rows, 1,435 orphans (52%). Prefixes: `26B-` (1,271), `26EX` (73), `2026` (33).
- These are real 2026 permits the nightly tracker found but the bulk permits table hasn't refreshed to include.
- `run_ingestion()` does DELETE + re-INSERT (full table replace). An incremental ingest must NOT run concurrently.
- `detect_nightly_changes()` in nightly_changes.py runs via `POST /cron/detect-changes`.

**Sequencing guard:** `ingest_recent_permits()` must run BEFORE `detect_nightly_changes()` in the pipeline, and must NEVER run concurrently with `run_ingestion()` (full ingest). Add a check: if `cron_log` shows a `full_ingest` job running or completed in the last hour, skip the incremental ingest and log why.

**TEMPLATE RENDERING WARNING:** If you add context processors or before_request hooks that depend on `request`, verify that email template rendering still works: `pytest tests/ -k "email" -v`. Email templates are rendered outside request context. Your context processor must handle `has_request_context() == False` gracefully.

---

## PHASE 2: BUILD

### Task B-1: ingest_recent_permits() function (~10 min)
**Files:** `src/ingest.py` (append)

Add `ingest_recent_permits(conn, client, days=30)`:
- SODA query to `5xp9-gcjq` (permits endpoint) with `$where=filed_date > '...'` for last N days
- INSERT ... ON CONFLICT (permit_number) DO UPDATE — upsert, not full replace
- Return count of rows upserted
- Add docstring explaining: this is incremental, NOT a replacement for run_ingestion()

### Task B-2: Cron endpoint (~5 min)
**Files:** `web/routes_cron.py` (append)

Add `POST /cron/ingest-recent-permits`:
- CRON_SECRET auth
- Check `cron_log` for recent `full_ingest` jobs (< 1 hour). If found, skip and return `{"ok": True, "skipped": true, "reason": "full ingest completed recently"}`
- Call `ingest_recent_permits(conn, client, days=30)`
- Return count of permits upserted

### Task B-3: --backfill mode for nightly_changes.py (~10 min)
**Files:** `scripts/nightly_changes.py` (add CLI flag)

Add `--backfill` flag:
- Query permit_changes for rows where permit_number NOT IN permits table (orphans)
- For each orphan batch (chunks of 50), fetch from SODA by permit_number
- Upsert into permits table
- Report: N orphans found, M successfully backfilled, K still missing

### Task B-4: Wire into nightly pipeline (~5 min)
**Files:** `scripts/nightly_changes.py` or `web/routes_cron.py`

Ensure `ingest_recent_permits()` runs BEFORE `detect_nightly_changes()` in the nightly pipeline sequence. Document the ordering in a code comment.

### Task B-5: Write tests (~10 min)
**Files:** `tests/test_qs5_b_backfill.py` (NEW)

- ingest_recent_permits returns count of upserted rows
- ingest_recent_permits does ON CONFLICT DO UPDATE (not error)
- POST /cron/ingest-recent-permits requires CRON_SECRET
- POST /cron/ingest-recent-permits returns count
- Sequencing guard: skips if full_ingest ran recently
- --backfill flag exists in nightly_changes.py argparse
- Backfill queries orphan permit_changes correctly
- Pipeline ordering: recent-permits before detect-changes

**Target: 10+ tests**

### Task B-6: QA script (~3 min)

### Task B-7: Scenarios (~3 min)

### Task B-8: CHANGELOG (~2 min)

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
- `scenarios-pending-review-qs5-b.md` (per-agent file)
- `scenarios-pending-review.md` (shared file, append only)

1. "Incremental permit ingest reduces orphan rate in permit_changes from 52% to under 10%"
2. "Nightly pipeline runs incremental ingest before change detection to prevent false orphans"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs5-b-backfill-qa.md`:

```
1. [NEW] ingest_recent_permits() returns integer count — PASS/FAIL
2. [NEW] POST /cron/ingest-recent-permits requires CRON_SECRET — PASS/FAIL
3. [NEW] POST /cron/ingest-recent-permits returns upserted count — PASS/FAIL
4. [NEW] Sequencing guard skips when full_ingest ran recently — PASS/FAIL
5. [NEW] --backfill flag accepted by nightly_changes.py — PASS/FAIL
6. [NEW] Pipeline ordering is documented in code — PASS/FAIL
```

Save results to `qa-results/qs5-b-results.md`

---

## PHASE 5.5: VISUAL REVIEW

No UI pages in this session — skip visual review. Note "N/A — backend only" in CHECKCHAT.

---

## PHASE 6: CHECKCHAT

### 1. VERIFY
- All QA FAILs fixed or BLOCKED
- pytest passing, no regressions

### 2. DOCUMENT
- Write `CHANGELOG-qs5-b.md` with session entry

### 3. CAPTURE
- 2 scenarios in both files

### 4. SHIP
- Commit with: "feat: Permit changes backfill + incremental ingest (QS5-B)"
- Report: files created, test count, QA results

### 5. PREP NEXT
- Note: run --backfill once manually on prod after merge to clear existing orphans

### 6. BLOCKED ITEMS REPORT

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Actual |
|--------|--------|
| Wall clock time | [first commit to CHECKCHAT] |
| New tests | [count] |
| Tasks completed | [N of 8] |
| Scope changes | [count + reasons] |
| Waiting on | [count + reasons] |
| QA checks | [pass/fail/skip] |
| Scenarios proposed | [count] |
```

### Visual QA Checklist
- N/A — backend only, no UI changes

---

## File Ownership (Session B ONLY)
**Own:**
- `src/ingest.py` (append ingest_recent_permits function)
- `scripts/nightly_changes.py` (add --backfill flag + pipeline ordering)
- `web/routes_cron.py` (append ingest-recent-permits endpoint)
- `tests/test_qs5_b_backfill.py` (NEW)
- `CHANGELOG-qs5-b.md` (NEW)
- `scenarios-pending-review-qs5-b.md` (NEW)

**Do NOT touch:**
- `scripts/release.py` (Session A)
- `web/app.py` (Session A + C)
- `web/report.py` (Session A)
- `web/data_quality.py` (Session C)
- `web/templates/` (no template changes in this session)
