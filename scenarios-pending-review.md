# Scenarios Pending Review
<!-- CC appends suggested scenarios here after each feature session -->
<!-- Do not edit scenario-design-guide.md directly -->
<!-- This file is reviewed and drained each planning session -->
<!-- Drained Sprint 68-A: 102 scenarios reviewed, 48 accepted, 30 merged, 22 rejected, 2 deferred -->
<!-- See scenarios-reviewed-sprint68.md for full review log -->

_Last reviewed: Sprint 68-A (2026-02-26)_

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
