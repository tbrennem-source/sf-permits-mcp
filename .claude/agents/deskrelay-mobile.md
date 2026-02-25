---
name: deskrelay-mobile
description: "DeskCC mobile visual verification for sfpermits.ai. Takes real device-size screenshots at common breakpoints, checks touch targets, readability, and scrolling behavior. Invoke as Stage 2 of the Black Box Protocol for mobile visual QA."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# DeskRelay Agent: Mobile Visual Verification

## Purpose
Perform visual verification of mobile and tablet rendering at common device breakpoints. Where the termCC qa-mobile agent checks for overflow programmatically, this agent visually assesses usability — are touch targets large enough, is text readable at phone size, does scrolling work naturally?

## When to Use
- Invoked by DeskCC after termCC Stage 1 CHECKCHAT that includes a DeskRelay HANDOFF section with mobile visual items
- After any sprint that modifies CSS, templates, or layout
- When qa-mobile agent reported FAILs or flagged items for visual review

## Breakpoints

| Label | Width | Height | Device Equivalent |
|-------|-------|--------|-------------------|
| phone-small | 375 | 667 | iPhone SE |
| phone-large | 390 | 844 | iPhone 14 |
| tablet-portrait | 768 | 1024 | iPad portrait |
| tablet-landscape | 1024 | 768 | iPad landscape |

## Checks

For each check: screenshot at the specified breakpoint, assess visually, record PASS/FAIL.

### M1. Landing Page — Phone Small (375px)
- Load `/` at 375x667
- Screenshot: full page
- PASS if: headline readable (font size at least 18px visually), CTA button large enough to tap (at least 44px height visually), no horizontal scroll needed
- FAIL if: text too small to read, buttons tiny, horizontal scroll visible

### M2. Landing Page — Phone Large (390px)
- Load `/` at 390x844
- Screenshot: above-the-fold only
- PASS if: same criteria as M1, layout uses the additional width appropriately
- FAIL if: content identical to 375px with no responsive adjustment (unused whitespace or layout issues)

### M3. Search Results — Phone
- Submit a search and view results at 375px
- Screenshot: results list
- PASS if: result cards stack vertically, each card shows address and status with readable text (visually 14px+), tappable area for each card is adequate
- FAIL if: cards too narrow to read, text too small, cards horizontally overflowing

### M4. Morning Brief — Phone
- Load `/brief` as authenticated user at 375px
- Screenshot: first visible section
- PASS if: section headers readable, data items stack vertically and don't overflow, text doesn't require zooming
- FAIL if: brief data overflows phone width, columns collapse in a way that hides data, text too small

### M5. Navigation — Phone Hamburger/Mobile Menu
- At 375px on any page, test mobile navigation
- Screenshot: navigation closed, then navigation open
- PASS if: hamburger/menu icon clearly visible and large enough to tap (44px+), menu opens correctly, menu items readable and tappable
- FAIL if: no mobile navigation visible, menu icon too small to tap, menu doesn't open or is partially off-screen

### M6. Forms — Phone Usability
- On search form or any input form at 375px
- Screenshot: form with keyboard-focused input (or simulate by clicking input)
- PASS if: input fields visibly large enough to type in (at least 44px height), labels are above inputs (not side-by-side on phone), submit button full-width or clearly tappable
- FAIL if: side-by-side label+input on phone causing cramping, submit button too small, inputs too small to tap

### M7. Admin Dashboard — Tablet Portrait (768px)
- Load `/admin/dashboard` as admin at 768x1024
- Screenshot: full visible dashboard
- PASS if: admin data cards readable at tablet size, no horizontal overflow, key metrics visible without scrolling excessively
- FAIL if: dashboard designed only for desktop (fixed 1280px layout doesn't adapt to 768px), data hidden or overflowing

### M8. Plan Analysis Upload — Tablet Portrait
- Load `/analyze-plans` at 768x1024
- Screenshot: upload interface
- PASS if: upload zone and controls clearly visible at tablet size, drag-and-drop area adequate size
- FAIL if: upload zone too small on tablet, controls cut off or not reachable

### M9. Tablet Landscape (1024px) — Not Phone Layout
- Load `/` at 1024x768
- Screenshot: above the fold
- PASS if: layout uses appropriate tablet-landscape treatment (wider columns, not phone stacking), content fills width reasonably
- FAIL if: phone-stacking layout at 1024px (underusing available width by more than 40%)

### M10. Scrolling — No Fixed Overlay Blocking Content
- At 375px, scroll down 300px on landing page and 300px on brief page
- PASS if: no fixed overlay or sticky element blocks reading content during scroll (some fixed headers are acceptable if they don't cover more than 80px)
- FAIL if: fixed overlay covers more than 20% of the viewport during normal reading scroll

## Screenshot Requirements

Save screenshots in organized subdirectories:
- `qa-results/screenshots/[session-id]/deskrelay-mobile/phone/`
- `qa-results/screenshots/[session-id]/deskrelay-mobile/tablet/`

Name files descriptively: `phone-landing-375.png`, `tablet-admin-768.png`, etc.

## Touch Target Guidelines (for visual assessment)

A touch target is adequate if it appears to be at least 44x44px visually. In practice:
- Buttons should span most of the available width on phone (or be clearly large enough to tap with a thumb)
- Links in nav should have visible padding around the text
- Form inputs should have visible height (not hairline thin)

## Output Format

Write results to `qa-results/[session-id]-deskrelay-mobile-qa.md`:

```
# DeskRelay Mobile QA Results — [date]

| # | Breakpoint | Check | Status | Notes |
|---|------------|-------|--------|-------|
| M1 | 375px | Landing page phone | PASS | Text readable, CTA large |
| M2 | 390px | Landing page large phone | PASS | |
| M5 | 375px | Mobile navigation | FAIL | Hamburger icon 28x28px, too small |
...

Screenshots: qa-results/screenshots/[session-id]/deskrelay-mobile/
```

Mark each check PASS, FAIL, or SKIP (with reason for SKIP).
FAIL items should describe what was visually observed.

## Worktree Isolation Rule
All build agents MUST run in isolated worktrees. Never modify files outside your owned file list.
