# Design Spec — sfpermits.ai Obsidian Design System

**This file is the external truth for visual design. Agents READ this, never WRITE it.**
**Updated only by Tim or with Tim's explicit approval.**

---

## 1. Foundation

All pages MUST use the Obsidian design system. No exceptions.

### How to apply Obsidian to any page:
```html
{% include "fragments/head_obsidian.html" %}     <!-- in <head> -->
<body class="obsidian">                          <!-- on body tag -->
<div class="obs-container">                      <!-- wraps all content -->
```

### Core CSS file
`web/static/design-system.css` — the single source of truth for tokens and components.

---

## 2. Tokens (DO NOT hardcode hex values — use these variables)

### Colors
| Token | Value | Use |
|-------|-------|-----|
| `--bg-deep` | #0B0F19 | Page background |
| `--bg-surface` | #131825 | Card backgrounds |
| `--bg-elevated` | #1A2035 | Input backgrounds, hover states |
| `--bg-glass` | rgba(255,255,255, 0.04) | Subtle hover fills |
| `--text-primary` | #E8ECF4 | Body text, headings |
| `--text-secondary` | #8B95A8 | Labels, muted text |
| `--text-tertiary` | #5A6478 | Placeholders, disabled |
| `--signal-cyan` | #22D3EE | Primary accent, links, active states |
| `--signal-blue` | #60A5FA | Hover accent |
| `--signal-green` | #34D399 | Success, healthy, on-track |
| `--signal-amber` | #FBBF24 | Warning, at-risk |
| `--signal-red` | #F87171 | Error, critical, high-risk |

### Typography
| Element | Font | Weight | Size |
|---------|------|--------|------|
| h1 | `var(--font-display)` JetBrains Mono | 700 | `var(--text-2xl)` |
| h2 | `var(--font-display)` JetBrains Mono | 600 | `var(--text-xl)` |
| h3 | `var(--font-display)` JetBrains Mono | 600 | `var(--text-lg)` |
| Body | `var(--font-body)` IBM Plex Sans | 400 | `var(--text-base)` |
| Labels | `var(--font-body)` IBM Plex Sans | 600 | `var(--text-sm)`, uppercase, letter-spacing 0.05em |
| Code/data | `var(--font-mono)` JetBrains Mono | 400 | `var(--text-sm)` |

### Spacing
Use `var(--space-N)` tokens: 1=4px, 2=8px, 3=12px, 4=16px, 6=24px, 8=32px, 10=40px, 12=48px, 16=64px.

Minimum spacing between content sections: `var(--space-6)` (24px).
Minimum padding inside cards: `var(--space-6)` (24px).

---

## 3. Layout Rules

### Content centering (MANDATORY)
Every page wraps content in `.obs-container`:
- `max-width: var(--content-max)` (1400px)
- `margin: 0 auto`
- `padding: 0 var(--space-6)` (24px sides)

Content must NEVER be flush-left. Content must NEVER span full viewport width (except header background colors).

### Card containers (MANDATORY)
Every distinct content section wraps in `.glass-card`:
- `background: var(--bg-surface)`
- `border: var(--card-border)` — 1px solid rgba(255,255,255, 0.06)
- `border-radius: var(--card-radius)` — 12px
- `box-shadow: var(--card-shadow)`
- `backdrop-filter: blur(8px)`
- Padding: `var(--space-6)` minimum

Sections that need cards: search areas, data displays, form groups, stat blocks, action button groups, tables.

### Grid patterns
- 2-column: `grid-template-columns: 1fr 1fr` at 640px+, stack on mobile
- 3-column: `grid-template-columns: repeat(3, 1fr)` at 768px+, stack on mobile
- Gap: `var(--space-4)` (16px) minimum

---

## 4. Navigation Rules

### Desktop (>768px)
- Sticky header with `backdrop-filter: blur(12px)`
- Logo left, nav items right
- Max 5-6 visible badge items
- Additional items in "More" or admin dropdown
- Badge style: `var(--text-sm)`, `var(--bg-elevated)` background, rounded pill shape

### Mobile (<=768px)
- Hamburger menu icon (3 lines)
- Logo left, hamburger right
- Tap hamburger → slide-down panel with nav items stacked vertically
- Each nav item: full-width, 48px min-height, left-aligned text
- Close on tap outside or second hamburger tap

### NEVER
- Never more than 6 items visible in the desktop nav row
- Never let nav items wrap to a second line
- Never use text links smaller than `var(--text-sm)` for navigation

---

## 5. Component Patterns

