# Sprint 56 Post-Mortem: Chang Family Loop + Infrastructure Close-Out

**Date:** 2026-02-25
**Sprint:** 56 — 6-agent parallel swarm build
**Duration:** ~5 hours (Wave 0 to final QA pass)
**Outcome:** All deliverables shipped, 2,304 tests passing, staging verified (54 tables, 18.79M rows)

---

## What Went Well

1. **All 6 agents completed their missions.** No agent got stuck or failed to deliver. Combined output: 265+ new tests, 24 scenarios, 4 knowledge files, 5 new tables, 6 new cron endpoints, 3 new user-facing routes.

2. **PgConnWrapper cursor bug caught before prod.** The Stateful Deployment Protocol (added in Sprint 55 postmortem) worked as designed — by requiring post-deploy ingest verification, it surfaced a latent cursor lifecycle bug that would have silently dropped data on every future ingest function that used `.fetchone()`.

3. **FK divergence caught during schema gate.** `analysis_sessions REFERENCES users(id)` failed on Postgres because the PK is `user_id`. Caught by the schema migration step in the Stateful Deployment Protocol.

4. **User instinct caught what the orchestrator missed.** When I reported plumbing inspections "didn't persist" and moved on, Tim flagged it as worrying. That led to the cursor bug discovery. Lesson: don't brush off data integrity issues.

---

## What Went Wrong

### Issue 1: Railway Build Queue Flood

**What happened:** 6 agents pushed to `main` independently during the build phase. With 3 Railway services watching `main`, each push triggered 3 builds. ~15 pushes × 3 services = ~45 queued builds. This coincided with a Railway infrastructure incident (degraded build machines), resulting in a 55-minute deploy queue delay.

**Root cause:** The agent prompts said "commit with message" but didn't say "do NOT push." Agents C and D took initiative and merged to main + pushed on their own. The orchestrator then pushed additional commits (FK fix, CHANGELOG, QA results), compounding the queue.

**Impact:** 55-minute delay in staging verification. Multiple CI runs on partial code (noisy failures). User confusion about GitHub CI status.

**Fix for next sprint:** Single-push swarm pattern. Agent prompts must include: "Commit to your worktree branch. Do NOT merge or push to main. The orchestrator handles all merges." Orchestrator does one merge sequence, one push.

**Protocol change:** Add to swarm orchestration rules in CLAUDE.md.

---

### Issue 2: PgConnWrapper.execute() Returns Closed Cursor

**What happened:** The `_PgConnWrapper.execute()` method (Sprint 54) used `with self._conn.cursor() as cur:` and returned `cur` from inside the context manager. The `with` block closes the cursor on exit. Any caller doing `.fetchone()` on the returned cursor got an `InterfaceError`.

**How it caused silent data loss:**
1. `ingest_plumbing_inspections()` calls `conn.execute("SELECT MAX(id) FROM inspections").fetchone()`
2. `.fetchone()` fails on the closed cursor → `InterfaceError`
3. `except Exception: start_id = 1` catches it silently
4. 398,731 plumbing inspections are inserted with IDs 1–398,731
5. These collide with existing building inspections (IDs 1–671,949)
6. `ON CONFLICT DO NOTHING` silently drops every single row
7. The function returns `398731` as the count (it counted the batch, not the actual inserts)
8. The cron endpoint returns `{"ok": true, "rows": 398731}` — looks successful

**Why it wasn't caught earlier:** Existing ingest functions (boiler, fire, electrical, plumbing permits) don't call `.fetchone()` on the wrapper — they use `_fetch_all_pages()` through the SODA client. The bug was latent since Sprint 54 but only triggered when Sprint 56C added the first function that reads from the DB via the wrapper.

**Fix:** Removed the `with` context manager. Cursor is now created with plain `self._conn.cursor()` and stays open for the caller.

**Broader impact audit:** All other `conn.execute()` calls in ingest functions were audited. The only caller that does `.fetchone()` is `ingest_plumbing_inspections()`. However, any future ingest code using the pattern `conn.execute("SELECT ...").fetchone()` would have hit the same bug.

**Prevention:**
- Add integration test: `test_pg_wrapper_execute_fetchone_works()`
- Add to agent prompts: "When writing Postgres-compatible code, verify cursor lifecycle — never return a cursor from inside a `with` block"
- Add to dforge lessons

---

### Issue 3: CI Running on Partial Merges

**What happened:** When Agent D pushed its commit to main, Agent C's tests (`test_sprint56c.py`) were already in the repo but Agent C's implementation code (`normalize_plumbing_inspection`, `_get_street_use_activity`, etc.) was not yet merged. GitHub CI ran on Agent D's commit and reported 44 test failures — all `ImportError: cannot import name` errors from Agent C's test file.

**Root cause:** Same as Issue 1 — agents pushing independently meant CI ran on partial code states.

**Impact:** User saw CI failures on GitHub, worried about account status. The failures were real at that commit but resolved at HEAD once all agents were merged. Noise, not a real problem, but confusing.

**Fix:** Single-push pattern eliminates this entirely.

