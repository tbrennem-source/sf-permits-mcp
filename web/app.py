"""sfpermits.ai — Amy's permit analysis web UI.

A simple Flask + HTMX app exposing the 5 djarvis permit decision tools:
  - predict_permits
  - estimate_fees
  - estimate_timeline
  - required_documents
  - revision_risk

Plus the plan set validator (EPR compliance checker).
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from datetime import timedelta
from functools import wraps
from flask import Flask, render_template, render_template_string, request, abort, Response, redirect, url_for, session, g, send_file, jsonify, make_response
import markdown

# Configure logging so gunicorn captures warnings from tools
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.tools.predict_permits import predict_permits
from src.tools.estimate_fees import estimate_fees
from src.tools.estimate_timeline import estimate_timeline
from src.tools.required_documents import required_documents
from src.tools.revision_risk import revision_risk
from src.tools.validate_plans import validate_plans
from src.tools.analyze_plans import analyze_plans
from src.tools.context_parser import extract_triggers, enhance_description, reorder_sections
from src.tools.team_lookup import generate_team_profile
from src.tools.permit_lookup import permit_lookup
from src.tools.search_entity import search_entity
from src.tools.knowledge_base import get_knowledge_base
from src.tools.intent_router import classify as classify_intent
from src.tools.search_complaints import search_complaints
from src.tools.search_violations import search_violations

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-key-change-in-prod")
app.permanent_session_lifetime = timedelta(days=30)


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

# Cookie security: Secure (HTTPS-only in prod), HttpOnly (default), SameSite=Lax
_is_prod = os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("BASE_URL", "").startswith("https")
app.config["SESSION_COOKIE_SECURE"] = bool(_is_prod)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# 400 MB max upload for plan set PDFs (site permit addenda can be up to 350 MB)
app.config["MAX_CONTENT_LENGTH"] = 400 * 1024 * 1024

# ---------------------------------------------------------------------------
# White-label / brand config (env-overridable)
# ---------------------------------------------------------------------------
BRAND_CONFIG = {
    "name": os.environ.get("BRAND_NAME", "sfpermits.ai"),
    "persona": os.environ.get("BRAND_PERSONA", "our knowledge base"),
    "answer_header": os.environ.get("BRAND_ANSWER_HEADER", "Here's what I found"),
    "draft_header": os.environ.get("BRAND_DRAFT_HEADER", "Draft reply"),
}


# Knowledge quiz — curated questions from data/knowledge/GAPS.md
QUIZ_QUESTIONS = [
    "Walk me through how you decide whether a project qualifies for OTC vs in-house review.",
    "What's your mental checklist when a new client describes their project? What questions do you ask first?",
    "What are the top 5 reasons building permit applications get rejected or sent back?",
    "How do you estimate timelines for clients? What's the range for a typical residential remodel vs commercial TI vs new construction?",
    "How do you calculate/estimate permit fees for a client before they apply?",
    "What unexpected fees catch clients off guard?",
    "Which agency reviews cause the most delays? Planning? Fire?",
    "For what types of projects do you NOT need Planning review?",
    "How does the OCII routing work in practice? How often do you deal with it?",
    "What are the 5 most common project types you help clients with?",
    "What's the most confusing part of the process for first-time applicants?",
    "Are there any 'gotchas' in the process that aren't well documented?",
    "Can you validate this form selection logic for common permit types?",
    "Can you validate this agency routing for a kitchen remodel?",
    "Is the 11-step in-house review process on sf.gov accurate and complete?",
]


@app.context_processor
def inject_brand():
    """Make BRAND_CONFIG available in all templates."""
    return {"brand": BRAND_CONFIG}


# ---------------------------------------------------------------------------
# Startup migrations (idempotent, run once per deploy)
# ---------------------------------------------------------------------------
def _run_startup_migrations():
    """Run any pending schema migrations on startup. Idempotent."""
    from src.db import BACKEND, get_connection
    if BACKEND != "postgres":
        return  # DuckDB schema is managed by init_user_schema
    try:
        conn = get_connection()
        conn.autocommit = True
        cur = conn.cursor()

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

        # invite_code column (added in invite code feature — safe on fresh DB too)
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
        # Screenshot data column for feedback attachments
        cur.execute("ALTER TABLE feedback ADD COLUMN IF NOT EXISTS screenshot_data TEXT")
        # Primary address columns (added for homeowner personalization)
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
        # Fix inspections.id for auto-increment (needed for nightly upserts)
        # Original migration used INTEGER, but we need SERIAL for auto-increment.
        # Always resync the sequence to MAX(id) in case bulk data was loaded.
        try:
            cur.execute("""
                DO $$
                BEGIN
                    -- Create sequence if it doesn't exist
                    IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE schemaname = 'public' AND sequencename = 'inspections_id_seq') THEN
                        CREATE SEQUENCE inspections_id_seq;
                        ALTER TABLE inspections ALTER COLUMN id SET DEFAULT nextval('inspections_id_seq');
                    END IF;
                    -- Always resync to MAX(id) so nightly inserts don't collide
                    PERFORM setval('inspections_id_seq', COALESCE((SELECT MAX(id) FROM inspections), 0) + 1);
                END
                $$
            """)
        except Exception:
            pass  # Non-fatal if already set up
        # cron_log table (nightly refresh + brief send tracking)
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

        # Plan analysis session tables (image gallery)
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
        # user_id column on sessions (link sessions to users for persistent storage)
        cur.execute("ALTER TABLE plan_analysis_sessions ADD COLUMN IF NOT EXISTS user_id INTEGER")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_plan_sessions_user ON plan_analysis_sessions (user_id)")
        # page_annotations column for spatial annotation overlay data
        cur.execute("ALTER TABLE plan_analysis_sessions ADD COLUMN IF NOT EXISTS page_annotations TEXT")

        # Plan analysis jobs table (async processing + job history)
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

        # Tags column for watch items (client grouping feature)
        cur.execute("ALTER TABLE watch_items ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT ''")

        # Progress tracking columns for multi-stage indicator
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS progress_stage TEXT")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS progress_detail TEXT")

        # Vision usage tracking (timing, tokens, cost)
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS vision_usage_json TEXT")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS gallery_duration_ms INTEGER")

        # Billing tier plumbing (Free/Pro)
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'free'")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS analysis_mode TEXT DEFAULT 'sample'")
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS pages_analyzed INTEGER")

        # Submission stage (preliminary, permit, resubmittal)
        cur.execute("ALTER TABLE plan_analysis_jobs ADD COLUMN IF NOT EXISTS submission_stage TEXT")

        # Phase D1: Close Project — archive flag
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

        # Phase F2: Project Notes — free-text per version group
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

        # Voice & style preferences (macro instructions for AI response tone)
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS voice_style TEXT")

        # Voice calibration — per-scenario style preferences
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

        # Addenda changes table (tracks plan review routing changes nightly)
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

        # ── Admin auto-seed ───────────────────────────────────────
        # If the users table is empty and ADMIN_EMAIL is set, create
        # the admin account automatically so a fresh DB is immediately
        # usable without an invite code.
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

        cur.close()
        conn.close()
        logging.getLogger(__name__).info("Startup migrations complete")
    except Exception as e:
        logging.getLogger(__name__).warning("Startup migration failed (non-fatal): %s", e)


_run_startup_migrations()

# Recover stale background analysis jobs from previous worker restarts
try:
    from web.plan_worker import recover_stale_jobs
    recover_stale_jobs()
except Exception as e:
    logging.getLogger(__name__).warning("Stale job recovery failed (non-fatal): %s", e)


# ---------------------------------------------------------------------------
# Simple in-memory rate limiter (per-IP, resets on deploy — good enough for
# Phase 1 on a single dyno; swap for Redis-backed in Phase 2)
# ---------------------------------------------------------------------------
_rate_buckets: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT_WINDOW = 60        # seconds
RATE_LIMIT_MAX_ANALYZE = 10   # /analyze requests per window
RATE_LIMIT_MAX_VALIDATE = 5   # /validate requests per window (heavier)
RATE_LIMIT_MAX_ANALYZE_PLANS = 3  # /analyze-plans requests per window (vision, costs $)
RATE_LIMIT_MAX_LOOKUP = 15    # /lookup requests per window (lightweight)
RATE_LIMIT_MAX_ASK = 20       # /ask requests per window (conversational search)
RATE_LIMIT_MAX_AUTH = 5       # /auth/send-link requests per window


def _is_rate_limited(ip: str, max_requests: int) -> bool:
    """Return True if ip has exceeded max_requests in the current window."""
    now = time.monotonic()
    bucket = _rate_buckets[ip]
    # Prune old entries
    _rate_buckets[ip] = [t for t in bucket if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_buckets[ip]) >= max_requests:
        return True
    _rate_buckets[ip].append(now)
    return False


# ---------------------------------------------------------------------------
# robots.txt — block ALL crawlers during beta; re-open selectively post-launch
# ---------------------------------------------------------------------------
ROBOTS_TXT = """\
# Beta period — hidden from all crawlers
User-agent: *
Disallow: /
"""


@app.route("/robots.txt")
def robots():
    return Response(ROBOTS_TXT, mimetype="text/plain")


# Block common vulnerability scanner paths early (before 404 processing)
_BLOCKED_PATHS = {
    "/wp-admin", "/wp-login.php", "/wp-content", "/.env", "/.git",
    "/phpmyadmin", "/xmlrpc.php", "/config.php",
    "/actuator", "/.well-known/security.txt",
}
# Exact-match blocked paths (scanners probe these without subpaths)
_BLOCKED_EXACT = {"/admin"}



@app.before_request
def _security_filters():
    """Block scanners and apply rate limits."""
    path = request.path.lower()

    # Block known scanner probes with 404 (don't waste cycles)
    if path in _BLOCKED_EXACT:
        abort(404)
    for blocked in _BLOCKED_PATHS:
        if path.startswith(blocked):
            abort(404)

    # Rate limit POST endpoints
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip:
        ip = ip.split(",")[0].strip()  # First IP in chain

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


# Paths worth logging (skip static, favicon, healthcheck, etc.)
_LOG_PATHS = {"/ask", "/analyze", "/validate", "/analyze-plans", "/lookup", "/brief",
              "/portfolio", "/account", "/auth/send-link", "/auth/verify",
              "/watch/add", "/watch/remove", "/watch/tags", "/feedback/submit",
              "/admin/send-invite", "/account/primary-address",
              "/account/primary-address/clear"}


@app.after_request
def _log_activity(response):
    """Log meaningful user actions to activity_log. Fire-and-forget."""
    path = request.path
    # Only log interesting paths, not static/assets/health
    if path not in _LOG_PATHS and not path.startswith("/auth/verify/"):
        return response
    # Skip failed requests (4xx client errors, except 403 which is interesting)
    if response.status_code >= 400 and response.status_code != 403:
        return response
    try:
        from web.activity import log_activity
        user_id = g.user["user_id"] if g.user else None
        # Map path to action name
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
        }
        action = action_map.get(path, "page_view")
        if path.startswith("/auth/verify/"):
            action = "login_verify"
        # Extract detail based on action
        detail = None
        if action == "search":
            q = request.form.get("q") or request.args.get("q", "")
            if q:
                detail = {"query": q[:200]}
        elif action in ("analyze", "validate", "lookup"):
            # Capture the endpoint was used, not the full form data
            detail = {"method": request.method}
        log_activity(user_id, action, detail=detail, path=path,
                     ip=request.remote_addr)
    except Exception:
        pass  # Never break the response
    return response


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def login_required(f):
    """Redirect to login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user:
            return redirect(url_for("auth_login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Abort 403 if not admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user or not g.user.get("is_admin"):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def run_async(coro):
    """Run an async function synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def md_to_html(text: str) -> str:
    """Convert markdown output from tools to HTML."""
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
    )


# Neighborhood list for the dropdown (from DuckDB top neighborhoods)
NEIGHBORHOODS = [
    "", "Bayview Hunters Point", "Bernal Heights", "Castro/Upper Market",
    "Chinatown", "Crocker Amazon", "Diamond Heights", "Excelsior",
    "Financial District/South Beach", "Glen Park", "Golden Gate Park",
    "Haight Ashbury", "Hayes Valley", "Inner Richmond", "Inner Sunset",
    "Japantown", "Lakeshore", "Lincoln Park", "Lone Mountain/USF",
    "Marina", "McLaren Park", "Mission", "Mission Bay", "Nob Hill",
    "Noe Valley", "North Beach", "Oceanview/Merced/Ingleside",
    "Outer Mission", "Outer Richmond", "Pacific Heights",
    "Portola", "Potrero Hill", "Presidio", "Presidio Heights",
    "Russian Hill", "Seacliff", "South of Market", "Sunset/Parkside",
    "Tenderloin", "Treasure Island", "Twin Peaks",
    "Visitacion Valley", "West of Twin Peaks", "Western Addition",
]


@app.route("/health")
def health():
    """Health check endpoint — database connectivity and table row counts.

    Public (no auth). Used by Claude sessions to verify prod DB state
    without needing Railway CLI or direct database access.
    """
    from src.db import get_connection, BACKEND, DATABASE_URL
    info = {"status": "ok", "backend": BACKEND, "has_db_url": bool(DATABASE_URL), "tables": {}}
    try:
        conn = get_connection()
        try:
            if BACKEND == "postgres":
                conn.autocommit = True
                with conn.cursor() as cur:
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
                tables = conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main' ORDER BY table_name"
                ).fetchall()
                for (table_name,) in tables:
                    info["tables"][table_name] = conn.execute(
                        f"SELECT COUNT(*) FROM {table_name}"
                    ).fetchone()[0]
            info["db_connected"] = True
        finally:
            conn.close()
    except Exception as e:
        info["db_connected"] = False
        info["db_error"] = str(e)
        info["status"] = "degraded"

    import json
    return Response(json.dumps(info, indent=2), mimetype="application/json")


def _resolve_block_lot(street_number: str, street_name: str) -> tuple[str, str] | None:
    """Lightweight lookup: resolve a street address to (block, lot) from permits table."""
    from src.db import query
    from src.tools.permit_lookup import _strip_suffix
    base_name, _suffix = _strip_suffix(street_name)
    nospace_name = base_name.replace(' ', '')
    rows = query(
        "SELECT block, lot FROM permits "
        "WHERE street_number = %s "
        "  AND ("
        "    UPPER(street_name) = UPPER(%s)"
        "    OR UPPER(street_name) = UPPER(%s)"
        "    OR UPPER(COALESCE(street_name, '') || ' ' || COALESCE(street_suffix, '')) = UPPER(%s)"
        "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
        "  ) "
        "  AND block IS NOT NULL AND lot IS NOT NULL "
        "LIMIT 1",
        (street_number, base_name, street_name, street_name, nospace_name),
    )
    if rows:
        return (rows[0][0], rows[0][1])
    return None


@app.route("/")
def index():
    # If logged-in user has a primary address, resolve block/lot for report link
    user_report_url = None
    user_report_address = None
    if g.user and g.user.get("primary_street_number") and g.user.get("primary_street_name"):
        try:
            bl = _resolve_block_lot(g.user["primary_street_number"], g.user["primary_street_name"])
            if bl:
                user_report_url = f"/report/{bl[0]}/{bl[1]}"
                user_report_address = f"{g.user['primary_street_number']} {g.user['primary_street_name']}"
        except Exception:
            pass  # Non-critical — homepage still works

    upload_error = request.args.get("upload_error")

    return render_template(
        "index.html",
        neighborhoods=NEIGHBORHOODS,
        user_report_url=user_report_url,
        user_report_address=user_report_address,
        upload_error=upload_error,
    )


@app.route("/analyze", methods=["POST"])
def analyze():
    """Run all 5 tools on the submitted project and return HTML fragments."""
    # --- Section A: existing fields ---
    description = request.form.get("description", "").strip()
    address = request.form.get("address", "").strip() or None
    neighborhood = request.form.get("neighborhood", "").strip() or None
    cost_str = request.form.get("cost", "").strip()
    sqft_str = request.form.get("sqft", "").strip()

    if not description:
        return '<div class="error">Please enter a project description.</div>', 400

    estimated_cost = float(cost_str) if cost_str else None
    square_footage = float(sqft_str) if sqft_str else None

    # --- Section B: personalization fields ---
    priorities_raw = request.form.get("priorities", "").strip()
    priorities = [p for p in priorities_raw.split(",") if p]
    target_date = request.form.get("target_date", "").strip() or None
    contractor_name = request.form.get("contractor_name", "").strip() or None
    architect_name = request.form.get("architect_name", "").strip() or None
    consultant_name = request.form.get("consultant_name", "").strip() or None
    experience_level = request.form.get("experience_level", "unspecified").strip()
    additional_context = request.form.get("additional_context", "").strip() or None

    # Extract keyword triggers from description + additional context
    combined_text = description
    if additional_context:
        combined_text += " " + additional_context
    context_triggers = extract_triggers(combined_text)

    # Enhance description with additional context
    enriched_description = enhance_description(
        description, additional_context, context_triggers
    )

    # Determine section ordering from priorities
    section_order = reorder_sections(priorities) if priorities else None

    results = {}

    # 1. Predict Permits (primary — drives inputs for other tools)
    try:
        pred_result = run_async(predict_permits(
            project_description=enriched_description,
            address=address,
            estimated_cost=estimated_cost,
            square_footage=square_footage,
        ))
        results["predict"] = md_to_html(pred_result)
    except Exception as e:
        results["predict"] = f'<div class="error">Prediction error: {e}</div>'
        pred_result = ""

    # Parse prediction output for downstream tool inputs
    permit_type = "alterations"  # default
    review_path = "in_house"
    agency_routing = []
    project_types = []
    permit_forms = ["Form 3/8"]

    if pred_result:
        text = pred_result.lower()
        if "new construction" in text or "form 1" in text:
            permit_type = "new_construction"
            permit_forms = ["Form 1/2"]
        if "otc" in text:
            review_path = "otc"

        # Extract agencies
        for agency in ["Planning", "SFFD (Fire)", "DPH (Public Health)",
                       "DPW (Public Works)", "DBI (Building)",
                       "DBI Mechanical/Electrical"]:
            if agency.lower() in text:
                agency_routing.append(agency)

        # Extract project types
        for ptype in ["restaurant", "adu", "commercial_ti", "historic",
                      "seismic", "solar", "demolition", "change_of_use",
                      "new_construction"]:
            if ptype.replace("_", " ") in text or ptype in text:
                project_types.append(ptype)

    project_type = project_types[0] if project_types else "general_alteration"

    # Derive triggers from project types + context triggers
    triggers = []
    if "restaurant" in project_types or "restaurant" in context_triggers:
        triggers.extend(["dph_food_facility", "fire_suppression", "grease_interceptor"])
    if "historic" in project_types or "historic" in context_triggers:
        triggers.append("historic_preservation")
    if "seismic" in project_types or "seismic" in context_triggers:
        triggers.append("seismic_retrofit")
    if estimated_cost and estimated_cost > 195358:
        triggers.append("ada_path_of_travel")
    if "commercial_ti" in project_types or "green_building" in context_triggers:
        triggers.append("title24")
    if "adu" in context_triggers:
        triggers.append("adu_specific")
    if "fire" in context_triggers:
        triggers.append("fire_suppression")

    # 2. Estimate Fees
    if estimated_cost:
        try:
            fees_result = run_async(estimate_fees(
                permit_type=permit_type,
                estimated_construction_cost=estimated_cost,
                square_footage=square_footage,
                neighborhood=neighborhood,
                project_type=project_type,
            ))
            results["fees"] = md_to_html(fees_result)
        except Exception as e:
            results["fees"] = f'<div class="error">Fee estimation error: {e}</div>'
    else:
        results["fees"] = '<div class="info">Enter an estimated cost to calculate fees.</div>'

    # 3. Estimate Timeline
    try:
        timeline_result = run_async(estimate_timeline(
            permit_type=permit_type,
            neighborhood=neighborhood,
            review_path=review_path,
            estimated_cost=estimated_cost,
            triggers=triggers or None,
        ))
        # Add target date buffer calculation if provided
        if target_date:
            timeline_result = _add_target_date_context(timeline_result, target_date)
        results["timeline"] = md_to_html(timeline_result)
    except Exception as e:
        results["timeline"] = f'<div class="error">Timeline error: {e}</div>'

    # 4. Required Documents
    try:
        docs_result = run_async(required_documents(
            permit_forms=permit_forms,
            review_path=review_path,
            agency_routing=agency_routing or None,
            project_type=project_type,
            triggers=triggers or None,
        ))
        results["docs"] = md_to_html(docs_result)
    except Exception as e:
        results["docs"] = f'<div class="error">Documents error: {e}</div>'

    # 5. Revision Risk
    try:
        risk_result = run_async(revision_risk(
            permit_type=permit_type,
            neighborhood=neighborhood,
            project_type=project_type,
            review_path=review_path,
        ))
        results["risk"] = md_to_html(risk_result)
    except Exception as e:
        results["risk"] = f'<div class="error">Risk assessment error: {e}</div>'

    # 6. Team Lookup (if any names provided)
    team_md = ""
    if contractor_name or architect_name or consultant_name:
        try:
            team_md = generate_team_profile(
                contractor=contractor_name,
                architect=architect_name,
                consultant=consultant_name,
            )
            if team_md:
                results["team"] = md_to_html(team_md)
        except Exception as e:
            results["team"] = f'<div class="error">Team lookup error: {e}</div>'

    return render_template(
        "results.html",
        results=results,
        section_order=section_order,
        experience_level=experience_level,
        has_team=bool(team_md),
    )


def _add_target_date_context(timeline_md: str, target_date: str) -> str:
    """Add target date buffer/deficit info to timeline output."""
    import re
    from datetime import date, timedelta

    try:
        target = date.fromisoformat(target_date)
    except ValueError:
        return timeline_md

    today = date.today()

    # Extract the p50 (typical) days from the timeline output
    match = re.search(r"(?:typical|p50)[^0-9]*(\d+)\s*days", timeline_md, re.IGNORECASE)
    if not match:
        # Try "estimated.*weeks" pattern
        match = re.search(r"(\d+)\s*weeks?", timeline_md, re.IGNORECASE)
        if match:
            est_days = int(match.group(1)) * 7
        else:
            return timeline_md
    else:
        est_days = int(match.group(1))

    est_permit_date = today + timedelta(days=est_days)
    buffer_days = (target - est_permit_date).days

    if buffer_days >= 14:
        note = (
            f"\n\n**Target Date Analysis:** Your target of {target_date} "
            f"gives you approximately **{buffer_days} days of buffer** "
            f"after the estimated permit issuance ({est_permit_date.isoformat()}). "
            f"You're in good shape."
        )
    elif buffer_days >= 0:
        note = (
            f"\n\n**Target Date Analysis:** Your target of {target_date} "
            f"is **tight** — only {buffer_days} days after the estimated "
            f"permit issuance ({est_permit_date.isoformat()}). "
            f"Consider filing as soon as possible to build buffer."
        )
    else:
        note = (
            f"\n\n**&#9888; Target Date At Risk:** Your target of {target_date} "
            f"is **{abs(buffer_days)} days before** the typical permit issuance "
            f"date ({est_permit_date.isoformat()}). Consider: "
            f"filing immediately, using OTC pathway if eligible, "
            f"or hiring a land use consultant to compress the timeline."
        )

    return timeline_md + note


@app.route("/validate", methods=["POST"])
def validate():
    """DEPRECATED: Kept for backwards compatibility. Use /analyze-plans instead.

    The Validate Plan Set section has been merged into Analyze Plans.
    This route still works but logs a deprecation notice.
    """
    logging.info("[validate] DEPRECATED route called — use /analyze-plans with quick_check=on instead")
    uploaded = request.files.get("planfile")
    if not uploaded or not uploaded.filename:
        return '<div class="error">Please select a PDF file to upload.</div>', 400

    filename = uploaded.filename
    if not filename.lower().endswith(".pdf"):
        return '<div class="error">Only PDF files are supported.</div>', 400

    is_addendum = request.form.get("is_addendum") == "on"
    enable_vision = request.form.get("enable_vision") == "on"

    try:
        pdf_bytes = uploaded.read()
    except Exception as e:
        return f'<div class="error">Error reading file: {e}</div>', 400

    if len(pdf_bytes) == 0:
        return '<div class="error">The uploaded file is empty.</div>', 400

    try:
        result_md = run_async(validate_plans(
            pdf_bytes=pdf_bytes,
            filename=filename,
            is_site_permit_addendum=is_addendum,
            enable_vision=enable_vision,
        ))
        result_html = md_to_html(result_md)
    except Exception as e:
        logging.exception(f"[validate] Error: {e}")
        result_html = f'<div class="error">Validation error: {e}</div>'

    return render_template(
        "validate_results.html",
        result=result_html,
        filename=filename,
        filesize_mb=round(len(pdf_bytes) / (1024 * 1024), 1),
    )


@app.route("/analyze-plans", methods=["POST"])
def analyze_plans_route():
    """Upload a PDF plan set for full AI-powered analysis.

    Small files (≤ threshold) are processed synchronously.
    Large files (> threshold) are queued for async background processing.
    """
    # Check if this is an HTMX request (returns fragment) or direct POST (needs full page)
    is_htmx = request.headers.get("HX-Request") == "true"

    def _upload_error(msg: str, code: int = 400):
        """Return styled error for HTMX or redirect for direct POST."""
        if is_htmx:
            return f'<div class="error">{msg}</div>', code
        from urllib.parse import quote
        return redirect(f"/?upload_error={quote(msg)}#analyze-plans")

    uploaded = request.files.get("planfile")
    if not uploaded or not uploaded.filename:
        return _upload_error("Please select a PDF file to upload.")

    filename = uploaded.filename
    if not filename.lower().endswith(".pdf"):
        return _upload_error("Only PDF files are supported.")

    project_description = request.form.get("project_description", "").strip() or None
    permit_type = request.form.get("permit_type", "").strip() or None
    quick_check = request.form.get("quick_check") == "on"
    is_addendum = request.form.get("is_addendum") == "on"
    property_address = request.form.get("property_address", "").strip() or None
    permit_number_input = request.form.get("permit_number", "").strip() or None
    submission_stage = request.form.get("submission_stage", "").strip() or None
    # analysis_mode: 'compliance', 'sample', or 'full' (from form hidden field)
    requested_mode = request.form.get("analysis_mode", "sample").strip()
    # Legacy support: analyze_all_pages checkbox
    analyze_all_pages = request.form.get("analyze_all_pages") == "on"
    if analyze_all_pages and requested_mode == "sample":
        requested_mode = "full"

    try:
        pdf_bytes = uploaded.read()
    except Exception as e:
        return _upload_error(f"Error reading file: {e}")

    if len(pdf_bytes) == 0:
        return _upload_error("The uploaded file is empty.")

    # VALIDATION: Check file size
    size_mb = len(pdf_bytes) / (1024 * 1024)
    max_size = 350 if is_addendum else 400
    if size_mb > max_size:
        return _upload_error(f"File too large: {size_mb:.1f} MB. Maximum is {max_size} MB.", 413)

    user_id = session.get("user_id")
    mode = "quick-check" if quick_check else "full-analysis"
    logging.info(f"[analyze-plans] Processing PDF: {filename} ({size_mb:.2f} MB, mode={mode})")

    # ── Full Analysis always uses background worker (vision API calls take minutes) ──
    if not quick_check:
        from web.auth import get_user_by_id
        from web.billing import resolve_analysis_mode
        from web.plan_jobs import create_job
        from web.plan_worker import submit_job

        user = get_user_by_id(user_id) if user_id else None
        analysis_mode, was_downgraded = resolve_analysis_mode(user, requested_mode)

        job_id = create_job(
            user_id=user_id,
            filename=filename,
            file_size_mb=size_mb,
            pdf_data=pdf_bytes,
            property_address=property_address,
            permit_number=permit_number_input,
            project_description=project_description,
            permit_type=permit_type,
            is_addendum=is_addendum,
            quick_check=False,
            is_async=True,
            submission_stage=submission_stage,
            analysis_mode=analysis_mode,
        )
        submit_job(job_id)

        logging.info(f"[analyze-plans] Async job {job_id} submitted for {filename} (mode={analysis_mode}, downgraded={was_downgraded})")
        # HTMX gets a fragment; direct POST gets full page with nav/theme
        if is_htmx:
            return render_template(
                "analyze_plans_processing.html",
                job_id=job_id,
                filename=filename,
                filesize_mb=round(size_mb, 1),
                user_email=_get_user_email(user_id),
                mode_downgraded=was_downgraded,
                analysis_mode=analysis_mode,
            )
        else:
            return render_template(
                "plan_processing_page.html",
                job_id=job_id,
                filename=filename,
                filesize_mb=round(size_mb, 1),
                user_email=_get_user_email(user_id),
                mode_downgraded=was_downgraded,
                analysis_mode=analysis_mode,
            )

    # ── Quick Check mode: metadata-only via validate_plans ──
    if quick_check:
        from datetime import datetime, timezone
        result_md = None
        qc_started_at = datetime.now(timezone.utc)
        try:
            result_md = run_async(validate_plans(
                pdf_bytes=pdf_bytes,
                filename=filename,
                is_site_permit_addendum=is_addendum,
                enable_vision=False,
            ))
            result_html = md_to_html(result_md)
        except Exception as e:
            logging.exception(f"[analyze-plans] Quick-check error for '{filename}': {e}")
            import traceback
            result_html = f'''
                <div class="error" style="text-align: left; max-width: 900px; margin: 20px auto;">
                    <p style="font-weight: 600; color: #d32f2f;">Quick Check Error</p>
                    <p><strong>Error:</strong> {str(e)}</p>
                    <details style="margin-top: 12px;">
                        <summary style="cursor: pointer; color: #1976d2;">Technical Details</summary>
                        <pre style="background: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 0.85rem; margin-top: 8px;">{traceback.format_exc()}</pre>
                    </details>
                </div>
            '''
        qc_completed_at = datetime.now(timezone.utc)

        # Track job for history (no PDF stored for quick check)
        try:
            from web.plan_jobs import create_job, update_job_status
            job_id = create_job(
                user_id=user_id, filename=filename, file_size_mb=size_mb,
                property_address=property_address, permit_number=permit_number_input,
                quick_check=True, is_async=False,
            )
            update_job_status(
                job_id, "completed",
                report_md=result_md,
                started_at=qc_started_at,
                completed_at=qc_completed_at,
            )
        except Exception:
            pass  # Job tracking is non-fatal

        # HTMX requests get a fragment; direct POSTs get the full page wrapper
        template = "analyze_plans_results.html" if is_htmx else "plan_results_page.html"
        return render_template(
            template,
            result=result_html,
            filename=filename,
            filesize_mb=round(size_mb, 1),
            session_id=None,
            page_count=0,
            extractions_json="{}",
            annotations_json="[]",
            quick_check=True,
        )

    # Note: Full Analysis always routes to async worker above, so this point
    # is only reached if quick_check somehow falls through (shouldn't happen).
    return _upload_error("Unexpected routing error. Please try again.", 500)


def _parse_address(address: str) -> tuple:
    """Split '123 Main St' into ('123', 'Main St'). Best-effort."""
    if not address:
        return ("", "")
    parts = address.strip().split(None, 1)
    if len(parts) == 2 and parts[0][0].isdigit():
        return (parts[0], parts[1])
    return ("", address)


def _get_user_email(user_id: int | None) -> str | None:
    """Get user email for display, returns None if not logged in."""
    if not user_id:
        return None
    try:
        from web.auth import get_user_by_id
        user = get_user_by_id(user_id)
        return user.get("email") if user else None
    except Exception:
        return None


@app.route("/plan-images/<session_id>/<int:page_number>")
def plan_image(session_id, page_number):
    """Serve a rendered plan page image as PNG."""
    import base64
    from web.plan_images import get_page_image

    b64_data = get_page_image(session_id, page_number)
    if not b64_data:
        abort(404)

    image_bytes = base64.b64decode(b64_data)
    return Response(
        image_bytes,
        mimetype="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.route("/plan-session/<session_id>")
def plan_session(session_id):
    """Return plan analysis session metadata as JSON."""
    import json
    from web.plan_images import get_session

    session = get_session(session_id)
    if not session:
        abort(404)

    # Serialize datetime for JSON
    if session.get("created_at"):
        session["created_at"] = session["created_at"].isoformat()

    return Response(json.dumps(session), mimetype="application/json")


@app.route("/plan-images/<session_id>/download-all")
def download_all_pages(session_id):
    """Download all plan pages as a ZIP file."""
    import base64
    import io
    import zipfile
    from web.plan_images import get_session, get_page_image

    session = get_session(session_id)
    if not session:
        abort(404)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for page_num in range(session['page_count']):
            b64_data = get_page_image(session_id, page_num)
            if b64_data:
                image_bytes = base64.b64decode(b64_data)
                zip_file.writestr(f"page-{page_num + 1}.png", image_bytes)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{session['filename']}-pages.zip"
    )


@app.route("/plan-analysis/<session_id>/email", methods=["POST"])
def email_analysis(session_id):
    """Email plan analysis to specified recipient."""
    from web.plan_images import get_session
    from web.email_brief import send_brief_email

    data = request.get_json()
    recipient = data.get('recipient')
    message = data.get('message', '')
    context = data.get('context', 'full')

    session = get_session(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'Session not found'})

    # Build email body
    if context == 'full':
        subject = f"Plan Analysis: {session['filename']}"
        html_body = f"""
<h2>Plan Analysis: {session['filename']}</h2>
<p>{message}</p>
<p>Analysis for <strong>{session['filename']}</strong> ({session['page_count']} pages)</p>
<p><a href="{request.url_root}plan-session/{session_id}">View online</a></p>
"""
    elif context.startswith('comparison-'):
        parts = context.split('-')
        left, right = parts[1], parts[2]
        subject = f"Plan Comparison: Pages {int(left)+1} and {int(right)+1}"
        html_body = f"""
<h2>Plan Comparison</h2>
<p>{message}</p>
<p>Comparison of pages {int(left)+1} and {int(right)+1} from <strong>{session['filename']}</strong></p>
"""
    else:
        subject = f"Plan Analysis: {session['filename']}"
        html_body = f"<p>{message}</p>"

    try:
        send_brief_email(
            to_email=recipient,
            subject=subject,
            html_body=html_body,
        )
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Email send failed: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route("/plan-jobs/<job_id>/status")
def plan_job_status(job_id):
    """HTMX polling endpoint for async job status."""
    from web.plan_jobs import get_job

    job = get_job(job_id)
    if not job:
        abort(404)

    if job["status"] == "completed":
        # Use HX-Redirect so htmx navigates the browser to results
        # (inline <script> tags are not executed in htmx-swapped content)
        resp = make_response("", 200)
        resp.headers["HX-Redirect"] = f"/plan-jobs/{job['job_id']}/results"
        return resp
    elif job["status"] == "failed":
        return render_template("analyze_plans_failed.html", job=job)
    elif job["status"] == "stale":
        return render_template("analyze_plans_stale.html", job=job)
    elif job["status"] == "cancelled":
        return """
        <div id="job-status-poll" style="text-align:center;">
            <div style="font-size:2rem; margin-bottom:12px;">&#10060;</div>
            <div style="font-size:1rem; font-weight:600; color:var(--text, #fff); margin-bottom:8px;">
                Analysis Cancelled
            </div>
            <div style="font-size:0.85rem; color:var(--text-muted, #999); margin-bottom:16px;">
                The analysis was cancelled.
            </div>
            <a href="/#section-analyze-plans" style="color:var(--accent); font-size:0.9rem;">
                &larr; Start New Analysis
            </a>
        </div>
        """
    else:
        # Compute elapsed time for display in polling UI
        elapsed_s = None
        if job.get("started_at"):
            from datetime import datetime, timezone
            started = job["started_at"]
            if hasattr(started, "tzinfo") and started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            elapsed_s = int((datetime.now(timezone.utc) - started).total_seconds())
        return render_template("analyze_plans_polling.html", job=job, elapsed_s=elapsed_s)


@app.route("/plan-jobs/<job_id>/cancel", methods=["POST"])
def cancel_plan_job(job_id):
    """Cancel a running async plan analysis job."""
    from web.plan_jobs import cancel_job

    user_id = g.user["id"] if g.user else None
    if user_id is None:
        abort(403)

    success = cancel_job(job_id, user_id)
    if not success:
        abort(404)

    # Return an HTMX fragment that replaces the polling div
    return """
    <div id="job-status-poll" style="text-align:center;">
        <div style="font-size:2rem; margin-bottom:12px;">&#10060;</div>
        <div style="font-size:1rem; font-weight:600; color:var(--text, #fff); margin-bottom:8px;">
            Analysis Cancelled
        </div>
        <div style="font-size:0.85rem; color:var(--text-muted, #999); margin-bottom:16px;">
            The analysis has been cancelled. You can start a new one anytime.
        </div>
        <a href="/#section-analyze-plans" style="color:var(--accent); font-size:0.9rem;">
            &larr; Try Again
        </a>
    </div>
    """


@app.route("/plan-jobs/<job_id>/results")
def plan_job_results(job_id):
    """View completed analysis results (async or quick-check)."""
    from web.plan_jobs import get_job, find_previous_analyses
    from web.plan_images import get_session

    job = get_job(job_id)
    if not job or job["status"] != "completed":
        abort(404)

    # Quick Check jobs have report_md but no session_id (no gallery)
    if not job["session_id"]:
        if not job.get("report_md"):
            abort(404)
        result_html = md_to_html(job["report_md"])
        return render_template(
            "plan_results_page.html",
            result=result_html,
            filename=job["filename"],
            filesize_mb=round(job["file_size_mb"], 1),
            session_id=None,
            page_count=0,
            extractions_json="{}",
            annotations_json="[]",
            quick_check=job["quick_check"],
        )

    session_data = get_session(job["session_id"])
    if not session_data:
        abort(404)

    result_html = md_to_html(job["report_md"]) if job["report_md"] else ""

    # Format extractions for JavaScript
    page_extractions = session_data.get("page_extractions", [])
    extractions_json = json.dumps({
        pe.get("page_number", i + 1) - 1: pe
        for i, pe in enumerate(page_extractions)
    }) if page_extractions else "{}"

    page_annotations = session_data.get("page_annotations", [])
    annotations_json = json.dumps(page_annotations)

    # Parse vision usage stats for display
    vision_stats = None
    raw_usage = job.get("vision_usage_json")
    if raw_usage:
        try:
            vision_stats = json.loads(raw_usage) if isinstance(raw_usage, str) else raw_usage
        except Exception:
            pass

    # Find previous analyses for same address/permit (revision tracking)
    previous_analyses = []
    try:
        previous_analyses = find_previous_analyses(
            job_id=job_id,
            property_address=job.get("property_address"),
            permit_number=job.get("permit_number"),
            user_id=job.get("user_id"),
        )
    except Exception:
        logging.debug("Previous analyses lookup failed", exc_info=True)

    return render_template(
        "plan_results_page.html",
        result=result_html,
        filename=session_data["filename"],
        filesize_mb=round(job["file_size_mb"], 1),
        session_id=job["session_id"],
        page_count=session_data["page_count"],
        extractions=page_extractions,
        extractions_json=extractions_json,
        annotations_json=annotations_json,
        annotation_count=len(page_annotations) if page_annotations else 0,
        quick_check=job["quick_check"],
        analysis_mode=job.get("analysis_mode", "sample"),
        property_address=job.get("property_address"),
        street_number=_parse_address(job.get("property_address", ""))[0],
        street_name=_parse_address(job.get("property_address", ""))[1],
        vision_stats=vision_stats,
        gallery_duration_ms=job.get("gallery_duration_ms"),
        previous_analyses=previous_analyses,
    )


def _normalize_address_for_grouping(addr: str) -> str:
    """Normalize address for project grouping."""
    if not addr:
        return ""
    addr = addr.upper().strip()
    # Strip unit/apt FIRST (before suffix stripping, since unit comes after street type)
    addr = re.sub(r'\s*(UNIT|APT|#|SUITE|STE)\s*\S*$', '', addr)
    addr = re.sub(r'\s+', ' ', addr).strip()
    # Strip common street-type suffixes
    for suffix in [" STREET", " ST", " AVENUE", " AVE", " BOULEVARD", " BLVD",
                   " DRIVE", " DR", " ROAD", " RD", " LANE", " LN",
                   " COURT", " CT", " PLACE", " PL", " WAY"]:
        if addr.endswith(suffix):
            addr = addr[:-len(suffix)]
            break
    return addr.strip()


def _normalize_filename_for_grouping(name: str) -> str:
    """Normalize filename for project grouping - strip versions, dates, extensions."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove extension
    name = re.sub(r'\.pdf$', '', name, flags=re.IGNORECASE)
    # Strip version suffixes: -v2, _v3, -rev2, _final, -FINAL, (1), _copy
    name = re.sub(r'[-_]?(v\d+|rev\d+|final|copy|draft)$', '', name, flags=re.IGNORECASE)
    # Strip trailing parens: (1), (2)
    name = re.sub(r'\s*\(\d+\)$', '', name)
    # Strip date suffixes: -251114, -2025-02-20, _20250220
    name = re.sub(r'[-_]?\d{6,8}$', '', name)
    name = re.sub(r'[-_]?\d{4}-\d{2}-\d{2}$', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def group_jobs_by_project(jobs: list[dict]) -> list[dict]:
    """Group jobs by normalized property_address or filename.

    Two-pass approach: first groups by address or filename, then merges
    filename-only groups into address groups when they share the same
    normalized filename (same PDF analyzed with and without vision).

    Returns list of dicts: {"key": str, "display_name": str, "jobs": list,
    "count": int, "latest_status": str, "date_range": str}
    """
    from collections import OrderedDict
    groups: OrderedDict[str, dict] = OrderedDict()

    # Track which normalized filenames map to which address groups
    filename_to_address_key: dict[str, str] = {}

    for job in jobs:
        # Try address first, then filename
        if job.get("property_address"):
            key = _normalize_address_for_grouping(job["property_address"])
            display = job["property_address"]
            # Remember that this filename belongs to an address group
            norm_fn = _normalize_filename_for_grouping(job["filename"])
            if norm_fn:
                filename_to_address_key[norm_fn] = key
        else:
            key = _normalize_filename_for_grouping(job["filename"])
            display = job["filename"]

        if not key:
            key = job["filename"]
            display = job["filename"]

        if key not in groups:
            groups[key] = {"key": key, "display_name": display, "jobs": [], "count": 0}
        groups[key]["jobs"].append(job)
        groups[key]["count"] += 1

    # Pass 2: merge filename-only groups into address groups for the same file
    keys_to_remove = []
    for key, grp in list(groups.items()):
        # Skip groups that are already address-based
        if key in filename_to_address_key.values():
            continue
        # Check if this filename key maps to an address group
        if key in filename_to_address_key:
            addr_key = filename_to_address_key[key]
            if addr_key in groups and addr_key != key:
                groups[addr_key]["jobs"].extend(grp["jobs"])
                groups[addr_key]["count"] += grp["count"]
                keys_to_remove.append(key)

    for key in keys_to_remove:
        del groups[key]

    # Sort groups by most recent job
    result = list(groups.values())
    for g in result:
        g["jobs"].sort(key=lambda j: j.get("created_at") or "", reverse=True)
        g["latest_status"] = g["jobs"][0].get("status", "unknown")
        # Date range (convert UTC to Pacific)
        dates = [j["created_at"] for j in g["jobs"] if j.get("created_at")]
        if dates:
            oldest = _to_pst_filter(min(dates))
            newest = _to_pst_filter(max(dates))
            if hasattr(oldest, 'strftime'):
                g["date_range"] = f"{oldest.strftime('%b %d')} – {newest.strftime('%b %d, %Y')}"
            else:
                g["date_range"] = ""
        else:
            g["date_range"] = ""

        # Add version numbers
        for i, job in enumerate(reversed(g["jobs"])):
            job["_version_num"] = i + 1
            job["_version_total"] = g["count"]

    return result


@app.route("/account/analyses")
def analysis_history():
    """View past plan analyses for logged-in user."""
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth_login"))

    from web.plan_jobs import get_user_jobs, search_jobs, get_analysis_stats
    from web.plan_notes import get_project_notes

    search_q = request.args.get("q", "").strip()
    sort_by = request.args.get("sort", "newest")
    if sort_by not in ("newest", "oldest", "address", "filename", "status"):
        sort_by = "newest"

    group_mode = request.args.get("group", "").strip()
    if group_mode not in ("project", ""):
        group_mode = ""

    if search_q:
        jobs = search_jobs(user_id, search_q, limit=50)
    else:
        jobs = get_user_jobs(user_id, limit=50, order_by=sort_by)

    # Compute project groups (always computed so flat view can show "1 of N")
    groups = group_jobs_by_project(jobs) if jobs else []

    # Phase F1: stats banner
    stats = get_analysis_stats(user_id)

    # Phase F2: attach project notes to each group (keyed by version_group)
    for g in groups:
        vg = None
        for j in g.get("jobs", []):
            vg = j.get("version_group")
            if vg:
                break
        g["_notes"] = get_project_notes(user_id, vg) if vg else ""
        g["_version_group"] = vg or ""

    return render_template(
        "analysis_history.html",
        jobs=jobs,
        groups=groups,
        group_mode=group_mode,
        search_q=search_q,
        sort_by=sort_by,
        stats=stats,
    )


@app.route("/account/analyses/compare")
def compare_analyses():
    """Compare two versions of the same analysis (Phase E2).

    Query params:
      ?a=<job_id>&b=<job_id>   — compare two specific jobs (b must be newer)

    Access control: both jobs must belong to the requesting user.
    """
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth_login"))

    from web.plan_jobs import get_job, get_version_chain
    from web.plan_images import get_session
    from web.plan_compare import get_or_compute_comparison

    job_a_id = request.args.get("a", "").strip()
    job_b_id = request.args.get("b", "").strip()

    if not job_a_id or not job_b_id:
        abort(400)

    job_a = get_job(job_a_id)
    job_b = get_job(job_b_id)

    # Both jobs must exist, be completed, and belong to this user
    for job in (job_a, job_b):
        if not job:
            abort(404)
        if job.get("user_id") != user_id:
            abort(403)
        if job.get("status") != "completed":
            abort(400)

    # Load sessions (page_extractions + page_annotations)
    session_a = get_session(job_a["session_id"]) if job_a.get("session_id") else None
    session_b = get_session(job_b["session_id"]) if job_b.get("session_id") else None
    if not session_a:
        session_a = {"page_extractions": [], "page_annotations": []}
    if not session_b:
        session_b = {"page_extractions": [], "page_annotations": []}

    # Compute or retrieve cached comparison
    comparison = get_or_compute_comparison(job_a, session_a, job_b, session_b)

    # Build version chain for context (if jobs share a version_group)
    version_chain = []
    vg = job_b.get("version_group") or job_a.get("version_group")
    if vg:
        try:
            version_chain = get_version_chain(vg)
        except Exception:
            pass

    # Phase F2: load project notes for this version group
    from web.plan_notes import get_project_notes
    project_notes = get_project_notes(user_id, vg) if vg else ""

    # Phase F3: page counts for visual comparison tab
    pages_a = session_a.get("page_count") or len(session_a.get("page_extractions") or [])
    pages_b = session_b.get("page_count") or len(session_b.get("page_extractions") or [])
    session_id_a = job_a.get("session_id") or ""
    session_id_b = job_b.get("session_id") or ""

    # Phase F4: extract revision history from both sessions' page_extractions
    def _extract_revisions(page_extractions):
        """Gather revision rows from title_block.revisions across all pages."""
        revisions = []
        seen = set()
        for ext in (page_extractions or []):
            tb = ext.get("title_block") or {}
            for rev in (tb.get("revisions") or []):
                key = (rev.get("revision_number"), rev.get("revision_date"))
                if key not in seen:
                    seen.add(key)
                    revisions.append(rev)
        return revisions

    revisions_a = _extract_revisions(session_a.get("page_extractions") or [])
    revisions_b = _extract_revisions(session_b.get("page_extractions") or [])

    # Fix #17: Load EPR check display names from tier1 knowledge base
    epr_check_names = {}
    try:
        import json as _json
        import os
        epr_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "knowledge", "tier1", "epr-requirements.json",
        )
        with open(epr_path) as f:
            epr_data = _json.load(f)
        for _category in epr_data.get("requirements", {}).values():
            if isinstance(_category, list):
                for req in _category:
                    if req.get("id") and req.get("rule"):
                        epr_check_names[req["id"]] = req["rule"]
    except Exception:
        logger.debug("Failed to load EPR check names", exc_info=True)

    return render_template(
        "analysis_compare.html",
        job_a=job_a,
        job_b=job_b,
        comparison=comparison,
        version_chain=version_chain,
        project_notes=project_notes,
        version_group=vg or "",
        session_id_a=session_id_a,
        session_id_b=session_id_b,
        pages_a=pages_a,
        pages_b=pages_b,
        revisions_a=revisions_a,
        revisions_b=revisions_b,
        epr_check_names=epr_check_names,
    )


@app.route("/api/plan-sessions/<session_id>/pages/<int:page_number>/image")
def get_session_page_image(session_id, page_number):
    """Return a page image for the visual comparison tab (Phase F3).

    Access control: the session must belong to a job owned by the requesting user.
    Returns a PNG image (Content-Type: image/png) from base64 stored data.
    """
    import base64 as _b64

    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    # Verify session belongs to a job owned by this user
    from src.db import query_one as _qone
    row = _qone(
        "SELECT user_id FROM plan_analysis_jobs WHERE session_id = %s LIMIT 1",
        (session_id,),
    )
    if not row or row[0] != user_id:
        return "", 403

    from web.plan_images import get_page_image
    img_b64 = get_page_image(session_id, page_number)
    if not img_b64:
        return "", 404

    try:
        img_bytes = _b64.b64decode(img_b64)
    except Exception:
        return "", 500

    return Response(img_bytes, mimetype="image/png")


@app.route("/api/project-notes/<version_group>", methods=["GET"])
def get_project_notes_api(version_group):
    """Return project notes for a version group (JSON)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    from web.plan_notes import get_project_notes
    text = get_project_notes(user_id, version_group)
    return jsonify({"notes_text": text})


@app.route("/api/project-notes/<version_group>", methods=["POST"])
def save_project_notes_api(version_group):
    """Save project notes for a version group (JSON or form POST).

    Body (JSON or form): { "notes_text": "..." }
    Returns: 200 {"ok": true} or 400 on error.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    if request.is_json:
        data = request.get_json(silent=True) or {}
        notes_text = data.get("notes_text", "")
    else:
        notes_text = request.form.get("notes_text", "")

    from web.plan_notes import save_project_notes
    ok = save_project_notes(user_id, version_group, notes_text)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"error": "save failed"}), 400


