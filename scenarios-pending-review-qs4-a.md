## SUGGESTED SCENARIO: Admin views station SLA compliance and identifies bottleneck departments
**Source:** QS4-A /admin/metrics dashboard
**User:** admin
**Starting state:** Admin is logged in, metrics data has been ingested
**Goal:** View which review stations are meeting their SLA targets and identify departments causing delays
**Expected outcome:** Dashboard shows station-level SLA percentages with color coding (green >= 80%, amber 60-79%, red < 60%), sorted by volume, enabling admin to identify bottleneck stations
**Edge cases seen in code:** NULL stations are excluded; zero-total stations handled to avoid division by zero; DuckDB BOOLEAN vs Postgres BOOLEAN for met_cal_sla
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Station velocity query returns cached results in under 100ms
**Source:** QS4-A station_velocity_v2 caching layer
**User:** expediter | architect
**Starting state:** Velocity cache has been populated by nightly cron job
**Goal:** Get station processing time estimates without waiting for a 3.9M-row addenda query
**Expected outcome:** Pre-computed velocity data returned from station_velocity_v2 table; falls back to 'all' period if requested period has no data; returns None gracefully on cache miss
**Edge cases seen in code:** Stale cache handled by nightly refresh; fallback from 'current' to 'all' period; CURRENT_WIDEN_DAYS=180 fallback when sample count < 30
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Nightly pipeline includes metrics refresh alongside permit data
**Source:** QS4-A run_ingestion() pipeline integration
**User:** admin
**Starting state:** Nightly ingestion pipeline runs on schedule
**Goal:** Ensure metrics datasets (issuance, review, planning) are refreshed during the main pipeline run, not only via separate cron endpoints
**Expected outcome:** run_ingestion() calls all 3 metrics ingest functions after dwelling_completions, keeping metrics data in sync with permit data
**Edge cases seen in code:** Metrics ingest runs outside the try block's feature-flag guards (always runs); individual metrics cron endpoints still available for manual refreshes
**CC confidence:** high
**Status:** PENDING REVIEW
