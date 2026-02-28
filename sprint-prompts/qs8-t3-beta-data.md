# QS8 Terminal 3: Beta + Data (Sprint 81)

You are the orchestrator for QS8-T3. Spawn 4 parallel build agents, collect results, merge, push to main. Do NOT run the full test suite — T0 handles that in the merge ceremony.

## Pre-Flight (30 seconds — T0 already verified tests + prod health)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T3 start: $(git rev-parse --short HEAD)"
```

## Context

This sprint adds beta onboarding, search intelligence, trade permit data, E2E tests, and a demo seed script. Each agent owns completely separate files — zero cross-agent conflicts expected.

**A separate CC terminal is rebuilding page templates from mockups.** That work touches ONLY web/templates/ layout files and has ZERO overlap with T3's work. No coordination needed.

**Known test exclusions:** `--ignore=tests/test_tools.py --ignore=tests/e2e`

## Agent Preamble (include verbatim in every agent prompt)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. The orchestrator handles all merges.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-pending-review-qs8-t3-{agent}.md
  * CHANGELOG-qs8-t3-{agent}.md
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e 2>&1 | tail -10

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → Postgres needs ON CONFLICT DO UPDATE
- DuckDB uses ? placeholders, Postgres uses %s. Check src.db.BACKEND.
- conn.execute() works on DuckDB. Postgres needs cursor.
- before_request hooks must check app.config.get("TESTING") — daily limits accumulate across test files.
- CRON_WORKER env var needed for cron endpoint tests.

CSS Variable Mapping (for templates):
- --font-display = --mono (data, addresses, numbers)
- --font-body = --sans (prose, labels, descriptions)
- Do NOT use --font-display or --font-body. They are LEGACY names.
- Read docs/DESIGN_TOKENS.md before creating any template.
- Check web/static/mockups/ for approved page designs.
```

## File Ownership Matrix

| Agent | Files Owned |
|-------|-------------|
| A | `web/routes_auth.py`, `web/feature_gate.py`, `web/templates/welcome.html`, new `web/templates/onboarding_*.html` |
| B | `web/routes_search.py`, `web/routes_public.py` |
| C | `src/ingest.py` (ADD functions only), `datasets/` |
| D | `tests/e2e/test_onboarding_scenarios.py` (NEW), `tests/e2e/test_performance_scenarios.py` (NEW), `scripts/seed_demo.py` (NEW) |

**Cross-agent overlap: ZERO.**

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent A: Beta Onboarding + Feature Gates

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Multi-step onboarding wizard + PREMIUM tier + feature flags

### File Ownership
- web/routes_auth.py
- web/feature_gate.py
- web/templates/welcome.html
- web/templates/onboarding_step1.html (NEW)
- web/templates/onboarding_step2.html (NEW)
- web/templates/onboarding_step3.html (NEW)

### Read First
- web/routes_auth.py (current onboarding — first-login detection, onboarding_complete)
- web/feature_gate.py (FeatureTier enum, feature registry, gate checks)
- web/templates/welcome.html (current welcome page)
- web/auth.py (invite code validation, user creation)
- docs/DESIGN_TOKENS.md (for template styling — read FULL file)
- web/static/mockups/ (check if onboarding mockup exists — if so, follow it exactly)

CSS VARIABLE MAPPING:
- --mono for data/addresses/numbers
- --sans for prose/labels/descriptions
- Do NOT use --font-display or --font-body (legacy names)

### Build

Task A-1: Multi-step onboarding wizard (3 steps):
- Step 1: "Welcome to sfpermits.ai" — role selector (homeowner/architect/expediter/contractor)
  Saves role to user profile
- Step 2: "Watch your first property" — pre-filled with 1455 Market St demo parcel
  "Add to portfolio" button → creates watch_item. "Skip" option.
- Step 3: "Your morning brief" — sample brief card for demo parcel
  "Go to Dashboard" CTA

