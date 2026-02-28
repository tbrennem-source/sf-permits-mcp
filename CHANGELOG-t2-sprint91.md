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
# Changelog — Sprint 91 T2 (Auth + Supporting Template Migration)

## Sprint 91 — Template Migration: Auth + Consultants

### web/templates/consultants.html — MIGRATED (1/5 → 5/5 lint score)

**What changed:**
- Replaced entire custom `:root` CSS variable block (`--bg: #0f1117`, `--surface`, `--surface-2`,
  `--border: #333749`, `--text`, `--text-muted`, `--accent: #4f8ff7` [wrong blue!]) with
  the full Obsidian design token set (`--obsidian`, `--accent: #5eead4`, `--text-primary/secondary/tertiary`, etc.)
- Replaced `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
  with `var(--sans)` on `body`
- Replaced all `font-family: inherit` on form elements with `var(--sans)` or `var(--mono)`
- Added `{% include "fragments/head_obsidian.html" %}` — provides shared CSS, CSRF meta tag,
  Google Fonts, PWA manifest, HTMX CSRF header injection
- Replaced old custom `<header>` + `.logo` + `.badge` nav with `{% include "fragments/nav.html" %}`
- Replaced `.form-card` container with `glass-card` token component
- Replaced custom `.form-group label` styles with `form-label` token class
- Replaced custom `input, select` styles with `form-input`, `form-select` token classes
- Replaced custom checkbox divs with `form-check` / `form-check__input` / `form-check__box` /
  `form-check__label` token components
- Replaced `.btn` (filled blue button) with `action-btn` token component
- Replaced `.badge-hood` color `#c084fc`, `.badge-network` color `#93c5fd`,
  `.badge-recent` color `#6ee7b7` with signal token colors (`--signal-blue`, `--signal-green`)
- Replaced `rgba(79,143,247,...)` (non-token blue) on `.badge-address`, `.info`,
  and inline style prefill banner with token equivalents (`rgba(94,234,212,...)` / `var(--glass)`)
- Removed inline `style="margin-bottom:...; background:rgba(79,143,247,0.08); ..."` prefill
  banner — replaced with `.context-banner` class using `var(--glass)` and `var(--glass-border)`
- Added `csrf_token` hidden input to the HTMX form (was missing in original)
- Replaced `.consultant-card:hover` border color from `var(--accent)` [was wrong blue]
  to `var(--glass-hover)`
- Added `obs-container` layout class on `<main>` wrapper
- Replaced `.error` and `.info` message classes with `msg-error` and `msg-info`
  using token border-left signal colors
- Replaced `.sort-chip.active` filled blue background with `var(--accent-glow)` + `var(--accent)`

**Lint score:** 1/5 → 5/5 (0 violations)

---

### web/templates/auth_login.html — NO CHANGES NEEDED

Already fully compliant (0 violations, 5/5 lint score). Uses design token CSS vars,
`--mono`/`--sans` font vars, glass-card, form-label/input, ghost-cta, action-btn, toast
components throughout.

---

### web/templates/beta_request.html — NO CHANGES NEEDED

Already fully compliant (0 violations, 5/5 lint score). Uses design token CSS vars,
`--mono`/`--sans` font vars, glass-card, form-label/input, action-btn, ghost-cta components.

---

### tests/test_migration_auth.py — NEW

16 tests covering:
- Template render tests (3): auth_login, beta_request, consultants render without errors
- Hex color compliance (3): no non-token hex colors in any template
- Font var compliance (3): no legacy --font-body / --font-display vars
- consultants-specific structure (7): uses --mono/--sans, head_obsidian include,
  csrf_token, nav fragment, glass-card, form-label/input/select, action-btn

**Results:** 16/16 passing
**Full suite:** 4185 passed, 6 skipped, 17 xfailed, 4 xpassed (no regressions)
# CHANGELOG — Sprint 91 T2: Tool & Content Template Migration

## Sprint 91 T2 — Design Token Migration

### Templates migrated to Obsidian design system

**methodology.html** — Full migration from standalone page to Obsidian system
- Replaced standalone `<head>` with `{% include "fragments/head_obsidian.html" %}`
- Replaced custom header + minimal nav with `{% include "fragments/nav.html" %}`
- Removed entire `:root {}` var block (now comes from design-system.css via head_obsidian)
- Replaced `.container` with `.obs-container` (standard 1000px max-width container)
- Replaced all hardcoded font sizes (1.4rem, 0.9rem, etc.) with `--text-*` scale vars
- Replaced all hardcoded spacing (24px, 48px, etc.) with `--space-*` vars
- Moved footer inside `obs-container` div as `.methodology-footer`
- Added `{% include 'fragments/feedback_widget.html' %}` and admin scripts
- Token lint: 5/5 clean

**demo.html** — Full migration from standalone page to Obsidian system
- Replaced standalone `<head>` with `{% include "fragments/head_obsidian.html" %}`
- Replaced custom header (logo + demo badge) with `{% include "fragments/nav.html" %}` + inline demo-badge on hero h1
- Removed entire `:root {}` var block
- Replaced `.container` with `.obs-container`
- Replaced all hardcoded pixel sizes with token vars (`--space-*`, `--text-*`)
- Replaced `.cta-button` custom class with `.ghost-cta` token component
- Moved footer inside obs-container as `.demo-footer`
- Added `{% include 'fragments/feedback_widget.html' %}` and admin scripts
- Token lint: 5/5 clean

**web/templates/tools/what_if.html** — Pre-migrated; verified clean
- Already extends `head_obsidian.html` and `nav.html`
- All CSS uses token vars — no changes needed
- Token lint: 5/5 clean

**web/templates/tools/cost_of_delay.html** — Pre-migrated; verified clean
- Already extends `head_obsidian.html` and `nav.html`
- All CSS uses token vars — no changes needed
- Token lint: 5/5 clean

### Tests added

**tests/test_migration_tools.py** — 20 tests
- Route render tests: all 4 pages render (200 or expected redirect)
- Fragment inclusion: all 4 templates use `head_obsidian.html`
- Nav fragment: methodology + demo use `fragments/nav.html`
- No legacy font vars: `--font-body`, `--font-display` absent from all templates
- No standalone `:root` token blocks in methodology or demo
- No non-token hex colors in any template
- Full suite: 4219 passed, 6 skipped, 0 failures

### Design lint results
- what_if.html: 5/5 clean
- cost_of_delay.html: 5/5 clean
- methodology.html: 5/5 clean
- demo.html: 5/5 clean
