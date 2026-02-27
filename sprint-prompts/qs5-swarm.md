<!-- LAUNCH: Paste into a single CC terminal (Opus):
     "Read sprint-prompts/qs5-swarm.md and execute it" -->

# QS5 Swarm Orchestrator — Data Completeness

You are the **swarm orchestrator** for Quad Sprint 5 (Sprint 73). You will spawn 4 parallel build agents via the Task tool, collect their results, merge their branches, run the test suite once, and push.

## Pre-flight

1. Verify you are in the main repo root: `/Users/timbrenneman/AIprojects/sf-permits-mcp`
2. `git checkout main && git pull origin main`
3. `git log --oneline -3` — verify HEAD is clean
4. Verify prod tables exist:
   ```
   curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -c "
   import sys,json; d=json.load(sys.stdin)
   tables = d.get('tables',{})
   for t in ['boiler_permits','fire_permits']:
       print(f'{t}: {\"EXISTS\" if t in tables else \"MISSING\"} ({tables.get(t,0)} rows)')
   "
   ```
   **STOP if any table is MISSING.**

---

## Launch: Spawn 4 Agents in Parallel

Use the **Task tool** to spawn all 4 agents SIMULTANEOUSLY in a single message. Each agent:
- `subagent_type: "general-purpose"`
- `model: "sonnet"`
- `isolation: "worktree"`

### Agent A: Materialized Parcels Table

```
prompt: |
  You are QS5 Agent A — Materialized Parcels Table.
  You are a build agent following Black Box Protocol v1.3.

  You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
  Your working directory is your isolated worktree copy of the repo.

  ## Agent Rules
  SAFETY TAG: git tag pre-qs5-a before any code changes.
  MERGE RULE: Do NOT merge to main. Commit to your worktree branch only.
  CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files.
  APPEND FILES:
    - scenarios-pending-review-qs5-a.md (per-agent, for merge safety)
    - scenarios-pending-review.md (shared, append only — for stop hook compliance)
    - CHANGELOG-qs5-a.md (per-agent)
  TEST FIXUP EXCEPTION: If your code changes cause tests in files you don't own to fail, you MAY fix those tests. Limit fixes to assertion updates. Document in CHANGELOG.

  ## READ (before any code)
  1. CLAUDE.md — project structure, deployment, rules
  2. web/report.py — current _fetch_property() SODA call, generate_property_report()
  3. scripts/release.py — existing DDL migration pattern
  4. web/app.py lines 700-780 — _run_startup_migrations() + EXPECTED_TABLES
  5. web/routes_cron.py — existing cron endpoint pattern
  6. src/db.py lines 1280-1400 — existing table schemas

  Architecture notes:
  - report.py currently makes 3 live SODA API calls per property report. This eliminates 1 (tax data).
  - tax_rolls table exists locally but report.py ignores it — uses SODA API instead.
  - property_health already materializes signal tiers nightly — parcel_summary LEFT JOINs it.
  - fire_permits has NO block/lot columns — excluded from parcel counts.

  TEMPLATE RENDERING WARNING: If you add context processors or before_request hooks that depend on `request`, verify email templates still work: `pytest tests/ -k "email" -v`

  ## BUILD

  ### Task A-1: parcel_summary DDL
  Files: scripts/release.py (append)
  Add parcel_summary DDL:
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

  ### Task A-2: Register in app.py
  Files: web/app.py
  - Add parcel_summary to EXPECTED_TABLES list
  - Add DDL call to _run_startup_migrations() (for DuckDB test env)

  ### Task A-3: Cron refresh endpoint
  Files: web/routes_cron.py (append)
  Add POST /cron/refresh-parcel-summary:
  - CRON_SECRET auth
  - INSERT...SELECT joining permits, tax_rolls, complaints, violations, boiler_permits, property_health
  - ON CONFLICT (block, lot) DO UPDATE
  - canonical_address: UPPER(street_number || ' ' || street_name) from most recent filed permit
  - Correlated subquery counts for complaints, violations, boiler_permits, inspections
  - Returns count of parcels refreshed

  ### Task A-4: Wire into report.py
  Files: web/report.py
  In generate_property_report() or _fetch_property():
  - Before SODA gather, query parcel_summary for block/lot
  - If found: use tax_value, zoning_code, use_definition, neighborhood
  - Skip _fetch_property() SODA call
  - Fallback to SODA if no parcel_summary row

  ### Task A-5: Write tests
  Files: tests/test_qs5_a_parcels.py (NEW)
  - parcel_summary table created successfully
  - POST /cron/refresh-parcel-summary requires CRON_SECRET
  - POST /cron/refresh-parcel-summary returns count
  - canonical_address is UPPER-cased
  - report.py uses parcel_summary when row exists
  - report.py falls back to SODA when no parcel_summary row
  - EXPECTED_TABLES includes parcel_summary
  - _run_startup_migrations creates the table
  Target: 12+ tests

  ## TEST
  source .venv/bin/activate && pytest tests/ --ignore=tests/test_tools.py -q
  Run after EACH task.

  ## SCENARIOS
  Append 2 scenarios to BOTH scenarios-pending-review-qs5-a.md AND scenarios-pending-review.md:
  1. "Property report loads tax/zoning data from parcel_summary cache instead of live SODA API"
  2. "Nightly parcel refresh materializes counts from 5 source tables into one-row-per-parcel cache"

  ## QA
  Write qa-drop/qs5-a-parcels-qa.md with PASS/FAIL checks.
  Save results to qa-results/qs5-a-results.md

  ## SHIP
  Commit: "feat: Materialized parcels table + report.py optimization (QS5-A)"

  ## File Ownership
  Own: scripts/release.py, web/app.py (parcel_summary DDL + EXPECTED), web/report.py, web/routes_cron.py (refresh-parcel-summary), tests/test_qs5_a_parcels.py
  Do NOT touch: src/ingest.py, scripts/nightly_changes.py, web/data_quality.py
```

