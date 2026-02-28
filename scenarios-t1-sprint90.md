## SUGGESTED SCENARIO: MCP demo auto-plays on scroll
**Source:** web/templates/components/mcp_demo.html, web/static/mcp-demo.js
**User:** homeowner | architect | expediter
**Starting state:** User is on the landing page, has not scrolled to the MCP demo section
**Goal:** See the animated chat transcript showing Claude using sfpermits.ai tools
**Expected outcome:** When the MCP demo section scrolls into view (30% visible), animation begins automatically: user message fades in, tool badge pulses, Claude response types line by line. After 4s pause, transitions to next demo. Cycles through all 3 demos indefinitely.
**Edge cases seen in code:** Reduced motion preference skips animation and shows all content immediately. IntersectionObserver fallback for older browsers starts animation immediately.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: MCP demo manual navigation
**Source:** web/static/mcp-demo.js
**User:** homeowner | architect | expediter
**Starting state:** User is viewing the MCP demo section, animation is playing
**Goal:** Manually switch between demo conversations
**Expected outcome:** Clicking left/right arrows or navigation dots immediately transitions to the selected demo. Auto-advance timer resets. Animation plays for the newly selected demo. Dots update to reflect current position.
**Edge cases seen in code:** Clicking during fade transition should not break state. Clicking same dot does nothing if already animating that slide.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: MCP demo mobile table collapse
**Source:** web/static/mcp-demo.css, web/templates/components/mcp_demo.html
**User:** homeowner
**Starting state:** User views the landing page on a mobile device (width <= 480px)
**Goal:** Read the What-If comparison data without horizontal scrolling
**Expected outcome:** Desktop comparison table is hidden. Instead, two stacked cards appear: "Kitchen Only" card with its key-value pairs, then "Kitchen + Bath + Wall" card. Data is readable without scrolling horizontally. Long Claude responses (Demo 1 stuck permit) show a "See full analysis" expand button, capping visible height at 300px.
**Edge cases seen in code:** Tool badges wrap to max 2 lines on mobile. Expand button disappears after clicking.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: MCP demo CTA drives connection
**Source:** web/templates/components/mcp_demo.html
**User:** architect | expediter
**Starting state:** User has watched at least one demo cycle and is impressed by the tool outputs
**Goal:** Connect their AI assistant to sfpermits.ai
**Expected outcome:** Below the demo terminal, a "Connect your AI" button is visible. Below it, a 3-step explainer shows: (1) Connect - Add sfpermits.ai to your AI assistant, (2) Ask - Ask about any SF property or permit, (3) Get Intelligence - Receive data-backed analysis with specific actions.
**Edge cases seen in code:** Button href is placeholder #connect (future Anthropic directory link). Steps stack vertically on mobile.
**CC confidence:** medium
**Status:** PENDING REVIEW
