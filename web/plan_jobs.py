"""Plan analysis job tracking for async processing.

Tracks every plan analysis request (sync and async) with status,
metadata, and results. Large PDFs are processed asynchronously
via background threads; this module handles the CRUD operations
for the job queue.

Job lifecycle:
  pending → processing → completed | failed | stale
"""

import json
import logging
import secrets
from datetime import datetime

from src.db import BACKEND, execute_write, get_connection, query, query_one

logger = logging.getLogger(__name__)


def create_job(
    *,
    user_id: int | None = None,
    filename: str,
    file_size_mb: float,
    pdf_data: bytes | None = None,
    property_address: str | None = None,
    permit_number: str | None = None,
    project_description: str | None = None,
    permit_type: str | None = None,
    is_addendum: bool = False,
    quick_check: bool = False,
    is_async: bool = False,
    analysis_mode: str = "sample",
    submission_stage: str | None = None,
) -> str:
    """Create a new plan analysis job.

    Args:
        user_id: Logged-in user (None for anonymous)
        filename: Original PDF filename
        file_size_mb: File size in MB
        pdf_data: Raw PDF bytes (stored for async processing, cleared after)
        property_address: Manual property address from user
        permit_number: Manual permit number from user
        project_description: User-provided project description
        permit_type: User-selected permit type
        is_addendum: Whether this is a site permit addendum
        quick_check: Whether this is metadata-only (no vision)
        is_async: Whether this job runs in background
        analysis_mode: 'sample' (free tier) or 'full' (pro tier, all pages)

    Returns:
        job_id (str): Unique job identifier
    """
    job_id = secrets.token_urlsafe(16)

    # Phase D2 — compute SHA-256 hash of PDF bytes at upload time (Layer 1)
    pdf_hash: str | None = None
    pdf_hash_failed: bool = False
    if pdf_data:
        from web.plan_fingerprint import compute_pdf_hash
        pdf_hash = compute_pdf_hash(pdf_data)
        if pdf_hash is None:
            pdf_hash_failed = True

    if BACKEND == "postgres":
        import psycopg2

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO plan_analysis_jobs "
                    "(job_id, user_id, filename, file_size_mb, pdf_data, "
                    "property_address, permit_number, address_source, permit_source, "
                    "project_description, permit_type, is_addendum, quick_check, is_async, "
                    "analysis_mode, submission_stage, pdf_hash, pdf_hash_failed) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        job_id,
                        user_id,
                        filename,
                        file_size_mb,
                        psycopg2.Binary(pdf_data) if pdf_data else None,
                        property_address,
                        permit_number,
                        "manual" if property_address else None,
                        "manual" if permit_number else None,
                        project_description,
                        permit_type,
                        is_addendum,
                        quick_check,
                        is_async,
                        analysis_mode,
                        submission_stage,
                        pdf_hash,
                        pdf_hash_failed,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    else:
        execute_write(
            "INSERT INTO plan_analysis_jobs "
            "(job_id, user_id, filename, file_size_mb, pdf_data, "
            "property_address, permit_number, address_source, permit_source, "
            "project_description, permit_type, is_addendum, quick_check, is_async, "
            "analysis_mode, submission_stage, pdf_hash, pdf_hash_failed) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job_id,
                user_id,
                filename,
                file_size_mb,
                pdf_data,
                property_address,
                permit_number,
                "manual" if property_address else None,
                "manual" if permit_number else None,
                project_description,
                permit_type,
                is_addendum,
                quick_check,
                is_async,
                analysis_mode,
                submission_stage,
                pdf_hash,
                pdf_hash_failed,
            ),
        )

    logger.info(
        f"Created plan job {job_id}: {filename} ({file_size_mb:.1f} MB, "
        f"async={is_async}, user={user_id}, pdf_hash={'ok' if pdf_hash else ('failed' if pdf_hash_failed else 'none')})"
    )
    return job_id


