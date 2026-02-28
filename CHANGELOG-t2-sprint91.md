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
