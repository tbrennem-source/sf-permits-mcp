# Changelog

## Session 31 — Smart Address Card Enhancements (2026-02-18)

### Problem Solved
The address search result card showed a static "Analyze Project" button that posted a useless literal string, and a "Check Violations" button that looked identical whether there were 0 or 10 open violations — no incentive to engage.

### Solution: Rich Quick Actions + Go Button Pulse

#### Smart "Analyze Project" button (`web/app.py`, `web/templates/search_results.html`)
- New `_get_primary_permit_context()` helper queries the most recent permit at an address
- Button label shows real permit type + cost: **"🔍 Analyze: Additions + Repairs · $85K"**
- Hidden fields `estimated_cost` + `neighborhood` POST directly to `_ask_analyze_prefill()`
- `_ask_analyze_prefill()` updated to read those fields, pre-filling the cost analyzer form with real data
- Falls back to "🔍 Analyze Project" if no permit context available

#### Violations badge — 3 visual states (`web/app.py`, `web/templates/search_results.html`)
- New `_get_open_violation_counts()` helper counts open violations + complaints by block/lot
- **Red badge** when violations exist: "⚠️ Check Violations · 3 open"
- **Green** when clean: "✓ No open violations"
- **Neutral** when violations table not yet ingested (auto-activates when data lands)

#### Active businesses row (gated on data)
- New `_get_active_businesses()` helper fetches up to 5 active businesses at the address
- Green-tinted card shows business name, operating since year, and type flag (🅿️ Parking, 🏨 Short-term rental)
- Auto-activates when `businesses` table is populated

#### "Who's Here" 4th button (gated on data)
- Appears only when businesses data exists
- "🏢 Who's Here · 3 businesses" or "🏢 Who's Here · Acme Corp" for single business
- Routes to AI question about who operates at the address

#### Go button pulse (`web/templates/index.html`)
- One CSS rule: `form.loading .search-btn` gets a breathing opacity animation (0.9s) while `/ask` response is loading
- Reuses existing `@keyframes pulse` + `.loading` class already toggled by HTMX event listeners

#### More detail + sources (`web/app.py`, `web/templates/draft_response.html`)
- "Cite sources" button removed; "More detail" renamed to **"More detail + sources"**
- `more_detail` modifier instructions updated to include citation rules:
  - SF Planning Code + SFBC: formatted as AM Legal markdown hyperlinks (clickable end-to-end)
  - CBC, Title 24, ASCE 7: inline citations only (paywalled)

### Gating Strategy
All new data-dependent features (`_get_open_violation_counts`, `_get_active_businesses`) check table population with `SELECT COUNT(*) … LIMIT 1` and return `None`/`[]` silently when empty. Template guards ensure zero UI change until data lands — safe to ship before ingest completes.

### Tests
985 passing, 6 pre-existing failures (unrelated: test_auth watch edit routes, test_report URL format, test_web Plan Set Validator).

---

## Session 32 — Populate 4 New SODA Tables in Production (2026-02-18)

### Problem Solved
4 new tables (addenda, violations, complaints, businesses) existed in prod Postgres with schema but no data. Needed full SODA → DuckDB → Postgres population for the first time.

### Solution: Full SODA Ingest + Push to Prod

#### Data Ingested (SODA → local DuckDB)
- **addenda** (87xy-gk8d): 3,920,710 rows — ~82 min, 50K page / 100K batch flush
- **violations** (nbtm-fbw5): 508,906 rows — ~5 min
- **complaints** (gm2e-bten): 325,977 rows — ~4 min
- **businesses** (g8m3-pdis, active only): 126,585 rows — ~1.5 min

#### Data Pushed to Production Postgres
Used `scripts/push_to_prod.py` via `/cron/migrate-data` endpoint:
- violations: 56s (~9K rows/sec)
- complaints: 32s
- businesses: 14s
- addenda: ~7.5 min (3.9M rows)

#### push_to_prod.py Script (New)
- `scripts/push_to_prod.py` — CLI tool for pushing any of the 4 tables from local DuckDB to prod Postgres
- Usage: `python scripts/push_to_prod.py --table violations` or `--all`
- Reads DuckDB in 5K-row batches, POSTs to `/cron/migrate-data` with truncate-on-first-batch
- Requires `CRON_SECRET` env var (get full value via `railway run -- printenv CRON_SECRET`)

#### Production State After
```
addenda:       3,920,710 rows
violations:      508,906 rows
complaints:      325,977 rows
businesses:      126,585 rows
contacts:      1,847,052 rows (unchanged — extraction runs separately)
entities:      1,014,670 rows (unchanged)
relationships:   576,323 rows (unchanged)
permits:       1,137,816 rows (unchanged)
inspections:     671,359 rows (unchanged)
```

### Notes
- DuckDB is single-writer — ingest jobs must run sequentially, not in parallel
- Full ingest is a one-time cost; daily updates only fetch changed records (seconds to minutes)
- Bulk data (SODA-sourced) is fully recoverable from API; only user-generated data needs Railway backups

### Files Changed
- `scripts/push_to_prod.py` — **NEW**: DuckDB → prod Postgres push script

---

## Session 30 — Building Permit Addenda Routing + Nightly Change Detection (2026-02-18)

