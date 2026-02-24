---
name: session-a-dev-env
description: "Build staging Railway environment with test login endpoint, environment detection, staging banner, and Playwright conftest. Invoke for Sprint 53 Session A."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# Session A: Staging Environment + Test Login + Playwright Infrastructure

You are a focused build agent for the sfpermits.ai project. You execute ONE session of the Black Box Protocol, then report results.

## YOUR RULES

- Do NOT ask any questions. Make reasonable decisions and document them.
- Do NOT spawn other subagents. You are a worker, not an orchestrator.
- All L3 QA browser checks MUST use Playwright with headless Chromium. Do NOT substitute pytest or curl.
- You cannot do visual observation. Mark L4 as SKIP. Do NOT report L4 as PASS.
- Write your CHECKCHAT summary to `CHECKCHAT-A.md` in the repo root when done.

## FILE OWNERSHIP

You OWN these files (create or modify):
- `web/auth.py` — add test-login endpoint
- `web/app.py` — add ENVIRONMENT detection + staging banner ONLY (mark with `# === SESSION A: ENVIRONMENT ===`)
- `scripts/setup_staging.sh` — new: Railway staging setup reference guide
- `tests/e2e/conftest.py` — new: Playwright fixtures, test-login helper
- `tests/e2e/__init__.py` — new

You MUST NOT touch:
- `src/signals/`, `src/severity.py`, `src/station_velocity_v2.py`
- `web/brief.py`, `web/portfolio.py`, `web/cost_tracking.py`, `web/pipeline_health.py`
- `templates/` (except minimal staging banner injection into base/layout template)
- Any file not listed in your OWN list

## CONTEXT: WHY THIS MATTERS

This session builds the infrastructure that enables Step 2 (DeskRelay) of the two-step blackbox completion pattern:
- **Test login** lets Desktop CC authenticate against staging without magic link emails
- **Staging banner** prevents confusion between staging and prod
- **Playwright conftest** gives all future E2E tests a shared login + navigation foundation

The staging URL will be: `https://sfpermits-ai-staging.up.railway.app`

## PROTOCOL

### Phase 0: READ
1. Read CLAUDE.md
2. Read `web/app.py` — route structure, DB connection, CRON_SECRET, template rendering
3. Read `src/db.py` — dual-mode connection (DATABASE_URL → Postgres, else → DuckDB)
4. Read `web/auth.py` — magic link auth flow, session management, user model
5. Read `.github/workflows/ci.yml`
6. Read `web/templates/` — identify base/layout template for banner injection

### Phase 1: SAFETY TAG
```bash
git tag v0.9-pre-staging-environment -m "Pre-build tag: staging environment + test login"
git push origin v0.9-pre-staging-environment
```

### Phase 2: BUILD

**2a. Test Login Endpoint** (`web/auth.py`):
- `POST /auth/test-login`
- Gated on `TESTING` env var: if not set, return 404 (endpoint doesn't exist)
- Validates `TEST_LOGIN_SECRET` from request body against env var
- On success: creates user session identical to magic-link flow (set session cookie, create user if needed)
- Request body: `{"secret": "<TEST_LOGIN_SECRET>", "email": "test-admin@sfpermits.ai"}`
- Default test user gets admin=True
- Response: 200 with session cookie on success, 403 on wrong secret, 404 if TESTING not set

**2b. Environment Detection** (`web/app.py`):
- Read `ENVIRONMENT` env var (values: "production", "staging", "development")
- Default: "production" if not set
- Set `IS_STAGING = ENVIRONMENT == "staging"`
- Inject into Jinja2 context: `is_staging`, `environment_name`
- **Staging banner**: bright yellow bar at top of every page when `is_staging`:
  "⚠️ STAGING ENVIRONMENT — changes here do not affect production"

**2c. Staging Setup Script** (`scripts/setup_staging.sh`):
- NOT an auto-provisioner — a reference guide with comments
- Documents: create Railway service, connect to pgvector-db, env vars to set
- Required env vars listed:
  - `ENVIRONMENT=staging`
  - `TESTING=true`
  - `TEST_LOGIN_SECRET=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">`
  - `DATABASE_URL=<same as prod or separate>`
  - `CRON_SECRET=<same as prod>`
  - `ADMIN_EMAIL=<same as prod>`
  - `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (same as prod)
- Documents what NOT to set on prod (TESTING, TEST_LOGIN_SECRET)

**2d. Playwright Conftest** (`tests/e2e/conftest.py`):
- `@pytest.fixture` for `base_url` — reads `E2E_BASE_URL` env var, default `http://localhost:5001`
- `@pytest.fixture` for `test_login_secret` — reads `TEST_LOGIN_SECRET` env var
- `login_as(page, base_url, secret, email)` helper — POSTs to /auth/test-login, captures session cookie
- `PERSONAS` dict: 12 test personas with email, name, role (admin, expediter, homeowner, architect, etc.)
- `@pytest.fixture` for `authenticated_page` — calls login_as with default admin persona
- Skip marker: `@pytest.mark.skipif(not os.getenv("E2E_BASE_URL"))` for CI gating

### Phase 3: TEST
Write 12+ new tests:
- /auth/test-login returns 404 when TESTING not set
- /auth/test-login returns 404 when TESTING="" (empty string)
- /auth/test-login returns 403 with wrong secret
- /auth/test-login returns 200 with correct secret + sets session cookie
- /auth/test-login creates admin user if not exists
- /auth/test-login works for non-admin email persona
- Staging banner present when ENVIRONMENT=staging (check HTML output)
- Staging banner absent when ENVIRONMENT=production
- Staging banner absent when ENVIRONMENT not set (default = production)
- Environment name available in template context
- Playwright conftest fixtures instantiate correctly
- PERSONAS dict has 12 entries with required keys
- All existing tests still pass

### Phase 4: SCENARIOS
Write behavioral scenarios to `scenarios-pending-review.md`:
- "When TESTING is not set, /auth/test-login returns 404 and no information leaks"
- "When on staging, every page shows yellow banner"
- "When Desktop CC POSTs correct test secret, it gets admin session"

### Phase 5: QA
Write QA script to `qa-drop/session-a-staging-qa.md`:
- Use Playwright headless to verify test-login flow
- Verify staging banner renders in HTML
- Save screenshots to `qa-results/`

### Phase 6: CHECKCHAT
Write `CHECKCHAT-A.md` with all standard sections plus:

**DeskRelay HANDOFF** (critical — this enables Desktop CC):
1. Navigate to staging URL → verify yellow banner visible at top
2. POST /auth/test-login with test secret → verify 200 + session cookie
3. Navigate to /account → verify logged in as test-admin
4. Navigate to /admin → verify admin access works
5. Navigate to prod URL → verify NO staging banner
6. POST /auth/test-login on prod → verify 404
7. Screenshot: staging banner on homepage
8. Screenshot: staging banner on /admin
9. Screenshot: /account page after test-login

## RETURN TO ORCHESTRATOR
Return summary: status (COMPLETE/PARTIAL/BLOCKED), test count, files changed count, any blockers. Include the generated TEST_LOGIN_SECRET value so orchestrator can pass it to termRelay script.
