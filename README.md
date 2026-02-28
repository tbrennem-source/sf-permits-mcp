# SF Permits MCP Server

MCP server + web application for San Francisco building permit data, entity network analysis, AI-powered permit guidance, and AI vision plan analysis. Built with [FastMCP](https://github.com/jlowin/fastmcp), Flask + HTMX, and deployed on [Railway](https://railway.app).

**Live**: https://sfpermits-ai-production.up.railway.app

## Tools (34 MCP Tools)

| Phase | Tool | Description |
|-------|------|-------------|
| **1 — SODA API** | `search_permits` | Search building permits by neighborhood, type, status, cost, date, address |
| | `get_permit_details` | Full details for a specific permit by number |
| | `permit_stats` | Aggregate statistics grouped by neighborhood, type, status, month, year |
| | `search_businesses` | Search registered business locations |
| | `property_lookup` | Property assessments by address or block/lot |
| | `search_complaints` | DBI complaint records |
| | `search_violations` | Notices of violation |
| | `search_inspections` | Building inspection records |
| **2 — Entity/Network** | `search_entity` | Find entities by name across 1M+ resolved records |
| | `entity_network` | N-hop network traversal for entity relationships |
| | `network_anomalies` | Anomaly detection across entity networks |
| **2.75 — Knowledge** | `predict_permits` | Predict required permits via decision tree walk |
| | `estimate_timeline` | Timeline estimates from historical percentiles |
| | `estimate_fees` | Fee calculation from structured fee tables |
| | `required_documents` | Document checklist assembly |
| | `revision_risk` | Revision probability from cost/code analysis |
| **3.5 — Facilitation** | `recommend_consultants` | Land use consultant recommendations |
| | `permit_lookup` | Quick permit lookup by number, address, or parcel — exact matching, historical lot discovery, parcel-level merge |
| **4 — Vision** | `analyze_plans` | AI vision analysis of architectural drawings |
| | `validate_plans` | EPR compliance checking via Claude Vision |
| **5 — Addenda** | `search_addenda` | Search 3.9M+ plan review routing records by permit, station, reviewer, date |
| **6 — Severity/Health** | `permit_severity` | Severity scoring for permits (CRITICAL/HIGH/MEDIUM/LOW/GREEN) |
| | `property_health` | Signal-based property health aggregation |
| **7 — Project Intelligence** | `run_query` | Execute SQL against the local database |
| | `read_source` | Read source files for project intelligence |
| | `search_source` | Search across source files |
| | `schema_info` | Database schema information |
| | `list_tests` | List test files and coverage |
| | `similar_projects` | Find similar permit projects by type, cost, neighborhood |
| **8 — Intelligence** | `predict_next_stations` | Predict what review stations a permit will visit next (Markov transition model) |
| | `diagnose_stuck_permit` | Diagnose why a permit is stalled + generate ranked intervention playbook |
| | `simulate_what_if` | Compare base project vs. N variations across timeline, fees, revision risk in parallel |
| | `calculate_delay_cost` | Financial cost-of-delay analysis: carrying cost per scenario, break-even, mitigation strategies |

## Data Sources

All data from [DataSF](https://data.sfgov.org/) via the Socrata SODA API. **22 datasets** cataloged, **13.3M records**:

- **Permits**: Building (1.3M), Plumbing (513K), Electrical (344K), Boiler (152K), Street-Use (1.2M)
- **Contacts**: Building (1M), Electrical (340K), Plumbing (503K) — resolved into 1M+ entities
- **Violations**: Inspections (671K), Complaints (326K), Notices of Violation (509K)
- **Enrichment**: Business Locations (354K), Property Tax Rolls (3.7M), Development Pipeline, Housing Production

See [`datasets/CATALOG.md`](datasets/CATALOG.md) for the full catalog.

## Architecture

```
Users (browser)
    |
    v
Flask + HTMX Web UI (Railway)  <-- https://sfpermits-ai-production.up.railway.app
    |
    |--- PostgreSQL (pgvector-db) -- users, auth, RAG embeddings, permit tracking
    |--- SODA API (data.sfgov.org) -- live permit queries
    |--- Claude Vision API ---------- plan analysis
    |
Claude (claude.ai / Claude Code)
    |
    v
FastMCP Server — 34 tools
    |--- Phase 1 (8 tools) -------> SODA API (live HTTP)
    |--- Phase 2 (3 tools) -------> PostgreSQL (entities, relationships)
    |--- Phase 2.75 (5 tools) ----> Knowledge Base (47 tier1 JSON files)
    |--- Phase 3.5 (2 tools) -----> PostgreSQL + Knowledge Base
    |--- Phase 4 (2 tools) -------> Claude Vision API
    |--- Phase 5 (1 tool) -------> PostgreSQL (addenda routing, 3.9M rows)
    |--- Phase 6 (2 tools) -------> PostgreSQL (severity scoring, health signals)
    |--- Phase 7 (6 tools) -------> PostgreSQL + local DB (project intelligence)
    |--- Phase 8 (4 tools) -------> PostgreSQL + addenda routing (permit intelligence)
```

## Key Numbers

| Metric | Value |
|--------|-------|
| MCP tools | 34 |
| SODA datasets | 22 (13.3M records) |
| Entities | 1M+ (resolved from 1.8M contacts) |
| Relationship edges | 576K |
| Addenda routing records | 3.9M |
| Knowledge base | 47 tier1 JSON files, ~86 semantic concepts |
| RAG chunks | 1,035 (pgvector embeddings) |
| Tests | 4,357+ collected |
| PostgreSQL tables | 59 |

## Setup

```bash
git clone https://github.com/tbrennem-source/sf-permits-mcp.git
cd sf-permits-mcp
pip install -e ".[dev]"

# MCP server
python -m src.server

# Web UI (local)
python -m web.app

# Tests
pytest tests/ -v
```

## Project Phases

- [x] **Phase 1**: MCP server + SODA API tools + dataset catalog + benchmarks
- [x] **Phase 2**: DuckDB local analytics, entity resolution, co-occurrence graph
- [x] **Phase 2.75**: Knowledge base, decision tree, permit guidance tools
- [x] **Phase 3**: Web UI (Flask + HTMX), auth, morning briefs, feedback
- [x] **Phase 3.5**: Railway deployment, PostgreSQL migration, regulatory watch, consultant recommendations
- [x] **Phase 4**: AI Vision plan analysis, EPR compliance checking
- [x] **Phase 5**: Addenda routing search (3.9M records)
- [x] **Phase 6**: Severity scoring, property health signals
- [x] **Phase 7**: Project intelligence tools (SQL, source, schema, tests, similar projects)
- [x] **Phase 8**: Permit intelligence — predict next stations, diagnose stuck permits, what-if simulation, delay cost calculator

## Current State

Phases 1-8 substantially complete. QS8 (Sprint 79 + Sprint 81) delivered 4 new MCP intelligence tools (predict_next_stations, diagnose_stuck_permit, simulate_what_if, calculate_delay_cost) plus infrastructure improvements (SODA circuit breaker, batch DB queries, response timing headers, cache stats in /health). Sprint 81 added multi-step onboarding wizard, PREMIUM feature tier, search NLP parser, and 22 new E2E tests. Blueprint route refactor complete (Sprint 69) — routes extracted from monolithic `app.py` into 8 Blueprint files; `app.py` reduced from ~8K to 1,061 lines. Live: https://sfpermits-ai-production.up.railway.app

## Documentation

| Document | Purpose |
|----------|---------|
| [`CLAUDE.md`](CLAUDE.md) | **Primary reference** — project structure, Railway infra, deploy instructions |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Data flow, schemas, module details |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Architecture decision log |
| [`docs/BACKUPS.md`](docs/BACKUPS.md) | Backup strategy and recovery playbook |
| [`CHANGELOG.md`](CHANGELOG.md) | Session-by-session build log |
| [`data/knowledge/SOURCES.md`](data/knowledge/SOURCES.md) | Knowledge base inventory |
