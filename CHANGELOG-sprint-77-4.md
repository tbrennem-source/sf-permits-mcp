# CHANGELOG — Sprint 77-4 (Agent 77-4: Auth + Mobile Scenarios)

## Sprint 77-4 — Auth + Mobile E2E Tests

### Added

- **`tests/e2e/test_auth_mobile_scenarios.py`** — 17 new Playwright E2E tests covering:

  **TestAnonymousLanding (2 tests)**
  - `test_landing_page_renders_for_anonymous` — Verifies h1 hero heading and search input present for anonymous users
  - `test_landing_mentions_permits` — Verifies "permit" appears in body content

  **TestAuthRedirects (4 tests)**
  - `test_brief_redirects_anonymous` — /brief redirects unauthenticated visitors to login
  - `test_portfolio_redirects_anonymous` — /portfolio redirects unauthenticated visitors to login
  - `test_account_redirects_anonymous` — /account redirects unauthenticated visitors to login
  - `test_login_page_itself_is_accessible` — /auth/login returns 200 and shows email input

  **TestMobileNoHorizontalScroll (4 tests)**
  - `test_landing_no_horizontal_scroll_mobile` — / no horizontal overflow at 375px
  - `test_demo_no_horizontal_scroll_mobile` — /demo no horizontal overflow at 375px
  - `test_login_no_horizontal_scroll_mobile` — /auth/login no horizontal overflow at 375px
  - `test_beta_request_no_horizontal_scroll_mobile` — /beta-request no horizontal overflow at 375px

  **TestMobileNavigation (2 tests)**
  - `test_mobile_nav_exists_anonymous` — Nav element/hamburger/links present at 375px (anonymous)
  - `test_mobile_nav_authenticated` — Nav accessible at 375px after login (homeowner persona)

  **TestBetaRequestForm (5 tests)**
  - `test_beta_request_page_loads` — /beta-request returns HTTP 200
  - `test_beta_request_has_email_field` — Email input present
  - `test_beta_request_has_name_field` — Name field or text input present
  - `test_beta_request_accepts_input_no_js_errors` — Filling fields produces no JS errors
  - `test_beta_request_form_has_submit` — Submit button present

### Test Results

All 17 tests PASSED in 11.45s (local Flask server, TESTING=1, TEST_LOGIN_SECRET=e2e-test-secret-local).

Screenshots captured to `qa-results/screenshots/sprint-77-4/`.

### File Ownership

- Created: `tests/e2e/test_auth_mobile_scenarios.py`
- Zero production files modified.
