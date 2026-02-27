# Design Tokens Bible — sfpermits.ai

> The agent-facing reference. Paste relevant sections into agent prompts verbatim.
> When creating or modifying ANY template, this document is the authority.

## Quick Reference for Agents

**READ FIRST:** `docs/DESIGN_CANON.md` for the "why." This document is the "what."

**The rule:** If a CSS property isn't documented here, check the v5 mockup (`web/static/landing-v5.html`). If it's not there either, keep it minimal and ask.

---

## 1. Color Palette

### Backgrounds

```css
:root {
  --obsidian:       #0a0a0f;   /* page background — 90% of everything */
  --obsidian-mid:   #12121a;   /* card/surface background */
  --obsidian-light: #1a1a26;   /* elevated elements (inputs, dropdowns, modals) */
  --glass:          rgba(255, 255, 255, 0.04);  /* glassmorphism tint */
  --glass-border:   rgba(255, 255, 255, 0.06);  /* card/container borders */
  --glass-hover:    rgba(255, 255, 255, 0.10);  /* border on hover */
}
```

### Text

```css
:root {
  --text-primary:   rgba(255, 255, 255, 0.92);  /* headings, data values, primary content */
  --text-secondary: rgba(255, 255, 255, 0.55);  /* body copy, descriptions, labels */
  --text-tertiary:  rgba(255, 255, 255, 0.30);  /* placeholders, hints, disabled text */
  --text-ghost:     rgba(255, 255, 255, 0.15);  /* wordmarks, footers, barely-there text */
}
```

### Accent & Signal

```css
:root {
  --accent:       #5eead4;                       /* THE brand color — links, focus, active */
  --accent-glow:  rgba(94, 234, 212, 0.08);     /* subtle teal glow for hover/focus bg */
  --accent-ring:  rgba(94, 234, 212, 0.30);     /* focus ring border color */

  /* Semantic signal colors — ONLY for their semantic purpose */
  --signal-green: #34d399;   /* on track, success, approved — text */
  --signal-amber: #fbbf24;   /* warning, stalled, pending — text */
  --signal-red:   #f87171;   /* alert, violation, complaint — text */
  --signal-blue:  #60a5fa;   /* informational, premium badge — text */

  /* Higher-saturation variants for 6px status dots (legibility at small sizes) */
  --dot-green: #22c55e;
  --dot-amber: #f59e0b;
  --dot-red:   #ef4444;
}
```

### Do NOT use

- No other colors. No gradients on backgrounds. No brand blues/purples.
- The only gradient allowed is the ambient hero glow (landing page only).
- Signal colors are never used decoratively — only for status semantics.

---

## 2. Typography

### Font Stacks

```css
:root {
  --mono: 'JetBrains Mono', ui-monospace, 'Cascadia Code', monospace;
  --sans: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
```

**Google Fonts import** (must appear in `<head>`):
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
```

### Font Role Assignment

| Element | Font | Weight | Example |
|---------|------|--------|---------|
| Hero headline | `--sans` | 300 | "Permit intelligence, distilled" |
| Page titles (h1, h2) | `--sans` | 300–400 | "Timeline Estimation" |
| Card headings (h3, h4) | `--sans` | 400–500 | "Active Permits" |
| Wordmark / logo | `--mono` | 300, letter-spacing 0.35em, uppercase | "SFPERMITS.AI" |
| Section labels | `--mono` | 400, uppercase, letter-spacing 0.06em | "RECENT", "WATCHING" |
| Data values (numbers, addresses, permits) | `--mono` | 300–400 | "487 Noe St", "$125,000", "202401015555" |
| Status text | `--mono` | 400 | "3 in review", "BLDG ✓" |
| Body copy / descriptions | `--sans` | 300–400 | "Station-sum model from real routing data." |
| Labels / captions | `--sans` | 400 | "Active permits", "Routing progress" |
| Navigation links | `--sans` | 400 | "Search", "Methodology" |
| Buttons / CTAs | `--mono` | 300–400 | "Full property intelligence →" |
| Form inputs / placeholders | `--mono` | 300 | "Search any SF address" |
| Badge text | `--mono` | 400 | "Commercial", "Kitchen remodel" |
| Timestamps / metadata | `--mono` | 300 | "Feb 26, 2026", "Updated nightly" |

**The split:** `--sans` = anything you'd READ (headlines, prose, labels). `--mono` = anything that IS DATA (numbers, addresses, codes, inputs, timestamps, badges, CTAs, wordmark).

### Type Scale (fluid)

```css
:root {
  --text-xs:  clamp(0.65rem, 0.6rem + 0.2vw, 0.75rem);   /* 10–12px: kbd hints, micro labels */
  --text-sm:  clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem);  /* 12–14px: captions, badges, meta */
  --text-base: clamp(0.8125rem, 0.75rem + 0.3vw, 1rem);   /* 13–16px: body copy, labels */
  --text-lg:  clamp(0.875rem, 0.8rem + 0.4vw, 1.125rem);  /* 14–18px: card titles, nav */
  --text-xl:  clamp(1.125rem, 1rem + 0.5vw, 1.5rem);      /* 18–24px: section headings */
  --text-2xl: clamp(1.5rem, 1.2rem + 1.2vw, 2.5rem);      /* 24–40px: page titles */
  --text-3xl: clamp(1.875rem, 1.5rem + 1.8vw, 3.75rem);   /* 30–60px: hero headline */
}
```

---

## 3. Spacing

```css
:root {
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
  --space-24: 96px;
  --space-32: 128px;
}
```

**Spacing rules:**
- Between sections: `--space-24` to `--space-32` (96–128px)
- Between cards in a group: `--space-6` to `--space-8` (24–32px)
- Card internal padding: `--space-6` to `--space-8` (24–32px)
- Between label and value: `--space-2` to `--space-3` (8–12px)
- Inline element gaps: `--space-2` to `--space-3` (8–12px)

---

## 4. Layout

### Containers

```css
/* Public pages — focused reading width */
.obs-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);  /* 24px sides */
}

