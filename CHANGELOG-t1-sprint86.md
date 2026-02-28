# CHANGELOG — T1 Sprint 86 (Agent: visual-qa structural mode)

## scripts/visual_qa.py
- Added `--structural` CLI flag enabling DOM fingerprint mode (mutually exclusive with pixel diff matrix — exits early after structural run)
- Added `--structural-baseline` flag to capture fingerprints as new baselines (saved to `qa-results/structural-baselines/<slug>-<viewport>.json`)
- Added `--structural-check` flag (informational; default when `--structural` given without `--structural-baseline`)
- Added `--structural-changed-only` flag to restrict fingerprinting to pages whose templates appear in `git diff HEAD~1`
- Added `TEMPLATE_TO_SLUG` dict mapping 22 Jinja2 template paths to their associated PAGES slugs
- Added `_SHARED_TEMPLATES` set — changes to these files (base.html, nav.html, obsidian.css, etc.) trigger full-page-matrix re-check
- Added `slugs_for_changed_files(changed_files)` — maps git-changed paths to affected page slugs; shared templates expand to all slugs
- Added `get_page_fingerprint(page)` — runs `_FINGERPRINT_JS` via `page.evaluate()` to collect: body/container CSS classes, component counts, HTMX attribute presence, viewport overflow, centering check
- Added `diff_fingerprints(baseline, current)` — compares two fingerprint dicts and returns human-readable diff strings; empty list = PASS
- Added `StructuralResult` dataclass — parallel to `CompareResult`; fields: page_slug, viewport, status, diffs, baseline_path, message
- Added `run_structural_qa()` — full Playwright pipeline for structural mode; handles auth, retries, baseline save/load, results aggregation
- Added `_write_structural_results_md()` — writes `qa-results/qs10-structural-results.md` with per-page table and per-failure diff details
- Added `_get_changed_files_from_git()` — shells out to `git diff --name-only HEAD~1`; returns empty list on error
- Added `import subprocess` to support git diff in `_get_changed_files_from_git()`
- Updated module docstring to document the three modes and new structural CLI flags

## tests/test_visual_regression.py (new file)
- 19 Playwright-free pytest tests covering:
  - `get_page_fingerprint`: mock page.evaluate, error propagation, single evaluate call
  - `diff_fingerprints`: identical → no diffs, body class added, body class removed, component count changed, HTMX boolean changed, viewport overflow changed, multiple independent changes
  - `slugs_for_changed_files`: known template, admin template, shared layout template (all pages), shared CSS (all pages), unknown file (empty), empty input (empty)
  - Baseline round-trip: save to tmp_path → reload → identical; diff against self → empty; all required keys present
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
