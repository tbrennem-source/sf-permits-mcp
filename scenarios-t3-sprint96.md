# QS12 T3 Sprint Scenarios

## SUGGESTED SCENARIO: anonymous user discovers tool from landing page
**Source:** Agent 3A — tool page public access
**User:** homeowner
**Starting state:** User arrives at landing page via search result or word of mouth, sees "Station Predictor" showcased, clicks "Try it yourself"
**Goal:** Preview what the Station Predictor tool does without creating an account
**Expected outcome:** User lands on the Station Predictor page, sees demo data pre-loaded or empty state with hint text, can click demo permit chips to see sample output — no login wall
**Edge cases seen in code:** ?permit= query param auto-fills and runs the prediction on page load; demo chips call fillDemo()
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: anonymous user sees soft CTA after interacting with tool
**Source:** Agent 3A — tool page public access / anon-cta block
**User:** homeowner
**Starting state:** Anonymous user has been using a tool page (station predictor, stuck permit, what-if, or cost of delay) and found it useful
**Goal:** Convert from anonymous visitor to signed-up user
**Expected outcome:** A non-blocking CTA is visible on the page linking to /beta/join ("Sign up free →") — it does not interrupt tool use, appears below the results area, and is absent for already-signed-in users
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: authenticated user sees no soft CTA
**Source:** Agent 3A — anon CTA gated with {% if not g.user %}
**User:** expediter (logged in)
**Starting state:** Authenticated user navigates to any of the 4 tool pages
**Goal:** Use the tool without any signup noise
**Expected outcome:** The "Sign up free" CTA is not present in the rendered HTML; tool functions fully without any anonymous-mode restrictions
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: anonymous user tries to submit a tool form (API auth requirement)
**Source:** Agent 3A — API endpoints may still require auth even though page is public
**User:** homeowner
**Starting state:** Anonymous user navigates to a tool page, enters permit number or parameters, and submits
**Goal:** Understand what happens when the underlying API requires authentication
**Expected outcome:** Tool page renders successfully (200); if the underlying API returns 401, the template shows an inline auth prompt within the results area (not a page redirect) — user is invited to log in without losing context
**Edge cases seen in code:** JS fetch handlers catch 401 and call showAuthPrompt() inline
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: all 6 tool routes accessible without login
**Source:** Agent 3A — parity between entity-network/revision-risk (already public) and the 4 newly public routes
**User:** architect
**Starting state:** Anonymous user has bookmarked any tool URL
**Goal:** Reach the tool page directly without being intercepted by a login wall
**Expected outcome:** All 6 /tools/* routes return 200 for anonymous users; none redirect to /auth/login
**CC confidence:** high
**Status:** PENDING REVIEW
