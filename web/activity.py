"""Activity logging and feedback for sfpermits.ai.

Lightweight server-side analytics:
  - activity_log: every meaningful user action (search, analyze, login, etc.)
  - feedback: user-submitted bugs, suggestions, questions

No external dependencies. All data in Postgres/DuckDB.
"""

from __future__ import annotations

import hashlib
import json
import logging

from src.db import BACKEND, execute_write, get_connection, init_user_schema, query, query_one

logger = logging.getLogger(__name__)

_schema_initialized = False


def _ensure_schema():
    """Lazily initialize tables for DuckDB dev mode."""
    global _schema_initialized
    if _schema_initialized:
        return
    if BACKEND == "duckdb":
        init_user_schema()
    _schema_initialized = True


# ── Activity Log ──────────────────────────────────────────────────

def log_activity(
    user_id: int | None,
    action: str,
    detail: dict | None = None,
    path: str | None = None,
    ip: str | None = None,
) -> None:
    """Log a user activity event. Fire-and-forget (never raises)."""
    try:
        _ensure_schema()
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else None
        detail_str = json.dumps(detail) if detail else None

        if BACKEND == "postgres":
            execute_write(
                "INSERT INTO activity_log (user_id, action, detail, path, ip_hash) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user_id, action, detail_str, path, ip_hash),
            )
        else:
            row = query_one("SELECT COALESCE(MAX(log_id), 0) + 1 FROM activity_log")
            log_id = row[0]
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO activity_log (log_id, user_id, action, detail, path, ip_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (log_id, user_id, action, detail_str, path, ip_hash),
                )
            finally:
                conn.close()
    except Exception:
        logger.debug("Activity log write failed (non-fatal)", exc_info=True)


def get_recent_activity(limit: int = 50) -> list[dict]:
    """Get recent activity log entries (admin view)."""
    _ensure_schema()
    rows = query(
        "SELECT a.log_id, a.user_id, a.action, a.detail, a.path, a.created_at, "
        "u.email "
        "FROM activity_log a "
        "LEFT JOIN users u ON a.user_id = u.user_id "
        "ORDER BY a.created_at DESC "
        "LIMIT %s",
        (limit,),
    )
    results = []
    for r in rows:
        detail = None
        if r[3]:
            try:
                detail = json.loads(r[3]) if isinstance(r[3], str) else r[3]
            except (json.JSONDecodeError, TypeError):
                detail = {"raw": str(r[3])}
        results.append({
            "log_id": r[0],
            "user_id": r[1],
            "action": r[2],
            "detail": detail,
            "path": r[4],
            "created_at": r[5],
            "email": r[6],
        })
    return results


def get_activity_stats(hours: int = 24) -> dict:
    """Get activity summary stats for the last N hours."""
    _ensure_schema()
    if BACKEND == "postgres":
        time_filter = f"created_at > NOW() - INTERVAL '{hours} hours'"
    else:
        time_filter = f"created_at > CURRENT_TIMESTAMP - INTERVAL {hours} HOUR"

    rows = query(
        f"SELECT action, COUNT(*) FROM activity_log "
        f"WHERE {time_filter} "
        f"GROUP BY action ORDER BY COUNT(*) DESC"
    )
    total = sum(r[1] for r in rows)
    return {
        "total": total,
        "by_action": {r[0]: r[1] for r in rows},
        "hours": hours,
    }


# ── Feedback ──────────────────────────────────────────────────────

def submit_feedback(
    user_id: int | None,
    feedback_type: str,
    message: str,
    page_url: str | None = None,
    screenshot_data: str | None = None,
) -> dict:
    """Submit user feedback. Returns the feedback dict."""
    if feedback_type not in ("bug", "suggestion", "question"):
        feedback_type = "suggestion"

    _ensure_schema()
    if BACKEND == "postgres":
        feedback_id = execute_write(
            "INSERT INTO feedback (user_id, feedback_type, message, page_url, screenshot_data) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING feedback_id",
            (user_id, feedback_type, message, page_url, screenshot_data),
            return_id=True,
        )
    else:
        row = query_one("SELECT COALESCE(MAX(feedback_id), 0) + 1 FROM feedback")
        feedback_id = row[0]
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO feedback (feedback_id, user_id, feedback_type, message, page_url, screenshot_data) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (feedback_id, user_id, feedback_type, message, page_url, screenshot_data),
            )
        finally:
            conn.close()

    return {
        "feedback_id": feedback_id,
        "feedback_type": feedback_type,
        "message": message,
        "page_url": page_url,
        "has_screenshot": screenshot_data is not None,
        "status": "new",
    }


