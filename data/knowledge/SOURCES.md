# Knowledge Source Index
## SF Permitting Knowledge Base - Phase 2.5

Last updated: 2026-02-17

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
| consultants | SF Permit Consultant Registry | tier1/permit-consultants-registry.json | 115K | Structured - 167 filings, 115 consultants, Amy Lee profile, DBI consultant rankings |
| fee-tables | Building Permit Fee Tables (1A-A through 1A-S) | tier1/fee-tables.json | 54K | Structured - 19 tables (14 active, 5 reserved), 10 valuation tiers, 9-step fee algorithm |
| ab-index | Administrative Bulletins Complete Index | tier1/administrative-bulletins-index.json | 35K | Structured - 47 ABs indexed with titles, line ranges, relevance, subject areas |
| fire-code | Fire Code Key Sections | tier1/fire-code-key-sections.json | 37K | Structured - 13 SFFD triggers, sprinkler/alarm rules, assembly thresholds, high-rise reqs |
| fire-safety-info-sheets | DBI FS-Series Fire Safety Info Sheets | tier1/fire-safety-info-sheets.json | ~30K | Structured - 7 info sheets (FS-01/03/04/05/06/07/12), sprinkler rules, deck fire, PFP, ADU exemption |
| semantic-index | Semantic Concept-to-Source Mapping | tier1/semantic-index.json | ~90K | Structured - 86 concepts, ~817 aliases, cross-cutting search layer, 10/10 stress test |
| commercial-checklist | Commercial TI Permit Submission Checklist | tier1/commercial-completeness-checklist.json | ~12K | Structured - forms, plan set requirements, agency routing triggers, 8 common rejection reasons |
| school-impact-fees | SFUSD School Impact Fee Schedule | tier1/school-impact-fees.json | ~8K | Structured - fee rates, exemptions, calculation method, payment process (GAP-11 resolved) |
| special-inspections | Special Inspection Requirements | tier1/special-inspection-requirements.json | ~14K | Structured - 9 inspection types, certifications, SSI form, SF-specific requirements (GAP-13 resolved) |

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

**Structured**: `tier1/fire-safety-info-sheets.json` — 7 info sheets encoded (Session 27)

| File Label | Actual Doc | Subject | Status |
|-----------|-----------|---------|--------|
| FS-01 | DA-19 | Stoops (mislabeled — wrong series) | ❌ Skip |
| FS-03 | **FS-01** | Combustible Roof Decks — Materials & Area | ✅ Structured |
| FS-04 | **FS-03** | R-3 4-Story Sprinkler (addition vs alteration) | ✅ Structured |
| FS-05 | **FS-04** | Wood-Frame Construction Fire Safety (PFP) | ✅ Structured |
| FS-06 | **FS-05** | Dwelling Unit Sprinkler (R3→R2, in-law) | ✅ Structured |
| FS-07 | **FS-06** | Deck/Stairway Fire Protection at Property Lines | ✅ Structured |
| FS-12 | **FS-07** | Elevator Lobbies in High-Rise Buildings | ✅ Structured |
| FS-13 | **FS-12** | ADU Fire Safety — Sprinkler & Unit Separation | ✅ Structured |

*Note: Filenames are systematically shifted by one position from OCR batch. Actual FS numbers verified from document headers.*

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

## Tier 4: Building Codes and Planning Code

| Source | File | Size | Status |
|--------|------|------|--------|
| SF Planning Code (complete) | tier4/sf-planning-code-full.txt | 12.6MB (222K lines) | ✅ Downloaded from amlegal.com — key sections parsed to tier1 |
| SF BICC + Fire Code (complete) | tier4/sf-bicc-fire-codes-full.txt | 3.6MB (57,938 lines) | ✅ Downloaded from amlegal.com — fee tables, AB index, fire code extracted to tier1 |
| 2025 SF Building Code Amendments | tier4/sf-2025-building-code-amendments.txt | 506KB (7,758 lines) | ✅ Downloaded from sf.gov — 160 pages, operative Jan 1 2026 |
| 2025 SF Existing Building Code Amendments | tier4/sf-2025-existing-building-code-amendments.txt | 205KB (3,114 lines) | ✅ Downloaded from sf.gov — 71 pages |
| 2025 SF Electrical Code Amendments | tier4/sf-2025-electrical-code-amendments.txt | 55KB (855 lines) | ✅ Downloaded from sf.gov — 20 pages |
| 2025 SF Green Building Code Amendments | tier4/sf-2025-green-building-code-amendments.txt | 48KB (880 lines) | ✅ Downloaded from sf.gov — 19 pages |
| 2025 SF Plumbing Code Amendments | tier4/sf-2025-plumbing-code-amendments.txt | 42KB (775 lines) | ✅ Downloaded from sf.gov — 18 pages |
| 2025 SF Mechanical Code Amendments | tier4/sf-2025-mechanical-code-amendments.txt | 18KB (348 lines) | ✅ Downloaded from sf.gov — 9 pages |

## Derived Outputs

| File | Description | Size | Status |
|------|-------------|------|--------|
| decision-tree-draft.json | 7-step decision tree mapping projects to permit requirements | 38K | ✅ Complete (updated with OTC criteria) |
| document-mapping.json | Correct file-to-document-ID mapping (31 mapped, 21 unmapped) | 13K | ✅ Complete |
| GAPS.md | Knowledge gaps analysis with 15 Amy interview questions | 8K | ✅ Complete (GAP-1 + GAP-5 resolved) |
| SOURCES.md | This file | - | ✅ Complete |
| INGESTION_LOG.md | Chronological ingestion log | 6K | ✅ Complete |
| stress_test_semantic_index.py | 10-scenario semantic index stress test | 8K | ✅ 10/10 perfect (100% concept + file recall) |

## Statistics

- **Total PDFs downloaded**: 51 of 52 info sheets (DA-02 failed - WAF challenge)
- **PDFs with extracted text**: 51 (31 via pdfplumber + 20 via OCR)
- **OCR'd PDFs**: 20 (183,696 chars from 85 pages via pytesseract)
- **Administrative Bulletins**: 47 indexed in BICC (11,344 lines full text) + 6 individual tier3 files (~201K chars)
- **Fee Tables**: 19 tables (1A-A through 1A-S), 14 active, 5 reserved — 54K structured JSON
- **Fire Code**: 13 SFFD triggers, sprinkler/alarm rules, assembly thresholds — 37K structured JSON
- **Structured JSON files**: 15 (G-20 routing, permit forms, in-house process, decision tree, OTC criteria, completeness checklist, planning code key sections, permit consultant registry, document mapping, G-20 tables, fee tables, AB index, fire code, semantic index, Amy portfolio data)
- **Semantic Index**: 61 concepts, ~500 aliases, cross-cutting search layer — 75K structured JSON
- **Web pages scraped**: 5 (3 via Playwright + 2 via WebFetch)
- **Planning Code**: 12.6MB (222K lines) from amlegal.com
- **BICC + Fire Code**: 3.6MB (57,938 lines) from amlegal.com
- **Permit Consultant Registry**: 167 filings from SF Ethics Commission (SODA API umwe-sn9p)
- **DBI Consultant Rankings**: Top 50 by permit volume (SODA API 3pee-9qhc)
- **Total knowledge base size**: ~1.1MB raw text + ~560K structured JSON + 16.2MB code corpus (Planning + BICC/Fire)
