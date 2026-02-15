-- Activity log and feedback tables
-- Run against PostgreSQL: psql $DATABASE_URL -f scripts/add_activity_tables.sql
-- Idempotent: uses IF NOT EXISTS throughout.

-- -------------------------------------------------------------------------
-- activity_log — every meaningful user action
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_log (
    log_id      SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    action      TEXT NOT NULL,           -- 'search','analyze','login','watch_add','brief_view','page_view'
    detail      JSONB,                   -- {"query":"723 16th ave","intent":"search_address"}
    path        TEXT,                    -- '/ask', '/analyze', etc.
    ip_hash     TEXT,                    -- SHA256 of IP (privacy-preserving)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log (user_id);
CREATE INDEX IF NOT EXISTS idx_activity_action ON activity_log (action);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log (created_at);

-- -------------------------------------------------------------------------
-- feedback — user-submitted bugs, suggestions, questions
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id     SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    feedback_type   TEXT NOT NULL DEFAULT 'suggestion',  -- 'bug','suggestion','question'
    message         TEXT NOT NULL,
    page_url        TEXT,                -- the page they were on
    status          TEXT NOT NULL DEFAULT 'new',  -- 'new','reviewed','resolved','wontfix'
    admin_note      TEXT,                -- admin response / internal note
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,

    CONSTRAINT valid_feedback_type CHECK (
        feedback_type IN ('bug', 'suggestion', 'question')
    ),
    CONSTRAINT valid_feedback_status CHECK (
        status IN ('new', 'reviewed', 'resolved', 'wontfix')
    )
);

CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback (status);
CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback (user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback (created_at);
