# Scenarios Pending Review
<!-- CC appends suggested scenarios here after each feature session -->
<!-- Do not edit scenario-design-guide.md directly -->
<!-- This file is reviewed and drained each planning session -->
<!-- Drained Sprint 68-A: 102 scenarios reviewed, 48 accepted, 30 merged, 22 rejected, 2 deferred -->
<!-- See scenarios-reviewed-sprint68.md for full review log -->

_Last reviewed: Sprint 68-A (2026-02-26)_

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