@app.route("/api/plan-jobs/<job_id>", methods=["DELETE"])
def delete_plan_job(job_id):
    """Soft-delete a plan analysis job (HTMX endpoint).

    Sets is_archived=TRUE. Can be restored via POST /api/plan-jobs/<job_id>/restore.
    """
    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    from web.plan_jobs import delete_job

    deleted = delete_job(job_id, user_id)
    if not deleted:
        return "", 404

    # Return empty string so HTMX removes the card (outerHTML swap)
    return ""


@app.route("/api/plan-jobs/<job_id>/restore", methods=["POST"])
def restore_plan_job(job_id):
    """Restore a soft-deleted plan analysis job (undo)."""
    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    from web.plan_jobs import restore_job

    restored = restore_job(job_id, user_id)
    if not restored:
        return "", 404

    return jsonify({"restored": True})


@app.route("/api/plan-jobs/<job_id>/prefill", methods=["GET"])
def prefill_plan_job(job_id):
    """Return metadata from a failed job to pre-fill the upload form for retry (#3)."""
    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    from web.plan_jobs import get_job

    job = get_job(job_id)
    if not job or job.get("user_id") != user_id:
        return "", 404

    return jsonify({
        "property_address": job.get("property_address") or "",
        "permit_number": job.get("permit_number") or "",
        "submission_stage": job.get("submission_stage") or "",
        "project_description": job.get("project_description") or "",
        "permit_type": job.get("permit_type") or "",
        "filename": job.get("filename") or "",
    })


