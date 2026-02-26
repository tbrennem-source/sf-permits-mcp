# Model Release Probes — sfpermits.ai

Domain-specific prompts to run against every new Claude release. These test real capabilities that matter for the sfpermits.ai platform.

**How to use:** Run each probe against the new model via claude.ai with the sfpermits MCP server connected. Compare output quality against the baseline notes. Track improvements and regressions.

---

## Category 1: Permit Prediction (3 probes)

### Probe 1.1: Kitchen Remodel in a Victorian

**Prompt:**
```
I want to remodel my kitchen in a 1906 Victorian in the Mission District. I'm moving a gas line, replacing the window over the sink with a larger one, and adding an island with a prep sink. The house is on a 25x100 lot. Estimated cost is $85,000.

What permits do I need, what's the review path, and which agencies will review my plans?
```

**Expected capability:** Should identify building permit (Form 3/8), plumbing permit for the prep sink and gas line, possibly electrical. Should route through DBI Building, potentially SFFD (gas line), and note that a window size change may trigger energy compliance. Should distinguish OTC-eligible vs in-house review components.

**What "better" looks like:** Correctly identifies that a 1906 building in the Mission may be in an historic district, triggering Planning review. Mentions Section 317 demolition thresholds if applicable. Notes that gas line work requires a separate plumbing permit.

**Baseline:** Current Claude correctly predicts building + plumbing permits but sometimes misses the historic district trigger for Mission District Victorians.

### Probe 1.2: ADU Over Garage

**Prompt:**
```
I want to convert my detached garage into an ADU in Noe Valley. The garage is 400 sq ft, single story, on a property with an existing single-family home. I'll add a bathroom, kitchenette, and sleeping area. Estimated cost $150,000.
```

**Expected capability:** Should identify this as an ADU conversion (not new construction), reference AB-017 or current ADU ordinance, predict OTC eligibility under state ADU laws, identify required permits (building, plumbing, electrical), and note fire safety requirements (sprinklers per FS-12/ADU exemption rules).

**What "better" looks like:** Correctly distinguishes between JADU and full ADU based on the detached garage scenario. References the specific fire-safety info sheet (FS-12/ADU sprinkler exemption for units under 750 sq ft). Notes that Noe Valley has specific design guidelines.

**Baseline:** Current Claude handles ADU predictions well but occasionally conflates JADU and ADU requirements.

### Probe 1.3: Commercial Tenant Improvement

**Prompt:**
```
I'm opening a restaurant in a former retail space on Valencia Street in the Mission. The space is 2,400 sq ft. I need a Type I commercial hood, a grease trap, an ADA-compliant restroom, and new electrical for kitchen equipment. Estimated cost $350,000.
```

**Expected capability:** Should predict building permit (Form 3/8), plumbing, electrical, possibly mechanical. Should identify change-of-use trigger (retail to restaurant = Assembly), SFFD review for commercial hood, DPH review for food service, Planning review for Valencia Street neighborhood commercial district. Should note Section 311 notification requirement for change of use.

**What "better" looks like:** References G-25 restaurant permitting FAQ. Identifies the grease interceptor sizing requirement. Notes that Valencia Street has specific planning controls (Valencia Street NCT). Predicts 6+ month timeline due to multi-agency review.

**Baseline:** Current Claude catches the major agencies but sometimes misses the Section 311 notification trigger for change of use.

---

## Category 2: Vision Analysis (2 probes)

### Probe 2.1: EPR Compliance Assessment

**Prompt:**
```
I'm about to submit plans for a residential addition in Pacific Heights. My architect prepared a 12-page plan set. What are the most common EPR compliance issues that would cause rejection, and what should I check before uploading?
```

**Expected capability:** Should enumerate key EPR checks: file size limits (250MB, 350MB for site permit addenda), page dimensions (ARCH D or 24x36), no encryption/password protection, embedded fonts, proper title blocks on every sheet, address visible, professional stamps, sheet indexing on cover page.

**What "better" looks like:** References specific EPR bulletin numbers. Distinguishes between hard failures (encryption, oversized) and soft warnings (missing stamps on preliminary submissions). Notes that Pacific Heights projects often get extra scrutiny from Planning.

**Baseline:** Current Claude lists EPR requirements accurately but doesn't always distinguish hard vs soft failures.

### Probe 2.2: Plan Set Completeness Check

**Prompt:**
```
My plan set for a 3-story residential new construction in SoMa has these sheets: A1 (site plan), A2 (floor plans), A3 (elevations), A4 (sections), S1 (foundation plan), S2 (framing plans). Is this complete enough to submit?
```

**Expected capability:** Should identify missing sheets: cover/index sheet, roof plan, electrical plan, plumbing riser diagram, energy compliance (Title 24), accessibility details, geotechnical report reference, shoring plan (3-story in SoMa likely needs it). Should note that new construction requires more comprehensive documentation than alterations.

