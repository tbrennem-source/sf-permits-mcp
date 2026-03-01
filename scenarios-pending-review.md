# Scenarios Pending Review
<!-- CC appends suggested scenarios here after each feature session -->
<!-- Do not edit scenario-design-guide.md directly -->
<!-- This file is reviewed and drained each planning session -->
<!-- Drained Sprint 68-A: 102 scenarios reviewed, 48 accepted, 30 merged, 22 rejected, 2 deferred -->
<!-- Sprint 85-B consolidation: 38 per-agent files merged, deduped, and deleted -->
<!-- See scenarios-reviewed-sprint68.md for full review log -->

_Last reviewed: Sprint 68-A (2026-02-26)_
_Consolidated: Sprint 85-B (2026-02-27) — 116 unique scenarios, 27 duplicates flagged_
_Appended: QS9 hotfix session (2026-02-28) — 4 scenarios_

---

## SUGGESTED SCENARIO: post-form-csrf-protection
**Source:** CSRF hotfix session (nav.html, head_obsidian.html)
**User:** authenticated user (any role)
**Starting state:** User is logged in and interacts with a POST form (e.g., logout, feedback, plan upload)
**Goal:** Submit the form and complete the action
**Expected outcome:** Form submits successfully; no 403 error; action completes
**Edge cases seen in code:** TESTING mode disables CSRF — tests pass even when csrf_token is missing; production fails
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: htmx-post-action-csrf
**Source:** CSRF hotfix — HTMX hx-post requests
**User:** authenticated user
**Starting state:** User is on any page using HTMX for server interactions (search, feedback, toggles)
**Goal:** Trigger an HTMX POST action
**Expected outcome:** Request succeeds; X-CSRFToken header included automatically; action completes
**Edge cases seen in code:** Templates not using head_obsidian.html do not inherit the global listener
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: admin-tour-url-only
**Source:** admin-tour.js cookie persistence bug
**User:** admin
**Starting state:** Admin previously visited a page with ?tour=1; now navigates elsewhere without ?tour=1
**Goal:** Browse normally without the QA tour appearing
**Expected outcome:** Tour does not launch; no cookie persists tour state across page loads
**Edge cases seen in code:** Stale qa_tour cookie must be actively cleared on load
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: qa-feedback-panel-pending-only
**Source:** admin-feedback.js synced-item prune
**User:** admin
**Starting state:** Admin submits QA feedback; feedback syncs to server successfully
**Goal:** See only unresolved/pending feedback in the panel
**Expected outcome:** Synced items disappear from the panel after sync; count badge shows pending count only; on next page load, synced items are pruned from localStorage
**Edge cases seen in code:** Items that fail to sync remain visible until manually cleared via "Clear local"
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## Summary Table

| Category | Count |
|---|---|
| Search & Public Access | 18 |
| Property Intelligence & Reports | 12 |
| Admin & Operations | 22 |
| Performance & Infrastructure | 20 |
| Onboarding & Auth | 14 |
| Security | 8 |
| Design System & UI | 8 |
| MCP Tools (Permit Intelligence) | 21 |
| Data Ingest & Pipeline | 7 |
| **Total unique** | **130** |
| Duplicates flagged | 27 |

---

## SEARCH & PUBLIC ACCESS

## SUGGESTED SCENARIO: Anonymous visitor sees live data counts on landing page
**Source:** Sprint 69 S1 — landing.html rewrite + /api/stats endpoint
**User:** homeowner
**Starting state:** User has never visited sfpermits.ai. Not logged in.
**Goal:** Understand the scale and credibility of the platform within 10 seconds of landing.
**Expected outcome:** Landing page shows permit count, routing record count, entity count, and inspection count. Numbers are non-zero and formatted for readability (e.g. "1.1M+"). Data pulse panel shows a green status dot and "Live Data Pulse" label.
**Edge cases seen in code:** If /api/stats fails or DB is unavailable, fallback numbers already baked into HTML render correctly. Numbers don't show "undefined" or "NaN".
**CC confidence:** high
**Status:** PENDING REVIEW
**DUPLICATE OF:** SCENARIO 37 (Anonymous user discovers site via landing page) + SCENARIO 73 (ADU landing page shows pre-computed permit stats) — flagged by QS7-4D. Rewritten version below preferred.

---

## SUGGESTED SCENARIO: Data counts endpoint returns fresh platform statistics with graceful fallback
**Source:** Sprint 69 S1 — /api/stats endpoint (rewritten by QS7-4D)
**User:** architect
**Starting state:** The platform data counts have not been requested externally in the last hour.
**Goal:** Fetch current data volume statistics for display or integration (permits indexed, entities resolved, inspections tracked).
**Expected outcome:** A data counts request returns integer values for each major data category (permits, routing records, entities, inspections). A timestamp indicates data freshness. A second identical request within the cache window returns the same values without re-querying the database. If the database is unavailable, the response returns pre-configured fallback values rather than an error.
**Edge cases seen in code:** Rate limiting applies per-IP; DB unavailable returns hardcoded values not nulls
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Landing page search bar submits to /search endpoint
**Source:** Sprint 69 S1 — landing.html hero search form
**User:** homeowner
**Starting state:** On the sfpermits.ai landing page, not logged in.
**Goal:** Search for a property by address to see permit history.
**Expected outcome:** Typing an address in the search bar and pressing Enter (or clicking Search) navigates to search results. Search results page renders with results or a "no results" message.
**Edge cases seen in code:** Empty query redirects to /. Suggested address codes (1455 Market St) are clickable and pre-fill the input. Search is rate limited at 15 requests/window.
**CC confidence:** high
**Status:** PENDING REVIEW
**DUPLICATE OF:** SCENARIO 37 (search box present) + SCENARIO 38 (anonymous user searches and sees public results)

---

## SUGGESTED SCENARIO: Landing page is usable on a phone without horizontal scrolling
**Source:** Sprint 69 S1 — landing.html responsive design (rewritten by QS7-4D)
**User:** homeowner
**Starting state:** Viewing sfpermits.ai on a phone-sized viewport.
**Goal:** Use the landing page comfortably on mobile — search for an address, read about the platform, understand the CTA.
**Expected outcome:** All content is accessible without side-scrolling. The search bar is reachable and tappable. Capability highlights are browsable (horizontal swipe or vertical stack). Data stats are readable. All interactive elements are large enough to tap comfortably.
**Edge cases seen in code:** Capability cards use scroll-snap for horizontal swiping; header actions collapse at small widths
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Design system styles are isolated to new pages and do not alter existing authenticated pages
**Source:** Sprint 69 S1 — design-system.css scoping (rewritten by QS7-4D)
**User:** expediter
**Starting state:** Logged-in user viewing their dashboard, morning brief, or account page after a design system CSS update.
**Goal:** Navigate normally — any new CSS introduced for the landing page must not visually alter authenticated app pages.
**Expected outcome:** All previously-working authenticated pages render exactly as before: no color changes, no font changes, no layout shifts. New design system classes only affect pages that explicitly opt in.
**Edge cases seen in code:** Global :root vars can leak across pages if not scoped; test at 375px and 1280px
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Anonymous search shows routing progress for active permits
**Source:** Sprint 69-S2 search intelligence (rewritten by QS7-4D)
**User:** homeowner
**Starting state:** Anonymous visitor on sfpermits.ai, not logged in
**Goal:** Search an address and understand how far along active permits are in city review
**Expected outcome:** Search results show permit cards plus a property intelligence panel with colored progress indicators showing how far each active permit has progressed through review stations. Station names are visible. No login required to see this summary view.
**Edge cases seen in code:** Property with no active permits (empty routing), property with many permits (capped display), routing data timeout (2-second deadline returns graceful empty state)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Intelligence panel loads after initial page without blocking permit results
**Source:** Sprint 69-S2 search results progressive enhancement (rewritten by QS7-4D)
**User:** homeowner
**Starting state:** Anonymous visitor searches an address
**Goal:** See permit results immediately while intelligence enrichment loads asynchronously
**Expected outcome:** Permit result cards render on the initial page load. An intelligence panel (routing progress, entity names, complaints/violations summary) appears in a separate panel and loads independently. A loading state is visible while the intel is being fetched. If intel fails to load, the permit cards remain fully functional.
**Edge cases seen in code:** HTMX failure (page still usable without intel); intelligence timeout shows a retry then an empty state
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Anonymous visitor sees entity names on search but not the full network
**Source:** Sprint 69-S2 intel_preview gated content (rewritten by QS7-4D)
**User:** homeowner
**Starting state:** Anonymous visitor views search results with the intelligence panel loaded
**Goal:** Understand who the key decision-makers are on a property's permits
**Expected outcome:** Top entities (contractor, architect, owner) are shown by name, role, and a permit count that establishes their experience level. A prompt to log in to see the full entity relationship network is present. The complete network graph, station velocity charts, and severity scores are not shown to anonymous users.
**Edge cases seen in code:** Property with no contacts data (entity section hidden); all contacts are generic/blank (filtered out)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Search results remain usable when intelligence enrichment times out
**Source:** Sprint 69-S2 address search timeout handling (rewritten by QS7-4D)
**User:** homeowner
**Starting state:** Anonymous visitor searches an address; backend intelligence queries are slow
**Goal:** Still see the basic permit list even when property intelligence enrichment cannot complete in time
**Expected outcome:** Permit cards always load and are the primary content. If the intelligence panel cannot load within its deadline, it shows a loading indicator with one auto-retry. If retry also times out, the panel shows a compact empty state. No error page, no broken layout, no JavaScript console errors visible to the user.
**Edge cases seen in code:** SODA API down (complaints/violations count stays 0); DuckDB connection fails (all enrichment catches exceptions); partial data returned (intel panel shows what succeeded)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Mobile search results expandable intelligence
**Source:** Sprint 69-S2 mobile responsive layout
**User:** homeowner
**Starting state:** Anonymous visitor on mobile device (< 1024px) views search results
**Goal:** Access property intelligence without leaving the page
**Expected outcome:** Intelligence panel is hidden by default on mobile. A reveal button is visible below permit cards. Tapping it expands the intel section inline. Content loads on first expansion.
**Edge cases seen in code:** No block/lot resolved (toggle button hidden), viewport resize between mobile and desktop (JS media query handler switches display)
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Search crawlers are guided to index public content and excluded from private routes
**Source:** web/app.py robots.txt (Sprint 69 S4) (rewritten by QS7-4D)
**User:** admin
**Starting state:** Search engine crawler visits the site for the first time.
**Goal:** Ensure public permit and methodology pages are indexable while admin, auth, and internal routes are not crawled.
**Expected outcome:** A robots.txt file is publicly accessible and contains clear crawl directives. Public pages (landing, search, methodology, about-data) are permitted. Admin, cron, auth, and account sections are disallowed. A sitemap reference is included for search engine discovery.
**Edge cases seen in code:** Allow: / directive precedence must come before Disallow lines for correct interpreter behavior
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Search engine indexes methodology and about-data
**Source:** web/routes_misc.py sitemap (Sprint 69 S3)
**User:** homeowner
**Starting state:** Google crawls sfpermits.ai's sitemap.xml
**Goal:** Methodology and about-data pages should be discoverable; demo page should not be indexed
**Expected outcome:** sitemap.xml includes /methodology and /about-data URLs. Demo page has noindex meta tag and is NOT in the sitemap.
**Edge cases seen in code:** Demo page intentionally excluded from sitemap to keep it unlisted
**CC confidence:** high
**Status:** PENDING REVIEW
**DUPLICATE OF:** Near-duplicate of "Search crawlers are guided to index public content" above — both cover robots.txt/sitemap behavior. Prefer the rewritten version above.

---

## SUGGESTED SCENARIO: authenticated address search returns permit results
**Source:** tests/e2e/test_search_scenarios.py / web/routes_search.py (Sprint 77-3)
**User:** expediter
**Starting state:** User is logged in. No search has been performed.
**Goal:** Search for a street name ("valencia") and see a list of matching permits.
**Expected outcome:** Search results page loads with permit data or a count of matching records. Page is not blank and contains permit-related content.
**Edge cases seen in code:** Authenticated users are redirected from /search to /?q= for the full experience.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: permit number lookup returns meaningful response
**Source:** tests/e2e/test_search_scenarios.py / web/routes_search.py (Sprint 77-3)
**User:** expediter
**Starting state:** User is logged in. A permit-style number is entered into search.
**Goal:** Look up a specific permit by its number and see the permit detail or a "not found" message.
**Expected outcome:** Page returns a result — either the permit detail, a "no results" message, or a search context explanation. Page must not show a server error.
**Edge cases seen in code:** If the permit number doesn't exist in the DB, the page should show a graceful "not found" state rather than crashing.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: empty search query handled gracefully
**Source:** tests/e2e/test_search_scenarios.py / web/routes_public.py (Sprint 77-3)
**User:** homeowner
**Starting state:** User (authenticated or anonymous) submits a search with an empty query string.
**Goal:** The app handles the empty query without crashing.
**Expected outcome:** User is redirected to the landing/index page or sees a helpful guidance message. No server error or blank page.
**Edge cases seen in code:** Whitespace-only queries are stripped and treated as empty.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Search query for address returns results or graceful empty state
**Source:** web/routes_public.py — /search route; SCENARIO-38 (Sprint 77-1)
**User:** homeowner
**Starting state:** Anonymous or authenticated user enters partial address ("market")
**Goal:** Find permits at a known address
**Expected outcome:** Search returns at least one result card referencing the search term, OR displays a clear "no results" message. Never returns blank page or Python traceback. XSS-escaped query reflected safely in the page.
**Edge cases seen in code:** Empty q= param is handled; XSS injection in q= is sanitized (SCENARIO-34)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: natural language address query resolves correctly
**Source:** web/helpers.py parse_search_query, web/routes_public.py public_search (QS8-T3-B)
**User:** homeowner
**Starting state:** User is on search and types a natural language query that contains a street address embedded in prose
**Goal:** Find permit records for their property using a plain-English description like "permits at 123 Market St"
**Expected outcome:** Permit records for 123 Market St are returned, not a "no results" page, even though the query wasn't a bare address
**Edge cases seen in code:** Intent router may classify as "analyze_project" if query contains action verbs — NLP parser upgrades to "search_address" when it finds street_number + street_name
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: neighborhood-scoped search shows guidance
**Source:** web/helpers.py parse_search_query, build_empty_result_guidance (QS8-T3-B)
**User:** expediter
**Starting state:** User searches "kitchen remodel in the Mission" with no specific address
**Goal:** Filter permit results to Mission neighborhood, or get helpful guidance on how to search
**Expected outcome:** Either filtered results are shown OR, if no results, contextual suggestions are shown that match the query intent (neighborhood + permit type)
**Edge cases seen in code:** "Mission" alias maps to "Mission" neighborhood; "in the Mission" prep phrase is stripped before passing residual text as description_search
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: zero results shows demo link and contextual suggestions
**Source:** web/routes_public.py public_search, web/helpers.py build_empty_result_guidance (QS8-T3-B)
**User:** homeowner
**Starting state:** User searches for something that returns no permit records
**Goal:** Get guidance on what to try next, not a dead end
**Expected outcome:** Page shows "No permits found", a contextual "Did you mean?" hint if applicable, example search links matching the query intent, and a link to /demo
**Edge cases seen in code:** build_empty_result_guidance inspects parsed dict to generate query-specific suggestions (not generic boilerplate)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: year filter extracted from natural language query
**Source:** web/helpers.py parse_search_query (_YEAR_RE) (QS8-T3-B)
**User:** expediter
**Starting state:** User types "new construction SoMa 2024"
**Goal:** Find new construction permits in South of Market filed in 2024
**Expected outcome:** NLP parser extracts neighborhood ("South of Market"), permit type ("new construction"), and year filter (2024-01-01 onwards)
**Edge cases seen in code:** Year must be in 2018-2030 range; year is extracted BEFORE address to prevent "2022" being parsed as a street number
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: result badges distinguish address vs permit vs description matches
**Source:** web/helpers.py rank_search_results (QS8-T3-B)
**User:** expediter
**Starting state:** Search returns a mix of exact address matches, permit number matches, and description keyword matches
**Goal:** Quickly identify which results are the most relevant
**Expected outcome:** Each result has a badge ("Address Match", "Permit", or "Description") and results are sorted with address matches first, then permit number matches, then description matches
**Edge cases seen in code:** badge is computed per result; ties within same type maintain original order
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## PROPERTY INTELLIGENCE & REPORTS

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

