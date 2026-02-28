# QS9 — Overnight Hardening Quad Sprint

**Date:** 2026-02-27 (overnight)
**Type:** Quad sprint (4 terminals × 4 agents = 16 agents)
**Status:** READY TO LAUNCH
**Risk level:** LOW — no template changes, no design decisions, mechanical/infrastructure work
**Experiment:** Tim sleeps, T0 monitors and merges

## Goal

Ship everything that doesn't need design input: tool registration, test hardening, scaling infrastructure. When Tim wakes up, the codebase is cleaner, faster, and ready for the design session.

## Pre-Requisites

| Requirement | Status |
|-------------|--------|
| QS8 promoted to prod | Done |
| Redis provisioned on Railway (REDIS_URL env var) | Tim does this pre-launch |
| Main branch clean | Verify in pre-flight |

## Success Criteria

| # | Criterion | How to Measure |
|---|---|---|
| 1 | 34 MCP tools registered | `python -c "from src.server import server; print(len(server.tools))"` |
| 2 | Admin health panel shows pool + cache stats | `/admin` page check |
| 3 | Zero stale test failures | `pytest tests/test_landing.py -x -q` passes |
| 4 | Page cache test passes in full suite (not just isolation) | Full suite without -k skip |
| 5 | Scenario files consolidated (no per-agent files in root) | `ls scenarios-pending-review-*.md` returns nothing |
| 6 | Rate limiter uses Redis when REDIS_URL set | Check import path in web/helpers.py |
| 7 | DB pool max configurable + documented | Check src/db.py + ONBOARDING.md |
| 8 | Full test suite passes | `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -q` |

## Wall Clock: ~25-35 min (agents), ~10 min (merge ceremony)

T0 monitors but does not intervene unless a terminal fails completely.

---

## Terminal 1: Tool Registration + Admin Health (Sprint 82-partial)

**Theme:** Register QS8's intelligence tools and surface system health in admin.

### Agents

| Agent | Task | Files Owned |
|-------|------|-------------|
| 1A | Register 4 tools in src/server.py | `src/server.py` |
| 1B | Admin health panel (pool + circuit breaker + cache stats) | `web/routes_admin.py`, `web/templates/fragments/admin_health.html` (NEW) |
| 1C | Fix prod gate ratchet logic (check specific issues, not overall score) | `scripts/prod_gate.py` |
| 1D | Consolidate QS7+QS8 per-agent output files into main files | `scenarios-pending-review.md`, `CHANGELOG.md`, cleanup `*-qs8-*.md` files |

### Key Details

**1A tool registration:** Follow existing patterns in server.py. 4 tools:
- predict_next_stations (from src.tools.predict_next_stations)
- diagnose_stuck_permit (from src.tools.stuck_permit)
- simulate_what_if (from src.tools.what_if_simulator)
- calculate_delay_cost (from src.tools.cost_of_delay)

**1B admin health:** New section on /admin dashboard:
- DB pool: used/available/max from get_pool_stats()
- SODA circuit breaker: state + failure count (import from soda_client)
- Page cache: row count + oldest entry age (query page_cache table)
- Auto-refresh via HTMX poll every 30s

**1C prod gate fix:** The ratchet triggers HOLD on consecutive score-3 even when the specific issues changed. Fix: track which checks scored <5 in HOTFIX_REQUIRED.md, only trigger ratchet if the SAME checks are still failing.

**1D consolidation:** Cat all `scenarios-pending-review-qs8-*.md` and `scenarios-pending-review-qs7-*.md` into main file, cat all `CHANGELOG-qs8-*.md` into CHANGELOG.md, then delete the per-agent files. Pure file operations.

---

## Terminal 2: Test Hardening

**Theme:** Fix every known test issue so the full suite is trustworthy.

### Agents

| Agent | Task | Files Owned |
|-------|------|-------------|
| 2A | Fix stale landing tests | `tests/test_landing.py` |
| 2B | Fix page_cache intra-session flakiness | `tests/test_page_cache.py`, `tests/conftest.py` (cleanup fixture only) |
| 2C | Audit all cron tests for CRON_WORKER env var | `tests/test_cron_*.py`, `tests/test_brief_cache.py`, `tests/test_sprint_79_3.py` |
| 2D | Clean up stale worktree branches + test file hygiene | Git operations only, `tests/test_sprint_79_*.py` (minor fixes) |

### Key Details

**2A landing tests:** `test_landing_has_feature_cards` and `test_landing_has_stats` assert text from before Sprint 69's landing rebuild. Read current landing.html, update assertions to match actual content. Don't delete tests — fix them.

**2B page_cache flakiness:** The test passes in isolation but fails in the full suite. Root cause: a preceding test leaves stale data in the session-scoped temp DuckDB that the cleanup fixture doesn't clear. Fix: make the test_page_cache.py cleanup fixture more aggressive — DELETE FROM page_cache before each test class (not just test:%/brief:% patterns). Or use unique cache keys per test run via uuid.

**2C CRON_WORKER audit:** Grep all test files for `/cron/` endpoint calls. Every one needs `monkeypatch.setenv("CRON_WORKER", "1")`. Missing this causes 404 (CRON_GUARD) instead of the expected 403/200.

**2D worktree cleanup:** Run `git worktree prune`, then delete merged agent branches: `git branch | grep worktree-agent | xargs git branch -d`. Also clean up any test files that reference nonexistent imports or have syntax issues.

---

## Terminal 3: Scaling Infrastructure (#364, #365, #366)

