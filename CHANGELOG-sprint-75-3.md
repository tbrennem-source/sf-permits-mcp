# CHANGELOG — Sprint 75-3 (Agent 3: Template Migration Batch 1)

## Summary

Migrated 5 user-facing templates to the Obsidian design system (Sprint 75-3).

## Changes

### Templates Migrated

**1. web/templates/account.html** (FULL PAGE)
- Replaced inline `:root` CSS variable block and `-apple-system` font stack with `{% include "fragments/head_obsidian.html" %}`
- Added `class="obsidian"` to `<body>` tag
- Wrapped main content in `.obs-container`
- Replaced `.card` with a glass-card-aliased `.card { }` definition using Obsidian tokens (`var(--bg-surface)`, `var(--card-radius)`, etc.)
- Tab buttons now use `var(--signal-cyan)` for active state
- Removed 165 lines of old inline CSS; added 85 lines of minimal supplemental styles using design tokens

**2. web/templates/search_results.html** (HTMX FRAGMENT)
- Added `glass-card` class to root `.result-card.search-result-card` wrapper
- Quick Actions section converted to `.glass-card` with Obsidian spacing tokens
- "View Property Report" button uses `.obsidian-btn.obsidian-btn-primary`
- "Analyze Project" and "Who's Here" buttons use `.obsidian-btn.obsidian-btn-outline`
- "Check Violations" button uses `.obsidian-btn.obsidian-btn-outline` with conditional inline color overrides for red/green states
- No-results block uses `.glass-card`
- Neighborhood stats card uses `.glass-card`
- All Jinja logic, HTMX attributes, and fragment includes preserved

**3. web/templates/analyze_plans_complete.html** (HTMX FRAGMENT)
- Root div uses `.glass-card` with Obsidian spacing tokens
- "View Results" link uses `.obsidian-btn.obsidian-btn-primary`
- Success text uses `var(--signal-green)` token
- Auto-redirect JS preserved

**4. web/templates/analyze_plans_results.html** (HTMX FRAGMENT)
- Root `.result-card` gets `.glass-card` class
- Previous analyses banner uses `.glass-card`
- All bulk action toolbar buttons use `.obsidian-btn.obsidian-btn-outline`
- Annotation filter select uses `.obsidian-input`
- Detail panel action buttons use `.obsidian-btn.obsidian-btn-outline`
- Lightbox Download/Print buttons use `.obsidian-btn.obsidian-btn-outline`
- Comparison panel buttons use `.obsidian-btn.obsidian-btn-outline`
- Email modal Send/Cancel use `.obsidian-btn-primary`/`.obsidian-btn-outline`
- Email inputs use `.obsidian-input`
- Watch cross-sell prompt uses `.glass-card`; Watch button uses `.obsidian-btn.obsidian-btn-outline`
- "Analyze Another Plan" link uses `.obsidian-btn.obsidian-btn-outline`
- All Jinja variables, annotation JS, and HTMX logic preserved

**5. web/templates/analyze_plans_polling.html** (HTMX FRAGMENT)
- Cancel Analysis button uses `.obsidian-btn.obsidian-btn-outline`
- Spacing tokens used (`var(--space-4)`)
- Step indicator, HTMX polling trigger, and elapsed time display preserved

### Tests Added

**tests/test_sprint_75_3.py** (43 tests, all passing)
- 12 tests for account.html structure, Obsidian compliance, preserved includes
- 8 tests for search_results.html glass-card classes, obsidian-btn classes, preserved Jinja/HTMX
- 6 tests for analyze_plans_complete.html
- 8 tests for analyze_plans_results.html
- 5 tests for analyze_plans_polling.html
- 4 route smoke tests (account redirects anon → 302, design-system.css serves 200)

### Notes

- `plan_results_page.html` (parent of `analyze_plans_results.html`) was NOT migrated — not in agent 75-3 file ownership. This means the results page inherits its dark background from the parent but Obsidian component classes will activate via the `.obsidian` body class when that page is also migrated.
- Pre-existing test failure: `test_permit_lookup_address_suggestions` in `tests/test_permit_lookup.py` — not caused by these changes.
