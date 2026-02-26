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

## SUGGESTED SCENARIO: Anonymous search shows routing progress
**Source:** Sprint 69-S2 search intelligence (/lookup/intel-preview)
**User:** homeowner
**Starting state:** Anonymous visitor on sfpermits.ai, not logged in
**Goal:** Search an address and understand how far along active permits are in review
**Expected outcome:** Search results show permit list plus intelligence panel with colored progress bars showing "X of Y stations cleared" for each active permit. Station names visible. No login required.
**Edge cases seen in code:** Property with no active permits (empty routing), property with >10 permits (capped), routing data timeout (2-second deadline)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Intelligence panel loads asynchronously
**Source:** Sprint 69-S2 search results HTMX progressive enhancement
**User:** homeowner
**Starting state:** Anonymous visitor searches an address
**Goal:** See permit results immediately, then intelligence loads after
**Expected outcome:** Permit result cards render first (fast). Intelligence panel appears in sidebar (desktop) or expandable section (mobile) via HTMX after initial page load. Loading spinner visible while intel loads.
**Edge cases seen in code:** HTMX fails to load (page still usable without intel), intelligence timeout returns retry spinner once then gives up
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Anonymous visitor sees entity names but not full network
**Source:** Sprint 69-S2 intel_preview.html gated content
**User:** homeowner
**Starting state:** Anonymous visitor views search results with intelligence panel
**Goal:** See who the key players are on a property's permits
**Expected outcome:** Top 3 entities shown by name, role, and SF permit count (e.g., "Architect: Smith & Associates (47 SF permits)"). "See full network analysis" link goes to login gate. Full entity network graph, station velocity, and severity scores are NOT shown.
**Edge cases seen in code:** Property with no contacts data (entity section hidden), all contacts are "N/A" (filtered out)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Search results degrade gracefully on intel timeout
**Source:** Sprint 69-S2 _gather_intel timeout logic
**User:** homeowner
**Starting state:** Anonymous visitor searches an address, backend intelligence queries are slow
**Goal:** Still see permit results even if intelligence fails
**Expected outcome:** Permit cards always appear. If intelligence gathering exceeds 2-second deadline, intel panel shows "Loading..." spinner with one auto-retry. If retry also times out, panel shows empty state. No error page, no broken layout.
**Edge cases seen in code:** SODA API down (complaints/violations count stays 0), DuckDB connection fails (_gather_intel catches all exceptions), partial data returned (has_intelligence based on any non-empty section)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Mobile search results expandable intelligence
**Source:** Sprint 69-S2 mobile responsive layout
**User:** homeowner
**Starting state:** Anonymous visitor on mobile device (< 1024px) views search results
**Goal:** Access property intelligence without leaving the page
**Expected outcome:** Intelligence panel is hidden by default on mobile. "View property intelligence" button is visible below permit cards. Tapping it expands the intel section inline. HTMX loads content on first expansion.
**Edge cases seen in code:** No block/lot resolved (toggle button hidden), viewport resize between mobile and desktop (JS media query handler switches display)
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Circuit breaker auto-skips enrichment queries after repeated timeouts
**Source:** QS3-B — CircuitBreaker in src/db.py + permit_lookup.py integration
**User:** expediter | architect
**Starting state:** Three consecutive permit lookups have timed out on the inspections query (database under heavy load)
**Goal:** Subsequent permit lookups should remain fast and responsive despite the degraded database
**Expected outcome:** After 3 failures within 2 minutes, the circuit breaker opens for the "inspections" category. Subsequent permit lookups skip the inspections query entirely and show "temporarily unavailable (circuit breaker open)" instead. After 5 minutes cooldown, the circuit breaker closes and the next lookup retries the inspections query. Successful query resets the failure count.
**Edge cases seen in code:** Different enrichment categories (contacts, addenda, related_team, planning_records, boiler_permits) have independent circuit breakers. A circuit breaker opening for one category does not affect others.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Health endpoint shows circuit breaker states and cron heartbeat age
**Source:** QS3-B — /health enhancement in web/app.py
**User:** admin
**Starting state:** Admin monitoring the health endpoint, cron heartbeat running every 15 minutes
**Goal:** Quickly assess system health including circuit breaker states and cron worker liveness
**Expected outcome:** GET /health returns JSON with "circuit_breakers" dict showing each category as "closed" or "open (N failures, reopens in Xm)". Also includes "cron_heartbeat_age_minutes" (float) and "cron_heartbeat_status" (OK/WARNING/CRITICAL). Heartbeat age > 30 min = WARNING, > 120 min = CRITICAL, no data = NO_DATA.
**Edge cases seen in code:** In DuckDB dev mode, heartbeat query gracefully falls back when cron_log table doesn't exist (returns NO_DATA). Circuit breaker status is empty dict when no failures have been recorded.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Pipeline summary shows elapsed time per nightly step
**Source:** QS3-B — _timed_step wrapper + GET /cron/pipeline-summary
**User:** admin
**Starting state:** Nightly pipeline has completed its most recent run
**Goal:** Review which pipeline steps are slow or erroring to diagnose operational issues
**Expected outcome:** GET /cron/pipeline-summary returns JSON with per-step entries including job_type, elapsed_seconds, status (ok/error), and timestamps. The nightly pipeline response includes a "step_timings" dict with elapsed seconds for each post-processing step. Steps that error still record their elapsed time.
**Edge cases seen in code:** Pipeline summary is read-only with no auth. Step timing survives exceptions — _timed_step catches errors and still records elapsed. The main SODA fetch has its own cron_log tracking.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: PostHog tracks page views for anonymous visitors without blocking page load
**Source:** QS3-D PostHog integration (web/helpers.py, web/app.py, landing.html)
**User:** homeowner | new visitor
**Starting state:** POSTHOG_API_KEY env var is set on production. Anonymous visitor loads the landing page.
**Goal:** Analytics tracking captures page views and search events without degrading page load performance.
**Expected outcome:** PostHog JS loads asynchronously (async attribute). Server-side after_request hook fires posthog_track() for page views and search events. If POSTHOG_API_KEY is not set, both JS snippet and server hook are complete no-ops — zero overhead. Page renders identically with or without PostHog configured.
**Edge cases seen in code:** PostHog capture fails silently (exception swallowed), /static/ and /health paths excluded from tracking, anonymous users tracked as "anonymous" distinct_id
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Feature flag permit_prep_enabled gates Permit Prep feature rollout
**Source:** QS3-D PostHog feature flags (web/helpers.py, web/app.py)
**User:** admin | expediter
**Starting state:** POSTHOG_API_KEY is set. PostHog dashboard has permit_prep_enabled flag configured for specific user IDs.
**Goal:** Permit Prep features are only visible to users whose PostHog feature flags include permit_prep_enabled=True.
**Expected outcome:** g.posthog_flags is populated in before_request for authenticated users (populated from PostHog API). Anonymous users always get empty flags dict. Templates can check g.posthog_flags.get("permit_prep_enabled") to conditionally render Permit Prep UI. If PostHog is not configured, flags are always empty — features default to hidden.
**Edge cases seen in code:** PostHog get_all_flags() returns None (coerced to {}), PostHog API timeout (swallowed, returns {}), flag key not in dict (template uses .get() with default)
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: User creates Permit Prep checklist for an existing permit and sees categorized document requirements
**Source:** web/permit_prep.py, web/routes_property.py
**User:** expediter | architect
**Starting state:** User is logged in. A permit exists in the database.
**Goal:** Generate a document checklist to track what's needed for permit submission.
**Expected outcome:** User navigates to /prep/<permit_number>. System calls predict_permits and required_documents to generate a categorized checklist. Items are grouped into Required Plans, Application Forms, Supplemental Documents, and Agency-Specific. All items start with "Required" status. Progress bar shows 0% addressed.
**Edge cases seen in code:** Permit not found in DB (falls back to "general alterations" description), tool failure (falls back to 3 minimal items), duplicate checklist creation (returns existing)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: User toggles document status from Required to Submitted and progress bar updates
**Source:** web/routes_api.py PATCH /api/prep/item/<id>, web/templates/fragments/prep_item.html
**User:** expediter | architect
**Starting state:** User has an active Permit Prep checklist with items in "Required" status.
**Goal:** Track that a document has been submitted.
**Expected outcome:** User clicks "Submitted" radio button on an item. HTMX PATCH request updates the item status in-place. The item card updates to show blue "Submitted" styling. Progress bar updates to reflect the new count.
**Edge cases seen in code:** Invalid status value rejected, wrong user ownership rejected (returns 404), concurrent updates on same item
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Preview Mode shows predicted checklist for a permit without saving
**Source:** web/permit_prep.py preview_checklist(), /api/prep/preview/<permit>
**User:** homeowner | architect
**Starting state:** User is logged in but has not yet created a checklist for this permit.
**Goal:** See what documents would be required before committing to a checklist.
**Expected outcome:** GET /api/prep/preview/<permit> returns a JSON response with is_preview=true, items grouped by category, and prediction metadata (form, review path, agencies). No checklist row is created in the database. User can then decide to create a real checklist.
**Edge cases seen in code:** Permit not in database (uses fallback description), prediction tool timeout
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Morning brief shows permits with incomplete checklists
**Source:** web/brief.py _get_prep_summary()
**User:** expediter
**Starting state:** User has one or more Permit Prep checklists with items still in "Required" status.
**Goal:** See at a glance which permits need attention during the morning brief.
**Expected outcome:** Morning brief data includes prep_summary with a list of checklists showing permit_number, total_items, completed_items, and missing_required counts. Permits with missing items are highlighted.
**Edge cases seen in code:** prep_checklists table doesn't exist yet (returns empty list gracefully), user has no checklists (returns empty list)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Anonymous user clicking Prep Checklist is redirected to login then back to /prep
**Source:** web/routes_property.py /prep/<permit>, web/helpers.py login_required
**User:** homeowner
**Starting state:** User is not logged in. Viewing public search results.
**Goal:** Access a Permit Prep checklist for a specific permit.
**Expected outcome:** User clicks "Prep Checklist" button on search results. Since /prep requires authentication, they are redirected to /auth/login. After logging in, they should be able to navigate to /prep/<permit_number> to see their checklist.
**Edge cases seen in code:** login_required redirects to auth.auth_login (no next parameter currently — user must manually navigate back)
**CC confidence:** medium
**Status:** PENDING REVIEW
