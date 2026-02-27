# QS7 Terminal 1: Speed Infrastructure

> Paste this into CC Terminal 1. It spawns 4 agents via Task tool.
> **Merge order: Terminal 1 merges FIRST** — Terminals 2+3 depend on this.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3  # verify clean HEAD
source .venv/bin/activate
pytest tests/ -x -q --tb=no --ignore=tests/test_tools.py --timeout=30 2>&1 | tail -3
```

Verify: tests pass, HEAD is the expected commit. If not, stop and investigate.

## File Ownership (Terminal 1 ONLY touches these)

| Agent | Files |
|---|---|
| 1A | `web/helpers.py`, new migration in `web/app.py` startup block |
| 1B | `web/routes_misc.py` |
| 1C | `web/routes_cron.py` |
| 1D | `web/app.py` (after_request handler only), `scripts/prod_gate.py`, `web/static/sw.js` |

**No templates.** Terminal 1 is pure backend. Template work belongs to Terminals 2+3.

## Launch All 4 Agents (FOREGROUND, parallel)

Spawn all 4 agents in a single message using the Task tool:

---

### Agent 1A: Page Cache Infrastructure

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Page Cache Infrastructure

Build the page_cache table and cache utility that enables sub-second page loads.

### Read First
- docs/DESIGN_TOKENS.md (skim — you won't touch templates, but understand the context)
- web/helpers.py (your primary file — currently 243 lines)
- web/app.py lines 1-100 (startup block where table creation happens)
- src/db.py (understand get_db_connection patterns)

### Build

**1. Add page_cache table DDL to web/app.py startup block:**

Find the existing `CREATE TABLE IF NOT EXISTS` block in `_ensure_tables()` or equivalent startup function. Add:

```sql
CREATE TABLE IF NOT EXISTS page_cache (
    cache_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    computed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    invalidated_at TIMESTAMP,
    ttl_minutes INT DEFAULT 30
);
CREATE INDEX IF NOT EXISTS idx_page_cache_invalidated ON page_cache (cache_key) WHERE invalidated_at IS NOT NULL;
```

IMPORTANT: Use TEXT for payload, not JSONB — DuckDB doesn't support JSONB. The payload is JSON-serialized via `json.dumps()`.

**2. Add cache utility to web/helpers.py:**

```python
import json
import time
from datetime import datetime, timezone