### Problem Solved
Amy discovered permit 202509155257 ($13M, 125 Mason St) showed "no changes" despite 25 active plan review routing steps across 10 agencies with approvals as recent as 2/18. Root cause: our nightly change detection only watched the top-level `status` field on the Building Permits dataset (`i98e-djp9`), which stayed "filed" throughout the multi-month plan review process.

### Solution: Ingest Building Permit Addenda + Routing Dataset (87xy-gk8d)

#### Database Schema
- **`addenda` table** — 18 columns storing station-by-station plan review routing data (DuckDB + PostgreSQL)
- **`addenda_changes` table** — nightly delta tracking with 4 change types: `new_routing`, `review_completed`, `review_updated`, `routing_updated`
- **6 indexes** on addenda table: application_number, station, reviewer, finish_date, composite app/addenda/step, primary_key

#### Ingestion Pipeline (`src/ingest.py`)
- `_normalize_addenda()` — field extraction with int conversion for addenda_number/step, whitespace stripping, empty→None
- `ingest_addenda()` — DELETE + re-insert pattern for 3.9M rows from SODA endpoint `87xy-gk8d`
- CLI: `python -m src.ingest --addenda`

#### Nightly Change Detection (`scripts/nightly_changes.py`)
- `fetch_recent_addenda()` — queries SODA for `finish_date > since OR arrive > since`
- `detect_addenda_changes()` — compares SODA records against local addenda table by `primary_key`, detects 4 change types
- `_upsert_addenda_row()` — keeps local addenda table current via insert/update
- Non-fatal error handling — addenda failures don't block permit/inspection processing

#### Permit Lookup Enhancement (`src/tools/permit_lookup.py`)
- **Plan Review Routing section** between Inspection History and Related Permits
- Summary stats: routing steps, station count, completed/pending counts
- Markdown table with Station, Rev, Reviewer, Result, Finish Date, Notes
- **DBI Permit Details link** — direct URL to `dbiweb02.sfgov.org` permit tracker

#### New MCP Tool: `search_addenda` (Phase 5, tool #21)
- Search local addenda table by permit_number, station, reviewer, department, review_result, date range
- Returns markdown table + review notes section
- Registered in `src/server.py`

#### Morning Brief + Email Brief
- **Plan Review Activity section** in `web/brief.py` — joins `addenda_changes` with `watch_items` (permit, address, parcel watches)
- Color-coded result badges: green (Approved), orange (Issued Comments), blue (Routed)
- Up to 10 items in email brief, 50 in dashboard brief
- Added to `has_content` check in email delivery

#### Report Links
- `ReportLinks.dbi_permit_details(permit_number)` — URL builder for DBI permit tracker detail page

### Files Changed (12 modified + 2 new)
- `src/db.py` — addenda + addenda_changes tables, 6 indexes
- `src/ingest.py` — _normalize_addenda(), ingest_addenda(), --addenda CLI flag
- `src/report_links.py` — dbi_permit_details() method
- `src/server.py` — register search_addenda tool
- `src/tools/permit_lookup.py` — _get_addenda(), _format_addenda(), DBI details link
- `scripts/nightly_changes.py` — fetch_recent_addenda(), detect_addenda_changes(), _upsert_addenda_row()
- `web/app.py` — addenda_changes table in PostgreSQL migrations
- `web/brief.py` — _get_plan_review_activity(), plan_reviews in get_morning_brief()
- `web/email_brief.py` — plan_reviews in render context + has_content check
- `web/templates/brief.html` — Plan Review Activity section
- `web/templates/brief_email.html` — Plan Review Activity section (inline styles)
- `tests/test_permit_lookup.py` — added _get_addenda mock entries
- `src/tools/search_addenda.py` — **NEW**: search_addenda MCP tool
- `tests/test_addenda.py` — **NEW**: 14 tests (normalization, formatting, search, brief integration)

### Commits
- `b6fc3aa` — feat: ingest building permit addenda routing + nightly change detection

## Session 30b — Ingest 3 New SODA Datasets + Contact Extraction (2026-02-18)

### New Dataset Ingestion
- **Notices of Violation** (nbtm-fbw5, ~509K rows): Violation tracking by property, joins to permits via block+lot and to complaints via complaint_number
- **DBI Complaints** (gm2e-bten, ~326K rows): Complaint lifecycle tracking, links to violations
- **Registered Business Locations** (g8m3-pdis, active only): Entity resolution enrichment — fetches only active businesses via SODA-level `location_end_date IS NULL` filter

### Addenda Ingestion Enhancement
- Memory-efficient batch INSERT with 50K page size + 100K row flush (for 3.9M rows)

### Contact Extraction
- Plan checkers from addenda routing -> contacts table (source='addenda', role='plan_checker')
- Business owners/DBAs from business registry -> contacts table (source='business', role='owner'/'dba')
- All new contacts participate in entity resolution cascade automatically

### Schema Changes
- 3 new DuckDB tables: `violations`, `complaints`, `businesses`
- 3 new PostgreSQL tables with matching schema + pg_trgm indexes on business names
- 12 new indexes on join columns (complaint_number, block/lot, etc.)

### Pipeline Updates
- CLI flags: `--violations`, `--complaints`, `--businesses`
- Extended `_fetch_all_pages()` with `where` and `page_size` parameters
- Pipeline ordering: new datasets ingest before contacts so extraction can read them
- Updated `ALLOWED_TABLES` for data migration endpoint

