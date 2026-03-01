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

---

## Decision 7: PostgreSQL (pgvector) for Production, DuckDB for Local Development

**Date:** 2026-02-15
**Status:** Decided — Dual-mode via DATABASE_URL detection

### Context

Phase 3+ requires persistent user data (accounts, auth tokens, watch items, feedback), RAG vector embeddings, and vision analysis sessions. DuckDB is excellent for analytical queries but doesn't support pgvector extensions or concurrent web connections well.

### Decision

Use PostgreSQL with pgvector in production (Railway), DuckDB locally. `src/db.py` auto-detects `DATABASE_URL` env var:
- Present → PostgreSQL mode (production)
- Absent → DuckDB mode (local development)

### Rationale

- **pgvector** provides native vector similarity search for RAG (1536-dim OpenAI embeddings)
- **PostgreSQL** handles concurrent web connections from Flask, cron jobs, and background workers
- **DuckDB** stays for local development — fast, zero-setup, no server dependency
- Startup migrations (`_run_startup_migrations()`) handle schema creation in both modes
- Same SQL works in both backends for most queries; db.py abstracts the differences

---

## Decision 8: Railway Deployment with GitHub Auto-Deploy

**Date:** 2026-02-15 (initial), 2026-02-17 (auto-deploy configured)
**Status:** Decided — Railway + GitHub auto-deploy from `main` branch

### Context

Need a deployment platform that supports Python, PostgreSQL with pgvector, automatic builds, and internal networking between services.

### Decision

Deploy on Railway with:
- **sfpermits-ai** service: Flask web app, auto-deploys on push to `main`
- **pgvector-db** service: PostgreSQL + pgvector, internal networking only
- GitHub auto-deploy: pushes to `main` trigger Railway builds automatically

### Rationale

- Railway supports NIXPACKS (auto-detects Python from `pyproject.toml`)
- Internal networking means Postgres is never exposed to the internet
- GitHub auto-deploy eliminates manual `railway up` CLI commands
- `railway redeploy` only restarts old images — must push new code to trigger fresh builds
- Fallback: `railway up` from CLI if auto-deploy breaks

---

## Decision 9: Three-Layer Backup Strategy

**Date:** 2026-02-17
**Status:** Decided — Railway native + pg_dump cron + admin auto-seed

### Context

Production Postgres was wiped during a database migration, losing all user accounts. No backups existed. Need a recovery strategy that prevents this from happening again.

### Decision

Three complementary layers:
1. **Railway native backups** — Daily + Weekly snapshots via Railway dashboard
2. **pg_dump cron** — `POST /cron/backup` endpoint, CRON_SECRET auth, custom-format dumps
3. **Admin auto-seed** — If `users` table is empty and `ADMIN_EMAIL` is set, create admin account on startup

### Rationale

- Railway native backups are the first line of defense (point-in-time recovery)
- pg_dump provides portable backups that can be restored anywhere
- Admin auto-seed ensures the system is never completely locked out after a wipe
- User-generated data (accounts, watches, feedback) is the only data that genuinely needs backups — permit/entity/knowledge data is regenerable from SODA API and git

---

## Decision 10: Claude Vision API for Plan Analysis

**Date:** 2026-02-16
**Status:** Decided — Anthropic Claude Vision API with async job processing

### Context

Phase 4 requires analyzing architectural drawings (PDFs) for EPR compliance — checking energy requirements, plumbing code, structural elements. This is a visual analysis task that requires understanding building plans.

### Decision

Use Anthropic's Claude Vision API via `src/vision/`:
- PDFs converted to base64 images (`pdf_to_images.py`)
- Sent to Claude Vision with structured EPR prompts (`prompts.py`)
- Results stored in `plan_analysis_*` PostgreSQL tables
- Full analysis runs as async background jobs to avoid HTTP timeouts

### Rationale

- Claude Vision handles architectural drawings well (spatial reasoning, text recognition)
- Async processing prevents web request timeouts on multi-page PDFs
- Structured prompts ensure consistent EPR checking across submissions
- Results persist in Postgres for session continuity and annotation

### Alternatives Considered

- **OpenAI Vision:** Evaluated — Claude Vision showed better spatial understanding for architectural plans
- **Custom CV pipeline:** Rejected — would require significant training data and wouldn't match the quality of foundation model vision

## Decision 11: Annotation Matching Strategy for Plan Version Comparison

**Date:** 2026-02-22
**Status:** Decided — Token overlap threshold=2 with type-first bucketing and position tiebreak

### Context

The Analysis History revision tracking feature (Phases E/F) needs to detect which annotations in a v2 plan upload correspond to the same physical element as annotations in v1. Claude Vision produces non-deterministic label text across runs — the same stamp might be described as `"PE Stamp: CA #C12345 — John Smith"` in one run and `"Architect Stamp Present — RA License"` in another.

