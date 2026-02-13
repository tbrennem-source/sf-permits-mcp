# Architecture Decisions Log

## Decision 1: Build from Scratch vs Fork Existing Socrata MCP Server

**Date:** 2026-02-12
**Status:** Decided — Build from scratch with Python/FastMCP

### Context

Before building, we evaluated two existing Socrata MCP servers:

1. **socrata/odp-mcp** — Official Socrata MCP server (TypeScript, Dec 2025)
2. **OpenGov Socrata MCP Server** — By Scott Robbin (Go, MIT license)

### Evaluation: socrata/odp-mcp

Cloned and reviewed thoroughly. It's a well-engineered, production-ready generic SODA client:

**What it provides:**
- 4 tools: `list_datasets`, `get_metadata`, `preview_dataset`, `query_dataset`
- Full SoQL query builder with structured conditions, aggregations, injection prevention
- Multi-domain support (works with any Socrata portal including data.sfgov.org)
- App token auth, LRU caching, rate limiting, retry logic
- Dual transport: stdio + HTTP bridge
- 19 test suites

**What it does NOT provide:**
- No domain-specific tools (`search_permits`, `get_permit_details`, `permit_stats`, etc.)
- No dataset catalog awareness (doesn't know building permits = `i98e-djp9`)
- No field-level schema knowledge (doesn't know `neighborhoods_analysis_boundaries` or `adu`)
- No response formatting optimized for Claude consumption
- No cross-dataset intelligence

**Language:** TypeScript (Node.js). Our target stack is Python/FastMCP to match our existing chief-mcp-server deployment patterns.

### Evaluation: OpenGov Socrata MCP Server (Scott Robbin)

**Not found.** Searched GitHub for "opengov socrata", "srobbin socrata mcp", and variations. No matching repo exists publicly. May be private, renamed, or removed.

### Decision: Build from Scratch

**Reasons:**

1. **Wrong language.** odp-mcp is TypeScript. We chose Python/FastMCP to match our Chief MCP server's deployment patterns (FastMCP, Railway/NIXPACKS, same ops tooling). Forking means maintaining a TS codebase alongside our Python ecosystem.

2. **Wrong abstraction level.** odp-mcp is a generic SODA browser — it exposes raw SoQL queries to Claude. Our spec requires *domain-specific tools* where Claude says "search permits in the Mission over $100K" and gets structured results, not "run this SoQL query against endpoint i98e-djp9 with these parameters."

3. **The SODA client is the easy part.** Our `soda_client.py` is ~60 lines. The real value is the dataset catalog, field mappings, response formatters, and domain-specific tool interfaces. odp-mcp doesn't help with any of that.

4. **Future phases need custom tools.** Phases 2-4 add fraud detection (contractor network analysis), permit facilitation, and cross-dataset joins. These require deep domain knowledge baked into the server, not a generic query proxy.

**What we DID take from odp-mcp:**
- Validated that SoQL structured conditions with operator mapping is the right pattern
- Confirmed that injection prevention via parameter validation (not raw string interpolation) is important
- Their rate limiter design (token bucket) is a good reference for production hardening

### Alternatives Considered

- **Fork odp-mcp and extend:** Rejected — wrong language, and the extension surface would be larger than building from scratch
- **Use odp-mcp as a secondary MCP alongside ours:** Possible for Phase 2+ if we need generic SODA browsing alongside domain-specific tools. Noted for future consideration.
- **Use sodapy (Python SODA client library):** Evaluated — it's archived but functional. Decided to write our own thin client (~60 lines with httpx) since sodapy has dependencies we don't need and is no longer maintained. Our client is simple enough that maintaining it is trivial.

---

## Decision 2: SODA Client — Custom vs sodapy

**Date:** 2026-02-12
**Status:** Decided — Custom thin client with httpx

### Context

`sodapy` is the standard Python client for SODA API. It's archived (no longer maintained) but pip-installable and functional.

### Decision

Build a custom thin client (`soda_client.py`) using `httpx`:
- ~60 lines of code
- Async-native (httpx.AsyncClient)
- Only the SoQL parameters we actually use
- No dependency on an archived package
- Easy to extend for Phase 2+ needs

### Rationale

- sodapy is synchronous (uses `requests`). We want async for FastMCP.
- sodapy has features we don't need (upsert, replace, dataset creation)
- Our client is simple enough that maintenance cost is near zero
- If we need sodapy's features later, we can add it alongside our client

---

## Decision 3: No Dockerfile — Use NIXPACKS

**Date:** 2026-02-12
**Status:** Decided — Deferred to Phase 4 (Railway deployment)

When we deploy to Railway, we'll use NIXPACKS (automatic Python environment detection) matching our Chief MCP server pattern. No Dockerfile needed. Railway reads `pyproject.toml` and builds automatically.

---

## Decision 4: DuckDB over SQLite for Local Analytics

**Date:** 2026-02-13
**Status:** Decided — DuckDB

### Context

Phase 2 requires local storage for 1.8M+ contact records, entity resolution, and graph queries. The workload is analytical: aggregations, self-joins across million-row tables, GROUP BY with complex expressions, and graph traversal via SQL set operations.

### Decision

Use DuckDB (`data/sf_permits.duckdb`) instead of SQLite.

### Rationale

- **Columnar storage.** DuckDB is columnar, which is significantly faster for analytical queries (aggregations, GROUP BY, COUNT DISTINCT) over wide tables. SQLite is row-oriented and optimized for OLTP.
- **Self-join performance.** The co-occurrence graph is built via a self-join on the contacts table (1.8M rows joined to itself on permit_number). DuckDB handles this in seconds; SQLite would struggle without extensive manual optimization.
- **Rich SQL dialect.** DuckDB supports `LIST()`, `list_sort()`, `list_slice()`, `array_to_string()`, `STRING_AGG()`, `MEDIAN()`, and `DATEDIFF()` natively. These are used extensively in graph construction and anomaly detection. SQLite lacks most of these.
- **No server dependency.** Like SQLite, DuckDB is embedded — single file, no daemon, no setup. Fits our local-first architecture.
- **Python bindings.** `duckdb` pip package provides direct Python integration. Connection semantics are similar to SQLite (`duckdb.connect(path)`).

### Trade-offs

- DuckDB is less widely deployed than SQLite. But we only use it server-side, so client compatibility doesn't matter.
- DuckDB files are not human-readable. Acceptable since the data is regenerable from SODA API.

---

## Decision 5: Entity Resolution — Multi-Key Cascading with Fuzzy Fallback

**Date:** 2026-02-13
**Status:** Decided — 5-step cascade (pts_agent_id, license, biz license, fuzzy name, singletons)

### Context

1.8M contact records across 3 datasets refer to the same real-world actors using inconsistent identifiers. Building contacts have `pts_agent_id` + `license1` + names. Electrical contacts have `license_number` + `company_name`. Plumbing contacts have `license_number` + `firm_name`. No single key spans all three.

### Decision

Cascade through identifier keys in decreasing confidence order:

1. **`pts_agent_id`** — building contacts only. Unique per actor in the DBI system. High confidence.
2. **`license_number`** — present in all 3 datasets (mapped from `license1` in building). If a license already belongs to a step-1 entity, merge; otherwise create new entity. Medium confidence.
3. **`sf_business_license`** — present in all 3 datasets. Same merge logic as step 2. Medium confidence.
4. **Fuzzy name matching** — for remaining unresolved contacts that have a non-empty name. Low confidence.
5. **Singletons** — one entity per remaining contact (no name, no keys). Low confidence.

### Blocking Strategy for Fuzzy Matching

Naive pairwise comparison on 1.8M records (3.24 trillion pairs) is infeasible. We block by the first 3 characters of `UPPER(name)`, reducing each block to a manageable size. Within each block, we use greedy clustering with token-set Jaccard similarity >= 0.75.

Token-set Jaccard (`|A intersection B| / |A union B|` on whitespace-split uppercase tokens) was chosen over Levenshtein because it handles word reordering (e.g., "Smith Construction" vs "Construction Smith") and is fast to compute without external dependencies.

### Merge Behavior

Steps 2 and 3 check whether the key already belongs to an entity from a prior step. If so, they assign the new contacts to the existing entity and update its counts/sources. This prevents creating duplicate entities when the same actor appears with both `pts_agent_id` and `license_number`.

### Alternatives Considered

- **Single-key resolution (license only):** Rejected — would miss ~57% of building contacts that have `pts_agent_id` but no license, and all plumbing contacts with only firm_name.
- **External dedupe libraries (dedupe, recordlinkage):** Rejected — adds heavy dependencies and ML training overhead. The cascading key approach handles the structured identifiers directly. Fuzzy matching handles the long tail.
- **Phonetic matching (Soundex, Metaphone):** Not used — our name data is mostly business names, not personal names. Token-set similarity handles abbreviations and word order better than phonetic encoding for firm names.

---

## Decision 6: Graph Model — Co-occurrence via Self-Join, SQL-First

**Date:** 2026-02-13
**Status:** Decided — SQL self-join in DuckDB, no external graph library

### Context

The network model connects entities that co-appear on permits. We need to build edges, store edge metadata (shared permit count, cost, neighborhoods), and support 1-hop and N-hop traversal queries.

### Decision

Build the graph entirely in SQL via a self-join on the `contacts` table, store edges in a `relationships` table, and query via SQL. No external graph library (NetworkX, igraph, neo4j).

### Implementation

The core edge computation is a single INSERT...SELECT:

```sql
INSERT INTO relationships (entity_id_a, entity_id_b, shared_permits, ...)
SELECT a.entity_id, b.entity_id, COUNT(DISTINCT a.permit_number), ...
FROM contacts a
JOIN contacts b
    ON a.permit_number = b.permit_number
    AND a.entity_id < b.entity_id
LEFT JOIN permits p ON a.permit_number = p.permit_number
WHERE a.entity_id IS NOT NULL AND b.entity_id IS NOT NULL
GROUP BY a.entity_id, b.entity_id
```

The canonical ordering (`a.entity_id < b.entity_id`) avoids duplicate edges and self-loops. The LEFT JOIN to `permits` enriches edges with cost, type, date, and neighborhood data.

N-hop traversal is done in Python by iteratively expanding a frontier set and querying for neighbors at each hop. This is simple BFS, not recursive SQL.

### Rationale

- **DuckDB handles the self-join.** The contacts table has ~1.8M rows, but the join is on `permit_number` (indexed), and DuckDB's columnar engine handles the aggregation efficiently.
- **SQL-first avoids data movement.** Loading 1.8M rows into a Python graph library would require significant memory and serialization overhead. Keeping computation in SQL means only query results leave DuckDB.
- **Simple storage.** The `relationships` table is a standard adjacency list. No proprietary graph format to maintain.
- **Sufficient for our queries.** We need 1-hop neighbors, 2-hop networks, connected components, and anomaly detection. All of these work with simple SQL + Python BFS. We don't need shortest-path, PageRank, or other algorithms that would justify a graph engine.

### Alternatives Considered

- **NetworkX:** Evaluated — good for algorithms but requires loading the full graph into memory. At scale (100K+ edges), memory and startup cost become significant. Also adds a dependency.
- **Neo4j:** Rejected — server dependency, operational overhead. Overkill for a single-user MCP server querying a static dataset.
- **DuckDB recursive CTEs:** Considered for N-hop traversal. Decided against because DuckDB's recursive CTE support is functional but the Python frontier-expansion approach is clearer and easier to debug.