def get_job(job_id: str) -> dict | None:
    """Get job metadata (without pdf_data to avoid loading large blobs).

    Returns:
        dict with job fields, or None if not found
    """
    row = query_one(
        "SELECT job_id, user_id, session_id, filename, file_size_mb, "
        "status, is_async, project_description, permit_type, "
        "is_addendum, quick_check, report_md, error_message, "
        "property_address, permit_number, address_source, permit_source, "
        "created_at, started_at, completed_at, email_sent, "
        "progress_stage, progress_detail, "
        "vision_usage_json, gallery_duration_ms, "
        "analysis_mode, pages_analyzed, "
        "submission_stage, "
        "structural_fingerprint, version_group, version_number, parent_job_id "
        "FROM plan_analysis_jobs WHERE job_id = %s",
        (job_id,),
    )
    if not row:
        return None

    return {
        "job_id": row[0],
        "user_id": row[1],
        "session_id": row[2],
        "filename": row[3],
        "file_size_mb": row[4],
        "status": row[5],
        "is_async": row[6],
        "project_description": row[7],
        "permit_type": row[8],
        "is_addendum": row[9],
        "quick_check": row[10],
        "report_md": row[11],
        "error_message": row[12],
        "property_address": row[13],
        "permit_number": row[14],
        "address_source": row[15],
        "permit_source": row[16],
        "created_at": row[17],
        "started_at": row[18],
        "completed_at": row[19],
        "email_sent": row[20],
        "progress_stage": row[21],
        "progress_detail": row[22],
        "vision_usage_json": row[23],
        "gallery_duration_ms": row[24],
        "analysis_mode": row[25],
        "pages_analyzed": row[26],
        "submission_stage": row[27] if len(row) > 27 else None,
        "structural_fingerprint": row[28] if len(row) > 28 else None,
        "version_group": row[29] if len(row) > 29 else None,
        "version_number": row[30] if len(row) > 30 else None,
        "parent_job_id": row[31] if len(row) > 31 else None,
    }


def get_job_pdf(job_id: str) -> bytes | None:
    """Get the stored PDF bytes for a job (used by background worker).

    Returns:
        Raw PDF bytes, or None if not found or already cleared
    """
    row = query_one(
        "SELECT pdf_data FROM plan_analysis_jobs WHERE job_id = %s",
        (job_id,),
    )
    if not row or not row[0]:
        return None
    # PostgreSQL returns memoryview for BYTEA; convert to bytes
    data = row[0]
    return bytes(data) if isinstance(data, memoryview) else data


def update_job_status(job_id: str, status: str, **fields) -> None:
    """Update job status and optional additional fields.

    Args:
        job_id: Job identifier
        status: New status (pending, processing, completed, failed, stale)
        **fields: Additional columns to update (e.g., session_id, report_md,
                  error_message, started_at, completed_at, email_sent,
                  property_address, permit_number, address_source, permit_source)
    """
    set_parts = ["status = %s"]
    params = [status]

    for col, val in fields.items():
        set_parts.append(f"{col} = %s")
        params.append(val)

    params.append(job_id)

    sql = f"UPDATE plan_analysis_jobs SET {', '.join(set_parts)} WHERE job_id = %s"
    execute_write(sql, tuple(params))


