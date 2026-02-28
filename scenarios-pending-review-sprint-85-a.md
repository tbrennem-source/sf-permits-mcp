## SUGGESTED SCENARIO: API client fetches next station prediction for active permit
**Source:** web/routes_api.py — GET /api/predict-next/<permit_number>
**User:** expediter
**Starting state:** User is logged in; permit 202201234567 is active with addenda routing records
**Goal:** Retrieve a structured prediction of the permit's next review stations via API
**Expected outcome:** 200 JSON response with permit_number and result (markdown) fields; prediction includes probability, p50 days for top 3 next stations
**Edge cases seen in code:** Permit not found returns markdown error message (not 404); permit with no addenda returns "No routing data available" in the result markdown
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: API rejects unauthenticated request with 401
**Source:** web/routes_api.py — all 4 intelligence endpoints
**User:** homeowner
**Starting state:** User is not logged in (no session cookie)
**Goal:** Call any intelligence API endpoint without authentication
**Expected outcome:** 401 JSON response with {"error": "unauthorized"}; no tool execution occurs
**Edge cases seen in code:** All 4 endpoints (predict-next, stuck-permit, what-if, delay-cost) share identical auth check pattern
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: What-if endpoint compares base vs variation scenarios
**Source:** web/routes_api.py — POST /api/what-if
**User:** architect
**Starting state:** User is logged in; wants to compare kitchen remodel vs kitchen+bathroom addition
**Goal:** POST base_description and one variation to see side-by-side permit, timeline, fee, and revision risk comparison
**Expected outcome:** 200 JSON with result field containing markdown comparison table; delta summary shows changes in review path, timeline, and fees between base and variation
**Edge cases seen in code:** Empty base_description returns 400; variations must be a list (not a string); omitting variations entirely is valid and evaluates only the base scenario
**CC confidence:** high
**Status:** PENDING REVIEW
