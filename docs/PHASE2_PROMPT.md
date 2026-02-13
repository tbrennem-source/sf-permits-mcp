# Phase 2: Network Model Validation — Claude Code Prompt

## Context

You are working on **sf-permits-mcp**, a Python MCP server that queries San Francisco open data via SODA API. Phase 1 is complete — 5 MCP tools, 10/10 tests passing, 22 datasets cataloged, pushed to GitHub.

**Repo:** `~/AIprojects/sf-permits-mcp`

### Key Files (Current State)

```
src/
├── server.py           # FastMCP entry point, registers 5 tools
├── soda_client.py      # Async SODA client (httpx, ~108 lines)
├── formatters.py       # Response formatting for Claude
└── tools/
    ├── search_permits.py      # Search building permits with filters
    ├── get_permit_details.py  # Get full details for a permit by number
    ├── permit_stats.py        # Aggregate stats grouped by neighborhood/type/etc
    ├── search_businesses.py   # Search registered business locations
    └── property_lookup.py     # Property assessments by address or block/lot

datasets/
├── catalog.json        # 22 dataset catalog (machine-readable)
└── CATALOG.md          # Dataset documentation (human-readable)

docs/
├── DECISIONS.md        # Architecture decisions log
├── contact-data-report.md  # Deep-dive on contact/actor data schemas
└── mehri-reference.md  # Reference for NYC bad actor social network model

benchmarks/
└── RESULTS.md          # Phase 1 SODA API performance benchmarks

tests/
└── test_server.py      # 10 passing integration tests
```

### Existing Code to Reuse

- **`src/soda_client.py`** — `SODAClient` class with async `query()`, `count()`, `schema()` methods. Uses `httpx.AsyncClient`, reads `SODA_APP_TOKEN` from env. Reuse this for all SODA API calls in Phase 2.
- **`src/server.py`** — FastMCP server instance. New Phase 2 tools get registered here alongside existing tools.
- **Environment variable:** `SODA_APP_TOKEN` (not `SF_DATA_APP_TOKEN`). Already configured in `~/.claude/settings.json`.

---

## Phase 2 Objective

**Core question:** Can we build a social network graph from SF permit contact data that reveals real relationships between actors (contractors, architects, agents, owners)?

We need to validate this by:
1. Ingesting 1.8M+ contact records into local DuckDB
2. Building co-occurrence relationships (who works with whom)
3. Searching for known bad actors as ground truth
4. Proving the network model works before investing in Phase 3+

---

## Data Sources

### Contact Datasets (SODA API)

All three must be ingested:

| Dataset | Endpoint | Records | Key Fields |
|---|---|---|---|
| **Building Permits Contacts** | `3pee-9qhc` | ~1,004,592 | `permit_number`, `role` (11 types), `first_name`, `last_name`, `firm_name`, `license1`, `sf_business_license_number`, `pts_agent_id` |
| **Electrical Permits Contacts** | `fdm7-jqqf` | ~339,926 | `permit_number`, `contact_type`, `company_name`, `license_number`, `sf_business_license_number`, `phone` |
| **Plumbing Permits Contacts** | `k6kv-9kix` | ~502,534 | `permit_number`, `firm_name`, `license_number`, `sf_business_license_number`, `phone` |

#### Schema Differences Between Contact Datasets

| Feature | Building (3pee-9qhc) | Electrical (fdm7-jqqf) | Plumbing (k6kv-9kix) |
|---|---|---|---|
| Name fields | `first_name` + `last_name` | `company_name` (single field, mixed individual/business) | `firm_name` (business name only) |
| Role field | `role` (11 types) | `contact_type` (3 types: Contractor 99.85%, Owner, Others) | No field (all implicitly contractors) |
| Agent ID | `pts_agent_id` (present) | **NOT present** | **NOT present** |
| License | `license1` | `license_number` | `license_number` |
| Firm fields | `firm_name`, `firm_address`, etc. | No firm fields | No separate firm fields |
| Phone | **NOT present** | `phone`, `phone2` | `phone` |

#### Building Permits Contacts Role Breakdown (3pee-9qhc)

| Role | Count | % |
|---|---|---|
| contractor | 573,125 | 57.1% |
| authorized agent-others | 142,565 | 14.2% |
| architect | 94,795 | 9.4% |
| engineer | 68,714 | 6.8% |
| lessee | 42,323 | 4.2% |
| payor | 31,679 | 3.2% |
| pmt consultant/expediter | 25,571 | 2.5% |
| designer | 14,844 | 1.5% |
| project contact | 10,278 | 1.0% |
| attorney | 565 | 0.06% |
| subcontractor | 133 | 0.01% |

### Entity Resolution Keys (Priority Order)

