"""Background worker for async plan analysis.

Uses a ThreadPoolExecutor to process large PDFs outside the HTTP
request cycle. Each gunicorn worker gets its own single-thread pool
to avoid overwhelming the Railway single-dyno deployment.

The background thread:
  1. Reads PDF bytes from plan_analysis_jobs
  2. Runs vision analysis via analyze_plans()
  3. Renders page images at 72 DPI (gallery quality)
  4. Creates a plan_analysis_session for the image gallery
  5. Auto-extracts address/permit from vision results
  6. Updates job status and sends email notification
"""

import asyncio
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Allow 2 concurrent analysis jobs per gunicorn worker
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="plan-worker")

# DPI for gallery images (lower than 150 DPI used for vision analysis)
GALLERY_DPI = 72


def submit_job(job_id: str) -> None:
    """Submit a plan analysis job to the background thread pool.

    Args:
        job_id: Job identifier (must already exist in plan_analysis_jobs)
    """
    logger.info(f"[plan-worker] Submitting job {job_id} to background thread")
    _executor.submit(_process_job, job_id)


def _process_job(job_id: str) -> None:
    """Process a plan analysis job in a background thread.

    Requires its own Flask app context and asyncio event loop.
    """
    # Import here to avoid circular imports at module level
    from web.app import app

    with app.app_context():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            _do_analysis(job_id, loop)
        except Exception as e:
            logger.exception(f"[plan-worker] Job {job_id} failed: {e}")
            try:
                from web.plan_jobs import update_job_status

                update_job_status(
                    job_id,
                    "failed",
                    error_message=str(e),
                    completed_at=datetime.now(timezone.utc),
                )
                _send_failure_email(job_id, str(e))
            except Exception:
                logger.exception(f"[plan-worker] Failed to update job {job_id} status")
        finally:
            loop.close()


