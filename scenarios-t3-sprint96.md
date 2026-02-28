## SUGGESTED SCENARIO: permit station badge shows current queue wait time
**Source:** web/helpers.py compute_triage_signals, web/templates/search_results_public.html
**User:** expediter
**Starting state:** Expediter searches for a property address that has an active permit in plan review at BLDG station for 45 days
**Goal:** Quickly assess how long the permit has been waiting without opening SF DBI portal
**Expected outcome:** A colored station badge appears in the search results showing "45d at BLDG" — amber because 45 days exceeds the 30-day median but is below the 2x (60-day) stuck threshold
**Edge cases seen in code:** Days exactly equal to median (30) shows amber, not green. Days exactly at 2x median (60) shows red and sets is_stuck=True.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: stuck permit indicator surfaces without false positives
**Source:** web/helpers.py classify_days_threshold, is_stuck logic
**User:** expediter
**Starting state:** Expediter searches for a property with a permit at SFFD-HQ for 89 days (SFFD-HQ median is 45d, 2x = 90d)
**Goal:** Know whether the permit is actually stuck or just moving slowly
**Expected outcome:** Badge shows "89d at SFFD-HQ" in amber (below 2x threshold of 90d). No "Stuck" indicator. At 90+ days, the "Stuck" indicator would appear.
**Edge cases seen in code:** Each station has a different median: BLDG=30d, SFFD-HQ=45d, CP-ZOC=60d, MECH-E=25d, ELEC=25d. Comparison uses station-specific threshold, not a global one.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: reviewer name shows on active plan review station
**Source:** web/helpers.py compute_triage_signals reviewer field, search_results_public.html triage-reviewer class
**User:** expediter
**Starting state:** Permit is at BLDG station with plan_checked_by = "ARRIOLA LAURA" in the addenda table
**Goal:** Know who is assigned to the permit so they can follow up directly
**Expected outcome:** The triage card shows "Reviewer: ARRIOLA LAURA" in a secondary text style below the station badge
**Edge cases seen in code:** reviewer is None when no plan_checked_by row exists — field is omitted from the card (not shown as "None" or blank label)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: triage signals absent when permit has no active station
**Source:** web/helpers.py compute_triage_signals — station_rows empty path
**User:** homeowner
**Starting state:** Permit was issued 10 days ago and is no longer in any active plan review station
**Goal:** User searches their address — expects to see permit status without confusing station timing info
**Expected outcome:** Triage card shows the permit number and status but no station badge or reviewer — the card renders without timing data (days_at_station is None, current_station is None)
**Edge cases seen in code:** is_stuck is always False when there is no station data. The card body renders conditionally: station badge block only shown if current_station is set.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: search page gracefully degrades when DB triage query fails
**Source:** web/routes_public.py triage_signals try/except, web/helpers.py compute_triage_signals try/except
**User:** homeowner
**Starting state:** DB is unavailable or throws an exception during the triage query (e.g., connection timeout)
**Goal:** User still gets their search results — triage is an enhancement, not a blocker
**Expected outcome:** Page renders with full AI search results and no triage panel visible. No error message shown. Error is silently caught.
**Edge cases seen in code:** Two catch layers: outer try/except in routes_public.py, and inner try/except inside compute_triage_signals itself.
**CC confidence:** high
**Status:** PENDING REVIEW