@app.route("/api/plan-jobs/bulk-delete", methods=["POST"])
def bulk_delete_plan_jobs():
    """Bulk soft-delete plan analysis jobs (HTMX/JSON endpoint)."""
    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    from web.plan_jobs import bulk_delete_jobs

    data = request.get_json(silent=True) or {}
    job_ids = data.get("job_ids", [])
    if not job_ids or not isinstance(job_ids, list):
        return jsonify({"error": "job_ids required"}), 400

    # Cap at 100 to prevent abuse
    job_ids = job_ids[:100]
    deleted = bulk_delete_jobs(job_ids, user_id)
    return jsonify({"deleted": deleted, "job_ids": job_ids})


@app.route("/api/plan-jobs/bulk-close", methods=["POST"])
def bulk_close_plan_jobs():
    """Bulk close (archive) plan analysis jobs."""
    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    from web.plan_jobs import close_project

    data = request.get_json(silent=True) or {}
    job_ids = data.get("job_ids", [])
    if not job_ids or not isinstance(job_ids, list):
        return jsonify({"error": "job_ids required"}), 400

    job_ids = job_ids[:100]
    closed = close_project(job_ids, user_id)
    return jsonify({"closed": closed})


@app.route("/api/plan-jobs/<job_id>/close", methods=["POST"])
def close_plan_job(job_id):
    """Close (archive) a single plan analysis job."""
    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    from web.plan_jobs import close_project

    close_project([job_id], user_id)
    return jsonify({"closed": True})


@app.route("/api/plan-jobs/<job_id>/reopen", methods=["POST"])
def reopen_plan_job(job_id):
    """Reopen (unarchive) a single plan analysis job."""
    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    from web.plan_jobs import reopen_project

    reopen_project([job_id], user_id)
    return jsonify({"reopened": True})


@app.route("/lookup", methods=["POST"])
def lookup():
    """Look up permits by number, address, or block/lot."""
    lookup_mode = request.form.get("lookup_mode", "number")
    permit_number = request.form.get("permit_number", "").strip() or None
    street_number = request.form.get("street_number", "").strip() or None
    street_name = request.form.get("street_name", "").strip() or None
    block = request.form.get("block", "").strip() or None
    lot = request.form.get("lot", "").strip() or None

    # Validate based on selected mode
    if lookup_mode == "number" and not permit_number:
        return '<div class="error">Please enter a permit number.</div>', 400
    if lookup_mode == "address" and (not street_number or not street_name):
        return '<div class="error">Please enter both street number and street name.</div>', 400
    if lookup_mode == "parcel" and (not block or not lot):
        return '<div class="error">Please enter both block and lot numbers.</div>', 400

    try:
        result_md = run_async(permit_lookup(
            permit_number=permit_number if lookup_mode == "number" else None,
            street_number=street_number if lookup_mode == "address" else None,
            street_name=street_name if lookup_mode == "address" else None,
            block=block if lookup_mode == "parcel" else None,
            lot=lot if lookup_mode == "parcel" else None,
        ))
        result_html = md_to_html(result_md)
    except Exception as e:
        result_html = f'<div class="error">Lookup error: {e}</div>'

    # Resolve report URL for property report link
    report_url = None
    try:
        if lookup_mode == "parcel" and block and lot:
            report_url = f"/report/{block}/{lot}"
        elif lookup_mode == "address" and street_number and street_name:
            bl = _resolve_block_lot(street_number, street_name)
            if bl:
                report_url = f"/report/{bl[0]}/{bl[1]}"
    except Exception:
        pass

    # Extract street address for action buttons
    street_address = None
    permit_type = None

    if lookup_mode == "address" and street_number and street_name:
        street_address = f"{street_number} {street_name}"
    elif lookup_mode == "parcel" and block and lot:
        street_address = f"Block {block}, Lot {lot}"

    # Could extract permit_type from result_md if needed in future
    # For now, leave as None and buttons will use default

    return render_template(
        "lookup_results.html",
        result=result_html,
        report_url=report_url,
        street_address=street_address,
        permit_type=permit_type,
    )


# ---------------------------------------------------------------------------
# Conversational search box — /ask endpoint
# ---------------------------------------------------------------------------

@app.route("/ask", methods=["POST"])
def ask():
    """Classify a free-text query and route to the appropriate handler."""
    query = request.form.get("q", "").strip() or request.form.get("query", "").strip()
    if not query:
        return '<div class="error">Please type a question or search term.</div>', 400

    # Quick-action modifier (re-generate with overlay instructions)
    modifier = request.form.get("modifier", "").strip() or None

    # If modifier is set, skip classification — go straight to draft_response
    if modifier:
        return _ask_draft_response(query, {"query": query}, modifier=modifier)

    # Smart Analyze button: analyze=1 is always posted by the button,
    # so route to analyze_project regardless of description content.
    if request.form.get("analyze") == "1":
        return _ask_analyze_prefill(query, {})

    # Classify intent
    result = classify_intent(query, [n for n in NEIGHBORHOODS if n])
    intent = result.intent
    entities = result.entities

    # Allow explicit draft mode override via form field
    if request.form.get("draft") == "1" and intent not in (
        "lookup_permit", "search_complaint", "search_address",
        "search_parcel", "search_person", "validate_plans",
    ):
        intent = "draft_response"
        entities = {"query": query}

    try:
        if intent == "lookup_permit":
            return _ask_permit_lookup(query, entities)
        elif intent == "search_complaint":
            return _ask_complaint_search(query, entities)
        elif intent == "search_address":
            return _ask_address_search(query, entities)
        elif intent == "search_parcel":
            return _ask_parcel_search(query, entities)
        elif intent == "search_person":
            return _ask_person_search(query, entities)
        elif intent == "analyze_project":
            return _ask_analyze_prefill(query, entities)
        elif intent == "validate_plans":
            return _ask_validate_reveal(query)
        elif intent == "draft_response":
            return _ask_draft_response(query, entities)
        else:
            return _ask_general_question(query, entities)
    except Exception as e:
        logging.error("Error in /ask handler for intent=%s: %s", intent, e)
        return render_template(
            "search_results.html",
            query_echo=query,
            result_html=f'<div class="error">Something went wrong: {e}</div>',
        )


def _watch_context(watch_data: dict) -> dict:
    """Build template context for watch button (check existing watch status)."""
    ctx = {"watch_data": watch_data}
    if g.user:
        from web.auth import check_watch
        # Exclude watch_type and label from kwargs — they're positional or not DB fields
        kw = {k: v for k, v in watch_data.items() if k not in ("watch_type", "label")}
        existing = check_watch(g.user["user_id"], watch_data["watch_type"], **kw)
        if existing:
            ctx["existing_watch_id"] = existing["watch_id"]
    return ctx


def _ask_permit_lookup(query: str, entities: dict) -> str:
    """Handle permit number lookup."""
    permit_num = entities.get("permit_number")
    try:
        result_md = run_async(permit_lookup(permit_number=permit_num))
    except Exception as e:
        logging.warning("permit_lookup failed for permit %s: %s", permit_num, e)
        return _ask_general_question(query, entities)
    watch_data = {
        "watch_type": "permit",
        "permit_number": permit_num,
        "label": f"Permit #{permit_num}",
    }
    return render_template(
        "search_results.html",
        query_echo=f"Permit #{permit_num}",
        result_html=md_to_html(result_md),
        **_watch_context(watch_data),
    )


def _ask_complaint_search(query: str, entities: dict) -> str:
    """Handle complaint/violation/enforcement search."""
    complaint_number = entities.get("complaint_number")
    street_number = entities.get("street_number")
    street_name = entities.get("street_name")
    block = entities.get("block")
    lot = entities.get("lot")

    # Build full address string for display and filtering
    if street_number and street_name:
        full_address = f"{street_number} {street_name}"
    elif street_name:
        full_address = street_name
    else:
        full_address = None

    # Run both complaints and violations searches in parallel via the same
    # run_async helper. Build combined results.
    parts = []

    # Search complaints
    try:
        complaints_md = run_async(search_complaints(
            complaint_number=complaint_number,
            address=street_name,
            street_number=street_number,
            block=block,
            lot=lot,
        ))
        parts.append("## Complaints\n\n" + complaints_md)
    except Exception as e:
        logging.warning("search_complaints failed: %s", e)

    # Search violations
    try:
        violations_md = run_async(search_violations(
            complaint_number=complaint_number,
            address=street_name,
            street_number=street_number,
            block=block,
            lot=lot,
        ))
        parts.append("## Violations (NOVs)\n\n" + violations_md)
    except Exception as e:
        logging.warning("search_violations failed: %s", e)

    if not parts:
        return _ask_general_question(query, entities)

    combined_md = "\n\n---\n\n".join(parts)

    # Build label for display
    if complaint_number:
        label = f"Complaint #{complaint_number}"
    elif full_address:
        label = f"Complaints at {full_address}"
    elif block and lot:
        label = f"Complaints at Block {block}, Lot {lot}"
    else:
        label = "Complaint search"

    # Build watch data for address or parcel
    watch_data = {}
    if block and lot:
        watch_data = {
            "watch_type": "parcel",
            "block": block,
            "lot": lot,
            "label": f"Block {block}, Lot {lot}",
        }
    elif street_name:
        watch_data = {
            "watch_type": "address",
            "street_name": street_name,
            "label": f"Near {full_address or street_name}",
        }

    ctx = {}
    if watch_data:
        ctx = _watch_context(watch_data)

    report_url = f"/report/{block}/{lot}" if block and lot else None
    street_address = full_address or (f"Block {block}, Lot {lot}" if block and lot else None)

    return render_template(
        "search_results.html",
        query_echo=label,
        result_html=md_to_html(combined_md),
        report_url=report_url,
        street_address=street_address,
        show_quick_actions=False,
        **ctx,
    )


def _get_primary_permit_context(street_number: str, street_name: str) -> dict | None:
    """Get the most recent permit at an address for Analyze button pre-fill."""
    try:
        from src.db import query
        ctx_base = street_name.split()[0] if street_name else ""
        ctx_nospace = ctx_base.replace(' ', '')
        rows = query(
            "SELECT description, permit_type_definition, estimated_cost, "
            "       revised_cost, proposed_use, adu, neighborhood "
            "FROM permits "
            "WHERE street_number = %s "
            "  AND ("
            "    UPPER(street_name) = UPPER(%s)"
            "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
            "  ) "
            "ORDER BY filed_date DESC LIMIT 1",
            (street_number, ctx_base, ctx_nospace),
        )
        if not rows:
            return None
        desc, ptd, cost, revised_cost, proposed_use, adu, neighborhood = rows[0]
        effective_cost = revised_cost or cost
        # Build a short human label for the button
        label_parts = []
        if ptd:
            short = ptd.replace("Additions Alterations or Repairs", "Additions + Repairs")
            short = short.replace("New Construction Wood Frame", "New Construction")
            label_parts.append(short[:35])
        if effective_cost:
            label_parts.append(
                f"${effective_cost/1000:.0f}K" if effective_cost < 1_000_000
                else f"${effective_cost/1_000_000:.1f}M"
            )
        label = " · ".join(label_parts) if label_parts else "Active Permit"
        return {
            "description": (desc or ptd or "")[:200],
            "estimated_cost": effective_cost,
            "neighborhood": neighborhood,
            "label": label,
        }
    except Exception as e:
        logging.debug("_get_primary_permit_context failed: %s", e)
        return None


