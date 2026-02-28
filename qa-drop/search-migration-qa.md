# QA Script: Search Flow Template Migration (Sprint 91 T2)

**Feature:** Migrate search flow templates to Obsidian design tokens
**Templates:** search_results_public.html, results.html, search_results.html
**Date:** 2026-02-28

---

## UNIT TESTS

1. Run migration tests
   ```
   pytest tests/test_migration_search.py -v
   ```
   PASS: 18 passed, 0 failed

---

## DESIGN TOKEN COMPLIANCE

- [x] Run: `python scripts/design_lint.py --files web/templates/search_results_public.html web/templates/results.html web/templates/search_results.html`
- [x] Score: 5/5 for all three files
- [x] No inline colors outside DESIGN_TOKENS.md palette
- [x] Font families: --mono for data, --sans for prose
- [x] Components use token classes (glass-card, obs-table, ghost-cta, etc.)
- [x] Interactive text uses --text-secondary or higher (not --text-tertiary)
- [x] No legacy --font-body or --font-display variables
- [x] No non-token hex colors (#4f8ff7, #8b8fa3, #7ab0ff)

---

## FUNCTIONAL CHECKS

2. Public search results — happy path
   - Navigate to `/search?q=614+6th+Ave`
   - PASS: Page renders with status 200
   - PASS: Search input pre-filled with query
   - PASS: Results shown in styled card layout

3. Public search results — no results state
   - Navigate to `/search?q=zzz_nonexistent_address_xyz_99999`
   - PASS: Page renders with status 200
   - PASS: "No permits found" message shown
   - PASS: Search guidance card with examples shown

4. Public search results — mobile viewport (375px)
   - Viewport: 375×812
   - PASS: No horizontal overflow
   - PASS: Search input full-width
   - PASS: Navigation wordmark readable

5. Public search results — error state
   - Check template handles `{{ error }}` variable gracefully
   - PASS: "Something went wrong" message shown when error set

---

## REGRESSION CHECKS

6. Authenticated search results (search_results.html fragment)
   - Log in, search any address
   - PASS: Intel panel loads (quick actions, violations, business data)
   - PASS: No broken styling on intel columns
   - PASS: Enforcement alert (red tint) shows when violations present

7. Results fragment (results.html — authenticated analysis tabs)
   - Run a permit analysis on a known address
   - PASS: Tabs render (Permits, Timeline, Fees, Documents, Risk)
   - PASS: Tab switching works
   - PASS: Methodology expand/collapse works

---

## CHANGE SUMMARY

### search_results_public.html
- `--text-tertiary` on interactive `.mobile-intel-toggle` → `--text-secondary`
- `rgba(10,10,15,0.85)` nav background → `rgba(0,0,0,0.85)` (allowed token)
- `&#10024;` HTML entity → `✨` Unicode (fixed lint false positive)

### search_results.html
- `#4f8ff7` (old blue) → `var(--accent)` throughout
- `#8b8fa3` (old muted) → `var(--text-secondary)` throughout
- `#7ab0ff` (old hover blue) → `var(--accent)` with opacity
- `rgba(239,68,68,...)` → `rgba(248,113,113,...)` (signal-red token)
- `rgba(79,143,247,...)` → `var(--glass-border)`
- `font-family:inherit` → `var(--sans)` on all buttons
- Legacy `var(--text, #fallback)` → `var(--text-primary)` / `var(--text-secondary)`
- Legacy `var(--success, #fallback)` → `var(--signal-green)`
- `intel-col--alert` CSS class added (replaces conditional inline style)
- Font size `0.7rem`, `0.8rem`, etc. → token scale vars (`--text-xs`, `--text-sm`)

### results.html
- Already at 5/5. No changes needed.
