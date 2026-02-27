"""API routes: CRON_SECRET-protected JSON endpoints + plan job management.

Blueprint: api (no url_prefix)
"""

import logging
import os
import time

from flask import (
    Blueprint, request, abort, Response, jsonify, session, g,
    render_template,
)

from web.helpers import login_required, run_async, _is_rate_limited

bp = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# Permit Prep API (QS3-A)
# ---------------------------------------------------------------------------

@bp.route("/api/prep/create", methods=["POST"])
def api_prep_create():
    """Create a Permit Prep checklist for a permit. Requires auth."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    permit_number = data.get("permit_number", "").strip()
    if not permit_number:
        # Also try form data
        permit_number = request.form.get("permit_number", "").strip()
    if not permit_number:
        return jsonify({"error": "permit_number required"}), 400

    from web.permit_prep import create_checklist, get_checklist
    try:
        checklist_id = create_checklist(permit_number, user_id)
        checklist = get_checklist(permit_number, user_id)
        return jsonify({
            "checklist_id": checklist_id,
            "permit_number": permit_number,
            "total_items": checklist["progress"]["total"] if checklist else 0,
        }), 201
    except Exception as e:
        logging.exception("Failed to create prep checklist for %s", permit_number)
        return jsonify({"error": str(e)}), 500


@bp.route("/api/prep/<permit_number>")
def api_prep_get(permit_number):
    """Get Permit Prep checklist JSON. Requires auth."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    from web.permit_prep import get_checklist
    checklist = get_checklist(permit_number, user_id)
    if not checklist:
        return jsonify({"error": "not found"}), 404
    return jsonify(checklist)


@bp.route("/api/prep/item/<int:item_id>", methods=["PATCH"])
def api_prep_item_update(item_id):
    """Update a prep item status. HTMX-friendly: returns updated item fragment."""
    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    data = request.get_json(silent=True) or {}
    new_status = data.get("status", "").strip()
    if not new_status:
        new_status = request.form.get("status", "").strip()
    if not new_status:
        return jsonify({"error": "status required"}), 400

    from web.permit_prep import update_item_status
    result = update_item_status(item_id, new_status, user_id)
    if not result:
        return jsonify({"error": "not found or invalid status"}), 404

    # If HTMX request, return HTML fragment
    if request.headers.get("HX-Request"):
        return render_template("fragments/prep_item.html", item=result)

    return jsonify(result)


