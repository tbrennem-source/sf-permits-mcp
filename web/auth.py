"""Authentication and watch list logic for sfpermits.ai.

Passwordless magic-link authentication with Flask sessions.
No external dependencies beyond Flask + stdlib.
"""

from __future__ import annotations

import logging
import os
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from src.db import BACKEND, execute_write, get_connection, init_user_schema, query, query_one

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5001")
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@sfpermits.ai")
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")

TOKEN_EXPIRY_MINUTES = 30

# ── Invite Codes ─────────────────────────────────────────────────
# Comma-separated list of valid invite codes. If empty/unset, signup is open.
# Example: INVITE_CODES=sfp-team-5b032f5b,sfp-amy-22204097
_INVITE_CODES_RAW = os.environ.get("INVITE_CODES", "")
INVITE_CODES: set[str] = {
    c.strip() for c in _INVITE_CODES_RAW.split(",") if c.strip()
}


def invite_required() -> bool:
    """Whether an invite code is required to create a new account."""
    return len(INVITE_CODES) > 0


def validate_invite_code(code: str) -> bool:
    """Check if an invite code is valid. Case-sensitive."""
    if not invite_required():
        return True  # No codes configured → open signup
    return code.strip() in INVITE_CODES

_schema_initialized = False


def _ensure_schema():
    """Lazily initialize user tables for DuckDB dev mode."""
    global _schema_initialized
    if _schema_initialized:
        return
    if BACKEND == "duckdb":
        init_user_schema()
    _schema_initialized = True


# ── User CRUD ─────────────────────────────────────────────────────

def create_user(
    email: str,
    invite_code: str | None = None,
    referral_source: str = "invited",
) -> dict:
    """Create a new user. Returns user dict.

    Sets is_admin if email matches ADMIN_EMAIL.
    Stores invite_code for cohort tracking.
    referral_source: 'invited' | 'shared_link' | 'organic'
    """
    _ensure_schema()
    is_admin = bool(ADMIN_EMAIL and email.lower() == ADMIN_EMAIL.lower())
    code = invite_code.strip() if invite_code else None
    ref_src = referral_source or "invited"
    if BACKEND == "postgres":
        sql = """
            INSERT INTO users (email, is_admin, invite_code, referral_source)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id
        """
        user_id = execute_write(sql, (email, is_admin, code, ref_src), return_id=True)
    else:
        # DuckDB: manual ID assignment
        row = query_one("SELECT COALESCE(MAX(user_id), 0) + 1 FROM users")
        user_id = row[0]
        conn = get_connection()
        try:
            sql = (
                "INSERT INTO users (user_id, email, is_admin, invite_code, referral_source) "
                "VALUES (?, ?, ?, ?, ?)"
            )
            conn.execute(sql, (user_id, email, is_admin, code, ref_src))
        finally:
            conn.close()
    return get_user_by_id(user_id)


