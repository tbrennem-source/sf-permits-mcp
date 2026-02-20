"""Phase F2: Project Notes — free-text notes per version group.

Notes are keyed by (user_id, version_group) — one note blob per project per user.
Stored in the `project_notes` table created in Phase F migrations.
"""

import logging
from datetime import datetime, timezone

from src.db import BACKEND, execute_write, query_one

logger = logging.getLogger(__name__)

_MAX_NOTES_LEN = 4000  # characters


def get_project_notes(user_id: int, version_group: str) -> str:
    """Return the notes text for a version group, or '' if none."""
    try:
        row = query_one(
            "SELECT notes_text FROM project_notes "
            "WHERE user_id = %s AND version_group = %s",
            (user_id, version_group),
        )
        return (row[0] or "") if row else ""
    except Exception:
        logger.debug(
            "get_project_notes failed for user %d group %s", user_id, version_group,
            exc_info=True,
        )
        return ""


def save_project_notes(user_id: int, version_group: str, notes_text: str) -> bool:
    """Upsert project notes for a version group.

    Args:
        user_id: Owner of the notes
        version_group: The version_group identifier
        notes_text: Free-text note content (truncated to _MAX_NOTES_LEN)

    Returns:
        True on success, False on error.
    """
    text = (notes_text or "").strip()[:_MAX_NOTES_LEN]
    try:
        if BACKEND == "postgres":
            execute_write(
                """
                INSERT INTO project_notes (user_id, version_group, notes_text, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id, version_group)
                DO UPDATE SET notes_text = EXCLUDED.notes_text, updated_at = NOW()
                """,
                (user_id, version_group, text),
            )
        else:
            # DuckDB: check existence then insert or update.
            # DuckDB INTEGER PRIMARY KEY has no SERIAL/auto-increment, so we
            # generate a stable note_id from the (user_id, version_group) pair.
            existing = query_one(
                "SELECT note_id FROM project_notes "
                "WHERE user_id = %s AND version_group = %s",
                (user_id, version_group),
            )
            if existing:
                execute_write(
                    "UPDATE project_notes SET notes_text = %s, updated_at = CURRENT_TIMESTAMP "
                    "WHERE user_id = %s AND version_group = %s",
                    (text, user_id, version_group),
                )
            else:
                note_id = abs(hash((user_id, version_group))) % (2 ** 30)
                execute_write(
                    "INSERT INTO project_notes "
                    "(note_id, user_id, version_group, notes_text, updated_at) "
                    "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                    (note_id, user_id, version_group, text),
                )
        return True
    except Exception:
        logger.warning(
            "save_project_notes failed for user %d group %s", user_id, version_group,
            exc_info=True,
        )
        return False