@bp.route("/api/prep/preview/<permit_number>")
def api_prep_preview(permit_number):
    """Preview predicted checklist without saving. Requires auth."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    from web.permit_prep import preview_checklist
    try:
        preview = preview_checklist(permit_number)
        return jsonify(preview)
    except Exception as e:
        logging.exception("Failed to preview prep for %s", permit_number)
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Timeline sequence API (Sprint 76-1)
# ---------------------------------------------------------------------------

@bp.route("/api/timeline/<permit_number>")
def api_timeline_sequence(permit_number):
    """Return station routing sequence timeline for a specific permit.

    GET /api/timeline/<permit_number>

    Public endpoint (no auth required — permit numbers are public data).
    Rate limited at 60 req/min per IP.

    Returns JSON:
      {
        "permit_number": str,
        "stations": [{"station": str, "p50_days": float|null, "status": "done|stalled|pending", ...}],
        "total_estimate_days": float,
        "confidence": "high|medium|low"
      }
    or {"error": "no addenda found"} with 404 if no routing data exists.
    """
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    if ip:
        ip = ip.split(",")[0].strip()
    if _is_rate_limited(ip, 60):
        return jsonify({"error": "rate limited"}), 429

    permit_number = permit_number.strip()
    if not permit_number:
        return jsonify({"error": "permit_number required"}), 400

    try:
        from src.tools.estimate_timeline import estimate_sequence_timeline  # noqa: F401 (importable for patching)
        result = estimate_sequence_timeline(permit_number)
    except Exception:
        logging.exception("api_timeline_sequence failed for %s", permit_number)
        return jsonify({"error": "internal error"}), 500

    if result is None:
        return jsonify({"error": "no addenda found", "permit_number": permit_number}), 404

    return jsonify(result)


# ---------------------------------------------------------------------------
# Public stats endpoint (cached, rate-limited)
# ---------------------------------------------------------------------------

_stats_cache: dict = {}
_STATS_CACHE_TTL = 3600  # 1 hour

_STATS_FALLBACK = {
    "permits": 1137816,
    "routing_records": 3920710,
    "entities": 1000000,
    "inspections": 671000,
    "last_refresh": None,
    "today_changes": 0,
}


def _fetch_stats_from_db() -> dict:
    """Query actual counts from the database."""
    from src.db import query_one
    stats = {}
    try:
        row = query_one("SELECT COUNT(*) FROM permits")
        stats["permits"] = row[0] if row else _STATS_FALLBACK["permits"]
    except Exception:
        stats["permits"] = _STATS_FALLBACK["permits"]

    try:
        row = query_one("SELECT COUNT(*) FROM addenda")
        stats["routing_records"] = row[0] if row else _STATS_FALLBACK["routing_records"]
    except Exception:
        stats["routing_records"] = _STATS_FALLBACK["routing_records"]

    try:
        row = query_one("SELECT COUNT(*) FROM entities")
        stats["entities"] = row[0] if row else _STATS_FALLBACK["entities"]
    except Exception:
        stats["entities"] = _STATS_FALLBACK["entities"]

    try:
        row = query_one("SELECT COUNT(*) FROM inspections")
        stats["inspections"] = row[0] if row else _STATS_FALLBACK["inspections"]
    except Exception:
        stats["inspections"] = _STATS_FALLBACK["inspections"]

    try:
        row = query_one(
            "SELECT MAX(filed_date) FROM permits WHERE filed_date IS NOT NULL"
        )
        if row and row[0]:
            stats["last_refresh"] = str(row[0]) + "T04:00:00Z"
        else:
            stats["last_refresh"] = None
    except Exception:
        stats["last_refresh"] = None

    try:
        row = query_one(
            "SELECT COUNT(*) FROM permits WHERE filed_date = CURRENT_DATE"
        )
        stats["today_changes"] = row[0] if row else 0
    except Exception:
        stats["today_changes"] = 0

    return stats


@bp.route("/api/stats")
def api_stats():
    """Public JSON endpoint: cached data counts for the landing page.

    Rate limited to 60 requests/min per IP. Results cached for 1 hour.
    """
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    if ip:
        ip = ip.split(",")[0].strip()
    if _is_rate_limited(ip, 60):
        return jsonify({"error": "rate limited"}), 429

    now = time.time()
    if _stats_cache.get("data") and (now - _stats_cache.get("ts", 0)) < _STATS_CACHE_TTL:
        return jsonify(_stats_cache["data"])

    try:
        data = _fetch_stats_from_db()
    except Exception:
        data = dict(_STATS_FALLBACK)

    _stats_cache["data"] = data
    _stats_cache["ts"] = now
    return jsonify(data)


# ---------------------------------------------------------------------------
# CSP violation reporting (public — browsers send reports automatically)
# ---------------------------------------------------------------------------

@bp.route("/api/csp-report", methods=["POST"])
def csp_report():
    """Receive CSP violation reports from browsers.

    Browsers send these automatically when Content-Security-Policy-Report-Only
    detects a violation. No auth required — the browser initiates the POST.

    Logs the violation for analysis. Returns 204 No Content.
    """
    try:
        data = request.get_json(silent=True, force=True)
        if data:
            report = data.get("csp-report", data)
            logging.getLogger("csp").info(
                "CSP violation: %s on %s (blocked: %s)",
                report.get("violated-directive", "?"),
                report.get("document-uri", "?"),
                report.get("blocked-uri", "?"),
            )
    except Exception:
        pass  # Fire and forget — never fail on a CSP report
    return Response(status=204)


# ---------------------------------------------------------------------------
# API auth helper
# ---------------------------------------------------------------------------

def _check_api_auth():
    """Verify CRON_SECRET bearer token. Aborts 403 if invalid."""
    token = request.headers.get("Authorization", "").strip()
    secret = os.environ.get("CRON_SECRET", "").strip()
    expected = f"Bearer {secret}"
    if not secret or token != expected:
        logging.warning(
            "API auth failed: token_len=%d expected_len=%d path=%s",
            len(token), len(expected), request.path,
        )
        abort(403)


# ---------------------------------------------------------------------------
# Plan session / job API endpoints
# ---------------------------------------------------------------------------

@bp.route("/api/plan-sessions/<session_id>/pages/<int:page_number>/image")
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


@bp.route("/api/project-notes/<version_group>", methods=["GET"])
def get_project_notes_api(version_group):
    """Return project notes for a version group (JSON)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    from web.plan_notes import get_project_notes
    text = get_project_notes(user_id, version_group)
    return jsonify({"notes_text": text})


