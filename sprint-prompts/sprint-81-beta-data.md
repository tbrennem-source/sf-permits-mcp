<!-- LAUNCH: Paste into CC terminal 4:
     "Read sprint-prompts/sprint-81-beta-data.md and execute it" -->

# Sprint 81 — Beta Experience + Data Expansion

You are the orchestrator for Sprint 81. Spawn 4 parallel build agents, collect results, merge, test, push.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git tag pre-sprint-81
```

## IMPORTANT CONTEXT

This sprint adds beta onboarding, search intelligence, trade permit data, and E2E tests. Each agent owns completely separate files — zero cross-agent conflicts expected.

**Known DuckDB/Postgres Gotchas:**
- `INSERT OR REPLACE` → Postgres needs `ON CONFLICT DO UPDATE`
- DuckDB uses `?` placeholders, Postgres uses `%s`. Check `src.db.BACKEND` variable.
- Tests run on DuckDB locally. Postgres bugs only surface on staging.
- Any `before_request` hook that blocks requests must check `app.config.get("TESTING")` and return early, or test clients hit limits.

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
- MERGE RULE: Do NOT merge to main. Commit to worktree branch only.
- CONFLICT RULE: Do NOT run git checkout <branch> -- <file>. Report conflicts as BLOCKED.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- DO NOT modify ANY file outside your owned list.
- APPEND FILES (dual-write):
  * scenarios-pending-review-sprint-81-N.md (per-agent)
  * scenarios-pending-review.md (shared, append only)
  * CHANGELOG-sprint-81-N.md (per-agent)
- Test after each task: pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q 2>&1 | tail -5
```

---

### Agent 81-1: Beta Onboarding + Feature Gates

**File Ownership:**
- web/routes_auth.py
- web/feature_gate.py
- web/templates/welcome.html
- web/templates/onboarding_step1.html (NEW)
- web/templates/onboarding_step2.html (NEW)
- web/templates/onboarding_step3.html (NEW)

**PHASE 1: READ**
- web/routes_auth.py (current onboarding flow — first-login detection, onboarding_complete flag)
- web/feature_gate.py (FeatureTier enum, feature registry, gate checks)
- web/templates/welcome.html (current welcome page)
- web/auth.py (invite code validation, user creation)
- docs/DESIGN_TOKENS.md (for template styling)

**PHASE 2: BUILD**

Task 81-1-1: Multi-step onboarding wizard (3 steps):
- Step 1: "Welcome to sfpermits.ai" — role selector (homeowner / architect / expediter / contractor)
  - Saves role to user profile (add role column if needed — check existing schema first)
- Step 2: "Watch your first property" — pre-filled with 1455 Market St demo parcel
  - "Add this to my portfolio" button → creates watch_item for the demo parcel
  - "Skip" option
- Step 3: "Your morning brief" — brief the user on what they'll get
  - Show a sample brief card for the demo parcel
  - "Go to Dashboard" CTA

Task 81-1-2: Add PREMIUM tier to FeatureTier enum in feature_gate.py:
- PREMIUM sits between AUTHENTICATED and ADMIN
- Gate plan analysis (full) and entity network deep-dive behind PREMIUM
- Beta users get PREMIUM for free (check user.tier or invite_code prefix)

Task 81-1-3: Feature flag expansion:
- Add 5 new features to the registry: plan_analysis_full, entity_deep_dive, export_pdf, api_access, priority_support
- Default all to AUTHENTICATED tier during beta (everyone gets everything free)
- Add comment: "Raise to PREMIUM tier when beta period ends"

All templates MUST use Obsidian design tokens (docs/DESIGN_TOKENS.md).

Commit: "feat: multi-step onboarding wizard + PREMIUM tier + feature flags (Sprint 81-1)"

---

### Agent 81-2: Search NLP Improvement

**File Ownership:**
- web/routes_search.py
- web/routes_public.py

**PHASE 1: READ**
- web/routes_search.py (full file — understand search handling)
- web/routes_public.py (public search endpoint)
- src/tools/permit_lookup.py (_lookup_by_address, _suggest_street_names patterns)

**PHASE 2: BUILD**

Task 81-2-1: Natural language query parser — extract structured filters from free text:
- "kitchen remodel in the Mission" → description_search="kitchen remodel", neighborhood="Mission"
- "permits at 123 Market St" → street_number="123", street_name="Market"
- "new construction SoMa 2024" → permit_type="new construction", neighborhood="SoMa", date_from="2024-01-01"
- "ADU" → description_search="ADU" OR permit_type filter

