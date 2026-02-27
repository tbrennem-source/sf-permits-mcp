"""Public-facing routes — index, search, analyze, plan analysis, shareable analysis.

Extracted from web/app.py during Sprint 64 Blueprint refactor.
"""

import json
import logging
import re

from flask import (
    Blueprint, render_template, request, abort, Response,
    redirect, url_for, session, g, send_file, jsonify, make_response,
)

from src.tools.predict_permits import predict_permits
from src.tools.estimate_fees import estimate_fees
from src.tools.estimate_timeline import estimate_timeline
from src.tools.required_documents import required_documents
from src.tools.revision_risk import revision_risk
from src.tools.validate_plans import validate_plans
from src.tools.context_parser import extract_triggers, enhance_description, reorder_sections
from src.tools.team_lookup import generate_team_profile
from src.tools.permit_lookup import permit_lookup
from src.tools.intent_router import classify as classify_intent

from web.helpers import (
    login_required,
    admin_required,
    run_async,
    md_to_html,
    _is_rate_limited,
    _resolve_block_lot,
    _is_no_results,
    NEIGHBORHOODS,
    _rate_limited_ai,
    _rate_limited_plans,
    BRAND_CONFIG,
    RATE_LIMIT_MAX_ANALYZE,
)

bp = Blueprint("public", __name__)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

@bp.route("/")
def index():
    # Unauthenticated users see the public landing page
    if not g.user:
        return render_template("landing.html")

    # If logged-in user has a primary address, resolve block/lot for report link
    user_report_url = None
    user_report_address = None
    if g.user.get("primary_street_number") and g.user.get("primary_street_name"):
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


# ---------------------------------------------------------------------------
# Public search
# ---------------------------------------------------------------------------

@bp.route("/search")
def public_search():
    """Public address lookup — free for unauthenticated users."""
    query_str = request.args.get("q", "").strip()
    if not query_str:
        return redirect(url_for("index"))

    # Authenticated users go to the full search experience
    if g.user:
        return redirect(f"/?q={query_str}")

    # Parse the query to extract address components
    result = classify_intent(query_str, [n for n in NEIGHBORHOODS if n])
    intent = result.intent
    entities = result.entities

    # === SESSION D: NL query detection for search guidance ===
    nl_query = intent in ("general_question", "analyze_project")

    # Track block/lot for intel preview HTMX panel
    resolved_block = None
    resolved_lot = None
    search_street_number = None
    search_street_name = None

    try:
        if intent == "lookup_permit":
            permit_num = entities.get("permit_number")
            result_md = run_async(permit_lookup(permit_number=permit_num))
        elif intent in ("search_address", "search_parcel"):
            street_number = entities.get("street_number")
            street_name = entities.get("street_name")
            block = entities.get("block")
            lot = entities.get("lot")
            search_street_number = street_number
            search_street_name = street_name
            resolved_block = block
            resolved_lot = lot
            result_md = run_async(permit_lookup(
                street_number=street_number,
                street_name=street_name,
                block=block,
                lot=lot,
            ))
        else:
            # Default: try as an address lookup
            result_md = run_async(permit_lookup(street_name=query_str))

        result_html = md_to_html(result_md)
        no_results = _is_no_results(result_md)
    except Exception as e:
        logging.warning("Public search failed for %r: %s", query_str, e)
        return render_template(
            "search_results_public.html",
            query=query_str,
            error="We couldn't complete your search right now. Please try again.",
            no_results=False,
            result_html="",
            nl_query=False,
        )

    # Resolve block/lot from address for intel preview
    if not resolved_block and search_street_number and search_street_name:
        try:
            bl = _resolve_block_lot(search_street_number, search_street_name)
            if bl:
                resolved_block, resolved_lot = bl[0], bl[1]
        except Exception:
            pass

    # E3: Check for violation context
    violation_context = request.args.get("context") == "violation"

    return render_template(
        "search_results_public.html",
        query=query_str,
        result_html=result_html,
        no_results=no_results,
        error=None,
        violation_context=violation_context,
        nl_query=nl_query,
        block=resolved_block,
        lot=resolved_lot,
    )


