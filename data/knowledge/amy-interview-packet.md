# Amy Lee Interview Packet
## djarvis SF Permitting Knowledge Validation

**Prepared for**: Tim Brenneman → Amy Lee (Eun Young Lee)
**Date**: February 14, 2026
**Purpose**: Validate our machine-readable SF permitting knowledge base before building the djarvis AI assistant

---

## Background for Amy

We're building **djarvis**, an AI-powered assistant that helps people navigate SF's building permit process. Think of it as a knowledgeable friend who can answer questions like "Do I need a permit for X?" and "What forms do I need?" — the kind of guidance you provide your clients every day.

We've ingested a large body of DBI documentation and structured it into a decision tree. Before we build the AI on top of it, we need your expert eye to validate whether we've gotten the rules right, and to fill in the gaps that aren't well-documented.

**What we have so far:**
- 51 DBI information sheets (all series: G, DA, FS, S)
- 6 Administrative Bulletins (AB-004, 005, 032, 093, 110, 112)
- Complete SF Planning Code (12.6MB)
- G-20 routing matrix (154 entries across 9 agencies)
- OTC eligibility criteria (55 project types classified)
- Residential completeness checklist (13 sections)
- 7-step decision tree: need_permit → which_form → otc_or_inhouse → agency_routing → required_docs → timeline → fees

---

## Part 1: Process & Decision Questions

These help us validate the core decision tree logic.

### Q1. OTC vs In-House Review
We found that DBI classifies projects into three categories for OTC eligibility:
- **12 project types**: OTC without plans (re-roofing, in-kind kitchen/bath, water heater, etc.)
- **24 project types**: OTC with plans (layout-changing remodels, new windows, commercial TI, etc.)
- **19 project types**: NOT OTC / requires In-House Review (ADU, unit changes, hillside, excavation, etc.)

And the key routing criterion is the **"one-hour rule"** — if plan review can't be done in about 1 hour per station, it goes to in-house.

**Questions:**
- Does this match your experience? Are there project types that *should* be OTC but routinely get bumped to in-house?
- How strictly is the one-hour rule applied? Do specific plan reviewers interpret it differently?
- Are there any OTC-eligible project types that you'd recommend clients always do in-house instead? (e.g., to avoid counter wait times or because of hidden complexity?)

### Q2. Initial Client Intake
When a new client describes their project:
- What are the first 3-5 questions you always ask?
- What's the minimum information you need to tell them which permit path they're on?
- At what point can you give a confident "this is OTC" vs "this needs in-house review"?

### Q3. Top Rejection Reasons
- What are the top 5 reasons building permit applications get rejected or sent back during completeness review?
- Are there common mistakes that even experienced architects make?
- What percentage of first submissions pass completeness review on the first try?

### Q4. Timeline Estimation
Our decision tree has limited timeline data. We know:
- OTC: same day (if wait times allow)
- In-house: ~4 weeks after filing fee paid (per sf.gov)
- Priority permits per AB-004 have expedited timelines

**Questions:**
- What are realistic timeline ranges you tell clients for: residential kitchen remodel, bathroom remodel, ADU, commercial TI, new construction?
- What's the single biggest cause of delays?
- How much does Planning review add to timelines?
- Are there seasonal patterns (slower months, busier months)?

---

## Part 2: Fee & Cost Questions

### Q5. Fee Calculation
G-13 (DBI Cost Schedule) is our fee reference. We've OCR'd it but haven't fully structured it.
- How do you estimate permit fees for a client before they apply?
- Is there a rule of thumb (e.g., percentage of construction cost)?
- What's the typical fee range for: kitchen remodel, ADU, commercial TI, new construction?

### Q6. Unexpected Fees
- What fees catch clients off guard?
- Are there agency-specific fees that aren't obvious from the application? (Planning, Fire, DPH, etc.)
- How have fees changed in the past 2-3 years?

---

## Part 3: Agency Routing Questions

Our G-20 routing matrix maps 154 project types to 9 reviewing agencies. Here's the simplified routing:

| Agency | Code | Triggers (simplified) |
|--------|------|-----------------------|
| Planning (CP-ZOC) | X | Almost all projects except minor mechanical/plumbing |
| DPW-Streets (BSM) | # | Sidewalk, curb cuts, grading, street frontage work |
| DPW-Forestry (BUF) | * | Tree removal, protected trees, street trees |
| PUC | ^ | Sewer connections, stormwater, water service |
| Fire Prevention (SFFD) | // | Assembly occupancy, high-rise, sprinklers, hood systems |
| Public Health (DPH) | + | Restaurants, food handling, tattoo, body art |
| MOD (Disability) | O | Commercial, public accommodation, multifamily |
| OCII | OCII | Redevelopment areas (Mission Bay, Hunters Point, Transbay) |
| Environment | ENV | Maher Ordinance (hazardous materials sites) |

### Q7. Agency Delays
- Which agency reviews cause the most delays?
- Is Planning consistently the longest? Or does it depend on the project type?
- Are there agencies that are "rubber stamp" fast?

