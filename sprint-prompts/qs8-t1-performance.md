# QS8 Terminal 1: Performance + Ops (Sprint 79)

You are the orchestrator for QS8-T1. Spawn 4 parallel build agents, collect results, merge, push to main. Do NOT run the full test suite — T0 handles that in the merge ceremony.

## Pre-Flight (30 seconds — T0 already verified tests + prod health)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T1 start: $(git rev-parse --short HEAD)"
```

## Context

**QS7 already shipped:** page_cache table, get_cached_or_compute(), invalidate_cache(), /cron/compute-caches, brief cache-read, Cache-Control on /brief. The 26 cache tests (test_page_cache.py + test_brief_cache.py) ALREADY PASS.

**What T1 builds:** The remaining performance work — N+1 DB fix, pipeline stats, cron endpoints for signals/velocity, SODA circuit breaker, and DB pool tuning.

**Sprint 78 shipped:** Per-session temp DuckDB for tests (conftest.py). No lock contention. Tests run on DuckDB locally, prod uses Postgres.

**Known test exclusions:** `--ignore=tests/test_tools.py --ignore=tests/e2e`

## Agent Preamble (include verbatim in every agent prompt)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. The orchestrator handles all merges.
Violating this rule destroys other agents' work.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-pending-review-qs8-t1-{agent}.md (e.g., scenarios-pending-review-qs8-t1-a.md)
  * CHANGELOG-qs8-t1-{agent}.md
  * Do NOT write to scenarios-pending-review.md or CHANGELOG.md directly.
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e 2>&1 | tail -10

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → Postgres needs ON CONFLICT DO UPDATE
- DuckDB uses ? placeholders, Postgres uses %s. Use src.db._PH or check src.db.BACKEND.
- conn.execute() works on DuckDB. Postgres needs cursor: with conn.cursor() as cur: cur.execute(...)
- Tests run on per-session temp DuckDB (conftest.py). Postgres bugs only surface on staging.
- CRON_WORKER env var needed for cron endpoint tests: monkeypatch.setenv("CRON_WORKER", "1")
```

## File Ownership Matrix

| Agent | Files Owned |
|-------|-------------|
| A | `web/report.py` |
| B | `web/brief.py`, `web/routes_cron.py` |
| C | `src/soda_client.py` |
| D | `web/routes_misc.py`, `web/app.py` (pool config + response timing ONLY) |

**Cross-agent overlap: ZERO.**

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent A: Report N+1 Fix

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Fix N+1 DB queries in property report (11s → ~2-3s)

### File Ownership
- web/report.py (ONLY this file)

### Read First
- web/report.py (full file — find the per-permit loop calling _get_contacts + _get_inspections)
- src/tools/permit_lookup.py (_get_contacts, _get_inspections patterns)
- src/db.py (BACKEND, _PH placeholder, get_connection)

### Problem
Property report for 44-permit parcel takes 11.6s. Root cause: _get_contacts() and _get_inspections() called per-permit in a loop (web/report.py). For 44 permits = 88 serial DB queries.

### Build

Task A-1: Create _get_contacts_batch(conn, permit_numbers: list) -> dict[str, list]
- Single query: SELECT * FROM contacts WHERE permit_number IN (...)
- Returns dict mapping permit_number -> list of contact dicts
- Handle both DuckDB (?) and Postgres (%s) placeholders via src.db.BACKEND

Task A-2: Create _get_inspections_batch(conn, permit_numbers: list) -> dict[str, list]
- Same pattern as contacts batch

Task A-3: Replace the per-permit loop in get_property_report():
```python
# BEFORE (N+1):
for permit in permits:
    permit['contacts'] = _get_contacts(conn, pnum)
    permit['inspections'] = _get_inspections(conn, pnum)

# AFTER (2 queries total):
pnums = [p['permit_number'] for p in permits if p.get('permit_number')]
contacts_map = _get_contacts_batch(conn, pnums)
inspections_map = _get_inspections_batch(conn, pnums)
for permit in permits:
    pnum = permit.get('permit_number', '')
    permit['contacts'] = contacts_map.get(pnum, [])
    permit['inspections'] = inspections_map.get(pnum, [])
```

