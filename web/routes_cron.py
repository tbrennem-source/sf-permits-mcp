"""Cron job routes — CRON_SECRET-protected endpoints for scheduled tasks.

Extracted from web/app.py during Sprint 64 Blueprint refactor.
"""

import asyncio
import json
import logging
import os
import time

from flask import Blueprint, Response, abort, g, jsonify, request

from web.helpers import run_async

bp = Blueprint("cron", __name__)


# ---------------------------------------------------------------------------
# Auth helper — verifies CRON_SECRET bearer token
# ---------------------------------------------------------------------------

def _check_api_auth():
    """Verify CRON_SECRET bearer token. Aborts 403 if invalid."""
    token = request.headers.get("Authorization", "").strip()
    secret = os.environ.get("CRON_SECRET", "").strip()
    expected = f"Bearer {secret}"
    if not secret or token != expected:
        logging.warning(
            "API auth failed: token_len=%d expected_len=%d path=%s",
            len(token), len(expected), request.path,
        )
        abort(403)


# ---------------------------------------------------------------------------
# Cron status endpoint — read-only, no auth required
# ---------------------------------------------------------------------------

@bp.route("/cron/status")
def cron_status():
    """Read-only view of recent cron job results."""
    from src.db import query
    try:
        rows = query(
            "SELECT job_type, started_at, completed_at, status, "
            "soda_records, changes_inserted, inspections_updated, "
            "was_catchup, error_message "
            "FROM cron_log "
            "ORDER BY started_at DESC "
            "LIMIT 20"
        )
        jobs = []
        for r in rows:
            jobs.append({
                "job_type": r[0],
                "started_at": str(r[1]) if r[1] else None,
                "completed_at": str(r[2]) if r[2] else None,
                "status": r[3],
                "soda_records": r[4],
                "changes_inserted": r[5],
                "inspections_updated": r[6],
                "was_catchup": r[7],
                "error_message": r[8],
            })
        return jsonify({"ok": True, "jobs": jobs, "total": len(jobs)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "jobs": []})


# ---------------------------------------------------------------------------
# Staleness alert helper
# ---------------------------------------------------------------------------

def _send_staleness_alert(warnings: list[str], nightly_result: dict) -> dict:
    """Send an email alert to admins when SODA data staleness is detected.

    Returns dict with send stats.
    """
    import smtplib
    from email.message import EmailMessage

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_from = os.environ.get("SMTP_FROM", "noreply@sfpermits.ai")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not all([smtp_host, smtp_user, smtp_pass]):
        logging.info("SMTP not configured — skipping staleness alert")
        return {"skipped": "smtp_not_configured"}

    from web.activity import get_admin_users
    admins = get_admin_users()
    if not admins:
        return {"skipped": "no_admins"}

    severity = "⚠️ Warning"
    if any("ALL sources returned 0" in w for w in warnings):
        severity = "🚨 Critical"
    elif any("even with extended lookback" in w for w in warnings):
        severity = "🚨 Alert"

    since = nightly_result.get("since", "?")
    lookback = nightly_result.get("lookback_days", "?")
    permits = nightly_result.get("soda_permits", 0)
    inspections = nightly_result.get("soda_inspections", 0)
    addenda = nightly_result.get("soda_addenda", 0)
    retry = nightly_result.get("retry_extended", False)

    warning_lines = "\n".join(f"  • {w}" for w in warnings)
    body = (
        f"{severity} — SODA Data Staleness Detected\n\n"
        f"The nightly job detected potential data freshness issues:\n\n"
        f"{warning_lines}\n\n"
        f"Details:\n"
        f"  Since: {since}\n"
        f"  Lookback: {lookback} days\n"
        f"  Auto-retry extended: {'Yes' if retry else 'No'}\n"
        f"  Permits: {permits}\n"
        f"  Inspections: {inspections}\n"
        f"  Addenda: {addenda}\n\n"
        f"If this persists, check https://data.sfgov.org for SODA API status.\n"
    )

    stats = {"total": len(admins), "sent": 0, "failed": 0}
    for admin in admins:
        email = admin.get("email")
        if not email:
            continue
        try:
            msg = EmailMessage()
            msg["Subject"] = f"sfpermits.ai {severity} — SODA data staleness"
            msg["From"] = smtp_from
            msg["To"] = email
            msg.set_content(body)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            stats["sent"] += 1
        except Exception:
            logging.exception("Failed to send staleness alert to %s", email)
            stats["failed"] += 1

    logging.info("Staleness alert: %d sent, %d failed", stats["sent"], stats["failed"])
    return stats


# ---------------------------------------------------------------------------
# Cron endpoints — protected by bearer token
# ---------------------------------------------------------------------------

