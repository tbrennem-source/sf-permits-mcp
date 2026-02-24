"""Pipeline health monitoring — Sprint 53 Session C.

Provides structured health checks for the nightly data pipeline:
  - Cron job success/failure history
  - Data freshness across permits, inspections, addenda
  - Stuck job detection
  - Pipeline health summary for admin dashboard and morning brief

All checks are read-only and safe to run at any time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.db import BACKEND, query, query_one

logger = logging.getLogger(__name__)


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


# ── Health check results ─────────────────────────────────────────


@dataclass
class HealthCheck:
    """Result of a single health check."""
    name: str
    status: str          # "ok" | "warn" | "critical" | "unknown"
    message: str
    detail: Optional[dict] = None


@dataclass
class PipelineHealthReport:
    """Aggregated pipeline health report."""
    run_at: str
    overall_status: str          # "ok" | "warn" | "critical" | "unknown"
    checks: list[HealthCheck] = field(default_factory=list)
    cron_history: list[dict] = field(default_factory=list)
    data_freshness: dict = field(default_factory=dict)
    stuck_jobs: list[dict] = field(default_factory=list)
    summary_line: str = ""


# ── Individual checks ────────────────────────────────────────────


def check_cron_health(warn_hours: float = 26.0, critical_hours: float = 50.0) -> HealthCheck:
    """Check when the last nightly cron run succeeded.

    warn_hours: alert if no success in this many hours (default 26 = slight over 1 day)
    critical_hours: critical alert if no success in this many hours (default 50 = ~2 days)
    """
    try:
        row = query_one(
            "SELECT started_at, completed_at FROM cron_log "
            "WHERE job_type = 'nightly' AND status = 'success' "
            "ORDER BY started_at DESC LIMIT 1"
        )
    except Exception as e:
        return HealthCheck(
            name="cron_nightly",
            status="unknown",
            message=f"Could not query cron_log: {e}",
        )

    if row is None or row[0] is None:
        return HealthCheck(
            name="cron_nightly",
            status="critical",
            message="No successful nightly run found — pipeline may never have run",
            detail={"last_success": None},
        )

    ts = row[0]
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return HealthCheck(
                name="cron_nightly",
                status="unknown",
                message=f"Could not parse last success timestamp: {ts}",
            )
    if isinstance(ts, datetime) and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    hours_ago = (now - ts).total_seconds() / 3600

    detail = {
        "last_success": ts.isoformat(),
        "hours_ago": round(hours_ago, 1),
    }

    if hours_ago > critical_hours:
        return HealthCheck(
            name="cron_nightly",
            status="critical",
            message=f"Last successful nightly run was {hours_ago:.1f}h ago (>{critical_hours}h threshold)",
            detail=detail,
        )
    elif hours_ago > warn_hours:
        return HealthCheck(
            name="cron_nightly",
            status="warn",
            message=f"Last successful nightly run was {hours_ago:.1f}h ago (>{warn_hours}h threshold)",
            detail=detail,
        )
    else:
        return HealthCheck(
            name="cron_nightly",
            status="ok",
            message=f"Last successful nightly run was {hours_ago:.1f}h ago",
            detail=detail,
        )


def check_data_freshness() -> HealthCheck:
    """Check data freshness across permits, inspections, and addenda tables."""
    results = {}

    # Permits: check MAX(status_date)
    try:
        row = query_one("SELECT MAX(status_date) FROM permits")
        if row and row[0]:
            results["permits_max_status_date"] = str(row[0])[:10]
        else:
            results["permits_max_status_date"] = None
    except Exception as e:
        results["permits_error"] = str(e)

    # Addenda: check MAX(data_as_of) and row count
    try:
        row = query_one("SELECT MAX(data_as_of), COUNT(*) FROM addenda")
        if row:
            results["addenda_max_data_as_of"] = str(row[0])[:10] if row[0] else None
            results["addenda_row_count"] = int(row[1]) if row[1] else 0
        else:
            results["addenda_max_data_as_of"] = None
            results["addenda_row_count"] = 0
    except Exception as e:
        results["addenda_error"] = str(e)

    # Inspections: check MAX(scheduled_date)
    try:
        row = query_one("SELECT MAX(scheduled_date) FROM inspections")
        if row and row[0]:
            results["inspections_max_date"] = str(row[0])[:10]
        else:
            results["inspections_max_date"] = None
    except Exception as e:
        results["inspections_error"] = str(e)

    # Determine status based on addenda freshness (primary concern)
    from datetime import date
    today = date.today()
    stale_fields = []

    addenda_dao = results.get("addenda_max_data_as_of")
    if addenda_dao:
        try:
            dao_date = date.fromisoformat(addenda_dao)
            days_old = (today - dao_date).days
            results["addenda_days_old"] = days_old
            if days_old > 5:
                stale_fields.append(f"addenda ({days_old}d old)")
        except (ValueError, TypeError):
            pass
    elif "addenda_error" not in results:
        stale_fields.append("addenda (no data_as_of found)")

    if stale_fields:
        status = "warn" if len(stale_fields) <= 1 else "critical"
        return HealthCheck(
            name="data_freshness",
            status=status,
            message=f"Stale data detected: {', '.join(stale_fields)}",
            detail=results,
        )

    return HealthCheck(
        name="data_freshness",
        status="ok",
        message="Data freshness OK",
        detail=results,
    )


def check_stuck_jobs(stuck_threshold_minutes: int = 120) -> HealthCheck:
    """Detect cron jobs that have been 'running' too long (likely crashed without cleanup)."""
    try:
        ph = _ph()
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=stuck_threshold_minutes)).isoformat()
        rows = query(
            f"SELECT log_id, job_type, started_at FROM cron_log "
            f"WHERE status = 'running' AND started_at < {ph} "
            f"ORDER BY started_at",
            (cutoff,),
        )
    except Exception as e:
        return HealthCheck(
            name="stuck_jobs",
            status="unknown",
            message=f"Could not query cron_log for stuck jobs: {e}",
        )

    if not rows:
        return HealthCheck(
            name="stuck_jobs",
            status="ok",
            message="No stuck jobs detected",
        )

    stuck = [
        {"log_id": r[0], "job_type": r[1], "started_at": str(r[2])}
        for r in rows
    ]
    return HealthCheck(
        name="stuck_jobs",
        status="warn",
        message=f"{len(stuck)} job(s) stuck in 'running' state for >{stuck_threshold_minutes}min",
        detail={"stuck_jobs": stuck},
    )


def check_recent_failures() -> HealthCheck:
    """Check for recent cron failures in the last 48 hours."""
    try:
        ph = _ph()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        rows = query(
            f"SELECT log_id, job_type, started_at, error_message FROM cron_log "
            f"WHERE status = 'failed' AND started_at > {ph} "
            f"ORDER BY started_at DESC",
            (cutoff,),
        )
    except Exception as e:
        return HealthCheck(
            name="recent_failures",
            status="unknown",
            message=f"Could not query cron_log for failures: {e}",
        )

    if not rows:
        return HealthCheck(
            name="recent_failures",
            status="ok",
            message="No failures in last 48h",
        )

    failures = [
        {
            "log_id": r[0],
            "job_type": r[1],
            "started_at": str(r[2]),
            "error": (r[3] or "")[:200],  # truncate long errors
        }
        for r in rows
    ]
    return HealthCheck(
        name="recent_failures",
        status="warn" if len(failures) <= 2 else "critical",
        message=f"{len(failures)} failure(s) in last 48h",
        detail={"failures": failures},
    )


# ── Cron history ─────────────────────────────────────────────────


def get_cron_history(limit: int = 20) -> list[dict]:
    """Get recent cron job history for the admin dashboard."""
    try:
        rows = query(
            "SELECT log_id, job_type, started_at, completed_at, status, "
            "lookback_days, soda_records, changes_inserted, inspections_updated, "
            "was_catchup, error_message "
            "FROM cron_log "
            "ORDER BY started_at DESC "
            f"LIMIT {limit}"
        )
    except Exception as e:
        logger.warning("Could not get cron history: %s", e)
        return []

    result = []
    for r in rows:
        # Compute duration
        started_at = r[2]
        completed_at = r[3]
        duration_s = None
        if started_at and completed_at:
            try:
                if isinstance(started_at, str):
                    started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                if isinstance(completed_at, str):
                    completed_at = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                if isinstance(started_at, datetime) and isinstance(completed_at, datetime):
                    duration_s = int((completed_at - started_at).total_seconds())
            except (ValueError, TypeError):
                pass

        result.append({
            "log_id": r[0],
            "job_type": r[1],
            "started_at": str(r[2]) if r[2] else None,
            "completed_at": str(r[3]) if r[3] else None,
            "status": r[4],
            "lookback_days": r[5],
            "soda_records": r[6],
            "changes_inserted": r[7],
            "inspections_updated": r[8],
            "was_catchup": r[9],
            "error_message": (r[10] or "")[:300] if r[10] else None,
            "duration_s": duration_s,
        })

    return result


# ── Main health report ───────────────────────────────────────────


def get_pipeline_health() -> PipelineHealthReport:
    """Run all health checks and return a consolidated report."""
    run_at = datetime.now(timezone.utc).isoformat()

    checks = [
        check_cron_health(),
        check_data_freshness(),
        check_stuck_jobs(),
        check_recent_failures(),
    ]

    # Compute overall status (worst of all checks)
    status_rank = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}
    overall_status = max(
        (c.status for c in checks),
        key=lambda s: status_rank.get(s, 0),
        default="unknown",
    )

    # Get recent cron history
    cron_history = get_cron_history(limit=15)

    # Get data freshness details
    freshness_check = next((c for c in checks if c.name == "data_freshness"), None)
    data_freshness = freshness_check.detail or {} if freshness_check else {}

    # Stuck jobs
    stuck_check = next((c for c in checks if c.name == "stuck_jobs"), None)
    stuck_jobs = (
        stuck_check.detail.get("stuck_jobs", [])
        if stuck_check and stuck_check.detail
        else []
    )

    # Human-readable summary line
    issues = [c.message for c in checks if c.status in ("warn", "critical")]
    if not issues:
        summary_line = "All pipeline checks passed"
    else:
        summary_line = f"{len(issues)} issue(s): " + "; ".join(issues[:2])

    return PipelineHealthReport(
        run_at=run_at,
        overall_status=overall_status,
        checks=checks,
        cron_history=cron_history,
        data_freshness=data_freshness,
        stuck_jobs=stuck_jobs,
        summary_line=summary_line,
    )


def get_pipeline_health_brief() -> dict:
    """Compact health summary for the morning brief (no heavy cron_history query)."""
    try:
        cron_check = check_cron_health()
        freshness_check = check_data_freshness()
        stuck_check = check_stuck_jobs()
        failures_check = check_recent_failures()

        checks = [cron_check, freshness_check, stuck_check, failures_check]
        status_rank = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}
        overall = max(
            (c.status for c in checks),
            key=lambda s: status_rank.get(s, 0),
            default="unknown",
        )

        issues = [c.message for c in checks if c.status in ("warn", "critical")]
        return {
            "status": overall,
            "issues": issues,
            "checks": [
                {"name": c.name, "status": c.status, "message": c.message}
                for c in checks
            ],
        }
    except Exception as e:
        logger.warning("Pipeline health brief failed: %s", e)
        return {"status": "unknown", "issues": [str(e)], "checks": []}
