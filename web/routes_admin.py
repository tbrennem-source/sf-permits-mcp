"""Admin routes Blueprint — extracted from web/app.py (Sprint 64 refactor).

Contains:
- Admin invite, feedback queue, activity, ops hub, sources, regulatory watch
- Knowledge capture (quiz, add-note)
- Voice calibration redirects
- Cost dashboard + kill switch
- Pipeline health admin
- Beta request management
- QA replay routes
"""

import base64
import json
import logging
import os
import re
import signal
import tempfile as _tempfile

from datetime import datetime
from flask import (
    Blueprint, Response, abort, current_app, g, jsonify, redirect, render_template,
    render_template_string, request, send_file, session, url_for,
)

from web.helpers import login_required, admin_required, md_to_html, QUIZ_QUESTIONS, BRAND_CONFIG

bp = Blueprint("admin", __name__)

# ---------------------------------------------------------------------------
# QA replay storage directory (mirrors the constant in app.py)
# ---------------------------------------------------------------------------
QA_STORAGE_DIR = os.environ.get("QA_STORAGE_DIR", "qa-results")


# ---------------------------------------------------------------------------
# Admin: send invite
# ---------------------------------------------------------------------------

@bp.route("/admin/send-invite", methods=["POST"])
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

@bp.route("/feedback/submit", methods=["POST"])
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


@bp.route("/feedback/draft-edit", methods=["POST"])
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


@bp.route("/feedback/draft-good", methods=["POST"])
def feedback_draft_good():
    """Record that an AI-generated draft was used as-is (positive signal).

    This is a lightweight positive reinforcement signal -- no RAG chunk needed,
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


@bp.route("/admin/feedback")
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


@bp.route("/admin/feedback/update", methods=["POST"])
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


@bp.route("/admin/feedback/<int:feedback_id>/screenshot")
@login_required
def admin_feedback_screenshot(feedback_id):
    """Serve feedback screenshot as image (admin only)."""
    if not g.user.get("is_admin"):
        abort(403)

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


@bp.route("/admin/activity")
@login_required
def admin_activity():
    """Admin activity feed page."""
    if not g.user.get("is_admin"):
        abort(403)

    # === SESSION B: offset pagination ===
    from web.activity import get_recent_activity, get_activity_stats
    action_filter = request.args.get("action") or None
    user_id_filter_str = request.args.get("user_id") or None
    user_id_filter = int(user_id_filter_str) if user_id_filter_str else None
    limit = 100
    offset = int(request.args.get("offset", 0))
    activity = get_recent_activity(limit=limit, offset=offset, action_filter=action_filter, user_id_filter=user_id_filter)
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
                           users=users,
                           limit=limit,
                           offset=offset)


@bp.route("/admin/ops")
@login_required
def admin_ops():
    """Admin operations hub -- pipeline health + data quality."""
    if not g.user.get("is_admin"):
        abort(403)
    return render_template("admin_ops.html", user=g.user, active_page="admin")


def _fragment_timeout_fallback(tab_name: str) -> str:
    """Graceful fallback when a tab query exceeds 25s."""
    return (
        '<div style="text-align:center;padding:60px 20px;color:var(--text-muted);">'
        f'<p style="font-size:1.1rem;margin-bottom:8px;">{tab_name} is loading slowly</p>'
        '<p>The query is taking longer than 25 seconds.</p>'
        '<p style="margin-top:12px;">'
        '<a href="javascript:location.reload()" style="color:var(--accent);">Retry</a>'
        '</p></div>'
    )


@bp.route("/admin/ops/fragment/<tab>")
@login_required
def admin_ops_fragment(tab):
    """HTMX fragment endpoints for admin ops hub tabs.

    Every tab is wrapped in a 25s SIGALRM timeout so a slow DB query
    never hangs the HTMX request indefinitely.
    """
    if not g.user.get("is_admin"):
        abort(403)

    class _Timeout(Exception):
        pass

    def _alarm(signum, frame):
        raise _Timeout()

    old_handler = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(25)

    try:
        result = _render_ops_tab(tab)
    except _Timeout:
        tab_labels = {
            "pipeline": "Pipeline Health",
            "quality": "Data Quality",
            "activity": "User Activity",
            "feedback": "Feedback",
            "sources": "LUCK Sources",
            "regulatory": "Regulatory Watch",
            "intel": "Intelligence",
            "syshealth": "System Health",
        }
        result = _fragment_timeout_fallback(tab_labels.get(tab, tab.title()))
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    return result


@bp.route("/admin/ops/refresh-dq", methods=["POST"])
@login_required
def admin_ops_refresh_dq():
    """Manually trigger a DQ cache refresh (admin only).

    Runs all checks synchronously (may take 30-60s on big tables),
    stores results in dq_cache, then returns the updated DQ fragment.
    """
    if not g.user.get("is_admin"):
        abort(403)
    from web.data_quality import refresh_dq_cache, get_cached_checks, check_bulk_indexes
    refresh_dq_cache()
    checks, refreshed_at = get_cached_checks()
    indexes = check_bulk_indexes()
    return render_template("fragments/admin_quality.html",
                           checks=checks, refreshed_at=refreshed_at,
                           indexes=indexes)


def _render_ops_tab(tab: str):
    """Render a single ops tab fragment (called inside SIGALRM guard)."""
    if tab == "pipeline":
        from web.velocity_dashboard import get_dashboard_data
        user_id = g.user["user_id"] if g.user else None
        data = get_dashboard_data(user_id=user_id)
        return render_template("velocity_dashboard.html", data=data,
                               active_page="admin", fragment=True)

    elif tab == "quality":
        from web.data_quality import get_cached_checks, check_bulk_indexes
        checks, refreshed_at = get_cached_checks()
        indexes = check_bulk_indexes()
        return render_template("fragments/admin_quality.html",
                               checks=checks, refreshed_at=refreshed_at,
                               indexes=indexes)

    elif tab == "activity":
        # === SESSION B: offset pagination ===
        from web.activity import get_recent_activity, get_activity_stats
        action_filter = request.args.get("action") or None
        user_id_filter_str = request.args.get("user_id") or None
        user_id_filter = int(user_id_filter_str) if user_id_filter_str else None
        limit = 100
        offset = int(request.args.get("offset", 0))
        activity = get_recent_activity(limit=limit, offset=offset, action_filter=action_filter,
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
                               users=users, fragment=True,
                               limit=limit,
                               offset=offset)

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

    elif tab == "syshealth":
        # Delegate to the dedicated /admin/health handler (reuses its logic)
        return admin_health()

    # === SESSION A: Activity Intelligence ===
    elif tab == "intel":
        from web.activity_intel import (
            get_bounce_rate, get_feature_funnel, get_query_refinements,
            get_feedback_by_page, get_time_to_first_action
        )
        bounce = get_bounce_rate()
        funnel = get_feature_funnel()
        refinements = get_query_refinements()
        feedback_pages = get_feedback_by_page()
        time_to_action = get_time_to_first_action()
        return render_template("fragments/admin_intel.html",
                               bounce=bounce, funnel=funnel,
                               refinements=refinements,
                               feedback_pages=feedback_pages,
                               time_to_action=time_to_action)
    # === END SESSION A ===

    else:
        abort(404)


@bp.route("/admin/sources")
@login_required
def admin_sources():
    """Knowledge source inventory -- printable reference for Amy."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.sources import get_source_inventory
    inventory = get_source_inventory()
    return render_template("admin_sources.html", user=g.user, **inventory)


