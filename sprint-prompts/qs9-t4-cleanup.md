# QS9 Terminal 4: Cleanup + Documentation + API Routes

You are the orchestrator for QS9-T4. Spawn 4 parallel build agents, collect results, merge, push to main. Do NOT run the full test suite — T0 handles that.

## Pre-Flight (30 seconds)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T4 start: $(git rev-parse --short HEAD)"
```

## File Ownership

| Agent | Files Owned |
|-------|-------------|
| A | `web/routes_api.py` |
| B | `scenarios-pending-review.md`, `scenario-design-guide.md`, delete `scenarios-pending-review-*.md` per-agent files |
| C | Delete stale files in `sprint-prompts/`, delete `web/static/landing-v5.html` |
| D | `README.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`, delete `CHANGELOG-qs*.md` per-agent files |

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent A: Intelligence Tool API Routes

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Expose 4 intelligence tools as JSON API endpoints

### File Ownership
- web/routes_api.py (ONLY this file)

### Read First
- web/routes_api.py (existing API endpoints — follow the pattern)
- src/tools/predict_next_stations.py (function signature)
- src/tools/stuck_permit.py (function signature)
- src/tools/what_if_simulator.py (function signature)
- src/tools/cost_of_delay.py (function signature)
- web/auth.py (login_required decorator)

### Build

Task A-1: Add 4 JSON API endpoints to web/routes_api.py:

```python
@bp.route("/api/predict-next/<permit_number>", methods=["GET"])
@login_required
def api_predict_next(permit_number):
    from src.tools.predict_next_stations import predict_next_stations
    result = run_async(predict_next_stations(permit_number))
    return jsonify({"permit_number": permit_number, "prediction": result})

@bp.route("/api/stuck-permit/<permit_number>", methods=["GET"])
@login_required
def api_stuck_permit(permit_number):
    from src.tools.stuck_permit import diagnose_stuck_permit
    result = run_async(diagnose_stuck_permit(permit_number))
    return jsonify({"permit_number": permit_number, "diagnosis": result})

@bp.route("/api/what-if", methods=["POST"])
@login_required
def api_what_if():
    data = request.get_json()
    from src.tools.what_if_simulator import simulate_what_if
    result = run_async(simulate_what_if(
        data.get("base_description", ""),
        data.get("variations", [])
    ))
    return jsonify({"result": result})

@bp.route("/api/delay-cost", methods=["POST"])
@login_required
def api_delay_cost():
    data = request.get_json()
    from src.tools.cost_of_delay import calculate_delay_cost
    result = run_async(calculate_delay_cost(
        data.get("permit_type", "alterations"),
        float(data.get("monthly_carrying_cost", 5000)),
        neighborhood=data.get("neighborhood"),
        triggers=data.get("triggers")
    ))
    return jsonify({"result": result})
```

Use run_async from web.helpers for async-to-sync conversion. Follow existing error handling patterns (try/except → 500 with error message).

Task A-2: Add input validation — return 400 on missing required fields.

### Test
Write tests/test_api_intelligence.py:
- test_predict_next_requires_auth
- test_predict_next_returns_json (mock tool)
- test_stuck_permit_returns_json (mock tool)
- test_what_if_requires_post
- test_what_if_returns_json (mock tool)
- test_delay_cost_returns_json (mock tool)
- test_delay_cost_validates_input

### Output Files
- scenarios-pending-review-qs9-t4-a.md
- CHANGELOG-qs9-t4-a.md

### Commit
feat: expose 4 intelligence tools as JSON API endpoints (QS9-T4-A)
""")
```

---

### Agent B: Scenario Consolidation + Drain

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Consolidate and categorize 100+ pending scenarios

### File Ownership
- scenarios-pending-review.md
- scenario-design-guide.md (READ ONLY — do NOT add scenarios to it, only reference for dedup)
- Delete all scenarios-pending-review-qs*.md and scenarios-pending-review-sprint-*.md files

### Read First
- scenario-design-guide.md (73 approved scenarios — use for deduplication)
- scenarios-pending-review.md (current pending scenarios)
- ls for all per-agent scenario files: scenarios-pending-review-qs8-*.md, scenarios-pending-review-qs7-*.md, scenarios-pending-review-sprint-*.md

### Build

Task B-1: Consolidate all per-agent files into scenarios-pending-review.md:
- Read each per-agent file
- If a scenario title already exists in scenarios-pending-review.md OR scenario-design-guide.md, skip it (duplicate)
- Append unique scenarios to scenarios-pending-review.md
- Delete all per-agent scenario files

Task B-2: Categorize scenarios in scenarios-pending-review.md:
- Add a summary table at the top:
```markdown
## Pending Scenario Summary
| Category | Count |
|----------|-------|
| Property Intelligence | N |
| Search & Discovery | N |
| Onboarding & Auth | N |
| Performance & Caching | N |
| Admin & Ops | N |
| Data & Ingest | N |
```

Task B-3: Flag duplicates and near-duplicates:
- If two scenarios describe the same behavior with different wording, mark the duplicate with `**DUPLICATE OF:** [title]`
- Do NOT delete duplicates — just flag them for Tim's review

Task B-4: Count total unique scenarios after consolidation.

### Test
```bash
ls scenarios-pending-review-*.md 2>/dev/null | wc -l  # Should be 0
grep -c "SUGGESTED SCENARIO" scenarios-pending-review.md  # Total count
grep -c "DUPLICATE OF" scenarios-pending-review.md  # Flagged duplicates
```