def get_user_jobs(
    user_id: int,
    limit: int = 20,
    order_by: str = "newest",
    include_archived: bool = False,
) -> list[dict]:
    """Get recent jobs for a user with configurable sort order.

    Args:
        user_id: User identifier
        limit: Max results
        order_by: Sort order — one of 'newest', 'oldest', 'address',
                  'filename', 'status'. Defaults to 'newest'.
        include_archived: If True, include archived/closed jobs. Default False.

    Returns:
        List of job dicts (without pdf_data or report_md for efficiency)
    """
    # Validate order_by against allowed values to prevent SQL injection
    ORDER_CLAUSES = {
        "newest": "ORDER BY created_at DESC",
        "oldest": "ORDER BY created_at ASC",
        "address": "ORDER BY property_address ASC NULLS LAST, created_at DESC",
        "filename": "ORDER BY filename ASC, created_at DESC",
        "status": (
            "ORDER BY CASE WHEN status='failed' THEN 0 "
            "WHEN status='stale' THEN 1 "
            "WHEN status='processing' THEN 2 "
            "WHEN status='pending' THEN 3 "
            "WHEN status='completed' THEN 4 "
            "ELSE 5 END, created_at DESC"
        ),
    }
    order_clause = ORDER_CLAUSES.get(order_by, ORDER_CLAUSES["newest"])

    archive_filter = "" if include_archived else "AND is_archived = FALSE "

    try:
        rows = query(
            "SELECT job_id, session_id, filename, file_size_mb, status, "
            "is_async, quick_check, property_address, permit_number, "
            "created_at, completed_at, error_message, "
            "analysis_mode, pages_analyzed, started_at, is_archived, "
            "parent_job_id, version_group "
            "FROM plan_analysis_jobs "
            f"WHERE user_id = %s {archive_filter}"
            f"{order_clause} "
            "LIMIT %s",
            (user_id, limit),
        )
    except Exception:
        # is_archived column not yet migrated — fall back to pre-D1 query
        logger.warning("is_archived column missing — falling back to unfiltered query")
        rows_raw = query(
            "SELECT job_id, session_id, filename, file_size_mb, status, "
            "is_async, quick_check, property_address, permit_number, "
            "created_at, completed_at, error_message, "
            "analysis_mode, pages_analyzed, started_at "
            "FROM plan_analysis_jobs "
            f"WHERE user_id = %s "
            f"{order_clause} "
            "LIMIT %s",
            (user_id, limit),
        )
        return [
            {
                "job_id": r[0],
                "session_id": r[1],
                "filename": r[2],
                "file_size_mb": r[3],
                "status": r[4],
                "is_async": r[5],
                "quick_check": r[6],
                "property_address": r[7],
                "permit_number": r[8],
                "created_at": r[9],
                "completed_at": r[10],
                "error_message": r[11],
                "analysis_mode": r[12],
                "pages_analyzed": r[13],
                "started_at": r[14],
                "is_archived": False,
                "parent_job_id": None,
            }
            for r in rows_raw
        ]

    return [
        {
            "job_id": r[0],
            "session_id": r[1],
            "filename": r[2],
            "file_size_mb": r[3],
            "status": r[4],
            "is_async": r[5],
            "quick_check": r[6],
            "property_address": r[7],
            "permit_number": r[8],
            "created_at": r[9],
            "completed_at": r[10],
            "error_message": r[11],
            "analysis_mode": r[12],
            "pages_analyzed": r[13],
            "started_at": r[14],
            "is_archived": r[15],
            "parent_job_id": r[16] if len(r) > 16 else None,
        }
        for r in rows
    ]


def search_jobs(user_id: int, query_text: str, limit: int = 20) -> list[dict]:
    """Search user's jobs by address, permit number, or filename.

    Args:
        user_id: User identifier
        query_text: Search text (matched against address, permit, filename)
        limit: Max results

    Returns:
        List of matching job dicts
    """
    pattern = f"%{query_text}%"
    rows = query(
        "SELECT job_id, session_id, filename, file_size_mb, status, "
        "is_async, quick_check, property_address, permit_number, "
        "created_at, completed_at, error_message, "
        "analysis_mode, pages_analyzed, started_at, "
        "is_archived, parent_job_id "
        "FROM plan_analysis_jobs "
        "WHERE user_id = %s AND is_archived = FALSE "
        "AND (property_address ILIKE %s OR permit_number ILIKE %s OR filename ILIKE %s) "
        "ORDER BY created_at DESC "
        "LIMIT %s",
        (user_id, pattern, pattern, pattern, limit),
    )
    return [
        {
            "job_id": r[0],
            "session_id": r[1],
            "filename": r[2],
            "file_size_mb": r[3],
            "status": r[4],
            "is_async": r[5],
            "quick_check": r[6],
            "property_address": r[7],
            "permit_number": r[8],
            "created_at": r[9],
            "completed_at": r[10],
            "error_message": r[11],
            "analysis_mode": r[12],
            "pages_analyzed": r[13],
            "started_at": r[14],
            "is_archived": r[15] if len(r) > 15 else False,
            "parent_job_id": r[16] if len(r) > 16 else None,
        }
        for r in rows
    ]


