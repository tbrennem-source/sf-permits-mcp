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
**CC confidence:** medium
**Status:** PENDING REVIEW