### Agent B: Permit Changes Backfill

```
prompt: |
  You are QS5 Agent B — Permit Changes Backfill.
  You are a build agent following Black Box Protocol v1.3.

  You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.

  ## Agent Rules
  SAFETY TAG: git tag pre-qs5-b before any code changes.
  MERGE RULE: Do NOT merge to main. Commit to your worktree branch only.
  CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files.
  APPEND FILES:
    - scenarios-pending-review-qs5-b.md (per-agent)
    - scenarios-pending-review.md (shared, append only)
    - CHANGELOG-qs5-b.md (per-agent)
  TEST FIXUP EXCEPTION: If your code changes cause tests in files you don't own to fail, you MAY fix those tests. Limit fixes to assertion updates. Document in CHANGELOG.

  ## READ
  1. CLAUDE.md — project structure
  2. scripts/nightly_changes.py — change detection pipeline, detect_nightly_changes(), fetch_recent_boiler_permits()
  3. src/ingest.py — run_ingestion() pipeline, existing ingest patterns
  4. web/routes_cron.py — existing cron endpoints, CRON_SECRET auth
  5. src/db.py lines 1-50 — BACKEND detection

  Architecture notes:
  - permit_changes: 2,764 rows, 1,435 orphans (52%). Prefixes: 26B- (1,271), 26EX (73), 2026 (33).
  - run_ingestion() does DELETE + re-INSERT (full table replace). Incremental must NOT run concurrently.
  - Sequencing guard: ingest_recent_permits() must run BEFORE detect_nightly_changes(), and NEVER concurrently with run_ingestion(). Check cron_log for full_ingest in last hour; if found, skip and log.

  ## BUILD

  ### Task B-1: ingest_recent_permits() function
  Files: src/ingest.py (append)
  Add ingest_recent_permits(conn, client, days=30):
  - SODA query with date filter for last 30 days
  - INSERT ON CONFLICT DO UPDATE (upsert)
  - Return count

  ### Task B-2: Cron endpoint
  Files: web/routes_cron.py (append)
  Add POST /cron/ingest-recent-permits:
  - CRON_SECRET auth
  - Check cron_log for recent full_ingest (< 1 hour). If found, skip.
  - Call ingest_recent_permits()
  - Return count

  ### Task B-3: --backfill mode
  Files: scripts/nightly_changes.py (add CLI flag)
  Add --backfill:
  - Query orphan permit_changes (permit_number NOT IN permits)
  - Fetch from SODA in batches of 50
  - Upsert into permits
  - Report counts

  ### Task B-4: Wire into pipeline
  Ensure ingest_recent_permits() runs BEFORE detect_nightly_changes(). Document ordering.

  ### Task B-5: Write tests
  Files: tests/test_qs5_b_backfill.py (NEW)
  - ingest_recent_permits returns count
  - ON CONFLICT DO UPDATE works
  - POST /cron/ingest-recent-permits requires CRON_SECRET
  - Sequencing guard skips if full_ingest ran recently
  - --backfill flag exists
  - Pipeline ordering correct
  Target: 10+ tests

  ## TEST
  source .venv/bin/activate && pytest tests/ --ignore=tests/test_tools.py -q

  ## SCENARIOS
  Append 2 to BOTH files:
  1. "Incremental permit ingest reduces orphan rate from 52% to under 10%"
  2. "Nightly pipeline runs incremental ingest before change detection"

  ## QA
  Write qa-drop/qs5-b-backfill-qa.md. Save results to qa-results/qs5-b-results.md

  ## SHIP
  Commit: "feat: Permit changes backfill + incremental ingest (QS5-B)"

  ## File Ownership
  Own: src/ingest.py (append), scripts/nightly_changes.py, web/routes_cron.py (append ingest-recent-permits)
  Do NOT touch: scripts/release.py, web/app.py, web/report.py, web/data_quality.py
```