Task A-2: Add PREMIUM tier to FeatureTier enum in feature_gate.py:
- PREMIUM between AUTHENTICATED and ADMIN
- Gate plan analysis (full) + entity deep-dive behind PREMIUM
- Beta users get PREMIUM free (check invite_code prefix or user.subscription_tier)

Task A-3: Feature flag expansion — 5 new features:
- plan_analysis_full, entity_deep_dive, export_pdf, api_access, priority_support
- Default all to AUTHENTICATED during beta (everyone gets everything)
- Comment: "Raise to PREMIUM when beta period ends"

All templates MUST use Obsidian design tokens.

### Test
Write tests/test_sprint_81_1.py:
- test_onboarding_step1_renders
- test_onboarding_saves_role
- test_onboarding_step2_creates_watch_item
- test_premium_tier_exists
- test_feature_flags_registered

### Output Files
- scenarios-pending-review-qs8-t3-a.md
- CHANGELOG-qs8-t3-a.md

### Commit
feat: multi-step onboarding wizard + PREMIUM tier + feature flags (QS8-T3-A)
""")
```

---

### Agent B: Search NLP Improvement

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Search NLP parser + empty result guidance + result ranking

### File Ownership
- web/routes_search.py
- web/routes_public.py

### Read First
- web/routes_search.py (full — understand search handling)
- web/routes_public.py (public search endpoint)
- src/tools/permit_lookup.py (_lookup_by_address, _suggest_street_names)

### Build

Task B-1: Natural language query parser:
```python
def parse_search_query(q: str) -> dict:
    # "kitchen remodel in the Mission" → description_search="kitchen remodel", neighborhood="Mission"
    # "permits at 123 Market St" → street_number="123", street_name="Market"
    # "new construction SoMa 2024" → permit_type="new construction", neighborhood="SoMa", date_from="2024-01-01"
    # Use regex + keyword matching (no ML needed)
    # Match neighborhoods against known SF list
    # Detect address patterns, permit types, years
    # Everything unmatched → description_search
```

Task B-2: Empty result guidance:
- 0 results → show "Did you mean?" suggestions, common examples, link to /demo

Task B-3: Result ranking:
- Exact address → first. Permit number → second. Description match → third.
- Add badges: "Address Match", "Permit", "Description"

### Test
Write tests/test_sprint_81_2.py:
- test_parse_neighborhood ("in the Mission" → neighborhood="Mission")
- test_parse_address ("123 Market St" → street_number + street_name)
- test_parse_permit_type ("new construction" → permit_type filter)
- test_parse_year ("2024" → date_from)
- test_parse_combined ("kitchen remodel Mission 2024" → all fields)
- test_empty_results_shows_suggestions

### Output Files
- scenarios-pending-review-qs8-t3-b.md
- CHANGELOG-qs8-t3-b.md

### Commit
feat: search NLP parsing + empty result guidance + ranking (QS8-T3-B)
""")
```

---

### Agent C: Trade Permits Data Expansion

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Add electrical/plumbing/boiler permit ingest functions

### File Ownership
- src/ingest.py (ADD new functions only — do NOT modify existing functions)
- datasets/ (add catalog entries if needed)

### Read First
- src/ingest.py (understand ingest pipeline — SODA query, transform, load)
- datasets/datasets.json (dataset catalog)
- src/db.py (table creation, BACKEND, get_connection)

### Build

Task C-1: ingest_electrical_permits(conn, limit=None)
- SODA endpoint: sb82-77pd (~200K records)
- Match permits table schema, add permit_subtype='electrical'

Task C-2: ingest_plumbing_permits(conn, limit=None)
- SODA endpoint: p7e6-mr2g (~200K records)

Task C-3: ingest_boiler_permits(conn, limit=None)
- SODA endpoint: iif8-dssv (~50K records)

Task C-4: CLI integration
- python -m src.ingest --electrical --plumbing --boiler
- Add to argparse in __main__ block

IMPORTANT: Do NOT run actual ingest. Write functions + test with mocked SODA responses.

### Test
Write tests/test_sprint_81_3.py:
- Mock SODA responses, verify transform logic, verify INSERT queries

### Output Files
- scenarios-pending-review-qs8-t3-c.md
- CHANGELOG-qs8-t3-c.md

### Commit
feat: electrical/plumbing/boiler permit ingest functions (QS8-T3-C)
""")
```

