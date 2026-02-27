# QA Script: brief.html Token Migration + Cache Freshness UI

**Feature:** Migrate brief.html to design tokens + add cache freshness UI
**File:** `web/templates/brief.html`
**Date:** 2026-02-27

---

## DESIGN TOKEN COMPLIANCE

- [ ] Run: `python scripts/design_lint.py --files web/templates/brief.html --quiet`
- [ ] Score: 5/5 (expected — verified clean)
- [ ] No inline colors outside DESIGN_TOKENS.md palette
- [ ] Font families: `--mono` for data/timestamps/badges, `--sans` for prose/labels (spot check 3 elements)
- [ ] Components use token classes (`glass-card` equivalent via `.section`, `status-dot`, `ghost-cta`, `chip`, etc.)
- [ ] Status dots use `--dot-*` tokens (`.health-dot.on_track` uses `--dot-green`, not `--success`)
- [ ] Interactive text uses `--text-secondary` or higher (not `--text-tertiary` for readable content)
- [ ] New components logged in `docs/DESIGN_COMPONENT_LOG.md`: `.data-stale-warning`, `.all-quiet-card`, `.cache-freshness`, `.impact-badge`

---

## FUNCTIONAL CHECKS (CLI — no browser needed)

1. **Lint score**
   - Run: `python scripts/design_lint.py --files web/templates/brief.html`
   - PASS: Score 5/5, 0 violations
   - FAIL: Any violations shown

2. **Template syntax valid**
   - Run: `python -c "from jinja2 import Environment, FileSystemLoader; e=Environment(loader=FileSystemLoader('web/templates')); e.get_template('brief.html'); print('OK')"`
   - PASS: Prints `OK`
   - FAIL: Jinja2 parse error

3. **No stale variable references**
   - Run: `grep -n "var(--font-display)\|var(--font-body)\|var(--surface)\|var(--border)\|var(--text-muted)\|var(--error)\|var(--warning)\|var(--success)" web/templates/brief.html`
   - PASS: No output (all replaced)
   - FAIL: Any matches found

---

## BROWSER CHECKS (Playwright — staging URL)

Requires authenticated session (magic-link login as test user with watched properties).

4. **Brief page loads without 500 error**
   - Navigate to `/brief`
   - PASS: Page renders, `<h1>` visible with "Good Morning"
   - FAIL: Error page or 500

5. **Summary cards render with correct font family**
   - Check `.summary-number` elements
   - PASS: Numbers rendered in monospace font (JetBrains Mono)
   - FAIL: Serif or system font visible

6. **Lookback toggle buttons styled**
   - Check `.lookback-btn` elements
   - PASS: Buttons have border, appropriate background, mono font
   - FAIL: Unstyled links

7. **Property cards have left border color coding**
   - If at-risk properties exist: `.prop-card.health-at_risk` has red left border
   - PASS: Border visible and color-coded
   - FAIL: No border or wrong color

8. **Status dots use --dot-* colors (not old --success)**
   - Inspect `.health-dot.on_track` computed background
   - PASS: `rgb(34, 197, 94)` (--dot-green)
   - FAIL: Different green value from old --success

9. **Progress bars render**
   - If health section has permits: `.progress-track` and `.progress-fill` visible
   - PASS: Thin horizontal bar visible with gradient fill
   - FAIL: No bar or bar invisible

10. **Cache freshness UI (if brief.cached_at is set)**
    - Check for `.cache-freshness` div
    - PASS: Green status dot + timestamp text visible, OR section absent when `cached_at` is None
    - FAIL: Section present but missing dot, OR crashes with template error

11. **Stale data warning (if applicable)**
    - Check `.data-stale-warning` class
    - PASS: Warning uses amber text with glass border, no inline hex colors
    - FAIL: Hardcoded hex color visible in computed styles

12. **All-quiet state**
    - Visit brief with lookback=1 for an account with no recent activity
    - PASS: `.all-quiet-card` renders with accent-glow background and ghost-cta link
    - FAIL: Inline rgba blue styles visible

13. **Regulatory watch impact badges**
    - If regulatory alerts present: `.impact-badge` with appropriate class
    - PASS: Badges use class-based colors (`impact-high`, `impact-moderate`, `impact-low`)
    - FAIL: Inline style with hardcoded hex color

14. **Email pref link**
    - Bottom of page link `.email-pref-link`
    - PASS: Monospace font, secondary text color
    - FAIL: Inline style with `color: var(--text-muted)` (non-token var)

---

## EDGE CASES

15. **Empty brief (no watches)**
    - Navigate to brief as user with 0 watches
    - PASS: Onboarding `.section.onboarding` renders with "No morning brief yet" h2
    - FAIL: Error or blank page

16. **Property synopsis section**
    - As user with single watched address: synopsis section renders
    - PASS: "Your Property" section with stat counters, permit link uses `--accent` color, CTA uses `.ghost-cta`
    - FAIL: Inline styles on permit link or CTA
