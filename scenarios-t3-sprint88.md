## SUGGESTED SCENARIO: what-if base project only, no variations
**Source:** what_if.html / tools_what_if route
**User:** expediter
**Starting state:** Authenticated user on the What-If Simulator page with no input
**Goal:** Analyze a base project description to understand its permit implications without comparing variations
**Expected outcome:** After entering a base project description and submitting, the simulator returns a structured analysis of the project's expected timeline, fees, and revision risk without requiring any variation input
**Edge cases seen in code:** Variations array can be empty — API accepts base_description alone; empty variations are excluded from the JSON body
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: what-if comparison with two variations
**Source:** what_if.html / tools_what_if route
**User:** architect
**Starting state:** Authenticated user on the What-If Simulator page; user is evaluating two design options for a client's project
**Goal:** Compare how two different project scopes (e.g., ADU with and without solar panels) would differ in timeline, fees, and revision risk
**Expected outcome:** After entering a base description and two labeled variations, the simulator returns a side-by-side comparison table showing how each variation changes the projected timeline, fees, and revision risk relative to the base
**Edge cases seen in code:** Variations with empty label get auto-labeled (A, B, C); max 3 variations enforced in UI
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: what-if unauthenticated access redirects to login
**Source:** tools_what_if route in web/routes_search.py
**User:** homeowner
**Starting state:** User is not logged in and navigates directly to the What-If Simulator URL
**Goal:** Access the What-If Simulator
**Expected outcome:** User is redirected to the login page; after logging in, they can access the simulator
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: what-if 401 error shows login prompt inline
**Source:** what_if.html — fetch error handling
**User:** expediter
**Starting state:** Authenticated user's session expires while on the What-If Simulator page
**Goal:** Submit a simulation after session expiry
**Expected outcome:** The simulator displays a friendly prompt to log in again (inline in the results area) rather than a cryptic error or a full page redirect
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: what-if variation add/remove flow
**Source:** what_if.html — variation JS logic
**User:** architect
**Starting state:** Authenticated user on the What-If Simulator with one variation visible (Variation A)
**Goal:** Add a second and third variation, remove the second, then submit with only the first and third
**Expected outcome:** The Add Variation button is disabled after three variations are shown; removing a variation hides it and clears its fields; the simulation submission includes only the variations that are currently visible and have content
**Edge cases seen in code:** Max 3 variations; remove button clears field values; visible count tracked to gate Add button
**CC confidence:** medium
**Status:** PENDING REVIEW
