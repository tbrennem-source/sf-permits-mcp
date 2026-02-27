# Sprint 77-1: Severity + Property Health — Suggested Scenarios

_Agent: 77-1 | Session date: 2026-02-26_

---

## Design-Guide Scenario Coverage (this sprint's tests)

| Test | Scenarios covered |
|------|-------------------|
| test_property_report_loads_for_known_parcel | SCENARIO-1, 2a, 2b, 3 |
| test_property_report_contains_sections | SCENARIO-1, 3 |
| test_search_results_for_market_st | SCENARIO-16, 38 |
| test_portfolio_loads_for_expediter | SCENARIO-40 |
| test_portfolio_anonymous_redirected | SCENARIO-40 |
| test_brief_loads_for_authenticated_user | SCENARIO-1, 39 |
| test_brief_anonymous_redirected | SCENARIO-40 |
| test_demo_page_loads_without_auth | SCENARIO-27 (demo shows permit data) |

---

## SUGGESTED SCENARIO: Property report skips gracefully when DuckDB not ingested

**Source:** tests/e2e/test_severity_scenarios.py — TestPropertyReport
**User:** expediter
**Starting state:** Fresh checkout of the repo; `python -m src.ingest` has NOT been run; local DuckDB lacks the `permits` table
**Goal:** Developer runs the E2E test suite to validate their local environment
**Expected outcome:** Property report tests skip with a clear message ("DuckDB permits table absent — run python -m src.ingest") rather than failing with a raw Python traceback or an unhelpful assertion error
**Edge cases seen in code:** The route returns HTTP 500 with a DuckDB CatalogException when the table is missing; the test correctly distinguishes this known condition from a real app bug
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Demo page serves property intelligence without auth

**Source:** web/routes_misc.py — /demo route; tests/e2e/test_severity_scenarios.py — TestDemoPageAnonymous
**User:** homeowner (anonymous visitor)
**Starting state:** User has not logged in; they land on /demo from a marketing link
**Goal:** Preview property intelligence before creating an account
**Expected outcome:** Demo page loads with pre-populated 1455 Market St data. Page contains permit data, structured headings, and meaningful content. The density=max query parameter is accepted without error.
**Edge cases seen in code:** density_max param toggles a higher-density data view; should not error even with unexpected param values
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Morning brief lookback parameter accepts any valid range

**Source:** web/routes_misc.py — /brief route; web/templates/brief.html lookback toggle
**User:** expediter
**Starting state:** Authenticated expediter on the morning brief page
**Goal:** Switch lookback window using URL parameter (?lookback=7, ?lookback=30, ?lookback=90)
**Expected outcome:** All valid lookback values (1, 7, 30, 90) return HTTP 200. Values outside 1-90 are clamped (min 1, max 90). Non-integer values fall back to 1. The active lookback button reflects the current selection.
**Edge cases seen in code:** `max(1, min(int(lookback), 90))` — ValueError on non-numeric input defaults to 1
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Anonymous users cannot access brief or portfolio

**Source:** web/helpers.py — login_required decorator; SCENARIO-40
**User:** homeowner (anonymous / not logged in)
**Starting state:** User is not authenticated; tries to navigate directly to /brief or /portfolio
**Goal:** Check their permits without logging in
**Expected outcome:** Both /brief and /portfolio redirect to the login page. The redirect preserves the intended destination so post-login they land on the right page. No partial page content is shown.
**Edge cases seen in code:** /portfolio and /brief are listed in the login_required route list in app.py
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Search query for address returns results (or graceful empty state)

**Source:** web/routes_public.py — /search route; SCENARIO-38
**User:** homeowner
**Starting state:** Anonymous or authenticated user on the search page; enters partial address ("market")
**Goal:** Find permits at a known address
**Expected outcome:** Search returns at least one result card referencing the search term, OR displays a clear "no results" message. Never returns a blank page or Python traceback. XSS-escaped query is reflected safely in the page.
**Edge cases seen in code:** Empty q= param is handled; XSS injection in q= is sanitized (SCENARIO-34)
**CC confidence:** high
**Status:** PENDING REVIEW