def get_user_by_email(email: str) -> dict | None:
    """Look up user by email, return dict or None."""
    _ensure_schema()
    row = query_one(
        "SELECT user_id, email, display_name, role, firm_name, entity_id, "
        "email_verified, is_admin, is_active, "
        "COALESCE(brief_frequency, 'none'), invite_code, "
        "primary_street_number, primary_street_name, "
        "COALESCE(subscription_tier, 'free'), voice_style, "
        "COALESCE(referral_source, 'invited'), detected_persona, "
        "COALESCE(notify_permit_changes, FALSE), notify_email, "
        "COALESCE(onboarding_complete, FALSE) "
        "FROM users WHERE email = %s",
        (email,),
    )
    return _row_to_user(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    """Look up user by user_id, return dict or None."""
    _ensure_schema()
    row = query_one(
        "SELECT user_id, email, display_name, role, firm_name, entity_id, "
        "email_verified, is_admin, is_active, "
        "COALESCE(brief_frequency, 'none'), invite_code, "
        "primary_street_number, primary_street_name, "
        "COALESCE(subscription_tier, 'free'), voice_style, "
        "COALESCE(referral_source, 'invited'), detected_persona, "
        "COALESCE(notify_permit_changes, FALSE), notify_email, "
        "COALESCE(onboarding_complete, FALSE) "
        "FROM users WHERE user_id = %s",
        (user_id,),
    )
    return _row_to_user(row) if row else None


def _row_to_user(row) -> dict:
    """Convert a user row tuple to a dict.

    Admin status is derived from BOTH the DB flag and the ADMIN_EMAIL env var,
    so that adding ADMIN_EMAIL after a user already exists still grants admin.
    Row columns (0-indexed):
        0: user_id, 1: email, 2: display_name, 3: role, 4: firm_name, 5: entity_id,
        6: email_verified, 7: is_admin, 8: is_active,
        9: brief_frequency, 10: invite_code,
        11: primary_street_number, 12: primary_street_name,
        13: subscription_tier, 14: voice_style,
        15: referral_source, 16: detected_persona,
        17: notify_permit_changes, 18: notify_email,
        19: onboarding_complete
    """
    email = row[1]
    db_admin = row[7]
    # Dynamic admin check: DB flag OR email matches ADMIN_EMAIL
    is_admin = bool(db_admin) or bool(
        ADMIN_EMAIL and email and email.lower() == ADMIN_EMAIL.lower()
    )
    return {
        "user_id": row[0],
        "email": email,
        "display_name": row[2],
        "role": row[3],
        "firm_name": row[4],
        "entity_id": row[5],
        "email_verified": row[6],
        "is_admin": is_admin,
        "is_active": row[8],
        "brief_frequency": row[9] if len(row) > 9 else "none",
        "invite_code": row[10] if len(row) > 10 else None,
        "primary_street_number": row[11] if len(row) > 11 else None,
        "primary_street_name": row[12] if len(row) > 12 else None,
        "subscription_tier": row[13] if len(row) > 13 else "free",
        "voice_style": row[14] if len(row) > 14 else None,
        "referral_source": row[15] if len(row) > 15 else "invited",
        "detected_persona": row[16] if len(row) > 16 else None,
        "notify_permit_changes": bool(row[17]) if len(row) > 17 else False,
        "notify_email": row[18] if len(row) > 18 else None,
        "onboarding_complete": bool(row[19]) if len(row) > 19 else False,
    }


def get_or_create_user(email: str) -> dict:
    """Get existing user or create a new one."""
    user = get_user_by_email(email)
    if user:
        return user
    return create_user(email)


# ── Magic Link Tokens ─────────────────────────────────────────────

def create_magic_token(user_id: int, purpose: str = "login") -> str:
    """Generate a magic link token, store it, return the token string."""
    _ensure_schema()
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRY_MINUTES)

    if BACKEND == "postgres":
        execute_write(
            "INSERT INTO auth_tokens (user_id, token, purpose, expires_at) "
            "VALUES (%s, %s, %s, %s)",
            (user_id, token, purpose, expires_at),
        )
    else:
        row = query_one("SELECT COALESCE(MAX(token_id), 0) + 1 FROM auth_tokens")
        token_id = row[0]
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO auth_tokens (token_id, user_id, token, purpose, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (token_id, user_id, token, purpose, expires_at),
            )
        finally:
            conn.close()
    return token


def verify_magic_token(token: str) -> dict | None:
    """Verify a magic link token. Returns user dict if valid, None otherwise.

    Marks the token as used and updates user's last_login_at and email_verified.
    """
    _ensure_schema()
    row = query_one(
        "SELECT token_id, user_id, purpose, expires_at, used_at "
        "FROM auth_tokens WHERE token = %s",
        (token,),
    )
    if not row:
        return None

    token_id, user_id, purpose, expires_at, used_at = row

    # Already used?
    if used_at is not None:
        return None

    # Expired? DuckDB TIMESTAMP strips tz and converts to local time,
    # so compare using naive local time for DuckDB, tz-aware UTC for Postgres.
    if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is not None:
        now = datetime.now(timezone.utc)
    else:
        now = datetime.now()
    if now > expires_at:
        return None

    # Mark as used + update user
    if BACKEND == "postgres":
        execute_write(
            "UPDATE auth_tokens SET used_at = NOW() WHERE token_id = %s",
            (token_id,),
        )
        execute_write(
            "UPDATE users SET last_login_at = NOW(), email_verified = TRUE "
            "WHERE user_id = %s",
            (user_id,),
        )
    else:
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE auth_tokens SET used_at = CURRENT_TIMESTAMP WHERE token_id = ?",
                (token_id,),
            )
            conn.execute(
                "UPDATE users SET last_login_at = CURRENT_TIMESTAMP, email_verified = TRUE "
                "WHERE user_id = ?",
                (user_id,),
            )
        finally:
            conn.close()

    return get_user_by_id(user_id)


