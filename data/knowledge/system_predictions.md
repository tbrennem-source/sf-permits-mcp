# System Predictions — Amy Stress Test

Generated: 2026-02-14
Tools: predict_permits, estimate_fees, estimate_timeline, required_documents, revision_risk
Tests: 74 passing (16 existing + 48 new + 10 Phase 1 integration)

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

## Confidence Summary

- overall: medium
- form_selection: high
- review_path: high
- agency_routing: high
- documents: high

## Gaps / Caveats

- No address provided — cannot check zoning, historic status, or neighborhood-specific rules

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

## Statistical Context (DuckDB)

Similar permits (3,365 in database):
- 25th percentile cost: $50,000
- Median cost: $72,000
- 75th percentile cost: $100,000
- Filtered to: Noe Valley

## Notes

- Fee schedule effective 9/1/2025 (Ord. 126-25)
- DBI may adjust valuation per DBI Cost Schedule
- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total
- Fees subject to periodic update — verify against current DBI schedule

**Confidence:** high

### Estimated Timeline

# Timeline Estimate

**Permit Type:** alterations
**Neighborhood:** Noe Valley
**Cost Bracket:** 50k_150k

## Filing to Issuance

| Percentile | Days |
|-----------|------|
| 25th (optimistic) | 18 |
| 50th (typical) | 84 |
| 75th (conservative) | 222 |
| 90th (worst case) | 406 |

*Sample size: 1,739 permits*

## Issuance to Completion

- Typical (p50): 157 days
- Conservative (p75): 300 days

## Recent Trend

- Recent 6 months: 25 days avg (136 permits)
- Prior 12 months: 45 days avg (358 permits)
- Trend: **faster** (-45.4%)

**Confidence:** high

### Required Documents

# Required Documents Checklist

**Forms:** Form 3/8
**Review Path:** in_house

## Initial Filing Documents

1. [ ] Building Permit Application (Form 3/8)
2. [ ] Construction plans (PDF for EPR)
3. [ ] Permit Applicant Disclosure and Certification form
4. [ ] Title 24 Energy compliance forms
5. [ ] San Francisco Green Building form (GS1-GS6)
6. [ ] Construction cost estimate worksheet

## Electronic Plan Review (EPR) Requirements

*All plans must be submitted electronically as of January 1, 2024*

- PDF format required: All construction plans must be submitted as PDF files
- Vector-based PDF preferred: PDF should be created from CAD/BIM software, not scanned images. Scanned PDFs may be rejected or cause review delays.
- Unlocked PDF (no password protection): PDFs must not have security restrictions that prevent markup, commenting, or printing
- Fonts embedded: All fonts must be embedded in the PDF to ensure correct rendering across systems
- Bookmarks for each sheet: PDF must contain bookmarks corresponding to each sheet for navigation during plan review
- Minimum sheet size: Plans must be at minimum 11x17 inches per completeness checklist; full plan sets typically 22x34 inches or 24x36 inches
- Back Check page required: All plan sets must include a Back Check page for reviewer corrections tracking

## Pre-Submission Checklist

- [ ] All sheets bookmarked in PDF
- [ ] No security restrictions on PDF file
- [ ] Proper layering (demolition, new work, existing to remain)
- [ ] Title block with permit application number on each sheet
- [ ] Prepared by licensed architect or engineer (stamp and signature)
- [ ] Construction cost estimate included
- [ ] Title 24 energy compliance forms attached
- [ ] Green Building form (GS1-GS6) attached as applicable
- [ ] Back Check page included

## Pro Tips

- Obtain Planning approval BEFORE submitting building permit application
- Expect 3 rounds of completeness review — 3rd round escalates to supervisor
- Include a Back Check page in all plan sets

**Confidence:** high

### Revision Risk

# Revision Risk Assessment

**Permit Type:** alterations
**Neighborhood:** Noe Valley

## Revision Probability

