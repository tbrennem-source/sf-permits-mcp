> EXECUTE IMMEDIATELY. You are a build terminal in a quad sprint. Read the tasks below and execute them sequentially. Do NOT summarize or ask for confirmation — execute now.

# QS13 T4 — QA + Vision + Promote (Sprint 101)

You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to YOUR branch only.

## Read First
- CLAUDE.md (project rules, QA protocols)
- docs/DESIGN_TOKENS.md (scoring rubric)
- qa-drop/ (existing QA scripts for reference)

## Agent 4A: Vision QA Pass (includes QS12.5 Task #409)

### Pages to Screenshot (14 total)
New QS13 pages:
1. `/join-beta` (honeypot capture page)
2. `/join-beta/thanks` (confirmation)
3. `/docs` (API documentation)
4. `/privacy` (privacy policy)
5. `/terms` (terms of service)
6. Landing page in HONEYPOT_MODE=1

QS12 demo-flow pages (Task #409):
7. `/` (landing page, normal mode)
8. `/search?q=487+Noe+St` (search results)
9. `/tools/station-predictor`
10. `/tools/stuck-permit`
11. `/tools/what-if`
12. `/tools/cost-of-delay`
13. `/tools/entity-network`
14. `/tools/revision-risk`

### Process for Each Page
1. Start local dev server: `HONEYPOT_MODE=0 python -c "from web.app import app; app.run(host='127.0.0.1', port=5111, debug=False)"`
2. Use Playwright (`playwright.sync_api`, `chromium.launch(headless=True)`) at 3 viewports:
   - Desktop: 1440x900
   - Tablet: 768x1024
   - Phone: 375x812
3. Screenshot each to `qa-results/screenshots/qs13-vision/`
4. Score against DESIGN_TOKENS.md rubric (1-5 scale):
   - 5: Perfect token compliance
   - 4: Minor issues (wrong font weight, slight spacing)
   - 3: Notable (non-token color, missing component)
   - 2: Significant (off-brand, user trust risk)
   - 1: Broken (layout broken, unreadable)
5. Fix anything scoring ≤ 3.0 (template visual fixes ONLY — no logic changes)

For HONEYPOT_MODE=1 pages, restart dev server with `HONEYPOT_MODE=1`.

### Persona QA Agents
After vision scoring, run these specialized checks:

**New Visitor Journey (honeypot path):**
Using Playwright, simulate the full journey:
1. Land on `/` (HONEYPOT_MODE=1)
2. Click a showcase CTA → verify redirect to `/join-beta?ref=...`
3. Fill out signup form (email, role, optional address)
4. Submit → verify redirect to `/join-beta/thanks`
5. Verify queue position number is displayed
6. Go back to `/` → click search → verify redirect to `/join-beta?ref=search&q=...`

**Mobile Checks (375px viewport):**
1. `/join-beta` — form fields usable, CTAs ≥ 44px touch target
2. `/join-beta/thanks` — text readable, no overflow
3. `/docs` — tool catalog readable, no horizontal scroll
4. Landing page (honeypot) — all elements visible, no overflow

**Public Route Regression (HONEYPOT_MODE=1):**
1. `/` returns 200 (not redirected)
2. `/demo/guided` returns 200
3. `/health` returns 200
4. `/join-beta` returns 200
5. `/static/obsidian.css` returns 200
6. `/sitemap.xml` returns 200
7. `/search` redirects to `/join-beta`
8. `/tools/station-predictor` redirects to `/join-beta`
9. `/auth/login` redirects to `/join-beta`
10. `/admin/feedback` does NOT redirect (admin exempt)

**Public Route Regression (HONEYPOT_MODE=0):**
1. All routes work as before QS13 (no unintended redirects)
2. `/join-beta` still accessible (even without honeypot mode)

### Output
Write results to `qa-results/qs13-vision-qa-results.md`:
- Score table: page × viewport → score
- Screenshots path for each
- Fixes applied (if any)
- Persona QA: PASS/FAIL for each check

### Files Owned
- Template visual fixes only (CSS tweaks, spacing, font — NO logic changes)
- `qa-results/screenshots/qs13-vision/` (screenshots)
- `qa-results/qs13-vision-qa-results.md`

---

## Agent 4B: Integration Test Suite

### Honeypot Tests (`tests/test_honeypot_integration.py`)
- HONEYPOT_MODE=1: GET /search → 302 to /join-beta
- HONEYPOT_MODE=1: GET /search?q=kitchen → 302 to /join-beta?ref=search&q=kitchen
- HONEYPOT_MODE=1: GET /tools/station-predictor → 302 to /join-beta?ref=/tools/station-predictor
- HONEYPOT_MODE=1: GET / → 200 (not redirected)
- HONEYPOT_MODE=1: GET /health → 200
- HONEYPOT_MODE=1: GET /static/obsidian.css → 200
- HONEYPOT_MODE=1: GET /cron/status → 200 (not redirected)
- HONEYPOT_MODE=1: GET /admin/feedback (with admin session) → 200
- HONEYPOT_MODE=0: GET /search → 200 (normal behavior)
- HONEYPOT_MODE=0: GET /join-beta → 200 (still accessible)
- POST /join-beta: valid email → 302 to /join-beta/thanks + DB write
- POST /join-beta: honeypot field filled → 200, no DB write
- POST /join-beta: rate limit (4th request in 1 hour) → 429 or redirect with error
- GET /join-beta/thanks: shows queue position number
- /admin/beta-funnel: requires admin, shows data
- /admin/beta-funnel/export: returns CSV

### OAuth Tests (`tests/test_oauth_integration.py`)
- GET /.well-known/oauth-authorization-server → 200 with valid JSON
- POST /register → creates client, returns client_id
- GET /authorize with valid client_id → returns consent page or redirect
- POST /token with valid auth code → returns access_token + refresh_token
- POST /token with invalid code → 400
- POST /token with grant_type=refresh_token → new access_token
- POST /revoke → invalidates token
- MCP tool call with valid token → 200
- MCP tool call without token → 401
- MCP tool call with expired token → 401

### Rate Limiting Tests (`tests/test_mcp_rate_limit_integration.py`)
- Demo scope: 10 calls → all succeed, 11th → 429
- Rate limit headers present in responses
- Response > 20K tokens gets truncated

### Security Tests (`tests/test_mcp_security.py`)
- run_query: SELECT from users → blocked
- run_query: SELECT from permits → allowed
- read_source: CLAUDE.md → blocked
- read_source: src/server.py → allowed
- list_feedback: demo scope → permission denied
- list_feedback: professional scope → allowed

### Content Page Tests (`tests/test_content_pages.py`)
- GET /docs → 200, contains "API"
- GET /privacy → 200, contains "Privacy"
- GET /terms → 200, contains "Terms"
- GET /docs → lists at least 30 tools
- OG tags present on landing page
- JSON-LD present on landing page
- index.html does NOT have noindex meta

### Design Lint
```bash
python scripts/design_lint.py --changed --quiet
```
Write results to `qa-results/design-lint-qs13.md`

### Files Owned
- NEW `tests/test_honeypot_integration.py`
- NEW `tests/test_oauth_integration.py`
- NEW `tests/test_mcp_rate_limit_integration.py`
- NEW `tests/test_mcp_security.py`
- NEW `tests/test_content_pages.py`
- `qa-results/design-lint-qs13.md`

---

## Agent 4C: Prod Gate + Promote Prep

### Run Prod Gate
```bash
python scripts/prod_gate.py --quiet
```

### Verify All Tests Pass
```bash
pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q
```

### Design Lint Summary
```bash
python scripts/design_lint.py --changed
```
Score must be ≥ 4/5 on all new templates.

### Create Promote Checklist
Write `qa-results/qs13-promote-checklist.md`:
- [ ] All tests pass
- [ ] Design lint ≥ 4/5
- [ ] Prod gate passes
- [ ] Vision QA: all pages ≥ 3.0
- [ ] Persona QA: new-visitor journey completes
- [ ] Mobile QA: /join-beta usable at 375px
- [ ] Public routes: correct behavior in both honeypot modes
- [ ] OAuth: discovery + registration + auth flow works
- [ ] Rate limiting: demo tier enforced
- [ ] /docs: renders 34 tools
- [ ] /privacy + /terms: accessible
- [ ] DIRECTORY_SUBMISSION.md: complete

### Railway Env Var Instructions
Document in the promote checklist:
```
After merge to prod:
1. sfpermits-ai (prod): Add HONEYPOT_MODE=1
2. sfpermits-mcp-api: Remove MCP_AUTH_TOKEN (OAuth replaces it)
3. Verify: curl https://sfpermits-ai-production.up.railway.app/ → landing page
4. Verify: curl https://sfpermits-ai-production.up.railway.app/search → redirect to /join-beta
5. Verify: curl https://sfpermits-mcp-api-production.up.railway.app/.well-known/oauth-authorization-server → OAuth metadata
```

### Files Owned
- `qa-results/qs13-promote-checklist.md`
- Scripts only (no production code changes)

---

## Build Order
1. Agent 4A + Agent 4B in parallel (vision QA + test writing — independent)
2. Agent 4C after both (runs tests that 4B wrote, checks pages that 4A scored)

## T4 Merge Validation
- All new tests pass
- Vision QA scores ≥ 3.0 on all pages
- Design lint ≥ 4/5
- Promote checklist complete

## Commit + Push
```bash
git add -A && git commit -m "feat(qs13-t4): vision QA + integration tests + promote prep"
git push origin HEAD
```

## Scenarios
Append to `scenarios-pending-review.md`:
- New visitor completes honeypot signup journey on mobile
- OAuth flow works end-to-end from c.ai custom connector
- Rate-limited user sees helpful upgrade message
- /docs page accurately reflects all 34 tools
- Admin sees beta funnel analytics dashboard
