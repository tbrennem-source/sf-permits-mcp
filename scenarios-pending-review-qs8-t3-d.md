# Scenarios Pending Review — QS8-T3-D (E2E Onboarding + Performance)

## SUGGESTED SCENARIO: welcome page onboarding flow for new user

**Source:** tests/e2e/test_onboarding_scenarios.py — TestWelcomePage
**User:** homeowner
**Starting state:** User has just verified their magic-link email for the first time. `onboarding_complete` is False in their user record.
**Goal:** User wants to get started using sfpermits.ai — understand what it does and how to add their first address.
**Expected outcome:** User lands on /welcome, sees 3-step onboarding guidance (search, report, watchlist), can proceed to the main app without being locked in a loop.
**Edge cases seen in code:** If `user.get("onboarding_complete")` is True, /welcome redirects to index — so returning users don't see the page again.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: demo page previews property intelligence without login

**Source:** tests/e2e/test_onboarding_scenarios.py — TestDemoPageAnonymous
**User:** homeowner
**Starting state:** Anonymous visitor arrives at /demo (e.g. from a Zoom demo link or marketing email).
**Goal:** Visitor wants to see what sfpermits.ai looks like without creating an account.
**Expected outcome:** /demo renders with 1455 Market St data pre-loaded — permits, severity tier, timeline estimate, neighborhood. No login prompt required. density=max parameter shows maximum data density.
**Edge cases seen in code:** Demo data is cached for 15 minutes (_DEMO_CACHE_TTL=900). If DuckDB permits table is empty, page still renders using hardcoded timeline fallback.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: methodology page explains calculations for skeptical users

**Source:** tests/e2e/test_onboarding_scenarios.py — TestMethodologyPage
**User:** expediter
**Starting state:** User has seen a severity tier on a property report and wants to understand how it was calculated.
**Goal:** User navigates to /methodology to verify the scoring approach is defensible.
**Expected outcome:** Page loads publicly (no auth), has multiple sections covering severity scoring, timeline estimation, entity resolution, and data sources.
**Edge cases seen in code:** Page is a static template render — no DB queries. Should be very fast.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: beta request form as organic signup path

**Source:** tests/e2e/test_onboarding_scenarios.py — TestBetaRequestForm
**User:** homeowner
**Starting state:** User tries to sign up but no invite code configured or code is invalid. Route logic redirects them to /beta-request.
**Goal:** User wants to request access to sfpermits.ai without an invite code.
**Expected outcome:** Form renders with email + reason fields. Honeypot field is invisible. Valid submission shows confirmation message. Invalid email (no @) returns 400 not 500.
**Edge cases seen in code:** Honeypot field named `website` — bots that fill it get silently "success" response. Rate limiting by IP. Empty reason field returns 400.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: portfolio empty state guidance for new user

**Source:** tests/e2e/test_onboarding_scenarios.py — TestPortfolioEmptyState
**User:** homeowner
**Starting state:** Newly onboarded user has not yet added any watch items.
**Goal:** User navigates to /portfolio expecting to see their watched properties.
**Expected outcome:** Page renders without crash. Shows an empty state with guidance on how to add a watch item — not a blank page or uncaught exception. Anonymous users are redirected to login.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: health endpoint responds under 500ms for Railway probe

**Source:** tests/e2e/test_performance_scenarios.py — TestHealthEndpoint
**User:** admin
**Starting state:** Railway health probe hits /health every ~30s. Response time determines instance health status.
**Goal:** System needs to respond reliably within Railway's health-check window.
**Expected outcome:** /health returns 200 with valid JSON containing a status field in under 500ms. If health check takes >500ms consistently, Railway marks instance unhealthy and restarts it.
**Edge cases seen in code:** Pool exhaustion (PoolError) causes health to fail. statement_timeout is set per connection.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: search results within 2s latency budget

**Source:** tests/e2e/test_performance_scenarios.py — TestSearchPerformance
**User:** expediter
**Starting state:** User types a street name into the search box on the landing page.
**Goal:** User expects results to appear quickly — ideally under 1s, definitely under 2s.
**Expected outcome:** /search?q=<address> returns 200 or redirect within 2s. Sprint 69 Hotfix added graceful degradation on query timeouts — 30s statement_timeout prevents hangs.
**Edge cases seen in code:** If DuckDB is not populated (CI/fresh checkout), search returns empty quickly. Postgres with missing pgvector index causes slow semantic search.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: rapid page navigation does not produce 500 errors

**Source:** tests/e2e/test_performance_scenarios.py — TestRapidNavigationResilience
**User:** expediter
**Starting state:** User clicks quickly between multiple pages (landing, methodology, about-data, demo, beta-request).
**Goal:** System handles burst navigation without connection pool exhaustion or session corruption.
**Expected outcome:** None of the 5 pages return 500. All pages return 200 or redirect. Flask sessions and g.user remain consistent across rapid sequential requests.
**Edge cases seen in code:** DB_POOL_MAX defaults to 20. If Flask is configured with threaded=True (used in tests), concurrent requests share the pool. DuckDB only allows one write connection at a time.
**CC confidence:** medium
**Status:** PENDING REVIEW
