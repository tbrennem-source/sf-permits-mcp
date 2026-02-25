---
name: qa-public
description: "Tests all unauthenticated public-facing routes on sfpermits.ai. Invoke for any sprint QA pass covering public access."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# QA Agent: Public Routes

## Purpose
Verify that all unauthenticated routes load correctly, return expected content, and handle edge cases without errors.

## When to Use
- After any sprint that touches public-facing routes (`/`, `/search`, `/health`, `/report/*`)
- As part of RELAY QA loop before session close
- After a deploy to confirm no regressions on public surfaces

## Checks

All browser checks use Playwright headless Chromium. API checks use curl or Python requests.

### 1. Health Endpoint
- Navigate to `/health`
- PASS if: HTTP 200, response body is valid JSON with at least `{"status": "ok"}` or equivalent
- FAIL if: non-200 status, malformed JSON, or missing `status` key

### 2. Landing Page Loads
- Navigate to `/`
- PASS if: page title contains "SF Permits" or "sfpermits", at least one visible CTA button present, no 500 error banner
- FAIL if: blank page, server error, missing content above the fold

### 3. Search Form Present
- On `/` or `/search`, locate search input
- PASS if: input field is visible and accepts text input
- FAIL if: input missing, disabled, or not interactable

### 4. Search Results — Valid Address
- Submit search for "123 Main St San Francisco"
- PASS if: results page loads, at least one permit result or "no results" message displayed, no traceback or 500
- FAIL if: server error, blank page, unhandled exception rendered

### 5. Search Results — Empty Query
- Submit search with blank input or whitespace only
- PASS if: graceful error message shown (e.g., "Please enter an address"), no 500
- FAIL if: traceback rendered, server crash, blank page

### 6. Search Results — Special Characters
- Submit search for `<script>alert(1)</script>`
- PASS if: input is escaped in response HTML, no alert executes, no server error
- FAIL if: XSS reflected unescaped, 500 error

### 7. Public Report Page
- Navigate to a known permit report URL (e.g., `/report/1234567890` or first result from search)
- PASS if: page loads with permit details, no auth redirect, no 500
- FAIL if: redirected to login when not required, server error, blank page

### 8. Unauthenticated Access to Protected Routes
- Navigate to `/brief` without logging in
- PASS if: redirected to login page or `/` with appropriate message
- FAIL if: brief content shown without auth, server error

### 9. Static Assets Load
- On landing page, check that CSS and JS assets return 200
- PASS if: page has no broken asset console errors (check via `page.on("console", ...)`)
- FAIL if: 404s on critical CSS/JS files that break layout

### 10. /health Database Connectivity
- Parse `/health` JSON response
- PASS if: DB connection status is reported (field exists and is truthy, e.g., `"db": "ok"`)
- FAIL if: DB field missing or reports error/unreachable

## Tools
- Playwright headless Chromium for all browser checks (checks 2-9)
- curl or Python requests for check 1 and 10
- Screenshots saved to `qa-results/screenshots/[session-id]/public/`

## Output Format

Write results to `qa-results/[session-id]-public-qa.md`:

```
# Public QA Results — [date]

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Health endpoint | PASS | |
| 2 | Landing page loads | PASS | |
...

Screenshots: qa-results/screenshots/[session-id]/public/
```

Mark each check PASS, FAIL, or SKIP (with reason for SKIP).
Any FAIL triggers a RELAY loop fix attempt (max 3 tries, then BLOCKED).

## Worktree Isolation Rule
All build agents MUST run in isolated worktrees. Never modify files outside your owned file list.