1. **`pts_agent_id`** — Best key for building permits. Unique per actor. Only in `3pee-9qhc`.
2. **`license1` / `license_number`** — Works across all three contact datasets. Note the field name difference: `license1` in building contacts, `license_number` in electrical/plumbing.
3. **`sf_business_license_number`** — Present in all three. Good secondary key.
4. **Name + Company** — Fuzzy fallback. Use for owners/applicants who don't have license numbers. **Requires blocking strategy** (see Technical Decisions).

### Enrichment Datasets

| Dataset | Endpoint | Records | Purpose |
|---|---|---|---|
| **Building Permits** | `i98e-djp9` | ~1,282,446 | Join contact records to permit details (type, cost, location, dates, status) |
| **Building Inspections** | `vckc-dh2h` | ~670,946 | Has `inspector` field — needed for ground truth validation (Santos, Kong) |

---

## Deliverables

### 1. DuckDB Ingestion Pipeline (`src/ingest.py`)

Build a CLI tool that:
- Fetches all records from the three contact datasets via SODA API (paginated, **10K per page** to avoid timeouts)
- Fetches building permit records for enrichment
- Fetches building inspection records (for inspector data)
- Loads everything into a local DuckDB database (`data/sf_permits.duckdb`)
- Handles incremental updates (store last-fetched timestamp, only fetch new/updated records on re-run)
- Reports progress during ingestion (these are large datasets — show page count, records fetched, elapsed time)
- Reuse the existing `SODAClient` from `src/soda_client.py` for all API calls

**Schema design requirements:**

Normalize contact records across the three sources into a **unified `contacts` table**:

```sql
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,           -- 'building', 'electrical', 'plumbing'
    permit_number TEXT NOT NULL,
    role TEXT,                      -- normalized: 'contractor', 'architect', 'engineer', 'owner', 'agent', 'expediter', 'designer', 'lessee', 'payor', 'project_contact', 'attorney', 'subcontractor', 'other'
    name TEXT,                      -- normalized full name (from first_name+last_name or company_name or firm_name)
    first_name TEXT,                -- original first_name (building only)
    last_name TEXT,                 -- original last_name (building only)
    firm_name TEXT,                 -- original firm/company name
    pts_agent_id TEXT,              -- building contacts only
    license_number TEXT,            -- license1 (building) or license_number (electrical/plumbing)
    sf_business_license TEXT,       -- sf_business_license_number from all three
    phone TEXT,                     -- electrical/plumbing only
    address TEXT,                   -- normalized address
    city TEXT,
    state TEXT,
    zipcode TEXT,
    is_applicant TEXT,
    from_date TEXT,                 -- building contacts only
    entity_id INTEGER,             -- FK to entities table (populated after entity resolution)
    data_as_of TEXT
);
```

Additional tables:
- **`entities`** — resolved actors (deduplicated people/companies)
- **`relationships`** — co-occurrence edges
- **`permits`** — building permit enrichment data
- **`inspections`** — building inspection data (inspector, result, permit reference)
- **`ingest_log`** — tracking last fetch timestamp per dataset for incremental updates

Add indexes on: `permit_number`, `pts_agent_id`, `license_number`, `sf_business_license`, `entity_id`, `role`.

**CRITICAL:** The `estimated_cost` field in building permits is stored as TEXT, not numeric. Cast it during ingestion: `CAST(estimated_cost AS DOUBLE)`.

### 2. Entity Resolution (`src/entities.py`)

Build entity resolution that:
1. **Groups by `pts_agent_id`** (building contacts) — confidence: `high`
2. **Groups by `license_number`** across all three datasets (mapping `license1` → `license_number`) — confidence: `medium`
3. **Groups by `sf_business_license_number`** across all three — confidence: `medium`
4. **Fuzzy-matches remaining** by normalized name + company — confidence: `low`

Produces a canonical `entity_id` for each real-world actor.

**Entity table schema:**
```sql
CREATE TABLE entities (
    entity_id INTEGER PRIMARY KEY,
    canonical_name TEXT,            -- best name for display
    canonical_firm TEXT,            -- best firm name
    entity_type TEXT,               -- 'contractor', 'architect', 'engineer', 'owner', 'agent', 'expediter', 'designer', 'other'
    pts_agent_id TEXT,              -- if available
    license_number TEXT,            -- if available
    sf_business_license TEXT,       -- if available
    resolution_method TEXT,         -- 'pts_agent_id', 'license_number', 'sf_biz_license', 'fuzzy_name'
    resolution_confidence TEXT,     -- 'high', 'medium', 'low'
    contact_count INTEGER,          -- number of contact records resolved to this entity
    permit_count INTEGER,           -- number of unique permits
    source_datasets TEXT            -- comma-separated: 'building,electrical,plumbing'
);
```

