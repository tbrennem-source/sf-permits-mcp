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
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import timedelta
from functools import wraps
from flask import Flask, render_template, request, abort, Response, redirect, url_for, session, g
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

# 400 MB max upload for plan set PDFs (site permit addenda can be up to 350 MB)
app.config["MAX_CONTENT_LENGTH"] = 400 * 1024 * 1024


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
        # invite_code column (added in invite code feature)
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
        # Primary address columns (added for homeowner personalization)
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_street_number TEXT")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_street_name TEXT")
        # Fix inspections.id for auto-increment (needed for nightly upserts)
        # Original migration used INTEGER, but we need SERIAL for auto-increment
        try:
            cur.execute("""
                DO $$
                BEGIN
                    -- Create a sequence if it doesn't exist
                    IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE schemaname = 'public' AND sequencename = 'inspections_id_seq') THEN
                        CREATE SEQUENCE inspections_id_seq;
                        -- Set the sequence to start after the max existing id
                        PERFORM setval('inspections_id_seq', COALESCE((SELECT MAX(id) FROM inspections), 0) + 1);
                        -- Set the column default
                        ALTER TABLE inspections ALTER COLUMN id SET DEFAULT nextval('inspections_id_seq');
                    END IF;
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
        cur.close()
        conn.close()
        logging.getLogger(__name__).info("Startup migrations complete")
    except Exception as e:
        logging.getLogger(__name__).warning("Startup migration failed (non-fatal): %s", e)


_run_startup_migrations()


# ---------------------------------------------------------------------------
# Simple in-memory rate limiter (per-IP, resets on deploy — good enough for
# Phase 1 on a single dyno; swap for Redis-backed in Phase 2)
# ---------------------------------------------------------------------------
_rate_buckets: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT_WINDOW = 60        # seconds
RATE_LIMIT_MAX_ANALYZE = 10   # /analyze requests per window
RATE_LIMIT_MAX_VALIDATE = 5   # /validate requests per window (heavier)
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
_LOG_PATHS = {"/ask", "/analyze", "/validate", "/lookup", "/brief",
              "/account", "/auth/send-link", "/auth/verify",
              "/watch/add", "/watch/remove", "/feedback/submit",
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
            "/lookup": "lookup",
            "/brief": "brief_view",
            "/account": "account_view",
            "/auth/send-link": "login_request",
            "/watch/add": "watch_add",
            "/watch/remove": "watch_remove",
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
    """Health check endpoint — tests database connectivity."""
    from src.db import get_connection, BACKEND, DATABASE_URL
    info = {"status": "ok", "backend": BACKEND, "has_db_url": bool(DATABASE_URL)}
    try:
        conn = get_connection()
        try:
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM permits")
                    info["permits"] = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM timeline_stats")
                    info["timeline_stats"] = cur.fetchone()[0]
            else:
                info["permits"] = conn.execute("SELECT COUNT(*) FROM permits").fetchone()[0]
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
    from src.db import query, _ph
    ph = _ph()
    pattern = f"%{street_name}%"
    rows = query(
        f"SELECT block, lot FROM permits "
        f"WHERE street_number = {ph} "
        f"  AND ("
        f"    UPPER(street_name) LIKE UPPER({ph})"
        f"    OR UPPER(COALESCE(street_name, '') || ' ' || COALESCE(street_suffix, '')) LIKE UPPER({ph})"
        f"  ) "
        f"  AND block IS NOT NULL AND lot IS NOT NULL "
        f"LIMIT 1",
        (street_number, pattern, pattern),
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

    return render_template(
        "index.html",
        neighborhoods=NEIGHBORHOODS,
        user_report_url=user_report_url,
        user_report_address=user_report_address,
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
    expediter_name = request.form.get("expediter_name", "").strip() or None
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
    if contractor_name or architect_name or expediter_name:
        try:
            team_md = generate_team_profile(
                contractor=contractor_name,
                architect=architect_name,
                expediter=expediter_name,
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
            f"or hiring an experienced expediter to compress the timeline."
        )

    return timeline_md + note


@app.route("/validate", methods=["POST"])
def validate():
    """Upload a PDF plan set and validate against EPR requirements."""
    uploaded = request.files.get("planfile")
    if not uploaded or not uploaded.filename:
        return '<div class="error">Please select a PDF file to upload.</div>', 400

    filename = uploaded.filename
    if not filename.lower().endswith(".pdf"):
        return '<div class="error">Only PDF files are supported.</div>', 400

    is_addendum = request.form.get("is_addendum") == "on"

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
        ))
        result_html = md_to_html(result_md)
    except Exception as e:
        result_html = f'<div class="error">Validation error: {e}</div>'

    return render_template(
        "validate_results.html",
        result=result_html,
        filename=filename,
        filesize_mb=round(len(pdf_bytes) / (1024 * 1024), 1),
    )


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

    return render_template("lookup_results.html", result=result_html, report_url=report_url)


# ---------------------------------------------------------------------------
# Conversational search box — /ask endpoint
# ---------------------------------------------------------------------------

@app.route("/ask", methods=["POST"])
def ask():
    """Classify a free-text query and route to the appropriate handler."""
    query = request.form.get("q", "").strip()
    if not query:
        return '<div class="error">Please type a question or search term.</div>', 400

    # Classify intent
    result = classify_intent(query, [n for n in NEIGHBORHOODS if n])
    intent = result.intent
    entities = result.entities

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
    result_md = run_async(permit_lookup(permit_number=permit_num))
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
    address = entities.get("street_name")
    block = entities.get("block")
    lot = entities.get("lot")

    # Run both complaints and violations searches in parallel via the same
    # run_async helper. Build combined results.
    parts = []

    # Search complaints
    complaints_md = run_async(search_complaints(
        complaint_number=complaint_number,
        address=address,
        block=block,
        lot=lot,
    ))
    parts.append("## Complaints\n\n" + complaints_md)

    # Search violations
    violations_md = run_async(search_violations(
        complaint_number=complaint_number,
        address=address,
        block=block,
        lot=lot,
    ))
    parts.append("## Violations (NOVs)\n\n" + violations_md)

    combined_md = "\n\n---\n\n".join(parts)

    # Build label for display
    if complaint_number:
        label = f"Complaint #{complaint_number}"
    elif address:
        label = f"Complaints near {address}"
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
    elif address:
        watch_data = {
            "watch_type": "address",
            "street_name": address,
            "label": f"Near {address}",
        }

    ctx = {}
    if watch_data:
        ctx = _watch_context(watch_data)

    report_url = f"/report/{block}/{lot}" if block and lot else None
    return render_template(
        "search_results.html",
        query_echo=label,
        result_html=md_to_html(combined_md),
        report_url=report_url,
        **ctx,
    )


def _ask_address_search(query: str, entities: dict) -> str:
    """Handle address-based permit search."""
    street_number = entities.get("street_number")
    street_name = entities.get("street_name")
    result_md = run_async(permit_lookup(
        street_number=street_number,
        street_name=street_name,
    ))
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
        bl = _resolve_block_lot(street_number, street_name)
        if bl:
            report_url = f"/report/{bl[0]}/{bl[1]}"
    except Exception:
        pass
    return render_template(
        "search_results.html",
        query_echo=f"{street_number} {street_name}",
        result_html=md_to_html(result_md),
        show_primary_prompt=show_primary_prompt,
        prompt_street_number=street_number,
        prompt_street_name=street_name,
        report_url=report_url,
        **_watch_context(watch_data),
    )


def _ask_parcel_search(query: str, entities: dict) -> str:
    """Handle block/lot parcel search."""
    block = entities.get("block")
    lot = entities.get("lot")
    result_md = run_async(permit_lookup(block=block, lot=lot))
    watch_data = {
        "watch_type": "parcel",
        "block": block,
        "lot": lot,
        "label": f"Block {block}, Lot {lot}",
    }
    report_url = f"/report/{block}/{lot}" if block and lot else None
    return render_template(
        "search_results.html",
        query_echo=f"Block {block}, Lot {lot}",
        result_html=md_to_html(result_md),
        report_url=report_url,
        **_watch_context(watch_data),
    )


def _ask_person_search(query: str, entities: dict) -> str:
    """Handle person/company name search."""
    name = entities.get("person_name", "")
    role = entities.get("role")
    result_md = run_async(search_entity(name=name, entity_type=role))
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
    prefill_data = {
        "description": entities.get("description", query),
        "estimated_cost": entities.get("estimated_cost"),
        "square_footage": entities.get("square_footage"),
        "neighborhood": entities.get("neighborhood"),
    }
    # Remove None values for cleaner JSON
    prefill_data = {k: v for k, v in prefill_data.items() if v is not None}
    return render_template(
        "search_prefill.html",
        prefill_json=json.dumps(prefill_data),
    )


def _ask_validate_reveal(query: str) -> str:
    """Reveal the validation section."""
    return render_template("search_reveal.html", section="validate")


def _ask_general_question(query: str, entities: dict) -> str:
    """Answer a general question using the knowledge base."""
    kb = get_knowledge_base()
    scored = kb.match_concepts_scored(entities.get("query", query))

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
    watches = get_watches(g.user["user_id"])
    # Sort codes so the dropdown is consistent
    invite_codes = sorted(INVITE_CODES) if g.user.get("is_admin") else []
    # Admin stats for dashboard cards
    activity_stats = None
    feedback_counts = None
    if g.user.get("is_admin"):
        from web.activity import get_activity_stats, get_feedback_counts
        activity_stats = get_activity_stats(hours=24)
        feedback_counts = get_feedback_counts()
    return render_template("account.html", user=g.user, watches=watches,
                           invite_codes=invite_codes,
                           activity_stats=activity_stats,
                           feedback_counts=feedback_counts)


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
        lookback_days = max(1, min(int(lookback), 30))
    except ValueError:
        lookback_days = 1
    primary_addr = get_primary_address(g.user["user_id"])
    brief_data = get_morning_brief(g.user["user_id"], lookback_days,
                                   primary_address=primary_addr)
    return render_template("brief.html", user=g.user, brief=brief_data)


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
    message = request.form.get("message", "").strip()

    if not to_email or "@" not in to_email:
        return '<span style="color:var(--error);">Invalid email address.</span>'

    if not validate_invite_code(invite_code):
        return '<span style="color:var(--error);">Invalid invite code.</span>'

    # Render invite email
    sender_name = g.user.get("display_name") or g.user["email"]
    html_body = render_template(
        "invite_email.html",
        base_url=BASE_URL,
        invite_code=invite_code,
        sender_name=sender_name,
        message=message,
    )

    # Send via SMTP (or log in dev mode)
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_from = os.environ.get("SMTP_FROM", "noreply@sfpermits.ai")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not smtp_host:
        logging.getLogger(__name__).info(
            "Invite (dev mode): would send to %s with code %s", to_email, invite_code
        )
        return (
            f'<span style="color:var(--success);">Dev mode: invite logged for '
            f'{to_email} with code {invite_code}</span>'
        )

    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = "You're invited to sfpermits.ai"
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg.set_content(
            f"You've been invited to sfpermits.ai!\n\n"
            f"Your invite code: {invite_code}\n\n"
            f"Sign up at: {BASE_URL}/auth/login\n"
        )
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass or "")
            server.send_message(msg)

        return f'<span style="color:var(--success);">Invite sent to {to_email}</span>'
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to send invite to %s", to_email)
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

    if not message or len(message) < 3:
        return '<span style="color:var(--error);">Please enter a message.</span>'

    user_id = g.user["user_id"] if g.user else None
    submit_feedback(user_id, feedback_type, message, page_url or None)

    return (
        '<span style="color:var(--success);">Thanks for the feedback! '
        'We\'ll review it soon.</span>'
    )


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

    status_label = {"new": "New", "reviewed": "Reviewed",
                    "resolved": "Resolved", "wontfix": "Won't fix"}.get(status, status)
    color = {"resolved": "var(--success)", "wontfix": "var(--text-muted)",
             "reviewed": "var(--warning)"}.get(status, "var(--accent)")
    return f'<span style="color:{color};">{status_label}</span>'


@app.route("/admin/activity")
@login_required
def admin_activity():
    """Admin activity feed page."""
    if not g.user.get("is_admin"):
        abort(403)

    from web.activity import get_recent_activity, get_activity_stats
    activity = get_recent_activity(limit=100)
    stats = get_activity_stats(hours=24)
    return render_template("admin_activity.html", user=g.user,
                           activity=activity, stats=stats)


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
# Expediter Dashboard
# ---------------------------------------------------------------------------

@app.route("/expediters")
def expediters():
    """Expediter recommendation dashboard."""
    return render_template("expediters.html", neighborhoods=NEIGHBORHOODS)


@app.route("/expediters/search", methods=["POST"])
def expediters_search():
    """Search for expediters and return HTMX fragment with results."""
    from src.tools.recommend_expediters import recommend_expediters, ScoredExpediter

    address = request.form.get("address", "").strip() or None
    block = request.form.get("block", "").strip() or None
    lot = request.form.get("lot", "").strip() or None
    neighborhood = request.form.get("neighborhood", "").strip() or None
    permit_type = request.form.get("permit_type", "").strip() or None
    has_complaint = request.form.get("has_active_complaint") == "on"
    needs_planning = request.form.get("needs_planning") == "on"

    try:
        # recommend_expediters is async, returns markdown string
        # But for the dashboard we want structured data — call the internal
        # scoring logic directly
        from src.tools.recommend_expediters import (
            _query_expediters, _query_relationships,
            _load_registry, _get_registered_names,
        )
        from src.db import get_connection, BACKEND
        from datetime import date

        conn = get_connection()
        try:
            expediters_raw = _query_expediters(conn, min_permits=20)
            if not expediters_raw:
                return render_template(
                    "expediters.html",
                    neighborhoods=NEIGHBORHOODS,
                    error="No expediters found with sufficient activity.",
                )

            max_permits = max(e["permit_count"] for e in expediters_raw)
            registered_names = _get_registered_names()
            registry = _load_registry()
            scored = []

            for exp in expediters_raw:
                s = ScoredExpediter(
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

                scored.append(s)
        finally:
            conn.close()

        scored.sort(key=lambda x: x.score, reverse=True)
        top = scored[:10]

        return render_template(
            "expediters.html",
            neighborhoods=NEIGHBORHOODS,
            results=top,
        )

    except Exception as e:
        logging.error("Expediter search failed: %s", e)
        return render_template(
            "expediters.html",
            neighborhoods=NEIGHBORHOODS,
            error=f"Search failed: {e}",
        )


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
    Remediation Roadmap and extended expediter scoring.
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

    try:
        html_body = render_template(
            "report_email.html",
            report=report,
            report_url=report_url,
            is_owner=is_owner,
            links=ReportLinks,
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
        msg.set_content(
            f"Property Report for {address}\n\n"
            f"View the full report: {report_url}\n\n"
            f"--\nsfpermits.ai - San Francisco Building Permit Intelligence"
        )
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
# Cron endpoints — protected by bearer token
# ---------------------------------------------------------------------------

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
        lookback_days = max(1, min(int(lookback), 30))
    except ValueError:
        lookback_days = 1

    dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes")

    try:
        result = run_async(run_nightly(lookback_days=lookback_days, dry_run=dry_run))
        return Response(
            json.dumps({"status": "ok", **result}, indent=2),
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
        return Response(
            json.dumps({"status": "ok", "frequency": frequency, **result}, indent=2),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error("Brief send cron failed: %s", e)
        return Response(
            json.dumps({"status": "error", "error": str(e)}, indent=2),
            status=500,
            mimetype="application/json",
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)
