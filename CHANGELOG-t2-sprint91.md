# Changelog — T2 Sprint 91 (Search Template Migration)

## [Sprint 91 T2] — 2026-02-28

### Changed

#### Design Token Migration — Search Flow Templates

- **`web/templates/search_results_public.html`** (5/5 lint):
  - Fixed WCAG accessibility: `.mobile-intel-toggle` button now uses `--text-secondary` instead of `--text-tertiary` (interactive elements must pass WCAG AA contrast)
  - Fixed hint text color: guidance suggestion hints now use `--text-secondary` (was `--text-tertiary`, which fails on informational content)
  - Replaced non-token nav background `rgba(10,10,15,0.85)` with `rgba(0,0,0,0.85)` (in allowed token palette)
  - Replaced `&#10024;` HTML entity with `✨` Unicode (avoids design lint false positive)

- **`web/templates/search_results.html`** (5/5 lint):
  - Replaced all non-token hex colors: `#4f8ff7` → `var(--accent)`, `#8b8fa3` → `var(--text-secondary)`, `#7ab0ff` → `var(--accent)` with opacity
  - Replaced non-token rgba: `rgba(239,68,68,...)` → `rgba(248,113,113,...)` (signal-red family), `rgba(79,143,247,...)` → `var(--glass-border)`
  - Fixed `font-family:inherit` on all form buttons → `var(--sans)` (explicit token required)
  - Removed legacy fallbacks: `var(--accent, #4f8ff7)` → `var(--accent)`, `var(--text-muted, #8b8fa3)` → `var(--text-secondary)`, `var(--success, #34d399)` → `var(--signal-green)`, `var(--text, #e4e6eb)` → `var(--text-primary)`
  - Added `intel-col--alert` CSS class (replaces conditional inline style for enforcement alert state)
  - Updated intel panel component CSS: added `font-family`, `font-size` token vars to `.intel-col-label`, `.intel-col-value`, `.intel-col-detail`
  - Replaced raw `border-radius: 10px` with `var(--radius-md)` token
  - Replaced raw pixel `font-size` values with fluid token scale (`--text-xs`, `--text-sm`, `--text-base`, `--text-lg`)

- **`web/templates/results.html`**: Already 5/5 before migration. No changes needed.

### Added

- **`tests/test_migration_search.py`**: 18 tests covering design token compliance, render behavior, and regression checks for all 3 templates
