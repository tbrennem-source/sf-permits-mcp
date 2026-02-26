"""Run all production database migrations in order.

Each migration is idempotent — safe to re-run at any time. Migrations are
applied in strict order: core schema → user tables → activity tables →
misc columns → signal tables.

Usage:
    python -m scripts.run_prod_migrations               # full run
    python -m scripts.run_prod_migrations --dry-run     # show plan only
    python -m scripts.run_prod_migrations --list        # list migrations
    python -m scripts.run_prod_migrations --only signals  # one step by name

Exit codes:
    0 — all migrations succeeded (or no-ops)
    1 — one or more migrations failed
    2 — incorrect usage / configuration error
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, NamedTuple

# Ensure project root is on sys.path when running as a module
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------

class Migration(NamedTuple):
    name: str
    description: str
    run: Callable[[], dict[str, Any]]


def _run_sql_file(sql_path: Path) -> dict[str, Any]:
    """Execute a .sql file against the active Postgres connection."""
    from src.db import get_connection, BACKEND  # type: ignore

    if BACKEND != "postgres":
        return {"ok": True, "skipped": True,
                "reason": f"DuckDB mode — {sql_path.name} not needed"}

    sql = sql_path.read_text()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        return {"ok": True, "file": sql_path.name}
    except Exception as exc:
        conn.rollback()
        logger.error("SQL migration %s failed: %s", sql_path.name, exc)
        return {"ok": False, "error": str(exc), "file": sql_path.name}
    finally:
        conn.close()


# ---- individual migration runners ----------------------------------------

def _run_user_tables() -> dict[str, Any]:
    """Create users, auth_tokens, watch_items tables (add_user_tables.sql)."""
    return _run_sql_file(Path(__file__).parent / "add_user_tables.sql")


def _run_activity_tables() -> dict[str, Any]:
    """Create activity_log, feedback tables (add_activity_tables.sql)."""
    return _run_sql_file(Path(__file__).parent / "add_activity_tables.sql")


def _run_changes_table() -> dict[str, Any]:
    """Create permit_changes cron-log table (add_changes_table.sql)."""
    return _run_sql_file(Path(__file__).parent / "add_changes_table.sql")


def _run_brief_email() -> dict[str, Any]:
    """Add email brief columns to users table (add_brief_email.sql)."""
    return _run_sql_file(Path(__file__).parent / "add_brief_email.sql")


def _run_invite_code() -> dict[str, Any]:
    """Add invite_code column to users table (add_invite_code.sql)."""
    return _run_sql_file(Path(__file__).parent / "add_invite_code.sql")


def _run_signals() -> dict[str, Any]:
    """Create signal_types, permit_signals, property_signals, property_health tables."""
    from scripts.migrate_signals import run_migration  # type: ignore
    return run_migration()


def _run_schema() -> dict[str, Any]:
    """Create bulk data tables from postgres_schema.sql (permits, contacts, etc.)."""
    return _run_sql_file(Path(__file__).parent / "postgres_schema.sql")


def _run_cron_log_columns() -> dict[str, Any]:
    """Add duration_seconds and records_processed columns to cron_log."""
    from src.db import get_connection, BACKEND  # type: ignore

    if BACKEND != "postgres":
        return {"ok": True, "skipped": True, "reason": "DuckDB mode — not needed"}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE cron_log ADD COLUMN IF NOT EXISTS duration_seconds FLOAT;
                ALTER TABLE cron_log ADD COLUMN IF NOT EXISTS records_processed INTEGER;
            """)
        conn.commit()
        return {"ok": True, "columns_added": ["duration_seconds", "records_processed"]}
    except Exception as exc:
        conn.rollback()
        logger.error("cron_log column migration failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def _run_reference_tables() -> dict[str, Any]:
    """Create reference tables for predict_permits and seed with initial data."""
    from src.db import get_connection, BACKEND  # type: ignore

    conn = get_connection()
    try:
        # Create tables (idempotent)
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ref_zoning_routing (
                        zoning_code TEXT PRIMARY KEY,
                        zoning_category TEXT,
                        planning_review_required BOOLEAN DEFAULT FALSE,
                        fire_review_required BOOLEAN DEFAULT FALSE,
                        health_review_required BOOLEAN DEFAULT FALSE,
                        historic_district BOOLEAN DEFAULT FALSE,
                        height_limit TEXT,
                        notes TEXT
                    );
                    CREATE TABLE IF NOT EXISTS ref_permit_forms (
                        id SERIAL PRIMARY KEY,
                        project_type TEXT NOT NULL,
                        permit_form TEXT NOT NULL,
                        review_path TEXT,
                        notes TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_ref_forms_type ON ref_permit_forms(project_type);
                    CREATE TABLE IF NOT EXISTS ref_agency_triggers (
                        id SERIAL PRIMARY KEY,
                        trigger_keyword TEXT NOT NULL,
                        agency TEXT NOT NULL,
                        reason TEXT,
                        adds_weeks INTEGER
                    );
                    CREATE INDEX IF NOT EXISTS idx_ref_triggers_keyword ON ref_agency_triggers(trigger_keyword);
                """)
            conn.commit()
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ref_zoning_routing (
                    zoning_code TEXT PRIMARY KEY,
                    zoning_category TEXT,
                    planning_review_required BOOLEAN DEFAULT FALSE,
                    fire_review_required BOOLEAN DEFAULT FALSE,
                    health_review_required BOOLEAN DEFAULT FALSE,
                    historic_district BOOLEAN DEFAULT FALSE,
                    height_limit TEXT,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ref_permit_forms (
                    id INTEGER PRIMARY KEY,
                    project_type TEXT NOT NULL,
                    permit_form TEXT NOT NULL,
                    review_path TEXT,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ref_agency_triggers (
                    id INTEGER PRIMARY KEY,
                    trigger_keyword TEXT NOT NULL,
                    agency TEXT NOT NULL,
                    reason TEXT,
                    adds_weeks INTEGER
                )
            """)
    except Exception as exc:
        logger.error("reference_tables table creation failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()

    # Seed with initial data
    from scripts.seed_reference_tables import seed_reference_tables  # type: ignore
    result = seed_reference_tables()
    if not result.get("ok"):
        return result
    return {
        "ok": True,
        "tables_created": ["ref_zoning_routing", "ref_permit_forms", "ref_agency_triggers"],
        "ref_zoning_routing": result["ref_zoning_routing"],
        "ref_permit_forms": result["ref_permit_forms"],
        "ref_agency_triggers": result["ref_agency_triggers"],
    }


def _run_shareable_analysis() -> dict[str, Any]:
    """Sprint 56D: analysis_sessions table, beta_requests table, users columns for three-tier signup."""
    from src.db import get_connection, BACKEND  # type: ignore

    conn = get_connection()
    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                # analysis_sessions table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_sessions (
                        id TEXT PRIMARY KEY,
                        user_id INTEGER REFERENCES users(user_id),
                        project_description TEXT NOT NULL,
                        address TEXT,
                        neighborhood TEXT,
                        estimated_cost DOUBLE PRECISION,
                        square_footage DOUBLE PRECISION,
                        results_json JSONB NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        shared_count INTEGER DEFAULT 0,
                        view_count INTEGER DEFAULT 0
                    );
                    CREATE INDEX IF NOT EXISTS idx_analysis_sessions_user ON analysis_sessions(user_id);
                    CREATE INDEX IF NOT EXISTS idx_analysis_sessions_created ON analysis_sessions(created_at);
                """)
                # beta_requests table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS beta_requests (
                        id SERIAL PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        name TEXT,
                        reason TEXT,
                        ip TEXT,
                        honeypot_filled BOOLEAN NOT NULL DEFAULT FALSE,
                        status TEXT NOT NULL DEFAULT 'pending',
                        admin_note TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        reviewed_at TIMESTAMPTZ,
                        approved_at TIMESTAMPTZ
                    );
                    CREATE INDEX IF NOT EXISTS idx_beta_requests_email ON beta_requests(email);
                    CREATE INDEX IF NOT EXISTS idx_beta_requests_status ON beta_requests(status);
                """)
                # users table: three-tier signup columns
                cur.execute("""
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_source TEXT DEFAULT 'invited';
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS detected_persona TEXT;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS beta_requested_at TIMESTAMPTZ;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS beta_approved_at TIMESTAMPTZ;
                """)
            conn.commit()
        else:
            # DuckDB — handled in init_user_schema via ALTER TABLE IF NOT EXISTS
            pass
        return {
            "ok": True,
            "tables_created": ["analysis_sessions", "beta_requests"],
            "columns_added": ["users.referral_source", "users.detected_persona",
                              "users.beta_requested_at", "users.beta_approved_at"],
        }
    except Exception as exc:
        if BACKEND == "postgres":
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error("shareable_analysis migration failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def _run_inspections_unique() -> dict[str, Any]:
    """Add UNIQUE constraint on inspections natural key after dedup.

    Steps:
    1. Skip if DuckDB (Postgres only)
    2. Deduplicate rows by (reference_number, scheduled_date, inspection_description),
       keeping the row with the lowest id
    3. Create UNIQUE index on the natural key using COALESCE for NULLable description
    """
    from src.db import get_connection, BACKEND  # type: ignore

    if BACKEND != "postgres":
        return {"ok": True, "skipped": True, "reason": "DuckDB mode — not needed"}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Count duplicates before dedup
            cur.execute("""
                SELECT COUNT(*) FROM inspections
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM inspections
                    GROUP BY reference_number, scheduled_date,
                             COALESCE(inspection_description, '')
                )
            """)
            dup_count = cur.fetchone()[0]

            if dup_count > 0:
                logger.info("Deduplicating %d duplicate inspection rows...", dup_count)
                cur.execute("""
                    DELETE FROM inspections
                    WHERE id NOT IN (
                        SELECT MIN(id)
                        FROM inspections
                        GROUP BY reference_number, scheduled_date,
                                 COALESCE(inspection_description, '')
                    )
                """)

            # Create UNIQUE index (idempotent — IF NOT EXISTS)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uk_inspections_natural
                ON inspections(reference_number, scheduled_date,
                               COALESCE(inspection_description, ''))
            """)

        conn.commit()
        return {
            "ok": True,
            "duplicates_removed": dup_count,
            "index": "uk_inspections_natural",
        }
    except Exception as exc:
        conn.rollback()
        logger.error("inspections_unique migration failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()

def _run_neighborhood_backfill() -> dict[str, Any]:
    """Backfill NULL neighborhoods on trade permits from tax_rolls.

    847K electrical + plumbing permits have neighborhood = NULL because the
    SODA ingest doesn't populate that field for trade permits. This migration
    joins against tax_rolls on block+lot to recover the neighborhood value.

    Idempotent: only updates rows where neighborhood IS NULL.
    """
    from src.db import get_connection, BACKEND  # type: ignore

    conn = get_connection()
    try:
        sql = """
            UPDATE permits SET neighborhood = t.neighborhood
            FROM tax_rolls t
            WHERE permits.block = t.block AND permits.lot = t.lot
              AND permits.neighborhood IS NULL
              AND t.neighborhood IS NOT NULL
        """
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.rowcount
            conn.commit()
        else:
            conn.execute(sql)
            rows_result = conn.execute("SELECT changes()").fetchone()
            rows = rows_result[0] if rows_result else 0
        return {"ok": True, "rows_updated": rows}
    except Exception as exc:
        if BACKEND == "postgres":
            conn.rollback()
        logger.error("neighborhood_backfill migration failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


# ---- ordered registry ------------------------------------------------

MIGRATIONS: list[Migration] = [
    Migration(
        name="schema",
        description="Bulk data tables: permits, contacts, entities, relationships, "
                    "inspections, timeline_stats (postgres_schema.sql)",
        run=_run_schema,
    ),
    Migration(
        name="user_tables",
        description="Core user tables: users, auth_tokens, watch_items (add_user_tables.sql)",
        run=_run_user_tables,
    ),
    Migration(
        name="activity_tables",
        description="Activity + feedback tables (add_activity_tables.sql)",
        run=_run_activity_tables,
    ),
    Migration(
        name="changes_table",
        description="Permit changes + cron_log table (add_changes_table.sql)",
        run=_run_changes_table,
    ),
    Migration(
        name="brief_email",
        description="Email brief columns on users (add_brief_email.sql)",
        run=_run_brief_email,
    ),
    Migration(
        name="invite_code",
        description="Invite code column on users (add_invite_code.sql)",
        run=_run_invite_code,
    ),
    Migration(
        name="signals",
        description="Signal tables: signal_types, permit_signals, property_signals, "
                    "property_health — seeds 13 signal types (migrate_signals.py)",
        run=_run_signals,
    ),
    Migration(
        name="cron_log_columns",
        description="Add duration_seconds and records_processed columns to cron_log",
        run=lambda: _run_cron_log_columns(),
    ),
    Migration(
        name="reference_tables",
        description="Reference tables for predict_permits: zoning routing, permit forms, agency triggers",
        run=_run_reference_tables,
    ),
    Migration(
        name="inspections_unique",
        description="Add UNIQUE constraint on inspections natural key after dedup",
        run=_run_inspections_unique,
    ),
    Migration(
        name="shareable_analysis",
        description="Sprint 56D: analysis_sessions table, beta_requests table, users three-tier columns",
        run=_run_shareable_analysis,
    ),
    Migration(
        name="neighborhood_backfill",
        description="Backfill NULL neighborhoods on trade permits from tax_rolls (block+lot join)",
        run=_run_neighborhood_backfill,
    ),
]

MIGRATION_BY_NAME: dict[str, Migration] = {m.name: m for m in MIGRATIONS}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_migrations(
    migrations: list[Migration],
    *,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Run the given migrations in order.

    Returns (succeeded, failed) counts.
    """
    succeeded = 0
    failed = 0

    for i, mig in enumerate(migrations, start=1):
        prefix = f"[{i}/{len(migrations)}] {mig.name}"
        if dry_run:
            logger.info("DRY-RUN %s — %s", prefix, mig.description)
            succeeded += 1
            continue

        logger.info("Running %s — %s", prefix, mig.description)
        t0 = time.monotonic()
        try:
            result = mig.run()
        except Exception as exc:
            logger.exception("Unhandled exception in migration %s", mig.name)
            result = {"ok": False, "error": str(exc)}

        elapsed = time.monotonic() - t0

        if result.get("ok"):
            if result.get("skipped"):
                logger.info("  SKIP %s (%.2fs): %s",
                            mig.name, elapsed, result.get("reason", ""))
            else:
                logger.info("  OK   %s (%.2fs): %s",
                            mig.name, elapsed,
                            {k: v for k, v in result.items() if k not in ("ok", "skipped")})
            succeeded += 1
        else:
            logger.error("  FAIL %s (%.2fs): %s", mig.name, elapsed,
                         result.get("error", "unknown error"))
            failed += 1

    return succeeded, failed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_all_migrations() -> dict:
    """Run all migrations programmatically. Returns a results dict for the /cron/migrate endpoint."""
    results = []
    for mig in MIGRATIONS:
        t0 = time.monotonic()
        try:
            result = mig.run()
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        elapsed = round(time.monotonic() - t0, 2)
        results.append({
            "name": mig.name,
            "ok": result.get("ok", False),
            "skipped": result.get("skipped", False),
            "elapsed_seconds": elapsed,
            **({k: v for k, v in result.items() if k not in ("ok", "skipped")}),
        })
    succeeded = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    return {
        "ok": failed == 0,
        "succeeded": succeeded,
        "failed": failed,
        "total": len(MIGRATIONS),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run sfpermits.ai production database migrations in order.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--list",
        action="store_true",
        help="Print all migrations and exit (no DB connection required)",
    )
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which migrations would run without executing them",
    )
    group.add_argument(
        "--only",
        metavar="NAME",
        help="Run only a single named migration (e.g. --only signals)",
    )
    args = parser.parse_args()

    # --list
    if args.list:
        print(f"{'#':<3} {'Name':<20} Description")
        print("-" * 72)
        for i, m in enumerate(MIGRATIONS, 1):
            print(f"{i:<3} {m.name:<20} {m.description}")
        return 0

    # --only
    if args.only:
        if args.only not in MIGRATION_BY_NAME:
            logger.error(
                "Unknown migration %r. Available: %s",
                args.only,
                ", ".join(MIGRATION_BY_NAME),
            )
            return 2
        to_run = [MIGRATION_BY_NAME[args.only]]
    else:
        to_run = MIGRATIONS

    # Verify we're not running against a database we can't reach when needed
    if not args.dry_run:
        try:
            from src.db import BACKEND  # type: ignore  # noqa: F401
        except ImportError as exc:
            logger.error("Cannot import src.db: %s — is the venv activated?", exc)
            return 2

    logger.info("sfpermits.ai migration runner — %d migration(s) to run", len(to_run))
    if args.dry_run:
        logger.info("DRY-RUN mode — no changes will be made")

    succeeded, failed = run_migrations(to_run, dry_run=args.dry_run)

    logger.info("Done: %d succeeded, %d failed", succeeded, failed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
