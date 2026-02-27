## SUGGESTED SCENARIO: sequence timeline from permit routing history
**Source:** src/tools/estimate_timeline.py — estimate_sequence_timeline()
**User:** expediter
**Starting state:** A permit with a known application number has addenda routing records in the database. Station velocity data exists in station_velocity_v2 for at least some of those stations.
**Goal:** The expediter wants to understand how long the permit's specific review route will take, given the actual stations it has been routed through (not a generic estimate based on permit type).
**Expected outcome:** The response includes a per-station breakdown showing each station's p50 velocity, status (done/stalled/pending), whether it's running in parallel with another station, and a total estimate in days with a confidence level. Stations with no velocity data are listed as skipped.
**Edge cases seen in code:** If no addenda exist for the permit number, returns null (no estimate). If the station_velocity_v2 table doesn't exist yet, still returns a result with the station sequence but 0 total days and "low" confidence.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: parallel station detection in sequence model
**Source:** src/tools/estimate_timeline.py — estimate_sequence_timeline() parallel detection logic
**User:** expediter
**Starting state:** A permit has been routed to two or more stations simultaneously (same arrive date). Both stations have velocity data.
**Goal:** The timeline estimate correctly treats concurrent review stations as parallel (not additive), so the total estimate reflects real-world review time.
**Expected outcome:** The total_estimate_days uses the max p50 of the parallel group, not the sum. The station entries have is_parallel=true for the stations that overlap. The total is lower than if all stations were summed sequentially.
**Edge cases seen in code:** Parallel detection compares date portions (first 10 chars) of first_arrive timestamps. Stations with the same arrive date are grouped as parallel. Only the p50 of the longest station in the group contributes to the total.
**CC confidence:** high
**Status:** PENDING REVIEW
