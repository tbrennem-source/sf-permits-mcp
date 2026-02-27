<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/sprint-76-intelligence.md and execute it" -->

# Sprint 76 — Intelligence v2

You are the orchestrator for Sprint 76. Spawn 4 parallel build agents, collect results, merge, test, push.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git tag pre-sprint-76
```

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
- Read design-spec.md FIRST before touching any templates.
- MERGE RULE: Do NOT merge to main. Commit to worktree branch only.
- CONFLICT RULE: Do NOT run git checkout <branch> -- <file>. Report conflicts as BLOCKED.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- TEST FIXUP EXCEPTION: If your code changes cause tests in files you don't own to fail, you MAY fix those tests. Limit fixes to assertion updates. Document in CHANGELOG.
- TEMPLATE RENDERING WARNING: If you add context processors or before_request hooks that depend on `request`, verify email templates still work: pytest tests/ -k "email" -v. Must handle has_request_context() == False.
- APPEND FILES (dual-write):
  * scenarios-pending-review-sprint-76-N.md (per-agent)
  * scenarios-pending-review.md (shared, append only)
  * CHANGELOG-sprint-76-N.md (per-agent)
- TELEMETRY: Use "Scope changes" (not "descoped"), "Waiting on" (not "blocked").
- Test after each task: pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q 2>&1 | tail -5
```

---

### Agent 76-1: Station Routing Sequence Model

**PHASE 1: READ**
- src/tools/estimate_timeline.py (full file — understand current model)
- src/station_velocity_v2.py (velocity data model, p50/p75/p90 per station)
- web/routes_api.py (API endpoint pattern)
- src/db.py (query patterns, BACKEND variable, placeholder style)

**PHASE 2: BUILD**

Task 76-1-1: Add estimate_sequence_timeline(permit_number) to src/tools/estimate_timeline.py
Task 76-1-2: Query addenda table for the permit's station sequence: SELECT DISTINCT station, MIN(arrive) as first_arrive FROM addenda WHERE application_number = ? GROUP BY station ORDER BY first_arrive
Task 76-1-3: For each station in sequence, look up p50 velocity from station_velocity_v2 table
Task 76-1-4: Sum sequential stations for total estimate. If stations overlap in time (parallel review), use max instead of sum for the overlapping period.
Task 76-1-5: Return structured result: {"permit_number": str, "stations": [{"station": str, "p50_days": float, "status": "done|pending|stalled"}], "total_estimate_days": float, "confidence": "high|medium|low"}
Task 76-1-6: Handle missing data: if no addenda → return None. If velocity data missing for a station → skip it with a note.
Task 76-1-7: GET /api/timeline/<permit_number> in web/routes_api.py — JSON response with the sequence timeline

**PHASE 3: TEST**
tests/test_sprint-76_1.py — 10+ tests: mock addenda data, station chaining logic, parallel detection, missing data fallback, API endpoint format, no addenda case

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-76-1.md (2 scenarios), CHANGELOG-sprint-76-1.md
Commit: "feat: station routing sequence model (Sprint 76-1)"

**File Ownership:**
Own: src/tools/estimate_timeline.py (add function), web/routes_api.py (add route), tests/test_sprint-76_1.py (NEW)

---

### Agent 76-2: Cost Tracking Middleware Wiring

**PHASE 1: READ**
- web/cost_tracking.py (FULL FILE — log_api_call, estimate_cost_usd, check_rate_limit, rate_limited decorator, is_kill_switch_active, set_kill_switch)
- web/app.py lines 980-1110 (before/after request hooks)
- web/helpers.py lines 161-174 (_rate_limited_ai, _rate_limited_plans wrappers)
- web/routes_public.py (find AI-calling routes — look for Claude API calls or _rate_limited decorators)
- web/routes_property.py (same)
- web/routes_cron.py (cron endpoint pattern for new aggregation endpoint)

**PHASE 2: BUILD**

Task 76-2-1: Add after_request hook in web/app.py: if hasattr(g, 'api_usage') and g.api_usage, call log_api_call() from cost_tracking. try/except, never fail the response.
Task 76-2-2: Audit web/routes_public.py — find routes that call Claude API but lack @_rate_limited_ai. Apply the decorator. (Check /analyze-preview, /ask, /lookup/intel-preview)
Task 76-2-3: Audit web/routes_property.py — same audit. Apply decorator where missing.
Task 76-2-4: Daily aggregation function in web/cost_tracking.py: aggregate_daily_usage() — INSERT INTO api_daily_summary SELECT date, SUM(cost_usd), COUNT(*) FROM api_usage WHERE called_at >= yesterday GROUP BY date. Handle missing table gracefully.
Task 76-2-5: POST /cron/aggregate-api-usage in web/routes_cron.py — CRON_SECRET auth, calls aggregate_daily_usage()
Task 76-2-6: Kill switch in before_request: if is_kill_switch_active() and request is to an AI route, return 503. Define AI routes by path prefix (/ask, /analyze, /lookup/intel-preview).
Task 76-2-7: Verify POST /admin/costs/kill-switch exists in routes_admin.py. If not, add it.

**PHASE 3: TEST**
tests/test_sprint-76_2.py — 10+ tests: after_request hook logs usage, rate limiter blocks excess, aggregation produces totals, kill switch returns 503, cron endpoint requires auth

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-76-2.md (2 scenarios), CHANGELOG-sprint-76-2.md
Commit: "feat: cost tracking middleware wiring (Sprint 76-2)"

