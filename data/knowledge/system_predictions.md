# System Predictions — Amy Stress Test

Generated: 2026-02-14
Tools: predict_permits, estimate_fees, estimate_timeline, required_documents, revision_risk
Source citations: Enabled (17-source registry with clickable links)

---


## Scenario A: Residential Kitchen Remodel (Noe Valley, $85K)

### Predicted Permits

# Permit Prediction

**Project:** Gut renovation of residential kitchen in Noe Valley, removing a non-bearing wall, relocating gas line, new electrical panel. Budget $85K.
**Estimated Cost:** $85,000

**Detected Project Types:** commercial_ti
**Matched Concepts:** commercial_ti

## Permit Form

**Form:** Form 3/8
**Reason:** Alterations/repairs to existing building
**Notes:** Mark Form 3 for in-house review, Form 8 for OTC-eligible projects

## Review Path

**Path:** likely_in_house
**Reason:** Scope likely exceeds OTC one-hour review threshold
**Confidence:** medium

## Agency Routing

- **DBI (Building)** (Required): All permitted work
- **DBI Mechanical/Electrical** (Required): HVAC, electrical, or commercial kitchen systems

## Special Requirements

- **ADA path-of-travel (20% rule):** Construction cost $85,000 below threshold $203,611 — accessibility upgrades limited to 20% ($17,000)
- **DA-02 Checklist required:** Disabled Access Upgrade Compliance Checklist Package required for all commercial alterations
- **Plan signature — verify G-01 Status I exempt or Status III required:** Non-highrise single-floor TI ≤$400,000 with non-structural scope may qualify for exempt status (G-01). Otherwise CA-licensed architect or engineer required.
- **Title-24 energy compliance (nonresidential alteration):** NRCC required if altering HVAC, lighting, or envelope. NRCI sub-forms at inspection per DBI M-04 checklist. NRCA acceptance testing for systems >54,000 BTU/hr (MCH-04-A economizer, LTI-02-A daylighting, etc.).
- **Title-24 Final Compliance Affidavit (M-06):** Prior to final inspection, email affidavit to dbi.energyinspections@sfgov.org. Must list all certificate form codes. Allow 10 business days for review. HERS items require certified HERS Rater; NRCA items require certified ATT.

## Confidence Summary

- overall: medium
- form_selection: high
- review_path: high
- agency_routing: high
- documents: high

## Gaps / Caveats

- No address provided — cannot check zoning, historic status, or neighborhood-specific rules

---
## Sources

