# QA Script — Sprint 75-3: Obsidian Template Migration

**Session:** Sprint 75-3 — Agent 3 Template Migration Batch 1
**Templates:** account.html, search_results.html, analyze_plans_complete.html, analyze_plans_results.html, analyze_plans_polling.html
**Runner:** Playwright headless Chromium

---

## Pre-flight

1. App server running on `http://localhost:5000`
   - PASS: Server responds 200 on GET /
   - FAIL: Server not running or returns 5xx

---

## 1. Account Page — Obsidian Migration

**URL:** GET /account (redirects to login if not authenticated)

1. Navigate to `/account` as anonymous user
   - PASS: Redirected to login page (3xx), not a 500 error
   - FAIL: 500 error or raw HTML with no CSS

2. Log in and navigate to `/account`
   - PASS: Page has dark (#0B0F19 or near-black) background
   - FAIL: Page has white or light grey background

3. Check page headings
   - PASS: "My Account" heading uses monospace font (JetBrains Mono)
   - FAIL: Heading uses system sans-serif

4. Check Profile card section
   - PASS: Profile card is visibly separated from background (glass-card style)
   - FAIL: Card has no visible border or background differentiation

5. Check tab bar (admin accounts only)
   - PASS: Settings/Admin tabs visible, active tab uses cyan accent color
   - FAIL: Tab bar broken or tabs invisible

---

## 2. Search Results — Quick Actions

**URL:** POST /ask with a valid SF address

1. Search for "123 Main St"
   - PASS: Results appear in dark-themed card
   - FAIL: Results appear with white/grey background

2. Verify Quick Actions section (if address found)
   - PASS: "View Property Report" button has gradient/filled button style
   - FAIL: Button is plain link with no styling

3. Verify outline buttons (Analyze Project, Who's Here)
   - PASS: Buttons have border outline style consistent with Obsidian
   - FAIL: Buttons are unstyled or have old blue filled style

---

## 3. Plan Analysis — Polling State

**URL:** GET /plan-jobs/{job_id}/status (while job processing)

1. Navigate to a plan job status page while job is running
   - PASS: Step indicator dots visible with dark background
   - FAIL: Step indicator invisible or page is white

2. Cancel button visible
   - PASS: "Cancel Analysis" button has outline button style
   - FAIL: Button missing or unstyled

---

## 4. Plan Analysis — Complete State

**URL:** HTMX fragment (replaces #job-status-poll on completion)

1. When analysis completes, completion state renders
   - PASS: Card visible with dark glass background
   - FAIL: Card blends into background or is invisible

2. "View Results" button
   - PASS: Button has filled/gradient primary style (cyan/signal-cyan)
   - FAIL: Button is plain link or unstyled

---

## 5. Plan Analysis — Results Page

**URL:** GET /plan-jobs/{job_id}/results (completed job)

1. Results page renders
   - PASS: Plan Set Analysis Report title visible with cyan accent
   - FAIL: Title invisible or wrong color

2. Bulk action toolbar buttons
   - PASS: "Download All Pages", "Print Report" etc use outline button style
   - FAIL: Buttons are unstyled or have wrong appearance

3. Email modal (click "Email Full Analysis")
   - PASS: Modal appears with dark glass background
   - PASS: Email input field has Obsidian input styling
   - FAIL: Modal is invisible or has white background

4. Watch cross-sell (if property_address set)
   - PASS: "Track changes to this property?" card visible in dark style
   - FAIL: Card is invisible or has white background

---

## Static Asset Check

1. GET /static/design-system.css returns 200
   - PASS: 200 OK
   - FAIL: 404 or 500

2. design-system.css contains `.glass-card`
   - PASS: Contains `.glass-card` definition
   - FAIL: Missing

---

## Automated Test Results

Run: `pytest tests/test_sprint_75_3.py -v`

Expected: 43/43 PASS