### Agent C: Trade Permit Bridge + Orphan Inspections

```
prompt: |
  You are QS5 Agent C — Trade Permit Bridge + Orphan Inspections.
  You are a build agent following Black Box Protocol v1.3.

  You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.

  ## Agent Rules
  SAFETY TAG: git tag pre-qs5-c before any code changes.
  MERGE RULE: Do NOT merge to main. Commit to your worktree branch only.
  CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files.
  APPEND FILES:
    - scenarios-pending-review-qs5-c.md (per-agent)
    - scenarios-pending-review.md (shared, append only)
    - CHANGELOG-qs5-c.md (per-agent)
  TEST FIXUP EXCEPTION: If your code changes cause tests in files you don't own to fail, you MAY fix those tests.

  ## READ
  1. CLAUDE.md
  2. web/data_quality.py — existing DQ check patterns
  3. web/app.py lines 700-780 — _run_startup_migrations() + EXPECTED_TABLES
  4. src/db.py lines 1036-1080 — boiler_permits + fire_permits DDL
  5. src/ingest.py — ingest_boiler_permits(), ingest_fire_permits()

  Architecture notes:
  - boiler_permits: 151K rows on prod, HAS block/lot columns
  - fire_permits: 84K rows on prod, NO block/lot columns
  - 44K orphan inspections may have year-prefixed permit numbers vs code-prefixed building permits
  - Investigation is TIME-BOXED to 30 minutes max

  ## BUILD

  ### Task C-1: Investigation — Orphan inspection root cause (30 min MAX)
  Read-only. Query DuckDB:
  - Count orphans (inspections WHERE permit_number NOT IN permits)
  - Sample orphan permit number formats (LEFT(permit_number, 4) grouping)
  - Check if orphans match boiler_permits or fire_permits
  Document findings in CHANGELOG-qs5-c.md. If inconclusive at 30 min, proceed.

  ### Task C-2: Orphan inspection DQ check
  Files: web/data_quality.py (append)
  Add _check_orphan_inspections():
  - Count orphan percentage
  - Thresholds: green <5%, yellow 5-15%, red >15%

  ### Task C-3: Trade permit count DQ check
  Files: web/data_quality.py (append)
  Add _check_trade_permit_counts():
  - Verify boiler_permits > 0 rows, fire_permits > 0 rows
  - Red if either empty

  ### Task C-4: Add trade tables to EXPECTED_TABLES
  Files: web/app.py
  Add boiler_permits and fire_permits to EXPECTED_TABLES list only.
  Do NOT add DDL to _run_startup_migrations() (already in src/db.py).

  ### Task C-5: Verify trade ingest through _PgConnWrapper
  Read-only verification. Check ingest_boiler_permits() and ingest_fire_permits() work correctly. Fix if buggy, note "verified" if fine.

  ### Task C-6: Write tests
  Files: tests/test_qs5_c_bridges.py (NEW)
  - _check_orphan_inspections returns structured DQ result
  - Thresholds correct (green/yellow/red)
  - _check_trade_permit_counts returns green when populated, red when empty
  - EXPECTED_TABLES includes boiler_permits and fire_permits
  Target: 10+ tests

  ## TEST
  source .venv/bin/activate && pytest tests/ --ignore=tests/test_tools.py -q

  ## SCENARIOS
  Append 2 to BOTH files:
  1. "Data quality dashboard shows orphan inspection rate with green/yellow/red thresholds"
  2. "Trade permit pipeline health check flags empty boiler_permits or fire_permits tables"

  ## QA
  Write qa-drop/qs5-c-bridges-qa.md. Save results to qa-results/qs5-c-results.md

  ## SHIP
  Commit: "feat: Trade permit bridge + orphan inspection DQ checks (QS5-C)"

  ## File Ownership
  Own: web/data_quality.py (append), web/app.py (EXPECTED_TABLES only), tests/test_qs5_c_bridges.py
  Do NOT touch: scripts/release.py, web/report.py, web/routes_cron.py, src/ingest.py, scripts/nightly_changes.py
```

