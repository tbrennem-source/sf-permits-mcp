# QS8 — Beta Launch Quad Sprint Spec

**Date:** 2026-02-27
**Type:** Quad sprint (3 terminals × 4 agents = 12 agents)
**Status:** APPROVED (c.ai flags addressed)
**Pre-requisite:** Sprint 78 (test harness fix) merged to main
**Sprint prompts:** `qs8-t1-performance.md`, `qs8-t2-intelligence.md`, `qs8-t3-beta-data.md` (to be written from existing sprint-79/80/81 prompts)
**Planning doc:** `sprint-prompts/qs8-planning.md`

## What Changed from Original QS9 Plan

Original plan had 4 terminals / 16 agents (Sprints 78-81). Two things shipped early:

| Change | Impact |
|--------|--------|
| QS7 shipped template migration (#355) | Sprint 78 (design migration) cut from QS8 — done |
| Sprint 78 ships test harness (#359) solo | QS8 starts with reliable test infra |

**Result:** QS8 is now 3 terminals / 12 agents covering Sprints 79-81.

## Goal

Three pillars for public beta launch: performance (pages load fast), intelligence (new tools that justify the product), and beta experience (onboarding + data + polish).

## Pre-Requisites

| Requirement | Status |
|-------------|--------|
| QS7 in prod (obsidian.css, template migration, prod gate v2) | Promoting now |
| Sprint 78 merged (test harness — reliable pytest for merge ceremony) | Next to execute |
| Clean main branch, all tests passing | Verified at Sprint 78 close |

## Success Criteria

| # | Criterion | How to Measure | Where |
|---|---|---|---|
| 1 | Property report <3s (44-permit parcel) | `curl -w '%{time_total}' /report/3512/001` | Staging |
| 2 | /brief cached after first load | Second request skips compute_fn | Staging |
| 3 | 4 new intelligence tools importable + tested | `python -c "from src.tools.station_predictor import ..."` | Local |
| 4 | Onboarding wizard renders for new users | Playwright E2E test | Local |
| 5 | Search NLP parses "kitchen remodel in the Mission" | Unit test with structured output | Local |
| 6 | QS7 cache tests pass (test_page_cache, test_brief_cache) | `pytest tests/test_page_cache.py tests/test_brief_cache.py` | Local |
| 7 | Full test suite passes after merge | `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -q` | Local |
| 8 | Prod gate PROMOTE | `python scripts/prod_gate.py --quiet` | Local |
| 9 | ~150 new tests | pytest count delta | Local |

## Wall Clock (estimated: 40-50 min)

```
T+0:     All 3 terminals launch (each spawns 4 agents)
T+15:    T2 finishes (all new files, fastest)
T+20:    T1 finishes (performance — most complex)
T+22:    T3 finishes
T+25:    Merge ceremony — T1 first (infra), T2 second (new files), T3 last (consumers)
T+30:    Full test suite (~5 min)
T+35:    Design lint + prod gate
T+37:    Fix failures (0-10 min)
T+40-50: Push, promote, verify
```

---

## Terminal 1: Performance + Ops (Sprint 79)

**Theme:** Make the app fast. Fix the 11-second property report. Add caching infrastructure. Wire circuit breakers.

**Existing prompt:** `sprint-prompts/sprint-79-performance.md`

### Agents

| Agent | Task | Files Owned | Chief Tasks |
|-------|------|-------------|-------------|
| 79-1 | Report N+1 fix — batch contacts/inspections | `web/report.py` | #349 partial |
| 79-2 | page_cache infra — table + get_cached_or_compute | `web/helpers.py`, `src/db.py`, `scripts/release.py` | #349 Phase A |
| 79-3 | Brief cache + cron endpoints | `web/brief.py`, `web/routes_cron.py` | #349 Phase B, #164, #218, #217 |
| 79-4 | SODA circuit breaker + Cache-Control headers | `src/soda_client.py`, `web/routes_misc.py` | #287 |

### Key Interface Contract (c.ai Flag 1: spelled out verbatim for 79-3's prompt)

**79-2 builds `get_cached_or_compute()` in `web/helpers.py`. 79-3 consumes it in `web/brief.py`.**

Both agents build in parallel. 79-3's prompt must include this exact contract so it can code against it without waiting for 79-2:

```python
def get_cached_or_compute(cache_key: str, compute_fn: callable, ttl_minutes: int = 30) -> dict:
    """Returns compute_fn() result dict.
    On cache hit, adds: _cached=True, _cached_at="2026-02-27T15:30:00" (ISO 8601)
    On miss: calls compute_fn(), stores as JSON in page_cache table, returns result.
    Cache write failure is non-fatal — returns compute_fn() result regardless."""

def invalidate_cache(pattern: str) -> int:
    """SET invalidated_at = NOW() on rows matching SQL LIKE pattern.
    Returns count invalidated. Non-fatal on error."""
```

79-3 uses a try/except import pattern so it builds independently:
```python
try:
    from web.helpers import get_cached_or_compute
except ImportError:
    get_cached_or_compute = None  # works without cache
```

QS7's 26 cache tests (`test_page_cache.py` + `test_brief_cache.py`) validate the interface at merge time.

### Merge Order Within T1

79-2 first (infrastructure), then 79-1, 79-3, 79-4. 79-3 depends on 79-2's function being available at merge time.

### Inherited Test Debt

QS7-T4 wrote `tests/test_page_cache.py` (16 tests) and `tests/test_brief_cache.py` (13 tests) against this interface spec. All 26 currently fail (expected — implementation doesn't exist yet). **After T1 merges, these 26 tests should pass.** If they don't, the implementation doesn't match the spec — fix the implementation.

### Known DuckDB/Postgres Gotchas

Sprint 78 may have moved tests to Postgres. If so:
- `INSERT OR REPLACE` in page_cache DDL → use `ON CONFLICT DO UPDATE`
- page_cache DDL must be valid Postgres (TIMESTAMPTZ, JSONB are fine)
- If Sprint 78 used the DuckDB fallback, tests still run on DuckDB — use DuckDB DDL as before

Agent 79-2 must check `src.db.BACKEND` at runtime and use the correct DDL. The existing pattern in `init_user_schema` already handles both backends — follow it.

---

## Terminal 2: Intelligence Tools (Sprint 80)

**Theme:** Build the tools that justify the product. 4 new MCP tools, all brand new files, zero conflicts.

**Existing prompt:** `sprint-prompts/sprint-80-intelligence.md`

### Agents

| Agent | Task | Files Created (ALL NEW) | Chief Tasks |
|-------|------|------------------------|-------------|
| 80-1 | "What's Next" station predictor | `src/tools/station_predictor.py`, `tests/test_station_predictor.py` | #129 |
| 80-2 | Stuck Permit Intervention Playbook | `src/tools/stuck_permit.py`, `tests/test_stuck_permit.py` | #174 |
| 80-3 | What-If Permit Simulator | `src/tools/what_if_simulator.py`, `tests/test_what_if_simulator.py` | #166 |
| 80-4 | Cost of Delay Calculator | `src/tools/cost_of_delay.py`, `tests/test_cost_of_delay.py` | #169 |

### Key Properties

- **ZERO existing file modifications.** Every agent creates new files only.
- **ZERO cross-agent dependencies.** Each tool is self-contained.
- **ZERO merge conflict risk.** This is the safest terminal.
- Tools are NOT registered in `src/server.py` or exposed via web routes in this sprint. Follow-up: Chief task #360. They're importable and tested standalone.
- All tools must handle both DuckDB and Postgres via `BACKEND` and `_PH` from `src.db`.
- All tools are async functions matching existing tool signatures.

### Merge Order

Doesn't matter — all new files. Merge in any order.

---

## Terminal 3: Beta + Data (Sprint 81)

**Theme:** The user-facing beta experience. Onboarding, search intelligence, data expansion, E2E tests, and the demo seed script (absorbed from Sprint 78).

**Existing prompt:** `sprint-prompts/sprint-81-beta-data.md`

### Agents

| Agent | Task | Files Owned | Chief Tasks |
|-------|------|-------------|-------------|
| 81-1 | Onboarding wizard + PREMIUM tier + feature flags | `web/routes_auth.py`, `web/feature_gate.py`, `web/templates/welcome.html`, new `web/templates/onboarding_*.html` | #330, #135, #139 |
| 81-2 | Search NLP + empty result guidance + result ranking | `web/routes_search.py`, `web/routes_public.py` | #271 |
| 81-3 | Trade permits ingest (electrical/plumbing/boiler) | `src/ingest.py`, `datasets/` | #130 |
| 81-4 | E2E tests + seed_demo.py | `tests/e2e/test_onboarding_scenarios.py` (NEW), `tests/e2e/test_performance_scenarios.py` (NEW), `scripts/seed_demo.py` (NEW) | — |

### c.ai Flag 2: 81-1 Scope Reduction

Original 81-1 had 4 deliverables (onboarding + PREMIUM + feature flags + seed_demo.py). seed_demo.py moved to 81-4 (lightest scope agent). 81-1 now focuses on: onboarding wizard (3 step templates), PREMIUM tier in feature_gate.py, and 5 feature flag registrations. Still the widest T3 agent but manageable.

### seed_demo.py (now on Agent 81-4)

```bash
python scripts/seed_demo.py --email tbrennem@gmail.com
# Adds watch items for 1455 Market, 146 Lake, 125 Mason
# Adds 5 recent searches
# Dashboard now shows real data instead of zeros
```

Idempotent CLI script. Agent 81-4 builds this alongside E2E tests — both are lightweight, no production route changes.

### E2E Test Dependencies

Agent 81-4 writes tests that exercise features from 81-1 (onboarding) and T1/79 (performance headers). These tests validate the interface spec. If they fail after merge, the implementation needs fixing — the tests define correct behavior.

### Known Gotchas

- `before_request` hooks must check `app.config.get("TESTING")` — daily limits accumulate across test files without this guard
- `CRON_WORKER` env var needed for cron endpoint tests via `monkeypatch.setenv("CRON_WORKER", "1")`
- Agent 81-3 writes ingest functions but does NOT run them (SODA API calls are slow). Tests mock SODA responses.

---

## Cross-Terminal File Ownership

| File | Owner | Others touch? |
|------|-------|--------------|
| `web/report.py` | T1-79-1 | No |
| `web/helpers.py` | T1-79-2 | No |
| `src/db.py` | T1-79-2 | No |
| `scripts/release.py` | T1-79-2 | No |
| `web/brief.py` | T1-79-3 | No |
| `web/routes_cron.py` | T1-79-3 | No |
| `src/soda_client.py` | T1-79-4 | No |
| `web/routes_misc.py` | T1-79-4 | No |
| `src/tools/station_predictor.py` | T2-80-1 | No (NEW) |
| `src/tools/stuck_permit.py` | T2-80-2 | No (NEW) |
| `src/tools/what_if_simulator.py` | T2-80-3 | No (NEW) |
| `src/tools/cost_of_delay.py` | T2-80-4 | No (NEW) |
| `web/routes_auth.py` | T3-81-1 | No |
| `web/feature_gate.py` | T3-81-1 | No |
| `scripts/seed_demo.py` | T3-81-4 | No (NEW) |
| `web/routes_search.py` | T3-81-2 | No |
| `web/routes_public.py` | T3-81-2 | No |
| `src/ingest.py` | T3-81-3 | No |
| `tests/e2e/test_onboarding_scenarios.py` | T3-81-4 | No (NEW) |
| `tests/e2e/test_performance_scenarios.py` | T3-81-4 | No (NEW) |

**Cross-terminal conflicts: ZERO.** T1 owns backend infra. T2 creates new tool files. T3 owns user-facing routes + data.

---

## Merge Strategy

**Merge order: T1 → T2 → T3** (infrastructure first, new files second, consumers last)

T2 can go anywhere (all new files, zero deps) but merging after T1 means T2's tests run against the cache infrastructure if they happen to import it.

T3 merges last because:
- 81-4's E2E tests exercise T1's cache headers + T1's performance improvements
- 81-1's onboarding may reference helpers from T1

Each terminal completes its own internal 4-agent merge + push. T0 orchestrates cross-terminal order.

```bash
# T0 runs after all terminals finish:
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -20  # Verify commits from all 3 terminals

# Full test suite (includes QS7's 26 cache tests — should now pass)
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e

# Design lint (migrated templates should still be 5/5)
python scripts/design_lint.py --changed --quiet

# Prod gate
python scripts/prod_gate.py --quiet

# c.ai Flag 4: If Sprint 78 shipped DuckDB fallback (not Postgres),
# verify T1's cache code works against staging Postgres before promoting:
curl -s https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool | head -5
# Hit a cache-dependent route on staging to verify no SQL divergence:
# curl -s https://sfpermits-ai-staging-production.up.railway.app/brief (with auth)

# Promote
git checkout prod && git merge main && git push origin prod && git checkout main
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| page_cache doesn't match QS7 test spec | Medium | Medium | T1-79-2 reads test_page_cache.py as input spec. Budget 10 min for interface fixup. |
| N+1 fix breaks report rendering | Low | High | Agent 79-1 reads existing code thoroughly. CSS/layout untouched. |
| Intelligence tools can't query addenda table | Medium | Medium | Agents read existing tool patterns. Mock DB in tests. |
| Onboarding wizard breaks auth flow | Medium | Medium | 81-1 reads existing auth code first. Tests exercise login + onboarding path. |
| Search NLP regex too aggressive | Medium | Low | 81-2 tests with diverse query inputs. False positives are low impact. |
| Trade permit ingest schema mismatch | Low | Low | 81-3 writes functions + tests, doesn't run actual ingest. |
| Sprint 78 DuckDB fallback (not Postgres) | Medium | Low | All agent prompts handle both backends. DuckDB gotchas section included. |
| SODA circuit breaker blocks real requests | Low | Medium | 79-4 reads existing CircuitBreaker in src/db.py. Configurable thresholds. |

---

## Failure Recovery

| Scenario | Action |
|---|---|
| One agent fails | Terminal merges other 3. Failed task = follow-up. |
| Entire terminal fails | Merge other 2. Failed terminal = follow-up sprint. |
| QS7 cache tests fail after T1 merge | Interface mismatch. Fix implementation to match test spec. Budget 10 min. |
| Merge conflicts | Should not happen. If it does, file owner wins. |
| >5 test failures after all merges | Bisect: revert last terminal merge, re-test. |
| Prod gate HOLD | Read report. Fix blockers. Score 3 = promote + mandatory hotfix. |

---

## Expected Outcomes

| Terminal | New Tools | New Tests | Chief Tasks Resolved |
|----------|-----------|-----------|---------------------|
| T1 (Performance) | page_cache system, batch queries, circuit breaker, 3 cron endpoints | ~50 | #349 A+B, #164, #218, #217, #287 |
| T2 (Intelligence) | 4 MCP tools (station predictor, stuck permit, what-if, cost of delay) | ~60 | #129, #174, #166, #169 |
| T3 (Beta + Data) | onboarding wizard, search NLP, trade ingest, seed_demo.py | ~40 + 16 E2E | #330, #135, #139, #271, #130 |
| **Total** | **8 systems** | **~150** | **~12 tasks** |

Plus: QS7's 26 cache tests (test_page_cache + test_brief_cache) should pass after T1 merges.

---

## What Ships / What Doesn't

**Ships:**
- Property report: 11s → ~2-3s (N+1 fix + SODA caching)
- page_cache table + get_cached_or_compute + cron pre-compute
- SODA circuit breaker with graceful degradation
- Cache-Control headers for static pages
- 4 new intelligence tools (standalone, not yet registered as MCP tools)
- Multi-step onboarding wizard with role selection
- PREMIUM tier + 5 feature flags (all open during beta)
- Search NLP parser (natural language → structured filters)
- Trade permit ingest functions (electrical/plumbing/boiler)
- Demo seed script
- ~150 new tests + 26 QS7 cache tests validated

**Deferred:**
- Intelligence tool registration in src/server.py (follow-up sprint)
- Intelligence tool UI in web routes (follow-up sprint)
- #349 Phase C: edge caching + service worker
- Actual trade permit data ingest (functions built, data not loaded)
- Scenario drain (62 pending — separate sprint)
- Visual QA sweep on staging
- Remaining template migration (~20 admin/plan-analysis pages)

---

## Relationship to Sprint 78

Sprint 78 (test harness) is a hard pre-requisite. It provides:
1. **Reliable merge-ceremony test runs** — no DuckDB lock contention when T0 runs `pytest` after merging 12 branches
2. **Possibly Postgres-based tests** — if Sprint 78's primary path succeeds, QS8 agents' tests run against temp Postgres, catching SQL divergence before staging

If Sprint 78 shipped the DuckDB fallback instead, QS8 still works — agents handle both backends. The DuckDB/Postgres gotchas section in each terminal prompt covers the known divergences.

## Post-QS8

- Register intelligence tools in src/server.py (4 tools → 34 total)
- Build intelligence tool UI (web routes + templates)
- Run actual trade permit ingest (~450K records)
- Scenario drain: 62 pending
- Visual QA sweep
- #349 Phase C: edge caching + service worker
- Infrastructure: blue-green deploys, PgBouncer
- Product: timeline visualizer, congestion forecasting
