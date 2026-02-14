# Amy Lee Interview Packet
## djarvis SF Permitting Knowledge Validation

**Prepared for**: Tim Brenneman → Amy Lee (Eun Young Lee)
**Date**: February 14, 2026
**Purpose**: Validate our machine-readable SF permitting knowledge base and surface the knowledge that isn't in any document

---

## What We've Built

We've machine-ingested essentially the entire published regulatory corpus for SF building permits:

- **Complete SF Planning Code** (222,000 lines) — parsed into structured decision logic for all 6 Planning review pathways
- **Complete Building Inspection Commission Codes** — Building Code, Existing Building Code, Electrical, Mechanical, Plumbing, Green Building, Housing Code
- **Complete 2022 Fire Code** — all SF amendments to California Fire Code
- **All 40+ Administrative Bulletins** in full text — from AB-001 through AB-113
- **All 19 fee tables** (Tables 1A-A through 1A-S) — building permit fees, plan review fees, hourly rates, electrical, plumbing/mechanical, inspections, penalties
- **51 DBI Information Sheets** (G, DA, FS, S series) — all OCR'd and extracted
- **G-20 Routing Matrix** — 154 project-type entries across 9 reviewing agencies
- **OTC eligibility criteria** — 55 project types classified (12 no-plan, 24 with-plan, 19 not-OTC)
- **SF Ethics Commission Permit Consultant Registry** — 167 filings, 115 registered consultants

This is structured into a **7-step decision tree**: need_permit → which_form → otc_or_inhouse → agency_routing → required_docs → timeline → fees

**What we can't get from documents is what's in your head.** That's why we're here.

---

## Part 1: We Show You What We Know — You Tell Us Where We're Wrong

These aren't open-ended questions. We're making specific claims based on the code. Correct us.

### Claim 1: OTC Routing Logic
We believe the OTC/in-house split works like this:

> A project goes OTC if it's on the published OTC list AND the plan reviewer at the counter estimates they can review it in roughly 1 hour per station. Otherwise it gets routed to in-house review.

Specific cases we're uncertain about:
- **Kitchen remodel that moves the sink but doesn't touch walls**: OTC-with-plans per the published list, but does moving the sink trigger DPW/PUC review for plumbing relocation, which bumps it to in-house?
- **Window replacement on a building in an Article 10 historic district**: OTC-eligible project type, but Article 10 requires a Certificate of Appropriateness. Does this go OTC at DBI but with a separate Planning/HPC approval? Or does the historic status route the entire permit to in-house?
- **Commercial TI under 2,000 sq ft in a C-3 zone**: OTC-eligible per the list, but Section 309 requires Planning Commission review for C-3 projects that need exceptions. At what square footage or scope does this practically stop being OTC?

### Claim 2: Fee Calculation
From Table 1A-A of the Building Code, we've extracted the valuation-based fee tiers. For a project valued at $100,001-$500,000:

> Base fee = $1,809.00 + $8.60 per additional $1,000 over $100,000. Plan review fee = 65% of building permit fee.

- Is this the formula you actually use, or is there a simpler rule of thumb?
- When your clients get hit with fees significantly higher than the Table 1A-A calculation, what's the source? (Surcharges? Technology fees? Agency-specific fees not in the tables?)
- The tables list 19 fee categories (1A-A through 1A-S). For a typical residential remodel, which tables actually apply? Just 1A-A and 1A-B, or do others get triggered?

### Claim 3: Planning Review Pathways
From our Planning Code analysis, we've mapped 6 pathways. Our understanding of the fastest path through Planning:

> A project gets Planning OTC approval if: (1) the use is principally permitted in the zoning district, (2) it doesn't trigger Section 311 notification thresholds, (3) the property is not a historic resource or the work is exempt under Section 1005(e)/1110(g), (4) no residential units are being removed, (5) it's not in C-3 requiring Section 309 review, (6) it's fully code-compliant.

- Is this the mental checklist you run? What do you check first?
- Section 311 notification is 30 days. How often does that 30 days actually turn into a DR request? What percentage — 5%? 20%?
- When a project needs a Conditional Use hearing, what's the realistic calendar wait for a Planning Commission slot? The code says 90 days from application to hearing — is that real?

### Claim 4: Fire Department Triggers
From Chapter 9 of the 2022 Fire Code, we believe SFFD review is triggered by:

> Assembly occupancy (A-2 restaurants ≥50 occupants), high-rise (>75 ft), new sprinkler systems, commercial kitchen hood systems (Type I), changes in occupancy classification, nightclubs/bars, any project requiring fire alarm modifications.

