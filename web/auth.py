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

def create_user(email: str) -> dict:
    """Create a new user. Returns user dict. Sets is_admin if email matches ADMIN_EMAIL."""
    _ensure_schema()
    is_admin = bool(ADMIN_EMAIL and email.lower() == ADMIN_EMAIL.lower())
    if BACKEND == "postgres":
        sql = """
            INSERT INTO users (email, is_admin)
            VALUES (%s, %s)
            RETURNING user_id
        """
        user_id = execute_write(sql, (email, is_admin), return_id=True)
    else:
        # DuckDB: manual ID assignment
        row = query_one("SELECT COALESCE(MAX(user_id), 0) + 1 FROM users")
        user_id = row[0]
        conn = get_connection()
        try:
            sql = "INSERT INTO users (user_id, email, is_admin) VALUES (?, ?, ?)"
            conn.execute(sql, (user_id, email, is_admin))
        finally:
            conn.close()
    return get_user_by_id(user_id)


def get_user_by_email(email: str) -> dict | None:
    """Look up user by email, return dict or None."""
    _ensure_schema()
    row = query_one(
        "SELECT user_id, email, display_name, role, firm_name, entity_id, "
        "email_verified, is_admin, is_active FROM users WHERE email = %s",
        (email,),
    )
    return _row_to_user(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    """Look up user by user_id, return dict or None."""
    _ensure_schema()
    row = query_one(
        "SELECT user_id, email, display_name, role, firm_name, entity_id, "
        "email_verified, is_admin, is_active FROM users WHERE user_id = %s",
        (user_id,),
    )
    return _row_to_user(row) if row else None


def _row_to_user(row) -> dict:
    """Convert a user row tuple to a dict."""
    return {
        "user_id": row[0],
        "email": row[1],
        "display_name": row[2],
        "role": row[3],
        "firm_name": row[4],
        "entity_id": row[5],
        "email_verified": row[6],
        "is_admin": row[7],
        "is_active": row[8],
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


def send_magic_link(email: str, token: str) -> bool:
    """Send the magic link via email (or log to console in dev mode).

    Returns True if sent/logged successfully.
    """
    link = f"{BASE_URL}/auth/verify/{token}"

    if not SMTP_HOST:
        logger.info("Magic link for %s: %s", email, link)
        return True

    try:
        msg = EmailMessage()
        msg["Subject"] = "Sign in to sfpermits.ai"
        msg["From"] = SMTP_FROM
        msg["To"] = email
        msg.set_content(
            f"Click to sign in to sfpermits.ai:\n\n{link}\n\n"
            f"This link expires in {TOKEN_EXPIRY_MINUTES} minutes."
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS or "")
            server.send_message(msg)
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
        "block, lot, entity_id, neighborhood, label, created_at "
        "FROM watch_items WHERE user_id = %s AND is_active = TRUE "
        "ORDER BY created_at DESC",
        (user_id,),
    )
    return [
        {
            "watch_id": r[0], "watch_type": r[1], "permit_number": r[2],
            "street_number": r[3], "street_name": r[4], "block": r[5],
            "lot": r[6], "entity_id": r[7], "neighborhood": r[8],
            "label": r[9], "created_at": r[10],
        }
        for r in rows
    ]


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
