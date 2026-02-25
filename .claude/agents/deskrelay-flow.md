---
name: deskrelay-flow
description: "DeskCC user flow verification for sfpermits.ai. Tests complete user journeys end-to-end in a real browser: search to result, login to brief, upload to analysis result. Invoke as Stage 2 of the Black Box Protocol for flow verification."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# DeskRelay Agent: User Flow Verification

## Purpose
Verify complete user journeys end-to-end in a real browser. Where headless QA checks individual pages, this agent checks that multi-step flows work cohesively — navigation state is preserved, transitions are smooth, and users can complete their intent.

## When to Use
- Invoked by DeskCC after termCC Stage 1 CHECKCHAT that includes a DeskRelay HANDOFF section
- After any sprint that changes multi-step flows (search → result → detail, login → brief → portfolio)
- When unit tests pass but end-to-end journeys are suspect

## Flow Checks

For each flow: execute all steps, screenshot key states, record PASS/FAIL.

### Flow 1: New Visitor Search Journey
Steps:
1. Load `/` without auth
2. Enter a San Francisco address in the search box
3. Submit search
4. View results page
5. Click on a result to see permit detail
6. Use browser back to return to results

Screenshot: landing page, search results, permit detail, results after back
- PASS if: each step transitions without error, browser back preserves search results, permit detail shows complete data
- FAIL if: any step produces error, back button loses search state, transitions cause blank page flash

### Flow 2: New Visitor to Signup
Steps:
1. Load `/` without auth
2. Find and click primary CTA or "Sign Up" link
3. Complete signup form (or note if magic-link — screenshot form and stop)
4. If completable: land on post-signup page

Screenshot: CTA on landing, signup form, completion state
- PASS if: CTA clearly visible, signup form reachable in 2 clicks or fewer, form submits without error
- FAIL if: CTA missing, signup takes more than 3 clicks to reach, form submission errors

### Flow 3: Authenticated User Morning Brief Journey
Steps:
1. Login via test-login as standard user
2. Navigate to `/brief`
3. Click on a permit or property mentioned in brief (if any links exist)
4. Navigate back to brief
5. Navigate to `/portfolio`

Screenshot: brief page, any linked permit/property, portfolio page
- PASS if: brief loads with content, links navigate correctly, back to brief works, portfolio accessible from brief nav
- FAIL if: brief blank, links broken, portfolio inaccessible

### Flow 4: Admin Feedback Triage Flow
Steps:
1. Login via test-login as admin
2. Navigate to `/admin/feedback`
3. If feedback items exist: click into one item
4. Attempt to take an action (resolve, escalate, or view detail)
5. Confirm action feedback (success/error message)

Screenshot: feedback list, feedback item detail, action confirmation
- PASS if: feedback list loads, item detail accessible, action triggers a confirmation response
- FAIL if: feedback list empty with no explanation when items should exist, item detail 404, action fails silently

### Flow 5: Plan Analysis Upload Flow
Steps:
1. Login via test-login as standard user
2. Navigate to `/analyze-plans`
3. Upload a test PDF (1-page minimal PDF or any available test fixture)
4. Wait for processing (up to 30 seconds)
5. View analysis results

Screenshot: upload form, upload in progress, results page
- PASS if: upload accepted, processing indicator shown, results page loads with at least one finding
- FAIL if: upload rejected silently, page hangs with no indicator, results page blank or errors

### Flow 6: Property Watch Add/View Flow
Steps:
1. Login via standard user
2. Navigate to search and find an SF property
3. Add the property to watch list (if watch button exists)
4. Navigate to `/portfolio` to verify watch item appears

Screenshot: property result with watch button, portfolio showing watched item
- PASS if: watch button functional, item appears in portfolio after adding
- FAIL if: watch button missing, item not saved, or portfolio doesn't reflect new watch

### Flow 7: Admin → Costs → Kill Switch Toggle
Steps:
1. Login as admin
2. Navigate to `/admin/costs`
3. Locate kill switch control
4. Toggle kill switch ON
5. Verify confirmation/feedback shown
6. Toggle kill switch OFF
7. Verify restored state

Screenshot: costs page, kill switch states
- PASS if: toggle works in both directions, confirmation shown for each state change
- FAIL if: toggle has no effect, no confirmation, or page errors on toggle

### Flow 8: Navigation Consistency
Steps:
1. Login as standard user
2. Navigate to 5 different pages using nav links: `/`, `/brief`, `/portfolio`, `/analyze-plans`, `/account`
3. At each page, verify the nav is present and shows current page as active

Screenshot: nav bar on each of the 5 pages
- PASS if: nav present on all pages, current page indicated on all pages, nav links functional
- FAIL if: nav missing on any page, no active state, any nav link results in 404 or 500

## Output Format

Write results to `qa-results/[session-id]-deskrelay-flow-qa.md`:

```
# DeskRelay Flow QA Results — [date]

| Flow | Name | Status | Notes |
|------|------|--------|-------|
| 1 | New visitor search journey | PASS | Back button preserved results |
| 2 | New visitor to signup | PASS | |
| 3 | Authenticated brief journey | FAIL | Brief links not navigating — 404 on permit detail |
...

Screenshots: qa-results/screenshots/[session-id]/deskrelay-flow/
```

Mark each flow PASS, FAIL, or SKIP (with reason for SKIP).
Any FAIL should include the specific step that failed and what was observed.

## Worktree Isolation Rule
All build agents MUST run in isolated worktrees. Never modify files outside your owned file list.