# ---------------------------------------------------------------------------
# Analyze (5-tool analysis)
# ---------------------------------------------------------------------------

@bp.route("/analyze", methods=["POST"])
def analyze():
    """Run all 5 tools on the submitted project and return HTML fragments."""
    # --- Section A: existing fields ---
    description = request.form.get("description", "").strip()
    address = request.form.get("address", "").strip() or None
    neighborhood = request.form.get("neighborhood", "").strip() or None
    cost_str = request.form.get("cost", "").strip()
    sqft_str = request.form.get("sqft", "").strip()

    # === SESSION C: Cost of Delay ===
    carrying_cost_str = request.form.get("carrying_cost", "").strip()
    monthly_carrying_cost = float(carrying_cost_str) if carrying_cost_str else None
    # === END SESSION C ===

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
    # === SPRINT 57D: METHODOLOGY ===
    methodology = {}

    # 1. Predict Permits (primary — drives inputs for other tools)
    try:
        pred_raw = run_async(predict_permits(
            project_description=enriched_description,
            address=address,
            estimated_cost=estimated_cost,
            square_footage=square_footage,
            return_structured=True,
        ))
        pred_result, pred_meta = pred_raw
        results["predict"] = md_to_html(pred_result)
        methodology["predict"] = pred_meta
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
            fees_raw = run_async(estimate_fees(
                permit_type=permit_type,
                estimated_construction_cost=estimated_cost,
                square_footage=square_footage,
                neighborhood=neighborhood,
                project_type=project_type,
                return_structured=True,
            ))
            fees_md, fees_meta = fees_raw
            results["fees"] = md_to_html(fees_md)
            methodology["fees"] = fees_meta
        except Exception as e:
            results["fees"] = f'<div class="error">Fee estimation error: {e}</div>'
    else:
        results["fees"] = '<div class="info">Enter an estimated cost to calculate fees.</div>'

    # 3. Estimate Timeline
    try:
        timeline_raw = run_async(estimate_timeline(
            permit_type=permit_type,
            neighborhood=neighborhood,
            review_path=review_path,
            estimated_cost=estimated_cost,
            triggers=triggers or None,
            return_structured=True,
            monthly_carrying_cost=monthly_carrying_cost,  # SESSION C
        ))
        timeline_md, timeline_meta = timeline_raw
        # Add target date buffer calculation if provided
        if target_date:
            timeline_md = _add_target_date_context(timeline_md, target_date)
        results["timeline"] = md_to_html(timeline_md)
        methodology["timeline"] = timeline_meta
    except Exception as e:
        results["timeline"] = f'<div class="error">Timeline error: {e}</div>'

    # 4. Required Documents
    try:
        docs_raw = run_async(required_documents(
            permit_forms=permit_forms,
            review_path=review_path,
            agency_routing=agency_routing or None,
            project_type=project_type,
            triggers=triggers or None,
            return_structured=True,
        ))
        docs_md, docs_meta = docs_raw
        results["docs"] = md_to_html(docs_md)
        methodology["docs"] = docs_meta
    except Exception as e:
        results["docs"] = f'<div class="error">Documents error: {e}</div>'

    # 5. Revision Risk
    try:
        risk_raw = run_async(revision_risk(
            permit_type=permit_type,
            neighborhood=neighborhood,
            project_type=project_type,
            review_path=review_path,
            return_structured=True,
        ))
        risk_md, risk_meta = risk_raw
        results["risk"] = md_to_html(risk_md)
        methodology["risk"] = risk_meta
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

    # D4: Save analysis results to analysis_sessions for sharing
    # === SPRINT 58A: methodology persistence ===
    # === SPRINT 61B: project auto-create ===
    analysis_id = None
    try:
        import uuid
        import json as _json
        from src.db import execute_write as _db_write, BACKEND as _BACKEND, query_one as _qone, get_connection as _get_conn
        from web.projects import _get_or_create_project
        analysis_id = str(uuid.uuid4())
        user_id = g.user.get("user_id") if g.user else None
        # Sprint 61B: resolve block/lot for parcel dedup; create/link project
        _block = request.form.get("block", "").strip() or None
        _lot = request.form.get("lot", "").strip() or None
        _project_id = None
        if user_id and (address or _block or _lot):
            try:
                _project_id = _get_or_create_project(address, _block, _lot, neighborhood, user_id)
            except Exception as _pe:
                logging.warning("project auto-create failed (non-fatal): %s", _pe)
        # Store raw markdown text (pre-rendered) + full methodology dicts for sharing
        # Fix: use correct variable names (fees_md, timeline_md, docs_md, risk_md)
        # Sprint 58A: methodology dict is now included alongside raw results
        raw_results = {
            "predict": pred_result if pred_result else "",
            "fees": fees_md if "fees_md" in locals() else "",
            "timeline": timeline_md if "timeline_md" in locals() else "",
            "docs": docs_md if "docs_md" in locals() else "",
            "risk": risk_md if "risk_md" in locals() else "",
            # Sprint 58A: persist full methodology for each tool
            "_methodology": methodology,
        }
        results_json_str = _json.dumps(raw_results)
        if _BACKEND == "postgres":
            _db_write(
                "INSERT INTO analysis_sessions "
                "(id, user_id, project_description, address, neighborhood, "
                "estimated_cost, square_footage, results_json, project_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)",
                (analysis_id, user_id, description, address, neighborhood,
                 estimated_cost, square_footage, results_json_str, _project_id),
            )
        else:
            id_row = _qone("SELECT COALESCE(MAX(CAST(1 AS INTEGER)), 0) FROM analysis_sessions")
            conn2 = _get_conn()
            try:
                conn2.execute(
                    "INSERT INTO analysis_sessions "
                    "(id, user_id, project_description, address, neighborhood, "
                    "estimated_cost, square_footage, results_json, project_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (analysis_id, user_id, description, address, neighborhood,
                     estimated_cost, square_footage, results_json_str, _project_id),
                )
            finally:
                conn2.close()
    except Exception as _save_err:
        logging.warning("analysis_sessions save failed (non-fatal): %s", _save_err)
        analysis_id = None

    return render_template(
        "results.html",
        results=results,
        methodology=methodology,
        section_order=section_order,
        experience_level=experience_level,
        has_team=bool(team_md),
        analysis_id=analysis_id,
        # SESSION A: params for similar projects lazy load
        analyze_permit_type=permit_type,
        analyze_neighborhood=neighborhood or "",
        analyze_cost=estimated_cost or "",
    )


