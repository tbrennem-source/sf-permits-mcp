# QS4-D Security QA Results

**Date:** 2026-02-26
**Agent:** QS4-D (Security + Beta Launch Polish)
**Branch:** worktree-qs4-d

## Results: 10 PASS / 0 FAIL / 0 SKIP

| # | Check | Result | Detail |
|---|-------|--------|--------|
| 1 | CSP-Report-Only header present | PASS | |
| 2 | CSP-Report-Only contains nonce | PASS | |
| 3 | CSP-Report-Only allows external sources (unpkg, jsdelivr, fonts, posthog) | PASS | |
| 4 | Enforced CSP still has unsafe-inline | PASS | |
| 5 | POST /auth/send-link without csrf_token returns 403 | PASS | got 403 |
| 6 | POST /auth/send-link with csrf_token succeeds | PASS | got 200 |
| 7 | HTMX POST with X-CSRFToken header succeeds | PASS | got 302 |
| 8 | auth_login.html contains csrf_token hidden input | PASS | |
| 9 | posthog_track callable, no-ops without key | PASS | |
| 10 | Nonces change per request | PASS | |

## Test Results

28 new tests in `tests/test_qs4_d_security.py` — all passing.

## Visual Review

See Phase 5.5 below.