def _do_analysis(job_id: str, loop: asyncio.AbstractEventLoop) -> None:
    """Core analysis logic — runs inside app context with event loop."""
    import json
    from io import BytesIO

    from pypdf import PdfReader

    from src.tools.analyze_plans import analyze_plans
    from src.tools.validate_plans import validate_plans
    from src.vision.pdf_to_images import pdf_page_to_base64
    from web.plan_images import create_session
    from web.plan_jobs import (
        clear_pdf_data,
        get_job,
        get_job_pdf,
        update_job_status,
    )

    # Mark as processing
    update_job_status(
        job_id, "processing",
        started_at=datetime.now(timezone.utc),
        progress_stage="analyzing",
        progress_detail="Preparing analysis...",
    )

    # Load job metadata and PDF
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    pdf_bytes = get_job_pdf(job_id)
    if not pdf_bytes:
        raise ValueError(f"No PDF data for job {job_id}")

    filename = job["filename"]
    job_t0 = time.time()
    logger.info(
        f"[plan-worker] Processing {filename} ({job['file_size_mb']:.1f} MB) "
        f"mode={job.get('analysis_mode', 'sample')} quick={job['quick_check']}"
    )

    # ── Run analysis ──
    update_job_status(
        job_id, "processing",
        progress_stage="analyzing",
        progress_detail="Running AI vision analysis...",
    )

    analysis_mode = job.get("analysis_mode", "sample")
    analyze_all_pages = (analysis_mode == "full")

    analysis_t0 = time.time()
    vision_usage = None
    if job["quick_check"]:
        result_md = loop.run_until_complete(
            validate_plans(
                pdf_bytes=pdf_bytes,
                filename=filename,
                is_site_permit_addendum=job["is_addendum"],
                enable_vision=False,
            )
        )
        page_extractions = []
        page_annotations = []
    else:
        result_md, page_extractions, page_annotations, vision_usage = loop.run_until_complete(
            analyze_plans(
                pdf_bytes=pdf_bytes,
                filename=filename,
                project_description=job["project_description"],
                permit_type=job["permit_type"],
                return_structured=True,
                analyze_all_pages=analyze_all_pages,
                analysis_mode=analysis_mode,
                property_address=job.get("property_address"),
                submission_stage=job.get("submission_stage"),
            )
        )
    analysis_ms = int((time.time() - analysis_t0) * 1000)
    logger.info(f"[plan-worker] stage=analysis duration_ms={analysis_ms} job={job_id}")

    # ── Get page count ──
    reader = PdfReader(BytesIO(pdf_bytes))
    page_count = len(reader.pages)

    # ── Render gallery images at lower DPI (parallel) ──
    total_render = min(page_count, 50)
    update_job_status(
        job_id, "processing",
        progress_stage="rendering",
        progress_detail=f"Rendering page gallery (0/{total_render})...",
    )

    gallery_t0 = time.time()

    def _render_page(pn: int) -> tuple[int, str] | None:
        try:
            b64 = pdf_page_to_base64(pdf_bytes, pn, dpi=GALLERY_DPI)
            return (pn, b64)
        except Exception as e:
            logger.warning(f"[plan-worker] Skipped page {pn} for {filename}: {e}")
            return None

    # Parallel rendering with 4 threads (PDF rendering is I/O-bound on disk)
    from concurrent.futures import ThreadPoolExecutor as GalleryPool

    page_images = []
    with GalleryPool(max_workers=4, thread_name_prefix="gallery") as gallery_exec:
        futures = {gallery_exec.submit(_render_page, pn): pn for pn in range(total_render)}
        done_count = 0
        for future in futures:
            result = future.result()
            if result:
                page_images.append(result)
            done_count += 1
            if done_count % 5 == 0 or done_count == total_render:
                update_job_status(
                    job_id, "processing",
                    progress_stage="rendering",
                    progress_detail=f"Rendering page gallery ({done_count}/{total_render})...",
                )

    # Sort by page number to maintain order
    page_images.sort(key=lambda x: x[0])
    gallery_duration_ms = int((time.time() - gallery_t0) * 1000)
    logger.info(f"[plan-worker] stage=gallery pages={total_render} duration_ms={gallery_duration_ms} job={job_id}")

    # ── Finalize ──
    update_job_status(
        job_id, "processing",
        progress_stage="finalizing",
        progress_detail="Saving results...",
    )

    # ── Create session ──
    session_id = create_session(
        filename=filename,
        page_count=page_count,
        page_extractions=page_extractions,
        page_images=page_images,
        user_id=job["user_id"],
        page_annotations=page_annotations,
    )

    # ── Phase D2: Extract structural fingerprint ──
    fingerprint_json: str | None = None
    if page_extractions:  # guard: hollow sessions skip fingerprinting
        try:
            import json as _json
            from web.plan_fingerprint import extract_structural_fingerprint
            fp = extract_structural_fingerprint(page_extractions)
            if fp:
                fingerprint_json = _json.dumps(fp)
        except Exception:
            logger.warning("[plan-worker] Fingerprint extraction failed for %s", job_id, exc_info=True)

    # ── Auto-extract tags ──
    tags = _auto_extract_tags(page_extractions)
    tag_updates = {}

    if tags.get("property_address"):
        if job["property_address"]:
            tag_updates["address_source"] = "both"
        else:
            tag_updates["property_address"] = tags["property_address"]
            tag_updates["address_source"] = "auto"

    if tags.get("permit_number"):
        if job["permit_number"]:
            tag_updates["permit_source"] = "both"
        else:
            tag_updates["permit_number"] = tags["permit_number"]
            tag_updates["permit_source"] = "auto"

    # ── Update job as completed ──
    usage_fields = {}
    if vision_usage and vision_usage.total_calls > 0:
        usage_fields["vision_usage_json"] = json.dumps(vision_usage.to_dict())
    usage_fields["gallery_duration_ms"] = gallery_duration_ms
    usage_fields["pages_analyzed"] = len(page_extractions)

    fingerprint_fields = {}
    if fingerprint_json is not None:
        fingerprint_fields["structural_fingerprint"] = fingerprint_json

    update_job_status(
        job_id,
        "completed",
        session_id=session_id,
        report_md=result_md,
        completed_at=datetime.now(timezone.utc),
        **tag_updates,
        **usage_fields,
        **fingerprint_fields,
    )

    # ── Phase E1: Assign version group via fingerprint matching ──
    if job.get("user_id"):
        try:
            import json as _json2
            from web.plan_fingerprint import find_matching_job
            from web.plan_jobs import assign_version_group
            from src.db import query_one as _qone

            fp_parsed = _json2.loads(fingerprint_json) if fingerprint_json else []
            effective_address = tag_updates.get("property_address") or job.get("property_address")
            effective_permit = tag_updates.get("permit_number") or job.get("permit_number")

            # Fetch pdf_hash from DB (not in get_job() dict)
            hash_row = _qone(
                "SELECT pdf_hash FROM plan_analysis_jobs WHERE job_id = %s", (job_id,)
            )
            current_hash = hash_row[0] if hash_row else None

            match_job_id = find_matching_job(
                user_id=job["user_id"],
                current_job_id=job_id,
                current_fp=fp_parsed,
                current_hash=current_hash,
                filename=filename,
                property_address=effective_address,
                permit_number=effective_permit,
            )

            if match_job_id:
                # Get the matched job's version_group (or use its job_id as the group seed)
                match_row = _qone(
                    "SELECT version_group FROM plan_analysis_jobs WHERE job_id = %s",
                    (match_job_id,),
                )
                existing_group = match_row[0] if match_row else None

                if existing_group:
                    group_id = existing_group
                else:
                    # Seed the group — assign the matched job as v1 first
                    group_id = match_job_id
                    assign_version_group(match_job_id, group_id)

                assign_version_group(job_id, group_id)
                logger.info(
                    "[plan-worker] Assigned %s to version_group=%s (matched %s)",
                    job_id,
                    group_id,
                    match_job_id,
                )
        except Exception:
            logger.warning("[plan-worker] Version group assignment failed for %s", job_id, exc_info=True)

    # ── Clear PDF data to free storage ──
    clear_pdf_data(job_id)

    usage_log = ""
    if vision_usage and vision_usage.total_calls > 0:
        usage_log = (
            f", vision={vision_usage.total_calls} calls/"
            f"{vision_usage.total_tokens:,} tokens/"
            f"~${vision_usage.estimated_cost_usd:.4f}"
        )
    total_wall_ms = int((time.time() - job_t0) * 1000)
    logger.info(
        f"[plan-worker] Completed {filename}: {page_count} pages, "
        f"session={session_id}, analysis={analysis_ms}ms, gallery={gallery_duration_ms}ms, "
        f"total_wall={total_wall_ms}ms{usage_log}"
    )

    # ── Send email notification ──
    _send_success_email(job_id, filename, page_count, job["file_size_mb"])


