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
    "/admin", "/phpmyadmin", "/xmlrpc.php", "/config.php",
    "/actuator", "/.well-known/security.txt",
}


@app.before_request
def _security_filters():
    """Block scanners and apply rate limits."""
    path = request.path.lower()

    # Block known scanner probes with 404 (don't waste cycles)
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


@app.route("/")
def index():
    return render_template("index.html", neighborhoods=NEIGHBORHOODS)


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

    return render_template("lookup_results.html", result=result_html)


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
        existing = check_watch(g.user["user_id"], watch_data["watch_type"], **watch_data)
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

    return render_template(
        "search_results.html",
        query_echo=label,
        result_html=md_to_html(combined_md),
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
    return render_template(
        "search_results.html",
        query_echo=f"{street_number} {street_name}",
        result_html=md_to_html(result_md),
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
    return render_template(
        "search_results.html",
        query_echo=f"Block {block}, Lot {lot}",
        result_html=md_to_html(result_md),
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
    return render_template("auth_login.html")


@app.route("/auth/send-link", methods=["POST"])
def auth_send_link():
    """Create user if needed, generate magic link, send/display it."""
    from web.auth import get_or_create_user, create_magic_token, send_magic_link, BASE_URL

    email = request.form.get("email", "").strip().lower()
    if not email or "@" not in email:
        return render_template(
            "auth_login.html",
            message="Please enter a valid email address.",
            message_type="error",
        ), 400

    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    sent = send_magic_link(email, token)

    link = f"{BASE_URL}/auth/verify/{token}"

    if sent and os.environ.get("SMTP_HOST"):
        # Prod: email sent
        return render_template(
            "auth_login.html",
            message=f"Magic link sent to <strong>{email}</strong>. Check your inbox.",
        )
    else:
        # Dev: show link directly
        return render_template(
            "auth_login.html",
            message=f'Magic link (dev mode): <a href="{link}">{link}</a>',
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
    from web.auth import get_watches
    watches = get_watches(g.user["user_id"])
    return render_template("account.html", user=g.user, watches=watches)


# ---------------------------------------------------------------------------
# Morning Brief
# ---------------------------------------------------------------------------

@app.route("/brief")
@login_required
def brief():
    """Morning brief dashboard — what changed, permit health, inspections."""
    from web.brief import get_morning_brief
    lookback = request.args.get("lookback", "1")
    try:
        lookback_days = max(1, min(int(lookback), 30))
    except ValueError:
        lookback_days = 1
    brief_data = get_morning_brief(g.user["user_id"], lookback_days)
    return render_template("brief.html", user=g.user, brief=brief_data)


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

    try:
        result = run_async(run_nightly(lookback_days=lookback_days))
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)
