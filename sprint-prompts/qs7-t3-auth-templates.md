# QS7 Terminal 3: Authenticated + Data Templates

> Paste this into CC Terminal 3. It spawns 4 agents via Task tool.
> **Merge order: Terminal 3 merges THIRD** (after Terminals 1+2).
> Terminal 1 provides cache variables for brief. Terminal 2 provides obsidian.css.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/brief.html web/templates/report.html web/templates/portfolio.html web/templates/index.html web/templates/auth_login.html --quiet
```

Note baseline violation counts.

## File Ownership (Terminal 3 ONLY touches these)

| Agent | Files |
|---|---|
| 3A | `web/templates/brief.html`, `web/templates/fragments/brief_prompt.html` |
| 3B | `web/templates/report.html`, `web/templates/fragments/severity_badge.html`, `web/templates/fragments/inspection_timeline.html` |
| 3C | `web/templates/portfolio.html`, `web/templates/project_detail.html`, `web/templates/index.html` |
| 3D | `web/templates/auth_login.html`, `web/templates/account_prep.html`, `web/templates/beta_request.html`, `web/templates/fragments/feedback_widget.html`, `web/templates/fragments/watch_button.html`, `web/static/toast.js` (NEW) |

## Interface Contract from Terminal 1

Agent 1B adds these to the brief template context:
- `brief.cached_at` — ISO timestamp string or None (None = computed fresh)
- `brief.can_refresh` — True (always, for now)

Agent 3A renders these in the brief template.

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent 3A: Brief Template Migration

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Migrate brief.html to design tokens + add cache UI

### Read First
- docs/DESIGN_TOKENS.md (full file — especially obs-table, status-dot, data-row, skeleton, insight, tabs, load-more)
- web/templates/brief.html (820 lines, 35 violations)
- web/templates/fragments/brief_prompt.html
- web/static/mockups/portfolio.html (closest mockup for data-dense layout reference)

### Build

**1. Migrate brief.html to token classes (35 violations → 0):**

The brief is the most data-dense page. Key migrations:
- Property cards → `glass-card` containers
- Status indicators → `status-dot--{color}` + `status-text--{color}` (dots use --dot-* tokens, text uses --signal-*)
- Data displays (permit numbers, addresses, dates) → `data-row` with `--mono` values
- Section headers → `--sans` weight 400, or mono uppercase for labels
- Progress bars → `progress-track` + `progress-fill`
- Stat counters → `stat-number` + `stat-label`

**2. Add cache freshness UI:**

At the top of the brief (inside the page header area), add:

```html
{% if brief.cached_at %}
<div style="display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4);">
  <span class="status-dot status-dot--green" title="Cached"></span>
  <span style="font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary);">
    Updated {{ brief.cached_at | timeago }}
  </span>
  {% if brief.can_refresh %}
  <form method="post" action="{{ url_for('misc.brief_refresh') }}" style="display: inline;">
    <button type="submit" class="ghost-cta" style="font-size: var(--text-xs);">
      Refresh →
    </button>
  </form>
  {% endif %}
</div>
{% endif %}
```

If the `timeago` filter doesn't exist, render the raw timestamp: `{{ brief.cached_at[:16] }}`.

**3. Replace any inline `<style>` blocks with token classes.** Move unique brief-specific styles to a `<style>` block at the top that ONLY uses CSS custom properties from the token system.

**Do NOT change Jinja logic, data bindings, or conditional blocks.** Only change presentation.

### Verify
```bash
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/brief.html --quiet
# Target: 5/5
```

### Commit
`feat: migrate brief.html to obsidian tokens + cache freshness UI`
""")
```

---

### Agent 3B: Property Report Template

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Migrate report.html to design tokens

### Read First
- docs/DESIGN_TOKENS.md (full file — especially obs-table, data-row, insight, risk-flag, expandable, action-prompt)
- web/templates/report.html (968 lines, 46 violations — second heaviest migration)
- web/templates/fragments/severity_badge.html
- web/templates/fragments/inspection_timeline.html
- web/static/mockups/property-intel.html (golden mockup for property report)

### Build

**report.html** is the property intelligence page — Amy's most-used view after the brief. 46 violations.

Key migrations:
- Property header → `--sans` weight 300 for address headline, `chip` for type badges
- Data sections → `glass-card` containers with `data-row` key-value pairs
- Permit tables → `obs-table` with sort indicators and `obs-table__mono` for data columns
- Status → `status-dot--{color}` + `status-text--{color}`
- Severity badges → use token signal colors, `chip` pattern
- Inspection timeline → `data-row` pairs or `obs-table` depending on density
- Risk flags → `risk-flag--{high|medium|low}` for violations/complaints
- Expandable sections → `expandable` component for detail-on-demand
- "Full intelligence" links → `ghost-cta` with arrow suffix
- Insight callouts → `insight--{color}` for key findings
- Action prompts → `action-prompt` at section ends

