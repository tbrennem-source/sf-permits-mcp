# QS11 T2: Page Migration Blitz

> **EXECUTE IMMEDIATELY.** You are a terminal orchestrator. Read this prompt, run Pre-Flight, then spawn ALL 4 agents in PARALLEL using the Agent tool (subagent_type="general-purpose", model="sonnet", isolation="worktree"). Do NOT summarize or ask for confirmation — execute now. After all agents complete, run the Post-Agent merge ceremony, then CHECKQUAD.

**Sprint:** QS11 — Intelligence-Forward Beta
**Terminal:** T2 — Page Migration Blitz
**Agents:** 4 (all parallel — no dependencies between agents)
**Theme:** Migrate top inner pages to Obsidian design system for visual coherence

---

## Terminal Overview

| Agent | Focus | Templates Owned |
|---|---|---|
| 2A | Search Flow | search_results_public.html, results.html, search_results.html |
| 2B | Property + Tools (pair 1) | report.html, tools/station_predictor.html, tools/stuck_permit.html |
| 2C | Auth Pages | auth_login.html, beta_request.html, consultants.html |
| 2D | Tools (pair 2) + Supporting | tools/what_if.html, tools/cost_of_delay.html, methodology.html, demo.html |

**All 4 agents run in parallel — zero file overlap.**

---

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
```

---

## Agent Rules (ALL agents must follow)

1. **Worktree**: You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run `git checkout main`. Do NOT run `git merge`.
2. **No descoping**: Attempt every template. Do not skip.
3. **Early commit**: Commit within 10 minutes. Use `git add <specific-files>`.
4. **CRITICAL: NEVER merge to main.** T2 orchestrator handles merges.
5. **File ownership**: Only touch templates in YOUR assignment.
6. **Test command**: `source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short`
7. **Scenario file**: Write to `scenarios-t2-sprint91.md`.
8. **Changelog file**: Write to `CHANGELOG-t2-sprint91.md`.
9. **Design system**: Read `docs/DESIGN_TOKENS.md` FIRST. This is the single source of truth.
10. **Skip-and-flag rule**: If a template actively resists migration (heavy custom JS, complex conditional rendering that breaks when CSS changes), spend max 15 minutes trying. If still broken, flag as BLOCKED-FIXABLE with the specific issue, revert your changes to that template, and move to the next one. Do NOT burn time on one stubborn template.

---

## Migration Methodology (identical for all agents)

For each template:

1. **Read** `docs/DESIGN_TOKENS.md` (do this ONCE at start, not per template)
2. **Check current state**: Does this template extend `fragments/head_obsidian.html`?
   - If YES: it's partially migrated. Fix remaining violations.
   - If NO: convert it to extend head_obsidian.html.
3. **Replace ad-hoc hex colors** → CSS custom properties (--obsidian, --text-primary, etc.)
4. **Swap font-family** → `--mono` for data/numbers, `--sans` for prose/labels
5. **Replace custom components** → token classes (glass-card, obs-table, ghost-cta, status-dot)
6. **Remove inline `<style>` blocks** where possible — move to design-system.css or obsidian.css only if globally reusable, otherwise keep as scoped `<style>` with token vars
7. **Verify mobile** at 375px — ensure no horizontal overflow, readable text
8. **Include error/empty states** — what shows when data is missing?
9. **Run design lint**: `python scripts/design_lint.py --files web/templates/<file>`
10. **Target 5/5 lint score** on each template

### What NOT to do during migration
- Do NOT change route logic or Python code
- Do NOT change template variable names or Jinja logic
- Do NOT add new features
- Do NOT copy CSS patterns from OTHER templates — always reference DESIGN_TOKENS.md
- Do NOT use legacy font vars (--font-body, --font-display) — use --mono and --sans

---

## DuckDB / Postgres Gotchas

Not directly relevant to template migration, but if you encounter any in tests:
- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE SET ...`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()`

---

## Agent 2A Prompt — Search Flow Templates

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
Read docs/DESIGN_TOKENS.md before touching any template.

## YOUR TASK: Migrate search flow templates to Obsidian design system

Migrate these 3 templates to use Obsidian design tokens:

1. **web/templates/search_results_public.html** — Public search results page. Currently uses
   custom inline :root vars. Convert to extend head_obsidian.html, replace all custom colors
   with token vars, swap fonts, use obs-table and glass-card where applicable.

2. **web/templates/results.html** — Authenticated search results. Similar custom inline styling.
   Same migration process.

3. **web/templates/search_results.html** — Another search results variant. Check if it exists
   first. If it does, migrate it. If it doesn't exist, skip and note in your report.

### Migration Process (per template)
1. Read the template — understand its structure and current styling
2. Check: does it extend head_obsidian.html? If not, convert it.
3. Replace all hardcoded hex colors with CSS custom properties
4. Replace font-family declarations with --mono/--sans
5. Replace custom components with token classes
6. Verify error/empty states exist (what shows for "no results"?)
7. Run: python scripts/design_lint.py --files web/templates/<file>
8. Target 5/5 lint score

### Skip-and-flag
If a template takes more than 15 minutes and you can't get lint ≥ 3/5, flag it as
BLOCKED-FIXABLE, revert changes, and note the specific issue.

### FILES YOU OWN
- MODIFY: web/templates/search_results_public.html
- MODIFY: web/templates/results.html
- MODIFY: web/templates/search_results.html (if it exists)
- CREATE: tests/test_migration_search.py

### FILES YOU MUST NOT TOUCH
- web/templates/landing.html, web/routes_*.py
- Any template not in your list
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_migration_search.py)
- Test each migrated template renders without error (mock minimal context)
- Test templates extend head_obsidian.html (check for the include)
- Test no hardcoded hex colors remain in the template (regex check)
- At least 6 tests.

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Read each template
3. Migrate each template (commit after each one)
4. Run design lint on each
5. Create tests
6. Run: pytest tests/test_migration_search.py -v
7. Run full suite
8. Write scenarios to scenarios-t2-sprint91.md
9. Write changelog to CHANGELOG-t2-sprint91.md
```

