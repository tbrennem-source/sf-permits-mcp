# CHANGELOG — Sprint 77-2 (2026-02-26)

## Agent 77-2: Admin + Security E2E Scenarios

### New: tests/e2e/test_admin_scenarios.py

Added 18 Playwright E2E tests covering admin access control and security hardening
scenarios. 15 pass, 3 skip gracefully without TEST_LOGIN_SECRET (admin auth tests).

**TestAdminOpsPage (4 tests)**
- `test_admin_ops_loads` — Admin user can load /admin/ops; page has ops/pipeline/quality content
- `test_admin_ops_has_tabs` — Admin ops page renders at least 2 of: pipeline/quality/activity/feedback
- `test_non_admin_ops_blocked` — Non-admin authenticated user (homeowner) is denied /admin/ops
- `test_anonymous_ops_redirect` — Anonymous visitor is redirected from /admin/ops to login

**TestSQLInjectionSearch (3 tests)**
- `test_sql_injection_no_500` — Classic `' OR 1=1 --` payload does not produce HTTP 500
- `test_sql_injection_variants_no_500` — 5 injection variants all handled gracefully (no 500, no traceback)
- `test_sql_injection_xss_combo_no_500` — Combined XSS+SQL payload: no 500, script tag sanitized in HTML

**TestDirectoryTraversal (3 tests)**
- `test_traversal_report_passwd` — `/report/../../../etc/passwd` returns safe response (no passwd contents)
- `test_traversal_paths_no_file_contents` — 4 traversal paths produce no file exposure, no 500
- `test_traversal_etc_passwd_direct` — `/../etc/passwd` from root returns safe response

**TestCSPHeaders (5 tests)**
- `test_csp_on_landing` — Landing page response includes Content-Security-Policy with default-src
- `test_csp_on_search` — Search page response includes CSP
- `test_csp_on_login` — Login page response includes CSP
- `test_csp_blocks_framing` — frame-ancestors CSP or X-Frame-Options present on landing
- `test_csp_multiple_pages` — CSP consistently present across 5 page types
- `test_security_headers_present` — X-Content-Type-Options: nosniff + Referrer-Policy present

**TestAnonymousRateLimiting (2 tests)**
- `test_search_rate_limited_after_many_requests` — 20 rapid /search requests trigger 429 or rate-limit message
- `test_search_rate_limit_message_is_friendly` — Rate-limited response body has no traceback or ISE message

### Scenarios appended
- scenarios-pending-review-sprint-77-2.md (per-agent, 5 scenarios)
- scenarios-pending-review.md (shared, 5 scenarios appended)