### Files Changed
- `src/db.py` — 3 new table DDL in `init_schema`, 12 new indexes in `_create_indexes`
- `src/ingest.py` — 3 DATASETS entries, 3 normalizers, 3 ingest functions, 2 contact extractors, memory-efficient addenda batching, updated `run_ingestion` + CLI
- `scripts/postgres_schema.sql` — 3 new table definitions with indexes
- `web/app.py` — updated `ALLOWED_TABLES`
- `tests/test_phase2.py` — 11 new tests (normalizers, schema, contact extraction)

## Session 29 — Voice Calibration, Plan Viewer UX, Vision Prompt Enhancement (2026-02-17)

### Voice Calibration System (Phase A)
- **Voice templates**: 15 scenario templates across 7 audience types × 8 situation types in `web/voice_templates.py`
- **Voice calibration CRUD**: `web/voice_calibration.py` — seed, save, reset, get calibration data
- **Database schema**: `voice_calibrations` table added to both Postgres and DuckDB
- **Admin page**: `/admin/voice-calibration` — cards grouped by audience, side-by-side template/rewrite textareas, save/reset per scenario, HTMX inline updates
- **Account page**: calibration progress indicator + link to calibration page
- **Quick-action buttons**: "Get a meeting", "Cite sources", "Shorter", "More detail" pills on AI responses in `draft_response.html`
- **Modifier handling**: `/ask` route accepts `modifier` param, `_synthesize_with_ai()` prepends modifier instructions

### Inline Draft Editing & Voice Settings
- **Inline contenteditable editing** on AI draft responses — Edit button makes draft editable, Save submits diff to `/feedback/draft-edit`, "Used as-is" sends positive signal to `/feedback/draft-good`
- **Voice style textarea** on account page — stored in `users.voice_style`, injected into `_synthesize_with_ai()` system prompt
- **Button styling**: consistent primary/outline styling across plan analysis and response UI

### Plan Viewer UX Improvements
- **Label collision avoidance**: `resolveCollisions()` iterative algorithm pushes overlapping annotation labels apart with leader lines to original positions
- **Lasso/rubber-band zoom**: Click-drag to select rectangular area, zoom to fit selection — toggle via ⬚ button or keyboard
- **Minimap**: Shows viewport position indicator when zoomed beyond 1.1x, updates on pan/zoom
- **Left-side legend panel**: Slide-out panel with per-annotation-type toggle checkboxes, color swatches, counts, Show All / Hide All buttons
- **Per-type visibility**: Individual annotation type toggles persisted to localStorage
- **Enhanced keyboard shortcuts**: +/- zoom, 0 reset, L legend panel, Escape cascades (lasso → legend → lightbox)
- **Pan/dblclick handlers**: Updated to respect lasso mode state

### Vision Prompt Enhancement
- **Reviewer comment pattern recognition**: Enhanced `PROMPT_ANNOTATION_EXTRACTION` with specific visual patterns — revision clouds/bubbles (green, red, blue wavy outlines), callout bubbles with leader lines, handwritten markings, delta/revision triangles, strikethrough marks, circled items
- **Priority boost**: Reviewer notes prioritized first in annotation extraction
- **Max annotations**: Bumped from 12 to 15 per page to avoid crowding out reviewer notes

### Files Changed
- `web/voice_templates.py` — NEW: 15 scenario templates, audience/situation definitions
- `web/voice_calibration.py` — NEW: CRUD + seed + stats for voice calibrations
- `web/templates/admin_voice_calibration.html` — NEW: admin calibration page
- `web/templates/draft_response.html` — inline editing, quick-action modifier buttons
- `web/templates/account.html` — voice style textarea, calibration progress link
- `web/templates/analyze_plans_results.html` — lasso zoom, minimap, legend panel, collision avoidance (+629 lines)
- `web/app.py` — voice calibration routes, modifier handling in `/ask`, DB schema
- `src/db.py` — `voice_calibrations` table in DuckDB schema
- `src/vision/prompts.py` — enhanced reviewer comment detection patterns
- `src/vision/epr_checks.py` — max annotations 12→15

### Commits
- `bae27f2` — feat: inline draft editing, voice settings, and button styling fixes
- `af55176` — feat: voice calibration system + quick-action response modifiers (Phase A)
- `5c41c54` — feat: plan viewer UX — lasso zoom, minimap, legend panel, label collision avoidance
- `44f8167` — feat: enhance vision prompt to recognize reviewer comment patterns

## Session 27 — FS-Series Fire Safety Knowledge + Cookie Hardening (2026-02-17)

### FS-Series Fire Safety Info Sheets (Task #46)
- **New tier1 file**: `fire-safety-info-sheets.json` — 7 DBI fire safety info sheets encoded from raw OCR tier2 text
  - **FS-01**: Combustible Roof Decks — 500 sqft max, WUI-listed materials, ASTM E-84 Class B
  - **FS-03**: R-3 4-Story Sprinkler Rules — addition = full building, alteration = area only
  - **FS-04**: Wood-Frame Construction Fire Safety — Pre-Fire Plan for 50+ units / 350K+ sqft
  - **FS-05**: Dwelling Unit Sprinkler Rules — R3→R2 conversion scenario matrix (Ord 43-14/49-14/30-15)
  - **FS-06**: Deck Fire Separation — 3ft R3, 5ft R2 from property line
  - **FS-07**: High-Rise Elevator Lobbies — 20-min/45-min doors, CBC exceptions don't apply
  - **FS-12**: ADU Fire Exemption — state law Gov Code 65852.2 overrides local sprinkler requirements
