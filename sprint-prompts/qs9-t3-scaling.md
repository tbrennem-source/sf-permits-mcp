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

REDIS_URL is set on all Railway services (staging, prod, cron worker). Internal URL — only reachable from Railway. For local testing, use `fakeredis` package.

## File Ownership

| Agent | Files Owned |
|-------|-------------|
| A | `src/db.py`, `docs/ONBOARDING.md` |
| B | `web/app.py` (after_request hooks ONLY) |
| C | `web/helpers.py` (rate limiter section ONLY), `pyproject.toml` |
| D | `scripts/load_test.py`, `docs/SCALING.md` (NEW) |

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent A: DB Pool Tuning

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
- docs/ONBOARDING.md (add pool config docs)

### Build
1. DB_POOL_MIN: 2 → 5, DB_POOL_MAX: 20 → 50
2. Add pool exhaustion warning: log when >80% utilized
3. Document all pool env vars in ONBOARDING.md

### Test
Write tests/test_pool_tuning.py:
- test_default_pool_min_is_5
- test_default_pool_max_is_50
- test_pool_config_from_env_vars

### Scenarios
Write 2 scenarios to scenarios-pending-review-qs9-t3-a.md:
- Scenario: App logs warning when DB pool nears exhaustion
- Scenario: Admin increases pool size via env var without code change

### CHECKCHAT
Summary: defaults changed, warning added, docs updated, tests passing. Visual QA Checklist: N/A.

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
- web/app.py (ONLY after_request hooks)

### Read First
- web/app.py (existing after_request hooks)
- web/routes_misc.py (existing Cache-Control on /methodology etc — don't duplicate)

### Build
Add after_request hook for /static/ paths:
- CSS/JS: Cache-Control: public, max-age=86400, stale-while-revalidate=604800
- Images/fonts: Cache-Control: public, max-age=604800
- Do NOT cache HTML responses

### Test
Write tests/test_cache_headers.py:
- test_static_css_has_cache_control
- test_static_js_has_cache_control
- test_html_page_no_cache_control

### Scenarios
Write 2 scenarios to scenarios-pending-review-qs9-t3-b.md:
- Scenario: Browser caches CSS for 24 hours after first load
- Scenario: HTML pages are never served from browser cache

### CHECKCHAT
Summary: headers added, tests passing. Visual QA Checklist: N/A — headers only, no visual change.

### Output Files
- scenarios-pending-review-qs9-t3-b.md
- CHANGELOG-qs9-t3-b.md

### Commit
feat: Cache-Control headers on static assets (QS9-T3-B)
""")
```

---

### Agent C: Redis Rate Limiter

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Redis-backed rate limiter with in-memory fallback

### File Ownership
- web/helpers.py (rate limiter section ONLY)
- pyproject.toml (add redis + fakeredis deps)

### Read First
- web/helpers.py (find _rate_buckets and rate limiting functions)

### Context
REDIS_URL set on Railway (internal only). Must work WITH and WITHOUT Redis.

### Build
1. Add redis>=5.0.0 and fakeredis>=2.20.0 to pyproject.toml
2. Create Redis-backed rate limiter:
   - If REDIS_URL set: use Redis INCR + EXPIRE
   - If not set or unreachable: fall back to in-memory dict
3. Replace existing rate limit calls with new function

### Test
Write tests/test_redis_rate_limiter.py (use fakeredis):
- test_redis_rate_limit_counts_requests
- test_redis_rate_limit_blocks_over_threshold
- test_redis_rate_limit_resets_after_window
- test_fallback_to_memory_when_no_redis
- test_fallback_to_memory_when_redis_down

### Scenarios
Write 3 scenarios to scenarios-pending-review-qs9-t3-c.md:
- Scenario: Rate limit enforced consistently across multiple Gunicorn workers
- Scenario: Rate limiter degrades gracefully when Redis is down
- Scenario: Rate limit resets after time window expires

### CHECKCHAT
Summary: Redis integration done, fallback works, tests passing. Visual QA Checklist: N/A.

### Output Files
- scenarios-pending-review-qs9-t3-c.md
- CHANGELOG-qs9-t3-c.md

### Commit
feat: Redis-backed rate limiter with in-memory fallback (QS9-T3-C)
""")
```

---

### Agent D: Load Test + Scaling Docs

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Load test script + scaling documentation

### File Ownership
- scripts/load_test.py (enhance or create)
- docs/SCALING.md (NEW)

### Read First
- scripts/load_test.py (if exists)
- src/db.py (pool config)
- web/app.py (worker model)

### Build
1. Create/enhance scripts/load_test.py:
   - 50 concurrent users, 60s duration
   - Hit /, /search?q=market, /methodology, /health
   - Report p50/p95/p99, error rate, throughput
2. Create docs/SCALING.md:
   - Current capacity, env vars, bottlenecks, scaling checklist for 5K users

### Test
python -c "import scripts.load_test"
wc -l docs/SCALING.md

### Scenarios
Write 2 scenarios to scenarios-pending-review-qs9-t3-d.md:
- Scenario: Load test identifies bottleneck before it hits production users
- Scenario: New developer finds scaling guide and configures pool size

### CHECKCHAT
Summary: load test created, SCALING.md written. Visual QA Checklist: N/A.

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
  A: Pool tuning:           [PASS/FAIL]
  B: Static asset caching:  [PASS/FAIL]
  C: Redis rate limiter:    [PASS/FAIL]
  D: Load test + docs:      [PASS/FAIL]
  Scenarios: [N] across 4 files
  Pushed: [commit hash]
```