### Decision

Use token overlap (threshold ≥ 2 shared tokens after stopword removal) as the primary matching signal, with three refinements:

1. **Type-first bucketing**: compare v2 annotations only against v1 annotations of the same `type` field. Reduces false positives from unrelated domain terms.
2. **Position tiebreak**: when multiple candidates pass the token test, prefer the one with smallest Euclidean distance in (x, y). Handles split annotations.
3. **Stamp special case**: for `type="stamp"`, lower threshold to 1 — the physical element is unique per page, so any shared meaningful token (`stamp`, `pe`, `architect`) is sufficient.

### Rationale

Tested against real-world prod annotation pairs from 13 sessions of the same PDF. Token overlap ≥ 2 catches ~75% of same-concept annotations (code refs, EPR issues, reviewer notes, occupancy labels) with ~95% precision. The 25% miss rate is concentrated in stamps (detail-vs-generic collapse) and abbreviations — both low-frequency in SF permit plan sets.

### Why NOT Semantic Similarity

Annotation labels are short (≤60 chars), structured, and domain-specific. CBC section numbers (`CBC 1020.1`) and AHJ terminology are exactly the vocabulary where token overlap outperforms embeddings. Embeddings conflate related-but-distinct code sections (CBC 1006 vs CBC 1020 — both egress-related but different requirements). Given the current data volume (18 sessions in prod), the cost/latency of embedding calls is not justified.

### Failure Modes (Known)

- **Stamp detail collapse**: `"PE Stamp: CA #C12345"` → `"Stamp present"` — mitigated by stamp special case (threshold=1)
- **Merge/split**: one v1 annotation covering multiple sheets splits into per-sheet v2 annotations — use type coverage scoring
- **Type reassignment**: `epr_issue` in v1 becomes `general_note` in v2 — cross-type fallback at threshold ≥ 3
- **Abbreviations**: `"FEC cabinet"` vs `"fire extinguisher cabinet"` — pre-expand known AHJ abbreviations

## Decision 12: Sheet Number as Fingerprinting Signal for Plan Version Matching

**Date:** 2026-02-22
**Status:** Decided — Use (page_number, sheet_number) composite key; sheet_number alone is insufficient

### Context

Revision tracking needs to match pages across v1/v2 uploads of the same plan set. Sheet numbers (e.g. `A0.0`, `A2.1`) are extracted by Claude Vision from title blocks during page analysis. The question was whether sheet number extraction is reliable enough to use as a fingerprinting key.

### Findings from Prod Data

Analyzed 18 sessions across 4 distinct PDFs:

- **PrelimPermitSet11.14 (12-page SF plan set)**: 13 sessions, 100% sheet number consistency for every page that was sampled. `A0.0` always appeared on page 1; `A2.0` always on page 7; etc. Format: `X#.#` (Arch-standard) universally.
- **medeek-foundation-plan.pdf (1-page structural)**: sheet number `3` — plain integer, no title block standard. 100% consistent across 2 sessions.
- **medeek-dormer-framing.pdf (1-page structural)**: `S1.4` — consistent.
- **sudbury-sample-permit-drawings.pdf (17-page Canadian forms)**: 0% sheet number extraction — no architectural title blocks present.
- **test_plan.pdf (synthetic)**: 0% — no title block.

### Decision

Use `(page_number, sheet_number)` as a composite fingerprint key. Primary match on `page_number` (always present), confirm with `sheet_number` when non-null.

### Critical Constraint: A1.1 Collision

In PrelimPermitSet, `A1.1` appears on **both page 6 (FLOOR PLANS) and page 11 (DETAILS)**. Sheet number is not unique within a document. Never use sheet_number as the sole key — always anchor to page_number.

### Fallback for Non-DBI Documents

Sudbury-style forms packages, plugin-generated structural drawings, and synthetic test files produce 0% sheet number coverage. When `sheet_number` is null across all extracted pages, fall back to page_number-only matching with positional annotation heuristics.

### Guard Against Hollow Sessions

One prod session (`oeNQCmMYRT2evqRjO1-F7g`) has 0 extractions despite being linked to the 12-page PrelimPermitSet. Any fingerprinting logic must check `len(extractions) == 0` before attempting to match — never assume a completed session has data.

## Decision 13: CSP `unsafe-inline` for HTMX Compatibility

**Date:** 2026-02-26
**Status:** Decided — Accept `unsafe-inline` now, migrate to nonce-based CSP later

### Context

Sprint 62C added Content-Security-Policy headers. HTMX requires inline event handlers (`hx-on:*` attributes, inline `<script>` blocks), and many templates use inline `<style>` elements.

### Decision