def find_previous_analyses(
    *,
    job_id: str | None = None,
    property_address: str | None = None,
    permit_number: str | None = None,
    user_id: int | None = None,
    limit: int = 5,
) -> list[dict]:
    """Find previous completed analyses for the same address or permit.

    Used for revision tracking — when a user re-uploads plans for the same
    property, show links to their prior analyses.

    Matches on:
    1. Same permit_number (strongest match)
    2. Same property_address (weaker match, addresses may vary in format)

    Excludes the current job_id if provided.

    Returns list of job dicts ordered by completed_at DESC.
    """
    if not property_address and not permit_number:
        return []

    conditions = []
    params: list = []

    if permit_number:
        conditions.append("permit_number = %s")
        params.append(permit_number)
    elif property_address:
        conditions.append("UPPER(property_address) = UPPER(%s)")
        params.append(property_address)

    # Only completed analyses with results
    conditions.append("status = 'completed'")
    conditions.append("session_id IS NOT NULL")

    # Exclude current job
    if job_id:
        conditions.append("job_id != %s")
        params.append(job_id)

    # Optionally scope to same user
    if user_id:
        conditions.append("user_id = %s")
        params.append(user_id)

    where = " AND ".join(conditions)
    params.append(limit)

    try:
        rows = query(
            f"SELECT job_id, session_id, filename, file_size_mb, "
            f"property_address, permit_number, analysis_mode, pages_analyzed, "
            f"created_at, completed_at "
            f"FROM plan_analysis_jobs "
            f"WHERE {where} "
            f"ORDER BY completed_at DESC "
            f"LIMIT %s",
            tuple(params),
        )
    except Exception:
        logger.debug("find_previous_analyses failed", exc_info=True)
        return []

    return [
        {
            "job_id": r[0],
            "session_id": r[1],
            "filename": r[2],
            "file_size_mb": r[3],
            "property_address": r[4],
            "permit_number": r[5],
            "analysis_mode": r[6],
            "pages_analyzed": r[7],
            "created_at": r[8],
            "completed_at": r[9],
        }
        for r in rows
    ]


def mark_stale_jobs(max_age_minutes: int = 15) -> int:
    """Mark jobs stuck in 'processing' as 'stale'.

    Called on startup to handle jobs interrupted by worker restart.

    Args:
        max_age_minutes: How long a job can be in 'processing' before marked stale

    Returns:
        Number of jobs marked stale
    """
    if BACKEND == "postgres":
        row = query_one(
            "SELECT COUNT(*) FROM plan_analysis_jobs "
            "WHERE status = 'processing' "
            "AND started_at < NOW() - INTERVAL '%s minutes'",
            (max_age_minutes,),
        )
    else:
        row = query_one(
            "SELECT COUNT(*) FROM plan_analysis_jobs "
            "WHERE status = 'processing' "
            "AND started_at < CURRENT_TIMESTAMP - INTERVAL '"
            + str(max_age_minutes)
            + " minutes'"
        )

    count = row[0] if row else 0
    if count > 0:
        if BACKEND == "postgres":
            execute_write(
                "UPDATE plan_analysis_jobs SET status = 'stale' "
                "WHERE status = 'processing' "
                "AND started_at < NOW() - INTERVAL '%s minutes'",
                (max_age_minutes,),
            )
        else:
            execute_write(
                "UPDATE plan_analysis_jobs SET status = 'stale' "
                "WHERE status = 'processing' "
                "AND started_at < CURRENT_TIMESTAMP - INTERVAL '"
                + str(max_age_minutes)
                + " minutes'"
            )
        logger.info(f"Marked {count} stale plan analysis jobs (>{max_age_minutes}m old)")
    return count