def _get_open_violation_counts(block: str, lot: str) -> dict | None:
    """Count open violations + complaints at a parcel. Returns None if tables empty."""
    try:
        from src.db import query
        # Check table is populated first — return None if ingest not yet done
        check = query("SELECT COUNT(*) FROM violations LIMIT 1", ())
        if not check or check[0][0] == 0:
            return None
        v_rows = query(
            "SELECT COUNT(*) FROM violations "
            "WHERE block = %s AND lot = %s AND LOWER(status) = 'open'",
            (block, lot),
        )
        c_rows = query(
            "SELECT COUNT(*) FROM complaints "
            "WHERE block = %s AND lot = %s AND LOWER(status) = 'open'",
            (block, lot),
        )
        open_v = v_rows[0][0] if v_rows else 0
        open_c = c_rows[0][0] if c_rows else 0
        return {"open_violations": open_v, "open_complaints": open_c, "total": open_v + open_c}
    except Exception as e:
        logging.debug("_get_open_violation_counts failed: %s", e)
        return None


def _get_active_businesses(street_number: str, street_name: str) -> list:
    """Get active registered businesses at this address. Returns [] if table empty."""
    try:
        from src.db import query
        check = query("SELECT COUNT(*) FROM businesses LIMIT 1", ())
        if not check or check[0][0] == 0:
            return []
        rows = query(
            "SELECT dba_name, ownership_name, dba_start_date, "
            "       parking_tax, transient_occupancy_tax "
            "FROM businesses "
            "WHERE full_business_address ILIKE %s "
            "  AND location_end_date IS NULL "
            "ORDER BY dba_start_date DESC LIMIT 5",
            (f"%{street_number}%{street_name.split()[0]}%",),
        )
        results = []
        for dba, ownership, start, parking, tot in rows:
            name = (dba or ownership or "").strip()
            if not name:
                continue
            since = str(start or "")[:4] or "?"
            type_flag = None
            if parking == "Y":
                type_flag = "🅿️ Parking"
            elif tot == "Y":
                type_flag = "🏨 Short-term rental"
            results.append({"name": name, "since": since, "type_flag": type_flag})
        return results
    except Exception as e:
        logging.debug("_get_active_businesses failed: %s", e)
        return []


def _get_address_intel(
    block: str | None = None,
    lot: str | None = None,
    street_number: str | None = None,
    street_name: str | None = None,
) -> dict:
    """Assemble property intelligence panel data.

    Each section is independently fault-tolerant — one failure
    doesn't prevent the others from returning data.
    """
    from src.db import query as db_query

    result = {
        "open_violations": None,
        "open_complaints": None,
        "enforcement_total": None,
        "business_count": 0,
        "active_businesses": [],
        "total_permits": None,
        "active_permits": None,
        "latest_permit_type": None,
        # Routing progress for primary active permit
        "routing_total": None,
        "routing_complete": None,
        "routing_latest_station": None,
        "routing_latest_date": None,
        "routing_latest_result": None,
    }

    # ── Section 1: Violations (needs block + lot) ──
    open_v = 0
    if block and lot:
        try:
            v_rows = db_query(
                "SELECT COUNT(*) FROM violations "
                "WHERE block = %s AND lot = %s AND LOWER(status) = 'open'",
                (block, lot),
            )
            open_v = v_rows[0][0] if v_rows else 0
            result["open_violations"] = open_v
        except Exception as e:
            logging.debug("_get_address_intel violations failed: %s", e)

    # ── Section 2: Complaints (needs block + lot) ──
    open_c = 0
    if block and lot:
        try:
            c_rows = db_query(
                "SELECT COUNT(*) FROM complaints "
                "WHERE block = %s AND lot = %s AND LOWER(status) = 'open'",
                (block, lot),
            )
            open_c = c_rows[0][0] if c_rows else 0
            result["open_complaints"] = open_c
        except Exception as e:
            logging.debug("_get_address_intel complaints failed: %s", e)

    if result["open_violations"] is not None or result["open_complaints"] is not None:
        result["enforcement_total"] = (result["open_violations"] or 0) + (result["open_complaints"] or 0)

    # ── Section 3: Businesses (needs street address) ──
    if street_number and street_name:
        try:
            biz_rows = db_query(
                "SELECT dba_name, ownership_name, dba_start_date, "
                "       parking_tax, transient_occupancy_tax "
                "FROM businesses "
                "WHERE full_business_address ILIKE %s "
                "  AND location_end_date IS NULL "
                "ORDER BY dba_start_date DESC LIMIT 5",
                (f"%{street_number}%{street_name.split()[0]}%",),
            )
            for dba, ownership, start, parking, tot in biz_rows:
                name = (dba or ownership or "").strip()
                if not name:
                    continue
                since = str(start or "")[:4] or "?"
                type_flag = None
                if parking == "Y":
                    type_flag = "🅿️ Parking"
                elif tot == "Y":
                    type_flag = "🏨 Short-term rental"
                result["active_businesses"].append(
                    {"name": name, "since": since, "type_flag": type_flag}
                )
            result["business_count"] = len(result["active_businesses"])
        except Exception as e:
            logging.debug("_get_address_intel businesses failed: %s", e)

    # ── Section 4: Permit stats (works with address OR block+lot) ──
    try:
        if street_number and street_name:
            # Exact match on street name (no substring matching)
            base_name = street_name.split()[0] if street_name else ""
            nospace_name = base_name.replace(' ', '')
            count_rows = db_query(
                "SELECT COUNT(*), "
                "       COUNT(*) FILTER (WHERE UPPER(status) IN "
                "           ('ISSUED', 'FILED', 'PLANCHECK', 'REINSTATED')) "
                "FROM permits "
                "WHERE street_number = %s "
                "  AND ("
                "    UPPER(street_name) = UPPER(%s)"
                "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
                "  )",
                (street_number, base_name, nospace_name),
            )
        elif block and lot:
            count_rows = db_query(
                "SELECT COUNT(*), "
                "       COUNT(*) FILTER (WHERE UPPER(status) IN "
                "           ('ISSUED', 'FILED', 'PLANCHECK', 'REINSTATED')) "
                "FROM permits "
                "WHERE block = %s AND lot = %s",
                (block, lot),
            )
        else:
            count_rows = None

        if count_rows and count_rows[0]:
            result["total_permits"] = count_rows[0][0]
            result["active_permits"] = count_rows[0][1]
    except Exception as e:
        logging.debug("_get_address_intel permit counts failed: %s", e)

    try:
        if street_number and street_name:
            base_name2 = street_name.split()[0] if street_name else ""
            nospace_name2 = base_name2.replace(' ', '')
            latest_rows = db_query(
                "SELECT permit_type_definition FROM permits "
                "WHERE street_number = %s "
                "  AND ("
                "    UPPER(street_name) = UPPER(%s)"
                "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
                "  ) "
                "ORDER BY filed_date DESC LIMIT 1",
                (street_number, base_name2, nospace_name2),
            )
        elif block and lot:
            latest_rows = db_query(
                "SELECT permit_type_definition FROM permits "
                "WHERE block = %s AND lot = %s "
                "ORDER BY filed_date DESC LIMIT 1",
                (block, lot),
            )
        else:
            latest_rows = None

        if latest_rows and latest_rows[0]:
            ptd = latest_rows[0][0] or ""
            ptd = ptd.replace("Additions Alterations or Repairs", "Additions + Repairs")
            ptd = ptd.replace("New Construction Wood Frame", "New Construction")
            result["latest_permit_type"] = ptd[:40] if ptd else None
    except Exception as e:
        logging.debug("_get_address_intel latest permit failed: %s", e)

    # ── Section 5: Routing progress for primary active permit ──
    try:
        # Find the most recently filed active permit at this address
        primary_pnum = None
        if street_number and street_name:
            rp_base = street_name.split()[0] if street_name else ""
            rp_nospace = rp_base.replace(' ', '')
            pn_rows = db_query(
                "SELECT permit_number FROM permits "
                "WHERE street_number = %s "
                "  AND ("
                "    UPPER(street_name) = UPPER(%s)"
                "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
                "  ) "
                "  AND UPPER(status) IN ('FILED', 'PLANCHECK') "
                "ORDER BY filed_date DESC LIMIT 1",
                (street_number, rp_base, rp_nospace),
            )
        elif block and lot:
            pn_rows = db_query(
                "SELECT permit_number FROM permits "
                "WHERE block = %s AND lot = %s "
                "  AND UPPER(status) IN ('FILED', 'PLANCHECK') "
                "ORDER BY filed_date DESC LIMIT 1",
                (block, lot),
            )
        else:
            pn_rows = None

        if pn_rows and pn_rows[0]:
            primary_pnum = pn_rows[0][0]

        if primary_pnum:
            # Get the latest addenda_number for this permit
            latest_rev = db_query(
                "SELECT MAX(addenda_number) FROM addenda "
                "WHERE application_number = %s",
                (primary_pnum,),
            )
            rev_num = latest_rev[0][0] if latest_rev and latest_rev[0][0] is not None else None

            if rev_num is not None:
                # Count total steps and completed steps for this revision
                routing_rows = db_query(
                    "SELECT COUNT(*), "
                    "       COUNT(*) FILTER (WHERE finish_date IS NOT NULL) "
                    "FROM addenda "
                    "WHERE application_number = %s AND addenda_number = %s",
                    (primary_pnum, rev_num),
                )
                if routing_rows and routing_rows[0]:
                    result["routing_total"] = routing_rows[0][0]
                    result["routing_complete"] = routing_rows[0][1]

                # Get the most recent completed step
                latest_step = db_query(
                    "SELECT station, finish_date, review_results "
                    "FROM addenda "
                    "WHERE application_number = %s AND addenda_number = %s "
                    "  AND finish_date IS NOT NULL "
                    "ORDER BY finish_date DESC LIMIT 1",
                    (primary_pnum, rev_num),
                )
                if latest_step and latest_step[0]:
                    result["routing_latest_station"] = latest_step[0][0]
                    fd = latest_step[0][1]
                    result["routing_latest_date"] = str(fd)[:10] if fd else None
                    result["routing_latest_result"] = latest_step[0][2]
    except Exception as e:
        logging.debug("_get_address_intel routing progress failed: %s", e)

    return result


def _ask_address_search(query: str, entities: dict) -> str:
    """Handle address-based permit search."""
    street_number = entities.get("street_number")
    street_name = entities.get("street_name")
    try:
        result_md = run_async(permit_lookup(
            street_number=street_number,
            street_name=street_name,
        ))
    except Exception as e:
        logging.warning("permit_lookup failed for address %s %s: %s",
                        street_number, street_name, e)
        return _ask_general_question(query, entities)
    watch_data = {
        "watch_type": "address",
        "street_number": street_number,
        "street_name": street_name,
        "label": f"{street_number} {street_name}",
    }
    # Primary address prompt: show if logged in and no primary address set yet
    show_primary_prompt = bool(g.user and not g.user.get("primary_street_number"))
    # Resolve block/lot for property report link
    report_url = None
    try:
        from src.db import query as db_query
        from src.tools.permit_lookup import _strip_suffix
        bl = _resolve_block_lot(street_number, street_name)
        # Fallback: if _resolve_block_lot failed but permits exist, try a
        # broader query (just street_number + block/lot NOT NULL)
        if not bl:
            base_name, _sfx = _strip_suffix(street_name)
            fb_nospace = base_name.replace(' ', '')
            rows = db_query(
                "SELECT block, lot FROM permits "
                "WHERE street_number = %s "
                "  AND ("
                "    UPPER(street_name) = UPPER(%s)"
                "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
                "  ) "
                "  AND block IS NOT NULL AND lot IS NOT NULL "
                "LIMIT 1",
                (street_number, base_name, fb_nospace),
            )
            if rows:
                bl = (rows[0][0], rows[0][1])
                logging.info("_resolve_block_lot fallback matched: %s %s -> %s/%s",
                             street_number, street_name, bl[0], bl[1])
        if bl:
            report_url = f"/report/{bl[0]}/{bl[1]}"
    except Exception as e:
        logging.warning("Block/lot resolution failed for %s %s: %s",
                        street_number, street_name, e)
    # Detect no-results to show helpful next-step CTAs
    no_results = result_md.startswith("No permits found")
    street_address = f"{street_number} {street_name}" if street_number and street_name else None
    # Enrich Quick Actions with live context
    project_context = None
    address_intel = None
    if not no_results:
        project_context = _get_primary_permit_context(street_number, street_name)
        address_intel = _get_address_intel(
            block=bl[0] if bl else None,
            lot=bl[1] if bl else None,
            street_number=street_number,
            street_name=street_name,
        )
        # Sync badge count with MCP tool's actual permit count (which
        # includes parcel merge + historical lot discovery)
        if address_intel:
            import re
            _m = re.search(r'Found \*\*(\d+)\*\* permits', result_md)
            if _m:
                address_intel["total_permits"] = int(_m.group(1))
    # Extract for backward compat with Quick Actions buttons
    violation_counts = None
    active_businesses = []
    if address_intel:
        if address_intel["enforcement_total"] is not None:
            violation_counts = {
                "open_violations": address_intel["open_violations"] or 0,
                "open_complaints": address_intel["open_complaints"] or 0,
                "total": address_intel["enforcement_total"],
            }
        active_businesses = address_intel["active_businesses"]
    return render_template(
        "search_results.html",
        query_echo=f"{street_number} {street_name}",
        result_html=md_to_html(result_md),
        show_primary_prompt=show_primary_prompt,
        prompt_street_number=street_number,
        prompt_street_name=street_name,
        report_url=report_url,
        street_address=street_address,
        no_results=no_results,
        no_results_address=f"{street_number} {street_name}" if no_results else None,
        project_context=project_context,
        violation_counts=violation_counts,
        active_businesses=active_businesses,
        address_intel=address_intel,
        show_quick_actions=True,
        **_watch_context(watch_data),
    )


def _ask_parcel_search(query: str, entities: dict) -> str:
    """Handle block/lot parcel search."""
    block = entities.get("block")
    lot = entities.get("lot")
    try:
        result_md = run_async(permit_lookup(block=block, lot=lot))
    except Exception as e:
        logging.warning("permit_lookup failed for parcel %s/%s: %s", block, lot, e)
        return _ask_general_question(query, entities)
    watch_data = {
        "watch_type": "parcel",
        "block": block,
        "lot": lot,
        "label": f"Block {block}, Lot {lot}",
    }
    report_url = f"/report/{block}/{lot}" if block and lot else None
    street_address = f"Block {block}, Lot {lot}" if block and lot else None
    # Property intel — block/lot only, no street address for business lookup
    address_intel = None
    violation_counts = None
    if block and lot:
        address_intel = _get_address_intel(block=block, lot=lot)
        # Sync badge count with MCP tool's actual permit count
        if address_intel:
            import re
            _m = re.search(r'Found \*\*(\d+)\*\* permits', result_md)
            if _m:
                address_intel["total_permits"] = int(_m.group(1))
        if address_intel and address_intel["enforcement_total"] is not None:
            violation_counts = {
                "open_violations": address_intel["open_violations"] or 0,
                "open_complaints": address_intel["open_complaints"] or 0,
                "total": address_intel["enforcement_total"],
            }
    return render_template(
        "search_results.html",
        query_echo=f"Block {block}, Lot {lot}",
        result_html=md_to_html(result_md),
        report_url=report_url,
        street_address=street_address,
        project_context=None,
        violation_counts=violation_counts,
        active_businesses=[],
        address_intel=address_intel,
        show_quick_actions=True,
        **_watch_context(watch_data),
    )


def _ask_person_search(query: str, entities: dict) -> str:
    """Handle person/company name search."""
    name = entities.get("person_name", "")
    role = entities.get("role")
    try:
        result_md = run_async(search_entity(name=name, entity_type=role))
    except Exception as e:
        logging.warning("search_entity failed for %s: %s", name, e)
        return _ask_general_question(query, entities)
    # For person searches, we can't easily get entity_id without a DB lookup,
    # so we watch by name (general_question fallback — entity watching is best
    # done from the detailed entity page in a future iteration)
    watch_data = {
        "watch_type": "entity",
        "label": f"{name}" + (f" ({role})" if role else ""),
    }
    return render_template(
        "search_results.html",
        query_echo=f"Search: {name}" + (f" ({role})" if role else ""),
        result_html=md_to_html(result_md),
        **_watch_context(watch_data),
    )


def _ask_analyze_prefill(query: str, entities: dict) -> str:
    """Pre-fill the analyze form and reveal it."""
    import json
    # Accept real permit fields posted directly from the smart Analyze button
    cost_raw = request.form.get("estimated_cost", "")
    neighborhood_raw = request.form.get("neighborhood", "")
    address_raw = request.form.get("address", "")
    prefill_data = {
        "description": entities.get("description", query),
        "estimated_cost": float(cost_raw) if cost_raw else entities.get("estimated_cost"),
        "square_footage": entities.get("square_footage"),
        "neighborhood": neighborhood_raw or entities.get("neighborhood"),
        "address": address_raw or entities.get("address"),
    }
    # Remove None/empty values for cleaner JSON
    prefill_data = {k: v for k, v in prefill_data.items() if v}
    return render_template(
        "search_prefill.html",
        prefill_json=json.dumps(prefill_data),
    )


def _ask_validate_reveal(query: str) -> str:
    """Reveal the validation section."""
    return render_template("search_reveal.html", section="validate")


def _ask_draft_response(query: str, entities: dict, modifier: str | None = None) -> str:
    """Generate an AI-synthesized response to a conversational question.

    Uses RAG retrieval for context, then sends to Claude for a natural,
    helpful response. Falls back to raw RAG display if AI is unavailable.

    Args:
        modifier: Optional quick-action modifier (get_meeting, cite_sources, shorter, more_detail)
    """
    effective_query = entities.get("query", query)

    # Try RAG-augmented retrieval for context
    rag_results = _try_rag_retrieval(effective_query)
    if not rag_results:
        return _ask_general_question(query, entities)

    role = _get_user_response_role()

    # Assemble context from RAG results
    seen_sources = set()
    context_parts = []
    references = []
    source_details = []

    for r in rag_results:
        source_file = r.get("source_file", "")
        source_section = r.get("source_section", "")
        source_key = f"{source_file}:{source_section}"
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)

        content = r.get("content", "")
        label = _build_source_label(source_file, source_section)
        context_parts.append(f"[{label}]\n{content}")
        if label and label not in references:
            references.append(label)
        source_details.append({
            "source_label": label,
            "score": r.get("final_score", 0),
            "source_tier": r.get("source_tier", ""),
        })

    if not context_parts:
        return _ask_general_question(query, entities)

    # Synthesize with Claude
    ai_response = _synthesize_with_ai(
        effective_query, "\n\n---\n\n".join(context_parts), role, modifier=modifier
    )

    if ai_response:
        return render_template(
            "draft_response.html",
            query=query,
            ai_response_html=md_to_html(ai_response),
            references=references[:5],
            source_details=source_details,
            role=role,
            is_expert=_is_expert_user(),
        )

    # Fallback: show raw RAG results if AI synthesis fails
    cleaned_results = []
    for r in rag_results:
        sf = r.get("source_file", "")
        ss = r.get("source_section", "")
        sk = f"{sf}:{ss}"
        content = _clean_chunk_content(r.get("content", ""), sf)
        label = _build_source_label(sf, ss)
        cleaned_results.append({
            "content_html": md_to_html(content),
            "source_label": label,
            "score": r.get("final_score", 0),
            "source_tier": r.get("source_tier", ""),
        })
    return render_template(
        "draft_response.html",
        query=query,
        results=cleaned_results,
        references=references[:5],
        role=role,
        is_expert=_is_expert_user(),
    )