Use `'unsafe-inline'` for both `script-src` and `style-src` in the CSP directive. This is less restrictive than a nonce-based CSP but necessary for the current HTMX + inline style architecture.

### Trade-offs

- **Pro:** Immediate security improvement (CSP blocks XSS from external scripts, frame-ancestors blocks clickjacking)
- **Con:** `unsafe-inline` weakens script-src protection against reflected XSS
- **Mitigation:** X-Content-Type-Options nosniff + X-Frame-Options DENY + strict Referrer-Policy

### Future Migration Path

A future sprint can implement nonce-based CSP by:
1. Generating a per-request nonce in `@app.before_request`
2. Adding `nonce="{{ csp_nonce }}"` to all `<script>` and `<style>` tags
3. Replacing `'unsafe-inline'` with `'nonce-{value}'` in the CSP header

## Decision 14: Three-Tier Feature Gating

**Date:** 2026-02-26
**Status:** Decided — FREE / AUTHENTICATED / ADMIN tiers

### Context

Sprint 62D added feature access control for launch hardening. All features were previously visible to unauthenticated visitors.

### Decision

Three-tier enum: `FREE` (search, landing), `AUTHENTICATED` (analyze, brief, portfolio, watch, projects), `ADMIN` (ops, QA, costs). A `PREMIUM` tier is commented as reserved for future paid features.

### Implementation

- `FeatureTier` enum in `web/feature_gate.py`
- Feature registry maps 14 features to minimum tier
- `@app.context_processor` injects `gate` dict into all templates
- Nav items show greyed "Sign up" badges for locked features

## Decision 10: Tailwind v4 + Alpine.js for Dark Factory at Scale

**Date:** 2026-03-01
**Status:** Decided — Adopt Tailwind v4 + Alpine.js for all new pages, migrate on touch

### Context

Custom CSS tokens (DESIGN_TOKENS.md) served well through Sprint 69 but became a bottleneck:
- 26 hand-maintained components with copy-paste HTML/CSS
- Every sprint agent re-interprets token specs differently
- Design lint catches violations but doesn't prevent them
- New page builds take 2-3x longer than utility-first approach

### Decision

- **New pages**: Tailwind v4 (CDN for mockups, build pipeline for prod) + Alpine.js for interactivity
- **Existing pages**: Convert on touch (when a page is modified for feature work, migrate it)
- **ECharts** for product page data visualizations (not D3 — too complex for agent builds)
- **Custom CSS tokens remain authoritative** for obsidian palette colors, font families, and brand identity
- Tailwind config extends with our token colors/fonts — single source of truth

### Rationale

- Agent throughput: Tailwind utility classes are self-documenting — no "did I use the right token?" question
- Alpine.js replaces ad-hoc JS/jQuery for interactive elements (toggles, dropdowns, tabs)
- Mockup → production gap closes: Tailwind in mockups = same CSS in production

## Decision 11: Honeypot Data Strategy — Curated Real Data

**Date:** 2026-03-01
**Status:** Decided

### Context

The landing page showcases real SF permit data to demonstrate product value. Options:
1. Live-dynamic (query on every page load)
2. Fake/synthetic data
3. Curated real data, refreshed periodically

### Decision

**Curated real data, refreshed nightly.** Not fake, not live-dynamic.

### Rules

- **Anonymization**: Professional names shown (public record). Individual homeowner names anonymized on public/honeypot pages.
- **Environment borders**: staging=amber outline, honeypot=red outline, prod=none. Prevents accidentally thinking you're on prod.
- **Persona color coding**: QA navigation uses persona colors (homeowner=teal, architect=purple, expediter=amber, new-visitor=pink).
- **HONEYPOT_MODE env var**: 0=disabled (current), 1=enabled. Controls whether landing page shows curated data or generic demo.

## Decision 12: Landing Page Data Claims Must Be Defensible

**Date:** 2026-03-01
**Status:** Decided

### Context

QS13 preflight cost data validation found:
- "73% of kitchen remodels get sent back" — actual code shows 12% revision probability
- "$847/day commercial carrying cost" — illustrative only, no economic model
- "47 permits stalled at SFPUC" — placeholder, real queue data exists but isn't wired
- "4.2 months average kitchen remodel" — unit mismatch (p50=21 days)

### Decision

All public-facing data claims must be:
1. **Sourced from actual DB queries** or clearly marked as illustrative examples
2. **Within 2x of real data** — 73% vs 12% is a 6x overstatement, unacceptable
3. **Labeled with source** — "Based on 1.1M permits" footer on each data card
4. **Refreshed nightly** — not static mockup numbers that drift from reality

Placeholder numbers are acceptable in mockups during development (HONEYPOT_MODE=0) but must be replaced with real queries before HONEYPOT_MODE=1.
