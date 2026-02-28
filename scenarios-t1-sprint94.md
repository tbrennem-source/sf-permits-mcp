## SUGGESTED SCENARIO: What-if comparison card communicates scope impact without reading
**Source:** showcase_whatif.html (Sprint 94 visual-first redesign)
**User:** homeowner | expediter
**Starting state:** User lands on demo/landing page and sees showcase cards
**Goal:** Immediately understand that adding a bathroom and wall changes the entire permit path
**Expected outcome:** User sees two columns with bold timeline contrast (2 weeks vs 5 months) without needing to read data tables or strategy text
**Edge cases seen in code:** Both columns must display big monospace numbers; bars below reinforce the relative magnitude
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Risk gauge communicates 24.6% at a glance
**Source:** showcase_risk.html (Sprint 94 visual-first redesign)
**User:** architect | expediter
**Starting state:** User views showcase card without having read any surrounding text
**Goal:** Understand that revision risk is significant (roughly 1-in-4) in under 2 seconds
**Expected outcome:** Circular SVG arc gauge filled to 24.6% with the number centered inside reads as a meaningful percentage at-a-glance; context label identifies the project type and neighborhood
**Edge cases seen in code:** Gauge arc uses amber token color (--dot-amber); dashoffset math: 314 circumference * (1 - 0.246) = 237
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Entity node graph shows professional network before any interaction
**Source:** showcase_entity.html (Sprint 94 visual-first redesign)
**User:** expediter | architect
**Starting state:** User views the entity network showcase card
**Goal:** Immediately grasp that the address has multiple connected contractors/architects who worked together across thousands of permits
**Expected outcome:** SVG node graph with central node (1 Market St) and 4 surrounding nodes in teal edges renders on load; nodes float gently; stats line "63 permits · 12,674 connected projects" below confirms the scale
**Edge cases seen in code:** Float animations are CSS-driven; JS entrance animation fades nodes in sequentially after IntersectionObserver fires
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Cost of delay hero number translates bureaucratic time to money instantly
**Source:** showcase_delay.html (Sprint 94 visual-first redesign)
**User:** homeowner | contractor
**Starting state:** User views the financial intelligence showcase card
**Goal:** Immediately understand the daily financial cost of permit delays
**Expected outcome:** "$500" appears in large monospace amber text with "/day" unit beside it; "Expected total: $41,375" and "Based on $15K/mo carrying cost" are visible below as supporting context without requiring any interaction
**Edge cases seen in code:** Hero number is hardcoded to $500 (round number that reads faster than $493/day from data); expected total uses actual data value
**CC confidence:** high
**Status:** PENDING REVIEW
