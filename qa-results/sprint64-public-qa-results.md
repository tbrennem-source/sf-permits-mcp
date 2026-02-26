# Public QA Results — 2026-02-26

Session: sprint64
Target: https://sfpermits-ai-staging-production.up.railway.app

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Health endpoint | PASS | HTTP 200, body has status=ok |
| 2 | Landing page loads | PASS | title='sfpermits.ai — San Francisco Building Permit Intelligence', HTTP=200, 7 CTAs |
| 3 | Search form present | PASS | input visible on landing page, accepts text input |
| 4 | Search results — valid address | PASS | HTTP=200, page loaded with result elements and no-results message (graceful), no traceback |
| 5 | Search results — empty query | PASS | graceful response, no crash |
| 6 | Search results — special characters (XSS) | PASS | input escaped in response, no alert executed, no server error |
| 7 | Public report page | PASS | /report/3512/035 loaded without auth redirect or error |
| 8 | Unauthenticated /brief access | PASS | redirected to /auth/login |
| 9 | Static assets load | PASS | no 404s on CSS/JS assets, no console errors |
| 10 | /health DB connectivity | PASS | db_connected=true, 59 tables reported |

**Result: 10/10 PASS**

## Notes

- Check 4: "123 Main St San Francisco" returned no matching permits in the DB, but the response was graceful (no traceback, proper no-results handling). PASS by spec.
- Check 8: /brief correctly redirects unauthenticated users to /auth/login.
- Auth/admin pages (account, brief, portfolio, admin-*) skipped in visual QA golden capture because the test-login endpoint returns HTTP 500 on staging. Public pages (5 pages x 3 viewports = 15 goldens) were captured successfully.

## Visual QA Golden Capture

Sprint 64 golden baselines established for 15 public page-viewport combinations.

Summary from visual_qa.py: 48 PASS / 0 FAIL / 15 NEW

| Viewport | Pages Captured | Status |
|----------|---------------|--------|
| mobile (390x844) | 5 public pages | 5 NEW goldens |
| tablet (768x1024) | 5 public pages | 5 NEW goldens |
| desktop (1440x900) | 5 public pages | 5 NEW goldens |

Auth/admin pages: SKIP — test-login endpoint returns HTTP 500 on staging (pre-existing issue, not introduced this sprint)

Screenshots: qa-results/screenshots/sprint64-public-qa/
Goldens: qa-results/goldens/ (15 new files)
Filmstrips: qa-results/filmstrips/sprint64-{mobile,tablet,desktop}.png
Full visual results: qa-results/sprint64-visual-results.md