---

## Agent 2B Prompt — Property + Tools (Pair 1)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
Read docs/DESIGN_TOKENS.md before touching any template.

## YOUR TASK: Migrate property and tools templates to Obsidian design system

Migrate these 3 templates:

1. **web/templates/report.html** — Property report page. Has partial Obsidian migration
   (some token vars) but still uses inline styles. Complete the migration.

2. **web/templates/tools/station_predictor.html** — Station predictor tool page.

3. **web/templates/tools/stuck_permit.html** — Stuck permit analyzer tool page.

NOTE: These tool templates will be FURTHER polished by T3 agents who add interactive features.
Your job is design token compliance ONLY — replace colors, fonts, components. Do NOT add
functionality. T3 builds on top of your migration.

### Migration Process
Same as described in the Terminal Overview methodology section.
Skip-and-flag rule applies: 15 min max per template before flagging.

### FILES YOU OWN
- MODIFY: web/templates/report.html
- MODIFY: web/templates/tools/station_predictor.html
- MODIFY: web/templates/tools/stuck_permit.html
- CREATE: tests/test_migration_property.py

### FILES YOU MUST NOT TOUCH
- web/templates/landing.html, web/routes_*.py
- Any template not in your list
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_migration_property.py)
- Test each migrated template renders without error
- Test templates extend or include head_obsidian.html
- Test no legacy font vars (--font-body, --font-display) in templates
- At least 6 tests.

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Read each template
3. Migrate each template (commit after each)
4. Run design lint
5. Create tests, run tests, run full suite
6. Write scenarios + changelog
```

---

## Agent 2C Prompt — Auth Pages

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
Read docs/DESIGN_TOKENS.md before touching any template.

## YOUR TASK: Migrate auth and supporting templates to Obsidian design system

Migrate these 3 templates:

1. **web/templates/auth_login.html** — Login page. NOTE: the spec calls this "login.html"
   but the actual file is auth_login.html. Currently uses full custom inline styles.

2. **web/templates/beta_request.html** — Beta access request page. Inline styles.

3. **web/templates/consultants.html** — Consultant directory page.

### Migration Process
Same as described in the Terminal Overview methodology section.
Skip-and-flag rule applies: 15 min max per template before flagging.

### FILES YOU OWN
- MODIFY: web/templates/auth_login.html
- MODIFY: web/templates/beta_request.html
- MODIFY: web/templates/consultants.html
- CREATE: tests/test_migration_auth.py

### FILES YOU MUST NOT TOUCH
- web/templates/landing.html, web/routes_*.py
- Any template not in your list
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_migration_auth.py)
- Test each migrated template renders without error
- Test no hardcoded hex colors remain
- Test font vars use --mono/--sans not legacy names
- At least 6 tests.

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Read each template
3. Migrate each template (commit after each)
4. Run design lint
5. Create tests, run tests, run full suite
6. Write scenarios + changelog
```

