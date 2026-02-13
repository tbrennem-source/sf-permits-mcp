# SODA API Performance Benchmarks

**Date:** 2026-02-12 (runs at ~6:01pm and ~6:05pm PST)
**App Token:** No (SODA_APP_TOKEN not set; using anonymous/shared rate limits)
**Method:** curl with `-w` timing (`time_total`, `time_starttransfer` for TTFB)
**Network:** Residential internet from macOS client
**Note:** All times include TLS handshake + network round-trip. TTFB = time to first byte (server processing time + network latency). Cold-cache vs warm-cache effects are noted where observed.

---

## Building Permits (`i98e-djp9`) -- 1,282,446 records

| Query Pattern | Latency | TTFB | Records | Payload | Notes |
|---|---|---|---|---|---|
| Count query | 499ms | 498ms | 1 | 22B | `$select=count(*)` |
| Count query (run 2) | 694ms | -- | 1 | 22B | Slight variance |
| Simple lookup (by permit_number) | 486ms | 486ms | 1 | 1.5KB | `$where=permit_number='202212017475'` |
| Filtered search (2 params) | 627ms | 624ms | 20 | 29KB | neighborhood + status (estimated_cost is text type, cannot use `>` directly) |
| Aggregation (by neighborhood) | 1,421ms | 1,420ms | 42 | 2.9KB | GROUP BY neighborhoods_analysis_boundaries |
| Pagination (1K records) | 2,018ms | 846ms | 1,000 | 1.4MB | TTFB 846ms, rest is transfer time |
| Pagination (10K records) | 5,891ms | 1,420ms | 10,000 | 14.0MB | TTFB 1.4s, ~4.5s transfer for 14MB |
| Full-text search (`$q=solar`) | 1,004ms | 920ms | 50 | 59KB | Full-text scan across all fields |

**Schema Notes:** `estimated_cost` is stored as text (not numeric), so `> 100000` comparisons require casting or string comparison. The `status` field uses lowercase values like `'issued'`, `'complete'`.

---

## Plumbing Permits (`a6aw-rudh`) -- 512,836 records

| Query Pattern | Latency | TTFB | Records | Payload | Notes |
|---|---|---|---|---|---|
| Count query | 556ms | 556ms | 1 | 21B | |
| Simple lookup | 529ms | 528ms | 1 | 535B | `$limit=1` |
| Filtered search (2 params) | 664ms | 664ms | 20 | 14KB | `status='complete' AND zipcode='94110'` |
| Aggregation (by status) | 598ms | 597ms | 12 | 426B | 12 distinct status values |
| Pagination (1K records) | 1,421ms | 1,153ms | 1,000 | 358KB | |
| Full-text search (`$q=water`) | 615ms | 614ms | 50 | 18KB | |

**Schema Notes:** No `estimated_cost` field. Fields: permit_number, application_date, block, lot, status, description, street_name, street_number, street_suffix, zipcode, etc.

---

## Electrical Permits (`ftty-kx6y`) -- 343,780 records

| Query Pattern | Latency | TTFB | Records | Payload | Notes |
|---|---|---|---|---|---|
| Count query | 1,131ms | 1,130ms | 1 | 21B | Notably slower count than other datasets |
| Count query (run 2) | 750ms | -- | 1 | 21B | Faster on second run (cache) |
| Simple lookup | 495ms | 495ms | 1 | 495B | `$limit=1` |
| Filtered search (2 params) | 680ms | 679ms | 20 | 14KB | `status='complete' AND zip_code='94110'` |
| Aggregation (by status) | 507ms | 506ms | 10 | 372B | 10 distinct status values |
| Pagination (1K records) | 1,145ms | 700ms | 1,000 | 952KB | |
| Full-text search (`$q=panel`) | 611ms | 608ms | 50 | 35KB | |

**Schema Notes:** Similar to plumbing but uses `zip_code` (with underscore) instead of `zipcode`. No `estimated_cost` field.

---

## Registered Business Locations (`g8m3-pdis`) -- 354,222 records

| Query Pattern | Latency | TTFB | Records | Payload | Notes |
|---|---|---|---|---|---|
| Count query | 642ms | 641ms | 1 | 21B | |
| Simple lookup | 477ms | 476ms | 1 | 559B | `$limit=1` |
| Filtered search (zip + active) | 721ms | 721ms | 20 | 16KB | `business_zip='94110' AND location_end_date IS NULL` |
| Aggregation (by zip) | 541ms | 540ms | 20 | 837B | |
| Pagination (1K records) | 1,558ms | 1,162ms | 1,000 | 707KB | |
| Full-text search (`$q=restaurant`) | 717ms | 632ms | 50 | 46KB | |

