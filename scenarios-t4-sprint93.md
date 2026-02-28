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
