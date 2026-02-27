# QS7 Beta Readiness — Quad Sprint Spec (v2)

**Date:** 2026-02-27
**Type:** Quad sprint (4 terminals × 4 agents = 16 agents)
**Status:** READY TO EXECUTE (v2 — c.ai review findings addressed)
**Sprint prompts:** `sprint-prompts/qs7-t0-orchestrator.md` through `qs7-t4-testing.md`
**Review:** c.ai scored v1 at 7/10. This version addresses all 5 findings.

## Goal

Beta readiness in one sprint: sub-second brief page + all core pages on the obsidian design system.

## Success Criteria

| # | Criterion | How to Measure | Where |
|---|---|---|---|
| 1 | `/brief` loads in <200ms | `curl -w '%{time_total}'` (warm cache, logged-in session) | Staging |
| 2 | 9 core templates score 5/5 on design lint | `python scripts/design_lint.py --files [9 files] --quiet` | Local |
| 3 | `obsidian.css` contains all 26 components | grep count ≥26 class definitions | Local |
| 4 | Prod gate PROMOTE (score 4+/5) | `python scripts/prod_gate.py` using **existing** 10 checks (not 1D's new checks) | Local |
| 5 | 40+ new tests pass | pytest on new test files | Local |
| 6 | 404/500 error pages return correct status codes | curl status code check | Staging |

**Prod gate circularity resolved:** Success uses existing 10-check gate, NOT the 3 new checks Agent 1D builds. New checks are a bonus.

## Wall Clock (revised: 40-50 min)

```
T+0:    All 4 terminals launch
T+15:   T1 finishes → T0 merges (3 min)
T+20:   T2 finishes → T0 merges (3 min) + visual spot-check
T+20:   T4 finishes (parallel with T2)
T+25:   T3 finishes → T0 merges (3 min)
T+31:   T4 merges (3 min) → full test suite (2 min)
T+35:   Design lint + prod gate (1 min)
T+37:   Fix test failures (0-10 min)
T+40-50: Promote to prod
```

T3 starts immediately — agents build against DESIGN_TOKENS.md class names (spec), not obsidian.css (implementation). CSS available at render time after T2 merge.

## Interface Contracts (expanded per c.ai)

### Contract 1: `get_cached_or_compute()` (1A builds, 1B+1C consume)

```python
def get_cached_or_compute(cache_key: str, compute_fn: callable, ttl_minutes: int = 30) -> dict:
    """
    Returns compute_fn result dict. On cache hit, adds:
        _cached: True
        _cached_at: "2026-02-27T15:30:00" (ISO 8601)
    On cache miss: calls compute_fn(), stores as JSON TEXT in page_cache, returns result.
    Cache write failure is non-fatal.
    DuckDB: ? params. Postgres: match web/auth.py pattern.
    """

def invalidate_cache(pattern: str) -> None:
    """SET invalidated_at = NOW() on rows matching SQL LIKE pattern. Non-fatal."""
```

### Contract 2: Brief template context (1B→3A)

```python
brief_data['cached_at'] = brief_data.get('_cached_at')  # ISO string or None
# brief_data is a plain dict — Jinja accesses via {{ brief.cached_at }}
# None = fresh compute, no badge shown. String = show "Updated X ago" badge.
# can_refresh dropped — hardcode refresh button in template.
```

### Contract 3: obsidian.css (2A→T3)

T3 agents reference class names from DESIGN_TOKENS.md, not obsidian.css. Full class list documented in spec. T2 merges before T3 so CSS is available at render time.

## Intra-T1: `web/app.py` Section Boundaries

- **Agent 1A** owns `_ensure_tables()` — adds page_cache DDL
- **Agent 1D** owns `@app.after_request` — adds Cache-Control headers
- **T1 internal merge:** 1A first, then 1D. Neither touches the other's section.

## CSS Coexistence (risk: Medium/Medium)

Both `design-system.css` (old) and `obsidian.css` (new) load simultaneously.

**Mitigations:**
1. obsidian.css loads AFTER design-system.css — later wins on equal specificity
2. Migrated templates REMOVE old classes, replace with token classes
3. T0 visual spot-check after T2 merge, before T3 merge
4. Visual conflicts that lint misses → score-3 hotfix

## Cache Invalidation Strategy

- `invalidate_cache("brief:%")` — invalidate ALL briefs when any cron data changes
- ONE invalidation call per cron run, not per-change
- Cron pre-compute (every 15 min) recomputes stale entries on schedule
- No per-change recompute — debouncing built into the architecture

## Risk Assessment (updated)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CSS specificity conflicts (dual stylesheet) | Medium | Medium | Load order, class removal, T0 spot-check |
| T4 tests fail after merge | Medium | Medium | Interface contracts above. Budget 10 min. >5 failures = sprint extension |
| index.html too complex for full migration | Medium | High | 3C targets structural elements only. Must verify auth home renders |
| Migration breaks Jinja logic | Medium | High | Change CSS only, NOT Jinja structure. Violations in Jinja blocks: leave them |
| obsidian.css wrong class names | Low | High | T0 grep-checks after T2 merge before allowing T3 |
| brief cache vars missing for T3 | Low | Medium | T1 merges first. Contract above. Cold cache = None = no badge |
| Cache invalidation hammering | Low | Medium | One invalidation per cron run, not per change |
| DuckDB/Postgres DDL divergence | Low | Medium | Match web/auth.py patterns |

## Failure Recovery

| Scenario | Action |
|---|---|
| One agent fails | Terminal merges other 3. Failed task becomes follow-up |
| Entire terminal fails | Merge other 3 terminals. Failed terminal = follow-up sprint |
| obsidian.css wrong | T0 spot-check catches. Fix before T3 merge |
| Merge conflicts | File owner wins. `git checkout --theirs` for non-owner |
| >5 test failures | Stop. Diagnose. Fix or defer. Don't push broken |
| Prod gate HOLD (≤2) | Fix blocking issues. Auth/secret = fix immediately |
| Prod gate score 3 | Promote. Mandatory hotfix 48h. Ratchet enforces |
| Landing looks wrong | CSS coexistence issue. Fix obsidian.css specificity |
| Sprint finishes at 3/5 | Ship. Hotfix session. Not a sprint failure |

## File Ownership Matrix

**T1:** helpers.py, app.py (sections), routes_misc.py, routes_cron.py, prod_gate.py
**T2:** obsidian.css, head_obsidian.html, landing.html, search_results_public.html, results.html, methodology.html, about_data.html, demo.html, nav.html, error.html, login_prompt.html
**T3:** brief.html, report.html, portfolio.html, project_detail.html, index.html, auth_login.html, account_prep.html, beta_request.html, feedback_widget.html, watch_button.html, toast.js
**T4:** component_goldens.py, test_*.py (4 new files), docs/, scenarios-qs7-4d.md

**Cross-terminal conflicts: ZERO.**

## What Ships / What Doesn't

**Ships:** <200ms brief, obsidian.css (26 components), 9 templates migrated, error pages, toast system, prod gate v2, component goldens, 40+ tests, 25 scenarios drained

**Deferred:** Admin templates (13), plan analysis templates (14), email templates, service worker cache, visual regression baseline, date picker/tooltips/badges
