# QS9 Terminal 3: Scaling Infrastructure

You are the orchestrator for QS9-T3. Spawn 4 parallel build agents, collect results, merge, push to main. Do NOT run the full test suite — T0 handles that.

## Pre-Flight (30 seconds)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T3 start: $(git rev-parse --short HEAD)"
```

## Context

REDIS_URL is set on all Railway services (staging, prod, cron worker):
`redis://default:***@redis.railway.internal:6379`

This is an internal Railway URL — only reachable from within Railway's network. For local testing, agents should mock Redis or use `fakeredis` package.

## File Ownership

| Agent | Files Owned |
|-------|-------------|
| A | `src/db.py`, `docs/ONBOARDING.md` |
| B | `web/app.py` (after_request hooks ONLY) |
| C | `web/helpers.py` (rate limiter section ONLY), `pyproject.toml` |
| D | `scripts/load_test.py`, `docs/SCALING.md` (NEW) |

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent A: DB Pool Tuning + Health

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Tune DB pool defaults + add exhaustion warnings

### File Ownership
- src/db.py
- docs/ONBOARDING.md

### Read First
- src/db.py (_get_pool function — current defaults, env var names)
- docs/ONBOARDING.md (if it exists — add pool config documentation)

### Build

Task A-1: Increase pool defaults in src/db.py:
- DB_POOL_MIN: 2 → 5
- DB_POOL_MAX: 20 → 50
- Add comment: "Tune via DB_POOL_MIN/DB_POOL_MAX env vars. 50 supports ~200 concurrent users."

Task A-2: Add pool exhaustion warning:
- In get_connection(), after getting a connection from the pool:
- Check pool utilization: if used > 80% of max, log a warning
- Pattern: `if _pool._used and len(_pool._used) > 0.8 * _pool.maxconn: logger.warning(...)`

Task A-3: Document in docs/ONBOARDING.md:
- Add "Database Pool Configuration" section
- List env vars: DB_POOL_MIN, DB_POOL_MAX, DB_CONNECT_TIMEOUT
- Explain when to increase (>50 concurrent users)

### Test
Write tests/test_pool_tuning.py:
- test_default_pool_min_is_5
- test_default_pool_max_is_50
- test_pool_config_from_env_vars (monkeypatch)

### Output Files
- scenarios-pending-review-qs9-t3-a.md
- CHANGELOG-qs9-t3-a.md

### Commit
feat: increase DB pool defaults (min=5, max=50) + exhaustion warnings (QS9-T3-A)
""")
```

---

### Agent B: Static Asset Caching

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Add Cache-Control headers for static assets

### File Ownership
- web/app.py (ONLY after_request hooks — do NOT touch other parts)

### Read First
- web/app.py (find existing after_request hooks, understand middleware)
- web/routes_misc.py (Cache-Control on /methodology etc — already done in QS8, don't duplicate)

### Build

Task B-1: Add after_request hook in web/app.py for /static/ paths:
```python
@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        # CSS and JS with content hash → immutable, long cache
        if request.path.endswith(('.css', '.js')):
            response.headers['Cache-Control'] = 'public, max-age=86400, stale-while-revalidate=604800'
        # Images and fonts → medium cache
        elif request.path.endswith(('.png', '.jpg', '.ico', '.woff2', '.svg')):
            response.headers['Cache-Control'] = 'public, max-age=604800'
        else:
            response.headers['Cache-Control'] = 'public, max-age=3600'
    return response
```

Task B-2: Do NOT set Cache-Control on HTML responses (dynamic content).

Task B-3: Verify existing Cache-Control on /methodology, /about-data, /demo is not duplicated.

### Test
Write tests/test_cache_headers.py:
- test_static_css_has_cache_control
- test_static_js_has_cache_control
- test_static_image_has_cache_control
- test_html_page_no_cache_control (verify / and /search don't get cached)

### Output Files
- scenarios-pending-review-qs9-t3-b.md
- CHANGELOG-qs9-t3-b.md

### Commit
feat: Cache-Control headers on static assets — CSS/JS 24h, images 7d (QS9-T3-B)
""")
```

---

### Agent C: Redis Rate Limiter

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Add Redis-backed rate limiter with in-memory fallback

### File Ownership
- web/helpers.py (rate limiter section ONLY — do NOT touch other functions)
- pyproject.toml (add redis dependency)

### Read First
- web/helpers.py (find _rate_buckets dict and any rate limiting functions)
- Look for: check_rate_limit, _rate_buckets, or similar

### Context
REDIS_URL is set on Railway (internal network only). For local dev, Redis is not available.
The rate limiter must work with OR without Redis:
- With REDIS_URL: use Redis INCR + EXPIRE (shared across Gunicorn workers)
- Without REDIS_URL: use current in-memory dict (existing behavior, per-worker)

### Build

Task C-1: Add redis to pyproject.toml dependencies:
```
redis>=5.0.0
fakeredis>=2.20.0  # dev dependency for tests
```

Task C-2: Create a Redis-backed rate limiter that falls back to in-memory:
```python
import os

_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            import redis
            _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
            try:
                _redis_client.ping()
            except Exception:
                _redis_client = None  # Redis unreachable, fall back
    return _redis_client

