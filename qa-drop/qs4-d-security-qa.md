# QS4-D Security QA Script

## Prerequisites
- App running locally on port 5001
- No POSTHOG_API_KEY needed for structural checks

## Checks

1. [NEW] Response headers include Content-Security-Policy-Report-Only — PASS/FAIL
2. [NEW] CSP-Report-Only header contains nonce value — PASS/FAIL
3. [NEW] CSP-Report-Only header allows external sources (unpkg, jsdelivr, fonts, posthog) — PASS/FAIL
4. [NEW] Enforced CSP still has unsafe-inline — PASS/FAIL
5. [NEW] POST /auth/send-link without csrf_token returns 403 — PASS/FAIL
6. [NEW] POST /auth/send-link with csrf_token succeeds (not 403) — PASS/FAIL
7. [NEW] HTMX POST with X-CSRFToken header succeeds (not 403) — PASS/FAIL
8. [NEW] auth_login.html contains csrf_token hidden input in rendered HTML — PASS/FAIL
9. [NEW] posthog_track callable and no-ops without key — PASS/FAIL
10. [NEW] Nonces change between requests — PASS/FAIL
