<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs4-b-performance.md and execute it" -->

# Quad Sprint 4 — Session B: Performance + Production Hardening

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs4-b
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs4-b before any code changes.
MERGE RULE: Do NOT merge your branch to main. Commit to worktree branch only. The orchestrator (Tab 0) merges all branches.
CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files. If you encounter a conflict, stop and report it.
APPEND FILES: Write scenarios to `scenarios-pending-review-qs4-b.md` (not the shared file). Write changelog to `CHANGELOG-qs4-b.md`.
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
   Use EnterWorktree with name `qs4-b`

If worktree exists: `git worktree remove .claude/worktrees/qs4-b --force 2>/dev/null; true`

4. **Safety tag:** `git tag pre-qs4-b`

---

## PHASE 1: READ

Read these files before writing any code:
1. `CLAUDE.md` — project structure, deployment, rules
2. `src/db.py` lines 1-60 — connection pool config (maxconn=20, ThreadedConnectionPool)
3. `src/db.py` lines 120-170 — statement_timeout, slow query logging
4. `web/app.py` lines 1102-1150 — existing `/health` endpoint
5. `web/app.py` lines 1231-1280 — existing `/health/schema` endpoint (already built by CC0)
6. `web/routes_misc.py` — health-related routes
7. `Dockerfile` — current build process
8. `Dockerfile.mcp` — MCP server build
9. `web/railway.toml` — gunicorn config (4 workers, gevent, 100 connections)
10. `scenario-design-guide.md` — for scenario-keyed QA

**Architecture notes:**
- Connection pool: `psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=20)` at `src/db.py:44`
- Railway Postgres max_connections = 100. With 4 web workers + 1 cron worker, each gets own pool: 5 × 20 = 100. This is at the limit, NOT a bottleneck to fix by increasing. Gevent greenlets yield during I/O so 20 connections per worker handles concurrency well.
- Task is: make pool configurable via env var, add monitoring stats to /health. NOT increase pool size.
- `/health/schema` already exists (CC0 built it) — verify it works, don't rebuild
- `/health/ready` does NOT exist yet — needs to be created
- Docker build currently happens from source on Railway (~5 min). Pre-built GHCR images would cut to ~30s.

---

## PHASE 2: BUILD

### Task B-1: Connection Pool Monitoring + Env Override (~30 min)
**Files:** `src/db.py`

**IMPORTANT MATH:** Railway Postgres max_connections = 100. With 4 web workers + 1 cron worker, each gets a separate pool. Current `maxconn=20` means 5 × 20 = 100 — exactly at the limit. Do NOT increase the default. Instead, make it env-configurable and add monitoring.

```python
# At line ~44, make configurable but keep default at 20:
maxconn=int(os.environ.get("DB_POOL_MAX", "20"))
```

**Add pool stats function:**
```python
def get_pool_stats() -> dict:
    """Return connection pool statistics for /health endpoint."""
    if _pool is None:
        return {"status": "no_pool", "backend": BACKEND}
    return {
        "backend": BACKEND,
        "minconn": _pool.minconn,
        "maxconn": _pool.maxconn,
        "closed": _pool.closed,
        # psycopg2 ThreadedConnectionPool tracks used/available internally
        "pool_size": len(_pool._pool) if hasattr(_pool, '_pool') else -1,
        "used_count": len(_pool._used) if hasattr(_pool, '_used') else -1,
    }
```

### Task B-2: /health/ready Endpoint (~30 min)
**Files:** `web/app.py` (append after /health/schema)

**Create `/health/ready`:**
```python
@app.route("/health/ready")
def health_ready():
    """Readiness probe — returns 200 only when fully operational.

    Use as Railway health check for zero-downtime deploys.
    Checks: DB pool initialized, all expected tables exist, latest migration applied.
    """
    from src.db import get_connection, BACKEND
    checks = {"db_pool": False, "tables": False, "migrations": False}

    try:
        conn = get_connection()
        try:
            checks["db_pool"] = True
            # Check expected tables exist
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute("SET statement_timeout = '5s'")
                    cur.execute("""
                        SELECT tablename FROM pg_tables
                        WHERE schemaname = 'public' AND tablename = ANY(%s)
                    """, (EXPECTED_TABLES,))
                    found = {row[0] for row in cur.fetchall()}
                    missing = set(EXPECTED_TABLES) - found
                    checks["tables"] = len(missing) == 0
                    checks["missing_tables"] = sorted(missing) if missing else []
                    # Check latest migration marker (prep_checklists exists = QS3-A deployed)
                    cur.execute("SELECT 1 FROM pg_tables WHERE tablename = 'prep_checklists'")
                    checks["migrations"] = cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as e:
        checks["error"] = str(e)

    all_ready = all(checks.get(k) for k in ["db_pool", "tables", "migrations"])
    status_code = 200 if all_ready else 503
    return jsonify({"ready": all_ready, "checks": checks}), status_code
```

### Task B-3: Pool Stats in /health Response (~15 min)
**Files:** `web/app.py` (modify /health)

Add pool stats to the existing `/health` response:
```python
# After the tables dict is populated, before return:
from src.db import get_pool_stats
info["pool"] = get_pool_stats()
```

### Task B-4: Pre-built Docker Images via GitHub Actions (~45 min)
**Files:** `.github/workflows/docker-build.yml` (NEW)