def _auto_extract_tags(page_extractions: list[dict]) -> dict:
    """Extract property address and permit number from vision results.

    Scans page extractions for common metadata fields. Returns
    first non-empty values found.

    Args:
        page_extractions: List of dicts from vision analysis

    Returns:
        dict with 'property_address' and 'permit_number' (may be None)
    """
    address = None
    permit = None

    for ext in page_extractions:
        if not address:
            addr = ext.get("address") or ext.get("project_address") or ext.get("site_address")
            if addr and isinstance(addr, str) and len(addr.strip()) > 3:
                address = addr.strip()

        if not permit:
            pn = ext.get("permit_number") or ext.get("permit_no") or ext.get("dbi_permit")
            if pn and isinstance(pn, str):
                permit = pn.strip()
            else:
                # Try to find permit pattern in text fields
                for field in ["title", "sheet_id", "notes"]:
                    val = ext.get(field, "")
                    if isinstance(val, str):
                        match = re.search(r"20\d{8,10}", val)
                        if match:
                            permit = match.group(0)
                            break

        if address and permit:
            break

    return {"property_address": address, "permit_number": permit}


def _send_success_email(
    job_id: str,
    filename: str,
    page_count: int,
    file_size_mb: float,
) -> None:
    """Send email notification that analysis is ready."""
    from web.plan_jobs import get_job, update_job_status

    job = get_job(job_id)
    if not job or not job["user_id"]:
        return  # No email for anonymous users

    from web.auth import get_user_by_id

    user = get_user_by_id(job["user_id"])
    if not user or not user.get("email"):
        return

    base_url = os.environ.get("BASE_URL", "http://localhost:5001")
    results_url = f"{base_url}/plan-jobs/{job_id}/results"

    try:
        from flask import render_template
        from web.email_brief import send_brief_email

        html_body = render_template(
            "plan_analysis_email.html",
            filename=filename,
            page_count=page_count,
            filesize_mb=round(file_size_mb, 1),
            results_url=results_url,
            property_address=job.get("property_address"),
            permit_number=job.get("permit_number"),
        )

        subject = f"Plan Analysis Ready: {filename} — sfpermits.ai"
        send_brief_email(
            to_email=user["email"],
            html_body=html_body,
            subject=subject,
        )

        update_job_status(job_id, "completed", email_sent=True)
        logger.info(f"[plan-worker] Sent success email for job {job_id} to {user['email']}")
    except Exception as e:
        logger.warning(f"[plan-worker] Email send failed for job {job_id}: {e}")


def _send_failure_email(job_id: str, error_msg: str) -> None:
    """Send email notification that analysis failed."""
    from web.plan_jobs import get_job

    job = get_job(job_id)
    if not job or not job["user_id"]:
        return

    from web.auth import get_user_by_id

    user = get_user_by_id(job["user_id"])
    if not user or not user.get("email"):
        return

    base_url = os.environ.get("BASE_URL", "http://localhost:5001")

    try:
        from web.email_brief import send_brief_email

        html_body = f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #2563eb;">
        <h1 style="color: #2563eb; margin: 0; font-size: 1.5rem;">sfpermits.ai</h1>
    </div>
    <div style="padding: 30px 0;">
        <h2 style="color: #d32f2f;">Plan Analysis Issue</h2>
        <p>We encountered an error analyzing <strong>{job['filename']}</strong>.</p>
        <p style="color: #666; font-size: 0.9rem;">{error_msg}</p>
        <p style="margin-top: 24px;">
            <a href="{base_url}/" style="background: #2563eb; color: white; padding: 12px 28px;
               border-radius: 6px; text-decoration: none; font-weight: 600;">Try Again</a>
        </p>
        <p style="color: #999; font-size: 0.85rem; margin-top: 24px;">
            Tip: Try "Quick Check" mode for faster metadata-only analysis.
        </p>
    </div>
</div>
"""
        send_brief_email(
            to_email=user["email"],
            html_body=html_body,
            subject=f"Plan Analysis Issue: {job['filename']} — sfpermits.ai",
        )
        logger.info(f"[plan-worker] Sent failure email for job {job_id} to {user['email']}")
    except Exception as e:
        logger.warning(f"[plan-worker] Failure email send failed for job {job_id}: {e}")


def recover_stale_jobs() -> int:
    """Mark jobs stuck in 'processing' as 'stale'. Called on startup."""
    from web.plan_jobs import mark_stale_jobs

    count = mark_stale_jobs(max_age_minutes=15)
    if count:
        logger.info(f"[plan-worker] Recovered {count} stale jobs on startup")
    return count