def get_cached_or_compute(cache_key, compute_fn, ttl_minutes=30):
    \"\"\"Read from page_cache or compute and store. Returns dict.\"\"\"
    from src.db import get_db_connection
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT payload, computed_at, invalidated_at FROM page_cache WHERE cache_key = ?",
            (cache_key,)
        ).fetchone()
        if row:
            payload, computed_at, invalidated_at = row
            if invalidated_at is None:
                if isinstance(computed_at, str):
                    computed_at = datetime.fromisoformat(computed_at)
                age_minutes = (datetime.now(timezone.utc) - computed_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
                if age_minutes < ttl_minutes:
                    result = json.loads(payload)
                    result['_cached'] = True
                    result['_cached_at'] = computed_at.isoformat()
                    return result
    except Exception:
        pass  # Cache miss — compute below

    # Cache miss or stale
    result = compute_fn()
    try:
        payload_json = json.dumps(result, default=str)
        conn.execute(
            "INSERT INTO page_cache (cache_key, payload, computed_at, invalidated_at) VALUES (?, ?, NOW(), NULL) "
            "ON CONFLICT (cache_key) DO UPDATE SET payload = EXCLUDED.payload, computed_at = NOW(), invalidated_at = NULL",
            (cache_key, payload_json)
        )
        conn.commit()
    except Exception:
        pass  # Cache write failed — non-fatal, result still returned
    return result


def invalidate_cache(pattern):
    \"\"\"Invalidate cache entries matching a LIKE pattern.\"\"\"
    from src.db import get_db_connection
    try:
        conn = get_db_connection()
        conn.execute(
            "UPDATE page_cache SET invalidated_at = NOW() WHERE cache_key LIKE ?",
            (pattern,)
        )
        conn.commit()
    except Exception:
        pass
```

**Known DuckDB/Postgres gotcha:** DuckDB uses `?` for parameters, Postgres uses `%s`. Check how existing code in web/ handles this — likely there's a helper or the connection object normalizes it. Match the existing pattern.

### Test
```bash
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --timeout=30 -k "not test_cron" 2>&1 | tail -5
```

### Commit
Commit to your worktree branch with message:
`feat: page_cache table + get_cached_or_compute utility`

Do NOT merge to main. The orchestrator handles merging.
""")
```

---

### Agent 1B: Brief Route Cache Integration

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Wire /brief to serve from page_cache

### Read First
- web/routes_misc.py (your primary file — the /brief route is here)
- web/brief.py lines 1-100 (understand get_morning_brief signature)
- web/helpers.py (where get_cached_or_compute will live — Agent 1A is building it)

### Build

**1. Modify the /brief route in web/routes_misc.py:**

Current code:
```python
@bp.route("/brief")
@login_required
def brief():
    from web.brief import get_morning_brief
    from web.auth import get_primary_address
    lookback = request.args.get("lookback", "1")
    try:
        lookback_days = max(1, min(int(lookback), 90))
    except ValueError:
        lookback_days = 1
    primary_addr = get_primary_address(g.user["user_id"])
    brief_data = get_morning_brief(g.user["user_id"], lookback_days, primary_address=primary_addr)
    return render_template("brief.html", user=g.user, brief=brief_data, active_page="brief")
```

Replace with:
```python
@bp.route("/brief")
@login_required
def brief():
    from web.brief import get_morning_brief
    from web.auth import get_primary_address
    from web.helpers import get_cached_or_compute
    lookback = request.args.get("lookback", "1")
    try:
        lookback_days = max(1, min(int(lookback), 90))
    except ValueError:
        lookback_days = 1
    primary_addr = get_primary_address(g.user["user_id"])
    cache_key = f"brief:{g.user['user_id']}:{lookback_days}"
    brief_data = get_cached_or_compute(
        cache_key,
        lambda: get_morning_brief(g.user["user_id"], lookback_days, primary_address=primary_addr),
        ttl_minutes=30
    )
    # Add cache metadata for template
    brief_data['cached_at'] = brief_data.get('_cached_at')
    brief_data['can_refresh'] = True
    return render_template("brief.html", user=g.user, brief=brief_data, active_page="brief")
```

**2. Add POST /brief/refresh endpoint (rate-limited):**

```python
@bp.route("/brief/refresh", methods=["POST"])
@login_required
def brief_refresh():
    from web.helpers import invalidate_cache
    user_id = g.user["user_id"]
    # Rate limit: check if last refresh was < 5 min ago
    # Simple approach: use a session variable
    last_refresh = session.get("last_brief_refresh", 0)
    import time
    if time.time() - last_refresh < 300:
        return "Rate limited — try again in a few minutes", 429
    invalidate_cache(f"brief:{user_id}:%")
    session["last_brief_refresh"] = time.time()
    return redirect(url_for("misc.brief"))
```

**Interface contract for Terminal 3:** The template will receive `brief.cached_at` (ISO string or None) and `brief.can_refresh` (True). Terminal 3 Agent 3A will render these.

### Test
```bash
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --timeout=30 2>&1 | tail -5
```

### Commit
`feat: /brief serves from page_cache with refresh endpoint`
""")
```

---

### Agent 1C: Cron Pre-Compute + Invalidation

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Cron pre-compute briefs + event-driven cache invalidation

### Read First
- web/routes_cron.py (your primary file — 2042 lines, add endpoints here)
- web/brief.py lines 1-30 (get_morning_brief signature)
- web/auth.py (find get_primary_address, get user list patterns)
- web/helpers.py (where get_cached_or_compute and invalidate_cache will live)

### Build

**1. Add POST /cron/compute-caches endpoint to routes_cron.py:**

```python
@cron_bp.route("/cron/compute-caches", methods=["POST"])
def compute_caches():
    \"\"\"Pre-compute briefs for all active users. Runs every 15 min.\"\"\"
    _check_cron_auth()  # Use existing auth pattern from other cron endpoints
    from web.brief import get_morning_brief
    from web.auth import get_primary_address
    from web.helpers import get_cached_or_compute
    from src.db import get_db_connection

    conn = get_db_connection()
    users = conn.execute("SELECT user_id FROM users WHERE user_id IS NOT NULL").fetchall()

    computed = 0
    errors = 0
    for row in users:
        user_id = row[0]
        try:
            primary_addr = get_primary_address(user_id)
            cache_key = f"brief:{user_id}:1"  # Default lookback=1
            get_cached_or_compute(
                cache_key,
                lambda uid=user_id, pa=primary_addr: get_morning_brief(uid, 1, primary_address=pa),
                ttl_minutes=30
            )
            computed += 1
        except Exception as e:
            errors += 1
            current_app.logger.warning(f"Brief pre-compute failed for {user_id}: {e}")

    return jsonify({"computed": computed, "errors": errors, "total_users": len(users)})
```

Follow the existing patterns in routes_cron.py for auth checking, logging, and error handling.

**2. Wire invalidation into existing cron handlers:**

Find the functions that process permit_changes, inspections, and violations. After they insert new data, add:

```python
from web.helpers import invalidate_cache
# After inserting permit_changes for specific permits:
# invalidate_cache("brief:%")  # Invalidate all user briefs
```

Start simple: invalidate ALL briefs when any cron data changes. Per-user targeted invalidation is a future optimization.

**Known gotcha:** routes_cron.py has CRON_GUARD checking. Test fixtures need `monkeypatch.setenv("CRON_WORKER", "1")` for cron endpoint tests.

### Test
```bash
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --timeout=30 -k "cron" 2>&1 | tail -5
```

### Commit
`feat: cron pre-compute briefs + invalidation on data changes`
""")
```

---

### Agent 1D: Cache Headers + Prod Gate v2

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Cache-Control headers for static pages + prod gate enhancements

### Read First
- web/app.py (add after_request handler — 1440 lines, find existing after_request hooks)
- scripts/prod_gate.py (your secondary file — add 3 new checks)

### Build

**1. Add Cache-Control headers in web/app.py:**

Find the existing `after_request` handler (or create one). Add:

```python
@app.after_request
def add_cache_headers(response):
    static_pages = ["/methodology", "/about-data", "/demo", "/pricing"]
    if request.path in static_pages and response.status_code == 200:
        response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
    return response
