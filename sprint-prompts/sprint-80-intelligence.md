<!-- LAUNCH: Paste into CC terminal 3:
     "Read sprint-prompts/sprint-80-intelligence.md and execute it" -->

# Sprint 80 — Intelligence Tools

You are the orchestrator for Sprint 80. Spawn 4 parallel build agents, collect results, merge, test, push.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git tag pre-sprint-80
```

## IMPORTANT CONTEXT

This sprint creates 4 NEW intelligence tools. Zero modifications to existing files. Every agent creates NEW files only — this means zero merge conflicts.

Existing tools to build on (READ these for patterns):
- src/tools/estimate_timeline.py — has `estimate_sequence_timeline(permit_number)` (station routing model)
- src/station_velocity_v2.py — station velocity data (p50/p75/p90 per station)
- src/severity.py — severity scoring v2 (5 dimensions, data-driven thresholds)
- src/tools/permit_lookup.py — permit data access patterns

All new tools should:
1. Be async functions (matching existing tool signatures)
2. Use `get_connection()` from `src.db`
3. Return formatted markdown strings (matching existing tool output patterns)
4. Handle both DuckDB and Postgres via `BACKEND` and `_PH` variables
5. Include comprehensive docstrings matching existing tool patterns

**Known DuckDB/Postgres Gotchas:**
- DuckDB uses `?` placeholders, Postgres uses `%s`. Import `_PH` from src.db or define locally.
- DuckDB doesn't support all Postgres date functions. Use Python-side date math when possible.
- Tests run on DuckDB locally.

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
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- ONLY create NEW files. Do NOT modify ANY existing file.
- APPEND FILES (dual-write):
  * scenarios-pending-review-sprint-80-N.md (per-agent)
  * scenarios-pending-review.md (shared, append only)
  * CHANGELOG-sprint-80-N.md (per-agent)
- Test: pytest tests/test_station_predictor.py -v (or your test file name)
```

---

### Agent 80-1: "What's Next" Station Predictor

**File Ownership (ALL NEW):**
- src/tools/station_predictor.py
- tests/test_station_predictor.py

**PHASE 1: READ**
- src/tools/estimate_timeline.py (especially estimate_sequence_timeline at line 722+)
- src/station_velocity_v2.py (velocity lookup pattern)
- src/db.py (get_connection, BACKEND, _PH)
- src/server.py (tool registration pattern — DO NOT MODIFY, just understand)

**PHASE 2: BUILD**

Create `predict_next_stations(permit_number: str) -> str`:

1. Query addenda for the permit's station history: stations visited, current station, arrival/departure dates
2. Query addenda for ALL permits of the same type + neighborhood to build a transition probability matrix:
   - For each station S, what stations typically follow S?
   - What's the probability of each next station?
3. Based on the permit's current station + historical transitions, predict:
   - Most likely next 3 stations with probabilities
   - Estimated time at each station (from station_velocity_v2 p50 values)
   - Total estimated remaining time
4. Format as markdown with:
   - Current station status (how long in current station, is it stalled?)
   - Predicted next steps (station name, probability, estimated duration)
   - "All clear" estimate (when all reviews likely complete)

Handle edge cases:
- Permit not found → helpful error message
- No addenda data → "No routing data available for this permit"
- Permit already complete → "This permit has completed all review stations"

**Tests:** Mock DB responses. Test with complete/in-progress/no-data scenarios.
Commit: "feat: What's Next station predictor tool (Sprint 80-1)"

---

### Agent 80-2: Stuck Permit Playbook

**File Ownership (ALL NEW):**
- src/tools/stuck_permit.py
- tests/test_stuck_permit.py

**PHASE 1: READ**
- src/severity.py (severity scoring dimensions, SeverityResult)
- src/tools/estimate_timeline.py (station velocity, dwell times)
- src/tools/permit_lookup.py (permit data access patterns)

**PHASE 2: BUILD**

Create `diagnose_stuck_permit(permit_number: str) -> str`:

1. Fetch permit data + current routing status from addenda
2. For each station the permit is currently at:
   - Calculate dwell time (days since arrival)
   - Compare to p50/p75/p90 baselines from station_velocity_v2
   - Flag as "stalled" if dwell > p75, "critically stalled" if > p90
3. Check for common stuck patterns:
   - No inspector assigned (inspections table has no recent entries)
   - Comments issued but no resubmission (addenda shows "Issued Comments" with no follow-up)
   - Held at inter-agency station (SFFD, DPH, Planning) — these have longer baselines
   - Multiple revision cycles (count addenda entries for same station)
4. Generate intervention recommendations:
   - If stalled at BLDG: "Contact plan check counter, reference application #{permit_number}"
   - If stalled at inter-agency: "Contact {agency} directly, typical wait is {p50} days"
   - If comments issued: "Revise plans per comments and resubmit via EPR"
   - If no activity in 30+ days: "File inquiry with DBI customer service"
5. Format as markdown playbook with:
   - Severity score and status summary
   - Per-station diagnosis (current dwell vs baseline)
   - Ranked intervention steps (most impactful first)
   - Contact information for relevant stations

