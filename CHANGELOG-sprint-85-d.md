# CHANGELOG — Sprint 85-D: Docs Consolidation

## Sprint 85-D — Documentation Update (2026-02-27)

### README.md
- Updated tool count: 21 → 34
- Added Phase 8 tools to tool table: predict_next_stations, diagnose_stuck_permit, simulate_what_if, calculate_delay_cost
- Updated Key Numbers: 4,357+ tests, 34 tools, 59 PostgreSQL tables, 47 tier1 JSON files
- Added Phase 6-8 to architecture diagram
- Added Phase 6-8 to Project Phases checklist
- Updated Current State section with QS8/Sprint 79/Sprint 81 results

### docs/ARCHITECTURE.md
- Updated system overview diagram: 21 → 34 tools, added Phase 6/7/8 branches
- Added Phase 6 description: permit_severity, property_health
- Added Phase 7 description: run_query, read_source, search_source, schema_info, list_tests, similar_projects
- Added Phase 8 Intelligence Tools section: detailed descriptions of all 4 new tools with algorithms
  - predict_next_stations: Markov transition model, neighborhood-filtered, stall detection
  - diagnose_stuck_permit: dwell vs p50/p75/p90 baselines, 14 inter-agency station codes, ranked playbook
  - simulate_what_if: parallel asyncio.gather() orchestration of 4 sub-tools, delta section
  - calculate_delay_cost: carrying cost + revision risk, 13 permit types, live timeline integration
- Updated Key Modules tool file inventory: 21 → 34 files
- Added CircuitBreaker note to Phase 1 description
- Added severity.py, station_velocity_v2.py, signals/ to module list

### CHANGELOG.md
- Added QS8 (Sprint 79 + Sprint 81) consolidated entry at top
- Added QS5 (Sprint 79 data quality + incremental ingest) consolidated entry
- Removed raw per-agent dump appended at lines 3058+ (QS8-T1 through T3 raw files)

### Per-agent CHANGELOG files deleted (36 files)
- CHANGELOG-qs4-a.md through qs4-d.md (content already in CHANGELOG.md)
- CHANGELOG-qs5-a.md through qs5-d.md (consolidated into CHANGELOG.md)
- CHANGELOG-qs8-t1-a.md through qs8-t3-d.md (consolidated into CHANGELOG.md)
- CHANGELOG-sprint-74-1.md through sprint-77-4.md (content already in CHANGELOG.md)
