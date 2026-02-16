# SF Permits MCP Server

## Quick Orientation

This is a Python/FastMCP MCP server providing San Francisco building permit data, entity network analysis, and AI-powered permit guidance via 13 tools + a Flask web UI.

**Start here to understand the project:**
1. `README.md` — tools, architecture, setup, project phases
2. `docs/ARCHITECTURE.md` — data flow, DuckDB schema, knowledge base tiers, decision tools, web UI, database architecture
3. `docs/DECISIONS.md` — why we built from scratch, DuckDB over SQLite, entity resolution strategy, SQL-first graph model
4. `CHANGELOG.md` — what was built in each phase (reverse chronological)

**Knowledge base documentation (for understanding the curated permitting data):**
5. `data/knowledge/SOURCES.md` — complete inventory of all 21 tier1 JSON files, tier2 raw text, tier3 admin bulletins, tier4 code corpus
6. `data/knowledge/GAPS.md` — known gaps, resolved gaps, Amy interview questions
7. `data/knowledge/INGESTION_LOG.md` — chronological log of all 8 ingestion sessions

**External state:**
- Chief brain state: `projects/sf-permits-mcp/STATUS.md` (via chief MCP server)

## Project Structure

```
src/                    # MCP server code
  server.py             # FastMCP entry point, registers 13 tools
  soda_client.py        # Async SODA API client (httpx)
  formatters.py         # Response formatting for Claude
  db.py                 # DuckDB + PostgreSQL dual-mode connections
  knowledge.py          # KnowledgeBase singleton, semantic index
  ingest.py             # SODA -> DuckDB pipeline
  entities.py           # 5-step entity resolution cascade
  graph.py              # Co-occurrence graph (SQL self-join)
  validate.py           # Anomaly detection queries
  tools/                # 13 tool implementations (5 SODA, 3 DuckDB, 5 Knowledge)
web/                    # Flask + HTMX web UI (deployed on Railway)
  app.py                # Routes, tool orchestration
data/knowledge/         # 4-tier knowledge base (gitignored tier4)
  tier1/                # 21 structured JSON files, 1.15 MB — loaded at startup
  tier2/                # Raw text info sheets
  tier3/                # Administrative bulletins
  tier4/                # Full code corpus (Planning Code 12.6MB + BICC 3.6MB)
tests/                  # 289 tests
datasets/               # SODA dataset catalog (22 datasets, 13.3M records)
docs/                   # Architecture, decisions, contact data analysis
```

## Key Numbers

- **13 tools**: 5 SODA API (Phase 1), 3 DuckDB (Phase 2), 5 Knowledge (Phase 2.75)
- **22 SODA datasets**, 13.3M records cataloged
- **DuckDB**: 1.8M contacts -> 1M entities -> 576K relationship edges
- **PostgreSQL (prod)**: 5.6M rows, 7 tables, 2.05 GB on Railway
- **Knowledge base**: 21 tier1 JSON files, 1.15 MB, 78 semantic concepts, 692 aliases
- **Tests**: 748 passing
- **Live**: https://sfpermits-ai-production.up.railway.app

## Current State

Phases 1 through 3.5 complete. Phase 4 (RAG, nightly refresh, regulation monitoring) planned but not started. User said "before executing rag, let's regroup and think it through" — do NOT start RAG without explicit direction.

## Development

```bash
pip install -e ".[dev]"
python -m src.server          # MCP server
python -m web.app             # Web UI
pytest tests/ -v              # Tests
```

Database regeneration (from SODA API):
```bash
python -m src.ingest && python -m src.entities && python -m src.graph && python -m src.validate all
```

## Branch

Working branch: `claude/sad-williams` (worktree at `.claude/worktrees/sad-williams`)
