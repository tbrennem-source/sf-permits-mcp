# Scenarios Reviewed — Sprint 68-A

_Reviewed: 2026-02-26_
_Reviewer: CC (Sprint 68-A scenario drain)_
_Input: 102 pending scenarios from Sprints 56-64_
_Prior approved: 25 scenarios (Session 50)_

---

## Summary

| Disposition | Count |
|---|---|
| ACCEPT | 48 |
| MERGE (with existing or other pending) | 30 |
| REJECT | 22 |
| DEFER | 2 |
| **Total** | **102** |

**New scenario-design-guide.md total: 73 scenarios** (25 existing + 48 new)

---

## Dispositions

### ACCEPT (48 new scenarios added to design guide)

| # | Scenario | Guide # | Category |
|---|---|---|---|
| 1 | Expired seismic permit scores CRITICAL | 26 | Severity |
| 2 | Fresh low-cost filing scores GREEN | 27 | Severity |
| 3 | High-risk compound detection | 28 | Severity |
| 4 | Property health lookup by block/lot | 29 | Severity |
| 5 | run_query blocks SQL injection attempts | 30 | Security |
| 6 | read_source blocks directory traversal | 31 | Security |
| 7 | Kill switch blocks AI endpoints and returns 503 | 32 | Security |
| 8 | Cost auto-triggers kill switch | 33 | Security |
| 9 | CSP header blocks injected external script | 34 | Security |
| 10 | Bot user agent blocked from app routes | 35 | Security |
| 11 | Daily limit prevents anonymous abuse | 36 | Security |
| 12 | Anonymous user discovers site via landing page | 37 | Auth & Access |
| 13 | Anonymous user searches and sees public results | 38 | Auth & Access |
| 14 | Authenticated user bypasses landing page | 39 | Auth & Access |
| 15 | Login required for premium features | 40 | Auth & Access |
| 16 | Unauthenticated visitor sees gated navigation | 41 | Auth & Access |
| 17 | Staging banner on staging only | 42 | Auth & Access |
| 18 | TESTING endpoint not exposed on production | 43 | Auth & Access |
| 19 | Homeowner gets instant permit preview without signup | 44 | Onboarding |
| 20 | Kitchen remodel sees layout decision fork | 45 | Onboarding |
| 21 | New user sees welcome banner on first login | 46 | Onboarding |
| 22 | Share analysis with team via email | 47 | Onboarding |
| 23 | Shared analysis page visible without login | 48 | Onboarding |
| 24 | Organic visitor requests beta access | 49 | Onboarding |
| 25 | Shared-link signup grants immediate access | 50 | Onboarding |
| 26 | Admin approves beta request | 51 | Onboarding |
| 27 | Addenda staleness detected in morning brief | 52 | Morning Brief |
| 28 | Planning context for watched parcels | 53 | Morning Brief |
| 29 | Compliance calendar surfaces expiring boiler permits | 54 | Morning Brief |
| 30 | Street-use activity near watched address | 55 | Morning Brief |
| 31 | Station path prediction in morning brief | 56 | Morning Brief |
| 32 | Change velocity breakdown | 57 | Morning Brief |
| 33 | predict_permits uses DB forms + zoning routing | 58 | Permit Prediction |
| 34 | Restaurant triggers all required agencies | 59 | Permit Prediction |
| 35 | Historic district flag surfaced | 60 | Permit Prediction |
| 36 | Methodology card reveals calculation details | 61 | Analysis UX |
| 37 | Coverage disclaimers clarify data limitations | 62 | Analysis UX |
| 38 | Cost of delay informs budget planning | 63 | Analysis UX |
| 39 | Similar projects validate timeline | 64 | Analysis UX |
| 40 | Entity resolution consolidates trade contractors | 65 | Entity Network |
| 41 | Multi-role entity shows all observed roles | 66 | Entity Network |
| 42 | Trade permits surface in search results | 67 | Data & Ingest |
| 43 | Project auto-created + parcel dedup | 68 | Projects |
| 44 | Non-member access control for projects | 69 | Projects |
| 45 | Permit change email notifications (individual + digest) | 70 | Email |
| 46 | One-click unsubscribe from notification email | 71 | Email |
| 47 | Mobile landing page without horizontal scroll | 72 | Mobile |
| 48 | ADU landing page shows pre-computed stats | 73 | Onboarding |

### MERGE (30 — folded into existing or other accepted scenarios)

