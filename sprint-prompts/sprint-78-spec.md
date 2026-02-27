# Sprint 78 — Foundation Sprint Spec

**Date:** 2026-02-27
**Type:** Standard sprint (1 terminal × 6 agents)
**Status:** APPROVED (v2 — c.ai amendments addressed)
**Pre-requisite:** QS7 must be in prod (obsidian.css + head_obsidian.html needed for template migration)
**Sprint prompt:** `sprint-prompts/sprint-78-foundation.md`
**Chief tasks:** #359 (P0, replaces #357), #355 (P0)
**c.ai review:** Approved with 2 amendments (both addressed in v2)

## Goal

Two P0 foundations in one sprint: reliable test infrastructure + all core templates on the Obsidian design system. Secondary: dashboard looks alive for demos.

## Why Now (before QS8)

1. **#357 (test harness)** — DuckDB lock contention causes false failures in merge-ceremony test runs. Every quad sprint after this gets reliable test validation. We saw this fail live during QS7-T4 merge.
2. **#355 (template migration)** — Subsequent sprints (QS8: performance, intelligence, beta) build new UI. With migrated templates on main, agents copy token patterns instead of inventing ad-hoc styles. Design drift prevented at source.
3. **Demo readiness** — The authenticated dashboard currently shows flat boxes and zeros. One agent polishes index.html + creates a seed script so Tim can demo to Charis without embarrassment.

## Success Criteria

| # | Criterion | How to Measure | Where |
|---|---|---|---|
| 1 | No DuckDB lock contention in parallel test runs | Run 2 pytest sessions simultaneously — both pass | Local |
| 2 | 10 templates score 5/5 on design lint | `python scripts/design_lint.py --files [10 files] --quiet` | Local |
| 3 | Full test suite passes after merge | `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -q` | Local |
| 4 | Prod gate PROMOTE | `python scripts/prod_gate.py --quiet` | Local |
| 5 | Dashboard shows real data (not all zeros) | Run seed_demo.py, verify index.html visually | Staging |
| 6 | No layout regressions on migrated pages | Playwright screenshots at 375px + 1280px on 3 key pages | Staging |

## Wall Clock (estimated: 35-45 min)

```
T+0:     Launch 6 agents in parallel
T+15:    Agent A finishes (test harness — smallest scope)
T+18:    Agents B-E finish (template migration — read-lint-fix cycle)
T+20:    Agent F finishes (index.html + seed script)
T+22:    Merge all 6 branches (Fast Merge Protocol)
T+25:    Full test suite (3-5 min)
T+30:    Design lint + prod gate (1 min)
T+32:    Fix any failures (0-10 min)
T+35-45: Push, promote, verify
```

## Agent Scope

### Agent A: Test Harness (#357)

**Problem:** 90 test files reference DuckDB. When agents run `pytest` simultaneously (or during merge ceremony), they contend for the same file lock on `data/sf_permits.duckdb`. Random `IOException` failures mask real regressions.

**Solution:** Session-scoped pytest fixture in `tests/conftest.py` that patches `src.db._DUCKDB_PATH` to a per-session temp file. Each pytest session gets its own DuckDB — zero file contention.

**Constraint:** No local PostgreSQL installed. Solution uses DuckDB-only approach. Postgres testing deferred to CI (where Postgres is available).

**c.ai Amendment 1 (addressed):** Original Chief task #357 described a Postgres migration. Spec correctly scopes to DuckDB isolation only — solves the immediate pain (false failures) without Postgres complexity. Chief task updated: #357 closed, replaced by #359 with DuckDB-only scope.

**Files:** `tests/conftest.py`, `src/db.py` (minor — verify _DUCKDB_PATH is patchable), `pyproject.toml` (if new dev deps needed)

**Risk:** Low. The fixture patches a module-level variable. All 90 test files call `get_connection()` which reads that variable. No per-file changes needed.

**Validation:** Launch 2 pytest sessions in parallel, both pass without lock errors.

### Agents B-E: Template Migration (#355)

**Problem:** 9 core templates use ad-hoc hex colors, random fonts, and custom one-off components. Chief #355 identified 193 design-token violations across 6 core files. Total across all 9 is likely 250+.

