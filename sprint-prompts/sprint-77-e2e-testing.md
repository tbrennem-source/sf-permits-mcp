<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/sprint-77-e2e-testing.md and execute it" -->

# Sprint 77 — E2E Scenario Testing Blitz

You are the orchestrator for Sprint 77. Spawn 4 parallel build agents, collect results, merge, test, push.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git tag pre-sprint-77
```

## IMPORTANT CONTEXT
This sprint creates ONLY Playwright E2E test files. Zero production code. Zero template changes. Zero shared file conflicts. All 4 agents write to separate NEW test files.

Tests run against a local dev server started by conftest.py fixtures. Read tests/e2e/conftest.py for available fixtures.

73 approved scenarios in scenario-design-guide.md. ~53 E2E tests already exist. Each agent covers 5 uncovered scenarios.

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
- Read scenario-design-guide.md to understand scenario format.
- Read tests/e2e/conftest.py for available fixtures (live_server, auth_page, login_as).
- Read tests/e2e/test_scenarios.py for existing test patterns.
- MERGE RULE: Do NOT merge to main. Commit to worktree branch only.
- DO NOT modify ANY file in web/, src/, or scripts/. ONLY create test files.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- APPEND FILES (dual-write):
  * scenarios-pending-review-sprint-77-N.md (per-agent)
  * scenarios-pending-review.md (shared, append only)
  * CHANGELOG-sprint-77-N.md (per-agent)
- TELEMETRY: Use "Scope changes" (not "descoped"), "Waiting on" (not "blocked").
```

---

### Agent 77-1: Severity + Property Health Scenarios

**PHASE 1: READ**
- scenario-design-guide.md (find severity/property/health scenarios)
- tests/e2e/conftest.py (fixtures)
- tests/e2e/test_scenarios.py (pattern reference)
- web/templates/report.html (property report structure — what elements to assert on)

**PHASE 2: BUILD**

Create tests/e2e/test_severity_scenarios.py with 5+ Playwright tests:

Test 77-1-1: Property report page loads for a known parcel
- Navigate to /report/3507/004 (or a test block/lot)
- Assert page returns 200 and contains permit data

Test 77-1-2: Search results display for address query
- Navigate to /search?q=market
- Assert results appear (check for .search-result-card or similar element)

Test 77-1-3: Portfolio page loads for authenticated user
- Login via test-login, navigate to /portfolio
- Assert page loads (200 status)

Test 77-1-4: Brief page renders sections for authenticated user
- Login, navigate to /brief
- Assert morning brief sections visible (changes, health, inspections, etc.)

Test 77-1-5: Demo page shows property intelligence without auth
- Navigate to /demo (no login)
- Assert demo data renders (1455 Market St or similar)

Use authenticated `expediter` persona where needed. All tests should be resilient — use try/except for elements that may not exist in test data.

**PHASE 3: TEST**
Run: pytest tests/e2e/test_severity_scenarios.py -v --timeout=120
Note: may skip if Playwright not installed or dev server fails. That's OK.

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-77-1.md (reference which design-guide scenarios are covered)
CHANGELOG-sprint-77-1.md
Commit: "test: E2E severity + property scenarios (Sprint 77-1)"

**File Ownership:**
Own: tests/e2e/test_severity_scenarios.py (NEW). ZERO production files.

---

### Agent 77-2: Admin + Security Scenarios

**PHASE 1: READ**
- scenario-design-guide.md (admin, security sections)
- tests/e2e/conftest.py
- web/routes_admin.py (admin routes to test)

**PHASE 2: BUILD**

Create tests/e2e/test_admin_scenarios.py with 5+ Playwright tests:

Test 77-2-1: Admin ops page loads with tabs
- Login as admin, navigate to /admin/ops
- Assert page 200, tabs visible (pipeline, quality, activity, feedback)

Test 77-2-2: SQL injection blocked in search
- Navigate to /search?q=' OR 1=1 --
- Assert no 500 error (page handles gracefully)

Test 77-2-3: Directory traversal blocked
- Navigate to /report/../../../etc/passwd
- Assert 404 or redirect, not file contents

Test 77-2-4: CSP headers present
- Fetch any page, check response headers for Content-Security-Policy

