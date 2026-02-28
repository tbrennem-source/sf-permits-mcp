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
**CC confidence:** medium
**Status:** PENDING REVIEW
