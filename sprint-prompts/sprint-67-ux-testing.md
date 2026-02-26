<!-- LAUNCH: Open a fresh CC terminal from the MAIN repo root, then tell it:
     "Read sprint-prompts/sprint-67-ux-testing.md and execute it"
     The agent will read this file and follow the instructions below. -->

# Sprint 67: UX + Testing Infrastructure

You are a build agent for Sprint 67 of the sfpermits.ai project.

**FIRST:** Use EnterWorktree with name `sprint-67` to create an isolated worktree. All work happens there.

## Context
- Repo root: `/Users/timbrenneman/AIprojects/sf-permits-mcp`
- Phase 0 Blueprint refactor is COMPLETE — routes live in `web/routes_*.py`, app.py is slim
- 3,093 tests passing on main at commit `5ba4a6d`
- Always activate venv: `source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate`
- Run tests with: `pytest tests/ --ignore=tests/test_tools.py -q`

## Your 4 Tasks (do them sequentially)

### Task 67-A: Mobile UX Fixes
**Files:** `web/static/mobile.css`, `web/templates/admin_sources.html`, `web/templates/bottlenecks.html`

1. Read `web/static/mobile.css` to understand existing mobile styles
2. Read `web/templates/admin_sources.html` — fix mobile navigation: add the standard admin nav include if missing, ensure content doesn't overflow at 375px
3. Read `web/templates/bottlenecks.html` (velocity dashboard) — make the heatmap and table scrollable on mobile:
   - Add `overflow-x: auto` wrapper around the heatmap
   - Add scroll wrapper around data tables
   - Ensure touch-friendly tap targets (min 44px)
4. Do a responsive audit: check all `web/templates/admin_*.html` files at 375px conceptually — add CSS fixes for any that have obvious overflow/truncation issues
5. Write tests that verify the CSS changes are present

### Task 67-B: Account Page + Progressive Disclosure
**Files:** `web/templates/account.html`, `web/templates/fragments/account_*.html`, `web/templates/landing.html`, `web/static/style.css`

1. Read `web/templates/account.html` to understand current structure
2. Improve the account page tab navigation: ensure Settings and Admin tabs are clearly separated with better visual hierarchy
3. Add progressive disclosure CSS utility classes to `web/static/style.css`:
   - `.disclosure-panel` — collapsed by default, expands on click
   - `.tier-free`, `.tier-pro` — visibility classes based on user tier
4. Improve `web/templates/landing.html` → authenticated transition: ensure the signup CTA is prominent, add feature previews showing what authenticated users get
5. Write tests that verify the CSS classes exist and account tabs render

### Task 67-C: Playwright E2E Test Suite
**Files:** `tests/e2e/` (new test files), `tests/e2e/conftest.py`

1. Read `tests/e2e/conftest.py` to understand existing e2e test setup
2. Create `tests/e2e/test_scenarios.py` with behavioral scenario tests:
   - Test: anonymous user can access landing page
   - Test: anonymous user can search by address
   - Test: login flow (using test-login endpoint if TESTING=1)
   - Test: authenticated user sees index.html not landing.html
   - Test: /health returns 200 with expected JSON structure
   - Test: /robots.txt returns expected content
   - Test: rate limiting returns 429 after threshold
   - Add at least 7 more scenarios covering core user journeys
3. Create `tests/e2e/test_links.py` — dead link spider:
   - Start from / and crawl all internal links
   - Verify each returns 200 or 302 (not 404/500)
   - Cap at 100 pages to prevent infinite crawl
4. Write all tests using Flask test client (not Playwright — save Playwright for QA phase)

### Task 67-D: CSP Nonce Migration (Report-Only)
**Files:** `web/security.py`, `web/routes_api.py` (CSP report endpoint), `web/templates/*.html`

**IMPORTANT: This is report-only mode. Do NOT enforce CSP — only report violations.**

1. Read `web/security.py` to understand current security headers
2. Add a CSP violation reporting endpoint to `web/routes_api.py`:
   - `POST /api/csp-report` — receives CSP violation reports as JSON, logs them
   - No auth required (browsers send reports automatically)
3. In `web/app.py` before_request, generate a per-request nonce:
   - `g.csp_nonce = secrets.token_hex(16)`
   - Add to template context via context_processor
4. Update `web/security.py` `add_security_headers()` to add `Content-Security-Policy-Report-Only` header:
   - `script-src 'nonce-{nonce}' 'unsafe-inline'; style-src 'nonce-{nonce}' 'unsafe-inline'; report-uri /api/csp-report`
   - Keep `'unsafe-inline'` as fallback so nothing breaks
   - This is REPORT-ONLY — violations are logged, not blocked
5. Update ALL `web/templates/*.html` files: add `nonce="{{ csp_nonce }}"` to every `<script>` and `<style>` tag
   - Use a bulk find-replace approach
   - Be careful with HTMX script tags — they must also get nonces
6. Write tests that verify the CSP header is present and nonce is generated

**Run this task LAST within Sprint 67** since it touches all templates. Tasks A and B should complete first.

## Rules
- Work in worktree `sprint-67` (use EnterWorktree)
- Run `pytest tests/ --ignore=tests/test_tools.py -q` after each task
- Do NOT modify files owned by other sprints
- Commit after each task with descriptive message
- Run Task D LAST (it touches all templates)
- When all 4 tasks are done, report completion with test count

## File Ownership (Sprint 67 ONLY)
- `web/static/mobile.css` (67-A)
- `web/static/style.css` (67-B)
- `web/templates/admin_sources.html` (67-A)
- `web/templates/bottlenecks.html` (67-A: velocity dashboard)
- `web/templates/account.html` (67-B)
- `web/templates/fragments/account_*.html` (67-B)
- `web/templates/landing.html` (67-B)
- `web/templates/*.html` (67-D: nonce attributes ONLY — no content changes)
- `tests/e2e/` (67-C: new files)
- `web/security.py` (67-D)
- `web/routes_api.py` (67-D: CSP report endpoint ONLY)
- `web/app.py` (67-D: nonce context processor ONLY — minimal change)

Do NOT touch: `web/routes_cron.py`, `web/routes_search.py`, `web/routes_auth.py`, `web/routes_property.py`, `src/`, `scripts/`, `data/knowledge/`, `web/brief.py`, `web/data_quality.py`