def _add_target_date_context(timeline_md: str, target_date: str) -> str:
    """Add target date buffer/deficit info to timeline output."""
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


# ---------------------------------------------------------------------------
# Validate (deprecated — use /analyze-plans)
# ---------------------------------------------------------------------------

@bp.route("/validate", methods=["POST"])
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


# ---------------------------------------------------------------------------
# Analyze Plans (full AI vision analysis)
# ---------------------------------------------------------------------------

@bp.route("/analyze-plans", methods=["POST"])
@login_required
@_rate_limited_plans
def analyze_plans_route():
    """Upload a PDF plan set for full AI-powered analysis.

    Small files (<= threshold) are processed synchronously.
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

    # -- Full Analysis always uses background worker (vision API calls take minutes) --
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

    # -- Quick Check mode: metadata-only via validate_plans --
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


# ---------------------------------------------------------------------------
# Plan image / session endpoints
# ---------------------------------------------------------------------------

@bp.route("/plan-images/<session_id>/<int:page_number>")
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


@bp.route("/plan-session/<session_id>")
def plan_session(session_id):
    """Return plan analysis session metadata as JSON."""
    from web.plan_images import get_session

    sess = get_session(session_id)
    if not sess:
        abort(404)

    # Serialize datetime for JSON
    if sess.get("created_at"):
        sess["created_at"] = sess["created_at"].isoformat()

    return Response(json.dumps(sess), mimetype="application/json")


@bp.route("/plan-images/<session_id>/download-all")
def download_all_pages(session_id):
    """Download all plan pages as a ZIP file."""
    import base64
    import io
    import zipfile
    from web.plan_images import get_session, get_page_image

    sess = get_session(session_id)
    if not sess:
        abort(404)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for page_num in range(sess['page_count']):
            b64_data = get_page_image(session_id, page_num)
            if b64_data:
                image_bytes = base64.b64decode(b64_data)
                zip_file.writestr(f"page-{page_num + 1}.png", image_bytes)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{sess['filename']}-pages.zip"
    )


@bp.route("/plan-analysis/<session_id>/email", methods=["POST"])
def email_analysis(session_id):
    """Email plan analysis to specified recipient."""
    from web.plan_images import get_session
    from web.email_brief import send_brief_email

    data = request.get_json()
    recipient = data.get('recipient')
    message = data.get('message', '')
    context = data.get('context', 'full')

    sess = get_session(session_id)
    if not sess:
        return jsonify({'success': False, 'error': 'Session not found'})

    # Build email body
    if context == 'full':
        subject = f"Plan Analysis: {sess['filename']}"
        html_body = f"""
