# Sprint 78 — Test Harness Fix (Solo Sprint)

**Date:** 2026-02-27
**Type:** Solo sprint (1 terminal × 1 agent)
**Status:** APPROVED (v3-corrected — c.ai reviewed, Postgres-first with 10-min fallback)
**Pre-requisite:** QS7 merged to main
**Sprint prompt:** `sprint-prompts/sprint-78-foundation.md`
**Chief task:** #359 (P0)
**c.ai review:** Approved. Scope clarification: agent should get fixture working + document DuckDB-specific failures as follow-up, NOT chase dialect fixes.

## What Changed Across Versions

| Version | Scope | Why |
|---------|-------|-----|
| v1 | 6 agents (test harness + template migration + demo) | Original plan |
| v2 | Same | c.ai approved with 2 amendments (gate checks, task renumber) |
| v3 | 1 agent (test harness only) | QS7 shipped templates. 5 agents cut. |
| v3-corrected | 1 agent, Postgres-first with DuckDB fallback | c.ai + T0 recommended Postgres to fix divergence too |

## Goal

Eliminate DuckDB lock contention in test suite AND (if Postgres path succeeds) DuckDB/Postgres SQL divergence, so merge-ceremony test runs are reliable for QS8.

## Success Criteria

| # | Criterion | How to Measure |
|---|---|---|
| 1 | No DuckDB lock contention in parallel test runs | Run 2-3 pytest sessions simultaneously — all pass |
| 2 | Full test suite passes | `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -q` |
| 3 | No existing test behavior changes | Same pass/fail/skip counts before and after |
| 4 | (If Postgres path) Divergence test passes | A query using ON CONFLICT succeeds in tests |

## Wall Clock: ~20-30 min

```
T+0:     Launch 1 agent
T+10:    CLOCK CHECK — Postgres working? If not, switch to DuckDB fallback.
T+15:    Agent commits (fixture working, suite runs)
T+16:    Merge to main
T+18:    Full test suite
T+20:    Parallel contention test (2-3 sessions)
T+22:    Push
T+25-30: Promote (if clean)
```

## Agent A: Test Harness (#359)

### Primary Path: Temp Postgres via `testing.postgresql`

Each pytest session spins up an isolated temporary Postgres instance. Fixes both lock contention AND DuckDB/Postgres divergence.

Steps:
1. Install `postgresql@16` via brew + add `testing.postgresql` to dev deps
2. Session-scoped `autouse` fixture in `tests/conftest.py` — starts temp Postgres, patches `src.db.DATABASE_URL` and `BACKEND`
3. Initialize schema in temp Postgres (call `init_user_schema` + essential tables)
4. Run suite — document any failures

### c.ai Scope Clarification

**The agent's job is to get the fixture working and run the suite.** If tests fail due to DuckDB-specific SQL (INSERT OR REPLACE, ? placeholders, DuckDB functions), the agent should:
- Document which tests fail and why (SQL dialect mismatch)
- Create a follow-up Chief task listing the affected test files
- **NOT** chase 40+ INSERT OR REPLACE fixes in this sprint

This keeps the sprint at 20 minutes. The dialect fixes are a follow-up task.

### Hard Time-Box: 10 Minutes for Postgres Setup

If `testing.postgresql` isn't fully working within 10 minutes (brew install fails, binary won't start, connection pool issues), STOP and ship the DuckDB fallback instead.

### Fallback Path: Per-Session Temp DuckDB

Patches `src.db._DUCKDB_PATH` to a per-session temp file. Fixes lock contention but NOT SQL divergence. Still a valid P0 fix — the immediate pain is contention, not divergence.

### Files

| File | Change |
|------|--------|
| `tests/conftest.py` | Add session-scoped `_isolated_test_db` fixture |
| `src/db.py` | Minor — verify patchability of `_DUCKDB_PATH` / `DATABASE_URL` |
| `pyproject.toml` | Add `testing.postgresql>=1.3.0` to dev deps |
| `docs/ONBOARDING.md` | Document `brew install postgresql@16` requirement |

### Edge Cases

- Tests that import `_DUCKDB_PATH` or `BACKEND` directly
- Tests that create their own DuckDB connections with hard-coded paths
- Schema initialization — temp DB is empty, tests may expect tables to exist
- Existing `_clear_rate_state` fixture must coexist (function-scoped alongside session-scoped)
- If Postgres path: tests using `?` placeholders fail — document, don't fix

## Validation Protocol

```bash
# 1. Full suite
pytest tests/ -q --tb=no --ignore=tests/test_tools.py --ignore=tests/e2e 2>&1 | tail -3

# 2. Parallel contention test
pytest tests/test_auth.py -x -q &
pytest tests/test_brief.py -x -q &
wait

# 3. Triple parallel (stress test)
pytest tests/test_auth.py -q &
pytest tests/test_brief.py -q &
pytest tests/test_landing.py -q &
wait

# 4. (If Postgres) Divergence check
pytest tests/test_page_cache.py -x -q  # Uses ON CONFLICT
```

## Relationship to QS8

Sprint 78 is a hard pre-requisite for QS8. Provides:
1. Reliable merge-ceremony test runs (no lock contention)
2. Possibly Postgres-based tests (catches SQL divergence before staging)

If Sprint 78 shipped DuckDB fallback, QS8 adds a manual staging verification step to catch divergence.