def send_magic_link(email: str, token: str, sync: bool = False) -> bool:
    """Send the magic link via email (or log to console in dev mode).

    Args:
        sync: If True, send synchronously (for callers already in background).
              Default False sends via background thread pool.

    Returns True if sent/logged successfully.
    """
    link = f"{BASE_URL}/auth/verify/{token}"

    if not SMTP_HOST:
        logger.info("Magic link for %s: %s", email, link)
        return True

    if sync:
        return _send_magic_link_sync(email, link)

    from web.background import submit_task
    submit_task(_send_magic_link_sync, email, link)
    return True  # Optimistically return True — email delivery is fire-and-forget


def _send_magic_link_sync(email: str, link: str) -> bool:
    """Send the magic link synchronously via SMTP."""
    try:
        msg = EmailMessage()
        msg["Subject"] = "Your sfpermits.ai sign-in link"
        msg["From"] = f"SF Permits AI <{SMTP_FROM}>"
        msg["To"] = email
        msg["List-Unsubscribe"] = f"<mailto:{SMTP_FROM}?subject=unsubscribe>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        # Plain text version
        msg.set_content(
            f"Sign in to sfpermits.ai\n\n"
            f"Click the link below to sign in:\n\n"
            f"{link}\n\n"
            f"This link expires in {TOKEN_EXPIRY_MINUTES} minutes.\n\n"
            f"If you didn't request this, you can safely ignore this email.\n\n"
            f"--\n"
            f"sfpermits.ai - San Francisco Building Permit Intelligence"
        )

        # HTML version — improves deliverability significantly
        msg.add_alternative(
            f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
  <div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #2563eb;">
    <h1 style="color: #2563eb; margin: 0; font-size: 24px;">sfpermits.ai</h1>
    <p style="color: #666; margin: 5px 0 0 0; font-size: 14px;">San Francisco Building Permit Intelligence</p>
  </div>
  <div style="padding: 30px 0;">
    <h2 style="font-size: 20px; margin: 0 0 15px 0;">Sign in to your account</h2>
    <p style="line-height: 1.6;">Click the button below to securely sign in. No password needed.</p>
    <div style="text-align: center; padding: 25px 0;">
      <a href="{link}" style="background-color: #2563eb; color: white; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px; display: inline-block;">Sign In</a>
    </div>
    <p style="font-size: 13px; color: #888; line-height: 1.5;">This link expires in {TOKEN_EXPIRY_MINUTES} minutes. If you didn't request this, you can safely ignore this email.</p>
    <p style="font-size: 12px; color: #aaa; margin-top: 10px;">If the button doesn't work, copy and paste this URL into your browser:<br>
    <a href="{link}" style="color: #2563eb; word-break: break-all;">{link}</a></p>
  </div>
  <div style="border-top: 1px solid #eee; padding-top: 15px; font-size: 12px; color: #999; text-align: center;">
    <p>sfpermits.ai &mdash; Permit tracking for San Francisco homeowners</p>
  </div>
</body>
</html>""",
            subtype="html",
        )

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS or "")
            server.send_message(msg)
        logger.info("Magic link sent to %s", email)
        return True
    except Exception:
        logger.exception("Failed to send magic link to %s", email)
        return False


# ── Watch List CRUD ───────────────────────────────────────────────

def add_watch(user_id: int, watch_type: str, **kwargs) -> dict:
    """Add a watch item. Returns the watch item dict.

    Idempotent: if the user already watches the same item, returns existing.
    """
    _ensure_schema()
    existing = check_watch(user_id, watch_type, **kwargs)
    if existing:
        return existing

    label = kwargs.get("label", "")
    permit_number = kwargs.get("permit_number")
    street_number = kwargs.get("street_number")
    street_name = kwargs.get("street_name")
    block = kwargs.get("block")
    lot = kwargs.get("lot")
    entity_id = kwargs.get("entity_id")
    neighborhood = kwargs.get("neighborhood")

    if BACKEND == "postgres":
        watch_id = execute_write(
            "INSERT INTO watch_items "
            "(user_id, watch_type, permit_number, street_number, street_name, "
            "block, lot, entity_id, neighborhood, label) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING watch_id",
            (user_id, watch_type, permit_number, street_number, street_name,
             block, lot, entity_id, neighborhood, label),
            return_id=True,
        )
    else:
        row = query_one("SELECT COALESCE(MAX(watch_id), 0) + 1 FROM watch_items")
        watch_id = row[0]
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO watch_items "
                "(watch_id, user_id, watch_type, permit_number, street_number, "
                "street_name, block, lot, entity_id, neighborhood, label) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (watch_id, user_id, watch_type, permit_number, street_number,
                 street_name, block, lot, entity_id, neighborhood, label),
            )
        finally:
            conn.close()

    return {"watch_id": watch_id, "watch_type": watch_type, "label": label,
            "permit_number": permit_number, "street_number": street_number,
            "street_name": street_name, "block": block, "lot": lot,
            "entity_id": entity_id, "neighborhood": neighborhood}


def remove_watch(watch_id: int, user_id: int) -> bool:
    """Soft-delete a watch item. Returns True if found and deactivated."""
    _ensure_schema()
    if BACKEND == "postgres":
        execute_write(
            "UPDATE watch_items SET is_active = FALSE "
            "WHERE watch_id = %s AND user_id = %s",
            (watch_id, user_id),
        )
    else:
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE watch_items SET is_active = FALSE "
                "WHERE watch_id = ? AND user_id = ?",
                (watch_id, user_id),
            )
        finally:
            conn.close()
    return True


def get_watches(user_id: int) -> list[dict]:
    """Get all active watch items for a user."""
    _ensure_schema()
    rows = query(
        "SELECT watch_id, watch_type, permit_number, street_number, street_name, "
        "block, lot, entity_id, neighborhood, label, created_at, "
        "COALESCE(tags, '') "
        "FROM watch_items WHERE user_id = %s AND is_active = TRUE "
        "ORDER BY created_at DESC",
        (user_id,),
    )
    return [
        {
            "watch_id": r[0], "watch_type": r[1], "permit_number": r[2],
            "street_number": r[3], "street_name": r[4], "block": r[5],
            "lot": r[6], "entity_id": r[7], "neighborhood": r[8],
            "label": r[9], "created_at": r[10], "tags": r[11],
        }
        for r in rows
    ]


def update_watch_label(watch_id: int, user_id: int, label: str) -> bool:
    """Update a watch item's label. Returns True if found and updated."""
    _ensure_schema()
    if BACKEND == "postgres":
        execute_write(
            "UPDATE watch_items SET label = %s "
            "WHERE watch_id = %s AND user_id = %s AND is_active = TRUE",
            (label, watch_id, user_id),
        )
    else:
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE watch_items SET label = ? "
                "WHERE watch_id = ? AND user_id = ? AND is_active = TRUE",
                (label, watch_id, user_id),
            )
        finally:
            conn.close()
    return True


