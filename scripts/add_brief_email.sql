-- Add email brief preferences to users table
-- Run against PostgreSQL: psql $DATABASE_URL -f scripts/add_brief_email.sql
-- Idempotent: uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS.

-- brief_frequency: 'daily', 'weekly', 'none' (default: 'none')
-- Users must opt in explicitly.
ALTER TABLE users ADD COLUMN IF NOT EXISTS brief_frequency TEXT NOT NULL DEFAULT 'none';

-- last_brief_sent_at: tracks when we last emailed this user
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_brief_sent_at TIMESTAMPTZ;

-- Index for the cron job: find active users who want briefs
CREATE INDEX IF NOT EXISTS idx_users_brief
    ON users (brief_frequency)
    WHERE is_active = TRUE AND brief_frequency != 'none';
