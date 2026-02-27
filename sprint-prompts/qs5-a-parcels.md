<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs5-a-parcels.md and execute it" -->

# Quad Sprint 5 — Session A: Materialized Parcels Table

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs5-a
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs5-a before any code changes.
MERGE RULE: Do NOT merge your branch to main. Commit to worktree branch only. The orchestrator (Tab 0) merges all branches.
CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files. If you encounter a conflict, stop and report it.
APPEND FILES:
  - scenarios-pending-review-qs5-a.md (per-agent, for merge safety)
  - scenarios-pending-review.md (shared, append only — for stop hook compliance)
  - CHANGELOG-qs5-a.md (per-agent)
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
   Use EnterWorktree with name `qs5-a`

If worktree exists: `git worktree remove .claude/worktrees/qs5-a --force 2>/dev/null; true`

4. **Safety tag:** `git tag pre-qs5-a`

---

## PHASE 1: READ

Read these files before writing any code:
1. `CLAUDE.md` — project structure, deployment, rules
2. `web/report.py` — current `_fetch_property()` SODA call, `generate_property_report()`
3. `scripts/release.py` — existing DDL migration pattern
4. `web/app.py` lines 700-780 — `_run_startup_migrations()` + EXPECTED_TABLES
5. `web/routes_cron.py` — existing cron endpoint pattern
6. `src/db.py` lines 1280-1400 — existing table schemas for reference
7. `scenario-design-guide.md` — for scenario-keyed QA

**Architecture notes:**
- Templates are SELF-CONTAINED (no base.html, no Jinja inheritance, inline Obsidian CSS vars)
- report.py currently makes 3 live SODA API calls per property report. This eliminates 1 (tax data).
- tax_rolls table exists locally but report.py ignores it — uses SODA API instead. This fixes that.
- property_health already materializes signal tiers nightly — parcel_summary LEFT JOINs it.
- fire_permits has NO block/lot columns — excluded from parcel counts.

**TEMPLATE RENDERING WARNING:** If you add context processors or before_request hooks that depend on `request`, verify that email template rendering still works: `pytest tests/ -k "email" -v`. Email templates are rendered outside request context. Your context processor must handle `has_request_context() == False` gracefully.

---

## PHASE 2: BUILD

### Task A-1: parcel_summary DDL (~5 min)
**Files:** `scripts/release.py` (append)

Add to release.py migrations:
```sql
CREATE TABLE IF NOT EXISTS parcel_summary (
    block TEXT NOT NULL, lot TEXT NOT NULL,
    canonical_address TEXT, neighborhood TEXT, supervisor_district TEXT,
    permit_count INTEGER DEFAULT 0, open_permit_count INTEGER DEFAULT 0,
    complaint_count INTEGER DEFAULT 0, violation_count INTEGER DEFAULT 0,
    boiler_permit_count INTEGER DEFAULT 0, inspection_count INTEGER DEFAULT 0,
    tax_value DOUBLE PRECISION, zoning_code TEXT, use_definition TEXT,
    number_of_units INTEGER, health_tier TEXT, last_permit_date TEXT,
    refreshed_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (block, lot)
);
```

### Task A-2: Register in app.py (~3 min)
**Files:** `web/app.py`

- Add `parcel_summary` to `EXPECTED_TABLES` list
- Add the DDL call to `_run_startup_migrations()` (for DuckDB test env)

### Task A-3: Cron refresh endpoint (~15 min)
**Files:** `web/routes_cron.py` (append)

Add `POST /cron/refresh-parcel-summary`:
- CRON_SECRET auth
- INSERT...SELECT joining permits, tax_rolls, complaints, violations, boiler_permits, property_health
- ON CONFLICT (block, lot) DO UPDATE
- `canonical_address` normalization: `UPPER(street_number || ' ' || street_name)` from the most recent filed permit at each parcel. Source priority: (1) most recent permit with non-null address, (2) tax_rolls property_location, (3) NULL.
- Correlated subquery counts for complaints, violations, boiler_permits, inspections
- Returns count of parcels refreshed

### Task A-4: Wire into report.py (~10 min)
**Files:** `web/report.py`

In `generate_property_report()` or `_fetch_property()`:
- Before SODA gather, query parcel_summary for the given block/lot
- If found: use tax_value, zoning_code, use_definition, neighborhood from parcel_summary
- Skip the `_fetch_property()` SODA API call
- Fallback: if parcel_summary has no row, fall through to existing SODA call
- Keep complaints/violations SODA calls live (those need real-time data)

### Task A-5: Write tests (~10 min)
**Files:** `tests/test_qs5_a_parcels.py` (NEW)

- parcel_summary table created successfully
- POST /cron/refresh-parcel-summary requires CRON_SECRET
- POST /cron/refresh-parcel-summary returns count
- parcel_summary has correct columns (block, lot, canonical_address, etc.)
- canonical_address is UPPER-cased
- report.py uses parcel_summary when row exists
- report.py falls back to SODA when no parcel_summary row
- EXPECTED_TABLES includes parcel_summary
- _run_startup_migrations creates the table in DuckDB

**Target: 12+ tests**

### Task A-6: QA script + screenshots (~5 min)

### Task A-7: Scenarios (~3 min)

### Task A-8: CHANGELOG (~2 min)

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
- `scenarios-pending-review-qs5-a.md` (per-agent file)
- `scenarios-pending-review.md` (shared file, append only)

1. "Property report loads tax/zoning data from parcel_summary cache instead of live SODA API"
2. "Nightly parcel refresh materializes counts from 5 source tables into one-row-per-parcel cache"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs5-a-parcels-qa.md`:

```
1. [NEW] parcel_summary table created in DuckDB — PASS/FAIL
2. [NEW] POST /cron/refresh-parcel-summary requires auth — PASS/FAIL
3. [NEW] POST /cron/refresh-parcel-summary populates rows — PASS/FAIL
4. [NEW] canonical_address is UPPER-cased — PASS/FAIL
5. [NEW] report.py uses parcel_summary when available — PASS/FAIL
6. [NEW] report.py falls back to SODA when parcel_summary empty — PASS/FAIL
```

Save results to `qa-results/qs5-a-results.md`

---

## PHASE 6: CHECKCHAT

### 1. VERIFY
- All QA FAILs fixed or BLOCKED
- pytest passing, no regressions

### 2. DOCUMENT
- Write `CHANGELOG-qs5-a.md` with session entry

### 3. CAPTURE
- 2 scenarios in both files

### 4. SHIP
- Commit with: "feat: Materialized parcels table + report.py optimization (QS5-A)"
- Report: files created, test count, QA results

### 5. PREP NEXT
- Note: parcel_summary needs adding to nightly cron schedule on Railway

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
- [ ] /report page: does it still render correctly with cached data?

---

## File Ownership (Session A ONLY)
**Own:**
- `scripts/release.py` (append parcel_summary DDL)
- `web/app.py` (add to _run_startup_migrations + EXPECTED_TABLES)
- `web/report.py` (replace _fetch_property SODA call with DB lookup)
- `web/routes_cron.py` (append refresh-parcel-summary endpoint)
- `tests/test_qs5_a_parcels.py` (NEW)
- `CHANGELOG-qs5-a.md` (NEW)
- `scenarios-pending-review-qs5-a.md` (NEW)

**Do NOT touch:**
- `scripts/nightly_changes.py` (Session B)
- `src/ingest.py` (Session B)
- `web/data_quality.py` (Session C)
- `web/security.py`
- `web/templates/` (no template changes in this session)
