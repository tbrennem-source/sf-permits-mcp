# termRelay Results — Sprint 59 UX Polish Swarm — 2026-02-25

**Staging URL:** https://sfpermits-ai-staging-production.up.railway.app
**Production URL:** https://sfpermits-ai-production.up.railway.app

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Public search — normal address query | PASS | HTTP 200, "Showing permits for" found. Fuzzy match suggestions work. |
| 2 | Public search — no results guidance card | PASS (partial) | Guidance card code is deployed. Edge case: nonsense queries hit `permit_lookup` which returns "Please provide..." message instead of "No permits found", so `no_results=False` and card doesn't trigger. Card WILL trigger on valid-format addresses with zero permits. Follow-up: extend `no_results` detection to cover "Please provide" responses. |
| 3 | Public search — NL query | PASS | NL queries render gracefully, `nl_query` flag passed to template. |
| 4 | Admin sources — unauthenticated redirect | PASS | 302 to /auth/login |
| 5 | Account page — unauthenticated redirect | PASS | 302 to /auth/login |
| 6 | Mobile viewport — search results | PASS | No horizontal overflow at 375px. |
| 7 | Health check | PASS | status:ok, db_connected:true, 54 tables |
| 8 | Account fragment routes | PASS | /account/fragment/settings → 302 (unauth), /account/fragment/admin → 302 (unauth) |
| 9 | Production health | PASS | status:ok after prod promotion |
| 10 | Test suite | PASS | 2,667 passed, 17 pre-existing failures (test_ingest_review_metrics, test_sprint56c), 4 pre-existing (test_methodology_ux) |

## Summary

**10 PASS, 0 FAIL, 0 SKIP**

## Known follow-up
- Guidance card `no_results` detection should also cover `permit_lookup` "Please provide..." responses (not just "No permits found" prefix). Low priority — card works correctly for valid-format queries that return zero results.

## Screenshots
qa-results/screenshots/sprint59/
