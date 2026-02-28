## SUGGESTED SCENARIO: Landing page showcase section visible on scroll
**Source:** web/templates/landing.html, web/templates/components/showcase_*.html
**User:** homeowner
**Starting state:** Unauthenticated user arrives at landing page
**Goal:** Understand what the product does by browsing the page
**Expected outcome:** User scrolls past the hero search bar and sees 6 showcase cards in a 2-column grid, each showing a real data example (timeline Gantt, routing tracker, what-if comparison, risk score, entity profile, delay cost). Each card has a CTA linking to the relevant search query.
**Edge cases seen in code:** showcase_data.json missing → cards render with hardcoded fallback values; cards are still fully functional
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: MCP demo section engages AI-savvy users
**Source:** web/templates/components/mcp_demo.html, web/static/mcp-demo.css
**User:** expediter
**Starting state:** User is on the landing page, has scrolled past the showcase section
**Goal:** Understand how to connect their AI assistant (Claude, GPT-4) to sfpermits.ai
**Expected outcome:** User sees the "What your AI sees" section with an animated chat demo showing a permit query, a tool call (`search_permits()`), a result object, and a Claude response explaining the permit status. Sidebar shows 30 tools available. CTA links to sign-in.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Showcase analytics tracking fires correctly
**Source:** web/templates/landing.html data-track attributes, web/templates/components/showcase_*.html
**User:** admin
**Starting state:** PostHog is initialized on the landing page
**Goal:** Product team tracks which showcase cards users engage with
**Expected outcome:** When a showcase card scrolls into view, data-track="showcase-view" and data-showcase="[type]" are present for PostHog autocapture. When user clicks a CTA, data-track="showcase-click" fires. MCP demo section has data-track="mcp-demo-view" and the Connect CTA has data-track="mcp-demo-cta".
**Edge cases seen in code:** All 6 data-showcase values (gantt/stuck/whatif/risk/entity/delay) are distinct — PostHog can segment by showcase type
**CC confidence:** high
**Status:** PENDING REVIEW