- [DBI Decision Tree (7-step permit pathway)](https://sf.gov/departments/building-inspection/permits)
- [DBI OTC Permit Criteria (55 project type classifications)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Permit Forms Taxonomy](https://sf.gov/departments/building-inspection/permits)
- [DBI Info Sheet G-20: Routing Matrix](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheets DA-02, DA-12, DA-13 (CBC 11B Accessibility)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-01: Signature on Plans (4 status categories)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)](https://sf.gov/resource/2022/information-sheets-dbi)


### Estimated Fees

# Fee Estimate

**Construction Valuation:** $85,000
**Permit Category:** alterations

## DBI Building Permit Fees (Table 1A-A)

| Fee Component | Amount |
|--------------|--------|
| Plan Review Fee | $2,230.85 |
| Permit Issuance Fee | $757.80 |
| CBSC Fee | $3.40 |
| SMIP Fee | $11.05 |
| **Total DBI Fees** | **$3,003.10** |

*Fee tier: $50,001 to $200,000*

## Notes

- Fee schedule effective 9/1/2025 (Ord. 126-25)
- DBI may adjust valuation per DBI Cost Schedule
- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total
- Fees subject to periodic update — verify against current DBI schedule

**Confidence:** high

---
## Sources

- [DBI Fee Schedule G-13 (Tables 1A-A through 1A-S, eff. 9/1/2025)](https://sf.gov/resource/2022/information-sheets-dbi)


### Estimated Timeline

**ERROR:** Catalog Error: Table with name permits does not exist!
Did you mean "pg_settings"?

LINE 22:         FROM permits
                      ^

### Required Documents

# Required Documents Checklist

**Forms:** Form 3/8
**Review Path:** in_house
**Project Type:** general_alteration

## Initial Filing Documents

1. [ ] Building Permit Application (Form 3/8)
2. [ ] Construction plans (PDF for EPR)
3. [ ] Permit Applicant Disclosure and Certification form
4. [ ] Title 24 Energy compliance forms
5. [ ] San Francisco Green Building form (GS1-GS6)
6. [ ] Construction cost estimate worksheet

## Project-Specific Requirements

1. [ ] CF1R — Residential Certificate of Compliance (for alterations touching energy systems, per M-03)
2. [ ] Existing conditions documentation for Title-24 baseline (T24-C02 — #1 alteration correction)
3. [ ] Title-24 CEC Final Compliance Affidavit (M-06) — email to dbi.energyinspections@sfgov.org prior to final inspection
4. [ ] Plans may qualify for exempt status — unlicensed designer may sign if scope meets G-01 Status I conditions

## Electronic Plan Review (EPR) Requirements

*All plans must be submitted electronically as of January 1, 2024*

- Vector-based PDF required: CAD-produced vector lines, not scanned images. Non-compliant = rejection.
- TrueType/OpenType fonts: Searchable text required. SHX fonts need OCR post-processing.
- Single consolidated PDF: One PDF per document type. No individual sheet files.
- Full 1:1 scale: Print at 100% scale from authoring software.
- Minimum 22" x 34" sheets: ANSI D or Arch D minimum. Signage permits: 11x17. Supplements: 8.5x11.
- File size < 250MB: Per upload. Site permit addenda: 350MB limit.
- PDF unlocked: No encryption, passwords, or security restrictions.
- No digital certificate signatures: Use scanned graphic signatures. DocuSign/Adobe Sign certificates lock the PDF.
- Back Check page: DBI standardized Back Check page appended to plan set.

## Pre-Submission Checklist

- [ ] Vector-based lines (no scanned/raster drawings) [EPR-001]
- [ ] TrueType/OpenType fonts for searchable text [EPR-002]
- [ ] All sheets in single consolidated PDF [EPR-003]
- [ ] Full 1:1 scale output (not 'scale to fit') [EPR-004]
- [ ] Minimum sheet size 22" x 34" for drawings [EPR-005]
- [ ] File size under 250MB per upload [EPR-006]
- [ ] Bookmarks for each sheet (recommended) [EPR-007]
- [ ] PDF unlocked — no encryption or passwords [EPR-009]
- [ ] No certificate-type digital signatures [EPR-010]
- [ ] 8.5" x 11" blank area on cover sheet [EPR-012]
- [ ] Project address on every sheet [EPR-013]
- [ ] Sheet numbers on every sheet [EPR-014]
- [ ] Design professional signature/stamp on every sheet [EPR-018]
- [ ] Flatten PDF after adding graphic signatures [EPR-019]
- [ ] Back Check page appended [EPR-021]

## Plan Check Correction Response Workflow

*When corrections are required, follow this sequence:*

- **EPR-023:** Download marked-up plans from Bluebeam Studio session — Plan checker comments appear as Bluebeam markup annotations on specific sheets. Download the full annotated set to review all comments across all reviewers.
- **EPR-024:** Address ALL plan check comments — Every comment from every reviewing agency must be addressed. Use Bluebeam's markup reply feature to respond to each comment, or create a correction response letter referencing each comment by reviewer and sheet number.
- **EPR-025:** Add revision clouds on ALL changed items — Every change between submission rounds must be enclosed in a revision cloud. Include revision delta markers (triangle with revision number). Revision clouds must be on the drawing layer, not as Bluebeam annotations.
- **EPR-026:** Upload only changed sheets for corrections — For plan check corrections, upload only the sheets that were modified — not the entire plan set. Use the same file naming convention with incremented revision number. Full set re-upload is only for addenda (new scope).
- **EPR-027:** Update sheet index and page count — If sheets were added or removed, update the cover sheet's table of contents and total page count to match the revised set.
- **EPR-028:** Notify reviewer of resubmittal — After uploading corrected sheets, notify the reviewer through the Bluebeam Studio session or PermitSF portal. Do not assume reviewers are automatically notified of uploads.

**Corrections vs Addenda:**
- *Correction:* Response to plan check comments. Upload only changed sheets with revision clouds. Uses same application number and review session.
- *Addendum:* Additional scope added to an approved or in-review permit. Requires new document upload with full addenda set. Format: [Number Prefix]-[Document type]-[Revision Number] [Street address]_[Type/Count of Addenda]. File size limit for site permit addenda is 350MB (vs 250MB standard).

## Review Status Guide

- **Approved:** Plans meet all code requirements. No changes needed. → Proceed to fee payment and permit issuance.
- **Approved as Noted:** Plans are approved with minor notations. Changes may be required to be shown on job-site set but do not require resubmittal. → Review all notations. Incorporate notes into construction documents. Proceed to fee payment.
- **Corrections Required:** Plans have deficiencies that must be corrected and resubmitted for another review round. → Follow correction response workflow (EPR-023 through EPR-028). Upload corrected sheets with revision clouds.
- **Not Approved:** Plans have fundamental deficiencies. May require significant redesign. → Schedule pre-submittal meeting with plan checker. Address all comments. May need to restart review cycle.

## File Naming Convention

Format: `[Number Prefix]-[Document type]-[Revision Number] [Street address]_[Type/Count of Addenda]`

- `1-` Plans/Drawings (e.g., `1-Plans-R0 123 Main St`)
- `2-` Calculations (e.g., `2-Calculations-R0 123 Main St`)
- `3-` Reports/Studies (e.g., `3-Reports-R0 123 Main St`)
- `4-` Specifications (e.g., `4-Specifications-R0 123 Main St`)
- `5-` Other Documents (e.g., `5-Other-R0 123 Main St`)
- `6-` Addenda (e.g., `6-Addenda-R1 123 Main St_Addendum1`)

## Sheet Numbering Convention

- `G` — General
- `A` — Architectural
- `S` — Structural
- `M` — Mechanical
- `E` — Electrical
- `P` — Plumbing
- `T` — Title-24 Energy
- `L` — Landscape (if applicable)

## Pro Tips

- Obtain Planning approval BEFORE submitting building permit application
- Expect 3 rounds of completeness review — 3rd round escalates to supervisor
- Add DBI Back Check page as LAST page of plan set PDF (Bluebeam-formatted template)
- Bluebeam Studio folders: A.PERMIT SUBMITTAL → 1.Permit Forms, 2.Routing Forms, 3.Documents for Review

**Confidence:** high

---
## Sources

- [DBI 13-Section Completeness Checklist](https://sf.gov/departments/building-inspection/permits)
- [DBI Electronic Plan Review (EPR) Requirements](https://sf.gov/departments/building-inspection/permits)
- [DBI Permit Forms Taxonomy](https://sf.gov/departments/building-inspection/permits)
- [DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-01: Signature on Plans (4 status categories)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI In-House Review Process Guide](https://sf.gov/departments/building-inspection/permits)


### Revision Risk

**ERROR:** Catalog Error: Table with name permits does not exist!
Did you mean "pg_settings"?

LINE 21:         FROM permits
                      ^

---


## Scenario B: ADU Over Garage (Sunset, $180K)

### Predicted Permits

# Permit Prediction

**Project:** Convert existing detached garage to ADU with kitchenette and bathroom in the Sunset District. 450 sq ft, new plumbing/electrical, $180K budget.
**Estimated Cost:** $180,000
**Square Footage:** 450

**Detected Project Types:** adu, commercial_ti
**Matched Concepts:** change_of_use, adu, commercial_ti

## Permit Form

**Form:** Form 3/8
**Reason:** Alterations/repairs to existing building
**Notes:** Mark Form 3 for in-house review, Form 8 for OTC-eligible projects

## Review Path

**Path:** in_house
**Reason:** 'adu' projects require in-house review
**Confidence:** high

## Agency Routing

- **DBI (Building)** (Required): All permitted work
- **Planning** (Required): Change of use, new construction, demolition, exterior changes, or historic resource
- **DBI Mechanical/Electrical** (Required): HVAC, electrical, or commercial kitchen systems
- **SFPUC** (Conditional): New plumbing fixtures or water service

## Special Requirements

- **ADU pre-approval application:** Separate ADU application process for detached ADUs
- **Fire separation:** Fire separation between ADU and primary dwelling
- **Separate utility connections:** May need separate water/electric meters
- **ADA path-of-travel (20% rule):** Construction cost $180,000 below threshold $203,611 — accessibility upgrades limited to 20% ($36,000)
- **DA-02 Checklist required:** Disabled Access Upgrade Compliance Checklist Package required for all commercial alterations
- **Plan signature — verify G-01 Status I exempt or Status III required:** Non-highrise single-floor TI ≤$400,000 with non-structural scope may qualify for exempt status (G-01). Otherwise CA-licensed architect or engineer required.
- **Title-24 energy compliance (nonresidential alteration):** NRCC required if altering HVAC, lighting, or envelope. NRCI sub-forms at inspection per DBI M-04 checklist. NRCA acceptance testing for systems >54,000 BTU/hr (MCH-04-A economizer, LTI-02-A daylighting, etc.).
- **Title-24 Final Compliance Affidavit (M-06):** Prior to final inspection, email affidavit to dbi.energyinspections@sfgov.org. Must list all certificate form codes. Allow 10 business days for review. HERS items require certified HERS Rater; NRCA items require certified ATT.

## Confidence Summary

- overall: high
- form_selection: high
- review_path: high
- agency_routing: high
- documents: high

## Gaps / Caveats

- No address provided — cannot check zoning, historic status, or neighborhood-specific rules

---
## Sources

- [DBI Decision Tree (7-step permit pathway)](https://sf.gov/departments/building-inspection/permits)
- [DBI OTC Permit Criteria (55 project type classifications)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Permit Forms Taxonomy](https://sf.gov/departments/building-inspection/permits)
- [DBI Info Sheet G-20: Routing Matrix](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheets DA-02, DA-12, DA-13 (CBC 11B Accessibility)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-01: Signature on Plans (4 status categories)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)](https://sf.gov/resource/2022/information-sheets-dbi)
- [SF Planning Code (zoning, CU, Section 311)](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/)


### Estimated Fees

# Fee Estimate

**Construction Valuation:** $180,000
**Permit Category:** alterations
**Square Footage:** 450

## DBI Building Permit Fees (Table 1A-A)

| Fee Component | Amount |
|--------------|--------|
| Plan Review Fee | $3,780.30 |
| Permit Issuance Fee | $1,316.40 |
| CBSC Fee | $7.20 |
| SMIP Fee | $23.40 |
| **Total DBI Fees** | **$5,127.30** |

*Fee tier: $50,001 to $200,000*

## Additional Fees (estimated)

- Plumbing permit: $483-$701
- Electrical permit: per Table 1A-E Category 1 tiers

## Notes

- Fee schedule effective 9/1/2025 (Ord. 126-25)
- DBI may adjust valuation per DBI Cost Schedule
- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total
- Fees subject to periodic update — verify against current DBI schedule

**Confidence:** high

---
## Sources

- [DBI Fee Schedule G-13 (Tables 1A-A through 1A-S, eff. 9/1/2025)](https://sf.gov/resource/2022/information-sheets-dbi)


### Estimated Timeline

**ERROR:** Catalog Error: Table with name permits does not exist!
Did you mean "pg_settings"?

LINE 22:         FROM permits
                      ^

### Required Documents

# Required Documents Checklist

**Forms:** Form 3/8
**Review Path:** in_house
**Project Type:** adu

## Initial Filing Documents

1. [ ] Building Permit Application (Form 3/8)
2. [ ] Construction plans (PDF for EPR)
3. [ ] Permit Applicant Disclosure and Certification form
4. [ ] Title 24 Energy compliance forms
5. [ ] San Francisco Green Building form (GS1-GS6)
6. [ ] Construction cost estimate worksheet

## Agency-Specific Documents

1. [ ] Planning Department approval letter (obtain BEFORE building permit submission)
2. [ ] Section 311 notification materials (if neighborhood notification required)

## Project-Specific Requirements

1. [ ] ADU pre-approval application (for detached ADUs)
2. [ ] Fire separation details between ADU and primary dwelling
3. [ ] Utility connection plans (separate meter requirements)
4. [ ] CF1R — Residential Certificate of Compliance (for alterations touching energy systems, per M-03)
5. [ ] Existing conditions documentation for Title-24 baseline (T24-C02 — #1 alteration correction)
6. [ ] Title-24 CEC Final Compliance Affidavit (M-06) — email to dbi.energyinspections@sfgov.org prior to final inspection

## Electronic Plan Review (EPR) Requirements

*All plans must be submitted electronically as of January 1, 2024*

- Vector-based PDF required: CAD-produced vector lines, not scanned images. Non-compliant = rejection.
- TrueType/OpenType fonts: Searchable text required. SHX fonts need OCR post-processing.
- Single consolidated PDF: One PDF per document type. No individual sheet files.
- Full 1:1 scale: Print at 100% scale from authoring software.
- Minimum 22" x 34" sheets: ANSI D or Arch D minimum. Signage permits: 11x17. Supplements: 8.5x11.
- File size < 250MB: Per upload. Site permit addenda: 350MB limit.
- PDF unlocked: No encryption, passwords, or security restrictions.
- No digital certificate signatures: Use scanned graphic signatures. DocuSign/Adobe Sign certificates lock the PDF.
- Back Check page: DBI standardized Back Check page appended to plan set.

## Pre-Submission Checklist

- [ ] Vector-based lines (no scanned/raster drawings) [EPR-001]
- [ ] TrueType/OpenType fonts for searchable text [EPR-002]
- [ ] All sheets in single consolidated PDF [EPR-003]
- [ ] Full 1:1 scale output (not 'scale to fit') [EPR-004]
- [ ] Minimum sheet size 22" x 34" for drawings [EPR-005]
- [ ] File size under 250MB per upload [EPR-006]
- [ ] Bookmarks for each sheet (recommended) [EPR-007]
- [ ] PDF unlocked — no encryption or passwords [EPR-009]
- [ ] No certificate-type digital signatures [EPR-010]
- [ ] 8.5" x 11" blank area on cover sheet [EPR-012]
- [ ] Project address on every sheet [EPR-013]
- [ ] Sheet numbers on every sheet [EPR-014]
- [ ] Design professional signature/stamp on every sheet [EPR-018]
- [ ] Flatten PDF after adding graphic signatures [EPR-019]
- [ ] Back Check page appended [EPR-021]

## Plan Check Correction Response Workflow

*When corrections are required, follow this sequence:*

- **EPR-023:** Download marked-up plans from Bluebeam Studio session — Plan checker comments appear as Bluebeam markup annotations on specific sheets. Download the full annotated set to review all comments across all reviewers.
- **EPR-024:** Address ALL plan check comments — Every comment from every reviewing agency must be addressed. Use Bluebeam's markup reply feature to respond to each comment, or create a correction response letter referencing each comment by reviewer and sheet number.
- **EPR-025:** Add revision clouds on ALL changed items — Every change between submission rounds must be enclosed in a revision cloud. Include revision delta markers (triangle with revision number). Revision clouds must be on the drawing layer, not as Bluebeam annotations.
- **EPR-026:** Upload only changed sheets for corrections — For plan check corrections, upload only the sheets that were modified — not the entire plan set. Use the same file naming convention with incremented revision number. Full set re-upload is only for addenda (new scope).
- **EPR-027:** Update sheet index and page count — If sheets were added or removed, update the cover sheet's table of contents and total page count to match the revised set.
- **EPR-028:** Notify reviewer of resubmittal — After uploading corrected sheets, notify the reviewer through the Bluebeam Studio session or PermitSF portal. Do not assume reviewers are automatically notified of uploads.

**Corrections vs Addenda:**
- *Correction:* Response to plan check comments. Upload only changed sheets with revision clouds. Uses same application number and review session.
- *Addendum:* Additional scope added to an approved or in-review permit. Requires new document upload with full addenda set. Format: [Number Prefix]-[Document type]-[Revision Number] [Street address]_[Type/Count of Addenda]. File size limit for site permit addenda is 350MB (vs 250MB standard).

## Review Status Guide

- **Approved:** Plans meet all code requirements. No changes needed. → Proceed to fee payment and permit issuance.
- **Approved as Noted:** Plans are approved with minor notations. Changes may be required to be shown on job-site set but do not require resubmittal. → Review all notations. Incorporate notes into construction documents. Proceed to fee payment.
- **Corrections Required:** Plans have deficiencies that must be corrected and resubmitted for another review round. → Follow correction response workflow (EPR-023 through EPR-028). Upload corrected sheets with revision clouds.
- **Not Approved:** Plans have fundamental deficiencies. May require significant redesign. → Schedule pre-submittal meeting with plan checker. Address all comments. May need to restart review cycle.

## File Naming Convention

Format: `[Number Prefix]-[Document type]-[Revision Number] [Street address]_[Type/Count of Addenda]`

- `1-` Plans/Drawings (e.g., `1-Plans-R0 123 Main St`)
- `2-` Calculations (e.g., `2-Calculations-R0 123 Main St`)
- `3-` Reports/Studies (e.g., `3-Reports-R0 123 Main St`)
- `4-` Specifications (e.g., `4-Specifications-R0 123 Main St`)
- `5-` Other Documents (e.g., `5-Other-R0 123 Main St`)
- `6-` Addenda (e.g., `6-Addenda-R1 123 Main St_Addendum1`)

## Sheet Numbering Convention

- `G` — General
- `A` — Architectural
- `S` — Structural
- `M` — Mechanical
- `E` — Electrical
- `P` — Plumbing
- `T` — Title-24 Energy
- `L` — Landscape (if applicable)

## Pro Tips

- Obtain Planning approval BEFORE submitting building permit application
- Expect 3 rounds of completeness review — 3rd round escalates to supervisor
- Add DBI Back Check page as LAST page of plan set PDF (Bluebeam-formatted template)
- Bluebeam Studio folders: A.PERMIT SUBMITTAL → 1.Permit Forms, 2.Routing Forms, 3.Documents for Review

**Confidence:** high

---
## Sources

- [DBI 13-Section Completeness Checklist](https://sf.gov/departments/building-inspection/permits)
- [DBI Electronic Plan Review (EPR) Requirements](https://sf.gov/departments/building-inspection/permits)
- [DBI Permit Forms Taxonomy](https://sf.gov/departments/building-inspection/permits)
- [DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-01: Signature on Plans (4 status categories)](https://sf.gov/resource/2022/information-sheets-dbi)
- [SF Planning Code (zoning, CU, Section 311)](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/)
- [DBI In-House Review Process Guide](https://sf.gov/departments/building-inspection/permits)


### Revision Risk

**ERROR:** Catalog Error: Table with name permits does not exist!
Did you mean "pg_settings"?

LINE 21:         FROM permits
                      ^

---


## Scenario C: Commercial Tenant Improvement (Financial District, $350K)

### Predicted Permits

# Permit Prediction

**Project:** Office tenant improvement in Financial District, 3,500 sq ft. New walls, HVAC modifications, lighting, ADA-compliant restrooms. Budget $350K.
**Estimated Cost:** $350,000
**Square Footage:** 3,500

**Detected Project Types:** commercial_ti
**Matched Concepts:** commercial_ti, disability_access

## Permit Form

**Form:** Form 3/8
**Reason:** Alterations/repairs to existing building
**Notes:** Mark Form 3 for in-house review, Form 8 for OTC-eligible projects

## Review Path

**Path:** likely_in_house
**Reason:** Scope likely exceeds OTC one-hour review threshold
**Confidence:** medium

## Agency Routing

- **DBI (Building)** (Required): All permitted work
- **DBI Mechanical/Electrical** (Required): HVAC, electrical, or commercial kitchen systems

## Special Requirements

- **ADA full path-of-travel compliance:** Construction cost $350,000 exceeds threshold $203,611 — FULL CBC 11B compliance required
- **DA-02 Checklist required:** Disabled Access Upgrade Compliance Checklist Package required for all commercial alterations
- **Plan signature — verify G-01 Status I exempt or Status III required:** Non-highrise single-floor TI ≤$400,000 with non-structural scope may qualify for exempt status (G-01). Otherwise CA-licensed architect or engineer required.
- **Title-24 energy compliance (nonresidential alteration):** NRCC required if altering HVAC, lighting, or envelope. NRCI sub-forms at inspection per DBI M-04 checklist. NRCA acceptance testing for systems >54,000 BTU/hr (MCH-04-A economizer, LTI-02-A daylighting, etc.).
- **Title-24 Final Compliance Affidavit (M-06):** Prior to final inspection, email affidavit to dbi.energyinspections@sfgov.org. Must list all certificate form codes. Allow 10 business days for review. HERS items require certified HERS Rater; NRCA items require certified ATT.

## Confidence Summary

- overall: medium
- form_selection: high
- review_path: high
- agency_routing: high
- documents: high

## Gaps / Caveats

- No address provided — cannot check zoning, historic status, or neighborhood-specific rules

---
## Sources

- [DBI Decision Tree (7-step permit pathway)](https://sf.gov/departments/building-inspection/permits)
- [DBI OTC Permit Criteria (55 project type classifications)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Permit Forms Taxonomy](https://sf.gov/departments/building-inspection/permits)
- [DBI Info Sheet G-20: Routing Matrix](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheets DA-02, DA-12, DA-13 (CBC 11B Accessibility)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-01: Signature on Plans (4 status categories)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)](https://sf.gov/resource/2022/information-sheets-dbi)


### Estimated Fees

# Fee Estimate

**Construction Valuation:** $350,000
**Permit Category:** alterations
**Square Footage:** 3,500

## DBI Building Permit Fees (Table 1A-A)

| Fee Component | Amount |
|--------------|--------|
| Plan Review Fee | $6,135.50 |
| Permit Issuance Fee | $2,116.50 |
| CBSC Fee | $14.00 |
| SMIP Fee | $45.50 |
| **Total DBI Fees** | **$8,311.50** |

*Fee tier: $200,001 to $500,000*

## SFFD Fees (Table 107-B / 107-C)

| Fee Component | Amount |
|--------------|--------|
| SFFD Plan Review (Table 107-B) | $2,239.95 |
| SFFD Field Inspection (Table 107-C) | $408.00 |
| **Total SFFD Fees** | **$2,647.95** |

## Additional Fees (estimated)

- School Impact Fee (SFUSD): varies by floor area increase

## ADA/Accessibility Cost Impact

**Valuation Threshold:** $203,611
**Status:** ABOVE threshold — FULL path-of-travel compliance required (CBC 11B)
*Construction cost $350,000 exceeds $203,611 threshold*
- Submit DA-02 Disabled Access Compliance Checklist with permit application

## Notes

- Fee schedule effective 9/1/2025 (Ord. 126-25)
- DBI may adjust valuation per DBI Cost Schedule
- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total
- Fees subject to periodic update — verify against current DBI schedule

**Confidence:** high

---
## Sources

- [DBI Fee Schedule G-13 (Tables 1A-A through 1A-S, eff. 9/1/2025)](https://sf.gov/resource/2022/information-sheets-dbi)
- [SF Fire Code — Tables 107-B, 107-C (SFFD fees)](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_fire/0-0-0-2)
- [DBI Info Sheets DA-02, DA-12, DA-13 (CBC 11B Accessibility)](https://sf.gov/resource/2022/information-sheets-dbi)


### Estimated Timeline

**ERROR:** Catalog Error: Table with name permits does not exist!
Did you mean "pg_settings"?

LINE 22:         FROM permits
                      ^

### Required Documents

# Required Documents Checklist

**Forms:** Form 3/8
**Review Path:** in_house
**Project Type:** commercial_ti

## Initial Filing Documents

1. [ ] Building Permit Application (Form 3/8)
2. [ ] Construction plans (PDF for EPR)
3. [ ] Permit Applicant Disclosure and Certification form
4. [ ] Title 24 Energy compliance forms
5. [ ] San Francisco Green Building form (GS1-GS6)
6. [ ] Construction cost estimate worksheet

## Agency-Specific Documents

1. [ ] Planning Department approval letter (obtain BEFORE building permit submission)
2. [ ] Section 311 notification materials (if neighborhood notification required)

## Project-Specific Requirements

1. [ ] DA-02 Disabled Access Upgrade Compliance Checklist Package (required for ALL commercial alterations)
2. [ ] ADA path-of-travel documentation
3. [ ] NRCC energy compliance (if altering HVAC or lighting)
4. [ ] NRCC — Nonresidential Certificate of Compliance (if altering HVAC, lighting, or envelope)
5. [ ] NRCI/NRCA sub-forms at inspection — specific forms depend on scope (see M-04 checklist)
6. [ ] Existing conditions documentation for Title-24 baseline (T24-C02 — #1 alteration correction)
7. [ ] Title-24 CEC Final Compliance Affidavit (M-06) — email to dbi.energyinspections@sfgov.org prior to final inspection
8. [ ] DA-02 Form A: Building description (use, occupancy, total SF, alteration SF, year built)
9. [ ] DA-02 Form B: Compliance path selection (full compliance vs 20% disproportionate cost)
10. [ ] DA-02 Form C: CBC 11B checklist — entrance, restrooms, signage, counters, path of travel
11. [ ] Plans signed by CA-licensed architect or engineer — OR exempt if single-floor non-highrise TI ≤$400,000 (G-01 Status I/III)

## Electronic Plan Review (EPR) Requirements

*All plans must be submitted electronically as of January 1, 2024*

- Vector-based PDF required: CAD-produced vector lines, not scanned images. Non-compliant = rejection.
- TrueType/OpenType fonts: Searchable text required. SHX fonts need OCR post-processing.
- Single consolidated PDF: One PDF per document type. No individual sheet files.
- Full 1:1 scale: Print at 100% scale from authoring software.
- Minimum 22" x 34" sheets: ANSI D or Arch D minimum. Signage permits: 11x17. Supplements: 8.5x11.
- File size < 250MB: Per upload. Site permit addenda: 350MB limit.
- PDF unlocked: No encryption, passwords, or security restrictions.
- No digital certificate signatures: Use scanned graphic signatures. DocuSign/Adobe Sign certificates lock the PDF.
- Back Check page: DBI standardized Back Check page appended to plan set.

## Pre-Submission Checklist

- [ ] Vector-based lines (no scanned/raster drawings) [EPR-001]
- [ ] TrueType/OpenType fonts for searchable text [EPR-002]
- [ ] All sheets in single consolidated PDF [EPR-003]
- [ ] Full 1:1 scale output (not 'scale to fit') [EPR-004]
- [ ] Minimum sheet size 22" x 34" for drawings [EPR-005]
- [ ] File size under 250MB per upload [EPR-006]
- [ ] Bookmarks for each sheet (recommended) [EPR-007]
- [ ] PDF unlocked — no encryption or passwords [EPR-009]
- [ ] No certificate-type digital signatures [EPR-010]
- [ ] 8.5" x 11" blank area on cover sheet [EPR-012]
- [ ] Project address on every sheet [EPR-013]
- [ ] Sheet numbers on every sheet [EPR-014]
- [ ] Design professional signature/stamp on every sheet [EPR-018]
- [ ] Flatten PDF after adding graphic signatures [EPR-019]
- [ ] Back Check page appended [EPR-021]

## Plan Check Correction Response Workflow

*When corrections are required, follow this sequence:*

- **EPR-023:** Download marked-up plans from Bluebeam Studio session — Plan checker comments appear as Bluebeam markup annotations on specific sheets. Download the full annotated set to review all comments across all reviewers.
- **EPR-024:** Address ALL plan check comments — Every comment from every reviewing agency must be addressed. Use Bluebeam's markup reply feature to respond to each comment, or create a correction response letter referencing each comment by reviewer and sheet number.
- **EPR-025:** Add revision clouds on ALL changed items — Every change between submission rounds must be enclosed in a revision cloud. Include revision delta markers (triangle with revision number). Revision clouds must be on the drawing layer, not as Bluebeam annotations.
- **EPR-026:** Upload only changed sheets for corrections — For plan check corrections, upload only the sheets that were modified — not the entire plan set. Use the same file naming convention with incremented revision number. Full set re-upload is only for addenda (new scope).
- **EPR-027:** Update sheet index and page count — If sheets were added or removed, update the cover sheet's table of contents and total page count to match the revised set.
- **EPR-028:** Notify reviewer of resubmittal — After uploading corrected sheets, notify the reviewer through the Bluebeam Studio session or PermitSF portal. Do not assume reviewers are automatically notified of uploads.

**Corrections vs Addenda:**
- *Correction:* Response to plan check comments. Upload only changed sheets with revision clouds. Uses same application number and review session.
- *Addendum:* Additional scope added to an approved or in-review permit. Requires new document upload with full addenda set. Format: [Number Prefix]-[Document type]-[Revision Number] [Street address]_[Type/Count of Addenda]. File size limit for site permit addenda is 350MB (vs 250MB standard).

## Review Status Guide

- **Approved:** Plans meet all code requirements. No changes needed. → Proceed to fee payment and permit issuance.
- **Approved as Noted:** Plans are approved with minor notations. Changes may be required to be shown on job-site set but do not require resubmittal. → Review all notations. Incorporate notes into construction documents. Proceed to fee payment.
- **Corrections Required:** Plans have deficiencies that must be corrected and resubmitted for another review round. → Follow correction response workflow (EPR-023 through EPR-028). Upload corrected sheets with revision clouds.
- **Not Approved:** Plans have fundamental deficiencies. May require significant redesign. → Schedule pre-submittal meeting with plan checker. Address all comments. May need to restart review cycle.

## File Naming Convention

Format: `[Number Prefix]-[Document type]-[Revision Number] [Street address]_[Type/Count of Addenda]`

- `1-` Plans/Drawings (e.g., `1-Plans-R0 123 Main St`)
- `2-` Calculations (e.g., `2-Calculations-R0 123 Main St`)
- `3-` Reports/Studies (e.g., `3-Reports-R0 123 Main St`)
- `4-` Specifications (e.g., `4-Specifications-R0 123 Main St`)
- `5-` Other Documents (e.g., `5-Other-R0 123 Main St`)
- `6-` Addenda (e.g., `6-Addenda-R1 123 Main St_Addendum1`)

## Sheet Numbering Convention

- `G` — General
- `A` — Architectural
- `S` — Structural
- `M` — Mechanical
- `E` — Electrical
- `P` — Plumbing
- `T` — Title-24 Energy
- `L` — Landscape (if applicable)

## Pro Tips

- Obtain Planning approval BEFORE submitting building permit application
- Expect 3 rounds of completeness review — 3rd round escalates to supervisor
- Add DBI Back Check page as LAST page of plan set PDF (Bluebeam-formatted template)
- Bluebeam Studio folders: A.PERMIT SUBMITTAL → 1.Permit Forms, 2.Routing Forms, 3.Documents for Review

**Confidence:** high

---
## Sources

- [DBI 13-Section Completeness Checklist](https://sf.gov/departments/building-inspection/permits)
- [DBI Electronic Plan Review (EPR) Requirements](https://sf.gov/departments/building-inspection/permits)
- [DBI Permit Forms Taxonomy](https://sf.gov/departments/building-inspection/permits)
- [DBI Info Sheets DA-02, DA-12, DA-13 (CBC 11B Accessibility)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-01: Signature on Plans (4 status categories)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI In-House Review Process Guide](https://sf.gov/departments/building-inspection/permits)


### Revision Risk

**ERROR:** Catalog Error: Table with name permits does not exist!
Did you mean "pg_settings"?

LINE 21:         FROM permits
                      ^

---


## Scenario D: Restaurant Conversion (Mission, $250K)

### Predicted Permits

# Permit Prediction

**Project:** Convert vacant retail space to restaurant with Type I hood, grease interceptor, 49 seats, full commercial kitchen. Mission District, $250K budget.
**Estimated Cost:** $250,000

**Detected Project Types:** restaurant
**Matched Concepts:** commercial_kitchen_hood, restaurant, change_of_use

## Permit Form

**Form:** Form 3/8
**Reason:** Alterations/repairs to existing building
**Notes:** Mark Form 3 for in-house review, Form 8 for OTC-eligible projects

## Review Path

**Path:** in_house
**Reason:** 'restaurant' projects require in-house review
**Confidence:** high

## Agency Routing

- **DBI (Building)** (Required): All permitted work
- **Planning** (Required): Change of use, new construction, demolition, exterior changes, or historic resource
- **SFFD (Fire)** (Required): Fire code review — restaurant hood/suppression, new construction, or occupancy change
- **DPH (Public Health)** (Required): Health permit for food service — parallel review with DBI. DPH must approve before permit issuance.
- **DBI Mechanical/Electrical** (Required): HVAC, electrical, or commercial kitchen systems
- **SFPUC** (Conditional): New plumbing fixtures or water service
- **DPW/BSM** (Conditional): Work in or adjacent to public right-of-way

## Special Requirements

- **Occupancy classification (G-25):** Occupant load ≤50 = Group B (business). Occupant load >50 = Group A-2 (assembly) — triggers sprinklers, SFFD operational permit ($387), stricter egress and accessibility. Bars/lounges are always Group A-2.
- **Planning zoning verification (G-25 Step 1):** Visit Planning FIRST — confirm restaurant use is permitted at site. CU hearing may be required depending on zoning district.
- **DPH pre-application consultation (G-25 Step 2):** Contact DPH Environmental Health BEFORE design. Bring menu, floor plan concept, equipment list. DPH requirements heavily influence construction design.
- **Separate permits required (G-25):** Building permit + SEPARATE plumbing permit (Cat 6PA $543 or 6PB $1,525) + SEPARATE electrical permit (Table 1A-E) + DPH health permit (separate application). SFFD operational permit if >50 occupants.
- **DPH health permit application:** Food preparation workflow diagram + equipment schedule
- **Type I hood fire suppression:** Automatic suppression system for grease-producing equipment. Include hood data sheet with make, model, CFM, and duct sizing. UL 300 listed.
- **Grease interceptor sizing:** Grease trap calculations per CA Plumbing Code Table 7-3. Check SFPUC capacity charge — may require larger than code minimum.
- **DPH menu submission:** Full menu required — determines facility category and equipment requirements (DPH-007)
- **DPH equipment schedule:** Numbered equipment schedule cross-referenced to layout — columns: Item#, Name, Manufacturer, Model, Dimensions, NSF cert, Gas/Elec, BTU/kW (Appendix C template)
- **DPH room finish schedule:** Room-by-room finish schedule — floor, cove base, walls (lower/upper), ceiling per Appendix D template
- **DPH construction standards:** Cove base 3/8" radius, min 4" height. Floors slip-resistant in cooking areas. 50fc lighting at food prep, 20fc at handwash. Physical samples may be required.
- **ADA full path-of-travel compliance:** Construction cost $250,000 exceeds threshold $203,611 — FULL CBC 11B compliance required
- **DA-02 Checklist required:** Disabled Access Upgrade Compliance Checklist Package required for all commercial alterations
- **CA-licensed architect or engineer likely required (G-01):** Restaurant construction involves structural, mechanical, and fire suppression systems — typically requires licensed professional (G-01 Status III/IV). Sprinkler and hood suppression designs require SFFD-qualified professionals.
- **Title-24 energy compliance (nonresidential alteration):** NRCC required if altering HVAC, lighting, or envelope. NRCI sub-forms at inspection per DBI M-04 checklist. NRCA acceptance testing for systems >54,000 BTU/hr (MCH-04-A economizer, LTI-02-A daylighting, etc.).
- **Title-24 Final Compliance Affidavit (M-06):** Prior to final inspection, email affidavit to dbi.energyinspections@sfgov.org. Must list all certificate form codes. Allow 10 business days for review. HERS items require certified HERS Rater; NRCA items require certified ATT.

## Confidence Summary

- overall: high
- form_selection: high
- review_path: high
- agency_routing: high
- documents: high

## Gaps / Caveats

- No address provided — cannot check zoning, historic status, or neighborhood-specific rules

---
## Sources

- [DBI Decision Tree (7-step permit pathway)](https://sf.gov/departments/building-inspection/permits)
- [DBI OTC Permit Criteria (55 project type classifications)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Permit Forms Taxonomy](https://sf.gov/departments/building-inspection/permits)
- [DBI Info Sheet G-20: Routing Matrix](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-25: Restaurant Building Permit Requirements](https://sf.gov/resource/2022/information-sheets-dbi)
- [DPH Food Facility Construction Requirements (22 checks)](https://www.sfdph.org/dph/EH/Food/default.asp)
- [SF Fire Code — Tables 107-B, 107-C (SFFD fees)](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_fire/0-0-0-2)
- [DBI Info Sheets DA-02, DA-12, DA-13 (CBC 11B Accessibility)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-01: Signature on Plans (4 status categories)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)](https://sf.gov/resource/2022/information-sheets-dbi)
- [SF Planning Code (zoning, CU, Section 311)](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/)


### Estimated Fees

# Fee Estimate

**Construction Valuation:** $250,000
**Permit Category:** alterations

## DBI Building Permit Fees (Table 1A-A)

| Fee Component | Amount |
|--------------|--------|
| Plan Review Fee | $4,782.50 |
| Permit Issuance Fee | $1,661.50 |
| CBSC Fee | $10.00 |
| SMIP Fee | $32.50 |
| **Total DBI Fees** | **$6,486.50** |

*Fee tier: $200,001 to $500,000*

## SFFD Fees (Table 107-B / 107-C)

| Fee Component | Amount |
|--------------|--------|
| SFFD Plan Review (Table 107-B) | $1,953.95 |
| SFFD Field Inspection (Table 107-C) | $408.00 |
| New sprinkler systems | $408.00 |
| Place of Assembly (if >50 occupants) | $387.00 |
| **Total SFFD Fees** | **$3,156.95** |

## Additional Fees (estimated)

- Plumbing permit: $543-$1,525
- DPH health permit: varies by facility type

## ADA/Accessibility Cost Impact

**Valuation Threshold:** $203,611
**Status:** ABOVE threshold — FULL path-of-travel compliance required (CBC 11B)
*Construction cost $250,000 exceeds $203,611 threshold*
- Submit DA-02 Disabled Access Compliance Checklist with permit application

## Notes

- Fee schedule effective 9/1/2025 (Ord. 126-25)
- DBI may adjust valuation per DBI Cost Schedule
- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total
- Fees subject to periodic update — verify against current DBI schedule

**Confidence:** high

---
## Sources

- [DBI Fee Schedule G-13 (Tables 1A-A through 1A-S, eff. 9/1/2025)](https://sf.gov/resource/2022/information-sheets-dbi)
- [SF Fire Code — Tables 107-B, 107-C (SFFD fees)](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_fire/0-0-0-2)
- [DBI Info Sheets DA-02, DA-12, DA-13 (CBC 11B Accessibility)](https://sf.gov/resource/2022/information-sheets-dbi)


### Estimated Timeline

**ERROR:** Catalog Error: Table with name permits does not exist!
Did you mean "pg_settings"?

LINE 22:         FROM permits
                      ^

### Required Documents

# Required Documents Checklist

**Forms:** Form 3/8
**Review Path:** in_house
**Project Type:** restaurant

## Initial Filing Documents

1. [ ] Building Permit Application (Form 3/8)
2. [ ] Construction plans (PDF for EPR)
3. [ ] Permit Applicant Disclosure and Certification form
4. [ ] Title 24 Energy compliance forms
5. [ ] San Francisco Green Building form (GS1-GS6)
6. [ ] Construction cost estimate worksheet

## Agency-Specific Documents

1. [ ] Planning Department approval letter (obtain BEFORE building permit submission)
2. [ ] Section 311 notification materials (if neighborhood notification required)
3. [ ] DPH Health permit application
4. [ ] Floor plan showing entire facility drawn to scale (DPH-001)
5. [ ] Equipment layout with numbered equipment schedule — cross-referenced (DPH-002)
6. [ ] Complete plumbing layout with grease interceptor location and sizing (DPH-003)
7. [ ] Exhaust ventilation layout with hood data sheets and calculations (DPH-004)
8. [ ] Complete finish schedule — floors, cove base, walls, ceilings by area (DPH-005)
9. [ ] Electrical/lighting layout with foot-candle calculations (DPH-006)
10. [ ] Complete menu including alcohol service (DPH-007)
11. [ ] Fire suppression system plans
12. [ ] Occupancy load calculations
13. [ ] Fire flow study (new construction)

## Project-Specific Requirements

1. [ ] Use change justification letter
2. [ ] Existing and proposed occupancy documentation
3. [ ] Grease interceptor sizing calculations
4. [ ] Kitchen layout with equipment schedule
5. [ ] Type I hood specifications and fire suppression details
6. [ ] Ventilation calculations for commercial kitchen
7. [ ] DPH Health permit application
8. [ ] DA-02 Disabled Access Upgrade Compliance Checklist Package
9. [ ] ADA path-of-travel documentation showing route from primary entrance to area of alteration
10. [ ] Existing conditions survey with door widths, clearances, slopes, restroom dimensions
11. [ ] Restroom upgrade plans per CBC Chapter 11B
12. [ ] NRCC — Nonresidential Certificate of Compliance (if altering HVAC, lighting, or envelope)
13. [ ] NRCI/NRCA sub-forms at inspection — specific forms depend on scope (see M-04 checklist)
14. [ ] Existing conditions documentation for Title-24 baseline (T24-C02 — #1 alteration correction)
15. [ ] Title-24 CEC Final Compliance Affidavit (M-06) — email to dbi.energyinspections@sfgov.org prior to final inspection
16. [ ] DA-02 Form A: Building description (use, occupancy, total SF, alteration SF, year built)
17. [ ] DA-02 Form B: Compliance path selection (full compliance vs 20% disproportionate cost)
18. [ ] DA-02 Form C: CBC 11B checklist — entrance, restrooms, signage, counters, path of travel
19. [ ] DA-13: COU = alteration for accessibility — entire changed-use area must comply with CBC 11B. DA-02 required.
20. [ ] DPH: Three-compartment sink or commercial dishwasher specification (DPH-011)
21. [ ] DPH: Grease interceptor sizing per CA Plumbing Code Table 7-3 (DPH-012)
22. [ ] DPH: Handwashing station locations and specifications (DPH-010)
23. [ ] DPH: Finish schedule with approved materials — cove base min 4" height, 3/8" radius (DPH-005)
24. [ ] DPH: Lighting plan with foot-candle calcs — 50fc food prep, 20fc handwash, 10fc storage (DPH-006)
25. [ ] DPH: Equipment schedule with columns: Item #, Equipment Name, Manufacturer, Model Number + NSF cert, Gas/Elec, BTU/kW (Appendix C)
26. [ ] DPH: Room finish schedule — room-by-room: floor, cove base, walls (lower/upper), ceiling (Appendix D)
27. [ ] Plans must be signed and sealed by CA-licensed architect or civil engineer (G-01 Status III)
28. [ ] First plan sheet: original signature + professional seal + registration number + sheet index (G-01)

## Electronic Plan Review (EPR) Requirements

*All plans must be submitted electronically as of January 1, 2024*

- Vector-based PDF required: CAD-produced vector lines, not scanned images. Non-compliant = rejection.
- TrueType/OpenType fonts: Searchable text required. SHX fonts need OCR post-processing.
- Single consolidated PDF: One PDF per document type. No individual sheet files.
- Full 1:1 scale: Print at 100% scale from authoring software.
- Minimum 22" x 34" sheets: ANSI D or Arch D minimum. Signage permits: 11x17. Supplements: 8.5x11.
- File size < 250MB: Per upload. Site permit addenda: 350MB limit.
- PDF unlocked: No encryption, passwords, or security restrictions.
- No digital certificate signatures: Use scanned graphic signatures. DocuSign/Adobe Sign certificates lock the PDF.
- Back Check page: DBI standardized Back Check page appended to plan set.

## Pre-Submission Checklist

- [ ] Vector-based lines (no scanned/raster drawings) [EPR-001]
- [ ] TrueType/OpenType fonts for searchable text [EPR-002]
- [ ] All sheets in single consolidated PDF [EPR-003]
- [ ] Full 1:1 scale output (not 'scale to fit') [EPR-004]
- [ ] Minimum sheet size 22" x 34" for drawings [EPR-005]
- [ ] File size under 250MB per upload [EPR-006]
- [ ] Bookmarks for each sheet (recommended) [EPR-007]
- [ ] PDF unlocked — no encryption or passwords [EPR-009]
- [ ] No certificate-type digital signatures [EPR-010]
- [ ] 8.5" x 11" blank area on cover sheet [EPR-012]
- [ ] Project address on every sheet [EPR-013]
- [ ] Sheet numbers on every sheet [EPR-014]
- [ ] Design professional signature/stamp on every sheet [EPR-018]
- [ ] Flatten PDF after adding graphic signatures [EPR-019]
- [ ] Back Check page appended [EPR-021]

## Plan Check Correction Response Workflow

*When corrections are required, follow this sequence:*

- **EPR-023:** Download marked-up plans from Bluebeam Studio session — Plan checker comments appear as Bluebeam markup annotations on specific sheets. Download the full annotated set to review all comments across all reviewers.
- **EPR-024:** Address ALL plan check comments — Every comment from every reviewing agency must be addressed. Use Bluebeam's markup reply feature to respond to each comment, or create a correction response letter referencing each comment by reviewer and sheet number.
- **EPR-025:** Add revision clouds on ALL changed items — Every change between submission rounds must be enclosed in a revision cloud. Include revision delta markers (triangle with revision number). Revision clouds must be on the drawing layer, not as Bluebeam annotations.
- **EPR-026:** Upload only changed sheets for corrections — For plan check corrections, upload only the sheets that were modified — not the entire plan set. Use the same file naming convention with incremented revision number. Full set re-upload is only for addenda (new scope).
- **EPR-027:** Update sheet index and page count — If sheets were added or removed, update the cover sheet's table of contents and total page count to match the revised set.
- **EPR-028:** Notify reviewer of resubmittal — After uploading corrected sheets, notify the reviewer through the Bluebeam Studio session or PermitSF portal. Do not assume reviewers are automatically notified of uploads.

**Corrections vs Addenda:**
- *Correction:* Response to plan check comments. Upload only changed sheets with revision clouds. Uses same application number and review session.
- *Addendum:* Additional scope added to an approved or in-review permit. Requires new document upload with full addenda set. Format: [Number Prefix]-[Document type]-[Revision Number] [Street address]_[Type/Count of Addenda]. File size limit for site permit addenda is 350MB (vs 250MB standard).

## Review Status Guide

- **Approved:** Plans meet all code requirements. No changes needed. → Proceed to fee payment and permit issuance.
- **Approved as Noted:** Plans are approved with minor notations. Changes may be required to be shown on job-site set but do not require resubmittal. → Review all notations. Incorporate notes into construction documents. Proceed to fee payment.
- **Corrections Required:** Plans have deficiencies that must be corrected and resubmitted for another review round. → Follow correction response workflow (EPR-023 through EPR-028). Upload corrected sheets with revision clouds.
- **Not Approved:** Plans have fundamental deficiencies. May require significant redesign. → Schedule pre-submittal meeting with plan checker. Address all comments. May need to restart review cycle.

## File Naming Convention

Format: `[Number Prefix]-[Document type]-[Revision Number] [Street address]_[Type/Count of Addenda]`

- `1-` Plans/Drawings (e.g., `1-Plans-R0 123 Main St`)
- `2-` Calculations (e.g., `2-Calculations-R0 123 Main St`)
- `3-` Reports/Studies (e.g., `3-Reports-R0 123 Main St`)
- `4-` Specifications (e.g., `4-Specifications-R0 123 Main St`)
- `5-` Other Documents (e.g., `5-Other-R0 123 Main St`)
- `6-` Addenda (e.g., `6-Addenda-R1 123 Main St_Addendum1`)

## Sheet Numbering Convention

- `G` — General
- `A` — Architectural
- `S` — Structural
- `M` — Mechanical
- `E` — Electrical
- `P` — Plumbing
- `T` — Title-24 Energy
- `L` — Landscape (if applicable)

## Pro Tips

- Obtain Planning approval BEFORE submitting building permit application
- Expect 3 rounds of completeness review — 3rd round escalates to supervisor
- Add DBI Back Check page as LAST page of plan set PDF (Bluebeam-formatted template)
- Bluebeam Studio folders: A.PERMIT SUBMITTAL → 1.Permit Forms, 2.Routing Forms, 3.Documents for Review
- Visit Planning FIRST to confirm restaurant use is permitted (G-25 Step 1)
- Contact DPH for pre-application consultation BEFORE design — saves months of rework (G-25 Step 2)
- Separate plumbing permit (Cat 6PA/6PB) + electrical permit required after building permit (G-25)
- Expect parallel review by DBI, DPH, SFFD, Planning — ALL must approve before permit issuance
- Occupant load >50 triggers Group A-2 assembly classification — sprinklers, SFFD operational permit ($387)
- COU = alteration for accessibility (DA-13). Paperwork-only COU ($1 permit): accessibility spend = 20% of $1 ≈ $0

**Confidence:** high

---
## Sources

- [DBI 13-Section Completeness Checklist](https://sf.gov/departments/building-inspection/permits)
- [DBI Electronic Plan Review (EPR) Requirements](https://sf.gov/departments/building-inspection/permits)
- [DBI Permit Forms Taxonomy](https://sf.gov/departments/building-inspection/permits)
- [DBI Info Sheet G-25: Restaurant Building Permit Requirements](https://sf.gov/resource/2022/information-sheets-dbi)
- [DPH Food Facility Construction Requirements (22 checks)](https://www.sfdph.org/dph/EH/Food/default.asp)
- [DBI Info Sheets DA-02, DA-12, DA-13 (CBC 11B Accessibility)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-01: Signature on Plans (4 status categories)](https://sf.gov/resource/2022/information-sheets-dbi)
- [SF Planning Code (zoning, CU, Section 311)](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/)
- [DBI In-House Review Process Guide](https://sf.gov/departments/building-inspection/permits)


### Revision Risk

**ERROR:** Catalog Error: Table with name permits does not exist!
Did you mean "pg_settings"?

LINE 21:         FROM permits
                      ^

---


## Scenario E: Historic Building Renovation (Pacific Heights, $2.5M)

### Predicted Permits

# Permit Prediction

**Project:** Major renovation of Article 10 landmark building in Pacific Heights. Seismic retrofit, new MEP systems, ADA compliance, restore historic facade. 8,000 sq ft, $2.5M budget.
**Estimated Cost:** $2,500,000
**Square Footage:** 8,000

**Detected Project Types:** seismic, commercial_ti, historic
**Matched Concepts:** historic_preservation, seismic, disability_access, commercial_ti

## Permit Form

**Form:** Form 3/8
**Reason:** Alterations/repairs to existing building
**Notes:** Mark Form 3 for in-house review, Form 8 for OTC-eligible projects

## Review Path

**Path:** in_house
**Reason:** 'historic' projects require in-house review
**Confidence:** high

## Agency Routing

- **DBI (Building)** (Required): All permitted work
- **Planning** (Required): Change of use, new construction, demolition, exterior changes, or historic resource
- **SFFD (Fire)** (Required): Fire code review — restaurant hood/suppression, new construction, or occupancy change
- **DBI Mechanical/Electrical** (Required): HVAC, electrical, or commercial kitchen systems

## Special Requirements

- **Structural engineering report:** Licensed structural engineer evaluation required for engineered designs. Exception: prescriptive CEBC A3 cripple wall bracing (EBB/S-09) does NOT require licensed professional (G-01 Status I exempt).
- **Priority processing eligibility:** Voluntary/mandatory seismic upgrades per AB-004
- **Earthquake Brace+Bolt eligibility (S-09):** Pre-1979 wood-frame, cripple wall ≤4ft: qualifies for EBB program (up to $3K reimbursement). OTC-eligible with Form 8 if prescriptive per CEBC Appendix A3. Plans must show wall percentage calculations, anchor bolt schedule, and plywood nailing pattern.
- **Seismic accessibility — mixed-use adjusted cost (DA-12):** Mixed-use buildings: path-of-travel obligation applies ONLY to commercial portion. Adjusted cost = (% commercial floor area) × total construction cost. 20% of adjusted cost = max accessibility spend. Residential portions exempt from Chapter 11B.
- **Historic preservation review:** Certificate of Appropriateness from HPC (Article 10) or Permit to Alter (Article 11)
- **Secretary of Interior Standards:** All work must comply with SOI Standards for Treatment of Historic Properties
- **ADA full path-of-travel compliance:** Construction cost $2,500,000 exceeds threshold $203,611 — FULL CBC 11B compliance required
- **DA-02 Checklist required:** Disabled Access Upgrade Compliance Checklist Package required for all commercial alterations
- **CA-licensed structural engineer required (G-01 Status III):** Structural work requires licensed SE or CE. Seismic retrofit, wall removal, and structural alterations must be designed by State-licensed professional.
- **Title-24 energy compliance (nonresidential alteration):** NRCC required if altering HVAC, lighting, or envelope. NRCI sub-forms at inspection per DBI M-04 checklist. NRCA acceptance testing for systems >54,000 BTU/hr (MCH-04-A economizer, LTI-02-A daylighting, etc.).
- **Title-24 Final Compliance Affidavit (M-06):** Prior to final inspection, email affidavit to dbi.energyinspections@sfgov.org. Must list all certificate form codes. Allow 10 business days for review. HERS items require certified HERS Rater; NRCA items require certified ATT.

## Confidence Summary

- overall: high
- form_selection: high
- review_path: high
- agency_routing: high
- documents: high

## Gaps / Caveats

- No address provided — cannot check zoning, historic status, or neighborhood-specific rules

---
## Sources

- [DBI Decision Tree (7-step permit pathway)](https://sf.gov/departments/building-inspection/permits)
- [DBI OTC Permit Criteria (55 project type classifications)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Permit Forms Taxonomy](https://sf.gov/departments/building-inspection/permits)
- [DBI Info Sheet G-20: Routing Matrix](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet S-09: Earthquake Brace+Bolt (CEBC A3)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheets DA-02, DA-12, DA-13 (CBC 11B Accessibility)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-01: Signature on Plans (4 status categories)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)](https://sf.gov/resource/2022/information-sheets-dbi)
- [SF Planning Code (zoning, CU, Section 311)](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/)


### Estimated Fees

# Fee Estimate

**Construction Valuation:** $2,500,000
**Permit Category:** alterations
**Square Footage:** 8,000

## DBI Building Permit Fees (Table 1A-A)

| Fee Component | Amount |
|--------------|--------|
| Plan Review Fee | $25,568.00 |
| Permit Issuance Fee | $8,832.00 |
| CBSC Fee | $100.00 |
| SMIP Fee | $325.00 |
| **Total DBI Fees** | **$34,825.00** |

*Fee tier: $1,000,001 to $5,000,000*

## Notes

- Fee schedule effective 9/1/2025 (Ord. 126-25)
- DBI may adjust valuation per DBI Cost Schedule
- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total
- Fees subject to periodic update — verify against current DBI schedule

**Confidence:** high

---
## Sources

- [DBI Fee Schedule G-13 (Tables 1A-A through 1A-S, eff. 9/1/2025)](https://sf.gov/resource/2022/information-sheets-dbi)


### Estimated Timeline

**ERROR:** Catalog Error: Table with name permits does not exist!
Did you mean "pg_settings"?

LINE 22:         FROM permits
                      ^

### Required Documents

# Required Documents Checklist

**Forms:** Form 3/8
**Review Path:** in_house
**Project Type:** historic

## Initial Filing Documents

1. [ ] Building Permit Application (Form 3/8)
2. [ ] Construction plans (PDF for EPR)
3. [ ] Permit Applicant Disclosure and Certification form
4. [ ] Title 24 Energy compliance forms
5. [ ] San Francisco Green Building form (GS1-GS6)
6. [ ] Construction cost estimate worksheet

## Agency-Specific Documents

1. [ ] Planning Department approval letter (obtain BEFORE building permit submission)
2. [ ] Section 311 notification materials (if neighborhood notification required)
3. [ ] Fire suppression system plans
4. [ ] Occupancy load calculations
5. [ ] Fire flow study (new construction)

## Project-Specific Requirements

1. [ ] Secretary of Interior Standards compliance documentation
2. [ ] Historic resource evaluation
3. [ ] Certificate of Appropriateness application (Article 10) or Permit to Alter (Article 11)
4. [ ] CF1R — Residential Certificate of Compliance (for alterations touching energy systems, per M-03)
5. [ ] Existing conditions documentation for Title-24 baseline (T24-C02 — #1 alteration correction)
6. [ ] Title-24 CEC Final Compliance Affidavit (M-06) — email to dbi.energyinspections@sfgov.org prior to final inspection
7. [ ] Plans must be signed and sealed by CA-licensed architect or civil engineer (G-01 Status III)
8. [ ] First plan sheet: original signature + professional seal + registration number + sheet index (G-01)

## Electronic Plan Review (EPR) Requirements

*All plans must be submitted electronically as of January 1, 2024*

- Vector-based PDF required: CAD-produced vector lines, not scanned images. Non-compliant = rejection.
- TrueType/OpenType fonts: Searchable text required. SHX fonts need OCR post-processing.
- Single consolidated PDF: One PDF per document type. No individual sheet files.
- Full 1:1 scale: Print at 100% scale from authoring software.
- Minimum 22" x 34" sheets: ANSI D or Arch D minimum. Signage permits: 11x17. Supplements: 8.5x11.
- File size < 250MB: Per upload. Site permit addenda: 350MB limit.
- PDF unlocked: No encryption, passwords, or security restrictions.
- No digital certificate signatures: Use scanned graphic signatures. DocuSign/Adobe Sign certificates lock the PDF.
- Back Check page: DBI standardized Back Check page appended to plan set.

## Pre-Submission Checklist

- [ ] Vector-based lines (no scanned/raster drawings) [EPR-001]
- [ ] TrueType/OpenType fonts for searchable text [EPR-002]
- [ ] All sheets in single consolidated PDF [EPR-003]
- [ ] Full 1:1 scale output (not 'scale to fit') [EPR-004]
- [ ] Minimum sheet size 22" x 34" for drawings [EPR-005]
- [ ] File size under 250MB per upload [EPR-006]
- [ ] Bookmarks for each sheet (recommended) [EPR-007]
- [ ] PDF unlocked — no encryption or passwords [EPR-009]
- [ ] No certificate-type digital signatures [EPR-010]
- [ ] 8.5" x 11" blank area on cover sheet [EPR-012]
- [ ] Project address on every sheet [EPR-013]
- [ ] Sheet numbers on every sheet [EPR-014]
- [ ] Design professional signature/stamp on every sheet [EPR-018]
- [ ] Flatten PDF after adding graphic signatures [EPR-019]
- [ ] Back Check page appended [EPR-021]

## Plan Check Correction Response Workflow

*When corrections are required, follow this sequence:*

- **EPR-023:** Download marked-up plans from Bluebeam Studio session — Plan checker comments appear as Bluebeam markup annotations on specific sheets. Download the full annotated set to review all comments across all reviewers.
- **EPR-024:** Address ALL plan check comments — Every comment from every reviewing agency must be addressed. Use Bluebeam's markup reply feature to respond to each comment, or create a correction response letter referencing each comment by reviewer and sheet number.
- **EPR-025:** Add revision clouds on ALL changed items — Every change between submission rounds must be enclosed in a revision cloud. Include revision delta markers (triangle with revision number). Revision clouds must be on the drawing layer, not as Bluebeam annotations.
- **EPR-026:** Upload only changed sheets for corrections — For plan check corrections, upload only the sheets that were modified — not the entire plan set. Use the same file naming convention with incremented revision number. Full set re-upload is only for addenda (new scope).
- **EPR-027:** Update sheet index and page count — If sheets were added or removed, update the cover sheet's table of contents and total page count to match the revised set.
- **EPR-028:** Notify reviewer of resubmittal — After uploading corrected sheets, notify the reviewer through the Bluebeam Studio session or PermitSF portal. Do not assume reviewers are automatically notified of uploads.

**Corrections vs Addenda:**
- *Correction:* Response to plan check comments. Upload only changed sheets with revision clouds. Uses same application number and review session.
- *Addendum:* Additional scope added to an approved or in-review permit. Requires new document upload with full addenda set. Format: [Number Prefix]-[Document type]-[Revision Number] [Street address]_[Type/Count of Addenda]. File size limit for site permit addenda is 350MB (vs 250MB standard).

## Review Status Guide

- **Approved:** Plans meet all code requirements. No changes needed. → Proceed to fee payment and permit issuance.
- **Approved as Noted:** Plans are approved with minor notations. Changes may be required to be shown on job-site set but do not require resubmittal. → Review all notations. Incorporate notes into construction documents. Proceed to fee payment.
- **Corrections Required:** Plans have deficiencies that must be corrected and resubmitted for another review round. → Follow correction response workflow (EPR-023 through EPR-028). Upload corrected sheets with revision clouds.
- **Not Approved:** Plans have fundamental deficiencies. May require significant redesign. → Schedule pre-submittal meeting with plan checker. Address all comments. May need to restart review cycle.

## File Naming Convention

Format: `[Number Prefix]-[Document type]-[Revision Number] [Street address]_[Type/Count of Addenda]`

- `1-` Plans/Drawings (e.g., `1-Plans-R0 123 Main St`)
- `2-` Calculations (e.g., `2-Calculations-R0 123 Main St`)
- `3-` Reports/Studies (e.g., `3-Reports-R0 123 Main St`)
- `4-` Specifications (e.g., `4-Specifications-R0 123 Main St`)
- `5-` Other Documents (e.g., `5-Other-R0 123 Main St`)
- `6-` Addenda (e.g., `6-Addenda-R1 123 Main St_Addendum1`)

## Sheet Numbering Convention

- `G` — General
- `A` — Architectural
- `S` — Structural
- `M` — Mechanical
- `E` — Electrical
- `P` — Plumbing
- `T` — Title-24 Energy
- `L` — Landscape (if applicable)

## Pro Tips

- Obtain Planning approval BEFORE submitting building permit application
- Expect 3 rounds of completeness review — 3rd round escalates to supervisor
- Add DBI Back Check page as LAST page of plan set PDF (Bluebeam-formatted template)
- Bluebeam Studio folders: A.PERMIT SUBMITTAL → 1.Permit Forms, 2.Routing Forms, 3.Documents for Review
- HPC review happens BEFORE any other Planning approval — start early

**Confidence:** high

---
## Sources

- [DBI 13-Section Completeness Checklist](https://sf.gov/departments/building-inspection/permits)
- [DBI Electronic Plan Review (EPR) Requirements](https://sf.gov/departments/building-inspection/permits)
- [DBI Permit Forms Taxonomy](https://sf.gov/departments/building-inspection/permits)
- [DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)](https://sf.gov/resource/2022/information-sheets-dbi)
- [DBI Info Sheet G-01: Signature on Plans (4 status categories)](https://sf.gov/resource/2022/information-sheets-dbi)
- [SF Planning Code (zoning, CU, Section 311)](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/)
- [DBI In-House Review Process Guide](https://sf.gov/departments/building-inspection/permits)


### Revision Risk

**ERROR:** Catalog Error: Table with name permits does not exist!
Did you mean "pg_settings"?

LINE 21:         FROM permits
                      ^

---