**Create GitHub Actions workflow:**
```yaml
name: Build & Push Docker Image
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:latest
            ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Note:** Railway still needs to be configured to pull from GHCR instead of building from source. Document this as a manual step for Tim.

### Task B-5: Charis Beta Invite Flow Polish (~25 min)
**Files:** `web/templates/demo.html`

**Polish `/demo` page for Charis meeting:**
- Verify invite code `friends-gridcare` works (test signup flow)
- Update `/demo` copy to emphasize:
  - MCP architecture (Claude integration)
  - Entity resolution (1M entities, 576K relationships)
  - AI vision plan analysis
  - 30 tools available via MCP
- Add a clear CTA: "Try it yourself" → `/auth/login?invite_code=friends-gridcare`
- Ensure the page looks polished on desktop (Charis will view on laptop during Zoom)

---

## PHASE 3: TEST

```bash
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py -q
```

Write `tests/test_qs4_b_perf.py`:
- get_pool_stats returns dict with backend, maxconn keys
- get_pool_stats returns "no_pool" when pool is None
- DB_POOL_MAX env var overrides default maxconn
- Default maxconn is still 20 (Railway limit: 100 / 5 workers = 20)
- /health response includes "pool" key
- /health/ready returns 200 when all checks pass
- /health/ready returns 503 when tables missing
- /health/ready checks db_pool, tables, migrations
- /health/ready has 5s statement_timeout (doesn't hang)
- /health/schema still works (regression check — CC0 built it)
- GitHub Actions workflow file is valid YAML
- Dockerfile builds successfully (dry-run parse)
- /demo renders 200
- /demo contains MCP or entity resolution keywords
- /demo has CTA linking to signup with invite code
- /auth/send-link with friends-gridcare invite code succeeds

**Target: 20+ tests**

---

## PHASE 4: SCENARIOS

Append 3 scenarios to `scenarios-pending-review-qs4-b.md`:
1. "Production handles 50 concurrent users without connection pool exhaustion"
2. "Railway zero-downtime deploy uses /health/ready to verify new container is operational"
3. "Connection pool stats visible in /health response for ops monitoring"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs4-b-performance-qa.md`:

```
1. [NEW] GET /health includes pool stats (maxconn, used_count) — PASS/FAIL
2. [NEW] GET /health/ready returns 200 with all checks passing — PASS/FAIL
3. [NEW] GET /health/ready returns 503 when simulating missing table — PASS/FAIL
4. [NEW] GET /health/schema still works (CC0 regression) — PASS/FAIL
5. [NEW] DB_POOL_MAX env var is respected (default 20) — PASS/FAIL
6. [NEW] .github/workflows/docker-build.yml exists and is valid — PASS/FAIL
7. [NEW] /demo page renders with polished Charis copy — PASS/FAIL
8. [NEW] /demo has CTA linking to signup with invite code — PASS/FAIL
9. [NEW] Screenshot /demo at 1440px — PASS/FAIL
```

Save results to `qa-results/qs4-b-results.md`

---

## PHASE 5.5: VISUAL REVIEW

Score these pages 1-5:
- /demo at 1440px (Charis will see this on Zoom)

---

## PHASE 6: CHECKCHAT

### 1. VERIFY
- All QA FAILs fixed or BLOCKED
- pytest passing, no regressions

### 2. DOCUMENT
- Write `CHANGELOG-qs4-b.md` with session entry

### 3. CAPTURE
- 3 scenarios in `scenarios-pending-review-qs4-b.md`

### 4. SHIP
- Commit with: "feat: Pool monitoring + health/ready + Docker CI (QS4-B)"

### 5. PREP NEXT
- Note: Railway must be configured to pull from GHCR (manual Tim step)
- Note: /health/ready URL should be set as Railway health check

### 6. BLOCKED ITEMS REPORT

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Estimated | Actual |
|--------|-----------|--------|
| Wall clock time | 2 hours | [first commit to CHECKCHAT] |
| New tests | 20+ | [count] |
| Tasks completed | 5 | [N of 5] |
| Tasks descoped | — | [count + reasons] |
| Tasks blocked | — | [count + reasons] |
| Longest task | — | [task name, duration] |
| QA checks | 9 | [pass/fail/skip] |
| Visual Review avg | N/A | N/A (JSON endpoints only) |
| Scenarios proposed | 3 | [count] |
```

### Visual QA Checklist
- [ ] /health JSON: is the pool stats section clear and useful for ops?
- [ ] /health/ready: does the 200/503 distinction make sense for Railway?
- [ ] /demo page: would this impress an AI architect evaluating the product?

---

## File Ownership (Session B ONLY)
**Own:**
- `src/db.py` (pool config, pool stats function)
- `web/app.py` (health endpoint modifications, /health/ready)
- `.github/workflows/docker-build.yml` (NEW)
- `web/templates/demo.html` (Charis polish)
- `tests/test_qs4_b_perf.py` (NEW)
- `CHANGELOG-qs4-b.md` (NEW — per-agent)
- `scenarios-pending-review-qs4-b.md` (NEW — per-agent)

**Do NOT touch:**
- `web/security.py` (Session D)
- `web/templates/index.html` (Session C)
- `web/templates/brief.html` (Session C)
- `src/ingest.py` (Session A)
- `src/station_velocity_v2.py` (Session A)
- `web/routes_admin.py` (Session A)
- `web/routes_cron.py` (Session A)
- `web/static/design-system.css` (Session C)