<h2>Plan Analysis: {sess['filename']}</h2>
<p>{message}</p>
<p>Analysis for <strong>{sess['filename']}</strong> ({sess['page_count']} pages)</p>
<p><a href="{request.url_root}plan-session/{session_id}">View online</a></p>
"""
    elif context.startswith('comparison-'):
        parts = context.split('-')
        left, right = parts[1], parts[2]
        subject = f"Plan Comparison: Pages {int(left)+1} and {int(right)+1}"
        html_body = f"""
<h2>Plan Comparison</h2>
<p>{message}</p>
<p>Comparison of pages {int(left)+1} and {int(right)+1} from <strong>{sess['filename']}</strong></p>
"""
    else:
        subject = f"Plan Analysis: {sess['filename']}"
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


# ---------------------------------------------------------------------------
# Plan job status / cancel / results
# ---------------------------------------------------------------------------

@bp.route("/plan-jobs/<job_id>/status")
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


@bp.route("/plan-jobs/<job_id>/cancel", methods=["POST"])
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


@bp.route("/plan-jobs/<job_id>/results")
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


# ---------------------------------------------------------------------------
# Project grouping helpers (used by analysis_history)
# ---------------------------------------------------------------------------

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
    for grp in result:
        grp["jobs"].sort(key=lambda j: j.get("created_at") or "", reverse=True)
        grp["latest_status"] = grp["jobs"][0].get("status", "unknown")
        # Date range (convert UTC to Pacific)
        dates = [j["created_at"] for j in grp["jobs"] if j.get("created_at")]
        if dates:
            oldest = _to_pst(min(dates))
            newest = _to_pst(max(dates))
            if hasattr(oldest, 'strftime'):
                grp["date_range"] = f"{oldest.strftime('%b %d')} – {newest.strftime('%b %d, %Y')}"
            else:
                grp["date_range"] = ""
        else:
            grp["date_range"] = ""

        # Add version numbers
        for i, job in enumerate(reversed(grp["jobs"])):
            job["_version_num"] = i + 1
            job["_version_total"] = grp["count"]

    return result


def _to_pst(dt):
    """Convert a UTC datetime to US/Pacific. Standalone version of the Jinja filter."""
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


# ---------------------------------------------------------------------------
# Account: Analysis History
# ---------------------------------------------------------------------------

@bp.route("/account/analyses")
@login_required
def analysis_history():
    """View past plan analyses for logged-in user."""
    user_id = session.get("user_id")

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

    # Phase F2: attach project notes to each group (keyed by version_group or group key)
    for grp in groups:
        vg = None
        for j in grp.get("jobs", []):
            vg = j.get("version_group")
            if vg:
                break
        notes_key = vg or grp.get("key", "")
        grp["_notes"] = get_project_notes(user_id, notes_key) if notes_key else ""
        grp["_version_group"] = notes_key

    return render_template(
        "analysis_history.html",
        jobs=jobs,
        groups=groups,
        group_mode=group_mode,
        search_q=search_q,
        sort_by=sort_by,
        stats=stats,
    )


# ---------------------------------------------------------------------------
# Account: Compare Analyses
# ---------------------------------------------------------------------------

@bp.route("/account/analyses/compare")
@login_required
def compare_analyses():
    """Compare two versions of the same analysis (Phase E2).

    Query params:
      ?a=<job_id>&b=<job_id>   -- compare two specific jobs (b must be newer)

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
        logging.debug("Failed to load EPR check names", exc_info=True)

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


