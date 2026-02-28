## SUGGESTED SCENARIO: developer calculates delay cost for ADU project
**Source:** cost_of_delay.html / tools_cost_of_delay route
**User:** developer
**Starting state:** Developer is logged in and has a pending ADU permit with known monthly carrying costs (mortgage, opportunity cost).
**Goal:** Understand the total financial exposure from SF permit processing delays on their ADU project.
**Expected outcome:** Calculator accepts permit type "adu" and a monthly cost, calls the API, and renders a markdown breakdown of estimated delay costs with timeline percentiles.
**Edge cases seen in code:** API returns 400 if monthly_carrying_cost is 0 or negative — client-side validation must block submission before reaching the server.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: unauthenticated user blocked at gate
**Source:** tools_cost_of_delay route (g.user check + 401 handling in JS)
**User:** homeowner
**Starting state:** Visitor is not logged in and navigates directly to /tools/cost-of-delay.
**Goal:** Access the Cost of Delay Calculator.
**Expected outcome:** User is redirected to the login page (server-side redirect before the page renders). If they somehow reach the page and submit the form, a "you must be logged in" message appears inline with a link to log in.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: expediter adds neighborhood and delay triggers for precise estimate
**Source:** cost_of_delay.html — optional neighborhood and triggers inputs
**User:** expediter
**Starting state:** Expediter is logged in with a restaurant project in the Mission with known risk factors (active complaint, change of use).
**Goal:** Get a more accurate delay cost estimate by providing optional context.
**Expected outcome:** Form accepts neighborhood "Mission" and triggers "active complaint, change of use" as comma-separated values; API receives them as an array; result reflects the higher-risk scenario.
**Edge cases seen in code:** Triggers are split on comma and filtered for empty strings before JSON serialization.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: user submits with zero monthly cost
**Source:** cost_of_delay.html — client-side validation on monthly_carrying_cost
**User:** homeowner
**Starting state:** Homeowner is logged in and fills out the form with permit type "kitchen remodel" but enters "0" for monthly carrying cost.
**Goal:** Submit the form.
**Expected outcome:** Form does not submit. An inline error message appears below the monthly cost field stating the value must be greater than zero. No network request is made.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: result renders markdown cost breakdown
**Source:** cost_of_delay.html — marked.parse() call on API result
**User:** developer
**Starting state:** Developer is logged in and submits a valid request (permit type "commercial", monthly cost $8000, neighborhood "SoMa").
**Goal:** Read the AI-generated cost breakdown.
**Expected outcome:** The results area becomes visible. The markdown response is rendered as structured HTML — headings, bullet lists, bold currency values — not as raw markdown text.
**CC confidence:** high
**Status:** PENDING REVIEW
