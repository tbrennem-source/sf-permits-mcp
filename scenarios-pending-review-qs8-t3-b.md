# Scenarios — QS8 T3-B: Search NLP Parser + Empty Result Guidance + Result Ranking

## SUGGESTED SCENARIO: natural language address query resolves correctly

**Source:** web/helpers.py parse_search_query, web/routes_public.py public_search
**User:** homeowner
**Starting state:** User is on /search and types a natural language query that contains a street address embedded in prose
**Goal:** Find permit records for their property using a plain-English description like "permits at 123 Market St"
**Expected outcome:** Permit records for 123 Market St are returned, not a "no results" page, even though the query wasn't a bare address
**Edge cases seen in code:** Intent router may classify as "analyze_project" if query contains action verbs — NLP parser upgrades to "search_address" when it finds street_number + street_name
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: neighborhood-scoped search shows guidance

**Source:** web/helpers.py parse_search_query, build_empty_result_guidance
**User:** expediter
**Starting state:** User searches "kitchen remodel in the Mission" with no specific address
**Goal:** Filter permit results to Mission neighborhood, or get helpful guidance on how to search
**Expected outcome:** Either filtered results are shown OR, if no results, contextual suggestions are shown that match the query intent (neighborhood + permit type)
**Edge cases seen in code:** "Mission" alias maps to "Mission" neighborhood; "in the Mission" prep phrase is stripped before passing residual text as description_search
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: zero results shows demo link and contextual suggestions

**Source:** web/routes_public.py public_search, web/helpers.py build_empty_result_guidance
**User:** homeowner
**Starting state:** User searches for something that returns no permit records
**Goal:** Get guidance on what to try next, not a dead end
**Expected outcome:** Page shows "No permits found", a contextual "Did you mean?" hint if applicable, example search links matching the query intent, and a link to /demo
**Edge cases seen in code:** build_empty_result_guidance inspects parsed dict to generate query-specific suggestions (not generic boilerplate)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: year filter extracted from natural language query

**Source:** web/helpers.py parse_search_query (_YEAR_RE)
**User:** expediter
**Starting state:** User types "new construction SoMa 2024"
**Goal:** Find new construction permits in South of Market filed in 2024
**Expected outcome:** parse_search_query returns neighborhood="South of Market", permit_type="new construction", date_from="2024-01-01"
**Edge cases seen in code:** Year must be in 2018-2030 range; year is extracted BEFORE address to prevent "2022" being parsed as a street number
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: result badges distinguish address vs permit vs description matches

**Source:** web/helpers.py rank_search_results
**User:** expediter
**Starting state:** Search returns a mix of exact address matches, permit number matches, and description keyword matches
**Goal:** Quickly identify which results are the most relevant
**Expected outcome:** Each result has a badge ("Address Match", "Permit", or "Description") and results are sorted with address matches first, then permit number matches, then description matches
**Edge cases seen in code:** badge is computed per result; _rank_score removed before returning; ties within same type maintain original order
**CC confidence:** medium
**Status:** PENDING REVIEW
