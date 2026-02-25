# Sprint 53.B — Land What's Built

Read `specs/sprint53b-prod-verification-handoff.md` from chief-brain-state for full context.

You are the Sprint 53.B orchestrator. This is a VERIFICATION sprint — no new features. Your job is to make everything Sprint 52+53 shipped actually work in production, then prove it.

**Prod:** https://sfpermits-ai-production.up.railway.app
**Staging:** https://sfpermits-ai-staging-production.up.railway.app
**TEST_LOGIN_SECRET (staging):** Read from /tmp/test_login_secret.txt

## RULES
```
AUTONOMY RULE: Do NOT ask the user any questions. Make reasonable decisions and document them.
PLAYWRIGHT RULE: All browser checks MUST use Playwright with headless Chromium.
L4 RULE: You cannot do visual observation. Mark L4 as SKIP. Do NOT report L4 as PASS.
VENV RULE: Always `source .venv/bin/activate` before any python/pytest command.
TIMEOUT RULE: pytest-timeout is NOT installed. Do not use --timeout flag.
```

## PHASE 0: DIAGNOSTIC (you, the orchestrator, do this — no subagents)

Before spawning anything, assess the current state:

1. Read CLAUDE.md, scripts/run_prod_migrations.py, scripts/migrate_signals.py, web/cost_tracking.py, web/pipeline_health.py
2. Read web/email_brief.py — find the render_template call, confirm pipeline_health is missing from kwargs
3. Read scripts/nightly_changes.py — find where staleness_warnings are generated, confirm data_as_of age is NOT checked
4. Read .github/workflows/ — find nightly cron workflow, confirm /cron/signals and /cron/velocity-refresh are NOT configured
5. Check prod health: `curl -s https://sfpermits-ai-production.up.railway.app/health`
6. Use sfpermits MCP `run_query` tool to check prod state:
   - `SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('signal_types','permit_signals','property_signals','property_health','api_usage','api_daily_summary')`
   - `SELECT MAX(finish_date)::date, MAX(arrive)::date, MAX(data_as_of)::date FROM addenda`
   - `SELECT * FROM cron_log ORDER BY started_at DESC LIMIT 10`
   - `SELECT COUNT(*), MAX(baseline_date) FROM station_velocity`

Write a DIAGNOSTIC-53B.md with all findings before proceeding.

## PHASE 1: MIGRATIONS (you, sequential — must complete before agents spawn)

Run prod migrations. You CANNOT connect to Railway Postgres directly — it's internal-only. Options:
1. Try: `railway run python scripts/run_prod_migrations.py` (if Railway CLI is linked to prod service)
2. Try: Use sfpermits MCP `run_query` tool — but it's SELECT-only, won't work for DDL
3. Fallback: Create a one-time `POST /cron/run-migrations` endpoint in web/app.py (gated on CRON_SECRET), deploy, then curl it. Remove the endpoint after.

After migrations, verify via MCP run_query:
- `SELECT COUNT(*) FROM signal_types` → should be >0 (seeded)
- `SELECT COUNT(*) FROM api_usage` → should be 0 (empty, table exists)
- `SELECT column_name FROM information_schema.columns WHERE table_name='cron_log' AND column_name IN ('duration_seconds','records_processed')`

## PHASE 2: PARALLEL BUILD AGENTS (3 agents, worktree isolation)

After migrations are confirmed, spawn 3 fix agents in parallel:

### Agent FIX-BRIEF: Pipeline health in morning brief email
**Files owned:** web/email_brief.py, web/templates/brief_email.html
**Task:**
- Add `pipeline_health=brief_data.get("pipeline_health"),` to the render_template kwargs in email_brief.py
- Add a conditional alert section to brief_email.html: if pipeline_health.status is "warn" or "critical", show a yellow/red banner ABOVE the "What Changed" section with the issues list
- If status is "ok", show nothing (no clutter)
- Write 2 tests: one verifying pipeline_health renders when warn, one verifying it's hidden when ok
- Commit to worktree branch

### Agent FIX-STALENESS: data_as_of age check in nightly script
**Files owned:** scripts/nightly_changes.py, tests/test_nightly_hardening.py
**Task:**
- In scripts/nightly_changes.py, AFTER the addenda fetch step, add:
  ```python
  # Check data_as_of freshness (catches stale-but-nonzero data)
  max_dao = query_one("SELECT MAX(data_as_of)::date FROM addenda")
  if max_dao and max_dao[0]:
      days_old = (date.today() - max_dao[0]).days
      if days_old > 3:
          staleness_warnings.append(f"Addenda data_as_of is {days_old} days stale (last: {max_dao[0]})")
  ```
- Add test in test_nightly_hardening.py: mock a stale data_as_of, verify warning is generated
- Commit to worktree branch

### Agent FIX-CRON: GitHub Actions nightly alerting + endpoint wiring
**Files owned:** .github/workflows/nightly-cron.yml (or equivalent), .github/workflows/ci.yml
**Task:**
- Find the nightly cron workflow file
- Add /cron/signals and /cron/velocity-refresh calls in correct order (after /cron/nightly, before /cron/send-briefs)
- Add Telegram failure notification step (same pattern as CI workflow)
- Commit to worktree branch

## PHASE 3: MERGE + TEST

After all 3 agents complete:
1. File ownership audit — verify no overlaps
2. Merge FIX-BRIEF → FIX-STALENESS → FIX-CRON sequentially
3. Run `pytest tests/ -x -q` after final merge
4. Push to main → Railway auto-deploys prod + staging

Wait ~2 min for deploy, verify both health endpoints return 200.

## PHASE 4: PARALLEL QA AGENTS (5 agents against prod + staging)

