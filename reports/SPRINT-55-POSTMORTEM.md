# Sprint 55 Post-Mortem

**Sprint:** 55 (Wave 1: A/B/D/E parallel, Wave 2: C sequential, Wave 3: G docs)
**Date:** 2026-02-25
**Status:** All 6 agents COMPLETE, merged, deployed to staging. Prod promotion pending.

## What Went Well

- **Swarm execution recovered from Wave 1 loss.** Wave 1 initially lost to worktree collision (from earlier session). Clean re-run from main repo root succeeded — all 4 agents completed and merged.
- **Merge conflict resolution was clean.** Agents B and E both added migrations to `run_prod_migrations.py`. Conflict was structural (both added to the same registry list), resolved by keeping both and updating the count assertion from 9 to 10.
- **Test growth significant.** 1,820 → 1,964 (+144 tests across 6 agents). Zero regressions after full merge.
- **Agent isolation worked.** File ownership boundaries held — no agents stomped on each other's work outside the expected `run_prod_migrations.py` overlap.

## What Went Wrong

### P0: Stateful Deployment — Code Deploys But System Isn't Ready

This was the sprint's central failure. Five distinct bugs surfaced during staging verification, all sharing a common root cause: **the protocol assumes deployment is atomic (push → deploy → done), but Sprint 55 introduced stateful deployment where the system requires post-deploy operations (migrations, data ingest) to be functional.**

The protocol had no mechanism for:
- Verifying schema changes succeeded on Postgres
- Running data ingest endpoints and monitoring for completion
- Diagnosing and fixing failures discovered only at deploy time
- Retrying after fixing mid-deployment issues

**Time lost:** ~90 minutes of iterative diagnosis and fixing during what should have been a handoff to DeskRelay.

#### Bug 1: Schema Migration Transaction Failure

**Symptom:** All 8 new tables MISSING from staging /health despite code being deployed.

**Root cause:** `postgres_schema.sql` runs as a single transaction. Agent E added a `CREATE UNIQUE INDEX` on the inspections table that fails when duplicate rows exist. The failure rolled back the entire transaction, preventing all 5 new data tables and 3 reference tables from being created.

**Why agents missed it:** All agents test against DuckDB locally. DuckDB handles `CREATE UNIQUE INDEX` differently (no pre-existing duplicate data in test fixtures). The Postgres-specific failure path was untested.

**Fix:** Removed the UNIQUE index from `postgres_schema.sql` (it belongs in the dedicated `_run_inspections_unique` migration which deduplicates first). Added a comment explaining why.

#### Bug 2: INSERT OR REPLACE → Postgres Crash

**Symptom:** Cron ingest endpoints returned 500 with `UniqueViolation` errors.

**Root cause:** `_PgConnWrapper._translate_sql()` converts `INSERT OR REPLACE INTO` to plain `INSERT INTO` for Postgres, but without adding `ON CONFLICT` handling. When SODA API returns batches with duplicate `record_id` values, the plain INSERT crashes.

**Why agents missed it:** DuckDB natively supports `INSERT OR REPLACE`. The Postgres translation wrapper had a special case for `cron_log` (which has its own `ON CONFLICT` clause) but no general handling.

**Fix:** Added `ON CONFLICT DO NOTHING` fallback for all INSERT statements in the Postgres wrapper. Safe because ingest functions DELETE-then-INSERT, so duplicates in a batch are harmless.

#### Bug 3: CRON_SECRET Display Truncation

**Symptom:** `railway variables list` shows 32-character secret; staging expects 64 characters. Auth returns 403.

**Root cause:** Railway CLI table display wraps the 64-character CRON_SECRET across 2 lines. Without `od -c` or similar, the second line is invisible. The Sprint 54 `.strip()` fix handles trailing whitespace but not display truncation.

**Why agents missed it:** Build agents don't interact with Railway CLI. The orchestrator assumed the CLI output was the complete value.

**Fix:** Used `od -c` to reveal the full value. No code change needed — this is an operator knowledge gap.

#### Bug 4: Gunicorn Timeout on Large Ingest