def check_watch(user_id: int, watch_type: str, **kwargs) -> dict | None:
    """Check if user already watches an item. Returns watch dict or None."""
    _ensure_schema()
    # Build WHERE clause based on watch_type
    conditions = ["user_id = %s", "watch_type = %s", "is_active = TRUE"]
    params: list = [user_id, watch_type]

    if watch_type == "permit":
        conditions.append("permit_number = %s")
        params.append(kwargs.get("permit_number"))
    elif watch_type == "address":
        conditions.append("street_number = %s")
        conditions.append("street_name = %s")
        params.extend([kwargs.get("street_number"), kwargs.get("street_name")])
    elif watch_type == "parcel":
        conditions.append("block = %s")
        conditions.append("lot = %s")
        params.extend([kwargs.get("block"), kwargs.get("lot")])
    elif watch_type == "entity":
        conditions.append("entity_id = %s")
        params.append(kwargs.get("entity_id"))
    elif watch_type == "neighborhood":
        conditions.append("neighborhood = %s")
        params.append(kwargs.get("neighborhood"))

    where = " AND ".join(conditions)
    row = query_one(
        f"SELECT watch_id, watch_type, permit_number, street_number, street_name, "
        f"block, lot, entity_id, neighborhood, label "
        f"FROM watch_items WHERE {where}",
        params,
    )
    if not row:
        return None
    return {
        "watch_id": row[0], "watch_type": row[1], "permit_number": row[2],
        "street_number": row[3], "street_name": row[4], "block": row[5],
        "lot": row[6], "entity_id": row[7], "neighborhood": row[8],
        "label": row[9],
    }


