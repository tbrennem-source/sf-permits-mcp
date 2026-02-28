## SUGGESTED SCENARIO: expediter uses cost of delay to justify expediting fee
**Source:** src/tools/cost_of_delay.py — calculate_delay_cost
**User:** expediter
**Starting state:** Expediter has a restaurant permit client spending $80K/month on a closed location
**Goal:** Quantify the dollar value of shaving 30 days off the permit timeline
**Expected outcome:** Tool returns a formatted table showing carrying cost + revision risk cost per scenario. Break-even section shows daily delay cost. Expediter can use the daily rate to justify their expediting premium to the client.
**Edge cases seen in code:** revision_prob * revision_delay * daily_cost compounds even for p25 (best case) — this means there is always some expected revision cost regardless of timeline scenario
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: homeowner asks how much it costs to wait on a kitchen remodel permit
**Source:** src/tools/cost_of_delay.py — calculate_delay_cost
**User:** homeowner
**Starting state:** Homeowner is renting elsewhere at $5,000/month while waiting for kitchen remodel permit
**Goal:** Understand the total financial exposure of a kitchen remodel permit delay
**Expected outcome:** Tool returns best/likely/worst-case costs. Likely (p50 = 21 days) shows ~$3,450 carrying cost. OTC-eligible note appears since kitchen remodel can go OTC. Mitigation strategies include pre-application consultation.
**Edge cases seen in code:** OTC_ELIGIBLE_TYPES set — kitchen_remodel is in it, so the OTC note must appear
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: developer evaluates cost impact of CEQA trigger on new construction
**Source:** src/tools/cost_of_delay.py — triggers parameter
**User:** architect
**Starting state:** Architect is scoping a new construction project that may trigger CEQA environmental review
**Goal:** See the cost difference between base timeline and CEQA-triggered timeline
**Expected outcome:** With triggers=['ceqa'], the p50 and p90 timelines are escalated by ~180 days. The cost table shows dramatically higher totals. The trigger note "CEQA environmental review" appears in the output.
**Edge cases seen in code:** TRIGGER_DELAYS maps ceqa to 180 days — largest single trigger escalation. Only applies when DB fallback is used (db_available=False).
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: tool gracefully degrades when permit database is unavailable
**Source:** src/tools/cost_of_delay.py — _get_timeline_estimates fallback
**User:** expediter
**Starting state:** MCP server running in environment without DuckDB permit database
**Goal:** Get a cost of delay estimate for a commercial_ti permit
**Expected outcome:** Tool returns output using hard-coded historical averages (clearly noted in Methodology section with "Note: Live permit database unavailable" message). All sections present: table, break-even, mitigation, methodology.
**Edge cases seen in code:** db_available flag drives the note in Methodology section. Fallback timelines for all 13 permit types baked in.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: daily_delay_cost one-liner used in brief or property report
**Source:** src/tools/cost_of_delay.py — daily_delay_cost helper
**User:** expediter
**Starting state:** User has a project with known monthly carrying costs
**Goal:** Get a single-sentence summary of the daily delay cost for use in a client email or brief
**Expected outcome:** Returns exactly one line: "Every day of permit delay costs you $X/day" formatted with appropriate K/M suffix.
**Edge cases seen in code:** $30,440/month → ~$1,000/day. $304,400/month → ~$10K/day. Zero/negative returns error.
**CC confidence:** medium
**Status:** PENDING REVIEW