@bp.route("/api/project-notes/<version_group>", methods=["POST"])
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


@bp.route("/api/plan-jobs/<job_id>", methods=["DELETE"])
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


@bp.route("/api/plan-jobs/<job_id>/restore", methods=["POST"])
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


@bp.route("/api/plan-jobs/<job_id>/prefill", methods=["GET"])
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


@bp.route("/api/plan-jobs/bulk-delete", methods=["POST"])
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


@bp.route("/api/plan-jobs/bulk-close", methods=["POST"])
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


@bp.route("/api/plan-jobs/<job_id>/close", methods=["POST"])
def close_plan_job(job_id):
    """Close (archive) a single plan analysis job."""
    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    from web.plan_jobs import close_project

    close_project([job_id], user_id)
    return jsonify({"closed": True})


@bp.route("/api/plan-jobs/<job_id>/reopen", methods=["POST"])
def reopen_plan_job(job_id):
    """Reopen (unarchive) a single plan analysis job."""
    user_id = session.get("user_id")
    if not user_id:
        return "", 401

    from web.plan_jobs import reopen_project

    reopen_project([job_id], user_id)
    return jsonify({"reopened": True})


# ---------------------------------------------------------------------------
# Similar projects (lazy-loaded HTMX fragment)
# ---------------------------------------------------------------------------

@bp.route("/api/similar-projects")
def api_similar_projects():
    """Lazy-loaded similar projects for /analyze results page."""
    from src.tools.similar_projects import similar_projects as _similar_projects

    permit_type = request.args.get("permit_type", "alterations")
    neighborhood = request.args.get("neighborhood", "")
    cost_str = request.args.get("cost", "")
    analysis_id = request.args.get("analysis_id", "")

    estimated_cost = float(cost_str) if cost_str else None

    try:
        result_md, meta = run_async(_similar_projects(
            permit_type=permit_type,
            neighborhood=neighborhood or None,
            estimated_cost=estimated_cost,
            return_structured=True,
        ))
        projects = meta.get("projects", [])
    except Exception as e:
        logging.warning("similar_projects failed: %s", e)
        projects = []
        meta = {}

    return render_template(
        "fragments/similar_projects.html",
        projects=projects,
        methodology=meta,
        analysis_id=analysis_id,
    )


# ---------------------------------------------------------------------------
# Client-side activity tracking
# ---------------------------------------------------------------------------

@bp.route("/api/activity/track", methods=["POST"])
def api_activity_track():
    """Receive batched client-side events and write to activity_log."""
    try:
        data = request.get_json(silent=True)
        if not data or not isinstance(data.get("events"), list):
            return jsonify({"ok": False, "error": "invalid payload"}), 400

        events = data["events"][:50]  # Cap at 50 events per batch

        from web.activity import log_activity
        user_id = g.user["user_id"] if g.user else None
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip:
            ip = ip.split(",")[0].strip()

        for evt in events:
            event_type = evt.get("event", "unknown")
            event_data = evt.get("data", {})
            session_id = evt.get("session_id", "")
            event_data["client_session"] = session_id
            log_activity(
                user_id=user_id,
                action=f"client_{event_type}",
                detail=event_data,
                path=event_data.get("path", request.path),
                ip=ip,
            )

        return jsonify({"ok": True, "count": len(events)})
    except Exception:
        return jsonify({"ok": False}), 500


# ---------------------------------------------------------------------------
# CRON_SECRET-protected JSON access for CLI tools
# ---------------------------------------------------------------------------

@bp.route("/api/feedback")
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


@bp.route("/api/feedback/<int:feedback_id>/screenshot")
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


@bp.route("/api/feedback/<int:feedback_id>", methods=["PATCH"])
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


@bp.route("/api/points/<int:user_id>")
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
