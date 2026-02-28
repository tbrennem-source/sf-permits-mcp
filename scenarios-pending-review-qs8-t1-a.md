## SUGGESTED SCENARIO: property report loads fast for large parcels
**Source:** web/report.py _get_contacts_batch/_get_inspections_batch
**User:** expediter
**Starting state:** A parcel with 40+ permits (e.g., large commercial building) exists in the database. Each permit has multiple contacts and inspections.
**Goal:** Load the property report page without waiting 10+ seconds.
**Expected outcome:** Report renders in under 3 seconds. All permit contacts and inspections are present and correctly attributed to each permit.
**Edge cases seen in code:** Empty permit list returns empty contacts/inspections maps without any DB call. Permits with no contacts get an empty list (not an error). Permits with no permit_number are skipped in the batch.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: property report contacts are role-ordered per permit
**Source:** web/report.py _get_contacts_batch ORDER BY role priority
**User:** expediter
**Starting state:** A permit has contacts with roles: contractor, engineer, applicant.
**Goal:** View the property report and see contacts listed in a consistent order.
**Expected outcome:** Applicant appears first, then contractor, then engineer, then others. Order is consistent regardless of how data was inserted.
**Edge cases seen in code:** CASE WHEN ordering handles NULL/empty role strings via COALESCE — they sort last.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: SODA data is served from cache on rapid re-render
**Source:** web/report.py _soda_cache (15-min TTL)
**User:** expediter
**Starting state:** A property report was recently loaded (< 15 minutes ago). SODA API is available.
**Goal:** Load the same property report again (e.g., browser back-forward navigation or admin review).
**Expected outcome:** Second load is noticeably faster. SODA API is not called again. Complaints, violations, and property data are identical to the first load.
**Edge cases seen in code:** Cache is keyed by endpoint_id:block:lot — different parcels never share cache entries. Cache is module-level so it persists for the process lifetime.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: stale SODA cache is refreshed after TTL expires
**Source:** web/report.py _SODA_CACHE_TTL = 900
**User:** expediter
**Starting state:** A property report was loaded 16 minutes ago. A new complaint was filed since then.
**Goal:** Load the property report and see the new complaint.
**Expected outcome:** SODA API is called fresh. The new complaint appears in the report. Old cached data is replaced.
**Edge cases seen in code:** TTL checked via time.monotonic() — not affected by system clock changes. Expired entries are replaced, not deleted first.
**CC confidence:** low
**Status:** PENDING REVIEW
