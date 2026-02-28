<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs3-c-testing.md and execute it" -->

# Quad Sprint 3 — Session C: Testing Infrastructure

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs3-c
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs3-c before any code changes.
```

## SETUP — Session Bootstrap

1. `cd /Users/timbrenneman/AIprojects/sf-permits-mcp`
2. `git checkout main && git pull origin main`
3. Use EnterWorktree with name `qs3-c`
4. `git tag pre-qs3-c`

If worktree exists: `git worktree remove .claude/worktrees/qs3-c --force 2>/dev/null; true`

---

## PHASE 1: READ

1. `CLAUDE.md` — project structure
2. `tests/e2e/conftest.py` — READ THOROUGHLY. 12 personas already defined, base_url fixture, test_login_secret, login_as() function, browser_context_args
3. `tests/e2e/test_scenarios.py` — existing Flask client tests. You'll REWRITE to Playwright.
4. `tests/e2e/test_links.py` — existing dead link spider (100-page cap). You'll EXTEND.
5. `tests/e2e/test_smoke.py` — existing smoke tests (Sprint 68-D)
6. `scripts/visual_qa.py` — existing visual QA tool. Supports --capture-goldens. You'll wrap it.
7. `scenario-design-guide.md` — 73 approved scenarios. You'll cite IDs in QA.

**Pre-flight audit confirmed:**
- 12 personas in conftest.py (admin, expediter, homeowner, architect, contractor, engineer, developer, planner, reviewer, owner, inspector, guest)
- test_scenarios.py exists but uses Flask test client (no real browser)
- test_links.py exists with 100-page cap
- visual_qa.py exists with --capture-goldens and --journeys flags
- scripts/seed_test_personas.py does NOT exist — personas are in conftest.py only
- scripts/capture_baselines.py does NOT exist

### DO NOT REBUILD
- The 12 personas in conftest.py — already defined
- The Flask client tests in test_scenarios.py — you're REWRITING to Playwright, not adding alongside
- The basic spider in test_links.py — you're EXTENDING it
- visual_qa.py — you're wrapping it, not rewriting it

### E2E Test Server Pattern
Playwright tests need a running server. Use this pattern:
```python
import threading
from web.app import create_app

@pytest.fixture(scope="session")
def live_server():
    app = create_app()
    app.config["TESTING"] = True
    server = threading.Thread(target=app.run, kwargs={"port": 5001, "use_reloader": False})
    server.daemon = True
    server.start()
    import time; time.sleep(1)  # Wait for server startup
    yield "http://localhost:5001"
```

If conftest.py already has a similar fixture, extend it. If not, add it.

---

## PHASE 2: BUILD

### Task C-1: Upgrade test_scenarios.py to Playwright (~90 min)
**Files:** `tests/e2e/test_scenarios.py` (REWRITE), `tests/e2e/conftest.py` (extend with live_server + Playwright fixtures)

**Extend conftest.py:**
- Add `live_server` fixture (threaded Flask app, port 5001, TESTING=True)
- Add `page` fixture (Playwright browser page, navigates to live_server)
- Add `auth_page(persona_name)` fixture factory (logs in via test-login, returns page)

**Rewrite test_scenarios.py with Playwright tests:**

Read `scenario-design-guide.md` and implement browser tests for the top 20 testable scenarios. Group by persona:

**Anonymous (no login):**
- Landing page loads, search bar visible, capability cards present
- Search for "1455 Market St" returns permit results
- Methodology page loads with 8+ sections
- About-data page loads with data inventory
- Demo page loads with permit data
- Intel preview panel appears on search results (HTMX loads)

**Free user (login via test-login):**
- Dashboard renders after login
- Search with intel panel shows routing progress
- Account page accessible
- Watch list functionality works

**Admin:**
- /admin routes accessible
- Feedback queue renders
- DQ dashboard renders
- Pipeline health renders

**Each test:**
- Uses Playwright `page.goto()`, `page.locator()`, `expect()`
- Takes screenshot: `page.screenshot(path=f"qa-results/screenshots/e2e/{test_name}.png")`
- Cites scenario ID in docstring: `"""SCENARIO-37: Anonymous landing page renders."""`

**Target: 20+ Playwright browser tests**

### Task C-2: Extend Dead Link Spider (~30 min)
**Files:** `tests/e2e/test_links.py` (EXTEND)

- Increase page cap from 100 to 200
- Add authenticated crawl: log in as admin, crawl /admin/* pages too
- Track response time per page, flag any >5 seconds
- Separate internal links from external links (don't follow external)
- Output summary at end: total crawled, broken (non-200), slow (>5s)

### Task C-3: Sprint 69 Visual Baselines (~20 min)
**Files:** `scripts/capture_baselines.py` (NEW)

Thin wrapper around visual_qa.py:
```python
#!/usr/bin/env python3
"""Capture visual baselines for the current sprint."""
import subprocess, sys, os

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5001"
    sprint = sys.argv[2] if len(sys.argv) > 2 else "current"
    secret = os.environ.get("TEST_LOGIN_SECRET", "")

    cmd = [
        sys.executable, "scripts/visual_qa.py",
        "--url", url,
        "--sprint", sprint,
        "--capture-goldens",
    ]
    env = os.environ.copy()
    if secret:
        env["TEST_LOGIN_SECRET"] = secret

    print(f"Capturing baselines for {sprint} against {url}")
    subprocess.run(cmd, env=env, check=True)
    print(f"Baselines saved to qa-results/baselines/{sprint}/")