- **Semantic index**: 80 → 86 concepts, 817 aliases, 273 source references
  - 6 new concepts: `roof_deck_fire`, `dwelling_unit_sprinkler`, `wood_frame_construction_fire`, `deck_fire_protection`, `elevator_lobby_highrise`, `r3_sprinkler_4story`
  - 4 existing concepts updated with FS cross-references: `sprinkler_required`, `fire_department`, `high_rise`, `adu`
- **KnowledgeBase**: `fire_safety_info_sheets` attribute registered
- **15 new tests**, 174 knowledge tests passing

### Session Cookie Hardening
- `SESSION_COOKIE_SECURE = True` in production (HTTPS-only)
- `SESSION_COOKIE_HTTPONLY = True` (XSS protection)
- `SESSION_COOKIE_SAMESITE = "Lax"` (CSRF protection)
- Auto-detects prod vs dev via `RAILWAY_ENVIRONMENT` / `BASE_URL`

### Files Changed
- `data/knowledge/tier1/fire-safety-info-sheets.json` — NEW (7 FS sheets)
- `data/knowledge/tier1/semantic-index.json` — 6 new concepts, 4 updated
- `src/tools/knowledge_base.py` — fire_safety_info_sheets attribute
- `tests/test_knowledge_supplement.py` — 15 new FS tests
- `web/app.py` — cookie security settings

## Session 26 — Vision Timing, Token Usage & Cost Tracking (2026-02-17)

### Per-Call Timing & Token Tracking
- **`VisionCallRecord`** dataclass: records call_type, page_number, duration_ms, input/output tokens, success for every API call
- **`VisionUsageSummary`** aggregator: total calls, tokens, duration, with `estimated_cost_usd` property (Sonnet pricing: $3/$15 per MTok)
- `VisionResult.duration_ms` field wraps `time.perf_counter()` around each `client.messages.create()` call
- `_timed_analyze_image()` wrapper in epr_checks threads usage through all 5 vision callsites
- `run_vision_epr_checks` return changed from 3-tuple to 4-tuple: `(checks, extractions, annotations, usage)`

### Database Persistence
- New columns: `vision_usage_json TEXT`, `gallery_duration_ms INTEGER` on `plan_analysis_jobs`
- Full per-call JSON blob stored for every completed analysis (call breakdown, timing, tokens, cost)
- Gallery render timing captured separately

### User-Facing UI
- **Elapsed timer during polling**: "Elapsed: 1m 23s · Typical: 1–3 min" (server-computed from started_at)
- **Vision stats on results page**: "AI Vision: 14 calls · 42,300 tokens · ~$0.19 · 87s · Gallery: 3.2s"
- Stats only shown for Full Analysis jobs with vision data

### Tests
- 8 new tests for VisionCallRecord, VisionUsageSummary (aggregation, cost math, JSON serialization)
- Updated 3→4 tuple unpacking in all existing vision/analyze_plans tests
- 67 targeted tests pass, 956 full suite pass

### Files Changed
- `src/vision/client.py` — duration_ms, VisionCallRecord, VisionUsageSummary dataclasses
- `src/vision/epr_checks.py` — _timed_analyze_image wrapper, 4-tuple return, usage threading
- `src/tools/analyze_plans.py` — 4-tuple unpack, API Usage line in report header
- `web/plan_worker.py` — 4-tuple unpack, gallery timing, persist usage to DB
- `web/plan_jobs.py` — extended get_job() SELECT with new columns
- `web/app.py` — ALTER TABLE migrations, elapsed_s in polling, vision_stats in results
- `web/templates/analyze_plans_polling.html` — elapsed timer display
- `web/templates/analyze_plans_results.html` — vision stats line
- `tests/test_vision_client.py` — 8 new tests
- `tests/test_vision_epr_checks.py` — 4-tuple unpacking, usage assertions
- `tests/test_analyze_plans.py` — 4-tuple unpacking, mock updates

## Session 25 — Rebrand: Expediter → Land Use Consultant + LUCK (2026-02-17)

### Terminology Rename
- **"Expediter" → "Land Use Consultant"** across all user-facing UI, tools, knowledge base, and tests
- **LUCK branding**: Knowledge base referenced as "LUCK (Land Use Consultants Knowledgebase)" in user-facing contexts
- **Internal `KnowledgeBase` class** preserved — LUCK is user-facing only
- **Backward compatibility**: Old `/expediters` routes 301/308 redirect to `/consultants`; "expediter" kept as search alias in semantic index and intent router

### Core Python (6 files)
- `src/tools/recommend_consultants.py` — **NEW** (replaces `recommend_expediters.py`): `ScoredConsultant`, `recommend_consultants()`, `_query_consultants()`, `_format_recommendations()`
- `src/server.py` — updated import and tool registration
- `src/ingest.py` — role map value `"pmt consultant/expediter": "consultant"` (raw SODA key preserved)
- `src/tools/intent_router.py` — `PERSON_ROLES`, `_ROLE_TYPOS`, regex patterns updated; old terms map to `"consultant"`
- `src/tools/team_lookup.py` — parameter `consultant=`, label "Land Use Consultant"
- `src/tools/search_entity.py` — docstrings and entity_type enum updated