def _synthesize_with_ai(
    query: str, rag_context: str, role: str, modifier: str | None = None,
) -> str | None:
    """Call Claude to synthesize a conversational response from RAG context.

    Returns the AI-generated markdown response, or None if unavailable.
    Injects user's voice_style preferences if set.

    Args:
        modifier: Optional quick-action modifier that overrides default guidelines.
            Supported: get_meeting, cite_sources, shorter, more_detail
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    if role == "professional":
        tone = (
            "You are Amy, an expert SF permit expeditor. Respond professionally "
            "but warmly, as if advising a colleague. Be specific about code "
            "sections, required forms, and practical next steps."
        )
    elif role == "homeowner":
        tone = (
            "You are Amy, a friendly SF permit expert helping a homeowner. "
            "Explain things simply and clearly, avoiding jargon. Focus on "
            "what they need to do and what to expect."
        )
    else:
        tone = (
            "You are Amy, an SF building permit expert. Provide a clear, "
            "helpful response. Include specific code references and practical "
            "guidance where relevant."
        )

    # Inject user's voice & style preferences (macro instructions)
    voice_style = ""
    try:
        if g.user and g.user.get("voice_style"):
            voice_style = g.user["voice_style"]
    except RuntimeError:
        pass  # Outside request context

    style_block = ""
    if voice_style:
        style_block = (
            f"\n\nIMPORTANT — The user has set these style preferences. "
            f"Follow them closely:\n{voice_style}\n"
        )

    # Quick-action modifier overrides
    modifier_instructions = ""
    if modifier == "get_meeting":
        modifier_instructions = (
            "\n\nOVERRIDE: Keep the response brief (2-3 sentences max). "
            "Give one concrete helpful fact, then warmly suggest scheduling "
            "a call to discuss in detail. End with something like 'Would you "
            "like to set up a quick call to walk through this?'\n"
        )
    elif modifier == "shorter":
        modifier_instructions = (
            "\n\nOVERRIDE: Maximum 100 words. Be direct and concise. "
            "No pleasantries, just the key facts and one next step.\n"
        )
    elif modifier == "more_detail":
        modifier_instructions = (
            "\n\nOVERRIDE: Provide a thorough 400-600 word response with full details, "
            "timelines, fees, and step-by-step guidance. Include specific code section "
            "references for every claim. Use these rules for citations:\n"
            "- SF Planning Code sections: format as markdown links, e.g. "
            "[Planning Code §207](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/0-0-0-1)\n"
            "- SF Building Code (SFBC) sections: format as markdown links, e.g. "
            "[SFBC §3301](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-1)\n"
            "- CBC, Title 24, ASCE 7: use inline citations only, e.g. (CBC §706.1) — no links, these are paywalled.\n"
            "Be comprehensive and cite sources inline throughout, not just at the end.\n"
        )

    system_prompt = (
        f"{tone}{style_block}{modifier_instructions}\n\n"
        "Use the following knowledge base context to answer the question. "
        "If the context doesn't fully answer the question, say what you know "
        "and note what you're less certain about.\n\n"
        "Guidelines:\n"
        "- Start with a brief, direct summary (2-3 sentences) answering their core question\n"
        "- Then provide relevant details and next steps\n"
        "- Cite specific code sections (CBC, Planning Code, SFBC) when applicable\n"
        "- Keep the response concise — aim for 200-400 words\n"
        "- Use markdown formatting (bold, bullets, headers) for readability\n"
        "- End with a clear next-step recommendation\n"
        "- Do NOT say 'Based on the context provided' or reference the retrieval system\n"
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Knowledge base context:\n{rag_context}\n\n"
                        f"---\n\nQuestion from user:\n{query}"
                    ),
                }
            ],
        )
        if response.content and response.content[0].type == "text":
            return response.content[0].text
        return None
    except Exception as e:
        logging.warning("AI synthesis failed: %s", e)
        return None


def _ask_general_question(query: str, entities: dict) -> str:
    """Answer a general question using RAG retrieval (with keyword fallback)."""
    effective_query = entities.get("query", query)

    # Try RAG-augmented retrieval first
    rag_results = _try_rag_retrieval(effective_query)
    if rag_results:
        # Try AI synthesis first, fall back to raw display
        role = _get_user_response_role()
        context_parts = []
        references = []
        source_details = []
        seen = set()
        for r in rag_results:
            sf = r.get("source_file", "")
            ss = r.get("source_section", "")
            sk = f"{sf}:{ss}"
            if sk in seen:
                continue
            seen.add(sk)
            label = _build_source_label(sf, ss)
            context_parts.append(f"[{label}]\n{r.get('content', '')}")
            if label and label not in references:
                references.append(label)
            source_details.append({
                "source_label": label,
                "score": r.get("final_score", 0),
                "source_tier": r.get("source_tier", ""),
            })
        ai_response = _synthesize_with_ai(effective_query, "\n\n---\n\n".join(context_parts), role)
        if ai_response:
            return render_template(
                "draft_response.html",
                query=query,
                ai_response_html=md_to_html(ai_response),
                references=references[:5],
                source_details=source_details,
                role=role,
                is_expert=_is_expert_user(),
            )
        # Fall back to raw RAG display
        return _render_rag_results(query, rag_results)

    # Fallback: keyword-only matching from KnowledgeBase
    kb = get_knowledge_base()
    scored = kb.match_concepts_scored(effective_query)

    if not scored:
        return render_template(
            "search_results.html",
            query_echo=query,
            result_html=(
                '<div class="info">I don\'t have a specific answer for that yet. '
                'Try searching by permit number, address, or describing your project.</div>'
            ),
        )

    # Build an answer from the top matched concepts
    parts = []
    concepts = kb.semantic_index.get("concepts", {})
    for concept_name, score in scored[:3]:
        concept = concepts.get(concept_name, {})
        desc = concept.get("description", "")
        if desc:
            parts.append(f"**{concept_name.replace('_', ' ').title()}**: {desc}")

    result_html = md_to_html("\n\n".join(parts)) if parts else (
        '<div class="info">No matching knowledge found for that query.</div>'
    )
    return render_template(
        "search_results.html",
        query_echo=query,
        result_html=result_html,
    )


def _try_rag_retrieval(query: str) -> list[dict] | None:
    """Attempt RAG retrieval. Returns results or None if unavailable."""
    try:
        from src.rag.retrieval import retrieve
        results = retrieve(query, top_k=5)
        # Filter out keyword-only fallback results (those have similarity=0)
        real_results = [r for r in results if r.get("similarity", 0) > 0]
        return real_results if real_results else None
    except Exception as e:
        logging.debug("RAG retrieval unavailable: %s", e)
        return None


def _clean_chunk_content(content: str, source_file: str = "") -> str:
    """Clean raw RAG chunk content for human-readable display.

    Handles tier1 JSON-style key:value content, tier2 raw text,
    and expert notes.
    """
    lines = content.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Strip [filename] prefixes like "[epr-requirements]"
        stripped = re.sub(r'^\[[\w\-\.]+\]\s*', '', stripped)
        # Convert "key: value" (YAML-style) to bold key
        m = re.match(r'^(\w[\w_\s]{1,30}?):\s+(.+)$', stripped)
        if m:
            key = m.group(1).replace("_", " ").strip().title()
            val = m.group(2).strip()
            # Special handling for quote fields
            if key.lower() == "quote":
                cleaned.append(f'> "{val}"')
            else:
                cleaned.append(f"**{key}**: {val}")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            cleaned.append(stripped)
        elif stripped.startswith('"') and stripped.endswith('"'):
            cleaned.append(f"> {stripped}")
        else:
            cleaned.append(stripped)
    return "\n\n".join(cleaned)


def _get_user_response_role() -> str:
    """Determine response role based on current user."""
    if not g.user:
        return "general"
    if g.user.get("is_admin") or g.user.get("role") in ("admin", "consultant"):
        return "professional"
    return "homeowner"


def _is_expert_user() -> bool:
    """Check if current user can add expert notes."""
    return bool(
        g.user
        and (g.user.get("is_admin") or g.user.get("role") in ("admin", "consultant"))
    )


def _build_source_label(source_file: str, source_section: str) -> str:
    """Build a readable source label from file/section names."""
    label = source_file.replace(".json", "").replace(".txt", "")
    label = label.replace("-", " ").replace("_", " ").title()
    if source_section and source_section not in source_file:
        section = source_section.replace("_", " ").replace("-", " ").title()
        label = f"{label} \u203a {section}"
    return label


def _render_rag_results(query: str, results: list[dict]) -> str:
    """Render RAG retrieval results as a clean knowledge answer card."""
    seen_sources = set()
    cleaned_results = []

    for r in results:
        source_file = r.get("source_file", "")
        source_section = r.get("source_section", "")
        source_key = f"{source_file}:{source_section}"
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)

        content = _clean_chunk_content(r.get("content", ""), source_file)
        cleaned_results.append({
            "content_html": md_to_html(content),
            "source_label": _build_source_label(source_file, source_section),
            "score": r.get("final_score", 0),
            "source_tier": r.get("source_tier", ""),
        })

    if not cleaned_results:
        return render_template(
            "search_results.html",
            query_echo=query,
            result_html='<div class="info">No matching knowledge found.</div>',
        )

    return render_template(
        "knowledge_answer.html",
        query=query,
        results=cleaned_results,
        is_expert=_is_expert_user(),
    )


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/auth/login")
def auth_login():
    """Show the login/register page."""
    from web.auth import invite_required
    return render_template("auth_login.html", invite_required=invite_required())


@app.route("/auth/send-link", methods=["POST"])
def auth_send_link():
    """Create user if needed, generate magic link, send/display it."""
    from web.auth import (
        get_user_by_email, create_user, create_magic_token, send_magic_link,
        BASE_URL, invite_required, validate_invite_code,
    )

    email = request.form.get("email", "").strip().lower()
    if not email or "@" not in email:
        return render_template(
            "auth_login.html",
            message="Please enter a valid email address.",
            message_type="error",
            invite_required=invite_required(),
        ), 400

    # Check if existing user (existing users don't need an invite code)
    user = get_user_by_email(email)

    if not user:
        # New user — check invite code if required
        invite_code = request.form.get("invite_code", "").strip()
        if invite_required():
            if not invite_code or not validate_invite_code(invite_code):
                return render_template(
                    "auth_login.html",
                    message="A valid invite code is required to create an account.",
                    message_type="error",
                    invite_required=True,
                ), 403
        user = create_user(email, invite_code=invite_code or None)

    token = create_magic_token(user["user_id"])
    sent = send_magic_link(email, token)

    link = f"{BASE_URL}/auth/verify/{token}"

    if sent and os.environ.get("SMTP_HOST"):
        # Prod: email sent
        return render_template(
            "auth_login.html",
            message=f"Magic link sent to <strong>{email}</strong>. Check your inbox.",
            invite_required=invite_required(),
        )
    else:
        # Dev: show link directly
        return render_template(
            "auth_login.html",
            message=f'Magic link (dev mode): <a href="{link}">{link}</a>',
            invite_required=invite_required(),
        )


@app.route("/auth/verify/<token>")
def auth_verify(token):
    """Verify a magic link token and create a session."""
    from web.auth import verify_magic_token

    user = verify_magic_token(token)
    if not user:
        return render_template(
            "auth_login.html",
            message="Invalid or expired link. Please request a new one.",
            message_type="error",
        ), 400

    session.permanent = True
    session["user_id"] = user["user_id"]
    session["email"] = user["email"]
    session["is_admin"] = user["is_admin"]
    session.pop("impersonating", None)
    session.pop("admin_user_id", None)

    return redirect(url_for("index"))


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    """Clear the session."""
    session.clear()
    return redirect(url_for("index"))


@app.route("/auth/impersonate", methods=["POST"])
@admin_required
def auth_impersonate():
    """Admin: switch to viewing as another user."""
    from web.auth import get_user_by_email, get_or_create_user

    target_email = request.form.get("target_email", "").strip().lower()
    if not target_email:
        return redirect(url_for("account"))

    target_user = get_or_create_user(target_email)

    logging.warning(
        "Admin %s (id=%s) impersonating %s (id=%s)",
        session.get("email"), session.get("user_id"),
        target_email, target_user["user_id"],
    )

    session["admin_user_id"] = session["user_id"]
    session["admin_email"] = session["email"]
    session["user_id"] = target_user["user_id"]
    session["email"] = target_user["email"]
    session["impersonating"] = target_email

    return redirect(url_for("account"))


@app.route("/auth/stop-impersonate", methods=["POST"])
def auth_stop_impersonate():
    """Restore admin's own identity."""
    admin_id = session.pop("admin_user_id", None)
    admin_email = session.pop("admin_email", None)
    session.pop("impersonating", None)

    if admin_id:
        session["user_id"] = admin_id
        session["email"] = admin_email

    return redirect(url_for("account"))


# ---------------------------------------------------------------------------
# Watch routes
# ---------------------------------------------------------------------------

@app.route("/watch/add", methods=["POST"])
def watch_add():
    """Add item to watch list. Returns HTMX fragment."""
    if not g.user:
        return render_template("fragments/login_prompt.html")

    from web.auth import add_watch

    watch_type = request.form.get("watch_type", "")
    kwargs = {
        "permit_number": request.form.get("permit_number") or None,
        "street_number": request.form.get("street_number") or None,
        "street_name": request.form.get("street_name") or None,
        "block": request.form.get("block") or None,
        "lot": request.form.get("lot") or None,
        "entity_id": int(request.form["entity_id"]) if request.form.get("entity_id") else None,
        "neighborhood": request.form.get("neighborhood") or None,
        "label": request.form.get("label") or None,
    }

    watch = add_watch(g.user["user_id"], watch_type, **kwargs)
    return render_template("fragments/watch_confirmation.html", watch_id=watch["watch_id"])


@app.route("/watch/remove", methods=["POST"])
def watch_remove():
    """Remove item from watch list. Returns HTMX fragment or empty for account page."""
    if not g.user:
        return "", 403

    from web.auth import remove_watch

    watch_id = request.form.get("watch_id")
    if watch_id:
        remove_watch(int(watch_id), g.user["user_id"])

    # If called from account page (hx-swap="outerHTML"), return empty to remove the item
    return ""


@app.route("/watch/tags", methods=["POST"])
def watch_tags():
    """Update tags for a watch item. Returns HTMX tag editor fragment."""
    if not g.user:
        return "Unauthorized", 401

    from web.auth import update_watch_tags, get_watches

    watch_id = int(request.form.get("watch_id", 0))
    tags = request.form.get("tags", "")
    update_watch_tags(watch_id, g.user["user_id"], tags)
    # Return the updated tag editor
    watch = None
    for w in get_watches(g.user["user_id"]):
        if w["watch_id"] == watch_id:
            watch = w
            break
    if watch:
        return render_template("fragments/tag_editor.html", watch=watch)
    return "", 204


@app.route("/watch/edit", methods=["POST"])
def watch_edit():
    """Update label for a watch item. Returns the new label text."""
    if not g.user:
        return "Forbidden", 403

    from web.auth import update_watch_label

    watch_id_str = request.form.get("watch_id", "")
    label = request.form.get("label", "")
    if not watch_id_str:
        return "", 400

    update_watch_label(int(watch_id_str), g.user["user_id"], label)
    return label, 200


@app.route("/watch/list")
@login_required
def watch_list():
    """Return user's watch list as HTML fragment."""
    from web.auth import get_watches
    watches = get_watches(g.user["user_id"])
    return render_template("account.html", user=g.user, watches=watches)


# ---------------------------------------------------------------------------
# Account page
# ---------------------------------------------------------------------------

@app.route("/account")
@login_required
def account():
    """User account page with watch list."""
    from web.auth import get_watches, INVITE_CODES
    from web.activity import get_user_points, get_points_history
    watches = get_watches(g.user["user_id"])
    # Sort codes so the dropdown is consistent
    invite_codes = sorted(INVITE_CODES) if g.user.get("is_admin") else []
    # Points data
    total_points = get_user_points(g.user["user_id"])
    points_history = get_points_history(g.user["user_id"], limit=10)
    # Recent plan analyses
    recent_analyses = []
    try:
        from web.plan_jobs import get_user_jobs
        recent_analyses = get_user_jobs(g.user["user_id"], limit=3)
    except Exception:
        pass  # Non-fatal — plan_jobs table may not exist yet
    # Admin stats for dashboard cards
    activity_stats = None
    feedback_counts = None
    if g.user.get("is_admin"):
        from web.activity import get_activity_stats, get_feedback_counts
        activity_stats = get_activity_stats(hours=24)
        feedback_counts = get_feedback_counts()
    # Voice calibration stats (all users)
    cal_stats = None
    try:
        from web.voice_calibration import get_calibration_stats
        cal_stats = get_calibration_stats(g.user["user_id"])
        if cal_stats["total"] == 0:
            cal_stats = None  # Not yet seeded — show generic text
    except Exception:
        pass
    return render_template("account.html", user=g.user, watches=watches,
                           invite_codes=invite_codes,
                           activity_stats=activity_stats,
                           feedback_counts=feedback_counts,
                           total_points=total_points,
                           points_history=points_history,
                           recent_analyses=recent_analyses,
                           cal_stats=cal_stats)


# ---------------------------------------------------------------------------
# Primary address
# ---------------------------------------------------------------------------

@app.route("/account/primary-address", methods=["POST"])
@login_required
def account_set_primary_address():
    """Set or update the user's primary address. Returns HTMX fragment."""
    from web.auth import set_primary_address

    street_number = request.form.get("street_number", "").strip()
    street_name = request.form.get("street_name", "").strip()

    if not street_number or not street_name:
        return '<span style="color:var(--error);">Address is required.</span>'

    set_primary_address(g.user["user_id"], street_number, street_name)

    label = f"{street_number} {street_name}"
    return (
        f'<span style="color:var(--success);">'
        f'Saved — {label} is your primary address.</span>'
    )


@app.route("/account/primary-address/clear", methods=["POST"])
@login_required
def account_clear_primary_address():
    """Clear the user's primary address. Returns HTMX fragment."""
    from web.auth import clear_primary_address
    clear_primary_address(g.user["user_id"])
    return (
        '<span style="color:var(--text-muted);font-style:italic;">'
        'Not set &mdash; search for your address to save it</span>'
    )


# ---------------------------------------------------------------------------
# Morning Brief
# ---------------------------------------------------------------------------

@app.route("/brief")
@login_required
def brief():
    """Morning brief dashboard — what changed, permit health, inspections."""
    from web.brief import get_morning_brief
    from web.auth import get_primary_address
    lookback = request.args.get("lookback", "1")
    try:
        lookback_days = max(1, min(int(lookback), 90))
    except ValueError:
        lookback_days = 1
    primary_addr = get_primary_address(g.user["user_id"])
    brief_data = get_morning_brief(g.user["user_id"], lookback_days,
                                   primary_address=primary_addr)
    return render_template("brief.html", user=g.user, brief=brief_data,
                           active_page="brief")


# ---------------------------------------------------------------------------
# Velocity / Bottleneck Dashboard
# ---------------------------------------------------------------------------

@app.route("/dashboard/bottlenecks")
@login_required
def velocity_dashboard():
    """DBI approval pipeline bottleneck heatmap."""
    from web.velocity_dashboard import get_dashboard_data
    user_id = g.user["user_id"] if g.user else None
    data = get_dashboard_data(user_id=user_id)
    return render_template(
        "velocity_dashboard.html",
        data=data,
        active_page="bottlenecks",
    )


@app.route("/dashboard/bottlenecks/station/<path:station>")
@login_required
def velocity_station_detail(station: str):
    """JSON endpoint: reviewer stats for a single station (heatmap drill-down)."""
    from web.velocity_dashboard import get_reviewer_stats
    station = station.upper().strip()
    reviewers = get_reviewer_stats(station)
    return jsonify({"station": station, "reviewers": reviewers})


# ---------------------------------------------------------------------------
# Portfolio Dashboard
# ---------------------------------------------------------------------------

@app.route("/portfolio")
@login_required
def portfolio():
    """Portfolio dashboard — property card grid with health indicators."""
    from web.portfolio import get_portfolio

    filter_by = request.args.get("filter", "all")
    sort_by = request.args.get("sort", "recent")

    data = get_portfolio(g.user["user_id"])
    properties = data["properties"]

    # Apply filters
    if filter_by == "action_needed":
        properties = [p for p in properties if p["worst_health"] in ("behind", "at_risk")]
    elif filter_by == "in_review":
        properties = [p for p in properties if any(pm["status"] == "filed" for pm in p["permits"])]
    elif filter_by == "active":
        properties = [p for p in properties if p["active_count"] > 0]

    # Apply sort
    health_order = {"at_risk": 0, "behind": 1, "slower": 2, "on_track": 3}
    if sort_by == "cost_desc":
        properties.sort(key=lambda p: p["total_cost"] or 0, reverse=True)
    elif sort_by == "stale":
        properties.sort(key=lambda p: p["latest_activity"] or "")
    elif sort_by == "health":
        properties.sort(key=lambda p: health_order.get(p["worst_health"], 4))
    else:
        properties.sort(key=lambda p: p["latest_activity"] or "", reverse=True)

    return render_template("portfolio.html",
                           properties=properties,
                           summary=data["summary"],
                           filter_by=filter_by,
                           sort_by=sort_by)


# ---------------------------------------------------------------------------
# Account: brief frequency
# ---------------------------------------------------------------------------

@app.route("/account/brief-frequency", methods=["POST"])
@login_required
def account_brief_frequency():
    """Update user's morning brief email frequency."""
    from src.db import execute_write

    freq = request.form.get("brief_frequency", "none")
    if freq not in ("none", "daily", "weekly"):
        freq = "none"

    execute_write(
        "UPDATE users SET brief_frequency = %s WHERE user_id = %s",
        (freq, g.user["user_id"]),
    )

    label = {"none": "Off", "daily": "Daily", "weekly": "Weekly"}[freq]
    return f'<span style="color:var(--success);">Saved: {label}</span>'


