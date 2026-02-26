"""Railway release command -- runs schema migrations once per deploy.

Executed by Railway's releaseCommand before any gunicorn workers start.
This means migrations run exactly once, not per-worker, and don't block
the health check or incoming requests.

The migration SQL is intentionally duplicated from web/app.py's
``_run_startup_migrations()`` so this script stays lightweight and
never imports the full Flask application.

Usage: python -m scripts.release
"""

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("release")

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def run_release_migrations():
    """Run all pending Postgres schema migrations. Idempotent.

    Returns True on success, False if skipped (DuckDB backend).
    Raises on failure so the caller can sys.exit(1).
    """
    from src.db import BACKEND, get_connection

    if BACKEND != "postgres":
        logger.info("DuckDB backend -- skipping release migrations")
        return False

    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    # -- Base tables (needed for fresh Postgres, idempotent) ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     SERIAL PRIMARY KEY,
            email       TEXT NOT NULL UNIQUE,
            display_name TEXT,
            role        TEXT,
            firm_name   TEXT,
            entity_id   INTEGER,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_login_at TIMESTAMPTZ,
            email_verified BOOLEAN NOT NULL DEFAULT FALSE,
            is_admin    BOOLEAN NOT NULL DEFAULT FALSE,
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            brief_frequency TEXT NOT NULL DEFAULT 'none',
            last_brief_sent_at TIMESTAMPTZ,
            invite_code TEXT,
            primary_street_number TEXT,
            primary_street_name TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS auth_tokens (
            token_id    SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            token       TEXT NOT NULL UNIQUE,
            purpose     TEXT NOT NULL DEFAULT 'login',
            expires_at  TIMESTAMPTZ NOT NULL,
            used_at     TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS watch_items (
            watch_id    SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            watch_type  TEXT NOT NULL,
            permit_number TEXT,
            street_number TEXT,
            street_name TEXT,
            block       TEXT,
            lot         TEXT,
            entity_id   INTEGER,
            neighborhood TEXT,
            label       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            tags        TEXT DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS permit_changes (
            change_id   SERIAL PRIMARY KEY,
            permit_number TEXT NOT NULL,
            change_date DATE NOT NULL,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            old_status  TEXT,
            new_status  TEXT NOT NULL,
            old_status_date TEXT,
            new_status_date TEXT,
            change_type TEXT NOT NULL,
            is_new_permit BOOLEAN NOT NULL DEFAULT FALSE,
            source      TEXT NOT NULL DEFAULT 'nightly',
            permit_type TEXT,
            street_number TEXT,
            street_name TEXT,
            neighborhood TEXT,
            block       TEXT,
            lot         TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS regulatory_watch (
            watch_id    SERIAL PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT,
            source_type TEXT NOT NULL,
            source_id   TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'monitoring',
            impact_level TEXT DEFAULT 'moderate',
            affected_sections TEXT,
            semantic_concepts TEXT,
            url         TEXT,
            filed_date  TEXT,
            effective_date TEXT,
            notes       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_auth_token ON auth_tokens (token)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_watch_user ON watch_items (user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_watch_permit ON watch_items (permit_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pc_date ON permit_changes (change_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pc_permit ON permit_changes (permit_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_regwatch_status ON regulatory_watch (status)")

    # invite_code column
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_code TEXT")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_invite_code
        ON users (invite_code)
        WHERE invite_code IS NOT NULL
    """)

    # Activity log + feedback tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            log_id      SERIAL PRIMARY KEY,
            user_id     INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
            action      TEXT NOT NULL,
            detail      JSONB,
            path        TEXT,
            ip_hash     TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log (user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activity_action ON activity_log (action)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log (created_at)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id     SERIAL PRIMARY KEY,
            user_id         INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
            feedback_type   TEXT NOT NULL DEFAULT 'suggestion',
            message         TEXT NOT NULL,
            page_url        TEXT,
            status          TEXT NOT NULL DEFAULT 'new',
            admin_note      TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at     TIMESTAMPTZ
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback (status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback (user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback (created_at)")
    cur.execute("ALTER TABLE feedback ADD COLUMN IF NOT EXISTS screenshot_data TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_street_number TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_street_name TEXT")

    # Points ledger table (bounty system)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS points_ledger (
            ledger_id   SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            points      INTEGER NOT NULL,
            reason      TEXT NOT NULL,
            feedback_id INTEGER REFERENCES feedback(feedback_id) ON DELETE SET NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_points_user ON points_ledger (user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_points_feedback ON points_ledger (feedback_id)")

    # Fix inspections.id for auto-increment
    try:
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE schemaname = 'public' AND sequencename = 'inspections_id_seq') THEN
                    CREATE SEQUENCE inspections_id_seq;
                    ALTER TABLE inspections ALTER COLUMN id SET DEFAULT nextval('inspections_id_seq');
                END IF;
                PERFORM setval('inspections_id_seq', COALESCE((SELECT MAX(id) FROM inspections), 0) + 1);
            END
            $$
        """)
    except Exception:
        pass  # Non-fatal if inspections table doesn't exist yet

    # cron_log table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cron_log (
            log_id      SERIAL PRIMARY KEY,
            job_type    TEXT NOT NULL,
            started_at  TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ,
            status      TEXT NOT NULL DEFAULT 'running',
            lookback_days INTEGER,
            soda_records INTEGER,
            changes_inserted INTEGER,
            inspections_updated INTEGER,
            error_message TEXT,
            was_catchup BOOLEAN DEFAULT FALSE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cron_log_job_status ON cron_log (job_type, status)")

    # Plan analysis session tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plan_analysis_sessions (
            session_id      TEXT PRIMARY KEY,
            filename        TEXT NOT NULL,
            page_count      INTEGER NOT NULL,
            page_extractions JSONB,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plan_analysis_images (
            session_id      TEXT NOT NULL REFERENCES plan_analysis_sessions(session_id) ON DELETE CASCADE,
            page_number     INTEGER NOT NULL,
            image_data      TEXT NOT NULL,
            image_size_kb   INTEGER,
            PRIMARY KEY (session_id, page_number)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_plan_sessions_created ON plan_analysis_sessions (created_at)")
    cur.execute("ALTER TABLE plan_analysis_sessions ADD COLUMN IF NOT EXISTS user_id INTEGER")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_plan_sessions_user ON plan_analysis_sessions (user_id)")
    cur.execute("ALTER TABLE plan_analysis_sessions ADD COLUMN IF NOT EXISTS page_annotations TEXT")

    # Plan analysis jobs table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plan_analysis_jobs (
            job_id              TEXT PRIMARY KEY,
            user_id             INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
            session_id          TEXT REFERENCES plan_analysis_sessions(session_id) ON DELETE SET NULL,
            filename            TEXT NOT NULL,
            file_size_mb        REAL NOT NULL,
            status              TEXT NOT NULL DEFAULT 'pending',
            is_async            BOOLEAN NOT NULL DEFAULT FALSE,
            project_description TEXT,
            permit_type         TEXT,
            is_addendum         BOOLEAN NOT NULL DEFAULT FALSE,
            quick_check         BOOLEAN NOT NULL DEFAULT FALSE,
            report_md           TEXT,
            error_message       TEXT,
            pdf_data            BYTEA,
            property_address    TEXT,
            permit_number       TEXT,
            address_source      TEXT,
            permit_source       TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at          TIMESTAMPTZ,
            completed_at        TIMESTAMPTZ,
            email_sent          BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_plan_jobs_user ON plan_analysis_jobs (user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_plan_jobs_status ON plan_analysis_jobs (status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_plan_jobs_permit ON plan_analysis_jobs (permit_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_plan_jobs_address ON plan_analysis_jobs (property_address)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_plan_jobs_created ON plan_analysis_jobs (created_at)")

    # Tags column for watch items
    cur.execute("ALTER TABLE watch_items ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT ''")

    # Progress tracking columns
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS progress_stage TEXT")
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS progress_detail TEXT")

    # Vision usage tracking
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS vision_usage_json TEXT")
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS gallery_duration_ms INTEGER")

    # Billing tier plumbing
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'free'")
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS analysis_mode TEXT DEFAULT 'sample'")
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS pages_analyzed INTEGER")

    # Submission stage
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS submission_stage TEXT")

    # Phase D1: Close Project -- archive flag
    cur.execute(
        "ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS "
        "is_archived BOOLEAN NOT NULL DEFAULT FALSE"
    )

    # Phase D2: Document Fingerprinting
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS pdf_hash TEXT")
    cur.execute(
        "ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS "
        "pdf_hash_failed BOOLEAN NOT NULL DEFAULT FALSE"
    )
    cur.execute(
        "ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS structural_fingerprint JSONB"
    )

    # Phase E1: Version Chain data model
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS version_group TEXT")
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS version_number INTEGER")
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS parent_job_id TEXT")

    # Phase E2: Comparison cache
    cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS comparison_json JSONB")

    # Phase F2: Project Notes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS project_notes (
            note_id         SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            version_group   TEXT NOT NULL,
            notes_text      TEXT NOT NULL DEFAULT '',
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, version_group)
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_notes_user_group "
        "ON project_notes (user_id, version_group)"
    )

    # Voice & style preferences
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS voice_style TEXT")

    # Voice calibration table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS voice_calibrations (
            calibration_id  SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            scenario_key    TEXT NOT NULL,
            audience        TEXT NOT NULL,
            situation       TEXT NOT NULL,
            template_text   TEXT NOT NULL,
            user_text       TEXT,
            style_notes     TEXT,
            is_calibrated   BOOLEAN NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, scenario_key)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_voicecal_user ON voice_calibrations (user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_voicecal_scenario ON voice_calibrations (scenario_key)")

    # Addenda changes table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS addenda_changes (
            change_id           SERIAL PRIMARY KEY,
            application_number  TEXT NOT NULL,
            change_date         DATE NOT NULL,
            detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            station             TEXT,
            addenda_number      INTEGER,
            step                INTEGER,
            plan_checked_by     TEXT,
            old_review_results  TEXT,
            new_review_results  TEXT,
            hold_description    TEXT,
            finish_date         TEXT,
            change_type         TEXT NOT NULL,
            source              TEXT NOT NULL DEFAULT 'nightly',
            department          TEXT,
            permit_type         TEXT,
            street_number       TEXT,
            street_name         TEXT,
            neighborhood        TEXT,
            block               TEXT,
            lot                 TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ac_date ON addenda_changes (change_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ac_app_num ON addenda_changes (application_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ac_station ON addenda_changes (station)")

    # DQ cache table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dq_cache (
            id              SERIAL PRIMARY KEY,
            results_json    TEXT NOT NULL,
            refreshed_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            duration_secs   FLOAT
        )
    """)

    # Bulk table indexes
    _bulk_indexes = [
        ("idx_contacts_permit", "contacts", "permit_number"),
        ("idx_contacts_entity", "contacts", "entity_id"),
        ("idx_contacts_name", "contacts", "name"),
        ("idx_permits_number", "permits", "permit_number"),
        ("idx_permits_block_lot", "permits", "block, lot"),
        ("idx_permits_street", "permits", "street_number, street_name"),
        ("idx_permits_neighborhood", "permits", "neighborhood"),
        ("idx_permits_status_date", "permits", "status_date"),
        ("idx_inspections_ref", "inspections", "reference_number"),
        ("idx_inspections_block_lot", "inspections", "block, lot"),
        ("idx_entities_name", "entities", "canonical_name"),
        ("idx_relationships_a", "relationships", "entity_id_a"),
        ("idx_relationships_b", "relationships", "entity_id_b"),
        ("idx_addenda_app_num", "addenda", "application_number"),
        ("idx_addenda_station", "addenda", "station"),
        ("idx_addenda_finish", "addenda", "finish_date"),
        ("idx_addenda_app_finish", "addenda", "application_number, finish_date"),
        ("idx_permits_block_lot_status", "permits", "block, lot, status"),
        ("idx_ts_permit", "timeline_stats", "permit_number"),
    ]
    for idx_name, table, columns in _bulk_indexes:
        try:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})")
        except Exception:
            pass  # table may not exist yet on fresh installs

    # Admin auto-seed
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if admin_email:
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO users (email, is_admin, email_verified, is_active) "
                "VALUES (%s, TRUE, TRUE, TRUE)",
                (admin_email,),
            )
            logger.info("Auto-seeded admin user: %s", admin_email)

    cur.close()
    conn.close()
    logger.info("Release migrations complete")
    return True


if __name__ == "__main__":
    try:
        run_release_migrations()
    except Exception as e:
        logger.error("Release migrations failed: %s", e)
        sys.exit(1)
