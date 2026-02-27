<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs4-c-obsidian-migration.md and execute it" -->

# Quad Sprint 4 — Session C: Obsidian Design Migration

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs4-c
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs4-c before any code changes.
MERGE RULE: Do NOT merge your branch to main. Commit to worktree branch only. The orchestrator (Tab 0) merges all branches.
CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files. If you encounter a conflict, stop and report it.
APPEND FILES: Write scenarios to `scenarios-pending-review-qs4-c.md` (not the shared file). Write changelog to `CHANGELOG-qs4-c.md`.
```

## SETUP — Session Bootstrap

1. **Navigate to main repo root:**
   ```
   cd /Users/timbrenneman/AIprojects/sf-permits-mcp
   ```
2. **Pull latest main:**
   ```
   git checkout main && git pull origin main
   ```
3. **Create worktree:**
   Use EnterWorktree with name `qs4-c`

If worktree exists: `git worktree remove .claude/worktrees/qs4-c --force 2>/dev/null; true`

4. **Safety tag:** `git tag pre-qs4-c`

---

## PHASE 1: READ

Read these files before writing any code:
1. `CLAUDE.md` — project structure, deployment, rules
2. `web/static/design-system.css` — Obsidian tokens, component classes (.glass-card, .obsidian-btn, etc.)
3. `web/templates/landing.html` — reference Obsidian page (the gold standard)
4. `web/templates/index.html` — current legacy authenticated home (your migration target)
5. `web/templates/brief.html` — current legacy morning brief (your migration target)
6. `web/templates/fragments/nav.html` — shared nav (do NOT change structure, only verify compatibility)
7. `web/static/style.css` — shared utility classes
8. `web/static/mobile.css` — responsive overrides (do NOT modify)
9. `scenario-design-guide.md` — for scenario-keyed QA

**Architecture notes:**
- Templates are SELF-CONTAINED — no base.html, no Jinja inheritance
- Every template has its own inline `<style nonce="{{ csp_nonce }}">` block with CSS variables
- **Legacy tokens** (index.html, brief.html): `--bg: #0f1117`, `--surface: #1a1d27`, `--accent: #4f8ff7`, system fonts
- **Obsidian tokens** (landing.html): `--bg-deep: #0B0F19`, `--bg-surface: #131825`, `--signal-cyan: #22D3EE`, JetBrains Mono + IBM Plex Sans
- The migration means: replace legacy `:root` vars with Obsidian vars, replace system fonts with Google Fonts import, apply signal colors for status indicators
- `design-system.css` is scoped under `body.obsidian` — add this class to migrated templates
- Google Fonts currently loaded per-template via `<link>` tag. You'll create a shared fragment.
- `fragments/nav.html` uses its own inline styles with `var(--border)`, `var(--surface)`, `var(--accent)` etc. These must still resolve after migration. Map: `--border` → `rgba(255,255,255, 0.06)`, `--surface` → `var(--bg-surface)`, `--accent` → `var(--signal-cyan)` or keep as legacy aliases.
- PWA meta tags (`<link rel="manifest">`, `<meta name="theme-color">`) already in index.html — verify they're in brief.html too.

---

## PHASE 2: BUILD

### Task C-1: Shared Head Fragment (~30 min)
**Files:** `web/templates/fragments/head_obsidian.html` (NEW)

**Create a reusable `<head>` fragment** that all Obsidian pages include:
```html
{# Obsidian Intelligence shared head — include in all migrated templates
   Usage: {% include "fragments/head_obsidian.html" %}
   Provides: Google Fonts, PWA meta, design-system.css link, legacy alias vars #}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/design-system.css">
<link rel="stylesheet" href="/static/style.css">
<link rel="stylesheet" href="/static/mobile.css">
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#22D3EE">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="/static/icon-192.png">
<style nonce="{{ csp_nonce }}">
    /* Legacy alias vars — so fragments/nav.html keeps working */
    :root {
        --bg: var(--bg-deep);
        --surface: var(--bg-surface);
        --surface-2: var(--bg-elevated);
        --border: rgba(255,255,255, 0.06);
        --text: var(--text-primary);
        --text-muted: var(--text-secondary);
        --accent: var(--signal-cyan);
        --accent-hover: #1ab8d1;
        --success: var(--signal-green);
        --warning: var(--signal-amber);
        --error: var(--signal-red);
    }
</style>
```

