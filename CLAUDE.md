# SF Permits MCP Server

## Quick Orientation

This is a Python/FastMCP MCP server providing San Francisco building permit data, entity network analysis, AI-powered permit guidance, and AI vision plan analysis via 30 tools + a Flask web UI.

**Start here to understand the project:**
1. `README.md` — tools, architecture, setup, project phases
2. `docs/ARCHITECTURE.md` — data flow, DuckDB schema, knowledge base tiers, decision tools, web UI, database architecture
3. `docs/DECISIONS.md` — why we built from scratch, DuckDB over SQLite, entity resolution strategy, SQL-first graph model
4. `CHANGELOG.md` — what was built in each phase (reverse chronological)

**Knowledge base documentation (for understanding the curated permitting data):**
5. `data/knowledge/SOURCES.md` — complete inventory of all 47 tier1 JSON files, tier2 raw text, tier3 admin bulletins, tier4 code corpus
6. `data/knowledge/GAPS.md` — known gaps, resolved gaps, Amy interview questions
7. `data/knowledge/INGESTION_LOG.md` — chronological log of all 8 ingestion sessions

**External state:**
- Chief brain state: `projects/sf-permits-mcp/STATUS.md` (via chief MCP server)

## Project Structure

```
src/                    # MCP server code (62 files, ~24K lines)
  server.py             # FastMCP entry point, registers 30 tools
  soda_client.py        # Async SODA API client (httpx)
  formatters.py         # Response formatting for Claude
  db.py                 # DuckDB + PostgreSQL dual-mode connections, pool mgmt
  knowledge.py          # KnowledgeBase singleton, semantic index
  ingest.py             # SODA -> DuckDB pipeline
  entities.py           # 5-step entity resolution cascade
  graph.py              # Co-occurrence graph (SQL self-join)
  validate.py           # Anomaly detection queries
  report_links.py       # External links for property reports
  severity.py           # Permit severity scoring v2
  station_velocity_v2.py # Station-sum timeline model
  signals/              # Health signal aggregation
  tools/                # 30 tool implementations (33 files)
  vision/               # AI vision modules (Claude Vision API)
    client.py           # Anthropic Vision API wrapper
    pdf_to_images.py    # PDF-to-base64 image conversion
    prompts.py          # EPR check prompts for architectural drawings
    epr_checks.py       # Vision-based EPR compliance checker
web/                    # Flask + HTMX web UI (44 files, ~25K lines)
  app.py                # Flask app factory, middleware, startup (1,061 lines)
  routes_public.py      # Public search, landing, demo (1,783 lines)
  routes_search.py      # Authenticated search + tools (1,452 lines)
  routes_cron.py        # Cron endpoints, nightly jobs (1,414 lines)
  routes_admin.py       # Admin dashboard, feedback, ops (996 lines)
  routes_auth.py        # Magic-link auth, account mgmt (744 lines)
  routes_property.py    # Property reports, plan analysis (570 lines)
  routes_api.py         # JSON API endpoints (557 lines)
  routes_misc.py        # Health, static pages, misc (511 lines)
  auth.py               # Auth helpers, user management
  brief.py              # Morning brief data assembly
  report.py             # Property report generation
  helpers.py            # run_async, md_to_html, shared utils
  activity.py           # Feedback, bounty points, admin users
  email_brief.py        # Morning brief email delivery
  email_triage.py       # Nightly triage report email delivery
  regulatory_watch.py   # Regulatory watch CRUD + query helpers
  cost_tracking.py      # API cost tracking + rate limiting
  pipeline_health.py    # Permit pipeline monitoring
  intelligence.py       # Activity intelligence
  templates/            # 77 Jinja2 templates
  static/               # CSS, JS, PWA manifest, icons
data/knowledge/         # 4-tier knowledge base (gitignored tier4)
  tier1/                # 47 structured JSON files — loaded at startup
  tier2/                # Raw text info sheets
  tier3/                # Administrative bulletins
  tier4/                # Full code corpus (Planning Code 12.6MB + BICC 3.6MB)
scripts/                # CLI tools (29 files)
tests/                  # 3,455 tests (127 files, ~46K lines)
datasets/               # SODA dataset catalog (22 datasets, 13.3M records)
docs/                   # Architecture, decisions, contact data analysis
```

