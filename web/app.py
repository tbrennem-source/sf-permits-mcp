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
import os
import sys
import time
from collections import defaultdict
from flask import Flask, render_template, request, abort, Response
import markdown

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.tools.predict_permits import predict_permits
from src.tools.estimate_fees import estimate_fees
from src.tools.estimate_timeline import estimate_timeline
from src.tools.required_documents import required_documents
from src.tools.revision_risk import revision_risk
from src.tools.validate_plans import validate_plans

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-key-change-in-prod")

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
# robots.txt — allow search engines, block AI scrapers, block common probes
# ---------------------------------------------------------------------------
ROBOTS_TXT = """\
User-agent: *
Allow: /

# Block AI training scrapers — no value to us, just cost
User-agent: GPTBot
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: anthropic-ai
Disallow: /

User-agent: FacebookBot
Disallow: /

User-agent: Bytespider
Disallow: /

# Block common vulnerability probe paths
# (these don't exist but bots try them — 404 is fine)
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


@app.route("/")
def index():
    return render_template("index.html", neighborhoods=NEIGHBORHOODS)


@app.route("/analyze", methods=["POST"])
def analyze():
    """Run all 5 tools on the submitted project and return HTML fragments."""
    description = request.form.get("description", "").strip()
    address = request.form.get("address", "").strip() or None
    neighborhood = request.form.get("neighborhood", "").strip() or None
    cost_str = request.form.get("cost", "").strip()
    sqft_str = request.form.get("sqft", "").strip()

    if not description:
        return '<div class="error">Please enter a project description.</div>', 400

    estimated_cost = float(cost_str) if cost_str else None
    square_footage = float(sqft_str) if sqft_str else None

    results = {}

    # 1. Predict Permits (primary — drives inputs for other tools)
    try:
        pred_result = run_async(predict_permits(
            project_description=description,
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

    # Derive triggers from project types
    triggers = []
    if "restaurant" in project_types:
        triggers.extend(["dph_food_facility", "fire_suppression", "grease_interceptor"])
    if "historic" in project_types:
        triggers.append("historic_preservation")
    if "seismic" in project_types:
        triggers.append("seismic_retrofit")
    if estimated_cost and estimated_cost > 195358:
        triggers.append("ada_path_of_travel")
    if "commercial_ti" in project_types:
        triggers.append("title24")

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

    return render_template("results.html", results=results)


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)