### Commit
chore: consolidate 100+ scenarios from QS7+QS8 — [N] unique, [M] duplicates flagged (QS9-T4-B)
""")
```

---

### Agent C: Stale File Cleanup

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Delete stale/obsolete files from the repo

### File Ownership
- sprint-prompts/ (DELETE stale files only)
- web/static/landing-v5.html (DELETE)
- .claude/hooks/.stop_hook_fired (DELETE if exists)
- scenarios-reviewed-sprint69.md (DELETE)
- scripts/public_qa_checks.py (DELETE if obsolete — check first)
- scripts/sprint69_visual_qa.py (DELETE if obsolete — check first)

### Rules
- Do NOT delete any file that is referenced by active code (grep for imports/includes first)
- Do NOT delete sprint-prompts/qs8-* or sprint-prompts/qs9-* (current/recent)
- Do NOT delete sprint-prompts/sprint-79-*, sprint-80-*, sprint-81-* (QS8 source prompts)

### Build

Task C-1: Delete stale sprint prompts (pre-QS7):
```bash
# These are from sprints 68-69, superseded by QS7+:
sprint-prompts/qs3-a-permit-prep.md
sprint-prompts/qs3-b-ops-hardening.md
sprint-prompts/qs3-c-testing.md
sprint-prompts/qs3-d-analytics.md
sprint-prompts/sprint-68a-scenario-drain.md
sprint-prompts/sprint-68b-reliability.md
sprint-prompts/sprint-68c-cron-brief.md
sprint-prompts/sprint-68d-cleanup-docs.md
sprint-prompts/sprint-69-hotfix-search.md
sprint-prompts/sprint-69-session1-design-landing.md
sprint-prompts/sprint-69-session2-search-intel.md
sprint-prompts/sprint-69-session3-content-pages.md
sprint-prompts/sprint-69-session4-portfolio-pwa.md
```

Task C-2: Delete stale prototype files:
- web/static/landing-v5.html (superseded by web/static/mockups/landing.html)
- scenarios-reviewed-sprint69.md (one-off review artifact)
- .claude/hooks/.stop_hook_fired (transient state file)

Task C-3: Check scripts before deleting:
- scripts/public_qa_checks.py — grep for imports. If nothing imports it, delete.
- scripts/sprint69_visual_qa.py — same check. If nothing imports it, delete.

Task C-4: Report what was deleted in commit message.

### Test
```bash
ls sprint-prompts/qs3-* 2>/dev/null | wc -l  # Should be 0
ls sprint-prompts/sprint-68* 2>/dev/null | wc -l  # Should be 0
ls sprint-prompts/sprint-69-* 2>/dev/null | wc -l  # Should be 0
test -f web/static/landing-v5.html && echo "STILL EXISTS" || echo "DELETED"
```

### Commit
chore: delete [N] stale files — old sprint prompts, prototype artifacts (QS9-T4-C)
""")
```

---

### Agent D: Documentation Update

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Update project documentation with QS7/QS8/Sprint 78 results

### File Ownership
- README.md
- docs/ARCHITECTURE.md
- CHANGELOG.md
- Delete all CHANGELOG-qs*.md per-agent files after consolidating

### Read First
- README.md (find key numbers section, tool list, architecture overview)
- docs/ARCHITECTURE.md (find tool inventory, data flow sections)
- CHANGELOG.md (understand format, find latest entries)
- ls for CHANGELOG-qs*.md per-agent files

### Build

Task D-1: Consolidate per-agent changelogs:
- Read each CHANGELOG-qs8-*.md and CHANGELOG-qs9-*.md file
- Append entries to CHANGELOG.md under sprint headers
- Delete per-agent files after consolidation

Task D-2: Update README.md key numbers:
- Tools: 30 → 34 (4 intelligence tools added)
- Tests: update to ~3,782+
- Tables (prod): 65
- Add intelligence tools to the tool inventory list
- Update any stale sprint references

Task D-3: Update docs/ARCHITECTURE.md:
- Add "Intelligence Tools" section listing the 4 new tools with one-line descriptions
- Update tool count in overview
- Add page_cache to the data flow section if not already documented
- Add SODA circuit breaker to the reliability section

Task D-4: Add QS7, Sprint 78, QS8 entries to CHANGELOG.md if not already present:
- QS7: obsidian.css, template migration, page_cache, prod gate v2
- Sprint 78: DuckDB test isolation, Postgres opt-in
- QS8: N+1 fix, 4 intelligence tools, onboarding, search NLP, circuit breaker

### Test
```bash
grep "34 tools" README.md  # Updated count
grep "intelligence" docs/ARCHITECTURE.md -i  # New section exists
ls CHANGELOG-qs*.md 2>/dev/null | wc -l  # Should be 0
```

### Output Files
- scenarios-pending-review-qs9-t4-d.md
- CHANGELOG-qs9-t4-d.md (yes, meta — a changelog entry about updating the changelog)

### Commit
docs: update README, ARCHITECTURE, CHANGELOG with QS7-QS8 results — 34 tools, 3782+ tests (QS9-T4-D)
""")
```

---

## Post-Agent: Merge + Push

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
# Merge A first (API routes), then D (docs/changelog), then B (scenarios — needs clean CHANGELOG), then C (deletions last)
git merge <agent-a-branch> --no-edit
git merge <agent-d-branch> --no-edit
git merge <agent-b-branch> --no-edit
git merge <agent-c-branch> --no-edit
git push origin main
```

## Report

```
T4 (Cleanup + Docs + API) COMPLETE
  A: API routes:            [PASS/FAIL] (4 new /api/ endpoints)
  B: Scenario consolidation: [PASS/FAIL] ([N] unique, [M] duplicates flagged)
  C: Stale file cleanup:    [PASS/FAIL] ([N] files deleted)
  D: Documentation update:  [PASS/FAIL] (README + ARCHITECTURE + CHANGELOG)
  Pushed: [commit hash]
```