### Q8. Planning Review
From our Planning Code analysis, we've identified 6 review pathways:
1. **OTC** — principally permitted use, no Section 311 triggers, no historic, code-compliant
2. **Section 311 Notification** — 30-day notice period, potential DR request
3. **Conditional Use Hearing** — Planning Commission (uses requiring CU, formula retail, unit removal under Section 317)
4. **Section 309/329 Review** — C-3 districts (>120ft) or Eastern Neighborhoods large projects
5. **Historic Preservation Review** — Article 10/11 landmarks, historic districts, conservation districts
6. **Variance** — Zoning Administrator hearing for code non-compliance

**Questions:**
- For what percentage of your projects is Planning review the critical path?
- What types of projects typically skip Planning entirely?
- How does the new requirement (Planning approval BEFORE filing for building permit) change your workflow?
- Section 311 has a 30-day notification period. In practice, how often does a DR (Discretionary Review) request get filed? How does that change the timeline?

### Q9. OCII Routing
- How often do you deal with OCII routing in practice?
- Is it mainly Mission Bay and Hunters Point, or are there other areas?
- Any tips for OCII projects?

---

## Part 4: Stress-Test Scenarios

For each scenario below, walk us through how you'd handle it — what questions you'd ask, which permit path, what forms, what agencies, and realistic timeline.

### Scenario 1: Kitchen Remodel (Residential)
A homeowner in the Sunset District wants to:
- Reconfigure kitchen layout (move sink, add island)
- Replace all cabinets and countertops
- Add recessed lighting (6 fixtures)
- No structural changes, no wall removal

### Scenario 2: ADU Over Garage
A homeowner in Noe Valley wants to build a 600 sq ft ADU above their existing detached garage:
- New second story addition
- New kitchen and bathroom
- Separate entrance from alley
- Existing garage stays as-is below

### Scenario 3: Commercial TI in Downtown
A tech company leasing 5,000 sq ft in a Class B office building in the Financial District (C-3 zone) wants to:
- Build out open office with 2 conference rooms
- New kitchen/break area with commercial sink
- ADA bathroom renovation
- New data closet with dedicated HVAC

### Scenario 4: Restaurant Conversion
A property owner in the Mission (NC-2 zoning) wants to convert a vacant retail space into a restaurant:
- Full commercial kitchen build-out
- 80-seat dining area
- Type I hood system
- Outdoor parklet seating
- Liquor license (Type 47 - on-sale general)

### Scenario 5: Historic Building Renovation
An architect is renovating a 1920s building on a landmark site in Pacific Heights:
- Seismic retrofit (soft story)
- Kitchen and bathroom modernization on 3 floors
- New windows (double-pane replacement)
- Roof deck addition
- Solar panel installation

---

## Part 5: Validation Requests

### V1. Form Selection Logic
We've built a form selection taxonomy. Quick validation:
- **Form 1**: New building construction → correct?
- **Form 2**: Additions / alterations / repairs → correct?
- **Form 3**: Demolition / removal → correct?
- **Form 3A**: Address change → correct?
- **Form 6**: Special application (sign, sprinkler, antenna, sidewalk) → correct?
- **Form 8**: Over-the-counter permit → correct?

Are there cases where the form choice is ambiguous?

### V2. In-House Review Process
SF.gov shows an 11-step process. Is this accurate and complete?
1. Determine what type of permit you need
2. Hire design professional
3. Determine if preliminary project assessment needed
4. Get pre-application meeting (if needed)
5. Prepare permit application
6. Get Planning approval
7. Submit application
8. Pay filing fee
9. Get completeness review
10. Get plan review
11. Pick up approved permit

Anything missing? Any steps that have changed recently?

### V3. Completeness Checklist Spot-Check
Our residential completeness checklist has 13 sections. Does this match what you see in practice?
1. Application completeness
2. Previous apps & characteristics
3. Scope of work
4. Valuation
5. Plan check fees
6. Development review routing (11 departments)
7. Supporting documentation (special inspections, geotech, etc.)
8. Plans - cover sheet
9. Plans - site plan
10. Architectural plans
11. Structural plans
12. Green building sheets
13. Title 24 energy reports

### V4. Your "Gotchas" List
- What are the things that aren't well-documented but every experienced expediter knows?
- Any recent process changes (last 12 months) that the official docs haven't caught up with?
- If you could give one piece of advice to someone building an AI permit assistant, what would it be?

---

## Amy Lee Profile (from public records)

For context, here's what we found about your practice from public data:

- **Name**: Eun Young (Amy) Lee
- **Firm**: 3S LLC
- **Ethics Commission Registration**: Since October 2019 (5 filings through December 2024)
- **DBI Expediter Ranking**: #42 by permit volume (117 permits in DBI contacts database)
- **3S LLC Team**: Jerry Sanguinetti, Mark Luellen, Michie Wong, Simon Tam
- **Market Context**: Top expediter in SF is Danielle Romero (1,702 permits). Top firms by Ethics Commission filings: Reuben, Junius & Rose (29), Lighthouse Public Affairs (23)

---

## Next Steps

After this interview, we plan to:
1. Update our decision tree with your corrections
2. Build validation test cases from your stress-test answers
3. Incorporate your "gotchas" as edge cases in the AI
4. Schedule a follow-up to demo the prototype for your feedback

Thank you for your time, Amy!