Spawn all 5 in parallel after deploy is confirmed healthy:

### Agent QA-PROD-PUBLIC: Prod public routes
**Target:** https://sfpermits-ai-production.up.railway.app
**Screenshots:** qa-results/53b-prod/public/
- GET / → 200, contains "sfpermits"
- GET /health → 200, JSON with status: "ok"
- GET /search?q=75+Robin+Hood+Dr → 200, contains results
- GET /auth/login → 200, contains login form
- Verify NO staging banner on any prod page

### Agent QA-PROD-ADMIN: Prod admin routes (verify migrations landed)
**Target:** https://sfpermits-ai-production.up.railway.app
**Auth:** This is PROD — TESTING is NOT set. Use magic link if possible, or skip auth-dependent checks and document why.
**Screenshots:** qa-results/53b-prod/admin/
- GET /cron/pipeline-health → 200, JSON with health checks
- Verify via MCP run_query: signal_types table has rows
- Verify via MCP run_query: api_usage table exists (0 rows OK)
- Verify via MCP run_query: addenda MAX(data_as_of) is recent
- Verify via MCP run_query: station_velocity has rows + recent baseline_date

### Agent QA-STAGING: Staging full check
**Target:** https://sfpermits-ai-staging-production.up.railway.app
**TEST_LOGIN_SECRET:** Read from /tmp/test_login_secret.txt
**Screenshots:** qa-results/53b-staging/
- POST /auth/test-login as admin → 200
- GET / → staging banner visible
- GET /admin/costs → renders (chart may be empty)
- GET /admin/pipeline → renders with health check cards
- GET /account → shows logged-in user
- POST /auth/test-login as homeowner → 200, verify is_admin=false (bug fix from Sprint 53)
- Clean stuck cron jobs: identify via MCP run_query, update to failed

### Agent QA-MOBILE: Both environments at 375px
**Targets:** Both prod and staging URLs
**Screenshots:** qa-results/53b-mobile/
- 6 pages per environment at 375x812: /, /search?q=Mission, /auth/login, /account (staging only), /admin/costs (staging only), /brief (staging only)
- Per page: screenshot, check `document.body.scrollWidth <= window.innerWidth`, check mobile.css loaded

### Agent QA-SAFETY: Prod safety verification
**Target:** https://sfpermits-ai-production.up.railway.app
**Screenshots:** qa-results/53b-safety/
- POST /auth/test-login on PROD → must return 404 (TESTING not set)
- Verify no staging banner on prod homepage
- Verify /admin/* routes return 403 or redirect for unauthenticated users
- Verify CRON_SECRET is required: GET /cron/pipeline-health without auth → 401/403

## PHASE 5: REPORT

Write `SPRINT-53B-REPORT.md` combining:
- Diagnostic findings (Phase 0)
- Migration results (Phase 1)
- Fix agent results (Phase 2)
- QA results from all 5 agents (Phase 4)

Format:
```
| Agent | Target | Checks | Passed | Failed |
|-------|--------|--------|--------|--------|
| QA-PROD-PUBLIC | prod | X | Y | Z |
| QA-PROD-ADMIN | prod | X | Y | Z |
| QA-STAGING | staging | X | Y | Z |
| QA-MOBILE | both | X | Y | Z |
| QA-SAFETY | prod | X | Y | Z |
```

## PHASE 6: CHECKCHAT → CHECKCHAT-53B.md

Include all standard CHECKCHAT sections plus:

### Sprint Close Gate Assessment
- [ ] All migrations verified on prod (signal tables, cost tables, cron_log columns)
- [ ] Cron endpoints configured (/cron/signals, /cron/velocity-refresh)
- [ ] Addenda data freshness confirmed
- [ ] Observability fixes deployed (brief email, staleness check, Telegram alert)
- [ ] prodRelay PASSED on prod
- [ ] Staging verified
- [ ] Safety checks PASSED (no test-login on prod, no staging banner on prod)
- [ ] PUSH — no HOLD required

### DeskRelay HANDOFF — Stage 2
List specific visual checks for DeskCC with screenshot paths and pass criteria. Include:
1. /admin/pipeline on prod — health cards, cron history
2. /admin/costs on prod — cost chart, kill switch panel
3. /admin/ops on prod — all 6 tabs load
4. Landing page on prod mobile — no overflow, search usable
5. /search?q=75+Robin+Hood+Dr on prod — intel panel, severity badges
6. Staging banner on staging — yellow, visible
7. No staging banner on prod — confirmed absent

### Scenarios
Append to scenarios-pending-review.md:
- "When addenda data_as_of is >3 days old, morning brief email shows pipeline health warning"
- "When nightly cron fails, Tim receives Telegram notification within 5 minutes"
- "When /cron/signals runs on prod, signal_types are seeded and permit_signals computed"

Push to chief via chief_add_note with session summary.

## AGENT SUMMARY

| Phase | Agents | Parallel? | Purpose |
|-------|--------|-----------|---------|
| 0 Diagnostic | 0 (orchestrator) | — | Assess current state |
| 1 Migrations | 0 (orchestrator) | — | Sequential, must complete first |
| 2 Fixes | 3 (FIX-BRIEF, FIX-STALENESS, FIX-CRON) | Yes | Observability fixes |
| 3 Merge | 0 (orchestrator) | — | Merge + test + push |
| 4 QA | 5 (PROD-PUBLIC, PROD-ADMIN, STAGING, MOBILE, SAFETY) | Yes | Verify everything |
| 5-6 Report | 0 (orchestrator) | — | Assemble + CHECKCHAT |
| **Total** | **8 subagents** | | |
