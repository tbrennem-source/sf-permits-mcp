<!-- LAUNCH: Paste into CC terminal 1:
     "Read sprint-prompts/sprint-78-design-migration.md and execute it" -->

# Sprint 78 — Design Token Migration

You are the orchestrator for Sprint 78. Spawn 4 parallel build agents, collect results, merge, test, push.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git tag pre-sprint-78
```

Verify HEAD: `git log --oneline -3`

## IMPORTANT CONTEXT

This sprint migrates 9 high-traffic templates to the Obsidian design token system. Every agent MUST read docs/DESIGN_TOKENS.md and docs/DESIGN_CANON.md before touching any template. The landing page (web/static/landing-v5.html) is the visual reference — match its aesthetic.

Chief Task #355 identified 193 design-token violations across 6 core templates. This sprint covers those plus 3 additional high-value pages.

## Agent Launch

Spawn all 4 agents in parallel using Task tool:
```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree")
```

Each agent prompt MUST start with:
```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate

RULES:
- Read docs/DESIGN_TOKENS.md FIRST — this is THE authority for colors, fonts, spacing, components.
- Read docs/DESIGN_CANON.md for design philosophy.
- Read design-spec.md for page-level design decisions.
- MERGE RULE: Do NOT merge to main. Commit to worktree branch only.
- CONFLICT RULE: Do NOT run git checkout <branch> -- <file>. Report conflicts as BLOCKED.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- DO NOT modify ANY file outside your owned list. If you need a change in another file, document it in CHECKCHAT.
- APPEND FILES (dual-write):
  * scenarios-pending-review-sprint-78-N.md (per-agent)
  * scenarios-pending-review.md (shared, append only)
  * CHANGELOG-sprint-78-N.md (per-agent)
- Test after each task: pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q 2>&1 | tail -5
```

---

### Agent 78-1: Landing + Search Results Public

**File Ownership:**
- web/templates/landing.html
- web/templates/search_results_public.html

**PHASE 1: READ**
- docs/DESIGN_TOKENS.md (full file — THE authority)
- docs/DESIGN_CANON.md (design philosophy)
- web/static/landing-v5.html (visual reference)
- web/templates/landing.html (current state)
- web/templates/search_results_public.html (current state)
- web/static/design-system.css (available classes — DO NOT MODIFY this file)

**PHASE 2: BUILD**

For EACH template:
1. Replace all ad-hoc hex colors with CSS custom property vars from DESIGN_TOKENS.md
2. Replace all font-family declarations with `var(--font-mono)` / `var(--font-sans)`
3. Replace custom component HTML with token classes: `.glass-card`, `.obs-table`, `.ghost-cta`, `.status-dot`
4. Verify all text uses `--text-primary`, `--text-secondary`, `--text-tertiary` hierarchy
5. Verify signal colors use `--signal-green/amber/red` only for their semantic purpose
6. Check mobile at 375px — no horizontal overflow, touch targets ≥44px

**PHASE 3-6: TEST, SCENARIOS, QA, CHECKCHAT**
Test: pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q
Commit: "design: migrate landing + search_results_public to design tokens (Sprint 78-1)"

---

### Agent 78-2: Results + Report

**File Ownership:**
- web/templates/results.html
- web/templates/report.html

**PHASE 1: READ**
Same as Agent 78-1, plus:
- web/templates/results.html (current state)
- web/templates/report.html (current state — this is the most complex template)

**PHASE 2: BUILD**
Same migration pattern as Agent 78-1. report.html is large — focus on:
- Permit cards → `.glass-card`
- Status badges → `.status-dot` + signal colors
- Data tables → `.obs-table`
- Risk assessment section → signal color hierarchy
- Consultant signal → accent color for recommendations

Commit: "design: migrate results + report to design tokens (Sprint 78-2)"

---

### Agent 78-3: Brief + Velocity Dashboard

**File Ownership:**
- web/templates/brief.html
- web/templates/velocity_dashboard.html

**PHASE 1: READ**
Same base reads, plus:
- web/templates/brief.html (current state)
- web/templates/velocity_dashboard.html (current state)

**PHASE 2: BUILD**
Same migration pattern. brief.html specifics:
- Health indicators → signal colors (green=on track, amber=stalled, red=alert)
- Change summary cards → `.glass-card`
- Pipeline stats → `.obs-table`
- Inspection timeline → signal colors
velocity_dashboard.html:
- Station velocity charts → signal colors for fast/normal/slow
- Data tables → `.obs-table`

Commit: "design: migrate brief + velocity_dashboard to design tokens (Sprint 78-3)"

---

### Agent 78-4: Portfolio + Nav + Demo

**File Ownership:**
- web/templates/portfolio.html
- web/templates/fragments/nav.html
- web/templates/demo.html
- web/static/design-system.css (ONLY for adding new token classes if needed — do NOT modify existing classes)

**PHASE 1: READ**
Same base reads, plus:
- web/templates/portfolio.html
- web/templates/fragments/nav.html
- web/templates/demo.html
- web/static/design-system.css

**PHASE 2: BUILD**
Same migration pattern. Portfolio specifics:
- Watch list items → `.glass-card` with signal-color status dots
- Property cards → `.glass-card`
- Empty state → ghost text + accent CTA

Nav specifics:
- Verify responsive hamburger at 375px
- Active page indicator → accent color
- Badge counts → accent color background

Demo specifics:
- Pre-loaded property → `.glass-card`
- Intelligence sections → signal colors

If ANY needed component class is missing from design-system.css, ADD it following the naming conventions in DESIGN_TOKENS.md. Document additions in CHANGELOG.

Commit: "design: migrate portfolio + nav + demo to design tokens (Sprint 78-4)"

---

## Post-Agent Merge (Orchestrator)

1. Collect results from all 4 agents
2. Merge all branches (potential conflict only in scenarios-pending-review.md — resolve by keeping both sides)
3. Run tests: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q`
4. Push to main
5. Report: templates migrated, design violations fixed, any BLOCKED items
