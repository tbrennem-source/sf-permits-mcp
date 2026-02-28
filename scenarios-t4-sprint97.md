## SUGGESTED SCENARIO: Mobile user taps "Try it yourself" CTA on landing page
**Source:** web/static/obsidian.css — ghost-cta touch target fix
**User:** homeowner
**Starting state:** User is on a phone viewing the landing page
**Goal:** Tap a ghost CTA link to navigate to the demo or search
**Expected outcome:** The link responds to the tap — no missed taps or accidental presses due to tiny target. Navigation succeeds on first attempt.
**Edge cases seen in code:** ghost-cta is used site-wide — padding must not break desktop layout or create excessive vertical spacing in dense data rows
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Mobile user navigates landing page via mobile nav bar
**Source:** web/templates/landing.html — mobile nav addition
**User:** homeowner
**Starting state:** First-time visitor on a phone (≤480px viewport), no account, landing page loaded
**Goal:** Find and navigate to the demo or search from the landing page
**Expected outcome:** A navigation bar is visible at the top of the screen with clearly labeled links (Search, Demo, How, Sign in). Each link is tappable without zooming. Content below the nav is not obscured.
**Edge cases seen in code:** Nav is fixed-position; body padding-top added to push hero content clear. On desktop (>480px) the bar is hidden entirely via media query.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Mobile user interacts with MCP demo carousel dots
**Source:** web/static/mcp-demo.css — mcp-demo-dot touch target fix
**User:** expediter
**Starting state:** User scrolls to the MCP demo section on a phone
**Goal:** Tap dot indicators to navigate between demo slides
**Expected outcome:** Each dot responds to tap on first press. The active dot is visually distinct. No accidental adjacent-dot activation due to tiny target.
**Edge cases seen in code:** Dots use box-sizing: content-box so padding expands beyond the visual indicator without altering the indicator's rendered size.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Desktop user sees no layout regression after ghost-cta padding increase
**Source:** web/static/obsidian.css — ghost-cta is used site-wide
**User:** expediter
**Starting state:** Desktop browser, any page using .ghost-cta (search results, property report, load-more)
**Goal:** Normal browsing — user sees ghost CTAs such as "View report →" or "Load more →"
**Expected outcome:** CTAs display identically to before — no extra vertical gap, no layout shift, text alignment unchanged. The padding increase is absorbed without visual change on desktop.
**Edge cases seen in code:** print styles explicitly hide .ghost-cta — print output unaffected.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: stakeholder follows guided demo link
**Source:** web/templates/demo_guided.html
**User:** expediter | homeowner | architect
**Starting state:** User has not visited sfpermits.ai before; received a share link to /demo/guided
**Goal:** Understand what the product does within 2 minutes and self-navigate to a relevant tool
**Expected outcome:** User lands on the guided page, reads all 6 sections in sequence, and clicks into at least one intelligence tool; no authentication required
**Edge cases seen in code:** All 4 tool card links include demo query params — tool pages must handle ?demo= gracefully
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: stakeholder searches pre-filled address
**Source:** web/templates/demo_guided.html — Section 3 search block
**User:** homeowner
**Starting state:** User is on /demo/guided and clicks the "Search 487 Noe St →" pre-filled link
**Goal:** See real permit data for a sample SF property without having to type an address
**Expected outcome:** /search?q=487+Noe+St returns results for 487 Noe St with permit data; address and permit timeline visible
**Edge cases seen in code:** If DuckDB lacks data for that address, search should return empty state gracefully not a 500
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: professional shares demo link with client before kickoff meeting
**Source:** web/templates/demo_guided.html — Section 5 "For Professionals"
**User:** expediter
**Starting state:** Expediter wants to orient a new property owner client before a project kickoff
**Goal:** Send a single link that explains the permit intelligence workflow and pre-warms the client on terminology
**Expected outcome:** Client opens /demo/guided unauthenticated, reads Amy workflow bullets, understands morning triage concept, and arrives at kickoff with baseline context
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: AI practitioner evaluates MCP integration via demo page
**Source:** web/templates/demo_guided.html — Section 6 "Connect Your AI"
**User:** architect
**Starting state:** Technical user is evaluating whether to integrate sfpermits.ai into their Claude or ChatGPT workflow
**Goal:** Understand the MCP capability scope (34 tools, 18M records) and navigate to learn more
**Expected outcome:** User reads Section 6, clicks "Learn more →", lands on /methodology with sufficient technical detail to decide on integration
**CC confidence:** medium
**Status:** PENDING REVIEW
