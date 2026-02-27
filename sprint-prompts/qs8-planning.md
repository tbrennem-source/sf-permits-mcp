# QS8 Planning — Beta Launch Readiness

*Generated: 2026-02-27 | Renamed from QS9 → QS8 (no QS6 existed, numbering cleaned up)*
*Source: CC planning session (Sprint 77 closeout + backlog audit + performance analysis)*

## Context

Sprint 77 (E2E Testing Blitz) completed. 64 new Playwright tests across 4 files.
QS3-QS7 (Sprints 70-77) all promoted to prod as of 2026-02-27.

**Sprint 78 (Foundation)** ships first as a 6-agent standard sprint: #357 test harness + #355 template migration + demo polish. Then QS8 launches as a quad with Sprints 79-81 (performance, intelligence, beta).
25 Chief tasks closed during backlog audit — many were already implemented but never marked done.

## Performance Analysis (CRITICAL)

**Property report page is the primary bottleneck:**

| Parcel | Permits | Response Time |
|--------|---------|---------------|
| 3507/004 | 2 | ~5.4s |
| 0585/003 | 20 | ~1.3s |
| 3512/001 | 44 | **11.6s** |

**Root causes:**
1. **N+1 DB queries:** `_get_contacts()` + `_get_inspections()` called per-permit in a loop (web/report.py lines 773-783). For 44 permits = 88 serial DB queries.
2. **SODA API latency:** 3 parallel SODA calls (complaints, violations, property tax) each take 1-3s. Already parallelized via asyncio.gather but still network-bound.
3. **No caching:** Every page load recomputes everything from scratch.

**Existing spec:** Chief has `specs/instant-site-architecture-pre-compute-cache-strategy.md` with a 3-phase plan (page_cache table, cron pre-compute, edge caching). Task #349.

## Chief Task State (post-audit)

### Open P0 Tasks
- **#355** BETA-CRITICAL: Core template migration (6 templates, 193 design-token violations)
- **#343** dforge sub-agent parallelism (lesson exists, templates not updated)
- **#299** Nate prompt kit scraper (Substack auth required — external dependency)

### Open P1 Tasks (buildable in QS9)
- **#349** Instant Site Architecture — page_cache + cron pre-compute
- **#347** Review 87 pending scenarios
- **#346** Visual QA on staging post-deploy
- **#330** Beta onboarding flow (partial — welcome page exists, no wizard/demo seeding)
- **#319** Page migration (15/63 templates migrated, ~30 full pages remaining)
- **#218** Signals/velocity cron config
- **#217** Signals migration script
- **#164** Brief pipeline details (partial)
- **#287** SODA circuit breaker (open)
- **#271** Search NLP improvement
- **#174** Stuck Permit Intervention Playbook
- **#166** What-If Permit Simulator
- **#169** Cost of Delay Calculator
- **#129** "What's Next" station predictor
- **#130** Trade permits ingest (850K records)
- **#120** Pipeline health materialized views
- **#135** Premium beta tier
- **#139** Feature flag expansion

## File Ownership Map — 16 Agents Across 4 Terminals

All 4 terminals launch simultaneously. Every production file is owned by exactly ONE agent across ALL 16.

### Terminal 1: Design Token Migration (Sprint 78)
| Agent | Templates Owned | Also Owns |
|-------|----------------|-----------|
| 78-A | landing.html, search_results_public.html | — |
| 78-B | results.html, report.html | — |
| 78-C | brief.html, velocity_dashboard.html | — |
| 78-D | portfolio.html, fragments/nav.html, demo.html | web/static/design-system.css |

**Reference docs (read-only):** docs/DESIGN_TOKENS.md, docs/DESIGN_CANON.md, design-spec.md
**Chief tasks:** #355, #319 (partial)