Implementation: regex + keyword matching (no ML needed):
```python
def parse_search_query(q: str) -> dict:
    """Extract structured filters from natural language search query."""
    filters = {}
    # Neighborhood detection (match against known SF neighborhood list)
    # Permit type detection ("new construction", "demolition", "alteration")
    # Address detection (number + street name pattern)
    # Year detection (4-digit number 2000-2030)
    # Everything else → description_search
    return filters
```

Task 81-2-2: Improve empty-result guidance:
- When search returns 0 results, show:
  - "Did you mean?" suggestions (similar addresses)
  - Common search examples
  - Link to /demo for exploration

Task 81-2-3: Search result ranking — when multiple result types match:
- Exact address match → show first
- Permit number match → show second
- Description match → show third
- Add result type badges: "Address Match", "Permit", "Description"

Tests: test_sprint_81_2.py with various natural language queries.
Commit: "feat: search NLP parsing + improved empty results + ranking (Sprint 81-2)"

---

### Agent 81-3: Trade Permits Data Expansion

**File Ownership:**
- src/ingest.py (add new ingest functions — DO NOT modify existing functions, only ADD)
- datasets/ (add new dataset catalog entries if needed)

**PHASE 1: READ**
- src/ingest.py (understand ingest pipeline — SODA query, transform, load patterns)
- datasets/datasets.json (dataset catalog)
- src/db.py (table creation, BACKEND, get_connection)

**PHASE 2: BUILD**

Task 81-3-1: Add electrical permit ingest function:
- SODA endpoint: `sb82-77pd` (Electrical Permits)
- ~200K records
- Function: `ingest_electrical_permits(conn, limit=None)`
- Schema: match the permits table structure where possible, add permit_subtype='electrical'
- Use existing ingest patterns: batch SELECT with offset pagination, transform to match schema, INSERT

Task 81-3-2: Add plumbing permit ingest function:
- SODA endpoint: `p7e6-mr2g` (Plumbing Permits)
- ~200K records
- Function: `ingest_plumbing_permits(conn, limit=None)`

Task 81-3-3: Add boiler permit ingest function:
- SODA endpoint: `iif8-dssv` (Boiler Permits)
- ~50K records (smaller dataset)
- Function: `ingest_boiler_permits(conn, limit=None)`

Task 81-3-4: Add CLI integration:
- `python -m src.ingest --electrical --plumbing --boiler`
- Add to argparse in __main__ block

IMPORTANT: DO NOT run the actual ingest during the sprint (it's slow and hits SODA API).
Write the functions, test with mocked SODA responses, and document the CLI usage.

Tests: test_sprint_81_3.py — mock SODA responses, verify transform logic, verify INSERT queries.
Commit: "feat: electrical/plumbing/boiler permit ingest functions (Sprint 81-3)"

---

### Agent 81-4: E2E Tests for Recent Features

**File Ownership (ALL NEW):**
- tests/e2e/test_onboarding_scenarios.py
- tests/e2e/test_performance_scenarios.py

**PHASE 1: READ**
- tests/e2e/conftest.py (fixtures: live_server, auth_page, login_as, PERSONAS)
- tests/e2e/test_scenarios.py (existing patterns)
- tests/e2e/test_severity_scenarios.py (Sprint 77 patterns — most recent)
- web/routes_auth.py (onboarding endpoints)
- web/routes_misc.py (static pages)

**PHASE 2: BUILD**

Create tests/e2e/test_onboarding_scenarios.py (8+ tests):
- test_welcome_page_renders_for_new_user
- test_onboarding_dismissible
- test_demo_page_loads_without_auth
- test_demo_page_shows_property_data
- test_methodology_page_has_multiple_sections
- test_about_data_page_has_dataset_inventory
- test_beta_request_form_submits
- test_portfolio_empty_state_for_new_user

Create tests/e2e/test_performance_scenarios.py (8+ tests):
- test_health_endpoint_under_500ms
- test_landing_page_under_1s
- test_methodology_under_1s (should be fast — static page)
- test_demo_page_under_2s
- test_search_returns_under_2s
- test_no_500_errors_on_rapid_navigation (hit 5 pages in quick succession)
- test_csp_headers_on_all_pages
- test_static_assets_cached (check Cache-Control header on /static/ files)

All tests use the live_server fixture (Flask subprocess). Use `page.goto()` and assert response status + timing.

Commit: "test: E2E onboarding + performance scenarios (Sprint 81-4)"

---

## Post-Agent Merge (Orchestrator)

1. Collect results from all 4 agents
2. Merge all branches (conflict only in scenarios-pending-review.md — resolve by keeping both)
3. Run unit tests: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q`
4. Run E2E tests: `pytest tests/e2e/ -v --timeout=120` (may skip without Playwright)
5. Push to main
6. Report: features built, tests added, any BLOCKED items