- What are we missing? Are there common project types that unexpectedly trigger SFFD review?
- The G-20 routing matrix uses "//" for Fire. Is their review typically fast, or does it cause delays?
- For restaurants: does SFFD review the hood system at plan review, or is it a separate inspection cycle?

### Claim 5: Agency Routing for a Restaurant Build-Out
For a restaurant conversion in an NC-2 district (vacant retail → 80-seat restaurant with Type I hood, per the G-20 routing matrix), we predict these agency reviews:

| Agency | Reason | Est. Timeline |
|--------|--------|---------------|
| Planning (CP-ZOC) | Change of use (retail → restaurant). If restaurant is principally permitted in NC-2, no CU needed. Section 311 notification likely triggered. | 30-60 days |
| Fire Prevention (SFFD) | Assembly occupancy A-2, Type I hood system, fire suppression | 2-4 weeks |
| Public Health (DPH) | Food preparation, commercial kitchen | 2-4 weeks |
| DPW-Streets (BSM) | If parklet seating involves sidewalk use | 2-4 weeks |
| MOD (Disability) | Commercial/public accommodation ADA compliance | 1-2 weeks |

- How close is this? What are we getting wrong on the agencies or timelines?
- Does the liquor license (Type 47) affect the building permit process at all, or is that an entirely separate ABC track?
- NC-2 districts: is a restaurant principally permitted, or does it need CU? (We believe principally permitted if under a certain size threshold.)

---

## Part 2: The Stuff That's Not in Any Document

### Q6. Your First 60 Seconds
When a new client calls and says "I want to remodel my kitchen" — what's the first question out of your mouth? Walk us through the first 60 seconds of that conversation. We want to build the AI intake flow to mirror exactly what you do.

### Q7. The Real Rejection List
The completeness checklist has 13 sections. But what actually gets applications bounced back?
- What are the top 3 specific items that cause rejections — not categories, specific things like "forgot to include X on the cover sheet" or "valuation doesn't match scope"?
- When DBI says "completeness review can take up to 3 rounds" — what percentage of first submissions pass on the first try? 10%? 50%?

### Q8. Timeline Reality Check
SF.gov says in-house review takes ~4 weeks after filing fee paid. AB-004 describes priority processing.
- What's the real timeline for a typical residential alteration from application to approved permit? 4 weeks? 8 weeks? 12 weeks?
- What's the single action a client can take to shave the most time off?
- Do you ever use priority processing (AB-004)? When is it worth the extra fee?

### Q9. The Gotchas
Every experienced expediter has a mental list of things that aren't in any AB or info sheet. Things like:
- "Always do X before Y even though the website says the order doesn't matter"
- "If you're in [neighborhood], watch out for [thing]"
- "The form says optional but if you don't include it, they'll bounce you"
- "This fee exists but it's not on any published schedule"

Give us your top 5. These become the most valuable part of our AI.

### Q10. Process Changes in the Last 12 Months
The codes we've ingested are current through late 2025. But processes change faster than codes update.
- Any major changes to how DBI operates day-to-day that aren't reflected in published docs?
- Has the shift to 100% Electronic Plan Review (Bluebeam) since Jan 2024 changed anything about how you prepare submissions?
- Any new requirements, unofficial policies, or staffing changes that affect turnaround?

---

## Part 3: Stress-Test Scenarios

For each scenario, we'll show you our system's prediction. Tell us what we got right and wrong.

### Scenario 1: Kitchen Remodel — Sunset District
**Project**: Reconfigure layout (move sink, add island), replace cabinets/counters, add 6 recessed lights. No structural changes, no wall removal.

**Our prediction**:
- Form 8 (OTC with plans)
- Agencies: Planning (X), possibly MOD (O) if multi-unit
- OTC-eligible, same-day if plans are straightforward
- Est. fees: ~$1,500-2,500 based on $40-60K construction value (Table 1A-A)
- Key risk: Moving the sink requires plumbing permit — does this need a separate Form 6?

### Scenario 2: ADU Over Garage — Noe Valley
**Project**: 600 sq ft ADU above existing detached garage. New second story, kitchen, bathroom, separate entrance.

**Our prediction**:
- Form 2 (Addition/Alteration)
- NOT OTC — ADU is explicitly on the "not-OTC" list
- Agencies: Planning (Section 207.2 ADU provisions — exempt from Section 311), SFFD (new occupancy), DPW/PUC (new sewer/water connections), MOD
- In-house review: 8-16 weeks
- Est. fees: $5,000-12,000 based on $150-250K construction value
- Planning may be fast: ADUs are exempt from Section 311 notification and many historic review requirements per Sections 1005(e) and 1110(g)
- Key risk: Structural engineering for second-story addition. AB-082 structural design review may apply.