## SUGGESTED SCENARIO: Technical visitor reads methodology page
**Source:** web/templates/methodology.html (Sprint 69 S3) (rewritten by QS7-4D)
**User:** architect
**Starting state:** Visitor lands on sfpermits.ai and wants to understand the data quality before trusting estimates
**Goal:** Read the methodology page and understand how timeline estimates, fee calculations, and entity resolution work
**Expected outcome:** Visitor finds substantive methodology sections (at minimum: data sources, entity resolution, timeline modeling, limitations), a data provenance table with source identifiers, and at least one worked example. Visitor gains confidence in the tool's transparency.
**Edge cases seen in code:** Mobile view replaces CSS flowchart with numbered list; station velocity data may be unavailable (fallback model documented)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Visitor navigates to about-data page
**Source:** web/templates/about_data.html (Sprint 69 S3) (rewritten by QS7-4D)
**User:** homeowner
**Starting state:** Visitor sees a data transparency link in navigation
**Goal:** Understand what data sfpermits.ai uses and how fresh it is
**Expected outcome:** Visitor sees a complete data inventory with dataset names, record volumes, and freshness schedule. Nightly pipeline schedule is described. Knowledge base tiers are explained. QA coverage statistics are present.
**Edge cases seen in code:** Planning data refreshes weekly not nightly; property data refreshes annually
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Tim shares demo URL with potential clients before signing up
**Source:** web/templates/demo.html + public demo route (Sprint 69 S3) (rewritten by QS7-4D)
**User:** admin
**Starting state:** Tim opens the demo page in a browser before showing it to a prospective client
**Goal:** Show all intelligence layers for a real SF property in one screen, without the client needing to interact with the UI
**Expected outcome:** Page loads with pre-queried data for a demo address showing permit history, routing progress, timeline estimate, connected entities, and complaints/violations. Everything is visible on load without clicking. An annotation or label explains each section.
**Edge cases seen in code:** Database unavailable produces graceful degradation with empty states; a density parameter reduces padding for information-dense presentation
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Demo page serves property intelligence without auth
**Source:** web/routes_misc.py — /demo route; tests/e2e/test_severity_scenarios.py (Sprint 77-1)
**User:** homeowner (anonymous visitor)
**Starting state:** User has not logged in; arrives at /demo from a marketing link
**Goal:** Preview property intelligence before creating an account
**Expected outcome:** Demo page loads with pre-populated 1455 Market St data. Contains permit data, structured headings, and meaningful content. density=max parameter is accepted without error.
**Edge cases seen in code:** density_max param toggles a higher-density view; unexpected param values should not error
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Demo page shows severity tier for active permits
**Source:** web/routes_misc.py _get_demo_data() + web/templates/demo.html severity badges (Sprint 75-4)
**User:** expediter
**Starting state:** User navigates to /demo as an anonymous visitor
**Goal:** Understand at a glance whether the demo property has high-risk active permits
**Expected outcome:** A severity badge (CRITICAL/HIGH/MEDIUM/LOW/GREEN) appears on the hero section and inline with each active permit in the permit table; color distinguishes risk level
**Edge cases seen in code:** If DB is unavailable, severity_tier is None and the banner is simply not rendered — no error displayed
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Property report loads cached parcel data
**Source:** QS5-A parcel_summary cache integration in report.py
**User:** expediter | homeowner
**Starting state:** parcel_summary table has a row for block/lot with tax_value, zoning_code, use_definition
**Goal:** View a property report without waiting for SODA API tax data call
**Expected outcome:** Property profile section shows assessed value, zoning, and use definition from cache; SODA property tax API call is skipped; complaints and violations still fetched live
**Edge cases seen in code:** parcel_summary row exists but all tax fields are NULL; concurrent cron refresh while report is loading
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: property report loads fast for large parcels
**Source:** web/report.py _get_contacts_batch/_get_inspections_batch (QS8-T1-A)
**User:** expediter
**Starting state:** A parcel with 40+ permits (e.g., large commercial building) exists in the database. Each permit has multiple contacts and inspections.
**Goal:** Load the property report page without waiting 10+ seconds.
**Expected outcome:** Report renders in under 3 seconds. All permit contacts and inspections are present and correctly attributed to each permit.
**Edge cases seen in code:** Empty permit list returns empty contacts/inspections maps without any DB call. Permits with no contacts get an empty list (not an error). Permits with no permit_number are skipped in the batch.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: property report contacts are role-ordered per permit
**Source:** web/report.py _get_contacts_batch ORDER BY role priority (QS8-T1-A)
**User:** expediter
**Starting state:** A permit has contacts with roles: contractor, engineer, applicant.
**Goal:** View the property report and see contacts listed in a consistent order.
**Expected outcome:** Applicant appears first, then contractor, then engineer, then others. Order is consistent regardless of how data was inserted.
**Edge cases seen in code:** CASE WHEN ordering handles NULL/empty role strings via COALESCE — they sort last.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: SODA data is served from cache on rapid re-render
**Source:** web/report.py _soda_cache (15-min TTL) (QS8-T1-A)
**User:** expediter
**Starting state:** A property report was recently loaded (< 15 minutes ago). SODA API is available.
**Goal:** Load the same property report again (e.g., browser back-forward navigation or admin review).
**Expected outcome:** Second load is noticeably faster. SODA API is not called again. Complaints, violations, and property data are identical to the first load.
**Edge cases seen in code:** Cache is keyed by endpoint_id:block:lot — different parcels never share cache entries. Cache is module-level so it persists for the process lifetime.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: stale SODA cache is refreshed after TTL expires
**Source:** web/report.py _SODA_CACHE_TTL = 900 (QS8-T1-A)
**User:** expediter
**Starting state:** A property report was loaded 16 minutes ago. A new complaint was filed since then.
**Goal:** Load the property report and see the new complaint.
**Expected outcome:** SODA API is called fresh. The new complaint appears in the report. Old cached data is replaced.
**Edge cases seen in code:** TTL checked via time.monotonic() — not affected by system clock changes. Expired entries are replaced, not deleted first.
**CC confidence:** low
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Severity badge visible on permit lookup
**Source:** web/routes_search.py (_ask_permit_lookup + _get_severity_for_permit) (Sprint 76-3)
**User:** expediter
**Starting state:** User is logged in and searches for a specific permit number that is in the permits DB
**Goal:** Quickly assess the risk level of a permit without reading the full details
**Expected outcome:** A colored tier badge (CRITICAL / HIGH / MEDIUM / LOW / GREEN) appears alongside the permit result, reflecting the permit's computed severity score
**Edge cases seen in code:** Severity computation fails gracefully — if DB is unavailable or scoring raises, the badge is simply omitted rather than breaking the search result
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: morning brief shows pipeline health stats
**Source:** web/brief.py — _get_pipeline_stats(), get_morning_brief() (QS8-T1-B)
**User:** admin
**Starting state:** Nightly cron has run at least once; cron_log has records
**Goal:** User opens morning brief and sees pipeline health summary (avg job duration, 24h success/fail counts)
**Expected outcome:** Brief data includes pipeline_stats with recent_jobs list and 24h counts; average duration is computed from successful runs; non-fatal if cron_log is empty or unavailable
**Edge cases seen in code:** If DB unavailable, pipeline_stats returns {} — brief still renders without it
**CC confidence:** high
**Status:** PENDING REVIEW

---

## ADMIN & OPERATIONS

## SUGGESTED SCENARIO: Admin views station SLA compliance and identifies bottleneck departments
**Source:** QS4-A /admin/metrics dashboard
**User:** admin
**Starting state:** Admin is logged in, metrics data has been ingested
**Goal:** View which review stations are meeting their SLA targets and identify departments causing delays
**Expected outcome:** Dashboard shows station-level SLA percentages with color coding (green >= 80%, amber 60-79%, red < 60%), sorted by volume, enabling admin to identify bottleneck stations
**Edge cases seen in code:** NULL stations are excluded; zero-total stations handled to avoid division by zero; DuckDB BOOLEAN vs Postgres BOOLEAN for met_cal_sla
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Station velocity query returns cached results in under 100ms
**Source:** QS4-A station_velocity_v2 caching layer
**User:** expediter | architect
**Starting state:** Velocity cache has been populated by nightly cron job
**Goal:** Get station processing time estimates without waiting for a 3.9M-row addenda query
**Expected outcome:** Pre-computed velocity data returned from station_velocity_v2 table; falls back to 'all' period if requested period has no data; returns None gracefully on cache miss
**Edge cases seen in code:** Stale cache handled by nightly refresh; fallback from 'current' to 'all' period; CURRENT_WIDEN_DAYS=180 fallback when sample count < 30
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Nightly pipeline includes metrics refresh alongside permit data
**Source:** QS4-A run_ingestion() pipeline integration
**User:** admin
**Starting state:** Nightly ingestion pipeline runs on schedule
**Goal:** Ensure metrics datasets (issuance, review, planning) are refreshed during the main pipeline run, not only via separate cron endpoints
**Expected outcome:** run_ingestion() calls all 3 metrics ingest functions after dwelling_completions, keeping metrics data in sync with permit data
**Edge cases seen in code:** Metrics ingest runs outside the try block's feature-flag guards (always runs); individual metrics cron endpoints still available for manual refreshes
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Admin views request performance dashboard
**Source:** web/routes_admin.py (admin_perf route), web/templates/admin_perf.html (Sprint 74-1)
**User:** admin
**Starting state:** Admin is logged in. The app has been running for at least a few minutes and some requests have been sampled into request_metrics (slow requests > 200ms or 10% random sample).
**Goal:** Admin wants to understand which endpoints are slowest and what the overall latency profile looks like.
**Expected outcome:** Admin sees p50/p95/p99 latency stat blocks at the top, a table of the 10 slowest endpoints by p95, and a volume table showing traffic by path. Empty state messages appear if no data has been collected yet.
**Edge cases seen in code:** If the request_metrics table is empty (fresh deploy), all stat blocks show 0ms and both tables show an empty state message rather than errors.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Request metrics are sampled automatically
**Source:** web/app.py (_slow_request_log after_request hook) (Sprint 74-1)
**User:** admin
**Starting state:** Admin is observing the system. Any user makes requests to the app.
**Goal:** Admin wants request performance data to accumulate passively without manual instrumentation.
**Expected outcome:** Requests slower than 200ms are always recorded. Approximately 10% of all other requests are recorded via random sampling. Recording never causes a request to fail — DB errors in metric capture are swallowed silently and the response still returns normally.
**Edge cases seen in code:** The metric insert happens only when g._request_start is set (i.e., request went through _set_start_time). Static file requests that bypass the before_request hook will not be recorded.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Health endpoint shows circuit breaker states and cron heartbeat age
**Source:** QS3-B — /health enhancement in web/app.py
**User:** admin
**Starting state:** Admin monitoring the health endpoint, cron heartbeat running every 15 minutes
**Goal:** Quickly assess system health including circuit breaker states and cron worker liveness
**Expected outcome:** GET /health returns JSON with "circuit_breakers" dict showing each category as "closed" or "open (N failures, reopens in Xm)". Also includes "cron_heartbeat_age_minutes" (float) and "cron_heartbeat_status" (OK/WARNING/CRITICAL). Heartbeat age > 30 min = WARNING, > 120 min = CRITICAL, no data = NO_DATA.
**Edge cases seen in code:** In DuckDB dev mode, heartbeat query gracefully falls back when cron_log table doesn't exist (returns NO_DATA). Circuit breaker status is empty dict when no failures have been recorded.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Health endpoint reports circuit breaker states and cron worker liveness
**Source:** QS3-B — /health enhancement (rewritten by QS7-4D)
**User:** admin
**Starting state:** Admin is monitoring system health; cron heartbeat job runs on a regular schedule
**Goal:** Quickly assess whether enrichment queries are degraded and whether the cron worker is alive
**Expected outcome:** The health response includes the current state of each enrichment circuit breaker (closed/open, how many failures, when it reopens). It also includes how long ago the cron worker last reported in, with a status indicator (OK / WARNING / CRITICAL) based on elapsed time.
**Edge cases seen in code:** In local dev mode (DuckDB), heartbeat query gracefully falls back when cron_log table doesn't exist; circuit breaker status is empty when no failures have been recorded
**CC confidence:** high
**Status:** PENDING REVIEW
**DUPLICATE OF:** Substantively same as "Health endpoint shows circuit breaker states and cron heartbeat age" above. Prefer rewritten version.

---

## SUGGESTED SCENARIO: Pipeline summary shows elapsed time per nightly step
**Source:** QS3-B — _timed_step wrapper + GET /cron/pipeline-summary
**User:** admin
**Starting state:** Nightly pipeline has completed its most recent run
**Goal:** Review which pipeline steps are slow or erroring to diagnose operational issues
**Expected outcome:** GET /cron/pipeline-summary returns JSON with per-step entries including job_type, elapsed_seconds, status (ok/error), and timestamps. The nightly pipeline response includes a "step_timings" dict with elapsed seconds for each post-processing step. Steps that error still record their elapsed time.
**Edge cases seen in code:** Pipeline summary is read-only with no auth. Step timing survives exceptions — _timed_step catches errors and still records elapsed. The main SODA fetch has its own cron_log tracking.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: PostHog tracks page views for anonymous visitors without blocking page load
**Source:** QS3-D PostHog integration (web/helpers.py, web/app.py, landing.html)
**User:** homeowner | new visitor
**Starting state:** POSTHOG_API_KEY env var is set on production. Anonymous visitor loads the landing page.
**Goal:** Analytics tracking captures page views and search events without degrading page load performance.
**Expected outcome:** PostHog JS loads asynchronously (async attribute). Server-side after_request hook fires posthog_track() for page views and search events. If POSTHOG_API_KEY is not set, both JS snippet and server hook are complete no-ops — zero overhead. Page renders identically with or without PostHog configured.
**Edge cases seen in code:** PostHog capture fails silently (exception swallowed), /static/ and /health paths excluded from tracking, anonymous users tracked as "anonymous" distinct_id
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Feature flag permit_prep_enabled gates Permit Prep feature rollout
**Source:** QS3-D PostHog feature flags (web/helpers.py, web/app.py)
**User:** admin | expediter
**Starting state:** POSTHOG_API_KEY is set. PostHog dashboard has permit_prep_enabled flag configured for specific user IDs.
**Goal:** Permit Prep features are only visible to users whose PostHog feature flags include permit_prep_enabled=True.
**Expected outcome:** g.posthog_flags is populated in before_request for authenticated users (populated from PostHog API). Anonymous users always get empty flags dict. Templates can check g.posthog_flags.get("permit_prep_enabled") to conditionally render Permit Prep UI. If PostHog is not configured, flags are always empty — features default to hidden.
**Edge cases seen in code:** PostHog get_all_flags() returns None (coerced to {}), PostHog API timeout (swallowed, returns {}), flag key not in dict (template uses .get() with default)
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Severity cache populated by nightly cron
**Source:** web/routes_cron.py (cron_refresh_severity_cache), scripts/release.py (severity_cache DDL) (Sprint 76-3)
**User:** admin
**Starting state:** severity_cache table exists but is empty (fresh deploy or manual flush)
**Goal:** Populate the cache with scores for all active permits so search results load quickly
**Expected outcome:** POST /cron/refresh-severity-cache with correct CRON_SECRET bearer token processes up to 500 permits, upserts score/tier/drivers for each, and returns a JSON response with permits_scored count and elapsed time
**Edge cases seen in code:** Batch limited to 500 per run to prevent Railway timeouts; individual permit errors are counted separately and do not abort the batch
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: daily API usage aggregation rolls up to summary table
**Source:** web/cost_tracking.py aggregate_daily_usage + web/routes_cron.py cron_aggregate_api_usage (Sprint 76-2)
**User:** admin
**Starting state:** api_usage table has entries from yesterday's activity (user queries, plan analyses).
**Goal:** Nightly cron job runs POST /cron/aggregate-api-usage to produce a daily summary for the dashboard.
**Expected outcome:** api_daily_summary table has a row for yesterday with correct total_calls, total_cost_usd, and endpoint breakdown. Subsequent runs are idempotent (UPSERT). Admin cost dashboard reflects up-to-date daily totals.
**Edge cases seen in code:** Missing api_usage table handled gracefully (returns inserted=False, no crash). Optional ?date=YYYY-MM-DD param for back-filling. Defaults to yesterday.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: admin navigates ops dashboard across tabs
**Source:** admin_ops.html Obsidian migration (Sprint 76-4)
**User:** admin
**Starting state:** Admin is logged in, visits /admin/ops
**Goal:** Check pipeline health, then look at feedback, then check user activity — all in one session
**Expected outcome:** Tab navigation loads each panel without a full page reload; hash in URL updates to reflect current tab; back/forward navigation restores correct tab
**Edge cases seen in code:** Hash aliases (luck, dq, watch, intelligence) allow bookmarking with friendly names; 30s HTMX timeout shows error if server is slow
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: signals cron endpoint logs to cron_log
**Source:** web/routes_cron.py — cron_signals() (QS8-T1-B)
**User:** admin
**Starting state:** CRON_SECRET configured; signals pipeline operational
**Goal:** Scheduler calls POST /cron/signals to run signal detection
**Expected outcome:** Job start logged as 'running', completion logged as 'success' or 'failed' with elapsed time; response includes ok, status, elapsed_seconds; failure does not crash the endpoint (returns ok=False)
**Edge cases seen in code:** cron_log insert failure is non-fatal (logged as warning); pipeline exception returns HTTP 500 with ok=False
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: velocity-refresh cron endpoint logs to cron_log
**Source:** web/routes_cron.py — cron_velocity_refresh() (QS8-T1-B)
**User:** admin
**Starting state:** CRON_SECRET configured; addenda table populated with routing data
**Goal:** Scheduler calls POST /cron/velocity-refresh to refresh station velocity baselines
**Expected outcome:** Velocity refresh runs, transitions and congestion sub-steps also attempted (non-fatal); all logged to cron_log; response includes rows_inserted, stations, transitions; partial failures (transitions/congestion) don't fail overall job
**Edge cases seen in code:** transitions failure logged as transitions_error key in response; congestion failure same pattern
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: pipeline stats unavailable at first deploy
**Source:** web/brief.py — _get_pipeline_stats() (QS8-T1-B)
**User:** admin
**Starting state:** Fresh deploy, cron_log table empty or not yet populated
**Goal:** Admin opens morning brief before any cron jobs have run
**Expected outcome:** Brief still renders; pipeline_stats is empty dict ({}); no error shown to user
**Edge cases seen in code:** Exception caught silently, returns {}
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Admin reviews stale task inventory
**Source:** QS5-D task hygiene diagnostic sweep (rewritten by QS7-4D)
**User:** admin
**Starting state:** Many open tasks have accumulated over multiple sprints, some referencing features that were already delivered.
**Goal:** Review open tasks, close those that are done, and create focused follow-ups for items that remain outstanding.
**Expected outcome:** Admin can distinguish between: tasks completed (close with evidence), tasks superseded by later work (close with note), and tasks still needed (update description to current understanding). After the review, the open task count is meaningfully reduced and remaining tasks have accurate descriptions.
**Edge cases seen in code:** Task descriptions may refer to sprint numbers or feature names that predate current architecture
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Admin ops hub gated by role
**Source:** tests/e2e/test_admin_scenarios.py — TestAdminOpsPage (Sprint 77-2)
**User:** admin
**Starting state:** Authenticated admin user, all other non-admin users also logged in
**Goal:** Only admin users can reach the admin ops hub; non-admins and anonymous visitors are blocked
**Expected outcome:** Admin user: page loads, shows ops hub content (pipeline, quality, activity, feedback sections). Non-admin authenticated user: blocked with 403 or redirected away from the ops hub. Anonymous visitor: redirected to login page before seeing any admin content.
**Edge cases seen in code:** abort(403) used directly — no intermediate redirect for non-admins
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Morning brief lookback parameter accepts any valid range
**Source:** web/routes_misc.py — /brief route; web/templates/brief.html lookback toggle (Sprint 77-1)
**User:** expediter
**Starting state:** Authenticated expediter on the morning brief page
**Goal:** Switch lookback window using URL parameter
**Expected outcome:** All valid values (1, 7, 30, 90) return HTTP 200. Values outside 1-90 are clamped. Non-integer values default to 1. Active lookback button reflects current selection.
**Edge cases seen in code:** max(1, min(int(lookback), 90)) — ValueError on non-numeric input defaults to 1
**CC confidence:** high
**Status:** PENDING REVIEW

---

## PERFORMANCE & INFRASTRUCTURE