---

### Issue 4: FK Column Name Divergence

**What happened:** Agent D wrote `analysis_sessions.user_id INTEGER REFERENCES users(id)`. The `users` table PK is `user_id`, not `id`. The `CREATE TABLE` statement failed on Postgres, blocking schema migration.

**Root cause:** Agent D didn't read the existing `users` table definition before writing the FK reference. All other tables in the codebase use `REFERENCES users(user_id)`.

**Impact:** Schema migration failed on first attempt. Required a fix-redeploy cycle (15 min).

**Fix:** Changed to `REFERENCES users(user_id)` in both `postgres_schema.sql` and `run_prod_migrations.py`.

**Prevention:** Add to agent prompts: "Before writing REFERENCES clauses, read the target table's CREATE TABLE statement and verify the exact column name of the primary key."

---

### Issue 5: Orchestrator Didn't Notify User of Infrastructure Blocker

**What happened:** Railway deploys were stuck in QUEUED for 20+ minutes. The orchestrator kept polling silently instead of notifying the user immediately. User had to tell the orchestrator to "notify me of something like this."

**Root cause:** Orchestrator treated the stuck queue as a transient issue and kept checking. Black Box Protocol requires surfacing blockers to the user.

**Impact:** User was unaware of the delay for ~20 minutes. Could have checked Railway dashboard, contacted support, or made a strategic decision about waiting vs. alternative approaches.

**Fix:** Added to memory: "When infrastructure is blocking, notify the user within 2 minutes."

**Protocol change:** Add explicit notification rule to Black Box Protocol or CLAUDE.md swarm section.

---

## Metrics

| Metric | Before Sprint 56 | After Sprint 56 |
|--------|-------------------|-----------------|
| Tests | 1,984 | 2,304 (+320) |
| Tables | 49 | 54 (+5) |
| Total rows | 17.7M | 18.79M (+1.09M) |
| Tier1 knowledge files | 40 | 44 (+4) |
| Semantic concepts | 100 | 114 (+14) |
| Scenarios pending | - | +24 |
| Fix-redeploy cycles | - | 2 (FK fix, cursor fix) |

---

## Action Items

| # | Action | Owner | Target |
|---|--------|-------|--------|
| 1 | Add "single-push swarm pattern" to CLAUDE.md swarm rules | CC/Tim | Sprint 57 CLAUDE.md update |
| 2 | Add dforge lesson: cursor lifecycle in DB wrappers | CC | Next dforge session |
| 3 | Add dforge lesson: silent data loss in ON CONFLICT patterns | CC | Next dforge session |
| 4 | Add integration test for PgConnWrapper.execute().fetchone() | CC | Sprint 57 |
| 5 | Add "verify FK column names" to agent prompt template | CC/Tim | Sprint 57 spec |
| 6 | Add "notify user within 2 min of infra blockers" to Black Box | CC/Tim | BLACKBOX_PROTOCOL v1.3 |
| 7 | Fix signals pipeline FK constraint (pre-existing) | CC | Sprint 57 |
| 8 | Build persona detection background job (spec'd but unassigned) | CC | Sprint 57 |
| 9 | End-to-end Chang Family flow test (DeskRelay Stage 2) | DeskCC | Next DeskRelay session |

---

## Timeline

| Time | Event |
|------|-------|
| 09:22 | Wave 0: commit protocol debt, update manifest, verify tests (1,984) |
| 09:28 | Wave 1: launch 6 parallel agents |
| 09:39 | Agent A complete (48 tests) |
| 09:44 | Agent B complete (72 tests), Agent F complete (58 tests) |
| 09:47 | Agent E complete (32 tests) |
| 09:56 | Agent C complete (55 tests) — merged to main independently |
| 09:57 | Agent D complete (54 tests) — merged to main independently |
| 09:58 | Wave 2: merge remaining agents A, B, F |
| 10:00 | Full test suite: 2,304 passed |
| 10:02 | Push to main, deploy queued |
| 10:05 | Schema migration fails — FK bug (users(id) vs users(user_id)) |
| 10:10 | FK fix committed, pushed |
| 10:12 | Deploy stuck in QUEUED — Railway infrastructure incident |
| 10:53 | Still queued after 40+ min |
| 11:05 | Railway status confirms active incident |
| 11:48 | Deploy starts INITIALIZING |
| 11:58 | Deploy SUCCESS |
| 12:00 | Schema gate passed (54 tables) |
| 12:02 | Staged ingest: planning metrics (69K), issuance metrics (138K) |
| 12:05 | Staged ingest: review metrics (439K) |
| 12:08 | Staged ingest: plumbing inspections (399K) — reports success |
| 12:08 | User flags "rows didn't persist — that's worrying" |
| 12:12 | Root cause found: PgConnWrapper cursor bug |
| 12:15 | Fix committed, pushed |
| 12:30 | New deploy SUCCESS |
| 12:33 | Plumbing inspections re-ingested — 398K rows PERSISTED |
| 12:38 | Final QA: 15/15 PASS |
| 12:42 | QA results committed, CHECKCHAT |