if __name__ == "__main__":
    main()
```

Run it locally if possible: `python scripts/capture_baselines.py http://localhost:5001 sprint69`
If server can't start (no DB), document the command for Tim to run against staging.

### Task C-4: Launch QA Plan (~30 min)
**Files:** `docs/LAUNCH_QA_PLAN.md` (NEW)

Write the QA plan:

```markdown
# Launch QA Plan — sfpermits.ai

## Automated Tests
- pytest: 3,500+ unit/integration tests
- Playwright e2e: 20+ browser scenario tests
- Dead link spider: 200-page crawl
- Visual regression: visual_qa.py --capture-goldens

## Smoke Test Checklist (run before every promote-to-prod)
1. curl /health → status ok, expected table count
2. curl /api/stats → real numbers (permits > 1M)
3. curl / → 200, landing page renders
4. curl /search?q=1455+Market+St → 200, permits appear
5. curl /methodology → 200
6. curl /about-data → 200
7. curl /robots.txt → 200, disallows /admin
8. pytest tests/ --ignore=tests/test_tools.py -q → all pass

## Manual Test Scripts (15 critical journeys)
[15 numbered scripts covering: first visit, search, signup, login,
 property report, morning brief, plan analysis upload, Permit Prep,
 admin dashboard, feedback triage, mobile experience, etc.]

## Visual Regression Process
1. Before sprint: capture baselines with visual_qa.py --capture-goldens
2. After sprint: run visual_qa.py (compares against baselines)
3. Review diffs: any pages with >5% pixel change flagged
4. Update baselines after review

## E2E Coverage Map
| Scenario ID | Description | Automated? | Test File |
[Map scenario IDs from design guide to test files]
```

---

## PHASE 3: TEST

```bash
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py -q
```

The Playwright tests ARE the new tests. Verify:
- `pytest tests/e2e/test_scenarios.py -v` — 20+ pass
- `pytest tests/e2e/test_links.py -v` — spider runs, 0 broken links
- `pytest tests/e2e/test_smoke.py -v` — existing smoke tests still pass
- Full suite: `pytest tests/ --ignore=tests/test_tools.py -q`

**Target: 30+ new/upgraded tests**

---

## PHASE 4: SCENARIOS

Read `scenario-design-guide.md`. Cite which scenario IDs your e2e tests cover:
- "test_scenarios.py covers: SCENARIO-1, SCENARIO-5, SCENARIO-12, ..."

If any scenarios can't be automated (require human judgment), note them in the Launch QA Plan under "Manual Test Scripts."

---

## PHASE 5: QA (termRelay)

The e2e test suite IS the QA. Run it:
```
pytest tests/e2e/ -v --tb=short
```

Write results to `qa-results/qs3-c-results.md`:
```
## QA Results — Session C (Testing Infrastructure)
Tests run: [count]
Passed: [count]
Failed: [count]
Skipped: [count]

Scenario coverage: [list of scenario IDs covered]
Dead link spider: [pages crawled, broken links]
Baselines: [captured / not captured + reason]
```

---

## PHASE 5.5: VISUAL REVIEW
N/A — testing infrastructure, no UI pages created.

---

## PHASE 6: CHECKCHAT

### 1-6: Standard

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Estimated | Actual |
|--------|-----------|--------|
| Wall clock time | 2-3 hours | [actual] |
| New tests | 30+ | [count] |
| Total tests | ~3,460 | [pytest output] |
| Tasks completed | 4 | [N of 4] |
| Tasks descoped | — | [count + reasons] |
| Tasks blocked | — | [count + reasons] |
| Longest task | — | [task, duration] |
| QA checks | e2e suite | [pass/fail] |
| Visual Review avg | N/A | N/A |
| Scenarios proposed | — | [count cited] |
```

### DeskRelay HANDOFF
None — testing infrastructure.

---

## File Ownership (Session C ONLY)
**Own:**
- `tests/e2e/test_scenarios.py` (REWRITE)
- `tests/e2e/test_links.py` (EXTEND)
- `tests/e2e/conftest.py` (extend with live_server + Playwright fixtures)
- `scripts/capture_baselines.py` (NEW)
- `docs/LAUNCH_QA_PLAN.md` (NEW)
- `qa-results/qs3-c-results.md` (NEW)

**Do NOT touch:**
- `web/` (any web files — Sessions A, B, D)
- `src/` (any src files — Session B)
- `scripts/release.py` (Sessions A + D)
- `web/templates/` (Sessions A + D)
- `scenarios-pending-review.md` (Session A owns scenario proposals this sprint)
