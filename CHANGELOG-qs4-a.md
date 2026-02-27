## QS4-A: Metrics UI + Data Surfacing (2026-02-26)

### Added
- **`/admin/metrics` dashboard** — new admin route with 3 sections:
  - Permit Issuance Trends (grouped by year/month/type/OTC)
  - Station SLA Compliance (color-coded: green ≥80%, amber 60-79%, red <60%)
  - Planning Velocity (grouped by stage/outcome)
- **Pipeline integration** — 3 metrics ingest functions now called from `run_ingestion()` main pipeline (permit_issuance, permit_review, planning_review)
- **25 new tests** in `tests/test_qs4_a_metrics.py` covering auth, template rendering, data queries, velocity cache, cron endpoints, and pipeline integration
- **3 scenarios** proposed for review

### Noted (pre-existing)
- Task A-3 (Station Velocity Caching) already implemented — `station_velocity_v2` table, `refresh_velocity_v2()`, `POST /cron/velocity-refresh` all exist from Sprint 64. Tests added confirming the cache works.
- Task A-4 (Street-Use Contacts) descoped to QS5 per sprint spec.