## SUGGESTED SCENARIO: Production handles concurrent users without pool exhaustion
**Source:** QS4-B Task B-1 (pool monitoring + env override)
**User:** admin
**Starting state:** 50+ concurrent users hitting sfpermits.ai during peak hours
**Goal:** Verify that the connection pool handles concurrent load without exhaustion or errors
**Expected outcome:** All requests complete successfully; /health pool stats show used_count stays below maxconn; no connection timeout errors in logs
**Edge cases seen in code:** Pool at Railway limit (5 workers x 20 = 100 connections = Postgres max); DB_POOL_MAX env var override for capacity tuning
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Railway zero-downtime deploy uses readiness probe
**Source:** QS4-B Task B-2 (/health/ready endpoint)
**User:** admin
**Starting state:** New container starting during Railway deployment
**Goal:** Verify that /health/ready returns 503 until DB pool, tables, and migrations are all verified, then returns 200
**Expected outcome:** Railway routes traffic to new container only after /health/ready returns 200; old container continues serving until new one is ready
**Edge cases seen in code:** Missing tables return 503 with list of what's missing; 5-second statement_timeout prevents readiness probe from hanging
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Connection pool stats visible in health monitoring
**Source:** QS4-B Task B-3 (pool stats in /health)
**User:** admin
**Starting state:** Production system running with active connections
**Goal:** View connection pool utilization via /health endpoint for capacity planning
**Expected outcome:** /health response includes pool.maxconn, pool.used_count, pool.pool_size; values update in real-time as connections are checked out/returned
**Edge cases seen in code:** DuckDB backend returns status "no_pool" since it has no connection pool; pool internals accessed via _pool/_used attributes which may change between psycopg2 versions
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Pool exhaustion surfaces diagnostic warning
**Source:** src/db.py get_connection() PoolError handler (Sprint 74-4)
**User:** admin
**Starting state:** Production app under high traffic; all DB_POOL_MAX connections are checked out
**Goal:** Diagnose why requests are failing with database errors
**Expected outcome:** Application log contains a WARNING entry with "Pool exhausted" and current pool stats (minconn, maxconn, in_use, available), allowing the operator to identify pool saturation without connecting to the database
**Edge cases seen in code:** PoolError is specifically caught before generic Exception, so pool exhaustion always logs at WARNING (not ERROR), distinct from other connection failures
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Pool health visible in health endpoint response
**Source:** src/db.py get_pool_stats() + get_pool_health() (Sprint 74-4)
**User:** admin
**Starting state:** App is running with an active PostgreSQL connection pool
**Goal:** Check current pool health from the /health endpoint to verify connections are available
**Expected outcome:** The health endpoint JSON response includes a pool stats section with a nested "health" object containing: healthy (bool), min, max, in_use, and available counts
**Edge cases seen in code:** When pool is None or pool.closed=True, healthy=False with all counts at 0
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Custom pool parameters take effect via env vars
**Source:** src/db.py _get_pool() DB_POOL_MIN, DB_CONNECT_TIMEOUT (Sprint 74-4)
**User:** admin
**Starting state:** Production deployment with custom pool sizing requirements
**Goal:** Configure minimum idle connections and connection timeout without code changes
**Expected outcome:** The connection pool is created with the env-configured minconn and connect_timeout values, visible in the startup log line
**Edge cases seen in code:** Default values (minconn=2, connect_timeout=10) apply when env vars are absent
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Statement timeout configurable per deployment context
**Source:** src/db.py get_connection() DB_STATEMENT_TIMEOUT (Sprint 74-4)
**User:** admin
**Starting state:** App deployed with DB_STATEMENT_TIMEOUT=60s for analytics workloads
**Goal:** Allow longer-running queries without hitting the default 30s kill threshold
**Expected outcome:** New database connections have statement_timeout SET to the configured value; cron workers bypass timeout entirely
**Edge cases seen in code:** CRON_WORKER=true bypasses the entire timeout setup regardless of DB_STATEMENT_TIMEOUT
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Circuit breaker skips slow enrichment queries after repeated timeouts
**Source:** QS3-B — CircuitBreaker in src/db.py + permit_lookup integration (rewritten by QS7-4D)
**User:** expediter | architect
**Starting state:** Three consecutive permit lookups have timed out on the same type of enrichment query (e.g., inspections) due to database load
**Goal:** Subsequent permit lookups remain fast and responsive despite the degraded database condition
**Expected outcome:** After a threshold of failures within a short window, that enrichment category is skipped automatically. Subsequent lookups show a "temporarily unavailable" note for that section instead of waiting for a timeout. After a cooldown period, the next lookup retries the enrichment. A successful enrichment resets the failure tracking.
**Edge cases seen in code:** Different enrichment categories (contacts, addenda, related_team, planning_records, boiler_permits) have independent circuit breakers
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: SODA API circuit breaker opens after repeated failures
**Source:** src/soda_client.py — CircuitBreaker integration with SODAClient.query() (QS8-T1-C)
**User:** homeowner | expediter
**Starting state:** SODA API is returning 503 errors or timing out on every request
**Goal:** User searches for permit data; app should not hang or surface raw errors
**Expected outcome:** After the failure threshold is reached, all SODA queries return empty results immediately without making network calls. The UI degrades gracefully (shows no results) rather than returning error pages or stalling.
**Edge cases seen in code:** 4xx errors (e.g., bad dataset ID) do NOT trip the circuit — only 5xx and network errors count as failures
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: SODA circuit breaker auto-recovers after cooldown
**Source:** src/soda_client.py — CircuitBreaker.is_open() half-open transition (QS8-T1-C)
**User:** expediter
**Starting state:** Circuit breaker was opened due to SODA API failures; recovery_timeout seconds have passed
**Goal:** Resume normal permit data queries without manual restart
**Expected outcome:** The next query after the cooldown window acts as a probe. If it succeeds, the circuit closes and normal queries resume. If it fails, the circuit reopens and the cooldown restarts.
**Edge cases seen in code:** Half-open state allows exactly one probe — not multiple concurrent probes
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: 4xx SODA errors do not trigger circuit breaker
**Source:** src/soda_client.py — HTTPStatusError handling in query() (QS8-T1-C)
**User:** expediter
**Starting state:** A tool passes an invalid dataset ID or malformed SoQL query to the SODA client
**Goal:** Bad queries surface as errors without poisoning the circuit breaker for healthy queries
**Expected outcome:** HTTPStatusError is raised to the caller as before; failure_count stays at 0; subsequent queries to valid endpoints succeed normally
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Load test shows staging can handle launch traffic
**Source:** scripts/load_test.py (Sprint 74-2)
**User:** admin
**Starting state:** Staging app is running; load_test.py available in scripts/
**Goal:** Verify the app sustains 10 concurrent users for 30 seconds without errors on the landing, search, and health pages
**Expected outcome:** All scenarios return p95 latency < 2000ms and error rate < 5%
**Edge cases seen in code:** Script exits with code 1 if any scenario error_rate > 5%; results saved to load-test-results.json
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Load test CLI filters to a single scenario
**Source:** scripts/load_test.py (Sprint 74-2)
**User:** admin
**Starting state:** App is deployed; user wants to isolate health check performance
**Goal:** Run load test on health endpoint only with custom concurrency
**Expected outcome:** Only /health requests are made; JSON output contains only the "health" scenario key; summary table shows one row
**Edge cases seen in code:** --scenario argument is validated against the SCENARIOS registry; invalid names rejected by argparse
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Load test captures timeout errors correctly
**Source:** scripts/load_test.py (Sprint 74-2)
**User:** admin
**Starting state:** A scenario endpoint is timing out (e.g., DB overload)
**Goal:** Load test should record timeout errors rather than crashing
**Expected outcome:** error_count increments for the affected scenario; elapsed_ms still recorded; error field explains the cause
**Edge cases seen in code:** httpx.TimeoutException is caught; result.success=False; exit code 1 if error_rate > 5%
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Response time visible in response headers
**Source:** QS8-T1-D / web/app.py _add_response_time_header
**User:** admin
**Starting state:** App is running, any page is requested
**Goal:** Measure and observe server-side response time without needing server logs
**Expected outcome:** Every HTTP response (2xx, 4xx, 5xx) includes X-Response-Time header with value in milliseconds (e.g., "47.2ms"); value increases proportionally with DB-heavy pages vs. static pages
**Edge cases seen in code:** Header uses time.time() wall clock, not monotonic; value is always >= 0; present on 404 and health check responses
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Static content pages cached at CDN/browser level
**Source:** QS8-T1-D / web/app.py add_cache_headers
**User:** homeowner
**Starting state:** User visits /methodology, /about-data, or /demo for the first time
**Goal:** Content loads quickly on repeat visits without hitting the origin server
**Expected outcome:** Response includes Cache-Control: public, max-age=3600, stale-while-revalidate=86400; browser/CDN serves from cache for up to 1 hour; stale content served up to 24 hours while revalidating
**Edge cases seen in code:** Cache header only set on 200 responses (not errors); auth pages, API endpoints, and search routes do NOT receive this header
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: health endpoint responds under 500ms for Railway probe
**Source:** tests/e2e/test_performance_scenarios.py — TestHealthEndpoint (QS8-T3-D)
**User:** admin
**Starting state:** Railway health probe hits /health every ~30s. Response time determines instance health status.
**Goal:** System needs to respond reliably within Railway's health-check window.
**Expected outcome:** /health returns 200 with valid JSON containing a status field in under 500ms. If health check takes >500ms consistently, Railway marks instance unhealthy and restarts it.
**Edge cases seen in code:** Pool exhaustion (PoolError) causes health to fail. statement_timeout is set per connection.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: search results within 2s latency budget
**Source:** tests/e2e/test_performance_scenarios.py — TestSearchPerformance (QS8-T3-D)
**User:** expediter
**Starting state:** User types a street name into the search box on the landing page.
**Goal:** User expects results to appear quickly — ideally under 1s, definitely under 2s.
**Expected outcome:** Search returns 200 or redirect within 2s. Sprint 69 Hotfix added graceful degradation on query timeouts — 30s statement_timeout prevents hangs.
**Edge cases seen in code:** If DuckDB is not populated (CI/fresh checkout), search returns empty quickly. Postgres with missing pgvector index causes slow semantic search.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: rapid page navigation does not produce 500 errors
**Source:** tests/e2e/test_performance_scenarios.py — TestRapidNavigationResilience (QS8-T3-D)
**User:** expediter
**Starting state:** User clicks quickly between multiple pages (landing, methodology, about-data, demo, beta-request).
**Goal:** System handles burst navigation without connection pool exhaustion or session corruption.
**Expected outcome:** None of the 5 pages return 500. All pages return 200 or redirect. Flask sessions and g.user remain consistent across rapid sequential requests.
**Edge cases seen in code:** DB_POOL_MAX defaults to 20. DuckDB only allows one write connection at a time.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Pre-computed brief loads sub-second
**Source:** Instant Site Architecture spec (Chief Task #349)
**User:** expediter
**Starting state:** User is logged in with 40+ watched properties, first load of the day
**Goal:** View morning brief quickly on mobile at job site
**Expected outcome:** Brief page loads in under 200ms from page_cache. Shows "Updated X min ago" badge. Manual refresh button available (rate-limited to 1 per 5 min). All property cards, status dots, and sections render from pre-computed JSON.
**Edge cases seen in code:** Cache miss on first-ever visit should compute and cache, not error. User with 0 watches gets clean empty state.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## ONBOARDING & AUTH

## SUGGESTED SCENARIO: App can be installed to a phone home screen
**Source:** web/static/manifest.json (Sprint 69 S4) (rewritten by QS7-4D)
**User:** homeowner
**Starting state:** User visits sfpermits.ai on a mobile device (iOS or Android) using a supported browser.
**Goal:** Save sfpermits.ai to their home screen for quick daily access.
**Expected outcome:** The browser signals that the app is installable (install prompt or browser menu option available). Once installed, the app opens in a standalone window without browser chrome. The app name, icon, and color theme are consistent with the brand.
**Edge cases seen in code:** Icons currently placeholder — branded icons needed; iOS requires additional <meta> tags separate from manifest
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: User creates a Permit Prep checklist for an existing permit and sees categorized document requirements
**Source:** web/permit_prep.py, web/routes_property.py (rewritten by QS7-4D)
**User:** expediter | architect
**Starting state:** User is logged in. A permit exists in the database.
**Goal:** Generate a document tracking checklist for a permit submission.
**Expected outcome:** User can initiate a checklist for a known permit. The checklist shows document requirements grouped by category (e.g., Required Plans, Application Forms, Supplemental Documents, Agency-Specific). All items start in a "Required" state. A progress indicator shows 0% addressed.
**Edge cases seen in code:** Permit not found in DB (falls back to general project type); tool failure (falls back to minimal item set); creating a checklist for a permit that already has one returns the existing checklist
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: User marks a document as submitted and the checklist progress updates
**Source:** web/routes_api.py — prep item status toggle (rewritten by QS7-4D)
**User:** expediter | architect
**Starting state:** User has an active Permit Prep checklist with items in "Required" status.
**Goal:** Record that a document has been submitted to the city.
**Expected outcome:** User changes an item's status (e.g., to "Submitted"). The item card updates to reflect the new status. The overall checklist progress indicator updates to show the new completion percentage. The change is persisted so it survives a page reload.
**Edge cases seen in code:** Invalid status value rejected; wrong user ownership rejected; concurrent updates on same item
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Preview Mode shows predicted document requirements without saving a checklist
**Source:** web/permit_prep.py preview_checklist() (rewritten by QS7-4D)
**User:** homeowner | architect
**Starting state:** User is logged in but has not yet created a checklist for this permit.
**Goal:** See what documents would be required before committing to creating a tracked checklist.
**Expected outcome:** A preview shows the predicted document requirements grouped by category, with the review path and agencies involved. No checklist is created in the database as a result of viewing the preview. The user can then choose to create a real checklist from the preview.
**Edge cases seen in code:** Permit not in database (uses fallback description); prediction tool timeout; preview data not persisted
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Morning brief flags permits with incomplete prep checklists
**Source:** web/brief.py _get_prep_summary() (rewritten by QS7-4D)
**User:** expediter
**Starting state:** User has one or more Permit Prep checklists with items still in "Required" status.
**Goal:** See at a glance which permits need document attention during the daily review.
**Expected outcome:** Morning brief includes a permit prep section listing each permit with an active checklist, showing how many items are outstanding. Permits with missing required documents are surfaced as needing attention.
**Edge cases seen in code:** prep_checklists table doesn't exist yet (returns empty list gracefully); user has no checklists (section is absent, not an error)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Unauthenticated user who tries to access a Permit Prep checklist is guided to log in
**Source:** web/routes_property.py /prep/<permit> (rewritten by QS7-4D)
**User:** homeowner
**Starting state:** User is viewing public search results and is not logged in.
**Goal:** Access a Permit Prep checklist for a specific permit to start tracking required documents.
**Expected outcome:** When the user attempts to open a checklist, they are redirected to the login page. The login page is clearly presented and functional. After logging in, the user can navigate to their checklist.
**Edge cases seen in code:** Currently no automatic post-login redirect back to the checklist — user must navigate manually after login; this is a known gap
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: beta approval sends welcome email with magic link
**Source:** web/auth.py — send_beta_welcome_email(), web/routes_admin.py — admin_approve_beta() (Sprint 75-2)
**User:** admin
**Starting state:** Admin is logged in; a beta request exists in "pending" status; SMTP is configured
**Goal:** Approve a beta request and notify the new user
**Expected outcome:** New user receives a branded HTML email with a one-click sign-in button; email contains a valid magic link URL; admin sees "Approved and sent welcome email" confirmation; if SMTP fails, fallback plain magic link email is sent instead
**Edge cases seen in code:** SMTP failure triggers fallback to send_magic_link(); dev mode (no SMTP_HOST) logs to console and returns True; already-approved requests return "not found" redirect
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: new beta user completes 3-step onboarding
**Source:** web/routes_misc.py — /welcome route, web/templates/welcome.html (Sprint 75-2)
**User:** homeowner
**Starting state:** User has just received beta approval email and clicked the magic sign-in link; onboarding_complete is FALSE in DB
**Goal:** Get oriented to the app (search, report, watchlist) and start using it
**Expected outcome:** /welcome shows 3-step page with search, property report, and watchlist cards; user can navigate to any step via CTA buttons; clicking "Start searching now" or the skip link dismisses onboarding; subsequent visits redirect to dashboard
**Edge cases seen in code:** Unauthenticated access redirects to login; if onboarding_complete already TRUE, immediate redirect to /; dismiss is fire-and-forget (non-blocking JS fetch)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: homeowner completes 3-step onboarding wizard
**Source:** web/routes_auth.py, web/templates/onboarding_step1.html (QS8-T3-A)
**User:** homeowner
**Starting state:** New user just verified their magic link for the first time; no role set, no watches, onboarding_complete=False
**Goal:** Complete the onboarding flow to get oriented with the product
**Expected outcome:** Role saved to profile, demo property added to portfolio, onboarding_complete=True, user lands on dashboard
**Edge cases seen in code:** User can skip step 2 (no watch created); all roles validated server-side; re-running onboarding via ?redo=1 is supported
**CC confidence:** high
**Status:** PENDING REVIEW
**DUPLICATE OF:** "new beta user completes 3-step onboarding" above — same core flow from different agent perspectives.

---

## SUGGESTED SCENARIO: beta user automatically gets PREMIUM tier access
**Source:** web/feature_gate.py (get_user_tier, _is_beta_premium) (QS8-T3-A)
**User:** expediter (beta invite code holder)
**Starting state:** User created account with invite code starting with "sfp-beta-" or "sfp-amy-" or "sfp-team-"
**Goal:** Access premium-gated features (plan_analysis_full, entity_deep_dive, etc.)
**Expected outcome:** gate_context() returns is_premium=True; can_plan_analysis_full=True; no paywall shown; seamless experience identical to paid users
**Edge cases seen in code:** is_admin check comes before PREMIUM check — admin tier always wins; subscription_tier='premium' in DB also grants PREMIUM regardless of invite code
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Charis signs up with invite code and reaches the dashboard
**Source:** QS4-D Task D-3 — Beta launch polish
**User:** architect
**Starting state:** User visits login with invite code
**Goal:** New beta user signs up and reaches the authenticated dashboard
**Expected outcome:** User enters email and invite code, receives magic link, clicks link, lands on authenticated index page with search and brief access
**Edge cases seen in code:** Three-tier signup: shared_link bypasses invite, valid code grants access, no code redirects to beta request form
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Anonymous users cannot access brief or portfolio
**Source:** web/helpers.py — login_required; SCENARIO-40 (Sprint 77-1)
**User:** homeowner (anonymous / not logged in)
**Starting state:** User is not authenticated; navigates directly to /brief or /portfolio
**Goal:** Access permit data without logging in
**Expected outcome:** Both /brief and /portfolio redirect to the login page. No partial page content shown. Post-login redirect preserves intended destination.
**Edge cases seen in code:** /portfolio and /brief listed in login_required route list in app.py
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: portfolio empty state guidance for new user
**Source:** tests/e2e/test_onboarding_scenarios.py — TestPortfolioEmptyState (QS8-T3-D)
**User:** homeowner
**Starting state:** Newly onboarded user has not yet added any watch items.
**Goal:** User navigates to /portfolio expecting to see their watched properties.
**Expected outcome:** Page renders without crash. Shows an empty state with guidance on how to add a watch item — not a blank page or uncaught exception. Anonymous users are redirected to login.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SECURITY

## SUGGESTED SCENARIO: CSP violations from inline styles are captured in report-only mode without breaking pages
**Source:** QS4-D Task D-1 — CSP-Report-Only with nonces
**User:** admin
**Starting state:** Pages load correctly with enforced CSP using unsafe-inline
**Goal:** Monitor which templates generate CSP violations when nonce-based policy is applied, without breaking any pages
**Expected outcome:** Browser sends violation reports to /api/csp-report when inline styles/scripts lack nonces; pages render normally because Report-Only doesn't enforce
**Edge cases seen in code:** Templates from external CDNs (unpkg, jsdelivr, Google Fonts) need explicit allow-listing in CSP-RO
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: POST form submission without CSRF token is rejected with 403
**Source:** QS4-D Task D-2 — CSRF protection middleware
**User:** homeowner | expediter
**Starting state:** User is on any page with a POST form
**Goal:** Prevent cross-site request forgery attacks on state-changing endpoints
**Expected outcome:** POST requests without a valid csrf_token form field or X-CSRFToken header receive 403 Forbidden; GET requests are unaffected; cron endpoints with Bearer auth skip CSRF
**Edge cases seen in code:** HTMX requests use X-CSRFToken header via hx-headers attribute on body; feedback widget, watch forms, and account settings all need tokens
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: SQL injection payload handled gracefully in search
**Source:** tests/e2e/test_admin_scenarios.py — TestSQLInjectionSearch (Sprint 77-2)
**User:** homeowner
**Starting state:** Anonymous or authenticated user, normal browser session
**Goal:** Malicious SQL injection payloads in the search query do not crash the server or expose data
**Expected outcome:** Server returns 200 or 400, never 500. No Python traceback appears in the response body. No raw database error message visible to the user. Result is empty search results or a graceful message.
**Edge cases seen in code:** Combined XSS + SQL payload also sanitized — script tag does not appear in rendered HTML
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Directory traversal attempt returns safe response
**Source:** tests/e2e/test_admin_scenarios.py — TestDirectoryTraversal (Sprint 77-2)
**User:** homeowner
**Starting state:** Anonymous user, crafts a URL with ../ sequences
**Goal:** Attacker tries to read system files by traversing path segments
**Expected outcome:** Response does not contain /etc/passwd file contents. Response status is 404 or a redirect, never 500. Flask/Werkzeug's path normalization neutralizes the traversal before routing.
**Edge cases seen in code:** /report/../../../etc/passwd, /static/../../../etc/passwd, /../etc/passwd all tested
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Content-Security-Policy header on every page response
**Source:** tests/e2e/test_admin_scenarios.py — TestCSPHeaders, web/security.py (Sprint 77-2)
**User:** homeowner
**Starting state:** Any page request (landing, search, login, health, methodology)
**Goal:** Every HTTP response includes a Content-Security-Policy header
**Expected outcome:** Content-Security-Policy header present on all page responses. Header includes default-src directive as baseline restriction. frame-ancestors none in CSP or X-Frame-Options DENY present (prevents clickjacking). X-Content-Type-Options nosniff present, Referrer-Policy header set.
**Edge cases seen in code:** CSP-Report-Only nonce-based policy also sent when per-request nonce generated
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Anonymous user rate-limited on rapid search requests
**Source:** tests/e2e/test_admin_scenarios.py — TestAnonymousRateLimiting (Sprint 77-2)
**User:** homeowner
**Starting state:** Anonymous visitor (no session), makes many rapid GET requests to search
**Goal:** Rate limiting fires to prevent scraping or abuse after sustained rapid requests
**Expected outcome:** After 15+ requests within 60 seconds from the same IP, server returns 429 or rate-limit message. The rate-limit response is friendly (not a raw server error, no traceback). Body text mentions waiting or rate-limiting.
**Edge cases seen in code:** Rate bucket is per-IP (X-Forwarded-For header); resets after 60 seconds; TESTING mode may reset buckets
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: security audit runs without crashing when tools are missing
**Source:** scripts/security_audit.py — run_bandit / run_pip_audit graceful degradation (Sprint 74-3)
**User:** admin
**Starting state:** CI environment where bandit and/or pip-audit are not installed
**Goal:** Run the security audit script and get a usable report even when tools are absent
**Expected outcome:** Script completes (exit 0), report clearly marks missing tools as SKIPPED, no stack trace or unhandled exception
**Edge cases seen in code:** tool not on PATH returns rc=-1 from run_command; check_tool_available guards both scanners independently
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: security audit exits 1 on HIGH severity bandit finding
**Source:** scripts/security_audit.py — main() exit code logic (Sprint 74-3)
**User:** admin
**Starting state:** Codebase has a bandit HIGH severity issue (e.g., subprocess shell=True)
**Goal:** CI job fails and draws attention to the finding
**Expected outcome:** Script exits with code 1; report contains "FAIL" status; HIGH issue details present with filename, line number, test ID
**Edge cases seen in code:** bandit exits 1 even when only LOW issues found — exit code alone cannot distinguish severity; script re-parses JSON counts
**CC confidence:** high
**Status:** PENDING REVIEW

---

## DESIGN SYSTEM & UI

## SUGGESTED SCENARIO: Consistent Obsidian design from landing through dashboard
**Source:** QS4-C Obsidian design migration (index.html + brief.html)
**User:** expediter | homeowner | architect
**Starting state:** User is on the landing page (not logged in)
**Goal:** Experience a visually consistent design when transitioning from landing page through login to the authenticated dashboard
**Expected outcome:** Landing page, index/search page, and morning brief all share the same color palette (deep navy backgrounds, cyan accents, IBM Plex Sans body text, JetBrains Mono headings), with no jarring visual shifts between pages
**Edge cases seen in code:** Nav fragment uses legacy alias vars that must resolve to Obsidian tokens; body.obsidian class must be present for design-system.css to activate
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Morning brief health indicators use signal colors
**Source:** QS4-C Obsidian design migration (brief.html signal colors)
**User:** expediter
**Starting state:** User has watched properties with varying health statuses (on_track, slower, behind, at_risk)
**Goal:** Quickly scan the morning brief and identify which properties need attention based on color coding
**Expected outcome:** Health indicators use distinct colors to distinguish on_track, slower/behind, and at_risk statuses, matching the Obsidian design system's signal color palette
**Edge cases seen in code:** Health status classes use CSS custom properties which now alias to signal colors via head_obsidian.html
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Design token ghost CTA meets WCAG AA
**Source:** DESIGN_TOKENS.md ghost CTA accessibility fix
**User:** architect | homeowner
**Starting state:** User is on any page with ghost CTA links (property report, search results)
**Goal:** Click a ghost CTA to navigate
**Expected outcome:** Ghost CTA text is visible and legible at rest state (--text-secondary, 5.2:1 contrast), turns teal on hover. Passes WCAG AA for interactive text.
**Edge cases seen in code:** Old templates may still use --text-tertiary for CTAs — migration needed
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Tabs switch content without full page reload
**Source:** DESIGN_TOKENS.md tabs component
**User:** expediter | admin
**Starting state:** User is on a page with tabbed views (e.g., inspection history with Recent/Failed/All tabs)
**Goal:** Switch between tab views
**Expected outcome:** Active tab shows --text-primary with teal underline. Inactive tabs show --text-tertiary. Content panel swaps without full page reload. On phone, tabs scroll horizontally if they overflow.
**Edge cases seen in code:** Tab count badges should update when content changes
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Load more pagination appends results
**Source:** DESIGN_TOKENS.md pagination / load more component
**User:** expediter | homeowner
**Starting state:** User is viewing a list with more than 20 results
**Goal:** See additional results
**Expected outcome:** "Showing 20 of 142" count displayed. "Show more →" ghost CTA loads next batch via HTMX append. Count updates. When no more results, button disappears. Skeleton placeholder shown during loading.
**Edge cases seen in code:** If only 20 or fewer results, no pagination UI shown at all
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Toast notification with undo on watch action
**Source:** DESIGN_TOKENS.md toast component
**User:** expediter | homeowner
**Starting state:** User is on a property page or search results
**Goal:** Add a property to watchlist and see confirmation
**Expected outcome:** "Watch added" toast appears top-center. Includes "Undo" link. Auto-dismisses after 5 seconds. Pauses on hover. Undo link reverses the action and dismisses toast immediately.
**Edge cases seen in code:** Multiple rapid actions should stack toasts vertically, not replace
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Authenticated dashboard displays search, quick actions, and recent items
**Source:** web/templates/index.html Sprint 75-1 redesign
**User:** expediter | homeowner | architect
**Starting state:** User is logged in and visits the dashboard
**Goal:** Quickly orient to available tools and start a search or action
**Expected outcome:** Dashboard shows a search card at top, quick action buttons (Analyze a project, Look up a permit, Upload plans, Draft a reply), a recent searches card, a watchlist card, and a stats row. Search input uses Obsidian styling. No horizontal overflow at any viewport width.
**Edge cases seen in code:** If user has no recent searches, recent card shows placeholder text. If user has a primary address set, a personalized "Check [address]" quick action appears.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Navigation collapses to hamburger menu on mobile viewport
**Source:** web/templates/fragments/nav.html Sprint 75-1 redesign
**User:** expediter | homeowner | architect
**Starting state:** User visits any authenticated page on a mobile device (viewport ≤768px)
**Goal:** Access navigation links without the nav overflowing or wrapping
**Expected outcome:** Desktop badge row is hidden. A hamburger icon (3 horizontal lines) appears. Tapping it reveals a slide-down panel with all nav items stacked vertically. Tapping outside the panel or tapping the hamburger again closes the panel.
**Edge cases seen in code:** Panel closes on tap-outside via document click handler. Hamburger transforms to X when open. Sign-up chips appear for locked features.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Mobile viewport has no horizontal overflow on key pages
**Source:** tests/e2e/test_auth_mobile_scenarios.py — TestMobileNoHorizontalScroll (Sprint 77-4)
**User:** homeowner
**Starting state:** User opens the app on a 375px-wide mobile device (iPhone SE / standard mobile)
**Goal:** Browse the landing page, demo, login, and beta-request page without side-scrolling
**Expected outcome:** document.body.scrollWidth <= window.innerWidth on all checked pages. No content is clipped or requires horizontal scrolling.
**Edge cases seen in code:** /demo and /beta-request pages are content-heavy and most likely to overflow if images or wide tables are not constrained.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## MCP TOOLS (PERMIT INTELLIGENCE)

## SUGGESTED SCENARIO: expediter checks next station for active permit
**Source:** src/tools/predict_next_stations.py — predict_next_stations tool (QS8-T2-A)
**User:** expediter
**Starting state:** Permit is active, has been routed through at least one station (BLDG completed), currently sitting at SFFD with an arrive date 10 days ago
**Goal:** Understand which stations the permit will visit next and how long each typically takes
**Expected outcome:** Tool returns current station (SFFD with dwell time), top 3 predicted next stations with transition probabilities and p50 durations, and a total estimated remaining time
**Edge cases seen in code:** If fewer than 5 similar permits have transitioned from the current station, no predictions are shown — tool explains why
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: homeowner asks about stalled permit (station predictor)
**Source:** src/tools/predict_next_stations.py — STALL_THRESHOLD_DAYS (QS8-T2-A)
**User:** homeowner
**Starting state:** Permit has been at CP-ZOC (Planning/Zoning) for 75 days with no finish_date recorded
**Goal:** Find out if their permit is stuck and what to do about it
**Expected outcome:** Tool surfaces "STALLED" indicator on the current station card, shows how many days the permit has been at that station, and recommends following up with DBI. Predictions for next stations are still shown based on historical transitions.
**Edge cases seen in code:** Stall threshold is configurable (STALL_THRESHOLD_DAYS = 60). Permits just over the threshold get the warning; those below do not.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: permit already complete — no action needed
**Source:** src/tools/predict_next_stations.py — COMPLETE_STATUSES short-circuit (QS8-T2-A)
**User:** homeowner | expediter
**Starting state:** Permit status is "complete" or "issued"
**Goal:** Check what happens next (doesn't know it's already done)
**Expected outcome:** Tool returns a clear message that the permit has completed all review stations, shows the issued/completed date if available. Does NOT attempt to build transition predictions.
**Edge cases seen in code:** Status values checked: "complete", "issued", "approved", "cancelled", "withdrawn" — all treated as terminal
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: permit not yet in plan review — no routing data
**Source:** src/tools/predict_next_stations.py — empty addenda short-circuit (QS8-T2-A)
**User:** homeowner
**Starting state:** Permit was recently filed (< 2 weeks ago) and has no addenda records yet
**Goal:** Ask what stations the permit will go through
**Expected outcome:** Tool returns "No routing data available" with an explanation that the permit may not have entered plan review yet. Does not error out or return an empty page.
**Edge cases seen in code:** Distinction between permit-not-found (permit table miss) and no-addenda (permit exists but addenda table has no rows for it)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: neighborhood-stratified prediction vs. city-wide fallback
**Source:** src/tools/predict_next_stations.py — _build_transition_matrix neighborhood fallback (QS8-T2-A)
**User:** expediter
**Starting state:** Permit is in a neighborhood with sufficient historical data (e.g., Mission — many similar permits). Separately, a permit in a rare neighborhood with very few historical records.
**Goal:** Get predictions that are relevant to the permit's actual location context
**Expected outcome:** For Mission: predictions are labeled as "based on historical routing patterns from permits in Mission" (neighborhood-filtered). For rare neighborhood: falls back to all similar permit types city-wide, labeled accordingly. Both cases return predictions if transition data exists.
**Edge cases seen in code:** Neighborhood fallback triggered when _build_transition_matrix returns empty dict for neighborhood query
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: expediter diagnoses critically stalled permit at plan check
**Source:** src/tools/stuck_permit.py — diagnose_stuck_permit (QS8-T2-B)
**User:** expediter
**Starting state:** Permit has been at BLDG plan check station for 95 days. Historical p90 for BLDG is 60 days. No comments have been issued.
**Goal:** Understand why the permit is stalled and what to do next
**Expected outcome:** Tool returns a playbook identifying BLDG as critically stalled (past p90), recommending expediter contact DBI plan check counter with specific address and phone number, severity score reflects age/staleness
**Edge cases seen in code:** Heuristic fallback when no velocity baseline exists for a station (>90d = critically stalled, >45d = stalled); stations missing from station_velocity_v2 still get flagged
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: homeowner learns to respond to plan check comments
**Source:** src/tools/stuck_permit.py — _diagnose_station, review_results detection (QS8-T2-B)
**User:** homeowner
**Starting state:** Permit routing shows "Comments Issued" review result at BLDG station. 1 revision cycle completed.
**Goal:** Understand what the comments mean and what action to take
**Expected outcome:** Playbook identifies comment-issued status as highest priority intervention, recommends revising plans and resubmitting via EPR (Electronic Plan Review), includes EPR URL
**Edge cases seen in code:** Revision cycle count (addenda_number >= 2) triggers additional warning about multiple rounds; 3+ cycles triggers expediter/architect recommendation
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: architect checks inter-agency hold at SFFD
**Source:** src/tools/stuck_permit.py — INTER_AGENCY_STATIONS, _get_agency_key (QS8-T2-B)
**User:** architect
**Starting state:** Permit routed to SFFD station 50 days ago. p75 baseline for SFFD is 30 days.
**Goal:** Know who to contact and what to say
**Expected outcome:** Playbook identifies SFFD as stalled inter-agency station, provides SFFD Permit Division contact info (phone, address, URL), recommends contacting SFFD directly rather than DBI
**Edge cases seen in code:** Multiple inter-agency stations (e.g. SFFD + HEALTH simultaneously) each get separate diagnosis entries ranked by severity; CP-ZOC (Planning) maps to Planning Department not DBI
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: expediter checks a healthy permit that is on track
**Source:** src/tools/stuck_permit.py — _diagnose_station normal status, _format_playbook (QS8-T2-B)
**User:** expediter
**Starting state:** Permit has been at BLDG for 10 days. Historical p50 for BLDG is 15 days.
**Goal:** Confirm permit routing is proceeding normally
**Expected outcome:** Playbook shows "OK" routing status, no CRITICAL or STALLED labels, no urgent intervention steps, dwell shown relative to p50 baseline for reassurance
**Edge cases seen in code:** Permit with no addenda data yet (not entered plan check queue) returns empty station list with advisory message about plan check queue status
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: homeowner looks up a permit number that doesn't exist
**Source:** src/tools/stuck_permit.py — permit not found branch (QS8-T2-B)
**User:** homeowner
**Starting state:** User enters an incorrect or old permit number
**Goal:** Understand the permit cannot be found
**Expected outcome:** Tool returns a clear "not found" message with the queried permit number and a link to the DBI permit tracking portal so the user can verify the number themselves
**Edge cases seen in code:** DB error during connection (e.g., connection pool exhausted) returns a formatted error message with permit number preserved, not a raw exception traceback
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: what-if comparison on scope expansion
**Source:** src/tools/what_if_simulator.py (QS8-T2-C)
**User:** expediter
**Starting state:** Expediter has a base kitchen remodel project ($80K) and client is considering adding a bathroom.
**Goal:** Quickly compare how adding a bathroom changes timeline, fees, and revision risk without pulling up each tool separately.
**Expected outcome:** A comparison table showing base vs. variation side-by-side; review path, p50 timeline, estimated DBI fees, and revision risk are all populated. Delta section calls out meaningful changes (e.g., review path shift from OTC to In-house if triggered).
**Edge cases seen in code:** When underlying tools return errors for a variation, the row shows "N/A" in affected columns rather than crashing; the simulation still completes.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: what-if simulation with no variations (base only)
**Source:** src/tools/what_if_simulator.py (QS8-T2-C)
**User:** homeowner
**Starting state:** Homeowner asks about a kitchen remodel but doesn't specify any variations.
**Goal:** Get the baseline permit picture without needing to provide variations.
**Expected outcome:** Simulator runs with just the base scenario, produces a 1-row table, no "Delta vs. Base" section appears, and output still includes all column values (permits, review path, timeline, fees, risk).
**Edge cases seen in code:** Empty variations list is valid input; no delta section should be rendered.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: what-if detects OTC-to-in-house review path shift
**Source:** src/tools/what_if_simulator.py — _evaluate_scenario + delta section (QS8-T2-C)
**User:** expediter
**Starting state:** Base project is OTC-eligible (simple kitchen remodel). Variation adds scope that triggers in-house review (e.g., change of use, structural work).
**Goal:** Identify that the scope change moves the project out of OTC path, which has significant timeline implications.
**Expected outcome:** Delta section explicitly calls out "OTC → In-house" review path change and notes it "may add weeks". Both table rows show different Review Path values.
**Edge cases seen in code:** Only flagged when both base and variation have non-N/A review paths; partial data (one N/A) is silently skipped in the delta.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: what-if tool gracefully handles sub-tool database errors
**Source:** src/tools/what_if_simulator.py — _evaluate_scenario try/except blocks (QS8-T2-C)
**User:** expediter
**Starting state:** Local DuckDB database is not initialized or is locked (e.g., parallel test run).
**Goal:** Simulator still returns usable output even when one or more sub-tools fail due to DB unavailability.
**Expected outcome:** Affected cells show "N/A". Notes section lists which sub-tools encountered errors. No exception is raised to the caller. Other cells that succeeded show valid data.
**Edge cases seen in code:** Each of the four sub-tool calls is wrapped in try/except; errors are accumulated in result["notes"] and surfaced in a "Data Notes" section at the end of the output.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: expediter uses cost of delay to justify expediting fee
**Source:** src/tools/cost_of_delay.py — calculate_delay_cost (QS8-T2-D)
**User:** expediter
**Starting state:** Expediter has a restaurant permit client spending $80K/month on a closed location
**Goal:** Quantify the dollar value of shaving 30 days off the permit timeline
**Expected outcome:** Tool returns a formatted table showing carrying cost + revision risk cost per scenario. Break-even section shows daily delay cost. Expediter can use the daily rate to justify their expediting premium to the client.
**Edge cases seen in code:** revision_prob * revision_delay * daily_cost compounds even for p25 (best case) — there is always some expected revision cost regardless of timeline scenario
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: homeowner asks how much it costs to wait on a kitchen remodel permit
**Source:** src/tools/cost_of_delay.py — calculate_delay_cost (QS8-T2-D)
**User:** homeowner
**Starting state:** Homeowner is renting elsewhere at $5,000/month while waiting for kitchen remodel permit
**Goal:** Understand the total financial exposure of a kitchen remodel permit delay
**Expected outcome:** Tool returns best/likely/worst-case costs. Likely (p50 = 21 days) shows ~$3,450 carrying cost. OTC-eligible note appears since kitchen remodel can go OTC. Mitigation strategies include pre-application consultation.
**Edge cases seen in code:** OTC_ELIGIBLE_TYPES set — kitchen_remodel is in it, so the OTC note must appear
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: tool gracefully degrades when permit database is unavailable
**Source:** src/tools/cost_of_delay.py — _get_timeline_estimates fallback (QS8-T2-D)
**User:** expediter
**Starting state:** MCP server running in environment without DuckDB permit database
**Goal:** Get a cost of delay estimate for a commercial_ti permit
**Expected outcome:** Tool returns output using hard-coded historical averages (clearly noted in Methodology section with "Note: Live permit database unavailable" message). All sections present: table, break-even, mitigation, methodology.
**Edge cases seen in code:** db_available flag drives the note in Methodology section. Fallback timelines for all 13 permit types baked in.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: sequence timeline from permit routing history
**Source:** src/tools/estimate_timeline.py — estimate_sequence_timeline() (Sprint 76-1)
**User:** expediter
**Starting state:** A permit with a known application number has addenda routing records in the database. Station velocity data exists in station_velocity_v2 for at least some of those stations.
**Goal:** The expediter wants to understand how long the permit's specific review route will take, given the actual stations it has been routed through (not a generic estimate based on permit type).
**Expected outcome:** The response includes a per-station breakdown showing each station's p50 velocity, status (done/stalled/pending), whether it's running in parallel with another station, and a total estimate in days with a confidence level. Stations with no velocity data are listed as skipped.
**Edge cases seen in code:** If no addenda exist for the permit number, returns null (no estimate). If the station_velocity_v2 table doesn't exist yet, still returns a result with the station sequence but 0 total days and "low" confidence.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: parallel station detection in sequence model
**Source:** src/tools/estimate_timeline.py — estimate_sequence_timeline() parallel detection logic (Sprint 76-1)
**User:** expediter
**Starting state:** A permit has been routed to two or more stations simultaneously (same arrive date). Both stations have velocity data.
**Goal:** The timeline estimate correctly treats concurrent review stations as parallel (not additive), so the total estimate reflects real-world review time.
**Expected outcome:** The total_estimate_days uses the max p50 of the parallel group, not the sum. The station entries have is_parallel=true for the stations that overlap. The total is lower than if all stations were summed sequentially.
**Edge cases seen in code:** Parallel detection compares date portions (first 10 chars) of first_arrive timestamps. Stations with the same arrive date are grouped as parallel. Only the p50 of the longest station in the group contributes to the total.
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

## DATA INGEST & PIPELINE

## SUGGESTED SCENARIO: Nightly parcel refresh materializes counts
**Source:** QS5-A cron refresh-parcel-summary endpoint
**User:** admin
**Starting state:** permits, tax_rolls, complaints, violations, boiler_permits, inspections tables populated
**Goal:** Run nightly cron job to materialize one-row-per-parcel summary with counts from 5+ source tables
**Expected outcome:** parcel_summary populated with correct permit_count, open_permit_count, complaint_count, violation_count, boiler_permit_count, inspection_count; canonical_address is UPPER-cased; tax_value computed from land + improvement; health_tier joined from property_health
**Edge cases seen in code:** parcel with no tax_rolls data (NULL tax fields); parcel with no complaints/violations (zero counts); property_health table doesn't exist yet (NULL health_tier)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Incremental permit ingest reduces orphan rate
**Source:** QS5-B ingest_recent_permits + backfill
**User:** admin
**Starting state:** permit_changes has 52% orphan rate (permits detected by nightly tracker but not in bulk permits table)
**Goal:** Reduce orphan rate by ingesting recently-filed permits before change detection runs
**Expected outcome:** After incremental ingest runs nightly, orphan rate in permit_changes drops below 10% because recently-filed permits are already in the permits table when detect_changes() runs
**Edge cases seen in code:** SODA API may return 0 records during quiet periods; pagination needed for >10K results; must not run concurrently with full_ingest
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Nightly pipeline runs incremental ingest before change detection
**Source:** QS5-B pipeline ordering in run_nightly()
**User:** admin
**Starting state:** Nightly cron job triggers run_nightly() which detects permit changes
**Goal:** Prevent false "new_permit" entries by ensuring recently-filed permits are in the DB before change detection compares against it
**Expected outcome:** Pipeline sequence is: incremental ingest → fetch SODA changes → detect_changes(). The incremental ingest step is non-fatal — if it fails, change detection still runs.
**Edge cases seen in code:** Incremental ingest must not run if full_ingest completed recently (sequencing guard via cron_log check); DuckDB vs Postgres SQL differences handled by existing patterns
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Orphan inspection rate DQ check
**Source:** web/data_quality.py _check_orphan_inspections (QS5-C)
**User:** admin
**Starting state:** Admin viewing Data Quality dashboard with inspections and permits tables populated
**Goal:** Verify that orphan inspection rate is calculated correctly and displayed with appropriate severity
**Expected outcome:** Orphan rate shown as percentage with green (<5%), yellow (5-15%), or red (>15%) status; only permit-type inspections counted (complaint inspections excluded)
**Edge cases seen in code:** 68K complaint inspections use complaint numbers as reference_number (not permit numbers) — must be filtered out to avoid inflated orphan rate
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Trade permit pipeline health check
**Source:** web/data_quality.py _check_trade_permit_counts (QS5-C)
**User:** admin
**Starting state:** Admin viewing Data Quality dashboard with trade permit tables present
**Goal:** Verify that boiler and fire permit pipeline health is monitored
**Expected outcome:** Green status when both tables have data; red status flagging which specific table(s) are empty if pipeline is broken
**Edge cases seen in code:** Both tables could be empty simultaneously; fire_permits has no block/lot columns so can't join to parcel graph
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Expediter finds all active electrical permits at an address
**Source:** src/ingest.py — ingest_electrical_permits, _normalize_electrical_permit (QS8-T3-C)
**User:** expediter
**Starting state:** Electrical permits have been ingested into the permits table with permit_type='electrical'
**Goal:** Find all active electrical permits at a property to understand current electrical work scope
**Expected outcome:** Search returns electrical permits with correct address, status, description, and filing/issue dates; permit_type is clearly identified as electrical
**Edge cases seen in code:** zip_code field aliased to zipcode column — searches by zip must handle this; neighborhood and supervisor_district are NULL for electrical permits (not in source dataset)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Admin triggers selective re-ingest of only electrical permits from CLI
**Source:** src/ingest.py — main() argparse block, --electrical-permits flag (QS8-T3-C)
**User:** admin
**Starting state:** Full database is populated but electrical permit data may be stale
**Goal:** Re-ingest only electrical permits without touching other datasets to save time
**Expected outcome:** Running `python -m src.ingest --electrical-permits` updates only electrical permit records; building, plumbing, boiler, and all other tables are unchanged; ingest_log shows updated timestamp only for electrical endpoint
**Edge cases seen in code:** do_all logic: if ANY specific flag is passed, do_all=False and only flagged datasets run; --boiler flag controls boiler permits (not --boiler-permits)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## ADDITIONAL SCENARIOS (not categorized above)

## SUGGESTED SCENARIO: cost kill switch blocks AI routes without affecting browsing
**Source:** web/app.py _kill_switch_guard + web/cost_tracking.py (Sprint 76-2)
**User:** homeowner
**Starting state:** Admin has activated the API kill switch (daily spend exceeded $20). User is browsing the site and tries to use the AI analysis tool.
**Goal:** User submits a project description to the /ask or /analyze endpoint while kill switch is active.
**Expected outcome:** User receives a clear error message saying AI features are temporarily unavailable (cost protection), with a prompt to try again later. All non-AI pages (home, property reports, search) continue to function normally.
**Edge cases seen in code:** Kill switch check happens in before_request hook before rate limiter or view function runs. JSON 503 response with kill_switch=True field. Health endpoint never blocked.
**CC confidence:** high
**Status:** PENDING REVIEW
**DUPLICATE OF:** SCENARIO 32 (Kill switch blocks AI endpoints and returns 503 — approved Sprint 68-A)

---

## SUGGESTED SCENARIO: Property report skips gracefully when DuckDB not ingested
**Source:** tests/e2e/test_severity_scenarios.py — TestPropertyReport (Sprint 77-1)
**User:** expediter
**Starting state:** Fresh checkout; DuckDB lacks the permits table
**Goal:** Developer runs E2E tests to validate local environment
**Expected outcome:** Property report tests skip with a clear message ("DuckDB permits table absent — run python -m src.ingest") rather than failing with a raw traceback or unhelpful assertion error
**Edge cases seen in code:** Route returns 500 with DuckDB CatalogException when table is missing; test distinguishes this from a real app bug
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: plan analysis upload form is present for authenticated users
**Source:** tests/e2e/test_search_scenarios.py / web/templates/index.html (Sprint 77-3)
**User:** architect
**Starting state:** User is logged in as an architect or any authenticated role.
**Goal:** Find and interact with the plan analysis upload form.
**Expected outcome:** The authenticated dashboard shows a file input element that accepts .pdf files. The plan/upload/analyze section is mentioned in the page content.
**Edge cases seen in code:** File input has accept=".pdf" to restrict to PDF only. Max size is 400 MB.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: methodology page is substantive and publicly accessible
**Source:** tests/e2e/test_search_scenarios.py / web/routes_misc.py (Sprint 77-3)
**User:** homeowner (anonymous)
**Starting state:** No authentication. User navigates directly to /methodology.
**Goal:** Read about how SF Permits AI works — data sources, entity resolution, plan analysis.
**Expected outcome:** Page returns HTTP 200. Page contains at least 3 section headings. Mentions data sources, entity or search methodology, and plan analysis/AI vision. Page is not a stub.
**Edge cases seen in code:** Methodology page has a dedicated #plan-analysis section.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Anonymous landing page renders with search and hero
**Source:** tests/e2e/test_auth_mobile_scenarios.py — TestAnonymousLanding (Sprint 77-4)
**User:** homeowner
**Starting state:** User is not logged in; navigates to the root URL
**Goal:** Understand what sfpermits.ai offers before signing up
**Expected outcome:** Page renders with an h1 heading, a search input, and at least one reference to "permit" in the body content. A CTA to sign up or log in is present.
**Edge cases seen in code:** Landing vs Index templates — anonymous users see landing.html, authenticated see index.html. Both must render the search bar.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Beta request form renders and accepts input without JS errors
**Source:** tests/e2e/test_auth_mobile_scenarios.py — TestBetaRequestForm (Sprint 77-4)
**User:** homeowner
**Starting state:** User has not yet been invited; navigates to /beta-request
**Goal:** Request beta access by filling out the form
**Expected outcome:** Page returns HTTP 200. Form has email input, name input (or text input), a reason/message field, and a submit button. Filling all visible fields produces no JavaScript errors. Honeypot and rate limiting are backend-only and do not appear in the UI.
**Edge cases seen in code:** Honeypot field must not be visible to real users. Rate limit (3 requests/IP/hour) fires only on repeated POST submissions, not on page load.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Share analysis email modal uses dark theme
**Source:** results.html design token migration
**User:** expediter
**Starting state:** User has completed a permit analysis with an analysis_id
**Goal:** Share the analysis with a team member via email
**Expected outcome:** Share bar appears below results. Clicking "Email to your team" opens a modal with dark background (obsidian), monospaced email inputs, and teal focus rings. Entering valid email(s) and clicking Send delivers the share link. Modal closes on success.
**Edge cases seen in code:** Empty email input shows validation error. More than 5 recipients blocked. Invalid email format shows inline error message. Cancel closes modal without sending.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: security audit produces artifact on every run including failures
**Source:** .github/workflows/security.yml — continue-on-error + upload-artifact with if: always() (Sprint 74-3)
**User:** admin
**Starting state:** Security audit finds HIGH issues (audit step returns exit 1)
**Goal:** Review the detailed report even when the CI job is marked failed
**Expected outcome:** GitHub Actions artifact "security-audit-report-<run_id>" is uploaded and available for download; report contains full issue details
**Edge cases seen in code:** continue-on-error on audit step + explicit fail step pattern ensures report upload always runs before job marks failed
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: weekly security scan runs on Sunday without manual trigger
**Source:** .github/workflows/security.yml — schedule cron trigger (Sprint 74-3)
**User:** admin
**Starting state:** No new commits; cron fires on schedule
**Goal:** Catch newly disclosed vulnerabilities in dependencies between development cycles
**Expected outcome:** Workflow runs at 06:00 UTC Sunday, both bandit and pip-audit execute against current installed packages, report artifact is stored for 90 days
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Google Fonts loaded once via shared fragment
**Source:** QS4-C head_obsidian.html shared fragment
**User:** all
**Starting state:** Any Obsidian-migrated page is loaded
**Goal:** Page loads efficiently without duplicate font requests
**Expected outcome:** Google Fonts (IBM Plex Sans, JetBrains Mono) are loaded via a single shared fragment (head_obsidian.html) included by all migrated templates, rather than each template having its own font link — reducing duplicate network requests and ensuring font consistency
**Edge cases seen in code:** design-system.css also has an @import for Google Fonts; the fragment uses preconnect hints for faster loading
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: feature flags default open during beta; all authenticated users access premium features
**Source:** web/feature_gate.py (FEATURE_REGISTRY TODO comments) (QS8-T3-A)
**User:** homeowner
**Starting state:** Regular authenticated user with no special invite code; subscription_tier='free'
**Goal:** Access plan_analysis_full, entity_deep_dive, export_pdf, api_access, priority_support
**Expected outcome:** All 5 features accessible during beta period; no upgrade prompt; TODO comments in code mark the transition point
**Edge cases seen in code:** When beta ends, raising tier to PREMIUM will gate these for non-premium users; this is a deliberate gradual reveal pattern
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Circuit breaker thresholds configurable per deployment
**Source:** src/soda_client.py — SODA_CB_THRESHOLD and SODA_CB_TIMEOUT env vars (QS8-T1-C)
**User:** admin
**Starting state:** Default thresholds (5 failures, 60s cooldown) are too aggressive for a slow network environment
**Goal:** Operator adjusts circuit breaker sensitivity without code changes
**Expected outcome:** Setting SODA_CB_THRESHOLD=3 and SODA_CB_TIMEOUT=120 in Railway env vars changes behavior at app startup — lower failure tolerance, longer cooldown
**Edge cases seen in code:** Values are parsed as int() at client instantiation, not lazily — restart required for changes to take effect
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Health endpoint reports pool connection state (enhanced)
**Source:** QS8-T1-D / web/app.py /health route enhancement
**User:** admin
**Starting state:** App connected to PostgreSQL with active connection pool
**Goal:** Diagnose connection pool health without needing direct DB access
**Expected outcome:** GET /health returns pool_stats with backend, minconn, maxconn, pool_size, used_count, and health sub-object; cache_stats shows page_cache row count and oldest entry age; both fields present even when pool is unused (DuckDB fallback returns no_pool status)
**Edge cases seen in code:** DuckDB backend returns {"status": "no_pool", "backend": "duckdb"} for pool_stats; cache_stats falls back to {"error": "unavailable"} on any DB exception
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Homeowner checks plumbing permit status after water heater replacement
**Source:** src/ingest.py — ingest_plumbing_permits, _normalize_plumbing_permit (QS8-T3-C)
**User:** homeowner
**Starting state:** Plumbing permit filed and issued; data ingested into permits table with permit_type='plumbing'
**Goal:** Confirm their plumbing permit was issued and completed so they can close out with the contractor
**Expected outcome:** Permit lookup returns plumbing permit with filed_date, issued_date, completed_date, and status; parcel_number and unit fields (present in source data) are not exposed since they don't exist in the permits schema
**Edge cases seen in code:** parcel_number and unit fields exist in SODA dataset but are dropped during normalization — users asking for parcel_number won't find it via permit lookup
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Property inspector looks up boiler permit history for a commercial building
**Source:** src/ingest.py — ingest_boiler_permits, _normalize_boiler_permit (QS8-T3-C)
**User:** expediter
**Starting state:** Boiler permits have been ingested into the boiler_permits table (separate from the main permits table)
**Goal:** Find all boiler permits at a commercial property to verify boiler equipment compliance history
**Expected outcome:** Boiler permits are returned with boiler_type, boiler_serial_number, model, expiration_date, and application_date; results are from boiler_permits table (distinct from building/electrical/plumbing permits)
**Edge cases seen in code:** Boiler permits are NOT in the shared permits table — tools querying permits table only will miss them
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: developer evaluates cost impact of CEQA trigger on new construction
**Source:** src/tools/cost_of_delay.py — triggers parameter (QS8-T2-D)
**User:** architect
**Starting state:** Architect is scoping a new construction project that may trigger CEQA environmental review
**Goal:** See the cost difference between base timeline and CEQA-triggered timeline
**Expected outcome:** With triggers=['ceqa'], the p50 and p90 timelines are escalated by ~180 days. The cost table shows dramatically higher totals. The trigger note "CEQA environmental review" appears in the output.
**Edge cases seen in code:** TRIGGER_DELAYS maps ceqa to 180 days — largest single trigger escalation. Only applies when DB fallback is used (db_available=False).
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Table sort indicators reflect active sort state
**Source:** DESIGN_TOKENS.md obs-table sort indicators
**User:** expediter | architect
**Starting state:** User is viewing a data table with sortable columns (inspection history, permit list)
**Goal:** Sort the table by clicking a column header
**Expected outcome:** Chevron indicator appears on sortable columns. Active sort column shows teal chevron pointing up (asc) or down (desc). Clicking toggles direction. Only one column active at a time.
**Edge cases seen in code:** Tables with no data should show empty state row, not sort controls
**CC confidence:** high
**Status:** PENDING REVIEW


---
## SUGGESTED SCENARIO: MCP client discovers all 34 tools
**Source:** src/server.py — Phase 9 tool registration
**User:** expediter
**Starting state:** MCP client connects to the SF Permits MCP server
**Goal:** Client wants to discover all available tools including the 4 new intelligence tools
**Expected outcome:** Client receives a tool list containing predict_next_stations, diagnose_stuck_permit, simulate_what_if, and calculate_delay_cost alongside the existing 30 tools (34 total)
**Edge cases seen in code:** Server must import all 4 tools without error on startup; any missing dependency causes the entire server to fail to load
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Intelligence tool returns formatted markdown via MCP
**Source:** src/server.py — simulate_what_if and calculate_delay_cost registration
**User:** expediter
**Starting state:** MCP client has connected and discovered tools; user provides a project description with two variations
**Goal:** User calls simulate_what_if to compare scoping options before filing a permit application
**Expected outcome:** Tool returns a markdown comparison table with timeline, fee, review path, and revision risk columns for each variation — consumable by Claude in a planning conversation
**Edge cases seen in code:** Simulator calls predict_permits, estimate_timeline, estimate_fees, revision_risk internally — any sub-tool failure degrades gracefully to "N/A" in the table
**CC confidence:** medium
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: Admin views DB pool utilization in real-time

**Source:** web/routes_admin.py — /admin/health endpoint (Sprint 82-B)
**User:** admin
**Starting state:** Admin is logged in; production app is under moderate load with several active DB connections
**Goal:** Admin wants to assess whether the DB connection pool is under pressure without querying infrastructure directly
**Expected outcome:** Admin sees a pool card showing connections in use vs. available vs. max, with a fill bar reflecting current utilization. Card highlights visually when utilization is ≥ 70%. Panel auto-refreshes every 30 seconds without manual reload.
**Edge cases seen in code:** Pool is None (app just started or DuckDB mode) — card renders with 0/0 without crashing. Pool is exhausted (in_use == max) — bar fills to 100%, card shows danger border.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Admin sees SODA circuit breaker state change

**Source:** src/soda_client.py — _soda_circuit_breaker singleton + web/routes_admin.py (Sprint 82-B)
**User:** admin
**Starting state:** SODA API has started returning errors; circuit breaker has accumulated failures and transitioned to "open" state
**Goal:** Admin wants to know if the external SODA data API is degraded so they can inform users or take action
**Expected outcome:** System Health panel shows the SODA circuit breaker card with a red dot and "OPEN" state label. After the recovery timeout elapses, state changes to "HALF-OPEN" (amber dot), then back to "CLOSED" (green dot) on the next successful probe. The 30-second auto-refresh picks up the state change without page reload.
**Edge cases seen in code:** CircuitBreaker is per-module singleton — state persists across requests within a process; workers may have divergent state.
**CC confidence:** medium
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: Prod gate promotes when new issues differ from previous sprint
**Source:** scripts/prod_gate.py — hotfix ratchet logic
**User:** admin
**Starting state:** Previous sprint got score 3 with "Test Suite" failing. HOTFIX_REQUIRED.md exists recording "Test Suite". This sprint's builds fix the test suite but introduce a lint trend issue.
**Goal:** Understand whether the prod gate will block or allow promotion.
**Expected outcome:** Gate returns PROMOTE with mandatory hotfix, not HOLD. The ratchet does not trigger because the failing check changed from "Test Suite" to "Lint Trend". The hotfix file is overwritten to record the new failing check.
**Edge cases seen in code:** Partial overlap (some same, some new) still triggers ratchet. Legacy HOTFIX_REQUIRED.md files without the "## Failing checks" structured section do not trigger the ratchet.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Prod gate holds when same issue persists across sprints
**Source:** scripts/prod_gate.py — hotfix ratchet logic
**User:** admin
**Starting state:** Previous sprint got score 3 with "Migration Safety" failing. HOTFIX_REQUIRED.md exists recording "Migration Safety". This sprint still has migration safety issues and scores 3 again.
**Goal:** Understand whether the prod gate will escalate to HOLD.
**Expected outcome:** Gate returns HOLD with reason citing the overlapping check ("Migration Safety"). The ratchet message is clear that it is a repeat failure of the same specific check, not merely a consecutive score-3 sprint.
**Edge cases seen in code:** Score 4+ in any sprint between the two score-3 runs deletes HOTFIX_REQUIRED.md, so the ratchet resets — the second score-3 after a clean sprint is treated as first occurrence.
**CC confidence:** high
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: API client fetches next station prediction for active permit
**Source:** web/routes_api.py — GET /api/predict-next/<permit_number>
**User:** expediter
**Starting state:** User is logged in; permit 202201234567 is active with addenda routing records
**Goal:** Retrieve a structured prediction of the permit's next review stations via API
**Expected outcome:** 200 JSON response with permit_number and result (markdown) fields; prediction includes probability, p50 days for top 3 next stations
**Edge cases seen in code:** Permit not found returns markdown error message (not 404); permit with no addenda returns "No routing data available" in the result markdown
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: API rejects unauthenticated request with 401
**Source:** web/routes_api.py — all 4 intelligence endpoints
**User:** homeowner
**Starting state:** User is not logged in (no session cookie)
**Goal:** Call any intelligence API endpoint without authentication
**Expected outcome:** 401 JSON response with {"error": "unauthorized"}; no tool execution occurs
**Edge cases seen in code:** All 4 endpoints (predict-next, stuck-permit, what-if, delay-cost) share identical auth check pattern
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: What-if endpoint compares base vs variation scenarios
**Source:** web/routes_api.py — POST /api/what-if
**User:** architect
**Starting state:** User is logged in; wants to compare kitchen remodel vs kitchen+bathroom addition
**Goal:** POST base_description and one variation to see side-by-side permit, timeline, fee, and revision risk comparison
**Expected outcome:** 200 JSON with result field containing markdown comparison table; delta summary shows changes in review path, timeline, and fees between base and variation
**Edge cases seen in code:** Empty base_description returns 400; variations must be a list (not a string); omitting variations entirely is valid and evaluates only the base scenario
**CC confidence:** high
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: new developer finds clean sprint-prompts directory
**Source:** Sprint 85-C stale file cleanup
**User:** expediter
**Starting state:** New developer clones the repo and opens sprint-prompts/ for context
**Goal:** Quickly understand current and recent sprint history without wading through obsolete files
**Expected outcome:** Only current/recent sprint prompts are visible (qs8-*, qs9-*, sprint-79 through sprint-82); no qs3-*, qs4-*, qs5-*, qs7-*, sprint-64 through sprint-69, or sprint-74 through sprint-78 files are present
**Edge cases seen in code:** Stale sprint files from 2+ generations back (qs3, sprint-64) were mixed in with active ones — cleanup needed explicit retention rules to avoid deleting current qs8/qs9/sprint-79-82 files
**CC confidence:** medium
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: New developer reads README and finds accurate project stats
**Source:** README.md update (Sprint 85-D docs consolidation)
**User:** architect | expediter
**Starting state:** Developer opens README.md on a fresh checkout to understand project scope
**Goal:** Quickly understand how many tools exist, how many tests pass, and what phases are complete
**Expected outcome:** README accurately states 34 tools, 4357+ tests, and all phases 1-8 complete; no stale numbers from earlier sprints
**Edge cases seen in code:** README previously showed 21 tools and outdated test counts; stale docs cause developer confusion about what's actually shipped
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Architecture doc describes all 34 tools with one-line summaries
**Source:** docs/ARCHITECTURE.md update (Sprint 85-D docs consolidation)
**User:** architect | expediter
**Starting state:** Developer opens ARCHITECTURE.md to understand which tool to use for a given task
**Goal:** Find the right MCP tool by scanning the tool inventory
**Expected outcome:** ARCHITECTURE.md lists all 34 tools with file paths and one-line descriptions; Phase 8 tools (predict_next_stations, diagnose_stuck_permit, simulate_what_if, calculate_delay_cost) are clearly described with their algorithms and data sources
**Edge cases seen in code:** Architecture doc previously showed 21 tools and was missing Phase 6-8 tools entirely
**CC confidence:** high
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: Landing page displays key capability questions to new visitor
**Source:** tests/test_landing.py — test_landing_has_feature_cards
**User:** homeowner
**Starting state:** User is unauthenticated, visits the root URL
**Goal:** Understand what the product does before signing up
**Expected outcome:** The landing page presents the three core capability questions ("Do I need a permit?", "How long will it take?", "Is my permit stuck?") as navigable sections
**Edge cases seen in code:** Sub-row anchor links (#cap-permits, #cap-timeline, #cap-stuck) must resolve to the correct section IDs on the page
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Landing page shows data credibility stats to build trust
**Source:** tests/test_landing.py — test_landing_has_stats
**User:** homeowner
**Starting state:** User is unauthenticated, visits the root URL
**Goal:** Verify that the site is backed by real data before trusting it
**Expected outcome:** The landing page shows quantified stats including SF building permit count and city data source count, giving credibility to the AI guidance
**Edge cases seen in code:** The permit count is rendered via a JS counting animation (data-target attribute) — the static label "SF building permits" must be present even before JS runs
**CC confidence:** high
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: Page cache returns cached result on second request
**Source:** tests/test_page_cache.py — TestCacheMissAndHit
**User:** expediter | homeowner | architect | admin
**Starting state:** Page cache is empty (no cached entry for the requested key)
**Goal:** Retrieve the same data twice — the second request should be served from cache without recomputing
**Expected outcome:** The compute function is called exactly once; the second response includes `_cached: true` and `_cached_at` timestamp indicating it was served from cache
**Edge cases seen in code:** TTL=0 forces every read to recompute; large nested payloads (100 items) round-trip without truncation; empty dict `{}` is cached and annotated correctly
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Page cache cleanup prevents cross-test contamination
**Source:** tests/conftest.py — _restore_db_path fixture; tests/test_page_cache.py — _clear_page_cache fixture
**User:** admin
**Starting state:** A prior test (e.g. test_qs3_a_permit_prep.py) called importlib.reload(src.db), resetting _DUCKDB_PATH to the real database path rather than the session temp path
**Goal:** Subsequent page_cache tests should still connect to the correct session-scoped temp database and see cache entries they wrote in the same test
**Expected outcome:** The `_restore_db_path` conftest fixture restores `_DUCKDB_PATH`, `BACKEND`, and `DATABASE_URL` after each test; the `_clear_page_cache` fixture truncates all rows from page_cache so no stale key from any prefix can produce a false hit
**Edge cases seen in code:** TEST GUARD in conftest raises RuntimeError when the real DB path is opened during tests — this RuntimeError was silently swallowed by get_cached_or_compute's bare `except Exception: pass`, causing every cache read to silently fail and compute_fn to be called on every request
**CC confidence:** high
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: Cron endpoint rejects unauthenticated requests with 403
**Source:** tests/test_brief_cache.py, tests/test_sprint_79_3.py — CRON_WORKER env var audit
**User:** admin
**Starting state:** CRON_WORKER=1 is set (cron worker mode active), CRON_SECRET is set to a known value
**Goal:** Verify that /cron/* endpoints reject requests without a valid CRON_SECRET bearer token
**Expected outcome:** POST to any /cron/* endpoint without Authorization header returns 403; wrong token also returns 403; only the correct bearer token grants access
**Edge cases seen in code:** Some endpoints check for missing header vs wrong secret separately; both should return 403 (not 500)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Cron endpoint returns 404 when CRON_WORKER not set (guard behavior)
**Source:** tests/test_station_velocity_v2.py, tests/test_db_backup.py, tests/test_reference_tables.py — CRON_GUARD pattern
**User:** admin
**Starting state:** CRON_WORKER env var is NOT set (web worker mode, the default)
**Goal:** Verify that the cron guard blocks POST requests to /cron/* routes on web workers
**Expected outcome:** POST to /cron/* returns 404 (not 403, not 500) — the cron guard intercepts before auth; GET requests to /cron/* are still allowed through on web workers
**Edge cases seen in code:** GET /cron/status and GET /cron/pipeline-health are allowed on web workers; only POST is blocked; the 404 comes from the guard before any route handler runs
**CC confidence:** high
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: Post-sprint cleanup removes all merged worktree branches

**Source:** Sprint 83-D branch cleanup task
**User:** admin
**Starting state:** Repository has accumulated stale worktree branches from multiple sprints that have since been merged into main; some branches have active worktree directories, some do not
**Goal:** Remove all stale merged worktree branches to reduce repo clutter without disrupting any active work sessions
**Expected outcome:** Branches that are merged into main AND have no active worktree checked out are deleted; branches currently checked out in active worktrees are not deleted (git prevents this); unmerged sprint branches are reported but not deleted; git worktree prune clears stale admin references
**Edge cases seen in code:** A branch can be merged into main but still have an active worktree checked out (git will refuse deletion with `+` prefix marker in --merged output); prunable worktrees (nested inside other worktrees) are flagged but only cleared by prune, not by branch deletion
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: DB pool exhaustion visible in logs before outage
**Source:** Sprint 84-A — src/db.py pool exhaustion warning
**User:** admin
**Starting state:** App is under heavy load; DB pool is 80%+ utilized
**Goal:** Detect connection pressure before it becomes a user-facing error
**Expected outcome:** Warning log appears citing current utilization percentage; no user request is dropped; admin can act (scale pool or traffic) before connections are exhausted
**Edge cases seen in code:** Warning fires on every acquired connection above threshold — could be noisy at sustained high load
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Consistent rate limiting across dyno restarts
**Source:** Sprint 84-C — web/helpers.py Redis rate limiter
**User:** expediter
**Starting state:** User has made 18 of 20 allowed requests; app dyno restarts mid-window
**Goal:** Rate limit state is preserved so user cannot reset their count by triggering a restart
**Expected outcome:** With Redis enabled, the counter survives the dyno restart; user's next 2 requests succeed and the 3rd is blocked until the window expires
**Edge cases seen in code:** Without Redis, in-memory state is lost on restart — documented as known limitation in SCALING.md
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Load test surfaces p95 regression before prod deploy
**Source:** Sprint 84-D — scripts/load_test.py
**User:** admin
**Starting state:** A new build is on staging; no load has been applied yet
**Goal:** Catch latency regression before the build hits production users
**Expected outcome:** Running load_test.py against staging reports p95 > acceptable threshold; deploy is held; root cause identified in logs
**Edge cases seen in code:** Script exits 1 when error rate exceeds 5% — useful as a deploy gate signal
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Test suite maintains isolation when one test reloads a module
**Source:** Sprint 83-B — conftest.py _restore_db_path autouse fixture
**User:** admin
**Starting state:** Test A calls importlib.reload(src.db) as part of its app fixture setup, which resets module-level globals like _DUCKDB_PATH
**Goal:** Subsequent tests should not inherit the leaked state from Test A's module reload
**Expected outcome:** Test B runs with the correct session-scoped temp DuckDB path regardless of test ordering; _DUCKDB_PATH, BACKEND, and DATABASE_URL are restored after every test via autouse fixture
**Edge cases seen in code:** The bare `except Exception: pass` in get_cached_or_compute() was silently swallowing the TEST_GUARD RuntimeError when _DUCKDB_PATH pointed at the real DB — making every cache miss look like a hit miss with no error output
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Test hygiene hook warns on anti-patterns
**Source:** scripts/test_hygiene.py, .claude/hooks/test-hygiene-hook.sh
**User:** admin
**Starting state:** Agent is writing a new test file to tests/ directory
**Goal:** Prevent cross-test contamination from os.environ assignments, sys.path.insert, importlib.reload, and bare 'from app import' patterns
**Expected outcome:** When agent writes a test file containing anti-patterns, the hook fires a non-blocking stderr warning identifying each violation with a fix suggestion; the write proceeds (exit 0); agent is informed but not blocked
**Edge cases seen in code:** os.environ.get() and monkeypatch lines must not trigger false positives; non-test files (src/, web/) must be silently ignored; the hook must handle malformed JSON gracefully
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: CHECKQUAD terminal close produces structured artifact
**Source:** dforge swarm-coordination template — CHECKQUAD protocol
**User:** admin
**Starting state:** Quad sprint terminal has finished all agent work; agents have committed to worktree branches and reported COMPLETE
**Goal:** Close the terminal session with a structured session artifact that T0 can systematically review
**Expected outcome:** Terminal merges agent branches, writes qa-drop/qsN-tN-session.md with Agent Results table (PASS/FAIL per agent), Merge Conflicts, File Ownership Violations, Test Surprises, Gotchas Discovered, and Impediments sections; concatenates per-agent scenario and changelog files into per-terminal files; runs test hygiene audit; prints CHECKQUAD banner; does NOT update canonical STATUS.md/CHANGELOG.md or ship to Chief
**Edge cases seen in code:** Session artifact must contain PASS/FAIL lines to satisfy the stop hook; terminal must write '## CHECKCHAT' header to trigger the hook gate; per-terminal files (scenarios-pending-review-tN.md) must not collide with canonical files
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: CHECKQUAD-T0 harvests dforge lessons from session artifacts
**Source:** dforge swarm-coordination template — CHECKQUAD-T0 Step 6: HARVEST
**User:** admin
**Starting state:** All quad sprint terminals have completed CHECKQUAD and pushed to main; session artifacts exist in qa-drop/
**Goal:** Systematically extract generalizable patterns from terminal session artifacts into dforge lessons
**Expected outcome:** T0 reads all qa-drop/qsN-t*-session.md files; identifies dforge-worthy patterns from Gotchas Discovered, Test Surprises, and Merge Conflicts sections; applies criteria (would help different project, agents would repeat without guidance, cost >10 min to diagnose); proposes lessons in standard dforge format
**Edge cases seen in code:** Some gotchas are project-specific (DuckDB syntax) vs generalizable (env leak patterns); T0 must distinguish between the two
**CC confidence:** medium
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: Admin switches to Beta Active persona to preview watch state
**Source:** QS10 T2 Agent 2A — admin persona impersonation
**User:** admin
**Starting state:** Admin is logged in with the feedback widget open; no persona is active
**Goal:** Switch to "Beta Active (3 watches)" persona to preview the UI as a beta user with 3 active watches
**Expected outcome:** The persona dropdown shows "Beta Active (3 watches)" as selected; applying it injects the persona into the session and shows a success status; navigating to any watch-aware page reflects the beta-user watch state (3 watches visible)
**Edge cases seen in code:** Applying a persona does not modify the real user_id — the admin's account is preserved
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Admin resets impersonation and returns to their own session
**Source:** QS10 T2 Agent 2A — admin persona impersonation
**User:** admin
**Starting state:** Admin has an active persona ("Beta Active") injected into the session
**Goal:** Clear the impersonation and return to their real admin session state
**Expected outcome:** After clicking the Reset link (or navigating to reset URL), all persona session keys are cleared; the UI no longer shows any active persona; the admin sees their real account state
**Edge cases seen in code:** Reset does not clear the user_id — only the impersonation overlay keys are removed
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Non-admin user cannot access the impersonation endpoint
**Source:** QS10 T2 Agent 2A — admin persona impersonation
**User:** expediter (non-admin authenticated user)
**Starting state:** A regular (non-admin) user is logged in
**Goal:** Attempt to POST to the persona impersonation endpoint directly
**Expected outcome:** The server returns 403 Forbidden; no session changes are made; the user remains in their original state
**CC confidence:** high
**Status:** PENDING REVIEW

---

# T2 Sprint 87 — Suggested Scenarios

## SUGGESTED SCENARIO: admin sees pending visual QA badge count in widget
**Source:** feedback_widget.html qa-review-panel, qa-results/pending-reviews.json
**User:** admin
**Starting state:** Tim is logged in as admin. vision_score.py has written 3 entries to pending-reviews.json for pages scoring below 3.0.
**Goal:** Tim opens the feedback widget and immediately sees how many visual QA items need his review.
**Expected outcome:** The "QA Reviews" panel is visible at the top of the feedback modal with a badge showing "3 pending". Non-admin users do not see this panel.
**Edge cases seen in code:** Badge defaults to 0 when qa_pending_count is not injected by the rendering route.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: admin accepts a borderline visual QA item with an explanatory note
**Source:** web/routes_admin.py admin_qa_decision, qa-results/review-decisions.json
**User:** admin
**Starting state:** A page scored 2.8/5 — above the auto-reject threshold but flagged for human review. The pending entry is loaded into the widget via window.qaLoadItem().
**Goal:** Tim reviews the screenshot context, decides the layout is acceptable for data-dense pages, and accepts it with a note for training purposes.
**Expected outcome:** The Accept button returns a green "Accepted" confirmation. The decision is written to review-decisions.json with tim_verdict="accept", the note field populated, and a timestamp. The entry is removed from pending-reviews.json.
**Edge cases seen in code:** Note is capped at 500 characters; pipeline_score coerced to float.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: admin rejects a layout regression; item tracked for follow-up
**Source:** web/routes_admin.py admin_qa_decision, qa-results/pending-reviews.json
**User:** admin
**Starting state:** A page scored 1.6/5 — clearly broken centering. Entry loaded into widget via window.qaLoadItem().
**Goal:** Tim rejects the item so it remains tracked for a fix in the next sprint.
**Expected outcome:** The Reject button returns a red "Rejected — flagged for fix" message. The decision appears in review-decisions.json with tim_verdict="reject". The entry is removed from pending-reviews.json (verdict recorded; fix tracking handled separately by the sprint workflow).
**Edge cases seen in code:** Missing pending-reviews.json is handled gracefully — endpoint does not crash.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Accept/Reject/Note decisions persist as training data across sessions
**Source:** qa-results/review-decisions.json (append-only array)
**User:** admin
**Starting state:** Tim has made 10+ decisions across multiple QA sessions. review-decisions.json contains entries from previous sprints.
**Goal:** The QS10 orchestrator reads review-decisions.json to build a training dataset for vision_score.py calibration.
**Expected outcome:** review-decisions.json is a valid JSON array containing all decisions in append order with page, persona, viewport, dimension, pipeline_score, tim_verdict, sprint, note, and timestamp fields. No entries are overwritten — only appended.
**Edge cases seen in code:** Atomic write (tmp + rename) prevents partial writes on crash.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor happy path — active permit
**Source:** station_predictor.html / tools_station_predictor route
**User:** expediter
**Starting state:** Authenticated user has a permit number for a currently active permit in the DBI system.
**Goal:** Quickly see which review stations the permit will likely pass through next, to plan client communication and set expectations.
**Expected outcome:** Predicted routing stations are displayed in formatted markdown. The result shows the permit number back to the user and a sequence of likely upcoming stations with any relevant commentary.
**Edge cases seen in code:** API returns {"permit_number": str, "result": str (markdown)} — result must be parsed and rendered as markdown, not raw text.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor — unauthenticated access redirects to login
**Source:** station_predictor.html / tools_station_predictor route
**User:** homeowner
**Starting state:** Unauthenticated user navigates directly to the Station Predictor URL.
**Goal:** Access the station predictor tool.
**Expected outcome:** User is redirected to the login page without seeing any permit data. After logging in, they can return to the tool.
**Edge cases seen in code:** Route checks g.user and redirects to /auth/login if falsy. The client-side JavaScript also handles 401 API responses with a "Please log in" message for any JS-initiated calls before the redirect fires.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor — invalid or nonexistent permit number
**Source:** station_predictor.html / tools_station_predictor route
**User:** expediter
**Starting state:** Authenticated user enters a permit number that does not exist in the system or is malformed.
**Goal:** Get routing prediction for what turns out to be an invalid permit.
**Expected outcome:** An error message is displayed in the results area. The tool does not crash. User can enter a different permit number and try again without page reload.
**Edge cases seen in code:** API returns {"error": "..."} on failure; client-side showError() renders it. Empty input triggers a client-side validation message before the fetch fires.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor — markdown result rendering
**Source:** station_predictor.html / tools_station_predictor route
**User:** architect
**Starting state:** Authenticated user submits a valid permit number. The API returns a richly formatted markdown response with headers, bullets, and code spans for station names.
**Goal:** Read the predicted routing in a clear, formatted view.
**Expected outcome:** Markdown is rendered as HTML — headers appear as styled headings, bullet lists render as bullets, station code spans appear in monospace. Raw markdown text is never shown to the user.
**Edge cases seen in code:** Template uses marked.js with a fallback to <pre> if marked is unavailable. Code spans styled with --mono font family and --accent color.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: station predictor — Enter key submits the form
**Source:** station_predictor.html / tools_station_predictor route
**User:** expediter
**Starting state:** Authenticated user has typed a permit number into the input field.
**Goal:** Submit the prediction request by pressing Enter rather than clicking the button.
**Expected outcome:** The prediction fires when Enter is pressed in the permit number field, identical to clicking the button. This matches the expected keyboard workflow for power users.
**Edge cases seen in code:** keydown listener on the input checks for e.key === 'Enter' and calls runPrediction().
# Agent 3B — Scenarios (Sprint QS10-T3)

## SUGGESTED SCENARIO: expediter diagnoses a stalled permit
**Source:** stuck_permit.html / tools_stuck_permit route
**User:** expediter
**Starting state:** Expediter is logged in. They have a permit number for a project that has not moved in 90+ days.
**Goal:** Understand why the permit is stuck and get a prioritized list of actions to unstick it.
**Expected outcome:** User enters permit number, submits, and receives a ranked intervention playbook in readable form explaining probable delay causes and concrete next steps. Response renders correctly with no raw markdown visible.
**Edge cases seen in code:** API returns markdown text in `result` field — marked.js parses it; if marked not loaded, a pre-formatted fallback is shown.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: unauthenticated user attempts to use stuck permit analyzer
**Source:** tools_stuck_permit route (auth guard) / 401 handling in stuck_permit.html
**User:** homeowner
**Starting state:** User is not logged in (no active session). They navigate directly to the stuck permit analyzer tool.
**Goal:** Access the analyzer to diagnose their permit.
**Expected outcome:** User is redirected to the login page without seeing the tool UI. If they somehow reach the page and trigger the API call without session, a login prompt appears in the results area (not a raw 401 error).
**Edge cases seen in code:** Route-level redirect (302) for unauthenticated GET; JS 401 handler renders auth prompt inline for any race conditions.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: user enters an invalid or unknown permit number
**Source:** stuck_permit.html error handling
**User:** homeowner
**Starting state:** User is logged in. They type an invalid or non-existent permit number and click Diagnose.
**Goal:** Get information about their permit even with an incorrect number.
**Expected outcome:** User sees a clear error message (not a crash or blank screen) indicating the analysis failed. The error message is rendered in the results area with contextual styling.
**Edge cases seen in code:** API may return 500 with `{"error": "..."}` — JS catch block renders the error.message; empty permit number short-circuits before making the API call.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: user navigates to stuck permit analyzer on mobile
**Source:** stuck_permit.html responsive styles
**User:** expediter
**Starting state:** User is on a mobile device (375px viewport), logged in.
**Goal:** Use the stuck permit analyzer on the go.
**Expected outcome:** Input field and diagnose button stack vertically and fill the full width. Page renders without horizontal overflow. Results playbook is readable.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: playbook renders rich markdown with headers and lists
**Source:** stuck_permit.html — marked.js integration + .playbook-content styles
**User:** architect
**Starting state:** User is logged in. The stuck permit API returns a multi-section markdown playbook with headers, bullet lists, and bold text.
**Goal:** Read a structured intervention plan for their client's delayed permit.
**Expected outcome:** Markdown is parsed and displayed as formatted HTML — headers use the sans-serif type stack, code spans use monospace, bullet lists are indented. No raw markdown characters (**, ##, *, `) are visible to the user.
## SUGGESTED SCENARIO: what-if base project only, no variations
**Source:** what_if.html / tools_what_if route
**User:** expediter
**Starting state:** Authenticated user on the What-If Simulator page with no input
**Goal:** Analyze a base project description to understand its permit implications without comparing variations
**Expected outcome:** After entering a base project description and submitting, the simulator returns a structured analysis of the project's expected timeline, fees, and revision risk without requiring any variation input
**Edge cases seen in code:** Variations array can be empty — API accepts base_description alone; empty variations are excluded from the JSON body
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: what-if comparison with two variations
**Source:** what_if.html / tools_what_if route
**User:** architect
**Starting state:** Authenticated user on the What-If Simulator page; user is evaluating two design options for a client's project
**Goal:** Compare how two different project scopes (e.g., ADU with and without solar panels) would differ in timeline, fees, and revision risk
**Expected outcome:** After entering a base description and two labeled variations, the simulator returns a side-by-side comparison table showing how each variation changes the projected timeline, fees, and revision risk relative to the base
**Edge cases seen in code:** Variations with empty label get auto-labeled (A, B, C); max 3 variations enforced in UI
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: what-if unauthenticated access redirects to login
**Source:** tools_what_if route in web/routes_search.py
**User:** homeowner
**Starting state:** User is not logged in and navigates directly to the What-If Simulator URL
**Goal:** Access the What-If Simulator
**Expected outcome:** User is redirected to the login page; after logging in, they can access the simulator
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: what-if 401 error shows login prompt inline
**Source:** what_if.html — fetch error handling
**User:** expediter
**Starting state:** Authenticated user's session expires while on the What-If Simulator page
**Goal:** Submit a simulation after session expiry
**Expected outcome:** The simulator displays a friendly prompt to log in again (inline in the results area) rather than a cryptic error or a full page redirect
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: what-if variation add/remove flow
**Source:** what_if.html — variation JS logic
**User:** architect
**Starting state:** Authenticated user on the What-If Simulator with one variation visible (Variation A)
**Goal:** Add a second and third variation, remove the second, then submit with only the first and third
**Expected outcome:** The Add Variation button is disabled after three variations are shown; removing a variation hides it and clears its fields; the simulation submission includes only the variations that are currently visible and have content
**Edge cases seen in code:** Max 3 variations; remove button clears field values; visible count tracked to gate Add button
**CC confidence:** medium
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: developer calculates delay cost for ADU project
**Source:** cost_of_delay.html / tools_cost_of_delay route
**User:** developer
**Starting state:** Developer is logged in and has a pending ADU permit with known monthly carrying costs (mortgage, opportunity cost).
**Goal:** Understand the total financial exposure from SF permit processing delays on their ADU project.
**Expected outcome:** Calculator accepts permit type "adu" and a monthly cost, calls the API, and renders a markdown breakdown of estimated delay costs with timeline percentiles.
**Edge cases seen in code:** API returns 400 if monthly_carrying_cost is 0 or negative — client-side validation must block submission before reaching the server.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: unauthenticated user blocked at gate
**Source:** tools_cost_of_delay route (g.user check + 401 handling in JS)
**User:** homeowner
**Starting state:** Visitor is not logged in and navigates directly to /tools/cost-of-delay.
**Goal:** Access the Cost of Delay Calculator.
**Expected outcome:** User is redirected to the login page (server-side redirect before the page renders). If they somehow reach the page and submit the form, a "you must be logged in" message appears inline with a link to log in.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: expediter adds neighborhood and delay triggers for precise estimate
**Source:** cost_of_delay.html — optional neighborhood and triggers inputs
**User:** expediter
**Starting state:** Expediter is logged in with a restaurant project in the Mission with known risk factors (active complaint, change of use).
**Goal:** Get a more accurate delay cost estimate by providing optional context.
**Expected outcome:** Form accepts neighborhood "Mission" and triggers "active complaint, change of use" as comma-separated values; API receives them as an array; result reflects the higher-risk scenario.
**Edge cases seen in code:** Triggers are split on comma and filtered for empty strings before JSON serialization.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: user submits with zero monthly cost
**Source:** cost_of_delay.html — client-side validation on monthly_carrying_cost
**User:** homeowner
**Starting state:** Homeowner is logged in and fills out the form with permit type "kitchen remodel" but enters "0" for monthly carrying cost.
**Goal:** Submit the form.
**Expected outcome:** Form does not submit. An inline error message appears below the monthly cost field stating the value must be greater than zero. No network request is made.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: result renders markdown cost breakdown
**Source:** cost_of_delay.html — marked.parse() call on API result
**User:** developer
**Starting state:** Developer is logged in and submits a valid request (permit type "commercial", monthly cost $8000, neighborhood "SoMa").
**Goal:** Read the AI-generated cost breakdown.
**Expected outcome:** The results area becomes visible. The markdown response is rendered as structured HTML — headings, bullet lists, bold currency values — not as raw markdown text.
**CC confidence:** high
**Status:** PENDING REVIEW
# Sprint 89-4A — Suggested Scenarios

## SUGGESTED SCENARIO: New beta user clicks invite link and completes 3-step onboarding
**Source:** Sprint 89 — Beta Onboarding Flow
**User:** homeowner
**Starting state:** User has a valid beta invite link (/beta/join?code=xxx). User is unauthenticated.
**Goal:** Complete beta onboarding from invite link to dashboard
**Expected outcome:** User is redirected to login with code preserved, logs in, tier is upgraded to beta, is walked through 3-step onboarding (welcome → add property → severity preview), lands on dashboard with onboarding marked complete
**Edge cases seen in code:** Code is preserved as query param through login redirect; if INVITE_CODES is empty (open signup) validate_invite_code returns True for any code
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Free user encounters tier gate teaser on gated feature
**Source:** Sprint 89 — @requires_tier decorator
**User:** homeowner
**Starting state:** User is authenticated with subscription_tier = 'free'. They navigate to a route decorated with @requires_tier('beta').
**Goal:** Access a beta-gated feature
**Expected outcome:** User sees a 403 page with a glass-card teaser explaining the beta feature benefit and a CTA to join beta. Current plan is shown as "free". No raw error page — a properly branded upgrade prompt.
**Edge cases seen in code:** has_tier() treats None, missing, or unknown tier values as free (level 0); tier hierarchy means premium users automatically pass beta checks
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Already-beta user clicks invite link again — no double upgrade
**Source:** Sprint 89 — Beta Onboarding Flow
**User:** expediter
**Starting state:** User is authenticated with subscription_tier = 'beta'. They receive a second invite link and click it.
**Goal:** Click a beta invite link they already used
**Expected outcome:** User is immediately redirected to dashboard (/). No tier modification, no error. No second round of onboarding is triggered.
**Edge cases seen in code:** Route checks current_tier in ("beta", "premium") before calling execute_write; premium users also skip the upgrade
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Unauthenticated user hits /beta/join — redirected to login with code preserved
**Source:** Sprint 89 — Beta Onboarding Flow
**User:** homeowner
**Starting state:** User is not logged in. They click a beta invite link with a valid code.
**Goal:** Start beta onboarding without being logged in
**Expected outcome:** Redirected to /auth/login with invite_code and referral_source=beta_invite as query parameters. After login, the invite link can be re-visited to complete the tier upgrade.
**Edge cases seen in code:** The redirect preserves the code via query string concatenation; the login page already handles invite_code form field for pre-filling
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Premium user accessing beta-gated feature passes tier check
**Source:** Sprint 89 — @requires_tier decorator + tier hierarchy
**User:** expediter
**Starting state:** User has subscription_tier = 'premium'. They access a route decorated with @requires_tier('beta').
**Goal:** Access a feature that requires beta tier
**Expected outcome:** Full content is rendered (not the teaser). Tier hierarchy means premium >= beta, so premium users always pass beta checks.
**Edge cases seen in code:** _TIER_LEVELS dict uses numeric ordering; _user_tier_level() defaults unknown tiers to 0; the check is >= not ==
**CC confidence:** high
**Status:** PENDING REVIEW

---

# Sprint 89-4B — Suggested Scenarios (Agent 4B)

## SUGGESTED SCENARIO: Free user hits portfolio tier gate
**Source:** Sprint 89 — Tier-Gated Content Application
**User:** homeowner
**Starting state:** User has free tier account, clicks Portfolio in nav
**Goal:** View their property portfolio
**Expected outcome:** Sees portfolio page with upgrade teaser — clear value prop,
  CTA to upgrade to beta, not a hard 403 error. The page returns 200 so HTMX
  and nav continue to work correctly.
**Edge cases seen in code:** tier_locked=True still returns 200 so HTMX works correctly;
  empty properties/summary dicts passed to avoid template errors in teaser mode
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Free user sees morning brief header but body is gated
**Source:** Sprint 89 — Brief Tier Gate
**User:** homeowner
**Starting state:** Free tier account, navigates to /brief
**Goal:** View their morning brief
**Expected outcome:** Sees the brief page with the morning greeting ("Good morning..."),
  but the property data sections are replaced by a beta upgrade teaser with clear
  value proposition (full severity analysis, AI risk assessment). Not a 403.
**Edge cases seen in code:** Brief header is always rendered; teaser replaces the
  content body between the header and freshness footer
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Free user asks a question, sees AI teaser in search results
**Source:** Sprint 89 — AI Consultation Tier Gate
**User:** homeowner
**Starting state:** Free tier, types a general question in the /ask search box
**Goal:** Get AI analysis of their permit situation
**Expected outcome:** Sees teaser card in search results panel explaining the beta
  AI feature, with upgrade CTA. Not a blank response, not an error, not a redirect.
  Data lookups (permit number, address search) still work without gating.
**Edge cases seen in code:** AI synthesis intents (draft_response, general_question)
  are gated; data lookup intents (lookup_permit, search_address, search_complaint,
  search_parcel, search_person, validate_plans) bypass the gate entirely
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Beta user sees full AI consultation
**Source:** Sprint 89 — Tier-Gated Content Application
**User:** expediter
**Starting state:** Beta tier account
**Goal:** Get AI analysis via /ask
**Expected outcome:** Full AI response (draft_response template) — no teaser, no tier gate.
  Modifier quick-actions (shorter, cite_sources, get_meeting) also work without gating.
**Edge cases seen in code:** has_tier(user, 'beta') returns True for both beta and
  premium users; modifier path also checks tier before calling _ask_draft_response
**CC confidence:** high
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: Tier gate overlay shows on gated page for free user

**Source:** web/templates/components/tier_gate_overlay.html, web/static/css/tier-gate.css
**User:** homeowner
**Starting state:** User is logged in as free tier. Visits a gated feature page (e.g., property report, permit timeline). The route injects `tier_locked=True` into the template context.
**Goal:** User wants to view permit details for their property.
**Expected outcome:** Page content is visible but blurred (structure visible, text unreadable). A centered overlay card appears with a "Get access" CTA linking to /beta/join. User can see the page has valuable data without being able to read it.
**Edge cases seen in code:** `tier_locked=False` produces zero DOM output — no overlay, no blur — ensuring entitled users see no performance or layout impact.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Tier gate CTA navigates to beta join flow

**Source:** web/templates/components/tier_gate_overlay.html
**User:** homeowner
**Starting state:** Free user is viewing a gated page with the blur overlay active.
**Goal:** User clicks the "Get access" CTA.
**Expected outcome:** User is navigated to /beta/join to begin the beta signup flow. The CTA href is hardcoded (not dynamic) so it works before the user has a session context.
**Edge cases seen in code:** CTA has `data-track="tier-gate-click"` for analytics — the click event should be captured even if the page navigates immediately after.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Tier gate overlay does not appear for entitled user

**Source:** web/templates/components/tier_gate_overlay.html
**User:** homeowner (beta tier)
**Starting state:** User is logged in as beta tier. Visits a page that is gated for free users only. Route injects `tier_locked=False`.
**Goal:** User accesses their permit data normally.
**Expected outcome:** Page renders without any blur or overlay. The tier_gate_overlay.html partial renders nothing (template conditional is False). No `.tier-locked-content` class is applied to any DOM element.
**Edge cases seen in code:** JS checks for `.tier-gate-overlay` presence before adding blur — no overlay means no blur is ever applied.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Tier gate overlay is accessible on mobile viewport

**Source:** web/static/css/tier-gate.css (mobile breakpoint at 480px)
**User:** homeowner
**Starting state:** Free user visits a gated page on a mobile device (viewport < 480px).
**Goal:** User sees the tier gate CTA on their phone.
**Expected outcome:** The overlay card adjusts padding. The CTA becomes a full-width block button for easier touch targeting. The card does not overflow its viewport horizontally.
**Edge cases seen in code:** Mobile CSS sets `margin: 0 var(--space-4)` on the card and `display: block; width: 100%` on the CTA link.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Tier gate analytics attributes are present for event tracking

**Source:** web/templates/components/tier_gate_overlay.html
**User:** admin (QA)
**Starting state:** Tier gate overlay is rendered on a gated page.
**Goal:** Analytics team can track tier gate impressions and CTA clicks.
**Expected outcome:** The overlay div has `data-track="tier-gate-impression"`, `data-tier-required`, and `data-tier-current` attributes. The CTA link has `data-track="tier-gate-click"`. These allow the activity tracking script to capture conversion funnel events.
**Edge cases seen in code:** Both the impression event (overlay render) and the click event (CTA) are independently trackable.
**CC confidence:** medium
**Status:** PENDING REVIEW
## SUGGESTED SCENARIO: New user skips onboarding from step 1

**Source:** onboarding_step1.html, web/routes_auth.py onboarding_skip route
**User:** homeowner
**Starting state:** User has just verified their email and landed on onboarding step 1
**Goal:** Skip the entire setup and go straight to the dashboard
**Expected outcome:** User is redirected to the dashboard immediately; flash message "Welcome to sfpermits.ai!" is displayed; no role is saved; user can still use the app normally
**Edge cases seen in code:** onboarding_dismissed flag is set in session; show_onboarding_banner is cleared; onboarding_complete is NOT persisted to DB (skip does not mark complete)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: New user selects role on step 1 and advances

**Source:** onboarding_step1.html, web/routes_auth.py onboarding_step1_save
**User:** expediter
**Starting state:** User is on step 1 of onboarding; no role has been saved yet
**Goal:** Select "Expediter" role and continue to step 2
**Expected outcome:** Role is persisted to the users table; user's session g.user reflects the new role; user is redirected to step 2 with progress indicator showing step 1 as "done" (green dot)
**Edge cases seen in code:** Submitting with no role selected returns an error message; role must be one of homeowner/architect/expediter/contractor
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: New user enters custom address on step 2

**Source:** onboarding_step2.html, web/routes_auth.py onboarding_step2_save
**User:** homeowner
**Starting state:** User is on step 2 with an address input field visible
**Goal:** Type their own address (e.g., "487 Noe St") into the input and add it to their portfolio
**Expected outcome:** The address is saved as a watch item; user advances to step 3; demo property (1455 Market St) was NOT automatically added
**Edge cases seen in code:** address field is accepted as-is; no validation or geocoding happens on the form submission itself
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: New user uses demo property on step 2

**Source:** onboarding_step2.html, web/routes_auth.py onboarding_step2_save (action=skip)
**User:** architect
**Starting state:** User is on step 2; they don't have a specific SF property to watch yet
**Goal:** Use the demo property (1455 Market St) to proceed through onboarding
**Expected outcome:** 1455 Market St is added to their portfolio as a watch item (label "Demo — 1455 Market St"); user advances to step 3; add_watch failure is non-fatal (may already exist)
**Edge cases seen in code:** Non-fatal exception handling if watch already exists
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: New user completes onboarding on step 3

**Source:** onboarding_step3.html, web/routes_auth.py onboarding_complete
**User:** homeowner
**Starting state:** User is on step 3 (final step); they have watched at least one property
**Goal:** Click "Go to Dashboard →" to complete onboarding
**Expected outcome:** onboarding_complete flag is set to TRUE in the users table; session onboarding_dismissed = True; flash message "Welcome to sfpermits.ai!" appears on dashboard; user will not be shown the onboarding wizard again on future logins
**Edge cases seen in code:** DB update failure is logged but non-fatal; user still gets redirected to dashboard
**CC confidence:** high
**Status:** PENDING REVIEW
# Scenarios — T2 Sprint 91 (Search Template Migration)

## SUGGESTED SCENARIO: public search results page loads for unauthenticated user

**Source:** search_results_public.html migration
**User:** homeowner
**Starting state:** User is not logged in and searches for an SF address
**Goal:** See permit history for a specific address without signing up
**Expected outcome:** A page with permit data renders, showing a search box pre-filled with the query, results or a "no results" state, and a CTA to sign up for more detail
**Edge cases seen in code:** No-results state shows guidance card with example searches; violation context mode shows enforcement data first
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: public search results handles non-existent address gracefully

**Source:** search_results_public.html — no_results branch
**User:** homeowner
**Starting state:** User searches for an address with no permit history
**Goal:** Find out if permits exist for their address
**Expected outcome:** A "No permits found" message is shown with guidance on how to search (by address, permit number, or block/lot), plus a "Sign up free" CTA
**Edge cases seen in code:** empty_guidance.suggestions may offer "Did you mean?" alternatives; empty_guidance.show_demo_link shows demo link
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: mobile intel toggle works on narrow viewports

**Source:** search_results_public.html — mobile-intel-toggle component
**User:** homeowner
**Starting state:** User on mobile (< 900px) views search results for an address with block/lot data
**Goal:** Access property intelligence panel on mobile
**Expected outcome:** A "Property intelligence" toggle button appears below the results; tapping it expands to show the intel panel with routing/entity data
**Edge cases seen in code:** Desktop shows sticky sidebar; mobile shows collapsible panel
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: enforcement violations shown with visual alert state

**Source:** search_results.html — intel-col--alert CSS class
**User:** expediter
**Starting state:** Searching an address that has open violations or complaints
**Goal:** Quickly identify enforcement risk on a property
**Expected outcome:** The enforcement column in the intel panel shows a visually distinct alert background (red-tinted border/background) and displays the count of open violations
**Edge cases seen in code:** `intel-col--alert` class applied when `enforcement_total > 0`; shows violation+complaint breakdown
**CC confidence:** high
**Status:** PENDING REVIEW
# Sprint 91 T2 — Suggested Scenarios

## SUGGESTED SCENARIO: Property report loads with Obsidian design system
**Source:** web/templates/report.html migration
**User:** homeowner | expediter
**Starting state:** User navigates to a property report URL (e.g. /report/3512/035)
**Goal:** View the full property permit history, risk assessment, and intel grid
**Expected outcome:** Page renders with consistent dark Obsidian theme, correct font hierarchy (--mono for data values like permit numbers, --sans for prose/labels), status dots in correct signal colors, no visual artifacts from CSS variable conflicts
**Edge cases seen in code:** Empty permits array renders "No permits found" empty state; error state renders with back-to-search CTA; is_owner mode shows owner banner with tailored recommendations
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Station predictor returns routing forecast
**Source:** web/templates/tools/station_predictor.html
**User:** expediter | homeowner
**Starting state:** User is logged in and navigates to the station predictor tool
**Goal:** Enter a permit number and see the predicted next review stations
**Expected outcome:** Input accepts a permit number, prediction loads asynchronously, results render as formatted markdown with station names and timing estimates, error message shown if permit not found
**Edge cases seen in code:** 401 response shows auth prompt with login link; empty permit number input triggers client-side validation; spinner shown during async fetch
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Stuck permit analyzer diagnoses delays
**Source:** web/templates/tools/stuck_permit.html
**User:** expediter | homeowner
**Starting state:** User is logged in and navigates to the stuck permit analyzer
**Goal:** Diagnose why a permit is stalled and get an intervention playbook
**Expected outcome:** Input accepts a permit number, analysis loads with loading indicator, result shows permit number with amber status dot, playbook content renders with ranked intervention steps in markdown
**Edge cases seen in code:** 401 response renders auth prompt; fetch error renders error message; Enter key triggers diagnosis; loading indicator uses pulse-dot animation with signal-amber color
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Property report risk assessment section
**Source:** web/templates/report.html — risk-item, severity-chip components
**User:** homeowner | expediter
**Starting state:** User views a property report for a property with active risk factors
**Goal:** Understand what risks are flagged for this property
**Expected outcome:** Risk items shown with severity chips (high/moderate/low/clear), high-severity items appear in "Needs attention" action items at top of page, KB citations shown as linked chips, cross-reference links work
**Edge cases seen in code:** "No known risks" clears state shown with severity-chip--clear; risk-item--none variant for zero-risk properties
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Property report owner mode
**Source:** web/templates/report.html — owner-banner, remediation-roadmap, consultant-callout
**User:** homeowner
**Starting state:** User visits /report with ?owner=1 parameter while logged in
**Goal:** See property recommendations tailored for the owner (remediation roadmap, consultant signal)
**Expected outcome:** Owner banner displayed, remediation roadmap section visible with effort options and source citations, consultant callout reflects risk level (warm/recommended/strongly_recommended/essential)
**Edge cases seen in code:** is_owner flag toggles "This is my property" nav CTA; consultant signal can be 'cold' (hidden) or progressive urgency levels
**CC confidence:** medium
**Status:** PENDING REVIEW
# Sprint 91 T2 — Suggested Scenarios

## SUGGESTED SCENARIO: consultant search renders on first page load
**Source:** web/templates/consultants.html migration
**User:** homeowner | expediter | architect
**Starting state:** User navigates to /consultants without any prefill query parameters
**Goal:** User wants to find a consultant for their SF permit project
**Expected outcome:** Page loads successfully with a search form (street name, block, lot, neighborhood, permit type fields), two checkboxes, and a "Find Consultants" button. No results shown on initial load.
**Edge cases seen in code:** prefill context banner only shown when prefill.signal is truthy — should be absent on direct navigation
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: consultant search prefill from property report
**Source:** web/templates/consultants.html — prefill context banner
**User:** homeowner | expediter
**Starting state:** User navigates to /consultants with block/lot/address query parameters (from property report link)
**Goal:** User wants to find consultants familiar with their specific property
**Expected outcome:** Page loads with form pre-filled with block, lot, address values. Context banner appears showing "Searching for consultants matching your property at Block X, Lot Y". Form auto-submits within 300ms and shows ranked results.
**Edge cases seen in code:** neighborhood pre-fill only shown in banner if prefill.neighborhood is set
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: consultant results sorted by user preference
**Source:** web/templates/consultants.html — sort-chip controls
**User:** expediter | architect
**Starting state:** User has performed a consultant search and results are showing
**Goal:** User wants to find the consultant with the most recent permit activity
**Expected outcome:** Sort chips (Best Match, Most Permits, Most Recent, Largest Network) appear above results. Clicking "Most Recent" re-submits the form with sort_by=recency and re-renders results ordered by recency. Active chip visually differs from inactive ones.
**Edge cases seen in code:** sort_by hidden input defaults to 'score' if undefined
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: login page accessible without account
**Source:** web/templates/auth_login.html
**User:** homeowner (new)
**Starting state:** User has no account and navigates to the login page
**Goal:** User wants to sign in or create an account via magic link
**Expected outcome:** Login form shows email input, optional invite code field (when invite_required), and "Send magic link" button. Page explains no password needed. Footer links to About and Methodology.
**Edge cases seen in code:** invite_code field hidden unless invite_required flag is true
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: beta request form submission with honeypot
**Source:** web/templates/beta_request.html — honeypot field
**User:** homeowner (prospective)
**Starting state:** User navigates to the beta request page
**Goal:** User wants to request access to sfpermits.ai
**Expected outcome:** Form shows email, name, and reason fields. Hidden honeypot field (website) is invisible to real users. On submission with the website field filled, bot protection triggers silently. On legitimate submission, confirmation shown.
**Edge cases seen in code:** Already-signed-in users see prefill_email populated; submitted state hides the form
**CC confidence:** medium
**Status:** PENDING REVIEW
# Sprint 91 T2 — Scenarios (Design Token Migration)

## SUGGESTED SCENARIO: Methodology page navigation consistency
**Source:** web/templates/methodology.html migration
**User:** homeowner | architect | expediter
**Starting state:** User has arrived at the Methodology page from a link or direct URL
**Goal:** User wants to navigate to other parts of the site from the Methodology page
**Expected outcome:** Full site navigation (Search, Brief, Portfolio, sign-in) is available via the standard nav bar, consistent with all other pages
**Edge cases seen in code:** Pre-migration, the page had a custom minimal nav — migrated to fragments/nav.html which respects auth state (shows account link for logged-in users)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Demo page shows live data with standard navigation
**Source:** web/templates/demo.html migration
**User:** homeowner (unauthenticated prospect)
**Starting state:** User visits /demo directly or via a shared link
**Goal:** User views live permit intelligence for the demo address and can navigate to sign up
**Expected outcome:** Page renders with standard nav bar, shows permit history, routing, timeline estimate, entity network, and a CTA to sign up. Navigation to rest of site works normally.
**Edge cases seen in code:** demo.html uses density_max template var for compact view — styles must work in both density modes; the page is noindex so should not appear in search results
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: What-If Simulator form — empty state and demo load
**Source:** web/templates/tools/what_if.html
**User:** expediter | architect
**Starting state:** User navigates to /tools/what-if with no prior data
**Goal:** User sees the empty state prompt, clicks the demo link, and the form auto-fills with demo data and runs a comparison
**Expected outcome:** Empty state shows "Compare two project scopes" message. Demo link (?demo=kitchen-vs-full) auto-populates Project A and B fields and triggers comparison after 400ms delay. Result shows comparison table and strategy callout.
**Edge cases seen in code:** Demo auto-submit fires after setTimeout(400ms) — form must be rendered and ready before auto-submit fires
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Cost of Delay Calculator — validation error then success
**Source:** web/templates/tools/cost_of_delay.html
**User:** homeowner | developer
**Starting state:** User visits /tools/cost-of-delay
**Goal:** User tries to submit with no monthly cost, sees validation error, corrects it, and gets results
**Expected outcome:** Submit with empty monthly cost shows inline validation error on that field. After entering a valid cost (e.g. 15000) and permit type (restaurant), the error clears and calculation proceeds. Results show expected cost card, bottleneck warning if applicable, and percentile table.
**Edge cases seen in code:** input-error class applied to field on validation fail; inline-error shown with .visible toggle; monthly cost must be > 0 (not just non-empty)
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Design-system migrated pages — mobile viewport renders cleanly
**Source:** methodology.html, demo.html migration
**User:** homeowner (mobile)
**Starting state:** User accesses methodology or demo page on 375px viewport
**Goal:** Content is fully readable, no horizontal overflow, tables scroll horizontally where needed
**Expected outcome:** No horizontal scroll on the page body. Tables are wrapped in overflow-x:auto containers. The flowchart (entity resolution steps) is hidden on mobile and replaced with a numbered list. Navigation collapses to hamburger.
**Edge cases seen in code:** methodology flowchart uses display:none on mobile, flow-list becomes visible; data-table has overflow-x:auto on mobile
**CC confidence:** high
**Status:** PENDING REVIEW


<!-- Agent 3C — QS12 Sprint 96 — 2026-02-28 -->

## SUGGESTED SCENARIO: Question query routes to AI consultation not permit search
**Source:** Agent 3C — search routing + intent_router.py
**User:** homeowner
**Starting state:** User is on the public landing page, unauthenticated
**Goal:** Ask "Do I need a permit for a kitchen remodel?" in the search box
**Expected outcome:** Instead of "No permits found", user sees guidance that this is an AI-answerable question, with a prompt to sign up for AI consultation, not a failed literal permit lookup
**Edge cases seen in code:** Queries with construction context (kitchen, bathroom, ADU, garage, deck) + question prefix are classified as `question` intent; validate_plans and address patterns still take priority
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Validate query beats question intent
**Source:** Agent 3C — intent_router.py priority ordering
**User:** architect | expediter
**Starting state:** User types "how do I validate plans?" in search
**Goal:** Access the plan validation feature
**Expected outcome:** Query routes to validate_plans intent, not question/AI consultation — the validate keyword wins over question prefix detection
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Beta user property click goes to full search not loop
**Source:** Agent 3C — landing.html state machine
**User:** homeowner (beta tester, authenticated)
**Starting state:** User is on the landing page in beta state with a watched property shown
**Goal:** Click a watched property link (e.g., "487 Noe — PPC stalled 12d")
**Expected outcome:** User goes directly to the full search results page for that property, not back to the landing page via /search redirect loop
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Beta badge shows correct label for beta users
**Source:** Agent 3C — landing.html UX fixes
**User:** homeowner (beta tester)
**Starting state:** User is on landing page in beta state (via admin toggle)
**Goal:** See their account context clearly labeled
**Expected outcome:** Badge next to wordmark reads "Beta Tester" (not "beta"), giving a polished look for beta program participants
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Scroll-cue arrow is clearly visible after page load
**Source:** Agent 3C — landing.html UX fixes
**User:** homeowner (new visitor)
**Starting state:** User arrives on landing page, hero section is visible
**Goal:** Notice the call-to-action scroll arrow to see the showcase
**Expected outcome:** After 3.6s, the scroll cue arrow fades in and is visible at 60% opacity — noticeable without dominating the hero section
**CC confidence:** low
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: honeypot waitlist capture in HONEYPOT_MODE
**Source:** web/app.py _honeypot_redirect + web/routes_misc.py join_beta
**User:** homeowner
**Starting state:** HONEYPOT_MODE=1 is set on the server; user navigates to /search or any non-exempt URL
**Goal:** User wants to use the app but the site is in pre-launch honeypot mode
**Expected outcome:** User is redirected to /join-beta capture page; they submit their email and receive a confirmation page showing queue position
**Edge cases seen in code:** Bots filling the hidden 'website' field get silently dropped (200, no DB write); IP rate-limited at 3 req/hr
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: join-beta waitlist form submission
**Source:** web/routes_misc.py join_beta_post
**User:** homeowner
**Starting state:** User is on /join-beta; has not previously signed up
**Goal:** User wants to join the waitlist for early access
**Expected outcome:** User fills email + optional name/role/address; submits; redirected to /join-beta/thanks showing their queue position
**Edge cases seen in code:** Duplicate email silently updates existing record (ON CONFLICT DO UPDATE); admin notification email sent if ADMIN_EMAIL configured
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: out_of_scope intent blocks irrelevant searches
**Source:** src/tools/intent_router.py + web/routes_public.py
**User:** homeowner
**Starting state:** User is on the public search page; not authenticated
**Goal:** User mistakenly searches for a non-SF-permit topic (e.g. "weather in Oakland" or "how to get a dog license")
**Expected outcome:** Search shows a friendly "out of our coverage area" guidance message explaining sfpermits.ai specializes in SF building permits, with suggestions to try an address or permit number instead
**Edge cases seen in code:** Short queries (<2 words) and queries matching SF permit vocabulary are NOT flagged; only clear other-city or non-permit-topic queries trigger this
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: honeypot allows exempt paths through in HONEYPOT_MODE
**Source:** web/app.py _honeypot_redirect
**User:** admin
**Starting state:** HONEYPOT_MODE=1; admin navigates to /admin/ pages
**Goal:** Admin needs to access the admin dashboard during honeypot mode
**Expected outcome:** Admin pages, /health, /cron/, /static/, and /join-beta itself are not redirected; only non-exempt user-facing routes redirect to capture page
**Edge cases seen in code:** /demo/guided also exempt (used for stakeholder demos during pre-launch)
**CC confidence:** high
**Status:** PENDING REVIEW
