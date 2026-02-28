# CHANGELOG — QS8-T3-D: E2E Onboarding + Performance Tests + Demo Seed Script

## Sprint: QS8 Terminal 3, Agent D
## Date: 2026-02-27
## Branch: worktree-agent-aad095bf

---

## New: tests/e2e/test_onboarding_scenarios.py

Added 8 Playwright E2E tests covering the onboarding and content-page user journeys:

- `TestWelcomePage::test_welcome_page_renders_for_new_user` — /welcome loads for authenticated user, contains onboarding content
- `TestWelcomePage::test_onboarding_dismissible` — user can navigate away from /welcome without loop
- `TestDemoPageAnonymous::test_demo_page_loads_without_auth` — /demo returns 200 for anonymous visitors
- `TestDemoPageAnonymous::test_demo_page_shows_property_data` — demo renders 1455 Market St data
- `TestDemoPageAnonymous::test_demo_page_has_structured_content` — demo has headings (not flat text blob)
- `TestMethodologyPage::test_methodology_page_has_multiple_sections` — /methodology has 2+ headings
- `TestMethodologyPage::test_methodology_page_no_auth_required` — /methodology is public
- `TestAboutDataPage::test_about_data_page_has_dataset_inventory` — /about-data contains dataset references
- `TestAboutDataPage::test_about_data_no_auth_required` — /about-data is public
- `TestBetaRequestForm::test_beta_request_form_renders` — email input present
- `TestBetaRequestForm::test_beta_request_form_submits` — valid submission produces no 500
- `TestBetaRequestForm::test_beta_request_invalid_email_rejected` — invalid email returns 400/422
- `TestPortfolioEmptyState::test_portfolio_empty_state_for_new_user` — empty portfolio shows guidance
- `TestPortfolioEmptyState::test_portfolio_anonymous_redirect` — anon users redirected from /portfolio

Follows established E2E patterns from test_severity_scenarios.py:
- Playwright skip guard (only runs when file is targeted or E2E_PLAYWRIGHT=1)
- `_screenshot()` helper (best-effort, never fails tests)
- `auth_page` and `page` fixtures from conftest.py
- Screenshot output to `qa-results/screenshots/e2e/`

---

## New: tests/e2e/test_performance_scenarios.py

Added 9 Playwright E2E tests covering response time budgets and security headers:

- `TestHealthEndpoint::test_health_endpoint_under_500ms` — /health responds in <500ms
- `TestHealthEndpoint::test_health_endpoint_returns_json` — /health returns valid JSON with status field
- `TestLandingPagePerformance::test_landing_page_under_1s` — / renders in <1s (warm)
- `TestMethodologyPerformance::test_methodology_under_1s` — /methodology renders in <1s
- `TestDemoPagePerformance::test_demo_page_under_2s` — /demo renders in <2s (cached)
- `TestSearchPerformance::test_search_returns_under_2s` — /search?q=... returns in <2s
- `TestRapidNavigationResilience::test_no_500_errors_on_rapid_navigation` — 5 pages visited quickly, no 500s
- `TestRapidNavigationResilience::test_no_500_errors_on_authenticated_pages` — auth pages handle rapid nav
- `TestSecurityHeaders::test_csp_headers_on_all_pages` — CSP header check (warn-only)
- `TestSecurityHeaders::test_x_frame_options_header` — clickjacking protection check (warn-only)
- `TestStaticAssetCaching::test_static_assets_cached` — CSS/JS have Cache-Control or ETag (warn-only)
- `TestStaticAssetCaching::test_static_css_returns_200` — at least one CSS file returns 200

Timing approach:
- Uses `time.monotonic()` around `page.goto()` for accurate measurement
- Warm-up request before measured request (primes Flask startup and DB cache)
- Security header checks are warn-only (headers may be set at CDN/proxy layer)

---

## New: scripts/seed_demo.py

Idempotent demo seed script for Zoom presentations and QA:

- `--email` (required): target user email
- `--dry-run` flag: prints actions without writing
- Supports both DuckDB (local) and Postgres (production) via `src.db.BACKEND`
- Step 1: Find or create user via `web.auth.get_user_by_email` / `create_user`
- Step 2: Add 3 watch items via `web.auth.add_watch` (idempotent via `check_watch`)
  - 1455 Market St — Block 3507 / Lot 004 — South of Market
  - 146 Lake St — Block 1386 / Lot 025 — Inner Richmond
  - 125 Mason St — Block 0312 / Lot 005 — Tenderloin
- Step 3: Append 5 demo recent searches to `activity_log` table
- Prints clear summary of what was added vs. skipped

Usage:
```bash
source .venv/bin/activate
python scripts/seed_demo.py --email tbrennem@gmail.com
python scripts/seed_demo.py --email demo@sfpermits.ai --dry-run
```

---

## Test Impact

- **New E2E tests**: 22+ Playwright tests across 2 files
- **Main test suite**: No impact — E2E tests are skip-guarded
- **Script verification**: `python -c "import scripts.seed_demo"` passes cleanly
- **Module imports**: All 3 new files import without errors in .venv

## Files Changed

| File | Action |
|------|--------|
| `tests/e2e/test_onboarding_scenarios.py` | NEW |
| `tests/e2e/test_performance_scenarios.py` | NEW |
| `scripts/seed_demo.py` | NEW |
| `scenarios-pending-review-qs8-t3-d.md` | NEW (per-agent output) |
| `CHANGELOG-qs8-t3-d.md` | NEW (per-agent output) |
