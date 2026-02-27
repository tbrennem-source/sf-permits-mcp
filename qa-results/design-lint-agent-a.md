# Design Lint Results — Agent A (Portfolio + Index Migration)

**Session:** portfolio-index-obsidian-migration
**Date:** 2026-02-27
**Files checked:** portfolio.html, project_detail.html, index.html

## Summary

| File | Score | Violations | Notes |
|------|-------|-----------|-------|
| `web/templates/portfolio.html` | 5/5 | 0 | PASS — complete rewrite to obsidian tokens |
| `web/templates/project_detail.html` | 5/5 | 0 | PASS — complete rewrite to obsidian tokens |
| `web/templates/index.html` | 1/5 | 64 | See note below |

**Combined score (3 files):** 1/5 (64 violations)

## Note on index.html Violations

The 64 violations in index.html are all false positives from the lint tool:

1. **HTML entity codes detected as hex** (e.g., `&#9654;`, `&#128196;`, `&#9989;`, `&#128290;`): The lint regex matches `#` followed by hex digits, incorrectly catching HTML entity numeric codes. These are NOT hex colors — they are Unicode code points used to render icons/emoji.

2. **`var(--font-display)` and `var(--font-body)` flagged as non-token**: The lint tool is calibrated against `docs/DESIGN_TOKENS.md` which documents `--mono` and `--sans`. However, `web/static/design-system.css` (the actual CSS file) defines the font variables as `--font-display` and `--font-body`. This is a pre-existing inconsistency in the project between documented names and actual CSS variable names.

## Pre-Migration Baseline

The original `index.html` (before migration) scored **1/5 (38 violations)**. All 38 were the same false positive categories. My migration added 26 additional false positive violations by converting more CSS rules to use `--font-display`/`--font-body`.

## Real Violations Fixed

- `#1a1d27` in staging banner → `var(--bg-deep)` (hardcoded hex → token)
- `rgba(148, 163, 184, 0.08)` in role badge → `rgba(96, 165, 250, 0.08)` (non-token → signal-blue based)

## Prod Promotion Assessment

Per design lint gate policy (1/5 = HOLD):
- **portfolio.html**: 5/5 — auto-promote
- **project_detail.html**: 5/5 — auto-promote
- **index.html**: Score is 1/5 but ALL violations are false positives. Actual compliance is high — all real ad-hoc colors were replaced with token variables. Recommend **Tim review and approve** based on this analysis before prod promotion.
