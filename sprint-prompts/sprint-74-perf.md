<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/sprint-74-perf.md and execute it" -->

# Sprint 74 — Performance + Observability

You are the orchestrator for Sprint 74. Spawn 4 parallel build agents, collect results, merge, test, push.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git tag pre-sprint-74
```

Verify HEAD: `git log --oneline -3`

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
- Read design-spec.md FIRST if touching any templates.
- MERGE RULE: Do NOT merge to main. Commit to worktree branch only.
- CONFLICT RULE: Do NOT run git checkout <branch> -- <file>. Report conflicts as BLOCKED.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- TEST FIXUP EXCEPTION: If your code changes cause tests in files you don't own to fail, you MAY fix those tests. Limit fixes to assertion updates that reflect your intentional changes. Document cross-file test fixes in CHANGELOG.
- TEMPLATE RENDERING WARNING: If you add context processors or before_request hooks that depend on `request`, verify email templates still work: pytest tests/ -k "email" -v. Email templates render outside request context. Your code must handle has_request_context() == False gracefully.
- APPEND FILES (dual-write for stop hook compliance):
  * scenarios-pending-review-sprint-74-N.md (per-agent, for merge safety)
  * scenarios-pending-review.md (shared, append only — do NOT delete existing content)
  * CHANGELOG-sprint-74-N.md (per-agent)
- TELEMETRY: Use "Scope changes" (not "descoped"), "Waiting on" (not "blocked") in your CHECKCHAT table to avoid stop hook false positives.
- Test after each task: pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q 2>&1 | tail -5
```

---

### Agent 74-1: Request Metrics + /admin/perf Dashboard

**PHASE 1: READ**
- design-spec.md
- web/app.py lines 128-136 (EXPECTED_TABLES), lines 1097-1110 (_slow_request_log)
- scripts/release.py (DDL pattern — look for labeled sections)
- src/db.py init_user_schema (DuckDB DDL pattern)
- web/routes_admin.py (admin route pattern, @admin_required decorator)
- web/templates/admin_ops.html (admin template reference)

**PHASE 2: BUILD**

Task 74-1-1: request_metrics DDL in scripts/release.py
```
# === Sprint 74-1: request_metrics ===
CREATE TABLE IF NOT EXISTS request_metrics (
    id SERIAL PRIMARY KEY,
    path TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'GET',
    status_code INTEGER,
    duration_ms FLOAT NOT NULL,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reqmetrics_path_ts ON request_metrics (path, recorded_at);
```

Task 74-1-2: Add "request_metrics" to EXPECTED_TABLES in web/app.py

Task 74-1-3: DuckDB DDL in src/db.py init_user_schema (TIMESTAMP not TIMESTAMPTZ, INTEGER PK not SERIAL)

Task 74-1-4: Enhance after_request in web/app.py — after _slow_request_log, add: if duration > 0.2s OR random.random() < 0.1, INSERT into request_metrics via execute_write. Wrap in try/except — never fail the response.

Task 74-1-5: GET /admin/perf route in web/routes_admin.py with @admin_required. Query: top 10 slowest (avg + p95), volume by path (24h), overall p50/p95/p99. Render admin_perf.html.

Task 74-1-6: Create web/templates/admin_perf.html — Obsidian design: {% include "fragments/head_obsidian.html" %}, body class="obsidian", content in .obs-container, sections in .glass-card, stat-blocks for percentiles, data table for endpoints.

Task 74-1-7: Grep-verify: grep -c "head_obsidian\|obsidian\|obs-container\|glass-card" web/templates/admin_perf.html >= 4

**PHASE 3: TEST**
tests/test_sprint-74_1.py — 10+ tests: DDL created, EXPECTED_TABLES includes it, metric insert, admin route 200, non-admin 403, after_request records metrics.

**PHASE 4: SCENARIOS**
Write scenarios-pending-review-sprint-74-1.md (1-2 scenarios)

**PHASE 5: QA**
CLI-only QA (no browser needed): verify table creation, admin route auth, metric recording.

**PHASE 6: CHECKCHAT**
Commit: "feat: request metrics table + /admin/perf dashboard (Sprint 74-1)"
CHANGELOG-sprint-74-1.md

**File Ownership:**
Own: scripts/release.py (append section), web/app.py (EXPECTED_TABLES + after_request), src/db.py (init_user_schema append), web/routes_admin.py (add route), web/templates/admin_perf.html (NEW), tests/test_sprint-74_1.py (NEW)

---

### Agent 74-2: Load Test Script

**PHASE 1: READ**
- scripts/ directory (pattern reference)

