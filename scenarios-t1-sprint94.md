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
