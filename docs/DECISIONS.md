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
