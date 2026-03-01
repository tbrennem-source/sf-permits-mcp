# QS14 QA Script

**Session:** QS14 — Intelligence surfaces, landing showcase, branded 404, persona UX fixes
**Written by:** T4-D
**Date:** 2026-03-01

---

## Setup

No credentials needed for public page checks. For auth-gated checks, ensure TESTING=1 is set or use a valid test session.

---

## 1. Landing Page

- [ ] Landing page loads at `/` without JS console errors
  - **PASS:** Page loads, no errors in browser console
  - **FAIL:** JS errors appear, page blank, or 500 response

- [ ] Hero section contains a search form
  - **PASS:** Search input visible and accepts text input
  - **FAIL:** Search input missing or non-functional

- [ ] Showcase section renders with real data (not blank, not placeholder JSON)
  - **PASS:** Permit count, timeline, or similar metric shown with a real number
  - **FAIL:** Section empty, shows "{{}}", shows "undefined", or shows "0" for all values

- [ ] Gantt/timeline visualization shows parallel stations (review stations appear side by side, not sequential only)
  - **PASS:** At least two parallel tracks visible in the timeline visualization
  - **FAIL:** All stations shown as purely sequential with no parallelism indicated

- [ ] Showcase numbers appear defensible to professionals (no "99%" approval rates or obviously inflated stats)
  - **PASS:** Numbers reflect realistic SF permit data ranges
  - **FAIL:** Numbers appear fabricated or statistically implausible

- [ ] Mobile (375px viewport): page is usable with no horizontal overflow; search bar is tappable
  - **PASS:** No horizontal scroll, search input is accessible, text is legible
  - **FAIL:** Horizontal overflow, overlapping elements, or search input too small to tap

---

## 2. Intelligence API Endpoints

- [ ] `GET /api/intelligence/stuck/[any-permit-number]` returns 200 or 404, not 500
  - **PASS:** Response is 200 with data or 404 with structured error
  - **FAIL:** 500 error or unhandled exception visible in response

- [ ] `GET /api/intelligence/delay?permit_type=alterations&monthly_cost=5000` returns 200 or 404
  - **PASS:** Structured JSON response with 200 or 404 status
  - **FAIL:** 500 error, HTML error page, or malformed JSON

- [ ] `GET /api/intelligence/similar?permit_type=alterations` returns 200 or 404
  - **PASS:** JSON response or 404; no 500
  - **FAIL:** 500 error or unhandled exception

---

## 3. Analyze Flow

- [ ] POST to analyze endpoint with a valid description returns 200
  - **PASS:** Analysis page loads or redirects to results
  - **FAIL:** 500 error, blank page, or unhandled exception

- [ ] Analyze results page shows at minimum: permit predictions and timeline estimate
  - **PASS:** At least one prediction visible and a timeline section present
  - **FAIL:** Results page blank or shows only an error message

- [ ] Results page degrades gracefully if intelligence data is unavailable
  - **PASS:** Missing intelligence sections are hidden; no unhandled errors visible to user
  - **FAIL:** Stack trace or raw exception shown in the page

---

## 4. Property Report

- [ ] Property report loads for a real SF address (e.g., "1660 Mission St San Francisco")
  - **PASS:** Report page renders with permit data or a "no permits found" message
  - **FAIL:** 500 error, blank page, or unhandled exception

- [ ] If active permits exist on the property, an intelligence section is present in the report
  - **PASS:** Intelligence section (stuck status, dwell time) visible for at least one active permit
  - **FAIL:** Section missing entirely when active permits exist

- [ ] If no permits exist for the address, report still loads without errors
  - **PASS:** Empty state message shown; no 500
  - **FAIL:** Error or blank page on empty result

---

## 5. Morning Brief (requires authenticated user)

- [ ] Brief page loads for an authenticated user
  - **PASS:** Brief page renders with sections (permit health, recent changes, etc.)
  - **FAIL:** 403 redirect loop, blank page, or 500

- [ ] If watched permits are stuck, "Stuck Permits" section appears in the brief
  - **PASS:** Section visible with permit name, station, and dwell time
  - **FAIL:** Section missing when stuck permits exist; or section throws an error

- [ ] If no permits are stuck, Stuck Permits section is hidden (not an empty card)
  - **PASS:** Section absent from page when no permits are stalled
  - **FAIL:** Empty card with no content rendered on page

- [ ] Delay Cost section appears if stuck permits with project value are found
  - **PASS:** Cost estimate shown with clear "estimate" labeling
  - **FAIL:** $0 shown, section erroring, or raw exception

---

## 6. Admin

- [ ] `GET /admin/home` requires auth + admin role; redirects non-admins
  - **PASS:** Non-authenticated request redirects to login; non-admin gets 403
  - **FAIL:** Admin page loads without auth, or 500 error

- [ ] Admin home page loads for admin user and shows basic stats
  - **PASS:** Dashboard renders with at least one stat (user count, recent activity, etc.)
  - **FAIL:** Blank page, 500, or raw DB error visible

---

## 7. Error Handling

- [ ] `GET /nonexistent-route-xyz-12345` returns 404 with branded template (not Flask default white page)
  - **PASS:** Response status is 404; page uses dark background, site wordmark, and "Page not found" message
  - **FAIL:** Flask default white error page shown; or 200 response; or 500

- [ ] 404 page has navigation back to home (logo link or explicit "Back to home" link)
  - **PASS:** At least one clickable link to `/` present on the 404 page
  - **FAIL:** No navigation links; user is stranded

- [ ] Intelligence endpoint errors degrade gracefully (no unhandled exceptions visible to user)
  - **PASS:** Any intelligence failure shows a user-friendly message or hides the section
  - **FAIL:** Stack trace or raw Python exception shown in browser

---

## 8. Auth / Login

- [ ] Login page with `invite_required=True` displays beta explanation message
  - **PASS:** Text like "SF Permits AI is currently in private beta" visible above the invite code field; includes a contact link
  - **FAIL:** Invite code field appears with no explanation; user has no context

- [ ] Login page without invite requirement does NOT show the beta message
  - **PASS:** Beta message absent when invite_required is False
  - **FAIL:** Beta message always shown regardless of invite_required flag

---

## 9. Design Token Compliance

- [ ] Run: `python scripts/design_lint.py --changed --quiet`
  - **PASS:** Score 4/5 or 5/5
  - **FAIL:** Score 3/5 or below

- [ ] No inline hex colors outside DESIGN_TOKENS.md palette in modified templates
  - **PASS:** All colors use `var(--token-name)` or are from the approved palette
  - **FAIL:** Arbitrary hex values found (e.g., `#abc123` not in token list)

- [ ] Font families use `--mono` for data/inputs/CTAs and `--sans` for prose/labels
  - Spot-check 3 elements: search input, body paragraph, CTA button
  - **PASS:** Font roles correctly assigned per DESIGN_TOKENS.md §2
  - **FAIL:** Mismatched font roles (e.g., body text in `--mono`)

- [ ] Components use token classes where applicable (`glass-card`, `ghost-cta`, `obs-table`, etc.)
  - **PASS:** New UI elements match documented token components
  - **FAIL:** Custom one-off classes used where a token component exists

- [ ] New components (if any) logged in `docs/DESIGN_COMPONENT_LOG.md`
  - **PASS:** Log updated with component name, HTML, and CSS
  - **FAIL:** New component introduced but not documented
