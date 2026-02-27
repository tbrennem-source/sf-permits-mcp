# QS7 Terminal 2: CSS Foundation + Public Templates

> Paste this into CC Terminal 2. It spawns 4 agents via Task tool.
> **Merge order: Terminal 2 merges SECOND** (after Terminal 1).

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/landing.html web/templates/search_results_public.html web/templates/results.html web/templates/error.html --quiet
```

Note the baseline violation counts. Each agent's target is 0 violations on their files.

## File Ownership (Terminal 2 ONLY touches these)

| Agent | Files |
|---|---|
| 2A | `web/static/obsidian.css` (NEW), `web/templates/fragments/head_obsidian.html` |
| 2B | `web/templates/landing.html`, `web/templates/search_results_public.html` |
| 2C | `web/templates/results.html`, `web/templates/methodology.html`, `web/templates/about_data.html`, `web/templates/demo.html` |
| 2D | `web/templates/fragments/nav.html`, `web/templates/error.html`, `web/templates/fragments/login_prompt.html` |

**No Python route files.** Terminal 2 is pure frontend. Backend belongs to Terminal 1.

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent 2A: Production CSS + Head Fragment

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Create production obsidian.css from DESIGN_TOKENS.md

### Read First
- docs/DESIGN_TOKENS.md (the ENTIRE file — this is your source of truth)
- web/static/mockups/obsidian-tokens.css (reference implementation from mockups)
- web/templates/fragments/head_obsidian.html (the <head> fragment all templates include)
- web/static/design-system.css (the OLD CSS — understand what it defines so you don't break unmigrated templates)

### Build

**1. Create web/static/obsidian.css**

Extract ALL CSS from DESIGN_TOKENS.md into a single production CSS file. This includes:
- CSS custom properties (:root block with all colors, fonts, spacing, radius)
- All 26 component classes (glass-card, search-input, ghost-cta, action-btn, status-dot, chip, data-row, stat-number, stat-label, progress-track, progress-fill, dropdown, section-divider, skeleton, obs-table, form elements, toast, modal, insight, expandable, risk-flag, action-prompt, tabs, load-more, nav-float, reveal, ambient)
- Responsive breakpoints (@media queries)
- Print styles (@media print)
- Reduced motion (@media prefers-reduced-motion)
- Focus indicators (:focus-visible)
- Keyframe animations (skeleton-pulse, toast-in, toast-out, backdrop-in, modal-fade-in, modal-slide-up, drift, fadeIn)

Structure the file with clear section comments matching DESIGN_TOKENS.md section numbers.

**2. Update web/templates/fragments/head_obsidian.html**

Add the new CSS import BEFORE the old one (so token classes take precedence):
```html
<link rel="stylesheet" href="{{ url_for('static', filename='obsidian.css') }}">
```

Keep the old design-system.css import — unmigrated templates still need it. Both CSS files coexist. The old one will be removed once all templates are migrated.

**3. Do NOT delete or modify web/static/design-system.css** — other agents' templates still reference old classes.

### Verify
The CSS file should be ~400-500 lines. Spot-check: search for every component name from DESIGN_TOKENS.md and verify it has a CSS rule.

### Commit
`feat: obsidian.css production stylesheet from DESIGN_TOKENS.md`
""")
```

---

### Agent 2B: Landing + Search Templates

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Migrate landing.html and search_results_public.html to design tokens

### Read First
- docs/DESIGN_TOKENS.md (full file — your bible)
- web/static/mockups/landing.html (the golden mockup — this is what landing should look like)
- web/static/mockups/search-results.html (golden mockup for search)
- web/templates/landing.html (current — 743 lines, 15 violations)
- web/templates/search_results_public.html (current — 672 lines, 25 violations)

### Build

**For each template:**

1. Replace all inline hex colors with CSS custom properties (`var(--obsidian)`, `var(--text-primary)`, etc.)
2. Replace all font-family declarations with `var(--mono)` or `var(--sans)` per the role assignment table
3. Replace ad-hoc component patterns with token classes:
   - Cards → `glass-card`
   - Buttons → `ghost-cta` or `action-btn`
   - Status indicators → `status-dot` + `status-text--{color}`
   - Data displays → `data-row` with `data-row__label` + `data-row__value`
   - Badges → `chip`
   - Section labels → mono uppercase with `--text-tertiary`
4. Add `class="reveal"` to content sections for scroll animation
5. Verify the landing page matches the mockup in web/static/mockups/landing.html
6. Verify mobile layout at 375px (check the responsive rules in DESIGN_TOKENS.md §8)

