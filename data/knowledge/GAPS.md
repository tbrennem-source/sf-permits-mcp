# Knowledge Gaps Analysis
## SF Permitting Knowledge Base - Phase 2.5

Last updated: 2026-02-16

## Critical Gaps (Block Decision Tree Accuracy)

### GAP-1: OTC vs In-House Review Criteria — ✅ RESOLVED
**Impact**: Step 3 of decision tree (otc_or_inhouse) — was weakest link, now fully populated
**Resolution**: Found definitive source at sf.gov/information--projects-eligible-over-counter-otc-permit
- 12 project types: OTC without plans (re-roofing, in-kind kitchen/bath, etc.)
- 24 project types: OTC with plans (layout-changing remodels, new windows, commercial TI, etc.)
- 19 project types: NOT OTC / requires In-House Review (ADU, unit changes, hillside, excavation, etc.)
- Key routing criterion: the "one-hour rule" — if plan review can't be done in ~1hr, goes to in-house
- Saved as: tier1/otc-criteria.json
- Decision tree step 3 updated with complete criteria
**Note**: AB-093 was NOT the source — it's a web page, not an Administrative Bulletin. OTC criteria do not have an AB number.

### GAP-2: Fee Calculation Schedule — ✅ RESOLVED
**Impact**: Step 7 of decision tree (fees) — was missing concrete data, now fully populated
**Resolution**: All 19 fee tables (Tables 1A-A through 1A-S) extracted from BICC full text into structured JSON
- 10 valuation tiers from $1 to $200M+, 3 permit categories (new construction, alterations, no plans)
- Plumbing/mechanical fees (20 categories), electrical fees (5 categories with sub-tiers)
- Standard hourly rates: Plan Review $481/hr, Inspection $571/hr, Administration $298/hr
- Penalties: work without permit = 9x permit issuance fee + original
- 14 active tables + 5 reserved
- Saved as: tier1/fee-tables.json (54K)
- G-13 OCR'd text superseded by more complete/accurate BICC source
**Ask Amy**: "How do you currently calculate fees for clients? Do you use the published tables or rules of thumb?"

### GAP-3: Timeline Estimates by Project Type
**Impact**: Step 6 of decision tree (timeline) relies on sparse data
**What we know**: In-house review is ~4 weeks after filing fee paid. Priority permits per AB-004 have expedited timelines.
**What we need**: Realistic timeline ranges for common project types (OTC, small residential, commercial TI, new construction)
**Source needed**: AB-004 (Priority Permit Processing), DBI's published processing time metrics
**Ask Amy**: "What are realistic timeline expectations you set for clients by project type? What causes delays?"

### GAP-4: Planning Department Pre-Approval Rules — ✅ RESOLVED
**Impact**: Step 1 of decision tree (need_permit) and Step 4 (agency_routing)
**Resolution**: Planning Code parsed into 6 major structured sections (36K JSON):
- **Section 311/312 Neighborhood Notification**: 30-day notice thresholds, DR request process, exempt projects (ADUs, change-of-use to principally permitted in W.SoMa/C.SoMa/E.SoMa, vertical additions adding units)
- **Conditional Use Authorization**: Section 303 criteria, residential demolition (Section 317), formula retail triggers
- **Building Permit Review**: Section 305 variances, Section 309 C-3 district review, Section 329 large project authorization
- **Zoning District Exemptions**: Principally permitted uses, parking/loading exemptions, historic exemptions
- **Historic Preservation**: Article 10 (landmarks/districts) and Article 11 (downtown) review processes, Certificate of Appropriateness, demolition standards
- **CEQA Environmental Review**: When required (CU, variance, Section 309/329), categorical exemptions, timeline implications
- **Review Pathway Summary**: 6 pathways (OTC → Section 311 → CU → Section 309/329 → HPC → Variance) with conditions for each
- Saved as: tier1/planning-code-key-sections.json
**Ask Amy**: "What percentage of your projects need Planning review? What types typically skip it?"

### GAP-5: Completeness Review Checklist Details — ✅ RESOLVED
**Impact**: Step 5 (required_docs) — was missing specific checklist items, now fully populated
**Resolution**: Found definitive 4-page PDF: "Residential Pre-Plan Check Processing Checklist"
- URL: sf.gov/sites/default/files/2022-07/Residential%20Pre-Plan%20Check%20Checklist.pdf
- Linked from In-House Review step-by-step page (Step 7: Submit your application)
- 13 sections: application completeness, scope of work, valuation, dev review routing (11 depts), supporting docs, cover sheet, site plan, architectural plans, structural plans, green building, Title 24
- DBI caveat: "only a guide as required information may vary depending on scope of project"
- Saved as: tier1/completeness-checklist.json
**Note**: AB-112 was NOT the source — it's a PDF on sf.gov, not an Administrative Bulletin. Checklist does not have an AB number.
**Remaining gap**: This is residential only — no equivalent commercial checklist found yet.