**Role mapping** — normalize the 11 building permit roles + electrical/plumbing types to canonical entity types:

| Source Role | Canonical Type |
|---|---|
| contractor | contractor |
| authorized agent-others | agent |
| architect | architect |
| engineer | engineer |
| lessee | owner |
| payor | other |
| pmt consultant/expediter | expediter |
| designer | designer |
| project contact | other |
| attorney | other |
| subcontractor | contractor |
| Contractor (electrical/plumbing) | contractor |
| Owner (electrical) | owner |
| Others (electrical) | other |

**Fuzzy matching blocking strategy** (IMPORTANT — naive fuzzy matching on 1.8M records will never finish):
- Only fuzzy-match records that share the **same first 3 characters of normalized name** (blocking by trigram prefix)
- OR share the **same zipcode + role**
- Use simple Levenshtein distance or token-set ratio, threshold ≥ 0.85
- Only run fuzzy matching on records NOT already resolved by pts_agent_id, license, or business license
- Log stats: how many entities resolved by each method

### 3. Co-occurrence Graph (`src/graph.py`)

Build the relationship graph:
- **Edge definition:** Two entities have a relationship if they appear on the same permit.
- **Edge weight:** Number of permits they co-appear on.
- **Edge metadata:** Permit types, date range, total estimated cost, neighborhoods.
- Store as adjacency list in DuckDB `relationships` table.

```sql
CREATE TABLE relationships (
    entity_id_a INTEGER,
    entity_id_b INTEGER,
    shared_permits INTEGER,         -- count of co-occurrences
    permit_numbers TEXT,            -- comma-separated (first 20)
    permit_types TEXT,              -- distinct types seen
    date_range_start TEXT,
    date_range_end TEXT,
    total_estimated_cost DOUBLE,
    neighborhoods TEXT,             -- distinct neighborhoods
    PRIMARY KEY (entity_id_a, entity_id_b)
);
```

Support querying:
- "Show me everyone who has worked with Entity X" — 1-hop neighbors
- 2-hop traversal: "Who are the associates of Entity X's associates?"

### 4. Ground Truth Validation (`src/validate.py`)

**IMPORTANT DISTINCTION:** Some known actors appear in **contact data** (as contractors, agents, etc.) and some appear in **inspection data** (as DBI staff). The validation must search both.

#### Known Actors to Search For

**In Building Inspections data (DBI staff):**
- **Rodrigo Santos** — Former DBI senior inspector, convicted of bribery. Search the `inspector` field in Building Inspections (`vckc-dh2h`). Then find which permits he inspected, and look up who the contractors/architects were on those permits via the contacts data.
- **Florence Kong** — DBI permit technician, charged in corruption probe. May appear in inspections or in the Building Permit Addenda routing data (`87xy-gk8d`, `plan_checked_by` field).

**In Contact data (external actors):**
- **Bernard Curran** — Contractor linked to Santos corruption case. Should appear in contact data with a license number. Search `first_name`/`last_name` in building contacts and `company_name` in electrical contacts.
- **Contractors who paid bribes** — Search for patterns: same contractor appearing on permits inspected by known corrupt inspectors (Santos).

#### Validation Queries to Implement

1. **`search_entity(name)`** — Find an entity by name, return all permits and co-occurring entities
2. **`entity_network(entity_id, hops=2)`** — Return N-hop network around an entity
3. **`find_clusters()`** — Find tightly connected clusters of entities (potential rings). Use simple connected-component or community detection.
4. **`anomaly_scan()`** — Flag entities with unusual patterns:
   - Extremely high permit volume relative to peers
   - Always paired with same inspector/agent
   - Permits concentrated in narrow geography
   - Unusually fast permit approvals (filed_date to issued_date)
   - High cost permits with minimal review time
5. **`inspector_contractor_links(inspector_name)`** — Given an inspector name from the inspections data, find all permits they inspected, then find all contractors/entities on those permits. This is the key query for tracing Santos→Curran type relationships.

#### Success Criteria

