"""sfpermits.ai — Amy's permit analysis web UI.

Flask application factory, middleware, hooks, and Blueprint registration.
Route implementations live in web/routes_*.py modules.
"""

import json
import logging
import os
import sys
import time
from datetime import timedelta

from flask import (
    Flask, render_template, request, abort, Response, redirect,
    url_for, session, g, jsonify,
)

# Configure logging so gunicorn captures warnings from tools
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


# ---------------------------------------------------------------------------
# App creation + config
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-key-change-in-prod")
app.permanent_session_lifetime = timedelta(days=30)

# Cookie security: Secure (HTTPS-only in prod), HttpOnly (default), SameSite=Lax
_is_prod = os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("BASE_URL", "").startswith("https")
app.config["SESSION_COOKIE_SECURE"] = bool(_is_prod)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# 400 MB max upload for plan set PDFs (site permit addenda can be up to 350 MB)
app.config["MAX_CONTENT_LENGTH"] = 400 * 1024 * 1024


# ---------------------------------------------------------------------------
# Jinja2 template filters
# ---------------------------------------------------------------------------

@app.template_filter("to_pst")
def _to_pst_filter(dt):
    """Convert a UTC datetime to US/Pacific for display."""
    if not dt:
        return ""
    from datetime import timezone as tz
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz.utc)
    return dt.astimezone(ZoneInfo("America/Los_Angeles"))


@app.template_filter("friendly_error")
def _friendly_error_filter(msg):
    """Convert raw Python errors to user-friendly messages."""
    if not msg:
        return ""
    if "interpreter shutdown" in msg or "cannot schedule new futures" in msg:
        return "Server restarted during analysis. Please try again."
    if "ANTHROPIC_API_KEY" in msg:
        return "AI vision service temporarily unavailable."
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return "Analysis timed out. Try Quick Check for faster results."
    return msg


# ---------------------------------------------------------------------------
# Context processors
# ---------------------------------------------------------------------------

from web.helpers import BRAND_CONFIG  # noqa: E402


@app.context_processor
def inject_brand():
    """Make BRAND_CONFIG available in all templates."""
    return {"brand": BRAND_CONFIG}


@app.context_processor
def _inject_gate():
    """Inject feature gate context into all templates."""
    from web.feature_gate import gate_context
    return {"gate": gate_context(getattr(g, 'user', None))}


ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")
IS_STAGING = ENVIRONMENT == "staging"


@app.context_processor
def inject_environment():
    """Make environment flags available in all templates."""
    return {
        "is_staging": IS_STAGING,
        "environment_name": ENVIRONMENT,
    }


# ---------------------------------------------------------------------------
# Startup migrations (idempotent, run once per deploy)
# ---------------------------------------------------------------------------

# Tables that _run_startup_migrations creates. Used for post-migration
# verification and /health expected-tables check.
EXPECTED_TABLES = [
    "users", "auth_tokens", "watch_items", "permit_changes", "activity_log",
    "feedback", "points_ledger", "addenda_changes", "regulatory_watch",
    "cron_log", "beta_requests", "projects", "project_members",
    "voice_calibrations", "plan_analysis_sessions", "plan_analysis_images",
    "plan_analysis_jobs", "project_notes", "analysis_sessions",
    "pim_cache", "dq_cache",
]


