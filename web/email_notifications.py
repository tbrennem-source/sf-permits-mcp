"""Email notifications for permit status changes.

Sends individual or digest emails to users who have opted in to
permit change alerts (notify_permit_changes = TRUE).

Called by scripts/nightly_changes.py after change detection.

Rules:
  - Individual emails for <= 10 changes per user per run
  - Digest email for > 10 changes per user per run
  - Never sends more than 10 individual emails per user per nightly run
    (enforced by the digest threshold)
  - SMTP failures do not crash the nightly pipeline
  - Users with notify_permit_changes = FALSE are skipped

Usage from nightly pipeline:
    from web.email_notifications import send_permit_notifications
    send_permit_notifications(new_changes)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

from flask import render_template

from src.db import BACKEND, query

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@sfpermits.ai")
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5001")
UNSUBSCRIBE_SECRET = os.environ.get("UNSUBSCRIBE_SECRET", "dev-unsub-secret")

# Max individual emails per user per nightly run before switching to digest
MAX_INDIVIDUAL_EMAILS = 10


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


# ── Unsubscribe tokens ───────────────────────────────────────────────────────

def generate_unsubscribe_token(user_id: int, email: str) -> str:
    """Generate HMAC-based unsubscribe token (no DB storage needed)."""
    payload = f"{user_id}:{email}"
    return hmac.new(
        UNSUBSCRIBE_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:32]


# ── SMTP send ────────────────────────────────────────────────────────────────

def _send_email_sync(to_email: str, subject: str, html_body: str,
                     plain_body: str | None = None) -> bool:
    """Send an email synchronously via SMTP. Returns True on success."""
    if not SMTP_HOST:
        logger.info(
            "SMTP not configured — would send notification to %s: %s",
            to_email, subject,
        )
        return True  # Dev mode: treat as sent

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["List-Unsubscribe"] = f"<{BASE_URL}/account>"

        # Plain-text fallback
        msg.set_content(
            plain_body or (
                f"sfpermits.ai — permit update notification\n\n"
                f"View details: {BASE_URL}/brief\n"
                f"Manage preferences: {BASE_URL}/account"
            )
        )
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS or "")
            server.send_message(msg)

        logger.info("Notification sent to %s: %s", to_email, subject)
        return True
    except Exception:
        logger.exception("Failed to send notification to %s", to_email)
        return False


def send_notification_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send a notification email via background executor or synchronously.

    Designed to be called directly or submitted via submit_task().
    SMTP failures are caught and logged — never raises.
    """
    return _send_email_sync(to_email, subject, html_body)


# ── Query watchers ───────────────────────────────────────────────────────────

def _get_watchers_for_change(change: dict) -> list[dict]:
    """Return users watching the block/lot in a change who have opted in to notifications."""
    block = change.get("block") or ""
    lot = change.get("lot") or ""

    if not block or not lot:
        return []

    ph = _ph()
    rows = query(
        f"SELECT u.user_id, u.email, "
        f"  COALESCE(u.notify_email, u.email) AS notify_to "
        f"FROM users u "
        f"JOIN watch_items w ON u.user_id = w.user_id "
        f"WHERE u.notify_permit_changes = TRUE "
        f"  AND u.is_active = TRUE "
        f"  AND w.is_active = TRUE "
        f"  AND w.block = {ph} AND w.lot = {ph}",
        (block, lot),
    )
    return [
        {"user_id": r[0], "email": r[1], "notify_to": r[2]}
        for r in (rows or [])
    ]


# ── Group changes by user ────────────────────────────────────────────────────

def _group_changes_by_user(new_changes: list[dict]) -> dict[int, dict]:
    """Return {user_id: {email, notify_to, changes: [...]}} for opted-in users."""
    user_changes: dict[int, dict[str, Any]] = {}

    for change in new_changes:
        watchers = _get_watchers_for_change(change)
        for w in watchers:
            uid = w["user_id"]
            if uid not in user_changes:
                user_changes[uid] = {
                    "email": w["email"],
                    "notify_to": w["notify_to"],
                    "changes": [],
                }
            user_changes[uid]["changes"].append(change)

    return user_changes


# ── Address formatting ───────────────────────────────────────────────────────

def _format_address(change: dict) -> str:
    """Return a human-readable address string from a change dict."""
    parts = []
    if change.get("street_number"):
        parts.append(str(change["street_number"]).strip())
    if change.get("street_name"):
        parts.append(str(change["street_name"]).strip())
    if parts:
        return " ".join(parts)
    return change.get("permit_number") or "Unknown"


def _format_date(change: dict) -> str:
    """Return a human-readable date from new_status_date or change_date."""
    raw = change.get("new_status_date") or change.get("change_date") or ""
    if not raw:
        return ""
    try:
        if hasattr(raw, "strftime"):
            return raw.strftime("%b %d, %Y")
        ds = str(raw)[:10]
        dt = datetime.strptime(ds, "%Y-%m-%d")
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return str(raw)[:10]


def _format_status_change(change: dict) -> str:
    """Return a concise description of what changed."""
    new_status = change.get("new_status") or ""
    old_status = change.get("old_status")
    change_type = change.get("change_type", "")

    if change_type == "new_permit":
        return f"New permit filed — {new_status}" if new_status else "New permit filed"
    if old_status and new_status:
        return f"Status changed to {new_status}"
    if new_status:
        return f"Status: {new_status}"
    return "Status updated"


