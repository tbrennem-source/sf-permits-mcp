-- permit_changes: Daily changelog populated by nightly SODA delta fetch + historical backfill.
-- Run against Railway Postgres after deploying the nightly_changes.py script.
--
-- Usage: psql $DATABASE_URL -f scripts/add_changes_table.sql

CREATE TABLE IF NOT EXISTS permit_changes (
    change_id       SERIAL PRIMARY KEY,
    permit_number   TEXT NOT NULL,
    change_date     DATE NOT NULL,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- What changed (old -> new)
    old_status      TEXT,
    new_status      TEXT NOT NULL,
    old_status_date TEXT,
    new_status_date TEXT,

    -- Classification
    change_type     TEXT NOT NULL,               -- 'status_change', 'new_permit', 'cost_revision'
    is_new_permit   BOOLEAN NOT NULL DEFAULT FALSE,
    source          TEXT NOT NULL DEFAULT 'nightly',  -- 'nightly', 'backfill'

    -- Denormalized permit context (avoids multi-table joins in dashboard queries)
    permit_type     TEXT,
    street_number   TEXT,
    street_name     TEXT,
    neighborhood    TEXT,
    block           TEXT,
    lot             TEXT
);

CREATE INDEX IF NOT EXISTS idx_pc_date ON permit_changes (change_date);
CREATE INDEX IF NOT EXISTS idx_pc_permit ON permit_changes (permit_number);
CREATE INDEX IF NOT EXISTS idx_pc_permit_date ON permit_changes (permit_number, change_date DESC);
CREATE INDEX IF NOT EXISTS idx_pc_source ON permit_changes (source);

-- Also add the missing status_date index on permits (needed for nightly delta queries)
CREATE INDEX IF NOT EXISTS idx_permits_status_date ON permits (status_date);
