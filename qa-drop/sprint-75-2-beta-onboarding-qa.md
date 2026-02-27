# QA Script — Sprint 75-2: Beta Approval Email + Onboarding

**Sprint:** 75-2
**Feature:** Beta approval welcome email + /welcome onboarding page
**Agent:** 75-2
**Run on:** Staging — sfpermits-ai-staging-production.up.railway.app

---

## Pre-conditions

- Staging is running Sprint 75-2 code (check `/health` response for recent deploy)
- Admin email configured in Railway env (`ADMIN_EMAIL`)
- SMTP configured (or dev-mode acceptable: check Railway logs for "Beta welcome email for...")
- TEST_LOGIN_SECRET available

---

## 1. Schema — onboarding_complete column

**Step:** Check the column exists on prod/staging DB
**How:** `curl -s https://sfpermits-ai-staging.../health | jq .`
**PASS:** Health endpoint returns 200; no migration errors in logs
**FAIL:** 500 on health; column error in Railway logs

---

## 2. /welcome — unauthenticated redirect

**Step:** GET /welcome without authentication
**How:** `curl -sI https://sfpermits-ai-staging.../welcome`
**PASS:** 302 redirect to login page
**FAIL:** 200 with onboarding content (auth bypass)

---

## 3. /welcome — authenticated user sees 3-step page

**Step:** Log in as test user, then GET /welcome
**How:** Browser: log in → navigate to /welcome
**PASS:** Page loads with 3 step cards: "Search any SF address", "Pull a property report", "Watch properties for changes"
**FAIL:** Error page, blank page, or redirect to dashboard

---

## 4. /welcome — progress dots visible

**Step:** On /welcome, verify progress dots display
**How:** Inspect page or Playwright screenshot
**PASS:** 3 dots visible with connecting lines
**FAIL:** No dots, or raw CSS tokens showing (unrendered design system)

---

## 5. /onboarding/dismiss — sets session flag

**Step:** POST /onboarding/dismiss
**How:** `curl -X POST -s https://sfpermits-ai-staging.../onboarding/dismiss` (with session cookie)
**PASS:** 200, empty body
**FAIL:** 4xx or body with error HTML

---

## 6. /onboarding/dismiss — GET returns 405

**Step:** GET /onboarding/dismiss
**How:** `curl -sI https://sfpermits-ai-staging.../onboarding/dismiss`
**PASS:** 405 Method Not Allowed
**FAIL:** 200 or 302

---

## 7. /onboarding/dismiss — persists onboarding_complete in DB

**Step:** After POST /onboarding/dismiss for logged-in user, verify DB flag
**How:** Check Railway logs for `UPDATE users SET onboarding_complete = TRUE` or re-check /welcome (should redirect)
**PASS:** Subsequent /welcome GET redirects to / (onboarding_complete=TRUE)
**FAIL:** /welcome still shows onboarding page

---

## 8. Beta approval welcome email (dev mode — no SMTP)

**Step:** Admin approves a beta request in dev/staging (where SMTP may not be fully configured)
**How:** Admin → /admin/beta-requests → approve a pending request
**PASS:** Railway logs contain "Beta welcome email for <email>" (dev mode log) OR email is received
**FAIL:** 500 error on approve; no log entry; plain magic link sent instead of welcome email

---

## 9. /welcome — Obsidian design compliance (Playwright visual)

**Step:** Screenshot /welcome at desktop (1280x900) and mobile (375x812)
**How:** Playwright — `page.goto('/welcome')`, `page.screenshot()`
**PASS:** Score ≥ 3/5 — dark theme, cards visible, content centered, no horizontal scroll
**FAIL:** Score < 3/5 — flush-left content, no cards, wrong theme, horizontal scroll

---

## 10. Email template renders correctly

**Step:** Verify `web/templates/emails/beta_approved.html` is valid HTML with correct brand colors
**How:** Open file in browser or trigger approval to get email
**PASS:** Dark background (#0B0F19), cyan CTA button, 3-step list visible
**FAIL:** Missing styles, broken layout, white background

---

## Notes

- The `send_magic_link` fallback triggers if `send_beta_welcome_email` returns False — this is expected behavior and not a failure
- `onboarding_complete` column is added idempotently (IF NOT EXISTS in Postgres, ALTER TABLE with try/except in DuckDB)
- `/welcome` guard redirects to `url_for("index")` which is the authenticated dashboard

QA READY: qa-drop/sprint-75-2-beta-onboarding-qa.md | 2 scenarios appended to scenarios-pending-review.md
