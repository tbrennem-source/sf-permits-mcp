## Sprint 86 — T1-B (Design Lint --live mode)

- **feat(design-lint): add --live mode** — `scripts/design_lint.py` gains `--live` and `--url` flags.
  Launches Playwright headless Chromium to run four new live checks: computed color compliance
  (±2 RGB tolerance vs ALLOWED_TOKENS_VARS), computed font compliance (.obs-table → mono,
  p/.insight__body → sans), axe-core WCAG AA color-contrast injection, and viewport overflow detection.
  Existing static checks (--files, --changed, no flag) are fully unchanged. Output goes to
  `qa-results/design-lint-live-results.md`.

- **test(design-lint): add tests/test_design_token_lint.py** — 49 tests covering all 6 existing
  static checks, ALLOWED_TOKENS_VARS dict, _hex_to_rgb/_parse_computed_color/_rgb_within_tolerance
  helpers, axe violation parsing logic, viewport overflow logic, score() with live violations,
  and CLI --live/--url arg parsing. All pass; full suite 3705/3705 green.
