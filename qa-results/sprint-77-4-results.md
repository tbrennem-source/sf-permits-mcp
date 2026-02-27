# QA Results — Sprint 77-4: Auth + Mobile Scenarios

**Date:** 2026-02-26
**Agent:** 77-4
**Test file:** tests/e2e/test_auth_mobile_scenarios.py
**Duration:** 11.45s

## Summary

17 PASS / 0 FAIL / 0 BLOCKED

## Detailed Results

| # | Test | Status | Screenshot |
|---|------|--------|-----------|
| 1 | TestAnonymousLanding::test_landing_page_renders_for_anonymous | PASS | 77-4-1-landing-anonymous.png |
| 2 | TestAnonymousLanding::test_landing_mentions_permits | PASS | — |
| 3 | TestAuthRedirects::test_brief_redirects_anonymous | PASS | 77-4-2-brief-redirect.png |
| 4 | TestAuthRedirects::test_portfolio_redirects_anonymous | PASS | 77-4-2-portfolio-redirect.png |
| 5 | TestAuthRedirects::test_account_redirects_anonymous | PASS | 77-4-2-account-redirect.png |
| 6 | TestAuthRedirects::test_login_page_itself_is_accessible | PASS | 77-4-2-login-page.png |
| 7 | TestMobileNoHorizontalScroll::test_landing_no_horizontal_scroll_mobile | PASS | 77-4-3-mobile-landing.png |
| 8 | TestMobileNoHorizontalScroll::test_demo_no_horizontal_scroll_mobile | PASS | 77-4-3-mobile-demo.png |
| 9 | TestMobileNoHorizontalScroll::test_login_no_horizontal_scroll_mobile | PASS | 77-4-3-mobile-login.png |
| 10 | TestMobileNoHorizontalScroll::test_beta_request_no_horizontal_scroll_mobile | PASS | 77-4-3-mobile-beta-request.png |
| 11 | TestMobileNavigation::test_mobile_nav_exists_anonymous | PASS | 77-4-4-mobile-nav-anonymous.png |
| 12 | TestMobileNavigation::test_mobile_nav_authenticated | PASS | 77-4-4-mobile-nav-authenticated.png |
| 13 | TestBetaRequestForm::test_beta_request_page_loads | PASS | 77-4-5-beta-request-load.png |
| 14 | TestBetaRequestForm::test_beta_request_has_email_field | PASS | — |
| 15 | TestBetaRequestForm::test_beta_request_has_name_field | PASS | — |
| 16 | TestBetaRequestForm::test_beta_request_accepts_input_no_js_errors | PASS | 77-4-5-beta-request-filled.png |
| 17 | TestBetaRequestForm::test_beta_request_form_has_submit | PASS | — |

## Screenshots captured
qa-results/screenshots/sprint-77-4/ (13 PNG files)

## Blocked Items
None.

## Visual QA Checklist (for DeskRelay escalation)
No pages scored ≤2.0. Visual checks are informational only.
- Mobile landing (375px): nav visible, no overflow — PASS
- Mobile demo (375px): no horizontal scroll — PASS
- Beta request form: fields rendered correctly, submit button visible — PASS
- Auth redirect: login page renders with email input — PASS
