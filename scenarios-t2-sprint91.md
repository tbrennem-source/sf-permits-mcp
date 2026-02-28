# Scenarios — T2 Sprint 91 (Search Template Migration)

## SUGGESTED SCENARIO: public search results page loads for unauthenticated user

**Source:** search_results_public.html migration
**User:** homeowner
**Starting state:** User is not logged in and searches for an SF address
**Goal:** See permit history for a specific address without signing up
**Expected outcome:** A page with permit data renders, showing a search box pre-filled with the query, results or a "no results" state, and a CTA to sign up for more detail
**Edge cases seen in code:** No-results state shows guidance card with example searches; violation context mode shows enforcement data first
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: public search results handles non-existent address gracefully

**Source:** search_results_public.html — no_results branch
**User:** homeowner
**Starting state:** User searches for an address with no permit history
**Goal:** Find out if permits exist for their address
**Expected outcome:** A "No permits found" message is shown with guidance on how to search (by address, permit number, or block/lot), plus a "Sign up free" CTA
**Edge cases seen in code:** empty_guidance.suggestions may offer "Did you mean?" alternatives; empty_guidance.show_demo_link shows demo link
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: mobile intel toggle works on narrow viewports

**Source:** search_results_public.html — mobile-intel-toggle component
**User:** homeowner
**Starting state:** User on mobile (< 900px) views search results for an address with block/lot data
**Goal:** Access property intelligence panel on mobile
**Expected outcome:** A "Property intelligence" toggle button appears below the results; tapping it expands to show the intel panel with routing/entity data
**Edge cases seen in code:** Desktop shows sticky sidebar; mobile shows collapsible panel
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: enforcement violations shown with visual alert state

**Source:** search_results.html — intel-col--alert CSS class
**User:** expediter
**Starting state:** Searching an address that has open violations or complaints
**Goal:** Quickly identify enforcement risk on a property
**Expected outcome:** The enforcement column in the intel panel shows a visually distinct alert background (red-tinted border/background) and displays the count of open violations
**Edge cases seen in code:** `intel-col--alert` class applied when `enforcement_total > 0`; shows violation+complaint breakdown
**CC confidence:** high
**Status:** PENDING REVIEW