/* Admin pages — wider for tables */
.obs-container-wide {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}
```

### Border Radius

```css
:root {
  --radius-sm:  6px;   /* badges, small chips */
  --radius-md:  12px;  /* cards, inputs, dropdowns */
  --radius-lg:  16px;  /* modals, large containers */
  --radius-full: 9999px; /* pills, status dots */
}
```

---

## 5. Components

Each component includes CSS + copy-paste HTML. Agents: use these exactly.

### Glass Card

The primary content container across all pages.

```html
<div class="glass-card">
  <h3>Card Title</h3>
  <p>Card content goes here.</p>
</div>
```

```css
.glass-card {
  background: var(--obsidian-mid);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: var(--space-8);
  transition: border-color 0.3s;
}
.glass-card:hover {
  border-color: var(--glass-hover);
}
```

### Search Input

```html
<div class="search-bar">
  <input type="text" class="search-input" placeholder="Search any SF address" autocomplete="off">
  <span class="kbd-hint">/</span>
  <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
</div>
```

```css
.search-input {
  width: 100%;
  padding: 16px 22px;
  padding-right: 50px;
  font-family: var(--mono);
  font-size: 14px;
  font-weight: 300;
  color: var(--text-primary);
  background: var(--glass);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  outline: none;
  transition: border-color 0.4s, background 0.4s, box-shadow 0.4s;
}
.search-input::placeholder {
  color: var(--text-tertiary);
  font-weight: 300;
}
.search-input:focus {
  border-color: var(--accent-ring);
  background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 0 40px var(--accent-glow);
}
```

### Ghost Button (Primary CTA)

```html
<a href="/report" class="ghost-cta">Full property intelligence →</a>
```

```css
.ghost-cta {
  font-family: var(--mono);
  font-size: var(--text-sm);
  font-weight: 300;
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
  padding-bottom: 1px;
  border-bottom: 1px solid transparent;
  transition: color 0.3s, border-color 0.3s;
  letter-spacing: 0.04em;
}
.ghost-cta:hover {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
/* Always include arrow suffix in content: "View report →" */
```

### Action Button (Secondary — forms, uploads, destructive)

For functional actions that need more affordance than a ghost link (save, upload, delete):

```html
<button class="action-btn">Upload plans</button>
<button class="action-btn action-btn--danger">Delete</button>
```

```css
.action-btn {
  font-family: var(--mono);
  font-size: var(--text-sm);
  font-weight: 400;
  color: var(--text-secondary);
  background: var(--glass);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 8px 16px;
  cursor: pointer;
  transition: border-color 0.3s, color 0.3s, background 0.3s;
}
.action-btn:hover {
  border-color: var(--glass-hover);
  color: var(--text-primary);
  background: var(--obsidian-light);
}
/* Destructive variant */
.action-btn--danger:hover {
  border-color: rgba(248, 113, 113, 0.3);
  color: var(--signal-red);
}
```

### Status Badge

```html
<span class="status-dot status-dot--green" title="On track"></span>
<span class="status-text--green">3 in review</span>

<span class="status-dot status-dot--amber" title="Stalled 12 days"></span>
<span class="status-text--amber">PPC pending</span>

<span class="status-dot status-dot--red" title="2 active complaints"></span>
<span class="status-text--red">2 complaints</span>
```

```css
/* Dots use higher-saturation variants for legibility at 6px */
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  display: inline-block;
}
.status-dot--green  { background: var(--dot-green); }
.status-dot--amber  { background: var(--dot-amber); }
.status-dot--red    { background: var(--dot-red); }

/* Text uses standard signal colors */
.status-text--green  { color: var(--signal-green); }
.status-text--amber  { color: var(--signal-amber); }
.status-text--red    { color: var(--signal-red); }
```

### Type Badge / Chip

```html
<span class="chip">Commercial</span>
<span class="chip">Kitchen remodel</span>
```

```css
.chip {
  font-family: var(--mono);
  font-size: var(--text-xs);
  font-weight: 400;
  color: var(--text-tertiary);
  background: var(--glass);
  border: 1px solid var(--glass-border);
  padding: 1px 7px;
  border-radius: 3px;
  white-space: nowrap;
}
```

### Data Row (key-value pairs)

```html
<div class="data-row">
  <span class="data-row__label">Active permits</span>
  <span class="data-row__value status-text--green">3 in review</span>
</div>
<div class="data-row">
  <span class="data-row__label">Est. remaining</span>
  <span class="data-row__value status-text--amber">4–7 months</span>
</div>
```

```css
.data-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid var(--glass-border);
}
.data-row__label {
  font-family: var(--sans);
  font-size: var(--text-base);
  color: var(--text-secondary);
}
.data-row__value {
  font-family: var(--mono);
  font-size: var(--text-sm);
  color: var(--text-primary);
}
```

### Stat Counter

```html
<div class="stat-item">
  <div class="stat-number">1,137,816</div>
  <div class="stat-label">Permits tracked</div>
</div>
```

```css
.stat-number {
  font-family: var(--mono);
  font-size: clamp(22px, 3vw, 36px);
  font-weight: 300;
  line-height: 1;
  color: var(--text-primary);
}
.stat-label {
  font-family: var(--sans);
  font-size: var(--text-sm);
  font-weight: 400;
  color: var(--text-tertiary);
  margin-top: var(--space-2);
}
```

### Progress Bar

```html
<div class="progress-label">
  <span>Plan review</span>
  <span>5 / 8 stations</span>
