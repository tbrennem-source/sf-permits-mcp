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