Task A-4: Add SODA response caching (15-min TTL) for complaints/violations/property:
- Module-level dict: _soda_cache: dict[str, tuple[float, Any]] = {}
- Cache key = f'{endpoint_id}:{block}:{lot}'
- Before SODA calls, check cache. If fresh (<15 min), skip API call.

### Test
Write tests/test_sprint_79_1.py:
- test_get_contacts_batch returns dict grouped by permit_number
- test_get_inspections_batch same pattern
- test_soda_cache_hit skips API call on second request
- test_soda_cache_expired makes new API call after TTL

### Output Files
- scenarios-pending-review-qs8-t1-a.md
- CHANGELOG-qs8-t1-a.md

### Commit
perf: batch contacts/inspections + SODA caching in report.py (QS8-T1-A)
""")
```

---

### Agent B: Brief Pipeline Stats + Signals/Velocity Cron

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Brief pipeline stats + signals/velocity cron endpoints

### File Ownership
- web/brief.py
- web/routes_cron.py

### Read First
- web/brief.py (get_morning_brief function — understand the data assembly)
- web/routes_cron.py (existing cron endpoints — follow the auth pattern with CRON_SECRET)
- web/helpers.py (get_cached_or_compute is ALREADY IMPLEMENTED — use it directly)
- src/severity.py (severity scoring — for signals cron)
- src/station_velocity_v2.py (velocity data — for velocity cron)

### IMPORTANT: get_cached_or_compute() ALREADY EXISTS

QS7 shipped this in web/helpers.py. It is NOT a future dependency — it's live code. Import it directly:

```python
from web.helpers import get_cached_or_compute

# Usage:
brief_data = get_cached_or_compute(
    f"brief:{user_id}:{lookback}",
    lambda: get_morning_brief(user_id, lookback),
    ttl_minutes=30
)
```

Interface (already implemented):
- get_cached_or_compute(cache_key: str, compute_fn: callable, ttl_minutes: int = 30) -> dict
- On cache hit: returns dict with _cached=True, _cached_at="ISO 8601"
- On miss: calls compute_fn(), stores in page_cache table, returns result
- invalidate_cache(pattern: str) -> None (best-effort, SQL LIKE pattern)

### Build

Task B-1: Add pipeline stats to get_morning_brief() return dict:
- Query cron_log for last 5 nightly job durations, compute average
- Check which cron jobs succeeded/failed in last 24h
- Add under key "pipeline_stats" in returned dict

Task B-2: Add /cron/signals endpoint to web/routes_cron.py:
- POST, CRON_SECRET bearer auth (follow existing cron pattern)
- Run severity scoring for watched parcels
- Log results to cron_log
- monkeypatch.setenv("CRON_WORKER", "1") needed in tests

Task B-3: Add /cron/velocity-refresh endpoint to web/routes_cron.py:
- POST, CRON_SECRET bearer auth
- Refresh station_velocity_v2 data from addenda table
- Log results to cron_log

### Test
Write tests/test_sprint_79_3.py:
- test_pipeline_stats_included_in_brief
- test_cron_signals_requires_auth (with CRON_WORKER=1)
- test_cron_signals_runs_severity
- test_cron_velocity_refresh_requires_auth (with CRON_WORKER=1)
- test_cron_velocity_refresh_runs

### Output Files
- scenarios-pending-review-qs8-t1-b.md
- CHANGELOG-qs8-t1-b.md

### Commit
feat: brief pipeline stats + signals/velocity cron endpoints (QS8-T1-B)
""")
```

---

### Agent C: SODA Circuit Breaker

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Add circuit breaker to SODA API client

### File Ownership
- src/soda_client.py (ONLY this file)

### Read First
- src/soda_client.py (full file — SODAClient class, query method)
- src/db.py (look for any CircuitBreaker class or pattern — if it exists, reuse it)

### Build

Task C-1: Implement a simple CircuitBreaker class (or import from src.db if one exists):
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = 'closed'  # closed=normal, open=failing, half-open=testing

    def is_open(self) -> bool: ...
    def record_success(self): ...
    def record_failure(self): ...
```