**Schema Notes:** Rich schema with uniqueid, certificate_number, ttxid, ownership details, NAICS codes, business_zip, location geometry, etc.

---

## Property Tax Rolls (`wv5m-vpq2`) -- 3,722,920 records

| Query Pattern | Latency | TTFB | Records | Payload | Notes |
|---|---|---|---|---|---|
| Count query | 819ms | 818ms | 1 | 22B | Larger dataset = slightly slower count |
| Count query (run 2) | 1,450ms | -- | 1 | 22B | Variable, sometimes slower |
| Simple lookup | 535ms | 535ms | 1 | 1.3KB | `$limit=1` |
| Filtered search (year + block) | 504ms | 503ms | 6 | 8KB | `closed_roll_year='2024' AND block='3512'` -- very fast with indexed fields |
| Aggregation (by year) | **14,166ms** | 14,165ms | 18 | 829B | **COLD CACHE: 14.2s** -- full table scan of 3.7M records |
| Aggregation (by year, run 2) | **707ms** | -- | 18 | 829B | **WARM CACHE: 707ms** -- 20x faster after caching |
| Pagination (1K records) | 1,144ms | 638ms | 1,000 | 1.3MB | |
| Full-text search (`$q=market`) | 1,384ms | 1,300ms | 50 | 67KB | Slower due to dataset size |

**Key Finding:** Aggregation on the largest dataset (3.7M rows) can take 14+ seconds on a cold cache, but drops to ~700ms once cached. This is the most important finding for caching strategy.

---

## Building Inspections (`vckc-dh2h`) -- 670,946 records

| Query Pattern | Latency | TTFB | Records | Payload | Notes |
|---|---|---|---|---|---|
| Count query | 576ms | 576ms | 1 | 21B | |
| Simple lookup | 983ms | 982ms | 1 | 858B | Slower than typical -- possibly cold |
| Filtered search (code + result) | -- | -- | -- | -- | Schema uses `code` + `result` fields; exact filter values unclear |
| Aggregation (by inspection_description) | 652ms | 651ms | 20 | 1.2KB | Corrected from initial schema mismatch |
| Pagination (1K records) | 1,286ms | 746ms | 1,000 | 831KB | |
| Full-text search (`$q=fire`) | **9,999ms** | 9,997ms | 31 | 26KB | **COLD CACHE: 10s** |
| Full-text search (`$q=fire`, run 2) | **2,374ms** | -- | 31 | 26KB | **WARM CACHE: 2.4s** -- still slow for full-text |

**Key Finding:** Full-text search on this dataset is unusually slow (2-10s), likely because the dataset has many text fields that need scanning. Only 31 results found, suggesting sparse matches.

**Schema Notes:** Uses `inspection_description`, `code`, `result`, `analysis_neighborhood`, `inspector`, `bid_district` instead of more standard field names.

---

## Street-Use Permits (`b6tj-gt35`) -- 1,202,419 records

| Query Pattern | Latency | TTFB | Records | Payload | Notes |
|---|---|---|---|---|---|
| Count query | 610ms | 610ms | 1 | 22B | |
| Count query (run 2) | 1,917ms | -- | 1 | 22B | High variance on this dataset |
| Simple lookup | 457ms | 457ms | 1 | 951B | `$limit=1` |
| Filtered search (permit_type) | 561ms | 561ms | 20 | 21KB | `permit_type='Excavation'` |
| Aggregation (by permit_type) | **10,115ms** | 10,115ms | 20 | 887B | **COLD CACHE: 10.1s** |
| Aggregation (by permit_type, run 2) | **597ms** | -- | 20 | 887B | **WARM CACHE: 597ms** -- 17x faster |
| Pagination (1K records) | 1,992ms | 1,130ms | 1,000 | 1.1MB | |
| Full-text search (`$q=sidewalk`) | 976ms | 887ms | 50 | 65KB | |

**Key Finding:** Another large dataset with dramatic cold-cache aggregation penalty (10s -> 600ms).

---

## Cross-Dataset Summary

### Latency by Query Pattern (typical, warm cache)

| Query Pattern | Small Dataset (<500K) | Medium (500K-1M) | Large (>1M) |
|---|---|---|---|
| Count (`$select=count(*)`) | 500-650ms | 550-650ms | 600-1500ms |
| Simple lookup (`$limit=1`) | 450-530ms | 500-980ms | 460-535ms |
| Filtered search (2-3 params) | 500-720ms | 550-660ms | 500-630ms |
| Aggregation (GROUP BY) | 500-600ms | 600-650ms | 600-1400ms (cold: 10-14s) |
| Pagination (1K records) | 1,100-1,560ms | 1,290-1,420ms | 1,140-2,020ms |
| Pagination (10K records) | -- | -- | ~5,900ms (14MB) |
| Full-text search (`$q=`) | 610-720ms | 615-10,000ms | 980-1,380ms |

