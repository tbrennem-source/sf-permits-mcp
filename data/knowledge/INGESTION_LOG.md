# Ingestion Log
## SF Permitting Knowledge Base - Phase 2.5

### 2026-02-13 Session 1: Initial Scraping and Structuring

#### 11:55 - G-20 PDF Extraction
- Downloaded G-20 from `https://media.api.sf.gov/documents/INFORMATION_SHEET_G-20_8-29-2025.pdf`
- Extracted via pdfplumber: 34 pages, 46,371 chars, 26 tables
- Created: tier1/G-20-raw-text.txt, tier1/G-20-tables.json

#### 12:00 - sf.gov Web Scraping (Playwright)
- sf.gov pages are JS-rendered (React) - curl/urllib return 0 bytes
- Installed playwright + chromium for headless browser scraping
- Scraped 3 pages: permit-forms (9K), inhouse-review (20K), info-sheets-index (8.5K)

#### 12:01 - G-20 Structuring
- Parsed G-20 into structured JSON: 154 routing matrix entries, 14 discussion rules
- Mapped 9 agencies with symbol legend (X, #, *, ^, //, +, O)
- Created: tier1/G-20-routing.json (133K)

#### 12:02 - Permit Forms Structuring
- Parsed sf.gov permit forms page into taxonomy JSON
- 7 main forms (Form 1-8), special applications, green building (GS1-6), disabled access
- Created: tier1/permit-forms-taxonomy.json (4.8K)

#### 12:03 - In-House Review Structuring
- Parsed sf.gov in-house review page into process JSON
- 11 steps with all pre-application requirements and agency triggers
- Created: tier1/inhouse-review-process.json (10.2K)

#### 12:04 - Info Sheet PDF Link Extraction
- Found 91 PDF links from sf.gov info-sheets index page using Playwright
- Categorized into G-series, FS-series, DA-series, S-series

#### 12:05-12:07 - Batch PDF Download
- Downloaded 51 of 52 info sheet PDFs (DA-02 failed - WAF challenge)
- Extracted text via pdfplumber: 31 with text (403K chars), 20 scanned images (0 chars)
- Priority tier1 docs: G-25 (10.7K), G-27 (5.9K), G-29 (69.6K) extracted; G-13 scanned (0 chars)
- Created: tier2/{G,FS,DA,S}-series/*.txt, tier2/download_results.json

### 2026-02-13 Session 2: Analysis and Decision Tree

#### ~12:08 - File Naming Discovery
- Discovered systematic off-by-one naming error in downloaded files
- sf.gov index page PDF URLs don't match actual document numbers
- Example: file "G-25" contains G-24 (MOU procedures), not G-25 (restaurant)
- Launched file mapping agent to create correct document-mapping.json

#### ~12:08 - Decision Tree Construction
- Launched agent to build 7-step decision tree from structured data
- Steps: need_permit → which_form → otc_or_inhouse → agency_routing → required_docs → timeline → fees

#### ~12:08 - Administrative Bulletins Scraping
- Launched agent to find and download priority ABs (AB-004, AB-005, AB-032, AB-093, AB-110, AB-112)
- Searching sf.gov and amlegal.com for PDF URLs

#### ~12:10 - Gaps Analysis
- Created GAPS.md with 14 identified gaps
- Priority gaps: OTC criteria (GAP-1), fee schedule (GAP-2), timelines (GAP-3)
- 15 refined Amy interview questions organized by category
- Created SOURCES.md index and INGESTION_LOG.md

### 2026-02-13 Session 3: Decision Tree, AB Completion, Final Cleanup

#### ~15:29 - Administrative Bulletins Downloaded
- All 6 priority ABs downloaded from amlegal.com via Playwright
- AB-004 (Priority Processing, 29K), AB-005 (Local Equivalencies, 31K), AB-032 (Site Permits, 48K)
- AB-093 (Green Building Regulations, 73K) — NOT OTC criteria as originally expected
- AB-110 (Facade Inspection, 99K), AB-112 (All-Electric New Construction, 116K) — NOT completeness review as expected
- Created: tier3/AB-{004,005,032,093,110,112}.txt, tier3/download_results.json

#### ~17:03 - AB Text Files Cleaned
- Stripped amlegal.com navigation boilerplate and footers from AB-004, AB-005, AB-032
- AB-004.txt: 439→274 lines (contains AB-001 + AB-004)
- AB-005.txt: 443→278 lines (contains AB-004 + AB-005)
- AB-032.txt: 559→394 lines (contains AB-028 + AB-032)
- AB-093, AB-110, AB-112 still have boilerplate (large files, cleaning in progress)

#### ~18:33 - Decision Tree Completed
- Built comprehensive 7-step decision tree JSON (33.1K)
- Synthesized from: G-20 routing (154 entries), permit forms taxonomy, in-house review process
- 7 steps: need_permit → which_form → otc_or_inhouse → agency_routing → required_docs → timeline → fees
- 6 special project types: restaurant, ADU, seismic, commercial TI, adaptive reuse, solar/clean energy
- 11 pre-application checklist items
- 5 known gaps documented within the tree
- Created: decision-tree-draft.json

#### ~18:33 - File Mapping Completed
- document-mapping.json created: 31 files mapped to actual doc IDs, 21 unmapped (scanned PDFs)
- Key discovery: G-29 (Adaptive Reuse, 34K chars) found in tier2/S-series/S-03.txt
- Tier1 files renamed: G-25→G-24, G-27→G-26, G-29→G-28

#### ~18:35 - Index Files Updated
- GAPS.md: Updated with corrected AB-093/AB-112 subjects, resolved GAP-7/8/9
- SOURCES.md: Updated with all AB downloads, decision tree, final statistics
- INGESTION_LOG.md: Updated with Session 3 activities

---

## Session 4: OTC Criteria + Completeness + Planning Code (2026-02-13, ~21:00)

#### ~21:00 - OTC Criteria Found and Structured
- Definitive OTC eligibility list found at sf.gov/information--projects-eligible-over-counter-otc-permit
- 12 project types: OTC without plans
- 24 project types: OTC with plans
- 19 project types: NOT OTC (requires In-House Review)
- Key routing criterion: "one-hour rule" (if plan review can't be done in ~1hr per station, goes to in-house)
- Created: tier1/otc-criteria.json
- **GAP-1 RESOLVED** — OTC criteria are a web page, NOT an Administrative Bulletin

#### ~21:00 - Completeness Review Checklist Found and Structured
- 4-page residential pre-plan check checklist PDF found at sf.gov
- 13 sections covering application, scope, routing (11 departments), supporting docs, plans
- Created: tier1/completeness-checklist.json
- **GAP-5 RESOLVED** — Completeness checklist is a PDF, NOT an Administrative Bulletin

#### ~21:00 - Decision Tree Updated
- Step 3 (otc_or_inhouse) replaced with complete OTC criteria (was weakest link)
- 55 project type classifications now in decision tree
- Known gaps list updated (GAP-1 and GAP-5 resolved, GAP-4 partially resolved)
- decision-tree-draft.json updated and validated

#### ~21:00 - SF Planning Code Ingested
- Complete SF Planning Code downloaded from amlegal.com (12.6MB, 222K lines)
- Saved to: tier4/sf-planning-code-full.txt
- Contains 17 OTC references, 73 completeness/plan-check references, 180 facilitator/expediter references
- Needs indexing/parsing for structured extraction
- **GAP-4 PARTIALLY RESOLVED** — raw text available, needs structuring

#### ~21:00 - SF Permit Consultant Registry Discovered
- SF Ethics Commission dataset: umwe-sn9p (~200 registered permit consultants)
- Amy Lee found: "Eun Young (Amy) Lee", firm "3S LLC", registered Oct 2019
- 40 permits as "pmt consultant/expediter" in DBI contacts dataset (3pee-9qhc)
- Former Acting Director of SF DBI (~2005)
- New potential data source for djarvis user base

### Session 5: OCR + Planning Code Parsing + Consultant Registry (2026-02-14, overnight)

#### ~05:00 - OCR All 20 Scanned PDFs (Task A) ✅
- Installed tesseract + pytesseract + pdf2image + poppler
- Built scripts/ocr_pdfs.py
- All 20 PDFs OCR'd successfully: 183,696 chars from 85 pages
- Key results: G-12 (31K, 12p), FS-05 (38K, 20p), DA-04 (28K, 10p), DA-12 (18K, 7p), S-09 (9.3K, 4p)
- G-13 fee schedule OCR'd: 5,703 chars — needs structuring
- Committed as 44dee7f
- **GAP-6 RESOLVED**

#### ~05:24 - Permit Consultant Registry Ingested (Task E) ✅
- Fetched 167 records from SF Ethics Commission (SODA API: umwe-sn9p)
- 115 unique consultant names; top firms: Reuben Junius & Rose (29), Lighthouse Public Affairs (23)
- Amy Lee profile: Eun Young (Amy) Lee, 3S LLC, rank #42 with 117 DBI permits
- 3S LLC team: Jerry Sanguinetti, Mark Luellen, Michie Wong, Simon Tam
- Top expediter: Danielle Romero (1,702 permits)
- Created: tier1/permit-consultants-registry.json (115K)

#### ~05:27 - Planning Code Key Sections Parsed (Task B) ✅
- Extracted 6 major sections from 222K-line Planning Code into structured JSON
- Section 311/312 (neighborhood notification), Section 303 (conditional use), Sections 305/309/329 (variances/review)
- Zoning exemptions, historic preservation (Articles 10/11), CEQA environmental review
- Review pathway summary: 6 pathways with conditions for each
- Created: tier1/planning-code-key-sections.json (36K)
- **GAP-4 RESOLVED** (was partially resolved, now fully structured)

### Known Issues (Updated)
1. **20 scanned image PDFs**: ✅ RESOLVED — All OCR'd successfully (183K chars, 85 pages)
2. **File naming offset**: ✅ RESOLVED — document-mapping.json created, tier1 files renamed
3. **DA-02 download failed**: AWS WAF blocked the PDF download
4. **FS-01 mislabeled**: Contains DA-19 content (wrong series entirely)
5. **G-29 found**: ✅ RESOLVED — Located in tier2/S-series/S-03.txt (34K chars)
6. **OTC criteria**: ✅ RESOLVED — sf.gov web page, not an AB
7. **Completeness checklist**: ✅ RESOLVED — sf.gov PDF, not an AB
8. **AB files contain multiple ABs**: amlegal.com pages show sequential ABs. Each file may contain 2-4 ABs.
9. **AB-093, AB-110, AB-112**: ✅ RESOLVED — All 3 recovered (AB-093 manual download, AB-110/112 from Planning Code)
10. **SF Planning Code parsing**: ✅ RESOLVED — Key sections extracted to tier1/planning-code-key-sections.json