## Significant Gaps (Reduce Decision Tree Quality)

### GAP-6: Scanned/Image PDFs (20 documents) — ✅ RESOLVED
**Impact**: 20 out of 51 info sheet PDFs extracted 0 characters (scanned images)
**Resolution**: All 20 PDFs OCR'd successfully using pytesseract + pdf2image + poppler
- Total: 183,696 characters from 85 pages, 20/20 success
- Key results: G-12 (31K, 12 pages), FS-05 (38K, 20 pages), DA-04 (28K, 10 pages), DA-12 (18K, 7 pages)
- G-13 OCR'd: 5,703 chars (fee schedule — needs structuring, see GAP-2)
- Script: scripts/ocr_pdfs.py
- OCR'd files committed to tier2/ directories

### GAP-7: File ID Mismatch — RESOLVED
**Impact**: Downloaded PDFs have off-by-one naming errors from sf.gov index page
**What happened**: sf.gov's info-sheets index page PDF links are numbered differently from actual document numbers
**Example**: File labeled "G-25" actually contains G-24 (MOU procedures)
**Resolution**: ✅ Document mapping created (document-mapping.json). Tier 1 files renamed. G-29 (Adaptive Reuse) found in S-03.txt.

### GAP-8: Administrative Bulletins — ✅ FULLY RESOLVED
**Impact**: ABs define key procedures referenced throughout info sheets
**Status**: ALL 47 Administrative Bulletins fully indexed from BICC full text (was only 6 before)
- Complete index with titles, subjects, line ranges, relevance classifications, subject areas
- 25 HIGH relevance, 18 MEDIUM, 4 LOW — 15 critical for permit routing
- 11,344 total lines of AB full text in the BICC source file
- Top subject areas: seismic (11), fire/life safety (8), accessibility (4), permit processing (4)
- Saved as: tier1/administrative-bulletins-index.json (35K)
- Tier 3 individual AB text files still available for detailed extraction
**Note**: OTC criteria and completeness review turned out to be sf.gov web pages, NOT ABs (see GAP-1 and GAP-5)

### GAP-9: Real G-29 (Adaptive Reuse) — RESOLVED
**Impact**: The spec listed G-29 as a priority Tier 1 source for adaptive reuse rules
**What happened**: File labeled G-29 actually contains G-28 (Floodplain Management)
**Resolution**: ✅ G-29 (Commercial-to-Residential Adaptive Reuse, 34K chars) FOUND in tier2/S-series/S-03.txt. Misplaced due to sf.gov index naming offset.

### GAP-10: Permit Revision / Amendment Process
**Impact**: Decision tree doesn't cover post-issuance changes
**What we know**: G-20 Rule F covers major changes on issued Site Permit. G-02 covers addenda schedules.
**What we need**: Complete rules for permit revisions, amendments, and renewals
**Ask Amy**: "How often do clients need to modify issued permits? What's the process?"

## Minor Gaps (Nice to Have)

### GAP-11: School Impact Fees Details — ✅ RESOLVED
**What we know**: SFUSD fees are calculated by DBI based on building permit application data
**What we need**: Current fee rates per sq ft, exemptions
**Source**: G-11 (School Impaction Fee) - not yet downloaded
**Resolution**: Structured JSON created from California Government Code Section 65995, SFUSD Board resolutions, and DBI guidelines:
- Residential rate: $4.79/sqft, Commercial: $0.78/sqft (2024 rates)
- Full exemptions: disaster replacement, 100% affordable, senior housing, government, religious
- Partial exemptions: remodel (no new area), ADU under 750 sqft
- 5-step calculation method with examples
- Saved as: tier1/school-impact-fees.json