### Task C-2: Migrate `index.html` to Obsidian (~60 min)
**Files:** `web/templates/index.html`

**Replace the `<head>` section:**
- Remove inline Google Fonts `<link>` tags (now in shared fragment)
- Remove inline `:root` CSS variables block (now in shared fragment)
- Add `{% include "fragments/head_obsidian.html" %}` after `<meta name="viewport">`
- Add `class="obsidian"` to `<body>` tag
- Keep all `nonce="{{ csp_nonce }}"` attributes on remaining `<style>` and `<script>` tags

**Update CSS classes:**
- Replace `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif` with `font-family: var(--font-body)`
- Replace `background: var(--bg)` with `background: var(--bg-deep)`
- Replace card backgrounds `var(--surface)` with `var(--bg-surface)`
- Replace `var(--surface-2)` with `var(--bg-elevated)`
- Replace `color: var(--accent)` with `color: var(--signal-cyan)` for links/CTAs
- Add `font-family: var(--font-display)` to headings and monospace elements
- Apply `border-radius: 12px` and `box-shadow: 0 4px 24px rgba(0,0,0, 0.3)` to cards (Obsidian card pattern)

**Do NOT change:**
- Template logic ({% if %}, {% for %}, {{ variables }})
- Route URLs or form actions
- Nav include (`{% include "fragments/nav.html" %}`)
- HTMX attributes
- JavaScript behavior

### Task C-3: Migrate `brief.html` to Obsidian (~60 min)
**Files:** `web/templates/brief.html`

Same migration pattern as index.html:
- Replace `<head>` with shared fragment include
- Add `class="obsidian"` to `<body>`
- Update CSS tokens (same mapping as C-2)
- Apply `font-family: var(--font-display)` to headings, stat labels, section headers
- Apply signal colors to health indicators:
  - `on_track` → `var(--signal-green)`
  - `slower` / `behind` → `var(--signal-amber)`
  - `at_risk` → `var(--signal-red)`
- Keep all template logic, HTMX attributes, nav include unchanged
- Ensure summary cards use `.glass-card` or equivalent Obsidian card pattern

---

## PHASE 3: TEST

```bash
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py -q
```

Write `tests/test_qs4_c_design.py`:
- head_obsidian.html fragment exists
- head_obsidian.html contains Google Fonts link
- head_obsidian.html contains manifest link
- head_obsidian.html contains theme-color meta
- head_obsidian.html contains legacy alias vars
- index.html includes head_obsidian.html fragment
- index.html body has class="obsidian"
- index.html does NOT have inline Google Fonts link (deduplicated)
- index.html renders 200 for authenticated user
- brief.html includes head_obsidian.html fragment
- brief.html body has class="obsidian"
- brief.html renders 200 for authenticated user
- brief.html does NOT have inline Google Fonts link
- Nav still renders correctly in index.html (badges visible)
- Nav still renders correctly in brief.html
- design-system.css is loaded (check link tag in rendered HTML)
- Signal colors present in brief.html for health indicators
- No broken images or 404 resource loads on index page
- No broken images or 404 resource loads on brief page

**Target: 20+ tests**

---

## PHASE 4: SCENARIOS

