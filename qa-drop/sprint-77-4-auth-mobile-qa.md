# QA Script — Sprint 77-4: Auth + Mobile Scenarios

**Session:** Sprint 77-4
**Feature:** Auth boundaries + mobile viewport E2E coverage
**Generated:** 2026-02-26
**Run with:** `TESTING=1 TEST_LOGIN_SECRET=e2e-test-secret-local pytest tests/e2e/test_auth_mobile_scenarios.py -v`

---

## Steps

### 1. Anonymous landing renders
**Command:** `pytest tests/e2e/test_auth_mobile_scenarios.py::TestAnonymousLanding -v`
**PASS:** Both tests pass; screenshot `77-4-1-landing-anonymous.png` shows page with heading and search bar
**FAIL:** Any test fails or screenshot is blank

### 2. Auth redirects enforced
**Command:** `pytest tests/e2e/test_auth_mobile_scenarios.py::TestAuthRedirects -v`
**PASS:** All 4 tests pass; /brief, /portfolio, /account redirect to login; /auth/login returns 200
**FAIL:** Protected route serves content without auth, or /auth/login returns non-200

### 3. No horizontal scroll at 375px
**Command:** `pytest tests/e2e/test_auth_mobile_scenarios.py::TestMobileNoHorizontalScroll -v`
**PASS:** All 4 tests pass; scrollWidth <= innerWidth on all pages
**FAIL:** Any page overflows horizontally (scrollWidth > innerWidth)

### 4. Mobile navigation accessible
**Command:** `pytest tests/e2e/test_auth_mobile_scenarios.py::TestMobileNavigation -v`
**PASS:** Both tests pass; nav/hamburger/links present at 375px for anon and authenticated
**FAIL:** No navigation element found at mobile viewport

### 5. Beta request form functional
**Command:** `pytest tests/e2e/test_auth_mobile_scenarios.py::TestBetaRequestForm -v`
**PASS:** All 5 tests pass; form loads, has email+name+submit, accepts input without JS errors
**FAIL:** Form missing required fields, returns non-200, or JS errors on fill

### 6. Full suite (all 17 tests)
**Command:** `TESTING=1 TEST_LOGIN_SECRET=e2e-test-secret-local pytest tests/e2e/test_auth_mobile_scenarios.py -v`
**PASS:** 17 passed
**FAIL:** Any test fails

---

## Results (Sprint 77-4 run)

| Test | Status |
|------|--------|
| TestAnonymousLanding::test_landing_page_renders_for_anonymous | PASS |
| TestAnonymousLanding::test_landing_mentions_permits | PASS |
| TestAuthRedirects::test_brief_redirects_anonymous | PASS |
| TestAuthRedirects::test_portfolio_redirects_anonymous | PASS |
| TestAuthRedirects::test_account_redirects_anonymous | PASS |
| TestAuthRedirects::test_login_page_itself_is_accessible | PASS |
| TestMobileNoHorizontalScroll::test_landing_no_horizontal_scroll_mobile | PASS |
| TestMobileNoHorizontalScroll::test_demo_no_horizontal_scroll_mobile | PASS |
| TestMobileNoHorizontalScroll::test_login_no_horizontal_scroll_mobile | PASS |
| TestMobileNoHorizontalScroll::test_beta_request_no_horizontal_scroll_mobile | PASS |
| TestMobileNavigation::test_mobile_nav_exists_anonymous | PASS |
| TestMobileNavigation::test_mobile_nav_authenticated | PASS |
| TestBetaRequestForm::test_beta_request_page_loads | PASS |
| TestBetaRequestForm::test_beta_request_has_email_field | PASS |
| TestBetaRequestForm::test_beta_request_has_name_field | PASS |
| TestBetaRequestForm::test_beta_request_accepts_input_no_js_errors | PASS |
| TestBetaRequestForm::test_beta_request_form_has_submit | PASS |

**Total: 17 PASS, 0 FAIL** — 11.45s