### GAP-12: Green Building Requirements Detail — RESOLVED
**What we know**: GS1-GS6 forms exist. Title 24 energy compliance required.
**What we need**: Decision logic for which GS form applies to which project type
**Source**: M-03, M-04, M-06, M-08 info sheets (not downloaded)
**Resolution**: Full AB-093 (Implementation of Green Building Regulations) extracted from tier3/AB-093.txt into structured JSON:
- **GS Form Decision Logic**: 5-step decision tree mapping project type to GS-1 through GS-6
- **Rating System Requirements**: When LEED, GreenPoint Rated, or Locally Required Measures apply (by occupancy, size, new/alteration)
- **5 Compliance Methods**: LEED certification, GreenPoint Rated, standards-without-certification, equivalency, locally required measures only
- **Green Building Compliance Professional**: Qualifications (Architect/Engineer + specialization), exemption for small residential (< 25K sqft, <= 1K sqft addition)
- **Special Cases**: ADU (treated as addition, use GS-5), historic buildings, mixed occupancy, municipal LEED Gold, large commercial TI (>= 25K sqft)
- **Energy Compliance**: Title 24 Part 6 in green building context, AB-112 all-electric mandate (since June 2021)
- **9 Quick Reference Scenarios**: Common project types with form, rating system, and professional requirements
- **Verification**: Attachment E final compliance, TCO rules, quality assurance
- M-03/M-04/M-06/M-08 content already captured in tier1/title24-energy-compliance.json (no separate download needed)
- Saved as: tier1/green-building-requirements.json
- Semantic index updated with expanded green_building concept pointing to new file

### GAP-13: Special Inspection Requirements Detail — ✅ RESOLVED
**What we know**: Structural work often requires special inspections
**What we need**: Which project types require which special inspections
**Source**: AB-046, S-series structural info sheets
**Resolution**: Comprehensive structured JSON created from CBC Chapter 17, SFBICC Sections 1701-1706, and AB-046:
- 9 inspection types: structural steel, concrete, masonry, wood, soils/foundations, welding, fire-resistant materials, smoke control, seismic systems
- Each type: CBC section, activities requiring inspection, qualified inspector certifications, frequency, documentation
- Who can perform: ICC certifications, AWS CWI, ACI technicians, licensed GE
- Statement of Special Inspections (SSI) form requirements
- SF-specific: seismic retrofit, high-rise, historic buildings
- Saved as: tier1/special-inspection-requirements.json

### GAP-14: Permit Expiration and Renewal Rules — ✅ RESOLVED
**Impact**: Permit expiration was hardcoded as 180 days for all permits, but actual law uses valuation-tiered limits
**Resolution**: Full Section 106A.4.4 extracted from BICC tier4 (line 30963) into structured JSON:
- **Table A** (application expiration): $1-$1M = 360 days, Over $1M = 720 days
- **Table B** (work completion): $1-$100K = 360 days, $100K-$2.5M = 1,080 days, $2.5M+ = 1,440 days
- Demolition permits: 180 days (the ONLY permit type with this limit)
- Site permits $2.5M+ get 50% bonus time (2,160 days)
- Extension rules, suspension/toll provisions, expired permit recovery (106A.4.4.1, 106A.4.4.2)
- Fee refunds (107A.6), investigation fees for work without permit (107A.5)
- Code fix: `web/brief.py` `_validity_days()` now uses Table B lookup instead of hardcoded 180 days
- Code fix: `web/report.py` dormant/aging risk flags now use Table B tiers instead of arbitrary 2yr/3yr thresholds
- Saved as: tier1/permit-expiration-rules.json
- Also created 5 additional tier1 files from BICC audit: permit-requirements.json, inspections-process.json, certificates-occupancy.json, enforcement-process.json, appeals-bodies.json

## Amy Interview Questions (Refined)

Based on the gaps above, here are the priority questions for Amy:

### Process & Decision Questions
1. "Walk me through how you decide whether a project qualifies for OTC vs in-house review."
2. "What's your mental checklist when a new client describes their project? What questions do you ask first?"
3. "What are the top 5 reasons building permit applications get rejected or sent back?"
4. "How do you estimate timelines for clients? What's the range for a typical residential remodel vs commercial TI vs new construction?"

### Fee & Cost Questions
5. "How do you calculate/estimate permit fees for a client before they apply?"
6. "What unexpected fees catch clients off guard?"

### Agency Routing Questions
7. "Which agency reviews cause the most delays? Planning? Fire?"
8. "For what types of projects do you NOT need Planning review?"
9. "How does the OCII routing work in practice? How often do you deal with it?"

### Common Scenarios
10. "What are the 5 most common project types you help clients with?"
11. "What's the most confusing part of the process for first-time applicants?"
12. "Are there any 'gotchas' in the process that aren't well documented?"

### Validation Questions
13. "Can you validate this form selection logic: [show permit-forms-taxonomy.json]"
14. "Can you validate this agency routing for a kitchen remodel: [show G-20 routing for kitchen]"
15. "Is the 11-step in-house review process on sf.gov accurate and complete?"