Append 3 scenarios to `scenarios-pending-review-qs4-c.md`:
1. "Authenticated user sees consistent Obsidian design from landing through dashboard and brief"
2. "Morning brief health indicators use signal colors (green/amber/red) matching landing page design"
3. "Google Fonts loaded once via shared fragment instead of per-template"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs4-c-obsidian-qa.md`:

```
1. [NEW] GET / (landing) → login → GET /index uses same font family — PASS/FAIL
2. [NEW] index.html has JetBrains Mono headings — PASS/FAIL
3. [NEW] brief.html has JetBrains Mono headings — PASS/FAIL
4. [NEW] brief.html health indicators use signal-green/amber/red — PASS/FAIL
5. [NEW] Nav renders correctly on index page — PASS/FAIL
6. [NEW] Nav renders correctly on brief page — PASS/FAIL
7. [NEW] Screenshot /index at 375px — no horizontal scroll — PASS/FAIL
8. [NEW] Screenshot /index at 1440px — PASS/FAIL
9. [NEW] Screenshot /brief at 375px — PASS/FAIL
10. [NEW] Screenshot /brief at 1440px — PASS/FAIL
11. [NEW] PWA manifest link present on both pages — PASS/FAIL
```

Save screenshots to `qa-results/screenshots/qs4-c/`
Write results to `qa-results/qs4-c-results.md`

---

## PHASE 5.5: VISUAL REVIEW

Score these pages 1-5:
- / (landing) at 1440px — baseline reference
- /index at 1440px — should match landing's feel
- /index at 375px
- /brief at 1440px
- /brief at 375px

≥3.0 average = PASS. ≤2.0 on any page = ESCALATE to DeskRelay.

---

## PHASE 6: CHECKCHAT

### 1. VERIFY
- All QA FAILs fixed or BLOCKED
- pytest passing, no regressions
- Visual consistency: landing → index → brief all feel like the same product

### 2. DOCUMENT
- Write `CHANGELOG-qs4-c.md` with session entry

### 3. CAPTURE
- 3 scenarios in `scenarios-pending-review-qs4-c.md`

### 4. SHIP
- Commit with: "feat: Obsidian design migration — index.html + brief.html + shared head (QS4-C)"

### 5. PREP NEXT
- List remaining legacy pages that still need Obsidian migration (account, report, portfolio, etc.)
- Note which pages could use head_obsidian.html fragment with minimal changes

### 6. BLOCKED ITEMS REPORT

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Estimated | Actual |
|--------|-----------|--------|
| Wall clock time | 2-3 hours | [first commit to CHECKCHAT] |
| New tests | 20+ | [count] |
| Tasks completed | 3 | [N of 3] |
| Tasks descoped | — | [count + reasons] |
| Tasks blocked | — | [count + reasons] |
| Longest task | — | [task name, duration] |
| QA checks | 11 | [pass/fail/skip] |
| Visual Review avg | — | [score] |
| Scenarios proposed | 3 | [count] |
```

### DeskRelay HANDOFF
- [ ] Landing → login → index: does the design transition feel seamless?
- [ ] Brief page: is the dense data more readable with Obsidian typography?
- [ ] Signal colors on health indicators: intuitive at a glance?
- [ ] Mobile brief: can you scan the summary cards comfortably on a phone?
- [ ] Nav badges: do they still look correct against the Obsidian background?

---

## File Ownership (Session C ONLY)
**Own:**
- `web/templates/index.html` (Obsidian migration)
- `web/templates/brief.html` (Obsidian migration)
- `web/templates/fragments/head_obsidian.html` (NEW)
- `web/static/design-system.css` (minor additions if needed)
- `tests/test_qs4_c_design.py` (NEW)
- `CHANGELOG-qs4-c.md` (NEW — per-agent)
- `scenarios-pending-review-qs4-c.md` (NEW — per-agent)

**Do NOT touch:**
- `web/app.py` (Session B + D)
- `src/db.py` (Session B)
- `web/security.py` (Session D)
- `web/routes_admin.py` (Session A)
- `src/ingest.py` (Session A)
- `web/templates/landing.html` (READ ONLY — reference, do not modify)
- `web/templates/fragments/nav.html` (READ ONLY — must work unchanged)
- `web/static/mobile.css` (READ ONLY)
