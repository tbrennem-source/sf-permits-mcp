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