@app.route("/account/voice-style", methods=["POST"])
@login_required
def account_voice_style():
    """Save user's voice & style preferences for AI response generation."""
    from src.db import execute_write

    voice_style = request.form.get("voice_style", "").strip()

    # Limit to 2000 chars
    if len(voice_style) > 2000:
        voice_style = voice_style[:2000]

    execute_write(
        "UPDATE users SET voice_style = %s WHERE user_id = %s",
        (voice_style or None, g.user["user_id"]),
    )

    if voice_style:
        return '<span style="color:var(--success);">Saved — I\'ll use this style in future responses.</span>'
    return '<span style="color:var(--text-muted);">Cleared — using default style.</span>'


# ---------------------------------------------------------------------------
# Admin: send invite
# ---------------------------------------------------------------------------

@app.route("/admin/send-invite", methods=["POST"])
@login_required
def admin_send_invite():
    """Send an invite email with a code to a recipient. Admin only."""
    if not g.user.get("is_admin"):
        abort(403)

    from web.auth import INVITE_CODES, validate_invite_code, BASE_URL

    to_email = request.form.get("to_email", "").strip().lower()
    invite_code = request.form.get("invite_code", "").strip()
    message = request.form.get("message", "").strip()[:500]
    cohort = request.form.get("cohort", "friends").strip()

    if not to_email or "@" not in to_email:
        return '<span style="color:var(--error);">Invalid email address.</span>'

    if not validate_invite_code(invite_code):
        return '<span style="color:var(--error);">Invalid invite code.</span>'

    # Cohort-specific subject lines
    COHORT_SUBJECTS = {
        "friends": "Hey! You're invited to try sfpermits.ai",
        "testers": "You're invited to beta test sfpermits.ai",
        "consultants": "Invitation: Join sfpermits.ai's Professional Network",
        "custom": "You're invited to sfpermits.ai",
    }
    subject = COHORT_SUBJECTS.get(cohort, COHORT_SUBJECTS["friends"])

    # Render invite email
    sender_name = g.user.get("display_name") or g.user["email"]
    html_body = render_template(
        "invite_email.html",
        base_url=BASE_URL,
        invite_code=invite_code,
        sender_name=sender_name,
        message=message,
        cohort=cohort,
    )

    # Send via SMTP (or log in dev mode)
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_from = os.environ.get("SMTP_FROM", "noreply@sfpermits.ai")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    log = logging.getLogger(__name__)

    if not smtp_host:
        log.info(
            "Invite (dev mode): would send to %s with code %s cohort=%s",
            to_email, invite_code, cohort,
        )
        return (
            f'<span style="color:var(--success);">Dev mode: invite logged for '
            f'{to_email} with code {invite_code}</span>'
        )

    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"SF Permits AI <{smtp_from}>"
        msg["To"] = to_email
        plain_text = f"You've been invited to sfpermits.ai!\n\n"
        if message:
            plain_text += f"{sender_name} says: {message}\n\n"
        plain_text += f"Your invite code: {invite_code}\n\n"
        plain_text += f"Sign up at: {BASE_URL}/auth/login\n"
        msg.set_content(plain_text)
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass or "")
            server.send_message(msg)

        log.info("Invite sent to %s with code %s cohort=%s", to_email, invite_code, cohort)
        return f'<span style="color:var(--success);">Invite sent to {to_email}</span>'
    except Exception as e:
        log.exception("Failed to send invite to %s", to_email)
        return f'<span style="color:var(--error);">Failed to send: {e}</span>'


# ---------------------------------------------------------------------------
# Feedback submission + admin queue
# ---------------------------------------------------------------------------

@app.route("/feedback/submit", methods=["POST"])
def feedback_submit():
    """Submit feedback (bug/suggestion/question). Works for logged-in and anon users."""
    from web.activity import submit_feedback

    feedback_type = request.form.get("feedback_type", "suggestion")
    message = request.form.get("message", "").strip()
    page_url = request.form.get("page_url", "")
    screenshot_data = request.form.get("screenshot_data", "").strip() or None

    if not message or len(message) < 3:
        return '<span style="color:var(--error);">Please enter a message.</span>'

    # Validate screenshot data if provided
    if screenshot_data:
        if not screenshot_data.startswith("data:image/"):
            screenshot_data = None
        elif len(screenshot_data) > 5 * 1024 * 1024:
            screenshot_data = None

    user_id = g.user["user_id"] if g.user else None
    submit_feedback(user_id, feedback_type, message, page_url or None,
                    screenshot_data=screenshot_data)

    return (
        '<span style="color:var(--success);">Thanks for the feedback! '
        'We\'ll review it soon.</span>'
    )


@app.route("/feedback/draft-edit", methods=["POST"])
def feedback_draft_edit():
    """Capture an expert's edits to an AI-generated draft response.

    Stores the (query, original, edited) tuple as an 'amy'-tier RAG chunk
    so future similar queries benefit from the expert's corrections.
    """
    original_query = request.form.get("original_query", "").strip()
    ai_draft = request.form.get("ai_draft", "").strip()
    edited_version = request.form.get("edited_version", "").strip()

    if not edited_version or len(edited_version) < 10:
        return '<span style="color:var(--error, #ef4444);">Edited version too short.</span>'

    if not original_query:
        return '<span style="color:var(--error, #ef4444);">Missing original query.</span>'

    # Build a learning note that captures the correction
    learning_note = (
        f"EXPERT CORRECTION for query: \"{original_query}\"\n\n"
        f"The AI-generated response was edited by the expert. "
        f"The expert's preferred version:\n\n{edited_version}"
    )

    user_id = g.user["user_id"] if g.user else None

    try:
        from src.rag.store import insert_single_note
        insert_single_note(learning_note, {
            "added_by_user_id": user_id,
            "query_context": original_query,
            "source": "draft_edit",
            "edit_type": "correction",
        })

        # Also log to activity
        from web.activity import log_activity
        log_activity(user_id, "draft_edit", {
            "query": original_query[:200],
            "had_changes": True,
        })

        return (
            '<span style="color:var(--success, #34d399); font-weight:600;">'
            '&#10003; Got it — I\'ll learn from your edits for next time.</span>'
        )
    except Exception as e:
        logging.error("Failed to save draft edit: %s", e)
        return f'<span style="color:var(--error, #ef4444);">Error saving: {e}</span>'


@app.route("/feedback/draft-good", methods=["POST"])
def feedback_draft_good():
    """Record that an AI-generated draft was used as-is (positive signal).

    This is a lightweight positive reinforcement signal — no RAG chunk needed,
    just an activity log entry.
    """
    original_query = request.form.get("original_query", "").strip()
    ai_draft = request.form.get("ai_draft", "").strip()

    user_id = g.user["user_id"] if g.user else None

    try:
        from web.activity import log_activity
        log_activity(user_id, "draft_used_as_is", {
            "query": original_query[:200],
        })

        return (
            '<span style="color:var(--success, #34d399);">'
            '&#10003; Thanks! Good to know that worked well.</span>'
        )
    except Exception as e:
        logging.error("Failed to log draft-good: %s", e)
        return '<span style="color:var(--success, #34d399);">&#10003; Noted!</span>'


@app.route("/admin/feedback")
@login_required
def admin_feedback():
    """Admin feedback queue page."""
    if not g.user.get("is_admin"):
        abort(403)

    from web.activity import get_feedback_queue, get_feedback_counts
    status_filter = request.args.get("status")
    items = get_feedback_queue(status=status_filter)
    counts = get_feedback_counts()
    return render_template("admin_feedback.html", user=g.user,
                           items=items, counts=counts,
                           current_status=status_filter)


@app.route("/admin/feedback/update", methods=["POST"])
@login_required
def admin_feedback_update():
    """Update feedback status (HTMX)."""
    if not g.user.get("is_admin"):
        abort(403)

    from web.activity import update_feedback_status

    feedback_id = request.form.get("feedback_id")
    status = request.form.get("status", "reviewed")
    admin_note = request.form.get("admin_note", "").strip() or None

    if feedback_id:
        update_feedback_status(int(feedback_id), status, admin_note)
        # Award points on resolution
        if status == "resolved":
            from web.activity import award_points
            first_reporter = request.form.get("first_reporter") == "on"
            award_points(int(feedback_id), first_reporter=first_reporter)

    status_label = {"new": "New", "reviewed": "Reviewed",
                    "resolved": "Resolved", "wontfix": "Won't fix"}.get(status, status)
    color = {"resolved": "var(--success)", "wontfix": "var(--text-muted)",
             "reviewed": "var(--warning)"}.get(status, "var(--accent)")
    return f'<span style="color:{color};">{status_label}</span>'


@app.route("/admin/feedback/<int:feedback_id>/screenshot")
@login_required
def admin_feedback_screenshot(feedback_id):
    """Serve feedback screenshot as image (admin only)."""
    if not g.user.get("is_admin"):
        abort(403)

    from web.activity import get_feedback_screenshot
    import base64

    data_url = get_feedback_screenshot(feedback_id)
    if not data_url:
        abort(404)

    try:
        header, encoded = data_url.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0]
        image_bytes = base64.b64decode(encoded)
    except Exception:
        abort(400)

    return Response(image_bytes, mimetype=mime_type)


@app.route("/admin/activity")
@login_required
def admin_activity():
    """Admin activity feed page."""
    if not g.user.get("is_admin"):
        abort(403)

    from web.activity import get_recent_activity, get_activity_stats
    action_filter = request.args.get("action") or None
    user_id_filter_str = request.args.get("user_id") or None
    user_id_filter = int(user_id_filter_str) if user_id_filter_str else None
    activity = get_recent_activity(limit=100, action_filter=action_filter, user_id_filter=user_id_filter)
    stats = get_activity_stats(hours=24)
    # Build a minimal users list from activity entries for the filter dropdown
    seen_ids: set = set()
    users = []
    for entry in activity:
        uid = entry.get("user_id")
        if uid and uid not in seen_ids:
            seen_ids.add(uid)
            users.append({"user_id": uid,
                          "display_name": entry.get("display_name") or entry.get("email") or str(uid),
                          "email": entry.get("email") or ""})
    return render_template("admin_activity.html", user=g.user,
                           activity=activity, stats=stats,
                           action_filter=action_filter,
                           user_id_filter=user_id_filter,
                           users=users)


@app.route("/admin/ops")
@login_required
def admin_ops():
    """Admin operations hub — pipeline health + data quality."""
    if not g.user.get("is_admin"):
        abort(403)
    return render_template("admin_ops.html", user=g.user, active_page="admin")


@app.route("/admin/ops/fragment/<tab>")
@login_required
def admin_ops_fragment(tab):
    """HTMX fragment endpoints for admin ops hub tabs."""
    if not g.user.get("is_admin"):
        abort(403)

    if tab == "pipeline":
        import signal

        class _Timeout(Exception):
            pass

        def _alarm(signum, frame):
            raise _Timeout()

        from web.velocity_dashboard import get_dashboard_data
        user_id = g.user["user_id"] if g.user else None
        try:
            old_handler = signal.signal(signal.SIGALRM, _alarm)
            signal.alarm(30)  # 30s timeout for heavy pipeline queries
            data = get_dashboard_data(user_id=user_id)
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        except _Timeout:
            signal.signal(signal.SIGALRM, old_handler)
            return ('<div style="text-align:center;padding:60px 20px;color:var(--text-muted);">'
                    '<p style="font-size:1.1rem;margin-bottom:8px;">Pipeline Health is loading slowly</p>'
                    '<p>The 3.9M-row addenda table queries are taking longer than 30s.</p>'
                    '<p style="margin-top:12px;"><a href="/dashboard/bottlenecks" '
                    'style="color:var(--accent);">Open full-page Pipeline dashboard &rarr;</a></p>'
                    '</div>')
        return render_template("velocity_dashboard.html", data=data,
                               active_page="admin", fragment=True)

    elif tab == "quality":
        from web.data_quality import run_all_checks
        checks = run_all_checks()
        return render_template("fragments/admin_quality.html", checks=checks)

    elif tab == "activity":
        from web.activity import get_recent_activity, get_activity_stats
        action_filter = request.args.get("action") or None
        user_id_filter_str = request.args.get("user_id") or None
        user_id_filter = int(user_id_filter_str) if user_id_filter_str else None
        activity = get_recent_activity(limit=100, action_filter=action_filter,
                                        user_id_filter=user_id_filter)
        stats = get_activity_stats(hours=24)
        seen_ids: set = set()
        users = []
        for entry in activity:
            uid = entry.get("user_id")
            if uid and uid not in seen_ids:
                seen_ids.add(uid)
                users.append({"user_id": uid,
                              "display_name": entry.get("display_name") or entry.get("email") or str(uid),
                              "email": entry.get("email") or "",
                              "action_count": sum(1 for a in activity if a.get("user_id") == uid)})
        return render_template("admin_activity.html", user=g.user,
                               activity=activity, stats=stats,
                               action_filter=action_filter,
                               user_id_filter=user_id_filter,
                               users=users, fragment=True)

    elif tab == "feedback":
        from web.activity import get_feedback_queue, get_feedback_counts
        status_filter = request.args.get("status")
        items = get_feedback_queue(status=status_filter)
        counts = get_feedback_counts()
        return render_template("admin_feedback.html", user=g.user,
                               items=items, counts=counts,
                               current_status=status_filter, fragment=True)

    elif tab == "sources":
        from web.sources import get_source_inventory
        inventory = get_source_inventory()
        return render_template("admin_sources.html", user=g.user,
                               fragment=True, **inventory)

    elif tab == "regulatory":
        from web.regulatory_watch import list_watch_items
        status_filter = request.args.get("status")
        items = list_watch_items(status_filter=status_filter)
        return render_template("admin_regulatory_watch.html", user=g.user,
                               items=items, current_status=status_filter,
                               fragment=True)

    else:
        abort(404)


@app.route("/admin/sources")
@login_required
def admin_sources():
    """Knowledge source inventory — printable reference for Amy."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.sources import get_source_inventory
    inventory = get_source_inventory()
    return render_template("admin_sources.html", user=g.user, **inventory)


@app.route("/admin/regulatory-watch")
@login_required
def admin_regulatory_watch():
    """Admin regulatory watch list."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.regulatory_watch import list_watch_items
    status_filter = request.args.get("status")
    items = list_watch_items(status_filter=status_filter)
    return render_template("admin_regulatory_watch.html", user=g.user,
                           items=items, current_status=status_filter)


@app.route("/admin/regulatory-watch/create", methods=["POST"])
@login_required
def admin_regulatory_watch_create():
    """Create a new regulatory watch item."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.regulatory_watch import create_watch_item

    sections_raw = request.form.get("affected_sections", "").strip()
    concepts_raw = request.form.get("semantic_concepts", "").strip()
    affected = [s.strip() for s in sections_raw.split(",") if s.strip()] if sections_raw else None
    concepts = [s.strip() for s in concepts_raw.split(",") if s.strip()] if concepts_raw else None

    create_watch_item(
        title=request.form["title"],
        source_type=request.form["source_type"],
        source_id=request.form["source_id"],
        description=request.form.get("description", "").strip() or None,
        status=request.form.get("status", "monitoring"),
        impact_level=request.form.get("impact_level", "moderate"),
        affected_sections=affected,
        semantic_concepts=concepts,
        url=request.form.get("url", "").strip() or None,
        filed_date=request.form.get("filed_date", "").strip() or None,
        effective_date=request.form.get("effective_date", "").strip() or None,
        notes=request.form.get("notes", "").strip() or None,
    )
    return redirect(url_for("admin_regulatory_watch"))


@app.route("/admin/regulatory-watch/<int:watch_id>/update", methods=["POST"])
@login_required
def admin_regulatory_watch_update(watch_id):
    """Update a regulatory watch item status."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.regulatory_watch import update_watch_item
    status = request.form.get("status")
    if status:
        update_watch_item(watch_id, status=status)
    return redirect(url_for("admin_regulatory_watch"))


@app.route("/admin/regulatory-watch/<int:watch_id>/delete", methods=["POST"])
@login_required
def admin_regulatory_watch_delete(watch_id):
    """Delete a regulatory watch item."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.regulatory_watch import delete_watch_item
    delete_watch_item(watch_id)
    return redirect(url_for("admin_regulatory_watch"))


# ---------------------------------------------------------------------------
# Admin: Knowledge capture
# ---------------------------------------------------------------------------

@app.route("/admin/knowledge/quiz")
@login_required
def admin_knowledge_quiz():
    """Serve the next quiz question with current RAG answer (admin only)."""
    if not (g.user.get("is_admin") or g.user.get("role") in ("admin", "consultant")):
        abort(403)

    idx = request.args.get("idx", 0, type=int)
    if idx < 0 or idx >= len(QUIZ_QUESTIONS):
        return '<div style="color:var(--text-muted);padding:16px;">All questions completed! Check back later for new ones.</div>'

    question = QUIZ_QUESTIONS[idx]

    # Get current RAG answer and synthesize a natural-language response
    rag_results = _try_rag_retrieval(question)
    current_answer_html = ""
    if rag_results:
        context_parts = []
        for r in rag_results[:3]:
            content = r.get("content", "")
            source = r.get("source_file", "")
            if source:
                content = f"[Source: {source}]\n{content}"
            context_parts.append(content)
        rag_context = "\n\n---\n\n".join(context_parts)

        # Synthesize with AI (same as /ask endpoint) for human-readable answer
        ai_text = _synthesize_with_ai(question, rag_context, "professional")
        if ai_text:
            current_answer_html = md_to_html(ai_text)
        else:
            # Fallback: cleaned chunks if AI unavailable
            parts = [
                _clean_chunk_content(r.get("content", ""), r.get("source_file", ""))
                for r in rag_results[:3]
            ]
            current_answer_html = md_to_html("\n\n---\n\n".join(parts))

    return render_template(
        "fragments/knowledge_quiz.html",
        question=question,
        question_idx=idx,
        total_questions=len(QUIZ_QUESTIONS),
        current_answer_html=current_answer_html,
    )


@app.route("/admin/knowledge/quiz/submit", methods=["POST"])
@login_required
def admin_knowledge_quiz_submit():
    """Accept a quiz improvement and save as expert note."""
    if not (g.user.get("is_admin") or g.user.get("role") in ("admin", "consultant")):
        abort(403)

    question = request.form.get("question", "")
    improvement = request.form.get("improvement", "").strip()
    idx = request.form.get("idx", 0, type=int)

    if not improvement or len(improvement) < 10:
        return '<span style="color:var(--error, #ef4444);">Answer too short (minimum 10 characters).</span>'

    try:
        from src.rag.store import insert_single_note
        insert_single_note(improvement, {
            "added_by_user_id": g.user["user_id"],
            "firm_id": g.user.get("firm_id"),
            "query_context": question,
            "source": "quiz",
        })

        # Re-retrieve to show updated answer
        rag_results = _try_rag_retrieval(question)
        updated_html = ""
        if rag_results:
            parts = []
            for r in rag_results[:3]:
                content = _clean_chunk_content(r.get("content", ""), r.get("source_file", ""))
                parts.append(content)
            updated_html = md_to_html("\n\n---\n\n".join(parts))

        next_idx = idx + 1
        return render_template_string("""
            <div style="color:var(--success, #34d399); font-weight:600; margin-bottom:12px;">
                Got it! Here's how your answer appears now:
            </div>
            <div style="padding:12px; background:var(--surface-2, #252834); border-radius:8px; margin-bottom:12px; font-size:0.9rem;">
                {{ updated_html | safe }}
            </div>
            {% if next_idx < total %}
            <button type="button"
                hx-get="/admin/knowledge/quiz?idx={{ next_idx }}"
                hx-target="#quiz-card"
                hx-swap="innerHTML"
                class="btn" style="padding:10px 24px; width:auto; font-size:0.85rem;">
                Next Question &rarr;
            </button>
            {% else %}
            <div style="color:var(--text-muted); font-size:0.85rem;">
                All questions completed! Check back later for new ones.
            </div>
            {% endif %}
        """, updated_html=updated_html, next_idx=next_idx, total=len(QUIZ_QUESTIONS))
    except Exception as e:
        logging.error("Failed to save quiz answer: %s", e)
        return f'<span style="color:var(--error, #ef4444);">Error: {e}</span>'


@app.route("/admin/knowledge/add-note", methods=["POST"])
@login_required
def admin_add_note():
    """Add an expert note to the RAG knowledge base (admin/consultant only)."""
    user = g.user
    if not (user.get("is_admin") or user.get("role") in ("admin", "consultant")):
        abort(403)

    note_text = request.form.get("note_text", "").strip()
    query_context = request.form.get("query_context", "")

    if not note_text or len(note_text) < 10:
        return '<span style="color:var(--error, #ef4444);">Note too short (minimum 10 characters).</span>'

    try:
        from src.rag.store import insert_single_note
        insert_single_note(note_text, {
            "added_by_user_id": user["user_id"],
            "firm_id": user.get("firm_id"),
            "query_context": query_context,
        })
        return '<span style="color:var(--success, #34d399);">Note saved — it will appear in future answers.</span>'
    except Exception as e:
        logging.error("Failed to save expert note: %s", e)
        return f'<span style="color:var(--error, #ef4444);">Error saving note: {e}</span>'


# ---------------------------------------------------------------------------
# Voice calibration — moved from /admin/ to /account/ (available to all users)
# Old /admin/ URLs redirect for bookmarks.
# ---------------------------------------------------------------------------

@app.route("/admin/voice-calibration")
@login_required
def admin_voice_calibration_redirect():
    """Redirect old admin URL to new account URL."""
    return redirect("/account/voice-calibration", code=301)


@app.route("/admin/voice-calibration/save", methods=["POST"])
@login_required
def admin_voice_calibration_save_redirect():
    """Redirect old admin POST to new account URL (307 preserves POST)."""
    return redirect("/account/voice-calibration/save", code=307)


@app.route("/admin/voice-calibration/reset", methods=["POST"])
@login_required
def admin_voice_calibration_reset_redirect():
    """Redirect old admin POST to new account URL (307 preserves POST)."""
    return redirect("/account/voice-calibration/reset", code=307)


@app.route("/account/voice-calibration")
@login_required
def account_voice_calibration():
    """Voice calibration page — rewrite templates in your voice."""
    from web.voice_calibration import seed_scenarios, get_calibrations_by_audience, get_calibration_stats
    from web.voice_templates import AUDIENCES, SITUATIONS, AUDIENCE_MAP, SITUATION_MAP

    # Auto-seed scenarios on first visit
    seed_scenarios(g.user["user_id"])

    grouped = get_calibrations_by_audience(g.user["user_id"])
    stats = get_calibration_stats(g.user["user_id"])

    return render_template("voice_calibration.html",
                           user=g.user,
                           grouped=grouped,
                           stats=stats,
                           audiences=AUDIENCES,
                           audience_map=AUDIENCE_MAP,
                           situation_map=SITUATION_MAP)


@app.route("/account/voice-calibration/save", methods=["POST"])
@login_required
def account_voice_calibration_save():
    """Save the expert's rewritten version for a scenario (HTMX)."""
    from web.voice_calibration import save_calibration, get_calibration, get_calibration_stats

    scenario_key = request.form.get("scenario_key", "").strip()
    user_text = request.form.get("user_text", "").strip()

    if not scenario_key:
        return '<span style="color:var(--error);">Missing scenario key.</span>'
    if not user_text or len(user_text) < 20:
        return '<span style="color:var(--error);">Please write at least 20 characters.</span>'

    save_calibration(g.user["user_id"], scenario_key, user_text)

    # Return updated status + stats
    stats = get_calibration_stats(g.user["user_id"])
    return (
        f'<span style="color:var(--success, #34d399);">✓ Saved!</span>'
        f'<script>'
        f'document.getElementById("cal-progress").textContent='
        f'"{stats["calibrated"]} of {stats["total"]} done";'
        f'var badge = document.getElementById("badge-{scenario_key}");'
        f'if(badge) {{ badge.textContent = "✓ calibrated"; badge.style.color = "var(--success, #34d399)"; }}'
        f'</script>'
    )


