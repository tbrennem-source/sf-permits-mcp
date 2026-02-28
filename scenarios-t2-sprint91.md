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