def close_project(job_ids: list[str], user_id: int) -> int:
    """Archive (close) one or more jobs belonging to a user.

    Sets is_archived=TRUE.  Idempotent — already-closed jobs are a no-op.

    Args:
        job_ids: List of job IDs to close
        user_id: Owner user ID (ensures users can only close their own jobs)

    Returns:
        Number of rows updated
    """
    if not job_ids:
        return 0
    placeholders = ", ".join(["%s"] * len(job_ids))
    execute_write(
        f"UPDATE plan_analysis_jobs SET is_archived = TRUE "
        f"WHERE user_id = %s AND job_id IN ({placeholders})",
        (user_id, *job_ids),
    )
    logger.info("Closed %d plan job(s) for user %d", len(job_ids), user_id)
    return len(job_ids)


def reopen_project(job_ids: list[str], user_id: int) -> int:
    """Re-open (unarchive) one or more jobs belonging to a user.

    Sets is_archived=FALSE.  Idempotent — already-open jobs are a no-op.

    Args:
        job_ids: List of job IDs to reopen
        user_id: Owner user ID (ensures users can only reopen their own jobs)

    Returns:
        Number of rows updated
    """
    if not job_ids:
        return 0
    placeholders = ", ".join(["%s"] * len(job_ids))
    execute_write(
        f"UPDATE plan_analysis_jobs SET is_archived = FALSE "
        f"WHERE user_id = %s AND job_id IN ({placeholders})",
        (user_id, *job_ids),
    )
    logger.info("Reopened %d plan job(s) for user %d", len(job_ids), user_id)
    return len(job_ids)


def _get_protected_version_groups(days: int) -> set[str]:
    """Return version_group values that contain any job created within `days` days.

    These groups must not be cleaned up even if some members are older than the
    threshold.  Returns an empty set if the version_group column does not yet
    exist (pre-D2 databases).
    """
    try:
        if BACKEND == "postgres":
            rows = query(
                "SELECT DISTINCT version_group FROM plan_analysis_jobs "
                "WHERE version_group IS NOT NULL "
                "AND created_at >= NOW() - INTERVAL '%s days'",
                (days,),
            )
        else:
            rows = query(
                "SELECT DISTINCT version_group FROM plan_analysis_jobs "
                "WHERE version_group IS NOT NULL "
                "AND created_at >= CURRENT_TIMESTAMP - INTERVAL '"
                + str(days)
                + " days'"
            )
        return {r[0] for r in rows if r[0]}
    except Exception:
        # Column doesn't exist yet — safe to skip the guard
        return set()