**Risk Level:** HIGH
**Revision Rate:** 23.4% of permits had cost increases during review
**Sample Size:** 12,195 permits analyzed

## Cost Impact

- Average cost increase when revisions occur: **102226.8%**
- Permits with cost increase: 2,852

## Timeline Impact

- Average days to issuance (no revisions): 82
- Average days to issuance (with revisions): 146
- **Revision penalty: +64 days on average**
- 90th percentile (worst case): 287 days

## Common Revision Triggers

1. Incomplete Title-24 energy compliance documentation
2. Missing ADA path-of-travel calculations
3. Structural calculations missing or insufficient
4. Site plan discrepancies with existing conditions
5. Plans not matching permit application description

## Mitigation Strategies

- Engage licensed professional experienced with SF DBI requirements
- Use the completeness checklist (tier1/completeness-checklist.json) before submission
- Include a Back Check page in all plan sets
- Ensure Title-24 energy compliance is complete before submission
- Verify plan description matches permit application exactly

## Questions for Expert Review

- What are the most common plan check correction items for this project type?
- Are there specific reviewers known for particular requirements?
- What pre-submission meetings (if any) could reduce revision rounds?

**Confidence:** high

---

## Scenario B: ADU Over Garage (Sunset, $180K)

### Predicted Permits

# Permit Prediction

**Project:** Convert detached garage to ADU in the Sunset, 450 sq ft, new plumbing and electrical, fire sprinkler required.
**Estimated Cost:** $180,000
**Square Footage:** 450

**Detected Project Types:** adu
**Matched Concepts:** adu, change_of_use, sprinkler_required

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
- **SFPUC** (Conditional): New plumbing fixtures or water service

## Special Requirements

- **ADU pre-approval application:** Separate ADU application process for detached ADUs
- **Fire separation:** Fire separation between ADU and primary dwelling
- **Separate utility connections:** May need separate water/electric meters

## Confidence Summary

- overall: high
- form_selection: high
- review_path: high
- agency_routing: high
- documents: high

## Gaps / Caveats

- No address provided — cannot check zoning, historic status, or neighborhood-specific rules

### Estimated Fees

# Fee Estimate

**Construction Valuation:** $180,000
**Permit Category:** alterations

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

- Plumbing permit (Category 2PA/2PB): $483-$701
- Electrical permit: per Category 1 tiers

## Statistical Context (DuckDB)

Similar permits (2,205 in database):
- 25th percentile cost: $100,000
- Median cost: $130,000
- 75th percentile cost: $180,000
- Filtered to: Sunset/Parkside

## Notes

- Fee schedule effective 9/1/2025 (Ord. 126-25)
- DBI may adjust valuation per DBI Cost Schedule
- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total
- Fees subject to periodic update — verify against current DBI schedule

**Confidence:** high

### Estimated Timeline

# Timeline Estimate

**Permit Type:** alterations
**Neighborhood:** Sunset/Parkside
**Review Path:** in_house
**Cost Bracket:** 150k_500k

## Filing to Issuance

| Percentile | Days |
|-----------|------|
| 25th (optimistic) | 180 |
| 50th (typical) | 306 |
| 75th (conservative) | 512 |
| 90th (worst case) | 721 |

*Sample size: 421 permits*

## Issuance to Completion

- Typical (p50): 163 days
- Conservative (p75): 308 days

## Recent Trend

- Recent 6 months: 71 days avg (15 permits)
- Prior 12 months: 139 days avg (47 permits)
- Trend: **faster** (-48.8%)

**Confidence:** high

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
3. [ ] Fire suppression system plans
4. [ ] Occupancy load calculations
5. [ ] Fire flow study (new construction)
6. [ ] SFPUC fixture count form
7. [ ] Stormwater Management Plan (if 5,000+ sq ft impervious surfaces)

## Project-Specific Requirements

