# Database Backup Strategy

## What we're protecting

| Data category | Recovery method | Backup needed? |
|---|---|---|
| Permits, contacts, entities, relationships, inspections | Re-ingest from SODA API (`python -m src.ingest`) | No |
| Knowledge base (tier1-3 JSON/text) | Checked into git (`data/knowledge/`) | No |
| **Users, watch items, feedback, activity logs** | **No external source — must backup** | **Yes** |
| **Permit changes (nightly diffs)** | **Accumulated over time — hard to recreate** | **Yes** |
| **Plan analysis sessions/jobs** | **User uploads — cannot recreate** | **Yes** |
| **Regulatory watch items** | **Admin-curated — cannot recreate** | **Yes** |

## Three layers of protection

### 1. Railway native backups (dashboard)

Railway offers volume-level snapshots for Postgres services with attached volumes.

**Setup steps:**
1. Go to Railway dashboard → your Postgres service (currently `pgvector-db`)
2. Click the service → **Settings** tab → **Backups** section
3. Enable:
   - **Daily** backups (6-day retention)
   - **Weekly** backups (1-month retention)

**Limitations:**
- Dashboard-only (no CLI commands)
- Cannot restore across environments
- Wiping the volume deletes all backups
- Backups capped at 50% of volume size

### 2. pg_dump via cron endpoint

A `/cron/backup` endpoint runs `pg_dump` on the user-data tables and stores timestamped `.dump` files.

**Tables backed up:**
- `users`, `auth_tokens`, `watch_items`
- `feedback`, `activity_log`, `points_ledger`
- `regulatory_watch`, `cron_log`, `permit_changes`
- `plan_analysis_sessions`, `plan_analysis_jobs`

**Trigger via scheduler (e.g., cron-job.org):**
```
POST https://sfpermits-ai-production.up.railway.app/cron/backup
Authorization: Bearer <CRON_SECRET>
```

**Trigger locally:**
```bash
# Backup user-data tables (default)
DATABASE_URL=<url> python -m scripts.db_backup

# Full database backup
DATABASE_URL=<url> python -m scripts.db_backup --full

# List existing backups
python -m scripts.db_backup --list

# Restore from backup
DATABASE_URL=<url> python -m scripts.db_backup --restore backups/backup-userdata-20260217-030000.dump
```

**Retention:** 7 days by default (`BACKUP_RETENTION_DAYS` env var). Old files pruned automatically.

### 3. Admin auto-seed

If the Postgres database is ever wiped and the `users` table is empty, the startup migration automatically creates an admin account from the `ADMIN_EMAIL` environment variable. This ensures the admin can always log in without an invite code after a DB reset.

## Env vars

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | (required for pg_dump) |
| `CRON_SECRET` | Bearer token for cron endpoints | (required) |
| `ADMIN_EMAIL` | Auto-seed admin on empty DB | (recommended) |
| `BACKUP_RETENTION_DAYS` | Days to keep local backups | `7` |

## Recovery playbook

**Scenario: Postgres wiped (what happened 2026-02-17)**

1. App restarts → startup migration creates empty tables
2. Admin auto-seed creates admin account from `ADMIN_EMAIL`
3. Restore user data: `python -m scripts.db_backup --restore <latest .dump>`
4. Re-ingest permit data: `python -m src.ingest && python -m src.entities && python -m src.graph`

**Scenario: Need to restore specific tables**

```bash
pg_restore --dbname $DATABASE_URL --no-owner --clean --if-exists -t users -t watch_items backups/backup-userdata-YYYYMMDD-HHMMSS.dump
```