def cleanup_old_jobs(days: int = 30) -> int:
    """Delete jobs older than N days. Returns count deleted.

    Jobs that belong to a version_group where any member was created within
    `days` days are skipped entirely — closing a project shouldn't prematurely
    delete shared-group history.

    Args:
        days: Age threshold in days (default 30)

    Returns:
        Number of jobs deleted
    """
    protected_groups = _get_protected_version_groups(days)

    if BACKEND == "postgres":
        if protected_groups:
            placeholders = ", ".join(["%s"] * len(protected_groups))
            row = query_one(
                "SELECT COUNT(*) FROM plan_analysis_jobs "
                f"WHERE created_at < NOW() - INTERVAL '%s days' "
                f"AND (version_group IS NULL OR version_group NOT IN ({placeholders}))",
                (days, *protected_groups),
            )
            count = row[0] if row else 0
            if count > 0:
                execute_write(
                    "DELETE FROM plan_analysis_jobs "
                    f"WHERE created_at < NOW() - INTERVAL '%s days' "
                    f"AND (version_group IS NULL OR version_group NOT IN ({placeholders}))",
                    (days, *protected_groups),
                )
        else:
            row = query_one(
                "SELECT COUNT(*) FROM plan_analysis_jobs "
                "WHERE created_at < NOW() - INTERVAL '%s days'",
                (days,),
            )
            count = row[0] if row else 0
            if count > 0:
                execute_write(
                    "DELETE FROM plan_analysis_jobs "
                    "WHERE created_at < NOW() - INTERVAL '%s days'",
                    (days,),
                )
    else:
        age_expr = f"CURRENT_TIMESTAMP - INTERVAL '{days} days'"
        if protected_groups:
            placeholders = ", ".join(["%s" for _ in protected_groups])
            row = query_one(
                f"SELECT COUNT(*) FROM plan_analysis_jobs "
                f"WHERE created_at < {age_expr} "
                f"AND (version_group IS NULL OR version_group NOT IN ({placeholders}))",
                tuple(protected_groups),
            )
            count = row[0] if row else 0
            if count > 0:
                execute_write(
                    f"DELETE FROM plan_analysis_jobs "
                    f"WHERE created_at < {age_expr} "
                    f"AND (version_group IS NULL OR version_group NOT IN ({placeholders}))",
                    tuple(protected_groups),
                )
        else:
            row = query_one(
                "SELECT COUNT(*) FROM plan_analysis_jobs "
                f"WHERE created_at < {age_expr}"
            )
            count = row[0] if row else 0
            if count > 0:
                execute_write(
                    "DELETE FROM plan_analysis_jobs "
                    f"WHERE created_at < {age_expr}"
                )

    if count > 0:
        logger.info(f"Cleaned up {count} old plan analysis jobs (>{days}d old)")
    return count


def delete_job(job_id: str, user_id: int) -> bool:
    """Soft-delete a job belonging to a specific user (sets is_archived=TRUE).

    The job can be restored within 30 seconds via restore_job().
    Permanently deleted later by cleanup_old_jobs().

    Args:
        job_id: Job identifier
        user_id: Owner user ID (ensures users can only delete their own jobs)

    Returns:
        True if a row was archived, False otherwise
    """
    # Check ownership first
    row = query_one(
        "SELECT user_id FROM plan_analysis_jobs WHERE job_id = %s",
        (job_id,),
    )
    if not row or row[0] != user_id:
        return False

    execute_write(
        "UPDATE plan_analysis_jobs SET is_archived = TRUE WHERE job_id = %s AND user_id = %s",
        (job_id, user_id),
    )
    logger.info(f"Soft-deleted (archived) plan job {job_id} for user {user_id}")
    return True


def restore_job(job_id: str, user_id: int) -> bool:
    """Restore a soft-deleted job (undo within grace period).

    Args:
        job_id: Job identifier
        user_id: Owner user ID

    Returns:
        True if restored, False otherwise
    """
    row = query_one(
        "SELECT user_id, is_archived FROM plan_analysis_jobs WHERE job_id = %s",
        (job_id,),
    )
    if not row or row[0] != user_id:
        return False

    execute_write(
        "UPDATE plan_analysis_jobs SET is_archived = FALSE WHERE job_id = %s AND user_id = %s",
        (job_id, user_id),
    )
    logger.info(f"Restored plan job {job_id} for user {user_id}")
    return True


def bulk_delete_jobs(job_ids: list[str], user_id: int) -> int:
    """Soft-delete multiple jobs owned by user. Returns count archived."""
    if not job_ids:
        return 0
    # Build parameterized IN clause
    placeholders = ", ".join(["%s"] * len(job_ids))
    execute_write(
        f"UPDATE plan_analysis_jobs SET is_archived = TRUE WHERE user_id = %s AND job_id IN ({placeholders})",
        (user_id, *job_ids),
    )
    logger.info("Soft-deleted %d jobs for user %d: %s", len(job_ids), user_id, job_ids)
    return len(job_ids)


