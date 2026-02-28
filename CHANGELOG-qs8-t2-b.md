# CHANGELOG — QS8-T2-B: Stuck Permit Intervention Playbook

## Added

### src/tools/stuck_permit.py (NEW)

New async tool `diagnose_stuck_permit(permit_number: str) -> str` — diagnoses why a
permit is stalled in the plan check routing queue and generates a ranked markdown
intervention playbook.

**Core logic:**
- Fetches permit data and active addenda routing stations from the database
- For each station: calculates dwell time (days since arrival) and compares to
  p50/p75/p90 baselines from the `station_velocity_v2` table
- Flags "stalled" if dwell > p75, "critically stalled" if dwell > p90
- Falls back to heuristics (>45d = stalled, >90d = critically) when no baseline exists
- Detects stuck patterns: comments issued (review_results contains "comment"),
  inter-agency holds (SFFD/HEALTH/Planning/DPW/HIS), multiple revision cycles
  (addenda_number >= 2), 30+ day inactivity

**Inter-agency classification:**
- 14 inter-agency station codes mapped to agency names (SFFD, HEALTH-*, CP-ZOC,
  DPW-BSM, DPW-BUF, SFPUC, SFPUC-PRG, HIS, ABE)
- 6 BLDG-family stations for DBI plan check routing
- Agency contact info (phone, URL, notes) for DBI, SFFD, HEALTH, Planning, DPW, HIS

**Playbook output (markdown):**
- Header: permit number, address, description, status, severity score, routing status
- Filed/issued dates with days-ago context
- Station Diagnosis section: one entry per active station sorted by severity,
  showing dwell vs p50/p75/p90 baselines with CRITICAL/STALLED/NORMAL labels
- Intervention Steps: ranked by urgency (IMMEDIATE > HIGH > MEDIUM > LOW) with
  agency contact details for each step
- Revision History section if revision_count >= 1 (3+ cycles: expediter advisory)
- Footer with generation date and EPR portal link

**Graceful degradation:**
- Permit not found → formatted "not found" message with DBI portal link
- No addenda data → advisory that permit may not yet be in plan check queue
- DB connection error → formatted error message with permit number preserved

**Backends:** DuckDB and Postgres compatible via BACKEND/placeholder pattern
from `src.db`.

### tests/test_stuck_permit.py (NEW)

34 tests — all passing. No live DB or network access (all DB calls mocked).

**Unit tests (no async):**
- `_parse_date` — string, date object, None inputs
- `_calc_dwell_days` — normal and None arrive inputs
- `_overall_status` — worst-case aggregation across stations
- `_severity_label` — CRITICAL/STALLED/NORMAL mapping
- `_diagnose_station` — 8 scenarios: critically stalled BLDG, stalled BLDG,
  stalled SFFD inter-agency, comments issued, healthy, no velocity heuristic,
  Planning inter-agency (CP-ZOC), revision cycle detection
- `_get_agency_key` — SFFD, HEALTH, Planning, DPW, DBI (default) mappings
- `_format_address` — full address, missing parts
- `INTER_AGENCY_STATIONS` — 6 expected stations present
- `BLDG_STATIONS` — none overlap with INTER_AGENCY_STATIONS

**Integration tests (async, full playbook):**
- Permit not found → "Not Found" in result
- Critically stalled BLDG → CRITICAL label, DBI recommendation
- Inter-agency hold (SFFD) → agency name and "Contact" in result
- Comments issued → EPR resubmission recommendation
- Multiple revision cycles (3) → Revision History section
- Healthy permit → no CRITICAL label
- No addenda data → graceful empty station message
- DB error → formatted error message (not raw exception)