**Solution:** Pure CSS migration — replace ad-hoc values with CSS custom properties from `docs/DESIGN_TOKENS.md`. No layout or functionality changes. Each agent owns 2-3 templates with zero file overlap.

| Agent | Templates | Est. Violations |
|-------|-----------|----------------|
| B | landing.html, search_results_public.html | ~40 |
| C | results.html, report.html | ~100 (report.html is largest) |
| D | brief.html, velocity_dashboard.html | ~50 |
| E | portfolio.html, fragments/nav.html, demo.html | ~50 |

**Migration pattern (same for all 4 agents):**
1. Replace hex colors → `var(--obsidian)`, `var(--accent)`, `var(--text-primary)`, etc.
2. Replace font-family → `var(--font-mono)` for data, `var(--font-sans)` for prose
3. Replace custom components → token classes (`.glass-card`, `.obs-table`, `.ghost-cta`, `.status-dot`)
4. Verify text hierarchy (primary/secondary/tertiary usage)
5. Verify signal colors used only for semantic meaning
6. Check mobile at 375px

**Key constraint:** Templates must NOT change Jinja logic, route behavior, or layout structure. CSS-only migration. If a violation lives inside a complex Jinja block that's risky to touch, leave it and document.

**Dependency on QS7:** These templates include `fragments/head_obsidian.html` which loads `obsidian.css`. Both shipped in QS7-T2. If QS7 isn't merged to main before Sprint 78 launches, agents will reference CSS classes that don't exist in their worktrees.

**c.ai Amendment 2 (addressed):** Each template agent (B-F) runs a gate check at T+0: `test -f web/static/obsidian.css && test -f web/templates/fragments/head_obsidian.html`. If either file is missing, agent reports BLOCKED-EXTERNAL and stops immediately. This prevents wasted work if QS7 hasn't landed.

**Validation:** `python scripts/design_lint.py --files [templates] --quiet` → 5/5 per template.

### Agent F: Demo-Ready Dashboard

**Problem:** The authenticated dashboard (index.html) shows "0 PERMITS WATCHED / 0 CHANGES THIS WEEK" with an empty watchlist box. This looks like a broken prototype, not a product you'd demo to a partner.

**Solution:** Two-part fix:
1. Polish index.html — fix remaining lint violations, replace empty states with compelling content (featured property preview, suggested searches, "Get started" messaging instead of raw zeros)
2. Create `scripts/seed_demo.py` — idempotent script that adds 3 watch_items and recent searches to a specified user account, so the dashboard shows real intelligence

**Files:** `web/templates/index.html`, `scripts/seed_demo.py` (NEW)

**Risk:** Low. index.html was partially migrated in QS7 (commit `26cb01d`). Agent F finishes the job. seed_demo.py is a standalone CLI script with no production impact.

**c.ai Observation (addressed):** Agent E migrates `fragments/nav.html` which Agent F's `index.html` includes. File ownership is clean (different files) but visual outcome has a dependency. Agent F's prompt includes a note to document any post-merge nav mismatch in CHECKCHAT. Orchestrator spot-checks after merge.

## Interface Contracts

### Contract 1: Design Token CSS Classes (QS7-T2 → Sprint 78 agents B-E)

Template agents reference class names from `docs/DESIGN_TOKENS.md`. The CSS implementing those classes lives in `web/static/obsidian.css` (shipped in QS7). If a class from DESIGN_TOKENS.md is missing from obsidian.css, the template agent documents it in CHECKCHAT but does not create CSS (that would require modifying obsidian.css, which is outside their file ownership).

### Contract 2: DuckDB Path Patching (Agent A → all future test runs)

Agent A patches `src.db._DUCKDB_PATH` via a session-scoped conftest fixture. This is transparent to all test files — they continue calling `get_connection()` as before. The fixture is `autouse=True`, so no test file needs modification.

### Contract 3: index.html Data Context (web routes → Agent F)

Agent F must read the route that renders index.html to understand what template variables are available. The empty-state improvements must work with the existing context dict (no route changes). If a new variable is needed, Agent F adds it to the route — but index.html is the ONLY template they can modify.