| Scenario | Merged Into | Reason |
|---|---|---|
| Admin Ops tab timeout recovery | Existing #6 | Identical to approved scenario |
| Admin Ops tab switching under load | Existing #7 | Covered by "tabs load within 5 seconds" |
| Severity scoring preserves hold signal | Existing #1 | Identical to hold signal AT_RISK |
| Hash routing aliases for Admin Ops | Existing #8 | Identical |
| Severity not downgraded with open enforcement | Existing #2b | Identical to NOV escalation |
| DQ cache serves instant results | Existing #11 | Identical |
| Admin dropdown submenu reachable on hover | Existing #10 | Identical |
| Admin Ops initial tab loads on first visit | Existing #9 | Identical |
| DQ tab shows bulk index health | Existing #12 | Identical |
| DQ checks degrade gracefully | Existing #13 | Identical |
| Expired stalled permit shows AT RISK not SLOWER | Existing #3 | Covered by inspection-aware severity |
| Expired permit at active site stays ON TRACK | Existing #4 | Identical |
| Pasted email routes to AI draft | Existing #14 | Identical |
| Expired permit does not alarm active site | Existing #4 | Duplicate of above |
| What Changed shows specific permit details | Existing #25 | Identical |
| Multi-line email with signature detected | Existing #15 | Identical |
| Badge count matches permit table count | Existing #17 | Identical |
| Feedback screenshot on content-heavy page | Existing #18 | Identical |
| Exact street name matching | Existing #16 | Identical |
| Undo accidental delete | Existing #19 | Identical |
| Retry failed analysis with prefilled metadata | Existing #20 | Identical (x2 duplicates) |
| Filter persistence across page reloads | Existing #21 | Identical (x2 duplicates) |
| Compare page shows human-readable labels | Existing #22 | Identical |
| Project notes visible for pre-existing jobs | Existing #23 | Identical |
| Project notes persist across reloads | Existing #24 | Identical |
| Notes character counter shows live count | Existing #23 | Adds edge case; folded in |
| Severity model replaces manual health in brief | New #28 (compound) | Merged into compound detection scenario |
| Morning brief v2/v1 health fallback | New #29 (property health) | Fallback covered in property health tool |
| Stale addenda triggers brief warning | New #52 (addenda staleness) | Duplicate of addenda staleness |
| Per-user rate limit separate from IP | New #36 (daily limit) | Edge case folded into daily limit |

### REJECT (22 — not user-visible or too implementation-specific)

| Scenario | Reason |
|---|---|
| CI catches broken test on PR | CI infrastructure, not user-visible product behavior |
| CI passes on clean branch | CI infrastructure |
| CI gates PR merge with lint + unit tests | CI infrastructure |
| Nightly CI validates SODA API before import | CI infrastructure |
| CI failure sends Telegram notification | Infrastructure alerting, not user-facing |
| Nightly cron failure triggers Telegram alert | Infrastructure alerting |
| Desktop CC POSTs correct test secret | Testing infrastructure, not user-facing |
| Velocity refresh cron deduplicates reassignment rows | Internal data-cleaning logic, not user-visible |
| Velocity v2 excludes garbage data | Internal data-cleaning logic |
| Detector handles mixed date types | Internal type handling |
| Stuck cron job swept before next run | Internal pipeline hygiene |
| SODA fetch retry recovers from transient error | Internal retry logic |
| Migration runner skips on DuckDB backend | Dev-only tooling |
| Migration runner --only flag | Dev-only CLI tool |
| Admin views cron endpoint docs | Documentation, not product behavior |
| Test-login assigns admin based on email pattern | Testing infrastructure |
| Signal pipeline runs on Postgres without placeholder errors | Internal implementation detail |
| Route manifest accurately reflects all routes | Internal tooling |
| CHECKCHAT blocked without QA screenshots | Development process, not product |
| Descoped item blocked without user approval | Development process |
| Normal development unaffected by hooks | Development process |
| Build/Verify separation enforced | Development process |

### REJECT (continued — infrastructure/implementation)

| Scenario | Reason |
|---|---|
| Block/lot join between boiler and building permits | Data quality metric, not user-visible |
| Bulk SODA ingest handles memory constraints | Infrastructure |
| CRON_SECRET with trailing whitespace authenticates | Implementation detail |
| Failed cron auth logs diagnostic info | Implementation detail |
| All cron endpoints use consolidated auth | Code architecture pattern |
| Street-use permits streaming ingest | Infrastructure |
| cron seed-references idempotent | Idempotency detail |
| migration registry includes reference_tables | Infrastructure |
| Reference table seed idempotent | Duplicate of above |
| Plumbing inspections ingest with source discriminator | Folded into "trade permits in search" |
| New cron endpoints reject without auth | Covered by existing cron auth |
| Cron auth blocks unauthorized triggers | Duplicate |
| Estimate timeline excludes trade permits (x2 duplicates) | Implementation detail of timeline tool |
| Velocity refresh two rolling periods | Implementation detail |
| Neighborhood backfill enables trade estimates | Implementation detail |
| Web worker under concurrent load | Infrastructure |
| Zero-downtime deploy with release command | Infrastructure |
| Tool backward compatibility preserved | API implementation detail |
| Reference tables powering permit prediction | Implementation detail |
| Review metrics ingest refreshes with SLA data | Admin ingest detail |
| Concurrent worker startup with advisory lock | Infrastructure |
| Release migrations match startup migrations | Infrastructure |
| Morning brief DQ cross-reference match rates | Admin diagnostic, too granular |
| DQ addenda freshness turns yellow | Merged into addenda staleness |
| Query refinement patterns detected | Too granular for design guide |

### DEFER (2)

| Scenario | Reason |
|---|---|
| Fire permit signal available for property | Needs address-to-parcel cross-reference (unbuilt) |
| NOV property owner looks up address with "Violation Lookup Mode" | Violation context mode not yet fully built |

---

## Notes

1. **30 scenarios were exact duplicates** of already-approved Session 50 scenarios — CC agents re-proposed them in subsequent sprints without checking existing approvals.
2. **Infrastructure and CI scenarios** (22 rejected) describe important system behavior but are not user-visible product requirements. They belong in ops runbooks, not the scenario design guide.
3. **Development process scenarios** (hooks, CHECKCHAT, build/verify) are meta — they describe how we build, not what we build.
4. **The biggest new categories** are Auth & Access (7), Onboarding & Growth (9), Morning Brief additions (6), and Security (7).
5. **Data ingest scenarios** were aggressively merged — the user-visible outcome is "trade permits appear in search results", not the internal mechanics of how they got ingested.