# ---------------------------------------------------------------------------
# Analyze Preview (unauthenticated permit preview)
# ---------------------------------------------------------------------------

# SF neighborhoods list for the preview form
_SF_NEIGHBORHOODS = [
    "Mission", "Noe Valley", "Castro/Upper Market", "Bernal Heights",
    "Pacific Heights", "Richmond", "Sunset", "SoMa", "Potrero Hill",
    "Haight Ashbury", "Marina", "North Beach", "Chinatown", "Tenderloin",
    "Bayview Hunters Point", "Excelsior", "Glen Park", "Visitacion Valley",
    "Outer Sunset",
]

# Kitchen/bath trigger words -- used to detect layout-decision fork
_KITCHEN_BATH_KEYWORDS = [
    "kitchen", "bath", "bathroom", "remodel", "renovate", "renovation",
    "sink", "toilet", "shower", "plumbing", "range", "cooktop", "island",
]


def _detect_kitchen_bath(description: str) -> bool:
    """Return True if the project description looks like a kitchen or bath remodel."""
    desc_lower = description.lower()
    return any(kw in desc_lower for kw in _KITCHEN_BATH_KEYWORDS)


def _parse_preview_predict(pred_md: str) -> dict:
    """Extract structured data from predict_permits markdown output."""
    text = pred_md.lower()
    is_otc = "otc" in text and "in-house" not in text[:text.find("otc") + 20] if "otc" in text else False
    # More reliable: check explicit path descriptions
    if "over-the-counter" in text or "over the counter" in text:
        is_otc = True
    if "in-house review" in text or "in-house" in text:
        is_otc = False

    # Extract form
    form = None
    if "form 3/8" in text or "form 3" in text:
        form = "Form 3/8"
    elif "form 8" in text:
        form = "Form 8"
    elif "form 1/2" in text or "form 1" in text:
        form = "Form 1/2"
    elif "form 6" in text:
        form = "Form 6"

    # Extract review reason (first line after "Review Path" or just take first sentence)
    review_reason = ""
    lines = pred_md.split("\n")
    for line in lines:
        stripped = line.strip().lstrip("#- ").strip()
        if stripped and len(stripped) > 20 and "review" in stripped.lower():
            review_reason = stripped[:200]
            break
    if not review_reason:
        # Take the first substantive non-header line
        for line in lines:
            stripped = line.strip().lstrip("#- *").strip()
            if stripped and len(stripped) > 30:
                review_reason = stripped[:200]
                break

    # Extract project type
    project_type = "general alteration"
    ptype_map = {
        "kitchen": "kitchen remodel", "bath": "bathroom remodel",
        "adu": "ADU", "restaurant": "restaurant", "solar": "solar installation",
        "seismic": "seismic retrofit", "new construction": "new construction",
        "demolition": "demolition",
    }
    for kw, label in ptype_map.items():
        if kw in text:
            project_type = label
            break

    return {
        "is_otc": is_otc,
        "review_reason": review_reason or ("OTC — simple scope" if is_otc else "In-house review required"),
        "form": form,
        "project_type": project_type,
        "raw": pred_md,
    }


