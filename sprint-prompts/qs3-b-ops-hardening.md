<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs3-b-ops-hardening.md and execute it" -->

# Quad Sprint 3 — Session B: Operational Hardening

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs3-b
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs3-b before any code changes.
```

## SETUP — Session Bootstrap

1. `cd /Users/timbrenneman/AIprojects/sf-permits-mcp`
2. `git checkout main && git pull origin main`
3. Use EnterWorktree with name `qs3-b`
4. `git tag pre-qs3-b`

If worktree exists: `git worktree remove .claude/worktrees/qs3-b --force 2>/dev/null; true`

---

## PHASE 1: READ

1. `CLAUDE.md` — project structure
2. `src/tools/permit_lookup.py` — read `_get_related_team` function (lines ~305-344). This is the O(n²) self-join you'll replace.
3. `src/db.py` — database connection handling, _PooledConnection wrapper
4. `web/routes_cron.py` — cron pipeline, existing endpoints
5. `web/app.py` — health endpoint (you'll enhance it). Note: Session D also touches this file. Mark your changes with `# === QS3-B: HEALTH ENHANCEMENT ===`
6. `scripts/postgres_schema.sql` — read `relationships` table schema (entity_id_a, entity_id_b, shared_permits, permit_numbers, neighborhoods)
7. `scenario-design-guide.md` — for scenario-keyed QA

**Pre-flight audit confirmed:**
- `_get_related_team` uses 4-table self-join (contacts × contacts × permits × entities) — NOT the relationships table
- No CircuitBreaker class exists anywhere
- No /cron/heartbeat endpoint exists
- CRON_WORKER pattern exists in src/db.py and web/app.py (_cron_guard)
- `relationships` table: 576K edges, PK (entity_id_a, entity_id_b), indexed on both columns

---

## PHASE 2: BUILD

### Task B-1: Graph-Based Related Team Lookup (~60 min)
**Files:** `src/tools/permit_lookup.py` (`_get_related_team` function ONLY)

Replace the O(n²) self-join with the pre-computed `relationships` table:

**Current (slow):**
```sql
FROM contacts c1
JOIN contacts c2 ON c1.entity_id = c2.entity_id AND c2.permit_number != ?
JOIN permits p ON c2.permit_number = p.permit_number
JOIN entities e ON c1.entity_id = e.entity_id
WHERE c1.permit_number = ?
```

**New approach:**
1. Get entity_ids from the permit's contacts: `SELECT DISTINCT entity_id FROM contacts WHERE permit_number = ? AND entity_id IS NOT NULL`
2. For each entity_id, query relationships: `SELECT entity_id_b, shared_permits, permit_numbers, neighborhoods FROM relationships WHERE entity_id_a = ?` (plus reverse: entity_id_b = ?)
3. Get connected entity details: `SELECT entity_id, canonical_name, canonical_firm, permit_count FROM entities WHERE entity_id IN (...)`
4. Get their recent permits: `SELECT permit_number, permit_type_definition, status, filed_date FROM permits WHERE permit_number IN (...) ORDER BY filed_date DESC LIMIT 25`

This is O(E) where E = number of entities on the permit (typically 3-5), vs O(N²) where N = all contacts sharing any entity.

**Keep the DuckDB fallback:** The relationships table may not exist in DuckDB test environments. If `relationships` table doesn't exist, fall back to the old self-join with a logged warning.

**Verify:** Add a comment showing before/after approach. If possible, log query time for comparison.

### Task B-2: Circuit Breaker Pattern (~45 min)
**Files:** `src/db.py` (new CircuitBreaker class)

```python
class CircuitBreaker:
    """Per-category query circuit breaker.

    Tracks failures per category. After max_failures within window_seconds,
    the circuit "opens" and auto-skips queries for cooldown_seconds.
    """
    def __init__(self, max_failures=3, window_seconds=120, cooldown_seconds=300):
        self._failures = {}  # category -> list of timestamps
        self._open_until = {}  # category -> timestamp when circuit closes

    def is_open(self, category: str) -> bool:
        """Return True if circuit is open (should skip queries)."""

    def record_failure(self, category: str):
        """Record a failure. Opens circuit if threshold exceeded."""

    def record_success(self, category: str):
        """Record success. Resets failure count for category."""

    def get_status(self) -> dict:
        """Return status dict for /health endpoint."""
        # {"inspections": "closed", "related_team": "open (3 failures, reopens in 4m)"}

# Module-level singleton
circuit_breaker = CircuitBreaker()
```

**Categories:** `inspections`, `contacts`, `related_team`, `addenda`, `complaints`, `violations`, `planning_records`, `boiler_permits`

**Integration:** Update the try/except blocks in `permit_lookup.py`'s enrichment functions to check `circuit_breaker.is_open(category)` before querying, and call `record_failure/success` after.

Wait — `permit_lookup.py` is owned by this session for `_get_related_team` only. The enrichment try/excepts are already there from the hotfix. Add circuit breaker checks to those existing try/excepts without restructuring — just add `if circuit_breaker.is_open("inspections"): return []` at the top of each enrichment function.

### Task B-3: Cron Heartbeat + Health Enhancement (~30 min)
**Files:** `web/routes_cron.py` (append), `web/app.py` (health — marked section)

**In `web/routes_cron.py`, add:**
```python
@bp.route("/cron/heartbeat", methods=["POST"])
def cron_heartbeat():
    """Write heartbeat timestamp to cron_log."""
    # INSERT INTO cron_log (job_type, status, started_at, finished_at)
    # VALUES ('heartbeat', 'completed', NOW(), NOW())
```