@bp.route("/admin/regulatory-watch")
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


@bp.route("/admin/regulatory-watch/create", methods=["POST"])
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
    return redirect(url_for("admin.admin_regulatory_watch"))


@bp.route("/admin/regulatory-watch/<int:watch_id>/update", methods=["POST"])
@login_required
def admin_regulatory_watch_update(watch_id):
    """Update a regulatory watch item status."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.regulatory_watch import update_watch_item
    status = request.form.get("status")
    if status:
        update_watch_item(watch_id, status=status)
    return redirect(url_for("admin.admin_regulatory_watch"))


@bp.route("/admin/regulatory-watch/<int:watch_id>/delete", methods=["POST"])
@login_required
def admin_regulatory_watch_delete(watch_id):
    """Delete a regulatory watch item."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.regulatory_watch import delete_watch_item
    delete_watch_item(watch_id)
    return redirect(url_for("admin.admin_regulatory_watch"))


# ---------------------------------------------------------------------------
# Admin: Knowledge capture
# ---------------------------------------------------------------------------

@bp.route("/admin/knowledge/quiz")
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
    # These helpers live in web.app (shared with /ask routes)
    from web.app import _try_rag_retrieval, _synthesize_with_ai, _clean_chunk_content

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


@bp.route("/admin/knowledge/quiz/submit", methods=["POST"])
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
        from web.app import _try_rag_retrieval, _clean_chunk_content
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


@bp.route("/admin/knowledge/add-note", methods=["POST"])
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
# Voice calibration -- moved from /admin/ to /account/ (available to all users)
# Old /admin/ URLs redirect for bookmarks.
# ---------------------------------------------------------------------------

@bp.route("/admin/voice-calibration")
@login_required
def admin_voice_calibration_redirect():
    """Redirect old admin URL to new account URL."""
    return redirect("/account/voice-calibration", code=301)


@bp.route("/admin/voice-calibration/save", methods=["POST"])
@login_required
def admin_voice_calibration_save_redirect():
    """Redirect old admin POST to new account URL (307 preserves POST)."""
    return redirect("/account/voice-calibration/save", code=307)


@bp.route("/admin/voice-calibration/reset", methods=["POST"])
@login_required
def admin_voice_calibration_reset_redirect():
    """Redirect old admin POST to new account URL (307 preserves POST)."""
    return redirect("/account/voice-calibration/reset", code=307)


# === SESSION B: COST PROTECTION ===

