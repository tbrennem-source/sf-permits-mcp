# Sprint 53B Report — Land What's Built

**Date:** 2026-02-24
**Type:** Verification sprint (no new features)
**Orchestrator:** Claude Opus 4.6

---

## Diagnostic Findings (Phase 0)

| Item | Status Before | Action Needed |
|------|--------------|---------------|
| Signal tables (4) | NOT on prod | Run migration |
| Cost tracking tables (2) | NOT on prod | Run migration |
| Addenda data_as_of | 1 day old (fresh) | None |
| Station velocity | 210 rows, baseline 2026-02-24 | None |
| Pipeline health in brief email | NOT wired | FIX-BRIEF agent |
| data_as_of age check in nightly | NOT implemented | FIX-STALENESS agent |
| /cron/signals in workflow | Endpoint exists, not wired | FIX-CRON agent |
| /cron/velocity-refresh in workflow | Endpoint exists, not wired | FIX-CRON agent |
| Telegram alerts in nightly-cron | Missing | FIX-CRON agent |
| cron_log stuck job (log_id 14) | Running since 2/22 | Noted for cleanup |
| cron_log duration_seconds column | No migration exists | BLOCKED |

## Migration Results (Phase 1)

Created temporary `POST /cron/run-migrations` endpoint (MIGRATION_KEY auth), deployed, executed, removed.

| Migration | Result | Detail |
|-----------|--------|--------|
| Signal tables (migrate_signals.py) | OK | 4 tables created, 13 signal types seeded |
| Cost tracking (migrate_cost_tracking.py) | OK | 2 tables created (api_usage, api_daily_summary) |

**Verification via MCP:**
- `signal_types`: 13 rows
- `api_usage`: 0 rows (table exists, empty as expected)
- `information_schema`: 6/6 tables confirmed

## Fix Agent Results (Phase 2)

### FIX-BRIEF (pipeline health in morning brief email)
- **Files:** web/email_brief.py, web/templates/brief_email.html, tests/test_brief_pipeline_health.py
- **Changes:** Added `get_pipeline_health_brief()` call in `render_brief_email()`, added conditional alert banner (yellow for warn, red for critical) in email template above "What Changed" section
- **Tests:** 2 new tests passing (warn renders, ok hidden)

### FIX-STALENESS (data_as_of age check)
- **Files:** scripts/nightly_changes.py, tests/test_nightly_hardening.py
- **Changes:** Added `MAX(data_as_of)::date FROM addenda` freshness check after existing staleness checks. Warns if >3 days stale.
- **Tests:** 2 new tests passing (stale triggers warning, fresh does not)

### FIX-CRON (GitHub Actions wiring + Telegram)
- **Files:** .github/workflows/nightly-cron.yml
- **Changes:** Added `/cron/signals` and `/cron/velocity-refresh` calls between nightly sync and RAG ingest. Added Telegram failure notification step.
- **New workflow order:** nightly -> signals -> velocity -> RAG -> briefs -> Telegram (on failure)

### Merge + Test
- File ownership audit: no overlaps across 3 agents
- Merge order: FIX-BRIEF -> FIX-STALENESS -> FIX-CRON (all clean, no conflicts)
- **pytest: 1705 passed, 20 skipped, 0 failures**
- Pushed to main, Railway auto-deploy succeeded for both prod and staging

## QA Results (Phase 4)

| Agent | Target | Checks | Passed | Failed | Skipped |
|-------|--------|--------|--------|--------|---------|
| QA-PROD-PUBLIC | prod | 5 | 5 | 0 | 0 |
| QA-PROD-ADMIN | prod | 6 | 6 | 0 | 0 |
| QA-STAGING | staging | 6 | 5 | 0 | 1 |
| QA-MOBILE | both | 9 | 9 | 0 | 0 |
| QA-SAFETY | prod | 4 | 4 | 0 | 0 |
| **Total** | | **30** | **29** | **0** | **1** |

### QA-PROD-PUBLIC (5/5 PASS)
1. Homepage 200 + sfpermits text
2. Health endpoint 200 + status ok JSON
3. Search results 200 + content
4. Login page 200 + form elements
5. No staging banner on prod

### QA-PROD-ADMIN (6/6 PASS)
1. Pipeline health endpoint 200 + 4 health checks
2. Signal tables present (signal_types: 13 rows)
3. Addenda data: 3.9M rows
4. Station velocity: 210 rows
5. API usage table exists (0 rows expected)
6. Screenshots captured

### QA-STAGING (5/6 PASS, 1 SKIP)
1. Admin test-login: PASS
2. Staging banner visible: PASS
3. Admin costs page: PASS
4. Admin pipeline page with health cards: PASS
5. Account page: PASS
6. Homeowner role gating: **SKIP** — test-login always authenticates as admin regardless of role parameter (pre-existing limitation)

### QA-MOBILE (9/9 PASS)
- 3 prod pages + 6 staging pages at 375x812
- All: no horizontal overflow, viewport meta present, HTTP 200

### QA-SAFETY (4/4 PASS)
1. test-login returns 404 on prod (TESTING not set)
2. No staging banner on prod
3. Admin routes redirect to login for unauthenticated users
4. Pipeline health POST requires CRON_SECRET (403 without)

## Observations

- **Stuck cron jobs:** log_id 14 still in "running" state since 2026-02-22 18:06. Pipeline health reports 2 stuck jobs. Should be cleaned up.
- **Test-login role parameter:** Staging test-login always returns admin regardless of role. This limits non-admin testing on staging.
- **CRON_SECRET discrepancy:** Railway CLI shows same CRON_SECRET across services, but direct curl with that value returns 403 on prod. GitHub Actions succeeds (uses GitHub secret). Possibly a Railway environment variable propagation issue.
- **Addenda far-future dates:** MAX(finish_date) = 2205-07-24 — SODA data quality issue, not a bug.
