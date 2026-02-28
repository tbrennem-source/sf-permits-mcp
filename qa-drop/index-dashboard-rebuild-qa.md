# QA Script: index.html Dashboard Rebuild
# Sprint 75-1 follow-up — brief-first layout, no zeros, ghost CTAs
# Feature: web/templates/index.html complete rebuild

## SETUP
- App must be running: `source .venv/bin/activate && python -m web.app`
- OR use staging: https://sfpermits-ai-staging-production.up.railway.app
- For authenticated checks: use a test account (magic link or TEST_LOGIN_SECRET)

---

## 1. UNAUTHENTICATED STATE — Landing redirect

**Step:** Navigate to `/` without being logged in.

**PASS:** Returns 200 (landing page) or 302 redirect to login. No 500.
**FAIL:** 500 error or server crash.

---

## 2. AUTHENTICATED — New user (no watches)

**Step:** Log in as a fresh user with no watched properties. Navigate to `/`.

**PASS:**
- Search bar visible at top with input field and submit button
- Onboarding card visible: heading contains "Watch your first property" (or similar)
- No "0 properties watched" / "0 changes" zero-state text visible
- No "Quick Actions" section heading visible

**FAIL:** Zero-state stats visible, Quick Actions row shown, or onboarding card missing.

---

## 3. AUTHENTICATED — User with watches

**Step:** Log in as a user with ≥1 active watch item. Navigate to `/`.

**PASS:**
- Search bar visible at top
- Brief summary card visible (shows watch count, changes if any)
- Summary card does NOT show "0 properties" or "0 changes" as the primary headline
- Ghost CTAs (underline on hover) for any action links — no filled/primary buttons on the card

**FAIL:** Onboarding card shown instead of brief card, filled buttons visible, zero stats shown.

---

## 4. SEARCH FORM — Submit triggers HTMX

**Step:** Type a query in the search input and submit (click button or press Enter).

**PASS:**
- HTMX request fires (check network tab or spinner appears)
- Results load below search bar without full page reload
- Loading indicator (`#search-loading`) visible briefly during request

**FAIL:** Full page reload on search, 404/500 on search endpoint, no loading indicator.

---

## 5. PRIMARY ADDRESS QUICK-CHIP

**Step:** Log in as a user with `primary_street_number` and `primary_street_name` set on their account. Navigate to `/`.

**PASS:** A chip button appears below search input showing the primary address (e.g. "Check 614 6th Ave →"). Clicking it populates the search input and triggers search.

**FAIL:** Chip missing for users with primary address set.

**NOTE:** If user has no primary address set, chip should NOT appear — this is correct behavior.

---

## 6. RECENT SEARCHES

**Step:** Perform 2-3 searches. Reload the page.

**PASS:** Recent searches section appears below the watch card (or search card if no watches), showing the previous queries as clickable chips.

**FAIL:** Recent searches absent after performing searches. Section shows even with no searches.

---

## 7. AUTHENTICATED — Admin user

**Step:** Log in as admin. Navigate to `/`.

**PASS:**
- Admin feedback widget renders (bottom of page)
- No JS console errors
- Admin tour elements present if applicable

**FAIL:** 500 error, missing fragments, JS errors.

---

## 8. MOBILE VIEWPORT (375px wide)

**Step:** Open `/` authenticated in a 375px viewport (Chrome DevTools or Playwright).

**PASS:**
- Search bar fills full width
- Watch state card stacks vertically, no horizontal overflow
- Ghost CTAs readable at mobile size
- No horizontal scrollbar

**FAIL:** Content overflows viewport, search bar truncated, CTA text too small.

---

## 9. TEMPLATE FRAGMENTS

**Step:** View page source on the authenticated dashboard.

**PASS:**
- `fragments/nav.html` included (nav element present)
- CSP nonce (`nonce="..."`) on all `<script>` and `<style>` tags
- `admin-feedback.js` and `admin-tour.js` loaded (deferred)
- `activity-tracker.js` loaded (deferred)

**FAIL:** Missing nonce on any inline script/style, missing JS includes.

---

## 10. NO REGRESSIONS — Other dashboard sections

**Step:** Log in as an authenticated user with a plan analysis or property report. Navigate to `/`.

**PASS:**
- Property report card renders if `user_report_url` is set
- Plan upload section present (for applicable users)
- No template rendering errors (no Jinja exceptions in response)

**FAIL:** 500 error, missing sections that should appear for the user's account state.

---

## DESIGN TOKEN COMPLIANCE

- [ ] Run: `python scripts/design_lint.py --files web/templates/index.html --quiet`
- [ ] Score: 5/5
- [ ] No inline colors outside DESIGN_TOKENS.md palette
- [ ] Font families: --mono for data, --sans for prose
- [ ] Components use token classes (glass-card, ghost-cta, obsidian-input, etc.)
- [ ] Status dots use --dot-* colors
- [ ] New components logged in DESIGN_COMPONENT_LOG.md
- [ ] No filled buttons (obsidian-btn-primary) on dashboard — ghost CTAs only

---

## PYTEST

```bash
source .venv/bin/activate
python -m pytest tests/test_sprint_75_1.py -v
```

Expected: 21 passed, 1 failed (test_nav_has_obs_nav_logo — pre-existing, not introduced here).