@bp.route("/admin/costs")
@login_required
def admin_costs():
    """Admin API cost dashboard -- today's spend, 7-day trend, kill switch."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.cost_tracking import get_cost_summary, ensure_schema
    ensure_schema()
    summary = get_cost_summary(days=7)
    return render_template("admin_costs.html", user=g.user, summary=summary)


@bp.route("/admin/costs/kill-switch", methods=["POST"])
@login_required
def admin_costs_kill_switch():
    """Toggle the Claude API kill switch (admin only)."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.cost_tracking import set_kill_switch
    active_str = request.form.get("active", "0")
    active = active_str.strip() in ("1", "true", "yes")
    set_kill_switch(active)
    return redirect(url_for("admin.admin_costs"))

# === END SESSION B: COST PROTECTION ===


# ---------------------------------------------------------------------------
# Pipeline health admin dashboard
# ---------------------------------------------------------------------------

@bp.route("/admin/pipeline")
@login_required
def admin_pipeline():
    """Pipeline health admin dashboard.

    Shows cron job history, data freshness, stuck jobs,
    and provides a manual re-run button.

    Admin-only.
    """
    if not g.user.get("is_admin"):
        abort(403)

    try:
        from web.pipeline_health import get_pipeline_health
        report = get_pipeline_health()
    except Exception as e:
        logging.exception("admin_pipeline health check failed")
        # Render page with error state so admin can still see the route
        from web.pipeline_health import PipelineHealthReport, HealthCheck
        report = PipelineHealthReport(
            run_at=__import__("datetime").datetime.utcnow().isoformat(),
            overall_status="unknown",
            checks=[HealthCheck(name="error", status="unknown", message=str(e))],
            summary_line=f"Health check failed: {e}",
        )

    return render_template(
        "admin_pipeline.html",
        user=g.user,
        active_page="admin",
        report=report,
    )


# ---------------------------------------------------------------------------
# Beta request management
# ---------------------------------------------------------------------------

@bp.route("/admin/beta-requests")
@login_required
def admin_beta_requests():
    """Admin: view pending beta access requests."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.auth import get_pending_beta_requests
    requests_list = get_pending_beta_requests()
    flash_message = request.args.get("msg", "")
    return render_template(
        "admin_beta_requests.html",
        requests=requests_list,
        flash_message=flash_message,
        user=g.user,
    )


@bp.route("/admin/beta-requests/<int:req_id>/approve", methods=["POST"])
@login_required
def admin_approve_beta(req_id):
    """Admin: approve a beta request and send magic link."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.auth import (
        approve_beta_request, create_magic_token, send_magic_link,
        send_beta_welcome_email, BASE_URL,
    )
    user = approve_beta_request(req_id)
    if not user:
        return redirect(url_for("admin.admin_beta_requests", msg="Request not found or already reviewed."))

    # Generate magic link token
    token = create_magic_token(user["user_id"])
    magic_link = f"{BASE_URL}/auth/verify/{token}"

    # Send beta approval welcome email (includes magic link CTA)
    welcome_sent = send_beta_welcome_email(user["email"], magic_link)

    # Fall back to plain magic link email if welcome send failed
    if not welcome_sent:
        send_magic_link(user["email"], token)

    logging.info(
        "Admin %s approved beta request %d for %s (welcome_email=%s)",
        g.user.get("email"), req_id, user["email"], welcome_sent,
    )
    return redirect(url_for("admin.admin_beta_requests", msg=f"Approved and sent welcome email to {user['email']}."))


