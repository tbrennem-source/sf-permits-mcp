## SUGGESTED SCENARIO: Property report loads cached parcel data

**Source:** QS5-A parcel_summary cache integration in report.py
**User:** expediter | homeowner
**Starting state:** parcel_summary table has a row for block/lot with tax_value, zoning_code, use_definition
**Goal:** View a property report without waiting for SODA API tax data call
**Expected outcome:** Property profile section shows assessed value, zoning, and use definition from cache; SODA property tax API call is skipped; complaints and violations still fetched live
**Edge cases seen in code:** parcel_summary row exists but all tax fields are NULL; concurrent cron refresh while report is loading
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Nightly parcel refresh materializes counts

**Source:** QS5-A cron refresh-parcel-summary endpoint
**User:** admin
**Starting state:** permits, tax_rolls, complaints, violations, boiler_permits, inspections tables populated
**Goal:** Run nightly cron job to materialize one-row-per-parcel summary with counts from 5+ source tables
**Expected outcome:** parcel_summary populated with correct permit_count, open_permit_count, complaint_count, violation_count, boiler_permit_count, inspection_count; canonical_address is UPPER-cased; tax_value computed from land + improvement; health_tier joined from property_health
**Edge cases seen in code:** parcel with no tax_rolls data (NULL tax fields); parcel with no complaints/violations (zero counts); property_health table doesn't exist yet (NULL health_tier)
**CC confidence:** high
**Status:** PENDING REVIEW
