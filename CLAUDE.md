# SF Permits MCP Server

## Quick Orientation

This is a Python/FastMCP MCP server providing San Francisco building permit data, entity network analysis, AI-powered permit guidance, and AI vision plan analysis via 21 tools + a Flask web UI.

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
  server.py             # FastMCP entry point, registers 21 tools
  soda_client.py        # Async SODA API client (httpx)
  formatters.py         # Response formatting for Claude
  db.py                 # DuckDB + PostgreSQL dual-mode connections, points_ledger table
  knowledge.py          # KnowledgeBase singleton, semantic index
  ingest.py             # SODA -> DuckDB pipeline
  entities.py           # 5-step entity resolution cascade
  graph.py              # Co-occurrence graph (SQL self-join)
  validate.py           # Anomaly detection queries
  report_links.py       # External links for property reports
  tools/                # 21 tool implementations (8 SODA, 3 Entity, 5 Knowledge, 2 Facilitation, 2 Vision, 1 Addenda)
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
  tier1/                # 39 structured JSON files — loaded at startup
  tier2/                # Raw text info sheets
  tier3/                # Administrative bulletins
  tier4/                # Full code corpus (Planning Code 12.6MB + BICC 3.6MB)
scripts/                # CLI tools
  feedback_triage.py    # 3-tier feedback classification + auto-resolve
tests/                  # 1,075+ tests
datasets/               # SODA dataset catalog (22 datasets, 13.3M records)
docs/                   # Architecture, decisions, contact data analysis
```

## Key Numbers

- **21 tools**: 8 SODA API (Phase 1), 3 Entity/Network (Phase 2), 5 Knowledge (Phase 2.75), 2 Facilitation (Phase 3.5), 2 Vision (Phase 4), 1 Addenda (Phase 5)
- **22 SODA datasets**, 13.3M records cataloged
- **DuckDB**: 1.8M contacts -> 1M entities -> 576K relationship edges
- **PostgreSQL (prod)**: 5.6M rows, 2.05 GB on Railway
- **Knowledge base**: 40 tier1 JSON files, 86 semantic concepts, ~817 aliases
- **RAG**: 1,035 chunks, hybrid retrieval (pgvector)
- **Voice calibration**: 15 scenarios, 7 audiences, 8 situations
- **Tests**: 1,075+ passing
- **Live**: https://sfpermits-ai-production.up.railway.app

## Current State

Phases 1 through 3.5 complete. Phase 4 partial: AI Vision plan analysis (analyze_plans tool, vision EPR checks, annotation legend, lasso zoom, minimap) deployed. Phase 5: Building Permit Addenda + Routing ingestion (3.9M rows), nightly change detection, search_addenda MCP tool, plan review routing in permit_lookup, and Plan Review Activity in morning brief — all deployed. RAG fully built + nightly refresh configured. Voice calibration Phase A deployed (templates, CRUD, admin UI, quick-action modifiers). Regulatory watch system deployed.

## Railway Production Infrastructure

**Live URL**: https://sfpermits-ai-production.up.railway.app
**Project**: sfpermits-ai (Railway)

### Services

| Service | Role | Status |
|---|---|---|
| **sfpermits-ai** | Flask web app (auto-deploys from `main` branch) | Active |
| **sfpermits-mcp-api** | MCP server over Streamable HTTP (`Dockerfile.mcp`) | Active |
| **pgvector-db** | PostgreSQL + pgvector — user data, RAG embeddings, permit changes | Active, primary DB |
| **pgVector-Railway** | pgvector instance (appears unused, has empty volume) | Active |
| Postgres | Old DB (removed, pending deletion, volume has 5.6GB data) | Removed |
| Postgres-CrX7 | Old DB (removed, pending deletion, volume has 1.1GB data) | Removed |

### Other Railway Projects (same account, Pro plan)

| Project | Service | What it is |
|---|---|---|
| **fortunate-cooperation** | `chief-mcp-server` | Chief brain state MCP server — manages tasks, goals, notes, specs via git-backed state |
| **optimistic-mindfulness** | `worker` | Telegram bot |

### MCP Server (sfpermits-mcp-api)

**MCP URL**: `https://sfpermits-mcp-api-production.up.railway.app/mcp`
**Health**: `https://sfpermits-mcp-api-production.up.railway.app/health`

Separate Railway service that exposes the same 22 MCP tools over Streamable HTTP for claude.ai integration. Uses `Dockerfile.mcp` and `src/mcp_http.py`. Requires the same env vars as the main Flask app (`DATABASE_URL`, `ANTHROPIC_API_KEY`, etc.).

**Connect from claude.ai**: Settings → Integrations → Add MCP server → paste the MCP URL above.

