# CHANGELOG — Sprint 76-4: Obsidian Migration — 5 Admin Templates

## Summary

Migrated 5 admin templates from the legacy dark-theme inline CSS system to the Obsidian design system. All admin pages now use `body.obsidian`, `.obs-container`, `.glass-card`, `design-system.css` tokens, and the Obsidian typography stack (JetBrains Mono headings, IBM Plex Sans body).

## Files Changed

### Templates (MODIFIED)
- `web/templates/admin_ops.html` — Tab-based operations dashboard. Replaced hardcoded `:root` vars with Obsidian design system. Preserved all HTMX tab loading, hash routing, hash aliases (luck/dq/watch/intelligence), 30s timeout handling, and fallback safety net JavaScript.
- `web/templates/admin_feedback.html` — Feedback queue (fragment-aware). Added `body.obsidian` and `obs-container` in standalone mode; applies Obsidian glass-card styling to feedback items. Fragment mode (used by admin_ops tabs) renders without full page shell. Preserved HTMX status update actions, resolve/wontfix buttons, screenshot toggle.
- `web/templates/admin_metrics.html` — Metrics dashboard. Replaced inline `:root` block with `head_obsidian.html` include. Each data section (issuance trends, SLA compliance, planning velocity) wrapped in `.glass-card`. Stat counts converted to Obsidian stat blocks with `--signal-cyan`. SLA color coding preserved (green/amber/red).
- `web/templates/admin_costs.html` — API cost dashboard. Kill switch panel, alert banner, stat cards, 7-day bar chart, and endpoint/user tables all migrated to Obsidian tokens. Kill switch status colors use `--signal-red`/`--signal-green`. Preserved kill switch form submission and back link.
- `web/templates/admin_activity.html` — Activity feed (fragment-aware). Stat cards for action filtering, user dropdown, filter tags, activity rows, and pagination all migrated. Fragment mode preserves HTMX injection into `#tab-content`. `filterByUser()` JS preserved with HTMX ajax fallback.

### Tests (NEW)
- `tests/test_sprint_76_4.py` — 34 tests covering all 5 admin templates. Tests: 200 response with admin auth, `obsidian` class marker, `obs-container`, `glass-card`, key functionality preserved (tabs, HTMX, filter buttons, kill switch panel, activity feed).

### Test Fixes (TEST FIXUP EXCEPTION)
- `tests/test_qs4_a_metrics.py::TestMetricsTemplate::test_has_obsidian_vars` — Updated assertion from checking hardcoded hex vars (`--bg: #0f1117`) to checking Obsidian design system markers (`design-system.css`, `obsidian` class). The test name "obsidian vars" was checking for the OLD non-obsidian CSS variables; now accurately tests the actual Obsidian system.

## Design System Compliance

All 5 templates now comply with `design-spec.md`:
- `{% include "fragments/head_obsidian.html" %}` in `<head>`
- `<body class="obsidian">` on body tag (standalone mode)
- `<div class="obs-container">` wraps all content
- Every distinct content section in `.glass-card`
- Signal color tokens used for status badges and indicators
- No hardcoded hex values — all reference CSS custom properties

## Pre-existing Test Failure (NOT caused by this sprint)

`tests/test_permit_lookup.py::test_permit_lookup_address_suggestions` — Fails due to a mock setup issue in that test file. Last modified by QS3-B sprint, unrelated to admin templates.
