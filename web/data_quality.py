"""Data quality checks for the Admin Ops hub.

Runs 10 live checks against the database and returns traffic-light
results (green/yellow/red) for display in the Data Quality tab.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from src.db import query

logger = logging.getLogger(__name__)


def _ph():
    """Return the correct placeholder for the current DB engine."""
    from src.db import _placeholder
    return _placeholder()


def run_all_checks() -> list[dict]:
    """Run all data quality checks and return results.

    Each result dict has:
        name, category, value, unit, status (green|yellow|red), detail
    """
    checks = [
        _check_cron_status,
        _check_records_fetched,
        _check_permit_changes_detected,
        _check_temporal_violations,
        _check_cost_outliers,
        _check_orphaned_contacts,
        _check_inspection_null_rate,
        _check_data_freshness,
        _check_rag_chunk_count,
        _check_entity_coverage,
    ]
    results = []
    for check_fn in checks:
        try:
            result = check_fn()
            if result:
                results.append(result)
        except Exception:
            logger.debug("DQ check %s failed", check_fn.__name__, exc_info=True)
            results.append({
                "name": check_fn.__name__.replace("_check_", "").replace("_", " ").title(),
                "category": "system",
                "value": "Error",
                "unit": "",
                "status": "red",
                "detail": "Check failed — see logs",
            })
    return results


def _check_cron_status() -> dict:
    """Check when the last successful nightly cron ran."""
    ph = _ph()
    rows = query(
        f"SELECT MAX(run_date) FROM cron_log WHERE status = {ph}",
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
    rows = query(
        f"SELECT records_fetched, run_date FROM cron_log "
        f"WHERE status = {ph} ORDER BY run_date DESC LIMIT 1",
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
    run_date = rows[0][1]
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
    rows = query(
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


def _check_temporal_violations() -> dict:
    """Count permits where filed_date > issued_date (temporal anomaly)."""
    rows = query(
        "SELECT COUNT(*) FROM permits "
        "WHERE filed_date IS NOT NULL AND issued_date IS NOT NULL "
        "AND filed_date > issued_date",
        (),
    )
    count = rows[0][0] if rows else 0
    status = "green" if count < 10 else ("yellow" if count < 100 else "red")
    return {
        "name": "Temporal Violations",
        "category": "anomaly",
        "value": f"{count:,}",
        "unit": "permits",
        "status": status,
        "detail": f"{count} permits with filed_date after issued_date",
    }


def _check_cost_outliers() -> dict:
    """Count permits with estimated cost > $500M (likely data errors)."""
    rows = query(
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
    """Count contacts without matching permits."""
    rows = query(
        "SELECT COUNT(*) FROM contacts c "
        "LEFT JOIN permits p ON c.permit_number = p.permit_number "
        "WHERE p.permit_number IS NULL",
        (),
    )
    count = rows[0][0] if rows else 0
    total_contacts = query("SELECT COUNT(*) FROM contacts", ())
    total = total_contacts[0][0] if total_contacts else 1
    pct = round(count / max(total, 1) * 100, 1)
    status = "green" if pct < 5 else ("yellow" if pct < 15 else "red")
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
    rows = query(
        "SELECT COUNT(*) FROM inspections WHERE inspection_type_desc IS NULL OR inspection_type_desc = ''",
        (),
    )
    null_count = rows[0][0] if rows else 0
    total_rows = query("SELECT COUNT(*) FROM inspections", ())
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
    rows = query(
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


def _check_rag_chunk_count() -> dict:
    """Check RAG knowledge_chunks count vs baseline (~1,012)."""
    rows = query("SELECT COUNT(*) FROM knowledge_chunks", ())
    count = rows[0][0] if rows else 0
    baseline = 1012
    pct_of_baseline = round(count / max(baseline, 1) * 100)
    status = "green" if pct_of_baseline >= 90 else ("yellow" if pct_of_baseline >= 70 else "red")
    return {
        "name": "RAG Chunks",
        "category": "completeness",
        "value": f"{count:,}",
        "unit": f"(baseline: {baseline:,})",
        "status": status,
        "detail": f"{count:,} knowledge chunks ({pct_of_baseline}% of baseline {baseline:,})",
    }


def _check_entity_coverage() -> dict:
    """Check entity resolution coverage (entities vs contacts)."""
    contact_rows = query("SELECT COUNT(*) FROM contacts", ())
    entity_rows = query("SELECT COUNT(*) FROM entities", ())
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
