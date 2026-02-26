"""Auth, account, watch, and onboarding routes — Flask Blueprint.

Extracted from web/app.py during Sprint 64 Phase 0 Blueprint refactor.
"""

import logging
import os

from flask import (
    Blueprint,
    abort,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from web.helpers import admin_required, login_required

bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@bp.route("/auth/login")
def auth_login():
    """Show the login/register page."""
    from web.auth import invite_required
    referral_source = request.args.get("referral_source", "")
    analysis_id = request.args.get("analysis_id", "")
    return render_template(
        "auth_login.html",
        invite_required=invite_required(),
        referral_source=referral_source,
        analysis_id=analysis_id,
    )


@bp.route("/auth/send-link", methods=["POST"])
def auth_send_link():
    """Create user if needed, generate magic link, send/display it.

    Three-tier signup logic (Session D):
    - shared_link: user came via /analysis/<id> — bypass invite code requirement
    - invited: has valid invite code — standard flow
    - organic: no code, no shared link — redirect to beta request form
    """
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

    # D8: Detect referral source
    referral_source = request.form.get("referral_source", "").strip()
    analysis_id_ref = request.form.get("analysis_id", "").strip()
    is_shared_link = referral_source == "shared_link" and bool(analysis_id_ref)

    # Check if existing user (existing users don't need an invite code)
    user = get_user_by_email(email)

    if not user:
        # New user — determine access path
        invite_code = request.form.get("invite_code", "").strip()

        if is_shared_link:
            # Shared-link path: grant full access immediately, no invite code needed
            user = create_user(email, referral_source="shared_link")
            # Store analysis_id in session for post-login redirect
            session["shared_analysis_id"] = analysis_id_ref
        elif invite_required():
            if invite_code and validate_invite_code(invite_code):
                # Valid invite code
                user = create_user(email, invite_code=invite_code, referral_source="invited")
            else:
                # No valid invite code and no shared link → redirect to beta request
                return redirect(
                    url_for("beta_request", email=email)
                )
        else:
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


@bp.route("/auth/verify/<token>")
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

    # SESSION E: First-login detection — set flag if user just created their account
    # email_verified was False before verify_magic_token flipped it to True,
    # so if it's now True but was previously unverified, this is first login.
    # We use a simpler proxy: check if there are no watches yet.
    # We use a session flag cleared on dismiss.
    if not session.get("onboarding_dismissed"):
        try:
            from web.auth import get_watches
            watches = get_watches(user["user_id"])
            if not watches:
                session["show_onboarding_banner"] = True
        except Exception:
            pass

    # D8: Redirect shared_link users back to the analysis they came from
    # Sprint 61B: auto-join project on signup via shared link
    shared_analysis_id = session.pop("shared_analysis_id", None)
    if shared_analysis_id:
        try:
            from web.projects import _auto_join_project
            _auto_join_project(user["user_id"], shared_analysis_id)
        except Exception as _aje:
            logging.warning("auto_join_project failed (non-fatal): %s", _aje)
        return redirect(url_for("analysis_shared", analysis_id=shared_analysis_id))

    return redirect(url_for("index"))


@bp.route("/auth/logout", methods=["POST"])
def auth_logout():
    """Clear the session."""
    session.clear()
    return redirect(url_for("index"))


# === SESSION A: TEST LOGIN ENDPOINT ===

@bp.route("/auth/test-login", methods=["POST"])
def auth_test_login():
    """Test-only login endpoint — 404 unless TESTING env var is set.

    Allows automated tests and Desktop CC RELAY sessions to authenticate
    without magic link emails. NEVER enable TESTING on production.

    Request body (JSON):
      {"secret": "<TEST_LOGIN_SECRET>", "email": "test-admin@sfpermits.ai"}

    Responses:
      404 — TESTING not set (endpoint does not exist in prod)
      403 — wrong or missing secret
      200 — success, session cookie set
    """
    from web.auth import handle_test_login

    payload = request.get_json(silent=True) or {}
    user, status = handle_test_login(payload)

    if status == 404:
        abort(404)
    if status == 403:
        return jsonify({"error": "forbidden"}), 403

    # Success — create session identical to magic-link flow
    session.permanent = True
    session["user_id"] = user["user_id"]
    session["email"] = user["email"]
    session["is_admin"] = user["is_admin"]
    session.pop("impersonating", None)
    session.pop("admin_user_id", None)

    return jsonify({
        "ok": True,
        "user_id": user["user_id"],
        "email": user["email"],
        "is_admin": user["is_admin"],
    }), 200

# === END SESSION A: TEST LOGIN ENDPOINT ===


@bp.route("/auth/impersonate", methods=["POST"])
@admin_required
def auth_impersonate():
    """Admin: switch to viewing as another user."""
    from web.auth import get_user_by_email, get_or_create_user

    target_email = request.form.get("target_email", "").strip().lower()
    if not target_email:
        return redirect(url_for("auth.account"))

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

    return redirect(url_for("auth.account"))


@bp.route("/auth/stop-impersonate", methods=["POST"])
def auth_stop_impersonate():
    """Restore admin's own identity."""
    admin_id = session.pop("admin_user_id", None)
    admin_email = session.pop("admin_email", None)
    session.pop("impersonating", None)

    if admin_id:
        session["user_id"] = admin_id
        session["email"] = admin_email

    return redirect(url_for("auth.account"))


# ---------------------------------------------------------------------------
# Watch routes
# ---------------------------------------------------------------------------

@bp.route("/watch/add", methods=["POST"])
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


@bp.route("/watch/remove", methods=["POST"])
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


@bp.route("/watch/tags", methods=["POST"])
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


@bp.route("/watch/edit", methods=["POST"])
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


@bp.route("/watch/list")
@login_required
def watch_list():
    """Return user's watch list as HTML fragment."""
    from web.auth import get_watches
    watches = get_watches(g.user["user_id"])
    return render_template("account.html", user=g.user, watches=watches)


# E6: Watch count for brief prompt
@bp.route("/watch/brief-prompt")
@login_required
def watch_brief_prompt():
    """Return watch-count-aware brief prompt fragment. Called after watch add."""
    from web.auth import get_watches
    watches = get_watches(g.user["user_id"])
    count = len([w for w in watches if w.get("is_active", True)])
    brief_freq = g.user.get("brief_frequency", "none")
    already_enabled = brief_freq and brief_freq != "none"
    return render_template(
        "fragments/brief_prompt.html",
        watch_count=count,
        already_enabled=already_enabled,
    )


# ---------------------------------------------------------------------------
# Account page
# ---------------------------------------------------------------------------

@bp.route("/account")
@login_required
def account():
    """User account page with watch list."""
    from web.auth import get_watches, INVITE_CODES
    from web.activity import get_user_points, get_points_history
    from src.db import execute_write

    # One-click unsubscribe from permit change notifications (linked from emails)
    if request.args.get("unsubscribe_notifications") == "1":
        try:
            from web.email_notifications import generate_unsubscribe_token
            uid_param = request.args.get("uid", "")
            token_param = request.args.get("token", "")
            if uid_param and token_param:
                uid_int = int(uid_param)
                expected = generate_unsubscribe_token(uid_int, g.user["email"])
                import hmac as _hmac
                if uid_int == g.user["user_id"] and _hmac.compare_digest(token_param, expected):
                    execute_write(
                        "UPDATE users SET notify_permit_changes = FALSE WHERE user_id = %s",
                        (g.user["user_id"],),
                    )
                    g.user["notify_permit_changes"] = False
        except Exception:
            pass  # Non-fatal — just continue to account page

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
# === SESSION A: Account tab fragments ===
# ---------------------------------------------------------------------------

@bp.route("/account/fragment/settings")
@login_required
def account_fragment_settings():
    """Settings tab fragment — user profile, watches, points, plan analyses."""
    from web.auth import get_watches
    from web.activity import get_user_points, get_points_history
    watches = get_watches(g.user["user_id"])
    total_points = get_user_points(g.user["user_id"])
    points_history = get_points_history(g.user["user_id"], limit=10)
    recent_analyses = []
    try:
        from web.plan_jobs import get_user_jobs
        recent_analyses = get_user_jobs(g.user["user_id"], limit=3)
    except Exception:
        pass
    cal_stats = None
    try:
        from web.voice_calibration import get_calibration_stats
        cal_stats = get_calibration_stats(g.user["user_id"])
        if cal_stats["total"] == 0:
            cal_stats = None
    except Exception:
        pass
    return render_template(
        "fragments/account_settings.html",
        user=g.user,
        watches=watches,
        total_points=total_points,
        points_history=points_history,
        recent_analyses=recent_analyses,
        cal_stats=cal_stats,
    )


@bp.route("/account/fragment/admin")
@login_required
def account_fragment_admin():
    """Admin tab fragment — admin-only sections. Returns 403 for non-admin users."""
    if not g.user.get("is_admin"):
        abort(403)
    from web.auth import INVITE_CODES
    from web.activity import get_activity_stats, get_feedback_counts
    invite_codes = sorted(INVITE_CODES)
    activity_stats = get_activity_stats(hours=24)
    feedback_counts = get_feedback_counts()
    return render_template(
        "fragments/account_admin.html",
        user=g.user,
        invite_codes=invite_codes,
        activity_stats=activity_stats,
        feedback_counts=feedback_counts,
    )


# ---------------------------------------------------------------------------
# Permit Prep dashboard (QS3-A)
# ---------------------------------------------------------------------------

@bp.route("/account/prep")
@login_required
def account_prep():
    """User's Permit Prep dashboard — lists all active checklists."""
    from web.permit_prep import get_user_checklists
    checklists = get_user_checklists(g.user["user_id"])
    return render_template("account_prep.html", checklists=checklists)


# ---------------------------------------------------------------------------
# Primary address
# ---------------------------------------------------------------------------

@bp.route("/account/primary-address", methods=["POST"])
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


@bp.route("/account/primary-address/clear", methods=["POST"])
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
# Account: brief frequency
# ---------------------------------------------------------------------------

@bp.route("/account/brief-frequency", methods=["POST"])
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


@bp.route("/account/voice-style", methods=["POST"])
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


# === SESSION D: notification push ===

@bp.route("/account/notify-permit-changes", methods=["POST"])
@login_required
def account_notify_permit_changes():
    """Toggle permit change email notifications for the current user."""
    from src.db import execute_write

    # Checkbox: present = True, absent = False
    notify = request.form.get("notify_permit_changes") == "1"

    execute_write(
        "UPDATE users SET notify_permit_changes = %s WHERE user_id = %s",
        (notify, g.user["user_id"]),
    )

    if notify:
        return '<span style="color:var(--success);">On — you\'ll get emails when watched permits change.</span>'
    return '<span style="color:var(--text-muted);">Off — permit change alerts disabled.</span>'

# === END SESSION D ===


# ---------------------------------------------------------------------------
# Voice calibration
# ---------------------------------------------------------------------------

@bp.route("/account/voice-calibration")
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


@bp.route("/account/voice-calibration/save", methods=["POST"])
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


@bp.route("/account/voice-calibration/reset", methods=["POST"])
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

@bp.route("/email/unsubscribe")
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
# Onboarding
# ---------------------------------------------------------------------------

# E4: First-login welcome banner dismiss
@bp.route("/onboarding/dismiss", methods=["POST"])
def onboarding_dismiss():
    """Dismiss the first-login welcome banner. HTMX endpoint.

    Returns empty string — hx-swap='outerHTML' removes the banner div.
    """
    session.pop("show_onboarding_banner", None)
    session["onboarding_dismissed"] = True
    return ""  # Empty response removes the banner via hx-swap="outerHTML"