Task C-2: Integrate into SODAClient.query():
- Before each SODA query, check circuit_breaker.is_open()
- When open: return empty list immediately (graceful degradation)
- On success: circuit_breaker.record_success()
- On timeout/httpx error: circuit_breaker.record_failure()
- Log circuit state changes (open/closed transitions)

Task C-3: Add configurable thresholds:
- SODA_CB_THRESHOLD env var (default 5)
- SODA_CB_TIMEOUT env var (default 60 seconds)

### Test
Write tests/test_sprint_79_4.py:
- test_circuit_breaker_starts_closed
- test_circuit_breaker_opens_after_threshold
- test_circuit_breaker_recovers_after_timeout
- test_soda_client_returns_empty_when_circuit_open
- test_soda_client_resets_on_success

### Output Files
- scenarios-pending-review-qs8-t1-c.md
- CHANGELOG-qs8-t1-c.md

### Commit
feat: SODA circuit breaker with configurable thresholds (QS8-T1-C)
""")
```

---

### Agent D: Cache-Control Headers + Response Timing + Pool Tuning

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Cache-Control headers + response timing + pool health endpoint

### File Ownership
- web/routes_misc.py
- web/app.py (ONLY: add response timing after_request hook + pool config. Do NOT touch other parts.)

### Read First
- web/routes_misc.py (existing routes — /methodology, /about-data, /demo, /health)
- web/app.py (after_request hooks, middleware, startup)
- src/db.py (get_pool_health, get_pool_stats — for health endpoint enhancement)

### Build

Task D-1: Add Cache-Control headers for static content pages in web/routes_misc.py:
- After /methodology, /about-data, /demo responses: Cache-Control: public, max-age=3600, stale-while-revalidate=86400
- These pages only change on deploy — safe to cache aggressively

Task D-2: Add response timing header in web/app.py (after_request hook):
- X-Response-Time: {ms}ms on every response
- Use g._request_start if it exists (timing middleware may already set this)
- If not, add a before_request that sets g._request_start = time.time()

Task D-3: Enhance /health endpoint in web/routes_misc.py:
- Add pool_stats: include get_pool_stats() output (connection pool health)
- Add cache_stats: count of page_cache rows, oldest entry age
- Keep existing health checks (tables, backend, etc.)

Task D-4: Add DB_POOL_MAX environment variable documentation:
- Read current pool config from src/db.py (_get_pool function)
- Current default: min=2, max=20
- Add comment in src/db.py near pool creation: "# Increase DB_POOL_MAX for >50 concurrent users. See Chief #364."
- Do NOT change the actual defaults — just document the knob.

### Test
Write tests/test_sprint_79_d.py:
- test_methodology_has_cache_control
- test_about_data_has_cache_control
- test_demo_has_cache_control
- test_response_timing_header_present
- test_health_includes_pool_stats

### Output Files
- scenarios-pending-review-qs8-t1-d.md
- CHANGELOG-qs8-t1-d.md

### Commit
feat: Cache-Control + response timing + pool health monitoring (QS8-T1-D)
""")
```

---

## Post-Agent: Merge + Push

After all 4 agents complete:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Merge in dependency order: D first (app.py infra), then A, B, C
git merge <agent-d-branch> --no-edit
git merge <agent-a-branch> --no-edit
git merge <agent-b-branch> --no-edit
git merge <agent-c-branch> --no-edit

# Concatenate per-agent output files
cat scenarios-pending-review-qs8-t1-*.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-qs8-t1-*.md >> CHANGELOG.md 2>/dev/null

# Push to main. Do NOT run the full test suite — T0 handles that.
git push origin main
```

## Report Template

```
T1 (Performance) COMPLETE
  A: Report N+1 fix:        [PASS/FAIL]
  B: Pipeline stats + cron:  [PASS/FAIL]
  C: SODA circuit breaker:   [PASS/FAIL]
  D: Headers + timing + pool: [PASS/FAIL]
  Scenarios: [N] across 4 files
  Pushed: [commit hash]
```
