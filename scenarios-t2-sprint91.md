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