# ---------------------------------------------------------------------------
# Watch tags
# ---------------------------------------------------------------------------

def update_watch_tags(watch_id: int, user_id: int, tags: str) -> bool:
    """Update tags for a watch item. Tags are comma-separated, lowercase, trimmed."""
    _ensure_schema()
    clean = ",".join(t.strip().lower() for t in tags.split(",") if t.strip())
    if BACKEND == "postgres":
        execute_write(
            "UPDATE watch_items SET tags = %s WHERE watch_id = %s AND user_id = %s AND is_active = TRUE",
            (clean, watch_id, user_id),
        )
    else:
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE watch_items SET tags = ? WHERE watch_id = ? AND user_id = ? AND is_active = TRUE",
                (clean, watch_id, user_id),
            )
        finally:
            conn.close()
    return True


def get_user_tags(user_id: int) -> list[str]:
    """Get all distinct tags across user's active watches."""
    _ensure_schema()
    rows = query(
        "SELECT tags FROM watch_items WHERE user_id = %s AND is_active = TRUE AND tags != ''",
        (user_id,),
    )
    all_tags: set[str] = set()
    for row in rows:
        if row[0]:
            all_tags.update(t.strip() for t in row[0].split(",") if t.strip())
    return sorted(all_tags)


# ---------------------------------------------------------------------------
# Primary address
# ---------------------------------------------------------------------------

def set_primary_address(user_id: int, street_number: str, street_name: str) -> bool:
    """Set the user's primary address. Returns True on success."""
    _ensure_schema()
    execute_write(
        "UPDATE users SET primary_street_number = %s, primary_street_name = %s "
        "WHERE user_id = %s",
        (street_number, street_name, user_id),
    )
    return True


def clear_primary_address(user_id: int) -> bool:
    """Clear the user's primary address. Returns True on success."""
    _ensure_schema()
    execute_write(
        "UPDATE users SET primary_street_number = NULL, primary_street_name = NULL "
        "WHERE user_id = %s",
        (user_id,),
    )
    return True


def get_primary_address(user_id: int) -> dict | None:
    """Get the user's primary address, or None if not set."""
    _ensure_schema()
    row = query_one(
        "SELECT primary_street_number, primary_street_name "
        "FROM users WHERE user_id = %s",
        (user_id,),
    )
    if row and row[0] and row[1]:
        return {"street_number": row[0], "street_name": row[1]}
    return None


# ---------------------------------------------------------------------------
# Beta request queue (organic signup — three-tier access)
# ---------------------------------------------------------------------------

# Rate limit: max 3 beta requests per IP per hour
_BETA_REQUEST_BUCKETS: dict = {}
_BETA_RATE_LIMIT_MAX = 3
_BETA_RATE_LIMIT_WINDOW = 3600  # seconds