@bp.route("/admin/beta-requests/<int:req_id>/deny", methods=["POST"])
@login_required
def admin_deny_beta(req_id):
    """Admin: deny a beta request."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.auth import deny_beta_request
    deny_beta_request(req_id)
    return redirect(url_for("admin.admin_beta_requests", msg="Request denied."))


# ---------------------------------------------------------------------------
# QA Replay routes
# ---------------------------------------------------------------------------

@bp.route("/admin/qa")
@login_required
def admin_qa():
    """QA run listing page -- video replays of RELAY sessions."""
    if not g.user.get("is_admin"):
        abort(403)

    markers_dir = os.path.join(QA_STORAGE_DIR, "markers")
    runs = []
    if os.path.isdir(markers_dir):
        for fname in os.listdir(markers_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(markers_dir, fname)
            try:
                with open(fpath) as f:
                    data = json.loads(f.read())
                # Format the timestamp for display
                started = data.get("started_at", "")
                try:
                    dt = datetime.fromisoformat(started)
                    data["started_at_fmt"] = dt.strftime("%b %d, %Y %H:%M")
                except (ValueError, TypeError):
                    data["started_at_fmt"] = started
                # Ensure numeric fields have defaults
                data.setdefault("total_steps", len(data.get("steps", [])))
                data.setdefault("passed", 0)
                data.setdefault("failed", 0)
                data.setdefault("blocked", 0)
                data.setdefault("duration_seconds", 0)
                runs.append(data)
            except (json.JSONDecodeError, OSError):
                continue

    # Sort newest first
    runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)

    return render_template("admin_qa.html", user=g.user, active_page="admin", runs=runs)


@bp.route("/admin/qa/<run_name>")
@login_required
def admin_qa_detail(run_name):
    """Single QA run playback -- video + step timeline."""
    if not g.user.get("is_admin"):
        abort(403)

    # Sanitize run_name to prevent path traversal
    safe_name = os.path.basename(run_name)
    markers_path = os.path.join(QA_STORAGE_DIR, "markers", f"{safe_name}.json")
    if not os.path.isfile(markers_path):
        abort(404)

    with open(markers_path) as f:
        data = json.loads(f.read())

    # Format timestamp
    started = data.get("started_at", "")
    try:
        dt = datetime.fromisoformat(started)
        data["started_at_fmt"] = dt.strftime("%b %d, %Y %H:%M")
    except (ValueError, TypeError):
        data["started_at_fmt"] = started

    data.setdefault("total_steps", len(data.get("steps", [])))
    data.setdefault("passed", 0)
    data.setdefault("failed", 0)
    data.setdefault("blocked", 0)
    data.setdefault("duration_seconds", 0)
    data.setdefault("video_file", None)

    return render_template(
        "admin_qa_detail.html", user=g.user, active_page="admin", run=data
    )


@bp.route("/admin/qa/<run_name>/video")
@login_required
def admin_qa_video(run_name):
    """Serve the .webm video file for a QA run."""
    if not g.user.get("is_admin"):
        abort(403)

    safe_name = os.path.basename(run_name)
    video_dir = os.path.join(QA_STORAGE_DIR, "videos", safe_name)
    if not os.path.isdir(video_dir):
        abort(404)

    # Find the .webm file (Playwright generates the filename)
    webm_files = [f for f in os.listdir(video_dir) if f.endswith(".webm")]
    if not webm_files:
        abort(404)

    return send_file(
        os.path.join(video_dir, webm_files[0]),
        mimetype="video/webm",
    )


@bp.route("/admin/qa/<run_name>/screenshot/<filename>")
@login_required
def admin_qa_screenshot(run_name, filename):
    """Serve a failure screenshot from a QA run."""
    if not g.user.get("is_admin"):
        abort(403)

    safe_name = os.path.basename(run_name)
    safe_file = os.path.basename(filename)
    screenshot_path = os.path.join(QA_STORAGE_DIR, "screenshots", safe_name, safe_file)
    if not os.path.isfile(screenshot_path):
        abort(404)

    return send_file(screenshot_path, mimetype="image/png")


# ---------------------------------------------------------------------------
# Admin funnel dashboard
# ---------------------------------------------------------------------------

@bp.route("/admin/beta-funnel")
@login_required
def admin_beta_funnel():
    """Admin funnel dashboard — beta signup analytics."""
    if not g.user.get("is_admin"):
        abort(403)

    from src.db import get_connection, BACKEND

    total = today = week = 0
    by_role = []
    by_ref = []
    top_addresses = []

    try:
        conn = get_connection()
        if BACKEND == "postgres":
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM beta_requests")
            total = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM beta_requests WHERE created_at >= NOW() - INTERVAL '1 day'"
            )
            today = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM beta_requests WHERE created_at >= NOW() - INTERVAL '7 days'"
            )
            week = cursor.fetchone()[0]

            cursor.execute(
                "SELECT role, COUNT(*) as count FROM beta_requests "
                "GROUP BY role ORDER BY count DESC LIMIT 10"
            )
            by_role = [{"role": r[0], "count": r[1]} for r in cursor.fetchall()]

            cursor.execute(
                "SELECT referrer, COUNT(*) as count FROM beta_requests "
                "GROUP BY referrer ORDER BY count DESC LIMIT 10"
            )
            by_ref = [{"referrer": r[0], "count": r[1]} for r in cursor.fetchall()]

            cursor.execute(
                "SELECT interest_address FROM beta_requests "
                "WHERE interest_address IS NOT NULL AND interest_address != '' "
                "GROUP BY interest_address ORDER BY COUNT(*) DESC LIMIT 10"
            )
            top_addresses = [r[0] for r in cursor.fetchall()]
        else:
            conn.execute("SELECT COUNT(*) FROM beta_requests")
            total = conn.fetchone()[0]

            conn.execute(
                "SELECT COUNT(*) FROM beta_requests WHERE created_at >= NOW() - INTERVAL '1 day'"
            )
            today = conn.fetchone()[0]

            conn.execute(
                "SELECT COUNT(*) FROM beta_requests WHERE created_at >= NOW() - INTERVAL '7 days'"
            )
            week = conn.fetchone()[0]

            conn.execute(
                "SELECT role, COUNT(*) as count FROM beta_requests "
                "GROUP BY role ORDER BY count DESC LIMIT 10"
            )
            by_role = [{"role": r[0], "count": r[1]} for r in conn.fetchall()]

            conn.execute(
                "SELECT referrer, COUNT(*) as count FROM beta_requests "
                "GROUP BY referrer ORDER BY count DESC LIMIT 10"
            )
            by_ref = [{"referrer": r[0], "count": r[1]} for r in conn.fetchall()]

            conn.execute(
                "SELECT interest_address FROM beta_requests "
                "WHERE interest_address IS NOT NULL AND interest_address != '' "
                "GROUP BY interest_address ORDER BY COUNT(*) DESC LIMIT 10"
            )
            top_addresses = [r[0] for r in conn.fetchall()]
    except Exception as e:
        current_app.logger.error("Beta funnel query error: %s", e)

    stats = {"total": total, "today": today, "week": week}
    return render_template(
        "admin/beta_funnel.html",
        stats=stats,
        by_role=by_role,
        by_ref=by_ref,
        top_addresses=top_addresses,
        user=g.user,
    )


@bp.route("/admin/beta-funnel/export")
@login_required
def admin_beta_funnel_export():
    """CSV export of all beta signups."""
    if not g.user.get("is_admin"):
        abort(403)

    import csv
    import io

    from src.db import get_connection, BACKEND

    rows = []
    try:
        conn = get_connection()
        if BACKEND == "postgres":
            cursor = conn.cursor()
            cursor.execute(
                "SELECT email, name, role, interest_address, referrer, status, created_at "
                "FROM beta_requests ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()
        else:
            conn.execute(
                "SELECT email, name, role, interest_address, referrer, status, created_at "
                "FROM beta_requests ORDER BY created_at DESC"
            )
            rows = conn.fetchall()
    except Exception as e:
        current_app.logger.error("Beta funnel export error: %s", e)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "name", "role", "interest_address", "referrer", "status", "created_at"])
    writer.writerows(rows)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=beta_signups.csv"},
    )


# ---------------------------------------------------------------------------
# Admin: Metrics Dashboard (QS4-A)
# ---------------------------------------------------------------------------

@bp.route("/admin/metrics")
@login_required
def admin_metrics():
    """Admin metrics dashboard — issuance trends, SLA compliance, planning velocity."""
    if not g.user.get("is_admin"):
        abort(403)

    from src.db import get_connection, BACKEND

    conn = get_connection()
    log = logging.getLogger(__name__)

    issuance_rows = []
    sla_rows = []
    planning_rows = []

    try:
        # --- Section 1: Permit Issuance Trends (last 2 years) ---
        try:
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT issued_year,
                               EXTRACT(MONTH FROM issued_date::TIMESTAMP)::INTEGER AS issued_month,
                               permit_type, otc_ih, COUNT(*) as count
                        FROM permit_issuance_metrics
                        WHERE issued_year IS NOT NULL
                          AND issued_date IS NOT NULL
                          AND issued_year::INTEGER >= EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - 2
                        GROUP BY issued_year, issued_month, permit_type, otc_ih
                        ORDER BY issued_year DESC, issued_month DESC
                    """)
                    issuance_rows = [
                        {"year": r[0], "month": r[1], "type": r[2], "otc_ih": r[3], "count": r[4]}
                        for r in cur.fetchall()
                    ]
            else:
                rows = conn.execute("""
                    SELECT issued_year,
                           MONTH(issued_date::TIMESTAMP) AS issued_month,
                           permit_type, otc_ih, COUNT(*) as count
                    FROM permit_issuance_metrics
                    WHERE issued_year IS NOT NULL
                      AND issued_date IS NOT NULL
                      AND CAST(issued_year AS INTEGER) >= YEAR(CURRENT_DATE) - 2
                    GROUP BY issued_year, issued_month, permit_type, otc_ih
                    ORDER BY issued_year DESC, issued_month DESC
                """).fetchall()
                issuance_rows = [
                    {"year": r[0], "month": r[1], "type": r[2], "otc_ih": r[3], "count": r[4]}
                    for r in rows
                ]
        except Exception:
            log.warning("admin_metrics: issuance query failed", exc_info=True)

        # --- Section 2: Station SLA Compliance ---
        try:
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT station, department,
                               COUNT(*) as total,
                               SUM(CASE WHEN met_cal_sla THEN 1 ELSE 0 END) as met_sla,
                               ROUND(AVG(calendar_days)::numeric, 1) as avg_days
                        FROM permit_review_metrics
                        WHERE station IS NOT NULL
                        GROUP BY station, department
                        ORDER BY total DESC
                        LIMIT 30
                    """)
                    sla_rows = [
                        {"station": r[0], "department": r[1], "total": r[2],
                         "met_sla": r[3], "avg_days": float(r[4]) if r[4] else 0,
                         "sla_pct": round(r[3] / r[2] * 100, 1) if r[2] else 0}
                        for r in cur.fetchall()
                    ]
            else:
                rows = conn.execute("""
                    SELECT station, department,
                           COUNT(*) as total,
                           SUM(CASE WHEN met_cal_sla THEN 1 ELSE 0 END) as met_sla,
                           ROUND(AVG(calendar_days), 1) as avg_days
                    FROM permit_review_metrics
                    WHERE station IS NOT NULL
                    GROUP BY station, department
                    ORDER BY total DESC
                    LIMIT 30
                """).fetchall()
                sla_rows = [
                    {"station": r[0], "department": r[1], "total": r[2],
                     "met_sla": r[3], "avg_days": float(r[4]) if r[4] else 0,
                     "sla_pct": round(r[3] / r[2] * 100, 1) if r[2] else 0}
                    for r in rows
                ]
        except Exception:
            log.warning("admin_metrics: SLA query failed", exc_info=True)

        # --- Section 3: Planning Velocity ---
        try:
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT project_stage, metric_outcome, COUNT(*) as count,
                               ROUND(AVG(metric_value)::numeric, 1) as avg_value
                        FROM planning_review_metrics
                        GROUP BY project_stage, metric_outcome
                        ORDER BY count DESC
                    """)
                    planning_rows = [
                        {"stage": r[0], "outcome": r[1], "count": r[2],
                         "avg_value": float(r[3]) if r[3] else 0}
                        for r in cur.fetchall()
                    ]
            else:
                rows = conn.execute("""
                    SELECT project_stage, metric_outcome, COUNT(*) as count,
                           ROUND(AVG(metric_value), 1) as avg_value
                    FROM planning_review_metrics
                    GROUP BY project_stage, metric_outcome
                    ORDER BY count DESC
                """).fetchall()
                planning_rows = [
                    {"stage": r[0], "outcome": r[1], "count": r[2],
                     "avg_value": float(r[3]) if r[3] else 0}
                    for r in rows
                ]
        except Exception:
            log.warning("admin_metrics: planning query failed", exc_info=True)

    finally:
        conn.close()

    return render_template(
        "admin_metrics.html",
        user=g.user,
        active_page="admin",
        issuance_rows=issuance_rows,
        sla_rows=sla_rows,
        planning_rows=planning_rows,
    )