```

If an after_request handler already exists, ADD to it rather than creating a duplicate.

**2. Add 3 new checks to scripts/prod_gate.py:**

Read the existing check functions for the pattern, then add:

**Check 11: Migration safety (Task #350)**
```python
def check_migration_safety():
    \"\"\"Check if recent commits contain migration-like SQL without down-migration.\"\"\"
    # Grep recent commits for CREATE TABLE, ALTER TABLE, DROP
    # Score 5 if no migrations, 3 if migrations present, 1 if DROP without backup
    ...
```

**Check 12: Cron endpoint health (Task #352)**
```python
def check_cron_health(staging_url):
    \"\"\"Verify cron endpoints return 200 (without executing).\"\"\"
    # HEAD or GET to /cron/nightly, /cron/compute-caches
    # These may require CRON_SECRET header
    # Score 5 if all respond, 3 if some fail, 1 if none respond
    ...
```

**Check 13: Design lint trend (Task #353)**
```python
def check_lint_trend():
    \"\"\"Track violation count trend across runs.\"\"\"
    # Read/write qa-results/design-lint-history.json
    # Compare current run to last 3 runs
    # Score 5 if stable/declining, 3 if growing, 1 if spiking
    ...
```

Wire all 3 into the main() function's check sequence. Add to CATEGORY_WEIGHTS:
- migration_safety → safety category (1.0x)
- cron_health → ops category (0.8x)
- lint_trend → design category (0.6x)

### Test
```bash
source .venv/bin/activate
python scripts/prod_gate.py --skip-remote --skip-tests --quiet
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --timeout=30 2>&1 | tail -5
```

### Commit
`feat: Cache-Control headers + prod gate v2 (migration, cron, lint trend)`
""")
```

---

## Post-Agent: Merge

After all 4 agents complete:

```bash
# From main repo root (not a worktree):
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull

# Merge in dependency order:
git merge <agent-1a-branch>  # page_cache infrastructure first
git merge <agent-1b-branch>  # brief route (depends on 1A's utility)
git merge <agent-1c-branch>  # cron pre-compute (depends on 1A's utility)
git merge <agent-1d-branch>  # cache headers + prod gate (independent)

# Single test run:
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --timeout=30

# Push:
git push origin main
```

**Report to Tim:**
```
Terminal 1 complete:
  1A: page_cache table + utility — [PASS/FAIL]
  1B: /brief cache integration — [PASS/FAIL]
  1C: cron pre-compute + invalidation — [PASS/FAIL]
  1D: cache headers + prod gate v2 — [PASS/FAIL]
  Tests: [N passed, M failed]
  Pushed to main: [commit hash]
```
