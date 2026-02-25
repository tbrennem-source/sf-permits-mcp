# DIAGNOSTIC-53B — Sprint 53.B Pre-Flight Assessment

**Date:** 2026-02-24
**Orchestrator:** Claude Opus 4.6

---

## 1. Signal Tables on Prod

**Status: NOT DEPLOYED**

```sql
SELECT COUNT(*) FROM information_schema.tables
WHERE table_name IN ('signal_types','permit_signals','property_signals',
                     'property_health','api_usage','api_daily_summary')
-- Result: 0
```

None of the 6 tables exist. Both `migrate_signals.py` (4 signal tables + 13 type seeds) and `migrate_cost_tracking.py` (2 cost tables) need to run.

## 2. Addenda Data Freshness

**Status: FRESH**

| Metric | Value |
|--------|-------|
| MAX(data_as_of) | 2026-02-23 (1 day old — OK) |
| MAX(finish_date) | 2205-07-24 (SODA data quality issue — far-future date) |
| MAX(arrive) | 2205-07-24 (same) |
| Row count | 3,920,710 |

## 3. Cron Log

**Status: RUNNING OK (1 stuck job)**

- Last successful nightly: 2026-02-24 12:09:03 UTC (today)
- 18 total runs, mostly succeeding
- **log_id 14 stuck** in `running` state since 2026-02-22 18:06 — needs cleanup
- Missing columns: `duration_seconds`, `records_processed` — no migration exists for these

## 4. Station Velocity

**Status: HEALTHY**

| Count | Max Baseline Date |
|-------|-------------------|
| 210 | 2026-02-24 |

## 5. Pipeline Health in Email Brief

**Status: CONFIRMED MISSING**

`web/email_brief.py:124` — `render_template("brief_email.html", ...)` does NOT include `pipeline_health` kwarg.

`web/pipeline_health.py:384` — `get_pipeline_health_brief()` exists and returns `{status, issues, checks}` but is never called in email_brief.py.

`web/templates/brief_email.html` — No conditional pipeline health alert section exists.

## 6. Nightly Script — data_as_of Age Check

**Status: CONFIRMED MISSING**

`scripts/nightly_changes.py:1057-1089` — `staleness_warnings` checks:
- Zero SODA records (permits, inspections, addenda)
- Retry-extended flag
- Step failures

Does NOT check `MAX(data_as_of)` age. A stale-but-nonzero addenda dataset would slip through undetected.

## 7. GitHub Actions Nightly Cron

**Status: MISSING ENDPOINTS**

`nightly-cron.yml` calls:
1. `POST /cron/nightly` (exists)
2. `POST /cron/rag-ingest?tier=ops` (exists)
3. `POST /cron/send-briefs` (exists)

**Missing from workflow:**
- `POST /cron/signals` (endpoint exists in app.py:6022 but not wired in workflow)
- `POST /cron/velocity-refresh` (endpoint exists in app.py:6054 but not wired in workflow)

**Telegram alert:** Present in `ci.yml` (notify job on schedule failures), but NOT in `nightly-cron.yml`.

## 8. Prod Health

**Status: HEALTHY**

- Backend: postgres
- DB connected: true
- 30 tables, key counts: permits 1.1M, contacts 1.8M, addenda 3.9M, entities 1M
- station_velocity: 210 rows

## 9. Existing Cron Endpoints

All needed endpoints already exist in `web/app.py`:
- `/cron/signals` (line 6022)
- `/cron/velocity-refresh` (line 6054)
- `/cron/pipeline-health` (line 6108)
- `/cron/migrate-schema` (line 5678) — for bulk table DDL, not signal/cost tables

## 10. Signal Pipeline Compatibility Issue

`src/signals/pipeline.py` uses DuckDB-style `conn.execute()` with `?` placeholders throughout.
On Postgres (psycopg2), this pattern may fail. The `/cron/signals` endpoint may need a compatibility fix.
The `migrate_signals.py` script uses proper Postgres patterns (cursor-based, `%s` placeholders).

---

## Action Plan

1. **Phase 1:** Create temp `/cron/run-migrations` endpoint calling both signal + cost DDL, deploy, run, verify, remove
2. **Phase 2:** 3 parallel fix agents (FIX-BRIEF, FIX-STALENESS, FIX-CRON)
3. **Phase 3:** Merge, test, push
4. **Phase 4:** 5 parallel QA agents
5. **Phase 5-6:** Report + CHECKCHAT