def _parse_preview_timeline(tl_md: str) -> dict:
    """Extract structured data from estimate_timeline markdown output."""
    text = tl_md

    # Look for p50 (median) estimate -- typical format "P50: X weeks" or "X weeks"
    p50_display = "See full analysis"
    detail = ""
    range_str = ""

    # Try to extract weeks/months/days patterns
    week_match = re.search(r"p50[:\s]+(\d+)\s*(day|week|month)", text, re.IGNORECASE)
    if not week_match:
        week_match = re.search(r"median[:\s]+(\d+)\s*(day|week|month)", text, re.IGNORECASE)

    if week_match:
        num = int(week_match.group(1))
        unit = week_match.group(2).lower()
        p50_display = f"{num} {unit}{'s' if num != 1 else ''}"
    else:
        # Look for range like "3-6 weeks" or "2-3 months"
        range_match = re.search(r"(\d+)\s*[–\-]\s*(\d+)\s*(day|week|month)", text, re.IGNORECASE)
        if range_match:
            lo, hi = range_match.group(1), range_match.group(2)
            unit = range_match.group(3).lower()
            p50_display = f"{lo}–{hi} {unit}s"

    # Extract a detail sentence
    lines = tl_md.split("\n")
    for line in lines:
        stripped = line.strip().lstrip("#- *").strip()
        if stripped and len(stripped) > 30 and not stripped.startswith("P"):
            detail = stripped[:200]
            break

    # Try to get P25/P75 range
    p25_match = re.search(r"p25[:\s]+(\d+)\s*(day|week|month)", text, re.IGNORECASE)
    p75_match = re.search(r"p75[:\s]+(\d+)\s*(day|week|month)", text, re.IGNORECASE)
    if p25_match and p75_match:
        range_str = f"{p25_match.group(1)} {p25_match.group(2)}s – {p75_match.group(1)} {p75_match.group(2)}s"

    return {
        "p50_display": p50_display,
        "detail": detail or "Based on historical SF permit data",
        "range": range_str,
        "raw": tl_md,
    }


@bp.route("/analyze-preview", methods=["POST"])
@_rate_limited_ai
def analyze_preview():
    """Unauthenticated permit preview -- runs predict_permits + estimate_timeline only.

    No login required. Shows 2 of 5 tools; fees/docs/risk are locked cards.
    Rate limited via @_rate_limited_ai (per-user/IP) + legacy IP bucket below.
    """
    description = request.form.get("description", "").strip()
    neighborhood = request.form.get("neighborhood", "").strip() or None

    if not description:
        return redirect(url_for("index"))

    # Rate limit: 10 per minute per IP (legacy IP-based check, kept for extra protection)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip:
        ip = ip.split(",")[0].strip()
    if _is_rate_limited(ip, RATE_LIMIT_MAX_ANALYZE):
        return render_template(
            "analyze_preview.html",
            description=description,
            neighborhood=neighborhood,
            predict=None,
            timeline=None,
            fork=False,
            error="Too many requests. Please wait a minute and try again.",
        ), 429

    predict_data = None
    timeline_data = None
    error = None
    fork = _detect_kitchen_bath(description)

    try:
        pred_md = run_async(predict_permits(
            project_description=description,
            address=None,
            estimated_cost=None,
            square_footage=None,
        ))
        predict_data = _parse_preview_predict(pred_md)
    except Exception as e:
        logging.warning("analyze_preview predict failed: %s", e)
        error = "Could not generate permit prediction. Please try again."

    try:
        # Determine permit_type and review_path from prediction
        _permit_type = "alterations"
        _review_path = None
        if predict_data:
            if predict_data["is_otc"]:
                _review_path = "otc"
            if "new construction" in predict_data.get("project_type", ""):
                _permit_type = "new_construction"

        tl_md = run_async(estimate_timeline(
            permit_type=_permit_type,
            neighborhood=neighborhood,
            review_path=_review_path,
        ))
        timeline_data = _parse_preview_timeline(tl_md)
    except Exception as e:
        logging.warning("analyze_preview timeline failed: %s", e)
        if not error:
            error = "Could not generate timeline estimate."

    return render_template(
        "analyze_preview.html",
        description=description,
        neighborhood=neighborhood,
        predict=predict_data,
        timeline=timeline_data,
        fork=fork,
        error=error,
    )


