## SUGGESTED SCENARIO: station predictor happy path — active permit
**Source:** station_predictor.html / tools_station_predictor route
**User:** expediter
**Starting state:** Authenticated user has a permit number for a currently active permit in the DBI system.
**Goal:** Quickly see which review stations the permit will likely pass through next, to plan client communication and set expectations.
**Expected outcome:** Predicted routing stations are displayed in formatted markdown. The result shows the permit number back to the user and a sequence of likely upcoming stations with any relevant commentary.
**Edge cases seen in code:** API returns {"permit_number": str, "result": str (markdown)} — result must be parsed and rendered as markdown, not raw text.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor — unauthenticated access redirects to login
**Source:** station_predictor.html / tools_station_predictor route
**User:** homeowner
**Starting state:** Unauthenticated user navigates directly to the Station Predictor URL.
**Goal:** Access the station predictor tool.
**Expected outcome:** User is redirected to the login page without seeing any permit data. After logging in, they can return to the tool.
**Edge cases seen in code:** Route checks g.user and redirects to /auth/login if falsy. The client-side JavaScript also handles 401 API responses with a "Please log in" message for any JS-initiated calls before the redirect fires.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor — invalid or nonexistent permit number
**Source:** station_predictor.html / tools_station_predictor route
**User:** expediter
**Starting state:** Authenticated user enters a permit number that does not exist in the system or is malformed.
**Goal:** Get routing prediction for what turns out to be an invalid permit.
**Expected outcome:** An error message is displayed in the results area. The tool does not crash. User can enter a different permit number and try again without page reload.
**Edge cases seen in code:** API returns {"error": "..."} on failure; client-side showError() renders it. Empty input triggers a client-side validation message before the fetch fires.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor — markdown result rendering
**Source:** station_predictor.html / tools_station_predictor route
**User:** architect
**Starting state:** Authenticated user submits a valid permit number. The API returns a richly formatted markdown response with headers, bullets, and code spans for station names.
**Goal:** Read the predicted routing in a clear, formatted view.
**Expected outcome:** Markdown is rendered as HTML — headers appear as styled headings, bullet lists render as bullets, station code spans appear in monospace. Raw markdown text is never shown to the user.
**Edge cases seen in code:** Template uses marked.js with a fallback to <pre> if marked is unavailable. Code spans styled with --mono font family and --accent color.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor — Enter key submits the form
**Source:** station_predictor.html / tools_station_predictor route
**User:** expediter
**Starting state:** Authenticated user has typed a permit number into the input field.
**Goal:** Submit the prediction request by pressing Enter rather than clicking the button.
**Expected outcome:** The prediction fires when Enter is pressed in the permit number field, identical to clicking the button. This matches the expected keyboard workflow for power users.
**Edge cases seen in code:** keydown listener on the input checks for e.key === 'Enter' and calls runPrediction().
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