# ---------------------------------------------------------------------------
# Admin: /admin/perf — Request performance dashboard (Sprint 74-1)
# ---------------------------------------------------------------------------

log = logging.getLogger(__name__)


@bp.route("/admin/perf")
@admin_required
def admin_perf():
    """Request performance dashboard — top slowest endpoints, volume by path, percentiles."""
    from src.db import BACKEND, get_connection

    # Default empty data structures
    top_slowest = []
    volume_rows = []
    overall_percentiles = {"p50": 0.0, "p95": 0.0, "p99": 0.0, "total": 0}

    conn = get_connection()
    try:
        if BACKEND == "postgres":
            # Top 10 slowest endpoints (avg + p95)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        path,
                        method,
                        COUNT(*) AS request_count,
                        ROUND(AVG(duration_ms)::numeric, 1) AS avg_ms,
                        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) AS p95_ms
                    FROM request_metrics
                    WHERE recorded_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY path, method
                    HAVING COUNT(*) >= 2
                    ORDER BY p95_ms DESC
                    LIMIT 10
                """)
                top_slowest = [
                    {
                        "path": r[0], "method": r[1], "count": r[2],
                        "avg_ms": float(r[3]) if r[3] else 0.0,
                        "p95_ms": float(r[4]) if r[4] else 0.0,
                    }
                    for r in cur.fetchall()
                ]

            # Volume by path (24h)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        path,
                        method,
                        COUNT(*) AS request_count,
                        ROUND(AVG(duration_ms)::numeric, 1) AS avg_ms
                    FROM request_metrics
                    WHERE recorded_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY path, method
                    ORDER BY request_count DESC
                    LIMIT 20
                """)
                volume_rows = [
                    {
                        "path": r[0], "method": r[1], "count": r[2],
                        "avg_ms": float(r[3]) if r[3] else 0.0,
                    }
                    for r in cur.fetchall()
                ]

            # Overall p50/p95/p99 (24h)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) AS total,
                        ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) AS p50,
                        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) AS p95,
                        ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) AS p99
                    FROM request_metrics
                    WHERE recorded_at >= NOW() - INTERVAL '24 hours'
                """)
                row = cur.fetchone()
                if row and row[0]:
                    overall_percentiles = {
                        "total": int(row[0]),
                        "p50": float(row[1]) if row[1] else 0.0,
                        "p95": float(row[2]) if row[2] else 0.0,
                        "p99": float(row[3]) if row[3] else 0.0,
                    }
        else:
            # DuckDB fallback
            rows = conn.execute("""
                SELECT
                    path,
                    method,
                    COUNT(*) AS request_count,
                    ROUND(AVG(duration_ms), 1) AS avg_ms,
                    ROUND(QUANTILE_CONT(duration_ms, 0.95), 1) AS p95_ms
                FROM request_metrics
                WHERE recorded_at >= NOW() - INTERVAL '24 hours'
                GROUP BY path, method
                HAVING COUNT(*) >= 2
                ORDER BY p95_ms DESC
                LIMIT 10
            """).fetchall()
            top_slowest = [
                {
                    "path": r[0], "method": r[1], "count": r[2],
                    "avg_ms": float(r[3]) if r[3] else 0.0,
                    "p95_ms": float(r[4]) if r[4] else 0.0,
                }
                for r in rows
            ]

            rows = conn.execute("""
                SELECT
                    path,
                    method,
                    COUNT(*) AS request_count,
                    ROUND(AVG(duration_ms), 1) AS avg_ms
                FROM request_metrics
                WHERE recorded_at >= NOW() - INTERVAL '24 hours'
                GROUP BY path, method
                ORDER BY request_count DESC
                LIMIT 20
            """).fetchall()
            volume_rows = [
                {
                    "path": r[0], "method": r[1], "count": r[2],
                    "avg_ms": float(r[3]) if r[3] else 0.0,
                }
                for r in rows
            ]

            row = conn.execute("""
                SELECT
                    COUNT(*) AS total,
                    ROUND(QUANTILE_CONT(duration_ms, 0.50), 1) AS p50,
                    ROUND(QUANTILE_CONT(duration_ms, 0.95), 1) AS p95,
                    ROUND(QUANTILE_CONT(duration_ms, 0.99), 1) AS p99
                FROM request_metrics
                WHERE recorded_at >= NOW() - INTERVAL '24 hours'
            """).fetchone()
            if row and row[0]:
                overall_percentiles = {
                    "total": int(row[0]),
                    "p50": float(row[1]) if row[1] else 0.0,
                    "p95": float(row[2]) if row[2] else 0.0,
                    "p99": float(row[3]) if row[3] else 0.0,
                }
    except Exception:
        log.warning("admin_perf: query failed", exc_info=True)
    finally:
        conn.close()

    return render_template(
        "admin_perf.html",
        user=g.user,
        active_page="admin",
        top_slowest=top_slowest,
        volume_rows=volume_rows,
        overall_percentiles=overall_percentiles,
    )


# ---------------------------------------------------------------------------
# Admin: System Health fragment (Sprint 82-B)
# ---------------------------------------------------------------------------

@bp.route("/admin/health")
@login_required
def admin_health():
    """HTMX fragment: pool, SODA circuit breaker, and page cache stats.

    Designed to be polled every 30s from the admin ops hub.
    Admin-only endpoint — 403 for non-admins.
    """
    if not g.user.get("is_admin"):
        abort(403)

    log = logging.getLogger(__name__)

    # --- Pool stats ---
    try:
        from src.db import get_pool_health
        pool = get_pool_health()
    except Exception as e:
        log.warning("admin_health: pool stats failed: %s", e)
        pool = {"healthy": False, "min": 0, "max": 0, "in_use": 0, "available": 0}

    # --- SODA circuit breaker ---
    try:
        from src.soda_client import get_soda_cb_status
        cb = get_soda_cb_status()
    except Exception as e:
        log.warning("admin_health: SODA CB stats failed: %s", e)
        cb = {"state": "unknown", "failure_count": 0, "failure_threshold": 5}

    # --- DB circuit breaker (per-category) ---
    try:
        from src.db import circuit_breaker as db_cb
        db_cb_status = db_cb.get_status()
    except Exception as e:
        log.warning("admin_health: DB CB stats failed: %s", e)
        db_cb_status = {}

    # --- Page cache stats ---
    cache = {"row_count": 0, "active_count": 0, "oldest_age": None}
    try:
        from src.db import get_connection, BACKEND
        from datetime import datetime, timezone
        conn = get_connection()
        try:
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*), "
                        "  COUNT(*) FILTER (WHERE invalidated_at IS NULL), "
                        "  MIN(computed_at) "
                        "FROM page_cache"
                    )
                    row = cur.fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*), "
                    "  COUNT(*) FILTER (WHERE invalidated_at IS NULL), "
                    "  MIN(computed_at) "
                    "FROM page_cache"
                ).fetchone()
            if row and row[0]:
                cache["row_count"] = int(row[0])
                cache["active_count"] = int(row[1]) if row[1] is not None else 0
                oldest_dt = row[2]
                if oldest_dt:
                    if isinstance(oldest_dt, str):
                        from datetime import datetime
                        oldest_dt = datetime.fromisoformat(oldest_dt)
                    now = (datetime.now(timezone.utc)
                           if getattr(oldest_dt, "tzinfo", None)
                           else datetime.now())
                    age_min = int((now - oldest_dt).total_seconds() / 60)
                    if age_min >= 60:
                        cache["oldest_age"] = f"{age_min // 60}h {age_min % 60}m ago"
                    else:
                        cache["oldest_age"] = f"{age_min}m ago"
        finally:
            conn.close()
    except Exception as e:
        log.warning("admin_health: cache stats failed: %s", e)

    return render_template(
        "fragments/admin_health.html",
        pool=pool,
        cb=cb,
        db_cb_status=db_cb_status,
        cache=cache,
    )


# ---------------------------------------------------------------------------
# Admin: Persona Impersonation (QS10 T2-A)
# ---------------------------------------------------------------------------

@bp.route("/admin/impersonate", methods=["POST"])
@login_required
def admin_impersonate():
    """Inject a QA persona into the session for UI preview.

    POST body: persona_id (str)
    Returns an HTMX snippet showing the active persona label.
    Admin-only — returns 403 for non-admins.
    """
    from web.admin_personas import get_persona, apply_persona

    if not g.user or not g.user.get("is_admin"):
        abort(403)

    persona_id = request.form.get("persona_id", "").strip()
    persona = get_persona(persona_id)

    if persona is None:
        return (
            '<span style="font-family:var(--mono);font-size:var(--text-xs);'
            'color:var(--signal-red);">Error: unknown persona</span>'
        ), 200

    apply_persona(session, persona)

    return (
        f'<span style="font-family:var(--mono);font-size:var(--text-xs);'
        f'color:var(--signal-green);">Persona: {persona["label"]}</span>'
    ), 200


@bp.route("/admin/reset-impersonation")
@login_required
def admin_reset_impersonation():
    """Clear all persona impersonation state and redirect back.

    Admin-only escape hatch to restore real session state.
    """
    from web.admin_personas import get_persona, apply_persona

    if not g.user or not g.user.get("is_admin"):
        abort(403)

    reset_persona = get_persona("admin_reset")
    apply_persona(session, reset_persona)

    referrer = request.referrer or "/"
    return redirect(referrer)


# ---------------------------------------------------------------------------
# Admin: Visual QA Accept/Reject/Note log (QS10 T2-B)
# ---------------------------------------------------------------------------

def _atomic_write_json(path: str, data) -> None:
    """Write JSON atomically using a temp file + rename."""
    dir_ = os.path.dirname(path) or "."
    with _tempfile.NamedTemporaryFile("w", dir=dir_, suffix=".tmp", delete=False) as f:
        json.dump(data, f, indent=2)
        tmp = f.name
    os.replace(tmp, path)


@bp.route("/admin/qa-decision", methods=["POST"])
@login_required
def admin_qa_decision():
    """Record Tim's Accept/Reject/Note verdict for a visual QA pending review.

    Appends to qa-results/review-decisions.json (append-only, git-tracked).
    Also removes the matching entry from qa-results/pending-reviews.json.

    Admin-only — 403 for non-admins.
    """
    if not g.user.get("is_admin"):
        abort(403)

    _log = logging.getLogger(__name__)

    # --- Validate verdict ---
    tim_verdict = request.form.get("tim_verdict", "").strip()
    if tim_verdict not in ("accept", "reject", "note"):
        return (
            '<span style="font-family:var(--mono);font-size:var(--text-xs);'
            'color:var(--signal-red);">Invalid verdict</span>',
            400,
        )

    # --- Collect fields ---
    page = request.form.get("page", "").strip()[:200]
    persona = request.form.get("persona", "unknown").strip()[:100]
    viewport = request.form.get("viewport", "desktop").strip()[:20]
    dimension = request.form.get("dimension", "").strip()[:100]
    note = request.form.get("note", "").strip()[:500]
    sprint = request.form.get("sprint", "qs10").strip()[:20]

    try:
        pipeline_score = float(request.form.get("pipeline_score", 0))
    except (ValueError, TypeError):
        pipeline_score = 0.0

    decision = {
        "page": page,
        "persona": persona,
        "viewport": viewport,
        "dimension": dimension,
        "pipeline_score": pipeline_score,
        "tim_verdict": tim_verdict,
        "sprint": sprint,
        "note": note,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    # --- Append to review-decisions.json ---
    decisions_path = os.path.join(QA_STORAGE_DIR, "review-decisions.json")
    try:
        if os.path.isfile(decisions_path):
            with open(decisions_path, "r") as f:
                decisions = json.load(f)
        else:
            decisions = []
        if not isinstance(decisions, list):
            decisions = []
        decisions.append(decision)
        _atomic_write_json(decisions_path, decisions)
    except Exception as e:
        _log.warning("admin_qa_decision: failed to write decisions: %s", e)

    # --- Remove matching entry from pending-reviews.json ---
    pending_path = os.path.join(QA_STORAGE_DIR, "pending-reviews.json")
    try:
        if os.path.isfile(pending_path):
            with open(pending_path, "r") as f:
                pending = json.load(f)
            if isinstance(pending, list):
                pending = [
                    p for p in pending
                    if not (
                        p.get("page") == page
                        and p.get("dimension") == dimension
                        and p.get("sprint") == sprint
                    )
                ]
                _atomic_write_json(pending_path, pending)
    except Exception as e:
        _log.warning("admin_qa_decision: failed to update pending-reviews: %s", e)

    # --- Return HTMX confirmation snippet ---
    if tim_verdict == "accept":
        color = "var(--signal-green)"
        label = "Accepted"
    elif tim_verdict == "reject":
        color = "var(--signal-red)"
        label = "Rejected \u2014 flagged for fix"
    else:
        color = "var(--accent)"
        label = "Noted"

    return (
        f'<span style="font-family:var(--mono);font-size:var(--text-xs);'
        f'color:{color};">{label}</span>'
    )
