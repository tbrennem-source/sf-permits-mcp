"""Addenda Staleness Diagnostic — Sprint 53 Session C.

Queries cron_log, addenda MAX dates, and optionally the SODA API
to identify data freshness gaps and root causes.

Usage:
    python -m scripts.diagnose_addenda                  # DB-only check
    python -m scripts.diagnose_addenda --soda           # Include SODA API check
    python -m scripts.diagnose_addenda --json           # Machine-readable output
    python -m scripts.diagnose_addenda --lookback 14    # Check last N days of cron runs

Exit codes:
    0 — data appears fresh (no staleness detected)
    1 — staleness detected (gap > threshold)
    2 — diagnostic error (could not connect to DB or API)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


# Staleness thresholds
ADDENDA_STALE_DAYS = 3       # Flag if addenda data_as_of is older than this
CRON_GAP_WARN_DAYS = 2       # Warn if no successful cron run in this many days
CRON_GAP_CRITICAL_DAYS = 5  # Critical if no successful cron run in this many days


@dataclass
class CronHealthSummary:
    last_success_at: Optional[str]
    last_run_at: Optional[str]
    last_run_status: Optional[str]
    days_since_success: Optional[float]
    total_runs_last_7d: int
    failed_runs_last_7d: int
    catchup_runs_last_7d: int


@dataclass
class AddenaFreshnessResult:
    max_data_as_of: Optional[str]   # Most recent data_as_of in addenda table
    max_finish_date: Optional[str]  # Most recent finish_date in addenda table
    total_rows: int
    days_since_data_as_of: Optional[float]
    is_stale: bool
    stale_reason: Optional[str]


@dataclass
class SodaCheckResult:
    reachable: bool
    recent_record_count: int          # records updated in last 3 days
    api_max_data_as_of: Optional[str]
    error: Optional[str]


@dataclass
class DiagnosticReport:
    run_at: str
    db_available: bool
    cron_health: Optional[CronHealthSummary]
    addenda_freshness: Optional[AddenaFreshnessResult]
    soda_check: Optional[SodaCheckResult]
    overall_status: str          # "fresh" | "stale" | "critical" | "unknown"
    root_cause: Optional[str]
    recommendations: list[str]


def _get_db_connection():
    """Get a database connection, returning None if unavailable."""
    try:
        from src.db import get_connection, BACKEND
        return get_connection(), BACKEND
    except Exception as e:
        logger.warning("DB connection failed: %s", e)
        return None, None


def check_cron_health(lookback_days: int = 7) -> CronHealthSummary:
    """Query cron_log for recent run history."""
    from src.db import query, query_one, BACKEND

    ph = "%s" if BACKEND == "postgres" else "?"
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    # Last successful run
    last_success_row = query_one(
        "SELECT started_at, completed_at FROM cron_log "
        f"WHERE job_type = 'nightly' AND status = 'success' "
        "ORDER BY started_at DESC LIMIT 1"
    )

    # Last run of any status
    last_run_row = query_one(
        "SELECT started_at, status FROM cron_log "
        "WHERE job_type = 'nightly' "
        "ORDER BY started_at DESC LIMIT 1"
    )

    # Run counts for the lookback window
    count_rows = query(
        f"SELECT status, COUNT(*) FROM cron_log "
        f"WHERE job_type = 'nightly' AND started_at > {ph} "
        f"GROUP BY status",
        (cutoff,),
    )
    count_by_status = {r[0]: r[1] for r in count_rows} if count_rows else {}
    total_runs = sum(count_by_status.values())
    failed_runs = count_by_status.get("failed", 0)

    # Catchup runs
    catchup_row = query_one(
        f"SELECT COUNT(*) FROM cron_log "
        f"WHERE job_type = 'nightly' AND was_catchup = TRUE AND started_at > {ph}",
        (cutoff,),
    )
    catchup_count = catchup_row[0] if catchup_row else 0

    # Compute days_since_success
    days_since = None
    last_success_at = None
    if last_success_row and last_success_row[0]:
        ts = last_success_row[0]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            days_since = (datetime.now(timezone.utc) - ts).total_seconds() / 86400
        last_success_at = str(ts)

    last_run_at = str(last_run_row[0]) if last_run_row and last_run_row[0] else None
    last_run_status = last_run_row[1] if last_run_row else None

    return CronHealthSummary(
        last_success_at=last_success_at,
        last_run_at=last_run_at,
        last_run_status=last_run_status,
        days_since_success=round(days_since, 2) if days_since is not None else None,
        total_runs_last_7d=total_runs,
        failed_runs_last_7d=failed_runs,
        catchup_runs_last_7d=catchup_count,
    )


def check_addenda_freshness() -> AddenaFreshnessResult:
    """Check the addenda table for data freshness."""
    from src.db import query_one, BACKEND

    # Probe for the addenda table
    try:
        if BACKEND == "postgres":
            table_exists_row = query_one(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'addenda'"
            )
        else:
            table_exists_row = query_one(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'addenda'"
            )
        if not table_exists_row or table_exists_row[0] == 0:
            return AddenaFreshnessResult(
                max_data_as_of=None,
                max_finish_date=None,
                total_rows=0,
                days_since_data_as_of=None,
                is_stale=True,
                stale_reason="addenda table does not exist",
            )
    except Exception as e:
        logger.debug("Table existence check failed: %s", e)

    row = query_one(
        "SELECT "
        "  MAX(data_as_of) AS max_data_as_of, "
        "  MAX(finish_date) AS max_finish_date, "
        "  COUNT(*) AS total_rows "
        "FROM addenda"
    )

    if row is None or row[2] == 0:
        return AddenaFreshnessResult(
            max_data_as_of=None,
            max_finish_date=None,
            total_rows=0,
            days_since_data_as_of=None,
            is_stale=True,
            stale_reason="addenda table is empty",
        )

    max_data_as_of_raw = row[0]
    max_finish_date_raw = row[1]
    total_rows = int(row[2])

    # Parse max_data_as_of
    days_since = None
    is_stale = False
    stale_reason = None

    if max_data_as_of_raw:
        try:
            dao_str = str(max_data_as_of_raw)[:10]
            dao_date = date.fromisoformat(dao_str)
            days_since = (date.today() - dao_date).days
            if days_since > ADDENDA_STALE_DAYS:
                is_stale = True
                stale_reason = (
                    f"data_as_of is {dao_str} — {days_since} days ago "
                    f"(threshold: {ADDENDA_STALE_DAYS} days)"
                )
        except (ValueError, TypeError) as e:
            logger.debug("Could not parse data_as_of: %s", e)

    return AddenaFreshnessResult(
        max_data_as_of=str(max_data_as_of_raw) if max_data_as_of_raw else None,
        max_finish_date=str(max_finish_date_raw) if max_finish_date_raw else None,
        total_rows=total_rows,
        days_since_data_as_of=days_since,
        is_stale=is_stale,
        stale_reason=stale_reason,
    )


async def check_soda_api() -> SodaCheckResult:
    """Query SODA API directly for recent addenda records."""
    try:
        from src.soda_client import SODAClient

        client = SODAClient()
        try:
            # Check for records updated in the last 3 days using data_as_of
            three_days_ago = (date.today() - timedelta(days=3)).isoformat()
            records = await client.query(
                endpoint_id="87xy-gk8d",
                where=f"data_as_of > '{three_days_ago}T00:00:00.000'",
                limit=10,
                order="data_as_of DESC",
            )
            recent_count = len(records)

            # Get the most recent data_as_of from the dataset
            latest_records = await client.query(
                endpoint_id="87xy-gk8d",
                limit=1,
                order="data_as_of DESC",
            )
            api_max_dao = None
            if latest_records:
                api_max_dao = latest_records[0].get("data_as_of")

            return SodaCheckResult(
                reachable=True,
                recent_record_count=recent_count,
                api_max_data_as_of=api_max_dao,
                error=None,
            )
        finally:
            await client.close()

    except Exception as e:
        logger.warning("SODA API check failed: %s", e)
        return SodaCheckResult(
            reachable=False,
            recent_record_count=0,
            api_max_data_as_of=None,
            error=str(e),
        )


def _determine_overall_status(
    cron: Optional[CronHealthSummary],
    freshness: Optional[AddenaFreshnessResult],
    soda: Optional[SodaCheckResult],
) -> tuple[str, Optional[str], list[str]]:
    """Determine overall status, root cause, and recommendations."""
    recommendations: list[str] = []
    root_cause = None

    # Critical: DB not available
    if cron is None and freshness is None:
        return "unknown", "Database unavailable — could not run checks", [
            "Verify DATABASE_URL is set and the database is reachable",
            "Check Railway service status for pgvector-db",
        ]

    # Assess cron health
    cron_critical = False
    cron_warn = False
    if cron:
        if cron.days_since_success is None:
            cron_critical = True
            root_cause = "No successful nightly run found in cron_log"
            recommendations.append(
                "Run POST /cron/nightly with CRON_SECRET to start tracking runs"
            )
        elif cron.days_since_success > CRON_GAP_CRITICAL_DAYS:
            cron_critical = True
            root_cause = (
                f"Nightly cron has not succeeded in {cron.days_since_success:.1f} days "
                f"(last: {cron.last_success_at})"
            )
            recommendations.append(
                f"POST /cron/nightly with lookback={int(cron.days_since_success) + 1} "
                f"to catch up on missed days"
            )
        elif cron.days_since_success > CRON_GAP_WARN_DAYS:
            cron_warn = True
            recommendations.append(
                f"Nightly cron last succeeded {cron.days_since_success:.1f} days ago — "
                f"check Railway cron schedule"
            )
        if cron.failed_runs_last_7d > 2:
            recommendations.append(
                f"{cron.failed_runs_last_7d} failed runs in last 7 days — "
                f"check error_message in cron_log"
            )

    # Assess addenda freshness
    addenda_stale = freshness and freshness.is_stale
    if freshness:
        if freshness.total_rows == 0:
            if root_cause is None:
                root_cause = "Addenda table is empty — initial ingest may not have run"
            recommendations.append(
                "Run: python -m src.ingest (full ingest, ~3.9M rows)"
            )
        elif addenda_stale:
            if root_cause is None:
                root_cause = freshness.stale_reason
            # Check if SODA also looks stale
            if soda and not soda.reachable:
                root_cause = "SODA API unreachable — addenda staleness may be from API outage"
                recommendations.append("Check https://data.sfgov.org for SODA API status")
            elif soda and soda.api_max_data_as_of:
                # Compare our DB to SODA
                try:
                    soda_date = date.fromisoformat(str(soda.api_max_data_as_of)[:10])
                    our_date = date.fromisoformat(str(freshness.max_data_as_of)[:10])
                    if soda_date > our_date:
                        recommendations.append(
                            f"SODA has newer data ({soda.api_max_data_as_of}) than our DB "
                            f"({freshness.max_data_as_of}) — "
                            f"nightly sync is behind"
                        )
                        recommendations.append(
                            "POST /cron/nightly with extended lookback, "
                            "or run python -m scripts.nightly_changes --lookback 7"
                        )
                    else:
                        root_cause = (
                            f"SODA itself appears stale "
                            f"(API max={soda.api_max_data_as_of}, our max={freshness.max_data_as_of}) "
                            f"— upstream data source issue, not our pipeline"
                        )
                        recommendations.append(
                            "SODA data source may be behind — monitor data.sfgov.org"
                        )
                except (ValueError, TypeError):
                    pass
            else:
                recommendations.append(
                    f"Run: python -m scripts.nightly_changes --lookback 7 "
                    f"to re-sync addenda data"
                )

    # Determine overall status
    if cron_critical or (freshness and freshness.total_rows == 0):
        return "critical", root_cause, recommendations
    elif cron_warn or addenda_stale:
        return "stale", root_cause, recommendations
    else:
        return "fresh", None, recommendations


async def run_diagnostic(
    check_soda: bool = False,
    lookback_days: int = 7,
) -> DiagnosticReport:
    """Run the full staleness diagnostic. Returns a DiagnosticReport."""
    run_at = datetime.now(timezone.utc).isoformat()

    # Try DB connection
    conn, backend = _get_db_connection()
    db_available = conn is not None
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass

    cron_health = None
    addenda_freshness = None
    soda_result = None

    if db_available:
        try:
            cron_health = check_cron_health(lookback_days=lookback_days)
        except Exception as e:
            logger.warning("cron_health check failed: %s", e)

        try:
            addenda_freshness = check_addenda_freshness()
        except Exception as e:
            logger.warning("addenda_freshness check failed: %s", e)

    if check_soda:
        soda_result = await check_soda_api()

    overall_status, root_cause, recommendations = _determine_overall_status(
        cron_health, addenda_freshness, soda_result
    )

    return DiagnosticReport(
        run_at=run_at,
        db_available=db_available,
        cron_health=cron_health,
        addenda_freshness=addenda_freshness,
        soda_check=soda_result,
        overall_status=overall_status,
        root_cause=root_cause,
        recommendations=recommendations,
    )


def _print_report(report: DiagnosticReport) -> None:
    """Print a human-readable diagnostic report."""
    STATUS_ICONS = {
        "fresh": "OK",
        "stale": "WARN",
        "critical": "CRITICAL",
        "unknown": "UNKNOWN",
    }
    icon = STATUS_ICONS.get(report.overall_status, "?")

    print(f"\n{'='*60}")
    print(f"  ADDENDA STALENESS DIAGNOSTIC — {report.run_at[:19]}Z")
    print(f"  Status: [{icon}] {report.overall_status.upper()}")
    print(f"{'='*60}")

    print(f"\n  DB Available: {'YES' if report.db_available else 'NO'}")

    if report.cron_health:
        c = report.cron_health
        print(f"\n  CRON LOG (last 7 days):")
        print(f"    Last success:        {c.last_success_at or 'NEVER'}")
        print(f"    Last run:            {c.last_run_at or 'NEVER'} ({c.last_run_status})")
        if c.days_since_success is not None:
            print(f"    Days since success:  {c.days_since_success:.1f}")
        print(f"    Runs (7d):           {c.total_runs_last_7d} total, {c.failed_runs_last_7d} failed, {c.catchup_runs_last_7d} catchup")

    if report.addenda_freshness:
        f = report.addenda_freshness
        print(f"\n  ADDENDA TABLE:")
        print(f"    Total rows:          {f.total_rows:,}")
        print(f"    Max data_as_of:      {f.max_data_as_of or 'NULL'}")
        print(f"    Max finish_date:     {f.max_finish_date or 'NULL'}")
        if f.days_since_data_as_of is not None:
            print(f"    Days since refresh:  {f.days_since_data_as_of}")
        print(f"    Stale:               {'YES — ' + f.stale_reason if f.is_stale else 'NO'}")

    if report.soda_check:
        s = report.soda_check
        print(f"\n  SODA API CHECK:")
        print(f"    Reachable:           {'YES' if s.reachable else 'NO'}")
        if s.reachable:
            print(f"    Recent records:      {s.recent_record_count} (last 3 days)")
            print(f"    API max data_as_of:  {s.api_max_data_as_of or 'NULL'}")
        if s.error:
            print(f"    Error:               {s.error}")

    if report.root_cause:
        print(f"\n  ROOT CAUSE:")
        print(f"    {report.root_cause}")

    if report.recommendations:
        print(f"\n  RECOMMENDATIONS:")
        for r in report.recommendations:
            print(f"    - {r}")

    print(f"\n{'='*60}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose addenda data staleness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--soda", action="store_true", help="Include SODA API check (requires network)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    parser.add_argument("--lookback", type=int, default=7, help="Days of cron history to review (default: 7)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    report = asyncio.run(run_diagnostic(
        check_soda=args.soda,
        lookback_days=args.lookback,
    ))

    if args.json:
        # Convert dataclasses to dicts for JSON serialization
        d = asdict(report)
        print(json.dumps(d, indent=2, default=str))
    else:
        _print_report(report)

    # Exit code based on status
    if report.overall_status == "fresh":
        return 0
    elif report.overall_status in ("stale", "unknown"):
        return 1
    else:  # critical
        return 1


if __name__ == "__main__":
    sys.exit(main())
