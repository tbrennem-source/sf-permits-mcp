"""Nightly delta fetch: detect permit & inspection changes via SODA API.

Queries SODA for permits whose status_date is more recent than our last run,
compares against current DB state, and inserts diffs into permit_changes.
Also refreshes recent inspections.

Resilience:
  - Tracks every run in cron_log (success/partial/failed)
  - Auto catch-up: if last success was >1 day ago, extends lookback to cover gap
  - Backfill source tagging: catch-up changes get source='backfill'

Usage:
    python -m scripts.nightly_changes                  # Normal run
    python -m scripts.nightly_changes --lookback 3     # Check last 3 days
    python -m scripts.nightly_changes --dry-run        # Preview only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_connection, BACKEND, query, query_one, execute_write, init_user_schema
from src.soda_client import SODAClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BUILDING_PERMITS_ENDPOINT = "i98e-djp9"
INSPECTIONS_ENDPOINT = "vckc-dh2h"
ADDENDA_ENDPOINT = "87xy-gk8d"
PAGE_SIZE = 10_000
MAX_LOOKBACK_DAYS = 30


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


def _parse_date(text: str | None) -> date | None:
    """Parse a TEXT date to a Python date."""
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except (ValueError, TypeError):
        return None


def _parse_float(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None


# ── cron_log table ───────────────────────────────────────────────

def ensure_cron_log_table() -> None:
    """Create cron_log and addenda_changes tables if they don't exist."""
    ph = _ph()
    if BACKEND == "postgres":
        execute_write("""
            CREATE TABLE IF NOT EXISTS cron_log (
                log_id      SERIAL PRIMARY KEY,
                job_type    TEXT NOT NULL,
                started_at  TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                status      TEXT NOT NULL DEFAULT 'running',
                lookback_days INTEGER,
                soda_records INTEGER,
                changes_inserted INTEGER,
                inspections_updated INTEGER,
                error_message TEXT,
                was_catchup BOOLEAN DEFAULT FALSE
            )
        """)
        # Ensure addenda_changes table exists for nightly addenda delta
        execute_write("""
            CREATE TABLE IF NOT EXISTS addenda_changes (
                change_id           SERIAL PRIMARY KEY,
                application_number  TEXT NOT NULL,
                change_date         DATE NOT NULL,
                detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                station             TEXT,
                addenda_number      INTEGER,
                step                INTEGER,
                plan_checked_by     TEXT,
                old_review_results  TEXT,
                new_review_results  TEXT,
                hold_description    TEXT,
                finish_date         TEXT,
                change_type         TEXT NOT NULL,
                source              TEXT NOT NULL DEFAULT 'nightly',
                department          TEXT,
                permit_type         TEXT,
                street_number       TEXT,
                street_name         TEXT,
                neighborhood        TEXT,
                block               TEXT,
                lot                 TEXT
            )
        """)
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_ac_date ON addenda_changes (change_date)",
            "CREATE INDEX IF NOT EXISTS idx_ac_app_num ON addenda_changes (application_number)",
            "CREATE INDEX IF NOT EXISTS idx_ac_station ON addenda_changes (station)",
        ]:
            try:
                execute_write(idx_sql)
            except Exception:
                pass
    else:
        init_user_schema()
        conn = get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cron_log (
                    log_id      INTEGER PRIMARY KEY,
                    job_type    TEXT NOT NULL,
                    started_at  TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    status      TEXT NOT NULL DEFAULT 'running',
                    lookback_days INTEGER,
                    soda_records INTEGER,
                    changes_inserted INTEGER,
                    inspections_updated INTEGER,
                    error_message TEXT,
                    was_catchup BOOLEAN DEFAULT FALSE
                )
            """)
        finally:
            conn.close()


def _log_cron_start(job_type: str, lookback_days: int, was_catchup: bool) -> int:
    """Insert a cron_log row for a starting run. Returns the log_id."""
    now = datetime.now(timezone.utc).isoformat()
    ph = _ph()
    if BACKEND == "postgres":
        row = execute_write(
            "INSERT INTO cron_log (job_type, started_at, lookback_days, was_catchup) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}) RETURNING log_id",
            (job_type, now, lookback_days, was_catchup),
            return_id=True,
        )
        return row
    else:
        rows = query("SELECT COALESCE(MAX(log_id), 0) FROM cron_log")
        log_id = (rows[0][0] if rows else 0) + 1
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO cron_log (log_id, job_type, started_at, lookback_days, was_catchup) "
                "VALUES (?, ?, ?, ?, ?)",
                (log_id, job_type, now, lookback_days, was_catchup),
            )
        finally:
            conn.close()
        return log_id


def _log_cron_finish(log_id: int, status: str, soda_records: int = 0,
                     changes_inserted: int = 0, inspections_updated: int = 0,
                     error_message: str | None = None) -> None:
    """Update a cron_log row with completion info."""
    now = datetime.now(timezone.utc).isoformat()
    ph = _ph()
    execute_write(
        f"UPDATE cron_log SET completed_at = {ph}, status = {ph}, "
        f"soda_records = {ph}, changes_inserted = {ph}, "
        f"inspections_updated = {ph}, error_message = {ph} "
        f"WHERE log_id = {ph}",
        (now, status, soda_records, changes_inserted,
         inspections_updated, error_message, log_id),
    )


def get_last_success(job_type: str = "nightly") -> datetime | None:
    """Get the started_at of the last successful cron run."""
    ph = _ph()
    row = query_one(
        "SELECT started_at FROM cron_log "
        f"WHERE job_type = {ph} AND status = 'success' "
        "ORDER BY started_at DESC LIMIT 1",
        (job_type,),
    )
    if row and row[0]:
        ts = row[0]
        if isinstance(ts, str):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return ts
    return None


def _compute_lookback(requested_days: int) -> tuple[int, bool]:
    """Determine actual lookback days, auto-extending to cover gaps.

    Returns (actual_lookback_days, was_catchup).
    """
    last = get_last_success("nightly")
    if last is None:
        # No previous success — use requested lookback
        return requested_days, False

    # How many days since last success?
    if isinstance(last, datetime):
        days_since = (datetime.now(timezone.utc) - last).days
    else:
        days_since = requested_days

    if days_since > requested_days:
        actual = min(days_since + 1, MAX_LOOKBACK_DAYS)  # +1 for safety overlap
        logger.info(
            "Gap detected: last success was %d days ago. "
            "Extending lookback from %d to %d days.",
            days_since, requested_days, actual,
        )
        return actual, True

    return requested_days, False


# ── SODA fetching ────────────────────────────────────────────────

async def fetch_recent_permits(client: SODAClient, since_date: str) -> list[dict]:
    """Fetch permits changed since `since_date` from SODA API."""
    all_records: list[dict] = []
    offset = 0
    while True:
        records = await client.query(
            endpoint_id=BUILDING_PERMITS_ENDPOINT,
            where=f"status_date > '{since_date}T00:00:00.000'",
            order="status_date DESC",
            limit=PAGE_SIZE,
            offset=offset,
        )
        if not records:
            break
        all_records.extend(records)
        if len(records) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return all_records


async def fetch_recent_inspections(client: SODAClient, since_date: str) -> list[dict]:
    """Fetch inspections scheduled since `since_date` from SODA API."""
    all_records: list[dict] = []
    offset = 0
    while True:
        records = await client.query(
            endpoint_id=INSPECTIONS_ENDPOINT,
            where=f"scheduled_date > '{since_date}T00:00:00.000'",
            order="scheduled_date DESC",
            limit=PAGE_SIZE,
            offset=offset,
        )
        if not records:
            break
        all_records.extend(records)
        if len(records) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return all_records


# ── Change detection ─────────────────────────────────────────────

def detect_changes(soda_records: list[dict], dry_run: bool = False,
                   source: str = "nightly") -> int:
    """Compare SODA records against DB and insert diffs into permit_changes."""
    if BACKEND == "duckdb":
        init_user_schema()

    ph = _ph()
    today = date.today()
    inserted = 0

    # For DuckDB manual IDs
    change_id_counter = 0
    if BACKEND == "duckdb":
        id_row = query("SELECT COALESCE(MAX(change_id), 0) FROM permit_changes")
        if id_row:
            change_id_counter = id_row[0][0]

    for record in soda_records:
        permit_number = record.get("permit_number")
        if not permit_number:
            continue

        new_status = record.get("status", "")
        new_status_date = record.get("status_date", "")

        # Lookup current state in our DB
        current = query_one(
            "SELECT status, status_date, permit_type_definition, "
            "street_number, street_name, neighborhood, block, lot "
            f"FROM permits WHERE permit_number = {ph}",
            (permit_number,),
        )

        if current is None:
            # New permit — not in our DB
            change_type = "new_permit"
            old_status = None
            old_status_date = None
            permit_type = record.get("permit_type_definition", "")
            street_number = record.get("street_number", "")
            street_name = (record.get("avs_street_name")
                           or record.get("street_name", ""))
            neighborhood = (record.get("analysis_neighborhood")
                            or record.get("neighborhoods_analysis_boundaries")
                            or record.get("neighborhood", ""))
            block_val = record.get("block", "")
            lot_val = record.get("lot", "")
            is_new = True
        else:
            (old_status_db, old_status_date_db, permit_type,
             street_number, street_name, neighborhood, block_val, lot_val) = current

            # Skip if status hasn't actually changed
            if old_status_db == new_status and old_status_date_db == new_status_date:
                continue

            change_type = "status_change"
            old_status = old_status_db
            old_status_date = old_status_date_db
            is_new = False

        if dry_run:
            action = "NEW" if is_new else f"{old_status} -> {new_status}"
            logger.info("  %s: %s (%s)", permit_number, action, new_status_date)
            inserted += 1
            continue

        change_id_counter += 1

        if BACKEND == "postgres":
            execute_write(
                "INSERT INTO permit_changes "
                "(permit_number, change_date, old_status, new_status, "
                "old_status_date, new_status_date, change_type, is_new_permit, "
                "source, permit_type, street_number, street_name, "
                "neighborhood, block, lot) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (permit_number, today, old_status, new_status,
                 old_status_date, new_status_date, change_type, is_new,
                 source, permit_type, street_number, street_name,
                 neighborhood, block_val, lot_val),
            )
        else:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO permit_changes "
                    "(change_id, permit_number, change_date, old_status, new_status, "
                    "old_status_date, new_status_date, change_type, is_new_permit, "
                    "source, permit_type, street_number, street_name, "
                    "neighborhood, block, lot) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (change_id_counter, permit_number, today, old_status, new_status,
                     old_status_date, new_status_date, change_type, is_new,
                     source, permit_type, street_number, street_name,
                     neighborhood, block_val, lot_val),
                )
            finally:
                conn.close()

        # Update or insert into permits table
        if is_new:
            _insert_new_permit(record)
        else:
            execute_write(
                f"UPDATE permits SET status = {ph}, status_date = {ph} "
                f"WHERE permit_number = {ph}",
                (new_status, new_status_date, permit_number),
            )

        inserted += 1

    return inserted


def _insert_new_permit(record: dict) -> None:
    """Insert a newly discovered permit into the permits table."""
    ph = _ph()
    cols = (
        "permit_number, permit_type, permit_type_definition, status, status_date, "
        "description, filed_date, issued_date, approved_date, completed_date, "
        "estimated_cost, revised_cost, existing_use, proposed_use, "
        "existing_units, proposed_units, "
        "street_number, street_name, street_suffix, zipcode, "
        "neighborhood, supervisor_district, block, lot, adu, data_as_of"
    )
    placeholders = ", ".join([ph] * 26)

    values = (
        record.get("permit_number", ""),
        record.get("permit_type"),
        record.get("permit_type_definition"),
        record.get("status"),
        record.get("status_date"),
        record.get("description"),
        record.get("filed_date"),
        record.get("issued_date"),
        record.get("approved_date"),
        record.get("completed_date"),
        _parse_float(record.get("estimated_cost")),
        _parse_float(record.get("revised_cost")),
        record.get("existing_use"),
        record.get("proposed_use"),
        _parse_int(record.get("existing_units")),
        _parse_int(record.get("proposed_units")),
        record.get("street_number"),
        record.get("street_name"),
        record.get("street_suffix"),
        record.get("zipcode"),
        (record.get("analysis_neighborhood")
         or record.get("neighborhoods_analysis_boundaries")
         or record.get("neighborhood", "")),
        record.get("supervisor_district"),
        record.get("block"),
        record.get("lot"),
        record.get("adu"),
        record.get("data_as_of"),
    )

    try:
        execute_write(
            f"INSERT INTO permits ({cols}) VALUES ({placeholders})",
            values,
        )
    except Exception:
        # May hit unique constraint if permit was added between our check and insert
        logger.debug("Permit %s already exists, skipping insert",
                     record.get("permit_number"))


# ── Inspection refresh ───────────────────────────────────────────

def upsert_inspections(soda_records: list[dict]) -> int:
    """Insert new or update existing inspections from SODA data."""
    ph = _ph()
    updated = 0

    for record in soda_records:
        ref_num = record.get("reference_number")
        sched_date = record.get("scheduled_date")
        insp_desc = record.get("inspection_description")
        if not ref_num or not sched_date:
            continue

        result = record.get("result")
        inspector = (record.get("inspector") or "").strip() or None

        # Check if this inspection already exists (by reference_number + scheduled_date + description)
        existing = query_one(
            f"SELECT id, result FROM inspections "
            f"WHERE reference_number = {ph} AND scheduled_date = {ph} "
            f"AND COALESCE(inspection_description, '') = COALESCE({ph}, '')"
            f" LIMIT 1",
            (ref_num, sched_date, insp_desc or ""),
        )

        if existing is None:
            # New inspection — insert
            if BACKEND == "postgres":
                execute_write(
                    "INSERT INTO inspections "
                    "(reference_number, reference_number_type, inspector, "
                    "scheduled_date, result, inspection_description, "
                    "block, lot, street_number, street_name, street_suffix, "
                    "neighborhood, supervisor_district, zipcode, data_as_of) "
                    f"VALUES ({', '.join([ph] * 15)})",
                    (ref_num,
                     record.get("reference_number_type"),
                     inspector,
                     sched_date,
                     result,
                     insp_desc,
                     record.get("block"),
                     record.get("lot"),
                     record.get("street_number"),
                     record.get("avs_street_name"),
                     record.get("avs_street_sfx"),
                     record.get("analysis_neighborhood"),
                     record.get("supervisor_district"),
                     record.get("zip_code"),
                     record.get("data_as_of")),
                )
            else:
                # DuckDB needs explicit id
                id_row = query("SELECT COALESCE(MAX(id), 0) FROM inspections")
                new_id = (id_row[0][0] if id_row else 0) + 1
                conn = get_connection()
                try:
                    conn.execute(
                        "INSERT INTO inspections VALUES "
                        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (new_id, ref_num,
                         record.get("reference_number_type"),
                         inspector, sched_date, result, insp_desc,
                         record.get("block"), record.get("lot"),
                         record.get("street_number"),
                         record.get("avs_street_name"),
                         record.get("avs_street_sfx"),
                         record.get("analysis_neighborhood"),
                         record.get("supervisor_district"),
                         record.get("zip_code"),
                         record.get("data_as_of")),
                    )
                finally:
                    conn.close()
            updated += 1
        elif existing[1] != result:
            # Result changed — update
            execute_write(
                f"UPDATE inspections SET result = {ph}, data_as_of = {ph} "
                f"WHERE id = {ph}",
                (result, record.get("data_as_of"), existing[0]),
            )
            updated += 1

    return updated


# ── Addenda delta ────────────────────────────────────────────────

async def fetch_recent_addenda(client: SODAClient, since_date: str) -> list[dict]:
    """Fetch addenda routing steps changed since `since_date` from SODA API.

    Queries for rows where finish_date or arrive recently updated, which
    catches both new routing assignments and completed reviews.
    """
    all_records: list[dict] = []
    offset = 0
    while True:
        records = await client.query(
            endpoint_id=ADDENDA_ENDPOINT,
            where=(
                f"finish_date > '{since_date}T00:00:00.000' "
                f"OR arrive > '{since_date}T00:00:00.000'"
            ),
            order=":id",
            limit=PAGE_SIZE,
            offset=offset,
        )
        if not records:
            break
        all_records.extend(records)
        if len(records) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return all_records


def detect_addenda_changes(soda_records: list[dict], dry_run: bool = False,
                           source: str = "nightly") -> int:
    """Compare SODA addenda records against DB and insert diffs into addenda_changes."""
    ph = _ph()
    today = date.today()
    inserted = 0

    # For DuckDB manual IDs
    change_id_counter = 0
    if BACKEND == "duckdb":
        try:
            id_row = query("SELECT COALESCE(MAX(change_id), 0) FROM addenda_changes")
            if id_row:
                change_id_counter = id_row[0][0]
        except Exception:
            change_id_counter = 0

    for record in soda_records:
        app_num = record.get("application_number")
        if not app_num:
            continue

        soda_pk = record.get("primary_key")
        new_review_results = (record.get("review_results") or "").strip() or None
        finish_date = record.get("finish_date")
        station = (record.get("station") or "").strip() or None
        addenda_number = _parse_int(record.get("addenda_number"))
        step_val = _parse_int(record.get("step"))
        reviewer = (record.get("plan_checked_by") or "").strip() or None
        hold_desc = (record.get("hold_description") or "").strip() or None
        department = (record.get("department") or "").strip() or None

        # Check if we already have this exact row in addenda table
        try:
            existing = query_one(
                f"SELECT review_results, finish_date FROM addenda "
                f"WHERE primary_key = {ph} LIMIT 1",
                (soda_pk,),
            )
        except Exception:
            existing = None

        if existing is None:
            change_type = "new_routing"
            old_review = None
        else:
            old_review = existing[0]
            old_finish = existing[1]
            # Skip if nothing meaningful changed
            if old_review == new_review_results and old_finish == finish_date:
                continue
            if new_review_results and not old_review:
                change_type = "review_completed"
            elif new_review_results != old_review:
                change_type = "review_updated"
            else:
                change_type = "routing_updated"

        # Denormalize permit info for fast brief queries
        try:
            permit_info = query_one(
                f"SELECT permit_type_definition, street_number, street_name, "
                f"neighborhood, block, lot "
                f"FROM permits WHERE permit_number = {ph}",
                (app_num,),
            )
        except Exception:
            permit_info = None
        if permit_info:
            permit_type, street_number, street_name, neighborhood, block_val, lot_val = permit_info
        else:
            permit_type = street_number = street_name = neighborhood = block_val = lot_val = None

        if dry_run:
            logger.info("  %s: %s at %s (%s)", app_num, change_type, station, new_review_results)
            inserted += 1
            continue

        change_id_counter += 1

        # Insert change record
        if BACKEND == "postgres":
            execute_write(
                "INSERT INTO addenda_changes "
                "(application_number, change_date, station, addenda_number, step, "
                "plan_checked_by, old_review_results, new_review_results, "
                "hold_description, finish_date, change_type, source, department, "
                "permit_type, street_number, street_name, neighborhood, block, lot) "
                f"VALUES ({', '.join(['%s'] * 19)})",
                (app_num, today, station, addenda_number, step_val,
                 reviewer, old_review, new_review_results,
                 hold_desc, finish_date, change_type, source, department,
                 permit_type, street_number, street_name, neighborhood, block_val, lot_val),
            )
        else:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO addenda_changes "
                    "(change_id, application_number, change_date, station, addenda_number, step, "
                    "plan_checked_by, old_review_results, new_review_results, "
                    "hold_description, finish_date, change_type, source, department, "
                    "permit_type, street_number, street_name, neighborhood, block, lot) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (change_id_counter, app_num, today, station, addenda_number, step_val,
                     reviewer, old_review, new_review_results,
                     hold_desc, finish_date, change_type, source, department,
                     permit_type, street_number, street_name, neighborhood, block_val, lot_val),
                )
            finally:
                conn.close()

        # Upsert into addenda table (keep local state current)
        _upsert_addenda_row(record, soda_pk)

        inserted += 1

    return inserted


def _upsert_addenda_row(record: dict, soda_pk: str) -> None:
    """Insert or update a single addenda row from SODA data."""
    ph = _ph()
    try:
        existing = query_one(
            f"SELECT id FROM addenda WHERE primary_key = {ph}",
            (soda_pk,),
        )
    except Exception:
        # addenda table may not exist yet in some environments
        return

    if existing:
        execute_write(
            f"UPDATE addenda SET review_results = {ph}, finish_date = {ph}, "
            f"plan_checked_by = {ph}, hold_description = {ph}, "
            f"addenda_status = {ph}, data_as_of = {ph} "
            f"WHERE primary_key = {ph}",
            (
                (record.get("review_results") or "").strip() or None,
                record.get("finish_date"),
                (record.get("plan_checked_by") or "").strip() or None,
                (record.get("hold_description") or "").strip() or None,
                (record.get("addenda_status") or "").strip() or None,
                record.get("data_as_of"),
                soda_pk,
            ),
        )
    else:
        # New row — insert
        if BACKEND == "postgres":
            execute_write(
                "INSERT INTO addenda (primary_key, application_number, addenda_number, "
                "step, station, arrive, assign_date, start_date, finish_date, "
                "approved_date, plan_checked_by, review_results, hold_description, "
                "addenda_status, department, title, data_as_of) "
                f"VALUES ({', '.join(['%s'] * 17)})",
                (
                    record.get("primary_key"),
                    record.get("application_number", ""),
                    _parse_int(record.get("addenda_number")),
                    _parse_int(record.get("step")),
                    (record.get("station") or "").strip() or None,
                    record.get("arrive"),
                    record.get("assign_date"),
                    record.get("start_date"),
                    record.get("finish_date"),
                    record.get("approved_date"),
                    (record.get("plan_checked_by") or "").strip() or None,
                    (record.get("review_results") or "").strip() or None,
                    (record.get("hold_description") or "").strip() or None,
                    (record.get("addenda_status") or "").strip() or None,
                    (record.get("department") or "").strip() or None,
                    (record.get("title") or "").strip() or None,
                    record.get("data_as_of"),
                ),
            )
        else:
            try:
                id_row = query("SELECT COALESCE(MAX(id), 0) FROM addenda")
                new_id = (id_row[0][0] if id_row else 0) + 1
            except Exception:
                return
            conn = get_connection()
            try:
                from src.ingest import _normalize_addenda
                row = _normalize_addenda(record, new_id)
                conn.execute(
                    "INSERT INTO addenda VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )
            finally:
                conn.close()


# ── Main entry point ─────────────────────────────────────────────

async def run_nightly(lookback_days: int = 1, dry_run: bool = False) -> dict:
    """Main entry point for nightly delta fetch.

    Auto-detects gaps since last successful run and extends lookback
    to cover missed days (up to MAX_LOOKBACK_DAYS).
    """
    ensure_cron_log_table()

    # Auto catch-up: extend lookback if we missed days
    actual_lookback, was_catchup = _compute_lookback(lookback_days)
    source = "backfill" if was_catchup else "nightly"

    since = date.today() - timedelta(days=actual_lookback)
    since_str = since.isoformat()

    # Log the start
    log_id = _log_cron_start("nightly", actual_lookback, was_catchup)

    logger.info(
        "Fetching permits changed since %s (lookback=%d days%s)",
        since_str, actual_lookback,
        ", CATCH-UP" if was_catchup else "",
    )

    try:
        client = SODAClient()
        try:
            # Fetch permits
            permit_records = await fetch_recent_permits(client, since_str)
            logger.info("SODA returned %d permit records", len(permit_records))

            # Fetch inspections
            inspection_records = await fetch_recent_inspections(client, since_str)
            logger.info("SODA returned %d inspection records", len(inspection_records))

            # Fetch addenda routing
            addenda_records = await fetch_recent_addenda(client, since_str)
            logger.info("SODA returned %d addenda records", len(addenda_records))
        finally:
            await client.close()

        if dry_run:
            logger.info("DRY RUN — previewing changes:")

        # Detect and record permit changes
        changes_inserted = detect_changes(
            permit_records, dry_run=dry_run, source=source,
        )

        # Upsert inspections
        inspections_updated = 0
        if not dry_run:
            inspections_updated = upsert_inspections(inspection_records)

        # Detect and record addenda routing changes
        addenda_inserted = 0
        try:
            addenda_inserted = detect_addenda_changes(
                addenda_records, dry_run=dry_run, source=source,
            )
        except Exception as e:
            logger.warning("Addenda change detection failed (non-fatal): %s", e)

        total_soda = len(permit_records) + len(inspection_records) + len(addenda_records)

        logger.info(
            "%s: %d permit changes, %d inspections, %d addenda changes %s from %d SODA records",
            "DRY RUN" if dry_run else "DONE",
            changes_inserted,
            inspections_updated,
            addenda_inserted,
            "detected" if dry_run else "inserted",
            total_soda,
        )

        # Staleness check: flag when SODA returns 0 records for a data source
        # On a normal weekday SF typically has dozens of permit updates.
        # Zero records may indicate a SODA API issue, schema change, or outage.
        staleness_warnings: list[str] = []
        if len(permit_records) == 0:
            staleness_warnings.append(
                "SODA returned 0 permits — possible API issue or data lag"
            )
        if len(inspection_records) == 0:
            staleness_warnings.append(
                "SODA returned 0 inspections — possible API issue or data lag"
            )
        if len(addenda_records) == 0 and actual_lookback <= 2:
            # Addenda can legitimately be 0 on quiet days, only warn
            # if single-day lookback returns nothing
            staleness_warnings.append(
                "SODA returned 0 addenda records"
            )
        if total_soda == 0:
            staleness_warnings.append(
                "ALL sources returned 0 records — SODA may be down or unreachable"
            )

        for warning in staleness_warnings:
            logger.warning("STALENESS CHECK: %s (since=%s, lookback=%d)",
                           warning, since_str, actual_lookback)

        # Log success
        if not dry_run:
            _log_cron_finish(
                log_id, "success",
                soda_records=total_soda,
                changes_inserted=changes_inserted,
                inspections_updated=inspections_updated,
            )

        return {
            "since": since_str,
            "lookback_days": actual_lookback,
            "was_catchup": was_catchup,
            "soda_permits": len(permit_records),
            "soda_inspections": len(inspection_records),
            "soda_addenda": len(addenda_records),
            "changes_inserted": changes_inserted,
            "inspections_updated": inspections_updated,
            "addenda_inserted": addenda_inserted,
            "dry_run": dry_run,
            "staleness_warnings": staleness_warnings,
        }

    except Exception as e:
        logger.exception("Nightly run failed")
        _log_cron_finish(log_id, "failed", error_message=str(e))
        raise


def main():
    parser = argparse.ArgumentParser(description="Nightly permit change detection")
    parser.add_argument("--lookback", type=int, default=1, help="Days to look back (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    args = parser.parse_args()

    result = asyncio.run(run_nightly(lookback_days=args.lookback, dry_run=args.dry_run))
    logger.info("Result: %s", result)


if __name__ == "__main__":
    main()
