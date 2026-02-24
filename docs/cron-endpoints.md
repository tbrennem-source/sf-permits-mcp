# Cron Endpoints

All cron-protected endpoints are under `/cron/` and `/api/`. They require a
`Authorization: Bearer <CRON_SECRET>` header unless noted otherwise.

`CRON_SECRET` is set as a Railway environment variable on the `sfpermits-ai`
service. Requests without a valid token receive **HTTP 403**.

---

## Quick Reference

| Endpoint | Method | Schedule | Purpose |
|---|---|---|---|
| `GET /cron/status` | GET | — (read-only) | View last 20 cron job results |
| `POST /cron/nightly` | POST | Daily ~3 AM PT | Delta permit fetch + change detection |
| `POST /cron/send-briefs` | POST | Daily ~6 AM PT | Email morning briefs to subscribers |
| `POST /cron/rag-ingest` | POST | After deploys | Re-embed knowledge base into pgvector |
| `POST /cron/migrate-schema` | POST | One-time / after schema changes | Create bulk data tables |
| `POST /cron/migrate-data` | POST | One-time / batch | Push bulk row data to Postgres |
| `POST /cron/seed-regulatory` | POST | One-time | Seed regulatory watch items |
| `POST /cron/refresh-dq` | POST | After bulk loads | Refresh data quality cache |
| `POST /cron/signals` | POST | Nightly after `/cron/nightly` | Signal detection + property health |
| `POST /cron/velocity-refresh` | POST | Nightly after `/cron/signals` | Refresh station velocity baselines |
| `POST /cron/backup` | POST | Daily after nightly | pg_dump user-data tables |

---

## Detailed Endpoint Reference

### `GET /cron/status`

**Auth:** none (public read-only)

Returns the 20 most recent entries from `cron_log` as JSON. Use this to
verify that nightly jobs are running and check for errors without needing
direct DB access.

```bash
curl https://sfpermits-ai-production.up.railway.app/cron/status | python3 -m json.tool
```

**Response shape:**
```json
{
  "ok": true,
  "total": 20,
  "jobs": [
    {
      "job_type": "nightly",
      "started_at": "2025-01-20 03:00:01",
      "completed_at": "2025-01-20 03:04:22",
      "status": "success",
      "soda_records": 1240,
      "changes_inserted": 38,
      "inspections_updated": 410,
      "was_catchup": false,
      "error_message": null
    }
  ]
}
```

---

### `POST /cron/nightly`

**Auth:** `CRON_SECRET` bearer token  
**Schedule:** Daily ~3 AM PT via Railway cron or cron-job.org  
**Query params:**
- `lookback` — days to look back (default: `1`, pass `7` for catch-up)

Fetches the latest permit/inspection/addenda delta from the SODA API, detects
changes vs. what was previously stored, and writes new rows to `permit_changes`.
Also updates the `cron_log` table. If data staleness is detected it sends an
alert email to admins.

```bash
curl -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-production.up.railway.app/cron/nightly
```

Catch-up run (7-day lookback):
```bash
curl -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "https://sfpermits-ai-production.up.railway.app/cron/nightly?lookback=7"
```

---

### `POST /cron/send-briefs`

**Auth:** `CRON_SECRET` bearer token  
**Schedule:** Daily ~6 AM PT (daily subscribers); Monday ~6 AM PT (weekly)  
**Query params:**
- `frequency` — `daily` (default) or `weekly`

Sends morning brief emails to all active users subscribed at the given
frequency. Also appends a nightly triage report email to admins.

```bash
# Daily run
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  "https://sfpermits-ai-production.up.railway.app/cron/send-briefs?frequency=daily"

# Weekly run (Monday only)
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  "https://sfpermits-ai-production.up.railway.app/cron/send-briefs?frequency=weekly"
```

---

### `POST /cron/rag-ingest`

**Auth:** `CRON_SECRET` bearer token  
**Schedule:** One-time after deploy; re-run after knowledge base updates  
**Query params:**
- `tier` — `tier1` | `tier2` | `tier3` | `tier4` | `ops` | `all` (default: `all`)
- `clear` — `0` to skip clearing existing chunks before re-ingestion

Chunks the knowledge base, generates OpenAI embeddings, and stores them in
the `knowledge_chunks` pgvector table. The `ops` tier self-manages its chunks
(no clear needed). After bulk insert, rebuilds the IVFFlat index for fast ANN
search.

```bash
# Full re-ingest
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  "https://sfpermits-ai-production.up.railway.app/cron/rag-ingest?tier=all"

# Tier1 only, skip clear
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  "https://sfpermits-ai-production.up.railway.app/cron/rag-ingest?tier=tier1&clear=0"
```

---

### `POST /cron/migrate-schema`

**Auth:** `CRON_SECRET` bearer token  
**Schedule:** One-time setup; safe to re-run (CREATE IF NOT EXISTS throughout)

Runs `scripts/postgres_schema.sql` to create the bulk data tables:
`permits`, `contacts`, `entities`, `relationships`, `inspections`,
`timeline_stats`, `ingest_log`. Only works in Postgres mode (Railway).

```bash
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-production.up.railway.app/cron/migrate-schema
```

---