### Record Counts Verified

| Dataset | Records | Category |
|---|---|---|
| Building Permits (i98e-djp9) | 1,282,446 | Large |
| Plumbing Permits (a6aw-rudh) | 512,836 | Medium |
| Electrical Permits (ftty-kx6y) | 343,780 | Small |
| Registered Business Locations (g8m3-pdis) | 354,222 | Small |
| Property Tax Rolls (wv5m-vpq2) | 3,722,920 | Very Large |
| Building Inspections (vckc-dh2h) | 670,946 | Medium |
| Street-Use Permits (b6tj-gt35) | 1,202,419 | Large |

### Payload Sizes

| Records Returned | Typical Payload Size | Per-Record Average |
|---|---|---|
| 1 (count) | 21-22 bytes | -- |
| 1 (full record) | 500B - 1.5KB | 500B - 1.5KB |
| 20 (filtered) | 8KB - 30KB | 400B - 1.5KB |
| 50 (search) | 18KB - 68KB | 360B - 1.4KB |
| 1,000 (pagination) | 358KB - 1.46MB | 360B - 1.5KB |
| 10,000 (pagination) | ~14MB | ~1.4KB |

---

## Summary and Recommendations

### API Performance Characteristics

1. **Baseline latency is ~450-650ms** for any query, regardless of dataset size. This is dominated by TLS handshake + network round-trip + SODA query planning overhead.

2. **Filtered queries are fast (500-720ms)** even on the largest datasets (3.7M records). The SODA API has good index support for `$where` clauses on common fields.

3. **Aggregation queries have extreme cold-cache variance:**
   - First run on large datasets: **10-14 seconds** (full table scan)
   - Subsequent runs: **600-700ms** (cached results)
   - This 17-20x difference is the single biggest performance concern.

4. **Full-text search (`$q=`) is unpredictable:**
   - Most datasets: 600ms - 1.4s (acceptable)
   - Building Inspections: 2.4s - 10s (problematic)
   - Performance depends on how many text fields exist and match density.

5. **Pagination bandwidth is the bottleneck for large fetches:**
   - 1,000 records: 1.1-2.0s (358KB-1.5MB payloads)
   - 10,000 records: ~5.9s (14MB payload)
   - Transfer time dominates over server processing time (TTFB ~0.6-1.4s).

6. **No rate limiting observed** across ~60 queries in rapid succession without an app token. The 0.3-0.5s delay between queries likely helped.

### What the API Is Sufficient For

- **Single record lookups** by permit number, parcel, etc. -- ~500ms is fine for interactive use.
- **Filtered searches** with 1-3 parameters returning 20-50 results -- consistently under 750ms.
- **Count queries** -- fast enough for UI display (~500-800ms).
- **Small aggregations** on warm cache -- fine for dashboards refreshed periodically.
- **Full-text search** on most datasets (except Building Inspections) -- under 1.5s.

### Where Local Storage / Caching Is Recommended

- **Aggregation results** should be cached locally with a TTL of 1-24 hours. Cold-cache aggregations on datasets >1M rows can take 10-14 seconds, which is unacceptable for interactive use.
- **Property Tax Rolls (3.7M records)** -- any query pattern that touches the full dataset benefits from local caching or pre-computation.
- **Building Inspections full-text search** -- if fire/safety keyword searches are common, pre-fetch and index locally.
- **Bulk data fetches** (>1,000 records) -- if your application needs to display or process large result sets, consider nightly sync to local storage. At 14MB per 10K records, fetching the full 1.28M Building Permits dataset would be ~1.8GB of JSON.
- **Repeated identical queries within a session** -- implement client-side response caching with 5-minute TTL to avoid redundant API calls.

### Rate Limit Observations

- No rate limiting encountered during this benchmark session (~60 queries over ~5 minutes, no app token).
- Anonymous rate limit is documented as ~1,000 requests/hour (shared by IP).
- With an app token, limit increases to ~1,000 requests/rolling hour per token.
- For an MCP server handling a single user session, rate limits are unlikely to be a concern (typical session would make 10-30 queries).

### Estimated Queries Per Session

For a typical permit lookup session:
- 1-2 count queries (orientation)
- 3-5 filtered searches (finding specific permits)
- 1-2 aggregations (neighborhood/status breakdowns)
- 0-1 full-text searches
- **Total: ~5-10 queries per session**, well within rate limits.

### Schema Inconsistencies to Note