### Buttons
- Primary: `.obsidian-btn .obsidian-btn-primary` — gradient background, white text
- Outline: `.obsidian-btn .obsidian-btn-outline` — transparent, border, muted text
- Min height: 44px desktop, 48px mobile
- Always `font-weight: 600`

### Inputs
- `.obsidian-input` — elevated background, subtle border, cyan focus ring
- Min height: 44px desktop, 48px mobile (prevents iOS zoom)
- Placeholder: `var(--text-tertiary)`

### Status badges
- Severity: CRITICAL (red bg), HIGH (amber bg), MEDIUM (yellow bg), LOW (blue bg), GREEN (green bg)
- Format: small rounded pill, uppercase text, `var(--text-xs)`
- Use with permit status, health tiers, risk scores

### Data tables
- Wrap in `.glass-card`
- Header row: `var(--text-secondary)`, uppercase, `var(--text-xs)`, `var(--font-body)`
- Data rows: `var(--text-primary)`, `var(--text-sm)`
- Row hover: `var(--bg-elevated)` background
- Alternating row colors: NO (use hover instead)
- Border between rows: `1px solid rgba(255,255,255, 0.04)`

### Stat blocks
- Use `.stat-block` class
- Number: `var(--font-display)`, `var(--text-2xl)`, `var(--signal-cyan)`
- Label: `var(--text-sm)`, uppercase, `var(--text-secondary)`

### Empty states
- Center text in a `.glass-card`
- Muted text explaining what will appear here
- Optional CTA button

---

## 6. Page-Specific Patterns

### Dashboard (authenticated home)
- Search bar in a `.glass-card` at the top
- Quick action buttons as `.obsidian-btn-outline` in a row/grid below search
- Recent items as small `.glass-card` chips with address + date
- Watched properties summary cards (when available)
- Stats bar at bottom with `.stat-block` components

### Detail page (property report, analysis results)
- Section headers as h2 with `var(--font-display)`
- Each section in its own `.glass-card`
- Risk/severity badges inline with section titles
- Data grids for permit lists, inspection tables
- Sidebar (desktop) or stacked (mobile) for metadata

### Form page (upload, settings, account)
- Form wrapped in `.glass-card`
- Labels above inputs, uppercase, muted
- Submit button full-width at bottom of card
- Validation errors: `var(--signal-red)` text below input

### Admin page (ops, costs, metrics)
- Tab navigation at top (horizontal pills)
- Each tab content in `.glass-card`
- Data tables with sort indicators
- Status badges for pipeline health, job status
- Filters row above tables

---

## 7. Responsive Breakpoints

| Breakpoint | Behavior |
|-----------|----------|
| <375px | Single column, full-width cards, 16px padding |
| 375-768px | Single column, cards with 16px padding, hamburger nav |
| 768-1024px | 2-column grids start, badge nav visible |
| 1024px+ | Full desktop layout, 3-column grids, 32px padding |

### HARD RULES
- No horizontal scroll at any viewport width. EVER.
- Touch targets minimum 44px on mobile.
- Inputs minimum 16px font-size on mobile (prevents iOS zoom).

---

## 8. Scoring Rubric (for Vision QA)

### 5/5 EXCELLENT
Content centered in obs-container. Every section in glass-card. JetBrains Mono headings, IBM Plex Sans body. Nav clean on one line. Adequate spacing (24px+). Dark theme consistent. Professional, polished.

### 4/5 GOOD
Centered, cards present, good spacing. Minor inconsistencies (one section missing card, slightly off font). Nav works cleanly.

### 3/5 MEDIOCRE
Some centering but inconsistent. Some cards, some raw sections. Mixed fonts. Nav crowded. Looks like a dev tool.

### 2/5 POOR
Mostly flush-left or full-width. Few cards. Nav overflows/wraps. Large unstyled sections. Looks unfinished.

### 1/5 BROKEN
No centering, no cards, nav broken, raw HTML, wrong theme.

### AUTOMATIC FAIL (score 1)
- Content flush left with no centering container
- Nav items wrapping to second line
- No dark theme
- Raw unstyled HTML elements visible
- Horizontal scroll present

---

## 9. File References

| File | Purpose |
|------|---------|
| `web/static/design-system.css` | Token definitions + component classes |
| `web/templates/fragments/head_obsidian.html` | Include fragment for <head> |
| `web/templates/fragments/nav.html` | Shared navigation bar |
| `web/templates/landing.html` | Reference implementation (best current page) |
| `design-spec.md` | THIS FILE — the external truth |
| `qa-results/goldens/` | Golden screenshots (populated after v5 design session) |

---

*This spec will be updated after the v5 golden design session with Tim.*