@bp.route("/cron/nightly", methods=["POST"])
def cron_nightly():
    """Nightly delta fetch — detect permit changes via SODA API.

    Protected by CRON_SECRET bearer token. Designed to be called by
    Railway cron or external scheduler (e.g., cron-job.org) daily ~3am PT.
    """
    _check_api_auth()

    # === SESSION E: Stuck cron auto-close ===
    # Auto-close stuck cron jobs (>10 minutes in 'running' state).
    # Normal nightly completes in 13-40 seconds. Anything running >10 min
    # is dead (worker killed, process crashed, SODA hung). Previous
    # threshold was 15 min — tightened in Sprint 64 for faster recovery.
    try:
        from src.db import execute_write
        execute_write(
            "UPDATE cron_log SET status = 'failed', "
            "completed_at = NOW(), "
            "error_message = 'auto-closed: stuck >10 min (worker likely killed)' "
            "WHERE status = 'running' AND started_at < NOW() - INTERVAL '10 minutes'"
        )
    except Exception:
        pass  # Don't let cleanup failure block nightly

    from scripts.nightly_changes import run_nightly

    lookback = request.args.get("lookback", "1")
    try:
        lookback_days = max(1, min(int(lookback), 90))
    except ValueError:
        lookback_days = 1

    dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes")

    try:
        # Hard timeout on SODA pipeline (480s) to prevent orphaned cron_log
        # rows when the worker is killed by gunicorn (600s timeout).
        import asyncio as _asyncio
        result = run_async(
            _asyncio.wait_for(
                run_nightly(lookback_days=lookback_days, dry_run=dry_run),
                timeout=480,
            )
        )

        # If run_nightly returned a "skipped" status (concurrency guard),
        # return immediately without running post-processing steps.
        if isinstance(result, dict) and result.get("status") == "skipped":
            return Response(
                json.dumps(result, indent=2),
                mimetype="application/json",
            )

        # Append feedback triage (non-fatal — failure doesn't fail nightly)
        triage_result = {}
        if not dry_run:
            try:
                from scripts.feedback_triage import run_triage, ADMIN_EMAILS
                from web.activity import get_admin_users
                ADMIN_EMAILS.update(
                    a["email"].lower() for a in get_admin_users() if a.get("email")
                )
                host = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost:5001")
                triage_result = run_triage(host, os.environ.get("CRON_SECRET", ""))
            except Exception as te:
                logging.error("Feedback triage failed (non-fatal): %s", te)
                triage_result = {"error": str(te)}

        # Cleanup expired plan analysis sessions (non-fatal)
        cleanup_result = {}
        if not dry_run:
            try:
                from web.plan_images import cleanup_expired
                from web.plan_jobs import cleanup_old_jobs
                sessions_deleted = cleanup_expired(hours=24)
                jobs_deleted = cleanup_old_jobs(days=30)
                count = sessions_deleted + jobs_deleted
                cleanup_result = {
                    "plan_sessions_deleted": sessions_deleted,
                    "plan_jobs_deleted": jobs_deleted,
                }
            except Exception as ce:
                logging.error("Plan session cleanup failed (non-fatal): %s", ce)
                cleanup_result = {"error": str(ce)}

        # Refresh station velocity baselines (non-fatal)
        velocity_result = {}
        if not dry_run:
            try:
                from web.station_velocity import refresh_station_velocity
                velocity_result = refresh_station_velocity()
            except Exception as ve:
                logging.error("Station velocity refresh failed (non-fatal): %s", ve)
                velocity_result = {"error": str(ve)}

        # === SESSION D: Station congestion refresh ===
        congestion_result = {}
        if not dry_run:
            try:
                from web.station_velocity import refresh_station_congestion
                cong_stats = refresh_station_congestion()
                congestion_result = {"congestion_stations": cong_stats.get("congestion_stations", 0)}
            except Exception as cong_e:
                logging.getLogger(__name__).warning("congestion refresh failed: %s", cong_e)
                congestion_result = {"error": str(cong_e)}
        # === END SESSION D ===

        # Refresh reviewer-entity interaction graph (non-fatal)
        reviewer_result = {}
        if not dry_run:
            try:
                from web.reviewer_graph import refresh_reviewer_interactions
                reviewer_result = refresh_reviewer_interactions()
            except Exception as re_:
                logging.error("Reviewer graph refresh failed (non-fatal): %s", re_)
                reviewer_result = {"error": str(re_)}

        # Refresh operational knowledge chunks (non-fatal, runs after velocity)
        ops_chunks_result = {}
        if not dry_run:
            try:
                from web.ops_chunks import ingest_ops_chunks
                count = ingest_ops_chunks()
                ops_chunks_result = {"chunks": count}
            except Exception as oe:
                logging.error("Ops chunk ingestion failed (non-fatal): %s", oe)
                ops_chunks_result = {"error": str(oe)}

        # Refresh DQ cache (non-fatal — runs all checks and caches results)
        dq_cache_result = {}
        if not dry_run:
            try:
                from web.data_quality import refresh_dq_cache
                dq_cache_result = refresh_dq_cache()
            except Exception as dqe:
                logging.error("DQ cache refresh failed (non-fatal): %s", dqe)
                dq_cache_result = {"error": str(dqe)}

        # === Sprint 64: Signals pipeline (non-fatal) ===
        signals_result = {}
        if not dry_run:
            try:
                from src.signals.pipeline import run_signal_pipeline
                from src.db import get_connection as _sig_gc
                _sig_conn = _sig_gc()
                try:
                    signals_result = run_signal_pipeline(_sig_conn)
                finally:
                    _sig_conn.close()
            except Exception as sig_e:
                logging.error("Signal pipeline failed (non-fatal): %s", sig_e)
                signals_result = {"error": str(sig_e)}

        # === Sprint 64: Station velocity v2 refresh (non-fatal) ===
        velocity_v2_result = {}
        if not dry_run:
            try:
                from src.station_velocity_v2 import refresh_velocity_v2
                from src.db import get_connection as _v2_gc
                _v2_conn = _v2_gc()
                try:
                    velocity_v2_result = refresh_velocity_v2(_v2_conn)
                finally:
                    _v2_conn.close()
                # Also refresh station transitions
                try:
                    from src.tools.station_predictor import refresh_station_transitions
                    trans_stats = refresh_station_transitions()
                    velocity_v2_result["transitions"] = trans_stats.get("transitions", 0)
                except Exception as tr_e:
                    logging.warning("Station transitions refresh failed: %s", tr_e)
                    velocity_v2_result["transitions_error"] = str(tr_e)
            except Exception as v2_e:
                logging.error("Velocity v2 refresh failed (non-fatal): %s", v2_e)
                velocity_v2_result = {"error": str(v2_e)}

        # Send staleness alert email to admins if warnings detected
        staleness_alert_result = {}
        warnings = result.get("staleness_warnings", [])
        if warnings and not dry_run:
            try:
                staleness_alert_result = _send_staleness_alert(warnings, result)
            except Exception as se:
                logging.error("Staleness alert email failed (non-fatal): %s", se)
                staleness_alert_result = {"error": str(se)}

        return Response(
            json.dumps({
                "status": "ok", **result,
                "triage": triage_result,
                "cleanup": cleanup_result,
                "velocity": velocity_result,
                "congestion": congestion_result,
                "reviewer_graph": reviewer_result,
                "ops_chunks": ops_chunks_result,
                "dq_cache": dq_cache_result,
                "signals": signals_result,
                "velocity_v2": velocity_v2_result,
                "staleness_alert": staleness_alert_result,
            }, indent=2),
            mimetype="application/json",
        )
    except asyncio.TimeoutError:
        logging.error("Nightly cron timed out after 480s — marking cron_log as failed")
        # Best-effort cleanup of orphaned cron_log row
        try:
            from src.db import get_connection as _gc
            _c = _gc()
            _c.autocommit = True if not hasattr(_c, '_conn') else False
            if hasattr(_c, '_conn'):
                _c._conn.autocommit = True
            with _c.cursor() as _cur:
                _cur.execute(
                    "UPDATE cron_log SET status = 'failed', completed_at = NOW(), "
                    "error_message = 'Pipeline timeout (480s)' "
                    "WHERE status = 'running'"
                )
            _c.close()
        except Exception:
            pass
        return Response(
            json.dumps({"status": "timeout", "error": "Pipeline timeout (480s)"}, indent=2),
            status=504,
            mimetype="application/json",
        )
    except Exception as e:
        logging.error("Nightly cron failed: %s", e)
        return Response(
            json.dumps({"status": "error", "error": str(e)}, indent=2),
            status=500,
            mimetype="application/json",
        )


