# SF Permits MCP — Dataset Catalog

**Discovery Date:** 2026-02-12
**Source:** data.sfgov.org (Socrata SODA API)
**Total Datasets Cataloged:** 20 primary + 5 related + 3 deprecated

---

## Permit Datasets

| Dataset | Endpoint | Records | Update | Contact Data |
|---|---|---|---|---|
| **Building Permits** | `i98e-djp9` | 1,282,446 | Nightly | No (see 3pee-9qhc) |
| **Building Permit Addenda + Routing** | `87xy-gk8d` | 3,918,600 | Nightly | plan_checked_by |
| **Plumbing Permits** | `a6aw-rudh` | 512,836 | Weekly | No |
| **Electrical Permits** | `ftty-kx6y` | 343,780 | Weekly | No (see fdm7-jqqf) |
| **Boiler Permits** | `5dp4-gtxk` | 151,708 | Weekly | No |
| **Street-Use Permits** | `b6tj-gt35` | 1,202,419 | Daily | agent, contact |
| **Large Utility Excavation** | `i926-ujnc` | 3,204 | Monthly | utility_contractor |
| **Utility Excavation (Active)** | `smdf-6c45` | 4,504 | Daily | utility_contractor |

## Contact / Actor Datasets

| Dataset | Endpoint | Records | Actor Types |
|---|---|---|---|
| **Building Permits Contacts** | `3pee-9qhc` | TBD | contractor, architect, owner (TBD) |
| **Electrical Permits Contacts** | `fdm7-jqqf` | TBD | contractor (TBD) |

**Status:** Deep-dive discovery in progress. These are the linchpin datasets for the Mehri-style social network model.

## Planning Datasets

| Dataset | Endpoint | Records | Update | Contact Data |
|---|---|---|---|---|
| **Planning Records - Projects** | `qvu5-m3a2` | 53,816 | Nightly | applicant, applicant_org |
| **Planning Records - Non-Projects** | `y673-d69b` | 228,090 | Nightly | applicant_org |

## Housing & Development

| Dataset | Endpoint | Records | Update |
|---|---|---|---|
| **SF Development Pipeline (Q3 2025)** | `6jgi-cpb4` | 2,063 | Quarterly |
| **Affordable Housing Pipeline** | `aaxw-2cb8` | 194 | Quarterly |
| **Dwelling Unit Completions** | `j67f-aayr` | 2,382 | Monthly |
| **Housing Production (2005+)** | `xdht-4php` | 5,798 | Annually |

## Enrichment Datasets

| Dataset | Endpoint | Records | Update |
|---|---|---|---|
| **Registered Business Locations** | `g8m3-pdis` | 354,222 | Daily |
| **Property Tax Rolls (2007-2024)** | `wv5m-vpq2` | 3,722,920 | Annually |

## Violation / Complaint Datasets

| Dataset | Endpoint | Records | Update | Contact Data |
|---|---|---|---|---|
| **Building Inspections** | `vckc-dh2h` | 670,946 | Nightly | inspector |
| **DBI Complaints** | `gm2e-bten` | 325,736 | Weekly | No |
| **Notices of Violation** | `nbtm-fbw5` | 508,675 | Daily | TBD |

---

## Cross-Reference Fields

Join keys that connect datasets:

| Field | Found In | Purpose |
|---|---|---|
| `permit_number` / `application_number` | Building, Plumbing, Electrical, Boiler, Street-Use, Addenda | Primary permit identifier |
| `block` + `lot` / `parcel_number` | Nearly all datasets | Parcel-level join key |
| `record_id` / `parent_id` / `child_id` | Planning Projects + Non-Projects | Planning record hierarchy |
| `case_no` / `planning_case_number` | Pipeline, Affordable Housing | Planning case cross-reference |
| `bpa` / `bpa_no` / `building_permit_application` | Pipeline, Housing Production, Dwelling Unit Completions | Building permit cross-reference |
| `supervisor_district` | Most datasets | Geographic aggregation |
| `neighborhoods_analysis_boundaries` / `analysis_neighborhood` | Most datasets | Neighborhood-level analysis |
| `reference_number` | Building Inspections | Links to permits when type='permit' |
| `complaint_number` | DBI Complaints, Notices of Violation | Complaint-violation linkage |

---

## Record Count Summary

| Category | Records |
|---|---|
| DBI Permits (Building + Addenda + Plumbing + Electrical + Boiler) | ~6,209,370 |
| Planning Records (Projects + Non-Projects) | ~281,906 |
| DPW/Public Works (Street-Use + Excavation) | ~1,210,127 |
| Housing/Development (Pipeline + Affordable + Completions + Production) | ~10,437 |
| Business & Property (Business Locations + Tax Rolls) | ~4,077,142 |
| Violations (Inspections + Complaints + NOVs) | ~1,505,357 |
| **Grand Total** | **~13,294,339** |

---

## Deprecated Datasets

| Dataset | Endpoint | Notes |
|---|---|---|
| SF Development Pipeline (Legacy) | `7mc4-5ee8` | 1 record. Use `6jgi-cpb4`. |
| SF Planning Permitting Data | `kncr-c6jw` | Replaced by `qvu5-m3a2` + `y673-d69b`. |
| SF Property Information Map | `i8ew-h6z7` | Not a data API. Interactive map. Returns 403. |

---

## API Usage Notes

- **Base URL:** `https://data.sfgov.org/resource/{endpoint_id}.json`
- **Default limit:** 1,000 records (use `$limit` to override, max 50,000)
- **Pagination:** `$limit` + `$offset`
- **Filtering:** SoQL via `$where`, `$select`, `$group`, `$order`
- **Count:** `$select=count(*)`
- **Full-text search:** `$q=keyword`
- **App token:** `X-App-Token` header for higher rate limits