- [ ] Can find Santos in inspections data (or determine he's not in the dataset and document why)
- [ ] Can find Curran in contacts data (or determine he's not in the dataset)
- [ ] Can trace inspector→contractor relationships (inspector_contractor_links works)
- [ ] Network reveals non-obvious connections (entities linked through shared permits)
- [ ] Anomaly patterns flag at least some suspicious patterns without being told names
- [ ] At least one "interesting" discovery — a pattern we didn't know about

### 5. New MCP Tools

Add these tools to the existing MCP server in `src/server.py`:

```python
@mcp.tool()
async def search_entity(name: str, entity_type: str = None) -> str:
    """Search for a person or company across all permit contact data.
    Returns entity details, permit history, and co-occurring entities."""

@mcp.tool()
async def entity_network(entity_id: str, hops: int = 1) -> str:
    """Get the relationship network around an entity.
    Returns connected entities with edge weights and shared permit details."""

@mcp.tool()
async def network_anomalies(min_permits: int = 10) -> str:
    """Scan for anomalous patterns in the permit network.
    Flags unusual concentrations, relationships, and timing patterns."""
```

These tools query the local DuckDB database, NOT the SODA API directly.

### 6. Documentation Updates

- **CHANGELOG.md** — Create with Phase 2 entry listing all new capabilities
- **CATALOG.md** — Update with DuckDB schema documentation
- **DECISIONS.md** — Add decisions: entity resolution approach, graph model, DuckDB choice, fuzzy matching blocking strategy
- **RESULTS.md** — Phase 2 benchmarks (ingestion time, entity resolution stats, query performance)
- **ARCHITECTURE.md** — Create. Document the full system: SODA API → DuckDB → Entity Resolution → Graph → MCP Tools

### 7. Tests

Add tests for:
- Ingestion pipeline (mock SODA responses, verify DuckDB schema)
- Entity resolution (known test cases with expected groupings)
- Graph construction (verify edge weights, hop traversal)
- Validation queries (verify search works, anomaly scan returns results)
- New MCP tools (integration tests)

Target: All existing tests still pass + new tests pass.

### 8. Configuration Updates

- Add `data/` to `.gitignore` (DuckDB file should not be committed)
- Add `duckdb` to dependencies in `pyproject.toml`
- Keep existing dependencies: `fastmcp>=2.0.0`, `httpx>=0.27.0`

---

## Technical Decisions

- **DuckDB over SQLite:** DuckDB handles analytical queries (aggregations, joins across million-row tables) much better. It's columnar, supports complex SQL, and has Python bindings. Perfect for "find all entities connected to X" type queries.
- **Local-first:** All data stored locally. No external database dependency. DuckDB file lives in `data/` directory (gitignored).
- **Incremental ingestion:** Store last-fetched timestamp per dataset in `ingest_log` table. Only fetch new/updated records on re-run.
- **SODA pagination:** Use `$offset` and `$limit` (**10,000 per page**, not 50K — larger pages risk timeouts on complex datasets). Use the `SODA_APP_TOKEN` from environment variable via the existing `SODAClient`.
- **Fuzzy matching uses blocking:** Do NOT compare all 1.8M records pairwise. Block by trigram prefix or zipcode+role before fuzzy comparison. This reduces comparisons from O(n²) to manageable levels.
- **Reuse existing code:** Use `SODAClient` from `src/soda_client.py`. Don't create a new API client.

---

## Implementation Order

1. **Config updates** — Add `data/` to `.gitignore`, add `duckdb` to `pyproject.toml`
2. **DuckDB schema + ingestion pipeline** — Get data loaded first
3. **Entity resolution** — Deduplicate and link actors
4. **Co-occurrence graph** — Build relationship edges
5. **Validation queries** — Search for known actors, run anomaly detection
6. **MCP tools** — Expose via MCP server
7. **Tests + documentation** — Full coverage
8. **Run ground truth search** — Actually execute the validation and report findings in RESULTS.md

---

## Important Notes

- The SODA API base URL is `https://data.sfgov.org/resource/{dataset_id}.json`
- App token goes in `X-App-Token` header (already handled by `SODAClient`)
- Existing `SODAClient` in `src/soda_client.py` has working SODA query patterns — **reuse it**
- DuckDB database file should be in `data/sf_permits.duckdb`
- All new code goes in `src/` alongside existing `server.py` and `tools/`
- Keep the existing 5 MCP tools working — Phase 2 adds to them, doesn't replace them
- Commit frequently with clear messages. Push when each deliverable is complete.

---

## Definition of Done

- [ ] 1.8M+ contact records ingested into DuckDB
- [ ] Building permits enrichment data loaded
- [ ] Building inspections data loaded (with inspector field)
- [ ] Entity resolution produces deduplicated actor list with confidence levels
- [ ] Co-occurrence graph built with weighted edges
- [ ] Can query "show me everyone who worked with [name]" and get meaningful results
- [ ] Can query "show me all contractors on permits inspected by [inspector]"
- [ ] Ground truth search executed — report on whether known bad actors are findable
- [ ] At least one anomaly pattern flagged
- [ ] 3 new MCP tools working (search_entity, entity_network, network_anomalies)
- [ ] All tests passing (old + new)
- [ ] Documentation updated (CHANGELOG, DECISIONS, ARCHITECTURE, RESULTS)
- [ ] `data/` in `.gitignore`, `duckdb` in `pyproject.toml`
- [ ] Everything committed and pushed
