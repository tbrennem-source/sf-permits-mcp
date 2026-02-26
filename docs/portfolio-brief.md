# Tim Brenneman — AI-Native Software Development

## What I Built

**sfpermits.ai** — San Francisco building permit intelligence platform analyzing 13.3M+ records across 22 government data sources. Not a demo. Not a prototype. A production system used by permit expediters, architects, and homeowners to navigate one of the most complex municipal permitting systems in the country.

Live at [sfpermits.ai](https://sfpermits-ai-production.up.railway.app)

## The Numbers

These are real, verified numbers from the codebase — not estimates:

- **21 sprints** of continuous production development (Phases 1-3.5, Sprints 53-64), plus 3 foundational phases
- **3,327 automated tests** passing across the full suite
- **29 MCP tools** across 7 functional domains (SODA API, Entity/Network, Knowledge, Facilitation, Vision, Addenda, Project Intelligence)
- **142 routes** across Flask Blueprint-organized modules
- **1.8M contacts** resolved into **1M entities** via a 5-step entity resolution cascade
- **576K relationship edges** in the co-occurrence graph
- **3.9M addenda routing records** with station velocity baselines and trend detection
- **59 PostgreSQL tables** on production (5.6M rows, 2.05 GB)
- **22 SODA datasets** cataloged (13.3M records total)
- **47 tier1 JSON knowledge files**, 86 semantic concepts, ~817 aliases
- **73 behavioral scenarios** in the design guide (reviewed from 102 candidates)
- AI vision plan analysis with EPR compliance checking via Claude Vision API
- Nightly pipeline: SODA API → change detection → velocity refresh → station transitions → congestion signals → RAG embeddings → morning briefs → email notifications

## Technical Architecture

**Stack:** Flask + HTMX + DuckDB + PostgreSQL (pgvector) + Claude Vision API + FastMCP

**Web application** (Railway):
- Blueprint-organized Flask app (~8,500 lines across route files + app.py)
- HTMX for progressive enhancement — no client-side framework
- PostgreSQL with pgvector for RAG embeddings (3,682 chunks, hybrid retrieval)
- Magic-link authentication, role-based access control
- Security middleware: CSP headers, UA blocking, rate limiting, path blocking

**MCP server** (Streamable HTTP):
- 29 tools exposed via FastMCP over Streamable HTTP for claude.ai integration
- Phase 1: 8 SODA API tools for live permit queries
- Phase 2: 3 entity/network tools (entity resolution, graph traversal, anomaly detection)
- Phase 2.75: 5 knowledge tools (permit prediction, timeline estimation, fee calculation, document checklists, revision risk)
- Phase 3.5: 2 facilitation tools (consultant recommendations, permit lookup)
- Phase 4: 2 vision tools (plan analysis, EPR validation via Claude Vision)
- Phase 5: 1 addenda tool (3.9M routing records search)
- Phase 6: 2 severity/health tools
- Phase 7: 6 project intelligence tools (SQL queries, source reading, schema introspection)

**Data pipeline:**
- 22 SODA API sources → DuckDB local analytics → PostgreSQL production
- 5-step entity resolution: exact match → normalized match → fuzzy match → company match → alias resolution
- Co-occurrence graph built via SQL self-join (576K edges)
- Station velocity computed from 3.9M addenda records with 90-day rolling windows
- Nightly cron: 12 sub-tasks including change detection, velocity refresh, transitions, congestion, signals, DQ checks, RAG refresh

**Knowledge base (4-tier):**
- Tier 1: 47 structured JSON files — permit forms, routing rules, fee tables, fire code, OTC criteria, semantic index
- Tier 2: Raw text info sheets (51 PDFs extracted, 20 via OCR)
- Tier 3: Administrative bulletins from amlegal.com
- Tier 4: Full code corpus — SF Planning Code (12.6MB), BICC + Fire Code (3.6MB), 2025 amendments

## How I Built It

Specification-driven AI-native development using the **dforge methodology** — a framework I created for human-AI collaborative software development:

**Black Box Protocol**: Every feature follows spec in → working software out → automated QA gate → deploy. The agent reads specifications (CANON.md, PRINCIPALS.md, SCENARIOS.md), builds the feature, writes tests, runs Playwright-based QA, and produces a CHECKCHAT session report. Enforcement hooks in the CI pipeline block incomplete deliverables.

**Multi-agent swarm builds**: Complex sprints use 4+ parallel Claude Code agents, each assigned to an isolated file domain. Agents build in worktree branches, the orchestrator validates file ownership boundaries, merges sequentially, and runs the full test suite between merges.

**Behavioral scenarios as quality gates**: 73 scenarios in the design guide define what the system MUST do — not how, but what outcomes users see. Scenarios are proposed by build agents, reviewed by the planning layer, and enforced during QA.

**Intent engineering**: Three governance documents control agent behavior:
- `CANON.md` — what the project KNOWS and how much to trust each source (7-tier hierarchy)
- `PRINCIPALS.md` — behavioral rules and explicit non-behaviors (the project's constitution)
- `SCENARIOS.md` — behavioral scenarios that define quality (73 approved)

**Two-layer architecture**: Claude.ai handles strategic planning (sprint design, scenario review, prioritization). Claude Code handles tactical execution (building, testing, QA, deployment). Chief brain-state system provides cross-project coordination.

## What This Demonstrates

- **Complex data pipeline engineering**: 22 SODA API sources, 5-step entity resolution cascade, co-occurrence graph with 576K edges, station velocity computation from 3.9M routing records
- **AI integration into production workflows**: Not a chatbot demo — Claude Vision analyzes architectural plan sets for EPR compliance, predict permits tool walks a decision tree built from curated government data, morning briefs synthesize overnight changes
- **Methodology design for human-AI collaboration**: dforge isn't a prompt template — it's a framework for treating AI agents as team members with specifications, governance, and quality gates
- **Domain expertise in municipal permitting**: 4-tier knowledge base built from 51 DBI info sheets, 47 administrative bulletins, full Planning Code and Building Code, structured fee tables, and hundreds of routing rules
- **Production operations**: Railway deployment with staging/production branches, nightly cron pipeline, backup strategy, monitoring, security middleware, rate limiting

## The Framework: dforge

**dforge** is my AI-native development framework — born from building sfpermits.ai across 21+ sprints.

It provides:
- **12 templates**: CANON.md, PRINCIPALS.md, STATUS.md, Black Box Protocol, Swarm Coordination, Sprint Close Gate, Prod Push Gate, and more
- **3 frameworks**: Five Levels of AI-Native Development, Project Intake Interview, Project Framework Meta-Spec
- **16 lessons learned**: Accumulated wisdom from production development — "Deployed != Landed", "The Agent That Builds Cannot Grade QA", "Schema Migrations in Startup = Time Bomb"
- **Maturity diagnostic**: Score any project across 8 AI-native development health dimensions
- **Portfolio dashboard**: Cross-project health monitoring

The thesis: AI development needs methodology the same way software development needed Agile. Without specifications, governance, and quality gates, AI-assisted development produces brittle, untestable code. With them, it produces software at a pace and quality level that traditional development cannot match.

## Contact

[Tim Brenneman — contact details to be added]
