# QS8-T2-A: Station Predictor Scenarios

## SUGGESTED SCENARIO: expediter checks next station for active permit

**Source:** src/tools/predict_next_stations.py — predict_next_stations tool
**User:** expediter
**Starting state:** Permit is active, has been routed through at least one station (BLDG completed), currently sitting at SFFD with an arrive date 10 days ago
**Goal:** Understand which stations the permit will visit next and how long each typically takes
**Expected outcome:** Tool returns current station (SFFD with dwell time), top 3 predicted next stations with transition probabilities and p50 durations, and a total estimated remaining time
**Edge cases seen in code:** If fewer than 5 similar permits have transitioned from the current station, no predictions are shown — tool explains why
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: homeowner asks about stalled permit

**Source:** src/tools/predict_next_stations.py — STALL_THRESHOLD_DAYS = 60 logic
**User:** homeowner
**Starting state:** Permit has been at CP-ZOC (Planning/Zoning) for 75 days with no finish_date recorded
**Goal:** Find out if their permit is stuck and what to do about it
**Expected outcome:** Tool surfaces "STALLED" indicator on the current station card, shows how many days the permit has been at that station, and recommends following up with DBI. Predictions for next stations are still shown based on historical transitions.
**Edge cases seen in code:** Stall threshold is configurable (STALL_THRESHOLD_DAYS = 60). Permits just over the threshold get the warning; those below do not.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: permit already complete — no action needed

**Source:** src/tools/predict_next_stations.py — COMPLETE_STATUSES short-circuit
**User:** homeowner | expediter
**Starting state:** Permit status is "complete" or "issued"
**Goal:** Check what happens next (doesn't know it's already done)
**Expected outcome:** Tool returns a clear message that the permit has completed all review stations, shows the issued/completed date if available. Does NOT attempt to build transition predictions.
**Edge cases seen in code:** Status values checked: "complete", "issued", "approved", "cancelled", "withdrawn" — all treated as terminal
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: permit not yet in plan review — no routing data

**Source:** src/tools/predict_next_stations.py — empty addenda short-circuit
**User:** homeowner
**Starting state:** Permit was recently filed (< 2 weeks ago) and has no addenda records yet
**Goal:** Ask what stations the permit will go through
**Expected outcome:** Tool returns "No routing data available" with an explanation that the permit may not have entered plan review yet. Does not error out or return an empty page.
**Edge cases seen in code:** Distinction between permit-not-found (permit table miss) and no-addenda (permit exists but addenda table has no rows for it)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: neighborhood-stratified prediction vs. city-wide fallback

**Source:** src/tools/predict_next_stations.py — _build_transition_matrix neighborhood fallback
**User:** expediter
**Starting state:** Permit is in a neighborhood with sufficient historical data (e.g., Mission — many similar permits). Separately, a permit in a rare neighborhood with very few historical records.
**Goal:** Get predictions that are relevant to the permit's actual location context
**Expected outcome:** For Mission: predictions are labeled as "based on historical routing patterns from permits in Mission" (neighborhood-filtered). For rare neighborhood: falls back to all similar permit types city-wide, labeled accordingly. Both cases return predictions if transition data exists.
**Edge cases seen in code:** Neighborhood fallback triggered when _build_transition_matrix returns empty dict for neighborhood query
**CC confidence:** medium
**Status:** PENDING REVIEW