1. [ ] ADU pre-approval application (for detached ADUs)
2. [ ] Fire separation details between ADU and primary dwelling
3. [ ] Utility connection plans (separate meter requirements)

## Electronic Plan Review (EPR) Requirements

*All plans must be submitted electronically as of January 1, 2024*

- PDF format required: All construction plans must be submitted as PDF files
- Vector-based PDF preferred: PDF should be created from CAD/BIM software, not scanned images. Scanned PDFs may be rejected or cause review delays.
- Unlocked PDF (no password protection): PDFs must not have security restrictions that prevent markup, commenting, or printing
- Fonts embedded: All fonts must be embedded in the PDF to ensure correct rendering across systems
- Bookmarks for each sheet: PDF must contain bookmarks corresponding to each sheet for navigation during plan review
- Minimum sheet size: Plans must be at minimum 11x17 inches per completeness checklist; full plan sets typically 22x34 inches or 24x36 inches
- Back Check page required: All plan sets must include a Back Check page for reviewer corrections tracking

## Pre-Submission Checklist

- [ ] All sheets bookmarked in PDF
- [ ] No security restrictions on PDF file
- [ ] Proper layering (demolition, new work, existing to remain)
- [ ] Title block with permit application number on each sheet
- [ ] Prepared by licensed architect or engineer (stamp and signature)
- [ ] Construction cost estimate included
- [ ] Title 24 energy compliance forms attached
- [ ] Green Building form (GS1-GS6) attached as applicable
- [ ] Back Check page included

## Pro Tips

- Obtain Planning approval BEFORE submitting building permit application
- Expect 3 rounds of completeness review — 3rd round escalates to supervisor
- Include a Back Check page in all plan sets

**Confidence:** high

### Revision Risk

# Revision Risk Assessment

**Permit Type:** alterations
**Neighborhood:** Sunset/Parkside
**Project Type:** adu
**Review Path:** in_house

## Revision Probability

**Risk Level:** HIGH
**Revision Rate:** 24.6% of permits had cost increases during review
**Sample Size:** 8,712 permits analyzed

## Cost Impact

- Average cost increase when revisions occur: **87907.3%**
- Permits with cost increase: 2,141

## Timeline Impact

- Average days to issuance (no revisions): 105
- Average days to issuance (with revisions): 235
- **Revision penalty: +130 days on average**
- 90th percentile (worst case): 369 days

## Common Revision Triggers

1. Fire separation between ADU and primary dwelling insufficient
2. Parking requirements not addressed (or waiver not obtained)
3. Setback violations in proposed design
4. Missing utility connection plans (separate meter)
5. Planning Department conditions not reflected in plans

## Mitigation Strategies

- Confirm Planning conditions before finalizing plans
- Engage licensed professional experienced with SF DBI requirements
- Use the completeness checklist (tier1/completeness-checklist.json) before submission
- Include a Back Check page in all plan sets
- Ensure Title-24 energy compliance is complete before submission
- Verify plan description matches permit application exactly

## Questions for Expert Review

- What are the most common plan check correction items for this project type?
- Are there specific reviewers known for particular requirements?
- What pre-submission meetings (if any) could reduce revision rounds?

**Confidence:** high

---

## Scenario C: Commercial TI (Financial District, $350K)

### Predicted Permits

# Permit Prediction

**Project:** 3,000 sq ft office-to-office tenant improvement in Financial District, new HVAC, ADA bathroom upgrades, no change of use.
**Estimated Cost:** $350,000
**Square Footage:** 3,000

**Detected Project Types:** commercial_ti, change_of_use
**Matched Concepts:** change_of_use, commercial_ti, disability_access

## Permit Form

**Form:** Form 3/8
**Reason:** Alterations/repairs to existing building
**Notes:** Mark Form 3 for in-house review, Form 8 for OTC-eligible projects

## Review Path

**Path:** in_house
**Reason:** 'change_of_use' projects require in-house review
**Confidence:** high

