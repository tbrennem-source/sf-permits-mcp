# Design Principals — sfpermits.ai

> The audiences, constraints, and real-world contexts that shape every design decision.

## Primary Audiences

### Amy — Permit Expediter (Power User)

**Who:** Professional who manages 15–90 active permits simultaneously. Uses sfpermits.ai daily as her primary work tool.

**What she needs from the design:**
- Glanceable status: red/amber/green dots tell her where to focus before reading a word
- Dense data that doesn't feel cluttered — monospace values in clean rows
- Keyboard-first interaction (/ to search, arrow keys in dropdowns)
- Fast page loads — she's checking 20+ permits in a morning session
- Watched property list with priority sorting (needs-attention first)

**Design implications:**
- Data rows must scan vertically — label left, value right, status dot far right
- No unnecessary animation delays on repeat visits (reveals fire once, not on every nav)
- Search dropdown shows watched properties on focus (no typing needed)
- Portfolio view supports 90+ items without pagination lag

### Homeowner — First-Time Visitor

**Who:** San Francisco homeowner planning a renovation. Found sfpermits.ai via search or word-of-mouth. No permit expertise.

**What they need from the design:**
- Immediate value proposition — understand what this site does in 5 seconds
- The search bar is the entire product. Make it the first thing they see and use
- Results that explain themselves — no permit jargon without context
- Reassurance: "this data is from city records" — trust signals without being heavy
- Mobile-optimized (they're on their phone, not a work desktop)

**Design implications:**
- Landing hero is ultra-clear: one headline, one search bar, nothing else above the fold
- Example addresses lower the barrier to first interaction
- Search results include plain-English descriptions alongside permit codes
- Ghost CTAs don't pressure — they invite ("Full property intelligence →")

### Architect — Technical Professional

**Who:** Licensed architect who needs accurate permit data for client projects. Expects density and precision.

**What they need from the design:**
- Permit numbers, dates, and routing data must be visible without expanding/clicking
- Entity network data (who worked on what) is a primary use case, not a nice-to-have
- Plan analysis results must feel credible — EPR checks with clear pass/fail
- They'll compare this data against DBI's own systems — accuracy is the design

**Design implications:**
- Monospace data presentation feels authoritative (matches terminal/DBI output)
- No rounding or approximation of numbers — show exact values
- Station routing progress shows all stations, not just a summary
- Entity profiles show permit counts, roles, and network connections

### Admin — Site Operator (Tim + Team)

**Who:** Internal team managing the platform, reviewing feedback, monitoring costs.

**What they need from the design:**
- Tables that are scannable at 1200px width
- Quick access to metrics, costs, feedback, pipeline health
- Same visual language as public site (not a separate admin "skin")
- Destructive actions (delete, override) must be visually distinct but not alarming

**Design implications:**
- Admin container is 1200px (wider than public 1000px) for table room
- Same obsidian palette, glass cards, mono/sans split
- Action buttons use the glass treatment; destructive variants show red on hover
- Admin nav may have more links than public nav

---

## Device Matrix

| Device | Viewport | Priority | Notes |
|--------|----------|----------|-------|
| Desktop (primary) | 1280–1920px | P0 | Where Amy works all day |
| Mobile phone | 375–414px | P0 | Where homeowners first arrive |
| Tablet | 768–1024px | P1 | iPad at a job site |
| Large desktop | 1920px+ | P2 | Content stays centered at max-width, doesn't stretch |
| Phone landscape | 667×375px | P3 | Uncommon but shouldn't break |

**PWA support:** The site is installable (manifest.json, service worker). Design must work in standalone PWA mode (no browser chrome).

---

## Accessibility Floor

**Target: WCAG 2.1 AA**

| Requirement | Our approach |
|-------------|--------------|
| Color contrast 4.5:1 (text) | `--text-primary` on `--obsidian` = 15.4:1. `--text-secondary` on `--obsidian` = 5.2:1. `--accent` on `--obsidian` = 9.8:1. All pass AA. |
| Color contrast 3:1 (large text) | All heading sizes pass with weight 300. |
| Don't rely on color alone | Status always has dot + text label, never color alone |
| Focus indicators | Teal focus ring (`box-shadow: 0 0 0 3px var(--accent-ring)`) on all interactive elements |
| Keyboard navigation | Tab order follows visual order. / shortcut for search. Escape closes dropdowns. |
| Motion sensitivity | `prefers-reduced-motion` media query disables animations (ambient glow, reveals, count-up) |
| Screen reader | Semantic HTML (headings, landmarks, lists). Status dots have `title` attributes. |

**Reduced motion implementation:**
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

---

## Performance Constraints

| Metric | Target | Why |
|--------|--------|-----|
| First Contentful Paint | < 1.5s | Amy loads 20+ pages per session |
| Largest Contentful Paint | < 2.5s | Hero headline on landing |
| Cumulative Layout Shift | < 0.1 | Reveal animations must not cause CLS |
| Total JS bundle | < 50KB | HTMX (~14KB) + intersection observer + search logic |
| Total CSS | < 30KB | Single design-system.css + page-specific inline |
| Google Fonts | 2 families, 4 weights total | Already optimized with `display=swap` |

**No CSS frameworks.** No Tailwind, no Bootstrap. The design system IS the framework.

**No JS frameworks.** HTMX for interactivity, vanilla JS for observers and search. No React, no Vue.

---

## Content Voice

The design voice matches the data voice:

| Attribute | In design | In copy |
|-----------|-----------|---------|
| Precise | Exact spacing tokens, no eyeballing | "174 days average" not "about 6 months" |
| Understated | Ghost buttons, subtle borders | "View report →" not "GET YOUR REPORT NOW!" |
| Authoritative | Monospace data, clean rows | "1,137,816 permits tracked" — let the number speak |
| Helpful | Clear labels, example addresses | "or try an example" — lower the barrier |

---

## Design Decision Authority

| Decision type | Who decides | How |
|---------------|-------------|-----|
| Palette, type, spacing tokens | Tim (via Design Canon) | Locked. Agents cannot change. |
| Component patterns | Design Tokens Bible | Agents follow. Propose changes via PR. |
| Page layout for new pages | Agent follows nearest archetype | Propose in CHECKCHAT if no archetype fits. |
| Responsive breakpoint behavior | Agent follows mobile rules in Tokens Bible | Must test at 375px and 768px. |
| Animation timing/easing | Agents match existing patterns | Do not invent new easings or durations. |
| New component needed | Agent proposes in CHECKCHAT | Tim approves before it enters Tokens Bible. |
