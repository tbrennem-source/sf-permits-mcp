# Scenario Drain — QS7 Agent 4D
# Processing batch 1 of 93 pending scenarios (first 25)

**Date:** 2026-02-27
**Agent:** QS7-4D (docs + scenario drain)
**Method:** Cross-reference each pending scenario against scenario-design-guide.md (73 approved scenarios). Categorize as KEPT, DUPLICATE, or REWRITTEN.

## Summary

- **KEPT:** 15 scenarios (valid product behaviors, not duplicates, left as PENDING REVIEW)
- **DUPLICATES:** 3 scenarios (substantive overlap with approved scenarios — listed with which approved scenario covers them)
- **REWRITTEN:** 7 scenarios (too implementation-specific — rewritten to outcome-focused per scenario durability spectrum)

---

## DUPLICATES (3)

These are substantively covered by existing approved scenarios. Recommended: remove from pending queue when Tim drains this file.

### DUP-1: "Anonymous visitor sees live data counts on landing page"
**Duplicates:** SCENARIO 37 (Anonymous user discovers site via landing page — approved Sprint 68-A) + SCENARIO 73 (ADU landing page shows pre-computed permit stats — approved Sprint 68-A)
**Why:** SCENARIO 37 covers "Landing page renders with hero, search box, feature cards, and stats." The data counts are a subset of the stats behavior already covered. The fallback behavior (no NaN/undefined on DB fail) is a desirable edge case but doesn't justify a separate scenario.
**Recommendation:** Merge the fallback edge case into SCENARIO 37's edge cases section when approved.

### DUP-2: "Landing page search bar submits to /search endpoint"
**Duplicates:** SCENARIO 37 (search box present) + SCENARIO 38 (anonymous user searches and sees public results)
**Why:** SCENARIO 38 already covers "Typing an address and getting public results." The rate limit behavior and empty query redirect are already in SCENARIO 36 and SCENARIO 38 edge cases.
**Recommendation:** The intent classifier routing edge case (empty query → redirect home) could be added to SCENARIO 38.

### DUP-3: "Search engine indexes methodology and about-data"
**Duplicates:** SCENARIO 34 (CSP header — approved) and the robots.txt scenario (DUP candidate with "robots.txt allows public pages while blocking admin routes" in same batch)
**Why:** Sitemap inclusion / noindex behavior is a deployment configuration check, not a user-visible behavioral scenario. This belongs in the QA script, not the scenario design guide.
**Note:** The "robots.txt allows public pages while blocking admin routes" scenario (pending line 92) is similarly a configuration check — but it's sufficiently distinct from existing approved scenarios to leave as PENDING REVIEW.

---

## REWRITTEN (7)

These scenarios reference implementation details (routes, CSS classes, specific UI element names, endpoint paths). Rewritten to be outcome-focused and durable across refactors.

### REWRITTEN-1: "/api/stats returns cached data counts"
**Before (implementation-specific):**
> GET /api/stats returns JSON with permits, routing_records, entities, inspections, last_refresh, today_changes... Rate limited at 60 requests/min.

**After (outcome-focused):**

## SUGGESTED SCENARIO: Data counts endpoint returns fresh platform statistics with graceful fallback
**Source:** Sprint 69 S1 — /api/stats endpoint
**User:** architect
**Starting state:** The platform data counts have not been requested externally in the last hour.
**Goal:** Fetch current data volume statistics for display or integration (permits indexed, entities resolved, inspections tracked).
**Expected outcome:** A data counts request returns integer values for each major data category (permits, routing records, entities, inspections). A timestamp indicates data freshness. A second identical request within the cache window returns the same values without re-querying the database. If the database is unavailable, the response returns pre-configured fallback values rather than an error.
**Edge cases seen in code:** Rate limiting applies per-IP; DB unavailable returns hardcoded values not nulls
**CC confidence:** medium
**Status:** PENDING REVIEW

---

### REWRITTEN-2: "Landing page renders correctly on mobile (375px)"
**Before (implementation-specific):**
> Single column layout. Hero section stacks (no split). Capability cards are in a horizontal scroll strip... 480px breakpoint reduces font size.

**After (outcome-focused):**

