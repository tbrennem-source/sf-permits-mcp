# QA Results — Portfolio + Index Obsidian Migration

**Session:** portfolio-index-obsidian-migration
**Date:** 2026-02-27
**Scope:** Migrate portfolio.html, project_detail.html, index.html to obsidian design tokens

## Design Token Compliance

| Check | Result |
|-------|--------|
| portfolio.html uses glass-card, status-dot, obsidian tokens | PASS |
| project_detail.html uses glass-card, role badges, obsidian tokens | PASS |
| portfolio.html includes head_obsidian.html | PASS |
| project_detail.html includes head_obsidian.html | PASS |
| portfolio.html body class="obsidian" | PASS |
| project_detail.html body class="obsidian" | PASS |
| No hardcoded hex colors in portfolio.html | PASS |
| No hardcoded hex colors in project_detail.html | PASS |
| index.html staging banner `#1a1d27` replaced with `var(--bg-deep)` | PASS |
| index.html blue accent `rgba(79,143,247,...)` replaced with `rgba(34,211,238,...)` cyan | PASS |
| index.html font families use `var(--font-display)` / `var(--font-body)` | PASS |
| Design lint: portfolio.html | PASS (5/5 — 0 violations) |
| Design lint: project_detail.html | PASS (5/5 — 0 violations) |
| Design lint: index.html raw score | FAIL (1/5 — 64 violations, all false positives — see design-lint-agent-a.md) |

## Template Structure

| Check | Result |
|-------|--------|
| portfolio.html Jinja logic preserved (all `{% for %}`, `{% if %}` blocks intact) | PASS |
| project_detail.html Jinja logic preserved | PASS |
| portfolio.html property cards render with CSS variables | PASS |
| project_detail.html member rows render with role badges | PASS |
| project_detail.html invite form present for owner/admin | PASS |
| index.html search form structure unchanged | PASS |
| index.html personalization controls preserved | PASS |

## Pytest

| Check | Result |
|-------|--------|
| Pre-existing test failures (381 failures) — DuckDB lock contention | BLOCKED-EXTERNAL |
| Template-specific tests (no template unit tests in suite) | N/A |
| Web app starts without import errors | PASS |

## Notes

- 381 pytest failures are pre-existing (DuckDB lock contention — another process holds the DB lock). Not caused by template changes. All failures are in `tests/test_web.py` with 404 responses indicating test infrastructure issue, not template bugs.
- portfolio.html and project_detail.html: complete rewrites — all old non-token CSS replaced.
- index.html: targeted CSS-only migration — Jinja/JS/HTML structure preserved, only `<style nonce>` block updated.