**Symptom:** Street-use ingest (1.2M rows) killed by gunicorn worker timeout after 300s. Zero rows landed.

**Root cause:** Two compounding issues:
1. `nixpacks.toml` and `web/railway.toml` had 300s timeout (Procfile had 600s but Railway uses the toml configs)
2. Streaming ingest flushed batches every 50K rows but never committed — entire transaction rolled back on timeout

**Why agents missed it:** Agent A tested the streaming code locally against DuckDB where it completes in ~60s. No timeout simulation in tests.

**Fix:** Bumped timeout to 600s. Added `conn.commit()` after each batch flush so partial data survives timeouts.

#### Bug 5: Auto-Deploy Not Triggering

**Symptom:** `git push origin main` succeeded but Railway didn't build a new deployment.

**Root cause:** Unknown — possibly a Railway platform lag or webhook delivery failure. An empty commit + push 3 minutes later triggered the build.

**Impact:** Minor (3 minutes lost), but could have been worse if not noticed.

### P1: DuckDB vs Postgres Divergence (Systemic)

Bugs 1, 2, and 4 are all instances of the same systemic problem: **code tested on DuckDB behaves differently on Postgres.** This has been a recurring theme across sprints:

| Sprint | Bug | DuckDB Behavior | Postgres Behavior |
|--------|-----|-----------------|-------------------|
| 54 | CRON_SECRET whitespace | N/A (env var issue) | `.strip()` needed |
| 55 | UNIQUE index on dirty data | Succeeds (clean test data) | Fails (duplicates in prod) |
| 55 | INSERT OR REPLACE | Native support | Must translate to ON CONFLICT |
| 55 | Streaming ingest timeout | Completes fast | Killed by gunicorn timeout |

**Root cause:** No Postgres integration tests exist. All tests use DuckDB. The `_PgConnWrapper` translation layer is a shim that's grown organically without systematic test coverage.

### P2: Orchestrator Had to Become Debugger

The Black Box Protocol assigns clear roles: build agents write code, DeskRelay does visual QA. But Sprint 55 needed a third role: **deployment operator** who can diagnose and fix issues that only manifest on staging infrastructure.

The orchestrator spent 90 minutes doing iterative fix-deploy-verify cycles that no existing protocol role covers:
1. Push fix → wait 2.5 min for deploy → test endpoint → discover new bug → repeat
2. Required Railway CLI knowledge, env var debugging, log reading
3. Required code fixes between deploy attempts (3 separate commits)

This work doesn't fit Stage 1 (build) or Stage 2 (visual QA). It's a distinct deployment validation phase.

---

## Amendments

### Amendment A: Stateful Deployment Protocol (BLACKBOX_PROTOCOL.md v1.2)

**Status: APPLIED**

New section in BLACKBOX_PROTOCOL.md: "Stateful Deployment Protocol." Applies when a sprint adds schema changes, cron endpoints, or data ingest. Defines a Stage 1.5 between BUILD/TEST and DeskRelay handoff with:

1. **Deploy Verification** — confirm staging build triggered and succeeded
2. **Schema Gate** — verify new tables exist via /health
3. **Auth Smoke Test** — verify cron secret works (with length diagnostic)
4. **Staged Ingest Runbook** — smallest first, monitor each, chunked execution for large datasets
5. **Fix-Redeploy Loop** — structured retry when staging issues require code fixes (max 3 cycles)

See BLACKBOX_PROTOCOL.md for full protocol text.

### Amendment B: Postgres Compatibility Test Markers

**Status: RECOMMENDATION FOR SPRINT 56**

Add `@pytest.mark.postgres_compat` marker for tests that validate Postgres-specific behavior:

```python
@pytest.mark.postgres_compat
def test_pg_translate_sql_on_conflict():
    """INSERT OR REPLACE must become INSERT ... ON CONFLICT on Postgres."""
    wrapper = _PgConnWrapper(mock_conn)
    result = wrapper._translate_sql("INSERT OR REPLACE INTO foo VALUES (?)")
    assert "ON CONFLICT" in result
```

