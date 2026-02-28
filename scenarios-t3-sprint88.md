# Agent 3B — Scenarios (Sprint QS10-T3)

## SUGGESTED SCENARIO: expediter diagnoses a stalled permit
**Source:** stuck_permit.html / tools_stuck_permit route
**User:** expediter
**Starting state:** Expediter is logged in. They have a permit number for a project that has not moved in 90+ days.
**Goal:** Understand why the permit is stuck and get a prioritized list of actions to unstick it.
**Expected outcome:** User enters permit number, submits, and receives a ranked intervention playbook in readable form explaining probable delay causes and concrete next steps. Response renders correctly with no raw markdown visible.
**Edge cases seen in code:** API returns markdown text in `result` field — marked.js parses it; if marked not loaded, a pre-formatted fallback is shown.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: unauthenticated user attempts to use stuck permit analyzer
**Source:** tools_stuck_permit route (auth guard) / 401 handling in stuck_permit.html
**User:** homeowner
**Starting state:** User is not logged in (no active session). They navigate directly to the stuck permit analyzer tool.
**Goal:** Access the analyzer to diagnose their permit.
**Expected outcome:** User is redirected to the login page without seeing the tool UI. If they somehow reach the page and trigger the API call without session, a login prompt appears in the results area (not a raw 401 error).
**Edge cases seen in code:** Route-level redirect (302) for unauthenticated GET; JS 401 handler renders auth prompt inline for any race conditions.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: user enters an invalid or unknown permit number
**Source:** stuck_permit.html error handling
**User:** homeowner
**Starting state:** User is logged in. They type an invalid or non-existent permit number and click Diagnose.
**Goal:** Get information about their permit even with an incorrect number.
**Expected outcome:** User sees a clear error message (not a crash or blank screen) indicating the analysis failed. The error message is rendered in the results area with contextual styling.
**Edge cases seen in code:** API may return 500 with `{"error": "..."}` — JS catch block renders the error.message; empty permit number short-circuits before making the API call.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: user navigates to stuck permit analyzer on mobile
**Source:** stuck_permit.html responsive styles
**User:** expediter
**Starting state:** User is on a mobile device (375px viewport), logged in.
**Goal:** Use the stuck permit analyzer on the go.
**Expected outcome:** Input field and diagnose button stack vertically and fill the full width. Page renders without horizontal overflow. Results playbook is readable.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: playbook renders rich markdown with headers and lists
**Source:** stuck_permit.html — marked.js integration + .playbook-content styles
**User:** architect
**Starting state:** User is logged in. The stuck permit API returns a multi-section markdown playbook with headers, bullet lists, and bold text.
**Goal:** Read a structured intervention plan for their client's delayed permit.
**Expected outcome:** Markdown is parsed and displayed as formatted HTML — headers use the sans-serif type stack, code spans use monospace, bullet lists are indented. No raw markdown characters (**, ##, *, `) are visible to the user.
**CC confidence:** medium
**Status:** PENDING REVIEW
