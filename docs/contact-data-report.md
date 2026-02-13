# SF Permit Contact/Actor Data Discovery Report

**Date:** 2026-02-12
**Purpose:** Map available contact/actor data in SF permit datasets for fraud detection social network modeling

---

## 1. Building Permits Contacts (3pee-9qhc)

### Record Count
**1,004,592 records**

### Full Field List

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique row identifier |
| `permit_number` | string | Links to building permits (i98e-djp9) |
| `first_name` | string | Contact's first name (free-text) |
| `last_name` | string | Contact's last name (free-text) |
| `role` | string | Actor type (see breakdown below) |
| `agent_address` | string | Individual's address (free-text, single field) |
| `city` | string | Agent city |
| `state` | string | Agent state |
| `agent_zipcode` | string | Agent zip code |
| `firm_name` | string | Company/firm name (free-text) |
| `firm_address` | string | Firm street address |
| `firm_city` | string | Firm city |
| `firm_state` | string | Firm state |
| `firm_zipcode` | string | Firm zip (format: XXXXX-XXXX) |
| `pts_agent_id` | string | **Internal agent ID from Permit Tracking System** |
| `from_date` | datetime | Date contact was associated with permit |
| `is_applicant` | string | Y/N flag |
| `license1` | string | Professional license number (e.g., "C22921" for architects, "552877" for contractors) |
| `sf_business_license_number` | string | SF business registration number |
| `data_as_of` | datetime | Data snapshot timestamp |
| `data_loaded_at` | datetime | ETL load timestamp |

### Role Breakdown (Actor Types)

| Role | Count | % of Total | NYC Equivalent |
|------|-------|------------|----------------|
| contractor | 573,125 | 57.1% | Contractor (general/filing) |
| authorized agent-others | 142,565 | 14.2% | Filing Representative (partial) |
| architect | 94,795 | 9.4% | Architect of Record |
| engineer | 68,714 | 6.8% | Engineer of Record |
| lessee | 42,323 | 4.2% | (no NYC equivalent) |
| payor | 31,679 | 3.2% | (no NYC equivalent) |
| pmt consultant/expediter | 25,571 | 2.5% | Filing Representative / Permit Expediter |
| designer | 14,844 | 1.5% | (subcategory of architect) |
| project contact | 10,278 | 1.0% | (no direct equivalent) |
| attorney | 565 | 0.06% | (no direct equivalent) |
| subcontractor | 133 | 0.01% | (no direct equivalent) |

### Join Key
**`permit_number`** joins to building permits dataset (i98e-djp9) on its `permit_number` field.

### Name Quality
- **Free-text, not normalized.** Names split into `first_name` and `last_name` but with data quality issues:
  - Example: first_name="William Kuk Son", last_name="Jo" (multi-word first name)
  - Example: first_name="Raracahn", last_name="Architecture" (firm name in last_name field)
  - Example: last_name="Hacker Architects" (firm suffix in name)
- Entity resolution will require fuzzy matching and cleaning.

### License Numbers
- `license1`: Present for architects (format "C22921") and contractors (numeric like "552877"). **Not populated on all records.**
- `sf_business_license_number`: SF local business license. Present on contractor records more consistently.
- `pts_agent_id`: Internal system ID -- **potentially the strongest identifier for entity resolution** as it persists across permits.

### Key Observation
The `pts_agent_id` field is a system-assigned identifier for each contact in SF's Permit Tracking System. This is a critical link for building the social network -- the same `pts_agent_id` appearing on multiple permits indicates the same entity, bypassing the need for name-based fuzzy matching.

---

## 2. Electrical Permits Contacts (fdm7-jqqf)

### Record Count
**339,926 records**

### Full Field List

| Field | Type | Description |
|-------|------|-------------|
| `permit_number` | string | Links to electrical permits (format: E2005XXXXXXXX) |
| `contact_type` | string | Actor type |
| `company_name` | string | Business/individual name (free-text, single field) |
| `street_number` | string | Address number |
| `street` | string | Street name |
| `street_suffix` | string | St, Av, Dr, etc. |
| `state` | string | State code |
| `zipcode` | string | Zip code |
| `phone` | string | Primary phone |
| `phone2` | string | Secondary phone (optional) |
| `license_number` | string | Contractor license number |
| `is_applicant` | string | Y/N flag |
| `sf_business_license_number` | string | SF business registration |
| `data_as_of` | datetime | Snapshot timestamp |
| `data_loaded_at` | datetime | ETL load timestamp |

