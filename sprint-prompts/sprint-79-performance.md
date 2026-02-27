<!-- LAUNCH: Paste into CC terminal 2:
     "Read sprint-prompts/sprint-79-performance.md and execute it" -->

# Sprint 79 — Performance + Instant Site Architecture

You are the orchestrator for Sprint 79. Spawn 4 parallel build agents, collect results, merge, test, push.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git tag pre-sprint-79
```

## IMPORTANT CONTEXT

Property report takes 1-12 seconds depending on permit count. Root causes:
1. N+1 DB queries: `_get_contacts()` + `_get_inspections()` called per-permit (web/report.py lines 773-783)
2. No caching: every page load recomputes from scratch
3. SODA API latency: 1-3s per call even when parallelized

The "Instant Site Architecture" spec exists in Chief (specs/instant-site-architecture-pre-compute-cache-strategy.md). It defines a `page_cache` table + `get_cached_or_compute()` pattern + cron pre-compute. We're implementing Phase A + B of that spec plus the N+1 fix.

**Known DuckDB/Postgres Gotchas:**
- `INSERT OR REPLACE` → Postgres needs `ON CONFLICT DO UPDATE`
- `CREATE UNIQUE INDEX` on dirty data → fails on Postgres. Use `CREATE INDEX IF NOT EXISTS`.
- DuckDB uses `?` placeholders, Postgres uses `%s`. Check `src.db.BACKEND` variable.
- Tests run on DuckDB locally. Postgres bugs only surface on staging.

## Agent Launch

Spawn all 4 agents in parallel using Task tool:
```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree")
```

Each agent prompt MUST start with:
```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate

RULES:
- MERGE RULE: Do NOT merge to main. Commit to worktree branch only.
- CONFLICT RULE: Do NOT run git checkout <branch> -- <file>. Report conflicts as BLOCKED.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- DO NOT modify ANY file outside your owned list.
- APPEND FILES (dual-write):
  * scenarios-pending-review-sprint-79-N.md (per-agent)
  * scenarios-pending-review.md (shared, append only)
  * CHANGELOG-sprint-79-N.md (per-agent)
- Test after each task: pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q 2>&1 | tail -5
```

---

### Agent 79-1: Report N+1 Fix

**File Ownership:**
- web/report.py

**PHASE 1: READ**
- web/report.py (full file — understand the data assembly pipeline)
- src/tools/permit_lookup.py (_get_contacts, _get_inspections, _lookup_by_block_lot functions)
- src/db.py (BACKEND variable, _PH placeholder, get_connection)

**PHASE 2: BUILD**

Task 79-1-1: Create `_get_contacts_batch(conn, permit_numbers: list) -> dict[str, list]`
- Single query: `SELECT * FROM contacts WHERE permit_number IN (...)`
- Returns dict mapping permit_number -> list of contact dicts
- Handle both DuckDB and Postgres placeholder styles

Task 79-1-2: Create `_get_inspections_batch(conn, permit_numbers: list) -> dict[str, list]`
- Same pattern as contacts batch

Task 79-1-3: Replace the per-permit loop in `get_property_report()` (lines 773-783):
```python
# BEFORE (N+1):
for permit in permits:
    permit["contacts"] = _get_contacts(conn, pnum)
    permit["inspections"] = _get_inspections(conn, pnum)

# AFTER (2 queries total):
pnums = [p["permit_number"] for p in permits if p.get("permit_number")]
contacts_map = _get_contacts_batch(conn, pnums)
inspections_map = _get_inspections_batch(conn, pnums)
for permit in permits:
    pnum = permit.get("permit_number", "")
    permit["contacts"] = contacts_map.get(pnum, [])
    permit["inspections"] = inspections_map.get(pnum, [])
