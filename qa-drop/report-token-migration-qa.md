# QA Script: Property Report Design Token Migration
**Session:** report-token-migration
**Files changed:** web/templates/report.html, web/templates/fragments/severity_badge.html, web/templates/fragments/inspection_timeline.html
**Scope:** Design token compliance, visual rendering, functional correctness

---

## 1. Design Token Lint

```bash
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/report.html web/templates/fragments/severity_badge.html web/templates/fragments/inspection_timeline.html --quiet
```

PASS: Score 5/5, 0 violations
FAIL: Any score below 5/5

---

## 2. Property Report Page Renders

Using Playwright headless Chromium:
1. Navigate to any property report URL (e.g., `/report/<block>/<lot>`)
2. Assert `h1.property-address` is visible with address text
3. Assert `.glass-card` containers are present (at least 2)
4. Assert page background is dark (obsidian theme active, not white/gray)

PASS: Page renders without errors; address headline visible; dark theme applied
FAIL: 500 error, missing sections, or white/light background visible

---

## 3. Risk Assessment Section

1. Navigate to a report with risk items
2. Assert `.risk-item` elements are visible
3. Assert `.severity-chip` exists inside `.risk-item__header`
4. Assert severity chips use correct color class (e.g., `severity-chip--high` has amber text, not a raw hex color)
5. Check "No known risks" state: `.risk-item--none` renders with green border and `.severity-chip--clear`

PASS: Risk items render with correct severity coloring; no raw hex values in computed styles
FAIL: Risk items missing; severity chips not rendering; wrong colors

---

## 4. Permit Table (obs-table)

1. Navigate to a report with permits
2. Assert `table.obs-table` is visible
3. Assert permit number cells have class `obs-table__mono` (mono font, primary color)
4. Assert status cells show `.status-chip` elements (not `.status-badge`)
5. Assert table rows hover to show glass background
6. On mobile viewport (375px): assert `.obs-table-wrap` scrolls horizontally

PASS: Table renders; obs-table__mono applied; status-chip present; mobile scroll works
FAIL: Old `data-table` class still present; status badges with inline colors; no horizontal scroll

---

## 5. Data Rows (Property Profile)

1. Navigate to a report with property_profile data
2. Assert `.data-row` elements render with label/value split
3. Assert labels use sans font (IBM Plex Sans) and values use mono font (JetBrains Mono)
4. Check last row has no bottom border (`:last-child` rule)

PASS: Rows render cleanly; correct font split; last row no border
FAIL: Old `profile-grid` layout present; incorrect font families; all rows have borders

---

## 6. Complaint / Violation Cards

1. Navigate to a report with complaints or violations
2. Assert `.cv-card` elements are visible
3. Assert `.cv-number a` links are teal (accent color)
4. Assert `.status-chip` (not `.status-badge`) is used for complaint status
5. Empty state: assert `.empty-state` italic text shows when no complaints

PASS: cv-card renders; correct status chips; empty state shown when no data
FAIL: Old `status-badge` classes; inline hex colors; missing empty state

---

## 7. Severity Badge Fragment

1. Load any page that renders `severity_badge.html` (e.g., property report with severity_tier)
2. Assert `.severity-badge` renders with correct tier class (e.g., `severity-badge--high`)
3. Assert no inline `background-color` with hardcoded hex values in the rendered HTML
4. Check that critical, high, medium, low, green tiers all produce distinct chip colors

PASS: Chip renders with token class; no raw hex in inline styles; tiers visually distinct
FAIL: Old pill pattern with `background-color: #f59e0b`; missing tier classes

---

## 8. Inspection Timeline Fragment

1. Load a permit detail panel that includes inspection_timeline.html
2. Assert `.inspection-timeline` is visible
3. Assert `.progress-track` and `.progress-fill` render a horizontal progress bar
4. Assert completed steps show "✓" checkmark in green (status-text--green)
5. Assert failed re-inspection items show `.risk-flag risk-flag--high`
6. Assert suggested next step renders with accent color

PASS: Timeline renders; progress bar visible; correct colors for step states; risk-flag for failures
FAIL: Old inline `style="background: var(--success)"` patterns; missing progress bar; entities as hex

---

## 9. Share Modal

1. Sign in as a test user and navigate to a report
2. Click "Share Report" button
3. Assert `.modal-backdrop.open` contains `.modal` with white nav background
4. Assert email input has class `form-input` and matches token styling (dark bg, glass border)
5. Close with Escape key; assert `modal-backdrop.open` class removed

PASS: Modal opens with correct token styling; closes on Escape
FAIL: Old `.modal-box` class; white background modal; non-token input styles

---

## 10. Navigation Bar

1. Navigate to any property report
2. Assert `.nav-float` is fixed at top
3. Assert `.nav-float__wordmark` has mono font, uppercase, letter-spacing
4. Assert nav background is dark semi-transparent (not solid blue/white)

PASS: Nav renders correctly; token font and color applied
FAIL: Old `.logo` class with blue accent; incorrect font

---

## DESIGN TOKEN COMPLIANCE
- [x] Run: `python scripts/design_lint.py --changed --quiet`
- [x] Score: 5/5
- [x] No inline colors outside DESIGN_TOKENS.md palette
- [x] Font families: --mono for data/badges/numbers, --sans for prose/labels
- [x] Components use token classes (glass-card, obs-table, ghost-cta, data-row, chip, status-dot, etc.)
- [x] Status dots use --dot-* not --signal-* colors
- [x] Interactive text uses --text-secondary or higher (not --text-tertiary)
- [x] New components (risk-item, severity-chip, status-chip, cv-card) logged in DESIGN_COMPONENT_LOG.md