## Agency Routing

- **DBI (Building)** (Required): All permitted work
- **Planning** (Required): Change of use, new construction, demolition, exterior changes, or historic resource
- **SFFD (Fire)** (Required): Fire code review — restaurant hood/suppression, new construction, or occupancy change
- **DBI Mechanical/Electrical** (Required): HVAC, electrical, or commercial kitchen systems

## Special Requirements

- **Section 311 notification:** 30-day neighborhood notification period (cannot go OTC during notification)

## Confidence Summary

- overall: high
- form_selection: high
- review_path: high
- agency_routing: high
- documents: high

## Gaps / Caveats

- No address provided — cannot check zoning, historic status, or neighborhood-specific rules

### Estimated Fees

# Fee Estimate

**Construction Valuation:** $350,000
**Permit Category:** alterations

## DBI Building Permit Fees (Table 1A-A)

| Fee Component | Amount |
|--------------|--------|
| Plan Review Fee | $6,135.50 |
| Permit Issuance Fee | $2,116.50 |
| CBSC Fee | $14.00 |
| SMIP Fee | $45.50 |
| **Total DBI Fees** | **$8,311.50** |

*Fee tier: $200,001 to $500,000*

## Additional Fees (estimated)

- School Impact Fee (SFUSD): varies by floor area increase

## Statistical Context (DuckDB)

Similar permits (11,405 in database):
- 25th percentile cost: $210,806
- Median cost: $300,000
- 75th percentile cost: $410,000
- Filtered to: Financial District/South Beach

## Notes

- Fee schedule effective 9/1/2025 (Ord. 126-25)
- DBI may adjust valuation per DBI Cost Schedule
- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total
- Fees subject to periodic update — verify against current DBI schedule

**Confidence:** high

### Estimated Timeline

# Timeline Estimate

**Permit Type:** alterations
**Neighborhood:** Financial District/South Beach
**Review Path:** in_house
**Cost Bracket:** 150k_500k

## Filing to Issuance

| Percentile | Days |
|-----------|------|
| 25th (optimistic) | 20 |
| 50th (typical) | 35 |
| 75th (conservative) | 63 |
| 90th (worst case) | 116 |

*Sample size: 5,559 permits*

## Issuance to Completion

- Typical (p50): 163 days
- Conservative (p75): 308 days

## Recent Trend

- Recent 6 months: 41 days avg (46 permits)
- Prior 12 months: 80 days avg (119 permits)
- Trend: **faster** (-48.0%)

**Confidence:** high

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

1. [ ] Disabled Access Compliance Checklist (required for ALL commercial TI)
2. [ ] Disabled Access Upgrade Documentation

## Electronic Plan Review (EPR) Requirements

*All plans must be submitted electronically as of January 1, 2024*

- PDF format required: All construction plans must be submitted as PDF files
- Vector-based PDF preferred: PDF should be created from CAD/BIM software, not scanned images. Scanned PDFs may be rejected or cause review delays.
- Unlocked PDF (no password protection): PDFs must not have security restrictions that prevent markup, commenting, or printing
- Fonts embedded: All fonts must be embedded in the PDF to ensure correct rendering across systems
- Bookmarks for each sheet: PDF must contain bookmarks corresponding to each sheet for navigation during plan review
- Minimum sheet size: Plans must be at minimum 11x17 inches per completeness checklist; full plan sets typically 22x34 inches or 24x36 inches
- Back Check page required: All plan sets must include a Back Check page for reviewer corrections tracking

## Pre-Submission Checklist

- [ ] All sheets bookmarked in PDF
- [ ] No security restrictions on PDF file
- [ ] Proper layering (demolition, new work, existing to remain)
- [ ] Title block with permit application number on each sheet
- [ ] Prepared by licensed architect or engineer (stamp and signature)
- [ ] Construction cost estimate included
- [ ] Title 24 energy compliance forms attached
- [ ] Green Building form (GS1-GS6) attached as applicable
- [ ] Back Check page included

