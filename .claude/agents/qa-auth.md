---
name: qa-auth
description: "Tests authenticated user routes on sfpermits.ai. Requires TESTING=1 and TEST_LOGIN_SECRET env vars. Invoke for any sprint QA pass covering logged-in user flows."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# QA Agent: Authenticated User Routes

## Purpose
Verify that authenticated user routes load correctly, that auth gates work, and that non-admin users cannot access admin-only surfaces.

## When to Use
- After any sprint touching `/brief`, `/portfolio`, `/analyze-plans`, `/account`, or auth flows
- As part of RELAY QA loop before session close
- After a deploy to confirm auth gates haven't regressed

## Prerequisites
- App running locally or on staging with `TESTING=1` env var set
- `TEST_LOGIN_SECRET` env var set and known
- Test user `test-user@sfpermits.ai` (non-admin) must be creatable via test-login endpoint

## Checks

All browser checks use Playwright headless Chromium. Login via `POST /auth/test-login`.

### Setup: Authenticate
- POST to `/auth/test-login` with `{"secret": "<TEST_LOGIN_SECRET>", "email": "test-user@sfpermits.ai"}`
- PASS if: HTTP 200 and session cookie set
- FAIL if: 403, 404, or no cookie — abort remaining checks and report setup failure

### 1. Morning Brief Loads
- Navigate to `/brief`
- PASS if: page loads with brief content visible (date, at least one section header), no 500
- FAIL if: blank page, server error, redirect loop

### 2. Brief Date is Current or Recent
- Check the date displayed on `/brief`
- PASS if: date shown matches today or is within 3 days
- FAIL if: date is more than 7 days stale or missing

### 3. Portfolio Page Loads
- Navigate to `/portfolio`
- PASS if: page loads, at least one section visible (watched properties, activity, or empty-state message)
- FAIL if: server error, blank page, 404

### 4. Analyze Plans Page Loads
- Navigate to `/analyze-plans`
- PASS if: upload form or plan analysis interface is visible, no 500
- FAIL if: server error, blank page, form missing

### 5. Account Page Loads
- Navigate to `/account`
- PASS if: account details shown (email visible or profile section), no 500
- FAIL if: server error, blank page, redirect to login (indicating session not maintained)

### 6. Non-Admin Cannot Access Admin Dashboard
- Navigate to `/admin/dashboard` as non-admin user
- PASS if: redirected to login, `/`, or shown a 403/unauthorized message
- FAIL if: admin dashboard content shown to non-admin user

### 7. Non-Admin Cannot Access Admin Feedback
- Navigate to `/admin/feedback` as non-admin user
- PASS if: access denied (redirect or 403)
- FAIL if: feedback admin content shown

### 8. Non-Admin Cannot Access Admin Costs
- Navigate to `/admin/costs` as non-admin user
- PASS if: access denied (redirect or 403)
- FAIL if: cost dashboard shown to non-admin

### 9. Logout Works
- Navigate to `/logout` or click logout
- PASS if: session cleared, subsequent navigate to `/brief` redirects to login
- FAIL if: session persists after logout, or logout causes server error

### 10. Session Persistence Across Pages
- Authenticate, navigate to `/brief`, then to `/portfolio`, then to `/account`
- PASS if: all three pages load without re-auth prompt
- FAIL if: any page redirects to login mid-session

## Tools
- Playwright headless Chromium for all browser checks
- `POST /auth/test-login` for authentication (not magic link)
- Screenshots saved to `qa-results/screenshots/[session-id]/auth/`

## Output Format

Write results to `qa-results/[session-id]-auth-qa.md`:

```
# Auth QA Results — [date]

Test user: test-user@sfpermits.ai (non-admin)
Base URL: [URL used]

| # | Check | Status | Notes |
|---|-------|--------|-------|
| Setup | test-login endpoint | PASS | |
| 1 | Morning brief loads | PASS | |
...

Screenshots: qa-results/screenshots/[session-id]/auth/
```

Mark each check PASS, FAIL, or SKIP (with reason for SKIP).
Any FAIL triggers a RELAY loop fix attempt (max 3 tries, then BLOCKED).

## Worktree Isolation Rule
All build agents MUST run in isolated worktrees. Never modify files outside your owned file list.
