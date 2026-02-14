# Decision Tree Validation Report

**Validated:** 2026-02-14
**Decision Tree:** `decision-tree-draft.json` (38K, 7 steps, 6 special project types)
**Machine-readable version:** `tier1/decision-tree-gaps.json`

## Summary

The decision tree is **ready for tool development**. 6 of 7 steps have complete backing data. Step 6 (timelines) is the primary gap, which will be resolved by the `estimate_timeline` tool using DuckDB historical data.

## Step-by-Step Validation

| Step | Name | Status | Confidence | Backing Files |
|------|------|--------|------------|---------------|
| 1 | Need permit? | Complete | High | otc-criteria.json |
| 2 | Which form? | Complete | High | permit-forms-taxonomy.json |
| 3 | OTC or In-House? | Complete | High | otc-criteria.json, inhouse-review-process.json |
| 4 | Agency routing | Complete | High | G-20-routing.json, fire-code-key-sections.json, planning-code-key-sections.json |
| 5 | Required documents | Complete | High | completeness-checklist.json, epr-requirements.json |
| 6 | Timeline | Partial | Medium | DuckDB permits table (needs statistical analysis) |
| 7 | Fees | Complete | High | fee-tables.json (19 tables, 10 tiers, 9-step algorithm) |

## Special Project Types

| Type | Status | Confidence | Notes |
|------|--------|------------|-------|
| Restaurant change of use | Complete | High | 10-step process from G-25 |
| ADU | Partial | Medium | Pre-approval process referenced, not fully structured |
| Seismic retrofit | Complete | High | Priority eligible per AB-004 |
| Commercial TI | Complete | High | Full routing mapped |
| Adaptive reuse | Partial | Medium | Guidelines in S-03, not fully structured |
| Solar/clean energy | Complete | High | Priority eligible per AB-004 |

## Known Gaps

### Critical (addressed by Phase 2.75 tools)
- **Timeline estimates (Step 6):** DBI does not publish standard processing timelines. The `estimate_timeline` tool will compute percentile-based timelines from 1.1M+ DuckDB permit records (filed_date to issued_date).

### Non-Critical (advisory)
- **Other-agency fees:** Planning, DPH, DPW fees not in fee-tables.json. Tools will note "additional agency fees may apply."
- **OTC cost thresholds:** The one-hour rule is operational, not codified. Edge cases exist.
- **Commercial completeness checklist:** The 13-section checklist is residential-focused. Commercial projects may have additional requirements.
- **EPR technical specs:** Bluebeam Studio requirements are operational, not in published regulations.

## DuckDB Schema Verification

- `estimated_cost`: **DOUBLE** (already cast during ETL — no CAST needed in queries)
- `revised_cost`: **DOUBLE** (populated for 796K of 1.1M permits; 125K have revised > estimated)
- `plansets`: **Does not exist** — revision risk tool uses `revised_cost` delta instead
- `neighborhood`: 41 distinct values matching SF Analysis Neighborhoods
- `filed_date`, `issued_date`, `completed_date`: VARCHAR (need DATE cast for date arithmetic)

## Data Coverage for Phase 2.75 Tools

| Tool | Primary Data Source | Coverage |
|------|-------------------|----------|
| predict_permits | Decision tree + semantic-index.json (61 concepts, ~500 aliases) | High |
| estimate_timeline | DuckDB permits (1.1M records with dates) | High |
| estimate_fees | fee-tables.json (19 tables) + DuckDB statistics | High |
| required_documents | completeness-checklist.json + epr-requirements.json | High |
| revision_risk | DuckDB revised_cost vs estimated_cost (125K revision events) | Medium |