def cancel_job(job_id: str, user_id: int) -> bool:
    """Cancel a running job belonging to a specific user.

    Sets status to 'cancelled'. The background worker thread continues
    but results will be discarded (the status check in plan_job_status
    won't show completed results for cancelled jobs).

    Args:
        job_id: Job identifier
        user_id: Owner user ID (ensures users can only cancel their own jobs)

    Returns:
        True if the job was cancelled, False otherwise
    """
    row = query_one(
        "SELECT user_id, status FROM plan_analysis_jobs WHERE job_id = %s",
        (job_id,),
    )
    if not row:
        return False
    # Must be owned by user (or anonymous job with None user_id)
    if row[0] is not None and row[0] != user_id:
        return False
    # Only cancel jobs that are still active
    if row[1] not in ("pending", "processing"):
        return False

    execute_write(
        "UPDATE plan_analysis_jobs SET status = 'cancelled' WHERE job_id = %s",
        (job_id,),
    )
    logger.info(f"Cancelled plan job {job_id} for user {user_id}")
    return True


def assign_version_group(job_id: str, group_id: str) -> None:
    """Assign a job to a version group and set its version_number.

    The version_number is auto-incremented within the group: it equals
    1 + the current max version_number for existing group members.
    If the group has no existing members (this job is the first), version_number = 1.

    Also sets parent_job_id to the most recent prior version in the group
    (the job with the highest version_number before this assignment).

    Args:
        job_id: Job to assign
        group_id: Shared version group identifier (UUID or job_id of first member)
    """
    # Find the current max version number and the job_id with that version
    row = query_one(
        "SELECT MAX(version_number), MAX(job_id) "  # placeholder for parent lookup
        "FROM plan_analysis_jobs WHERE version_group = %s AND job_id != %s",
        (group_id, job_id),
    )
    # Get the actual parent — the job with the max version_number in this group
    parent_row = query_one(
        "SELECT job_id FROM plan_analysis_jobs "
        "WHERE version_group = %s AND job_id != %s "
        "ORDER BY version_number DESC NULLS LAST "
        "LIMIT 1",
        (group_id, job_id),
    )
    max_version = row[0] if (row and row[0] is not None) else 0
    next_version = int(max_version) + 1
    parent_job_id = parent_row[0] if parent_row else None

    execute_write(
        "UPDATE plan_analysis_jobs "
        "SET version_group = %s, version_number = %s, parent_job_id = %s "
        "WHERE job_id = %s",
        (group_id, next_version, parent_job_id, job_id),
    )
    logger.info(
        "Assigned job %s to version_group=%s as v%d (parent=%s)",
        job_id,
        group_id,
        next_version,
        parent_job_id,
    )


