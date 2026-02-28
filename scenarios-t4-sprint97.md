## SUGGESTED SCENARIO: Demo page on a mobile phone shows annotation chips inline

**Source:** web/templates/demo.html — .callout fix for max-width 480px
**User:** homeowner
**Starting state:** User opens /demo on an iPhone 375px wide (default Safari width)
**Goal:** User wants to read the data source callouts on the permit history, routing, and entity cards
**Expected outcome:** The annotation chips (callouts) wrap and stack vertically within the card width — no horizontal scrolling, no chips extending past the right edge of the viewport
**Edge cases seen in code:** At 480px the callout is inline-block by default; without the override it can be wider than the card container, causing ~300px overflow
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Landing page stats counter animates to correct permit total

**Source:** web/templates/landing.html — stats section, data-target attribute
**User:** homeowner
**Starting state:** Anonymous visitor lands on the home page and scrolls past the hero into the stats row
**Goal:** User sees the permit count stat to understand the scope of the data
**Expected outcome:** The animated counter starts at 0 and counts up to 1,137,816 when the stats row scrolls into view
**Edge cases seen in code:** If data-target is stale or missing, the count would stop at 0 or show an incorrect number
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Returning user watched-property links navigate to search, not home

**Source:** web/templates/landing.html — states JS object (beta, returning state watched values)
**User:** expediter
**Starting state:** User is in the "beta" or "returning" persona state; the below-search watched row shows property links like "487 Noe — PPC stalled 12d"
**Goal:** User clicks a watched property shortcut to quickly navigate to that property's current permit data
**Expected outcome:** Clicking a watched property link navigates to the search results or report page for that address — not back to the landing page
**Edge cases seen in code:** If href="/" were used, clicking would reload the landing page instead of navigating to the property; this would strand users in a loop
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Demo page renders for anonymous users without authentication

**Source:** web/routes_misc.py demo() route — no auth requirement
**User:** homeowner
**Starting state:** Unauthenticated user follows a shared /demo link
**Goal:** User wants to see a live property intelligence demo without creating an account
**Expected outcome:** The /demo page loads with permit history, routing progress, entity network, and architecture stats — HTTP 200 with full content, no redirect to login
**Edge cases seen in code:** The route calls _get_demo_data() which uses a cached pre-loaded dataset; no user session required
**CC confidence:** high
**Status:** PENDING REVIEW