def is_beta_rate_limited(ip: str) -> bool:
    """Check if an IP has exceeded the beta request rate limit."""
    import time
    now = time.time()
    window_start = now - _BETA_RATE_LIMIT_WINDOW
    bucket = _BETA_REQUEST_BUCKETS.get(ip, [])
    # Prune old entries
    bucket = [t for t in bucket if t > window_start]
    _BETA_REQUEST_BUCKETS[ip] = bucket
    return len(bucket) >= _BETA_RATE_LIMIT_MAX


def record_beta_request_ip(ip: str) -> None:
    """Record a beta request for rate limiting."""
    import time
    bucket = _BETA_REQUEST_BUCKETS.get(ip, [])
    bucket.append(time.time())
    _BETA_REQUEST_BUCKETS[ip] = bucket


def create_beta_request(email: str, name: str | None, reason: str | None, ip: str) -> dict:
    """Create a beta access request. Returns dict with id and status."""
    _ensure_schema()
    if BACKEND == "postgres":
        row = query_one(
            "SELECT id, status FROM beta_requests WHERE email = %s",
            (email,),
        )
        if row:
            return {"id": row[0], "status": row[1], "existing": True}
        req_id = execute_write(
            "INSERT INTO beta_requests (email, name, reason, ip) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (email, name, reason, ip),
            return_id=True,
        )
    else:
        row = query_one(
            "SELECT id, status FROM beta_requests WHERE email = %s",
            (email,),
        )
        if row:
            return {"id": row[0], "status": row[1], "existing": True}
        id_row = query_one("SELECT COALESCE(MAX(id), 0) + 1 FROM beta_requests")
        req_id = id_row[0]
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO beta_requests (id, email, name, reason, ip) "
                "VALUES (?, ?, ?, ?, ?)",
                (req_id, email, name, reason, ip),
            )
        finally:
            conn.close()
    return {"id": req_id, "status": "pending", "existing": False}


def get_pending_beta_requests() -> list[dict]:
    """Get all pending beta requests for admin queue."""
    _ensure_schema()
    rows = query(
        "SELECT id, email, name, reason, ip, created_at "
        "FROM beta_requests WHERE status = %s ORDER BY created_at ASC",
        ("pending",),
    )
    return [
        {
            "id": r[0], "email": r[1], "name": r[2],
            "reason": r[3], "ip": r[4], "created_at": r[5],
        }
        for r in rows
    ]


def approve_beta_request(req_id: int) -> dict | None:
    """Approve a beta request, create/activate user, return user dict."""
    _ensure_schema()
    row = query_one(
        "SELECT email, name FROM beta_requests WHERE id = %s AND status = %s",
        (req_id, "pending"),
    )
    if not row:
        return None
    email, name = row[0], row[1]

    # Mark request approved
    execute_write(
        "UPDATE beta_requests SET status = %s, approved_at = %s WHERE id = %s",
        ("approved", datetime.now(timezone.utc), req_id),
    )

    # Create or activate user with shared_link referral source (full access)
    user = get_user_by_email(email)
    if not user:
        user = create_user(email, referral_source="organic")
    elif not user.get("is_active"):
        execute_write(
            "UPDATE users SET is_active = TRUE WHERE user_id = %s",
            (user["user_id"],),
        )
        user = get_user_by_id(user["user_id"])

    # Mark beta_approved_at on user
    execute_write(
        "UPDATE users SET beta_approved_at = %s WHERE user_id = %s",
        (datetime.now(timezone.utc), user["user_id"]),
    )
    return user


def deny_beta_request(req_id: int) -> bool:
    """Deny a beta request."""
    _ensure_schema()
    execute_write(
        "UPDATE beta_requests SET status = %s, reviewed_at = %s WHERE id = %s",
        ("denied", datetime.now(timezone.utc), req_id),
    )
    return True


