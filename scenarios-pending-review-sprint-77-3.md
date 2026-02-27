# Sprint 77-3 Suggested Scenarios — Search + Entity

## SUGGESTED SCENARIO: authenticated address search returns permit results
**Source:** tests/e2e/test_search_scenarios.py / web/routes_search.py
**User:** expediter
**Starting state:** User is logged in. No search has been performed.
**Goal:** Search for a street name ("valencia") and see a list of matching permits.
**Expected outcome:** Search results page loads with permit data or a count of matching records. Page is not blank and contains permit-related content.
**Edge cases seen in code:** Authenticated users are redirected from /search to /?q= for the full experience. Test accommodates this redirect.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: permit number lookup returns meaningful response
**Source:** tests/e2e/test_search_scenarios.py / web/routes_search.py `_ask_permit_lookup`
**User:** expediter
**Starting state:** User is logged in. A permit-style number is entered into search.
**Goal:** Look up a specific permit by its number (e.g., 202101234567) and see the permit detail or a "not found" message.
**Expected outcome:** Page returns a result — either the permit detail, a "no results" message, or a search context explanation. Page must not show a server error.
**Edge cases seen in code:** If the permit number doesn't exist in the DB, the page should show a graceful "not found" state rather than crashing.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: empty search query handled gracefully
**Source:** tests/e2e/test_search_scenarios.py / web/routes_public.py `public_search`
**User:** homeowner
**Starting state:** User (authenticated or anonymous) submits a search with an empty query string.
**Goal:** The app handles the empty query without crashing.
**Expected outcome:** User is redirected to the landing/index page or sees a helpful guidance message. No server error or blank page.
**Edge cases seen in code:** Whitespace-only queries (?q=   ) are stripped and treated as empty. Anonymous users are redirected to index. Authenticated users also redirected.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: plan analysis upload form is present for authenticated users
**Source:** tests/e2e/test_search_scenarios.py / web/templates/index.html
**User:** architect
**Starting state:** User is logged in as an architect or any authenticated role.
**Goal:** Find and interact with the plan analysis upload form.
**Expected outcome:** The authenticated dashboard shows a file input element that accepts .pdf files. The plan/upload/analyze section is mentioned in the page content.
**Edge cases seen in code:** The file input has `accept=".pdf"` to restrict to PDF only. Max size is 400 MB as shown in the label text.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: methodology page is substantive and publicly accessible
**Source:** tests/e2e/test_search_scenarios.py / web/routes_misc.py or routes_public.py
**User:** homeowner (anonymous)
**Starting state:** No authentication. User navigates directly to /methodology.
**Goal:** Read about how SF Permits AI works — data sources, entity resolution, plan analysis.
**Expected outcome:** Page returns HTTP 200. Page contains at least 3 section headings (h2/h3). Mentions data sources, entity or search methodology, and plan analysis/AI vision. Page is not a stub.
**Edge cases seen in code:** Methodology page has a dedicated #plan-analysis section per template grep.
**CC confidence:** high
**Status:** PENDING REVIEW
