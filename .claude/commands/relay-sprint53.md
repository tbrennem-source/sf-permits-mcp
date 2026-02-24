---
name: relay-sprint53
description: "termRelay QA swarm for Sprint 53. Spawn parallel Playwright agents by persona to verify staging deployment. Escalate visual-only checks to DeskRelay."
---

# Sprint 53 termRelay Orchestrator

You are the termRelay QA orchestrator. Verify the Sprint 53 build against staging using parallel headless Playwright agents, one per persona/domain.

## MODEL ROUTING

- You (orchestrator): Opus — strategic reasoning, result synthesis, escalation decisions
- termRelay agents: Sonnet — Playwright execution, DOM assertions, screenshot capture
- CC handles routing automatically via `CLAUDE_CODE_SUBAGENT_MODEL` env var and agent frontmatter

## termRelay ARCHITECTURE

```
termRelay Orchestrator (Opus, Terminal CC)
    |
    |--- Agent R1 (Sonnet): Admin persona — admin pages, cost/pipeline dashboards
    |--- Agent R2 (Sonnet): Homeowner persona — public search, reports, plan analysis
    |--- Agent R3 (Sonnet): Expediter persona — morning brief, portfolio, consultants
    |--- Agent R4 (Sonnet): Mobile regression — 375px/768px viewport sweep
    |
    v
termRelay-REPORT.md + DeskRelay escalations (visual-only, if any)
```

## BROWSER ISOLATION RULES

**Each agent gets its own isolated Playwright browser context.** This is critical for parallel execution.

```python
# Each agent creates its OWN browser — no shared state
browser = playwright.chromium.launch(headless=True)
context = browser.new_context(
    # R4 sets viewport here; others use default
    viewport={"width": 375, "height": 812} if mobile else None
)
page = context.new_page()
```

- R1, R2, R3: separate browser instances, default 1280x720 viewport
- R4: separate browser instance, parameterized viewports (375px, 768px)
- Each agent manages its own cookies/session — no session bleed between personas
- Each agent closes its browser when done

## SCREENSHOT FILE ISOLATION

Each agent writes to its own directory. **NO shared output paths.**

```
qa-results/
  relay/
    r1-admin/
      staging_banner.png
      admin_dashboard.png
      cost_dashboard.png
      pipeline_dashboard.png
      prod_test_login_404.png
    r2-homeowner/
      homepage.png
      search_results.png
      admin_blocked_403.png
      plan_analysis_form.png
    r3-expediter/
      morning_brief.png
      pipeline_health_section.png
      consultant_page.png
      account_page.png
    r4-mobile/
      homepage_375.png
      homepage_768.png
      search_375.png
      search_768.png
      admin_375.png
      brief_375.png
```

## PRE-FLIGHT

1. Staging is live: `curl -s https://sfpermits-ai-staging.up.railway.app/health`
2. Test login works: `curl -s -X POST .../auth/test-login -H "Content-Type: application/json" -d '{"secret":"...","email":"test-admin@sfpermits.ai"}'`
3. SWARM-REPORT.md exists and shows all build sessions COMPLETE
4. Playwright + Chromium installed: `python -c "from playwright.sync_api import sync_playwright; print('OK')"`

If any fail, STOP and report.

## AGENT DEFINITIONS

### Agent R1: Admin Persona
**Screenshot dir:** `qa-results/relay/r1-admin/`
**Login as:** `test-admin@sfpermits.ai` (is_admin=True)
**Own browser instance:** Yes — launch, login, test, screenshot, close

**Checks:**
1. POST /auth/test-login → 200 + session cookie set
2. GET / → homepage loads, staging banner visible (yellow bar, text "STAGING")
3. GET /admin → admin dashboard loads (not 403)
4. GET /admin/costs → cost tracking dashboard renders, shows $0.00 today
5. GET /admin/pipeline → pipeline health dashboard renders, shows check statuses
6. GET /account → shows admin role, username
7. **SAFETY:** POST /auth/test-login on PROD URL → must return 404

**Playwright assertions:** HTTP status codes, `page.locator()` for DOM elements, `page.text_content()` for text matching
**Each check:** screenshot BEFORE assertion (evidence regardless of pass/fail)

### Agent R2: Homeowner Persona
**Screenshot dir:** `qa-results/relay/r2-homeowner/`
**Login as:** `test-homeowner@sfpermits.ai` (is_admin=False)
**Own browser instance:** Yes

**Checks:**
1. POST /auth/test-login with homeowner email → 200
2. GET / → homepage loads, search form present, staging banner visible
3. Submit search for "Mission" neighborhood → results render with permit cards
4. GET /admin → 403 or redirect (non-admin blocked)
5. GET /analyze → plan analysis upload form accessible
6. Staging banner consistent across all pages