### Contact Type Breakdown

| Contact Type | Count | Notes |
|-------------|-------|-------|
| Contractor | 339,426 | 99.85% of all records |
| Owner | 49 | Extremely rare |
| Others | 37 | Miscellaneous |

### Schema Differences from Building Permits Contacts

| Feature | Building (3pee-9qhc) | Electrical (fdm7-jqqf) |
|---------|----------------------|------------------------|
| Name fields | `first_name` + `last_name` | `company_name` (single field) |
| Role field | `role` (11 types) | `contact_type` (3 types) |
| Agent ID | `pts_agent_id` (present) | **NOT present** |
| Firm fields | Separate firm_name, firm_address, etc. | No firm fields (company_name serves dual purpose) |
| Address | `agent_address` (single) + firm fields | Structured: street_number + street + street_suffix |
| Phone | Not present | `phone` + `phone2` |

### Key Observation
The electrical contacts dataset is **contractor-dominated** (99.85%) with almost no owner or other role data. It also lacks the `pts_agent_id` field, making cross-dataset entity resolution harder. The `company_name` field contains both individual names and business names in a single unstructured field (e.g., "James I Frost" for an owner vs. a business name for a contractor).

---

## 3. Plumbing Permits Contacts (k6kv-9kix)

### Record Count
**502,534 records**

### Full Field List

| Field | Type | Description |
|-------|------|-------------|
| `permit_number` | string | Links to plumbing permits (format: PMW2024XXXXXXX or numeric) |
| `firm_name` | string | Business name (single field) |
| `license_number` | string | Contractor license number |
| `address` | string | Business address (single free-text field) |
| `city` | string | City |
| `state` | string | State |
| `phone` | string | Phone number |
| `zipcode` | string | Zip code (format: XXXXX-XXXX) |
| `is_applicant` | string | Y/N flag |
| `sf_business_license_number` | string | SF business registration |
| `data_as_of` | datetime | Snapshot timestamp |
| `data_loaded_at` | datetime | ETL load timestamp |

### Schema Differences
- **No contact_type/role field** -- all records are implicitly contractors.
- **No individual name fields** -- only `firm_name`.
- **No `pts_agent_id`** -- no internal system identifier.
- Simplest schema of the three contact datasets.

---

## 4. Other Contact Datasets Found

### From Socrata Catalog Search

| Dataset | ID | Type | Relevance |
|---------|-----|------|-----------|
| Building Permits with Permit Contacts | 9itm-3rmi | Filter view | Pre-joined building permits + contacts. Convenience view, same underlying data. |
| Building Permits Lookup by Contractor, Subcontractor, Architect, Designer, or Engineer | kvek-u79k | Story view | Interactive lookup. Not a raw data API. |
| Building Permits with Contractor, Subcontractor, Architect, Designer, or Engineer | cw8k-gwb7 | Filter view | Another pre-joined view of the same data. |
| SFEC Form 126f2 - Named Parties | djj2-gvaq | Dataset | City contract named parties (contractors/subcontractors). Different context (city procurement, not building permits). |
| SFEC Form 126f4 - Affiliates and Subcontractors | czjm-dat8 | Dataset | City contract affiliates. Same -- procurement, not building permits. |
| Section 604 Affidavit | 75h8-2zhw | Dataset | Building inspection affidavits signed by licensed professionals. Could contain architect/engineer license data. |
| Historic Context Statements | 43um-8u7u | Dataset | Has an "architect" column for historic buildings. Very different context. |

### Assessment of Additional Datasets
- The **pre-joined views** (9itm-3rmi, cw8k-gwb7) are convenience layers over the same 3pee-9qhc + i98e-djp9 data. No new information.
- The **SFEC forms** are government procurement data (who gets city contracts), not building permit actors. Low relevance for permit fraud detection.
- The **Section 604 Affidavit** dataset could be useful as an additional signal -- it links licensed professionals to building inspections.

---

## 5. Building Permits Main Dataset (i98e-djp9) -- Contact Fields

**No contact fields exist in the main building permits dataset.** All 33 fields are property/permit metadata:

