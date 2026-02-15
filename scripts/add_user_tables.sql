-- User accounts, auth tokens, and watch list tables
-- Run against PostgreSQL: psql $DATABASE_URL -f scripts/add_user_tables.sql
-- Idempotent: uses IF NOT EXISTS throughout.

-- -------------------------------------------------------------------------
-- users — core user registration
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id         SERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    display_name    TEXT,
    role            TEXT,                -- 'expediter','architect','contractor','owner','other'
    firm_name       TEXT,
    entity_id       INTEGER,             -- optional: claimed entity from entities table
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ,
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_entity ON users (entity_id) WHERE entity_id IS NOT NULL;

-- -------------------------------------------------------------------------
-- auth_tokens — magic link passwordless authentication
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS auth_tokens (
    token_id    SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token       TEXT NOT NULL UNIQUE,
    purpose     TEXT NOT NULL DEFAULT 'login',   -- 'login', 'verify_email'
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_tokens_token ON auth_tokens (token) WHERE used_at IS NULL;

-- -------------------------------------------------------------------------
-- watch_items — what a user is watching (polymorphic)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS watch_items (
    watch_id        SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    watch_type      TEXT NOT NULL,       -- 'permit','address','parcel','entity','neighborhood'

    -- Type-specific keys (only relevant fields populated per type)
    permit_number   TEXT,                -- watch_type='permit'
    street_number   TEXT,                -- watch_type='address'
    street_name     TEXT,                -- watch_type='address'
    block           TEXT,                -- watch_type='parcel'
    lot             TEXT,                -- watch_type='parcel'
    entity_id       INTEGER,             -- watch_type='entity'
    neighborhood    TEXT,                -- watch_type='neighborhood'

    label           TEXT,                -- user-facing label
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT valid_watch_type CHECK (
        watch_type IN ('permit', 'address', 'parcel', 'entity', 'neighborhood')
    )
);

CREATE INDEX IF NOT EXISTS idx_watch_user ON watch_items (user_id);
CREATE INDEX IF NOT EXISTS idx_watch_permit ON watch_items (permit_number)
    WHERE watch_type = 'permit' AND is_active;
CREATE INDEX IF NOT EXISTS idx_watch_address ON watch_items (street_number, street_name)
    WHERE watch_type = 'address' AND is_active;
CREATE INDEX IF NOT EXISTS idx_watch_entity ON watch_items (entity_id)
    WHERE watch_type = 'entity' AND is_active;
