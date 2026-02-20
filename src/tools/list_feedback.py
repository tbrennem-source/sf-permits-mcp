"""Tool: list_feedback — Query user feedback submitted to SF Permits.

Enables reading the feedback queue during morning briefings and planning
sessions. Filters by status, type, date range, and more.
"""

import logging
from datetime import date, timedelta
from src.db import get_connection, BACKEND

logger = logging.getLogger(__name__)

_PH = "%s" if BACKEND == "postgres" else "?"


def _exec(conn, sql, params=None):
    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    else:
        return conn.execute(sql, params or []).fetchall()


async def list_feedback(
    status: str | None = None,
    feedback_type: str | None = None,
    days_back: int | None = None,
    limit: int = 50,
    include_resolved: bool = False,
) -> str:
    """Query user feedback submitted to sfpermits.ai.

    Returns feedback items from the queue, useful for:
    - Morning briefings: "What did users report this week?"
    - Planning sessions: "What bugs are open?"
    - Triage: "What suggestions have we gotten?"

    Args:
        status: Filter by status — 'new', 'reviewed', 'resolved', 'wontfix'.
                Omit to see all unresolved (new + reviewed) by default.
        feedback_type: Filter by type — 'bug', 'suggestion', 'question'.
        days_back: Only return items from the last N days (e.g. 7 for last week).
        limit: Max results to return (default 50, capped at 200).
        include_resolved: If True, include resolved/wontfix items (default False).

    Returns:
        Markdown-formatted feedback list with counts by status and type.
    """
    limit = min(max(1, limit), 200)

    conditions: list[str] = []
    params: list = []

    # Default: exclude resolved unless explicitly requested
    if status:
        conditions.append(f"f.status = {_PH}")
        params.append(status.strip().lower())
    elif not include_resolved:
        conditions.append(f"f.status IN ({_PH}, {_PH})")
        params.extend(["new", "reviewed"])

    if feedback_type:
        conditions.append(f"f.feedback_type = {_PH}")
        params.append(feedback_type.strip().lower())

    if days_back:
        if BACKEND == "postgres":
            conditions.append(f"f.created_at >= NOW() - INTERVAL '{days_back} days'")
        else:
            cutoff = (date.today() - timedelta(days=days_back)).isoformat()
            conditions.append(f"f.created_at >= {_PH}")
            params.append(cutoff)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Join to users for email — left join so anonymous feedback still shows
    user_col = (
        "u.email" if BACKEND == "postgres"
        else "COALESCE(u.email, 'anonymous')"
    )

    sql = f"""
        SELECT
            f.feedback_id,
            f.feedback_type,
            f.status,
            f.message,
            f.page_url,
            f.admin_note,
            f.created_at,
            {user_col} AS user_email,
            CASE WHEN f.screenshot_data IS NOT NULL THEN 'yes' ELSE 'no' END AS has_screenshot
        FROM feedback f
        LEFT JOIN users u ON f.user_id = u.user_id
        {where}
        ORDER BY f.created_at DESC
        LIMIT {_PH}
    """
    params.append(limit)

    # Counts query for summary
    count_sql = f"""
        SELECT f.status, f.feedback_type, COUNT(*) as cnt
        FROM feedback f
        {where.replace(f'LIMIT {_PH}', '')}
        GROUP BY f.status, f.feedback_type
        ORDER BY f.status, f.feedback_type
    """
    count_params = params[:-1]  # exclude the LIMIT param

    conn = get_connection()
    try:
        rows = _exec(conn, sql, params)
        count_rows = _exec(conn, count_sql, count_params)
    except Exception as e:
        logger.error("list_feedback query failed: %s", e)
        return f"Error querying feedback: {e}"
    finally:
        conn.close()

    # Build counts summary
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    total = 0
    for r in count_rows:
        s, t, cnt = r[0], r[1], r[2]
        status_counts[s] = status_counts.get(s, 0) + cnt
        type_counts[t] = type_counts.get(t, 0) + cnt
        total += cnt

    if not rows and total == 0:
        filter_desc = []
        if status:
            filter_desc.append(f"status={status}")
        if feedback_type:
            filter_desc.append(f"type={feedback_type}")
        if days_back:
            filter_desc.append(f"last {days_back} days")
        desc = ", ".join(filter_desc) if filter_desc else "all"
        return f"No feedback found ({desc}). The queue is empty."

    # Format header
    lines = ["## SF Permits Feedback Queue\n"]

    # Summary counts
    if status_counts:
        summary_parts = []
        for s in ["new", "reviewed", "resolved", "wontfix"]:
            if s in status_counts:
                summary_parts.append(f"**{status_counts[s]}** {s}")
        lines.append("**By status:** " + " · ".join(summary_parts))

    if type_counts:
        type_parts = []
        for t in ["bug", "suggestion", "question"]:
            if t in type_counts:
                emoji = {"bug": "🐛", "suggestion": "💡", "question": "❓"}.get(t, "")
                type_parts.append(f"{emoji} {type_counts[t]} {t}s")
        lines.append("**By type:** " + " · ".join(type_parts))

    lines.append("")

    if not rows:
        lines.append("*(No items match your filter — counts above reflect broader query)*")
        return "\n".join(lines)

    # Table
    lines.append("| ID | Type | Status | Message | Page | Screenshot | Submitted |")
    lines.append("|---|---|---|---|---|---|---|")

    type_emoji = {"bug": "🐛", "suggestion": "💡", "question": "❓"}

    for row in rows:
        fid, ftype, fstatus, message, page_url, admin_note, created_at, email, has_ss = row

        # Truncate message
        msg = (message or "").strip().replace("|", "—").replace("\n", " ")
        if len(msg) > 90:
            msg = msg[:87] + "..."

        # Page URL — show just the path
        page = ""
        if page_url:
            try:
                from urllib.parse import urlparse
                page = urlparse(page_url).path or page_url
            except Exception:
                page = page_url[:40]

        emoji = type_emoji.get(ftype, "")

        # Date format
        created = ""
        if created_at:
            try:
                if hasattr(created_at, "strftime"):
                    created = created_at.strftime("%b %d")
                else:
                    created = str(created_at)[:10]
            except Exception:
                created = str(created_at)[:10]

        ss_indicator = "📷" if has_ss == "yes" else ""
        lines.append(
            f"| #{fid} | {emoji}{ftype} | {fstatus} | {msg} | {page} | {ss_indicator} | {created} |"
        )

        # Show admin note inline if present
        if admin_note:
            note = admin_note.strip()[:120]
            lines.append(f"| | | | *Admin: {note}* | | | |")

    lines.append("")
    lines.append(f"*Showing {len(rows)} of {total} items · "
                 f"Full queue: /admin/feedback*")

    return "\n".join(lines)
