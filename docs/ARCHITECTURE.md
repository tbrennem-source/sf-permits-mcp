# Architecture

## System Overview

```
Claude (claude.ai / Claude Code)
    |
    | MCP tool calls
    v
SF Permits MCP Server (FastMCP) — 20 tools
    |
    |--- Phase 1 tools (8) -------> data.sfgov.org SODA API (live HTTP)
    |                                     |
    |                                     v
    |                                JSON response -> formatters.py -> Claude
    |
    |--- Phase 2 tools (3) -------> PostgreSQL / DuckDB (entities, relationships)
    |                                     |
    |                                     v
    |                                SQL query results -> Claude
    |
    |--- Phase 2.75 tools (5) ----> Knowledge Base (data/knowledge/tier1/*.json)
    |                                + PostgreSQL/DuckDB (historical statistics)
    |                                     |
    |                                     v
    |                                Decision tree walk -> predictions -> Claude
    |
    |--- Phase 3.5 tools (2) ----> PostgreSQL + Knowledge Base
    |                                     |
    |                                     v
    |                                Consultant recommendations, permit lookup -> Claude
    |
    |--- Phase 4 tools (2) ------> Claude Vision API (Anthropic)
                                         |
                                         v
                                    Plan analysis + EPR compliance -> Claude

Flask + HTMX Web UI (Railway) — https://sfpermits-ai-production.up.railway.app
    |
    |--- PostgreSQL (pgvector-db) -- users, auth, RAG, vision sessions, permit tracking
    |--- SODA API (proxied) -------- live permit queries for web users
    |--- Claude Vision API --------- async plan analysis jobs
```

Phase 1 tools (`search_permits`, `get_permit_details`, `permit_stats`, `search_businesses`, `property_lookup`, `search_complaints`, `search_violations`, `search_inspections`) query data.sfgov.org live via `SODAClient`.

Phase 2 tools (`search_entity`, `entity_network`, `network_anomalies`) query PostgreSQL (production) or DuckDB (local) containing 1.8M+ resolved contact records, entity relationships, and anomaly detection results.

Phase 2.75 tools (`predict_permits`, `estimate_timeline`, `estimate_fees`, `required_documents`, `revision_risk`) walk a 7-step permit decision tree backed by structured knowledge files (fee tables, routing matrix, OTC criteria, fire/planning code) plus historical statistics.

Phase 3.5 tools (`recommend_consultants`, `permit_lookup`) combine knowledge base consultant data with permit lookups.

Phase 4 tools (`analyze_plans`, `validate_plans`) use the Claude Vision API to analyze architectural drawings and check EPR compliance.

---

## Data Flow

```
SODA API (data.sfgov.org)
    |
    | python -m src.ingest (paginated fetch, 10K/page)
    v
DuckDB (data/sf_permits.duckdb)
    |
    | python -m src.entities (5-step cascade)
    v
Entity Resolution (contacts -> entities table)
    |
    | python -m src.graph (self-join + aggregation)
    v
Co-occurrence Graph (relationships table)
    |
    | python -m src.validate (queries + anomaly detection)
    v
Validation Results / MCP Tool Responses
```

### Ingestion (`src/ingest.py`)

Fetches 5 datasets from SODA API into DuckDB:

| Dataset | Endpoint | Target Table | Records |
|---|---|---|---|
| Building Permits Contacts | `3pee-9qhc` | `contacts` | ~1.0M |
| Electrical Permits Contacts | `fdm7-jqqf` | `contacts` | ~340K |
| Plumbing Permits Contacts | `k6kv-9kix` | `contacts` | ~503K |
| Building Permits | `i98e-djp9` | `permits` | ~1.28M |
| Building Inspections | `vckc-dh2h` | `inspections` | ~671K |

Contact records are normalized into a unified schema during ingestion. Key normalizations:
- `license1` (building) mapped to `license_number`
- `sf_business_license_number` mapped to `sf_business_license`
- `first_name` + `last_name` concatenated into `name`
- `company_name` (electrical) and `firm_name` (plumbing) mapped to both `name` and `firm_name`
- Roles normalized via `ROLE_MAP` (11 building roles -> 8 canonical types)
- `estimated_cost` cast from TEXT to DOUBLE

Uses existing `SODAClient` from `src/soda_client.py` for all API calls. Pagination at 10K records per page via `$offset` + `$limit`.

### Entity Resolution (`src/entities.py`)

Resolves 1.8M+ contact records into deduplicated entities using a priority cascade:

