# CHANGELOG — QS5-A: Materialized Parcels Table

## 2026-02-26 — QS5-A

### Added
- **parcel_summary table**: Materialized one-row-per-parcel cache with counts from permits, complaints, violations, boiler_permits, inspections + tax data from tax_rolls + health tier from property_health
- **POST /cron/refresh-parcel-summary**: CRON_SECRET-protected endpoint to populate/refresh parcel_summary via INSERT...SELECT with UPSERT (Postgres) or DELETE+INSERT (DuckDB)
- **report.py cache integration**: `_get_parcel_summary()` queries cache before SODA API; `_format_property_profile_from_cache()` builds property profile from cached data; skips `_fetch_property()` SODA call when cache hit
- **DDL in 3 locations**: `scripts/release.py` (Postgres prod), `web/app.py` `_run_startup_migrations()` (Postgres workers), `src/db.py` `init_user_schema()` (DuckDB dev/test)
- **14 tests** in `tests/test_qs5_a_parcels.py`: DDL creation, column schema, PK enforcement, EXPECTED_TABLES membership, cron auth (2 tests), cron count, UPPER address, permit counts, cache hit/miss, profile formatting (2 tests), release.py DDL presence
- **2 scenarios** proposed: cached property report load, nightly parcel refresh

### Technical Notes
- DuckDB refresh handles missing optional tables gracefully (complaints, violations, boiler_permits, inspections, tax_rolls, property_health may not exist in test env)
- DuckDB permits table has no `supervisor_district` column — handled dynamically via information_schema introspection
- Postgres uses `LATERAL` join for tax_rolls dedup; DuckDB uses `ROW_NUMBER()` window function
- canonical_address priority: (1) most recent permit with non-null address, (2) tax_rolls property_location, (3) NULL
