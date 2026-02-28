## SUGGESTED SCENARIO: first-time visitor sees Gantt before any other intelligence card
**Source:** web/templates/landing.html — showcase-gantt-section restructure (Sprint 94 T1A)
**User:** homeowner
**Starting state:** User arrives at landing page for the first time, not logged in
**Goal:** Understand how the permit timeline intelligence works before deciding to search
**Expected outcome:** User sees the Routing Intelligence / Station Timeline chart as the very first intelligence showcase below the search hero — not buried alongside other cards in a grid
**Edge cases seen in code:** If showcase data is absent (JSON missing), the Gantt section renders empty but the section container still exists
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: mobile visitor can scroll Gantt chart horizontally
**Source:** web/templates/landing.html — Gantt mobile treatment CSS (Sprint 94 T1A)
**User:** homeowner
**Starting state:** User on a mobile device (≤480px viewport) viewing the landing page
**Goal:** See the station timeline chart without it being truncated or illegible
**Expected outcome:** The Gantt chart body is scrollable horizontally; station labels (BLDG, CP-ZOC etc.) remain readable; user can swipe to see the full timeline
**Edge cases seen in code:** min-height: 300px ensures card is tall enough to be usable; overflow-x: auto enables native swipe
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: landing page credibility without overwhelming number display
**Source:** web/templates/landing.html — stats bar removed, credibility-line added (Sprint 94 T1A)
**User:** homeowner
**Starting state:** User on landing page, not logged in
**Goal:** Trust that the data is current without being distracted by raw permit counts
**Expected outcome:** A compact credibility line ("Updated nightly from 22 city data sources · Free during beta") appears near the page bottom — conveys freshness and accessibility without dominating the visual hierarchy
**Edge cases seen in code:** Stats bar fully removed; animateCount JS is harmless no-op when no .counting elements exist
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: showcase grid scales appropriately on tablet
**Source:** web/templates/landing.html — responsive grid breakpoints (Sprint 94 T1A)
**User:** expediter
**Starting state:** User on tablet device (≤768px viewport, >480px)
**Goal:** Browse the 5 intelligence showcase cards in a readable layout
**Expected outcome:** The 5 non-Gantt cards display in a 2-column grid; no overflow or card cutoff; Gantt above them is full-width
**Edge cases seen in code:** Media query at 768px sets showcase-grid to repeat(2, 1fr); at 480px falls back to single column

## SUGGESTED SCENARIO: Stuck permit showcase shows visual pipeline at a glance
**Source:** web/templates/components/showcase_stuck.html redesign (Sprint 94)
**User:** homeowner
**Starting state:** User is on the landing page, scrolled to the Diagnostic Intelligence showcase card
**Goal:** Quickly understand why a permit is stuck without reading dense text
**Expected outcome:** User sees 4 labeled station blocks in a horizontal row, each with a red X or green check, and immediately grasps which agencies are blocked
**Edge cases seen in code:** All 4 blocks may be critically_stalled, resulting in all red icons — card must still be scannable
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Stuck permit showcase CTA navigates to full playbook
**Source:** web/templates/components/showcase_stuck.html redesign (Sprint 94)
**User:** expediter
**Starting state:** User sees the "See full playbook →" CTA on the showcase card
**Goal:** Access the full intervention playbook with all 3 steps and contact info
**Expected outcome:** Clicking the CTA navigates to /tools/stuck-permit?permit=202412237330 (or equivalent demo permit), showing the complete playbook
**Edge cases seen in code:** CTA uses ghost-cta class and data-track="showcase-click" for analytics
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Stuck permit card headline immediately conveys scope
**Source:** web/templates/components/showcase_stuck.html — headline "432 days · 4 agencies blocked"
**User:** homeowner
**Starting state:** User views the landing page for the first time
**Goal:** Instantly understand the severity of a stuck permit without reading body text
**Expected outcome:** Headline displays "{N} days · {N} agencies blocked" in mono font, with a pulsing CRITICAL badge alongside it
**Edge cases seen in code:** If days_stuck or block_count is 0, the headline degrades gracefully (Jinja2 renders 0 values without error)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Stuck permit card shows only first intervention step
**Source:** web/templates/components/showcase_stuck.html — playbook[0] only
**User:** expediter
**Starting state:** User views the showcase card and reads the intervention hint
**Goal:** Get a single actionable next step without being overwhelmed by the full playbook
**Expected outcome:** Card shows "Step 1: [action text]" — only one step, not all three. The "See full playbook" CTA leads to the rest.
**Edge cases seen in code:** If playbook is empty, the intervention block is omitted entirely (wrapped in {% if stuck.playbook %})

**CC confidence:** medium
**Status:** PENDING REVIEW