Key fields: `permit_number`, `permit_type`, `permit_type_definition`, `block`, `lot`, `street_number`, `street_name`, `street_suffix`, `unit`, `description`, `status`, `status_date`, `filed_date`, `estimated_cost`, `revised_cost`, `existing_use`, `proposed_use`, `existing_units`, `proposed_units`, `supervisor_district`, `neighborhoods_analysis_boundaries`, `zipcode`, `location` (geo-coordinates).

**All contact information is externalized to 3pee-9qhc** and must be joined via `permit_number`.

---

## 6. Violation Data -- Notices of Violation (nbtm-fbw5)

### Record Count
**508,675 records**

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `complaint_number` | string | Unique complaint ID |
| `item_sequence_number` | string | Line item within complaint |
| `primary_key` | string | Composite: complaint_number-item_sequence_number |
| `date_filed` | datetime | When complaint was filed |
| `block` | string | Assessor block number |
| `lot` | string | Assessor lot number |
| `street_number` | string | Property address |
| `street_name` | string | Street name |
| `street_suffix` | string | St, Av, etc. |
| `unit` | string | Unit number (if applicable) |
| `status` | string | Active/not active |
| `receiving_division` | string | e.g., "Housing Inspection Services" |
| `assigned_division` | string | Which division is handling |
| `nov_category_description` | string | Category: "fire section", "interior surfaces section", etc. |
| `item` | string | Violation item code |
| `nov_item_description` | string | Free-text description of the violation |
| `neighborhoods_analysis_boundaries` | string | Neighborhood name |
| `supervisor_district` | string | District number |
| `zipcode` | string | Zip code |
| `location` | geo-point | Lat/long coordinates |

### How Violations Link to Permits
**There is NO direct `permit_number` field in the violations dataset.** Linking requires:
1. **Address matching:** Join on `block` + `lot` (assessor parcel, most reliable) or on `street_number` + `street_name` + `street_suffix`.
2. **Geo-spatial proximity:** Both datasets have `location` coordinates.

This is an **indirect join** -- a property at a given address may have both permits and violations, but there is no foreign key relationship.

---

## 7. Mehri Comparison: NYC vs SF Actor Types

### NYC Model (Mehri Reference) Requirements

| NYC Actor Type | Required for Fraud Model | SF Equivalent | SF Dataset | Quality |
|---------------|--------------------------|---------------|------------|---------|
| **Owner** | Yes -- property owner filing | `lessee` role (3pee-9qhc, 42K records) + rare `Owner` in electrical (49 records) | 3pee-9qhc | Partial -- "lessee" is not always "owner". No dedicated owner role in building contacts. |
| **Architect/Engineer of Record** | Yes -- licensed professional | `architect` (95K) + `engineer` (69K) + `designer` (15K) roles | 3pee-9qhc | Good coverage. License numbers present via `license1` field. |
| **Contractor (General/Filing)** | Yes -- who does the work | `contractor` role (573K records) | 3pee-9qhc, fdm7-jqqf, k6kv-9kix | Excellent coverage across all three datasets. License and business registration numbers available. |
| **Filing Representative (Expediter)** | Yes -- who files the permit | `pmt consultant/expediter` (26K) + `authorized agent-others` (143K) | 3pee-9qhc | Good. Expediters explicitly tracked. "Authorized agent-others" likely includes additional filing reps. |

### Gaps

1. **Owner data is thin.** The building permits contacts dataset has `lessee` (42K) but no explicit "owner" role. The electrical dataset has only 49 "Owner" records. Property ownership may need to be sourced from the SF Assessor-Recorder's data or cross-referenced with the block/lot to external ownership records.

2. **No person names in electrical/plumbing contacts.** The electrical dataset uses `company_name` (a single field mixing individual and business names). The plumbing dataset only has `firm_name`. Individual identity resolution across these datasets is harder.

3. **No `pts_agent_id` in electrical/plumbing.** The building permits contacts dataset has this system identifier, but the trade permit datasets do not. Cross-dataset entity matching for the same contractor working on building + electrical permits requires name/license matching.

---

## 8. Assessment: Can We Build the Social Network?

### Verdict: **YES, with caveats.**

### The Join Path

