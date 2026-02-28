# QS8 Terminal 2: Intelligence Tools (Sprint 80)

You are the orchestrator for QS8-T2. Spawn 4 parallel build agents, collect results, merge, push to main. Do NOT run the full test suite — T0 handles that in the merge ceremony.

## Pre-Flight (30 seconds — T0 already verified tests + prod health)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T2 start: $(git rev-parse --short HEAD)"
```

## Context

This sprint creates 4 NEW intelligence tools. **Zero modifications to existing files.** Every agent creates NEW files only — zero merge conflicts possible. This is the safest terminal.

Tools are NOT registered in src/server.py or exposed via web routes in this sprint. They're importable and tested standalone. Registration is a follow-up.

**Known test exclusions:** `--ignore=tests/test_tools.py --ignore=tests/e2e`

## Agent Preamble (include verbatim in every agent prompt)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. The orchestrator handles all merges.

RULES:
- ONLY create NEW files. Do NOT modify ANY existing file.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-pending-review-qs8-t2-{agent}.md
  * CHANGELOG-qs8-t2-{agent}.md
- TEST COMMAND: source .venv/bin/activate && pytest tests/{your_test_file}.py -v --tb=short 2>&1 | tail -20

Known DuckDB/Postgres Gotchas:
- DuckDB uses ? placeholders, Postgres uses %s. Import _PH from src.db or define locally.
- DuckDB doesn't support all Postgres date functions. Use Python-side date math.
- conn.execute() works on DuckDB. Postgres needs cursor: with conn.cursor() as cur: cur.execute(...)
- All tools must handle both backends via BACKEND and _PH from src.db.

Pattern to follow: Read src/tools/estimate_timeline.py for async tool structure,
src/station_velocity_v2.py for velocity data, src/severity.py for scoring patterns.
All new tools should be async functions returning formatted markdown strings.
```

## File Ownership Matrix

| Agent | Files Created (ALL NEW) |
|-------|------------------------|
| A | `src/tools/station_predictor.py`, `tests/test_station_predictor.py` |
| B | `src/tools/stuck_permit.py`, `tests/test_stuck_permit.py` |
| C | `src/tools/what_if_simulator.py`, `tests/test_what_if_simulator.py` |
| D | `src/tools/cost_of_delay.py`, `tests/test_cost_of_delay.py` |

**Cross-agent overlap: ZERO. All new files.**

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent A: "What's Next" Station Predictor

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. ONLY create NEW files — do NOT modify existing files.

## YOUR TASK: Build "What's Next" station predictor tool

### Files to Create (NEW)
- src/tools/station_predictor.py
- tests/test_station_predictor.py

### Read First
- src/tools/estimate_timeline.py (especially estimate_sequence_timeline — station routing model)
- src/station_velocity_v2.py (velocity lookup — p50/p75/p90 per station)
- src/db.py (get_connection, BACKEND, _PH)
- src/server.py (tool registration pattern — DO NOT MODIFY, just understand)

### Build

Create async function predict_next_stations(permit_number: str) -> str:

1. Query addenda for the permit's station history: stations visited, current station, dates
2. Query addenda for ALL permits of same type + neighborhood → build transition probability matrix
3. Based on current station + historical transitions, predict:
   - Most likely next 3 stations with probabilities
   - Estimated time at each (from station_velocity_v2 p50)
   - Total estimated remaining time
4. Format as markdown:
   - Current station status (dwell time, is it stalled?)
   - Predicted next steps (station, probability, duration)
   - "All clear" estimate

Edge cases:
- Permit not found → helpful error message
- No addenda data → "No routing data available"
- Already complete → "This permit has completed all review stations"

### Test
Mock DB responses. Test complete/in-progress/no-data scenarios.

### Output Files
- scenarios-pending-review-qs8-t2-a.md
- CHANGELOG-qs8-t2-a.md