def send_beta_welcome_email(email: str, magic_link: str) -> bool:
    """Send beta approval welcome email with magic link.

    Called when admin approves a beta request. Includes a one-click sign-in
    button so the new user lands immediately in the app.

    Args:
        email: Recipient email address.
        magic_link: Full URL for one-click sign-in (e.g. BASE_URL/auth/verify/<token>).

    Returns True on success (or dev mode with SMTP not configured).
    """
    if not SMTP_HOST:
        logger.info("Beta welcome email for %s: %s (SMTP not configured)", email, magic_link)
        return True
    try:
        msg = EmailMessage()
        msg["Subject"] = "You're in — sfpermits.ai beta access approved"
        msg["From"] = f"SF Permits AI <{SMTP_FROM}>"
        msg["To"] = email
        msg["List-Unsubscribe"] = f"<mailto:{SMTP_FROM}?subject=unsubscribe>"

        # Plain text version
        msg.set_content(
            f"Welcome to sfpermits.ai!\n\n"
            f"Your beta access request has been approved. Click the link below to sign in:\n\n"
            f"{magic_link}\n\n"
            f"This link expires in {TOKEN_EXPIRY_MINUTES} minutes.\n\n"
            f"After signing in, we'll walk you through your first search, property report, "
            f"and how to set up your watchlist.\n\n"
            f"--\n"
            f"sfpermits.ai - San Francisco Building Permit Intelligence"
        )

        # HTML version — brand colors, inline CSS for email client compatibility
        html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#0B0F19;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0B0F19;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
        <!-- Header -->
        <tr>
          <td style="background-color:#131825;border-radius:12px 12px 0 0;padding:32px 40px;border-bottom:1px solid rgba(255,255,255,0.06);text-align:center;">
            <span style="font-family:'Courier New',Courier,monospace;font-size:22px;font-weight:700;color:#22D3EE;letter-spacing:-0.5px;">sfpermits.ai</span>
            <p style="color:#8B95A8;font-size:13px;margin:6px 0 0 0;letter-spacing:0.05em;text-transform:uppercase;">San Francisco Building Permit Intelligence</p>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="background-color:#131825;padding:40px 40px 32px 40px;">
            <h1 style="color:#E8ECF4;font-size:24px;font-weight:700;margin:0 0 16px 0;line-height:1.3;">You're in — beta access approved</h1>
            <p style="color:#8B95A8;font-size:16px;line-height:1.6;margin:0 0 24px 0;">
              Welcome to sfpermits.ai! Your request has been approved. Click the button below to sign in — no password needed.
            </p>
            <!-- CTA Button -->
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr><td align="center" style="padding:8px 0 32px 0;">
                <a href="{magic_link}"
                   style="display:inline-block;background:linear-gradient(135deg,#22D3EE,#60A5FA);color:#0B0F19;text-decoration:none;padding:16px 40px;border-radius:8px;font-weight:700;font-size:16px;letter-spacing:0.02em;">
                  Sign in to sfpermits.ai
                </a>
              </td></tr>
            </table>
            <p style="color:#5A6478;font-size:13px;line-height:1.5;margin:0 0 24px 0;">
              This link expires in {TOKEN_EXPIRY_MINUTES} minutes. If the button doesn&rsquo;t work, copy and paste this URL:
              <br><a href="{magic_link}" style="color:#22D3EE;word-break:break-all;">{magic_link}</a>
            </p>
            <hr style="border:none;border-top:1px solid rgba(255,255,255,0.06);margin:24px 0;">
            <!-- What to expect -->
            <p style="color:#E8ECF4;font-size:15px;font-weight:600;margin:0 0 12px 0;">What happens next</p>
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding:8px 0;">
                  <span style="color:#22D3EE;font-weight:700;">1.</span>
                  <span style="color:#8B95A8;font-size:14px;"> Sign in with the button above</span>
                </td>
              </tr>
              <tr>
                <td style="padding:8px 0;">
                  <span style="color:#22D3EE;font-weight:700;">2.</span>
                  <span style="color:#8B95A8;font-size:14px;"> Run your first address search</span>
                </td>
              </tr>
              <tr>
                <td style="padding:8px 0;">
                  <span style="color:#22D3EE;font-weight:700;">3.</span>
                  <span style="color:#8B95A8;font-size:14px;"> Add properties to your watchlist for permit alerts</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background-color:#0F1520;border-radius:0 0 12px 12px;padding:20px 40px;text-align:center;border-top:1px solid rgba(255,255,255,0.06);">
            <p style="color:#5A6478;font-size:12px;margin:0;">sfpermits.ai &mdash; Permit intelligence for San Francisco homeowners and expediters</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS or "")
            server.send_message(msg)
        logger.info("Beta welcome email sent to %s", email)
        return True
    except Exception:
        logger.exception("Failed to send beta welcome email to %s", email)
        return False


