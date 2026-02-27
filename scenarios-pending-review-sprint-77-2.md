# Sprint 77-2 Scenarios — Admin + Security

## SUGGESTED SCENARIO: Admin ops hub gated by role
**Source:** tests/e2e/test_admin_scenarios.py — TestAdminOpsPage, web/routes_admin.py
**User:** admin
**Starting state:** Authenticated admin user, all other non-admin users also logged in
**Goal:** Only admin users can reach /admin/ops; non-admins and anonymous visitors are blocked
**Expected outcome:**
- Admin user: page loads, shows ops hub content (pipeline, quality, activity, feedback sections)
- Non-admin authenticated user: blocked with 403 or redirected away from the ops hub
- Anonymous visitor: redirected to login page before seeing any admin content
**Edge cases seen in code:** `abort(403)` used directly — no intermediate redirect for non-admins, so a 403 response body should not contain ops content
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: SQL injection payload handled gracefully in search
**Source:** tests/e2e/test_admin_scenarios.py — TestSQLInjectionSearch, web/app.py rate-limit middleware
**User:** homeowner
**Starting state:** Anonymous or authenticated user, normal browser session
**Goal:** Malicious SQL injection payloads in the search query do not crash the server or expose data
**Expected outcome:**
- Server returns 200 or 400, never 500
- No Python traceback appears in the response body
- No raw database error message visible to the user
- Result: empty search results or a graceful "no results" message
**Edge cases seen in code:** Combined XSS + SQL payload (`<script>alert()` + `OR 1=1`) also sanitized — script tag does not appear in rendered HTML
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Directory traversal attempt returns safe response
**Source:** tests/e2e/test_admin_scenarios.py — TestDirectoryTraversal
**User:** homeowner
**Starting state:** Anonymous user, no session, crafts a URL with `../` sequences
**Goal:** Attacker tries to read system files by traversing path segments
**Expected outcome:**
- Response does not contain /etc/passwd file contents (no "root:", "daemon:")
- Response status is 404 or a redirect, never 500
- Flask/Werkzeug's path normalization neutralizes the traversal before routing
**Edge cases seen in code:** `/report/../../../etc/passwd`, `/static/../../../etc/passwd`, `/../etc/passwd` all tested — Flask URL routing normalizes these before they reach the view
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Content-Security-Policy header on every page response
**Source:** tests/e2e/test_admin_scenarios.py — TestCSPHeaders, web/security.py add_security_headers()
**User:** homeowner
**Starting state:** Any page request (landing, search, login, health, methodology)
**Goal:** Every HTTP response includes a Content-Security-Policy header to prevent XSS and injection attacks
**Expected outcome:**
- `Content-Security-Policy` header present on all page responses
- Header includes `default-src` directive as baseline restriction
- `frame-ancestors 'none'` in CSP or `X-Frame-Options: DENY` header present (prevents clickjacking)
- `X-Content-Type-Options: nosniff` present (prevents MIME sniffing)
- `Referrer-Policy` header set
**Edge cases seen in code:** CSP-Report-Only nonce-based policy also sent when a per-request nonce is generated; enforced CSP uses `unsafe-inline` as fallback for HTMX compatibility
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Anonymous user rate-limited on rapid search requests
**Source:** tests/e2e/test_admin_scenarios.py — TestAnonymousRateLimiting, web/app.py RATE_LIMIT_MAX_LOOKUP
**User:** homeowner
**Starting state:** Anonymous visitor (no session), makes many rapid GET requests to /search
**Goal:** Rate limiting fires to prevent scraping or abuse after sustained rapid requests
**Expected outcome:**
- After 15+ requests within 60 seconds from the same IP, the server returns HTTP 429 or a "Rate limit exceeded" message
- The rate-limit response is friendly (not a raw server error, no traceback)
- The 429 body text mentions waiting or rate-limiting, not "Internal Server Error"
**Edge cases seen in code:** Rate bucket is per-IP (X-Forwarded-For header, first value); bucket resets after 60 seconds; TESTING mode may reset buckets between requests — tests account for this with graceful skip
**CC confidence:** medium
**Status:** PENDING REVIEW