### Web Backend (3 files)
- `web/app.py` — routes `/consultants`, `/consultants/search`; form field `consultant_name`; legacy redirects from `/expediters`
- `web/report.py` — `_compute_consultant_signal()`, `_SIGNAL_MESSAGES` rebranded, return key `consultant_signal`
- `web/owner_mode.py` — `compute_extended_consultant_factors()`

### Templates (7 files)
- `web/templates/consultants.html` — **NEW** (replaces `expediters.html`)
- `web/templates/report.html` — section "Do You Need a Consultant?", all `.expeditor-*` CSS → `.consultant-*`
- `web/templates/report_email.html` — "Consultant Assessment" section
- `web/templates/brief.html` — "Find a Consultant" badge
- `web/templates/index.html` — "Land Use Consultant" form label
- `web/templates/invite_email.html` — cohort `"consultants"`, "land use consultants"
- `web/templates/account.html` — cohort option "Land Use Consultants (professional)", LUCK source link

### Knowledge Base (3 JSON files)
- `tier1/semantic-index.json` — canonical name "Land Use Consultant", old terms kept as aliases
- `tier1/permit-consultants-registry.json` — field names updated, raw SODA values preserved
- `tier1/remediation-roadmap.json` — all "permit expediter" → "land use consultant" (~10 edits)

### LUCK Branding (5 files)
- `web/templates/account.html` — "LUCK (Land Use Consultants Knowledgebase) sources"
- `web/templates/admin_sources.html` — title "LUCK Sources", heading "LUCK Source Inventory"
- `web/templates/admin_regulatory_watch.html` — "may affect LUCK"
- `src/tools/revision_risk.py` — "LUCK-based assessment"
- `src/tools/estimate_timeline.py` — "LUCK-based estimates"

### Tests & Scripts (8 files)
- `tests/test_report.py` — `TestConsultantSignal`, `_compute_consultant_signal`
- `tests/test_owner_mode.py` — `TestExtendedConsultantFactors`
- `tests/test_intent_router.py` — role assertions → `"consultant"`
- `tests/test_team_lookup.py` — `consultant="Consultant C"`, "Land Use Consultant"
- `tests/test_web.py` — `"consultant_name"` assertion
- `tests/test_auth.py` — cohort `"consultants"`, "Land Use Consultants (professional)"
- `tests/test_sources.py` — "LUCK Source Inventory" assertion
- `scripts/feedback_triage.py` — `"/consultants": "Find a Consultant"`
- `scripts/add_user_tables.sql` — comment updated

### Documentation (3 files)
- `CHANGELOG.md` — this entry
- `data/knowledge/SOURCES.md` — "DBI Consultant Rankings"
- `data/knowledge/INGESTION_LOG.md` — terminology updates

### Production DB Migration (run manually)
```sql
UPDATE contacts SET role = 'consultant' WHERE role = 'expediter';
UPDATE entities SET entity_type = 'consultant' WHERE entity_type = 'expediter';
```

### Stats
- **~35 files changed**, 213 insertions, 986 deletions
- **949 tests passing** (7 pre-existing failures, 18 pre-existing errors — all unrelated)

## Session 24 — Annotation Polish, Legend, Reviewer Notes & Timeout Fix (2026-02-17)

### Critical Fix: Full Analysis Timeout
- **Root cause**: Gunicorn 300s worker timeout killed vision analysis (8+ min for 12-page PDF with 13+ API calls)
- **Fix**: Route ALL Full Analysis through async background worker (was only >10MB files)
- Removed ~95 lines of dead sync Full Analysis code from `web/app.py`
- Added user-visible error message to HTMX error handler (was silent failure — user saw "nothing appeared")

### Annotation UX Polish
- Button label: "Full Analysis" → "Full Analysis (AI Markup)"
- Updated subtitle and added feature hint below buttons promoting AI-powered annotations
- "AI Annotations" badge on analysis history cards for completed Full Analyses
- Annotation count in results page header (e.g., "· 24 annotations")
- **Color collisions fixed**: 10 unique colors — teal for construction type, warm gray for stamps, yellow for structural, violet for general notes (was 3 colors shared among 10 types)
- Window resize handler: debounced 200ms annotation repositioning
- localStorage persistence: annotation toggle + filter state survives page reloads
- Accessibility: ARIA labels on toggle button, filter dropdown, all SVG annotation layers

### Annotation Legend
- **"Legend" button** in annotation toolbar — opens collapsible dropdown panel
- Shows all 11 annotation types with color swatches and human-readable labels
- Click-outside-to-close behavior
- Auto-builds from ANNOTATION_COLORS map (always in sync)