```
Step 1: pts_agent_id     (building only, high confidence)
    |
    v   unresolved contacts pass through
Step 2: license_number   (all sources, medium confidence)
    |   merges into step-1 entities when license matches
    v
Step 3: sf_business_license (all sources, medium confidence)
    |   merges into existing entities when biz license matches
    v
Step 4: fuzzy name match  (remaining with name, low confidence)
    |   blocking: first 3 chars of UPPER(name)
    |   similarity: token-set Jaccard >= 0.75
    v
Step 5: singletons        (remaining without match, low confidence)
```

Steps 2 and 3 check for existing entities created by prior steps. If a `license_number` already belongs to a step-1 entity, unresolved contacts with that license are merged into the existing entity rather than creating a duplicate.

Each entity stores: `canonical_name`, `canonical_firm`, `entity_type`, identifier keys, `resolution_method`, `resolution_confidence`, `contact_count`, `permit_count`, `source_datasets`.

### Co-occurrence Graph (`src/graph.py`)

Builds relationship edges between entities that appear on the same permit.

**Edge computation** is a single SQL INSERT...SELECT:

```sql
FROM contacts a
JOIN contacts b
    ON a.permit_number = b.permit_number
    AND a.entity_id < b.entity_id     -- canonical ordering, no dupes
LEFT JOIN permits p
    ON a.permit_number = p.permit_number
WHERE a.entity_id IS NOT NULL
  AND b.entity_id IS NOT NULL
GROUP BY a.entity_id, b.entity_id
```

Edge attributes:
- `shared_permits` — count of co-occurrences (edge weight)
- `permit_numbers` — first 20 shared permit numbers
- `permit_types` — distinct permit types
- `date_range_start`, `date_range_end` — temporal span
- `total_estimated_cost` — sum across shared permits
- `neighborhoods` — distinct neighborhoods

**Query operations:**
- `get_neighbors(entity_id)` — 1-hop neighbors with edge attributes
- `get_network(entity_id, hops)` — N-hop ego network via iterative frontier expansion

### Validation & Anomaly Detection (`src/validate.py`)

Queries the graph and DuckDB tables for analysis:

| Function | Purpose |
|---|---|
| `search_entity(name)` | LIKE search on canonical_name/firm, returns entity + top 5 co-occurring |
| `entity_network(entity_id, hops)` | N-hop network traversal, returns nodes + edges |
| `inspector_contractor_links(name)` | Inspector -> permits -> contacts -> entities trace |
| `find_clusters(min_size, min_weight)` | Connected-component BFS on filtered subgraph |
| `anomaly_scan(min_permits)` | 4 anomaly categories (see below) |
| `run_ground_truth()` | Searches for known bad actors (Santos, Kong, Curran) |

**Anomaly categories:**
1. **High permit volume** — entities with permit_count > 3x the median for their entity_type
2. **Inspector concentration** — entities where 50%+ of inspected permits use the same inspector
3. **Geographic concentration** — entities with 80%+ of permits in one neighborhood
4. **Fast approvals** — permits with filed-to-issued < 7 days and estimated_cost > $100K

---

## DuckDB Schema

