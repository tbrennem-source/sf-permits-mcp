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

## SUGGESTED SCENARIO: permit station badge shows current queue wait time
**Source:** web/helpers.py compute_triage_signals, web/templates/search_results_public.html
**User:** expediter
**Starting state:** Expediter searches for a property address that has an active permit in plan review at BLDG station for 45 days
**Goal:** Quickly assess how long the permit has been waiting without opening SF DBI portal
**Expected outcome:** A colored station badge appears in the search results showing "45d at BLDG" — amber because 45 days exceeds the 30-day median but is below the 2x (60-day) stuck threshold
**Edge cases seen in code:** Days exactly equal to median (30) shows amber, not green. Days exactly at 2x median (60) shows red and sets is_stuck=True.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: stuck permit indicator surfaces without false positives
**Source:** web/helpers.py classify_days_threshold, is_stuck logic
**User:** expediter
**Starting state:** Expediter searches for a property with a permit at SFFD-HQ for 89 days (SFFD-HQ median is 45d, 2x = 90d)
**Goal:** Know whether the permit is actually stuck or just moving slowly
**Expected outcome:** Badge shows "89d at SFFD-HQ" in amber (below 2x threshold of 90d). No "Stuck" indicator. At 90+ days, the "Stuck" indicator would appear.
**Edge cases seen in code:** Each station has a different median: BLDG=30d, SFFD-HQ=45d, CP-ZOC=60d, MECH-E=25d, ELEC=25d. Comparison uses station-specific threshold, not a global one.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: reviewer name shows on active plan review station
**Source:** web/helpers.py compute_triage_signals reviewer field, search_results_public.html triage-reviewer class
**User:** expediter
**Starting state:** Permit is at BLDG station with plan_checked_by = "ARRIOLA LAURA" in the addenda table
**Goal:** Know who is assigned to the permit so they can follow up directly
**Expected outcome:** The triage card shows "Reviewer: ARRIOLA LAURA" in a secondary text style below the station badge
**Edge cases seen in code:** reviewer is None when no plan_checked_by row exists — field is omitted from the card (not shown as "None" or blank label)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: triage signals absent when permit has no active station
**Source:** web/helpers.py compute_triage_signals — station_rows empty path
**User:** homeowner
**Starting state:** Permit was issued 10 days ago and is no longer in any active plan review station
**Goal:** User searches their address — expects to see permit status without confusing station timing info
**Expected outcome:** Triage card shows the permit number and status but no station badge or reviewer — the card renders without timing data (days_at_station is None, current_station is None)
**Edge cases seen in code:** is_stuck is always False when there is no station data. The card body renders conditionally: station badge block only shown if current_station is set.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: search page gracefully degrades when DB triage query fails
**Source:** web/routes_public.py triage_signals try/except, web/helpers.py compute_triage_signals try/except
**User:** homeowner
**Starting state:** DB is unavailable or throws an exception during the triage query (e.g., connection timeout)
**Goal:** User still gets their search results — triage is an enhancement, not a blocker
**Expected outcome:** Page renders with full AI search results and no triage panel visible. No error message shown. Error is silently caught.
**Edge cases seen in code:** Two catch layers: outer try/except in routes_public.py, and inner try/except inside compute_triage_signals itself.
**CC confidence:** high

## SUGGESTED SCENARIO: Question query routes to AI consultation not permit search
**Source:** Agent 3C — search routing + intent_router.py
**User:** homeowner
**Starting state:** User is on the public landing page, unauthenticated
**Goal:** Ask "Do I need a permit for a kitchen remodel?" in the search box
**Expected outcome:** Instead of "No permits found", user sees guidance that this is an AI-answerable question, with a prompt to sign up for AI consultation, not a failed literal permit lookup
**Edge cases seen in code:** Queries with construction context (kitchen, bathroom, ADU, garage, deck) + question prefix are classified as `question` intent; validate_plans and address patterns still take priority
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Validate query beats question intent
**Source:** Agent 3C — intent_router.py priority ordering
**User:** architect | expediter
**Starting state:** User types "how do I validate plans?" in search
**Goal:** Access the plan validation feature
**Expected outcome:** Query routes to validate_plans intent, not question/AI consultation — the validate keyword wins over question prefix detection
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Beta user property click goes to full search not loop
**Source:** Agent 3C — landing.html state machine
**User:** homeowner (beta tester, authenticated)
**Starting state:** User is on the landing page in beta state with a watched property shown
**Goal:** Click a watched property link (e.g., "487 Noe — PPC stalled 12d")
**Expected outcome:** User goes directly to the full search results page for that property, not back to the landing page via /search redirect loop
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Beta badge shows correct label for beta users
**Source:** Agent 3C — landing.html UX fixes
**User:** homeowner (beta tester)
**Starting state:** User is on landing page in beta state (via admin toggle)
**Goal:** See their account context clearly labeled
**Expected outcome:** Badge next to wordmark reads "Beta Tester" (not "beta"), giving a polished look for beta program participants
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Scroll-cue arrow is clearly visible after page load
**Source:** Agent 3C — landing.html UX fixes
**User:** homeowner (new visitor)
**Starting state:** User arrives on landing page, hero section is visible
**Goal:** Notice the call-to-action scroll arrow to see the showcase
**Expected outcome:** After 3.6s, the scroll cue arrow fades in and is visible at 60% opacity — noticeable without dominating the hero section
**CC confidence:** low
**Status:** PENDING REVIEW
