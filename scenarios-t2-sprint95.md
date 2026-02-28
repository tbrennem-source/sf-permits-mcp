## SUGGESTED SCENARIO: Amy scans permit list and sees human-readable filed dates
**Source:** src/tools/permit_lookup.py — _format_permit_list
**User:** expediter
**Starting state:** Amy searches for a property address and sees the permit history table
**Goal:** Quickly scan filed dates across 20 permits to understand project timeline
**Expected outcome:** All dates display as "Mon D, YYYY" (e.g., "Apr 28, 2025") — not ISO timestamps like "2025-04-28T12:53:40.000"
**Edge cases seen in code:** Some permits have None filed_date — should show "—"
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Amy reads permit type without needing to decode DB values
**Source:** src/tools/permit_lookup.py — _format_permit_list, _format_permit_detail
**User:** expediter
**Starting state:** Permit records contain mixed-case type values from DB ("otc alterations permit", "NEW CONSTRUCTION")
**Goal:** Understand what type of permit was filed without decoding internal DB casing
**Expected outcome:** All permit type values display in Title Case (e.g., "Otc Alterations Permit", "Electrical Permit") regardless of how they were stored in the database
**Edge cases seen in code:** Some types already Title Case (should not be double-cased); None values show empty string
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Amy sees cost field explanation for electrical/plumbing permits
**Source:** src/tools/permit_lookup.py — _format_permit_list (has_missing_cost logic)
**User:** expediter
**Starting state:** A property has multiple permits — some building permits with cost estimates, some electrical/plumbing permits with no cost field
**Goal:** Understand why some rows show "—" in the cost column without confusion
**Expected outcome:** When any permit in the list has no cost estimate, a footnote appears below the table explaining "Cost shows — for permit types where SF DBI does not require a cost estimate (e.g., electrical, plumbing, and mechanical permits)."
**Edge cases seen in code:** When ALL permits have costs, no footnote is shown
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Intel panel shows formatted routing date
**Source:** web/templates/search_results.html — routing_latest_date display
**User:** expediter
**Starting state:** An address has a permit in plan review with recent routing activity
**Goal:** See when the most recent plan review step completed
**Expected outcome:** The date in the property intelligence panel routing section shows as "Mon D, YYYY" format, not "YYYY-MM-DD"
**Edge cases seen in code:** routing_latest_date can be None — should show nothing in that case
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Intel panel shows title-cased latest permit type
**Source:** web/templates/search_results.html — latest_permit_type display
**User:** expediter
**Starting state:** Address intel panel shows the most recent permit type filed at a property
**Goal:** Read the permit type without seeing raw DB casing
**Expected outcome:** "latest_permit_type" in the permits column shows in Title Case regardless of DB storage format
**Edge cases seen in code:** None value → shows nothing (not "None" literal)
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor pre-fill from URL
**Source:** web/templates/tools/station_predictor.html — DOMContentLoaded ?permit= handler
**User:** expediter
**Starting state:** User has been given a permit number (e.g. from search results) and navigates to /tools/station-predictor?permit=202509155257
**Goal:** See the station prediction without having to manually enter the permit number
**Expected outcome:** The permit input is pre-filled with the number from the URL, and the prediction runs automatically without user interaction
**Edge cases seen in code:** Empty ?permit= param is handled gracefully (no spurious API call); malformed permit triggers error state, not crash
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor stalled permit banner
**Source:** web/templates/tools/station_predictor.html — buildStalledBanner function
**User:** expediter
**Starting state:** User enters a permit number that is stalled at a review station (dwell >60 days with no finish_date)
**Goal:** Understand quickly that the permit is stalled and what action to take
**Expected outcome:** A visible warning banner appears above the Gantt chart identifying the stall and providing DBI's phone number as the next step
**Edge cases seen in code:** Banner only appears when STALLED keyword is present in markdown; normal permits show no banner
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor gantt click-to-expand
**Source:** web/static/js/gantt-interactive.js — attachEvents, toggleDetail
**User:** expediter
**Starting state:** Station predictor has returned results and rendered a Gantt chart with multiple station bars
**Goal:** See detailed information about a specific predicted station (probability, typical wait, dwell range)
**Expected outcome:** Clicking a Gantt bar or station row expands a detail panel showing dwell days, probability percentage, typical wait time (p50), and p25-p75 range; clicking again collapses it; clicking a different bar collapses the previously open one
**Edge cases seen in code:** Keyboard navigation via Enter/Space key also toggles; aria-hidden is managed for screen readers
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: stuck permit intervention playbook structured rendering
**Source:** web/templates/tools/stuck_permit.html — renderResult, buildPlaybookSteps
**User:** expediter
**Starting state:** User runs stuck permit analysis on a permit with comments issued at BLDG station
**Goal:** Get a prioritized action plan with agency contact information
**Expected outcome:** Intervention steps render as styled cards with urgency badge (IMMEDIATE/HIGH/MEDIUM/LOW), action text, and clickable agency phone numbers; contact phone numbers are rendered as tel: links; agency web URLs are clickable; full diagnostic report is collapsed but expandable
**Edge cases seen in code:** When structured parsing produces 0 steps (e.g. permit not stalled), full markdown renders directly without the collapsible wrapper
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: stuck permit demo chip auto-run
**Source:** web/templates/tools/stuck_permit.html — fillDemo, diagnosedPermit
**User:** homeowner
**Starting state:** User is on the stuck permit page with empty state showing demo permit chips
**Goal:** Try the tool with an example permit without knowing a real permit number
**Expected outcome:** Clicking a demo chip fills the input with that permit number and immediately runs the diagnosis (no extra button click required); skeleton loading screen appears, then results render with severity badge and playbook
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: revision risk pre-fill from URL param
**Source:** web/templates/tools/revision_risk.html — ?permit_type= pre-fill
**User:** expediter
**Starting state:** User on entity-network or search results page, follows a link with ?permit_type=restaurant
**Goal:** Land on Revision Risk page with form pre-filled and analysis auto-run
**Expected outcome:** Permit type selector pre-selects "restaurant", loading skeleton shows briefly, risk gauge and markdown results appear without any user interaction
**Edge cases seen in code:** If permitTypeParam is set but select has no matching option, auto-run skips gracefully
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: revision risk gauge shows colored arc by risk level
**Source:** web/templates/tools/revision_risk.html — renderGauge() function
**User:** architect
**Starting state:** User submits Revision Risk form for "new_construction" permit type
**Goal:** Understand revision probability at a glance
**Expected outcome:** SVG arc fills proportionally to risk percentage, arc color is red for HIGH, amber for MODERATE, green for LOW; risk level label and explanatory text appear alongside gauge
**Edge cases seen in code:** If API returns no explicit risk level keyword, gauge falls back to percentage extraction heuristic
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: entity network pre-fill from ?address= URL param
**Source:** web/templates/tools/entity_network.html — urlParams.get('address')
**User:** expediter
**Starting state:** User on a property report page, clicks "Explore contractor network" link with ?address=Smith+Construction
**Goal:** Land on Entity Network page with search pre-filled
**Expected outcome:** Input field shows "Smith Construction", loading skeleton appears immediately, network connections render when response returns
**Edge cases seen in code:** Also accepts ?q= as alternate param name
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: entity network shows connection stats before markdown
**Source:** web/templates/tools/entity_network.html — renderNetworkGraph()
**User:** expediter
**Starting state:** User searches for a contractor with >5 connected entities
**Goal:** Quickly assess network size before reading detailed markdown
**Expected outcome:** Three stat cards appear above connections (Connected entities count, Relationships count, Hops), followed by a center node display, then connection rows sorted by shared permits
**Edge cases seen in code:** If parsed.connections is empty, shows "No connections found" message instead of connection rows
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: revision risk tool graceful degradation on missing API endpoint
**Source:** web/templates/tools/revision_risk.html — fetch('/api/revision-risk') 404 handler
**User:** homeowner
**Starting state:** User fills revision risk form, but /api/revision-risk endpoint doesn't exist yet
**Goal:** See useful guidance even when backend isn't ready
**Expected outcome:** Error message explains the endpoint isn't available yet and suggests the What-If Simulator as an alternative; no unhandled JS exceptions
**Edge cases seen in code:** 404 response triggers informative redirect suggestion, not generic error
**CC confidence:** medium
**Status:** PENDING REVIEW
