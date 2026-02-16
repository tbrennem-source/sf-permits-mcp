# Changelog

## Session 19 — Bounty Points, Nightly Triage & Quick Fixes (2026-02-16)

### Bounty Points System
- `points_ledger` table (DuckDB + PostgreSQL) with user, points, reason, feedback_id
- `award_points()` — idempotent, auto-calculated on resolution: bugs 10pts, suggestions 5pts, screenshot +2, first reporter +5, high severity +3, admin bonus
- `get_user_points()`, `get_points_history()` — total and history with reason labels
- Wired into PATCH `/api/feedback/<id>` and admin HTMX resolve route
- Account page shows Points card with total and recent history
- Admin feedback queue: "1st reporter" checkbox + "Resolve (+pts)" button
- `GET /api/points/<user_id>` — CRON_SECRET-protected points API

### Nightly Feedback Triage (piggybacked on existing cron)
- Three-tier classification: Tier 1 (auto-resolve: dupes, test/junk, already-fixed), Tier 2 (actionable: clear repro context), Tier 3 (needs human input)
- `is_test_submission()` — pattern matching for test keywords, short admin messages, punctuation-only
- `detect_duplicates()` — exact match + Jaccard word-overlap >0.8 (same user/page within 7 days)
- `is_already_fixed()` — matches against recently resolved items by page+type+similarity
- `classify_tier()` — multi-signal scoring for actionability (repro signals, page URL, screenshot, message length)
- `auto_resolve_tier1()` — PATCH with `[Auto-triage]` prefix
- `run_triage()` — full pipeline, appended to `/cron/nightly` (non-fatal)

### Morning Triage Report (piggybacked on existing cron)
- `web/email_triage.py` — renders + sends triage report to all active admins
- `web/templates/triage_report_email.html` — table-based email: summary metrics, Tier 1 (green), Tier 2 (blue), Tier 3 (amber), CTA button
- `get_admin_users()` — queries `users WHERE is_admin = TRUE AND is_active = TRUE`
- Appended to `/cron/send-briefs` (non-fatal)

### Quick Fixes
- **#18**: "Expeditor Assessment" → "Expeditor Needs Assessment" with explanatory paragraph
- **#22**: View Parcel link fixed — `sfassessor.org` (301 redirect) → `sfplanninggis.org/pim/`
- **#19**: Expediter form pre-fills block/lot/address/neighborhood from query params; report page passes all fields in URL

### Tests
- 67 new tests: 18 bounty points, 43 triage classification + email, 6 others
- **748 tests passing** (681 → 748)

---

## Session 18 — Bug Fixes: No-Results UX & Morning Brief (2026-02-16)

### Bug #4: Address Search Dead End
- Address search returning "No permits found" now shows "What you can do next" CTA box
- Links to Ask AI (pre-filled with address) and search refinement
- Integrates with existing `report_url` — shows "Run Property Report" link when block/lot is resolvable
- Helpful context: "No permit history doesn't mean no permits are required"

### Bug #5: Morning Brief Empty State
- Fixed missing `query_one` import in `web/brief.py` (would crash data freshness section)
- Added "All quiet on your watched items" banner when user has watches but no permit activity
- Banner suggests expanding lookback period (Today → 7 days → 30 days)

### Branch Audit
- 1 unmerged branch (`claude/focused-chandrasekhar`) — only stale CHANGELOG, code already in main
- 12 merged branches identified for cleanup

### Tests
- **681 tests passing** (620 → 681, includes main-branch tests from prior session)

---

## Session 17 — Feedback Triage API (2026-02-16)

### Feedback Triage System
- New `/api/feedback` JSON endpoint — CRON_SECRET-protected, supports multi-status filtering
- New `/api/feedback/<id>/screenshot` endpoint — serves screenshot images via API auth
- New `scripts/feedback_triage.py` CLI — fetches unresolved feedback, classifies severity, extracts page areas, formats triage report
- Pre-processing: HIGH/NORMAL/LOW severity via keyword matching, page area extraction from URLs, relative age formatting
- Usage: `railway run -- python -m scripts.feedback_triage` to pull and triage production feedback
- New `get_feedback_items_json()` in `web/activity.py` — JSON-serializable feedback with ISO timestamps

### Tests
- 11 new tests: API auth (403), JSON structure, status filtering, multi-status, screenshot API, triage severity classification, page area extraction, age formatting, report formatting
- **620 tests passing** (609 → 620)

---

## Session 16 — Feedback Screenshot Attachment (2026-02-15)