**Theme:** Prepare for 5,000 users without a redesign.

### Agents

| Agent | Task | Files Owned |
|-------|------|-------------|
| 3A | DB pool tuning + connection health | `src/db.py`, `docs/ONBOARDING.md` |
| 3B | Cache-Control headers on all static assets | `web/app.py` (after_request hook) |
| 3C | Redis rate limiter (if REDIS_URL available) | `web/helpers.py` (rate limiter section), `requirements.txt` or `pyproject.toml` |
| 3D | Load test script + scaling documentation | `scripts/load_test.py` (enhance existing), `docs/SCALING.md` (NEW) |

### Key Details

**3A pool tuning:**
- Increase DB_POOL_MAX default from 20 to 50
- Add DB_POOL_MIN default increase from 2 to 5
- Add pool exhaustion logging (warn when >80% used)
- Document all pool env vars in docs/ONBOARDING.md
- Add pool stats to /health endpoint if not already there

**3B static asset caching:**
- Add after_request hook in web/app.py that sets Cache-Control on /static/ responses
- `Cache-Control: public, max-age=86400, immutable` for versioned assets (.css, .js with hash)
- `Cache-Control: public, max-age=3600` for non-versioned assets
- Do NOT cache HTML responses (only /static/ path)

**3C Redis rate limiter:**
- Current: in-memory dict `_rate_buckets` in web/helpers.py — doesn't share across workers
- If REDIS_URL is set: use Redis INCR + EXPIRE for rate counting (shared across all workers)
- If REDIS_URL not set: fall back to current in-memory dict (no change in behavior)
- Add `redis>=5.0.0` to pyproject.toml dev deps
- Pattern: `redis.Redis.from_url(os.environ["REDIS_URL"])` with connection pooling

**3D load test + docs:**
- Enhance existing scripts/load_test.py (if it exists) or create new
- Test: 50 concurrent users hitting /, /search, /brief, /report endpoints
- Measure: p50/p95/p99 response times, error rate, connection pool saturation
- Create docs/SCALING.md documenting: current capacity, bottlenecks, env vars, Redis setup, CDN options

### REDIS_URL Availability

If Tim provisioned Redis on Railway before launch:
- REDIS_URL will be in the Railway env vars
- Agent 3C can wire it in and test locally with a Redis container or mock
- For local testing: `docker run -d -p 6379:6379 redis:7-alpine` or mock Redis in tests

If REDIS_URL is NOT available:
- Agent 3C writes the Redis integration code with a fallback
- Tests mock Redis
- The code ships but doesn't activate until REDIS_URL is set on Railway
- This is fine — the integration is ready, just needs the env var

---

## Cross-Terminal File Ownership

| File | Owner | Others? |
|------|-------|---------|
| `src/server.py` | T1-1A | No |
| `web/routes_admin.py` | T1-1B | No |
| `scripts/prod_gate.py` | T1-1C | No |
| `scenarios-pending-review.md` | T1-1D | No |
| `CHANGELOG.md` | T1-1D | No |
| `tests/test_landing.py` | T2-2A | No |
| `tests/test_page_cache.py` | T2-2B | No |
| `tests/conftest.py` | T2-2B | No |
| `tests/test_brief_cache.py` | T2-2C | No |
| `src/db.py` | T3-3A | No |
| `web/app.py` | T3-3B | No |
| `web/helpers.py` | T3-3C | No |
| `docs/SCALING.md` | T3-3D | No (NEW) |

**Cross-terminal conflicts: ZERO.**

---

## Merge Strategy

**Order: T1 → T2 → T3** (registration first, tests second, infra last)

T2 depends on T1's scenario consolidation being done (so new scenario files don't conflict).
T3 is independent but merges last because infra changes are safest to verify last.

---

## Terminal 4: Cleanup + Documentation + API Routes

**Theme:** Consolidate artifacts, expose tools via API, clean stale files, update docs.

### Agents

| Agent | Task | Files Owned |
|-------|------|-------------|
| 4A | Expose 4 intelligence tools as /api/ JSON endpoints | `web/routes_api.py` |
| 4B | Consolidate 100+ scenarios, deduplicate, categorize | `scenarios-pending-review.md`, `scenario-design-guide.md` (read-only), delete per-agent files |
| 4C | Delete stale sprint prompts + prototype artifacts | `sprint-prompts/` (old files), `web/static/landing-v5.html` |
| 4D | Update README, ARCHITECTURE, CHANGELOG with QS7-QS8 results | `README.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`, delete per-agent CHANGELOG files |

---

## Merge Strategy

**Order: T1 → T3 → T2 → T4** (registration → scaling → tests → cleanup last)

T4 must merge LAST because:
- 4B consolidates scenario files that other terminals may create
- 4D consolidates CHANGELOG files that other terminals may create
- 4C deletes files — safest as final operation

---

## Overnight Protocol

1. Tim launches T1-T4, walks away
2. T0 monitors via this session
3. As terminals finish, T0 verifies their push
4. Once all 4 pushed: T0 runs merge ceremony (pull, test suite, prod gate)
5. If all green: T0 promotes to prod, posts report to Chief
6. If failures: T0 documents what failed, does NOT promote, leaves report for Tim
7. Tim wakes up to either "promoted, here's the report" or "blocked on X, here's what I tried"

**T0 does NOT:**
- Debug complex failures past 3 attempts
- Make design decisions
- Modify files outside the merge ceremony
- Force-push or destructive git operations
