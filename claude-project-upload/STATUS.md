# SF Permits MCP — Project Status

## Current State
Phases 1–3.5 complete. Phase 4 partial: Vision + Annotations + Legend + Reviewer Notes deployed. **RAG fully built + nightly refresh configured.** Entity resolution stays local DuckDB (manual batch).
18 feedback items scoped — see `specs/feedback-backlog-scoped-specs-items-6-24.md`
**All 11 priority items complete.** Remaining: backlog items.

## Session 34 (2026-02-19) — Tier 0 Operational Intelligence

### Concept
Introduced "Tier 0: Operational Intelligence" — live data as knowledge. While existing tiers answer "what are the rules?" (static files), Tier 0 answers "what's happening right now?" using 3.9M addenda routing records.

### Phase A: Activity Surface (DEPLOYED)
- **Addenda activity in 30-day banner** — plan review completions shown in permit_lookup (grouped by approved/comments/other)
- **Routing progress in intel panel** — color-coded progress bar (green/blue/amber) + latest station + X/Y completion count

### Phase B: Pattern Detection (DEPLOYED)
- **6 addenda intelligence rules** (Rules 9-14): station stall, hold unresolved, all stations clear, fresh approval, comment response needed, revision escalation
- **RoutingProgress tracker** — `web/routing.py` with batch query support for portfolio dashboard

### Phase C: Knowledge Materialization (DEPLOYED)
- **8 operational concepts** added to semantic index (92→100 concepts)
- Concepts reference live query patterns, not static files

### Phase D: Property Report + Velocity + RAG (ON BRANCH)
- **Plan review routing in property report** — per-permit routing progress bars, stalled warnings, latest activity in expandable details
- **Station velocity baselines** — `web/station_velocity.py` with rolling 90-day percentiles (avg/median/p75/p90), nightly refresh via `/cron/nightly`
- **Operational knowledge chunk generator** — `web/ops_chunks.py` generates RAG chunks from live data (station velocity, routing patterns, result distributions, system stats), stored as `source_tier='learned'` with `trust_weight=0.7`

### Data Exploration Complete
- Station velocity baselines: INTAKE 0d, BLDG 3d, SFFD 24d, PPC 174d
- 90.6% of records have null review_results (intermediate steps)
- 95% of routing is addenda #0 (original), only 5% actual revisions
- Full report: `docs/ADDENDA_DATA_EXPLORATION.md`

## Nightly Pipeline (3 AM PT)
```
GitHub Actions (0 11 * * * UTC)
  ├── POST /cron/nightly        → permit deltas + triage + cleanup + station velocity + ops chunks
  ├── sleep 30
  ├── POST /cron/rag-ingest     → re-embed knowledge tiers + ops chunks (~$0.02)
  ├── sleep 15
  └── POST /cron/send-briefs    → morning brief email delivery
```

## RAG Status
- **Phase 1**: COMPLETE — chunker, embeddings (OpenAI text-embedding-3-small), pgvector store, hybrid retrieval (60% vector + 30% keyword + 10% tier boost), web integration in /ask + draft responses
- **Nightly refresh**: CONFIGURED — runs at 3 AM PT via GitHub Actions
- **Operational chunks**: `web/ops_chunks.py` generates live-data chunks (station velocity, routing patterns) as `source_tier='learned'`
- **Tier 4 (code corpus)**: Chunker exists but NOT ingested (12.6MB Planning Code + 3.6MB BICC — decision deferred)
- **Phase 2** (task #68): Amy tribal knowledge capture UI + trust-weighted layer
- **Phase 3** (task #69): Learning from email draft edits with trust decay

## Entity Resolution Status
- **Pipeline**: 5-step cascade in DuckDB — PTS agent ID → license → SF biz license → fuzzy name → singleton
- **Results**: 1.8M contacts → 1M entities, 576K relationship edges
- **Runs**: Manual local batch (`python -m src.entities && python -m src.graph`)
- **Production**: Data migrated to Postgres (20 tables). Resolution stays local.
- **Refresh cadence**: Monthly or as-needed. Not automated.

## Open Knowledge Gaps (4 remaining)
- GAP-3: Timeline Estimates by Project Type (critical) — needs SODA addenda analysis
- GAP-10: Permit Revision/Amendment Process (significant) — partial from G-04 + G-20
- GAP-11: School Impact Fees (minor) — G-11 info sheet not downloaded
- GAP-13: Special Inspection Requirements (minor) — AB-046 in tier4, not extracted

## Key Numbers
- **21 MCP tools**, 22 SODA datasets, 985+ tests passing
- **39 tier1 knowledge files**, ~100 semantic concepts (92 static + 8 operational), ~817 aliases
- **14 intelligence rules** (8 permit-level + 6 addenda-level)
- **12 annotation types** (including reviewer_note + ai_reviewer_response), collapsible legend
- **RAG: 3,682+ chunks** (official + learned), hybrid retrieval
- **PostgreSQL: 9 bulk tables fully populated**
  - contacts: 1,847,052 | entities: 1,014,670 | relationships: 576,323
  - permits: 1,137,816 | inspections: 671,359
  - addenda: 3,920,710 | violations: 508,906 | complaints: 325,977 | businesses: 126,585
- Live: https://sfpermits-ai-production.up.railway.app

## Deploy
- Railway auto-deploys from main branch on GitHub push (confirmed working 2026-02-17)
- `railway.toml` forces Dockerfile builds (do NOT add healthcheckPath)
- GitHub Actions nightly cron handles data sync + RAG + briefs
- Entity resolution: run locally, push via `scripts/push_migration.py`
- Bulk data repopulation: `scripts/push_to_prod.py --all` (needs CRON_SECRET)
- **DO NOT** use `railway up` or `railway redeploy --yes` — conflicts with auto-deploy
