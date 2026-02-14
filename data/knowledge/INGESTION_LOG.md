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

### Known Issues (Updated)
1. **20 scanned image PDFs**: Need OCR (pytesseract or cloud) to extract text
2. **File naming offset**: ✅ RESOLVED — document-mapping.json created, tier1 files renamed
3. **DA-02 download failed**: AWS WAF blocked the PDF download
4. **FS-01 mislabeled**: Contains DA-19 content (wrong series entirely)
5. **G-29 found**: ✅ RESOLVED — Located in tier2/S-series/S-03.txt (34K chars)
6. **AB-093 is NOT OTC criteria**: It's "Green Building Regulations". OTC criteria AB number unknown.
7. **AB-112 is NOT completeness review**: It's "All-Electric New Construction". Completeness review AB unknown.
8. **AB files contain multiple ABs**: amlegal.com pages show sequential ABs. Each file may contain 2-4 ABs.
9. **AB-093, AB-110, AB-112 still have nav boilerplate**: Need cleanup pass (73K-116K files).