</div>
<div class="progress-track">
  <div class="progress-fill" style="width: 62%"></div>
</div>
```

```css
.progress-track {
  height: 2px;
  background: var(--glass);
  border-radius: 1px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), rgba(94, 234, 212, 0.4));
  border-radius: 1px;
  transition: width 1.6s cubic-bezier(0.16, 1, 0.3, 1);
}
```

### Dropdown

```css
.dropdown {
  background: var(--obsidian-mid);
  border: 1px solid var(--glass-border);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  overflow-y: auto;
  max-height: 380px;
  scrollbar-width: thin;
  scrollbar-color: var(--glass-border) transparent;
}
.dropdown__item {
  padding: 9px 22px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: background 0.12s;
}
.dropdown__item:hover {
  background: var(--glass);
}
.dropdown__label {
  font-family: var(--mono);
  font-size: var(--text-xs);
  font-weight: 400;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  padding: 10px 22px 4px;
}
```

### Section Divider

```css
.section-divider {
  border: none;
  border-top: 1px solid var(--glass-border);
  margin: 0;
}
```

### Skeleton Screen (loading placeholder)

Use instead of spinners. Skeleton shapes mirror the content they replace.

```html
<!-- Skeleton for a data row -->
<div class="skeleton-row">
  <div class="skeleton skeleton--text" style="width: 120px;"></div>
  <div class="skeleton skeleton--text" style="width: 80px;"></div>
</div>

<!-- Skeleton for a card -->
<div class="glass-card">
  <div class="skeleton skeleton--heading" style="width: 60%;"></div>
  <div class="skeleton skeleton--text" style="width: 100%; margin-top: 12px;"></div>
  <div class="skeleton skeleton--text" style="width: 85%; margin-top: 8px;"></div>
</div>
```

```css
.skeleton {
  background: var(--glass);
  border-radius: var(--radius-sm);
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}
.skeleton--heading { height: 20px; }
.skeleton--text { height: 12px; }
.skeleton--dot { width: 6px; height: 6px; border-radius: var(--radius-full); }
.skeleton-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 0; border-bottom: 1px solid var(--glass-border);
}
@keyframes skeleton-pulse {
  0%, 100% { opacity: 0.04; }
  50% { opacity: 0.08; }
}
```

### Table

For admin dashboards, portfolio views, and any structured data with columns.

```html
<table class="obs-table">
  <thead>
    <tr>
      <th></th>
      <th>Address</th>
      <th>Type</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="status-dot status-dot--green"></span></td>
      <td class="obs-table__mono">487 Noe St</td>
      <td>Kitchen remodel</td>
      <td class="obs-table__mono status-text--green">On track</td>
    </tr>
  </tbody>
</table>
```

```css
.obs-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--sans);
  font-size: var(--text-sm);
}
.obs-table th {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);  /* tertiary fails WCAG AA at small sizes */
  text-align: left;
  padding: 6px var(--space-3);
  border-bottom: 1px solid var(--glass-border);
}
.obs-table td {
  padding: 9px var(--space-3);
  color: var(--text-secondary);
  border-bottom: 1px solid var(--glass-border);
}
.obs-table tr {
  transition: background 0.12s;
  cursor: pointer;
}
.obs-table tr:hover {
  background: var(--glass);
}
.obs-table__mono {
  font-family: var(--mono);
  font-weight: 300;
  color: var(--text-primary);
}
/* Address goes teal on hover */
.obs-table tr:hover .obs-table__mono:first-of-type {
  color: var(--accent);
}
/* Mobile: horizontal scroll with shadow hint */
@media (max-width: 768px) {
  .obs-table-wrap {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin: 0 calc(-1 * var(--space-4));
    padding: 0 var(--space-4);
  }
  .obs-table { min-width: 600px; }
}
```

### Form Elements

#### Text Input (non-search)

```html
<label class="form-label" for="project-cost">Estimated cost</label>
<input class="form-input" id="project-cost" type="text" placeholder="e.g. $85,000">
```

```css
.form-label {
  display: block;
  font-family: var(--mono);
  font-size: var(--text-xs);
  font-weight: 400;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}
.form-input {
  width: 100%;
  padding: 10px 14px;
  font-family: var(--mono);
  font-size: var(--text-sm);
  font-weight: 300;
  color: var(--text-primary);
  background: var(--glass);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  outline: none;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.form-input:focus {
  border-color: var(--accent-ring);
  box-shadow: 0 0 0 3px rgba(94, 234, 212, 0.1);
}
```

#### Checkbox

```html
<label class="form-check">
  <input type="checkbox" class="form-check__input">
  <span class="form-check__box"></span>
  <span class="form-check__label">Include structural engineer letter</span>
</label>
```

```css
.form-check {
  display: flex; align-items: center; gap: var(--space-3);
  cursor: pointer; padding: 6px 0;
}
.form-check__input { display: none; }
.form-check__box {
  width: 16px; height: 16px; border-radius: 3px; flex-shrink: 0;
  border: 1px solid var(--glass-border);
  background: var(--glass);
  transition: border-color 0.2s, background 0.2s;
  display: flex; align-items: center; justify-content: center;
}
.form-check__input:checked + .form-check__box {
  border-color: var(--accent);
  background: var(--accent-glow);
}
.form-check__input:checked + .form-check__box::after {
  content: '✓'; font-size: 10px; color: var(--accent);
}
.form-check__label {
  font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary);
}
```

#### Toggle Switch

```html
<label class="form-toggle">
  <input type="checkbox" class="form-toggle__input">
  <span class="form-toggle__track"><span class="form-toggle__thumb"></span></span>
  <span class="form-toggle__label">Email notifications</span>
