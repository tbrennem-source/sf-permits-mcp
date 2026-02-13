# Mehri NYC Bad Actor Model — Quick Reference

Source: github.com/dariusmehri/Social-Network-Bad-Actor-Risk-Tool

## Actor Types Per Permit (NYC DOB)

NYC building permits contain these actor roles:
- Owner
- Architect or Engineer (of record)
- Contractor (general/filing)
- Filing Representative (permit expediter)

Each permit creates edges between all actors on that permit.

## Network Construction

- Node = Person (any actor on any permit)
- Edge = Co-occurrence on same permit (weighted by frequency)
- Bad actor seed list = actors with prior violations/dispositions

## Key Metrics Computed

- Total ties (degree)
- Bad ties (edges to known bad actors)
- Bad tie density = bad ties / total ties
- Unique bad tie density (deduplicated per person, not per permit)
- Betweenness centrality (brokering between groups)
- Community membership (Louvain community detection)
- Community bad density = bad actors in community / total in community

## Composite Risk Score

Ranks actors by: violation_count + unique_bad_tie_density + betweenness_centrality

## What to Look For in SF Data

Priority fields to find in SF datasets:
- Contractor name
- Architect/engineer name (and license/stamp number if available)
- Property owner name
- Filing representative / permit expediter name
- Any license numbers, stamp numbers, or registration IDs
- Inspector name (if available — needed for Curran-pattern detection)

## SF Contact Data Discovery (Phase 1 Findings)

### Confirmed Contact Datasets

| Dataset | Endpoint ID | Records | Actor Fields |
|---|---|---|---|
| Building Permits Contacts | `3pee-9qhc` | TBD | contractor, architect, owner, agent |
| Electrical Permits Contacts | `fdm7-jqqf` | TBD | contractor info |

### Contact Fields in Primary Datasets

| Dataset | Contact Fields Found |
|---|---|
| Building Permits (`i98e-djp9`) | None visible in schema — contacts are in separate `3pee-9qhc` dataset |
| Planning Projects (`qvu5-m3a2`) | `applicant`, `applicant_org`, `assigned_to_planner` |
| Planning Non-Projects (`y673-d69b`) | `applicant_org`, `assigned_to_planner` |
| Street-Use Permits (`b6tj-gt35`) | `agent`, `agentphone`, `contact`, `planchecker` |
| Large Utility Excavation (`i926-ujnc`) | `utility_contractor` |
| Building Inspections (`vckc-dh2h`) | `inspector` |

### Key Finding

The `3pee-9qhc` (Building Permits Contacts) dataset is the **linchpin** for the social network model. It separates contact/actor data from the permit record itself, similar to NYC's structure. This needs deep exploration in Phase 2.

### Risk: Entity Resolution

SF contact fields are likely free-text names (not normalized IDs). If "John Smith Construction" and "J. Smith Const." refer to the same entity, we need entity resolution — a significant sub-project. Look for license numbers or registration IDs that could serve as stable identifiers.