Priority targets:
- `_PgConnWrapper._translate_sql()` — all SQL translation paths
- `postgres_schema.sql` — DDL that may fail on dirty data
- Streaming ingest — batch commit behavior

### Amendment C: Deployment Manifest Ingest Runbook

**Status: APPLIED**

Added `ingest_runbook` section to `DEPLOYMENT_MANIFEST.yaml` that declares dataset sizes and ordering. The Stateful Deployment Protocol reads this to determine ingest sequence and timeout expectations.

### Amendment D: Known DuckDB/Postgres Divergences

**Status: RECOMMENDATION**

Maintain a living checklist in CLAUDE.md or a dedicated file:

```
## Known DuckDB vs Postgres Divergences
- INSERT OR REPLACE → must add ON CONFLICT on Postgres
- CREATE UNIQUE INDEX on dirty data → must dedup first (use migration, not schema.sql)
- Gunicorn timeout (300-600s) → streaming ingest must commit per-batch
- Railway env vars → may contain trailing whitespace or display across multiple lines
- DuckDB ? placeholders → Postgres uses %s (handled by _PgConnWrapper)
```

### Amendment E: CRON_SECRET Railway CLI Knowledge

**Status: APPLIED (memory update)**

Updated CC memory: Railway CLI wraps long env var values across multiple display lines. Use `od -c` or `wc -c` to verify actual length. The CRON_SECRET for this project is 64 characters.

---

## Metrics

| Agent | Tests at Close | New Tests | QA Checks | Status |
|---|---|---|---|---|
| A (Ingest) | 1,865 (worktree) | +81 | — | Merged |
| B (Ref Tables) | 1,805 (worktree) | +21 | — | Merged |
| D (Brief/Nightly) | 1,814 (worktree) | +30 | — | Merged |
| E (Signal/Fixes) | 1,802 (worktree) | +17 | — | Merged |
| C (Wire Tools) | 1,916 (worktree) | +30 | — | Merged |
| G (Docs/QA) | — | — | 10-step QA script | Merged |
| **HEAD (merged)** | **1,964** | **+144** | — | — |

## Time Lost to Deployment Issues

| Issue | Time Lost | Could Protocol Have Caught It? |
|---|---|---|
| Schema transaction failure (UNIQUE index) | ~20 min | Yes — Schema Gate would verify tables exist |
| ON CONFLICT missing | ~15 min | Yes — Auth Smoke + smallest ingest would surface it |
| CRON_SECRET display truncation | ~15 min | Partially — Auth Smoke would fail, but diagnosis still requires operator knowledge |
| Gunicorn timeout + no incremental commits | ~30 min | Yes — Staged Ingest Runbook with size-based ordering |
| Auto-deploy not triggering | ~10 min | Yes — Deploy Verification step |
| **Total** | **~90 min** | **~75 min recoverable with new protocol** |

## What the New Protocol Would Have Changed

With the Stateful Deployment Protocol in place, Sprint 55's DeskRelay handoff would have looked like:

1. **Deploy Verification** — catches the auto-deploy lag immediately (empty commit retry)
2. **Schema Gate** — discovers missing tables before attempting ingest, surfaces the UNIQUE index bug
3. **Auth Smoke** — validates CRON_SECRET works before running any ingest
4. **Staged Ingest** — runs `dwelling_completions` (2K rows) first, discovers ON CONFLICT bug on smallest dataset
5. **Fix-Redeploy Loop** — structured 3-attempt cycle for the schema and ON CONFLICT fixes
6. **Large Dataset Monitoring** — street-use flagged as >100K rows, timeout budget checked, incremental commits required

Estimated time with new protocol: ~30 min (fix-redeploy cycles are faster when the diagnosis framework is in place) vs ~90 min actual.

## Remaining Work

- [ ] Run street-use ingest on staging (waiting on current attempt with 600s timeout)
- [ ] Promote to prod via DeskRelay Stage 2
- [ ] Run all ingest endpoints on prod
- [ ] Add `@pytest.mark.postgres_compat` tests (Sprint 56)
- [ ] Write DuckDB/Postgres divergence checklist