### Agent D: Task Hygiene Diagnostic Sweep

```
prompt: |
  You are QS5 Agent D — Task Hygiene Diagnostic Sweep.
  You are a build agent following Black Box Protocol v1.3.

  You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
  This is a READ-ONLY investigation session. NO code changes. NO new tests.

  ## Agent Rules
  MERGE RULE: Do NOT merge to main.
  APPEND FILES:
    - scenarios-pending-review-qs5-d.md (per-agent)
    - scenarios-pending-review.md (shared, append only)
    - CHANGELOG-qs5-d.md (per-agent)
  OUTPUT: Chief brain state updates only (chief_add_note, chief_complete_task, chief_add_task).

  ## READ
  1. CLAUDE.md
  2. CHANGELOG.md — recent changes

  Then use chief_get_brain_state to read the full task list.

  ## INVESTIGATE

  For each item, read the relevant code, decide: CLOSE, UPDATE, or NEW TASK.

  1. Addenda nightly refresh (Chief #127) — does POST /cron/refresh-addenda exist?
  2. Inspections upsert PK collision (Chief #112) — still happening?
  3. Pre-build safety tagging (Chief #159) — solved by sprint prompt SAFETY TAG rule?
  4. Cost tracking middleware (Chief #143) — what DDL/routes exist? What's wired?
  5. Playwright test suite scope (Chief #220) — how many tests now?
  6. Test persona accounts (Chief #222) — still needed?
  7. CRON_SECRET 403 issue (Chief #179) — still happening?
  8. 5 failing DQ checks on prod (Chief #178) — current state?
  9. property_signals populating (Chief #261) — pipeline working?
  10. Orphaned test files (Chief #207) — any tests without matching source?
  11. Slow test_analyze_plans (Chief #210) — current runtime?
  12. Nightly CI verified (Chief #209) — GH Actions or Railway cron running?

  For each: call chief_complete_task, chief_add_task, or chief_add_note as appropriate.
  Write a summary note via chief_add_note at the end.

  ## SCENARIOS
  Append 1 to BOTH files:
  1. "Admin reviews stale task inventory and sees current status for each infrastructure item"

  ## QA
  Write qa-drop/qs5-d-hygiene-qa.md (document review, not code testing).
  Save results to qa-results/qs5-d-results.md

  ## SHIP
  Commit: "docs: Task hygiene diagnostic sweep (QS5-D)"
```

---

## Post-Merge (Orchestrator executes after all 4 agents complete)

After all 4 Task agents return:

### 1. Collect Results
Read each agent's result. Note any BLOCKED items.

### 2. Merge (Fast Merge Protocol)
```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Merge in dependency order — all at once
git merge <agent-a-branch>
git merge <agent-b-branch>
git merge <agent-c-branch>
# Agent D may have no code changes — merge if it has commits
git merge <agent-d-branch> 2>/dev/null || true
```

The branch names will be in each Task agent's return value (worktree branch names).

### 3. Single Test Run
```bash
source .venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py -q

# QS5-specific tests
pytest tests/test_qs5_a_parcels.py tests/test_qs5_b_backfill.py tests/test_qs5_c_bridges.py -v
```

If tests fail: bisect by reverting last merge, re-test. Fix conflicts. Do NOT run tests between each merge.

### 4. Push
```bash
git push origin main
```

### 5. Verify Deployment
```bash
curl -s https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool
```

### 6. Consolidate Agent Artifacts
Concatenate per-agent changelogs into CHANGELOG.md. Concatenate per-agent scenarios into scenarios-pending-review.md (dedup). Commit consolidated artifacts.

### 7. Report
Output a summary table:

| Agent | Status | Tests | Scenarios | Blocked |
|-------|--------|-------|-----------|---------|
| A: Parcels | [result] | [count] | [count] | [items] |
| B: Backfill | [result] | [count] | [count] | [items] |
| C: Bridges | [result] | [count] | [count] | [items] |
| D: Hygiene | [result] | N/A | [count] | [items] |

---

## Shared File Conflict Protocol

| File | Agent A | Agent B | Agent C |
|------|---------|---------|---------|
| web/app.py | parcel_summary DDL + EXPECTED | — | boiler/fire to EXPECTED only |
| scripts/release.py | parcel_summary DDL | — | — |
| web/routes_cron.py | refresh-parcel-summary | ingest-recent-permits | — |
| src/ingest.py | — | ingest_recent_permits() | — |

Merge order: A first, then B, then C. Agent D has no code changes.
