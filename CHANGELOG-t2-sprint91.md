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
