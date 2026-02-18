# SF Permits MCP Server

## Quick Orientation

This is a Python/FastMCP MCP server providing San Francisco building permit data, entity network analysis, AI-powered permit guidance, and AI vision plan analysis via 14 tools + a Flask web UI.

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
  server.py             # FastMCP entry point, registers 14 tools
  soda_client.py        # Async SODA API client (httpx)
  formatters.py         # Response formatting for Claude
  db.py                 # DuckDB + PostgreSQL dual-mode connections, points_ledger table
  knowledge.py          # KnowledgeBase singleton, semantic index
  ingest.py             # SODA -> DuckDB pipeline
  entities.py           # 5-step entity resolution cascade
  graph.py              # Co-occurrence graph (SQL self-join)
  validate.py           # Anomaly detection queries
  report_links.py       # External links for property reports
  tools/                # 14 tool implementations (5 SODA, 3 DuckDB, 5 Knowledge, 1 Vision)
  vision/               # AI vision modules (Claude Vision API)
    client.py           # Anthropic Vision API wrapper
    pdf_to_images.py    # PDF-to-base64 image conversion
    prompts.py          # EPR check prompts for architectural drawings
    epr_checks.py       # Vision-based EPR compliance checker
web/                    # Flask + HTMX web UI (deployed on Railway)
  app.py                # Routes, tool orchestration, cron endpoints
  activity.py           # Feedback, bounty points, admin users
  email_brief.py        # Morning brief email delivery
  email_triage.py       # Nightly triage report email delivery
  auth.py               # Magic-link auth, user management
  brief.py              # Morning brief data assembly
  regulatory_watch.py   # Regulatory watch CRUD + query helpers
data/knowledge/         # 4-tier knowledge base (gitignored tier4)
  tier1/                # 30 structured JSON files — loaded at startup
  tier2/                # Raw text info sheets
  tier3/                # Administrative bulletins
  tier4/                # Full code corpus (Planning Code 12.6MB + BICC 3.6MB)
scripts/                # CLI tools
  feedback_triage.py    # 3-tier feedback classification + auto-resolve
tests/                  # 812 tests
datasets/               # SODA dataset catalog (22 datasets, 13.3M records)
docs/                   # Architecture, decisions, contact data analysis
```

## Key Numbers

- **14 tools**: 5 SODA API (Phase 1), 3 DuckDB (Phase 2), 5 Knowledge (Phase 2.75), 1 Vision (Phase 4)
- **22 SODA datasets**, 13.3M records cataloged
- **DuckDB**: 1.8M contacts -> 1M entities -> 576K relationship edges
- **PostgreSQL (prod)**: 5.6M rows, 8 tables, 2.05 GB on Railway
- **Knowledge base**: 30 tier1 JSON files, 71 semantic concepts, 640 aliases
- **Tests**: 951 passing (888 + 63 new)
- **Live**: https://sfpermits-ai-production.up.railway.app

## Current State

Phases 1 through 3.5 complete. Phase 4 partial: AI Vision plan analysis (analyze_plans tool, vision EPR checks) deployed. Regulatory watch system (admin CRUD, brief/report integration) deployed. RAG, nightly refresh planned but not started. User said "before executing rag, let's regroup and think it through" — do NOT start RAG without explicit direction.

## Railway Production Infrastructure

**Live URL**: https://sfpermits-ai-production.up.railway.app
**Project**: sfpermits-ai (Railway)

### Services

| Service | Role | Status |
|---|---|---|
| **sfpermits-ai** | Flask web app (auto-deploys from `main` branch) | Active |
| **pgvector-db** | PostgreSQL + pgvector — user data, RAG embeddings, permit changes | Active, primary DB |
| **pgVector-Railway** | pgvector instance (appears unused, has empty volume) | Active |
| Postgres | Old DB (removed, pending deletion, volume has 5.6GB data) | Removed |
| Postgres-CrX7 | Old DB (removed, pending deletion, volume has 1.1GB data) | Removed |

### Database (pgvector-db)

The app's `DATABASE_URL` points to `pgvector-db.railway.internal:5432` — **only reachable from within Railway's network**, not from local machines.

**Tables on pgvector-db:**
- User tables: `users`, `auth_tokens`, `watch_items`, `feedback`, `activity_log`, `points_ledger`
- Permit tracking: `permit_changes`, `cron_log`, `regulatory_watch`
- Vision: `plan_analysis_sessions`, `plan_analysis_images`, `plan_analysis_jobs`
- RAG: `knowledge_chunks` (pgvector embeddings, ~624 chunks)
- Note: bulk permit/entity/relationship data is NOT in Postgres — that's in local DuckDB

### Deploying to Production

**IMPORTANT**: GitHub auto-deploy may not be configured. Pushing to `main` does NOT reliably trigger a Railway build. After merging to main and pushing, you MUST deploy explicitly:

```bash
# Deploy from local (builds fresh from current directory):
cd /Users/timbrenneman/AIprojects/sf-permits-mcp && railway service link sfpermits-ai && railway up

# Verify deploy succeeded:
railway deployment list                 # Check status
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool
```

**DO NOT** use `railway redeploy --yes` — it restarts the old image without rebuilding from new code.

### Interacting with Railway

```bash
# CLI basics (must be in project root: /Users/timbrenneman/AIprojects/sf-permits-mcp)
railway status                          # Current project/service/env
railway service link <service-name>     # Switch active service context
railway variable list                   # Show env vars for linked service
railway logs -n 100                     # Recent logs for linked service
railway deployment list                 # Recent deployments

# You CANNOT connect to pgvector-db from local — it's internal-only.
# To check prod DB state, use the /health endpoint:
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool

# Trigger backup:
curl -s -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-production.up.railway.app/cron/backup

# Key env vars are on the sfpermits-ai service:
#   DATABASE_URL, CRON_SECRET, ADMIN_EMAIL, INVITE_CODES,
#   SMTP_HOST/PORT/FROM/USER/PASS, ANTHROPIC_API_KEY, OPENAI_API_KEY
```

### Backups

See `docs/BACKUPS.md` for full strategy. Key points:
- Admin auto-seed: empty `users` table + `ADMIN_EMAIL` env var → admin account created on startup
- `POST /cron/backup` — pg_dump of user-data tables (CRON_SECRET auth)
- `python -m scripts.db_backup` — local CLI for backup/restore
- Railway native backups: enable Daily + Weekly in dashboard → pgvector-db → Settings → Backups

### What's recoverable vs. what needs backups

| Data | Source of truth | Recovery |
|---|---|---|
| Permits, contacts, entities, relationships | SODA API → DuckDB | `python -m src.ingest && python -m src.entities && python -m src.graph` |
| Knowledge base (tier1-3) | git (`data/knowledge/`) | Already in repo |
| Knowledge base (tier4) | Local files (gitignored, >1MB each) | Manual — keep local copies |
| RAG embeddings | pgvector-db `knowledge_chunks` | Re-run `POST /cron/rag-ingest` |
| Users, watches, feedback | pgvector-db | **Needs backups** — no external source |

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