# ---------------------------------------------------------------------------
# Shareable Analysis
# ---------------------------------------------------------------------------

@bp.route("/analysis/<analysis_id>")
def analysis_shared(analysis_id):
    """Public shareable analysis page -- no auth required.

    Increments view_count. Shows full 5-tool results with CTA to sign up.
    """
    from src.db import query_one as _qone, execute_write as _ew, BACKEND as _BE
    import json as _json

    try:
        row = _qone(
            "SELECT id, user_id, project_description, address, neighborhood, "
            "estimated_cost, square_footage, results_json, created_at, shared_count, view_count, "
            "project_id "
            "FROM analysis_sessions WHERE id = %s",
            (analysis_id,),
        )
    except Exception:
        abort(404)
    if not row:
        abort(404)

    # Increment view_count (non-fatal)
    try:
        _ew(
            "UPDATE analysis_sessions SET view_count = COALESCE(view_count, 0) + 1 WHERE id = %s",
            (analysis_id,),
        )
    except Exception:
        pass

    # Parse results_json -> rendered HTML
    # row indices: 0=id, 1=user_id, 2=project_description, 3=address, 4=neighborhood,
    #              5=estimated_cost, 6=square_footage, 7=results_json, 8=created_at,
    #              9=shared_count, 10=view_count, 11=project_id
    results_json_val = row[7]
    created_at_val = row[8]
    _session_project_id = row[11] if len(row) > 11 else None
    try:
        if isinstance(results_json_val, str):
            raw = _json.loads(results_json_val)
        elif isinstance(results_json_val, dict):
            raw = results_json_val
        else:
            raw = {}
    except Exception:
        raw = {}

    # Render markdown to HTML for display
    display_results = {}
    for key, val in raw.items():
        if val:
            display_results[key] = md_to_html(val)

    class _Session:
        def __init__(self):
            self.id = row[0]
            self.project_description = row[2] or ""
            self.address = row[3]
            self.neighborhood = row[4]
            self.estimated_cost = row[5]
            self.created_at = created_at_val
            self.results = display_results

    sess = _Session()

    # Try to determine referrer role from user record
    referrer_role = None
    if row[1]:
        try:
            from web.auth import get_user_by_id as _gubi
            owner = _gubi(row[1])
            if owner:
                referrer_role = owner.get("role") or "a permit professional"
        except Exception:
            pass

    # Sprint 61B: check if current user is a member of the linked project
    _is_project_member = False
    if _session_project_id and g.user:
        try:
            _mem = _qone(
                "SELECT 1 FROM project_members WHERE project_id = %s AND user_id = %s",
                (_session_project_id, g.user["user_id"]),
            )
            _is_project_member = bool(_mem)
        except Exception:
            pass

    return render_template(
        "analysis_shared.html",
        session=sess,
        session_id=analysis_id,
        referrer_role=referrer_role,
        project_id=_session_project_id,
        is_project_member=_is_project_member,
    )