## Pro Tips

- Obtain Planning approval BEFORE submitting building permit application
- Expect 3 rounds of completeness review — 3rd round escalates to supervisor
- Include a Back Check page in all plan sets

**Confidence:** high

### Revision Risk

# Revision Risk Assessment

**Permit Type:** alterations
**Neighborhood:** Financial District/South Beach
**Project Type:** commercial_ti
**Review Path:** in_house

## Revision Probability

**Risk Level:** MODERATE
**Revision Rate:** 11.4% of permits had cost increases during review
**Sample Size:** 38,952 permits analyzed

## Cost Impact

- Average cost increase when revisions occur: **1076845.7%**
- Permits with cost increase: 4,443

## Timeline Impact

- Average days to issuance (no revisions): 47
- Average days to issuance (with revisions): 70
- **Revision penalty: +23 days on average**
- 90th percentile (worst case): 105 days

## Common Revision Triggers

1. Disabled access compliance checklist incomplete
2. ADA path-of-travel calculations missing
3. HVAC load calculations not provided
4. Fire separation between tenants not addressed

## Mitigation Strategies

- Engage licensed professional experienced with SF DBI requirements
- Use the completeness checklist (tier1/completeness-checklist.json) before submission
- Include a Back Check page in all plan sets
- Ensure Title-24 energy compliance is complete before submission
- Verify plan description matches permit application exactly

## Questions for Expert Review

- What are the most common plan check correction items for this project type?
- Are there specific reviewers known for particular requirements?
- What pre-submission meetings (if any) could reduce revision rounds?

**Confidence:** high

---

## Scenario D: Restaurant Conversion (Mission, $250K)

### Predicted Permits

# Permit Prediction

**Project:** Convert 1,500 sq ft retail space to restaurant in the Mission. Need grease trap, hood ventilation, ADA compliance, new signage.
**Estimated Cost:** $250,000
**Square Footage:** 1,500

**Detected Project Types:** restaurant, commercial_ti
**Matched Concepts:** change_of_use, commercial_kitchen_hood, commercial_ti, disability_access, restaurant

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
- **Planning** (Required): Change of use, new construction, demolition, exterior changes, or historic resource
- **SFFD (Fire)** (Required): Fire code review — restaurant hood/suppression, new construction, or occupancy change
- **DPH (Public Health)** (Required): Health permit for food service establishment
- **DBI Mechanical/Electrical** (Required): HVAC, electrical, or commercial kitchen systems
- **SFPUC** (Conditional): New plumbing fixtures or water service
- **DPW/BSM** (Conditional): Work in or adjacent to public right-of-way

## Special Requirements

- **Planning zoning verification:** Confirm restaurant use is permitted at site
- **DPH health permit application:** Food preparation workflow diagram + equipment schedule
- **Type I hood fire suppression:** Automatic suppression system for grease-producing equipment
- **Grease interceptor sizing:** Grease trap calculations per plumbing code
- **ADA compliance:** Path of travel and restroom upgrades per CBC Chapter 11B

## Confidence Summary

- overall: medium
- form_selection: high
- review_path: high
- agency_routing: high
- documents: high

## Gaps / Caveats

- No address provided — cannot check zoning, historic status, or neighborhood-specific rules

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

## Additional Fees (estimated)

- Plumbing permit (Category 6PA/6PB): $543-$1,525
- DPH health permit: varies
- SFFD plan review: per Table 107-B

## Statistical Context (DuckDB)

Similar permits (2,064 in database):
- 25th percentile cost: $150,000
- Median cost: $200,000
- 75th percentile cost: $300,000
- Filtered to: Mission

## Notes

- Fee schedule effective 9/1/2025 (Ord. 126-25)
- DBI may adjust valuation per DBI Cost Schedule
- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total
- Fees subject to periodic update — verify against current DBI schedule