### `POST /cron/migrate-data`

**Auth:** `CRON_SECRET` bearer token  
**Schedule:** One-time data migration; use `scripts/push_migration.py` for automation

Accepts a JSON batch of rows and inserts them into a bulk data table. Used
by `scripts/push_migration.py` to push DuckDB data to production Postgres in
5,000-row batches.

**Request body:**
```json
{
  "table": "permits",
  "columns": ["permit_number", "permit_type", "status", "..."],
  "rows": [["202400001", "OTC Alterations", "complete", "..."]],
  "truncate": false
}
```

Allowed tables: `permits`, `contacts`, `entities`, `relationships`,
`inspections`, `timeline_stats`, `ingest_log`, `addenda`, `violations`,
`complaints`, `businesses`.

---

### `POST /cron/seed-regulatory`

**Auth:** `CRON_SECRET` bearer token  
**Schedule:** One-time; safe to re-run (will attempt to insert duplicates)

Seeds regulatory watch items from a JSON array. Useful for bootstrapping the
regulatory watch table from an external source.

**Request body:** JSON array of item objects:
```json
[
  {
    "title": "AB 2097 — Parking Minimums Reform",
    "source_type": "state_bill",
    "source_id": "CA-AB-2097",
    "status": "enacted",
    "impact_level": "high"
  }
]
```

---

### `POST /cron/refresh-dq`

**Auth:** `CRON_SECRET` bearer token  
**Schedule:** After bulk data loads; can also be called from the nightly job

Refreshes the data quality (DQ) cache — computes freshness metrics,
record counts, and completeness stats across the bulk data tables.

```bash
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-production.up.railway.app/cron/refresh-dq
```

---

### `POST /cron/signals`

**Auth:** `CRON_SECRET` bearer token  
**Schedule:** Nightly, after `/cron/nightly` completes

Runs the full signal detection pipeline across all permits, violations,
complaints, and inspections. Detects 13 signal types and computes per-property
health tiers (`on_track` → `high_risk`). Writes results to `permit_signals`,
`property_signals`, and `property_health` tables.

**Requires:** Signal tables to exist — run `scripts/run_prod_migrations.py --only signals`
or `POST /cron/signals` will fail if the tables are missing.

```bash
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-production.up.railway.app/cron/signals
```

---

### `POST /cron/velocity-refresh`

**Auth:** `CRON_SECRET` bearer token  
**Schedule:** Nightly, after `/cron/signals` completes

Recomputes station velocity v2 baselines (p25/p50/p75/p90) per review station,
per metric type (initial/revision), and per period (all / 2024–2026 / recent 6mo).
Used by the velocity dashboard and permit ETA estimates.

```bash
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-production.up.railway.app/cron/velocity-refresh
```

---

### `POST /cron/backup`

**Auth:** `CRON_SECRET` bearer token  
**Schedule:** Daily, after the nightly refresh  

Runs `pg_dump` of the user-data tables (`users`, `auth_tokens`, `watch_items`,
`feedback`, `activity_log`, `points_ledger`) and stores a timestamped backup
file. Returns backup metadata (filename, size, row counts).

```bash
curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-production.up.railway.app/cron/backup
```

---

## Recommended Nightly Schedule

Run these in order with 2–5 minute gaps between steps:

| Time (PT) | Endpoint | Notes |
|---|---|---|
| 3:00 AM | `POST /cron/nightly` | Core delta fetch |
| 3:10 AM | `POST /cron/signals` | Signal detection on fresh data |
| 3:20 AM | `POST /cron/velocity-refresh` | Velocity baselines |
| 3:30 AM | `POST /cron/backup` | Daily pg_dump |
| 6:00 AM | `POST /cron/send-briefs?frequency=daily` | User emails |
| Mon 6:00 AM | `POST /cron/send-briefs?frequency=weekly` | Weekly digest |

---

## Future Endpoints (Planned)

| Endpoint | Status | Purpose |
|---|---|---|
| `POST /cron/embed-ops` | Planned | Incrementally embed new ops chunks without full re-ingest |
| `POST /cron/cleanup-tokens` | Planned | Purge expired auth tokens from `auth_tokens` table |
| `POST /cron/aggregate-activity` | Planned | Roll up `activity_log` into weekly summary stats |
| `POST /cron/warm-cache` | Planned | Pre-warm neighborhood/entity stats after bulk data loads |
| `POST /cron/health-check` | Planned | Comprehensive internal health probe (DB, SODA, RAG index) |

---

## Environment Variables Required

| Variable | Used by | Notes |
|---|---|---|
| `CRON_SECRET` | All `/cron/*` POST endpoints | Set in Railway → sfpermits-ai → Variables |
| `DATABASE_URL` | All DB-touching endpoints | Points to pgvector-db (internal Railway URL) |
| `ANTHROPIC_API_KEY` | `/cron/signals` (indirectly) | If signal pipeline calls Claude |
| `OPENAI_API_KEY` | `/cron/rag-ingest` | Used for embedding generation |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` | `/cron/send-briefs`, staleness alerts | Optional — skipped if not set |
| `SMTP_FROM` | `/cron/send-briefs` | Defaults to `noreply@sfpermits.ai` |
