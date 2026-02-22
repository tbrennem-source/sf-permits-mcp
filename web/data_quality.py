"""Data quality checks for the Admin Ops hub.

Runs 10 live checks against the database and returns traffic-light
results (green/yellow/red) for display in the Data Quality tab.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from src.db import query as _raw_query

logger = logging.getLogger(__name__)

# Per-query timeout (seconds) for DQ checks.  Prevents a single
# slow analytical query (e.g. orphaned-contacts LEFT JOIN across 1.8M×1.1M)
# from blocking the entire tab load.
_DQ_QUERY_TIMEOUT_S = 10


def _ph():
    """Return the correct placeholder for the current DB engine."""
    from src.db import _placeholder
    return _placeholder()


def _timed_query(sql: str, params=None) -> list:
    """Run a query with a per-statement PostgreSQL timeout.

    On Postgres, wraps the query with ``SET LOCAL statement_timeout``
    so the DB kills it if it exceeds the limit.  On DuckDB, passes through.
    """
    from src.db import BACKEND, get_connection
    if BACKEND != "postgres":
        return _raw_query(sql, params)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL statement_timeout = '{_DQ_QUERY_TIMEOUT_S * 1000}'")
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def run_all_checks() -> list[dict]:
    """Run all data quality checks and return results.

    Each result dict has:
        name, category, value, unit, status (green|yellow|red), detail

    Results are sorted: red first, then yellow, then green.
    Checks that require prod-only tables (cron_log, permit_changes, etc.)
    are skipped gracefully on DuckDB.
    """
    from src.db import BACKEND

    # Checks that require prod-only tables (cron_log, permit_changes, knowledge_chunks)
    prod_only_checks = [
        _check_cron_status,
        _check_records_fetched,
        _check_permit_changes_detected,
        _check_rag_chunk_count,
        _check_entity_coverage,
    ]
    # Checks that work on both backends
    universal_checks = [
        _check_temporal_violations,
        _check_cost_outliers,
        _check_orphaned_contacts,
        _check_inspection_null_rate,
        _check_data_freshness,
    ]

    if BACKEND == "postgres":
        checks = prod_only_checks + universal_checks
    else:
        checks = universal_checks

    results = []
    for check_fn in checks:
        try:
            result = check_fn()
            if result:
                results.append(result)
        except Exception as exc:
            exc_str = str(exc).lower()
            is_timeout = "cancel" in exc_str or "timeout" in exc_str
            logger.debug("DQ check %s failed%s", check_fn.__name__,
                         " (timeout)" if is_timeout else "", exc_info=True)
            results.append({
                "name": check_fn.__name__.replace("_check_", "").replace("_", " ").title(),
                "category": "system",
                "value": "Timeout" if is_timeout else "Error",
                "unit": f">{_DQ_QUERY_TIMEOUT_S}s" if is_timeout else "",
                "status": "yellow" if is_timeout else "red",
                "detail": f"Query exceeded {_DQ_QUERY_TIMEOUT_S}s limit" if is_timeout else "Check failed — see logs",
            })

    # Sort: red first, then yellow, then green
    status_order = {"red": 0, "yellow": 1, "green": 2}
    results.sort(key=lambda r: status_order.get(r.get("status", "green"), 9))
    return results


# ── Prod-only checks (small tables, use _raw_query) ──────────────


def _check_cron_status() -> dict:
    """Check when the last successful nightly cron ran."""
    ph = _ph()
    rows = _raw_query(
        f"SELECT MAX(started_at) FROM cron_log "
        f"WHERE job_type = 'nightly' AND status = {ph}",
        ("success",),
    )
    if not rows or not rows[0][0]:
        return {
            "name": "Nightly Cron",
            "category": "pipeline",
            "value": "Never",
            "unit": "",
            "status": "red",
            "detail": "No successful cron runs found in cron_log",
        }
    last_run = rows[0][0]
    if isinstance(last_run, str):
        last_run = date.fromisoformat(last_run[:10])
    elif hasattr(last_run, "date"):
        last_run = last_run.date()
    days_ago = (date.today() - last_run).days
    status = "green" if days_ago <= 1 else ("yellow" if days_ago <= 3 else "red")
    return {
        "name": "Nightly Cron",
        "category": "pipeline",
        "value": str(last_run),
        "unit": f"{days_ago}d ago",
        "status": status,
        "detail": f"Last successful cron: {last_run} ({days_ago} days ago)",
    }


def _check_records_fetched() -> dict:
    """Check how many records the last cron run fetched."""
    ph = _ph()
    rows = _raw_query(
        f"SELECT soda_records, started_at FROM cron_log "
        f"WHERE job_type = 'nightly' AND status = {ph} "
        f"ORDER BY started_at DESC LIMIT 1",
        ("success",),
    )
    if not rows:
        return {
            "name": "Records Fetched",
            "category": "pipeline",
            "value": "N/A",
            "unit": "",
            "status": "yellow",
            "detail": "No cron_log entries found",
        }
    count = rows[0][0] or 0
    started = rows[0][1]
    run_date = started.date() if hasattr(started, "date") else started
    status = "green" if count > 0 else "red"
    return {
        "name": "Records Fetched",
        "category": "pipeline",
        "value": f"{count:,}",
        "unit": "records",
        "status": status,
        "detail": f"Last run ({run_date}) fetched {count:,} records",
    }


def _check_permit_changes_detected() -> dict:
    """Count permit changes detected in last 7 days."""
    cutoff = date.today() - timedelta(days=7)
    ph = _ph()
    rows = _raw_query(
        f"SELECT COUNT(*) FROM permit_changes WHERE detected_at >= {ph}",
        (str(cutoff),),
    )
    count = rows[0][0] if rows else 0
    status = "green" if count > 0 else ("yellow" if count == 0 else "red")
    return {
        "name": "Changes Detected (7d)",
        "category": "pipeline",
        "value": f"{count:,}",
        "unit": "changes",
        "status": status,
        "detail": f"{count} permit status changes detected since {cutoff}",
    }


def _check_rag_chunk_count() -> dict:
    """Check RAG knowledge_chunks count vs baseline.

    Baseline: ~1,012 official (tier1-4) + ops chunks (variable).
    Flags both under-count (data loss) AND over-count (duplicate accumulation).
    """
    rows = _raw_query("SELECT COUNT(*) FROM knowledge_chunks", ())
    count = rows[0][0] if rows else 0
    # Check for duplicates by comparing distinct vs total
    dup_rows = _raw_query(
        "SELECT COUNT(*) FROM ("
        "  SELECT DISTINCT source_file, source_section, chunk_index "
        "  FROM knowledge_chunks"
        ") sub",
        (),
    )
    distinct = dup_rows[0][0] if dup_rows else count
    duplicates = count - distinct
    baseline = 1100  # ~1,012 official + ~80-100 ops chunks
    pct_of_baseline = round(count / max(baseline, 1) * 100)
    if duplicates > 50:
        status = "red"
        detail = f"{count:,} chunks but only {distinct:,} unique — {duplicates:,} duplicates detected!"
    elif pct_of_baseline < 70:
        status = "red"
        detail = f"{count:,} chunks ({pct_of_baseline}% of baseline {baseline:,}) — data loss?"
    elif pct_of_baseline < 90:
        status = "yellow"
        detail = f"{count:,} chunks ({pct_of_baseline}% of baseline {baseline:,})"
    elif pct_of_baseline > 200:
        status = "yellow"
        detail = f"{count:,} chunks ({pct_of_baseline}% of baseline) — possible accumulation"
    else:
        status = "green"
        detail = f"{count:,} chunks ({pct_of_baseline}% of baseline {baseline:,})"
    return {
        "name": "RAG Chunks",
        "category": "completeness",
        "value": f"{count:,}",
        "unit": f"({distinct:,} unique)" if duplicates > 0 else f"(baseline: {baseline:,})",
        "status": status,
        "detail": detail,
    }


def _check_entity_coverage() -> dict:
    """Check entity resolution coverage (entities vs contacts)."""
    contact_rows = _timed_query("SELECT COUNT(*) FROM contacts", ())
    entity_rows = _timed_query("SELECT COUNT(*) FROM entities", ())
    contacts = contact_rows[0][0] if contact_rows else 0
    entities = entity_rows[0][0] if entity_rows else 0
    if contacts == 0:
        ratio = 0
    else:
        ratio = round(entities / contacts * 100, 1)
    # Expect ~55-60% compression (1.8M contacts -> 1M entities)
    status = "green" if 40 <= ratio <= 70 else ("yellow" if 30 <= ratio <= 80 else "red")
    return {
        "name": "Entity Resolution",
        "category": "completeness",
        "value": f"{ratio}%",
        "unit": f"({entities:,} entities from {contacts:,} contacts)",
        "status": status,
        "detail": f"{entities:,} entities resolved from {contacts:,} contacts ({ratio}% ratio)",
    }


# ── Universal checks (big tables, use _timed_query) ──────────────


def _check_temporal_violations() -> dict:
    """Count permits where filed_date > issued_date (temporal anomaly).

    Known: SF DBI records filed_date after issued_date for permit amendments
    and OTC permits.  ~0.2% is normal for this dataset.
    """
    rows = _timed_query(
        "SELECT COUNT(*) FROM permits "
        "WHERE filed_date IS NOT NULL AND issued_date IS NOT NULL "
        "AND filed_date > issued_date",
        (),
    )
    count = rows[0][0] if rows else 0
    total_rows = _timed_query("SELECT COUNT(*) FROM permits", ())
    total = total_rows[0][0] if total_rows else 1
    pct = round(count / max(total, 1) * 100, 2)
    # <0.5% is normal for SODA data; >1% suggests a load problem
    status = "green" if pct < 0.5 else ("yellow" if pct < 1 else "red")
    return {
        "name": "Temporal Violations",
        "category": "anomaly",
        "value": f"{pct}%",
        "unit": f"({count:,} of {total:,})",
        "status": status,
        "detail": f"{count:,} permits with filed_date after issued_date ({pct}%)",
    }


def _check_cost_outliers() -> dict:
    """Count permits with estimated cost > $500M (likely data errors)."""
    rows = _timed_query(
        "SELECT COUNT(*) FROM permits "
        "WHERE (revised_cost > 500000000 OR estimated_cost > 500000000) "
        "AND permit_type_definition NOT ILIKE '%new construction%'",
        (),
    )
    count = rows[0][0] if rows else 0
    status = "green" if count == 0 else ("yellow" if count < 5 else "red")
    return {
        "name": "Cost Outliers (>$500M)",
        "category": "anomaly",
        "value": f"{count:,}",
        "unit": "permits",
        "status": status,
        "detail": f"{count} non-new-construction permits with cost > $500M",
    }


def _check_orphaned_contacts() -> dict:
    """Count contacts without matching permits.

    Known: contacts dataset (1.8M) covers a broader date range than the
    permits dataset (1.1M), so ~40-50% orphan rate is expected.

    Uses NOT EXISTS instead of LEFT JOIN for better performance on large tables.
    """
    rows = _timed_query(
        "SELECT COUNT(*) FROM contacts c "
        "WHERE NOT EXISTS (SELECT 1 FROM permits p WHERE p.permit_number = c.permit_number)",
        (),
    )
    count = rows[0][0] if rows else 0
    total_contacts = _timed_query("SELECT COUNT(*) FROM contacts", ())
    total = total_contacts[0][0] if total_contacts else 1
    pct = round(count / max(total, 1) * 100, 1)
    # 40-50% is expected (contacts covers broader date range than permits).
    # >60% suggests a permits table load gap.
    status = "green" if pct < 55 else ("yellow" if pct < 65 else "red")
    return {
        "name": "Orphaned Contacts",
        "category": "anomaly",
        "value": f"{pct}%",
        "unit": f"({count:,} of {total:,})",
        "status": status,
        "detail": f"{count:,} contacts reference permits not in permits table ({pct}%)",
    }


def _check_inspection_null_rate() -> dict:
    """Check what percentage of inspections have null results."""
    rows = _timed_query(
        "SELECT COUNT(*) FROM inspections WHERE inspection_type_desc IS NULL OR inspection_type_desc = ''",
        (),
    )
    null_count = rows[0][0] if rows else 0
    total_rows = _timed_query("SELECT COUNT(*) FROM inspections", ())
    total = total_rows[0][0] if total_rows else 1
    pct = round(null_count / max(total, 1) * 100, 1)
    status = "green" if pct < 5 else ("yellow" if pct < 20 else "red")
    return {
        "name": "Inspection Null Rate",
        "category": "completeness",
        "value": f"{pct}%",
        "unit": f"({null_count:,} of {total:,})",
        "status": status,
        "detail": f"{null_count:,} inspections missing type description ({pct}%)",
    }


def _check_data_freshness() -> dict:
    """Check age of most recent permit status_date."""
    rows = _timed_query(
        "SELECT MAX(status_date) FROM permits WHERE status_date IS NOT NULL",
        (),
    )
    if not rows or not rows[0][0]:
        return {
            "name": "Data Freshness",
            "category": "pipeline",
            "value": "Unknown",
            "unit": "",
            "status": "red",
            "detail": "No status_date values found in permits table",
        }
    max_date = rows[0][0]
    if isinstance(max_date, str):
        max_date = date.fromisoformat(max_date[:10])
    days_old = (date.today() - max_date).days
    status = "green" if days_old <= 2 else ("yellow" if days_old <= 7 else "red")
    return {
        "name": "Data Freshness",
        "category": "pipeline",
        "value": str(max_date),
        "unit": f"{days_old}d old",
        "status": status,
        "detail": f"Most recent permit status_date: {max_date} ({days_old} days old)",
    }
