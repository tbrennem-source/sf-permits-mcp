# CHANGELOG — Sprint QS11 T4 (Tier Gate Overlay UI)

## [QS11-T4] 2026-02-28

### Added

- **Tier gate overlay component** (`web/templates/components/tier_gate_overlay.html`)
  - Jinja2 partial included at the bottom of gated page templates
  - Renders a fixed full-viewport overlay with signup CTA when `tier_locked=True`
  - Zero DOM output when `tier_locked=False` — no performance impact for entitled users
  - Extends `glass-card` and `ghost-cta` token components
  - Analytics attributes: `data-track="tier-gate-impression"` (overlay) and `data-track="tier-gate-click"` (CTA)
  - Template context vars: `tier_locked`, `tier_required`, `tier_current` (injected by context processor from Agent 4A)

- **Tier gate CSS** (`web/static/css/tier-gate.css`)
  - `.tier-locked-content`: 8px blur, pointer-events: none, user-select: none, smooth transition
  - `.tier-gate-overlay`: fixed inset-0, centered flex, z-index 100, 30% black backdrop
  - `.tier-gate-card`: max-width 420px, full token compliance (--sans, --space-*, --text-*)
  - `.tier-gate-cta`: extends ghost-cta with display/padding overrides
  - `.tier-gate-subtext`: --text-tertiary (WCAG AA exempt for non-interactive reassurance copy)
  - Mobile breakpoint at 480px: card margin + full-width block CTA
  - All colors, fonts, spacing from DESIGN_TOKENS.md — no ad-hoc hex values

- **Tier gate JavaScript** (`web/static/js/tier-gate.js`)
  - DOMContentLoaded listener adds `.tier-locked-content` to first `main`, `.obs-container`, or `.obs-container-wide`
  - Guard: exits early if `.tier-gate-overlay` is not present (no blur on non-gated pages)
  - 8px blur calibration: tantalizing but unreadable — user sees structure, cannot read text

- **Tier gate UI tests** (`tests/test_tier_gate_ui.py`)
  - 31 tests: 12 template tests, 12 CSS tests, 7 JS tests
  - Template: conditional rendering (True/False), CTA href, data-track attributes, glass-card class, data attribute injection
  - CSS: blur value, mobile breakpoint, token usage (spacing, colors, fonts), position, z-index, pointer-events, user-select
  - JS: DOMContentLoaded listener, overlay query, class addition, container targeting, missing-overlay guard
  - All 31 pass

- **Design Component Log** (`docs/DESIGN_COMPONENT_LOG.md`)
  - Logged new "Tier Gate Overlay" component with HTML, CSS, and usage notes

### Technical Notes

- Blur calibration: 8px is intentional. Less than 5px is readable; more than 8px is hostile. 8px shows structure (enough to create desire) without allowing data extraction.
- The `components/` subdirectory is new under `web/templates/`. Created for overlay-type partials that differ from `fragments/` (fragments are HTMX swap targets; components are structural includes).
- `web/static/css/` and `web/static/js/` directories are new. Previously all static assets were served from `web/static/` root or `mockups/`.