> **Blueprint refactor complete (Sprint 69).** Routes extracted from monolithic `app.py` (~8K lines) into 8 Blueprint files. `app.py` is now 1,061 lines — just app factory, middleware, and startup.

## Key Numbers

- **30 tools**: 8 SODA API (Phase 1), 3 Entity/Network (Phase 2), 5 Knowledge (Phase 2.75), 2 Facilitation (Phase 3.5), 2 Vision (Phase 4), 1 Addenda (Phase 5), 2 Severity/Health (Phase 6), 6 Project Intelligence (Phase 7), 1 Similar Projects
- **22 SODA datasets**, 13.3M records cataloged
- **DuckDB**: 1.8M contacts -> 1M entities -> 576K relationship edges
- **PostgreSQL (prod)**: 5.6M rows, 2.05 GB on Railway, 59 tables
- **Knowledge base**: 47 tier1 JSON files, 86 semantic concepts, ~817 aliases
- **RAG**: 1,035 chunks, hybrid retrieval (pgvector)
- **Voice calibration**: 15 scenarios, 7 audiences, 8 situations
- **Routes**: 153 (across 8 Blueprint files + app.py)
- **Tests**: 3,455 collected, 3,428 passing, 20 skipped
- **Scenarios**: 73 approved in scenario-design-guide.md
- **Live**: https://sfpermits-ai-production.up.railway.app

## Current State

Phases 1-7 substantially complete. Blueprint route refactor complete (Sprint 69) — routes extracted from monolithic `app.py` into 8 Blueprint files (`routes_public.py`, `routes_search.py`, `routes_cron.py`, `routes_admin.py`, `routes_auth.py`, `routes_property.py`, `routes_api.py`, `routes_misc.py`); `app.py` reduced from ~8K to 1,061 lines. Sprint 69 delivered: redesigned landing page, search intelligence with anonymous demo path, /methodology + /about-data + /demo content pages, portfolio/PWA support. Sprint 69 Hotfix: address search resilience — graceful degradation on query timeouts. Sprint 68-A: Scenario governance — 102 scenarios reviewed, 73 in design guide.

## Railway Production Infrastructure

**Live URL**: https://sfpermits-ai-production.up.railway.app
**Project**: sfpermits-ai (Railway)

### Services

| Service | Role | Branch | URL | Status |
|---|---|---|---|---|
| **sfpermits-ai** | Flask web app (production) | `prod` | sfpermits-ai-production.up.railway.app | Active |
| **sfpermits-ai-staging** | Flask web app (staging) | `main` | sfpermits-ai-staging-production.up.railway.app | Active |
| **sfpermits-mcp-api** | MCP server over Streamable HTTP (`Dockerfile.mcp`) | `main` | sfpermits-mcp-api-production.up.railway.app | Active |
| **sf-permits-mcp** | (verify purpose) | | | Active |
| **fantastic-mindfulness** | (verify purpose) | | | Active |
| **pgvector-db** | PostgreSQL + pgvector — user data, RAG embeddings, permit changes | — | internal only | Active, primary DB |
| **pgVector-Railway** | pgvector instance (appears unused, has empty volume) | — | — | Active |

### Other Railway Projects (same account, Pro plan)

| Project | Service | What it is |
|---|---|---|
| **fortunate-cooperation** | `chief-mcp-server` | Chief brain state MCP server — manages tasks, goals, notes, specs via git-backed state |
| **optimistic-mindfulness** | `worker` | Telegram bot |

### MCP Server (sfpermits-mcp-api)

**MCP URL**: `https://sfpermits-mcp-api-production.up.railway.app/mcp`
**Health**: `https://sfpermits-mcp-api-production.up.railway.app/health`