---

### Agent D: E2E Tests + seed_demo.py

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: E2E tests for recent features + demo seed script

### File Ownership (ALL NEW)
- tests/e2e/test_onboarding_scenarios.py (NEW)
- tests/e2e/test_performance_scenarios.py (NEW)
- scripts/seed_demo.py (NEW)

### Read First
- tests/e2e/conftest.py (fixtures: live_server, auth_page, login_as, PERSONAS)
- tests/e2e/test_scenarios.py (existing E2E patterns)
- tests/e2e/test_severity_scenarios.py (most recent E2E — Sprint 77)
- web/routes_auth.py (onboarding endpoints)
- web/routes_misc.py (static pages — /methodology, /about-data, /demo)
- src/db.py (get_connection, table schemas — for seed_demo.py)

### Build

Task D-1: tests/e2e/test_onboarding_scenarios.py (8+ tests):
- test_welcome_page_renders_for_new_user
- test_onboarding_dismissible
- test_demo_page_loads_without_auth
- test_demo_page_shows_property_data
- test_methodology_page_has_multiple_sections
- test_about_data_page_has_dataset_inventory
- test_beta_request_form_submits
- test_portfolio_empty_state_for_new_user

Task D-2: tests/e2e/test_performance_scenarios.py (8+ tests):
- test_health_endpoint_under_500ms
- test_landing_page_under_1s
- test_methodology_under_1s
- test_demo_page_under_2s
- test_search_returns_under_2s
- test_no_500_errors_on_rapid_navigation (5 pages quickly)
- test_csp_headers_on_all_pages
- test_static_assets_cached (Cache-Control header)

Task D-3: scripts/seed_demo.py
```python
#!/usr/bin/env python3
"""Seed a user account with demo data for demos.
Usage: python scripts/seed_demo.py --email tbrennem@gmail.com
"""
# Idempotent. Safe to run multiple times.
# 1. Find or confirm user exists
# 2. Add 3 watch_items: 1455 Market (3507/004), 146 Lake (1386/025), 125 Mason (0312/005)
# 3. Add 5 recent searches
# 4. Print summary
```

All E2E tests use live_server fixture. Use page.goto() + assert response status + timing.

### Test
- Run E2E tests: pytest tests/e2e/test_onboarding_scenarios.py tests/e2e/test_performance_scenarios.py -v
- Verify seed script parses: python -c "import scripts.seed_demo"

### Output Files
- scenarios-pending-review-qs8-t3-d.md
- CHANGELOG-qs8-t3-d.md

### Commit
test: E2E onboarding + performance scenarios + seed_demo.py (QS8-T3-D)
""")
```

---

## Post-Agent: Merge + Push

After all 4 agents complete:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Merge in order: C first (data layer), A (auth), B (search), D (tests)
git merge <agent-c-branch> --no-edit
git merge <agent-a-branch> --no-edit
git merge <agent-b-branch> --no-edit
git merge <agent-d-branch> --no-edit

# Concatenate per-agent output files
cat scenarios-pending-review-qs8-t3-*.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-qs8-t3-*.md >> CHANGELOG.md 2>/dev/null

# Push to main. Do NOT run the full test suite — T0 handles that.
git push origin main
```

## Report Template

```
T3 (Beta + Data) COMPLETE
  A: Onboarding + features: [PASS/FAIL]
  B: Search NLP:            [PASS/FAIL]
  C: Trade permits ingest:  [PASS/FAIL]
  D: E2E tests + seed:      [PASS/FAIL] [N E2E tests]
  Scenarios: [N] across 4 files
  Pushed: [commit hash]
```