**What "better" looks like:** References the DBI completeness checklist by name. Notes that SoMa soil conditions typically require geotechnical investigation. Identifies that a 3-story building triggers specific structural requirements (special inspections per S-series info sheets).

**Baseline:** Current Claude catches most missing sheets but sometimes misses geotechnical and shoring requirements for SoMa new construction.

---

## Category 3: Multi-Source Synthesis (3 probes)

### Probe 3.1: Property Due Diligence Report

**Prompt:**
```
I'm considering buying a property at 1234 Valencia Street. Can you give me a comprehensive due diligence report? Check permits, complaints, violations, inspections, property assessments, and any nearby businesses that might affect the property.
```

**Expected capability:** Should query multiple tools in sequence: property_lookup for assessor data, permit_lookup for permit history, search_complaints for complaint history, search_violations for NOVs, search_inspections for recent inspections, search_businesses for nearby commercial activity. Should synthesize findings into a coherent narrative with risk flags.

**What "better" looks like:** Identifies patterns across data sources (e.g., a complaint that led to a violation that led to a permit). Flags temporal correlations. Notes if the property has unpermitted work indicators (complaints about illegal construction + no matching permit). Compares assessed value trends to neighborhood averages.

**Baseline:** Current Claude queries the right tools but sometimes presents results as a list rather than synthesizing patterns across sources.

### Probe 3.2: Timeline Estimation with Context

**Prompt:**
```
How long will it take to get a permit for a seismic retrofit of a 4-story mixed-use building in Chinatown? The building is pre-1978 unreinforced masonry, estimated cost $800,000. We need Planning review because we're in a historic district.
```

**Expected capability:** Should use estimate_timeline with appropriate triggers (historic, seismic, multi_agency). Should combine station velocity data with delay factors. Should distinguish between the structural permit timeline and any parallel permits needed. Should note that Chinatown historic district adds significant Planning review time.

**What "better" looks like:** References AB-083 (Mandatory Soft Story Retrofit) or the UMB program if applicable. Provides a range with confidence levels. Notes that historic district review can add 4-12 weeks on top of standard building review. Mentions that seismic retrofit projects often have lower revision rates because the scope is well-defined.

**Baseline:** Current Claude produces reasonable timeline estimates but sometimes underestimates historic district delay factors.

### Probe 3.3: Consultant Recommendation with Reasoning

**Prompt:**
```
I need a permit consultant for a complex commercial project at 500 Market Street — it involves change of use, ADA upgrades, and fire suppression system modifications. Who would you recommend and why?
```

**Expected capability:** Should use recommend_consultants with relevant parameters (change_of_use trigger, planning coordination needed). Should explain the scoring criteria: permit volume, neighborhood experience, agency relationship depth, complaint resolution history. Should present top 3-5 recommendations with specific reasoning.

**What "better" looks like:** Cross-references consultant recommendations with entity_network data to show which consultants have worked on similar projects at nearby addresses. Notes which consultants have SFFD experience (critical for fire suppression work). Mentions specific permits the consultant has handled in the Financial District.

**Baseline:** Current Claude returns ranked recommendations but doesn't always explain the scoring dimensions clearly.

---

## Category 4: Entity Reasoning (2 probes)

### Probe 4.1: Contractor Network Analysis

**Prompt:**
```
Search for "Bay Area Construction" and show me their network. Who do they work with most frequently? Are there any unusual patterns in their permit history?
```

**Expected capability:** Should use search_entity to find the entity, then entity_network for connections, then interpret the results. Should identify frequent collaborators (architects, engineers, other contractors), note the geographic concentration of their work, and flag any anomalous patterns (e.g., unusually high concentration with one reviewer, or permits clustered in a short time period).

**What "better" looks like:** Distinguishes between legitimate business relationships (an architect-contractor pair that frequently collaborates) and potentially concerning patterns (a contractor who always gets the same inspector). Uses network_anomalies to contextualize the findings.

**Baseline:** Current Claude navigates the entity tools correctly but sometimes over-interprets coincidental patterns as anomalies.

### Probe 4.2: Entity Resolution Quality

**Prompt:**
```
Search for entity "AMY LEE" — there are likely multiple people with this name in the permit database. How does the system distinguish between them? What confidence level should I assign to entity resolution for common names?
```

**Expected capability:** Should search for Amy Lee, note the number of matches, explain the entity resolution methodology (5-step cascade), and discuss the challenges of common name disambiguation. Should show how the system uses additional signals (company name, address proximity, permit type patterns) to distinguish entities.

**What "better" looks like:** Quantifies the false-positive and false-negative tradeoffs for common names. Explains how the co-occurrence graph helps disambiguate (two "Amy Lee" entities that never share a project are likely different people). References the entity resolution cascade steps by name.