Also migrate severity_badge.html and inspection_timeline.html fragments.

### Verify
```bash
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/report.html web/templates/fragments/severity_badge.html web/templates/fragments/inspection_timeline.html --quiet
# Target: 5/5
```

### Commit
`feat: migrate property report + fragments to obsidian design tokens`
""")
```

---

### Agent 3C: Portfolio + Index

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Migrate portfolio.html, project_detail.html, index.html

### Read First
- docs/DESIGN_TOKENS.md (full file — especially tabs, load-more, obs-table, glass-card)
- web/templates/portfolio.html (334 lines, 18 violations)
- web/templates/project_detail.html
- web/templates/index.html (2091 lines — the authenticated home page)
- web/static/mockups/portfolio.html (golden mockup)

### Build

**portfolio.html:**
- Property cards → `glass-card` with `status-dot` indicators
- Use `tabs` component if portfolio has view modes (active/completed/all)
- Use `load-more` component for pagination (Amy may have 90+ properties)
- Data values (addresses, permit numbers) → `--mono`
- Labels and descriptions → `--sans`

**project_detail.html:**
- Use the Property Report archetype from DESIGN_TOKENS.md §9
- Data sections in `glass-card` containers
- `data-row` for key-value pairs
- `obs-table` for permit lists

**index.html (authenticated home — 2091 lines):**
- This is the biggest template. Focus on the structural elements:
  - Search bar → `search-input` component
  - Quick actions → `ghost-cta` or `action-btn`
  - Recent searches → `data-row` or simple list with `--mono` addresses
  - Watched properties summary → `glass-card` with status dots
  - Quick stats → `stat-number` + `stat-label`
- Do NOT rewrite Jinja logic — only change presentation classes and inline styles
- Mobile: verify the dashboard grid stacks to single column at 375px

### Verify
```bash
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/portfolio.html web/templates/project_detail.html web/templates/index.html --quiet
# Target: 5/5 (or close — index.html may have some irreducible violations from complex Jinja)
```

### Commit
`feat: migrate portfolio + index to obsidian design tokens`
""")
```

---

### Agent 3D: Auth Pages + Toast + Interactive Fragments

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Auth pages + toast JS + interactive fragments

### Read First
- docs/DESIGN_TOKENS.md (full file — especially form elements, toast, modal, action-btn, ghost-cta)
- web/templates/auth_login.html (158 lines)
- web/templates/account_prep.html (196 lines)
- web/templates/beta_request.html (87 lines)
- web/templates/fragments/feedback_widget.html
- web/templates/fragments/watch_button.html
- web/static/mockups/auth-login.html (golden mockup)

### Build

**1. Migrate auth templates:**

Auth pages follow the Auth Pages archetype (DESIGN_TOKENS.md §9):
- Centered `glass-card`, wordmark above
- `form-input` for email field
- `action-btn` for submit
- `ghost-cta` for secondary links
- Minimal — no nav bar, no ambient glow

**2. Create web/static/toast.js:**

Extract the `showToast()` JavaScript from DESIGN_TOKENS.md's toast component section. Make it a standalone JS file that any template can include:

```javascript
// web/static/toast.js
function showToast(message, opts = {}) {
  const { type = 'success', action, actionLabel = 'Undo', duration = 5000 } = opts;
  // ... (full implementation from DESIGN_TOKENS.md)
}
```

**3. Migrate feedback_widget.html:**
- Use `form-input` for text input
- Use `action-btn` for submit
- Use `chip` for feedback type selector

**4. Migrate watch_button.html:**
- Use `action-btn` for the watch toggle
- Wire to call `showToast('Watch added', { action: undoFn })` on success
- Include `<script src="{{ url_for('static', filename='toast.js') }}"></script>` in the fragment or ensure it's in head_obsidian.html

**5. Replace existing `.flash` divs across ALL templates you touch** with `showToast()` calls. The old `.flash` pattern (inline divs) is replaced by the toast component.

### Verify
```bash
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/auth_login.html web/templates/account_prep.html web/templates/beta_request.html web/templates/fragments/feedback_widget.html web/templates/fragments/watch_button.html --quiet
# Target: 5/5
```

### Commit
`feat: migrate auth pages + toast.js + interactive fragments to obsidian tokens`
""")
```

---

## Post-Agent: Merge

After all 4 agents complete, **wait for Terminals 1+2 to merge first**, then:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull  # Pick up Terminal 1+2 merges

git merge <agent-3a-branch>  # Brief (uses T1 cache vars + T2 CSS)
git merge <agent-3b-branch>  # Report
git merge <agent-3c-branch>  # Portfolio + index
git merge <agent-3d-branch>  # Auth + toast + fragments

# Design lint on all migrated files:
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/brief.html web/templates/report.html web/templates/portfolio.html web/templates/index.html web/templates/auth_login.html web/templates/account_prep.html --quiet

git push origin main
```
