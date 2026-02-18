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
                    "analysis_mode) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
            "analysis_mode) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            ),
        )

    logger.info(
        f"Created plan job {job_id}: {filename} ({file_size_mb:.1f} MB, "
        f"async={is_async}, user={user_id})"
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
        "analysis_mode, pages_analyzed "
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


def get_user_jobs(user_id: int, limit: int = 20) -> list[dict]:
    """Get recent jobs for a user, ordered by created_at desc.

    Args:
        user_id: User identifier
        limit: Max results

    Returns:
        List of job dicts (without pdf_data or report_md for efficiency)
    """
    rows = query(
        "SELECT job_id, session_id, filename, file_size_mb, status, "
        "is_async, quick_check, property_address, permit_number, "
        "created_at, completed_at, error_message, "
        "analysis_mode, pages_analyzed "
        "FROM plan_analysis_jobs "
        "WHERE user_id = %s "
        "ORDER BY created_at DESC "
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
        "analysis_mode, pages_analyzed "
        "FROM plan_analysis_jobs "
        "WHERE user_id = %s "
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


def cleanup_old_jobs(days: int = 30) -> int:
    """Delete jobs older than N days. Returns count deleted.

    Args:
        days: Age threshold in days (default 30)

    Returns:
        Number of jobs deleted
    """
    if BACKEND == "postgres":
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
        row = query_one(
            "SELECT COUNT(*) FROM plan_analysis_jobs "
            "WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '"
            + str(days)
            + " days'"
        )
        count = row[0] if row else 0
        if count > 0:
            execute_write(
                "DELETE FROM plan_analysis_jobs "
                "WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '"
                + str(days)
                + " days'"
            )

    if count > 0:
        logger.info(f"Cleaned up {count} old plan analysis jobs (>{days}d old)")
    return count


def delete_job(job_id: str, user_id: int) -> bool:
    """Delete a job belonging to a specific user.

    Args:
        job_id: Job identifier
        user_id: Owner user ID (ensures users can only delete their own jobs)

    Returns:
        True if a row was deleted, False otherwise
    """
    # Check ownership first
    row = query_one(
        "SELECT user_id FROM plan_analysis_jobs WHERE job_id = %s",
        (job_id,),
    )
    if not row or row[0] != user_id:
        return False

    execute_write(
        "DELETE FROM plan_analysis_jobs WHERE job_id = %s AND user_id = %s",
        (job_id, user_id),
    )
    logger.info(f"Deleted plan job {job_id} for user {user_id}")
    return True


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
