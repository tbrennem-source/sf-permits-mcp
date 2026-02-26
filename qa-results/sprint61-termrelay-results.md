# Sprint 61 termRelay QA Results — 2026-02-26 04:25

**Target:** https://sfpermits-ai-staging-production.up.railway.app
**Screenshots:** /Users/timbrenneman/AIprojects/sf-permits-mcp/qa-results/screenshots/sprint61

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | GET /api/similar-projects (Mission, cost=75000) | PASS | HTTP 200, 6412 bytes, content snippet: '<div style="margin-bottom:12px;">\n    <p style="color:var(--text-muted);font-si' |
| 2 | GET / → page loads, search form visible | PASS | HTTP 200, title='sfpermits.ai — San Francisco Building Permit Intelligence', search input visible |
| 3 | /health has 'projects' table | FAIL | 'projects' not in tables (table_count=56, sample=['activity_log', 'addenda', 'addenda_changes', 'affordable_housing', 'analysis_sessions', 'api_daily_summary', 'api_usage', 'auth_tokens']) |
| 4 | /health has 'project_members' table | FAIL | 'project_members' not in tables (table_count=56) |
| 5 | /health has 'users' table | PASS | found in tables dict (row_count=6) |
| 6 | GET /auth/login → 200, login form visible | PASS | HTTP 200, form visible |
| 7 | GET / at desktop (1280px) → loads | PASS | HTTP 200, title='sfpermits.ai — San Francisco Building Permit Intelligence' |
| 8 | GET / at mobile (375px) → no overflow | PASS | HTTP 200, scrollWidth=375px |
| 9 | GET /health → status=ok, tables>=56 | PASS | status=ok, table_count=56 |
| 10 | POST /analyze → results with tabs | PASS | Results page loaded, no 500 |
| 11 | GET /api/similar-projects (Noe Valley) | PASS | HTTP 200, 6159 bytes |
| 12 | /dashboard/bottlenecks → auth redirect | PASS | Redirected to https://sfpermits-ai-staging-production.up.railway.app/auth/login |
| 13 | /brief → auth redirect | PASS | Redirected to https://sfpermits-ai-staging-production.up.railway.app/auth/login |
| 14 | GET /sitemap.xml → 200 with XML | PASS | HTTP 200, 765 bytes, XML confirmed |

**Summary:** 12 PASS / 2 FAIL / 0 SKIP out of 14 checks

Screenshots saved to: `/Users/timbrenneman/AIprojects/sf-permits-mcp/qa-results/screenshots/sprint61/`

---

## RELAY Analysis

### BLOCKED: Checks 3 and 4 — Team Seed tables not on staging

**Check 3** (`projects` table) and **Check 4** (`project_members` table) both FAIL because the Sprint 61 Team Seed migration has not been applied to the staging database. The staging instance has 56 tables and does not include `projects` or `project_members`.

**Root cause:** Sprint 61 Team Seed (Agent B) tables require a DB migration that has not yet been deployed to the `sfpermits-ai-staging` Railway service.

**What was tried:**
1. Confirmed via `/health` — staging has 56 tables, neither `projects` nor `project_members` is present.
2. Verified production also does not have these tables (Sprint 61 Team Seed is a new feature, not yet merged/deployed).
3. No code fix is possible from the QA agent — this requires the migration to run on staging.

**Recommended next step:** Deploy Sprint 61 Team Seed migration to staging. After migration runs, re-run checks 3 and 4.

### Notes on User-Agent requirement

Staging returns HTTP 403 for API requests without a browser-like `User-Agent` header. This affects `/api/similar-projects`, `/sitemap.xml`, and `/health` when called from plain Python `requests`. All checks were retried with a Chrome UA and passed. This behavior appears intentional (bot protection on staging).

### Passing checks confirmation

- Landing page (desktop + mobile): renders correctly, no overflow, search form visible
- Auth flow: `/auth/login` shows magic-link form; `/brief` and `/dashboard/bottlenecks` both redirect to login (no 500)
- `/api/similar-projects`: returns HTML fragment with project cards (5 results for Mission, results for Noe Valley)
- `/sitemap.xml`: valid XML with `<url>` entries
- `/health`: `status=ok`, 56 tables, DB connected
- `/analyze` form: submittable, results load without 500