### Feedback Widget Enhancement
- Screenshot attachment for feedback submissions — users can capture page state for LLM debugging
- Dual capture: "Capture Page" (html2canvas) + "Upload Image" (file picker)
- Screenshots stored as base64 JPEG in PostgreSQL `screenshot_data TEXT` column (~300KB typical)
- html2canvas lazy-loaded on first click (saves ~40KB per page load)
- Capture overlay ("Capturing page screenshot...") replaces jarring modal hide/show
- Form auto-resets after successful submit (textarea, screenshot, radio buttons), modal auto-closes after 3s
- Admin feedback queue shows "View Screenshot" toggle with lazy-loaded image
- Admin-only `/admin/feedback/<id>/screenshot` route decodes base64 and serves image
- Server-side validation: must start with `data:image/`, max 2MB, invalid data silently dropped
- DuckDB + PostgreSQL dual-mode support with idempotent migrations

### Tests
- 12 new screenshot tests in `tests/test_activity.py`:
  - Submit with/without screenshot, store + retrieve, has_screenshot flag
  - Invalid data dropped, oversized data dropped
  - Admin route auth (403), missing screenshot (404), image serve (200 + mime type)
  - Admin page shows "View Screenshot" button, widget has capture/upload buttons
- **609 tests passing** (567 → 609), 0 skipped

---

## Session 9 — Web UI + Predictions Refresh (2026-02-14)

### Amy Web UI (sfpermits.ai)
- Built Flask + HTMX frontend in `web/` — dark-themed, tabbed results, preset scenarios
- Form accepts: project description, address, neighborhood, cost, square footage
- Runs all 5 decision tools and renders markdown output as styled HTML tabs
- 5 preset "quick start" scenarios matching Amy's stress tests
- Dockerfile.web for containerized deployment (Railway/Fly.io)
- Railway deployment files: Procfile, railway.toml, requirements.txt

### System Predictions Refresh
- Regenerated `data/knowledge/system_predictions.md` with source citations (37K → 69K chars)
- All 5 tools × 5 scenarios now include `## Sources` sections with clickable sf.gov links
- Generation script at `scripts/generate_predictions.py` for reproducible runs

### Tests
- 9 new web UI tests in `tests/test_web.py`:
  - Homepage rendering, neighborhood dropdown, empty description validation
  - Full analysis for kitchen/restaurant/ADU scenarios
  - No-cost fee info message, markdown-to-HTML conversion
- **254 tests passing** (245 → 254), 0 skipped

### Dependencies
- Added `flask`, `markdown`, `gunicorn` to `[project.optional-dependencies] web`

---

## Phase 2.75 — Permit Decision Tools (2026-02-14)

### Knowledge Supplement (Phase 2.6+)
- Created `tier1/title24-energy-compliance.json` — CA Title-24 Part 6 energy forms (CF1R/CF2R/CF3R residential, NRCC/NRCI/NRCA nonresidential), triggers by project type, 6 common corrections (T24-C01 through T24-C06), SF all-electric requirement (AB-112), climate zone 3
- Created `tier1/dph-food-facility-requirements.json` — SF DPH food facility plan review: 7 general requirements (DPH-001 through DPH-007), 8 specific system requirements (DPH-010 through DPH-017), facility categories, parallel permits needed
- Created `tier1/ada-accessibility-requirements.json` — ADA/CBC Chapter 11B path-of-travel: valuation threshold ($195,358), cost tiers (20% rule vs full compliance), 8 common corrections (ADA-C01 through ADA-C08), CASp information, special cases (historic, seismic, change of use)
- Updated `KnowledgeBase` to load all 15 tier1 JSON files (was 12)

### Tool Enhancements (knowledge integration)
- `predict_permits` — now flags SF all-electric requirement (AB-112) for new construction, ADA threshold analysis with 20% vs full compliance, DPH menu/equipment schedule requirements for restaurants, Title-24 form requirements by project scope
- `estimate_fees` — added ADA/Accessibility Cost Impact section: computes adjusted construction cost vs $195,358 threshold, reports whether full compliance or 20% limit applies
- `required_documents` — expanded DPH agency documents (7 items with DPH-001 through DPH-007 references), knowledge-driven Title-24 form requirements (CF1R/NRCC), existing conditions documentation for alterations (T24-C02), DA-02 checklist auto-flagged for all commercial projects
- `revision_risk` — added Top Correction Categories section with citywide frequencies (Title-24 ~45%, ADA ~38%, DPH for restaurants), CASp mitigation for commercial projects, DA-02 submission reminders

