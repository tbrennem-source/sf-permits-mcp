"""Email delivery for morning brief.

Renders the morning brief as HTML email and sends via SMTP.
Called by the /cron/send-briefs endpoint or manually.

Supports:
  - Daily briefs (lookback_days=1) sent every morning
  - Weekly briefs (lookback_days=7) sent on Mondays
  - Per-user watch list data
  - Unsubscribe tokens for one-click opt-out
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import smtplib
from datetime import date, datetime, timezone
from email.message import EmailMessage

from flask import render_template

from src.db import BACKEND, execute_write, query
from web.brief import get_morning_brief

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@sfpermits.ai")
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5001")
UNSUBSCRIBE_SECRET = os.environ.get("UNSUBSCRIBE_SECRET", "dev-unsub-secret")


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


# ── Unsubscribe tokens ────────────────────────────────────────────

def generate_unsubscribe_token(user_id: int, email: str) -> str:
    """Generate an HMAC-based unsubscribe token (no DB storage needed)."""
    payload = f"{user_id}:{email}"
    return hmac.new(
        UNSUBSCRIBE_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:32]


def verify_unsubscribe_token(user_id: int, email: str, token: str) -> bool:
    """Verify an unsubscribe token."""
    expected = generate_unsubscribe_token(user_id, email)
    return hmac.compare_digest(token, expected)


# ── User queries ──────────────────────────────────────────────────

def get_users_for_brief(frequency: str) -> list[dict]:
    """Get active users who want briefs at the given frequency.

    Args:
        frequency: 'daily' or 'weekly'

    Returns:
        List of user dicts with user_id, email, display_name.
    """
    ph = _ph()
    rows = query(
        f"SELECT u.user_id, u.email, u.display_name "
        f"FROM users u "
        f"WHERE u.is_active = TRUE AND u.brief_frequency = {ph} "
        f"  AND EXISTS ("
        f"    SELECT 1 FROM watch_items w "
        f"    WHERE w.user_id = u.user_id AND w.is_active = TRUE"
        f"  ) "
        f"ORDER BY u.user_id",
        (frequency,),
    )
    return [
        {"user_id": r[0], "email": r[1], "display_name": r[2]}
        for r in rows
    ]


def update_last_brief_sent(user_id: int) -> None:
    """Mark the user's last brief send time."""
    if BACKEND == "postgres":
        execute_write(
            "UPDATE users SET last_brief_sent_at = NOW() WHERE user_id = %s",
            (user_id,),
        )
    else:
        from src.db import get_connection
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE users SET last_brief_sent_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,),
            )
        finally:
            conn.close()


# ── Email rendering ───────────────────────────────────────────────

def render_brief_email(user: dict, brief_data: dict) -> str:
    """Render the morning brief as an HTML email string.

    Must be called within a Flask app context (for render_template).
    """
    unsubscribe_token = generate_unsubscribe_token(
        user["user_id"], user["email"]
    )
    unsubscribe_url = (
        f"{BASE_URL}/email/unsubscribe"
        f"?uid={user['user_id']}&token={unsubscribe_token}"
    )

    return render_template(
        "brief_email.html",
        base_url=BASE_URL,
        user_name=user.get("display_name") or "",
        lookback_days=brief_data["lookback_days"],
        summary=brief_data["summary"],
        changes=brief_data["changes"],
        plan_reviews=brief_data.get("plan_reviews", []),
        health=brief_data["health"],
        inspections=brief_data["inspections"],
        new_filings=brief_data["new_filings"],
        expiring=brief_data["expiring"],
        last_refresh=brief_data.get("last_refresh"),
        property_synopsis=brief_data.get("property_synopsis"),
        property_cards=brief_data.get("property_cards", []),
        unsubscribe_url=unsubscribe_url,
    )


# ── SMTP send ─────────────────────────────────────────────────────

def send_brief_email(to_email: str, html_body: str, subject: str | None = None) -> bool:
    """Send a brief email. Returns True on success."""
    if not subject:
        today = date.today().strftime("%b %d")
        subject = f"Morning Brief — {today} — sfpermits.ai"

    if not SMTP_HOST:
        logger.info(
            "SMTP not configured — would send brief to %s (%d chars)",
            to_email, len(html_body),
        )
        return True  # Dev mode: "sent" successfully

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["List-Unsubscribe"] = f"<{BASE_URL}/email/unsubscribe?email={to_email}>"

        # Set plain text fallback
        msg.set_content(
            f"Your sfpermits.ai morning brief is ready.\n\n"
            f"View it online: {BASE_URL}/brief\n\n"
            f"Manage preferences: {BASE_URL}/account"
        )
        # Add HTML version
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS or "")
            server.send_message(msg)

        return True
    except Exception:
        logger.exception("Failed to send brief to %s", to_email)
        return False


# ── Batch send ────────────────────────────────────────────────────

def send_briefs(frequency: str = "daily") -> dict:
    """Send morning briefs to all users subscribed at the given frequency.

    Args:
        frequency: 'daily' or 'weekly'

    Returns:
        Dict with counts: total, sent, skipped, failed.
    """
    lookback_days = 7 if frequency == "weekly" else 1
    users = get_users_for_brief(frequency)

    stats = {"total": len(users), "sent": 0, "skipped": 0, "failed": 0}
    logger.info("Sending %s briefs to %d users", frequency, len(users))

    for user in users:
        try:
            brief_data = get_morning_brief(user["user_id"], lookback_days)

            # Skip if nothing to report (no changes, no health issues, no properties)
            summary = brief_data["summary"]
            has_content = (
                summary["changes_count"] > 0
                or summary.get("plan_reviews_count", 0) > 0
                or summary["at_risk_count"] > 0
                or summary["inspections_count"] > 0
                or summary["new_filings_count"] > 0
                or summary["expiring_count"] > 0
                or len(brief_data.get("property_cards", [])) > 0
            )
            if not has_content:
                stats["skipped"] += 1
                logger.debug("Skipping brief for user %d — nothing to report", user["user_id"])
                continue

            html_body = render_brief_email(user, brief_data)
            sent = send_brief_email(user["email"], html_body)

            if sent:
                update_last_brief_sent(user["user_id"])
                stats["sent"] += 1
            else:
                stats["failed"] += 1

        except Exception:
            logger.exception("Error generating brief for user %d", user["user_id"])
            stats["failed"] += 1

    logger.info(
        "Brief send complete: %d sent, %d skipped, %d failed of %d total",
        stats["sent"], stats["skipped"], stats["failed"], stats["total"],
    )
    return stats