```
contacts
    id              INTEGER PK
    source          TEXT          -- 'building', 'electrical', 'plumbing'
    permit_number   TEXT
    role            TEXT          -- normalized canonical type
    name            TEXT          -- normalized full name
    first_name      TEXT
    last_name       TEXT
    firm_name       TEXT
    pts_agent_id    TEXT
    license_number  TEXT
    sf_business_license TEXT
    phone           TEXT
    address         TEXT
    city            TEXT
    state           TEXT
    zipcode         TEXT
    is_applicant    TEXT
    from_date       TEXT
    entity_id       INTEGER  --> entities.entity_id
    data_as_of      TEXT

entities
    entity_id              INTEGER PK
    canonical_name         TEXT
    canonical_firm         TEXT
    entity_type            TEXT
    pts_agent_id           TEXT
    license_number         TEXT
    sf_business_license    TEXT
    resolution_method      TEXT     -- 'pts_agent_id', 'license_number', 'sf_business_license', 'fuzzy_name', 'singleton'
    resolution_confidence  TEXT     -- 'high', 'medium', 'low'
    contact_count          INTEGER
    permit_count           INTEGER
    source_datasets        TEXT     -- comma-separated: 'building,electrical,plumbing'

relationships
    entity_id_a          INTEGER  --> entities.entity_id
    entity_id_b          INTEGER  --> entities.entity_id
    shared_permits       INTEGER
    permit_numbers       TEXT
    permit_types         TEXT
    date_range_start     TEXT
    date_range_end       TEXT
    total_estimated_cost DOUBLE
    neighborhoods        TEXT
    PK (entity_id_a, entity_id_b)

permits
    permit_number          TEXT PK
    permit_type            TEXT
    permit_type_definition TEXT
    status                 TEXT
    status_date            TEXT
    description            TEXT
    filed_date             TEXT
    issued_date            TEXT
    approved_date          TEXT
    completed_date         TEXT
    estimated_cost         DOUBLE
    revised_cost           DOUBLE
    existing_use           TEXT
    proposed_use           TEXT
    existing_units         INTEGER
    proposed_units         INTEGER
    street_number          TEXT
    street_name            TEXT
    street_suffix          TEXT
    zipcode                TEXT
    neighborhood           TEXT
    supervisor_district    TEXT
    block                  TEXT
    lot                    TEXT
    adu                    TEXT
    data_as_of             TEXT

inspections
    id                      INTEGER PK
    reference_number        TEXT
    reference_number_type   TEXT
    inspector               TEXT
    scheduled_date          TEXT
    result                  TEXT
    inspection_description  TEXT
    block                   TEXT
    lot                     TEXT
    street_number           TEXT
    street_name             TEXT
    street_suffix           TEXT
    neighborhood            TEXT
    supervisor_district     TEXT
    zipcode                 TEXT
    data_as_of              TEXT

ingest_log
    dataset_id          TEXT PK
    dataset_name        TEXT
    last_fetched        TEXT
    records_fetched     INTEGER
    last_record_count   INTEGER
```

---

## Key Modules

```
src/
├── server.py        # FastMCP entry point, registers all 20 tools
├── soda_client.py   # Async SODA API client (httpx), used by Phase 1 tools + ingestion
├── formatters.py    # Response formatting for Claude consumption
├── db.py            # DuckDB + PostgreSQL dual-mode connections
├── knowledge.py     # KnowledgeBase singleton, semantic index
├── ingest.py        # SODA -> DuckDB/Postgres pipeline (paginated fetch, normalization)
├── entities.py      # 5-step entity resolution cascade
├── graph.py         # Co-occurrence graph (self-join + N-hop traversal)
├── validate.py      # Validation queries + anomaly detection
├── report_links.py  # External links for property reports
├── vision/          # AI Vision modules
│   ├── client.py        # Anthropic Vision API wrapper
│   ├── pdf_to_images.py # PDF-to-base64 image conversion
│   ├── prompts.py       # EPR check prompts
│   └── epr_checks.py    # Vision-based EPR compliance checker
└── tools/
    ├── search_permits.py      # Phase 1: SODA API
    ├── get_permit_details.py  # Phase 1: SODA API
    ├── permit_stats.py        # Phase 1: SODA API
    ├── search_businesses.py   # Phase 1: SODA API
    ├── property_lookup.py     # Phase 1: SODA API
    ├── search_complaints.py   # Phase 1: SODA API
    ├── search_violations.py   # Phase 1: SODA API
    ├── search_inspections.py  # Phase 1: SODA API
    ├── search_entity.py       # Phase 2: Entity search
    ├── entity_network.py      # Phase 2: Network traversal
    ├── network_anomalies.py   # Phase 2: Anomaly detection
    ├── knowledge_base.py      # Phase 2.75: Shared loader for all tier1 JSON
    ├── predict_permits.py     # Phase 2.75: Decision tree walk + predictions
    ├── estimate_timeline.py   # Phase 2.75: Timeline percentiles
    ├── estimate_fees.py       # Phase 2.75: Fee table calculation + statistics
    ├── required_documents.py  # Phase 2.75: Document checklist assembly
    ├── revision_risk.py       # Phase 2.75: Revision probability from cost data
    ├── recommend_consultants.py # Phase 3.5: Land use consultant recommendations
    ├── permit_lookup.py       # Phase 3.5: Quick permit lookup
    ├── analyze_plans.py       # Phase 4: AI vision plan analysis
    └── validate_plans.py      # Phase 4: EPR compliance checking
```

### Knowledge Base Dependencies (Phase 2.75)