**PHASE 2: BUILD**

Task 74-2-1: Create scripts/load_test.py — concurrent.futures.ThreadPoolExecutor + httpx (already a dep, NO new deps)
Task 74-2-2: CLI: --url URL, --concurrency 10, --duration 30, --scenario all|health|search|demo|landing|sitemap
Task 74-2-3: Scenarios: health (GET /health), search (GET /search?q=valencia), demo (GET /demo), landing (GET /), sitemap (GET /sitemap.xml)
Task 74-2-4: Per-scenario JSON output: p50, p95, p99, max, min, mean, error_count, requests_per_second
Task 74-2-5: Human-readable summary table to stderr
Task 74-2-6: Save results to load-test-results.json

**PHASE 3: TEST**
tests/test_sprint-74_2.py — 8+ tests: config parsing, scenario registry, result aggregation, JSON format (mock httpx, no real HTTP)

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-74-2.md, CHANGELOG-sprint-74-2.md
Commit: "feat: load test script (Sprint 74-2)"

**File Ownership:**
Own: scripts/load_test.py (NEW), tests/test_sprint-74_2.py (NEW). ZERO shared files.

---

### Agent 74-3: Security Audit Tooling

**PHASE 1: READ**
- .github/workflows/ (existing workflow pattern)
- pyproject.toml (current deps)

**PHASE 2: BUILD**

Task 74-3-1: scripts/security_audit.py — subprocess bandit + pip-audit, parse JSON, combined markdown report, exit 1 on HIGH, handle missing tools gracefully
Task 74-3-2: .bandit config (exclude tests, skip B101)
Task 74-3-3: .github/workflows/security.yml — weekly cron Sunday 6am UTC + push to main, continue-on-error, upload report artifact

**PHASE 3: TEST**
tests/test_sprint-74_3.py — 8+ tests: script imports, config exists, YAML valid, report generation with mock subprocess, exit code logic

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-74-3.md, CHANGELOG-sprint-74-3.md
Commit: "feat: security audit tooling (Sprint 74-3)"

**File Ownership:**
Own: scripts/security_audit.py (NEW), .bandit (NEW), .github/workflows/security.yml (NEW), tests/test_sprint-74_3.py (NEW). ZERO shared files.

---

### Agent 74-4: Connection Pool Tuning

**PHASE 1: READ**
- src/db.py (FULL FILE — _get_pool line ~37, get_pool_stats line ~53, _PooledConnection, get_connection)

**PHASE 2: BUILD**

Task 74-4-1: In _get_pool(): read DB_POOL_MIN from env (default 2)
Task 74-4-2: DB_CONNECT_TIMEOUT env var (default 10)
Task 74-4-3: DB_STATEMENT_TIMEOUT env var (default "30s") — set on new connections
Task 74-4-4: Pool exhaustion logging: wrap _pool.getconn() in get_connection(), on PoolError log WARNING with pool stats
Task 74-4-5: get_pool_health() → {"healthy": bool, "min": int, "max": int, "in_use": int, "available": int}
Task 74-4-6: Enhance get_pool_stats() to include health dict

**PHASE 3: TEST**
tests/test_sprint-74_4.py — 8+ tests: env var config (monkeypatch), health function, stats includes health, exhaustion warning
Run FULL test suite — db.py is critical.

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-74-4.md, CHANGELOG-sprint-74-4.md
Commit: "feat: pool tuning + health checks (Sprint 74-4)"

**File Ownership:**
Own: src/db.py (modify pool setup + add functions), tests/test_sprint-74_4.py (NEW)

---

## Post-Agent Merge (Orchestrator)

1. Collect results from all 4 agents
2. Merge in this order (db.py dependency):
   a. 74-4 FIRST (pool tuning — foundational db.py changes)
   b. 74-2 and 74-3 (new files only — no conflicts)
   c. 74-1 LAST (appends to db.py + app.py that 74-4 modified)
3. Resolve any EXPECTED_TABLES conflict (add request_metrics)
4. Run: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q`
5. If pass: `git push origin main`
6. Concatenate: `cat CHANGELOG-sprint-74-*.md >> CHANGELOG.md && cat scenarios-pending-review-sprint-74-*.md >> scenarios-pending-review.md`
7. Report summary table:
```
| Agent | Tests | Files | Status |
|-------|-------|-------|--------|
| 74-1  |       |       |        |
| 74-2  |       |       |        |
| 74-3  |       |       |        |
| 74-4  |       |       |        |
```

## Push Order
Sprint 74 pushes FIRST (no pull needed).
