<!-- LAUNCH: Open a fresh CC terminal from the MAIN repo root, then tell it:
     "Read sprint-prompts/sprint-65-data.md and execute it"
     The agent will read this file and follow the instructions below. -->

# Sprint 65: Data Expansion

You are a build agent for Sprint 65 of the sfpermits.ai project.

**FIRST:** Use EnterWorktree with name `sprint-65` to create an isolated worktree. All work happens there.

## Context
- Repo root: `/Users/timbrenneman/AIprojects/sf-permits-mcp`
- Phase 0 Blueprint refactor is COMPLETE — routes live in `web/routes_*.py`, app.py is slim
- 3,093 tests passing on main at commit `5ba4a6d`
- Always activate venv: `source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate`
- Run tests with: `pytest tests/ --ignore=tests/test_tools.py -q`

## Your 4 Tasks (do them sequentially)

### Task 65-A: Planning Contacts → Entity Network
**Files:** `src/ingest.py`, `src/entities.py`

1. Read `src/ingest.py` to understand current ingestion pipeline
2. Read `src/entities.py` to understand the 5-step entity resolution cascade
3. Add a new function `extract_planning_contacts(conn)` in `src/ingest.py` that:
   - Queries `planning_records` table for `applicant`, `applicant_org`, `assigned_planner` columns
   - Transforms them into the standard contacts format (name, role, permit_number, block, lot)
   - Inserts into a `planning_contacts` staging table
4. In `src/entities.py`, add `planning` as a recognized source in the entity resolution cascade at step 3 (AFTER building + electrical/plumbing). Planning contacts have LOWER priority — if a name collides with an existing building entity, the building entity ID is preserved. Planning data attaches as additional source. Additive-only: no existing entity IDs are changed.
5. Write tests for the new extraction and entity resolution with planning source

### Task 65-B: DBI Metrics → Timeline Estimates
**Files:** `src/tools/estimate_timeline.py` (NEW helper function ONLY)

1. Read `src/tools/estimate_timeline.py` to understand the current station-sum model
2. Check what DBI metrics tables exist: `permit_issuance_metrics`, `permit_review_metrics`, `planning_review_metrics`
3. Add a new helper function `_query_dbi_metrics(permit_type, neighborhood=None)` that:
   - Queries the DBI metrics tables for relevant averages
   - Returns a markdown section `## DBI Processing Metrics` with weekly avg and 30-day rolling numbers
   - This section goes BELOW the existing station velocity output
4. Wire `_query_dbi_metrics` into the main `estimate_timeline` function — append its output
5. Write tests for the new helper (mock the DB queries)

**Interface contract with Sprint 66:** You add `_query_dbi_metrics` (new function). Sprint 66-A modifies `_query_station_velocity_v2` (existing function). Non-overlapping — no conflicts.

### Task 65-C: Knowledge Base Expansion
**Files:** `data/knowledge/tier1/` (new JSON files), `data/knowledge/GAPS.md`, `data/knowledge/SOURCES.md`

1. Read `data/knowledge/GAPS.md` to understand known gaps
2. Read `data/knowledge/SOURCES.md` for the inventory format
3. Create `data/knowledge/tier1/commercial-completeness-checklist.json` — structured checklist for commercial tenant improvement permit submissions. Include: required forms, plan set requirements, agency routing triggers, common rejection reasons. Model after existing residential checklists in tier1.
4. Create `data/knowledge/tier1/school-impact-fees.json` (GAP-11) — SF school impact fee schedule, thresholds, exemptions, calculation method
5. Create `data/knowledge/tier1/special-inspection-requirements.json` (GAP-13) — when special inspections are required, types (structural, welding, concrete, etc.), who can perform them
6. Update GAPS.md to mark these gaps as resolved
7. Update SOURCES.md with new file entries
8. Write tests that verify the new JSON files are valid and have expected structure

### Task 65-D: Entity Graph Enrichment
**Files:** `src/graph.py`, `src/entities.py` (quality scoring only), `src/validate.py`

1. Read `src/graph.py` to understand the co-occurrence graph model
2. Add reviewer-entity interaction edges: when a reviewer (plan_checked_by from addenda) reviews a permit, and an architect/consultant is on that same permit, create an edge between reviewer and architect/consultant
3. In `src/entities.py`, add an entity quality score function `compute_entity_quality(entity_id)` that returns a confidence metric (0-100) based on: number of sources, name consistency across sources, activity recency, number of relationships
4. In `src/validate.py`, add anomaly checks that flag entities with suspiciously high reviewer-specific approval rates
5. Write tests for new edge types and quality scoring

**Note:** Both 65-A and 65-D touch `src/entities.py` but in different sections (65-A adds planning source, 65-D adds quality scoring). Keep changes in separate functions to avoid conflicts.

## Rules
- Work in worktree `sprint-65` (use EnterWorktree)
- Run `pytest tests/ --ignore=tests/test_tools.py -q` after each task
- Do NOT modify files owned by other sprints
- Commit after each task with descriptive message
- When all 4 tasks are done, report completion with test count

## File Ownership (Sprint 65 ONLY)
- `src/ingest.py` (65-A: planning extraction)
- `src/entities.py` (65-A: planning source + 65-D: quality scoring)
- `src/graph.py` (65-D: new edge types)
- `src/validate.py` (65-D: anomaly checks)
- `src/tools/estimate_timeline.py` (65-B: new `_query_dbi_metrics` function ONLY)
- `data/knowledge/tier1/` (65-C: new JSON files)
- `data/knowledge/GAPS.md`, `data/knowledge/SOURCES.md` (65-C)

Do NOT touch: `web/app.py`, `web/routes_*.py`, `web/data_quality.py`, `web/brief.py`, `src/station_velocity_v2.py`, `web/static/`, `web/templates/`, `scripts/release.py`