@app.route("/account/voice-calibration/reset", methods=["POST"])
@login_required
def account_voice_calibration_reset():
    """Clear calibration for a scenario (HTMX)."""
    from web.voice_calibration import reset_calibration, get_calibration, get_calibration_stats

    scenario_key = request.form.get("scenario_key", "").strip()
    if not scenario_key:
        return '<span style="color:var(--error);">Missing scenario key.</span>'

    reset_calibration(g.user["user_id"], scenario_key)

    stats = get_calibration_stats(g.user["user_id"])
    return (
        f'<span style="color:var(--text-muted);">Reset — ready for rewrite.</span>'
        f'<script>'
        f'document.getElementById("cal-progress").textContent='
        f'"{stats["calibrated"]} of {stats["total"]} done";'
        f'var badge = document.getElementById("badge-{scenario_key}");'
        f'if(badge) {{ badge.textContent = "○ not yet"; badge.style.color = "var(--text-muted)"; }}'
        f'var ta = document.getElementById("ta-{scenario_key}");'
        f'if(ta) ta.value = "";'
        f'</script>'
    )


# ---------------------------------------------------------------------------
# Email unsubscribe
# ---------------------------------------------------------------------------

@app.route("/email/unsubscribe")
def email_unsubscribe():
    """One-click unsubscribe from email briefs."""
    from web.email_brief import verify_unsubscribe_token
    from src.db import execute_write

    uid = request.args.get("uid", type=int)
    token = request.args.get("token", "")
    email = request.args.get("email", "")

    # Token-based unsubscribe (from email links)
    if uid and token:
        from web.auth import get_user_by_id
        user = get_user_by_id(uid)
        if user and verify_unsubscribe_token(uid, user["email"], token):
            execute_write(
                "UPDATE users SET brief_frequency = 'none' WHERE user_id = %s",
                (uid,),
            )
            return render_template(
                "auth_login.html",
                message="You've been unsubscribed from email briefs. "
                        "You can re-enable them from your account page.",
            )

    # Email-based unsubscribe (List-Unsubscribe header)
    if email:
        from web.auth import get_user_by_email
        user = get_user_by_email(email)
        if user:
            execute_write(
                "UPDATE users SET brief_frequency = 'none' WHERE user_id = %s",
                (user["user_id"],),
            )
            return render_template(
                "auth_login.html",
                message="You've been unsubscribed from email briefs.",
            )

    return render_template(
        "auth_login.html",
        message="Invalid unsubscribe link.",
        message_type="error",
    ), 400


# ---------------------------------------------------------------------------
# Consultant Dashboard
# ---------------------------------------------------------------------------

@app.route("/consultants")
def consultants_page():
    """Consultant recommendation dashboard.

    Accepts optional query params from property report "Find a consultant" link:
      ?block=XXXX&lot=YYY&signal=recommended
    When present, pre-fills the form and auto-submits.
    """
    from src.db import query as db_query

    prefill = None
    block = request.args.get("block", "").strip()
    lot = request.args.get("lot", "").strip()
    signal = request.args.get("signal", "").strip()

    if block and lot:
        # Look up address and neighborhood from permits table
        addr = ""
        neighborhood = ""
        try:
            row = db_query(
                "SELECT street_number, street_name, neighborhood "
                "FROM permits WHERE block = %s AND lot = %s "
                "ORDER BY filed_date DESC LIMIT 1",
                (block, lot),
            )
            if row:
                addr = f"{row[0][0] or ''} {row[0][1] or ''}".strip()
                neighborhood = row[0][2] or ""
        except Exception:
            pass

        # Check if property has active complaints (for checkbox prefill)
        has_complaint = False
        try:
            c_row = db_query(
                "SELECT COUNT(*) FROM complaints "
                "WHERE block = %s AND lot = %s AND LOWER(status) = 'open'",
                (block, lot),
            )
            has_complaint = bool(c_row and c_row[0][0] > 0)
        except Exception:
            pass

        prefill = {
            "block": block,
            "lot": lot,
            "address": addr,
            "neighborhood": neighborhood,
            "signal": signal,
            "has_complaint": has_complaint,
        }

    return render_template("consultants.html",
                           neighborhoods=NEIGHBORHOODS,
                           prefill=prefill)


@app.route("/consultants/search", methods=["POST"])
def consultants_search():
    """Search for consultants and return HTMX fragment with results."""
    from src.tools.recommend_consultants import recommend_consultants, ScoredConsultant

    address = request.form.get("address", "").strip() or None
    block = request.form.get("block", "").strip() or None
    lot = request.form.get("lot", "").strip() or None
    neighborhood = request.form.get("neighborhood", "").strip() or None
    permit_type = request.form.get("permit_type", "").strip() or None
    has_complaint = request.form.get("has_active_complaint") == "on"
    needs_planning = request.form.get("needs_planning") == "on"
    sort_by = request.form.get("sort_by", "score").strip()

    try:
        # recommend_consultants is async, returns markdown string
        # But for the dashboard we want structured data — call the internal
        # scoring logic directly
        from src.tools.recommend_consultants import (
            _query_consultants, _query_relationships,
            _load_registry, _get_registered_names,
        )
        from src.db import get_connection, BACKEND
        from datetime import date

        conn = get_connection()
        try:
            consultants_raw = _query_consultants(conn, min_permits=20)
            if not consultants_raw:
                return render_template(
                    "consultants.html",
                    neighborhoods=NEIGHBORHOODS,
                    error="No consultants found with sufficient activity.",
                )

            max_permits = max(e["permit_count"] for e in consultants_raw)
            registered_names = _get_registered_names()
            registry = _load_registry()

            # Check which consultants have worked at this address (block/lot)
            address_match_ids: set[int] = set()
            if block and lot:
                try:
                    from src.db import query as db_query
                    ph = "%s" if BACKEND == "postgres" else "?"
                    addr_rows = db_query(
                        f"SELECT DISTINCT e.entity_id "
                        f"FROM contacts c JOIN entities e ON c.entity_id = e.entity_id "
                        f"WHERE c.block = {ph} AND c.lot = {ph} "
                        f"AND e.entity_type = 'consultant'",
                        (block, lot),
                    )
                    address_match_ids = {r[0] for r in addr_rows} if addr_rows else set()
                except Exception:
                    pass

            scored = []

            for exp in consultants_raw:
                s = ScoredConsultant(
                    entity_id=exp["entity_id"],
                    name=exp["canonical_name"],
                    firm=exp["canonical_firm"] or "",
                    permit_count=exp["permit_count"],
                )

                # Volume score (0-25)
                volume_score = (exp["permit_count"] / max_permits) * 25 if max_permits > 0 else 0
                s.breakdown["volume"] = round(volume_score, 1)
                s.score += volume_score

                # Get relationships
                rels = _query_relationships(conn, exp["entity_id"])

                total_rel_permits = 0
                residential_permits = 0
                all_neighborhoods = set()
                latest_date = ""
                network_partners = 0

                for r in rels:
                    shared = r["shared_permits"]
                    total_rel_permits += shared
                    ptypes = (r["permit_types"] or "").lower()
                    if "a" in ptypes.split(",") or "additions" in ptypes:
                        residential_permits += shared
                    if r["neighborhoods"]:
                        for n in r["neighborhoods"].split(","):
                            n = n.strip()
                            if n:
                                all_neighborhoods.add(n)
                    if r["date_range_end"] and r["date_range_end"] > latest_date:
                        latest_date = r["date_range_end"]
                    if shared >= 3:
                        network_partners += 1

                s.neighborhoods = sorted(all_neighborhoods)
                s.date_range_end = latest_date
                s.network_size = network_partners

                # Specialization (0-25)
                if total_rel_permits > 0:
                    spec_score = (residential_permits / total_rel_permits) * 25
                else:
                    spec_score = 12.5
                s.breakdown["specialization"] = round(spec_score, 1)
                s.score += spec_score

                # Neighborhood (0-20)
                hood_match = False
                if neighborhood:
                    target_lower = neighborhood.lower()
                    hood_match = any(
                        target_lower in n.lower() or n.lower() in target_lower
                        for n in all_neighborhoods
                    )
                    hood_score = 20 if hood_match else 0
                else:
                    hood_score = 10
                s.breakdown["neighborhood"] = round(hood_score, 1)
                s.score += hood_score

                # Recency (0-15)
                recency_score = 0
                if latest_date:
                    try:
                        end_date = date.fromisoformat(latest_date[:10])
                        months_ago = (date.today() - end_date).days / 30
                        if months_ago <= 6:
                            recency_score = 15
                        elif months_ago <= 12:
                            recency_score = 10
                        elif months_ago <= 24:
                            recency_score = 5
                    except (ValueError, TypeError):
                        pass
                s.breakdown["recency"] = round(recency_score, 1)
                s.score += recency_score

                # Network (0-15)
                if network_partners >= 10:
                    network_score = 15
                elif network_partners >= 5:
                    network_score = 10
                elif network_partners >= 2:
                    network_score = 5
                else:
                    network_score = 0
                s.breakdown["network"] = round(network_score, 1)
                s.score += network_score

                # Bonuses
                if has_complaint and exp["permit_count"] >= 50 and len(all_neighborhoods) >= 3:
                    s.breakdown["complaint_bonus"] = 10
                    s.score += 10
                if needs_planning and network_partners >= 5:
                    s.breakdown["planning_bonus"] = 10
                    s.score += 10

                name_lower = exp["canonical_name"].lower()
                if name_lower in registered_names:
                    s.is_registered = True
                    s.breakdown["ethics_bonus"] = 5
                    s.score += 5
                    for c in registry.get("consultants", []):
                        if c.get("name", "").strip().lower() == name_lower:
                            s.contact_info = {
                                "email": c.get("email", ""),
                                "phone": c.get("phone", ""),
                            }
                            break

                # Address match bonus (+5) + badge
                if exp["entity_id"] in address_match_ids:
                    s.score += 5
                    s.breakdown["address_match"] = 5

                # Build smart badges list (stored as tuples: label, css_class)
                badges = []
                if exp["entity_id"] in address_match_ids:
                    badges.append(("Worked at this address", "badge-address"))
                if s.is_registered:
                    badges.append(("Ethics Registered", "badge-ethics"))
                if hood_match and neighborhood:
                    badges.append(("Neighborhood match", "badge-hood"))
                if exp["permit_count"] >= 100:
                    badges.append(("High volume", "badge-volume"))
                if network_partners >= 10:
                    badges.append(("Strong network", "badge-network"))
                if recency_score == 15:
                    badges.append(("Recently active", "badge-recent"))
                # Store badges on the dataclass via dynamic attr
                s.badges = badges  # type: ignore[attr-defined]

                scored.append(s)
        finally:
            conn.close()

        # Sort by user-selected criterion
        if sort_by == "permits":
            scored.sort(key=lambda x: x.permit_count, reverse=True)
        elif sort_by == "recency":
            scored.sort(key=lambda x: x.date_range_end or "", reverse=True)
        elif sort_by == "network":
            scored.sort(key=lambda x: x.network_size, reverse=True)
        else:  # default: score
            scored.sort(key=lambda x: x.score, reverse=True)

        top = scored[:10]

        return render_template(
            "consultants.html",
            neighborhoods=NEIGHBORHOODS,
            results=top,
            sort_by=sort_by,
        )

    except Exception as e:
        logging.error("Consultant search failed: %s", e)
        return render_template(
            "consultants.html",
            neighborhoods=NEIGHBORHOODS,
            error=f"Search failed: {e}",
        )


# Legacy route redirects (backward compatibility)
@app.route("/expediters")
def expediters_redirect():
    return redirect("/consultants" + ("?" + request.query_string.decode() if request.query_string else ""), 301)

@app.route("/expediters/search", methods=["POST"])
def expediters_search_redirect():
    return redirect("/consultants/search", 308)


# ---------------------------------------------------------------------------
# Property report — comprehensive parcel report with inline source links
# ---------------------------------------------------------------------------

RATE_LIMIT_MAX_REPORT = 10  # /report views per window
RATE_LIMIT_MAX_SHARE = 3    # /report share emails per window


@app.route("/report/<block>/<lot>")
def property_report(block, lot):
    """Comprehensive property report — public (no login required).

    Owner Mode: If the logged-in user's primary address matches the
    report address (or ?owner=1 is set), the report includes a
    Remediation Roadmap and extended consultant scoring.
    """
    from web.report import get_property_report
    from web.owner_mode import detect_owner
    from src.report_links import ReportLinks

    ip = request.remote_addr or "unknown"
    if _is_rate_limited(ip, RATE_LIMIT_MAX_REPORT):
        abort(429)

    block = block.strip()
    lot = lot.strip()
    if not block or not lot:
        abort(400)

    user = getattr(g, "user", None)
    explicit_toggle = request.args.get("owner", "").lower() in ("1", "true", "yes")

    try:
        # First pass without owner mode to get the address
        report = get_property_report(block, lot)

        # Detect owner from address match or explicit toggle
        is_owner = detect_owner(user, report.get("address", ""), explicit_toggle)

        # If owner detected, regenerate with Owner Mode extensions
        if is_owner:
            report = get_property_report(block, lot, is_owner=True)
    except Exception as e:
        logging.exception("Report generation failed for %s/%s", block, lot)
        return render_template(
            "report.html",
            report=None,
            error=f"Could not generate report: {e}",
            user=user,
            is_owner=False,
            links=ReportLinks,
        ), 500

    is_owner = report.get("is_owner", False)

    if not report.get("permits") and not report.get("complaints") and not report.get("property_profile"):
        return render_template(
            "report.html",
            report=report,
            error=f"No data found for Block {block}, Lot {lot}.",
            user=user,
            is_owner=is_owner,
            links=ReportLinks,
        ), 404

    return render_template(
        "report.html",
        report=report,
        user=user,
        is_owner=is_owner,
        links=ReportLinks,
    )


@app.route("/report/<block>/<lot>/share", methods=["POST"])
@login_required
def property_report_share(block, lot):
    """Email a property report to a specified address."""
    from web.report import get_property_report
    from src.report_links import ReportLinks
    import smtplib
    from email.message import EmailMessage

    ip = request.remote_addr or "unknown"
    if _is_rate_limited(ip, RATE_LIMIT_MAX_SHARE):
        return "<div class='flash error'>Rate limited — please try again in a minute.</div>", 429

    to_email = request.form.get("email", "").strip()
    if not to_email or "@" not in to_email:
        return "<div class='flash error'>Please enter a valid email address.</div>", 400

    personal_message = request.form.get("message", "").strip()[:500]

    block = block.strip()
    lot = lot.strip()

    try:
        report = get_property_report(block, lot)
    except Exception as e:
        logging.exception("Report generation failed for share: %s/%s", block, lot)
        return f"<div class='flash error'>Failed to generate report: {e}</div>", 500

    base_url = os.environ.get("BASE_URL", "http://localhost:5001")
    report_url = f"{base_url}/report/{block}/{lot}"

    is_owner = report.get("is_owner", False)
    sender_name = g.user.get("display_name") or g.user.get("email", "Someone")

    try:
        html_body = render_template(
            "report_email.html",
            report=report,
            report_url=report_url,
            base_url=base_url,
            is_owner=is_owner,
            links=ReportLinks,
            sender_name=sender_name,
            personal_message=personal_message,
        )
    except Exception as e:
        logging.exception("Report email render failed")
        return f"<div class='flash error'>Failed to render email: {e}</div>", 500

    # Send via SMTP (reuse brief email SMTP config)
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_from = os.environ.get("SMTP_FROM", "noreply@sfpermits.ai")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    address = report.get("address", f"Block {block}, Lot {lot}")
    subject = f"Property Report — {address} — sfpermits.ai"

    if not smtp_host:
        logging.info("SMTP not configured — would send report to %s (%d chars)", to_email, len(html_body))
        return "<div class='flash success'>Report sent (dev mode — no SMTP configured).</div>"

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"SF Permits AI <{smtp_from}>"
        msg["To"] = to_email
        plain_text = f"Property Report for {address}\n\n"
        if personal_message:
            plain_text += f"{sender_name} says: {personal_message}\n\n"
        plain_text += f"View the full report: {report_url}\n\n"
        plain_text += "--\nsfpermits.ai - San Francisco Building Permit Intelligence"
        msg.set_content(plain_text)
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass or "")
            server.send_message(msg)

        logging.info("Report email sent to %s for %s/%s", to_email, block, lot)
        return "<div class='flash success'>Report sent! Check your inbox.</div>"
    except Exception as e:
        logging.exception("Failed to send report email to %s", to_email)
        return f"<div class='flash error'>Failed to send email: {e}</div>", 500


# ---------------------------------------------------------------------------
# Portfolio — inspection timeline (HTMX lazy-load)
# ---------------------------------------------------------------------------

@app.route("/portfolio/timeline/<block>/<lot>")
def portfolio_timeline(block, lot):
    """HTMX: load inspection timeline for a property."""
    from web.portfolio import get_inspection_timeline
    timeline = get_inspection_timeline(block, lot)
    return render_template("fragments/inspection_timeline.html", timeline=timeline)


@app.route("/portfolio/discover", methods=["POST"])
@login_required
def portfolio_discover():
    """HTMX: search for consultant's permits by name/firm."""
    from web.portfolio import discover_portfolio

    name = request.form.get("name", "").strip()
    firm = request.form.get("firm", "").strip()

    if not name and not firm:
        return '<div style="color: var(--text-muted);">Enter a name or firm to search.</div>'

    discovery = discover_portfolio(name, firm or None)
    return render_template("fragments/discover_results.html", discovery=discovery)


@app.route("/portfolio/import", methods=["POST"])
@login_required
def portfolio_import():
    """HTMX: bulk-create watches from discovery results."""
    from web.portfolio import bulk_add_watches

    selected = request.form.getlist("selected")
    addresses = []
    for idx in selected:
        addresses.append({
            "street_number": request.form.get(f"snum_{idx}", ""),
            "street_name": request.form.get(f"sname_{idx}", ""),
            "block": request.form.get(f"block_{idx}", ""),
            "lot": request.form.get(f"lot_{idx}", ""),
        })

    count = bulk_add_watches(g.user["user_id"], addresses)
    return render_template("fragments/import_confirmation.html", count=count)