def _run_startup_migrations():
    """Run any pending schema migrations on startup. Idempotent.

    Uses pg_advisory_lock to serialize across gunicorn workers — only one
    worker runs DDL at a time, preventing deadlocks on new table creation.
    """
    from src.db import BACKEND, get_connection
    if BACKEND != "postgres":
        return  # DuckDB schema is managed by init_user_schema
    logger = logging.getLogger(__name__)
    try:
        conn = get_connection()
        # Set autocommit on the UNDERLYING psycopg2 connection, not the
        # _PooledConnection wrapper (wrapper's __getattr__ only handles reads,
        # not __setattr__). Without this, DDL runs inside an implicit
        # transaction and a single failed ALTER TABLE aborts the entire chain.
        if hasattr(conn, '_conn'):
            conn._conn.autocommit = True
        else:
            conn.autocommit = True
        cur = conn.cursor()

        # Serialize migrations across workers. advisory_lock key 20260226
        # is arbitrary but stable. pg_try_advisory_lock returns immediately:
        # True if we got the lock, False if another worker already holds it.
        cur.execute("SELECT pg_try_advisory_lock(20260226)")
        got_lock = cur.fetchone()[0]
        if not got_lock:
            logger.info("Another worker is running migrations — skipping")
            cur.close()
            conn.close()
            return

        # Kill zombie transactions (e.g. from timed-out /cron/migrate calls)
        # that hold locks and block DDL. Only targets idle-in-transaction
        # sessions older than 5 minutes — safe for normal operations.
        try:
            cur.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid != pg_backend_pid()
                  AND state = 'idle in transaction'
                  AND NOW() - xact_start > interval '5 minutes'
            """)
        except Exception:
            pass

        # Prevent indefinite blocking on DDL locks
        cur.execute("SET lock_timeout = '30s'")

        # ── Base tables (needed for fresh Postgres, idempotent) ──────
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

        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_code TEXT")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_invite_code
            ON users (invite_code)
            WHERE invite_code IS NOT NULL
        """)
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
            pass
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

        cur.execute("ALTER TABLE watch_items ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT ''")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS progress_stage TEXT")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS progress_detail TEXT")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS vision_usage_json TEXT")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS gallery_duration_ms INTEGER")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'free'")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS analysis_mode TEXT DEFAULT 'sample'")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS pages_analyzed INTEGER")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS submission_stage TEXT")
        cur.execute(
            "ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS "
            "is_archived BOOLEAN NOT NULL DEFAULT FALSE"
        )
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS pdf_hash TEXT")
        cur.execute(
            "ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS "
            "pdf_hash_failed BOOLEAN NOT NULL DEFAULT FALSE"
        )
        cur.execute(
            "ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS structural_fingerprint JSONB"
        )
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS version_group TEXT")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS version_number INTEGER")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS parent_job_id TEXT")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS comparison_json JSONB")

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

        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_source TEXT DEFAULT 'invited'")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS detected_persona TEXT")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS beta_requested_at TIMESTAMPTZ")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS beta_approved_at TIMESTAMPTZ")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT, address TEXT, block TEXT, lot TEXT,
                neighborhood TEXT, created_by INTEGER REFERENCES users(user_id),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_parcel ON projects(block, lot)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_members (
                project_id TEXT REFERENCES projects(id), user_id INTEGER REFERENCES users(user_id),
                role TEXT DEFAULT 'member', invited_by INTEGER REFERENCES users(user_id),
                joined_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY (project_id, user_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pm_user ON project_members(user_id)")
        cur.execute("ALTER TABLE analysis_sessions ADD COLUMN IF NOT EXISTS project_id TEXT REFERENCES projects(id)")

        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS voice_style TEXT")

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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS dq_cache (
                id              SERIAL PRIMARY KEY,
                results_json    TEXT NOT NULL,
                refreshed_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                duration_secs   FLOAT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS pim_cache (
                block           TEXT NOT NULL,
                lot             TEXT NOT NULL,
                response_json   JSONB,
                fetched_at      TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (block, lot)
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_pim_cache_fetched ON pim_cache (fetched_at)"
        )

        # ── Bulk table indexes ──────────────────────────────────
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
            ("idx_ts_permit", "timeline_stats", "permit_number"),
        ]

        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'public'
        """)
        existing_indexes = {row[0] for row in cur.fetchall()}

        missing_indexes = [
            (name, table, cols) for name, table, cols in _bulk_indexes
            if name not in existing_indexes
        ]

        if missing_indexes:
            logging.getLogger(__name__).info(
                "Creating %d missing bulk indexes (of %d total)...",
                len(missing_indexes), len(_bulk_indexes),
            )
            cur.execute("SET lock_timeout = '15s'")
            for idx_name, table, columns in missing_indexes:
                try:
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})")
                except Exception:
                    pass
        else:
            logging.getLogger(__name__).info(
                "All %d bulk indexes exist — skipping creation", len(_bulk_indexes)
            )

        # ── Admin auto-seed ───────────────────────────────────────
        admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        if admin_email:
            cur.execute("SELECT COUNT(*) FROM users")
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "INSERT INTO users (email, is_admin, email_verified, is_active) "
                    "VALUES (%s, TRUE, TRUE, TRUE)",
                    (admin_email,),
                )
                logging.getLogger(__name__).info(
                    "Auto-seeded admin user: %s", admin_email
                )

        cur.execute("SELECT pg_advisory_unlock(20260226)")

        cur.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = ANY(%s)
        """, (EXPECTED_TABLES,))
        found = {row[0] for row in cur.fetchall()}
        missing = set(EXPECTED_TABLES) - found
        if missing:
            logger.error(
                "MIGRATION INCOMPLETE — missing tables: %s", sorted(missing)
            )
        else:
            logger.info("Startup migrations complete — all %d expected tables verified", len(EXPECTED_TABLES))

        cur.close()
        conn.close()
    except Exception as e:
        logger.error("Startup migration FAILED: %s", e)
        try:
            cur.execute("SELECT pg_advisory_unlock(20260226)")
            cur.close()
            conn.close()
        except Exception:
            pass


if os.environ.get("RUN_MIGRATIONS_ON_STARTUP", "").lower() in ("1", "true", "yes"):
    _run_startup_migrations()

# Recover stale background analysis jobs from previous worker restarts
try:
    from web.plan_worker import recover_stale_jobs
    recover_stale_jobs()
except Exception as e:
    logging.getLogger(__name__).warning("Stale job recovery failed (non-fatal): %s", e)


# ---------------------------------------------------------------------------
# Blueprint registration
# ---------------------------------------------------------------------------

# Projects (already a Blueprint from Sprint 61B)
from web.projects import (  # noqa: E402
    projects_bp,
    _create_project,
    _get_or_create_project,
    _auto_join_project,
)
app.register_blueprint(projects_bp)

# Route Blueprints (Phase 0 refactor, Sprint 64)
from web.routes_public import bp as public_bp      # noqa: E402
from web.routes_search import bp as search_bp      # noqa: E402
from web.routes_auth import bp as auth_bp          # noqa: E402
from web.routes_admin import bp as admin_bp        # noqa: E402
from web.routes_property import bp as property_bp  # noqa: E402
from web.routes_cron import bp as cron_bp          # noqa: E402
from web.routes_api import bp as api_bp            # noqa: E402
from web.routes_misc import bp as misc_bp          # noqa: E402

app.register_blueprint(public_bp)
app.register_blueprint(search_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(property_bp)
app.register_blueprint(cron_bp)
app.register_blueprint(api_bp)
app.register_blueprint(misc_bp)


# ---------------------------------------------------------------------------
# Backward-compatible endpoint aliases
# ---------------------------------------------------------------------------
# Templates and Python code use url_for("function_name") without Blueprint
# prefix. After Blueprint registration, endpoints become "bp.function_name".
# This block creates app-level aliases so the old names still resolve.

from werkzeug.routing import Rule  # noqa: E402

_alias_done = set()
for _rule in list(app.url_map.iter_rules()):
    _ep = _rule.endpoint
    if '.' not in _ep:
        continue
    _short = _ep.split('.', 1)[1]
    if _short in _alias_done or _short in app.view_functions:
        continue
    _alias_done.add(_short)
    # Register the view function under the short name
    app.view_functions[_short] = app.view_functions[_ep]
    # Add a URL rule so url_for can resolve the short endpoint name
    _methods = _rule.methods - {'OPTIONS', 'HEAD'} if _rule.methods else None
    try:
        app.add_url_rule(
            _rule.rule,
            endpoint=_short,
            view_func=app.view_functions[_ep],
            methods=sorted(_methods) if _methods else None,
        )
    except (AssertionError, ValueError):
        pass  # Duplicate rule — already registered (e.g., static)
del _alias_done, _rule, _ep, _short, _methods


# ---------------------------------------------------------------------------
# Import helpers into app module namespace for backward compatibility
# ---------------------------------------------------------------------------
# Tests and other modules do: from web.app import _rate_buckets, login_required, etc.

from web.helpers import (  # noqa: E402, F401
    _rate_buckets, _is_rate_limited, login_required, admin_required,
    run_async, md_to_html, _resolve_block_lot, _is_no_results,
    _rate_limited_ai, _rate_limited_plans,
    RATE_LIMIT_WINDOW, RATE_LIMIT_MAX_ANALYZE, RATE_LIMIT_MAX_VALIDATE,
    RATE_LIMIT_MAX_ANALYZE_PLANS, RATE_LIMIT_MAX_LOOKUP, RATE_LIMIT_MAX_ASK,
    RATE_LIMIT_MAX_AUTH, NEIGHBORHOODS, BRAND_CONFIG, QUIZ_QUESTIONS,
)

# Re-export functions that moved to Blueprint modules
# (some tests import these directly from web.app)
from web.routes_search import _clean_chunk_content  # noqa: E402, F401
from web.routes_search import _watch_context  # noqa: E402, F401
from web.routes_misc import _get_adu_stats, _adu_stats_cache  # noqa: E402, F401
from web.routes_public import group_jobs_by_project  # noqa: E402, F401

# Re-export tool imports that tests monkeypatch on web.app
# (tests do: patch("web.app.predict_permits", ...) etc.)
from src.tools.predict_permits import predict_permits  # noqa: E402, F401
from src.tools.estimate_fees import estimate_fees  # noqa: E402, F401
from src.tools.estimate_timeline import estimate_timeline  # noqa: E402, F401
from src.tools.required_documents import required_documents  # noqa: E402, F401
from src.tools.revision_risk import revision_risk  # noqa: E402, F401
from src.tools.validate_plans import validate_plans  # noqa: E402, F401
from src.tools.analyze_plans import analyze_plans  # noqa: E402, F401
from src.tools.context_parser import extract_triggers, enhance_description, reorder_sections  # noqa: E402, F401
from src.tools.permit_lookup import permit_lookup  # noqa: E402, F401
from src.tools.search_entity import search_entity  # noqa: E402, F401
from src.tools.knowledge_base import get_knowledge_base  # noqa: E402, F401
from src.tools.intent_router import classify as classify_intent  # noqa: E402, F401
from src.tools.search_complaints import search_complaints  # noqa: E402, F401
from src.tools.search_violations import search_violations  # noqa: E402, F401
from src.tools.team_lookup import generate_team_profile  # noqa: E402, F401


# ---------------------------------------------------------------------------
# Rate limiter state (imported from helpers, kept for backward compat)
# ---------------------------------------------------------------------------
# _rate_buckets is already imported above from web.helpers
# The before_request hooks below reference it via the helpers import.


# ---------------------------------------------------------------------------
# Security: blocked scanner paths
# ---------------------------------------------------------------------------

ROBOTS_TXT = """\
# Beta period — hidden from all crawlers
User-agent: *
Disallow: /
"""

_BLOCKED_PATHS = {
    "/wp-admin", "/wp-login.php", "/wp-content", "/.env", "/.git",
    "/phpmyadmin", "/xmlrpc.php", "/config.php",
    "/actuator", "/.well-known/security.txt",
}
_BLOCKED_EXACT = {"/admin"}


@app.route("/robots.txt")
def robots():
    return Response(ROBOTS_TXT, mimetype="text/plain")


# ---------------------------------------------------------------------------
# Before-request hooks
# ---------------------------------------------------------------------------

@app.before_request
def _security_filters():
    """Block scanners and apply rate limits."""
    path = request.path.lower()

    if path in _BLOCKED_EXACT:
        abort(404)
    for blocked in _BLOCKED_PATHS:
        if path.startswith(blocked):
            abort(404)

    from web.security import is_blocked_user_agent, EXTENDED_BLOCKED_PATHS
    for blocked in EXTENDED_BLOCKED_PATHS:
        if path.startswith(blocked):
            abort(404)
    if not (path == "/health" or path.startswith("/cron")):
        ua = request.headers.get("User-Agent", "")
        if is_blocked_user_agent(ua):
            abort(403)

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip:
        ip = ip.split(",")[0].strip()

    if path == "/search" and _is_rate_limited(ip, RATE_LIMIT_MAX_LOOKUP):
        return '<div class="error">Rate limit exceeded. Please wait a minute.</div>', 429

    if request.method == "POST":
        if path == "/analyze" and _is_rate_limited(ip, RATE_LIMIT_MAX_ANALYZE):
            return '<div class="error">Rate limit exceeded. Please wait a minute.</div>', 429
        if path == "/validate" and _is_rate_limited(ip, RATE_LIMIT_MAX_VALIDATE):
            return '<div class="error">Rate limit exceeded. Please wait a minute.</div>', 429
        if path == "/analyze-plans" and _is_rate_limited(ip, RATE_LIMIT_MAX_ANALYZE_PLANS):
            return '<div class="error">Rate limit exceeded. Please wait a minute.</div>', 429
        if path == "/lookup" and _is_rate_limited(ip, RATE_LIMIT_MAX_LOOKUP):
            return '<div class="error">Rate limit exceeded. Please wait a minute.</div>', 429
        if path == "/ask" and _is_rate_limited(ip, RATE_LIMIT_MAX_ASK):
            return '<div class="error">Rate limit exceeded. Please wait a minute.</div>', 429
        if path == "/auth/send-link" and _is_rate_limited(ip, RATE_LIMIT_MAX_AUTH):
            return render_template(
                "auth_login.html",
                message="Too many requests. Please wait a minute.",
                message_type="error",
            ), 429


def _is_cron_worker():
    """Check CRON_WORKER env var at request time (testable via monkeypatch.setenv)."""
    return os.environ.get("CRON_WORKER", "").lower() in ("1", "true", "yes")


@app.before_request
def _cron_guard():
    """Route isolation: cron workers only serve /cron/* + /health."""
    path = request.path
    if _is_cron_worker():
        if not (path.startswith("/cron") or path == "/health"):
            abort(404)
    else:
        if path.startswith("/cron") and path != "/cron/status" and request.method == "POST":
            abort(404)


@app.before_request
def _load_user():
    """Load current user from session into g for templates and routes."""
    g.user = None
    g.is_impersonating = False
    user_id = session.get("user_id")
    if user_id:
        from web.auth import get_user_by_id
        g.user = get_user_by_id(user_id)
        g.is_impersonating = bool(session.get("impersonating"))


@app.before_request
def _daily_limit_check():
    """Enforce daily request limits (authenticated: 200, anon: 50)."""
    if app.config.get("TESTING"):
        return
    path = request.path
    if (path.startswith("/static") or path == "/health" or
        path.startswith("/cron") or path == "/api/activity/track" or
        path.startswith("/auth") or path == "/robots.txt" or
            path == "/favicon.ico"):
        return

    from web.security import check_daily_limit
    user_id = g.user["user_id"] if getattr(g, 'user', None) else None
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip:
        ip = ip.split(",")[0].strip()

    if check_daily_limit(user_id, ip):
        return '<div class="error">Daily request limit exceeded. Please try again tomorrow.</div>', 429


@app.before_request
def _start_timer():
    """Record request start time for slow-request detection."""
    g._request_start = time.monotonic()


@app.before_request
def _inject_violation_context():
    """Inject violation onboarding context for search pages."""
    g.violation_context = request.args.get("context") == "violation"


# ---------------------------------------------------------------------------
# After-request hooks
# ---------------------------------------------------------------------------

_LOG_PATHS = {"/ask", "/analyze", "/validate", "/analyze-plans", "/lookup", "/brief",
              "/portfolio", "/account", "/auth/send-link", "/auth/verify",
              "/watch/add", "/watch/remove", "/watch/tags", "/feedback/submit",
              "/admin/send-invite", "/account/primary-address",
              "/account/primary-address/clear", "/search"}


@app.after_request
def _log_activity(response):
    """Log meaningful user actions to activity_log. Fire-and-forget."""
    path = request.path
    if path not in _LOG_PATHS and not path.startswith("/auth/verify/"):
        return response
    if response.status_code >= 400 and response.status_code != 403:
        return response
    try:
        from web.activity import log_activity
        user_id = g.user["user_id"] if g.user else None
        action_map = {
            "/ask": "search",
            "/analyze": "analyze",
            "/validate": "validate",
            "/analyze-plans": "analyze_plans",
            "/lookup": "lookup",
            "/brief": "brief_view",
            "/account": "account_view",
            "/auth/send-link": "login_request",
            "/watch/add": "watch_add",
            "/watch/remove": "watch_remove",
            "/watch/tags": "watch_tags_update",
            "/feedback/submit": "feedback_submit",
            "/admin/send-invite": "admin_invite",
            "/account/primary-address": "primary_address_set",
            "/account/primary-address/clear": "primary_address_clear",
            "/search": "public_search",
        }
        action = action_map.get(path, "page_view")
        if path.startswith("/auth/verify/"):
            action = "login_verify"
        detail = None
        if action == "search":
            q = request.form.get("q") or request.args.get("q", "")
            if q:
                detail = {"query": q[:200]}
        elif action in ("analyze", "validate", "lookup"):
            detail = {"method": request.method}
        log_activity(user_id, action, detail=detail, path=path,
                     ip=request.remote_addr)
    except Exception:
        pass
    return response


@app.after_request
def _slow_request_log(response):
    """Log requests that take more than 5 seconds."""
    start = getattr(g, '_request_start', None)
    if start is not None:
        elapsed = time.monotonic() - start
        if elapsed > 5.0:
            logging.getLogger("slow_request").warning(
                "SLOW REQUEST: %.1fs %s %s -> %d",
                elapsed, request.method, request.path, response.status_code,
            )
    return response


@app.after_request
def _security_headers(response):
    """Add security headers to every response."""
    from web.security import add_security_headers
    return add_security_headers(response)


# ---------------------------------------------------------------------------
# Health check (stays in app.py — infrastructure route)
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    """Health check endpoint — database connectivity and table list."""
    from src.db import get_connection, BACKEND, DATABASE_URL
    full = request.args.get("full") == "1"
    info = {"status": "ok", "backend": BACKEND, "has_db_url": bool(DATABASE_URL), "tables": {}}
    try:
        conn = get_connection()
        try:
            if BACKEND == "postgres":
                conn.autocommit = True
                with conn.cursor() as cur:
                    if full:
                        cur.execute("SET statement_timeout = '30s'")
                        cur.execute(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public' ORDER BY table_name"
                        )
                        for (table_name,) in cur.fetchall():
                            try:
                                cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                                info["tables"][table_name] = cur.fetchone()[0]
                            except Exception:
                                info["tables"][table_name] = "error"
                    else:
                        cur.execute("""
                            SELECT relname, GREATEST(reltuples::BIGINT, 0)
                            FROM pg_class
                            WHERE relnamespace = 'public'::regnamespace
                              AND relkind = 'r'
                            ORDER BY relname
                        """)
                        for table_name, est_rows in cur.fetchall():
                            info["tables"][table_name] = est_rows
                        info["row_counts"] = "estimated"
            else:
                tables = conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main' ORDER BY table_name"
                ).fetchall()
                for (table_name,) in tables:
                    info["tables"][table_name] = conn.execute(
                        f"SELECT COUNT(*) FROM {table_name}"
                    ).fetchone()[0]
            info["db_connected"] = True
            info["table_count"] = len(info["tables"])

            found_tables = set(info["tables"].keys())
            missing = sorted(set(EXPECTED_TABLES) - found_tables)
            if missing:
                info["missing_expected_tables"] = missing
                info["status"] = "degraded"
        finally:
            conn.close()
    except Exception as e:
        info["db_connected"] = False
        info["db_error"] = str(e)
        info["status"] = "degraded"

    return Response(json.dumps(info, indent=2), mimetype="application/json")