```
Building Permits (i98e-djp9)
    |
    |-- permit_number -->  Building Permits Contacts (3pee-9qhc)  [1M records, 11 role types]
    |                         |-- pts_agent_id (entity resolution within building permits)
    |                         |-- license1, sf_business_license_number (cross-dataset matching)
    |                         |-- first_name + last_name + firm_name (fuzzy matching)
    |
    |-- block + lot ------>  Notices of Violation (nbtm-fbw5)  [509K records]
    |   (address join)        |-- complaint_number, nov_category_description
    |
    |-- (separate universe)
    |
Electrical Permits --> Electrical Contacts (fdm7-jqqf)  [340K records, contractor-only]
    |                    |-- license_number, sf_business_license_number
    |                    |-- company_name (fuzzy match to firm_name above)
    |
Plumbing Permits ---> Plumbing Contacts (k6kv-9kix)  [503K records, contractor-only]
                       |-- license_number, sf_business_license_number
                       |-- firm_name (fuzzy match)
```

### Entity Resolution Strategy

**Strong identifiers (preferred):**
1. `pts_agent_id` -- Best identifier but only in building contacts (3pee-9qhc)
2. `license_number` / `license1` -- State contractor/architect license. Present across all three contact datasets. **Best cross-dataset join key.**
3. `sf_business_license_number` -- Local business registration. Present in all three. Good secondary key.

**Weak identifiers (fallback):**
4. `firm_name` / `company_name` -- Free-text, requires fuzzy matching and normalization
5. `first_name` + `last_name` -- Only in building contacts. Free-text with quality issues.
6. `phone` -- Only in electrical and plumbing contacts.

### Network Construction Potential

| Network Edge | Feasibility | Method |
|-------------|-------------|--------|
| Contractor <-> Permit | Excellent | Direct join via permit_number |
| Architect <-> Permit | Excellent | Direct join via permit_number (building only) |
| Expediter <-> Permit | Good | Direct join via permit_number (building only) |
| Contractor <-> Contractor (same permit) | Excellent | Two contacts on same permit_number |
| Contractor <-> Architect (same permit) | Excellent | Two contacts on same permit_number |
| Contractor <-> Property (violations) | Moderate | Requires block+lot address join |
| Same contractor across permit types | Moderate | Requires license_number or sf_business_license_number match |
| Owner <-> Permit | **Weak** | Lessee role exists but thin; no true "owner" role |

### Key Challenges

1. **Owner gap:** The Mehri model uses owner as a primary node. SF data has weak owner coverage in permits. Consider supplementing with SF Assessor data (property ownership records).

2. **Name normalization:** Free-text names with inconsistent formatting. Will need NLP-based entity resolution (dedupe library, etc.).

3. **Cross-permit-type linking:** Building, electrical, and plumbing contacts live in separate datasets with different schemas. The `license_number` and `sf_business_license_number` fields are the bridge, but coverage is not 100%.

4. **Violation linkage is address-based:** No direct permit-to-violation foreign key. Must join on block+lot or street address, which introduces potential false matches for multi-unit buildings.

### Recommendations for Implementation

1. **Start with building permits contacts (3pee-9qhc)** -- richest dataset, 1M records, 11 actor types, `pts_agent_id` for deduplication.
2. **Use `license_number` as the cross-dataset entity key** to link contractors across building/electrical/plumbing.
3. **Build the block+lot join** for violation signals on properties.
4. **Investigate SF Assessor data** for property ownership to fill the "Owner" gap.
5. **Pre-compute entity clusters** using `pts_agent_id` within building contacts, then expand via license number matching.

---

## Appendix: Dataset Summary

| Dataset | ID | Records | Actor Types | Has Names | Has License | Has System ID | Join Key |
|---------|-----|---------|-------------|-----------|-------------|---------------|----------|
| Building Permits Contacts | 3pee-9qhc | 1,004,592 | 11 roles | first_name + last_name | license1 | pts_agent_id | permit_number |
| Electrical Permits Contacts | fdm7-jqqf | 339,926 | 3 types | company_name (mixed) | license_number | None | permit_number |
| Plumbing Permits Contacts | k6kv-9kix | 502,534 | Implicit contractor only | firm_name only | license_number | None | permit_number |
| Notices of Violation | nbtm-fbw5 | 508,675 | N/A | None | None | complaint_number | block+lot (address) |
| Building Permits (main) | i98e-djp9 | ~250K+ | N/A | None | None | N/A | permit_number, block+lot |
