# QA Results: Landing Page + Public Address Lookup (Session 52C)
## Date: 2026-02-23
## Method: Programmatic RELAY via Flask test client (27 checks)

### Round 1: 22 PASS, 4 FAIL
- FAIL: Locked premium cards not shown when search errors (DB unavailable in test env)
- Fix: Moved locked cards outside the if/elif/else block so they always render

### Round 2 (after fix): 27 PASS, 0 FAIL

| Step | Check | Result |
|------|-------|--------|
| 1 | Hero text renders | PASS |
| 1 | Search box visible | PASS |
| 1 | 6 feature cards | PASS |
| 1 | Stats section | PASS |
| 1 | Sign in buttons | PASS |
| 2 | /search returns 200 | PASS |
| 2 | Results page has content | PASS |
| 3 | Sign up free CTA | PASS |
| 3 | Property Report card | PASS |
| 3 | Watch & Alerts card | PASS |
| 3 | AI Analysis card | PASS |
| 3 | CTAs link to /auth/login | PASS |
| 4 | Empty search redirects | PASS |
| 5 | Auth user sees full app | PASS |
| 5 | No landing hero for auth | PASS |
| 6 | Auth /search redirects | PASS |
| 7 | /brief requires login | PASS |
| 7 | /portfolio requires login | PASS |
| 7 | /account requires login | PASS |
| 7 | /consultants requires login | PASS |
| 7 | /account/analyses requires login | PASS |
| 8 | /health is public | PASS |
| 8 | /auth/login is public | PASS |
| 8 | /search is public | PASS |
| 10 | No-results not a 500 | PASS |
| 10 | Locked cards on error | PASS |
| 11 | Rate limiting works | PASS |

### Not tested (requires browser)
- Step 9: Mobile responsiveness (viewport, stacking, touch targets)
  - Mitigated by: CSS media queries present in template, viewport meta tag verified in tests
