## SUGGESTED SCENARIO: Authenticated dashboard displays search, quick actions, and recent items in Obsidian card layout

**Source:** web/templates/index.html Sprint 75-1 redesign
**User:** expediter | homeowner | architect
**Starting state:** User is logged in and visits the dashboard (/)
**Goal:** Quickly orient to available tools and start a search or action
**Expected outcome:** Dashboard shows a centered layout with a search card at top, quick action buttons (Analyze a project, Look up a permit, Upload plans, Draft a reply), a recent searches card, a watchlist card, and a stats row — all in glass-card containers. Search input uses Obsidian styling. No horizontal overflow at any viewport width.
**Edge cases seen in code:** If user has no recent searches, recent card shows placeholder text. If user has a primary address set, a personalized "Check [address]" quick action appears.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Navigation collapses to hamburger menu on mobile viewport

**Source:** web/templates/fragments/nav.html Sprint 75-1 redesign
**User:** expediter | homeowner | architect
**Starting state:** User visits any authenticated page on a mobile device (viewport ≤768px)
**Goal:** Access navigation links without the nav overflowing or wrapping
**Expected outcome:** Desktop badge row is hidden. A hamburger icon (3 horizontal lines) appears in the top-right. Tapping it reveals a slide-down panel with all nav items stacked vertically (min 48px height per item). Tapping outside the panel or tapping the hamburger again closes the panel. All items accessible: Search, Brief, Portfolio, Projects, My Analyses, Permit Prep, Consultants, Bottlenecks, Admin (if admin), Account, Logout.
**Edge cases seen in code:** Panel closes on tap-outside via document click handler. Hamburger transforms to X when open (CSS animation on spans). Sign-up chips appear for locked features.
**CC confidence:** high
**Status:** PENDING REVIEW