def get_feedback_queue(status: str | None = None, limit: int = 50) -> list[dict]:
    """Get feedback items (admin view). Optionally filter by status."""
    _ensure_schema()
    conditions = []
    params: list = []

    if status:
        conditions.append("f.status = %s")
        params.append(status)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = query(
        f"SELECT f.feedback_id, f.user_id, f.feedback_type, f.message, "
        f"f.page_url, f.status, f.admin_note, f.created_at, f.resolved_at, "
        f"u.email, "
        f"CASE WHEN f.screenshot_data IS NOT NULL THEN 1 ELSE 0 END "
        f"FROM feedback f "
        f"LEFT JOIN users u ON f.user_id = u.user_id "
        f"{where} "
        f"ORDER BY f.created_at DESC "
        f"LIMIT %s",
        params + [limit],
    )
    return [
        {
            "feedback_id": r[0],
            "user_id": r[1],
            "feedback_type": r[2],
            "message": r[3],
            "page_url": r[4],
            "status": r[5],
            "admin_note": r[6],
            "created_at": r[7],
            "resolved_at": r[8],
            "email": r[9],
            "has_screenshot": bool(r[10]),
        }
        for r in rows
    ]


def update_feedback_status(
    feedback_id: int,
    status: str,
    admin_note: str | None = None,
) -> bool:
    """Update feedback status (admin action)."""
    _ensure_schema()
    if status not in ("new", "reviewed", "resolved", "wontfix"):
        return False

    resolved_clause = ""
    if status in ("resolved", "wontfix"):
        if BACKEND == "postgres":
            resolved_clause = ", resolved_at = NOW()"
        else:
            resolved_clause = ", resolved_at = CURRENT_TIMESTAMP"

    if BACKEND == "postgres":
        execute_write(
            f"UPDATE feedback SET status = %s, admin_note = %s{resolved_clause} "
            f"WHERE feedback_id = %s",
            (status, admin_note, feedback_id),
        )
    else:
        conn = get_connection()
        try:
            conn.execute(
                f"UPDATE feedback SET status = ?, admin_note = ?{resolved_clause} "
                f"WHERE feedback_id = ?",
                (status, admin_note, feedback_id),
            )
        finally:
            conn.close()
    return True


def get_feedback_counts() -> dict:
    """Get counts by status for the admin badge."""
    _ensure_schema()
    rows = query(
        "SELECT status, COUNT(*) FROM feedback GROUP BY status"
    )
    counts = {r[0]: r[1] for r in rows}
    counts["total"] = sum(counts.values())
    return counts


def get_feedback_items_json(
    statuses: list[str] | None = None, limit: int = 100
) -> dict:
    """Get feedback items as JSON-serializable dicts for the API.

    Args:
        statuses: List of status values to include (e.g. ['new', 'reviewed']).
                  If None, returns all statuses.
        limit: Maximum number of items.

    Returns:
        Dict with 'items' list and 'counts' summary.
    """
    _ensure_schema()
    conditions = []
    params: list = []

    if statuses:
        placeholders = ", ".join(["%s"] * len(statuses))
        conditions.append(f"f.status IN ({placeholders})")
        params.extend(statuses)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = query(
        f"SELECT f.feedback_id, f.user_id, f.feedback_type, f.message, "
        f"f.page_url, f.status, f.admin_note, f.created_at, f.resolved_at, "
        f"u.email, "
        f"CASE WHEN f.screenshot_data IS NOT NULL THEN 1 ELSE 0 END "
        f"FROM feedback f "
        f"LEFT JOIN users u ON f.user_id = u.user_id "
        f"{where} "
        f"ORDER BY f.created_at DESC "
        f"LIMIT %s",
        params + [limit],
    )
    items = []
    for r in rows:
        created = r[7]
        resolved = r[8]
        items.append({
            "feedback_id": r[0],
            "feedback_type": r[2],
            "message": r[3],
            "page_url": r[4],
            "status": r[5],
            "admin_note": r[6],
            "created_at": created.isoformat() if created else None,
            "resolved_at": resolved.isoformat() if resolved else None,
            "email": r[9],
            "has_screenshot": bool(r[10]),
        })

    counts = get_feedback_counts()
    return {"items": items, "counts": counts}


def get_feedback_screenshot(feedback_id: int) -> str | None:
    """Get screenshot data URL for a specific feedback item."""
    _ensure_schema()
    row = query_one(
        "SELECT screenshot_data FROM feedback WHERE feedback_id = %s",
        (feedback_id,),
    )
    return row[0] if row else None


# ── Points / bounty system ────────────────────────────────────────