</label>
```

```css
.form-toggle {
  display: flex; align-items: center; gap: var(--space-3);
  cursor: pointer; padding: 6px 0;
}
.form-toggle__input { display: none; }
.form-toggle__track {
  width: 28px; height: 14px; border-radius: 7px; flex-shrink: 0;
  background: var(--glass-border);
  position: relative; transition: background 0.2s;
}
.form-toggle__input:checked + .form-toggle__track {
  background: var(--accent);
}
.form-toggle__thumb {
  width: 10px; height: 10px; border-radius: var(--radius-full);
  background: var(--text-tertiary);
  position: absolute; top: 2px; left: 2px;
  transition: left 0.2s, background 0.2s;
}
.form-toggle__input:checked + .form-toggle__track .form-toggle__thumb {
  left: 16px; background: var(--obsidian);
}
.form-toggle__label {
  font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary);
}
```

#### Select / Dropdown Input

```html
<label class="form-label" for="permit-type">Permit type</label>
<select class="form-select" id="permit-type">
  <option value="">Select...</option>
  <option>Alterations</option>
  <option>New construction</option>
  <option>Demolition</option>
</select>
```

```css
.form-select {
  width: 100%;
  padding: 10px 14px;
  font-family: var(--mono);
  font-size: var(--text-sm);
  font-weight: 300;
  color: var(--text-primary);
  background: var(--glass);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  outline: none;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.3)' stroke-width='2' xmlns='http://www.w3.org/2000/svg'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 14px center;
  cursor: pointer;
  transition: border-color 0.3s;
}
.form-select:focus {
  border-color: var(--accent-ring);
}
```

#### File Upload

```html
<label class="form-upload">
  <input type="file" class="form-upload__input">
  <span class="form-upload__zone">
    <span class="form-upload__icon">↑</span>
    <span class="form-upload__text">Drop plans here or click to browse</span>
    <span class="form-upload__hint">PDF up to 250MB · EPR format recommended</span>
  </span>
</label>
```

```css
.form-upload__input { display: none; }
.form-upload__zone {
  display: flex; flex-direction: column; align-items: center;
  gap: var(--space-2); padding: var(--space-8) var(--space-6);
  border: 1px dashed var(--glass-border); border-radius: var(--radius-md);
  cursor: pointer; text-align: center;
  transition: border-color 0.3s, background 0.3s;
}
.form-upload__zone:hover {
  border-color: var(--accent-ring);
  background: var(--accent-glow);
}
.form-upload__icon {
  font-size: 20px; color: var(--text-tertiary);
}
.form-upload__text {
  font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary);
}
.form-upload__hint {
  font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary);
}
```

### Toast / Notification

Transient feedback for user actions. Supports an optional undo/action link. Auto-dismisses after 5 seconds unless hovered.

```html
<div class="toast toast--success" role="status" aria-live="polite">
  <span class="toast__icon">✓</span>
  <span class="toast__message">Watch added</span>
  <a href="#" class="toast__action">Undo</a>
  <button class="toast__dismiss" aria-label="Dismiss">×</button>
</div>

<!-- Variants -->
<div class="toast toast--error">...</div>
<div class="toast toast--info">...</div>
```

```css
.toast {
  position: fixed;
  top: var(--space-6);
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 10px var(--space-5);
  background: var(--obsidian-mid);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  backdrop-filter: blur(12px);
  animation: toast-in 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  max-width: min(420px, calc(100vw - 32px));
}
.toast--success { border-left: 2px solid var(--signal-green); }
.toast--error   { border-left: 2px solid var(--signal-red); }
.toast--info    { border-left: 2px solid var(--signal-blue); }
.toast__icon {
  font-size: var(--text-sm);
}
.toast--success .toast__icon { color: var(--signal-green); }
.toast--error .toast__icon   { color: var(--signal-red); }
.toast--info .toast__icon    { color: var(--signal-blue); }
.toast__message {
  font-family: var(--sans);
  font-size: var(--text-sm);
  color: var(--text-primary);
}
.toast__action {
  font-family: var(--mono);
  font-size: var(--text-xs);
  color: var(--accent);
  text-decoration: none;
  margin-left: var(--space-2);
  white-space: nowrap;
}
.toast__action:hover { text-decoration: underline; }
.toast__dismiss {
  background: none;
  border: none;
  color: var(--text-tertiary);
  font-size: 16px;
  cursor: pointer;
  padding: 0 0 0 var(--space-2);
  transition: color 0.2s;
}
.toast__dismiss:hover { color: var(--text-primary); }
@keyframes toast-in {
  from { opacity: 0; transform: translateX(-50%) translateY(-12px); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0); }
}
.toast.toast--exit {
  animation: toast-out 0.25s ease-in forwards;
}
@keyframes toast-out {
  to { opacity: 0; transform: translateX(-50%) translateY(-12px); }
}
```

**Behavior:**
- Auto-dismiss after 5 seconds. Pause timer on hover.
- Multiple toasts stack vertically with `var(--space-3)` gap (newest on top).
- Undo action fires callback then dismisses. If no undo, omit `.toast__action`.
- Replaces the existing ad-hoc `.flash` divs in the codebase.

**JavaScript:**
```javascript
function showToast(message, { type = 'success', action, actionLabel = 'Undo', duration = 5000 } = {}) {
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.setAttribute('role', 'status');
  toast.innerHTML = `
    <span class="toast__icon">${type === 'success' ? '✓' : type === 'error' ? '!' : 'i'}</span>
    <span class="toast__message">${message}</span>
    ${action ? `<a href="#" class="toast__action">${actionLabel}</a>` : ''}
    <button class="toast__dismiss" aria-label="Dismiss">×</button>
  `;
  document.body.appendChild(toast);
  let timer = setTimeout(() => dismiss(), duration);
  toast.addEventListener('mouseenter', () => clearTimeout(timer));
  toast.addEventListener('mouseleave', () => { timer = setTimeout(() => dismiss(), duration); });
  toast.querySelector('.toast__dismiss').addEventListener('click', dismiss);
  if (action) toast.querySelector('.toast__action').addEventListener('click', (e) => { e.preventDefault(); action(); dismiss(); });
  function dismiss() { toast.classList.add('toast--exit'); setTimeout(() => toast.remove(), 250); }
}
```

### Modal / Dialog

Confirmation dialogs, mobile nav overlay, and any content that requires focus trapping. Desktop: centered fade. Mobile: slide-up sheet from bottom.

```html
<div class="modal-backdrop" aria-hidden="true">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <div class="modal__header">
      <h3 class="modal__title" id="modal-title">Delete this watch?</h3>
      <button class="modal__close" aria-label="Close">×</button>
    </div>
    <div class="modal__body">
      <p>This will remove 487 Noe St from your watched properties. You can re-add it later.</p>
    </div>
    <div class="modal__footer">
      <button class="action-btn" onclick="closeModal()">Cancel</button>
      <button class="action-btn action-btn--danger" onclick="confirmDelete()">Delete</button>
    </div>
  </div>