### Agent R3: Expediter Persona
**Screenshot dir:** `qa-results/relay/r3-expediter/`
**Login as:** `test-expediter@sfpermits.ai` (is_admin=False, cohort="consultants")
**Own browser instance:** Yes

**Checks:**
1. POST /auth/test-login with expediter email → 200
2. GET /brief → morning brief renders (or appropriate empty state)
3. Pipeline health section present in brief (top of page, Session C feature)
4. GET /consultants → consultant search page loads with form
5. GET /account → shows correct role/cohort

### Agent R4: Mobile + Regression
**Screenshot dir:** `qa-results/relay/r4-mobile/`
**Login as:** `test-admin@sfpermits.ai` (needs admin access for full page coverage)
**Own browser instance:** Yes — TWO contexts (375px and 768px)

**Pages to sweep:** /, /search (with results), /consultants, /account, /admin, /admin/costs, /admin/pipeline, /brief, /analyze

**Per page, per viewport:**
1. Screenshot full page
2. Assert: `document.body.scrollWidth <= window.innerWidth` (no horizontal overflow)
3. Assert: all `<a>`, `<button>`, `<input>` have offsetWidth >= 44 AND offsetHeight >= 44
4. Assert: no computed `font-size` below 14px on body text elements
5. Assert: tables wrapped in overflow-x container

**Report format:** matrix of page × viewport × check → PASS/FAIL

## ORCHESTRATION PROTOCOL

1. Create `qa-results/relay/` directory structure
2. Spawn all 4 agents in parallel
3. Each agent: launch browser → login → run checks → save screenshots → close browser → return results
4. Collect all results
5. Assemble termRelay-REPORT.md

## termRelay-REPORT.md

```markdown
# Sprint 53 termRelay Report
**Date:** [timestamp]
**Staging URL:** https://sfpermits-ai-staging.up.railway.app
**Duration:** [total time]
**Browser:** Chromium (headless) via Playwright

## Summary
| Agent | Persona | Viewport | Checks | Passed | Failed |
|-------|---------|----------|--------|--------|--------|
| R1 | Admin | 1280x720 | X | Y | Z |
| R2 | Homeowner | 1280x720 | X | Y | Z |
| R3 | Expediter | 1280x720 | X | Y | Z |
| R4 | Mobile | 375x812 | X | Y | Z |
| R4 | Tablet | 768x1024 | X | Y | Z |
| **Total** | | | **X** | **Y** | **Z** |

## Passed Checks
[List of all passing checks — brief, one line each]

## Failed Checks — Auto-Fixable
[Failures that Terminal CC can fix with code changes]
| Check | Agent | Screenshot | Proposed Fix |
|-------|-------|-----------|-------------|
| ... | ... | r4-mobile/admin_375.png | Add overflow-x:auto to .table-container |

## Failed Checks — Visual Judgment Needed (DeskRelay ESCALATION)
[Failures requiring human visual assessment]
| Check | Screenshot | Question |
|-------|-----------|----------|
| ... | r2-homeowner/search_results.png | "Does card spacing look right at this density?" |

## Cross-Browser Note
This termRelay tested Chromium only. Safari, Firefox, and mobile-native browsers
are deferred to Sprint 55 (beta testing phase). Tracked as backlog item.

## Screenshots Index
[Full list of all screenshots with paths]
```

## AUTO-FIX PROTOCOL

If the orchestrator finds auto-fixable failures (CSS issues, missing elements):
1. Create branch `sprint53/relay-fixes`
2. Apply fixes
3. Run `pytest tests/ -v --timeout=30 -q`
4. Merge to main if tests pass
5. Push → Railway redeploys staging
6. Re-run ONLY the failed checks to verify fix

## DeskRelay Escalation

Only if termRelay-REPORT.md has "Visual Judgment Needed" items.

Tim opens Desktop CC:
```
Read qa-results/relay/termRelay-REPORT.md from sf-permits-mcp repo.
[N] checks need visual judgment. For each:
- Open the screenshot at the listed path
- Navigate to the staging URL for the page in question
- Assess whether the visual issue is a real problem or acceptable
- Report PASS (acceptable) or FAIL (needs fix) with explanation
```

Target: ≤10 visual checks. If more, something went wrong with the Playwright assertions.

## ERROR HANDLING

- Staging unreachable: STOP all agents, report immediately
- Test-login fails: STOP, report "auth broken — Session A build issue"
- Single agent crash: log error, continue others, note in report
- Agent timeout (10 min): mark TIMEOUT, proceed with others