| Tool | Knowledge Files | DuckDB |
|------|----------------|--------|
| `predict_permits` | decision-tree-draft.json, semantic-index.json, otc-criteria.json, G-20-routing.json, ada-accessibility-requirements.json, title24-energy-compliance.json, dph-food-facility-requirements.json | No |
| `estimate_timeline` | — | Yes (timeline_stats materialized view) |
| `estimate_fees` | fee-tables.json, ada-accessibility-requirements.json | Yes (statistical comparison) |
| `required_documents` | completeness-checklist.json, epr-requirements.json, title24-energy-compliance.json, dph-food-facility-requirements.json | No |
| `revision_risk` | title24-energy-compliance.json, ada-accessibility-requirements.json, dph-food-facility-requirements.json | Yes (revised_cost analysis) |

All 15 knowledge files loaded once via `KnowledgeBase` singleton (`@lru_cache`).

---

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `SODA_APP_TOKEN` | SODA API app token for higher rate limits | None (anonymous) |
| `SF_PERMITS_DB` | Path to DuckDB database file | `data/sf_permits.duckdb` |
| `DATABASE_URL` | PostgreSQL connection string (production) | None (uses DuckDB) |
| `ADMIN_EMAIL` | Auto-seed admin user on empty DB | None |
| `CRON_SECRET` | Bearer token for cron endpoints | Required in prod |
| `ANTHROPIC_API_KEY` | Claude Vision API for plan analysis | Required for Vision tools |
| `OPENAI_API_KEY` | OpenAI embeddings for RAG | Required for RAG |

The DuckDB file lives in `data/` (gitignored). Regenerate by running the full pipeline:

```bash
python -m src.ingest        # Fetch data from SODA API
python -m src.entities      # Resolve entities
python -m src.graph         # Build co-occurrence graph
python -m src.validate all  # Run validation + anomaly scan
```

---

## PostgreSQL Production Database

In production (Railway), the app uses PostgreSQL with pgvector instead of DuckDB. `src/db.py` detects `DATABASE_URL` and switches backends automatically.

**pgvector-db tables:**

| Category | Tables |
|----------|--------|
| User data | `users`, `auth_tokens`, `watch_items`, `feedback`, `activity_log`, `points_ledger` |
| Permit data | `contacts`, `entities`, `relationships`, `permits`, `inspections`, `timeline_stats`, `ingest_log`, `permit_changes` |
| Vision | `plan_analysis_sessions`, `plan_analysis_images`, `plan_analysis_jobs` |
| RAG | `knowledge_chunks` (pgvector 1536-dim embeddings) |
| System | `cron_log`, `regulatory_watch` |

The database is internal-only (`pgvector-db.railway.internal:5432`). Use the `/health` endpoint to check table state remotely.

---

## Flask Web UI

The web application (`web/app.py`) provides a browser-based interface deployed on Railway:

- **Authentication**: Magic-link passwordless login (`web/auth.py`)
- **Morning briefs**: Daily permit activity summaries (`web/brief.py`, `web/email_brief.py`)
- **Triage reports**: Nightly email digests (`web/email_triage.py`)
- **Plan analysis**: Async AI vision analysis of uploaded PDFs (`/analyze`)
- **Regulatory watch**: Admin CRUD for regulation monitoring (`web/regulatory_watch.py`)
- **Feedback system**: User feedback with bounty points (`web/activity.py`)
- **Admin auto-seed**: Creates admin user from `ADMIN_EMAIL` on empty database

Tech stack: Flask, HTMX, Jinja2 templates, deployed via Railway GitHub auto-deploy.

---

## AI Vision Infrastructure

The Vision subsystem (`src/vision/`) analyzes architectural drawings using the Anthropic Claude Vision API:

```
PDF upload → pdf_to_images.py (base64 conversion) → client.py (Claude Vision API)
    → epr_checks.py (EPR compliance prompts) → results stored in plan_analysis_* tables
```

- **Async processing**: Full analysis runs as background jobs to avoid HTTP timeouts
- **EPR checks**: Energy, plumbing, structural compliance verification against code requirements
- **Annotations**: 10-color system with localStorage persistence, ARIA accessibility

---

## Backup Infrastructure

Three-layer strategy (see `docs/BACKUPS.md` for full details):

1. **Railway native backups** — Daily + Weekly via dashboard (pgvector-db → Settings → Backups)
2. **pg_dump cron** — `POST /cron/backup` endpoint with CRON_SECRET auth
3. **Admin auto-seed** — Empty `users` table + `ADMIN_EMAIL` env var → admin account on startup

User-generated data (users, watches, feedback) requires backups. Permit/entity/knowledge data is regenerable from SODA API and git.
