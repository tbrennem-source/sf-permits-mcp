"""Email delivery for nightly feedback triage report.

Renders the triage report as HTML email and sends via SMTP to all active admins.
Called by the /cron/send-briefs endpoint after user morning briefs.

Pattern: follows web/email_brief.py exactly.
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import date, datetime, timezone
from email.message import EmailMessage

from flask import render_template

from web.activity import get_admin_users

logger = logging.getLogger(__name__)

# ── Config (same env vars as email_brief.py) ──────────────────────

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@sfpermits.ai")
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5001")


# ── Email rendering ───────────────────────────────────────────────

def render_triage_email(triage_data: dict) -> str:
    """Render the triage report as an HTML email string."""
    return render_template(
        "triage_report_email.html",
        base_url=BASE_URL,
        tier1=triage_data.get("tier1", []),
        tier2=triage_data.get("tier2", []),
        tier3=triage_data.get("tier3", []),
        counts=triage_data.get("counts", {}),
        auto_resolved=triage_data.get("auto_resolved", 0),
        total_triaged=triage_data.get("total_triaged", 0),
        report_date=date.today().strftime("%B %d, %Y"),
    )


# ── SMTP send ─────────────────────────────────────────────────────

def send_triage_email(to_email: str, html_body: str) -> bool:
    """Send a triage report email to a single admin."""
    today = date.today().strftime("%b %d")
    subject = f"Feedback Triage Report \u2014 {today} \u2014 sfpermits.ai"

    if not SMTP_HOST:
        logger.info(
            "SMTP not configured \u2014 would send triage report to %s (%d chars)",
            to_email, len(html_body),
        )
        return True  # Dev mode pass-through

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email

        msg.set_content(
            f"Your sfpermits.ai feedback triage report is ready.\n\n"
            f"View feedback queue: {BASE_URL}/admin/feedback\n\n"
        )
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS or "")
            server.send_message(msg)

        return True
    except Exception:
        logger.exception("Failed to send triage report to %s", to_email)
        return False


# ── Batch send to all admins ──────────────────────────────────────

def _is_today(iso_timestamp) -> bool:
    """Check if a timestamp is from today (local time)."""
    if not iso_timestamp:
        return False
    try:
        if isinstance(iso_timestamp, str):
            dt = datetime.fromisoformat(iso_timestamp)
        else:
            dt = iso_timestamp
        # Convert to local time for comparison with date.today()
        local_date = dt.astimezone().date() if dt.tzinfo else dt.date()
        return local_date == date.today()
    except (ValueError, TypeError):
        return False


def send_triage_reports() -> dict:
    """Send triage report to all active admin users.

    Re-reads current feedback state (post-triage), classifies read-only,
    and sends to all admins. Skips if 0 unresolved items.
    """
    from scripts.feedback_triage import (
        fetch_feedback, preprocess, detect_duplicates, classify_tier,
    )

    admins = get_admin_users()
    stats = {"total": len(admins), "sent": 0, "failed": 0}
    logger.info("Preparing triage report for %d admins", len(admins))

    host = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost:5001")
    cron_secret = os.environ.get("CRON_SECRET", "")

    if not cron_secret:
        logger.warning("CRON_SECRET not set \u2014 skipping triage report")
        stats["skipped_reason"] = "no_cron_secret"
        return stats

    # Fetch current state (Tier 1 items already resolved by nightly run)
    unresolved_data = fetch_feedback(host, cron_secret,
                                     statuses=["new", "reviewed"], limit=500)
    resolved_data = fetch_feedback(host, cron_secret,
                                   statuses=["resolved"], limit=100)

    unresolved = preprocess(unresolved_data["items"])
    resolved_items = resolved_data["items"]
    duplicates = detect_duplicates(unresolved)

    # Classify remaining items (read-only, no auto-resolve)
    tier2, tier3 = [], []
    for item in unresolved:
        tier, reason = classify_tier(item, duplicates, resolved_items)
        item["tier"] = tier
        item["tier_reason"] = reason
        if tier == 2:
            tier2.append(item)
        else:
            tier3.append(item)

    # Find items auto-resolved today (by admin_note prefix)
    tier1_resolved = [
        i for i in resolved_items
        if i.get("admin_note", "").startswith("[Auto-triage]")
        and _is_today(i.get("resolved_at"))
    ]

    total_items = len(unresolved) + len(tier1_resolved)
    if total_items == 0:
        logger.info("No feedback to report \u2014 skipping triage report emails")
        stats["skipped_reason"] = "no_unresolved_feedback"
        return stats

    triage_data = {
        "tier1": tier1_resolved,
        "tier2": tier2,
        "tier3": tier3,
        "counts": unresolved_data["counts"],
        "auto_resolved": len(tier1_resolved),
        "total_triaged": total_items,
    }

    html_body = render_triage_email(triage_data)

    for admin in admins:
        sent = send_triage_email(admin["email"], html_body)
        if sent:
            stats["sent"] += 1
        else:
            stats["failed"] += 1

    logger.info(
        "Triage report: %d sent, %d failed of %d admins",
        stats["sent"], stats["failed"], stats["total"],
    )
    return stats