Separate Railway service that exposes the same 30 MCP tools over Streamable HTTP for claude.ai integration. Uses `Dockerfile.mcp` and `src/mcp_http.py`. Requires the same env vars as the main Flask app (`DATABASE_URL`, `ANTHROPIC_API_KEY`, etc.).

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

### Two-Branch Model (Sprint 54+)

| Branch | Purpose | Railway trigger |
|--------|---------|----------------|
| `main` | Staging — all builds land here first | Auto-deploys staging (if configured) |
| `prod` | Production — promoted from main after QA | Auto-deploys `sfpermits-ai` production service |

**Promotion ceremony** (after staging QA passes):
```bash
git checkout prod && git merge main && git push origin prod
```

**NEVER** push directly to `prod` — always merge from `main` after verification.

### Deploying to Production

GitHub auto-deploy is connected:
- Pushes to `main` → deploy **sfpermits-ai-staging** (staging)
- Pushes to `prod` → deploy **sfpermits-ai** (production)

```bash
# Verify staging:
curl -s https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool

# Verify production:
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

**Always activate the virtual environment first:**
```bash
source .venv/bin/activate
pip install -e ".[dev]"
python -m src.server          # MCP server
python -m web.app             # Web UI
pytest tests/ -v              # Tests
```

> **Note:** The system Python (Homebrew 3.14) does NOT have project dependencies installed.
> Always run `source .venv/bin/activate` before any `python`, `pytest`, or `pip` command.

Database regeneration (from SODA API):
```bash
python -m src.ingest && python -m src.entities && python -m src.graph && python -m src.validate all
```

## Branch & Merge Workflow

Development uses ephemeral Claude Code worktree branches (auto-created under `.claude/worktrees/`).

### IMPORTANT: Worktree branch close-out (CHECKCHAT requirement)

Worktrees live on their own branches (e.g. `claude/sharp-germain`) separate from `main`. **At CHECKCHAT close, always:**

1. Run `git status` from **inside the worktree directory** — not just from the main repo root
2. Commit any modified files on the worktree branch
3. From the main repo root, merge the worktree branch into `main`: `git merge claude/<name>`
4. Push `main`

Skipping this leaves uncommitted changes showing in the CC UI ("Commit changes" badge) even after a session that looks otherwise clean.

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
- **Cross-repo sessions:** If the feature lives in a different repo (e.g., dforge), write the QA script to `qa-drop/` in that repo instead. Same rules apply.
- Script must be self-contained — no setup, no credentials, no prior context needed
- Structure as numbered steps Cowork can execute sequentially
- Each step has an explicit PASS/FAIL criterion
- Cover happy path, empty state, and at least one edge case
- NO route-specific assertions unless absolutely necessary
- NO color/style assertions
- If the feature touches templates/CSS, include DESIGN TOKEN COMPLIANCE section (see Design System section)
- Output format: compact checklist, not prose
### Step 2: Append Suggested Scenarios
Append to `scenarios-pending-review.md` in **this repo's root** (create if missing). Always here, regardless of which repo the feature lives in.
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


---

## Design System

This project has a 3-file design system authority chain. **All agents modifying templates or CSS must follow it.**

### Authority Chain

1. `docs/DESIGN_CANON.md` — immutable identity ("why"). Do not modify.
2. `docs/DESIGN_TOKENS.md` — agent-facing bible ("what"). 26 components with copy-paste HTML/CSS.
3. `docs/DESIGN_PRINCIPALS.md` — audiences and constraints ("who/where").
4. `docs/DESIGN_COMPONENT_LOG.md` — running inventory of new components created during sprints.

### Agent Rules (mandatory for any template/CSS work)

Before modifying any file in `web/templates/` or `web/static/`:
1. **Read** `docs/DESIGN_TOKENS.md` — use ONLY components and tokens from this file
2. **No invented colors** — all hex values must come from the token palette (Section 1)
3. **No invented fonts** — `--mono` for data, `--sans` for prose (Section 2, role assignment table)
4. **No invented components** — use token components. If you need one that doesn't exist, append it to `docs/DESIGN_COMPONENT_LOG.md` with the HTML/CSS you created
5. **After building**, verify against the Agent Checklist (DESIGN_TOKENS.md §14)

### Template Migration (existing pages)

When an agent touches an existing template for feature work, it should reconcile that template with the design system as part of the task. This means: replace ad-hoc inline colors with token variables, swap non-standard components for token components, ensure font role split is correct. Do not do a separate migration pass — migrate on touch.

**Do NOT copy CSS patterns from existing templates** — always reference `docs/DESIGN_TOKENS.md`. Existing templates may predate the design system and contain non-token colors, fonts, and components that should not be propagated.

### Token Lint (`scripts/design_lint.py`)

Automated token compliance check. Runs in <5 seconds, no browser needed.

```bash
python scripts/design_lint.py --changed --quiet   # only git-changed templates
python scripts/design_lint.py --files web/templates/brief.html  # specific file
python scripts/design_lint.py                      # all templates (baseline)
```

**Agents run `--changed` mode during the BUILD step.** Results logged to `qa-results/design-lint-{agent}.md`. Non-blocking — agents keep building regardless of score.

### Prod Promotion Gate

Lint scores determine prod promotion. **Nothing blocks staging — only prod has a gate.**

| Score | Staging | Prod | Post-Prod |
|---|---|---|---|
| **5/5 — clean** | Auto | Auto-promote | Nothing |
| **4/5 — minor** | Auto | Auto-promote | Hotfix after prod push |
| **3/5 — notable** | Auto | Auto-promote | Mandatory hotfix after prod push |
| **2/5 — significant** | Auto | **HOLD** | Tim reviews, hotfix before promote |
| **1/5 — broken** | Auto | **HOLD** | Tim reviews, hotfix before promote |

**The threshold:** can a user see this and lose trust? Wrong font weight (4/5) — no. Completely off-brand page with random colors (2/5) — yes.

**Hotfix session flow (after quad sprint completes):**
1. Orchestrator consolidates lint results from all agents
2. If score ≤ 3: open a design review session
3. CC presents violations + screenshots of affected pages
4. Tim: fix / accept / defer per violation
5. Fixes committed as hotfix, promoted to prod

### QA Script — Token Compliance Checks

Every QA script that covers UI changes must include this section:

```
## DESIGN TOKEN COMPLIANCE
- [ ] Run: python scripts/design_lint.py --changed --quiet
- [ ] Score: [N]/5
- [ ] No inline colors outside DESIGN_TOKENS.md palette
- [ ] Font families: --mono for data, --sans for prose (spot check 3 elements)
- [ ] Components use token classes (glass-card, obs-table, ghost-cta, etc.)
- [ ] Status dots use --dot-* not --signal-* colors
- [ ] Interactive text uses --text-secondary or higher (not --text-tertiary)
- [ ] New components logged in DESIGN_COMPONENT_LOG.md
```

### Pre-Sprint Design Brief (for sprints with UI work)

Before any sprint that builds new pages or significant UI changes, run a design brief (10-15 min):

1. List all pages/components being built or modified
2. Check DESIGN_TOKENS.md for coverage — does every needed component exist?
3. Flag gaps: components that don't exist yet need to be specced BEFORE agents start building
4. Get Tim's sign-off on any new patterns or design decisions not covered by CANON/TOKENS
5. Add approved new patterns to DESIGN_TOKENS.md before launching agents

This prevents the cycle of: agent invents → review after → rework.

### CHECKCHAT Integration

**VERIFY step** — add: "Design token compliance: no ad-hoc colors/fonts/components introduced"

**CAPTURE step** — add: "DESIGN_COMPONENT_LOG.md updated if new components were created"

**Visual QA Checklist** — add: "Token compliance: [PASS/FAIL] — [N] ad-hoc styles found"

### Governance Cadence

- **Every sprint with UI work:** Token compliance checks in QA script + CHECKCHAT
- **Every 5 sprints:** Review DESIGN_COMPONENT_LOG.md. Promote good patterns to TOKENS, deprecate ad-hoc ones. Run token usage audit.
- **On request:** Full design review against CANON constraints

---

## 11. Chief Hub Protocol

This project reports into Chief — a git-backed brain-state system that gives the planning layer (Claude.ai) visibility into what's happening across all projects. Chief is the coordination hub; this CLAUDE.md is the project's local instructions.

### Chief Project Path

This project's artifacts live at:
```
chief-brain-state/projects/sf-permits-mcp/
├── STATUS.md              ← project state (synced at session close + nightly)
├── CLAUDE.md.current      ← latest working CLAUDE.md (nightly sync)
├── scenarios-pending-review.md  ← CC-suggested scenarios awaiting planning review
├── qa-results/            ← QA scripts and results from RELAY sessions
└── specs/                 ← specs that affect planning decisions
```

**Project slug in Chief:** `sf-permits-mcp` → maps to `projects/sf-permits-mcp/` in chief-brain-state

### What Gets Pushed to Chief

**At session close (CHECKCHAT step 4 — SHIP):**
- STATUS.md updates (via `chief_write_file`)
- New scenarios from `scenarios-pending-review.md` (via `chief_write_file`)
- QA scripts from `qa-drop/` (via `chief_write_file` to `projects/sf-permits-mcp/qa-results/`)
- Task/goal updates (via `chief_add_task`, `chief_complete_task`, `chief_add_goal`)
- Session notes (via `chief_add_note`)

**Nightly (automated):**
- `CLAUDE.md` → pushed as `CLAUDE.md.current`
- `scenarios-pending-review.md` (if changed)
- Any new files in `qa-drop/` not yet in Chief
- `git diff --stat` since last nightly sync → pushed as `nightly-diff.md`
- STATUS.md / CHANGELOG.md if changed

### What Chief Knows About This Project

The planning layer (Claude.ai with Chief MCP) can read:
- Current project state without needing repo access
- Pending scenarios that need review and approval
- QA results and coverage gaps
- What changed since last planning session (via nightly diff)
- Whether RELAY/CHECKCHAT protocols are being followed

### Required Project Artifacts

| Artifact | Purpose | Status |
|----------|---------|--------|
| `qa-drop/` | Directory for RELAY QA script output | ✅ exists |
| `qa-results/` | Directory for completed/reviewed QA scripts | ✅ exists |
| `scenarios-pending-review.md` | CC appends suggested scenarios here | ✅ exists |
| `STATUS.md` | Project state — read by Chief nightly | ✅ via Chief |

---

## 12. Session Protocols

This project participates in Tim's standard session protocols. These are defined in `~/.claude/CLAUDE.md` (the global file) and activated per-project by the markers below.

### Protocol Markers

**RELAY** — QA loop. After building, CC runs QA scripts using **Playwright headless Chromium** for any step involving page navigation or UI rendering. Do NOT substitute pytest or curl for browser verification — launch a real browser, navigate pages, take screenshots to `qa-results/screenshots/`. CLI-only steps (imports, DB queries, pytest) can use Python/bash directly. Loops until all tests PASS or are marked BLOCKED. New QA scripts go to `qa-drop/`.

**CHECKCHAT** — Session close protocol for **solo sessions** (single agent, design QA, hotfix). Six steps: VERIFY, DOCUMENT, CAPTURE, SHIP, PREP NEXT, BLOCKED ITEMS REPORT.

**CHECKQUAD** — Session close protocol for **quad sprint terminals** (T1-T4). Lighter than CHECKCHAT, artifact-first. Five steps: MERGE, ARTIFACT (session report), CAPTURE (per-terminal files), HYGIENE CHECK, SIGNAL DONE. Delegates documentation/shipping to T0. See dforge `swarm-coordination` template for full protocol.

**CHECKQUAD-T0** — Session close protocol for **quad sprint orchestrator** (T0). Heavier than CHECKCHAT, consolidates all terminals. Seven steps: COLLECT, VERIFY, VISUAL QA, CONSOLIDATE, DOCUMENT, HARVEST (dforge lessons), SHIP+PROMOTE.

**Black Box Session Protocol (2 stages):**

**Stage 1 — termCC (Terminal Claude Code):** READ → BUILD → TEST → SCENARIOS → QA (termRelay) → session close. Solo sessions use CHECKCHAT. Quad sprint terminals use CHECKQUAD. T0 orchestrator uses CHECKQUAD-T0.

**Stage 2 — DeskCC (Desktop Claude Code):** DeskRelay visual checks → CHECKCHAT (lightweight).

QA is not optional. Scenarios are not optional. Session close protocol is not optional.

> See `~/.claude/CLAUDE.md` for the full protocol definitions. This section activates them.
> See `BLACKBOX_PROTOCOL.md` for the full Black Box session structure and DeskRelay prompt generation rules.
> See `DEPLOYMENT_MANIFEST.yaml` for all URLs, topology, and deployment commands.

## Black Box Protocol: active
## Deployment Manifest: DEPLOYMENT_MANIFEST.yaml
## RELAY: active
## CHECKCHAT: active
## CHECKQUAD: active (see dforge swarm-coordination template)

---

## Swarm Orchestration Rules

This project uses multi-agent swarm builds. Two execution models depending on sprint size:

### Standard Sprint (4 agents, 1 terminal)

For focused sprints with 4 or fewer agents. One CC terminal (Opus) spawns agents via Task tool.

```
CC0 (Opus orchestrator)
├── Pre-flight: git pull, verify prod state
├── Spawn Agent A ──► Task(subagent_type="general-purpose", model="sonnet", isolation="worktree")
├── Spawn Agent B ──► Task(subagent_type="general-purpose", model="sonnet", isolation="worktree")
├── Spawn Agent C ──► Task(subagent_type="general-purpose", model="sonnet", isolation="worktree")
├── Spawn Agent D ──► Task(subagent_type="general-purpose", model="sonnet", isolation="worktree")
│   (all 4 run in parallel)
├── Collect results from all agents
├── Merge worktree branches in dependency order
├── Single test run (Fast Merge Protocol)
├── Push to main
└── Report summary table
```

**Key parameters for each Task call:**
- `subagent_type: "general-purpose"` — full tool access including Bash, Read, Write, Edit, Grep, Glob
- `model: "sonnet"` — build agents use Sonnet for execution speed
- `isolation: "worktree"` — each agent gets an isolated git worktree copy of the repo
- `prompt:` — self-contained build instructions (agent rules, read list, tasks, test/QA/scenarios/ship)

**Agent prompts must include this preamble:**
```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.
```

**Agents commit to their worktree branch. The orchestrator merges all branches to main after collecting results.** Agents must NEVER merge to main themselves.

### Quad Sprint (16 agents, 4 terminals) — THE STANDARD FOR LARGE SPRINTS

For sprints with 8+ tasks spanning multiple domains. 4 CC terminals × 4 agents each. Tim operates T0 (orchestrator terminal) which launches and coordinates T1-T4.

```
T0 (Tim — orchestrator, no agents)
├── Pre-flight: verify clean state, tests, prod health, baselines
├── Launch T1-T4 by pasting prompts into 4 CC terminals
├── Monitor: all agents FOREGROUND, watch for failures
├── After all terminals finish:
│   ├── Verify each terminal pushed to main
│   ├── File ownership audit (diff against ownership matrix)
│   ├── Full test suite (one run, not per-terminal)
│   ├── Prod gate: python scripts/prod_gate.py --quiet
│   └── Promote: git checkout prod && git merge main && git push origin prod
└── Report to Chief

