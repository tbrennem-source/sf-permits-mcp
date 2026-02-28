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
# Sprint 91 T2 — Changelog

## Design Token Migration: Property & Tool Templates

### report.html — Full Obsidian head migration

**File:** `web/templates/report.html`

**What changed:**
- Replaced standalone `<head>` (which duplicated all token vars, Google Fonts, HTMX loading, and full shared CSS) with `{% include "fragments/head_obsidian.html" %}`
- Removed ~120 lines of duplicated shared CSS that is now provided by `obsidian.css` (loaded via head_obsidian.html):
  - `:root` token variable definitions (backgrounds, text, accent, signals, dots, fonts, type scale, spacing, radius)
  - Reset (`*, *::before, *::after`)
  - `.obs-container`
  - `.nav-float` and variants
  - `.ghost-cta`
  - `.action-btn`, `.action-btn--danger`
  - `.chip`
  - `.status-dot`, `.status-text--*`
  - `.section-label`
  - `.glass-card`
  - `.data-row`, `.data-row__label`, `.data-row__value`
  - `.progress-track`, `.progress-fill`
  - `.obs-table` and variants
  - `.modal-backdrop`, `.modal`, `.modal__*`
  - `.section-divider`
  - `.freshness`, `.freshness-dot`
  - `.reveal`, `.reveal-delay-*`
  - Print styles, responsive breakpoints, reduced-motion media queries
- Retained all report-specific component CSS in scoped `<style nonce="{{ csp_nonce }}">` block:
  - `.property-header`, `.property-address`, `.property-meta`
  - `.owner-banner`
  - `.intel-grid`, `.intel-card` and variants
  - `.actions-section`, `.action-item` and variants
  - `.cta-row`, `.divider`
  - `.permit-list`, `.permit-item` and variants
  - `.status-chip` and variants
  - `.routing-section`, `.station-row`, `.station-name`, `.station-bar`, `.station-result`
  - `.entity-row`, `.entity-name`, `.entity-role`, `.entity-permits`
  - `.risk-item` and variants, `.severity-chip` and variants
  - `.cv-card`, `.cv-header`, `.cv-number`, `.cv-meta`, `.cv-desc`
  - `.permit-details`, `.permit-details__heading`, `.detail-item`
  - `.risk-flag` and variants
  - `.insight`, `.insight--amber`, `.insight__*`
  - `.remediation-option` and variants, `.effort-*`, `.remediation-sources`
  - `.consultant-callout` and variants, `.consultant-factors`
  - `.zoning-note`, `.show-more`, `.empty-state`
  - Report-specific link extensions for `.data-row__value a`, `.obs-table__mono a`, `.obs-table td a`
  - Report-specific responsive breakpoints (`.nav-search { display: none }`, `.intel-grid` reflows)
  - `.nav-search` (report-custom nav with address search bar)
- Added `<script nonce="{{ csp_nonce }}" src="/static/htmx.min.js">` (needed for share modal HTMX form)
- Removed duplicate `<link rel="stylesheet" href="/static/mobile.css">` (now loaded by head_obsidian.html)

### stuck_permit.html — CDN HTMX migration

**File:** `web/templates/tools/stuck_permit.html`

**What changed:**
- Replaced `<script src="https://unpkg.com/htmx.org@1.9.12">` (external CDN, no CSP nonce attribute) with `<script nonce="{{ csp_nonce }}" src="/static/htmx.min.js">` (local, nonce-compliant)
- Existing head_obsidian.html include retained

### station_predictor.html — No changes needed

**File:** `web/templates/tools/station_predictor.html`

Already fully compliant with Obsidian design system. No changes made.

### New test file

**File:** `tests/test_migration_property.py`

- 30 tests across 10 test functions
- Parametrized over all 3 templates
- Covers: template existence, head_obsidian include, no legacy font vars, token font var usage, no off-palette hex colors, report-specific component presence, form elements in tool templates, no external HTMX CDN, obs-container usage, no hardcoded px font sizes in inline styles, nonce on all script/style tags

### Design lint scores
- `report.html`: 5/5
- `station_predictor.html`: 5/5
- `stuck_permit.html`: 5/5