def get_version_chain(version_group: str) -> list[dict]:
    """Return all jobs in a version group ordered by version_number ascending.

    Args:
        version_group: Shared group identifier

    Returns:
        List of job dicts (job_id, version_number, parent_job_id, filename,
        status, created_at, completed_at, property_address, permit_number)
        ordered by version_number ASC.
    """
    try:
        rows = query(
            "SELECT job_id, version_number, parent_job_id, filename, status, "
            "created_at, completed_at, property_address, permit_number, "
            "analysis_mode, pages_analyzed "
            "FROM plan_analysis_jobs "
            "WHERE version_group = %s "
            "ORDER BY version_number ASC NULLS LAST",
            (version_group,),
        )
    except Exception:
        logger.debug("get_version_chain failed for group %s", version_group, exc_info=True)
        return []

    return [
        {
            "job_id": r[0],
            "version_number": r[1],
            "parent_job_id": r[2],
            "filename": r[3],
            "status": r[4],
            "created_at": r[5],
            "completed_at": r[6],
            "property_address": r[7],
            "permit_number": r[8],
            "analysis_mode": r[9],
            "pages_analyzed": r[10],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Phase F1: Analysis Stats Banner
# ---------------------------------------------------------------------------


def get_analysis_stats(user_id: int) -> dict:
    """Compute actionable stats for the analysis history stats banner.

    Returns:
        {
          "awaiting_resubmittal": int,  # projects with unresolved issues
          "new_issues":          int,  # new annotations found in latest scans
          "last_scan_at":        datetime | None,  # most recent completed job
        }
    """
    try:
        # Awaiting resubmittal: completed jobs that have comparison_json
        # with summary.new > 0 or summary.resolved < total non-unchanged
        # Simplified: count version groups where the latest comparison has new > 0
        if BACKEND == "postgres":
            row_resub = query_one(
                "SELECT COUNT(DISTINCT COALESCE(version_group, job_id)) "
                "FROM plan_analysis_jobs "
                "WHERE user_id = %s AND is_archived = FALSE "
                "AND comparison_json IS NOT NULL "
                "AND comparison_json::text LIKE %s",
                (user_id, '%"new": %'),
            )
            # Count total new issues across all latest comparisons
            row_new = query_one(
                "SELECT comparison_json FROM plan_analysis_jobs "
                "WHERE user_id = %s AND is_archived = FALSE "
                "AND comparison_json IS NOT NULL "
                "ORDER BY completed_at DESC LIMIT 20",
                (user_id,),
            )
            # Last scan
            row_last = query_one(
                "SELECT completed_at FROM plan_analysis_jobs "
                "WHERE user_id = %s AND status = 'completed' AND is_archived = FALSE "
                "ORDER BY completed_at DESC LIMIT 1",
                (user_id,),
            )
        else:
            row_resub = query_one(
                "SELECT COUNT(DISTINCT COALESCE(version_group, job_id)) "
                "FROM plan_analysis_jobs "
                "WHERE user_id = %s AND is_archived = FALSE "
                "AND comparison_json IS NOT NULL",
                (user_id,),
            )
            row_new = None
            row_last = query_one(
                "SELECT completed_at FROM plan_analysis_jobs "
                "WHERE user_id = %s AND status = 'completed' AND is_archived = FALSE "
                "ORDER BY completed_at DESC LIMIT 1",
                (user_id,),
            )

        # Count new issues from comparison JSONs
        new_issues = 0
        awaiting = 0
        try:
            if BACKEND == "postgres":
                rows_cmp = query(
                    "SELECT comparison_json FROM plan_analysis_jobs "
                    "WHERE user_id = %s AND is_archived = FALSE "
                    "AND comparison_json IS NOT NULL "
                    "AND status = 'completed' "
                    "ORDER BY completed_at DESC LIMIT 50",
                    (user_id,),
                )
                seen_groups = set()
                for r in rows_cmp:
                    raw = r[0]
                    try:
                        cmp = json.loads(raw) if isinstance(raw, str) else raw
                        summary = cmp.get("summary", {})
                        n = summary.get("new", 0)
                        if n > 0:
                            new_issues += n
                            # Count unique projects awaiting resubmittal
                            job_b_id = cmp.get("job_b_id", "")
                            if job_b_id not in seen_groups:
                                seen_groups.add(job_b_id)
                                awaiting += 1
                    except Exception:
                        pass
            else:
                awaiting = int(row_resub[0]) if (row_resub and row_resub[0]) else 0
        except Exception:
            awaiting = int(row_resub[0]) if (row_resub and row_resub[0]) else 0

        last_scan = row_last[0] if (row_last and row_last[0]) else None

        return {
            "awaiting_resubmittal": awaiting,
            "new_issues": new_issues,
            "last_scan_at": last_scan,
        }
    except Exception:
        logger.debug("get_analysis_stats failed for user %d", user_id, exc_info=True)
        return {
            "awaiting_resubmittal": 0,
            "new_issues": 0,
            "last_scan_at": None,
        }


def clear_pdf_data(job_id: str) -> None:
    """Clear stored PDF bytes after processing to free storage.

    Args:
        job_id: Job identifier
    """
    execute_write(
        "UPDATE plan_analysis_jobs SET pdf_data = NULL WHERE job_id = %s",
        (job_id,),
    )
    logger.debug(f"Cleared PDF data for job {job_id}")