**Tests:** Mock DB. Test stalled, comments-issued, inter-agency-hold, and healthy permit scenarios.
Commit: "feat: Stuck Permit Intervention Playbook tool (Sprint 80-2)"

---

### Agent 80-3: What-If Permit Simulator

**File Ownership (ALL NEW):**
- src/tools/what_if_simulator.py
- tests/test_what_if_simulator.py

**PHASE 1: READ**
- src/tools/predict_permits.py (predict_permits function — decision tree)
- src/tools/estimate_timeline.py (estimate_timeline function)
- src/tools/estimate_fees.py (estimate_fees function)
- src/tools/revision_risk.py (revision_risk function)

**PHASE 2: BUILD**

Create `simulate_what_if(base_description: str, variations: list[dict]) -> str`:

The simulator takes a base project description and a list of "what if" variations,
then shows how each variation changes the predicted timeline, fees, and risk.

Parameters:
- base_description: "Kitchen remodel in the Mission, $80K"
- variations: [
    {"label": "Add bathroom", "description": "Kitchen + bathroom remodel in the Mission, $120K"},
    {"label": "Drop cost below $50K", "description": "Minor kitchen update in the Mission, $45K"},
    {"label": "Move to SoMa", "description": "Kitchen remodel in SoMa, $80K"},
  ]

For each scenario (base + variations):
1. Run predict_permits() → get permit types, review path, agency routing
2. Run estimate_timeline() → get p50/p75 timeline estimates
3. Run estimate_fees() → get fee breakdown
4. Run revision_risk() → get revision probability

Format as comparison table:
| Scenario | Permits Needed | Review Path | Timeline (p50) | Fees | Revision Risk |
|----------|---------------|-------------|----------------|------|--------------|
| Base | Form 3/8 | In-house | 45 days | $2,100 | 23% |
| + Bathroom | Form 3/8 | In-house | 52 days | $3,400 | 31% |
| < $50K | Form 3/8 | **OTC** | 1 day | $890 | 8% |
| SoMa | Form 3/8 | In-house | 38 days | $2,100 | 19% |

Highlight the biggest delta for each variation (what changed most and why).

IMPORTANT: The underlying tools (predict_permits, estimate_timeline, etc.) are ASYNC.
Use `asyncio.run()` or a helper to call them from a sync context if needed.
Handle missing data gracefully — if a tool returns an error string instead of structured data, show "N/A" in the table.

**Tests:** Mock the underlying tool functions. Test with 2-3 variation scenarios.
Commit: "feat: What-If Permit Simulator tool (Sprint 80-3)"

---

### Agent 80-4: Cost of Delay Calculator

**File Ownership (ALL NEW):**
- src/tools/cost_of_delay.py
- tests/test_cost_of_delay.py

**PHASE 1: READ**
- src/tools/estimate_timeline.py (timeline estimation, p50/p75/p90 values)
- src/tools/estimate_fees.py (fee patterns)

**PHASE 2: BUILD**

Create `calculate_delay_cost(permit_type: str, monthly_carrying_cost: float, neighborhood: str = None, triggers: list[str] = None) -> str`:

Computes the financial impact of permit processing time:

1. Get timeline estimate (p50, p75, p90) from estimate_timeline
2. For each percentile scenario:
   - Total carrying cost = monthly_carrying_cost × (timeline_months)
   - Opportunity cost = lost rental income or delayed project value
3. Compute revision impact:
   - Get revision probability from revision_risk
   - If revised: add p50 revision delay × monthly_carrying_cost
   - Expected revision cost = probability × revision_delay_cost
4. Format as markdown:
   - **Cost Summary Table:**
     | Scenario | Timeline | Carrying Cost | Revision Risk Cost | Total |
     |----------|----------|---------------|-------------------|-------|
     | Best case (p25) | 30 days | $15,000 | $2,100 | $17,100 |
     | Likely (p50) | 45 days | $22,500 | $3,150 | $25,650 |
     | Worst case (p90) | 90 days | $45,000 | $6,300 | $51,300 |
   - **Break-even analysis:** "If you can expedite by N days, you save $X/day"
   - **Mitigation recommendations:** OTC path if eligible, pre-consultation, etc.

Handle missing data: if estimate_timeline returns an error, show manual estimate guidance.

Also create a simpler helper: `daily_delay_cost(monthly_carrying_cost: float) -> str`
Returns a one-liner: "Every day of permit delay costs you ${daily_cost}/day"

**Tests:** Mock timeline/revision tools. Test with various carrying costs and permit types.
Commit: "feat: Cost of Delay Calculator tool (Sprint 80-4)"

---

## Post-Agent Merge (Orchestrator)

1. Collect results from all 4 agents
2. Merge all branches (ZERO conflicts expected — all NEW files)
3. Run tests: `pytest tests/test_station_predictor.py tests/test_stuck_permit.py tests/test_what_if_simulator.py tests/test_cost_of_delay.py -v`
4. Run full suite: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q`
5. Push to main
6. Report: tools created, test counts, any BLOCKED items

NOTE: These tools are NOT yet registered in src/server.py or exposed via web routes.
Registration happens in a follow-up sprint. The tools are importable and tested standalone.