**Important**: Uses `mcp[cli]>=1.26.0` (Anthropic's official package), NOT the standalone `fastmcp` package. The standalone `fastmcp>=2.0.0` produces incompatible protocol responses that claude.ai cannot parse.

### Database (pgvector-db)

The app's `DATABASE_URL` points to `pgvector-db.railway.internal:5432` — **only reachable from within Railway's network**, not from local machines.

**Tables on pgvector-db:**
- User tables: `users`, `auth_tokens`, `watch_items`, `feedback`, `activity_log`, `points_ledger`
- Permit tracking: `permit_changes`, `cron_log`, `regulatory_watch`
- Vision: `plan_analysis_sessions`, `plan_analysis_images`, `plan_analysis_jobs`
- RAG: `knowledge_chunks` (pgvector embeddings, ~1,012 chunks)
- Bulk data: `contacts` (1.8M), `entities` (1M), `relationships` (576K), `permits` (1.1M), `inspections` (671K), `timeline_stats` (382K)

### Deploying to Production

GitHub auto-deploy is connected: pushes to `main` on `tbrennem-source/sf-permits-mcp` automatically trigger a Railway build and deploy. After merging and pushing:

```bash
# Verify deploy succeeded (give it ~2 min to build):
railway deployment list                 # Check status shows SUCCESS
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool
```

If auto-deploy ever stops working, fallback: `cd /Users/timbrenneman/AIprojects/sf-permits-mcp && railway service link sfpermits-ai && railway up`

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

## Branch & Merge Workflow

Development uses ephemeral Claude Code worktree branches (auto-created under `.claude/worktrees/`).

### Who can push to main directly
- **Tim (repo owner):** Merge to `main` locally and push directly — no PRs needed.
- **All other contributors (Steven, etc.):** Must open a PR and get Tim's review before merging. See `.github/PULL_REQUEST_TEMPLATE.md` for required QA evidence.

### PR requirements for contributors
- Branch from latest `main`, keep PRs small and focused (one feature or fix per PR)
- Fill out the PR template completely — "show your work" with screenshots, test output, manual QA steps
- Update `CHANGELOG.md` in every PR
- All `pytest` tests must pass before requesting review

### Onboarding
New developers: see `docs/ONBOARDING.md` for local setup, architecture overview, and coding conventions.

## Deployment Rules

**IMPORTANT: Do NOT run `railway up` or any Railway CLI deployment commands.**

Deployment is handled automatically by Railway via the GitHub integration whenever code is pushed or merged to the `main` branch. Running `railway up` manually will cancel the GitHub-triggered deployment and cause conflicts.

### What to do instead
- Push/commit code to `main` (or merge a PR into `main`)
- Railway will automatically detect the change and deploy
- Verify with: `curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool`

### Forbidden commands
- `railway up` — conflicts with GitHub auto-deploy
- `railway deploy` — same issue
- `railway redeploy --yes` — only restarts old image, doesn't rebuild from new code

## QA + Scenario Capture Protocol
This protocol applies at the close of EVERY feature session. Do not skip it.
### Step 1: Generate Cowork QA Script
Write a QA script to `qa-drop/[feature-name]-qa.md`. Rules:
- Name the file after the feature (e.g., `qa-drop/routing-progress-qa.md`)
- Script must be self-contained — no setup, no credentials, no prior context needed
- Structure as numbered steps Cowork can execute sequentially
- Each step has an explicit PASS/FAIL criterion
- Cover happy path, empty state, and at least one edge case
- NO route-specific assertions unless absolutely necessary
- NO color/style assertions
- Output format: compact checklist, not prose
### Step 2: Append Suggested Scenarios
Append to `scenarios-pending-review.md` in repo root (create if missing).
Use exactly this format for each scenario:
## SUGGESTED SCENARIO: [short descriptive name]
**Source:** [feature or file that prompted this]
**User:** expediter | homeowner | architect | admin
**Starting state:** [what's true before the action]
**Goal:** [what the user is trying to accomplish]
**Expected outcome:** [success criteria — no routes, no UI specifics, no colors]
**Edge cases seen in code:** [boundary conditions you noticed — optional]
**CC confidence:** high | medium | low
**Status:** PENDING REVIEW
Guidance:
- High confidence = core behavior that would break Amy's workflow if missing
- Medium confidence = important but might be implementation detail
- Low confidence = noticed in code but unsure if intentional product behavior
- Aim for 2-5 scenarios per feature session
- Never modify `scenario-design-guide.md` directly — that file is reviewed externally
### Step 3: Notify
After writing both files, output a single summary line:
`QA READY: qa-drop/[filename] | [N] scenarios appended to scenarios-pending-review.md`