### Commit
feat: What's Next station predictor tool (QS8-T2-A)
""")
```

---

### Agent B: Stuck Permit Playbook

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. ONLY create NEW files — do NOT modify existing files.

## YOUR TASK: Build Stuck Permit Intervention Playbook tool

### Files to Create (NEW)
- src/tools/stuck_permit.py
- tests/test_stuck_permit.py

### Read First
- src/severity.py (severity scoring dimensions, SeverityResult)
- src/tools/estimate_timeline.py (station velocity, dwell times)
- src/tools/permit_lookup.py (permit data access)

### Build

Create async function diagnose_stuck_permit(permit_number: str) -> str:

1. Fetch permit data + current routing from addenda
2. For each current station:
   - Calculate dwell time (days since arrival)
   - Compare to p50/p75/p90 from station_velocity_v2
   - Flag "stalled" if > p75, "critically stalled" if > p90
3. Check stuck patterns:
   - No inspector assigned
   - Comments issued, no resubmission
   - Held at inter-agency station (SFFD, DPH, Planning)
   - Multiple revision cycles
4. Generate intervention recommendations:
   - Stalled at BLDG → "Contact plan check counter"
   - Stalled at inter-agency → "Contact {agency} directly"
   - Comments issued → "Revise plans per comments, resubmit via EPR"
   - No activity 30+ days → "File inquiry with DBI customer service"
5. Format as markdown playbook:
   - Severity score + status summary
   - Per-station diagnosis (dwell vs baseline)
   - Ranked intervention steps
   - Contact info for relevant stations

### Test
Mock DB. Test stalled, comments-issued, inter-agency-hold, healthy scenarios.

### Output Files
- scenarios-pending-review-qs8-t2-b.md
- CHANGELOG-qs8-t2-b.md

### Commit
feat: Stuck Permit Intervention Playbook tool (QS8-T2-B)
""")
```

---

### Agent C: What-If Permit Simulator

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. ONLY create NEW files — do NOT modify existing files.

## YOUR TASK: Build What-If Permit Simulator tool

### Files to Create (NEW)
- src/tools/what_if_simulator.py
- tests/test_what_if_simulator.py

### Read First
- src/tools/predict_permits.py (decision tree)
- src/tools/estimate_timeline.py (timeline estimation)
- src/tools/estimate_fees.py (fee calculation)
- src/tools/revision_risk.py (revision probability)

### Build

Create async function simulate_what_if(base_description: str, variations: list[dict]) -> str:

Takes a base project and variations, shows how each changes timeline/fees/risk.

Parameters:
- base_description: "Kitchen remodel in the Mission, $80K"
- variations: [{"label": "Add bathroom", "description": "Kitchen + bathroom, $120K"}, ...]

For each scenario (base + variations):
1. predict_permits() → permit types, review path
2. estimate_timeline() → p50/p75 timelines
3. estimate_fees() → fee breakdown
4. revision_risk() → revision probability

Format as comparison table:
| Scenario | Permits | Review Path | Timeline (p50) | Fees | Revision Risk |

IMPORTANT: Underlying tools are ASYNC. Use await.
Handle missing data: if a tool returns error string, show "N/A".

### Test
Mock underlying tool functions. Test with 2-3 variations.

### Output Files
- scenarios-pending-review-qs8-t2-c.md
- CHANGELOG-qs8-t2-c.md

### Commit
feat: What-If Permit Simulator tool (QS8-T2-C)
""")
```

---

### Agent D: Cost of Delay Calculator

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. ONLY create NEW files — do NOT modify existing files.

## YOUR TASK: Build Cost of Delay Calculator tool

### Files to Create (NEW)
- src/tools/cost_of_delay.py
- tests/test_cost_of_delay.py

### Read First
- src/tools/estimate_timeline.py (timeline estimation, p50/p75/p90)
- src/tools/estimate_fees.py (fee patterns)
- src/tools/revision_risk.py (revision probability)

### Build

Create async function calculate_delay_cost(permit_type: str, monthly_carrying_cost: float, neighborhood: str = None, triggers: list[str] = None) -> str:

1. Get timeline estimate (p50, p75, p90) from estimate_timeline
2. For each percentile:
   - Carrying cost = monthly_carrying_cost × timeline_months
   - Expected revision cost = revision_probability × revision_delay × monthly_cost
3. Format as markdown:
   | Scenario | Timeline | Carrying Cost | Revision Risk Cost | Total |
   | Best (p25) | 30d | $15K | $2.1K | $17.1K |
   | Likely (p50) | 45d | $22.5K | $3.2K | $25.7K |
   | Worst (p90) | 90d | $45K | $6.3K | $51.3K |
   - Break-even: "Expediting by N days saves $X/day"
   - Mitigation: OTC if eligible, pre-consultation, etc.

Also create: daily_delay_cost(monthly_carrying_cost: float) -> str
Returns one-liner: "Every day of permit delay costs you ${daily}/day"

Handle missing data: if timeline tool errors, show manual estimate guidance.

### Test
Mock timeline/revision tools. Test various carrying costs and permit types.

### Output Files
- scenarios-pending-review-qs8-t2-d.md
- CHANGELOG-qs8-t2-d.md

### Commit
feat: Cost of Delay Calculator tool (QS8-T2-D)
""")
```

---

## Post-Agent: Merge + Push

After all 4 agents complete:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Merge all (order doesn't matter — all new files)
git merge <agent-a-branch> --no-edit
git merge <agent-b-branch> --no-edit
git merge <agent-c-branch> --no-edit
git merge <agent-d-branch> --no-edit

# Concatenate per-agent output files
cat scenarios-pending-review-qs8-t2-*.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-qs8-t2-*.md >> CHANGELOG.md 2>/dev/null

# Push to main. Do NOT run the full test suite — T0 handles that.
git push origin main
```

## Report Template

```
T2 (Intelligence) COMPLETE
  A: Station predictor:    [PASS/FAIL] [N tests]
  B: Stuck permit playbook: [PASS/FAIL] [N tests]
  C: What-if simulator:    [PASS/FAIL] [N tests]
  D: Cost of delay:        [PASS/FAIL] [N tests]
  Scenarios: [N] across 4 files
  Pushed: [commit hash]
```
