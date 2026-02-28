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

## SUGGESTED SCENARIO: MCP demo section loads with visible content on landing page
**Source:** web/templates/components/mcp_demo.html, web/static/mcp-demo.js
**User:** expediter | homeowner | architect
**Starting state:** User arrives at the landing page and scrolls down to the "What your AI sees" section
**Goal:** See an animated demonstration of what Claude responses look like with sfpermits.ai tools
**Expected outcome:** The demo section shows a chat conversation with tool call badge, user message, and a full Claude response including a comparison table. Navigation dots allow switching between 3 demos.
**Edge cases seen in code:** Section uses IntersectionObserver with 0.3 threshold — demo does not start until 30% of the section is visible. On reduced-motion devices, all content shows immediately without animation.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: MCP demo auto-advances through all three demos
**Source:** web/static/mcp-demo.js — scheduleNext() and animateSlide()
**User:** homeowner
**Starting state:** User has scrolled to see the MCP demo section
**Goal:** See multiple demo conversations without any interaction
**Expected outcome:** After ~4 seconds pause at the end of each demo, the section automatically transitions to the next demo (What-If → Stuck Permit → Cost of Delay), then cycles back to the beginning
**Edge cases seen in code:** Auto-advance timer is reset on manual navigation (prev/next clicks)
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: MCP demo navigation controls work correctly
**Source:** web/templates/components/mcp_demo.html navigation controls, mcp-demo.js goToSlide()
**User:** expediter
**Starting state:** User is viewing demo slide 1 (What-If comparison)
**Goal:** Skip to the stuck permit demo to see how permit diagnosis works
**Expected outcome:** Clicking the next arrow or the appropriate navigation dot transitions to the stuck permit demo (Demo 1) with the full analysis content visible
**Edge cases seen in code:** The goToSlide function aborts any in-progress animation before transitioning
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: MCP demo CTA connects to integration setup
**Source:** web/templates/components/mcp_demo.html CTA section
**User:** architect
**Starting state:** User has watched the MCP demo and wants to connect their AI assistant
**Goal:** Find and follow the instructions to add sfpermits.ai to their Claude instance
**Expected outcome:** "Connect your AI" CTA is visible below the demo terminal, linking to the #connect anchor with 3 setup steps visible (Connect, Ask, Get Intelligence)
**Edge cases seen in code:** CTA uses ghost button style with monospace font per design tokens
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: MCP demo mobile stacked cards replace tables on narrow viewport
**Source:** web/static/mcp-demo.css responsive breakpoint at 480px
**User:** homeowner
**Starting state:** User views the landing page on a mobile device (< 480px viewport)
**Goal:** Read the comparison data in the What-If and Cost of Delay demos
**Expected outcome:** Desktop comparison tables are hidden, replaced by readable stacked card layout with label/value pairs. The stuck permit demo has a "See full analysis" expand button for its long response.
**Edge cases seen in code:** The expand button uses absolute positioning on top of the truncated content
**CC confidence:** medium
**Status:** PENDING REVIEW