## SUGGESTED SCENARIO: Landing page is usable on a phone without horizontal scrolling
**Source:** Sprint 69 S1 — landing.html responsive design
**User:** homeowner
**Starting state:** Viewing sfpermits.ai on a phone-sized viewport.
**Goal:** Use the landing page comfortably on mobile — search for an address, read about the platform, understand the CTA.
**Expected outcome:** All content is accessible without side-scrolling. The search bar is reachable and tappable. Capability highlights are browsable (horizontal swipe or vertical stack). Data stats are readable. All interactive elements are large enough to tap comfortably.
**Edge cases seen in code:** Capability cards use scroll-snap for horizontal swiping; header actions collapse at small widths
**CC confidence:** high
**Status:** PENDING REVIEW

---

### REWRITTEN-3: "Design system CSS loads without breaking existing authenticated pages"
**Before (implementation-specific):**
> body.obsidian class is only on the landing page; other pages don't have it. style.css now has @import for design-system.css. Existing :root vars in inline styles may conflict...

**After (outcome-focused):**

## SUGGESTED SCENARIO: Design system styles are isolated to new pages and do not alter existing authenticated pages
**Source:** Sprint 69 S1 — design-system.css scoping
**User:** expediter
**Starting state:** Logged-in user viewing their dashboard, morning brief, or account page after a design system CSS update.
**Goal:** Navigate normally — any new CSS introduced for the landing page must not visually alter authenticated app pages.
**Expected outcome:** All previously-working authenticated pages render exactly as before: no color changes, no font changes, no layout shifts. New design system classes only affect pages that explicitly opt in.
**Edge cases seen in code:** Global :root vars can leak across pages if not scoped; test at 375px and 1280px
**CC confidence:** high
**Status:** PENDING REVIEW

---