</div>
```

```css
/* Backdrop */
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 90;
  background: rgba(0, 0, 0, 0.60);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: backdrop-in 0.2s ease-out;
}
@keyframes backdrop-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

/* Modal — desktop (centered fade) */
.modal {
  background: var(--obsidian-mid);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  max-width: 440px;
  width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  overflow-y: auto;
  animation: modal-fade-in 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes modal-fade-in {
  from { opacity: 0; transform: scale(0.96); }
  to   { opacity: 1; transform: scale(1); }
}
.modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-6) var(--space-6) 0;
}
.modal__title {
  font-family: var(--sans);
  font-size: var(--text-lg);
  font-weight: 400;
  color: var(--text-primary);
  margin: 0;
}
.modal__close {
  background: none;
  border: none;
  color: var(--text-tertiary);
  font-size: 20px;
  cursor: pointer;
  padding: 0;
  transition: color 0.2s;
}
.modal__close:hover { color: var(--text-primary); }
.modal__body {
  padding: var(--space-4) var(--space-6);
  font-family: var(--sans);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}
.modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: 0 var(--space-6) var(--space-6);
}

/* Mobile — slide-up sheet */
@media (max-width: 768px) {
  .modal-backdrop {
    align-items: flex-end;
  }
  .modal {
    max-width: 100%;
    width: 100%;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    max-height: 85vh;
    animation: modal-slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes modal-slide-up {
    from { transform: translateY(100%); }
    to   { transform: translateY(0); }
  }
  .modal__header {
    padding-top: var(--space-5);
  }
  /* Drag handle hint */
  .modal::before {
    content: '';
    display: block;
    width: 32px;
    height: 4px;
    background: var(--glass-hover);
    border-radius: 2px;
    margin: var(--space-3) auto 0;
  }
}
```

**Behavior:**
- `Escape` closes the modal. Backdrop click closes the modal.
- Focus is trapped inside the modal while open. First focusable element receives focus on open.
- On close, return focus to the element that triggered the modal.
- No nested modals (Canon constraint). One modal at a time.

### Print Styles

Property reports and morning briefs are printable. The obsidian palette inverts to white for ink efficiency.

```css
@media print {
  /* Invert palette */
  body {
    background: #fff !important;
    color: #1a1a1a !important;
  }

  /* Hide chrome */
  .nav-float,
  .ambient,
  .toast,
  .modal-backdrop,
  .ghost-cta,
  .action-btn,
  footer,
  .search-bar,
  .kbd-hint { display: none !important; }

  /* Cards become bordered containers */
  .glass-card {
    background: #fff !important;
    border: 1px solid #ddd !important;
    break-inside: avoid;
  }

  /* Text colors for print */
  .data-row__label,
  .obs-table td { color: #555 !important; }
  .data-row__value,
  .obs-table__mono,
  .stat-number { color: #1a1a1a !important; }

  /* Table headers */
  .obs-table th {
    color: #777 !important;
    border-bottom: 1px solid #ccc !important;
  }
  .obs-table tr:hover { background: none !important; }

  /* Status colors stay semantic (they're already high contrast) */
  .status-text--green  { color: #16a34a !important; }
  .status-text--amber  { color: #d97706 !important; }
  .status-text--red    { color: #dc2626 !important; }

  /* Status dots — darker for print */
  .status-dot--green  { background: #16a34a !important; }
  .status-dot--amber  { background: #d97706 !important; }
  .status-dot--red    { background: #dc2626 !important; }

  /* Links show URLs */
  a[href]:not(.ghost-cta)::after {
    content: " (" attr(href) ")";
    font-size: 9px;
    color: #888;
  }

  /* Disable animations */
  .reveal { opacity: 1 !important; transform: none !important; }

  /* Page breaks */
  h2, h3 { break-after: avoid; }
  .glass-card { break-inside: avoid; }

  /* Data freshness footer — keep visible */
  .data-freshness { display: block !important; color: #999 !important; }
}
```

**Rules:**
- Include `@media print` in the base stylesheet, not a separate file.
- Print button (if added) should be a ghost CTA: `Print report →`
- Property reports should fit on A4/Letter. Test with `Ctrl+P` preview.

### Content Patterns

Recurring content blocks used across AI consultations, property reports, and the brief. Agents: use these patterns instead of inventing new layouts.

#### Insight Callout

A left-bordered box highlighting a key finding or recommendation. Semantic color matches the signal type.

```html
<div class="insight insight--amber">
  <div class="insight__label">Things to know</div>
  <div class="insight__body">This permit has been in plan review for 47 days longer than the neighborhood median. Consider contacting the assigned plan checker.</div>
</div>
```

```css
.insight {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-4);
  border-left: 2px solid;
}
.insight--green  { background: rgba(52, 211, 153, 0.06); border-left-color: var(--signal-green); }
.insight--amber  { background: rgba(251, 191, 36, 0.06); border-left-color: var(--signal-amber); }
.insight--red    { background: rgba(248, 113, 113, 0.06); border-left-color: var(--signal-red); }
.insight--info   { background: rgba(96, 165, 250, 0.06); border-left-color: var(--signal-blue); }
.insight__label {
  font-family: var(--mono);
  font-size: var(--text-xs);
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 4px;
}
.insight--green .insight__label  { color: var(--signal-green); }
.insight--amber .insight__label  { color: var(--signal-amber); }
.insight--red .insight__label    { color: var(--signal-red); }
.insight--info .insight__label   { color: var(--signal-blue); }
.insight__body {
  font-family: var(--sans);
  font-size: var(--text-sm);
  font-weight: 300;
  color: var(--text-secondary);
  line-height: 1.5;
}
```

#### Expandable Section

Progressive disclosure for detail-on-demand. Summary visible, detail hidden until clicked.

```html
<details class="expandable">
  <summary class="expandable__summary">
    <span class="expandable__title">Why in-house review?</span>
    <span class="expandable__arrow">▾</span>
  </summary>
  <div class="expandable__body">
    <p>Estimated cost exceeds $50,000 and the project includes structural modifications, triggering mandatory DBI in-house review per Administrative Bulletin 003.</p>
  </div>
</details>
```

```css
.expandable {
  border-bottom: 1px solid var(--glass-border);
}
.expandable__summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) 0;
  cursor: pointer;
  list-style: none;
}
.expandable__summary::-webkit-details-marker { display: none; }
.expandable__title {
  font-family: var(--mono);
  font-size: var(--text-sm);
  font-weight: 400;
  color: var(--text-secondary);
  transition: color 0.2s;
}
.expandable__summary:hover .expandable__title { color: var(--accent); }
.expandable__arrow {
  font-size: 10px;
  color: var(--text-tertiary);
  transition: transform 0.3s;
}
.expandable[open] .expandable__arrow { transform: rotate(180deg); }
.expandable__body {
  padding: 0 0 var(--space-4);
  font-family: var(--sans);
  font-size: var(--text-sm);
  font-weight: 300;
  color: var(--text-secondary);
  line-height: 1.5;
}
```

#### Risk Flag

Compact inline warning for specific risk items in a list or card.

```html
<div class="risk-flag risk-flag--high">
  <span class="risk-flag__dot"></span>
  <span class="risk-flag__text">2 active complaints at this parcel</span>
</div>
```

```css
.risk-flag {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 4px 0;
}
.risk-flag__dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}
.risk-flag--high .risk-flag__dot   { background: var(--dot-red); }
.risk-flag--medium .risk-flag__dot { background: var(--dot-amber); }
.risk-flag--low .risk-flag__dot    { background: var(--dot-green); }
.risk-flag__text {
  font-family: var(--sans);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
```

#### Action Prompt

End-of-section nudge toward the next step. Always a ghost CTA with context.

```html
<div class="action-prompt">
  <span class="action-prompt__context">Based on 3,412 similar permits in your neighborhood</span>
  <a href="/report/3512/001" class="ghost-cta">Full property intelligence →</a>
</div>
```

```css
.action-prompt {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4) 0;
}
.action-prompt__context {
  font-family: var(--sans);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
```

---

## 6. Navigation

### Floating Nav Bar

Hidden at top of landing page. Appears on scroll and on all interior pages.

```css
.nav-float {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  padding: 12px var(--space-6);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(10, 10, 15, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--glass-border);
  transition: opacity 0.4s, transform 0.4s;
}
/* Hidden state (landing hero) */
.nav-float--hidden {
  opacity: 0;
  transform: translateY(-100%);
  pointer-events: none;
}
.nav-float__wordmark {
  font-family: var(--mono);
  font-size: var(--text-xs);
  font-weight: 300;
  letter-spacing: 0.35em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  text-decoration: none;
}
.nav-float__link {
  font-family: var(--sans);
  font-size: var(--text-sm);
  font-weight: 400;
  color: var(--text-secondary);
  text-decoration: none;
  transition: color 0.3s;
}
.nav-float__link:hover {
  color: var(--accent);
}
```

---

## 7. Animation

### Scroll Reveal (apply to all content sections)

```css
.reveal {
  opacity: 0;
  transform: translateY(24px);
  transition: opacity 0.9s cubic-bezier(0.16, 1, 0.3, 1),
              transform 0.9s cubic-bezier(0.16, 1, 0.3, 1);
}
.reveal.visible {
  opacity: 1;
  transform: translateY(0);
}
/* Staggered delays for sibling elements */
.reveal-delay-1 { transition-delay: 0.1s; }
.reveal-delay-2 { transition-delay: 0.2s; }
.reveal-delay-3 { transition-delay: 0.3s; }
.reveal-delay-4 { transition-delay: 0.4s; }
```

**JavaScript observer** (include in base template):
```javascript
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
```

### Ambient Glow (landing page ONLY)

```css
.ambient {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}
.ambient::before {
  content: '';
  position: absolute;
  top: -40%;
  left: -20%;
  width: 80%;
  height: 80%;
  background: radial-gradient(ellipse, rgba(94, 234, 212, 0.03) 0%, transparent 70%);
  animation: drift 25s ease-in-out infinite;
}
@keyframes drift {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(40px, 20px); }
}
```

### Fade In (for staggered hero elements)

```css
@keyframes fadeIn { to { opacity: 1; } }
/* Usage: opacity: 0; animation: fadeIn 2s 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards; */
```

### Hover Transitions

- Card borders: `transition: border-color 0.3s;`
- Links/CTAs: `transition: color 0.3s, border-color 0.3s;`
- Dropdown items: `transition: background 0.12s;`
- Inputs: `transition: border-color 0.4s, background 0.4s, box-shadow 0.4s;`

---

## 8. Responsive Breakpoints

```css
/* Mobile-first. Three tiers: */
@media (max-width: 768px) { /* Tablet and below */ }
@media (max-width: 480px) { /* Phone */ }
```

### What Changes at Each Breakpoint

| Element | Desktop (769px+) | Tablet (481–768px) | Phone (≤480px) |
|---------|-------------------|--------------------|----------------|
| **Container** | max-width 1000px, 24px padding | Fluid, 24px padding | Fluid, 16px padding |
| **Stats row** | 4-column flex | 2×2 grid, dividers hidden | Single column stack |
| **Capability list** | 3-column grid: number · content · stat | Content + stat only (number hidden) | Single column, stat below content |
| **Data rows** | Flex row: label left, value right | Same | Stack: label above value, left-aligned |
| **Cards** | padding 32px | padding 24px | padding 16px |
| **Card grids** (intel panel) | 2–3 columns side by side | 2 columns | Single column stack |
| **Nav** | Floating bar: wordmark + links + avatar | Wordmark + hamburger | Same as tablet |
| **Hero headline** | clamp max (60px) | Mid range (~40px) | clamp min (30px) |
| **Demo panel** | Full width in container | Same | Compact: rows stack, padding reduced |
| **Search dropdown** | max-height 380px | Same | max-height 320px |
| **Admin tables** | Horizontal scroll if needed at 1200px | Horizontal scroll | Horizontal scroll with shadow hints |

### Mobile-Specific Rules

```css
@media (max-width: 768px) {
  .stats-row { flex-wrap: wrap; gap: 24px; justify-content: center; }
  .stat-divider { display: none; }
  .stat-item { flex: 0 0 40%; }
  .cap-item { grid-template-columns: 1fr; gap: 6px; }
  .cap-num { display: none; }
  .demo-body { padding: 20px 16px; }
  .data-row { flex-direction: column; align-items: flex-start; gap: 4px; }
}
@media (max-width: 480px) {
  .stat-item { flex: 0 0 100%; }
  .obs-container { padding: 0 16px; }
}
```

---

## 9. Page Archetypes

### Landing Page (1000px, ambient glow)
Full-viewport hero → stats bar → capability list → demo panel → footer. No nav at top. Ambient glow.

### Search Results (1000px, no ambient)
Nav bar → search input → results list (glass cards). Each result is a data-row card with address, type badge, status dot.

### Property Report (1000px, no ambient)
Nav bar → property header (address, type chip) → data sections in glass cards → related permits list → ghost CTA links.

### Admin Dashboard (1200px, no ambient)
Nav bar → page title → summary stats row → data tables in glass cards → action buttons.

### Auth Pages (1000px, no ambient)
Centered card, wordmark above, minimal form fields, ghost CTA submit.

### Email Templates
Inline CSS only. Use obsidian-mid background, same type hierarchy, teal accent for links. Must render in Gmail/Outlook.

---

## 10. Do / Don't

### DO
- Use CSS custom properties from this document
- Use `var(--mono)` for ALL data/numbers
- Use `var(--sans)` for ALL prose/labels
- Use `clamp()` for font sizes (responsive)
- Use glass-card pattern for content containers
- Use ghost CTAs for navigation actions
- Add `class="reveal"` to content sections
- Test on mobile (375px) and tablet (768px)

### DON'T
- Add colors not in the palette
- Use font-weight above 500 on headings
- Use filled/gradient buttons for primary CTAs
- Add elevation shadows to cards (use border only; `box-shadow` OK for focus rings)
- Use solid background colors on cards (use --obsidian-mid)
- Add ambient glow to non-landing pages
- Import additional fonts
- Use rem/em without clamp() for display text
- Use `!important` (fix specificity instead)

---

## 11. Content Rules

### Action Bias

Every element must pass this test: **"Does this help the user take action or understand what needs attention?"** If not, it doesn't belong.

- No vanity metrics on interior pages. "1.1M permits tracked" is marketing, not intelligence.
- Data earns its place by being contextual. "Based on 3,412 similar permits" next to a timeline estimate = useful. Same number in a stats strip = decoration.
- Empty states are honest. "No urgent actions — your portfolio is healthy" > filling space with charts.
- **First-visit exception:** Anonymous users see the stats strip below the fold on their first visit only.

### Progressive Disclosure

Summary first, detail on demand. This pattern applies everywhere:

- Search dropdown: 3–5 items relevant to your state, not 20 results
- Property intel: 3 permits shown initially, "Show all 12" available
- AI consultation: Opening summary in one sentence, detail cards below
- Routing progress: Simple progress bar with fraction, expand for full station timeline

### Three User States

The interface adapts to who's using it:

| State | Search Dropdown Shows | Hero Subhead |
|-------|----------------------|--------------|
| **Anonymous** | Example addresses (on focus or "try an example" click) | "18.4 million San Francisco government records. One search." |
| **Returning** | Recent searches (3–5) + example addresses | Neutral |
| **Power** | "Needs attention" (red/amber, up to 3) → Recent → "All N watched →" | "{N} properties watched · {M} need attention" |

### Credibility Signals

Credibility belongs in context, not in banners.

- **DO:** "Based on 3,412 similar permits in your neighborhood" (inside a timeline estimate)
- **DON'T:** "Powered by 3.9 million routing records" (in a stats strip)
- **DO:** Data freshness indicator at bottom of data pages: `[green dot] Data as of Feb 26, 2026 · Updated nightly` (JetBrains Mono 11px, ghost color)

### AI Disclosure

Every AI-generated response includes:
1. **Label before:** Sparkle icon + "AI Analysis · Based on public records as of {date}" in accent color, mono 12px
2. **Disclaimer after:** "AI-generated from public records. Not legal advice." in ghost text, 11px

### Empty States

- **No urgent actions:** "All clear — no urgent actions across your portfolio."
- **No permits found:** "No permits found for this address. This could mean no work has been permitted, or the address format doesn't match DBI records." + suggestion
- **No search results:** "No matches — press Enter to search" (inside dropdown)

### Loading States

Use skeleton screens or subtle pulse animations on the content area. No spinners.

---

## 12. Icons

SVG stroke icons only. No filled icons. No emoji in UI chrome (emoji OK in AI-generated content).

```
Stroke width:  1.5 (default), 2.0 (emphasis)
Default color: var(--text-tertiary)
Hover color:   var(--accent) or var(--text-secondary)
Size:          13–16px (inline), 15–18px (buttons/nav)
```

Define SVGs inline. Core set: search, pin, clock, eye, back, menu, close, check, sparkle, user, portfolio, doc, settings.

---

## 13. Anti-Patterns (Never Do These)

| Anti-Pattern | Why | Instead |
|---|---|---|
| Stats strips on interior pages | Vanity metrics don't help users act | Put data in context next to the decision it supports |
| Example prompt chips below search bar | Redundant with intelligent dropdown | Use the dropdown's section system for all suggestions |
| Nav bar on home/hero page | Kills the cinematic single-purpose feel | Keep hero chrome-free. Nav on interior pages. |
| Marketing copy inside the product | Users are already here — don't sell to them | Informational tone, plain language |
| Nested cards > 2 levels | Visual clutter, lost hierarchy | Maximum one card inside another card |
| Bounce/spring animations | Feel cheap, break restrained-premium tone | Use `cubic-bezier(0.16, 1, 0.3, 1)` for everything |
| Loading spinners | Feel anxious, break the calm register | Use `.skeleton` component with pulse animation. Primary use: cache-miss fallback and manual refresh. Pre-computed pages should never show skeletons. |
| Solid divider lines | Too harsh for obsidian | Gradient fades: `linear-gradient(90deg, transparent, rgba(255,255,255,0.06), transparent)` |
| Gradient/filled buttons | No filled or gradient backgrounds on any button | Ghost CTAs for navigation, glass action-btn for functional actions |
| Elevation shadows on cards | Drop shadows break the glass-on-obsidian aesthetic | Use border opacity only. (`box-shadow` IS allowed for focus rings and glow effects.) |

---

## 14. Agent Implementation Checklist

Before shipping any new page or component, verify:

- [ ] **Action bias:** Every element helps the user act or understand what needs attention
- [ ] **Font pairing:** `--sans` for prose/headlines, `--mono` for data/labels/inputs
- [ ] **Colors from system:** All colors come from Section 1. No new hex values.
- [ ] **Ghost CTAs:** No filled/gradient buttons for primary navigation
- [ ] **Progressive disclosure:** Summary first, detail on demand
- [ ] **Mobile tested:** Works at 375px without horizontal scroll
- [ ] **Status colors semantic:** Green/amber/red only for their defined meanings
- [ ] **Scroll reveals added:** `class="reveal"` on content sections
- [ ] **AI disclosure present:** If AI content exists, label + disclaimer are present
- [ ] **Data freshness shown:** If displaying permit data, freshness indicator at bottom
- [ ] **Empty state designed:** What does the user see when there's no data?
- [ ] **Error state designed:** What does the user see when something breaks?
- [ ] **Reduced motion:** `prefers-reduced-motion` disables all animation

---

## 15. Accessibility

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
  .reveal { opacity: 1; transform: none; }
  .ambient { display: none; }
}
```

### Focus Indicators

All interactive elements get a visible focus ring:
```css
:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--accent-ring);
}
```

### Keyboard

- `/` focuses search from anywhere
- `Escape` closes dropdown and blurs
- `Enter` submits search
- Tab order follows visual order
- Status dots always have `title` attributes

---

## 16. File References

| File | Role | Status |
|------|------|--------|
| `web/static/design-system.css` | Production CSS (needs reconciliation) | Outdated — reconcile with these tokens |
| `web/static/landing-v5.html` | Design prototype (source of truth) | Reference |
| `web/templates/fragments/head_obsidian.html` | Shared `<head>` fragment for obsidian pages | Update with token imports |
| `docs/DESIGN_CANON.md` | Aesthetic philosophy | Current |
| `docs/DESIGN_PRINCIPALS.md` | Audiences and constraints | Current |
| `docs/DESIGN_MIGRATION.md` | Template migration manifest | Current |
