# QS5-D: Task Hygiene Diagnostic Sweep

## Investigation Summary

Read-only investigation of 12 stale Chief tasks. No code changes.

### Tasks Closed (8)

| Task | Description | Evidence |
|------|-------------|----------|
| #127 | Addenda nightly refresh | `nightly_changes.py` fetches addenda via SODA, upserts via `_upsert_addenda_row()`. In GH Actions `nightly-cron.yml` workflow. |
| #112 | Inspections upsert PK collision | Uses DELETE+INSERT pattern (`DELETE WHERE source='building'` then bulk INSERT). No PK collision possible. |
| #159 | Pre-build safety tagging | Solved by process — SAFETY TAG in Black Box Protocol v1.3 + embedded in every sprint prompt Agent Rules. |
| #179 | CRON_SECRET 403 | Auth code clean in `routes_cron.py:23-33`. Cron worker service separation (Sprint 65) resolved env var issues. |
| #220 | Playwright test suite scope | 4 files in `tests/e2e/`: 26 scenario tests + mobile + link spider + video recording. Core suite functional. |
| #222 | Test persona accounts (12) | Superseded by `TEST_LOGIN_SECRET` single-account test-login in `web/auth.py:781-807`. 12-persona plan abandoned. |
| #207 | Orphaned test files | test_plan_images.py → tests `web/plan_images.py` (exists). test_plan_ui.py → tests plan endpoints (exist). NOT orphaned. |
| #209 | Nightly CI verified | 3 GH Actions workflows: `ci.yml` (2:30 AM PT, lint+tests+network), `nightly-cron.yml` (pipeline after CI), `nightly-chief-sync.yml`. All working. |

### Tasks Kept Open (2)

| Task | Description | Reason |
|------|-------------|--------|
| #261 | property_signals populating | `/cron/signals` endpoint exists + in nightly workflow. But prod migration (#217) may be pending — can't verify from code. |
| #210 | Slow test_analyze_plans | P3. 20 tests, 494 lines. PDF processing + mocked Vision. Needs timing measurement on actual run. |

### Tasks Updated (1)

| Task | Description | Update |
|------|-------------|--------|
| #143 | Cost tracking middleware | DDL + full implementation exists in `web/cost_tracking.py` (407 lines, `log_api_call()`, `get_cost_summary()`, kill switch). BUT no middleware wired in `app.py` — zero `before_request`/`after_request` hooks. #333 covers the wiring work. |

### New Tasks Created (1)

| Task | Description | Priority |
|------|-------------|----------|
| #342 | Verify DQ checks pass on prod/staging (replaces stale #178) | P2 |

### Items Not Investigated (Future Session)

Chief #323 (expanded sweep) has Groups B and C remaining:
- **Group B** (run on prod/staging): inspections_unique migration (#260), api_usage table (#232), TESTING=1 on staging (#265), test-login admin sync (#246)
- **Group C** (read and assess): pipeline health materialized views (#120), cron_log timeout sweep (#118), signals migration (#217), signals + velocity cron config (#218)