**Baseline:** Current Claude explains the methodology but doesn't always quantify confidence for common name scenarios.

---

## Category 5: Specification Quality (2 probes)

### Probe 5.1: Scenario Evaluation

**Prompt:**
```
Evaluate this behavioral scenario for sfpermits.ai:

SCENARIO: User searches for permits
User: homeowner
Starting state: User is on the search page
Goal: Find permits
Expected outcome: Permits are shown

Is this a good scenario? How would you improve it?
```

**Expected capability:** Should identify that this scenario is too vague — no specific starting state, no specific search criteria, no specific expected outcome format, no edge cases. Should propose a concrete improvement with specific search terms, expected result format, and boundary conditions.

**What "better" looks like:** References the scenario design guide format explicitly. Identifies all 5 weaknesses: vague user persona (which type of homeowner?), underspecified starting state, no search criteria, no result format expectations, no edge cases. Proposes 2-3 concrete improved versions at different specificity levels.

**Baseline:** Current Claude correctly identifies the scenario as too vague but sometimes proposes improvements that are still too generic.

### Probe 5.2: Scenario Coverage Gap Analysis

**Prompt:**
```
Given that sfpermits.ai has tools for permit prediction, timeline estimation, fee estimation, and document checklists, what behavioral scenarios might be missing from the design guide? Focus on edge cases and error states.
```

**Expected capability:** Should propose scenarios for: prediction with insufficient data, timeline estimation for a permit type with no historical data, fee estimation for an unusual project type, document checklist for a project that triggers unusual agency routing. Should also propose scenarios for tool interaction patterns (user who gets a prediction, then asks for timeline, then asks for fees — the coherence of the sequence).

**What "better" looks like:** Identifies cross-tool coherence scenarios (prediction says "OTC eligible" but timeline estimates suggest in-house review times — contradiction detection). Proposes error-state scenarios (SODA API down, DuckDB corrupted, knowledge base stale). Identifies user journey gaps (what happens when a user disagrees with a prediction?).

**Baseline:** Current Claude proposes reasonable scenarios but tends to focus on happy-path variations rather than true edge cases and error states.

---

## Category 6: Domain Knowledge (2 probes)

### Probe 6.1: OTC vs In-House Routing

**Prompt:**
```
My project involves replacing a residential water heater (same location, same fuel type) and adding a new bathroom in an existing legal bedroom. Which parts are OTC-eligible and which require in-house review?
```

**Expected capability:** Should correctly identify the water heater replacement as OTC-eligible (like-for-like equipment replacement) and the bathroom addition as likely requiring in-house review (new plumbing fixtures, potential structural modifications for wet wall). Should note that the two components may be on separate permits.

**What "better" looks like:** References the specific OTC criteria document. Notes that "same location, same fuel type" water heater replacements are explicitly listed as OTC no-plan projects. Identifies that the bathroom addition's review path depends on whether structural modifications are needed (removing/adding walls vs. using existing closet space). Mentions that a plumber can pull the water heater permit separately.

**Baseline:** Current Claude correctly separates OTC and in-house components but sometimes doesn't reference the specific OTC criteria list.

### Probe 6.2: Fee Calculation Deep Dive

**Prompt:**
```
Walk me through exactly how DBI calculates permit fees for a $200,000 residential alteration project. Show me the formula, the applicable fee table rows, and what surcharges apply.
```

**Expected capability:** Should use estimate_fees tool and explain the calculation: Table 1A-A base fee lookup by valuation bracket, plan review fee (65% of building permit fee for in-house), technology surcharge, strong motion instrumentation fee, training surcharge. Should show the actual bracket ($200K falls in the $100,001-$500,000 tier) and compute the numbers.

**What "better" looks like:** Shows the step-by-step calculation with actual numbers from the fee tables. Distinguishes between the building permit fee and the plan review fee. Notes which surcharges are percentage-based vs flat. Compares the formula result to actual historical fees for similar projects (statistical context from the database).

**Baseline:** Current Claude produces accurate fee estimates but doesn't always show the step-by-step formula breakdown clearly.

---

## Running the Probes

### Setup
1. Connect to sfpermits.ai MCP server via claude.ai
2. Run each probe as a standalone conversation (no context carryover)
3. Record the model version and date

### Scoring
For each probe, score on:
- **Accuracy** (1-5): Are the facts correct?
- **Completeness** (1-5): Did it cover all relevant aspects?
- **Synthesis** (1-5): Did it connect information across sources?
- **Domain depth** (1-5): Did it demonstrate SF-specific knowledge beyond generic answers?

### Tracking
Record results in a spreadsheet with columns: Probe ID, Model Version, Date, Accuracy, Completeness, Synthesis, Domain Depth, Notes.

Compare across releases to identify capability improvements and regressions.
