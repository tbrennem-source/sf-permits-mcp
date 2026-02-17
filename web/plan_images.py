"""Plan analysis image storage and retrieval.

Stores rendered PDF page images in the database, keyed by session_id.
Images are base64-encoded PNGs at max 1568px resolution.
Sessions expire after 24 hours (cleaned by nightly cron).
"""

import json
import logging
import secrets
from datetime import datetime

from src.db import BACKEND, execute_write, get_connection, query_one

logger = logging.getLogger(__name__)


def create_session(
    filename: str,
    page_count: int,
    page_extractions: list[dict],
    page_images: list[tuple[int, str]],  # (page_number, base64_png)
) -> str:
    """Create a plan analysis session with page images.

    Args:
        filename: Original PDF filename
        page_count: Total number of pages in PDF
        page_extractions: List of extracted metadata dicts from Vision analysis
        page_images: List of (page_number, base64_data) tuples

    Returns:
        session_id (str): Unique session identifier
    """
    session_id = secrets.token_urlsafe(16)
    extractions_json = json.dumps(page_extractions)

    # Insert session
    if BACKEND == "postgres":
        execute_write(
            "INSERT INTO plan_analysis_sessions "
            "(session_id, filename, page_count, page_extractions) "
            "VALUES (%s, %s, %s, %s)",
            (session_id, filename, page_count, extractions_json),
        )
    else:
        execute_write(
            "INSERT INTO plan_analysis_sessions "
            "(session_id, filename, page_count, page_extractions) "
            "VALUES (?, ?, ?, ?)",
            (session_id, filename, page_count, extractions_json),
        )

    # Insert images
    conn = get_connection()
    try:
        for page_num, b64_data in page_images:
            size_kb = len(b64_data) * 3 // 4 // 1024  # approximate decoded size
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO plan_analysis_images "
                        "(session_id, page_number, image_data, image_size_kb) "
                        "VALUES (%s, %s, %s, %s)",
                        (session_id, page_num, b64_data, size_kb),
                    )
                conn.commit()
            else:
                conn.execute(
                    "INSERT INTO plan_analysis_images "
                    "(session_id, page_number, image_data, image_size_kb) "
                    "VALUES (?, ?, ?, ?)",
                    (session_id, page_num, b64_data, size_kb),
                )
    finally:
        conn.close()

    logger.info(
        f"Created plan session {session_id}: {filename} ({page_count} pages, {len(page_images)} images)"
    )
    return session_id


def get_session(session_id: str) -> dict | None:
    """Get session metadata (without image data).

    Args:
        session_id: Session identifier

    Returns:
        dict with keys: session_id, filename, page_count, page_extractions, created_at
        None if session not found
    """
    row = query_one(
        "SELECT session_id, filename, page_count, page_extractions, created_at "
        "FROM plan_analysis_sessions WHERE session_id = %s"
        if BACKEND == "postgres"
        else "SELECT session_id, filename, page_count, page_extractions, created_at "
        "FROM plan_analysis_sessions WHERE session_id = ?",
        (session_id,),
    )
    if not row:
        return None

    return {
        "session_id": row[0],
        "filename": row[1],
        "page_count": row[2],
        "page_extractions": row[3] if isinstance(row[3], (list, dict)) else (json.loads(row[3]) if row[3] else []),
        "created_at": row[4],
    }


def get_page_image(session_id: str, page_number: int) -> str | None:
    """Get base64 image data for a specific page.

    Args:
        session_id: Session identifier
        page_number: Zero-indexed page number

    Returns:
        Base64-encoded PNG image data (without data: prefix)
        None if image not found
    """
    row = query_one(
        "SELECT image_data FROM plan_analysis_images "
        "WHERE session_id = %s AND page_number = %s"
        if BACKEND == "postgres"
        else "SELECT image_data FROM plan_analysis_images "
        "WHERE session_id = ? AND page_number = ?",
        (session_id, page_number),
    )
    return row[0] if row else None


def cleanup_expired(hours: int = 24) -> int:
    """Delete sessions older than N hours. Returns count deleted.

    Args:
        hours: Age threshold in hours (default 24)

    Returns:
        Number of sessions deleted
    """
    if BACKEND == "postgres":
        row = query_one(
            "SELECT COUNT(*) FROM plan_analysis_sessions "
            "WHERE created_at < NOW() - INTERVAL '%s hours'",
            (hours,),
        )
        count = row[0] if row else 0
        if count > 0:
            execute_write(
                "DELETE FROM plan_analysis_sessions "
                "WHERE created_at < NOW() - INTERVAL '%s hours'",
                (hours,),
            )
            logger.info(f"Cleaned up {count} expired plan sessions (>{hours}h old)")
        return count
    else:
        # DuckDB: manual timestamp comparison
        row = query_one(
            "SELECT COUNT(*) FROM plan_analysis_sessions "
            "WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '" + str(hours) + " hours'"
        )
        count = row[0] if row else 0
        if count > 0:
            execute_write(
                "DELETE FROM plan_analysis_sessions "
                "WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '" + str(hours) + " hours'"
            )
            logger.info(f"Cleaned up {count} expired plan sessions (>{hours}h old)")
        return count