### Knowledge Validation (Phase 2.6)
- Validated `tier1/fee-tables.json` (54K, 19 tables, 9-step algorithm, eff. 9/1/2025)
- Validated `tier1/fire-code-key-sections.json` (37K, 13 SFFD triggers)
- Validated `tier1/planning-code-key-sections.json` (36K, 6 major sections)
- Created `tier1/epr-requirements.json` — 22 official DBI EPR checks from Exhibit F + Bluebeam Guide, severity-classified (reject/warning/recommendation)
- Created `tier1/decision-tree-gaps.json` — machine-readable gap analysis for all 7 steps + 6 special project types, used by tools for confidence reporting
- Created `DECISION_TREE_VALIDATION.md` — human-readable validation summary
- Confirmed: `estimated_cost` is DOUBLE in DuckDB (no CAST needed), `plansets` field does not exist

### New MCP Tools (5)
- `predict_permits` — Takes project description → walks 7-step decision tree → returns permits, forms, OTC/in-house review path, agency routing, special requirements, confidence levels. Uses `semantic-index.json` (492 keyword aliases from 61 concepts) for project type extraction.
- `estimate_timeline` — Queries DuckDB for percentile-based timeline estimates (p25/p50/p75/p90) with progressive query widening, trend analysis (recent 6mo vs prior 12mo), and delay factors. Creates `timeline_stats` materialized view on first call.
- `estimate_fees` — Applies Table 1A-A fee schedule (10 valuation tiers) to compute plan review + issuance fees, plus CBSC/SMIP surcharges. Statistical comparison against DuckDB actual permits. ADA threshold analysis for commercial projects.
- `required_documents` — Generates document checklist from permit form, review path, agency routing, and project triggers. Includes full EPR requirements (22 checks), Title-24 forms, DPH requirements, DA-02 for commercial, and pro tips.
- `revision_risk` — Estimates revision probability using `revised_cost > estimated_cost` as proxy signal (125K revision events in 1.1M permits). Computes timeline penalty, common triggers by project type, correction frequencies from compliance knowledge, mitigation strategies.

### Module Architecture
- Created `src/tools/knowledge_base.py` — shared `KnowledgeBase` class loads all 15 tier1 JSON files once via `@lru_cache`. Builds keyword index from semantic-index.json for project type matching.
- 5 new tool modules in `src/tools/`: `predict_permits.py`, `estimate_timeline.py`, `estimate_fees.py`, `required_documents.py`, `revision_risk.py`
- Server.py updated: imports + registers all 13 tools (5 SODA + 3 entity/network + 5 decision)

### Tests
- 70 new tests across 7 files:
  - `test_predict_permits.py` (14) — keyword extraction, KnowledgeBase loading, semantic matching, full predictions for restaurant/kitchen/ADU scenarios
  - `test_estimate_fees.py` (8) — fee calculation per tier, surcharges, tool output with project types
  - `test_required_docs.py` (7) — base docs, agency-specific, trigger-specific, EPR, demolition, historic, commercial TI ADA
  - `test_timeline.py` (5) — DuckDB queries with neighborhood, cost, review path, triggers
  - `test_revision_risk.py` (5) — basic, neighborhood, restaurant triggers, mitigation, timeline impact
  - `test_integration_scenarios.py` (9) — 5 Amy stress test scenarios through predict + fees + docs chain
  - `test_knowledge_supplement.py` (22) — Title-24/DPH/ADA loading, predict_permits all-electric/ADA threshold, required_docs DPH items/DA-02/NRCC, estimate_fees ADA analysis, revision_risk correction frequencies
- **All 96 tests passing** (86 pass + 10 DuckDB-dependent skipped)
- Improved DuckDB skip logic: now checks for actual permits table, not just file existence

### Integration Test Scenarios
- `data/knowledge/system_predictions.md` (37K) — full output of all 5 tools across 5 scenarios:
  - A: Residential kitchen remodel (Noe Valley, $85K)
  - B: ADU over garage (Sunset, $180K)
  - C: Commercial TI (Financial District, $350K)
  - D: Restaurant conversion (Mission, $250K)
  - E: Historic building renovation (Pacific Heights, $2.5M)

---

## Phase 2 — Network Model Validation (2026-02-13)

### DuckDB Ingestion Pipeline (`src/ingest.py`)
- Paginated fetch (10K/page) of 3 contact datasets via existing `SODAClient`
  - Building Permits Contacts (`3pee-9qhc`, ~1M records)
  - Electrical Permits Contacts (`fdm7-jqqf`, ~340K records)
  - Plumbing Permits Contacts (`k6kv-9kix`, ~503K records)