### Scenario 3: Commercial TI — Financial District (C-3)
**Project**: 5,000 sq ft office build-out: open office, 2 conference rooms, kitchen/break area with commercial sink, ADA bathroom reno, data closet with HVAC.

**Our prediction**:
- Form 2 (Alteration)
- OTC-eligible for commercial TI per the list, but C-3 zone may complicate
- Agencies: Planning (Section 309 applies in C-3 — but for a TI with no exterior changes, may be administrative), SFFD (if fire alarm modifications), MOD (commercial ADA), DPH (if "commercial sink" qualifies as food prep)
- Key question: Does the commercial sink in the break area trigger DPH review? Where's the line between "office break room" and "food preparation"?

### Scenario 4: Restaurant Conversion — Mission (NC-2)
**Project**: Vacant retail → 80-seat restaurant. Full commercial kitchen, Type I hood, outdoor parklet, liquor license.

**Our prediction**:
- Form 2 (Alteration) + possibly Form 6 for sprinkler work
- NOT OTC — change of use with commercial kitchen
- Agencies: Planning (change of use, Section 311 notification, possible CU for formula retail or late-night), SFFD (A-2 occupancy, Type I hood, fire suppression, occupant load ≥50), DPH (food prep, commercial kitchen), DPW (parklet/sidewalk), MOD (public accommodation), possibly Environment (Maher Ordinance if contamination history)
- In-house review: 12-20 weeks
- Key risk: The 80-seat occupant load triggers Assembly occupancy classification. Does this require a Certificate of Occupancy change? What does that add to the timeline?

### Scenario 5: Historic Building Renovation — Pacific Heights Landmark
**Project**: 1920s landmark site. Seismic retrofit (soft story per AB-094), kitchen/bath modernization on 3 floors, new double-pane windows, roof deck addition, solar panels.

**Our prediction**:
- Form 2 (Alteration)
- NOT OTC — landmark site + major scope
- Agencies: Planning/HPC (Article 10 Certificate of Appropriateness for exterior work — windows, roof deck, solar. Interior work may be exempt per Section 1005(e) if no exterior impact), SFFD (if sprinkler modifications), MOD (if multi-unit), DPW
- HPC review required for: window replacement (exterior change), roof deck (new addition), solar panels (visible from street?)
- HPC may NOT be required for: interior kitchen/bath work, seismic retrofit (structural, not aesthetic)
- Soft story retrofit per AB-094: voluntary program with specific engineering criteria
- Key risk: Window replacement on a landmark. Even energy-efficient upgrades must match historic character per Secretary of Interior's Standards. AB-013 (historic building disabled access) may also apply.
- Est. timeline: 16-24 weeks minimum. HPC hearing alone could take 8-12 weeks.

---

## Part 4: Your Competitive Landscape

We pulled your public data. No surprises here — just context for the conversation.

- **You**: Eun Young (Amy) Lee, 3S LLC. Ethics Commission registered since October 2019. 5 filings (most recent Dec 2024, amendment). DBI contacts database shows 117 permits as "pmt consultant/expediter" — **rank #42 in SF**.
- **Your team**: Jerry Sanguinetti, Mark Luellen, Michie Wong, Simon Tam (all registered under 3S LLC)
- **Market**: Top expediter is Danielle Romero (1,702 permits). Top firm by Ethics Commission filings is Reuben, Junius & Rose (29 filings). The top 5 expediters handle more permits than the bottom 30 combined. Median for top 50 is 182 permits.
- **Our perspective**: You're well-positioned. Solid mid-market practice with a diverse team. The AI tool we're building would be most valuable for someone at your scale — amplifying your capacity without needing Danielle Romero's volume to justify it.

---

## What Happens Next

1. We update the decision tree with your corrections (same day)
2. We build automated test cases from your scenario answers
3. Your "gotchas" become the highest-value rules in the AI
4. We build a prototype you can test on a real case
5. If it saves you time on even one permit, we've proven the concept

The goal: **an AI that knows what you know, available 24/7, that makes you faster** — not one that replaces you.

---

*This packet was assembled by ingesting and structuring the complete published SF permitting regulatory corpus: Planning Code (222K lines), Building Inspection Commission Codes (58K lines), Fire Code, 40+ Administrative Bulletins, 51 DBI information sheets, 19 fee tables, G-20 routing matrix (154 entries), and the SF Ethics Commission permit consultant registry. Total knowledge base: ~4.3MB raw text + ~500K structured JSON.*