### Terminal 2: Performance + Ops (Sprint 79)
| Agent | Files Owned |
|-------|------------|
| 79-A | web/report.py (N+1 fix: batch contacts/inspections) |
| 79-B | web/helpers.py (get_cached_or_compute), src/db.py (page_cache DDL), scripts/release.py (page_cache migration) |
| 79-C | web/brief.py (cache-read pattern + pipeline details), web/routes_cron.py (compute-caches + signals/velocity endpoints) |
| 79-D | src/soda_client.py (circuit breaker), web/routes_misc.py (Cache-Control headers for static pages) |

**Reference docs (read-only):** specs/instant-site-architecture-pre-compute-cache-strategy.md (in Chief)
**Chief tasks:** #349 Phase A+B, #164, #218, #217, #287

### Terminal 3: Intelligence Tools (Sprint 80)
| Agent | Files Created (ALL NEW) |
|-------|------------------------|
| 80-A | src/tools/station_predictor.py, tests/test_station_predictor.py |
| 80-B | src/tools/stuck_permit.py, tests/test_stuck_permit.py |
| 80-C | src/tools/what_if_simulator.py, tests/test_what_if_simulator.py |
| 80-D | src/tools/cost_of_delay.py, tests/test_cost_of_delay.py |

**ZERO existing file modifications.** All agents create new files only.
**Chief tasks:** #129, #174, #166, #169

### Terminal 4: Beta + Data + Polish (Sprint 81)
| Agent | Files Owned |
|-------|------------|
| 81-A | web/routes_auth.py, web/feature_gate.py, web/templates/welcome.html, new web/templates/onboarding_*.html |
| 81-B | web/routes_search.py, web/routes_public.py |
| 81-C | src/ingest.py, datasets/ (trade permits) |
| 81-D | tests/e2e/ (new test files only — test_onboarding.py, test_intelligence_tools.py) |

**Chief tasks:** #330, #135, #139, #271, #130

## Cross-Terminal Conflict Check

| File | Owner | Others touch? |
|------|-------|--------------|
| web/report.py | T2-79A | No |
| web/brief.py | T2-79C | No |
| web/routes_cron.py | T2-79C | No |
| web/helpers.py | T2-79B | No |
| web/routes_auth.py | T4-81A | No |
| web/routes_search.py | T4-81B | No |
| web/routes_public.py | T4-81B | No |
| src/db.py | T2-79B | No |
| src/soda_client.py | T2-79D | No |
| src/ingest.py | T4-81C | No |
| web/static/design-system.css | T1-78D | No |
| scripts/release.py | T2-79B | No |
| web/templates/landing.html | T1-78A | No |
| web/templates/report.html | T1-78B | No |
| web/templates/brief.html | T1-78C | No |
| web/templates/portfolio.html | T1-78D | No |

**CLEAN.** No cross-terminal file conflicts.

## Merge Strategy

After all 16 agents complete (across 4 terminals):
1. Terminal 1 merges its 4 branches to main, pushes
2. Terminal 2 pulls, merges its 4 branches, pushes
3. Terminal 3 pulls, merges its 4 branches, pushes (zero conflicts — all NEW files)
4. Terminal 4 pulls, merges its 4 branches, pushes

Alternatively: one orchestrator session merges all 16 branches sequentially.

## Expected Outcomes

| Terminal | Templates | Tools | Tests | Chief Tasks |
|----------|-----------|-------|-------|-------------|
| T1 (Design) | 9 migrated | 0 | ~40 | #355, #319 partial |
| T2 (Perf) | 0 | page_cache system | ~50 | #349 A+B, #164, #218, #217, #287 |
| T3 (Intel) | 0 | 4 new MCP tools | ~60 | #129, #174, #166, #169 |
| T4 (Beta) | 0 | onboarding, search NLP | ~50 | #330, #135, #139, #271, #130 |
| **Total** | **9** | **5 systems** | **~200** | **~16 tasks** |

## Post-QS9

- Scenario drain (#347 — 87 pending)
- Visual QA (#346)
- Remaining page migration (~20 templates)
- #349 Phase C (edge caching, service worker)
- Product features: timeline visualizer, congestion forecasting
- Infrastructure: blue-green deploys (#310), PgBouncer (#311)
