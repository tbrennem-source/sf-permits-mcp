## SUGGESTED SCENARIO: what-if comparison on scope expansion

**Source:** src/tools/what_if_simulator.py
**User:** expediter
**Starting state:** Expediter has a base kitchen remodel project ($80K) and client is considering adding a bathroom.
**Goal:** Quickly compare how adding a bathroom changes timeline, fees, and revision risk without pulling up each tool separately.
**Expected outcome:** A comparison table showing base vs. variation side-by-side; review path, p50 timeline, estimated DBI fees, and revision risk are all populated. Delta section calls out meaningful changes (e.g., review path shift from OTC to In-house if triggered).
**Edge cases seen in code:** When underlying tools return errors for a variation, the row shows "N/A" in affected columns rather than crashing; the simulation still completes.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: what-if simulation with no variations (base only)

**Source:** src/tools/what_if_simulator.py
**User:** homeowner
**Starting state:** Homeowner asks about a kitchen remodel but doesn't specify any variations.
**Goal:** Get the baseline permit picture without needing to provide variations.
**Expected outcome:** Simulator runs with just the base scenario, produces a 1-row table, no "Delta vs. Base" section appears, and output still includes all column values (permits, review path, timeline, fees, risk).
**Edge cases seen in code:** Empty variations list is valid input; no delta section should be rendered.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: what-if detects OTC-to-in-house review path shift

**Source:** src/tools/what_if_simulator.py — _evaluate_scenario + delta section
**User:** expediter
**Starting state:** Base project is OTC-eligible (simple kitchen remodel). Variation adds scope that triggers in-house review (e.g., change of use, structural work).
**Goal:** Identify that the scope change moves the project out of OTC path, which has significant timeline implications.
**Expected outcome:** Delta section explicitly calls out "OTC → In-house" review path change and notes it "may add weeks". Both table rows show different Review Path values.
**Edge cases seen in code:** Only flagged when both base and variation have non-N/A review paths; partial data (one N/A) is silently skipped in the delta.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: what-if with cost-free description uses default valuation

**Source:** src/tools/what_if_simulator.py — _evaluate_scenario cost parsing
**User:** homeowner
**Starting state:** Homeowner describes a project without mentioning a dollar amount ("kitchen remodel in the Mission").
**Goal:** Get a rough fee estimate even without explicit cost information.
**Expected outcome:** Simulator falls back to $50K default valuation for fee estimation; output still includes an estimated fee (not N/A). A note or the table still renders.
**Edge cases seen in code:** Both "$80K" and "80k" and "$80,000" are recognized; missing cost triggers $50K fallback defined in _evaluate_scenario.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: what-if tool gracefully handles sub-tool database errors

**Source:** src/tools/what_if_simulator.py — _evaluate_scenario try/except blocks
**User:** expediter
**Starting state:** Local DuckDB database is not initialized or is locked (e.g., parallel test run).
**Goal:** Simulator still returns usable output even when one or more sub-tools fail due to DB unavailability.
**Expected outcome:** Affected cells show "N/A". Notes section lists which sub-tools encountered errors. No exception is raised to the caller. Other cells that succeeded show valid data.
**Edge cases seen in code:** Each of the four sub-tool calls is wrapped in try/except; errors are accumulated in result["notes"] and surfaced in a "Data Notes" section at the end of the output.
**CC confidence:** high
**Status:** PENDING REVIEW
