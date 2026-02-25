---
name: qa-admin
description: "Tests admin-only routes on sfpermits.ai. Requires TESTING=1 and TEST_LOGIN_SECRET. Login as test-admin@sfpermits.ai. Invoke for any sprint QA pass covering admin surfaces."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# QA Agent: Admin Routes

## Purpose
Verify that admin-only routes are accessible to admin users, function correctly, and are properly gated against non-admin access.

## When to Use
- After any sprint touching `/admin/*` routes, feedback pipeline, cost tracking, or admin tooling
- As part of RELAY QA loop before session close
- After a deploy to confirm admin surfaces haven't broken

## Prerequisites
- App running locally or on staging with `TESTING=1` env var set
- `TEST_LOGIN_SECRET` env var set and known
- Admin test user `test-admin@sfpermits.ai` must be creatable via test-login endpoint with `admin=True`

## Checks

All browser checks use Playwright headless Chromium. Login via `POST /auth/test-login`.

### Setup: Authenticate as Admin
- POST to `/auth/test-login` with `{"secret": "<TEST_LOGIN_SECRET>", "email": "test-admin@sfpermits.ai"}`
- PASS if: HTTP 200, session cookie set, user has admin flag
- FAIL if: 403, 404, or no admin flag — abort remaining checks and report setup failure

### 1. Admin Dashboard Loads
- Navigate to `/admin/dashboard` or `/admin`
- PASS if: admin dashboard renders with at least one section (user stats, system status, or activity), no 500
- FAIL if: server error, blank page, redirect to non-admin page

### 2. Admin Feedback Page Loads
- Navigate to `/admin/feedback`
- PASS if: feedback interface loads, table or list of feedback items visible (or empty-state message), no 500
- FAIL if: server error, blank page, 404

### 3. Admin Feedback — Triage Actions Available
- On `/admin/feedback`, check that action controls exist (resolve, escalate, or similar buttons)
- PASS if: at least one action control is visible or the empty-state message explains no pending items
- FAIL if: page loads but triage controls are broken or missing when items exist

### 4. Admin Costs Page Loads
- Navigate to `/admin/costs`
- PASS if: cost dashboard renders with spend data or "no data" state, no 500
- FAIL if: server error, blank page, 404

### 5. Admin Costs — Kill Switch Control Visible
- On `/admin/costs`, check for kill switch toggle or button
- PASS if: kill switch UI element present and visible
- FAIL if: kill switch element missing from page

### 6. Admin Users Page (if exists)
- Navigate to `/admin/users`
- PASS if: user list loads or 404 (route does not exist yet — mark SKIP if 404)
- FAIL if: 500 server error

### 7. Admin Regulatory Watch
- Navigate to `/admin/regulatory-watch` or equivalent
- PASS if: regulatory watch interface loads, no 500
- FAIL if: server error, blank page

### 8. Admin-Only Route Returns 403 for Non-Admin
- In a separate browser context (not logged in as admin), navigate to `/admin/dashboard`
- PASS if: access denied or redirected to login
- FAIL if: admin content visible without admin session

### 9. Cron Endpoints Require Auth
- POST to `/cron/nightly` or `/cron/morning-brief` without `Authorization` header
- PASS if: 401 or 403 returned
- FAIL if: cron job executes without auth

### 10. Admin Navigation Links Work
- On admin dashboard, click each nav link in the admin sidebar/header
- PASS if: each link navigates to a page that loads without 500
- FAIL if: any nav link produces a server error or leads to blank page

## Tools
- Playwright headless Chromium for all browser checks
- `POST /auth/test-login` for admin authentication
- curl for cron endpoint auth check (check 9)
- Screenshots saved to `qa-results/screenshots/[session-id]/admin/`

## Output Format

Write results to `qa-results/[session-id]-admin-qa.md`:

```
# Admin QA Results — [date]

Admin user: test-admin@sfpermits.ai
Base URL: [URL used]

| # | Check | Status | Notes |
|---|-------|--------|-------|
| Setup | admin test-login | PASS | |
| 1 | Admin dashboard loads | PASS | |
...

Screenshots: qa-results/screenshots/[session-id]/admin/
```

Mark each check PASS, FAIL, or SKIP (with reason for SKIP).
Any FAIL triggers a RELAY loop fix attempt (max 3 tries, then BLOCKED).

## Worktree Isolation Rule
All build agents MUST run in isolated worktrees. Never modify files outside your owned file list.
