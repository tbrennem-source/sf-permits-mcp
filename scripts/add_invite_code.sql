-- Add invite code tracking to users table
-- Run against PostgreSQL: psql $DATABASE_URL -f scripts/add_invite_code.sql
-- Idempotent: uses ADD COLUMN IF NOT EXISTS.

-- invite_code: the code used at signup (NULL for pre-existing users)
ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_code TEXT;

-- Index for cohort queries
CREATE INDEX IF NOT EXISTS idx_users_invite_code
    ON users (invite_code)
    WHERE invite_code IS NOT NULL;