**Confidence:** high

### Estimated Timeline

# Timeline Estimate

**Permit Type:** alterations
**Neighborhood:** Mission
**Review Path:** in_house
**Cost Bracket:** 150k_500k

## Filing to Issuance

| Percentile | Days |
|-----------|------|
| 25th (optimistic) | 77 |
| 50th (typical) | 169 |
| 75th (conservative) | 329 |
| 90th (worst case) | 514 |

*Sample size: 719 permits*

## Issuance to Completion

- Typical (p50): 163 days
- Conservative (p75): 308 days

## Recent Trend

- Recent 6 months: 28 days avg (16 permits)
- Prior 12 months: 114 days avg (71 permits)
- Trend: **faster** (-75.8%)

## Additional Delay Factors

- **change_of_use**: +30 days minimum: Section 311 neighborhood notification
- **dph_review**: +2-4 weeks: DPH health permit review (food service)
- **fire_review**: +1-3 weeks: Fire Department plan review

**Confidence:** high

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
3. [ ] Fire suppression system plans
4. [ ] Occupancy load calculations
5. [ ] Fire flow study (new construction)
6. [ ] Health permit application
7. [ ] Food preparation workflow diagram
8. [ ] Equipment schedule with specifications
9. [ ] Street space permit application
10. [ ] Public right-of-way plans

## Project-Specific Requirements

1. [ ] Use change justification letter
2. [ ] Existing and proposed occupancy documentation
3. [ ] Grease interceptor sizing calculations
4. [ ] Kitchen layout with equipment schedule
5. [ ] Type I hood specifications and fire suppression details
6. [ ] Ventilation calculations for commercial kitchen
7. [ ] DPH health permit application

## Electronic Plan Review (EPR) Requirements

*All plans must be submitted electronically as of January 1, 2024*

- PDF format required: All construction plans must be submitted as PDF files
- Vector-based PDF preferred: PDF should be created from CAD/BIM software, not scanned images. Scanned PDFs may be rejected or cause review delays.
- Unlocked PDF (no password protection): PDFs must not have security restrictions that prevent markup, commenting, or printing
- Fonts embedded: All fonts must be embedded in the PDF to ensure correct rendering across systems
- Bookmarks for each sheet: PDF must contain bookmarks corresponding to each sheet for navigation during plan review
- Minimum sheet size: Plans must be at minimum 11x17 inches per completeness checklist; full plan sets typically 22x34 inches or 24x36 inches
- Back Check page required: All plan sets must include a Back Check page for reviewer corrections tracking

## Pre-Submission Checklist

- [ ] All sheets bookmarked in PDF
- [ ] No security restrictions on PDF file
- [ ] Proper layering (demolition, new work, existing to remain)
- [ ] Title block with permit application number on each sheet
- [ ] Prepared by licensed architect or engineer (stamp and signature)
- [ ] Construction cost estimate included
- [ ] Title 24 energy compliance forms attached
- [ ] Green Building form (GS1-GS6) attached as applicable
- [ ] Back Check page included

## Pro Tips

- Obtain Planning approval BEFORE submitting building permit application
- Expect 3 rounds of completeness review — 3rd round escalates to supervisor
- Include a Back Check page in all plan sets
- Visit Planning FIRST to confirm restaurant use is permitted at your site
- Separate electrical and plumbing permits needed after building permit

**Confidence:** high

### Revision Risk

# Revision Risk Assessment

**Permit Type:** alterations
**Neighborhood:** Mission
**Project Type:** restaurant
**Review Path:** in_house

## Revision Probability

**Risk Level:** MODERATE
**Revision Rate:** 19.7% of permits had cost increases during review
**Sample Size:** 10,979 permits analyzed

## Cost Impact

- Average cost increase when revisions occur: **900141.9%**
- Permits with cost increase: 2,163