### REWRITTEN-4: "PWA manifest enables add-to-homescreen"
**Before (implementation-specific):**
> The browser offers an "Add to Home Screen" prompt... theme color (#22D3EE)... Icons are placeholders — real branded icons needed before this is production-ready. iOS requires additional meta tags in the HTML head.

**After (outcome-focused):**

## SUGGESTED SCENARIO: App can be installed to a phone home screen
**Source:** web/static/manifest.json (Sprint 69 S4)
**User:** homeowner
**Starting state:** User visits sfpermits.ai on a mobile device (iOS or Android) using a supported browser.
**Goal:** Save sfpermits.ai to their home screen for quick daily access.
**Expected outcome:** The browser signals that the app is installable (install prompt or browser menu option available). Once installed, the app opens in a standalone window without browser chrome. The app name, icon, and color theme are consistent with the brand.
**Edge cases seen in code:** Icons currently placeholder — branded icons needed; iOS requires additional <meta> tags separate from manifest
**CC confidence:** medium
**Status:** PENDING REVIEW

---

### REWRITTEN-5: "robots.txt allows public pages while blocking admin routes"
**Before (implementation-specific):**
> GET /robots.txt returns 200 with Allow: / and Disallow directives for /admin/, /cron/, /api/, /auth/, /demo, /account, /brief, /projects. Includes Sitemap reference.

**After (outcome-focused):**

## SUGGESTED SCENARIO: Search crawlers are guided to index public content and excluded from private routes
**Source:** web/app.py robots.txt (Sprint 69 S4)
**User:** admin
**Starting state:** Search engine crawler visits the site for the first time.
**Goal:** Ensure public permit and methodology pages are indexable while admin, auth, and internal routes are not crawled.
**Expected outcome:** A robots.txt file is publicly accessible and contains clear crawl directives. Public pages (landing, search, methodology, about-data) are permitted. Admin, cron, auth, and account sections are disallowed. A sitemap reference is included for search engine discovery.
**Edge cases seen in code:** Allow: / directive precedence must come before Disallow lines for correct interpreter behavior
**CC confidence:** high
**Status:** PENDING REVIEW

---

### REWRITTEN-6: "Anonymous user clicking Prep Checklist is redirected to login then back to /prep"
**Before (implementation-specific):**
> login_required redirects to auth.auth_login (no next parameter currently — user must manually navigate back)

**After (outcome-focused):**

## SUGGESTED SCENARIO: Unauthenticated user who tries to access a Permit Prep checklist is guided to log in
**Source:** web/routes_property.py /prep/<permit>
**User:** homeowner
**Starting state:** User is viewing public search results and is not logged in.
**Goal:** Access a Permit Prep checklist for a specific permit to start tracking required documents.
**Expected outcome:** When the user attempts to open a checklist, they are redirected to the login page. The login page is clearly presented and functional. After logging in, the user can navigate to their checklist.
**Edge cases seen in code:** Currently no automatic post-login redirect back to the checklist — user must navigate manually after login; this is a known gap
**CC confidence:** medium
**Status:** PENDING REVIEW

---

### REWRITTEN-7: "Admin reviews stale task inventory"
**Before (implementation-specific):**
> Admin has access to Chief brain state with 50+ open tasks accumulated over multiple sprints... Tasks may reference features that were built under different task numbers (e.g., #207 "orphaned test files" was wrong...).

**After (outcome-focused):**

## SUGGESTED SCENARIO: Admin can identify and close obsolete infrastructure tasks
**Source:** QS5-D task hygiene diagnostic sweep
**User:** admin
**Starting state:** Many open tasks have accumulated over multiple sprints, some referencing features that were already delivered.
**Goal:** Review open tasks, close those that are done, and create focused follow-ups for items that remain outstanding.
**Expected outcome:** Admin can distinguish between: tasks completed (close with evidence), tasks superseded by later work (close with note), and tasks still needed (update description to current understanding). After the review, the open task count is meaningfully reduced and remaining tasks have accurate descriptions.
**Edge cases seen in code:** Task descriptions may refer to sprint numbers or feature names that predate current architecture
**CC confidence:** high
**Status:** PENDING REVIEW

---

## KEPT (15)

These are valid, outcome-focused, not covered by existing approved scenarios. Left as PENDING REVIEW for Tim.

---

## SUGGESTED SCENARIO: Portfolio brief contains accurate project statistics
**Source:** docs/portfolio-brief.md (Sprint 69 S4)
**User:** admin
**Starting state:** Portfolio brief document exists in the repository
**Goal:** Verify that all statistics cited in the portfolio brief match actual codebase metrics
**Expected outcome:** Test count, tool count, entity count, sprint count, and other numbers in the portfolio brief match the values derivable from the codebase (pytest collection count, server.py tool registrations, CHANGELOG sprint headers, etc.)
**Edge cases seen in code:** Numbers change every sprint — the brief must be updated or use ranges
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Model release probes cover all capability categories
**Source:** docs/model-release-probes.md (Sprint 69 S4)
**User:** admin
**Starting state:** Model release probes document exists with 14 probes across 6 categories
**Goal:** Validate that the probe set covers all major capabilities of the sfpermits.ai platform
**Expected outcome:** At least 2 probes per category (permit prediction, vision analysis, multi-source synthesis, entity reasoning, specification quality, domain knowledge), each with prompt text, expected capability, and scoring criteria
**Edge cases seen in code:** New tools or capabilities added in future sprints should trigger new probes
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Technical visitor reads methodology page
**Source:** web/templates/methodology.html (Sprint 69 S3)
**User:** architect
**Starting state:** Visitor lands on sfpermits.ai and wants to understand the data quality before trusting estimates
**Goal:** Read the methodology page and understand how timeline estimates, fee calculations, and entity resolution work
**Expected outcome:** Visitor finds substantive methodology sections (at minimum: data sources, entity resolution, timeline modeling, limitations), a data provenance table with source identifiers, and at least one worked example. Visitor gains confidence in the tool's transparency.
**Edge cases seen in code:** Mobile view replaces CSS flowchart with numbered list; station velocity data may be unavailable (fallback model documented)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Visitor navigates to about-data page
**Source:** web/templates/about_data.html (Sprint 69 S3)
**User:** homeowner
**Starting state:** Visitor sees a data transparency link in navigation
**Goal:** Understand what data sfpermits.ai uses and how fresh it is
**Expected outcome:** Visitor sees a complete data inventory with dataset names, record volumes, and freshness schedule. Nightly pipeline schedule is described. Knowledge base tiers are explained. QA coverage statistics are present.
**Edge cases seen in code:** Planning data refreshes weekly not nightly; property data refreshes annually
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Tim shares demo URL with potential clients before signing up
**Source:** web/templates/demo.html + public demo route (Sprint 69 S3)
**User:** admin
**Starting state:** Tim opens the demo page in a browser before showing it to a prospective client
**Goal:** Show all intelligence layers for a real SF property in one screen, without the client needing to interact with the UI
**Expected outcome:** Page loads with pre-queried data for a demo address showing permit history, routing progress, timeline estimate, connected entities, and complaints/violations. Everything is visible on load without clicking. An annotation or label explains each section.
**Edge cases seen in code:** Database unavailable produces graceful degradation with empty states; a density parameter reduces padding for information-dense presentation
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Anonymous search shows routing progress for active permits
**Source:** Sprint 69-S2 search intelligence
**User:** homeowner
**Starting state:** Anonymous visitor on sfpermits.ai, not logged in
**Goal:** Search an address and understand how far along active permits are in city review
**Expected outcome:** Search results show permit cards plus a property intelligence panel with colored progress indicators showing how far each active permit has progressed through review stations. Station names are visible. No login required to see this summary view.
**Edge cases seen in code:** Property with no active permits (empty routing), property with many permits (capped display), routing data timeout (2-second deadline returns graceful empty state)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Intelligence panel loads after initial page without blocking permit results
**Source:** Sprint 69-S2 search results progressive enhancement
**User:** homeowner
**Starting state:** Anonymous visitor searches an address
**Goal:** See permit results immediately while intelligence enrichment loads asynchronously
**Expected outcome:** Permit result cards render on the initial page load. An intelligence panel (routing progress, entity names, complaints/violations summary) appears in a separate panel and loads independently. A loading state is visible while the intel is being fetched. If intel fails to load, the permit cards remain fully functional.
**Edge cases seen in code:** HTMX failure (page still usable without intel); intelligence timeout shows a retry then an empty state
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Anonymous visitor sees entity names on search but not the full network
**Source:** Sprint 69-S2 intel_preview gated content
**User:** homeowner
**Starting state:** Anonymous visitor views search results with the intelligence panel loaded
**Goal:** Understand who the key decision-makers are on a property's permits
**Expected outcome:** Top entities (contractor, architect, owner) are shown by name, role, and a permit count that establishes their experience level. A prompt to log in to see the full entity relationship network is present. The complete network graph, station velocity charts, and severity scores are not shown to anonymous users.
**Edge cases seen in code:** Property with no contacts data (entity section hidden); all contacts are generic/blank (filtered out)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Search results remain usable when intelligence enrichment times out
**Source:** Sprint 69-S2 address search timeout handling
**User:** homeowner
**Starting state:** Anonymous visitor searches an address; backend intelligence queries are slow
**Goal:** Still see the basic permit list even when property intelligence enrichment cannot complete in time
**Expected outcome:** Permit cards always load and are the primary content. If the intelligence panel cannot load within its deadline, it shows a loading indicator with one auto-retry. If retry also times out, the panel shows a compact empty state. No error page, no broken layout, no JavaScript console errors visible to the user.
**Edge cases seen in code:** SODA API down (complaints/violations count stays 0); DuckDB connection fails (all enrichment catches exceptions); partial data returned (intel panel shows what succeeded)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Circuit breaker skips slow enrichment queries after repeated timeouts
**Source:** QS3-B — CircuitBreaker in src/db.py + permit_lookup integration
**User:** expediter | architect
**Starting state:** Three consecutive permit lookups have timed out on the same type of enrichment query (e.g., inspections) due to database load
**Goal:** Subsequent permit lookups remain fast and responsive despite the degraded database condition
**Expected outcome:** After a threshold of failures within a short window, that enrichment category is skipped automatically. Subsequent lookups show a "temporarily unavailable" note for that section instead of waiting for a timeout. After a cooldown period, the next lookup retries the enrichment. A successful enrichment resets the failure tracking.
**Edge cases seen in code:** Different enrichment categories (contacts, addenda, related_team, planning_records, boiler_permits) have independent circuit breakers
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Health endpoint reports circuit breaker states and cron worker liveness
**Source:** QS3-B — /health enhancement
**User:** admin
**Starting state:** Admin is monitoring system health; cron heartbeat job runs on a regular schedule
**Goal:** Quickly assess whether enrichment queries are degraded and whether the cron worker is alive
**Expected outcome:** The health response includes the current state of each enrichment circuit breaker (closed/open, how many failures, when it reopens). It also includes how long ago the cron worker last reported in, with a status indicator (OK / WARNING / CRITICAL) based on elapsed time.
**Edge cases seen in code:** In local dev mode (DuckDB), heartbeat query gracefully falls back when cron_log table doesn't exist; circuit breaker status is empty when no failures have been recorded
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: User creates a Permit Prep checklist for an existing permit and sees categorized document requirements
**Source:** web/permit_prep.py, web/routes_property.py
**User:** expediter | architect
**Starting state:** User is logged in. A permit exists in the database.
**Goal:** Generate a document tracking checklist for a permit submission.
**Expected outcome:** User can initiate a checklist for a known permit. The checklist shows document requirements grouped by category (e.g., Required Plans, Application Forms, Supplemental Documents, Agency-Specific). All items start in a "Required" state. A progress indicator shows 0% addressed.
**Edge cases seen in code:** Permit not found in DB (falls back to general project type); tool failure (falls back to minimal item set); creating a checklist for a permit that already has one returns the existing checklist
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: User marks a document as submitted and the checklist progress updates
**Source:** web/routes_api.py — prep item status toggle
**User:** expediter | architect
**Starting state:** User has an active Permit Prep checklist with items in "Required" status.
**Goal:** Record that a document has been submitted to the city.
**Expected outcome:** User changes an item's status (e.g., to "Submitted"). The item card updates to reflect the new status. The overall checklist progress indicator updates to show the new completion percentage. The change is persisted so it survives a page reload.
**Edge cases seen in code:** Invalid status value rejected; wrong user ownership rejected; concurrent updates on same item
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Preview Mode shows predicted document requirements without saving a checklist
**Source:** web/permit_prep.py preview_checklist()
**User:** homeowner | architect
**Starting state:** User is logged in but has not yet created a checklist for this permit.
**Goal:** See what documents would be required before committing to creating a tracked checklist.
**Expected outcome:** A preview shows the predicted document requirements grouped by category, with the review path and agencies involved. No checklist is created in the database as a result of viewing the preview. The user can then choose to create a real checklist from the preview.
**Edge cases seen in code:** Permit not in database (uses fallback description); prediction tool timeout; preview data not persisted
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Morning brief flags permits with incomplete prep checklists
**Source:** web/brief.py _get_prep_summary()
**User:** expediter
**Starting state:** User has one or more Permit Prep checklists with items still in "Required" status.
**Goal:** See at a glance which permits need document attention during the daily review.
**Expected outcome:** Morning brief includes a permit prep section listing each permit with an active checklist, showing how many items are outstanding. Permits with missing required documents are surfaced as needing attention.
**Edge cases seen in code:** prep_checklists table doesn't exist yet (returns empty list gracefully); user has no checklists (section is absent, not an error)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## Processing Notes

- Scenarios 1-25 processed from scenarios-pending-review.md (lines 11-289)
- Next batch to process: scenarios 26-50 (line 290 onward)
- Three scenarios were identified as duplicates of approved scenarios (SCENARIO 37, 38, 40 in scenario-design-guide.md)
- Seven scenarios were rewritten to remove route paths, CSS class names, JSON field names, and endpoint-specific implementation details
- Fifteen scenarios were kept as-is — they describe observable user outcomes without implementation coupling

## Durability Spectrum Applied

**Removed patterns (implementation-specific):**
- Endpoint paths (/api/stats, /cron/, auth.auth_login)
- JSON field names (routing_records, last_refresh, today_changes)
- CSS class names (body.obsidian, horizontal scroll strip)
- Pixel breakpoints (480px breakpoint reduces font size)
- Theme hex colors (#22D3EE)
- Internal component references (scroll-snap, version_group column, blueprint names)

**Preserved patterns (outcome-focused):**
- User-visible behaviors (results appear, progress updates, page is navigable)
- Error states the user would notice (no broken layout, no NaN, graceful empty state)
- Security boundaries (anonymous vs authenticated feature access)
- Performance characteristics (loads asynchronously, doesn't block main content)