@bp.route("/cron/send-briefs", methods=["POST"])
def cron_send_briefs():
    """Send morning brief emails to subscribed users.

    Protected by CRON_SECRET bearer token. Designed to be called:
      - Daily at ~6am PT for daily subscribers
      - Monday at ~6am PT for weekly subscribers

    Query params:
      - frequency: 'daily' (default) or 'weekly'
    """
    _check_api_auth()

    from web.email_brief import send_briefs

    frequency = request.args.get("frequency", "daily")
    if frequency not in ("daily", "weekly"):
        frequency = "daily"

    try:
        result = send_briefs(frequency)

        # Append triage report email to admins (non-fatal)
        triage_email_result = {}
        try:
            from web.email_triage import send_triage_reports
            triage_email_result = send_triage_reports()
        except Exception as te:
            logging.error("Triage report email failed (non-fatal): %s", te)
            triage_email_result = {"error": str(te)}

        return Response(
            json.dumps({
                "status": "ok", "frequency": frequency,
                **result, "triage_report": triage_email_result,
            }, indent=2),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error("Brief send cron failed: %s", e)
        return Response(
            json.dumps({"status": "error", "error": str(e)}, indent=2),
            status=500,
            mimetype="application/json",
        )


@bp.route("/cron/rag-ingest", methods=["POST"])
def cron_rag_ingest():
    """Run RAG knowledge ingestion — chunk, embed, store to pgvector.

    Protected by CRON_SECRET bearer token. Call once after deploy to populate
    the vector store, or after knowledge base updates.

    Query params:
      - tier: 'tier1', 'tier2', 'tier3', 'tier4', 'ops', or 'all' (default: all)
      - clear: '0' to skip clearing (default: true for tier1-4, ops self-manages)
    """
    _check_api_auth()

    import json as json_mod
    tier = request.args.get("tier", "all")
    skip_clear = request.args.get("clear", "").lower() in ("0", "false", "no")

    try:
        from src.rag.store import ensure_table, clear_tier, get_stats, rebuild_ivfflat_index
        from scripts.rag_ingest import ingest_tier1, ingest_tier2, ingest_tier3, ingest_tier4

        ensure_table()

        # Clear existing official (tier1-4) chunks before re-ingesting to
        # prevent duplicate accumulation.  Ops chunks self-manage via
        # clear_file() in ingest_ops_chunks().
        cleared = 0
        ingesting_static = tier in ("tier1", "tier2", "tier3", "tier4", "all")
        if ingesting_static and not skip_clear:
            cleared = clear_tier("official")

        total = 0
        if tier in ("tier1", "all"):
            total += ingest_tier1()
        if tier in ("tier2", "all"):
            total += ingest_tier2()
        if tier in ("tier3", "all"):
            total += ingest_tier3()
        if tier in ("tier4", "all"):
            total += ingest_tier4()
        if tier in ("ops", "all"):
            try:
                from web.ops_chunks import ingest_ops_chunks
                total += ingest_ops_chunks()
            except Exception as oe:
                logging.warning("Ops chunk ingestion failed (non-fatal): %s", oe)

        # Rebuild index after bulk insert
        if total > 0:
            try:
                rebuild_ivfflat_index()
            except Exception as ie:
                logging.warning("IVFFlat rebuild skipped: %s", ie)

        stats = get_stats()

        return Response(
            json_mod.dumps({
                "status": "ok",
                "chunks_ingested": total,
                "chunks_cleared": cleared,
                "tier": tier,
                "stats": stats,
            }, indent=2, default=str),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error("RAG ingestion cron failed: %s", e)
        return Response(
            json_mod.dumps({"status": "error", "error": str(e)}, indent=2),
            status=500,
            mimetype="application/json",
        )


# ---------------------------------------------------------------------------
# Data migration endpoints — push bulk DuckDB data to production Postgres
# ---------------------------------------------------------------------------

@bp.route("/cron/migrate-schema", methods=["POST"])
def cron_migrate_schema():
    """Create bulk data tables (permits, contacts, etc.) on production Postgres.

    Protected by CRON_SECRET. Runs scripts/postgres_schema.sql which uses
    CREATE IF NOT EXISTS — safe to re-run.
    """
    _check_api_auth()
    import json as _json
    from pathlib import Path
    from src.db import get_connection, BACKEND

    if BACKEND != "postgres":
        return Response(
            _json.dumps({"ok": False, "error": "Not running on Postgres"}),
            status=400, mimetype="application/json",
        )

    schema_file = Path(__file__).parent.parent / "scripts" / "postgres_schema.sql"
    if not schema_file.exists():
        return Response(
            _json.dumps({"ok": False, "error": "Schema file not found"}),
            status=404, mimetype="application/json",
        )

    conn = get_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(schema_file.read_text())
        # Report created tables
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
            tables = [r[0] for r in cur.fetchall()]
        return Response(
            _json.dumps({"ok": True, "tables": tables}),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error("migrate-schema failed: %s", e)
        return Response(
            _json.dumps({"ok": False, "error": str(e)}),
            status=500, mimetype="application/json",
        )
    finally:
        conn.close()


@bp.route("/cron/migrate-data", methods=["POST"])
def cron_migrate_data():
    """Accept a batch of rows for a bulk data table.

    Protected by CRON_SECRET. Accepts JSON body:
        {
            "table": "permits",
            "columns": ["col1", "col2", ...],
            "rows": [[val1, val2, ...], ...],
            "truncate": false  // optional, set true for first batch
        }

    Uses psycopg2.extras.execute_values for fast bulk insert.
    """
    _check_api_auth()
    import json as _json
    from src.db import get_connection, BACKEND

    if BACKEND != "postgres":
        return Response(
            _json.dumps({"ok": False, "error": "Not running on Postgres"}),
            status=400, mimetype="application/json",
        )

    ALLOWED_TABLES = {
        "permits", "contacts", "entities", "relationships",
        "inspections", "timeline_stats", "ingest_log",
        "addenda", "violations", "complaints", "businesses",
    }

    data = request.get_json(force=True)
    table = data.get("table", "")
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    do_truncate = data.get("truncate", False)

    if table not in ALLOWED_TABLES:
        return Response(
            _json.dumps({"ok": False, "error": f"Table '{table}' not allowed"}),
            status=400, mimetype="application/json",
        )
    if not columns or not rows:
        return Response(
            _json.dumps({"ok": False, "error": "columns and rows required"}),
            status=400, mimetype="application/json",
        )

    conn = get_connection()
    try:
        from psycopg2.extras import execute_values

        if do_truncate:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE {table} CASCADE")
            conn.commit()

        cols = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"INSERT INTO {table} ({cols}) VALUES %s",
                rows,
                template=f"({placeholders})",
                page_size=5000,
            )
        conn.commit()

        return Response(
            _json.dumps({"ok": True, "table": table, "rows_inserted": len(rows)}),
            mimetype="application/json",
        )
    except Exception as e:
        conn.rollback()
        logging.error("migrate-data failed for %s: %s", table, e)
        return Response(
            _json.dumps({"ok": False, "error": str(e)}),
            status=500, mimetype="application/json",
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Regulatory watch seed
# ---------------------------------------------------------------------------

@bp.route("/cron/seed-regulatory", methods=["POST"])
def cron_seed_regulatory():
    """Seed regulatory watch items from JSON array.

    Protected by CRON_SECRET bearer token.
    POST body: JSON array of items, each with: title, source_type, source_id,
    and optional: description, status, impact_level, affected_sections,
    semantic_concepts, url, filed_date, effective_date, notes.
    """
    _check_api_auth()
    import json as _json
    from web.regulatory_watch import create_watch_item

    items = request.get_json(force=True, silent=True)
    if not isinstance(items, list):
        return jsonify({"error": "Expected JSON array of items"}), 400

    created = []
    for item in items:
        try:
            wid = create_watch_item(
                title=item["title"],
                source_type=item["source_type"],
                source_id=item["source_id"],
                description=item.get("description"),
                status=item.get("status", "monitoring"),
                impact_level=item.get("impact_level", "moderate"),
                affected_sections=item.get("affected_sections"),
                semantic_concepts=item.get("semantic_concepts"),
                url=item.get("url"),
                filed_date=item.get("filed_date"),
                effective_date=item.get("effective_date"),
                notes=item.get("notes"),
            )
            created.append({"title": item["title"], "watch_id": wid})
        except Exception as exc:
            created.append({"title": item.get("title", "?"), "error": str(exc)})

    return jsonify({"created": len([c for c in created if "watch_id" in c]),
                     "items": created})


# ---------------------------------------------------------------------------
# Data quality cache refresh
# ---------------------------------------------------------------------------

@bp.route("/cron/refresh-dq", methods=["POST"])
def cron_refresh_dq():
    """Refresh the DQ cache externally (CRON_SECRET auth).

    Can be called independently of the nightly cron to populate the
    DQ cache after a deploy or after bulk data loads.
    """
    _check_api_auth()
    import json as _json
    from web.data_quality import refresh_dq_cache
    try:
        result = refresh_dq_cache()
        return Response(
            _json.dumps({"status": "ok", **result}),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error("DQ cache refresh failed: %s", e)
        return Response(
            _json.dumps({"status": "error", "error": str(e)}),
            status=500,
            mimetype="application/json",
        )


# ---------------------------------------------------------------------------
# Signal detection pipeline
# ---------------------------------------------------------------------------

@bp.route("/cron/signals", methods=["POST"])
def cron_signals():
    """Run the nightly signal detection + property health pipeline.

    Protected by CRON_SECRET bearer token. Detects 13 signal types across
    permits, violations, complaints, and inspections. Computes property-level
    health tiers (on_track -> high_risk) and persists to property_health table.
    """
    _check_api_auth()
    import json as _json_mod
    from src.signals.pipeline import run_signal_pipeline
    from src.db import get_connection

    try:
        conn = get_connection()
        try:
            stats = run_signal_pipeline(conn)
        finally:
            conn.close()
        return Response(
            _json_mod.dumps({"status": "ok", **stats}),
            mimetype="application/json",
        )
    except Exception as e:
        logging.getLogger(__name__).exception("signal pipeline failed")
        return Response(
            _json_mod.dumps({"status": "error", "error": str(e)}),
            status=500,
            mimetype="application/json",
        )


# ---------------------------------------------------------------------------
# Station velocity refresh
# ---------------------------------------------------------------------------

@bp.route("/cron/velocity-refresh", methods=["POST"])
def cron_velocity_refresh():
    """Refresh station velocity v2 baselines from addenda routing data.

    Protected by CRON_SECRET bearer token. Recomputes p25/p50/p75/p90
    per station per metric_type (initial/revision) per period (all, 2024-2026, recent_6mo).
    """
    _check_api_auth()
    import json as _json_mod
    from src.station_velocity_v2 import refresh_velocity_v2
    from src.db import get_connection

    try:
        conn = get_connection()
        try:
            stats = refresh_velocity_v2(conn)
        finally:
            conn.close()

        # === SESSION B: Station transitions refresh ===
        try:
            from src.tools.station_predictor import refresh_station_transitions
            trans_stats = refresh_station_transitions()
            stats["transitions"] = trans_stats.get("transitions", 0)
        except Exception as e:
            logging.getLogger(__name__).warning("transitions refresh failed: %s", e)
            stats["transitions_error"] = str(e)
        # === END SESSION B ===

        # === SESSION D: Station congestion refresh ===
        try:
            from web.station_velocity import refresh_station_congestion
            cong_stats = refresh_station_congestion()
            stats["congestion"] = cong_stats.get("congestion_stations", 0)
        except Exception as e:
            logging.getLogger(__name__).warning("congestion refresh failed: %s", e)
            stats["congestion_error"] = str(e)
        # === END SESSION D ===

        return Response(
            _json_mod.dumps({"status": "ok", **stats}),
            mimetype="application/json",
        )
    except Exception as e:
        logging.getLogger(__name__).exception("velocity-refresh failed")
        return Response(
            _json_mod.dumps({"status": "error", "error": str(e)}),
            status=500,
            mimetype="application/json",
        )


# ---------------------------------------------------------------------------
# Database migrations
# ---------------------------------------------------------------------------

@bp.route("/cron/migrate", methods=["POST"])
def cron_migrate():
    """Run all database migrations.

    Protected by CRON_SECRET bearer token. Designed to be called after
    deploy to apply any pending schema changes.

    Returns JSON with per-migration results.
    """
    _check_api_auth()
    from scripts.run_prod_migrations import run_all_migrations

    result = run_all_migrations()
    status = 200 if result.get("ok") else 500
    return Response(json.dumps(result, indent=2), mimetype="application/json"), status


# ---------------------------------------------------------------------------
# Database backup
# ---------------------------------------------------------------------------

@bp.route("/cron/backup", methods=["POST"])
def cron_backup():
    """Run pg_dump and store a timestamped backup.

    Protected by CRON_SECRET bearer token. Designed to be called daily
    by an external scheduler after the nightly refresh.

    Returns JSON with backup metadata (filename, size, row counts).
    """
    _check_api_auth()
    from scripts.db_backup import run_backup

    result = run_backup()
    status = 200 if result.get("ok") else 500
    return Response(json.dumps(result, indent=2), mimetype="application/json"), status


# === SESSION B: REFERENCE TABLES ===

@bp.route("/cron/seed-references", methods=["POST"])
def cron_seed_references():
    """Seed predict_permits reference tables from hardcoded rules.

    Protected by CRON_SECRET bearer token. Idempotent — safe to re-run
    after deploys to refresh reference data without data loss.

    Returns JSON with row counts for each table:
      - ref_zoning_routing
      - ref_permit_forms
      - ref_agency_triggers
    """
    _check_api_auth()
    from scripts.seed_reference_tables import seed_reference_tables

    result = seed_reference_tables()
    status = 200 if result.get("ok") else 500
    return jsonify(result), status


# === SPRINT 54C: DATA INGEST EXPANSION ===


class _PgConnWrapper:
    """Thin wrapper making psycopg2 connections usable by DuckDB-style ingest code.

    Translates conn.execute(sql, params) and conn.executemany(sql, batch)
    into cursor-based calls, and converts ? placeholders to %s for Postgres.
    """

    def __init__(self, pg_conn):
        self._conn = pg_conn
        self._conn.autocommit = False

    @staticmethod
    def _translate_sql(sql):
        """Convert DuckDB SQL to Postgres-compatible SQL."""
        sql = sql.replace("?", "%s")
        # INSERT OR REPLACE INTO ingest_log -> INSERT ... ON CONFLICT (PK) DO UPDATE
        if "INSERT OR REPLACE INTO ingest_log" in sql:
            sql = sql.replace(
                "INSERT OR REPLACE INTO ingest_log VALUES (%s, %s, %s, %s, %s)",
                "INSERT INTO ingest_log VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (dataset_id) DO UPDATE SET "
                "dataset_name=EXCLUDED.dataset_name, last_fetched=EXCLUDED.last_fetched, "
                "records_fetched=EXCLUDED.records_fetched, last_record_count=EXCLUDED.last_record_count",
            )
        else:
            # Convert to INSERT ... ON CONFLICT DO NOTHING for all other tables.
            # Ingest functions DELETE first, so duplicates in SODA batches are harmless.
            sql = sql.replace("INSERT OR REPLACE INTO", "INSERT INTO")
            if "ON CONFLICT" not in sql and "INSERT INTO" in sql:
                sql += " ON CONFLICT DO NOTHING"
        return sql

    def execute(self, sql, params=None):
        sql = self._translate_sql(sql)
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, batch):
        sql = self._translate_sql(sql)
        import psycopg2.extras
        with self._conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, batch, page_size=5000)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def _get_ingest_conn():
    """Get a connection suitable for SODA ingest (works on both DuckDB and Postgres)."""
    from src.db import get_connection, BACKEND, init_schema
    conn = get_connection()
    if BACKEND == "postgres":
        return _PgConnWrapper(conn)
    else:
        init_schema(conn)
        return conn


@bp.route("/cron/ingest-boiler", methods=["POST"])
def cron_ingest_boiler():
    """Ingest boiler permits from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_boiler_permits
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_boiler_permits(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "boiler_permits", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-fire", methods=["POST"])
def cron_ingest_fire():
    """Ingest fire permits from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_fire_permits
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_fire_permits(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "fire_permits", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-planning", methods=["POST"])
def cron_ingest_planning():
    """Ingest planning records (projects + non-projects) from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_planning_records
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_planning_records(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "planning_records", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-tax-rolls", methods=["POST"])
def cron_ingest_tax_rolls():
    """Ingest tax rolls (latest 3 years) from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_tax_rolls
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_tax_rolls(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "tax_rolls", "rows": count, "elapsed_s": round(elapsed, 1)})


# === SESSION A: TRADE PERMIT + NEW DATASET ENDPOINTS ===

@bp.route("/cron/ingest-electrical", methods=["POST"])
def cron_ingest_electrical():
    """Ingest electrical permits from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_electrical_permits
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_electrical_permits(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "permits", "permit_type": "electrical", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-plumbing", methods=["POST"])
def cron_ingest_plumbing():
    """Ingest plumbing permits from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_plumbing_permits
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_plumbing_permits(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "permits", "permit_type": "plumbing", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-street-use", methods=["POST"])
def cron_ingest_street_use():
    """Ingest street-use permits (~1.2M rows) from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_street_use_permits
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_street_use_permits(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "street_use_permits", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-development-pipeline", methods=["POST"])
def cron_ingest_development_pipeline():
    """Ingest SF Development Pipeline from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_development_pipeline
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_development_pipeline(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "development_pipeline", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-affordable-housing", methods=["POST"])
def cron_ingest_affordable_housing():
    """Ingest Affordable Housing Pipeline from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_affordable_housing
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_affordable_housing(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "affordable_housing", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-housing-production", methods=["POST"])
def cron_ingest_housing_production():
    """Ingest Housing Production from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_housing_production
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_housing_production(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "housing_production", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-dwelling-completions", methods=["POST"])
def cron_ingest_dwelling_completions():
    """Ingest Dwelling Unit Completions from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_dwelling_completions
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_dwelling_completions(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "dwelling_completions", "rows": count, "elapsed_s": round(elapsed, 1)})

# === END SESSION A: TRADE PERMIT + NEW DATASET ENDPOINTS ===


@bp.route("/cron/cross-ref-check", methods=["POST"])
def cron_cross_ref_check():
    """Run cross-reference verification queries. CRON_SECRET auth."""
    _check_api_auth()
    from src.db import get_connection, BACKEND

    conn = get_connection()
    results = {}
    try:
        if BACKEND == "postgres":
            conn.autocommit = True
            with conn.cursor() as cur:
                # Planning -> Building permits match
                cur.execute("""
                    SELECT COUNT(DISTINCT pr.record_id)
                    FROM planning_records pr
                    JOIN permits p ON pr.block = p.block AND pr.lot = p.lot
                """)
                results["planning_to_permits"] = cur.fetchone()[0]

                # Tax rolls -> Active permits match
                cur.execute("""
                    SELECT COUNT(DISTINCT tr.block || '-' || tr.lot)
                    FROM tax_rolls tr
                    JOIN permits p ON tr.block = p.block AND tr.lot = p.lot
                    WHERE p.status IN ('issued', 'complete', 'filed', 'approved')
                """)
                results["tax_to_active_permits"] = cur.fetchone()[0]

                # Boiler -> Building permits match
                cur.execute("""
                    SELECT COUNT(DISTINCT bp.permit_number)
                    FROM boiler_permits bp
                    JOIN permits p ON bp.block = p.block AND bp.lot = p.lot
                """)
                results["boiler_to_permits"] = cur.fetchone()[0]

                # Total counts for context
                cur.execute("SELECT COUNT(*) FROM planning_records")
                results["total_planning"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM tax_rolls")
                results["total_tax_rolls"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM boiler_permits")
                results["total_boiler"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM permits")
                results["total_permits"] = cur.fetchone()[0]
        else:
            results["planning_to_permits"] = conn.execute("""
                SELECT COUNT(DISTINCT pr.record_id)
                FROM planning_records pr
                JOIN permits p ON pr.block = p.block AND pr.lot = p.lot
            """).fetchone()[0]
            results["tax_to_active_permits"] = conn.execute("""
                SELECT COUNT(DISTINCT tr.block || '-' || tr.lot)
                FROM tax_rolls tr
                JOIN permits p ON tr.block = p.block AND tr.lot = p.lot
                WHERE p.status IN ('issued', 'complete', 'filed', 'approved')
            """).fetchone()[0]
            results["boiler_to_permits"] = conn.execute("""
                SELECT COUNT(DISTINCT bp.permit_number)
                FROM boiler_permits bp
                JOIN permits p ON bp.block = p.block AND bp.lot = p.lot
            """).fetchone()[0]
            results["total_planning"] = conn.execute("SELECT COUNT(*) FROM planning_records").fetchone()[0]
            results["total_tax_rolls"] = conn.execute("SELECT COUNT(*) FROM tax_rolls").fetchone()[0]
            results["total_boiler"] = conn.execute("SELECT COUNT(*) FROM boiler_permits").fetchone()[0]
            results["total_permits"] = conn.execute("SELECT COUNT(*) FROM permits").fetchone()[0]
    finally:
        conn.close()

    # Compute match rates
    for key, total_key in [
        ("planning_to_permits", "total_planning"),
        ("tax_to_active_permits", "total_tax_rolls"),
        ("boiler_to_permits", "total_boiler"),
    ]:
        total = results.get(total_key, 0)
        matched = results.get(key, 0)
        results[f"{key}_pct"] = round(matched * 100 / total, 1) if total > 0 else 0

    return jsonify({"ok": True, "cross_refs": results})


# === SESSION C: PIPELINE HEALTH ===

@bp.route("/cron/pipeline-health", methods=["GET", "POST"])
def cron_pipeline_health():
    """Pipeline health check endpoint.

    GET  — Returns current pipeline health as JSON (no auth required for read).
    POST — With action=run_nightly: triggers a nightly run (requires CRON_SECRET).

    Protected by CRON_SECRET for POST/write operations.
    """

    if request.method == "POST":
        # POST requires CRON_SECRET auth, or admin session for dashboard re-run
        token = request.headers.get("Authorization", "").strip()
        secret = os.environ.get("CRON_SECRET", "").strip()
        expected = f"Bearer {secret}"
        token_ok = secret and token == expected
        admin_ok = hasattr(g, "user") and g.user and g.user.get("is_admin")
        if not token_ok and not admin_ok:
            abort(403)

        action = request.args.get("action", "")
        if action == "run_nightly":
            from scripts.nightly_changes import run_nightly
            lookback = int(request.args.get("lookback", "1"))
            try:
                result = run_async(run_nightly(lookback_days=lookback, dry_run=False))
                return jsonify({"ok": True, "result": {
                    k: v for k, v in result.items()
                    if k != "step_results"  # omit verbose step details
                }})
            except Exception as e:
                logging.exception("cron_pipeline_health run_nightly failed")
                return jsonify({"ok": False, "error": str(e)}), 500

        return jsonify({"ok": False, "error": "unknown action"}), 400

    # GET — return pipeline health (read-only)
    try:
        from web.pipeline_health import get_pipeline_health
        from dataclasses import asdict
        report = get_pipeline_health()
        # Convert dataclass to dict
        report_dict = {
            "run_at": report.run_at,
            "overall_status": report.overall_status,
            "summary_line": report.summary_line,
            "checks": [
                {"name": c.name, "status": c.status, "message": c.message}
                for c in report.checks
            ],
            "stuck_jobs_count": len(report.stuck_jobs),
            "data_freshness": report.data_freshness,
        }
        return jsonify({"ok": True, "health": report_dict})
    except Exception as e:
        logging.exception("cron_pipeline_health GET failed")
        return jsonify({"ok": False, "error": str(e)}), 500


# === END SESSION C: PIPELINE HEALTH ===


# === SESSION C: PLUMBING INSPECTIONS + BRIEF ===

@bp.route("/cron/ingest-plumbing-inspections", methods=["POST"])
def cron_ingest_plumbing_inspections():
    """Ingest plumbing inspections (fuas-yurr) into shared inspections table. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_plumbing_inspections
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    client = SODAClient()
    try:
        count = run_async(ingest_plumbing_inspections(conn, client))
        conn.commit()
    finally:
        run_async(client.close())
        conn.close()
    elapsed = time.time() - start
    return jsonify({
        "ok": True,
        "table": "inspections",
        "source": "plumbing",
        "rows": count,
        "elapsed_s": round(elapsed, 1),
    })

# === END SESSION C: PLUMBING INSPECTIONS + BRIEF ===


# === SESSION F: REVIEW METRICS INGEST ===

@bp.route("/cron/ingest-permit-issuance-metrics", methods=["POST"])
def cron_ingest_permit_issuance_metrics():
    """Ingest DBI permit issuance metrics (gzxm-jz5j) from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_permit_issuance_metrics
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    try:
        count = run_async(ingest_permit_issuance_metrics(conn, SODAClient()))
        if hasattr(conn, "commit"):
            conn.commit()
    except Exception as e:
        logging.exception("cron_ingest_permit_issuance_metrics failed")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "permit_issuance_metrics", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-permit-review-metrics", methods=["POST"])
def cron_ingest_permit_review_metrics():
    """Ingest DBI permit review metrics (5bat-azvb) from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_permit_review_metrics
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    try:
        count = run_async(ingest_permit_review_metrics(conn, SODAClient()))
        if hasattr(conn, "commit"):
            conn.commit()
    except Exception as e:
        logging.exception("cron_ingest_permit_review_metrics failed")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "permit_review_metrics", "rows": count, "elapsed_s": round(elapsed, 1)})


@bp.route("/cron/ingest-planning-review-metrics", methods=["POST"])
def cron_ingest_planning_review_metrics():
    """Ingest Planning Department review metrics (d4jk-jw33) from SODA API. CRON_SECRET auth."""
    _check_api_auth()
    from src.ingest import ingest_planning_review_metrics
    from src.soda_client import SODAClient

    start = time.time()
    conn = _get_ingest_conn()
    try:
        count = run_async(ingest_planning_review_metrics(conn, SODAClient()))
        if hasattr(conn, "commit"):
            conn.commit()
    except Exception as e:
        logging.exception("cron_ingest_planning_review_metrics failed")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()
    elapsed = time.time() - start
    return jsonify({"ok": True, "table": "planning_review_metrics", "rows": count, "elapsed_s": round(elapsed, 1)})

# === END SESSION F: REVIEW METRICS INGEST ===