def send_beta_confirmation_email(email: str) -> bool:
    """Send confirmation email to organic beta requester."""
    if not SMTP_HOST:
        logger.info("Beta request confirmation for %s (SMTP not configured)", email)
        return True
    try:
        msg = EmailMessage()
        msg["Subject"] = "Your sfpermits.ai beta request received"
        msg["From"] = f"SF Permits AI <{SMTP_FROM}>"
        msg["To"] = email
        msg.set_content(
            "Thank you for your interest in sfpermits.ai!\n\n"
            "We've received your beta access request and will review it shortly.\n"
            "You'll receive a sign-in link by email when your request is approved.\n\n"
            "--\nsfpermits.ai - San Francisco Building Permit Intelligence"
        )
        msg.add_alternative(
            """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
             max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
  <div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #2563eb;">
    <h1 style="color: #2563eb; margin: 0; font-size: 24px;">sfpermits.ai</h1>
  </div>
  <div style="padding: 30px 0;">
    <h2 style="font-size: 20px;">Beta request received</h2>
    <p>Thank you for your interest in sfpermits.ai! We've received your request and will review it shortly.</p>
    <p>You'll receive a sign-in link by email when your request is approved.</p>
  </div>
  <div style="border-top: 1px solid #eee; padding-top: 15px; font-size: 12px; color: #999; text-align: center;">
    <p>sfpermits.ai &mdash; AI-powered permit guidance for San Francisco</p>
  </div>
</body>
</html>""",
            subtype="html",
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS or "")
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send beta confirmation to %s", email)
        return False


# === SESSION A: TEST LOGIN ===

# Required env vars for test login (must BOTH be set to enable):
#   TESTING=true            — activates the endpoint
#   TEST_LOGIN_SECRET=<str> — shared secret validated on every request

_TESTING_ENABLED = os.environ.get("TESTING", "").lower() in ("1", "true", "yes")
TEST_LOGIN_SECRET = os.environ.get("TEST_LOGIN_SECRET", "")

# Default email used when none is specified
TEST_DEFAULT_EMAIL = "test-admin@sfpermits.ai"


def handle_test_login(request_json: dict) -> tuple[dict | None, int]:
    """Process a test-login request.

    Returns (response_dict, status_code).  The caller is responsible for
    creating the Flask session from the returned user dict.

    Status codes:
      404 — TESTING not enabled (endpoint does not exist)
      403 — wrong or missing secret
      200 — success; response_dict contains the user record
    """
    # Reload at call time so tests can monkeypatch os.environ
    testing_enabled = os.environ.get("TESTING", "").lower() in ("1", "true", "yes")
    secret_configured = os.environ.get("TEST_LOGIN_SECRET", "")

    if not testing_enabled:
        return None, 404

    provided_secret = (request_json or {}).get("secret", "")
    if not secret_configured or provided_secret != secret_configured:
        return None, 403

    email = (request_json or {}).get("email", TEST_DEFAULT_EMAIL).strip().lower()

    _ensure_schema()
    user = get_user_by_email(email)
    if not user:
        user = create_user(email)

    # Always sync admin status based on email pattern (handles both new and existing users)
    should_be_admin = "test-admin" in email
    if BACKEND == "postgres":
        execute_write(
            "UPDATE users SET is_admin = %s WHERE user_id = %s",
            (should_be_admin, user["user_id"]),
        )
    else:
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE users SET is_admin = ? WHERE user_id = ?",
                (should_be_admin, user["user_id"]),
            )
        finally:
            conn.close()
    user = get_user_by_id(user["user_id"])

    return user, 200
