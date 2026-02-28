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
