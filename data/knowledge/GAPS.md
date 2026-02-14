# Knowledge Gaps Analysis
## SF Permitting Knowledge Base - Phase 2.5

Last updated: 2026-02-13

## Critical Gaps (Block Decision Tree Accuracy)

### GAP-1: OTC vs In-House Review Criteria
**Impact**: Step 3 of decision tree (otc_or_inhouse) has weak rules
**What we know**: Form 8 = OTC, Form 3 = In-House. G-20 "Work with No Plans" category lists 12 OTC-eligible scope-of-work types. G-02 mentions OTC conversion procedures.
**What we need**: Complete list of project types eligible for OTC review. **AB-093 turned out to be "Green Building Regulations" — NOT OTC criteria.** The OTC criteria AB number is unknown or may not exist as a standalone AB.
**Source needed**: G-02 Section P (Form 8 conversion), possible DBI internal OTC criteria document
**Ask Amy**: "What are the most common project types that qualify for OTC review? What disqualifies a project? Is there an official OTC criteria document?"

### GAP-2: Fee Calculation Schedule (G-13)
**Impact**: Step 7 of decision tree (fees) has no concrete data
**What we know**: G-13 is the DBI Cost Schedule. It was downloaded but is a scanned image PDF (0 chars extracted).
**What we need**: Fee table data - base fees, multipliers, fee categories by project type
**Source needed**: G-13 PDF (needs OCR), or fee tables from sf.gov/sfdbi.org
**Ask Amy**: "How do you currently calculate fees for clients? What's the typical fee range for common project types?"

### GAP-3: Timeline Estimates by Project Type
**Impact**: Step 6 of decision tree (timeline) relies on sparse data
**What we know**: In-house review is ~4 weeks after filing fee paid. Priority permits per AB-004 have expedited timelines.
**What we need**: Realistic timeline ranges for common project types (OTC, small residential, commercial TI, new construction)
**Source needed**: AB-004 (Priority Permit Processing), DBI's published processing time metrics
**Ask Amy**: "What are realistic timeline expectations you set for clients by project type? What causes delays?"

### GAP-4: Planning Department Pre-Approval Rules
**Impact**: Step 1 of decision tree (need_permit) and Step 4 (agency_routing)
**What we know**: G-20 routes many project types to Planning. Zoning approval needed before building permit.
**What we need**: Which projects DON'T need Planning review (exemptions), conditional use permit criteria
**Source needed**: Planning Department's own approval criteria, sf.gov Planning approval page
**Ask Amy**: "What percentage of your projects need Planning review? What types typically skip it?"

### GAP-5: Completeness Review Checklist Details
**Impact**: Step 5 (required_docs) - we know the categories but not the specific checklist items
**What we know**: DBI does completeness review in Step 9. Three rounds = escalation to supervisor.
**What we need**: The actual checklist DBI staff use. **AB-112 turned out to be "All-Electric New Construction Regulations" — NOT completeness review.** The completeness review AB number is unknown.
**Source needed**: DBI's internal completeness checklist, possible AB or other internal document
**Ask Amy**: "What are the most common reasons applications get rejected for incompleteness? Is there an official completeness review checklist?"

## Significant Gaps (Reduce Decision Tree Quality)

### GAP-6: Scanned/Image PDFs (20 documents)
**Impact**: 20 out of 51 info sheet PDFs extracted 0 characters (scanned images)
**Affected documents**: G-01, G-07, G-12, G-13, G-14, G-17, G-23, DA-04, DA-09, DA-12, DA-14, DA-15, DA-19, FS-04, FS-05, FS-07, FS-12, FS-13, S-04, S-09
**Resolution**: OCR processing (pytesseract or cloud OCR), or find text versions on sf.gov
**Priority**: G-13 (fees) is critical, G-12 (unknown topic), FS-05 (20 pages, likely substantial)

### GAP-7: File ID Mismatch — RESOLVED
**Impact**: Downloaded PDFs have off-by-one naming errors from sf.gov index page
**What happened**: sf.gov's info-sheets index page PDF links are numbered differently from actual document numbers
**Example**: File labeled "G-25" actually contains G-24 (MOU procedures)
**Resolution**: ✅ Document mapping created (document-mapping.json). Tier 1 files renamed. G-29 (Adaptive Reuse) found in S-03.txt.

### GAP-8: Administrative Bulletins — MOSTLY RESOLVED
**Impact**: ABs define key procedures referenced throughout info sheets
**Status**: ✅ 6 ABs downloaded from amlegal.com and cleaned:
- AB-004: Priority Permit Processing Guidelines (29K)
- AB-005: Procedures for Approval of Local Equivalencies (31K) — contains AB-004+AB-005
- AB-032: Site Permit Processing (48K) — contains AB-028+AB-032
- AB-093: Implementation of Green Building Regulations (73K) — NOT OTC criteria as hoped
- AB-110: Building Facade Inspection and Maintenance (99K)
- AB-112: Implementation of All-Electric New Construction Regulations (116K) — NOT completeness review as hoped
**Remaining gap**: OTC criteria AB and completeness review AB not identified

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

### GAP-11: School Impact Fees Details
**What we know**: SFUSD fees are calculated by DBI based on building permit application data
**What we need**: Current fee rates per sq ft, exemptions
**Source**: G-11 (School Impaction Fee) - not yet downloaded

### GAP-12: Green Building Requirements Detail
**What we know**: GS1-GS6 forms exist. Title 24 energy compliance required.
**What we need**: Decision logic for which GS form applies to which project type
**Source**: M-03, M-04, M-06, M-08 info sheets (not downloaded)

### GAP-13: Special Inspection Requirements Detail
**What we know**: Structural work often requires special inspections
**What we need**: Which project types require which special inspections
**Source**: AB-046, S-series structural info sheets

### GAP-14: Permit Expiration and Renewal Rules
**What we know**: Permits can expire. Renewals route through G-20.
**What we need**: Expiration timelines, renewal process, fee implications

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