## Timeline Impact

- Average days to issuance (no revisions): 94
- Average days to issuance (with revisions): 213
- **Revision penalty: +119 days on average**
- 90th percentile (worst case): 310 days

## Common Revision Triggers

1. Incomplete grease interceptor sizing calculations
2. Missing Type I hood fire suppression details
3. DPH health permit requirements not addressed in initial plans
4. Inadequate ventilation calculations for commercial kitchen
5. ADA path-of-travel calculations missing or insufficient

## Mitigation Strategies

- Have DPH review requirements addressed in initial plan submission
- Include complete grease interceptor calculations with first submittal
- Engage licensed professional experienced with SF DBI requirements
- Use the completeness checklist (tier1/completeness-checklist.json) before submission
- Include a Back Check page in all plan sets
- Ensure Title-24 energy compliance is complete before submission
- Verify plan description matches permit application exactly

## Questions for Expert Review

- What are the most common plan check correction items for this project type?
- Are there specific reviewers known for particular requirements?
- What pre-submission meetings (if any) could reduce revision rounds?

**Confidence:** high

---

## Scenario E: Historic Building Renovation (Pacific Heights, $2.5M)

### Predicted Permits

# Permit Prediction

**Project:** Major renovation of a 1906 building in Pacific Heights, historic district. Seismic retrofit, all new mechanical/electrical/plumbing systems, adding an elevator.
**Estimated Cost:** $2,500,000
**Square Footage:** 5,000

**Detected Project Types:** seismic, commercial_ti, historic
**Matched Concepts:** commercial_ti, historic_preservation, seismic

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

- **Structural engineering report:** Licensed structural engineer evaluation
- **Priority processing eligibility:** Voluntary/mandatory seismic upgrades per AB-004
- **Historic preservation review:** Certificate of Appropriateness from HPC (Article 10) or Permit to Alter (Article 11)
- **Secretary of Interior Standards:** All work must comply with SOI Standards for Treatment of Historic Properties

## Confidence Summary

- overall: high
- form_selection: high
- review_path: high
- agency_routing: high
- documents: high

## Gaps / Caveats

- No address provided — cannot check zoning, historic status, or neighborhood-specific rules

### Estimated Fees

# Fee Estimate

**Construction Valuation:** $2,500,000
**Permit Category:** alterations

## DBI Building Permit Fees (Table 1A-A)

| Fee Component | Amount |
|--------------|--------|
| Plan Review Fee | $25,568.00 |
| Permit Issuance Fee | $8,832.00 |
| CBSC Fee | $100.00 |
| SMIP Fee | $325.00 |
| **Total DBI Fees** | **$34,825.00** |

*Fee tier: $1,000,001 to $5,000,000*

## Statistical Context (DuckDB)

Similar permits (104 in database):
- 25th percentile cost: $1,516,500
- Median cost: $2,000,000
- 75th percentile cost: $2,500,000
- Filtered to: Pacific Heights

## Notes

- Fee schedule effective 9/1/2025 (Ord. 126-25)
- DBI may adjust valuation per DBI Cost Schedule
- Additional agency fees (Planning, SFFD, DPH, DPW) not included in DBI total
- Fees subject to periodic update — verify against current DBI schedule

**Confidence:** high

### Estimated Timeline

# Timeline Estimate

**Permit Type:** alterations
**Neighborhood:** Pacific Heights
**Review Path:** in_house
**Cost Bracket:** over_500k

## Filing to Issuance

| Percentile | Days |
|-----------|------|
| 25th (optimistic) | 112 |
| 50th (typical) | 202 |
| 75th (conservative) | 387 |
| 90th (worst case) | 591 |

*Sample size: 249 permits*

## Issuance to Completion

- Typical (p50): 163 days
- Conservative (p75): 308 days

## Recent Trend

