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

## SUGGESTED SCENARIO: Portfolio brief contains accurate project statistics
**Source:** docs/portfolio-brief.md (Sprint 69 S4)
**User:** admin
**Starting state:** Portfolio brief document exists in the repository
**Goal:** Verify that all statistics cited in the portfolio brief match actual codebase metrics
**Expected outcome:** Test count, tool count, entity count, sprint count, and other numbers in the portfolio brief match the values derivable from the codebase (pytest collection count, server.py tool registrations, CHANGELOG sprint headers, etc.)
**Edge cases seen in code:** Numbers change every sprint — the brief must be updated or use ranges
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Model release probes cover all capability categories
**Source:** docs/model-release-probes.md (Sprint 69 S4)
**User:** admin
**Starting state:** Model release probes document exists with 14 probes across 6 categories
**Goal:** Validate that the probe set covers all major capabilities of the sfpermits.ai platform
**Expected outcome:** At least 2 probes per category (permit prediction, vision analysis, multi-source synthesis, entity reasoning, specification quality, domain knowledge), each with prompt text, expected capability, and scoring criteria
**Edge cases seen in code:** New tools or capabilities added in future sprints should trigger new probes
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: PWA manifest enables add-to-homescreen
**Source:** web/static/manifest.json (Sprint 69 S4)
**User:** homeowner
**Starting state:** User visits sfpermits.ai on a mobile device
**Goal:** Add sfpermits.ai to their phone's home screen for quick access
**Expected outcome:** The browser offers an "Add to Home Screen" prompt (or the option is available in the browser menu). The installed app opens in standalone mode with the correct theme color (#22D3EE) and app name ("SF Permits")
**Edge cases seen in code:** Icons are placeholders — real branded icons needed before this is production-ready. iOS requires additional meta tags in the HTML head.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: robots.txt allows public pages while blocking admin routes
**Source:** web/app.py ROBOTS_TXT constant (Sprint 69 S4)
**User:** admin
**Starting state:** Search engine crawler visits /robots.txt
**Goal:** Ensure search engines can index public pages but not admin, auth, or API routes
**Expected outcome:** GET /robots.txt returns 200 with Allow: / and Disallow directives for /admin/, /cron/, /api/, /auth/, /demo, /account, /brief, /projects. Includes Sitemap reference.
**Edge cases seen in code:** The Allow: / must come before Disallow lines for proper precedence. Some crawlers interpret robots.txt differently.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Technical visitor reads methodology page
**Source:** web/templates/methodology.html (Sprint 69 S3)
**User:** architect
**Starting state:** Visitor lands on sfpermits.ai and wants to understand the data quality before trusting estimates
**Goal:** Read the methodology page and understand how timeline estimates, fee calculations, and entity resolution work
**Expected outcome:** Visitor finds 8 methodology sections with real technical depth (>2,500 words), data provenance table with SODA endpoints, entity resolution flowchart, worked timeline example, and an honest limitations section. Visitor gains confidence in the tool's transparency.
**Edge cases seen in code:** Mobile view replaces CSS flowchart with numbered list; station velocity data may be unavailable (fallback model documented)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Visitor navigates to about-data page
**Source:** web/templates/about_data.html (Sprint 69 S3)
**User:** homeowner
**Starting state:** Visitor sees "About the Data" link in navigation
**Goal:** Understand what data sfpermits.ai uses and how fresh it is
**Expected outcome:** Visitor sees complete data inventory table with 13+ datasets, record counts, and SODA endpoint IDs. Nightly pipeline schedule shows 6 pipeline steps with times. Knowledge base section explains the 4-tier system. QA section shows 3,300+ tests and 73 behavioral scenarios.
**Edge cases seen in code:** Planning data refreshes weekly not nightly; property data refreshes annually
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Tim shares demo URL in Zoom call
**Source:** web/templates/demo.html + web/routes_misc.py (Sprint 69 S3)
**User:** admin
**Starting state:** Tim opens /demo in a browser before a Zoom call with potential client
**Goal:** Show all intelligence layers for a real SF property in one screen, without needing to click anything
**Expected outcome:** Page loads with pre-queried data for demo address showing: permit history table, routing progress bars, timeline estimate visualization, connected entities list, complaints/violations summary. Annotation callouts explain each section's data source. Everything visible on load (no HTMX, no click-to-reveal).
**Edge cases seen in code:** Database unavailable produces graceful degradation with empty states; ?density=max reduces padding for information-dense presentation; timeline falls back to hardcoded example if DB unavailable
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Search engine indexes methodology and about-data
**Source:** web/routes_misc.py sitemap (Sprint 69 S3)
**User:** homeowner
**Starting state:** Google crawls sfpermits.ai's sitemap.xml
**Goal:** Methodology and about-data pages should be discoverable; demo page should not be indexed
**Expected outcome:** sitemap.xml includes /methodology and /about-data URLs. Demo page has noindex meta tag and is NOT in the sitemap.
**Edge cases seen in code:** Demo page intentionally excluded from sitemap to keep it unlisted
**CC confidence:** high
**Status:** PENDING REVIEW