- Building Permits (`i98e-djp9`, ~1.28M records) ingested for enrichment
- Building Inspections (`vckc-dh2h`, ~671K records) ingested for inspector data
- Unified `contacts` table normalizes names, roles, and keys across all three schemas
- `estimated_cost` cast from TEXT to DOUBLE during ingestion
- Ingest log tracks last-fetched timestamp per dataset

### DuckDB Schema (`src/db.py`)
- 6 tables: `contacts`, `entities`, `relationships`, `permits`, `inspections`, `ingest_log`
- 16 indexes on join columns: `permit_number`, `pts_agent_id`, `license_number`, `sf_business_license`, `entity_id`, `inspector`, `canonical_name`, etc.

### Entity Resolution (`src/entities.py`)
- 5-step cascading pipeline:
  1. `pts_agent_id` grouping (building contacts only, high confidence)
  2. `license_number` grouping across all sources (medium confidence, merges into existing entities)
  3. `sf_business_license` grouping across all sources (medium confidence, merges into existing entities)
  4. Fuzzy name matching with trigram-prefix blocking and token-set Jaccard similarity >= 0.75 (low confidence)
  5. Singleton entity creation for remaining unresolved contacts
- Canonical name/firm selection picks longest non-null value
- Entity type determined by most common role across grouped contacts

### Co-occurrence Graph (`src/graph.py`)
- Self-join on `contacts` table (a.entity_id < b.entity_id on shared permit_number)
- LEFT JOIN to `permits` for cost, type, date, neighborhood enrichment
- Edge attributes: shared_permits count, permit_numbers (capped at 20), permit_types, date range, total_estimated_cost, neighborhoods
- All computation in a single INSERT...SELECT pushed to DuckDB
- 1-hop neighbor and N-hop network traversal queries

### Validation & Anomaly Detection (`src/validate.py`)
- `search_entity(name)` — case-insensitive LIKE search on canonical_name/firm, returns top 5 co-occurring entities
- `entity_network(entity_id, hops)` — N-hop ego network with nodes and edges
- `inspector_contractor_links(inspector_name)` — traces inspector to permit to contact entity relationships
- `find_clusters(min_size, min_edge_weight)` — connected-component detection via BFS on filtered subgraph
- `anomaly_scan(min_permits)` — flags high permit volume (>3x type median), inspector concentration (>=50%), geographic concentration (>=80%), fast approvals (<7 days, >$100K)
- `run_ground_truth()` — searches for Rodrigo Santos, Florence Kong (inspectors), Bernard Curran (contact)

### New MCP Tools
- `search_entity` — search entities by name across all resolved contact data
- `entity_network` — get N-hop relationship network around an entity
- `network_anomalies` — scan for anomalous patterns in the permit network

### Tests
- 16 new tests in `tests/test_phase2.py` (in-memory DuckDB, no network access):
  - Schema creation verification
  - Entity resolution helpers: `_pick_canonical_name`, `_pick_canonical_firm`, `_most_common_role`, `_token_set_similarity`
  - Full entity resolution pipeline with cross-source merging assertions
  - Graph construction and edge weight verification
  - 1-hop neighbor and N-hop network queries
  - Entity search (found and not-found cases)
  - Inspector-contractor link tracing
  - Anomaly scan structure
  - Cluster detection

### Configuration
- Added `duckdb` to dependencies in `pyproject.toml`
- Added `data/` to `.gitignore` (DuckDB file not committed)

---

## Phase 1 — MCP Server + Dataset Catalog (2026-02-12)

### MCP Tools (5)
- `search_permits` — search building permits by neighborhood, type, status, cost, date, address, description
- `get_permit_details` — full details for a specific permit by permit number
- `permit_stats` — aggregate statistics grouped by neighborhood, type, status, month, or year
- `search_businesses` — search registered business locations in SF
- `property_lookup` — property assessments by address or block/lot

### Infrastructure
- FastMCP server entry point (`src/server.py`)
- Custom async SODA client with httpx (`src/soda_client.py`, ~108 lines)
- Response formatters for Claude consumption (`src/formatters.py`)
- 22 datasets cataloged in `datasets/catalog.json` and `datasets/CATALOG.md`
- SODA API performance benchmarks across 7 datasets (`benchmarks/RESULTS.md`)
- 10 integration tests in `tests/test_tools.py`

### Documentation
- Architecture decisions log (`docs/DECISIONS.md`): build-vs-fork, SODA client choice, NIXPACKS deployment
- Contact data deep-dive (`docs/contact-data-report.md`)
- Mehri reference model (`docs/mehri-reference.md`)

### Key Findings
- Baseline SODA API latency: ~450-650ms per query
- Aggregation cold-cache penalty: 10-14s on large datasets (warm cache: ~600ms)
- 13.3M total records across 22 datasets
