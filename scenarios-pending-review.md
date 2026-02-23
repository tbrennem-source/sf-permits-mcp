# Scenarios Pending Review
<!-- CC appends suggested scenarios here after each feature session -->
<!-- Do not edit scenario-design-guide.md directly -->
<!-- This file is reviewed and drained each planning session -->

## SUGGESTED SCENARIO: Badge count matches permit table count
**Source:** Session 45 — badge-table count sync fix
**User:** expediter
**Starting state:** User searches an address with permits across multiple parcels/historical lots
**Goal:** Understand how many permits exist at a property at a glance
**Expected outcome:** The PERMITS badge total matches the count shown in the permit results table
**Edge cases seen in code:** Address-only queries return fewer permits than parcel-level merge; single-permit results don't show "Found N permits" line
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Feedback screenshot on content-heavy page
**Source:** Session 45 — feedback screenshot capture/submit
**User:** homeowner
**Starting state:** User is viewing permit results page with 10+ permits in table
**Goal:** Report a bug or suggestion with a visual screenshot of what they see
**Expected outcome:** Screenshot captures within 5MB limit, attaches to feedback form, submits successfully with screenshot icon visible in admin queue
**Edge cases seen in code:** html2canvas CDN load failure shows fallback message; JPEG quality degrades from 0.7 to 0.4 if first pass exceeds 5MB
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Exact street name matching prevents false positives
**Source:** Session 45 — exact match fix
**User:** expediter
**Starting state:** User searches "146 Lake" (LAKE ST exists, BLAKE ST also exists)
**Goal:** See permits only for LAKE ST, not substring matches like BLAKE
**Expected outcome:** Results contain only LAKE ST permits; no BLAKE, LAKE MERCED HILL, or other partial matches appear
**Edge cases seen in code:** Space-variant street names (VAN NESS vs VANNESS) should still match; "Did you mean?" suggestions appear for non-matching addresses
**CC confidence:** high
**Status:** PENDING REVIEW
