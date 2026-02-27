# CHANGELOG — Sprint 77-1: Severity + Property Health E2E Scenarios

_Agent: 77-1 | Date: 2026-02-26_

## Added

### tests/e2e/test_severity_scenarios.py (NEW — 14 tests)

New Playwright E2E test file covering the severity scoring + property health
user journey. Tests are standalone-safe (skip in full pytest suite to avoid
asyncio conflicts; run with `pytest tests/e2e/test_severity_scenarios.py -v`).

**TestPropertyReport (3 tests)**
- `test_property_report_loads_for_known_parcel` — Navigates to /report/3507/004
  (1455 Market St parcel). Passes when DuckDB is populated; skips gracefully with
  a clear message when the `permits` table is absent (fresh checkout).
- `test_property_report_contains_sections` — Verifies the report template renders
  structured content (permits, complaints, risk cards) when data is available.
- `test_property_report_invalid_parcel_handled` — Confirms invalid block/lot does
  not produce an unexpected 500; distinguishes DuckDB-absent (skip) from real bug
  (fail) by inspecting the error body.

**TestSearchResultsSeverity (3 tests)**
- `test_search_results_for_market_st` — Search for "market" returns permit data or
  results context.
- `test_search_results_for_specific_address` — Search for "1455 Market St" returns
  targeted results.
- `test_search_empty_query_handled` — Empty search query returns 200 or 302, never
  a server error.

**TestPortfolioPageAuth (2 tests)**
- `test_portfolio_loads_for_expediter` — Authenticated expediter can access /portfolio
  without login redirect.
- `test_portfolio_anonymous_redirected` — Anonymous users are redirected away from
  /portfolio (SCENARIO-40).

**TestMorningBriefAuth (3 tests)**
- `test_brief_loads_for_authenticated_user` — Authenticated expediter lands on /brief
  and sees brief content (not a login redirect).
- `test_brief_lookback_parameter_accepted` — /brief?lookback=7 returns HTTP 200.
- `test_brief_anonymous_redirected` — Anonymous users are redirected away from /brief.

**TestDemoPageAnonymous (3 tests)**
- `test_demo_page_loads_without_auth` — /demo returns 200 with permit data for
  anonymous visitors.
- `test_demo_page_has_property_content` — Demo page has structured headings and
  meaningful content.
- `test_demo_page_density_param_handled` — /demo?density=max accepted without error.

## Test Results (local, 2026-02-26)

```
8 passed, 6 skipped in 3.99s
```

Skips:
- 3 property report tests: DuckDB `permits` table absent (local dev without ingest)
- 3 auth tests: TEST_LOGIN_SECRET not set (expected in local dev)

No failures. Tests are resilient to local-dev conditions.

## Scenarios Written

5 scenarios appended to `scenarios-pending-review-sprint-77-1.md`:
1. Property report graceful skip when DuckDB not ingested
2. Demo page serves property intelligence without auth
3. Morning brief lookback parameter accepts any valid range
4. Anonymous users cannot access brief or portfolio
5. Search query for address returns results (or graceful empty state)
