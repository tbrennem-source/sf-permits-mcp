## SUGGESTED SCENARIO: CSP violations from inline styles are captured in report-only mode without breaking pages
**Source:** QS4-D Task D-1 — CSP-Report-Only with nonces
**User:** admin
**Starting state:** Pages load correctly with enforced CSP using unsafe-inline
**Goal:** Monitor which templates generate CSP violations when nonce-based policy is applied, without breaking any pages
**Expected outcome:** Browser sends violation reports to /api/csp-report when inline styles/scripts lack nonces; pages render normally because Report-Only doesn't enforce
**Edge cases seen in code:** Templates from external CDNs (unpkg, jsdelivr, Google Fonts) need explicit allow-listing in CSP-RO
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: POST form submission without CSRF token is rejected with 403
**Source:** QS4-D Task D-2 — CSRF protection middleware
**User:** homeowner | expediter
**Starting state:** User is on any page with a POST form
**Goal:** Prevent cross-site request forgery attacks on state-changing endpoints
**Expected outcome:** POST requests without a valid csrf_token form field or X-CSRFToken header receive 403 Forbidden; GET requests are unaffected; cron endpoints with Bearer auth skip CSRF
**Edge cases seen in code:** HTMX requests use X-CSRFToken header via hx-headers attribute on body; feedback widget, watch forms, and account settings all need tokens
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Charis signs up with friends-gridcare invite code and reaches the dashboard
**Source:** QS4-D Task D-3 — Beta launch polish
**User:** architect
**Starting state:** User visits /auth/login with friends-gridcare invite code
**Goal:** New beta user signs up and reaches the authenticated dashboard
**Expected outcome:** User enters email and invite code, receives magic link, clicks link, lands on authenticated index page with search and brief access
**Edge cases seen in code:** Three-tier signup: shared_link bypasses invite, valid code grants access, no code redirects to beta request form
**CC confidence:** medium
**Status:** PENDING REVIEW