```

Task 79-1-4: Add SODA response caching (15-min TTL) for complaints/violations/property:
- Use a module-level dict with TTL: `_soda_cache: dict[str, tuple[float, Any]] = {}`
- Cache key = f"{endpoint_id}:{block}:{lot}"
- Before SODA calls, check cache. If fresh, skip API call.

**Expected impact:** 44-permit parcel drops from ~11s to ~2-3s.

**PHASE 3-6: TEST, SCENARIOS, QA, CHECKCHAT**
Write tests/test_sprint_79_1.py with:
- test_get_contacts_batch returns dict grouped by permit_number
- test_get_inspections_batch same pattern
- test_soda_cache_hit skips API call on second request
- test_soda_cache_expired makes new API call after TTL
Commit: "perf: batch contacts/inspections + SODA caching in report.py (Sprint 79-1)"

---

### Agent 79-2: page_cache Infrastructure

**File Ownership:**
- web/helpers.py (add get_cached_or_compute function)
- src/db.py (add page_cache DDL to init_user_schema)
- scripts/release.py (add page_cache migration)

**PHASE 1: READ**
- web/helpers.py (existing helpers — understand patterns)
- src/db.py lines 380-560 (init_user_schema — DDL patterns for DuckDB + Postgres)
- scripts/release.py (migration patterns)
- The spec: The page_cache table schema is:
```sql
CREATE TABLE IF NOT EXISTS page_cache (
    cache_key TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    html TEXT,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    invalidated_at TIMESTAMPTZ,
    ttl_minutes INT DEFAULT 60
);
CREATE INDEX IF NOT EXISTS idx_page_cache_stale ON page_cache (cache_key) WHERE invalidated_at IS NOT NULL;
```

**PHASE 2: BUILD**

Task 79-2-1: Add page_cache table DDL to src/db.py init_user_schema (both DuckDB and Postgres sections)
- DuckDB: use TIMESTAMP instead of TIMESTAMPTZ, JSON instead of JSONB

Task 79-2-2: Add page_cache migration to scripts/release.py

Task 79-2-3: Add `get_cached_or_compute(cache_key, compute_fn, ttl_minutes=30)` to web/helpers.py:
- Query page_cache for cache_key
- If found, not invalidated, and within TTL → return json.loads(payload)
- Otherwise call compute_fn(), upsert result to page_cache, return result
- Handle JSON serialization of datetimes (use default=str)
- Graceful fallback: if page_cache table doesn't exist, just call compute_fn()

Task 79-2-4: Add `invalidate_cache(pattern: str)` to web/helpers.py:
- UPDATE page_cache SET invalidated_at = NOW() WHERE cache_key LIKE pattern

Commit: "feat: page_cache infrastructure — table + get_cached_or_compute + invalidation (Sprint 79-2)"

---

### Agent 79-3: Brief Cache + Signals Cron

**File Ownership:**
- web/brief.py
- web/routes_cron.py

**PHASE 1: READ**
- web/brief.py (full file — understand get_morning_brief)
- web/routes_cron.py (cron endpoint patterns, auth, CRON_SECRET)
- web/helpers.py (will use get_cached_or_compute from Agent 79-2 — but write YOUR code independently, don't import it yet. Use a local try/except import pattern.)

**PHASE 2: BUILD**

Task 79-3-1: Wire cache-read pattern into brief route (if get_cached_or_compute is available):
```python
try:
    from web.helpers import get_cached_or_compute
    brief_data = get_cached_or_compute(
        f"brief:{user_id}:{lookback}",
        lambda: get_morning_brief(user_id, lookback),
        ttl_minutes=30
    )
except ImportError:
    brief_data = get_morning_brief(user_id, lookback)
```
NOTE: The actual route handler is in web/routes_search.py or web/app.py. If the brief route is NOT in web/brief.py, document this in CHECKCHAT as "wiring needed in routes file — not in my file ownership."

Task 79-3-2: Enhance brief pipeline stats — add to get_morning_brief():
- Pipeline timing: query cron_log for last 5 nightly job durations, show avg
- Pipeline health: which cron jobs succeeded/failed in last 24h
- Add to the returned dict under key "pipeline_stats"

Task 79-3-3: Add /cron/compute-caches endpoint to web/routes_cron.py:
- POST, CRON_SECRET auth (follow existing cron endpoint pattern)
- For each active user: pre-compute brief for lookback=1
- For each watched parcel: pre-compute property report
- Log results to cron_log

Task 79-3-4: Add /cron/signals endpoint to web/routes_cron.py (Chief #218):
- POST, CRON_SECRET auth
- Run src/severity.py scoring for all watched parcels
- Store results (follows existing cron pattern)

Task 79-3-5: Add /cron/velocity-refresh endpoint to web/routes_cron.py (Chief #218):
- POST, CRON_SECRET auth
- Refresh station_velocity_v2 data from addenda table

Commit: "feat: brief caching + compute-caches + signals/velocity cron endpoints (Sprint 79-3)"

---

### Agent 79-4: SODA Circuit Breaker + Static Cache Headers

**File Ownership:**
- src/soda_client.py
- web/routes_misc.py

**PHASE 1: READ**
- src/soda_client.py (full file — understand SODAClient, query method)
- src/db.py (CircuitBreaker class — lines 225+, reuse this pattern)
- web/routes_misc.py (route patterns, after_request hooks)

**PHASE 2: BUILD**

Task 79-4-1: Add CircuitBreaker integration to SODAClient:
- Import CircuitBreaker from src.db (or copy the pattern if import is complex)
- Before each SODA query, check circuit_breaker.is_open("soda")
- On success: circuit_breaker.record_success("soda")
- On timeout/error: circuit_breaker.record_failure("soda")
- When circuit is open: return empty list immediately (graceful degradation)

Task 79-4-2: Add Cache-Control headers for static pages in web/routes_misc.py:
- After /methodology, /about-data, /demo responses: add `Cache-Control: public, max-age=3600, stale-while-revalidate=86400`
- This is safe because these pages only change on deploy

Task 79-4-3: Add response timing header to all responses (via after_request):
- `X-Response-Time: {ms}ms` — helps identify slow pages from the client side
- Use g._request_start if available (already set by timing middleware in app.py)

Commit: "feat: SODA circuit breaker + Cache-Control + response timing header (Sprint 79-4)"

---

## Post-Agent Merge (Orchestrator)

1. Collect results from all 4 agents
2. Merge in order: 79-2 first (infrastructure), then 79-1, 79-3, 79-4
3. Run tests: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q`
4. Verify: `curl -s -o /dev/null -w "%{time_total}s" http://localhost:5000/report/3512/001` (should be faster)
5. Push to main
6. Report: response time before/after, cache hit rates, any BLOCKED items