| Field Concept | Building Permits | Plumbing Permits | Electrical Permits | Business Locations | Property Tax | Building Inspections | Street-Use |
|---|---|---|---|---|---|---|---|
| Zip code | `zipcode` | `zipcode` | `zip_code` | `business_zip` | -- | `zip_code` | -- |
| Status | `status` | `status` | `status` | -- | -- | `result` | -- |
| Cost/Value | `estimated_cost` (text!) | -- | -- | -- | multiple $ fields | -- | -- |
| Neighborhood | `neighborhoods_analysis_boundaries` | -- | -- | -- | -- | `analysis_neighborhood` | -- |

These inconsistencies mean each dataset requires its own query templates. A unified query layer should map logical field names to physical field names per dataset.

---

## Phase 2: DuckDB Entity Resolution & Graph Benchmarks

**Date:** 2026-02-13
**Machine:** macOS Apple Silicon (M-series), 32GB RAM
**Database:** DuckDB 1.2.2, file-based (602MB)

### Data Ingestion (SODA API -> DuckDB)

| Dataset | Records | Time | Rate | Notes |
|---|---|---|---|---|
| Building Contacts | 1,004,592 | 158.9s | 6,300 rec/s | 101 pages @ 10K/page |
| Electrical Contacts | 339,926 | 62.4s | 5,400 rec/s | 34 pages |
| Plumbing Contacts | 502,534 | 73.1s | 6,900 rec/s | 51 pages |
| Building Permits | 1,137,723 | 560.0s | 2,300 rec/s | 114 pages, slower pagination near end |
| Building Inspections | 671,170 | 214.3s | 3,100 rec/s | 68 pages, required retry logic |
| **Total** | **3,655,945** | **~1,069s** | **~3,400 rec/s** | **DuckDB file: 602MB** |

### Entity Resolution Pipeline

| Step | Entities Created | Contacts Resolved | Time | Method |
|---|---|---|---|---|
| 0. Clear existing | -- | -- | ~300s | UPDATE 1.8M rows to NULL |
| 1. pts_agent_id | 1,004,592 | 1,004,592 / 1,847,052 | 211.9s | DENSE_RANK + SQL join |
| 2. license_number | 9,873 | 1,846,838 / 1,847,052 | 179.3s | VALUES temp table + merge |
| 3. sf_business_license | 0 | 1,846,838 / 1,847,052 | 0.0s | All already covered |
| 4. Fuzzy name matching | 18 | 1,846,865 / 1,847,052 | 0.1s | Blocking + Jaccard similarity |
| 5. Singletons | 187 | 1,847,052 / 1,847,052 | 0.1s | ROW_NUMBER INSERT...SELECT |
| **Total** | **1,014,670** | **1,847,052 (100%)** | **785.1s** | **1.82x dedup ratio** |

**Key findings:**
- 98.9% of entities resolved via pts_agent_id (high confidence)
- 0.97% via license_number cross-dataset merging (medium confidence)
- Only 214 contacts remained after key-based resolution (0.01%)
- Pure SQL approach (DENSE_RANK + temp tables) critical for performance on 1.8M rows

### Co-occurrence Graph

| Metric | Value |
|---|---|
| Edges | 576,323 |
| Build time | 1.2s |
| Max edge weight | 1 |
| Avg edge weight | 1.00 |
| Max entity degree | 74 |

### Anomaly Detection

| Anomaly Type | Flagged |
|---|---|
| High permit volume (>3 stddev) | 2,783 entities |
| Fast approvals | 12,422 permits |
| Inspector concentration | 0 |
| Geographic concentration | 0 |
| Clusters (min_size=3, min_weight=1) | 88,916 |

**Top entities by permit volume:**
1. Gary Lemasters (contractor, Arb Inc): 12,674 permits
2. "*" (Homeowner's Permit): 8,239 permits
3. Peter & Josephine Mchugh (Ayoob & Peery Plumbing): 7,994 permits
4. Bayardo Chamorro (contractor): 7,309 permits
5. Leanne Goff (contractor): 7,205 permits

### Ground Truth Validation

| Target | Found | Details |
|---|---|---|
| Rodrigo Santos (inspector) | No | Not in current inspections dataset (2014-2026) |
| Florence Kong (inspector) | No | Not in current inspections dataset |
| Bernard Curran (inspector) | **Yes** | 7,495 inspections, 5,842 permits, 39 neighborhoods (2014-2021), 20 linked entities |

### Database Schema Summary

| Table | Rows | Description |
|---|---|---|
| contacts | 1,847,052 | Raw contact records from 3 SODA datasets |
| permits | 1,137,723 | Building permit records |
| inspections | 671,170 | Building inspection records |
| entities | 1,014,670 | Deduplicated entity records |
| relationships | 576,323 | Entity co-occurrence edges |
| ingest_log | 5 | Ingestion metadata |
