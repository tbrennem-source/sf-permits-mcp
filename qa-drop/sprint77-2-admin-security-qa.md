# QA Script — Sprint 77-2: Admin + Security E2E Scenarios

Self-contained. No credentials required for anonymous-only steps.
Auth steps require TEST_LOGIN_SECRET; they skip gracefully without it.

Run:
    pytest tests/e2e/test_admin_scenarios.py -v

Or against staging:
    E2E_BASE_URL=https://sfpermits-ai-staging-production.up.railway.app \
    TEST_LOGIN_SECRET=<secret> \
    pytest tests/e2e/test_admin_scenarios.py -v

---

## Steps

### 1. Admin ops page — anonymous redirect
**Action:** Navigate to /admin/ops without auth
**PASS:** Redirected to login page OR response status 302/403
**FAIL:** Admin ops content visible to unauthenticated user

### 2. Admin ops page — admin access (requires TEST_LOGIN_SECRET)
**Action:** Login as admin persona, navigate to /admin/ops
**PASS:** Page loads (200), body contains ops/pipeline/quality/admin keywords
**FAIL:** 403, redirect, or empty body

### 3. Admin ops page — tabs present (requires TEST_LOGIN_SECRET)
**Action:** Login as admin, navigate to /admin/ops, inspect body text
**PASS:** At least 2 of these keywords present: pipeline, quality, activity, feedback
**FAIL:** Fewer than 2 tab labels found

### 4. Admin ops page — non-admin blocked (requires TEST_LOGIN_SECRET)
**Action:** Login as homeowner persona, navigate to /admin/ops
**PASS:** Redirected away OR 403 returned OR forbidden in body
**FAIL:** Homeowner sees full admin ops content

### 5. SQL injection — no 500
**Action:** GET /search?q=%27+OR+1%3D1+--
**PASS:** Response status 200 or 4xx, no "Traceback" in body
**FAIL:** HTTP 500 or Python traceback in response body

### 6. SQL injection — multiple variants
**Action:** Run 5 injection payloads through /search?q=... (URL encoded)
**PASS:** All return non-500, no traceback in any response
**FAIL:** Any payload produces HTTP 500 or traceback

### 7. SQL + XSS combo — sanitized
**Action:** GET /search?q=%3Cscript%3Ealert%28%27xss%27%29%3C%2Fscript%3E%27+OR+1%3D1+--
**PASS:** No 500; `<script>alert` not found in rendered page.content()
**FAIL:** HTTP 500 OR script tag present in rendered HTML

### 8. Directory traversal — /report/../../../etc/passwd
**Action:** Navigate to /report/../../../etc/passwd
**PASS:** Response body does NOT contain "root:" or "daemon:", status != 500
**FAIL:** /etc/passwd contents appear in body OR HTTP 500

### 9. Directory traversal — multiple paths
**Action:** Test 4 traversal paths (/report/../../etc/hosts, /../etc/shadow, /static/../../../etc/passwd, /../etc/passwd)
**PASS:** None return "root:" / "daemon:" in body, none return 500
**FAIL:** Any path exposes system file contents or returns 500

### 10. CSP header — landing page
**Action:** GET / and inspect response headers
**PASS:** Content-Security-Policy header present, contains "default-src"
**FAIL:** Header absent or missing default-src directive

### 11. CSP header — multiple pages
**Action:** GET /, /search?q=test, /auth/login, /health, /methodology — check headers
**PASS:** All 5 pages return Content-Security-Policy header
**FAIL:** Any page missing CSP header

### 12. Anti-framing header present
**Action:** GET / and inspect headers
**PASS:** frame-ancestors in CSP OR X-Frame-Options header present
**FAIL:** Neither framing protection header found

### 13. Security headers — X-Content-Type-Options and Referrer-Policy
**Action:** GET / and inspect headers
**PASS:** X-Content-Type-Options: nosniff AND Referrer-Policy header set
**FAIL:** Either header missing or X-Content-Type-Options != nosniff

### 14. Rate limiting — triggers after rapid requests
**Action:** Make 20 rapid GET requests to /search?q=test0 through test19
**PASS:** At least one request returns HTTP 429 OR body contains "rate limit" / "wait a minute"
**FAIL:** All 20 requests return 200 with no rate-limit signal

### 15. Rate limit — friendly message
**Action:** Exhaust rate limit (25 requests), observe rate-limited response
**PASS:** Rate-limited body does NOT contain "Internal Server Error" or "Traceback"
**FAIL:** Rate-limited body contains raw error message

---

## Screenshots saved to
qa-results/screenshots/sprint77-2/
- admin-ops-hub.png
- admin-ops-tabs.png
- non-admin-ops-blocked.png
- anon-ops-redirect.png
- sql-injection-search.png
- sql-xss-combo.png
- traversal-report-passwd.png
- traversal-root-passwd.png
- csp-landing.png
- csp-search.png
- csp-login.png
- rate-limit-triggered.png
- rate-limit-friendly-msg.png
