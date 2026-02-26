# Sprint 62 — Activity Intelligence + Launch Hardening QA

## Pre-requisites
- Staging deployed from latest main
- TEST_LOGIN_SECRET available from Railway

## Stage 1: termRelay (Headless Playwright)

### A. Activity Intelligence (Admin Intel Tab)

- [ ] **A1**: Navigate to /admin/ops, log in as admin
- [ ] **A2**: Click "Intelligence" tab → tab loads with 5 metric sections
- [ ] **A3**: Bounce Rate card shows total_searches, bounced, bounce_rate
- [ ] **A4**: Feature Funnel shows 4 stages (search → detail → analyze → ask)
- [ ] **A5**: Query Refinements section renders (may show 0 if no data)
- [ ] **A6**: Feedback by Page section renders
- [ ] **A7**: Time to First Action section renders
- [ ] **A8**: Non-admin user gets 403 on /admin/ops/fragment/intel

### B. Client-Side Tracking

- [ ] **B1**: GET / → page source contains `activity-tracker.js` script tag
- [ ] **B2**: GET /search?q=test → page source contains `activity-tracker.js` script tag
- [ ] **B3**: POST /api/activity/track with valid JSON → 200 {"ok": true}
- [ ] **B4**: POST /api/activity/track with invalid JSON → 400
- [ ] **B5**: POST /api/activity/track with empty events → 200 {"ok": true, "count": 0}

### C. Security Headers

- [ ] **C1**: GET / → response has Content-Security-Policy header
- [ ] **C2**: CSP header contains "script-src 'self' 'unsafe-inline'"
- [ ] **C3**: Response has X-Frame-Options: DENY
- [ ] **C4**: Response has X-Content-Type-Options: nosniff
- [ ] **C5**: Response has Referrer-Policy header
- [ ] **C6**: Response has Permissions-Policy header
- [ ] **C7**: Response has Strict-Transport-Security (prod/staging only)
- [ ] **C8**: GET / with User-Agent "python-requests/2.28" → 403
- [ ] **C9**: GET /health with User-Agent "python-requests/2.28" → 200 (exempt)
- [ ] **C10**: GET /api/v1 → 404
- [ ] **C11**: GET /graphql → 404
- [ ] **C12**: GET /debug → 404

### D. Feature Gating

- [ ] **D1**: GET / as anonymous → nav contains "Sign up" badge text
- [ ] **D2**: GET / as anonymous → Brief link shows greyed with "Sign up" badge
- [ ] **D3**: GET / as anonymous → Portfolio link shows greyed with "Sign up" badge
- [ ] **D4**: GET / as logged-in user → Brief/Portfolio links are normal (no "Sign up")
- [ ] **D5**: GET / as logged-in user → no "Sign up" badges visible in nav

### E. Search Fix (Chief #279)

- [ ] **E1**: GET /search?q=abc123 (ambiguous query) → shows guidance card, not "provide a permit number"

## Stage 2: termRelay on Prod (after promotion)

- [ ] **PROD1**: GET / → has CSP + security headers
- [ ] **PROD2**: GET / → has HSTS header (prod-only)
- [ ] **PROD3**: POST /api/activity/track → 200
- [ ] **PROD4**: Admin ops Intelligence tab loads
- [ ] **PROD5**: Anonymous nav shows gated features with "Sign up"
