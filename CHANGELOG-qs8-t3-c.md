# CHANGELOG — QS8-T3-C: Electrical/Plumbing/Boiler Permit Ingest Tests

## [QS8-T3-C] — 2026-02-27

### Added

**tests/test_sprint_81_3.py** — 51 new tests covering electrical, plumbing, and boiler permit ingest functions

- `_normalize_boiler_permit()` — full field mapping, NULL handling, missing permit_number fallback, zip_code field name verification (uses `zip_code` not `zipcode`)
- `_normalize_electrical_permit()` — permit_type constant integrity, tuple length verification (26 columns)
- `_normalize_plumbing_permit()` — permit_type constant integrity, tuple length verification (26 columns)
- `ingest_electrical_permits()` — mock SODA client round-trip, INSERT verification, ingest_log entry, empty dataset, idempotent re-run
- `ingest_plumbing_permits()` — mock SODA client round-trip, INSERT verification, ingest_log entry, empty dataset, idempotent re-run
- `ingest_boiler_permits()` — mock SODA client round-trip, all 17 fields stored, DELETE+re-insert behavior, ingest_log entry, empty dataset
- CLI flags: `--electrical-permits`, `--plumbing-permits`, `--boiler` existence verified via source inspection
- `run_ingestion()` signature: `electrical_permits`, `plumbing_permits`, `boiler` kwargs verified present and defaulting to `True`
- Cross-type isolation: electrical vs plumbing in shared `permits` table; boiler in separate `boiler_permits` table

### Audit: Pre-existing functions (no new code needed)

Discovered that all three ingest functions already existed in `src/ingest.py`:
- `ingest_electrical_permits()` (line 1136) — endpoint `ftty-kx6y`
- `ingest_plumbing_permits()` (line 1169) — endpoint `a6aw-rudh`
- `ingest_boiler_permits()` (line 1441) — endpoint `5dp4-gtxk`

CLI flags and `run_ingestion()` wiring were also already present. Task spec listed stale SODA endpoint IDs (sb82-77pd, p7e6-mr2g, iif8-dssv) — production endpoints differ but are correct in the codebase.

### Test Results

- **51 tests added, 51 passing**
- Pre-existing failure: `test_landing.py::TestLandingPage::test_landing_has_feature_cards` — confirmed pre-existing (fails without our changes)
- No regressions introduced