@bp.route("/analysis/<analysis_id>/share", methods=["POST"])
@login_required
def analysis_share_email(analysis_id):
    """Send analysis share emails to up to 5 recipients.

    POST body: {"emails": ["a@b.com", "c@d.com"]}
    Returns: {"ok": true} or {"ok": false, "error": "..."}
    """
    import json as _json
    from src.db import query_one as _qone, execute_write as _ew, BACKEND as _BE
    import smtplib
    from email.message import EmailMessage

    # Validate owner
    try:
        row = _qone(
            "SELECT id, user_id, project_description, address, neighborhood, estimated_cost "
            "FROM analysis_sessions WHERE id = %s",
            (analysis_id,),
        )
    except Exception:
        return jsonify({"ok": False, "error": "Analysis not found"}), 404
    if not row:
        return jsonify({"ok": False, "error": "Analysis not found"}), 404

    # Only owner can share (or admin)
    owner_id = row[1]
    current_uid = g.user.get("user_id") if g.user else None
    if owner_id and current_uid and owner_id != current_uid and not g.user.get("is_admin"):
        return jsonify({"ok": False, "error": "Not authorized"}), 403

    data = request.get_json(silent=True) or {}
    emails = data.get("emails", [])

    # Validate
    if not emails:
        return jsonify({"ok": False, "error": "No email addresses provided"}), 400
    if len(emails) > 5:
        return jsonify({"ok": False, "error": "Maximum 5 recipients allowed"}), 400

    email_re = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    for em in emails:
        if not email_re.match(em):
            return jsonify({"ok": False, "error": f"Invalid email: {em}"}), 400

    # Build share URL
    from web.auth import BASE_URL, SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USER, SMTP_PASS
    share_url = f"{BASE_URL}/analysis/{analysis_id}"
    signup_url = f"{BASE_URL}/auth/login?referral_source=shared_link&analysis_id={analysis_id}"

    sender_name = g.user.get("display_name") if g.user else None
    sender_email = g.user.get("email") if g.user else "sfpermits.ai"

    project_description = row[2] or ""
    address = row[3]
    neighborhood = row[4]
    estimated_cost = row[5]

    included_sections = ["Permit type prediction", "Fee estimate", "Timeline estimate",
                         "Required documents checklist", "Revision risk assessment"]

    # Render email template
    email_html = render_template(
        "analysis_email.html",
        sender_name=sender_name,
        sender_email=sender_email,
        project_description=project_description,
        address=address,
        neighborhood=neighborhood,
        estimated_cost=estimated_cost,
        share_url=share_url,
        signup_url=signup_url,
        included_sections=included_sections,
    )

    sent_count = 0
    errors = []

    if not SMTP_HOST:
        # Dev mode: log
        for em in emails:
            logging.info("[analysis_share_email] dev mode — would send to %s: %s", em, share_url)
        sent_count = len(emails)
    else:
        for em in emails:
            try:
                msg = EmailMessage()
                msg["Subject"] = f"{sender_name or 'Someone'} shared a permit analysis with you"
                msg["From"] = f"SF Permits AI <{SMTP_FROM}>"
                msg["To"] = em
                msg.set_content(
                    f"{sender_name or 'Someone'} shared a permit analysis with you on sfpermits.ai.\n\n"
                    f"Project: {project_description[:200]}\n\n"
                    f"View the full analysis: {share_url}\n\n"
                    f"--\nsfpermits.ai - San Francisco Building Permit Intelligence"
                )
                msg.add_alternative(email_html, subtype="html")
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                    server.starttls()
                    if SMTP_USER:
                        server.login(SMTP_USER, SMTP_PASS or "")
                    server.send_message(msg)
                sent_count += 1
            except Exception as e:
                logging.error("analysis_share_email failed for %s: %s", em, e)
                errors.append(em)

    # Increment shared_count
    try:
        _ew(
            "UPDATE analysis_sessions SET shared_count = COALESCE(shared_count, 0) + %s WHERE id = %s",
            (sent_count, analysis_id),
        )
    except Exception:
        pass

    if errors:
        return jsonify({"ok": False, "error": f"Failed to send to: {', '.join(errors)}"}), 500

    return jsonify({"ok": True, "sent": sent_count})


# ---------------------------------------------------------------------------
# Shared link signup context helper
# ---------------------------------------------------------------------------

def _get_shared_link_signup_context():
    """Extract shared_link context from request args."""
    referral_source = request.args.get("referral_source") or request.form.get("referral_source", "")
    analysis_id = request.args.get("analysis_id") or request.form.get("analysis_id", "")
    return referral_source.strip(), analysis_id.strip()
