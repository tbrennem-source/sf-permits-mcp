# Scenarios Pending Review — QS8-T3-C

## SUGGESTED SCENARIO: Expediter finds all active electrical permits at an address
**Source:** src/ingest.py — ingest_electrical_permits, _normalize_electrical_permit
**User:** expediter
**Starting state:** Electrical permits have been ingested into the permits table with permit_type='electrical'
**Goal:** Find all active electrical permits at a property to understand current electrical work scope
**Expected outcome:** Search returns electrical permits with correct address, status, description, and filing/issue dates; permit_type is clearly identified as electrical
**Edge cases seen in code:** zip_code field aliased to zipcode column — searches by zip must handle this; neighborhood and supervisor_district are NULL for electrical permits (not in source dataset)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Homeowner checks plumbing permit status after water heater replacement
**Source:** src/ingest.py — ingest_plumbing_permits, _normalize_plumbing_permit
**User:** homeowner
**Starting state:** Plumbing permit filed and issued; data ingested into permits table with permit_type='plumbing'
**Goal:** Confirm their plumbing permit was issued and completed so they can close out with the contractor
**Expected outcome:** Permit lookup returns plumbing permit with filed_date, issued_date, completed_date, and status; parcel_number and unit fields (present in source data) are not exposed since they don't exist in the permits schema
**Edge cases seen in code:** parcel_number and unit fields exist in SODA dataset but are dropped during normalization — users asking for parcel_number won't find it via permit lookup
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Property inspector looks up boiler permit history for a commercial building
**Source:** src/ingest.py — ingest_boiler_permits, _normalize_boiler_permit
**User:** expediter
**Starting state:** Boiler permits have been ingested into the boiler_permits table (separate from the main permits table)
**Goal:** Find all boiler permits at a commercial property to verify boiler equipment compliance history
**Expected outcome:** Boiler permits are returned with boiler_type, boiler_serial_number, model, expiration_date, and application_date; results are from boiler_permits table (distinct from building/electrical/plumbing permits)
**Edge cases seen in code:** Boiler permits are NOT in the shared permits table — tools querying permits table only will miss them; neighborhood and supervisor_district fields are available (unlike electrical permits)
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Expediter verifies permit data freshness across all permit types
**Source:** src/ingest.py — run_ingestion, ingest_log table
**User:** expediter
**Starting state:** Full ingest pipeline has been run; ingest_log has entries for all dataset types
**Goal:** Confirm when electrical, plumbing, and boiler permit data was last refreshed to assess data currency for a client report
**Expected outcome:** System shows last-updated timestamps for electrical (ftty-kx6y), plumbing (a6aw-rudh), and boiler (5dp4-gtxk) datasets via ingest_log; times are human-readable and indicate same-day freshness after a nightly run
**Edge cases seen in code:** Each ingest run uses INSERT OR REPLACE on ingest_log — re-running updates the timestamp; boiler permits use DELETE+re-insert pattern (not INSERT OR REPLACE) so partial failures leave no data
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Admin triggers selective re-ingest of only electrical permits from CLI
**Source:** src/ingest.py — main() argparse block, --electrical-permits flag
**User:** admin
**Starting state:** Full database is populated but electrical permit data may be stale
**Goal:** Re-ingest only electrical permits without touching other datasets to save time
**Expected outcome:** Running `python -m src.ingest --electrical-permits` updates only electrical permit records; building, plumbing, boiler, and all other tables are unchanged; ingest_log shows updated timestamp only for electrical endpoint
**Edge cases seen in code:** do_all logic: if ANY specific flag is passed, do_all=False and only flagged datasets run; --boiler flag controls boiler permits (not --boiler-permits); --plumbing-permits controls plumbing permits (separate from --plumbing which controls plumbing inspections)
**CC confidence:** high
**Status:** PENDING REVIEW