**Do NOT change any Jinja logic, route references, or data bindings.** Only change CSS classes, inline styles, and HTML structure where needed to use token components.

**Do NOT copy patterns from other templates** — they predate the design system. Reference ONLY DESIGN_TOKENS.md.

### Verify
```bash
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/landing.html web/templates/search_results_public.html --quiet
# Target: 5/5 (0 violations)
```

### Commit
`feat: migrate landing + search templates to obsidian design tokens`
""")
```

---

### Agent 2C: Results + Content Pages

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Migrate results.html, methodology.html, about_data.html, demo.html

### Read First
- docs/DESIGN_TOKENS.md (full file)
- web/templates/results.html (416 lines, 54 violations — heaviest migration)
- web/templates/methodology.html
- web/templates/about_data.html
- web/templates/demo.html

### Build

**results.html** is the priority — it's the page users see after every search. It has 54 violations.

For each template, follow the same migration steps:
1. Replace inline hex colors → CSS custom properties
2. Replace font-family → `var(--mono)` / `var(--sans)` per role table
3. Replace ad-hoc components → token classes
4. Add scroll reveals to content sections
5. Check mobile layout at 375px

**For results.html specifically:**
- Search results should be `glass-card` containers
- Permit data (numbers, addresses, dates, costs) uses `--mono`
- Descriptive text uses `--sans`
- Status indicators use `status-dot` + `status-text--{color}`
- Type labels use `chip` component

**For content pages** (methodology, about_data, demo):
- These are mostly prose — `--sans` body text, `--mono` for code/data examples
- Section headings: `--sans` weight 300-400
- Use `expandable` component for FAQ-style sections if applicable
- Use `insight` callout for key takeaways

### Verify
```bash
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/results.html web/templates/methodology.html web/templates/about_data.html web/templates/demo.html --quiet
# Target: 5/5
```

### Commit
`feat: migrate results + content pages to obsidian design tokens`
""")
```

---

### Agent 2D: Nav Fragment + Error Pages

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Migrate nav fragment + build error pages

### Read First
- docs/DESIGN_TOKENS.md §6 (Navigation) and §9 (Page Archetypes)
- web/static/mockups/landing.html (nav implementation in mockup)
- web/templates/fragments/nav.html (current nav fragment)
- web/templates/fragments/login_prompt.html
- web/templates/error.html (current — 109 lines)
- web/templates/landing.html lines 1-30 (how landing includes nav differently)
- web/templates/index.html lines 1-30 (how authenticated pages include nav)

### Build

**1. Migrate web/templates/fragments/nav.html to token classes:**

Use the `nav-float` component from DESIGN_TOKENS.md §6:
- `nav-float__wordmark` for the logo
- `nav-float__link` for nav items
- Correct show/hide behavior: hidden on landing hero, visible on all other pages
- Mobile: wordmark + hamburger menu

IMPORTANT: The nav fragment is included by EVERY template. Changes here affect all pages. Be conservative — only change CSS classes and inline styles, not Jinja logic or conditional blocks.

**2. Build proper error pages (404, 500):**

Replace the minimal error.html with a designed version following the Auth Pages archetype:
- Centered `glass-card` on obsidian background
- Error code in `--mono` weight 300, large (`--text-2xl`)
- Friendly message in `--sans` (`--text-secondary`)
- Search bar as recovery path (use `search-input` component)
- Ghost CTA: "Back to home →"

Create two variants via Jinja conditionals (the route passes `error_code`):
- 404: "Page not found. Try searching for what you need."
- 500: "Something went wrong. We're looking into it."

**3. Migrate login_prompt.html fragment to token classes.**

### Verify
```bash
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/fragments/nav.html web/templates/error.html web/templates/fragments/login_prompt.html --quiet
# Target: 5/5
```

### Commit
`feat: migrate nav fragment + build obsidian error pages`
""")
```

---

## Post-Agent: Merge

After all 4 agents complete:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull  # Pick up Terminal 1's merge

# Merge in order:
git merge <agent-2a-branch>  # CSS foundation first
git merge <agent-2b-branch>  # Landing + search (uses 2A's CSS)
git merge <agent-2c-branch>  # Results + content
git merge <agent-2d-branch>  # Nav + errors

# Design lint check on all migrated files:
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/landing.html web/templates/search_results_public.html web/templates/results.html web/templates/methodology.html web/templates/about_data.html web/templates/demo.html web/templates/error.html web/templates/fragments/nav.html --quiet
# Target: 5/5

git push origin main
```
