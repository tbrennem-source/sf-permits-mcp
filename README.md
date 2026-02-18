# SF Permits MCP Server

MCP server + web application for San Francisco building permit data, entity network analysis, AI-powered permit guidance, and AI vision plan analysis. Built with [FastMCP](https://github.com/jlowin/fastmcp), Flask + HTMX, and deployed on [Railway](https://railway.app).

**Live**: https://sfpermits-ai-production.up.railway.app

## Tools (20 MCP Tools)

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
| | `permit_lookup` | Quick permit lookup by number |
| **4 — Vision** | `analyze_plans` | AI vision analysis of architectural drawings |
| | `validate_plans` | EPR compliance checking via Claude Vision |

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
FastMCP Server — 20 tools
    |--- Phase 1 (8 tools) -------> SODA API (live HTTP)
    |--- Phase 2 (3 tools) -------> PostgreSQL (entities, relationships)
    |--- Phase 2.75 (5 tools) ----> Knowledge Base (39 tier1 JSON files)
    |--- Phase 3.5 (2 tools) -----> PostgreSQL + Knowledge Base
    |--- Phase 4 (2 tools) -------> Claude Vision API
```

## Key Numbers

| Metric | Value |
|--------|-------|
| MCP tools | 20 |
| SODA datasets | 22 (13.3M records) |
| Entities | 1M+ (resolved from 1.8M contacts) |
| Relationship edges | 576K |
| Knowledge base | 39 tier1 JSON files, ~78 semantic concepts |
| RAG chunks | 1,012 (pgvector embeddings) |
| Tests | 1,058 |
| PostgreSQL tables | 20 |

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
- [x] **Phase 4** (partial): AI Vision plan analysis, EPR compliance checking
- [ ] **Phase 4** (remaining): RAG activation, nightly refresh

## Documentation

| Document | Purpose |
|----------|---------|
| [`CLAUDE.md`](CLAUDE.md) | **Primary reference** — project structure, Railway infra, deploy instructions |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Data flow, schemas, module details |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Architecture decision log |
| [`docs/BACKUPS.md`](docs/BACKUPS.md) | Backup strategy and recovery playbook |
| [`CHANGELOG.md`](CHANGELOG.md) | Session-by-session build log |
| [`data/knowledge/SOURCES.md`](data/knowledge/SOURCES.md) | Knowledge base inventory |