**File Ownership:**
Own: web/app.py (add after_request + before_request hooks), web/cost_tracking.py (add aggregation), web/routes_public.py (add decorators), web/routes_property.py (add decorators), web/routes_cron.py (add endpoint), tests/test_sprint-76_2.py (NEW)

---

### Agent 76-3: Severity UI Integration + Caching

**PHASE 1: READ**
- design-spec.md (signal colors for badges)
- src/severity.py (score_permit function, SeverityResult dataclass)
- web/routes_search.py (search result enrichment pattern)
- scripts/release.py (DDL pattern)
- web/app.py EXPECTED_TABLES
- src/db.py init_user_schema

**PHASE 2: BUILD**

Task 76-3-1: severity_cache DDL in scripts/release.py (# === Sprint 76-3 ===):
```sql
CREATE TABLE IF NOT EXISTS severity_cache (
    permit_number TEXT PRIMARY KEY,
    score INTEGER NOT NULL,
    tier TEXT NOT NULL,
    drivers JSONB,
    computed_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_severity_cache_tier ON severity_cache (tier);
```

Task 76-3-2: Add "severity_cache" to EXPECTED_TABLES in web/app.py
Task 76-3-3: DuckDB DDL in src/db.py init_user_schema
Task 76-3-4: Create web/templates/fragments/severity_badge.html:
```html
{% if severity_tier %}
<span class="severity-badge severity-{{ severity_tier|lower }}">{{ severity_tier }}</span>
{% endif %}
```
Add CSS in the fragment: .severity-badge base + .severity-critical (--signal-red), .severity-high (--signal-amber), .severity-medium (mix), .severity-low (--signal-blue), .severity-green (--signal-green)

Task 76-3-5: In web/routes_search.py, after fetching permits in search results: query severity_cache for each permit. Cache miss → compute with score_permit(), INSERT into cache.
Task 76-3-6: Pass severity data to template context so severity_badge.html can render
Task 76-3-7: POST /cron/refresh-severity-cache in web/routes_cron.py — CRON_SECRET auth, bulk-score all active permits (status in filed/issued/approved), upsert cache

**PHASE 3: TEST**
tests/test_sprint-76_3.py — 10+ tests: DDL, EXPECTED_TABLES, cache hit, cache miss computes, badge renders, cron refresh populates, search includes severity

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-76-3.md (2 scenarios), CHANGELOG-sprint-76-3.md
Commit: "feat: severity UI badges + cache (Sprint 76-3)"

**File Ownership:**
Own: scripts/release.py (append section), web/app.py (1 line EXPECTED_TABLES), src/db.py (init_user_schema append), web/routes_search.py (add enrichment), web/routes_cron.py (add endpoint), web/templates/fragments/severity_badge.html (NEW), tests/test_sprint-76_3.py (NEW)

---

### Agent 76-4: Template Migration Batch 2 (5 Admin Pages)

**PHASE 1: READ**
- design-spec.md
- web/templates/fragments/head_obsidian.html
- web/static/design-system.css
- web/templates/admin_ops.html (first target — understand current structure)

**PHASE 2: BUILD**

Migrate these 5 admin templates:
1. web/templates/admin_ops.html
2. web/templates/admin_feedback.html
3. web/templates/admin_metrics.html
4. web/templates/admin_costs.html
5. web/templates/admin_activity.html

Same migration pattern as QS7-3:
- Add head_obsidian.html include + body.obsidian class
- Wrap content in .obs-container
- Wrap sections in .glass-card
- Preserve all tab navigation, data tables, HTMX, Jinja logic
- Data tables: header row in --text-secondary uppercase, rows with hover --bg-elevated
- Status badges: use signal colors from design-spec
- Admin-specific: keep tab hash routing (#pipeline, #quality, etc.)

**PHASE 3: TEST**
tests/test_sprint-76_4.py — 10+ tests: each admin route returns 200 with admin auth, response contains obsidian markers

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-76-4.md (1 scenario), CHANGELOG-sprint-76-4.md
Commit: "feat: Obsidian migration — 5 admin templates (Sprint 76-4)"

**File Ownership:**
Own: 5 admin templates listed above, tests/test_sprint-76_4.py (NEW)

---

## Post-Agent Merge (Orchestrator)

1. Collect results from all 4 agents
2. Merge in this order (app.py dependency):
   a. 76-1 FIRST (estimate_timeline.py + routes_api.py — isolated files)
   b. 76-4 SECOND (admin templates — isolated files)
   c. 76-3 THIRD (severity cache — simpler app.py change: just EXPECTED_TABLES)
   d. 76-2 LAST (cost tracking — most invasive app.py changes: before/after_request hooks)
3. Resolve conflicts:
   - EXPECTED_TABLES: add "severity_cache" (Sprint 74 already added "request_metrics")
   - release.py: keep both Sprint 76-3 and Sprint 74-1 labeled sections
   - src/db.py: keep Sprint 74-4 pool changes + Sprint 76-3 severity_cache DDL
   - web/app.py: keep Sprint 74-1 after_request metric logging + Sprint 76-2 cost tracking hooks (different functions)
   - web/routes_cron.py: 76-2 and 76-3 both add endpoints — non-overlapping, just keep both
4. Run: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q`
5. `git pull origin main` (get Sprint 74+75), then `git push origin main`
6. Concatenate changelogs + scenarios
7. Report summary table

## Push Order
Sprint 76 pushes THIRD. Must pull Sprint 74+75 first.
