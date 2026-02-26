# Scenarios Pending Review
<!-- CC appends suggested scenarios here after each feature session -->
<!-- Do not edit scenario-design-guide.md directly -->
<!-- This file is reviewed and drained each planning session -->
<!-- Drained Sprint 68-A: 102 scenarios reviewed, 48 accepted, 30 merged, 22 rejected, 2 deferred -->
<!-- See scenarios-reviewed-sprint68.md for full review log -->

_Last reviewed: Sprint 68-A (2026-02-26)_

## SUGGESTED SCENARIO: Anonymous visitor sees live data counts on landing page
**Source:** Sprint 69 S1 — landing.html rewrite + /api/stats endpoint
**User:** homeowner
**Starting state:** User has never visited sfpermits.ai. Not logged in.
**Goal:** Understand the scale and credibility of the platform within 10 seconds of landing.
**Expected outcome:** Landing page shows permit count, routing record count, entity count, and inspection count. Numbers are non-zero and formatted for readability (e.g. "1.1M+"). Data pulse panel shows a green status dot and "Live Data Pulse" label.
**Edge cases seen in code:** If /api/stats fails or DB is unavailable, fallback numbers already baked into HTML render correctly. Numbers don't show "undefined" or "NaN".
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Landing page search bar submits to /search endpoint
**Source:** Sprint 69 S1 — landing.html hero search form
**User:** homeowner
**Starting state:** On the sfpermits.ai landing page, not logged in.
**Goal:** Search for a property by address to see permit history.
**Expected outcome:** Typing an address in the search bar and pressing Enter (or clicking Search) navigates to /search?q=<query>. Search results page renders with results or a "no results" message.
**Edge cases seen in code:** Empty query redirects to /. Suggested address codes (1455 Market St) are clickable and pre-fill the input. Search is rate limited at 15 requests/window.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Design system CSS loads without breaking existing authenticated pages
**Source:** Sprint 69 S1 — design-system.css with body.obsidian scoping
**User:** expediter
**Starting state:** Logged-in user viewing /account or /brief or any authenticated page.
**Goal:** Navigate normally — design system CSS is loaded globally but must not alter existing page styles.
**Expected outcome:** Authenticated pages render exactly as before. No color changes, no layout shifts, no font changes. The body.obsidian class is only on the landing page; other pages don't have it.
**Edge cases seen in code:** style.css now has @import for design-system.css. Existing :root vars in inline styles may conflict with design system :root — but component classes are all scoped under body.obsidian.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: /api/stats returns cached data counts
**Source:** Sprint 69 S1 — routes_api.py /api/stats endpoint
**User:** architect
**Starting state:** /api/stats has not been called in the last hour.
**Goal:** Fetch current data counts for display or integration.
**Expected outcome:** GET /api/stats returns JSON with permits, routing_records, entities, inspections, last_refresh, today_changes. All values are integers (except last_refresh which is ISO string or null). Second call within 1 hour returns cached results. Rate limited at 60 requests/min.
**Edge cases seen in code:** DB unavailable returns hardcoded fallback values. Rate limit returns 429.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Landing page renders correctly on mobile (375px)
**Source:** Sprint 69 S1 — landing.html responsive design
**User:** homeowner
**Starting state:** Viewing sfpermits.ai on a phone (375px viewport).
**Goal:** Use the landing page comfortably on mobile — search, read capabilities, understand the platform.
**Expected outcome:** Single column layout. Hero section stacks (no split). Search bar stacks vertically. Capability cards are in a horizontal scroll strip. Stats show in 2x2 grid. No horizontal overflow. All tap targets are at least 44px.
**Edge cases seen in code:** Capability cards use scroll-snap for horizontal swiping. Header actions might get cramped — 480px breakpoint reduces font size.
**CC confidence:** high
**Status:** PENDING REVIEW