# ---------------------------------------------------------------------------
# Cron status endpoint — read-only, no auth required
# ---------------------------------------------------------------------------

@app.route("/cron/status")
def cron_status():
    """Read-only view of recent cron job results."""
    from src.db import query
    try:
        rows = query(
            "SELECT job_type, started_at, completed_at, status, "
            "soda_records, changes_inserted, inspections_updated, "
            "was_catchup, error_message "
            "FROM cron_log "
            "ORDER BY started_at DESC "
            "LIMIT 20"
        )
        jobs = []
        for r in rows:
            jobs.append({
                "job_type": r[0],
                "started_at": str(r[1]) if r[1] else None,
                "completed_at": str(r[2]) if r[2] else None,
                "status": r[3],
                "soda_records": r[4],
                "changes_inserted": r[5],
                "inspections_updated": r[6],
                "was_catchup": r[7],
                "error_message": r[8],
            })
        return jsonify({"ok": True, "jobs": jobs, "total": len(jobs)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "jobs": []})


# ---------------------------------------------------------------------------
# Cron endpoints — protected by bearer token
# ---------------------------------------------------------------------------


def _send_staleness_alert(warnings: list[str], nightly_result: dict) -> dict:
    """Send an email alert to admins when SODA data staleness is detected.

    Returns dict with send stats.
    """
    import smtplib
    from email.message import EmailMessage

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_from = os.environ.get("SMTP_FROM", "noreply@sfpermits.ai")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not all([smtp_host, smtp_user, smtp_pass]):
        logging.info("SMTP not configured — skipping staleness alert")
        return {"skipped": "smtp_not_configured"}

    from web.activity import get_admin_users
    admins = get_admin_users()
    if not admins:
        return {"skipped": "no_admins"}

    severity = "⚠️ Warning"
    if any("ALL sources returned 0" in w for w in warnings):
        severity = "🚨 Critical"
    elif any("even with extended lookback" in w for w in warnings):
        severity = "🚨 Alert"

    since = nightly_result.get("since", "?")
    lookback = nightly_result.get("lookback_days", "?")
    permits = nightly_result.get("soda_permits", 0)
    inspections = nightly_result.get("soda_inspections", 0)
    addenda = nightly_result.get("soda_addenda", 0)
    retry = nightly_result.get("retry_extended", False)

    warning_lines = "\n".join(f"  • {w}" for w in warnings)
    body = (
        f"{severity} — SODA Data Staleness Detected\n\n"
        f"The nightly job detected potential data freshness issues:\n\n"
        f"{warning_lines}\n\n"
        f"Details:\n"
        f"  Since: {since}\n"
        f"  Lookback: {lookback} days\n"
        f"  Auto-retry extended: {'Yes' if retry else 'No'}\n"
        f"  Permits: {permits}\n"
        f"  Inspections: {inspections}\n"
        f"  Addenda: {addenda}\n\n"
        f"If this persists, check https://data.sfgov.org for SODA API status.\n"
    )

    stats = {"total": len(admins), "sent": 0, "failed": 0}
    for admin in admins:
        email = admin.get("email")
        if not email:
            continue
        try:
            msg = EmailMessage()
            msg["Subject"] = f"sfpermits.ai {severity} — SODA data staleness"
            msg["From"] = smtp_from
            msg["To"] = email
            msg.set_content(body)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            stats["sent"] += 1
        except Exception:
            logging.exception("Failed to send staleness alert to %s", email)
            stats["failed"] += 1

    logging.info("Staleness alert: %d sent, %d failed", stats["sent"], stats["failed"])
    return stats


@app.route("/cron/nightly", methods=["POST"])
def cron_nightly():
    """Nightly delta fetch — detect permit changes via SODA API.

    Protected by CRON_SECRET bearer token. Designed to be called by
    Railway cron or external scheduler (e.g., cron-job.org) daily ~3am PT.
    """
    token = request.headers.get("Authorization", "")
    expected = f"Bearer {os.environ.get('CRON_SECRET', '')}"
    if not os.environ.get("CRON_SECRET") or token != expected:
        abort(403)

    from scripts.nightly_changes import run_nightly
    import json

    lookback = request.args.get("lookback", "1")
    try:
        lookback_days = max(1, min(int(lookback), 90))
    except ValueError:
        lookback_days = 1

    dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes")

    try:
        result = run_async(run_nightly(lookback_days=lookback_days, dry_run=dry_run))

        # Append feedback triage (non-fatal — failure doesn't fail nightly)
        triage_result = {}
        if not dry_run:
            try:
                from scripts.feedback_triage import run_triage, ADMIN_EMAILS
                from web.activity import get_admin_users
                ADMIN_EMAILS.update(
                    a["email"].lower() for a in get_admin_users() if a.get("email")
                )
                host = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost:5001")
                triage_result = run_triage(host, os.environ.get("CRON_SECRET", ""))
            except Exception as te:
                logging.error("Feedback triage failed (non-fatal): %s", te)
                triage_result = {"error": str(te)}

        # Cleanup expired plan analysis sessions (non-fatal)
        cleanup_result = {}
        if not dry_run:
            try:
                from web.plan_images import cleanup_expired
                from web.plan_jobs import cleanup_old_jobs
                sessions_deleted = cleanup_expired(hours=24)
                jobs_deleted = cleanup_old_jobs(days=30)
                count = sessions_deleted + jobs_deleted
                cleanup_result = {
                    "plan_sessions_deleted": sessions_deleted,
                    "plan_jobs_deleted": jobs_deleted,
                }
            except Exception as ce:
                logging.error("Plan session cleanup failed (non-fatal): %s", ce)
                cleanup_result = {"error": str(ce)}

        # Refresh station velocity baselines (non-fatal)
        velocity_result = {}
        if not dry_run:
            try:
                from web.station_velocity import refresh_station_velocity
                velocity_result = refresh_station_velocity()
            except Exception as ve:
                logging.error("Station velocity refresh failed (non-fatal): %s", ve)
                velocity_result = {"error": str(ve)}

        # Refresh reviewer-entity interaction graph (non-fatal)
        reviewer_result = {}
        if not dry_run:
            try:
                from web.reviewer_graph import refresh_reviewer_interactions
                reviewer_result = refresh_reviewer_interactions()
            except Exception as re_:
                logging.error("Reviewer graph refresh failed (non-fatal): %s", re_)
                reviewer_result = {"error": str(re_)}

        # Refresh operational knowledge chunks (non-fatal, runs after velocity)
        ops_chunks_result = {}
        if not dry_run:
            try:
                from web.ops_chunks import ingest_ops_chunks
                count = ingest_ops_chunks()
                ops_chunks_result = {"chunks": count}
            except Exception as oe:
                logging.error("Ops chunk ingestion failed (non-fatal): %s", oe)
                ops_chunks_result = {"error": str(oe)}

        # Send staleness alert email to admins if warnings detected
        staleness_alert_result = {}
        warnings = result.get("staleness_warnings", [])
        if warnings and not dry_run:
            try:
                staleness_alert_result = _send_staleness_alert(warnings, result)
            except Exception as se:
                logging.error("Staleness alert email failed (non-fatal): %s", se)
                staleness_alert_result = {"error": str(se)}

        return Response(
            json.dumps({
                "status": "ok", **result,
                "triage": triage_result,
                "cleanup": cleanup_result,
                "velocity": velocity_result,
                "reviewer_graph": reviewer_result,
                "ops_chunks": ops_chunks_result,
                "staleness_alert": staleness_alert_result,
            }, indent=2),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error("Nightly cron failed: %s", e)
        return Response(
            json.dumps({"status": "error", "error": str(e)}, indent=2),
            status=500,
            mimetype="application/json",
        )


@app.route("/cron/send-briefs", methods=["POST"])
def cron_send_briefs():
    """Send morning brief emails to subscribed users.

    Protected by CRON_SECRET bearer token. Designed to be called:
      - Daily at ~6am PT for daily subscribers
      - Monday at ~6am PT for weekly subscribers

    Query params:
      - frequency: 'daily' (default) or 'weekly'
    """
    token = request.headers.get("Authorization", "")
    expected = f"Bearer {os.environ.get('CRON_SECRET', '')}"
    if not os.environ.get("CRON_SECRET") or token != expected:
        abort(403)

    from web.email_brief import send_briefs
    import json

    frequency = request.args.get("frequency", "daily")
    if frequency not in ("daily", "weekly"):
        frequency = "daily"

    try:
        result = send_briefs(frequency)

        # Append triage report email to admins (non-fatal)
        triage_email_result = {}
        try:
            from web.email_triage import send_triage_reports
            triage_email_result = send_triage_reports()
        except Exception as te:
            logging.error("Triage report email failed (non-fatal): %s", te)
            triage_email_result = {"error": str(te)}

        return Response(
            json.dumps({
                "status": "ok", "frequency": frequency,
                **result, "triage_report": triage_email_result,
            }, indent=2),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error("Brief send cron failed: %s", e)
        return Response(
            json.dumps({"status": "error", "error": str(e)}, indent=2),
            status=500,
            mimetype="application/json",
        )


@app.route("/cron/rag-ingest", methods=["POST"])
def cron_rag_ingest():
    """Run RAG knowledge ingestion — chunk, embed, store to pgvector.

    Protected by CRON_SECRET bearer token. Call once after deploy to populate
    the vector store, or after knowledge base updates.

    Query params:
      - tier: 'tier1', 'tier2', 'tier3', 'tier4', 'ops', or 'all' (default: all)
      - clear: '0' to skip clearing (default: true for tier1-4, ops self-manages)
    """
    token = request.headers.get("Authorization", "")
    expected = f"Bearer {os.environ.get('CRON_SECRET', '')}"
    if not os.environ.get("CRON_SECRET") or token != expected:
        abort(403)

    import json as json_mod
    tier = request.args.get("tier", "all")
    skip_clear = request.args.get("clear", "").lower() in ("0", "false", "no")

    try:
        from src.rag.store import ensure_table, clear_tier, get_stats, rebuild_ivfflat_index
        from scripts.rag_ingest import ingest_tier1, ingest_tier2, ingest_tier3, ingest_tier4

        ensure_table()

        # Clear existing official (tier1-4) chunks before re-ingesting to
        # prevent duplicate accumulation.  Ops chunks self-manage via
        # clear_file() in ingest_ops_chunks().
        cleared = 0
        ingesting_static = tier in ("tier1", "tier2", "tier3", "tier4", "all")
        if ingesting_static and not skip_clear:
            cleared = clear_tier("official")

        total = 0
        if tier in ("tier1", "all"):
            total += ingest_tier1()
        if tier in ("tier2", "all"):
            total += ingest_tier2()
        if tier in ("tier3", "all"):
            total += ingest_tier3()
        if tier in ("tier4", "all"):
            total += ingest_tier4()
        if tier in ("ops", "all"):
            try:
                from web.ops_chunks import ingest_ops_chunks
                total += ingest_ops_chunks()
            except Exception as oe:
                logging.warning("Ops chunk ingestion failed (non-fatal): %s", oe)

        # Rebuild index after bulk insert
        if total > 0:
            try:
                rebuild_ivfflat_index()
            except Exception as ie:
                logging.warning("IVFFlat rebuild skipped: %s", ie)

        stats = get_stats()

        return Response(
            json_mod.dumps({
                "status": "ok",
                "chunks_ingested": total,
                "chunks_cleared": cleared,
                "tier": tier,
                "stats": stats,
            }, indent=2, default=str),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error("RAG ingestion cron failed: %s", e)
        return Response(
            json_mod.dumps({"status": "error", "error": str(e)}, indent=2),
            status=500,
            mimetype="application/json",
        )


# ---------------------------------------------------------------------------
# Data migration endpoints — push bulk DuckDB data to production Postgres
# ---------------------------------------------------------------------------

@app.route("/cron/migrate-schema", methods=["POST"])
def cron_migrate_schema():
    """Create bulk data tables (permits, contacts, etc.) on production Postgres.

    Protected by CRON_SECRET. Runs scripts/postgres_schema.sql which uses
    CREATE IF NOT EXISTS — safe to re-run.
    """
    _check_api_auth()
    import json as _json
    from pathlib import Path
    from src.db import get_connection, BACKEND

    if BACKEND != "postgres":
        return Response(
            _json.dumps({"ok": False, "error": "Not running on Postgres"}),
            status=400, mimetype="application/json",
        )

    schema_file = Path(__file__).parent.parent / "scripts" / "postgres_schema.sql"
    if not schema_file.exists():
        return Response(
            _json.dumps({"ok": False, "error": "Schema file not found"}),
            status=404, mimetype="application/json",
        )

    conn = get_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(schema_file.read_text())
        # Report created tables
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
            tables = [r[0] for r in cur.fetchall()]
        return Response(
            _json.dumps({"ok": True, "tables": tables}),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error("migrate-schema failed: %s", e)
        return Response(
            _json.dumps({"ok": False, "error": str(e)}),
            status=500, mimetype="application/json",
        )
    finally:
        conn.close()


@app.route("/cron/migrate-data", methods=["POST"])
def cron_migrate_data():
    """Accept a batch of rows for a bulk data table.

    Protected by CRON_SECRET. Accepts JSON body:
        {
            "table": "permits",
            "columns": ["col1", "col2", ...],
            "rows": [[val1, val2, ...], ...],
            "truncate": false  // optional, set true for first batch
        }

    Uses psycopg2.extras.execute_values for fast bulk insert.
    """
    _check_api_auth()
    import json as _json
    from src.db import get_connection, BACKEND

    if BACKEND != "postgres":
        return Response(
            _json.dumps({"ok": False, "error": "Not running on Postgres"}),
            status=400, mimetype="application/json",
        )

    ALLOWED_TABLES = {
        "permits", "contacts", "entities", "relationships",
        "inspections", "timeline_stats", "ingest_log",
        "addenda", "violations", "complaints", "businesses",
    }

    data = request.get_json(force=True)
    table = data.get("table", "")
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    do_truncate = data.get("truncate", False)

    if table not in ALLOWED_TABLES:
        return Response(
            _json.dumps({"ok": False, "error": f"Table '{table}' not allowed"}),
            status=400, mimetype="application/json",
        )
    if not columns or not rows:
        return Response(
            _json.dumps({"ok": False, "error": "columns and rows required"}),
            status=400, mimetype="application/json",
        )

    conn = get_connection()
    try:
        from psycopg2.extras import execute_values

        if do_truncate:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE {table} CASCADE")
            conn.commit()

        cols = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"INSERT INTO {table} ({cols}) VALUES %s",
                rows,
                template=f"({placeholders})",
                page_size=5000,
            )
        conn.commit()

        return Response(
            _json.dumps({"ok": True, "table": table, "rows_inserted": len(rows)}),
            mimetype="application/json",
        )
    except Exception as e:
        conn.rollback()
        logging.error("migrate-data failed for %s: %s", table, e)
        return Response(
            _json.dumps({"ok": False, "error": str(e)}),
            status=500, mimetype="application/json",
        )
    finally:
        conn.close()


def _check_api_auth():
    """Verify CRON_SECRET bearer token. Aborts 403 if invalid."""
    token = request.headers.get("Authorization", "")
    expected = f"Bearer {os.environ.get('CRON_SECRET', '')}"
    if not os.environ.get("CRON_SECRET") or token != expected:
        abort(403)


# ---------------------------------------------------------------------------
# API endpoints — CRON_SECRET-protected JSON access for CLI tools
# ---------------------------------------------------------------------------


@app.route("/api/feedback")
def api_feedback():
    """Get feedback items as JSON. Supports multi-status filtering.

    Query params:
      - status: one or more status values (e.g. ?status=new&status=reviewed)
      - limit: max items (default 100)
    """
    _check_api_auth()
    import json
    from web.activity import get_feedback_items_json

    statuses = request.args.getlist("status") or None
    limit = min(int(request.args.get("limit", "100")), 500)

    data = get_feedback_items_json(statuses=statuses, limit=limit)
    return Response(
        json.dumps(data, indent=2),
        mimetype="application/json",
    )


@app.route("/api/feedback/<int:feedback_id>/screenshot")
def api_feedback_screenshot(feedback_id):
    """Serve feedback screenshot image. CRON_SECRET auth."""
    _check_api_auth()
    import base64
    from web.activity import get_feedback_screenshot

    data_url = get_feedback_screenshot(feedback_id)
    if not data_url:
        abort(404)

    try:
        header, encoded = data_url.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0]
        image_bytes = base64.b64decode(encoded)
    except Exception:
        abort(400)

    return Response(image_bytes, mimetype=mime_type)


@app.route("/api/feedback/<int:feedback_id>", methods=["PATCH"])
def api_feedback_update(feedback_id):
    """Update feedback status via API. CRON_SECRET auth.

    JSON body:
      - status: "resolved", "reviewed", "wontfix", "new"
      - admin_note: optional string
    """
    _check_api_auth()
    import json
    from web.activity import update_feedback_status

    try:
        data = request.get_json(force=True)
    except Exception:
        return Response(
            json.dumps({"error": "Invalid JSON body"}),
            status=400,
            mimetype="application/json",
        )

    status = data.get("status")
    admin_note = data.get("admin_note")

    if not status:
        return Response(
            json.dumps({"error": "Missing 'status' field"}),
            status=400,
            mimetype="application/json",
        )

    ok = update_feedback_status(feedback_id, status, admin_note=admin_note)
    if not ok:
        return Response(
            json.dumps({"error": f"Invalid status '{status}'. Use: new, reviewed, resolved, wontfix"}),
            status=400,
            mimetype="application/json",
        )

    # Award points on resolution
    points_awarded = []
    if status == "resolved":
        from web.activity import award_points
        first_reporter = data.get("first_reporter", False)
        admin_bonus_val = data.get("admin_bonus", 0)
        try:
            admin_bonus_val = int(admin_bonus_val) if admin_bonus_val else 0
        except (ValueError, TypeError):
            admin_bonus_val = 0
        points_awarded = award_points(feedback_id,
                                       first_reporter=bool(first_reporter),
                                       admin_bonus=admin_bonus_val)

    return Response(
        json.dumps({
            "feedback_id": feedback_id, "status": status,
            "admin_note": admin_note, "points_awarded": points_awarded,
        }),
        mimetype="application/json",
    )


@app.route("/api/points/<int:user_id>")
def api_user_points(user_id):
    """Get point total and history for a user. CRON_SECRET auth."""
    _check_api_auth()
    import json
    from web.activity import get_user_points, get_points_history

    total = get_user_points(user_id)
    history = get_points_history(user_id, limit=20)
    for entry in history:
        if entry.get("created_at"):
            entry["created_at"] = entry["created_at"].isoformat()

    return Response(
        json.dumps({"user_id": user_id, "total": total, "history": history}),
        mimetype="application/json",
    )


# ---------------------------------------------------------------------------
# Database backup endpoint — pg_dump to local file or stdout
# ---------------------------------------------------------------------------

@app.route("/cron/seed-regulatory", methods=["POST"])
def cron_seed_regulatory():
    """Seed regulatory watch items from JSON array.

    Protected by CRON_SECRET bearer token.
    POST body: JSON array of items, each with: title, source_type, source_id,
    and optional: description, status, impact_level, affected_sections,
    semantic_concepts, url, filed_date, effective_date, notes.
    """
    _check_api_auth()
    import json as _json
    from web.regulatory_watch import create_watch_item

    items = request.get_json(force=True, silent=True)
    if not isinstance(items, list):
        return jsonify({"error": "Expected JSON array of items"}), 400

    created = []
    for item in items:
        try:
            wid = create_watch_item(
                title=item["title"],
                source_type=item["source_type"],
                source_id=item["source_id"],
                description=item.get("description"),
                status=item.get("status", "monitoring"),
                impact_level=item.get("impact_level", "moderate"),
                affected_sections=item.get("affected_sections"),
                semantic_concepts=item.get("semantic_concepts"),
                url=item.get("url"),
                filed_date=item.get("filed_date"),
                effective_date=item.get("effective_date"),
                notes=item.get("notes"),
            )
            created.append({"title": item["title"], "watch_id": wid})
        except Exception as exc:
            created.append({"title": item.get("title", "?"), "error": str(exc)})

    return jsonify({"created": len([c for c in created if "watch_id" in c]),
                     "items": created})


# ---------------------------------------------------------------------------

@app.route("/cron/backup", methods=["POST"])
def cron_backup():
    """Run pg_dump and store a timestamped backup.

    Protected by CRON_SECRET bearer token. Designed to be called daily
    by an external scheduler after the nightly refresh.

    Returns JSON with backup metadata (filename, size, row counts).
    """
    _check_api_auth()
    import json
    from scripts.db_backup import run_backup

    result = run_backup()
    status = 200 if result.get("ok") else 500
    return Response(json.dumps(result, indent=2), mimetype="application/json"), status


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)
