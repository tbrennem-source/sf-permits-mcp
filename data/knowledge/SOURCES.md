# Knowledge Source Index
## SF Permitting Knowledge Base - Phase 2.5

Last updated: 2026-02-14

## Tier 1: Core Reference Documents (Structured JSON)

| Source ID | Title | File | Chars | Status |
|-----------|-------|------|-------|--------|
| G-20 | Building Permit Application Routing to City Agencies | tier1/G-20-routing.json | 133K | Structured - 154 routing entries, 14 discussion rules |
| G-20 (raw) | Raw text + tables | tier1/G-20-raw-text.txt, G-20-tables.json | 46K + 72K | Extracted from 34-page PDF |
| permit-forms | Building Permit Application Forms | tier1/permit-forms-taxonomy.json | 4.8K | Structured - 7 forms + selection logic |
| inhouse-review | In-House Review Process | tier1/inhouse-review-process.json | 10.2K | Structured - 11 steps with agency triggers |
| G-25 | Restaurant Permitting FAQ | tier2/G-series/G-26.txt* | 6.5K | Raw text (file naming offset - see note) |
| G-27 | Condo Unit Required Permits | tier2/G-series/G-28.txt* | 1.9K | Raw text (file naming offset) |
| G-28 | Floodplain Management Ordinance | tier1/G-29-raw-text.txt* | 70K | Raw text (file naming offset) |
| G-23 | ADU Dwelling Units per Ordinances | tier2/G-series/G-24.txt* | 22.7K | Raw text - rich ADU rules |
| G-13 | Fee Calculation / Cost Schedule | tier1/G-13-raw-text.txt | 5.7K | OCR'd — needs structuring into fee lookup table |
| otc-criteria | Projects Eligible for OTC Permit | tier1/otc-criteria.json | 10.5K | Structured - 12 no-plan + 24 with-plan + 19 not-OTC project types |
| completeness | Residential Pre-Plan Check Checklist | tier1/completeness-checklist.json | 8.2K | Structured - 13 sections, 11 review departments |
| planning-code | Planning Code Key Sections | tier1/planning-code-key-sections.json | 36K | Structured - 6 major sections (Section 311, CU, variances, historic, CEQA, exemptions) |
| consultants | SF Permit Consultant Registry | tier1/permit-consultants-registry.json | 115K | Structured - 167 filings, 115 consultants, Amy Lee profile, DBI expediter rankings |

*Note: File naming has systematic offset from sf.gov index page. See document-mapping.json for correct mapping.

## Tier 2: Information Sheets (Raw Text)

### G-Series (General)
| File Label | Actual Doc | Subject | Chars | Status |
|-----------|-----------|---------|-------|--------|
| G-01 | (unknown) | Scanned image | 0 | Needs OCR |
| G-02 | G-01 | Signature on Plans | 11K | Extracted |
| G-04 | G-02 | Plan Review Procedures | 28K | Extracted - OTC, parallel, premium review rules |
| G-05 | G-04 | Signs | 4.4K | Extracted |
| G-07 | (unknown) | Scanned image | 0 | Needs OCR |
| G-09 | (unknown) | Scanned image | 46 | Nearly empty |
| G-12 | (unknown) | Scanned image | 0 | Needs OCR (12 pages!) |
| G-14 | (unknown) | Scanned image | 0 | Needs OCR |
| G-15 | G-14 | Various Ordinances and Resolutions | 25K | Extracted |
| G-17 | (unknown) | Scanned image | 0 | Needs OCR |
| G-19 | G-17 | Legalization of Dwelling Units | 30K | Extracted - dwelling unit legalization rules |
| G-21 | G-19 | (General) | 7.3K | Extracted |
| G-23 | (unknown) | Scanned image | 0 | Needs OCR |
| G-24 | G-23 | ADU per Ordinances 162-16, 95-17, 162-17 | 22.7K | Extracted - comprehensive ADU rules |
| G-26 | G-25 | Restaurant Permitting FAQ | 6.5K | Extracted |
| G-28 | G-27 | Condo Unit Required Permits | 1.9K | Extracted |

### DA-Series (Disabled Access)
| File Label | Actual Doc | Subject | Chars | Status |
|-----------|-----------|---------|-------|--------|
| DA-03 | TBD | (Disabled Access) | 35.6K | Extracted |
| DA-04 | TBD | Scanned image | 0 | Needs OCR (10 pages) |
| DA-05 | TBD | (Disabled Access) | 6.2K | Extracted |
| DA-07 | TBD | (Disabled Access) | 7K | Extracted |
| DA-09 | TBD | Scanned image | 0 | Needs OCR |
| DA-10 | TBD | (Disabled Access) | 3.6K | Extracted |
| DA-11 | TBD | (Disabled Access) | 4.3K | Extracted |
| DA-12 | TBD | Scanned image | 0 | Needs OCR (7 pages) |
| DA-13 | TBD | (Disabled Access) | 12.2K | Extracted |
| DA-14 | TBD | Scanned image | 0 | Needs OCR |
| DA-15 | TBD | Scanned image | 0 | Needs OCR |
| DA-16 | TBD | (Disabled Access) | 9.1K | Extracted |
| DA-19 | TBD | Scanned image | 0 | Needs OCR |

