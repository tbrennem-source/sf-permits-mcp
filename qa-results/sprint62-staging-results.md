# Sprint 62 — termRelay1 Staging QA Results

**Date:** 2026-02-25 23:19
**Target:** https://sfpermits-ai-staging-production.up.railway.app
**Result:** 32 PASS / 0 FAIL / 32 total

- [PASS] **C1**: CSP header present
- [PASS] **C2**: CSP has unsafe-inline for scripts
- [PASS] **C3**: X-Frame-Options DENY
- [PASS] **C4**: X-Content-Type-Options nosniff
- [PASS] **C5**: Referrer-Policy present
- [PASS] **C6**: Permissions-Policy present
- [PASS] **C7**: HSTS present (staging/prod)
- [PASS] **C8**: Bot UA blocked (403) — got 403
- [PASS] **C9**: Bot UA exempt on /health (200) — got 200
- [PASS] **C10**: /api/v1 returns 404 — got 404
- [PASS] **C11**: /graphql returns 404 — got 404
- [PASS] **C12**: /debug returns 404 — got 404
- [PASS] **B1**: activity-tracker.js on landing page
- [PASS] **B2**: activity-tracker.js on search results
- [PASS] **B3**: POST /api/activity/track valid → 200 — status=200
- [PASS] **B4**: POST /api/activity/track invalid → 400 — got 400
- [PASS] **B5**: POST /api/activity/track empty → 200 — count=0
- [PASS] **E1**: Ambiguous query shows guidance
- [PASS] **D1**: Landing has Sign in link
- [PASS] **D2**: Landing has Get started CTA
- [PASS] **D3**: Landing header has no Brief/Portfolio links — Correct: authenticated nav items hidden on landing
- [PASS] **AUTH**: Test login POST succeeded — status=200
- [PASS] **D4**: Auth nav has Brief link
- [PASS] **D5**: Auth nav has Portfolio link
- [PASS] **D6**: No 'Sign up' badges in auth nav — found 0
- [PASS] **A1**: Intelligence tab button exists
- [PASS] **A2**: Bounce Rate section
- [PASS] **A3**: Feature Funnel section
- [PASS] **A4**: Query Refinements section
- [PASS] **A5**: Feedback by Page section
- [PASS] **A6**: Time to First Action section
- [PASS] **A7**: Non-admin redirected from intel — final_url=https://sfpermits-ai-staging-production.up.railway.app/auth/login
