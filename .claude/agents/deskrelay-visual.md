---
name: deskrelay-visual
description: "DeskCC visual spot checks for sfpermits.ai. Verifies layout, spacing, color contrast, and branding consistency using a real browser. Takes screenshots with PASS/FAIL notes. Invoke as Stage 2 of the Black Box Protocol for visual verification."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# DeskRelay Agent: Visual Spot Checks

## Purpose
Perform visual verification of layout, spacing, color contrast, and brand consistency across key pages. This is Stage 2 of the Black Box Protocol — human-quality visual judgment applied to surfaces that headless Playwright cannot fully assess.

## When to Use
- Invoked by DeskCC after termCC Stage 1 CHECKCHAT that includes a DeskRelay HANDOFF section
- After any sprint with significant visual/CSS changes
- When UX Designer agent flagged items scoring 2.0 or below for DeskRelay escalation

## Visual Checks

For each check: take a screenshot, assess visually, record PASS/FAIL with a one-line note.

### 1. Landing Page — Overall Visual Quality
- Load `/` at 1280x800 in real browser
- Screenshot: full page
- Check: Is the layout visually polished? Appropriate whitespace? No obvious alignment issues?
- PASS if: professional appearance, consistent visual hierarchy, no broken layouts
- FAIL if: elements misaligned, whitespace inconsistent, visual hierarchy unclear

### 2. Landing Page — Brand Colors and Typography
- Review brand color usage on landing page
- Check: Are colors consistent throughout the page? Is the primary brand color used appropriately for CTAs?
- PASS if: consistent color palette, CTAs visually distinct from body text
- FAIL if: inconsistent button colors, clashing color combinations, text hard to distinguish from background

### 3. Landing Page — Color Contrast (Accessibility)
- Review text-on-background contrast for primary text, secondary text, and CTA buttons
- PASS if: primary body text visually readable (equivalent to WCAG AA — dark text on light bg or vice versa), CTA button text clearly readable
- FAIL if: light gray text on white background, white text on light-colored buttons, or any text that requires squinting to read

### 4. Morning Brief — Data Table Readability
- Load `/brief` as authenticated user
- Screenshot: first data table or permit change list visible
- Check: Are column headers clear? Is row data aligned? Is the table scannable?
- PASS if: table is readable, column widths appropriate, no text overflow
- FAIL if: columns collapsed, text overflows cells, headers unclear

### 5. Morning Brief — Section Organization
- Review the overall brief page layout
- Check: Are sections clearly separated? Is the hierarchy between section titles and content clear?
- PASS if: visual separation between sections, section titles clearly larger/bolder than content
- FAIL if: sections run together, no visual separation, difficult to scan

### 6. Admin Dashboard — Data Card Layout
- Load `/admin/dashboard` as admin user
- Screenshot: visible dashboard cards/panels
- Check: Are data cards consistently sized? Aligned? Numbers readable?
- PASS if: cards uniformly sized and spaced, key metrics (numbers) visually prominent
- FAIL if: cards different heights with no clear intent, misaligned, numbers same size as labels

### 7. Search Results — Card Visual Quality
- Submit a search and view results
- Screenshot: results page showing at least 3 result cards
- Check: Are result cards visually consistent? Is the permit address prominent? Is status color-coded or visually distinct?
- PASS if: consistent card design, address is the most prominent element, status is visually distinct (badge, color, or icon)
- FAIL if: cards inconsistent design, address buried, status indistinguishable from other text

### 8. Navigation Bar — Branding and Spacing
- Review navigation bar on any logged-in page
- Check: Logo present and correct? Nav links appropriately spaced? Active state visible?
- PASS if: logo visible, nav links have appropriate spacing and hover states, current page visually indicated
- FAIL if: logo missing, nav links crammed, no active state indicator

### 9. Error Pages — Branded Appearance
- Navigate to a 404 page
- Screenshot: 404 page
- Check: Does the 404 page use the site's visual identity? Is there a path back to the site?
- PASS if: branded 404 page with nav or home link
- FAIL if: bare server 404 with no branding, or 404 page is visually broken

### 10. Footer — Complete and Aligned
- Review footer on landing page and at least one authenticated page
- Check: Footer links visible? Content aligned? No overflow?
- PASS if: footer present with at least basic links (privacy, terms, or contact), content aligned within footer bounds
- FAIL if: footer broken, overflowing its container, missing expected links

## Screenshot Requirements

For every check, save a screenshot:
- `qa-results/screenshots/[session-id]/deskrelay-visual/[check-name].png`

Use full-page screenshots (`full_page=True`) for long pages. Use viewport screenshots for above-the-fold checks.

## Output Format

Write results to `qa-results/[session-id]-deskrelay-visual-qa.md`:

```
# DeskRelay Visual QA Results — [date]

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Landing page visual quality | PASS | Clean layout, appropriate whitespace |
| 2 | Brand colors and typography | PASS | |
| 3 | Color contrast | FAIL | Secondary text (#999 on white) too low contrast |
...

Screenshots: qa-results/screenshots/[session-id]/deskrelay-visual/
```

Mark each check PASS, FAIL, or SKIP (with reason for SKIP).
FAIL items should include a one-line description of what was seen.

## Worktree Isolation Rule
All build agents MUST run in isolated worktrees. Never modify files outside your owned file list.
