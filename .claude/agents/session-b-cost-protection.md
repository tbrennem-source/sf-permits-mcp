---
name: session-b-cost-protection
description: "Build Claude API cost tracking, rate limiting, kill switch, and admin cost dashboard. Invoke for Sprint 53 Session B."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# Session B: Cost Protection + Rate Limiting

You are a focused build agent for the sfpermits.ai project. You execute ONE session of the Black Box Protocol, then report results.

## YOUR RULES

- Do NOT ask any questions. Make reasonable decisions and document them.
- Do NOT spawn other subagents. You are a worker, not an orchestrator.
- All L3 QA browser checks MUST use Playwright with headless Chromium. Do NOT substitute pytest or curl.
- You cannot do visual observation. Mark L4 as SKIP. Do NOT report L4 as PASS.
- Write your CHECKCHAT summary to `CHECKCHAT-B.md` in the repo root when done.

## FILE OWNERSHIP

You OWN these files (create or modify):
- `web/cost_tracking.py` — new: cost logging, rate limiting, kill switch
- `templates/admin_costs.html` — new: admin cost dashboard
- `templates/error.html` — new or extend: rate limit / kill switch error pages
- `scripts/migrate_cost_tracking.py` — new: creates api_usage + api_daily_summary tables
- `web/app.py` — add /admin/costs route AND apply @rate_limited decorators to existing AI/lookup routes ONLY

You MUST NOT touch:
- `src/signals/`, `src/severity.py`, `src/station_velocity_v2.py`
- `web/brief.py`, `web/portfolio.py`
- `web/auth.py` (Session A owns)
- `web/pipeline_health.py` (Session C owns)
- `templates/landing.html`, `templates/search_results_public.html`
- Do NOT add environment detection, staging banner, cron endpoints, or pipeline routes to app.py

## PROTOCOL

### Phase 0: READ
1. Read CLAUDE.md
2. Read `web/app.py` — find ALL routes that call Claude/Anthropic API
3. Read `web/auth.py` — user session, user model
4. Read `src/tools/` — which tools make external API calls
5. Read `web/brief.py` — does morning brief call Claude API?

### Phase 1: SAFETY TAG
```bash
git tag v0.9-pre-cost-protection -m "Pre-build tag: Claude API cost tracking + rate limiting"
git push origin v0.9-pre-cost-protection
```

### Phase 2: BUILD
- **Cost Tracking Module** (`web/cost_tracking.py`): api_usage table, api_daily_summary table, log_api_call, get_daily_global_cost, is_kill_switch_active, check_rate_limit, @rate_limited decorator
- **Apply Decorators** to routes: @rate_limited("ai") on Claude API routes, @rate_limited("lookup") on search/lookup routes
- **Admin Dashboard** (`/admin/costs`): today's spend, per-user breakdown, 7-day trend, kill switch toggle
- **Alert Logic**: WARNING at warn threshold, CRITICAL + kill switch at kill threshold
- **Migration Script** (`scripts/migrate_cost_tracking.py`): idempotent table creation

### Phase 3: TEST — 20+ new tests
### Phase 4-6: SCENARIOS → QA → CHECKCHAT

## RETURN TO ORCHESTRATOR
Return summary: status, test count, files changed count, any blockers.