---

## Agent 2D Prompt — Tools (Pair 2) + Supporting

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
Read docs/DESIGN_TOKENS.md before touching any template.

## YOUR TASK: Migrate tool and supporting templates to Obsidian design system

Migrate these 4 templates:

1. **web/templates/tools/what_if.html** — What-If simulator tool page.

2. **web/templates/tools/cost_of_delay.html** — Cost of Delay calculator page.

3. **web/templates/methodology.html** — Methodology page.

4. **web/templates/demo.html** — Demo page.

NOTE: Tool templates (what_if, cost_of_delay) will be FURTHER polished by T3 agents.
Your job is design token compliance ONLY. Do NOT add features.

### Migration Process
Same as described in the Terminal Overview methodology section.
Skip-and-flag rule applies: 15 min max per template before flagging.

### FILES YOU OWN
- MODIFY: web/templates/tools/what_if.html
- MODIFY: web/templates/tools/cost_of_delay.html
- MODIFY: web/templates/methodology.html
- MODIFY: web/templates/demo.html
- CREATE: tests/test_migration_tools.py

### FILES YOU MUST NOT TOUCH
- web/templates/landing.html, web/routes_*.py
- tools/station_predictor.html, tools/stuck_permit.html (Agent 2B)
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_migration_tools.py)
- Test each migrated template renders without error
- Test no legacy font vars
- Test no hardcoded hex colors
- At least 8 tests (2 per template).

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Read each template
3. Migrate each template (commit after each)
4. Run design lint
5. Create tests, run tests, run full suite
6. Write scenarios + changelog
```

---

## Post-Agent Merge Ceremony

After ALL 4 agents complete:

```bash
# Step 0: ESCAPE CWD
cd /Users/timbrenneman/AIprojects/sf-permits-mcp

# Step 1: Pull latest main
git checkout main && git pull origin main

# Step 2: Merge all agents (no dependency order — all independent)
git merge <2A-branch> --no-ff -m "feat(migration): search flow templates to Obsidian"
git merge <2B-branch> --no-ff -m "feat(migration): property + tools templates to Obsidian"
git merge <2C-branch> --no-ff -m "feat(migration): auth pages to Obsidian"
git merge <2D-branch> --no-ff -m "feat(migration): tools pair 2 + supporting pages to Obsidian"

# Step 3: Quick test
source .venv/bin/activate
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x

# Step 4: Design lint on all migrated files
python scripts/design_lint.py --changed --quiet

# Step 5: Push
git push origin main
```

---

## CHECKQUAD

### Step 0: ESCAPE CWD
`cd /Users/timbrenneman/AIprojects/sf-permits-mcp`

### Step 1: MERGE
See Post-Agent Merge Ceremony above.

### Step 2: ARTIFACT
Write `qa-drop/qs11-t2-session.md` with:
- Agent results table (4 agents, PASS/FAIL, lint scores per template)
- Templates migrated (count)
- Templates flagged BLOCKED (if any, with reasons)
- Design lint scores before/after

### Step 3: CAPTURE
- Concatenate scenario files → `scenarios-t2-sprint91.md`
- Concatenate changelog files → `CHANGELOG-t2-sprint91.md`

### Step 4: HYGIENE CHECK
```bash
python scripts/test_hygiene.py --changed --quiet 2>/dev/null || echo "No test_hygiene.py"
```

### Step 5: SIGNAL DONE
```
═══════════════════════════════════════════════════
  CHECKQUAD T2 COMPLETE — Page Migration Blitz
  Sprint 91 · 4 agents · X/4 PASS
  Templates migrated: N · Lint scores: all ≥ 3/5
  Pushed: <commit hash>
  Session: qa-drop/qs11-t2-session.md
═══════════════════════════════════════════════════
```

Do NOT run `git worktree remove` or `git worktree prune`. T0 handles cleanup.