T1 (CC Terminal 1 — e.g., infrastructure)     — spawns 4 agents, merges internally
T2 (CC Terminal 2 — e.g., public templates)    — spawns 4 agents, merges internally
T3 (CC Terminal 3 — e.g., auth templates)      — spawns 4 agents, merges internally
T4 (CC Terminal 4 — e.g., tests + docs)        — spawns 4 agents, merges internally
```

**Merge order:** Terminals merge to main in dependency order (infrastructure → foundation → consumers → tests). Each terminal handles its own 4-agent internal merge. T0 verifies cross-terminal file ownership after all pushes.

**Cross-terminal interface contracts:** When one terminal's output is consumed by another, document the interface in BOTH terminal prompts. Use merge order as the dependency resolver.

**Sprint prompt files:**
```
sprint-prompts/qsN-t0-orchestrator.md   ← Tim reads this
sprint-prompts/qsN-t1-[theme].md        ← Paste into CC Terminal 1
sprint-prompts/qsN-t2-[theme].md        ← Paste into CC Terminal 2
sprint-prompts/qsN-t3-[theme].md        ← Paste into CC Terminal 3
sprint-prompts/qsN-t4-[theme].md        ← Paste into CC Terminal 4
```

> Full quad sprint template with T0 orchestrator role, merge ceremony, prod gate integration, failure recovery, and report template: see dforge `swarm-coordination.md` template.

### Swarm Sprint Prompt Structure

Standard sprints use TWO prompt types, quad sprints use FIVE (T0 + T1-T4):

1. **`sprint-prompts/qsN-swarm.md`** (standard) or **`qsN-t0-orchestrator.md`** (quad) — The master orchestrator prompt.
2. **`sprint-prompts/qsN-X-*.md`** (standard) or **`qsN-tN-*.md`** (quad) — Per-terminal/agent prompts.

The swarm prompt contains the full agent instructions inline (not file references) so each Task call is self-contained.

### QA Protocol Naming

- **termRelay** — Automated QA via headless Playwright in Terminal CC. Runs persona-based browser checks, captures screenshots, reports PASS/FAIL. No human needed.
- **DeskRelay** — Visual QA escalation via Desktop CC. Only triggered when termRelay finds checks requiring human visual judgment. Typically ≤10 checks per sprint.
- **CHECKCHAT** — Session completion summary written by each build agent. Includes a "Visual QA Checklist" section listing items for human spot-check.

### Domain Parallel Patterns

Spawn parallel subagents when work spans independent file domains. File ownership tables go in both the swarm prompt and per-agent prompts.

**Critical rule:** Parallel agents ONLY work when they touch different files. The orchestrator validates file ownership after completion.

### Pre-Flight: Codebase Audit

Before writing sprint prompts, audit the actual code — not stale specs. Verify each assigned task creates something that DOES NOT ALREADY EXIST. Stale specs produce empty sprints.

### Shared File Protocol

When multiple agents must touch the same file, prefer function-level interface contracts over section-comment protocols. Specify: which agent owns which function, who adds vs modifies, who merges first.

### Sequential Dependencies

Merge order follows the dependency graph: infrastructure first, features second, UX/tests last.

### Fast Merge Protocol (QS4+)

**Merge all agents at once. Run the full test suite ONCE at the end.** Do NOT run between each merge — agents already ran the suite on their branches, and with clean file ownership the intermediate runs add ~7 min each with near-zero diagnostic value. If tests fail after all merges, bisect by reverting the last merge and re-testing (still faster than sequential). Only fall back to sequential test runs when file ownership is violated (2+ agents modify the same production file).

**Sprint sizing:** 8-10 tasks per agent, estimate 15-30 min per agent (not 3-5 tasks and 2-3 hours).

### Model Routing

- Orchestrator: Opus (strategic reasoning, conflict resolution)
- Build agents: Sonnet (execution, code generation, testing)
- Routing is handled by `model: "sonnet"` parameter in Task calls. No env var needed.

### Session Bootstrap (fallback for manual per-agent prompts)

Only needed in the per-agent `qsN-X-*.md` files (not the swarm prompt). Handles paste-into-CC-terminal use:
```
## SETUP — Session Bootstrap
1. cd /Users/timbrenneman/AIprojects/sf-permits-mcp  # escape any old worktree
2. git checkout main && git pull origin main          # get latest code
3. EnterWorktree with name `sprint-NN-agent`          # create fresh worktree
```

### Black Box Protocol (v1.3)

**Stage 1 — termCC (Terminal Claude Code):**

For swarm sprints, the orchestrator (CC0) spawns all build agents in parallel via Task tool. Each agent independently follows: READ → SAFETY TAG → BUILD → TEST → SCENARIOS → QA (termRelay) → VISUAL REVIEW → session close (CHECKQUAD for quad sprint terminals, CHECKCHAT for solo sessions).

After all agents complete, the orchestrator runs CHECKQUAD-T0: COLLECT → VERIFY → VISUAL QA → CONSOLIDATE → DOCUMENT → HARVEST → SHIP+PROMOTE.

**Visual Review (Phase 6.5):** After Playwright screenshots, run automated visual scoring. Use `scripts/visual_qa.py` (preferred) or send screenshots to Claude Vision. Score each page 1-5. ≥3.0 = PASS. ≤2.0 = escalate to DeskRelay. This is standard, not optional.

CHECKCHAT output includes visual scores and a Visual QA Checklist section for any pages scoring ≤2.0.

**Stage 2 — DeskCC (Desktop Claude Code):**
DeskRelay visual checks → CHECKCHAT

Both stages always end with CHECKCHAT. Stage 2 CHECKCHAT is lightweight (commit QA results, note follow-ups, no code changes expected).

---

## 13. Enforcement Hooks

Five hooks in `.claude/hooks/` enforce Black Box Protocol compliance. They are configured in `.claude/settings.json`.

**Do NOT disable or modify hooks without Tim's explicit approval.**

### Hook Summary

| Hook | Event | Purpose | Exit Code |
|------|-------|---------|-----------|
| `stop-checkchat.sh` | Stop | Blocks CHECKCHAT/CHECKQUAD without screenshots, QA results, and scenarios | 2 = block |
| `plan-accountability.sh` | (called by stop hook) | Audits descoped/blocked items for evidence | 1 = fail |
| `block-playwright.sh` | PreToolUse:Bash | Forces Playwright execution into QA subagents | 2 = block |
| `detect-descope.sh` | PostToolUse:Write | Warns on descoping language in QA/CHECKCHAT files | 0 (warning only) |
| `test-hygiene-hook.sh` | PostToolUse:Write | Warns on anti-patterns in test files (env leaks, dual imports) | 0 (warning only) |

### How They Work

**CHECKCHAT Pre-flight Gate (stop-checkchat.sh):** When the agent writes `## CHECKCHAT` (H2 header), the Stop hook checks for:
1. PNG screenshots in `qa-results/screenshots/` (verified with `file` magic bytes)
2. A results file matching `qa-results/*-results.md` with PASS/FAIL lines
3. Changes to `scenarios-pending-review.md` (via `git diff`)
4. Plan accountability (no undocumented descopes or unsubstantiated BLOCKED items)

Missing evidence → exit 2 (blocks the stop). Agent gets one retry (`stop_hook_active` bypass).

**Build/Verify Separation (block-playwright.sh):** Detects Playwright execution commands (`chromium.launch`, `page.goto`, `page.screenshot`, etc.) in Bash calls and blocks them in the main agent. QA subagents are allowed through via `CLAUDE_SUBAGENT=true` or nested worktree CWD detection. `pytest`, `pip install`, and other safe commands are explicitly allowed.

**Descope Warning (detect-descope.sh):** Soft warning when writing files to `qa-results/` or CHECKCHAT content containing descoping language. Warns via stderr but does not block.

### Claude Code Hooks API Reference

- **Exit 0:** Action proceeds
- **Exit 2:** Action blocked — reason written to stderr is shown to the agent
- **Any other exit code:** Action proceeds, stderr logged but not shown
- All hooks receive JSON on stdin. Key fields: `last_assistant_message` (Stop), `tool_input` (PreToolUse/PostToolUse)
