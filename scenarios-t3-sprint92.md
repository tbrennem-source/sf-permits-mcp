## SUGGESTED SCENARIO: what-if simulator two-panel comparison
**Source:** web/templates/tools/what_if.html (Sprint 92 — Agent 3B polish)
**User:** expediter | homeowner
**Starting state:** User is on the What-If Simulator page, unauthenticated or authenticated
**Goal:** Compare two project scopes (e.g., kitchen remodel vs. full gut + ADU) to understand timeline and fee differences before filing
**Expected outcome:** User fills Project A and Project B panels and sees a comparison table with green/red indicators on significant differences; a strategy callout summarizes key deltas
**Edge cases seen in code:** If Project B is empty, only base scenario is evaluated; if demo param is present, form auto-fills and auto-runs after 400ms
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: what-if simulator demo auto-run
**Source:** web/templates/tools/what_if.html ?demo=kitchen-vs-full
**User:** homeowner
**Starting state:** User arrives at /tools/what-if?demo=kitchen-vs-full
**Goal:** See a pre-populated comparison without having to fill in the form manually
**Expected outcome:** Both Project A and B panels are pre-filled with demo data and the simulation runs automatically; user sees comparison table within a few seconds
**Edge cases seen in code:** 400ms timeout before auto-submit so user can see the pre-filled state
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: cost of delay percentile breakdown
**Source:** web/templates/tools/cost_of_delay.html (Sprint 92 — Agent 3B polish)
**User:** expediter | homeowner | architect
**Starting state:** User selects a permit type and enters monthly carrying cost
**Goal:** Understand the financial exposure across best/likely/worst-case permit timelines
**Expected outcome:** Percentile table shows p25/p50/p75/p90 scenarios with days, carrying cost, revision risk cost, and total; expected cost highlight card shows p50+revision probability-weighted total
**Edge cases seen in code:** Permit type dropdown limited to 12 known types; restaurant gets a DPH-HQ bottleneck alert
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: cost of delay bottleneck alert
**Source:** web/templates/tools/cost_of_delay.html bottleneck-alert component
**User:** expediter | homeowner
**Starting state:** User selects a permit type with known slow stations (restaurant, commercial_ti, new_construction)
**Goal:** See a warning about known bottlenecks that will inflate the timeline
**Expected outcome:** An amber-dot bottleneck alert badge appears with a description of the specific slow station (e.g., "DPH-HQ averages +86% longer than DBI baseline" for restaurant)
**Edge cases seen in code:** Bottleneck message is permit-type-specific from a JS lookup table; generic message if unknown type
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: cost of delay demo auto-run
**Source:** web/templates/tools/cost_of_delay.html ?demo=restaurant-15k
**User:** homeowner
**Starting state:** User arrives at /tools/cost-of-delay?demo=restaurant-15k
**Goal:** See an example calculation without filling in the form
**Expected outcome:** Form pre-fills with restaurant permit type and $15K/month; calculation runs automatically and shows the percentile breakdown, expected cost card, and bottleneck warning for restaurant
**Edge cases seen in code:** 400ms delay before auto-submit; invalid monthly cost triggers inline error
**CC confidence:** high
**Status:** PENDING REVIEW