Test 77-2-5: Anonymous user rate limiting
- Make 50+ rapid requests to /search
- Assert eventually gets rate limited (429 or similar)

Use admin persona for admin tests, anonymous for security tests.

**PHASE 3-6: TEST, SCENARIOS, QA, CHECKCHAT**
pytest tests/e2e/test_admin_scenarios.py -v
scenarios-pending-review-sprint-77-2.md, CHANGELOG-sprint-77-2.md
Commit: "test: E2E admin + security scenarios (Sprint 77-2)"

**File Ownership:**
Own: tests/e2e/test_admin_scenarios.py (NEW). ZERO production files.

---

### Agent 77-3: Search + Entity Scenarios

**PHASE 1: READ**
- scenario-design-guide.md (search, entity, plan analysis sections)
- tests/e2e/conftest.py
- web/routes_search.py (search route structure)

**PHASE 2: BUILD**

Create tests/e2e/test_search_scenarios.py with 5+ Playwright tests:

Test 77-3-1: Address search returns results
- Login, search for "valencia"
- Assert search results appear

Test 77-3-2: Permit number search returns specific permit
- Login, search for a known permit number
- Assert specific permit detail appears

Test 77-3-3: Empty search shows guidance
- Login, submit empty search
- Assert helpful message appears (not a crash)

Test 77-3-4: Plan analysis upload form renders
- Login, navigate to plan analysis page
- Assert file upload input exists and is functional

Test 77-3-5: Methodology page renders full content
- Navigate to /methodology (no auth)
- Assert page is long (multiple sections), not a stub

Use authenticated user persona for search tests.

**PHASE 3-6: TEST, SCENARIOS, QA, CHECKCHAT**
pytest tests/e2e/test_search_scenarios.py -v
scenarios-pending-review-sprint-77-3.md, CHANGELOG-sprint-77-3.md
Commit: "test: E2E search + entity scenarios (Sprint 77-3)"

**File Ownership:**
Own: tests/e2e/test_search_scenarios.py (NEW). ZERO production files.

---

### Agent 77-4: Auth + Mobile Scenarios

**PHASE 1: READ**
- scenario-design-guide.md (auth, mobile, content sections)
- tests/e2e/conftest.py
- tests/e2e/test_mobile.py (existing mobile test patterns)

**PHASE 2: BUILD**

Create tests/e2e/test_auth_mobile_scenarios.py with 5+ Playwright tests:

Test 77-4-1: Landing page renders for anonymous
- Navigate to / without auth
- Assert hero section visible, search bar present

Test 77-4-2: Authenticated routes redirect to login
- Navigate to /brief without auth
- Assert redirect to /auth/login (or login page content)

Test 77-4-3: No horizontal scroll at 375px
- Set viewport 375x812
- Navigate to / and /demo
- Assert document.body.scrollWidth <= window.innerWidth via page.evaluate()

Test 77-4-4: Mobile navigation works
- Set viewport 375x812
- Navigate to / (authenticated)
- Assert hamburger menu exists OR nav items are accessible

Test 77-4-5: Beta request form renders and accepts input
- Navigate to /beta-request
- Assert form fields present (email, name, reason)
- Fill fields, verify no JS errors

Use mobile viewport: browser.new_context(viewport={"width": 375, "height": 812})

**PHASE 3-6: TEST, SCENARIOS, QA, CHECKCHAT**
pytest tests/e2e/test_auth_mobile_scenarios.py -v
scenarios-pending-review-sprint-77-4.md, CHANGELOG-sprint-77-4.md
Commit: "test: E2E auth + mobile scenarios (Sprint 77-4)"

**File Ownership:**
Own: tests/e2e/test_auth_mobile_scenarios.py (NEW). ZERO production files.

---

## Post-Agent Merge (Orchestrator)

1. Collect results from all 4 agents
2. Merge all branches (zero conflicts expected — all different NEW files)
3. Run unit tests: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q`
4. Run E2E tests standalone: `pytest tests/e2e/ -v --timeout=120` (may skip if Playwright unavailable)
5. `git pull origin main` (get QS6+QS7+QS8), then `git push origin main`
6. Concatenate changelogs + scenarios
7. Report: test count per agent, skips, failures

## Push Order
Sprint 77 pushes LAST. Must pull all prior sprint changes. E2E tests validate the final merged state.