**In `web/app.py`, enhance `/health` endpoint:**
Add inside clearly marked section:
```python
# === QS3-B: HEALTH ENHANCEMENT ===
# Add circuit breaker status
from src.db import circuit_breaker
health_data["circuit_breakers"] = circuit_breaker.get_status()

# Add cron heartbeat age
# Query: SELECT MAX(finished_at) FROM cron_log WHERE job_type = 'heartbeat'
# Calculate age in minutes
health_data["cron_heartbeat_age_minutes"] = heartbeat_age
if heartbeat_age and heartbeat_age > 120:
    health_data["cron_heartbeat_status"] = "CRITICAL"
elif heartbeat_age and heartbeat_age > 30:
    health_data["cron_heartbeat_status"] = "WARNING"
else:
    health_data["cron_heartbeat_status"] = "OK"
# === END QS3-B ===
```

### Task B-4: Pipeline Step Timing (~20 min)
**Files:** `web/routes_cron.py` (extend nightly pipeline)

In the nightly pipeline function, wrap each step with timing:
```python
import time
step_start = time.monotonic()
# ... run step ...
elapsed = time.monotonic() - step_start
# INSERT INTO cron_log (job_type, status, ..., extra)
# extra = json.dumps({"elapsed_seconds": elapsed})
```

Add `GET /cron/pipeline-summary`:
```python
@bp.route("/cron/pipeline-summary")
def pipeline_summary():
    """Return last nightly pipeline step timings."""
    # Query cron_log for most recent nightly entries, return JSON
```

---

## PHASE 3: TEST

Write `tests/test_qs3_b_ops_hardening.py`:
- _get_related_team returns results using relationships table (mock DB with relationships data)
- _get_related_team falls back to self-join when relationships table missing (DuckDB)
- CircuitBreaker starts closed
- CircuitBreaker opens after max_failures
- CircuitBreaker auto-skips when open
- CircuitBreaker resets on success
- CircuitBreaker cooldown expires and circuit closes
- CircuitBreaker.get_status returns correct dict
- /health includes circuit_breakers key
- /health includes cron_heartbeat_age_minutes
- Heartbeat age WARNING when >30 min
- Heartbeat age CRITICAL when >2 hours
- POST /cron/heartbeat writes to cron_log
- /cron/pipeline-summary returns JSON with step timings
- Enrichment functions check circuit_breaker.is_open before querying

**Target: 30+ tests**

---

## PHASE 4: SCENARIOS

Cite existing scenario IDs if any cover health/monitoring. Append 3 NEW:
1. "Circuit breaker auto-skips enrichment queries after repeated timeouts"
2. "Health endpoint shows circuit breaker states and cron heartbeat age"
3. "Pipeline summary shows elapsed time per nightly step"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs3-b-ops-hardening-qa.md`:
```
1. [NEW] _get_related_team returns results with mock relationships data — PASS/FAIL
2. [NEW] Simulate 3 timeouts — circuit breaker opens — PASS/FAIL
3. [NEW] Circuit breaker skips query when open — PASS/FAIL
4. [NEW] GET /health includes "circuit_breakers" key — PASS/FAIL
5. [NEW] GET /health includes "cron_heartbeat_age_minutes" — PASS/FAIL
6. [NEW] POST /cron/heartbeat returns 200 — PASS/FAIL
7. [NEW] GET /cron/pipeline-summary returns JSON — PASS/FAIL
```

No Playwright needed (backend only). Use pytest + Flask test client.
Write results to `qa-results/qs3-b-results.md`

---

## PHASE 5.5: VISUAL REVIEW
N/A — backend only, no UI pages.

---

## PHASE 6: CHECKCHAT

### 1-6: Standard (VERIFY, DOCUMENT, CAPTURE, SHIP, PREP NEXT, BLOCKED)

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Estimated | Actual |
|--------|-----------|--------|
| Wall clock time | 2-3 hours | [actual] |
| New tests | 30+ | [count] |
| Total tests | ~3,460 | [pytest output] |
| Tasks completed | 4 | [N of 4] |
| Tasks descoped | — | [count + reasons] |
| Tasks blocked | — | [count + reasons] |
| Longest task | — | [task, duration] |
| QA checks | 7 | [pass/fail/skip] |
| Visual Review avg | N/A | N/A |
| Scenarios proposed | 3 | [count] |
```

### DeskRelay HANDOFF
None — backend only.

---

## File Ownership (Session B ONLY)
**Own:**
- `src/tools/permit_lookup.py` (`_get_related_team` + circuit breaker integration in enrichment functions)
- `src/db.py` (CircuitBreaker class)
- `web/routes_cron.py` (heartbeat + pipeline timing)
- `web/app.py` (health enhancement — `# === QS3-B: HEALTH ENHANCEMENT ===` section ONLY)
- `tests/test_qs3_b_ops_hardening.py` (NEW)

**Do NOT touch:**
- `web/permit_prep.py` (Session A)
- `web/routes_api.py` (Session A)
- `web/routes_property.py` (Session A)
- `web/brief.py` (Session A)
- `web/templates/` (Sessions A + D)
- `tests/e2e/` (Session C)
- `web/helpers.py` (Session D)
- `web/routes_misc.py` (Session D)
- `scripts/release.py` (Sessions A + D)
