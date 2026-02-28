## SUGGESTED SCENARIO: expediter diagnoses critically stalled permit at plan check
**Source:** src/tools/stuck_permit.py — diagnose_stuck_permit
**User:** expediter
**Starting state:** Permit has been at BLDG plan check station for 95 days. Historical p90 for BLDG is 60 days. No comments have been issued.
**Goal:** Understand why the permit is stalled and what to do next
**Expected outcome:** Tool returns a playbook identifying BLDG as critically stalled (past p90), recommending expediter contact DBI plan check counter with specific address and phone number, severity score reflects age/staleness
**Edge cases seen in code:** Heuristic fallback when no velocity baseline exists for a station (>90d = critically stalled, >45d = stalled); stations missing from station_velocity_v2 still get flagged
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: homeowner learns to respond to plan check comments
**Source:** src/tools/stuck_permit.py — _diagnose_station, review_results detection
**User:** homeowner
**Starting state:** Permit routing shows "Comments Issued" review result at BLDG station. 1 revision cycle completed.
**Goal:** Understand what the comments mean and what action to take
**Expected outcome:** Playbook identifies comment-issued status as highest priority intervention, recommends revising plans and resubmitting via EPR (Electronic Plan Review), includes EPR URL
**Edge cases seen in code:** Revision cycle count (addenda_number >= 2) triggers additional warning about multiple rounds; 3+ cycles triggers expediter/architect recommendation
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: architect checks inter-agency hold at SFFD
**Source:** src/tools/stuck_permit.py — INTER_AGENCY_STATIONS, _get_agency_key
**User:** architect
**Starting state:** Permit routed to SFFD station 50 days ago. p75 baseline for SFFD is 30 days.
**Goal:** Know who to contact and what to say
**Expected outcome:** Playbook identifies SFFD as stalled inter-agency station, provides SFFD Permit Division contact info (phone, address, URL), recommends contacting SFFD directly rather than DBI
**Edge cases seen in code:** Multiple inter-agency stations (e.g. SFFD + HEALTH simultaneously) each get separate diagnosis entries ranked by severity; CP-ZOC (Planning) maps to Planning Department not DBI
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: expediter checks a healthy permit that is on track
**Source:** src/tools/stuck_permit.py — _diagnose_station normal status, _format_playbook
**User:** expediter
**Starting state:** Permit has been at BLDG for 10 days. Historical p50 for BLDG is 15 days.
**Goal:** Confirm permit routing is proceeding normally
**Expected outcome:** Playbook shows "OK" routing status, no CRITICAL or STALLED labels, no urgent intervention steps, dwell shown relative to p50 baseline for reassurance
**Edge cases seen in code:** Permit with no addenda data yet (not entered plan check queue) returns empty station list with advisory message about plan check queue status
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: homeowner looks up a permit number that doesn't exist
**Source:** src/tools/stuck_permit.py — permit not found branch
**User:** homeowner
**Starting state:** User enters an incorrect or old permit number
**Goal:** Understand the permit cannot be found
**Expected outcome:** Tool returns a clear "not found" message with the queried permit number and a link to the DBI permit tracking portal (dbiweb02.sfgov.org) so the user can verify the number themselves
**Edge cases seen in code:** DB error during connection (e.g., connection pool exhausted) returns a formatted error message with permit number preserved, not a raw exception traceback
**CC confidence:** high
**Status:** PENDING REVIEW
