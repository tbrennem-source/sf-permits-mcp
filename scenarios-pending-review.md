# Scenarios Pending Review
<!-- CC appends suggested scenarios here after each feature session -->
<!-- Do not edit scenario-design-guide.md directly -->
<!-- This file is reviewed and drained each planning session -->
<!-- Drained Sprint 68-A: 102 scenarios reviewed, 48 accepted, 30 merged, 22 rejected, 2 deferred -->
<!-- See scenarios-reviewed-sprint68.md for full review log -->

_Last reviewed: Sprint 68-A (2026-02-26)_

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
