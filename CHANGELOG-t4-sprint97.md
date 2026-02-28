# CHANGELOG — T4 Sprint 97 (Agent 4B)

## Agent 4B: Minor UX Fixes

### Fixed

- **`web/templates/demo.html`** — Mobile overflow fix: `.callout` elements (annotation chips) now use `display: block; max-width: 100%; box-sizing: border-box` inside `@media (max-width: 480px)`. Previously the `inline-block` default caused ~300px horizontal overflow on 375px phones.

### Verified (no changes needed)

- **`web/templates/landing.html`** — Stats counter: `data-target="1137816"` was already correct (1,137,816 SF building permits).
- **`web/templates/landing.html`** — State machine navigation: All watched-property `href` values in `beta` and `returning` states already navigate to `/search?q=...` or `/portfolio` — none use `href="/"`.

### Tests Added

- **`tests/test_minor_fixes.py`** — 5 tests:
  1. `/demo` route returns HTTP 200
  2. demo.html renders `.callout` elements
  3. demo.html `@media (max-width: 480px)` block contains `.callout` with `display:block`, `max-width:100%`, `box-sizing:border-box`
  4. landing.html stats counter `data-target` equals 1137816
  5. landing.html state machine watched-property links do not route to `"/"`