def check_rate_limit_redis(key: str, max_requests: int, window_seconds: int) -> bool:
    """Returns True if rate limit exceeded. Uses Redis if available, else in-memory."""
    r = _get_redis()
    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            count, _ = pipe.execute()
            return count > max_requests
        except Exception:
            pass  # Fall through to in-memory
    # In-memory fallback (existing behavior)
    return _check_rate_limit_memory(key, max_requests, window_seconds)
```

Task C-3: Replace existing rate limit calls to use the new function.
Keep backward compatibility — existing code should work unchanged.

### Test
Write tests/test_redis_rate_limiter.py:
- Use fakeredis for Redis tests (pip install fakeredis)
- test_redis_rate_limit_counts_requests
- test_redis_rate_limit_blocks_over_threshold
- test_redis_rate_limit_resets_after_window
- test_fallback_to_memory_when_no_redis (unset REDIS_URL)
- test_fallback_to_memory_when_redis_down (mock connection failure)

### Output Files
- scenarios-pending-review-qs9-t3-c.md
- CHANGELOG-qs9-t3-c.md

### Commit
feat: Redis-backed rate limiter with in-memory fallback (QS9-T3-C)
""")
```

---

### Agent D: Load Test Script + Scaling Docs

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Enhance load test script + create scaling documentation

### File Ownership
- scripts/load_test.py (enhance or create)
- docs/SCALING.md (NEW)

### Read First
- scripts/load_test.py (if it exists — understand current capabilities)
- src/db.py (pool configuration, env vars)
- web/app.py (understand Gunicorn worker model)
- web/helpers.py (rate limiting)

### Build

Task D-1: Create or enhance scripts/load_test.py:
```python
#!/usr/bin/env python3
"""Load test for sfpermits.ai — measures capacity under concurrent load.

Usage:
    python scripts/load_test.py --url https://sfpermits-ai-staging-production.up.railway.app --users 50 --duration 60
"""
# Use concurrent.futures.ThreadPoolExecutor
# Hit these endpoints: /, /search?q=market, /methodology, /health
# Measure: p50/p95/p99 response times, error rate, throughput (req/s)
# Report: summary table + per-endpoint breakdown
# Optional: --auth flag to test authenticated endpoints (/brief, /portfolio)
```

Task D-2: Create docs/SCALING.md:
```markdown
# Scaling Guide

## Current Capacity
- DB pool: min=5, max=50 connections
- Gunicorn workers: [check Procfile/railway.json]
- Rate limiting: Redis-backed when REDIS_URL set, per-worker otherwise
- Static assets: Cache-Control headers (24h CSS/JS, 7d images)
- Page cache: DB-backed, 30-min TTL, cron pre-compute every 15min

## Environment Variables
| Var | Default | Purpose |
|-----|---------|---------|
| DB_POOL_MIN | 5 | Minimum DB connections |
| DB_POOL_MAX | 50 | Maximum DB connections |
| DB_CONNECT_TIMEOUT | 10 | Connection timeout (seconds) |
| REDIS_URL | (none) | Redis for shared rate limiting |
| SODA_CB_THRESHOLD | 5 | Circuit breaker failure threshold |
| SODA_CB_TIMEOUT | 60 | Circuit breaker recovery (seconds) |

## Scaling Checklist for 5K Users
- [ ] DB pool max ≥ 50 (DB_POOL_MAX env var)
- [ ] Redis provisioned (REDIS_URL set on all services)
- [ ] Static assets cached (Cache-Control headers)
- [ ] Brief pre-compute running (cron every 15 min)
- [ ] SODA circuit breaker active
- [ ] CDN in front of Railway (Cloudflare recommended)
- [ ] Gunicorn workers = 2-4× CPU cores

## Bottlenecks (in order of impact)
1. Property report N+1 queries (FIXED in QS8 — batch queries)
2. DB connection pool exhaustion (MITIGATED — pool max 50)
3. SODA API latency (MITIGATED — circuit breaker + 15-min cache)
4. Rate limiter per-worker (FIXED — Redis-backed)
5. Static asset serving by Flask (MITIGATED — Cache-Control headers)
6. No CDN (OPEN — add Cloudflare for edge caching)
```

### Test
```bash
# Verify load test script parses
python -c "import scripts.load_test"
# Verify SCALING.md exists and has content
wc -l docs/SCALING.md
```

### Output Files
- scenarios-pending-review-qs9-t3-d.md
- CHANGELOG-qs9-t3-d.md

### Commit
feat: load test script + scaling documentation (QS9-T3-D)
""")
```

---

## Post-Agent: Merge + Push

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git merge <agent-a-branch> --no-edit
git merge <agent-b-branch> --no-edit
git merge <agent-c-branch> --no-edit
git merge <agent-d-branch> --no-edit
cat scenarios-pending-review-qs9-t3-*.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-qs9-t3-*.md >> CHANGELOG.md 2>/dev/null
git push origin main
```

## Report

```
T3 (Scaling) COMPLETE
  A: Pool tuning:           [PASS/FAIL] (min=5, max=50)
  B: Static asset caching:  [PASS/FAIL]
  C: Redis rate limiter:    [PASS/FAIL] (Redis connected: [yes/no])
  D: Load test + docs:      [PASS/FAIL]
  Pushed: [commit hash]
```
