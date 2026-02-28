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
# Sprint 91 T2 — Suggested Scenarios

## SUGGESTED SCENARIO: Property report loads with Obsidian design system
**Source:** web/templates/report.html migration
**User:** homeowner | expediter
**Starting state:** User navigates to a property report URL (e.g. /report/3512/035)
**Goal:** View the full property permit history, risk assessment, and intel grid
**Expected outcome:** Page renders with consistent dark Obsidian theme, correct font hierarchy (--mono for data values like permit numbers, --sans for prose/labels), status dots in correct signal colors, no visual artifacts from CSS variable conflicts
**Edge cases seen in code:** Empty permits array renders "No permits found" empty state; error state renders with back-to-search CTA; is_owner mode shows owner banner with tailored recommendations
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Station predictor returns routing forecast
**Source:** web/templates/tools/station_predictor.html
**User:** expediter | homeowner
**Starting state:** User is logged in and navigates to the station predictor tool
**Goal:** Enter a permit number and see the predicted next review stations
**Expected outcome:** Input accepts a permit number, prediction loads asynchronously, results render as formatted markdown with station names and timing estimates, error message shown if permit not found
**Edge cases seen in code:** 401 response shows auth prompt with login link; empty permit number input triggers client-side validation; spinner shown during async fetch
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Stuck permit analyzer diagnoses delays
**Source:** web/templates/tools/stuck_permit.html
**User:** expediter | homeowner
**Starting state:** User is logged in and navigates to the stuck permit analyzer
**Goal:** Diagnose why a permit is stalled and get an intervention playbook
**Expected outcome:** Input accepts a permit number, analysis loads with loading indicator, result shows permit number with amber status dot, playbook content renders with ranked intervention steps in markdown
**Edge cases seen in code:** 401 response renders auth prompt; fetch error renders error message; Enter key triggers diagnosis; loading indicator uses pulse-dot animation with signal-amber color
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Property report risk assessment section
**Source:** web/templates/report.html — risk-item, severity-chip components
**User:** homeowner | expediter
**Starting state:** User views a property report for a property with active risk factors
**Goal:** Understand what risks are flagged for this property
**Expected outcome:** Risk items shown with severity chips (high/moderate/low/clear), high-severity items appear in "Needs attention" action items at top of page, KB citations shown as linked chips, cross-reference links work
**Edge cases seen in code:** "No known risks" clears state shown with severity-chip--clear; risk-item--none variant for zero-risk properties
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Property report owner mode
**Source:** web/templates/report.html — owner-banner, remediation-roadmap, consultant-callout
**User:** homeowner
**Starting state:** User visits /report with ?owner=1 parameter while logged in
**Goal:** See property recommendations tailored for the owner (remediation roadmap, consultant signal)
**Expected outcome:** Owner banner displayed, remediation roadmap section visible with effort options and source citations, consultant callout reflects risk level (warm/recommended/strongly_recommended/essential)
**Edge cases seen in code:** is_owner flag toggles "This is my property" nav CTA; consultant signal can be 'cold' (hidden) or progressive urgency levels
**CC confidence:** medium
**Status:** PENDING REVIEW