- Recent 6 months: 67 days avg (10 permits)
- Prior 12 months: 104 days avg (43 permits)
- Trend: **faster** (-35.7%)

## Additional Delay Factors

- **historic**: +4-12 weeks: Historic preservation review (HPC)
- **planning_review**: +2-6 weeks: Planning Department review

**Confidence:** high

### Required Documents

# Required Documents Checklist

**Forms:** Form 3/8
**Review Path:** in_house

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
6. [ ] SFPUC fixture count form
7. [ ] Stormwater Management Plan (if 5,000+ sq ft impervious surfaces)

## Project-Specific Requirements

1. [ ] Secretary of Interior Standards compliance documentation
2. [ ] Historic resource evaluation
3. [ ] Certificate of Appropriateness application (Article 10) or Permit to Alter (Article 11)
4. [ ] Structural engineering report by licensed SE
5. [ ] Geotechnical investigation (if required by site conditions)
6. [ ] Seismic retrofit design drawings

## Electronic Plan Review (EPR) Requirements

*All plans must be submitted electronically as of January 1, 2024*

- PDF format required: All construction plans must be submitted as PDF files
- Vector-based PDF preferred: PDF should be created from CAD/BIM software, not scanned images. Scanned PDFs may be rejected or cause review delays.
- Unlocked PDF (no password protection): PDFs must not have security restrictions that prevent markup, commenting, or printing
- Fonts embedded: All fonts must be embedded in the PDF to ensure correct rendering across systems
- Bookmarks for each sheet: PDF must contain bookmarks corresponding to each sheet for navigation during plan review
- Minimum sheet size: Plans must be at minimum 11x17 inches per completeness checklist; full plan sets typically 22x34 inches or 24x36 inches
- Back Check page required: All plan sets must include a Back Check page for reviewer corrections tracking

## Pre-Submission Checklist

- [ ] All sheets bookmarked in PDF
- [ ] No security restrictions on PDF file
- [ ] Proper layering (demolition, new work, existing to remain)
- [ ] Title block with permit application number on each sheet
- [ ] Prepared by licensed architect or engineer (stamp and signature)
- [ ] Construction cost estimate included
- [ ] Title 24 energy compliance forms attached
- [ ] Green Building form (GS1-GS6) attached as applicable
- [ ] Back Check page included

## Pro Tips

- Obtain Planning approval BEFORE submitting building permit application
- Expect 3 rounds of completeness review — 3rd round escalates to supervisor
- Include a Back Check page in all plan sets
- HPC review happens BEFORE any other Planning approval — start early

**Confidence:** high

### Revision Risk

# Revision Risk Assessment

**Permit Type:** alterations
**Neighborhood:** Pacific Heights
**Review Path:** in_house

## Revision Probability

**Risk Level:** MODERATE
**Revision Rate:** 16.1% of permits had cost increases during review
**Sample Size:** 7,155 permits analyzed

## Cost Impact

- Average cost increase when revisions occur: **318308.1%**
- Permits with cost increase: 1,150

## Timeline Impact

- Average days to issuance (no revisions): 94
- Average days to issuance (with revisions): 209
- **Revision penalty: +115 days on average**
- 90th percentile (worst case): 294 days

## Common Revision Triggers

1. Incomplete Title-24 energy compliance documentation
2. Missing ADA path-of-travel calculations
3. Structural calculations missing or insufficient
4. Site plan discrepancies with existing conditions
5. Plans not matching permit application description

## Mitigation Strategies

- Engage licensed professional experienced with SF DBI requirements
- Use the completeness checklist (tier1/completeness-checklist.json) before submission
- Include a Back Check page in all plan sets
- Ensure Title-24 energy compliance is complete before submission
- Verify plan description matches permit application exactly

## Questions for Expert Review

- What are the most common plan check correction items for this project type?
- Are there specific reviewers known for particular requirements?
- What pre-submission meetings (if any) could reduce revision rounds?

**Confidence:** high