def get_feedback_item(feedback_id: int) -> dict | None:
    """Get a single feedback item by ID (for points calculation)."""
    _ensure_schema()
    ph = "%s" if BACKEND == "postgres" else "?"
    row = query_one(
        f"SELECT f.feedback_id, f.user_id, f.feedback_type, f.message, "
        f"f.page_url, f.status, f.admin_note, f.created_at, f.resolved_at, "
        f"CASE WHEN f.screenshot_data IS NOT NULL THEN 1 ELSE 0 END "
        f"FROM feedback f WHERE f.feedback_id = {ph}",
        (feedback_id,),
    )
    if not row:
        return None
    return {
        "feedback_id": row[0],
        "user_id": row[1],
        "feedback_type": row[2],
        "message": row[3],
        "page_url": row[4],
        "status": row[5],
        "admin_note": row[6],
        "created_at": row[7],
        "resolved_at": row[8],
        "has_screenshot": bool(row[9]),
    }


def award_points(
    feedback_id: int,
    first_reporter: bool = False,
    admin_bonus: int = 0,
) -> list[dict]:
    """Award points for a resolved feedback item. Idempotent.

    Returns list of ledger entries created (empty if already awarded or anonymous).
    """
    _ensure_schema()
    ph = "%s" if BACKEND == "postgres" else "?"

    # Idempotency: skip if already awarded for this feedback_id
    existing = query_one(
        f"SELECT COUNT(*) FROM points_ledger WHERE feedback_id = {ph}",
        (feedback_id,),
    )
    if existing and existing[0] > 0:
        logger.debug("Points already awarded for feedback_id=%s", feedback_id)
        return []

    item = get_feedback_item(feedback_id)
    if not item or not item["user_id"]:
        return []  # Anonymous feedback gets no points

    user_id = item["user_id"]
    entries = []

    # Base points by type
    if item["feedback_type"] == "bug":
        entries.append({"points": 10, "reason": "bug_report"})
    elif item["feedback_type"] in ("suggestion", "question"):
        entries.append({"points": 5, "reason": "suggestion"})

    # Screenshot bonus
    if item["has_screenshot"]:
        entries.append({"points": 2, "reason": "screenshot"})

    # First reporter bonus (admin-determined)
    if first_reporter:
        entries.append({"points": 5, "reason": "first_reporter"})

    # High severity bonus
    try:
        from scripts.feedback_triage import classify_severity
        severity = classify_severity({
            "feedback_type": item["feedback_type"],
            "message": item["message"],
        })
        if severity == "HIGH":
            entries.append({"points": 3, "reason": "high_severity"})
    except Exception:
        pass  # Non-fatal: triage module may not be importable in all contexts

    # Admin bonus
    if admin_bonus and admin_bonus > 0:
        entries.append({"points": admin_bonus, "reason": "admin_bonus"})

    # Insert all entries
    for entry in entries:
        if BACKEND == "postgres":
            execute_write(
                "INSERT INTO points_ledger (user_id, points, reason, feedback_id) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, entry["points"], entry["reason"], feedback_id),
            )
        else:
            row = query_one("SELECT COALESCE(MAX(ledger_id), 0) + 1 FROM points_ledger")
            ledger_id = row[0]
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO points_ledger (ledger_id, user_id, points, reason, feedback_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (ledger_id, user_id, entry["points"], entry["reason"], feedback_id),
                )
            finally:
                conn.close()

    return entries


def get_user_points(user_id: int) -> int:
    """Get total points for a user."""
    _ensure_schema()
    ph = "%s" if BACKEND == "postgres" else "?"
    row = query_one(
        f"SELECT COALESCE(SUM(points), 0) FROM points_ledger WHERE user_id = {ph}",
        (user_id,),
    )
    return row[0] if row else 0


def get_points_history(user_id: int, limit: int = 20) -> list[dict]:
    """Get recent points history for a user."""
    _ensure_schema()
    ph = "%s" if BACKEND == "postgres" else "?"
    rows = query(
        f"SELECT p.ledger_id, p.points, p.reason, p.feedback_id, p.created_at "
        f"FROM points_ledger p "
        f"WHERE p.user_id = {ph} "
        f"ORDER BY p.created_at DESC "
        f"LIMIT {ph}",
        (user_id, limit),
    )
    reason_labels = {
        "bug_report": "Bug report",
        "suggestion": "Suggestion",
        "first_reporter": "First reporter bonus",
        "screenshot": "Screenshot attached",
        "high_severity": "High severity bonus",
        "admin_bonus": "Admin bonus",
    }
    return [
        {
            "ledger_id": r[0],
            "points": r[1],
            "reason": r[2],
            "reason_label": reason_labels.get(r[2], r[2]),
            "feedback_id": r[3],
            "created_at": r[4],
        }
        for r in rows
    ]


# ── Admin helpers ─────────────────────────────────────────────────

def get_admin_users() -> list[dict]:
    """Get all active admin users with their email addresses."""
    _ensure_schema()
    rows = query(
        "SELECT user_id, email, display_name "
        "FROM users "
        "WHERE is_admin = TRUE AND is_active = TRUE "
        "ORDER BY user_id"
    )
    return [
        {"user_id": r[0], "email": r[1], "display_name": r[2]}
        for r in rows
    ]