### Reviewer Notes Capture
- **New annotation type**: `reviewer_note` (pink #ec4899)
- Vision prompt now identifies/transcribes existing reviewer comments, redlines, and handwritten notes
- Added to `VALID_ANNOTATION_TYPES` in `src/vision/epr_checks.py`
- Fixed filter dropdown: added 3 missing options (title_block, general_note, reviewer_note)

### Bug Fixes (Session 23 follow-up)
- Fixed DuckDB schema missing `page_annotations` column in `src/db.py`
- Fixed Full Analysis button visual feedback (`.btn-active` CSS + JS state management)
- Fixed `login_page` → `auth_login` endpoint crash in analysis_history route

### Files Changed
- `web/app.py` — async routing, dead code removal, annotation_count, error handler
- `web/templates/index.html` — button label, subtitle, feature hint, HTMX error feedback
- `web/templates/analyze_plans_results.html` — legend UI/CSS/JS, colors, resize, localStorage, a11y, filter options
- `web/templates/analysis_history.html` — AI Annotations badge
- `src/vision/prompts.py` — reviewer_note type + focus instruction in annotation prompt
- `src/vision/epr_checks.py` — reviewer_note in VALID_ANNOTATION_TYPES
- `src/db.py` — DuckDB page_annotations migration
- `tests/test_vision_annotations.py` — updated expected types set

## Session 22.6 — RAG Knowledge Retrieval System Phase 1 (2026-02-17)

### RAG Pipeline
- **`src/rag/` module** — Complete retrieval-augmented generation pipeline for the knowledge base
- **`chunker.py`** — Three chunking strategies: tier1 JSON section-level, tier2/3 paragraph sliding window (800 char, 150 overlap), tier4 code section boundaries
- **`embeddings.py`** — OpenAI `text-embedding-3-small` client with batching (100/batch), retries (3x exponential backoff), 30K char truncation
- **`store.py`** — pgvector CRUD: `knowledge_chunks` table with `vector(1536)` embeddings, IVFFlat indexing, tier/file/trust_weight columns, similarity search
- **`retrieval.py`** — Hybrid scoring pipeline: `final_score = (vector_sim × 0.60 + keyword_score × 0.30 + tier_boost × 0.10) × trust_weight`. Deduplication via Jaccard word-set comparison. Graceful fallback to keyword-only when embeddings unavailable.

### Ingestion Script
- **`scripts/rag_ingest.py`** — CLI to chunk, embed, and store all knowledge tiers. Supports `--tier`, `--dry-run`, `--clear`, `--rebuild-index`, `--stats`. Dry run shows 1,012 chunks across 38 tier1 JSON files, 52 tier2 text files, and 6 tier3 bulletins.

### Web Integration
- **`/ask` route** — General questions now attempt RAG retrieval before falling back to keyword-only concept matching. Results show source attribution with relevance scores.

### Infrastructure
- Added `openai>=1.0.0` to `pyproject.toml` dependencies
- **32 new tests** in `tests/test_rag.py` covering chunker (10), retrieval scoring (10), embeddings (2), store (6), ingestion (2), context assembly (2)

### Files Changed (7 files)
- `src/rag/__init__.py` — Module docstring
- `src/rag/embeddings.py` — OpenAI embedding client
- `src/rag/chunker.py` — Chunking strategies
- `src/rag/store.py` — pgvector store operations
- `src/rag/retrieval.py` — Hybrid retrieval pipeline
- `scripts/rag_ingest.py` — Ingestion CLI
- `web/app.py` — RAG integration in `_ask_general_question`
- `tests/test_rag.py` — 32 tests
- `pyproject.toml` — Added openai dependency

---
## Session 23 — AI-Generated Plan Annotations (2026-02-16)

### Vision Annotation Extraction
- **New prompt**: `PROMPT_ANNOTATION_EXTRACTION` in `src/vision/prompts.py` — asks Claude Vision to identify and spatially locate items on architectural drawings
- **Extraction function**: `extract_page_annotations()` in `src/vision/epr_checks.py` — validates coordinates (0-100%), type enum (10 types), label truncation (60 chars), max 12 per page
- **3-tuple return**: `run_vision_epr_checks()` now returns `(checks, extractions, annotations)` — annotations extracted from same sampled pages as title block data (no extra render cost)

### SVG Overlay Rendering
- **Client-side SVG overlays** on all image views: thumbnails (dots only), detail card (full callouts), lightbox (full callouts), comparison (both sides)
- **Color-coded by type**: red=EPR issues, green=code refs, blue=dimensions, purple=occupancy, orange=scope, gray=stamps/title blocks, teal=construction type
- **Resolution-independent**: coordinates stored as percentages (0-100), SVG viewBox maps to naturalWidth/naturalHeight
- **Toggle & filter controls**: toolbar button to show/hide all annotations, dropdown to filter by annotation type

### Storage & Plumbing
- **DB column**: `page_annotations TEXT` on `plan_analysis_sessions` (PostgreSQL + DuckDB migrations)
- **Pipeline threading**: `analyze_plans()` → `plan_worker.py` → `create_session()` → `get_session()` → template context → JavaScript
- **Graceful degradation**: old sessions with NULL annotations display normally (empty list)

### Tests
- **20 new tests** in `tests/test_vision_annotations.py` — extraction, validation, failure modes, constants
- Updated `test_analyze_plans.py` and `test_vision_epr_checks.py` for 3-tuple return signature

### Files Changed
- `src/vision/prompts.py` — new annotation extraction prompt
- `src/vision/epr_checks.py` — `extract_page_annotations()`, 3-tuple return
- `src/tools/analyze_plans.py` — 3-tuple unpacking, annotations threading
- `web/plan_images.py` — `page_annotations` in create/get session
- `web/app.py` — DB migration, route updates, `annotations_json` to templates
- `web/plan_worker.py` — 3-tuple unpacking, annotations to `create_session()`
- `web/templates/analyze_plans_results.html` — SVG overlay system, JS rendering engine, CSS, controls
- `src/db.py` — DuckDB schema migration for `page_annotations` column
- `tests/test_vision_annotations.py` — **NEW** 20 tests
- `tests/test_analyze_plans.py` — updated for 3-tuple
- `tests/test_vision_epr_checks.py` — updated for 3-tuple

## Session 22.5 — Plan Analysis UX Overhaul (2026-02-16)

### Multi-Stage Progress Indicator (Item 3)
- **DB migration**: `progress_stage` + `progress_detail` columns on `plan_analysis_jobs`
- **Worker updates**: 4 progress checkpoints — Analyzing → Rendering (with page count) → Finalizing
- **Step indicator UI**: Horizontal 3-dot stepper with pulsing active state, replaces generic bouncing bar
- Templates: `analyze_plans_processing.html` (initial state) + `analyze_plans_polling.html` (live updates)

### App Shell for Async Results (Item 1)
- **New template**: `plan_results_page.html` — full-page wrapper with shared nav fragment
- Async results route now renders inside app shell (header, nav, logout) instead of bare fragment
- `property_address` passed to template context for watch cross-sell

### Simplified Upload Form (Item 4)
- **Quick Check is now the default** primary action (instant metadata scan)
- Full Analysis (AI vision) is opt-in secondary button
- **Progressive disclosure**: description, permit type, address, permit number hidden behind "More options ▸" toggle
- Two side-by-side buttons replace single submit + checkbox

### Account Page "Plan Analyses" Card + Nav Links (Item 2)
- **Account page card**: shows 3 most recent analyses with status badges + "View all analyses →"
- **Header nav**: "My Analyses" badge added to shared `fragments/nav.html`
- **Below-form link**: "View your analysis history →" for logged-in users

### Card-Based History Layout (Item 5)
- **Full rewrite** of `analysis_history.html`: table → responsive card grid
- Cards show filename, status badge, file size, date, property/permit details, action links
- Adopted shared `fragments/nav.html` (was inline header)
- Responsive: single column below 640px

### Post-Analysis Watch Cross-Sell (Item 6)
- **Address parser**: `_parse_address("123 Main St")` → `("123", "Main St")` for watch system
- **Logged-in with address**: "Track changes to this property?" card with HTMX watch button
- **Logged-out with address**: "Sign in to watch {address}" prompt
- No address: nothing shown

### Files Changed
- `web/app.py` — migration, address parser, route updates (Items 1,2,3,6)
- `web/plan_jobs.py` — progress columns in `get_job()` SELECT (Item 3)
- `web/plan_worker.py` — 4 progress update calls (Item 3)
- `web/templates/plan_results_page.html` — **NEW** app shell wrapper (Item 1)
- `web/templates/analyze_plans_processing.html` — step indicator initial state (Item 3)
- `web/templates/analyze_plans_polling.html` — step indicator live updates (Item 3)
- `web/templates/index.html` — form restructure + nav link (Items 2,4)
- `web/templates/account.html` — Plan Analyses card (Item 2)
- `web/templates/analysis_history.html` — card grid + nav fragment (Item 5)
- `web/templates/analyze_plans_results.html` — watch cross-sell (Item 6)
- `web/templates/fragments/nav.html` — "My Analyses" badge (Item 2)

## Session 22.4 — Recent Searches (2026-02-16)

### Feature
- **Recent searches** — Last 5 searches saved to localStorage and rendered as clickable preset chips above quick-actions on the home page. Case-insensitive dedup, truncates long queries, clear button to wipe history. Pure client-side, no backend changes.

### Files Changed (1 file, +83 lines)
- `web/templates/index.html` — Recent searches container, CSS, JS (localStorage read/write, chip rendering, HTMX hook)

---

## Session 22.3 — Fix False Positive Assessor Use Mismatch (2026-02-16)

### Bug Fix
- **Assessor vs. permit use mismatch false positive** — "Single Family Residential" (Assessor) was flagged as a mismatch against "1 family dwelling" (permit) even though they mean the same thing. Added `"single family residential"` and `"two family residential"` to the `_USE_EQUIVALENTS` table in `web/owner_mode.py`.

### Tests
- Added `test_assessor_single_family_residential_equivalent` and `test_assessor_single_family_residential_no_mismatch` to `tests/test_owner_mode.py` — 49 tests passing.

### Files Changed (2 files)
- `web/owner_mode.py` — Added equivalents to `_USE_EQUIVALENTS`
- `tests/test_owner_mode.py` — 2 new tests for the fix

---

## Session 22 — Async Plan Analysis with Per-User Storage (2026-02-17)

### Async Background Processing
- **Large PDFs (>10 MB) processed asynchronously** via `ThreadPoolExecutor(max_workers=1)` — eliminates gunicorn timeout for 22+ MB architectural plan sets
- Immediate "Processing..." response with HTMX polling (3s interval)
- **Email notification** when analysis completes (success or failure) via existing SMTP
- Stale job recovery on worker restart — marks stuck jobs as "stale" after 15 min
- Gallery images rendered at **72 DPI** (vs 150 DPI for vision) for 4x faster rendering

### Per-User Persistent Storage
- **`plan_analysis_jobs` table** — tracks every analysis with full lifecycle: pending → processing → completed/failed/stale
- Original PDF stored as BYTEA during processing, cleared after completion
- **Tiered TTL**: 30-day retention for logged-in users, 24h for anonymous
- `user_id` column added to `plan_analysis_sessions` for ownership

### Property/Permit Tagging
- **Manual entry**: Property Address + Permit Number fields on upload form
- **Auto-extraction**: `_auto_extract_tags()` scans vision results for address and permit patterns
- Tags stored with source tracking: `manual`, `auto`, or `both`

### Analysis History
- **`/account/analyses` page** — searchable table of past analyses
- Search by address, permit number, or filename
- Status badges (completed, processing, failed, stale)
- Direct "View" links to completed results

### New Files
- `web/plan_jobs.py` — Job CRUD (385 lines, 8 functions)
- `web/plan_worker.py` — Background worker (336 lines)
- 6 new templates: processing, polling, complete, failed, stale, email, history

### Routes Added
- `GET /plan-jobs/<job_id>/status` — HTMX polling endpoint
- `GET /plan-jobs/<job_id>/results` — View completed async results
- `GET /account/analyses` — Analysis history page

## Session 21.10 — Fix 5 Analyze Plans QA Bugs (2026-02-17)

### Bug Fixes
- **ZIP Download 500 fix** — PostgreSQL JSONB returns Python objects (not JSON strings); `get_session()` now handles already-parsed list/dict via `isinstance()` check instead of always calling `json.loads()`
- **All thumbnails shown** — Thumbnail gallery now loops `range(page_count)` (all 17 pages) instead of `extractions` (only 5 vision-sampled pages)
- **Print/Download Report scoped** — Added `@media print` CSS that hides toolbar, gallery, lightbox, comparison, email modal; `printReport()` JS wrapper adds `printing-report` class to `<body>` during print
- **Email route fixed** — 4 sub-fixes: accept `session_id` route param, import `send_brief_email` (not `send_email`), use correct arg names (`to_email`, `html_body`), use `logging.error` (not `logger`)

### Files Modified
- `web/plan_images.py` — JSONB isinstance check (line 109)
- `web/templates/analyze_plans_results.html` — Thumbnail loop, @media print CSS (80+ lines), `printReport()` JS function
- `web/app.py` — Email route rewritten with correct imports, params, and error handling

## Session 20 — Phase 4.5: Visual Plan Analysis UI (2026-02-16)

### Visual Plan Gallery & Viewer
- **Database-backed image storage** — 24h session expiry with nightly cleanup
- `plan_analysis_sessions` table — stores filename, page_count, page_extractions (JSONB/TEXT)
- `plan_analysis_images` table — base64 PNG storage per page, CASCADE delete on session expiry
- `web/plan_images.py` module — `create_session()`, `get_session()`, `get_page_image()`, `cleanup_expired()`
- PostgreSQL (prod) + DuckDB (dev) dual-mode support

### Enhanced analyze_plans Tool
- Added `return_structured: bool = False` parameter to `src/tools/analyze_plans.py`
- Returns tuple `(markdown_report, page_extractions)` when True
- Backward compatible — existing MCP callers get markdown string as before
- Web route now renders all pages (cap at 50) and creates session

### Web UI Components (analyze_plans_results.html)
- **Thumbnail gallery** — CSS grid with lazy loading, page numbers + sheet IDs
- **Detail cards** — Extracted metadata (sheet #, address, firm, professional stamp)
- **Lightbox viewer** — Full-screen with keyboard navigation (arrows, escape)
- **Side-by-side comparison** — Compare any two pages with dropdown selectors
- **Email modal** — Share analysis with recipient via Mailgun
- Dark theme with CSS variables, responsive grid layout

### API Routes
- `GET /plan-images/<session_id>/<page_number>` — Serve rendered PNG images (24h cache)
- `GET /plan-session/<session_id>` — Return session metadata as JSON
- `GET /plan-images/<session_id>/download-all` — ZIP download of all pages
- `POST /plan-analysis/email` — Email analysis to recipient (full or comparison context)
- Nightly cron cleanup integrated — deletes sessions older than 24h

### JavaScript Interactivity
- State management: `currentPage`, `sessionId`, `pageCount`, `extractions`
- Functions: `openPageDetail()`, `openLightbox()`, `openComparison()`, `downloadPage()`, `downloadAllPages()`, `emailAnalysis()`
- Keyboard navigation in lightbox (ArrowLeft, ArrowRight, Escape)
- Dropdown population for comparison view with sheet metadata

### Tests
- **21 new tests** — `test_plan_images.py` (8 unit), `test_plan_ui.py` (10 integration), `test_analyze_plans.py` (+3)
- Tests cover: session creation, image retrieval, cleanup, route responses, ZIP download, email delivery
- **833 tests total** (812 → 833)

### Performance & Security
- 50-page cap to avoid timeouts (configurable)
- Graceful degradation — falls back to text report if image rendering fails
- Session IDs via `secrets.token_urlsafe(16)` act as capability tokens
- Per-page images: ~50-150 KB base64 PNG (150 DPI, max 1568px)
- 24h expiry prevents database bloat

---

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