**Correction:** Agent F's file ownership is `web/templates/index.html` + `scripts/seed_demo.py`. If the route rendering index.html needs a minor context addition (e.g., `featured_property`), Agent F should document it as BLOCKED-EXTERNAL rather than modifying the route file (which belongs to another domain).

## CSS Coexistence (inherited from QS7)

Both `design-system.css` (old) and `obsidian.css` (new) still load simultaneously. QS7 established the load order: obsidian.css loads AFTER design-system.css, later wins on equal specificity. Sprint 78 agents continue removing old classes and replacing with token classes, further reducing the overlap surface.

**Target:** After Sprint 78, the 10 migrated templates should reference only token classes. Remaining ad-hoc CSS lives in unmigrated templates (~20 pages, mostly admin/plan-analysis).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| conftest fixture breaks existing tests | Low | High | Session-scoped, autouse, patches only _DUCKDB_PATH. Reversible. |
| Template migration breaks Jinja rendering | Medium | Medium | CSS-only changes. No Jinja logic modifications. |
| report.html too complex for clean migration | Medium | Medium | Agent C focuses on structural elements. Leave deep Jinja blocks alone. |
| QS7 not merged when Sprint 78 launches | Low | High | **Hard pre-requisite.** Do not launch until QS7 is on main. |
| obsidian.css missing classes agents reference | Low | Medium | Agents document missing classes. Post-sprint hotfix adds them. |
| seed_demo.py fails on prod schema | Low | Low | Script is idempotent, uses standard get_connection(). Test locally first. |

## Failure Recovery

| Scenario | Action |
|---|---|
| Agent A breaks test suite | Revert conftest.py changes. Other 5 agents unaffected. |
| Template agent leaves violations | Run lint, fix inline. Budget 5 min per template. |
| Merge conflict | Should not happen (zero file overlap). If it does, file owner wins. |
| >5 test failures after merge | Bisect: revert last merge, re-test. Most likely Agent A's fixture. |
| Prod gate HOLD | Read report. Fix blocking issues before promoting. |
| Dashboard still looks bad | CSS migration + empty state fix should help. If not, targeted hotfix. |

## File Ownership Matrix

| Agent | Files | Creates | Modifies |
|-------|-------|---------|----------|
| A | tests/conftest.py, src/db.py, pyproject.toml | — | conftest.py (fixture), db.py (minor), pyproject.toml (deps) |
| B | web/templates/landing.html, search_results_public.html | — | Both (CSS migration) |
| C | web/templates/results.html, report.html | — | Both (CSS migration) |
| D | web/templates/brief.html, velocity_dashboard.html | — | Both (CSS migration) |
| E | web/templates/portfolio.html, fragments/nav.html, demo.html | — | All 3 (CSS migration) |
| F | web/templates/index.html, scripts/seed_demo.py | seed_demo.py | index.html (polish + empty states) |

**Cross-agent conflicts: ZERO.** Every file owned by exactly one agent.

## What Ships / What Doesn't

**Ships:**
- Reliable test harness (no more DuckDB lock contention in merge ceremonies)
- 10 templates on Obsidian design tokens (landing, search, results, report, brief, velocity, portfolio, nav, demo, index)
- Demo-ready dashboard with seed script
- ~250 design-token violations fixed

**Deferred:**
- PostgreSQL test fixtures (need local Postgres install or Docker — future sprint)
- Admin templates migration (~8 templates)
- Plan analysis templates migration (~6 templates)
- Email templates
- Full visual regression baseline (QA sprint)
- DuckDB/Postgres SQL divergence fixes (separate from lock contention)

## Relationship to QS8

Sprint 78 is a **pre-requisite** for QS8 (Sprints 79-81). After Sprint 78 lands:
- QS8-T1 (Performance) builds page_cache + N+1 fix on top of reliable tests
- QS8-T2 (Intelligence) creates new tools — agents see token patterns in templates they read
- QS8-T3 (Beta + Data) builds onboarding UI using migrated templates as reference

QS8 drops from 4 terminals to 3 (Sprint 78 absorbs what was T1-Design). Planning doc: `sprint-prompts/qs8-planning.md`.