### FS-Series (Fire/Sprinkler)
| File Label | Actual Doc | Subject | Chars | Status |
|-----------|-----------|---------|-------|--------|
| FS-01 | DA-19 | Stoops (mislabeled) | 5.1K | Extracted but wrong series |
| FS-03 | TBD | (Fire/Sprinkler) | 5K | Extracted |
| FS-04 | TBD | Scanned image | 0 | Needs OCR |
| FS-05 | TBD | Scanned image | 0 | Needs OCR (20 pages!) |
| FS-06 | TBD | (Fire/Sprinkler) | 3.6K | Extracted |
| FS-07 | TBD | Scanned image | 0 | Needs OCR |
| FS-12 | TBD | Scanned image | 0 | Needs OCR |
| FS-13 | TBD | Scanned image | 0 | Needs OCR |

### S-Series (Structural)
| File Label | Actual Doc | Subject | Chars | Status |
|-----------|-----------|---------|-------|--------|
| S-03 | TBD | (Structural) | 33.9K | Extracted |
| S-04 | TBD | Scanned image | 0 | Needs OCR |
| S-05 | TBD | (Structural) | 7.7K | Extracted |
| S-07 | S-04 | Demolition Permits | 13K | Extracted |
| S-09 | TBD | Scanned image | 0 | Needs OCR |
| S-10 | TBD | (Structural) | 4.1K | Extracted |
| S-11 | S-10 | Balconies, Decks, Projections | 3K | Extracted |
| S-12 | S-11 | Private School Earthquake Evaluation | 3.3K | Extracted |
| S-14 | S-12 | Cross-Laminated Timber | 3.4K | Extracted |
| S-17 | TBD | (Structural) | 21.7K | Extracted |

## Tier 3: Administrative Bulletins (from amlegal.com)

| AB Number | Subject | File | Chars | Status |
|-----------|---------|------|-------|--------|
| AB-004 | Priority Permit Processing Guidelines | tier3/AB-004.txt | 29K | ✅ Cleaned (also contains AB-001) |
| AB-005 | Procedures for Approval of Local Equivalencies | tier3/AB-005.txt | 31K | ✅ Cleaned (contains AB-004+AB-005) |
| AB-032 | Site Permit Processing | tier3/AB-032.txt | 48K | ✅ Cleaned (contains AB-028+AB-032) |
| AB-093 | Implementation of Green Building Regulations | tier3/AB-093.txt | 30K | ✅ Recovered — manually downloaded by Tim from amlegal.com |
| AB-110 | Building Facade Inspection and Maintenance | tier3/AB-110.txt | 28K | ✅ Recovered — extracted from SF Planning Code (lines 209124-209537) |
| AB-112 | All-Electric New Construction Regulations | tier3/AB-112.txt | 35K | ✅ Recovered — extracted from SF Planning Code (lines 210348-210867) |

## Web Pages Scraped (via Playwright / WebFetch)

| URL | Content | File |
|-----|---------|------|
| sf.gov/step-by-step--get-building-permit-house-review | In-House Review process | /tmp/sf-gov-inhouse-review.txt |
| sf.gov/resource--2022--building-permit-application-forms | Permit forms | /tmp/sf-gov-permit-forms.txt |
| sf.gov/resource/2022/information-sheets-dbi | Info sheets index | /tmp/sf-gov-info-sheets-index.txt |
| sf.gov/information--projects-eligible-over-counter-otc-permit | OTC eligibility criteria | tier1/otc-criteria.json |
| sf.gov/.../Residential%20Pre-Plan%20Check%20Checklist.pdf | Completeness review checklist | tier1/completeness-checklist.json |

## Tier 4: Planning Department

| Source | File | Size | Status |
|--------|------|------|--------|
| SF Planning Code (complete) | tier4/sf-planning-code-full.txt | 12.6MB (222K lines) | ✅ Downloaded from amlegal.com — needs indexing/parsing |

## Derived Outputs

| File | Description | Size | Status |
|------|-------------|------|--------|
| decision-tree-draft.json | 7-step decision tree mapping projects to permit requirements | 38K | ✅ Complete (updated with OTC criteria) |
| document-mapping.json | Correct file-to-document-ID mapping (31 mapped, 21 unmapped) | 13K | ✅ Complete |
| GAPS.md | Knowledge gaps analysis with 15 Amy interview questions | 8K | ✅ Complete (GAP-1 + GAP-5 resolved) |
| SOURCES.md | This file | - | ✅ Complete |
| INGESTION_LOG.md | Chronological ingestion log | 3K | ✅ Complete |

## Statistics

- **Total PDFs downloaded**: 51 of 52 info sheets (DA-02 failed - WAF challenge)
- **PDFs with extracted text**: 51 (31 via pdfplumber + 20 via OCR)
- **OCR'd PDFs**: 20 (183,696 chars from 85 pages via pytesseract)
- **Administrative Bulletins**: 6 committed (AB-004, AB-005, AB-032, AB-093, AB-110, AB-112 = ~201K chars)
- **Structured JSON files**: 10 (G-20 routing, permit forms, in-house process, decision tree, OTC criteria, completeness checklist, planning code key sections, permit consultant registry, document mapping, G-20 tables)
- **Web pages scraped**: 5 (3 via Playwright + 2 via WebFetch)
- **Planning Code**: 12.6MB (222K lines) from amlegal.com
- **Permit Consultant Registry**: 167 filings from SF Ethics Commission (SODA API umwe-sn9p)
- **DBI Expediter Rankings**: Top 50 by permit volume (SODA API 3pee-9qhc)
- **Total knowledge base size**: ~700K characters raw text + ~360K structured JSON + 12.6MB Planning Code
