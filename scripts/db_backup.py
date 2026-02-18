"""Database backup utility — pg_dump with retention management.

Supports two modes:
1. **Cron endpoint**: Called from /cron/backup on Railway, dumps user-data
   tables (users, auth_tokens, watch_items, feedback, activity_log,
   points_ledger, regulatory_watch, cron_log) to a local timestamped file.
2. **CLI**: Run directly for a full or selective pg_dump.

Usage:
    python -m scripts.db_backup                  # Full backup
    python -m scripts.db_backup --tables users   # Single table
    python -m scripts.db_backup --stdout          # Dump to stdout (pipe to file/S3)

Retention: keeps the last 7 daily backups by default (configurable via
BACKUP_RETENTION_DAYS env var). Older files are pruned automatically.

Requires: DATABASE_URL env var pointing to PostgreSQL.
pg_dump must be available on PATH (included in Railway's Postgres image,
or install locally via `brew install libpq`).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Tables containing user-generated data worth backing up.
# Permit data (permits, contacts, entities, relationships, inspections)
# is recoverable from SODA API via `python -m src.ingest`.
USER_DATA_TABLES = [
    "users",
    "auth_tokens",
    "watch_items",
    "feedback",
    "activity_log",
    "points_ledger",
    "regulatory_watch",
    "cron_log",
    "permit_changes",
    "plan_analysis_sessions",
    "plan_analysis_jobs",
    # plan_analysis_images excluded — large binary blobs, recoverable
]

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "7"))


def run_backup(
    *,
    tables: list[str] | None = None,
    to_stdout: bool = False,
    full: bool = False,
) -> dict:
    """Run pg_dump and return metadata dict.

    Args:
        tables: Specific tables to dump. None = USER_DATA_TABLES.
        to_stdout: Print SQL to stdout instead of writing a file.
        full: Dump the entire database (ignore tables list).

    Returns:
        {"ok": True, "file": "...", "size_kb": ..., "tables": [...]}
        or {"ok": False, "error": "..."} on failure.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target_tables = [] if full else (tables or USER_DATA_TABLES)

    # Build pg_dump command
    cmd = ["pg_dump", database_url, "--no-owner", "--no-privileges"]

    if not full:
        for t in target_tables:
            cmd.extend(["-t", t])

    # Use custom format for file output (supports pg_restore), plain SQL for stdout
    if to_stdout:
        cmd.extend(["--format=plain"])
    else:
        cmd.extend(["--format=custom"])

    if to_stdout:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                return {"ok": False, "error": result.stderr.strip()}
            sys.stdout.write(result.stdout)
            return {"ok": True, "mode": "stdout", "tables": target_tables}
        except FileNotFoundError:
            return {"ok": False, "error": "pg_dump not found on PATH"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "pg_dump timed out (300s)"}

    # File output
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "full" if full else "userdata"
    filename = f"backup-{suffix}-{timestamp}.dump"
    filepath = BACKUP_DIR / filename

    try:
        with open(filepath, "wb") as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=300)
        if result.returncode != 0:
            filepath.unlink(missing_ok=True)
            return {"ok": False, "error": result.stderr.decode().strip()}
    except FileNotFoundError:
        return {"ok": False, "error": "pg_dump not found on PATH"}
    except subprocess.TimeoutExpired:
        filepath.unlink(missing_ok=True)
        return {"ok": False, "error": "pg_dump timed out (300s)"}

    size_kb = filepath.stat().st_size // 1024
    logger.info("Backup written: %s (%d KB)", filename, size_kb)

    # Prune old backups
    pruned = _prune_old_backups()

    return {
        "ok": True,
        "file": filename,
        "path": str(filepath),
        "size_kb": size_kb,
        "tables": target_tables or ["(full database)"],
        "pruned": pruned,
    }


def _prune_old_backups() -> int:
    """Remove backup files older than RETENTION_DAYS. Returns count removed."""
    if not BACKUP_DIR.exists():
        return 0
    cutoff = datetime.now(timezone.utc).timestamp() - (RETENTION_DAYS * 86400)
    pruned = 0
    for f in BACKUP_DIR.glob("backup-*.dump"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            pruned += 1
            logger.info("Pruned old backup: %s", f.name)
    return pruned


def restore_backup(filepath: str) -> dict:
    """Restore a backup file using pg_restore.

    Args:
        filepath: Path to the .dump file.

    Returns:
        {"ok": True} or {"ok": False, "error": "..."}.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    cmd = [
        "pg_restore", "--dbname", database_url,
        "--no-owner", "--no-privileges",
        "--clean", "--if-exists",
        filepath,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        # pg_restore returns non-zero for warnings too, check stderr
        if result.returncode != 0 and "ERROR" in result.stderr:
            return {"ok": False, "error": result.stderr.strip()}
        return {"ok": True, "file": filepath}
    except FileNotFoundError:
        return {"ok": False, "error": "pg_restore not found on PATH"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "pg_restore timed out (600s)"}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Backup PostgreSQL database")
    parser.add_argument("--tables", nargs="*", help="Specific tables to dump")
    parser.add_argument("--full", action="store_true", help="Dump entire database")
    parser.add_argument("--stdout", action="store_true", help="Output SQL to stdout")
    parser.add_argument("--restore", type=str, help="Restore from a .dump file")
    parser.add_argument("--list", action="store_true", help="List existing backups")
    args = parser.parse_args()

    if args.list:
        if not BACKUP_DIR.exists():
            print("No backups directory found.")
            sys.exit(0)
        backups = sorted(BACKUP_DIR.glob("backup-*.dump"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not backups:
            print("No backup files found.")
        for f in backups:
            size = f.stat().st_size / 1024
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  {f.name}  ({size:.0f} KB)  {mtime}")
        sys.exit(0)

    if args.restore:
        result = restore_backup(args.restore)
        if result["ok"]:
            print(f"Restored from {args.restore}")
        else:
            print(f"Restore failed: {result['error']}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    result = run_backup(tables=args.tables, to_stdout=args.stdout, full=args.full)
    if result["ok"]:
        if not args.stdout:
            print(f"Backup complete: {result.get('file', 'stdout')}")
            print(f"  Size: {result.get('size_kb', '?')} KB")
            print(f"  Tables: {', '.join(result.get('tables', []))}")
            if result.get("pruned"):
                print(f"  Pruned {result['pruned']} old backup(s)")
    else:
        print(f"Backup failed: {result['error']}", file=sys.stderr)
        sys.exit(1)