# ── Individual email ─────────────────────────────────────────────────────────

def _send_individual_notification(
    user_id: int, to_email: str, change: dict, app
) -> bool:
    """Render and send a single permit change notification email."""
    address = _format_address(change)
    permit_number = change.get("permit_number", "")
    status_text = _format_status_change(change)
    date_text = _format_date(change)

    subject = f"Permit update at {address}"
    if permit_number:
        subject = f"Permit update: {permit_number} at {address}"

    unsubscribe_token = generate_unsubscribe_token(user_id, to_email)
    account_url = f"{BASE_URL}/account"
    permit_url = f"{BASE_URL}/?q={permit_number}" if permit_number else f"{BASE_URL}/"

    try:
        with app.app_context():
            html_body = render_template(
                "notification_email.html",
                base_url=BASE_URL,
                permit_number=permit_number,
                address=address,
                status_text=status_text,
                date_text=date_text,
                change=change,
                permit_url=permit_url,
                account_url=account_url,
                unsubscribe_token=unsubscribe_token,
                user_id=user_id,
            )
    except Exception:
        logger.exception("Failed to render individual notification for user %d", user_id)
        return False

    return _send_email_sync(to_email, subject, html_body)


# ── Digest email ─────────────────────────────────────────────────────────────

def _send_digest_email(
    user_id: int, to_email: str, changes: list[dict], app
) -> bool:
    """Render and send a digest email for > MAX_INDIVIDUAL_EMAILS changes."""
    count = len(changes)
    subject = f"{count} permit updates at your watched addresses"

    unsubscribe_token = generate_unsubscribe_token(user_id, to_email)
    account_url = f"{BASE_URL}/account"
    brief_url = f"{BASE_URL}/brief"

    # Build table rows for the template
    rows = []
    for c in changes:
        rows.append({
            "permit_number": c.get("permit_number", ""),
            "address": _format_address(c),
            "status_text": _format_status_change(c),
            "date_text": _format_date(c),
            "permit_url": (
                f"{BASE_URL}/?q={c['permit_number']}"
                if c.get("permit_number")
                else f"{BASE_URL}/"
            ),
        })

    try:
        with app.app_context():
            html_body = render_template(
                "notification_digest_email.html",
                base_url=BASE_URL,
                count=count,
                rows=rows,
                brief_url=brief_url,
                account_url=account_url,
                unsubscribe_token=unsubscribe_token,
                user_id=user_id,
            )
    except Exception:
        logger.exception("Failed to render digest notification for user %d", user_id)
        return False

    return _send_email_sync(to_email, subject, html_body)


# ── Main entry point ─────────────────────────────────────────────────────────

def send_permit_notifications(new_changes: list[dict], app=None) -> dict:
    """Send email notifications to users watching changed permits.

    Args:
        new_changes: List of change dicts from detect_changes() or similar.
                     Each dict should have: permit_number, block, lot,
                     old_status, new_status, change_date, street_number,
                     street_name, change_type, new_status_date.
        app: Flask app instance (required for render_template). If None,
             attempts to import from web.app.

    Returns:
        Dict with notification stats: users_notified, emails_sent, digests_sent,
        individual_sent, errors, skipped.
    """
    stats = {
        "users_notified": 0,
        "emails_sent": 0,
        "digests_sent": 0,
        "individual_sent": 0,
        "errors": 0,
        "skipped": 0,
    }

    if not new_changes:
        logger.info("send_permit_notifications: no changes to notify about")
        return stats

    # Get Flask app if not provided
    if app is None:
        try:
            from web.app import app as flask_app  # type: ignore
            app = flask_app
        except Exception:
            logger.warning(
                "send_permit_notifications: could not import flask app — "
                "notifications will be skipped"
            )
            return stats

    # Group changes by user
    user_changes = _group_changes_by_user(new_changes)

    if not user_changes:
        logger.info("send_permit_notifications: no opted-in users watching changed permits")
        return stats

    logger.info(
        "send_permit_notifications: %d users to notify about %d changes",
        len(user_changes), len(new_changes),
    )

    for uid, data in user_changes.items():
        notify_to = data["notify_to"]
        changes = data["changes"]

        try:
            if len(changes) > MAX_INDIVIDUAL_EMAILS:
                # Digest
                sent = _send_digest_email(uid, notify_to, changes, app)
                if sent:
                    stats["digests_sent"] += 1
                    stats["emails_sent"] += 1
                    stats["users_notified"] += 1
                else:
                    stats["errors"] += 1
            else:
                # Individual emails
                user_sent = 0
                for change in changes:
                    sent = _send_individual_notification(uid, notify_to, change, app)
                    if sent:
                        user_sent += 1
                        stats["individual_sent"] += 1
                        stats["emails_sent"] += 1
                    else:
                        stats["errors"] += 1

                if user_sent > 0:
                    stats["users_notified"] += 1

        except Exception:
            logger.exception("Unexpected error notifying user %d", uid)
            stats["errors"] += 1

    logger.info(
        "send_permit_notifications complete: %d users, %d emails "
        "(%d individual, %d digest), %d errors",
        stats["users_notified"],
        stats["emails_sent"],
        stats["individual_sent"],
        stats["digests_sent"],
        stats["errors"],
    )
    return stats
