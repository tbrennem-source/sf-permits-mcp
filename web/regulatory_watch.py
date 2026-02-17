"""Regulatory watch — track pending legislation and code amendments.

Monitors items like Board of Supervisors ordinances, DBI bulletins,
and planning code changes that may affect the knowledge base.
Surfaces alerts in the morning brief and property reports.
"""

from __future__ import annotations

import json
import logging

from src.db import BACKEND, execute_write, get_connection, init_user_schema, query, query_one

logger = logging.getLogger(__name__)

_schema_initialized = False

_VALID_STATUSES = ("monitoring", "passed", "effective", "withdrawn")
_VALID_SOURCE_TYPES = ("bos_file", "dbi_bulletin", "planning_code", "building_code", "other")
_VALID_IMPACT_LEVELS = ("high", "moderate", "low")


def _ensure_schema():
    global _schema_initialized
    if _schema_initialized:
        return
    if BACKEND == "duckdb":
        init_user_schema()
    _schema_initialized = True


def _now_expr() -> str:
    return "NOW()" if BACKEND == "postgres" else "CURRENT_TIMESTAMP"


# ── CRUD ─────────────────────────────────────────────────────────


def create_watch_item(
    title: str,
    source_type: str,
    source_id: str,
    description: str | None = None,
    status: str = "monitoring",
    impact_level: str = "moderate",
    affected_sections: list[str] | None = None,
    semantic_concepts: list[str] | None = None,
    url: str | None = None,
    filed_date: str | None = None,
    effective_date: str | None = None,
    notes: str | None = None,
) -> int:
    """Create a new regulatory watch item. Returns the watch_id."""
    _ensure_schema()
    sections_json = json.dumps(affected_sections) if affected_sections else None
    concepts_json = json.dumps(semantic_concepts) if semantic_concepts else None

    if BACKEND == "postgres":
        return execute_write(
            "INSERT INTO regulatory_watch "
            "(title, description, source_type, source_id, status, impact_level, "
            "affected_sections, semantic_concepts, url, filed_date, effective_date, notes) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING watch_id",
            (title, description, source_type, source_id, status, impact_level,
             sections_json, concepts_json, url, filed_date, effective_date, notes),
            return_id=True,
        )
    else:
        row = query_one("SELECT COALESCE(MAX(watch_id), 0) + 1 FROM regulatory_watch")
        watch_id = row[0]
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO regulatory_watch "
                "(watch_id, title, description, source_type, source_id, status, impact_level, "
                "affected_sections, semantic_concepts, url, filed_date, effective_date, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (watch_id, title, description, source_type, source_id, status, impact_level,
                 sections_json, concepts_json, url, filed_date, effective_date, notes),
            )
        finally:
            conn.close()
        return watch_id


def get_watch_item(watch_id: int) -> dict | None:
    """Get a single watch item by ID."""
    _ensure_schema()
    row = query_one(
        "SELECT watch_id, title, description, source_type, source_id, status, "
        "impact_level, affected_sections, semantic_concepts, url, filed_date, "
        "effective_date, notes, created_at, updated_at "
        "FROM regulatory_watch WHERE watch_id = %s",
        (watch_id,),
    )
    return _row_to_dict(row) if row else None


def list_watch_items(status_filter: str | None = None) -> list[dict]:
    """List all watch items, optionally filtered by status."""
    _ensure_schema()
    conditions: list[str] = []
    params: list = []
    if status_filter and status_filter in _VALID_STATUSES:
        conditions.append("status = %s")
        params.append(status_filter)
    where = ("WHERE " + " AND ".join(conditions) + " ") if conditions else ""
    rows = query(
        f"SELECT watch_id, title, description, source_type, source_id, status, "
        f"impact_level, affected_sections, semantic_concepts, url, filed_date, "
        f"effective_date, notes, created_at, updated_at "
        f"FROM regulatory_watch {where}"
        f"ORDER BY "
        f"CASE impact_level WHEN 'high' THEN 0 WHEN 'moderate' THEN 1 ELSE 2 END, "
        f"created_at DESC",
        tuple(params) if params else None,
    )
    return [_row_to_dict(r) for r in rows]


def update_watch_item(watch_id: int, **kwargs) -> bool:
    """Update specific fields on a watch item. Returns True if found."""
    _ensure_schema()
    allowed = {
        "title", "description", "source_type", "source_id", "status",
        "impact_level", "affected_sections", "semantic_concepts",
        "url", "filed_date", "effective_date", "notes",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    # Serialize JSON fields
    for json_field in ("affected_sections", "semantic_concepts"):
        if json_field in updates and isinstance(updates[json_field], list):
            updates[json_field] = json.dumps(updates[json_field])

    set_parts = [f"{k} = %s" for k in updates]
    set_parts.append(f"updated_at = {_now_expr()}")
    values = list(updates.values()) + [watch_id]

    execute_write(
        f"UPDATE regulatory_watch SET {', '.join(set_parts)} WHERE watch_id = %s",
        tuple(values),
    )
    return True


def delete_watch_item(watch_id: int) -> bool:
    """Delete a watch item."""
    _ensure_schema()
    execute_write(
        "DELETE FROM regulatory_watch WHERE watch_id = %s",
        (watch_id,),
    )
    return True


# ── Query helpers ────────────────────────────────────────────────


def get_alerts_for_concepts(concepts: list[str]) -> list[dict]:
    """Get active watch items whose semantic_concepts overlap with the given list.

    Used by property report to show pending regulations affecting a property.
    """
    _ensure_schema()
    items = list_watch_items()
    matching = []
    concept_set = {c.lower() for c in concepts}
    for item in items:
        if item["status"] not in ("monitoring", "passed"):
            continue
        item_concepts = {c.lower() for c in (item.get("semantic_concepts_list") or [])}
        if item_concepts & concept_set:
            matching.append(item)
    return matching


def get_approaching_effective(days_ahead: int = 90) -> list[dict]:
    """Get watch items with effective_date in the next N days."""
    _ensure_schema()
    from datetime import date, timedelta
    cutoff = (date.today() + timedelta(days=days_ahead)).isoformat()
    today = date.today().isoformat()
    rows = query(
        "SELECT watch_id, title, description, source_type, source_id, status, "
        "impact_level, affected_sections, semantic_concepts, url, filed_date, "
        "effective_date, notes, created_at, updated_at "
        "FROM regulatory_watch "
        "WHERE effective_date IS NOT NULL AND effective_date >= %s AND effective_date <= %s "
        "ORDER BY effective_date ASC",
        (today, cutoff),
    )
    return [_row_to_dict(r) for r in rows]


def get_regulatory_alerts() -> list[dict]:
    """Get active alerts for the morning brief.

    Returns items that are high-impact, recently created, or approaching effective date.
    Only items with status 'monitoring' or 'passed'.
    """
    _ensure_schema()
    items = list_watch_items()
    alerts = [i for i in items if i["status"] in ("monitoring", "passed")]
    return alerts


# ── Internal ─────────────────────────────────────────────────────


def _row_to_dict(row) -> dict:
    """Convert a query row tuple to a dict."""
    sections_raw = row[7]
    concepts_raw = row[8]
    try:
        sections_list = json.loads(sections_raw) if sections_raw else []
    except (json.JSONDecodeError, TypeError):
        sections_list = []
    try:
        concepts_list = json.loads(concepts_raw) if concepts_raw else []
    except (json.JSONDecodeError, TypeError):
        concepts_list = []

    return {
        "watch_id": row[0],
        "title": row[1],
        "description": row[2],
        "source_type": row[3],
        "source_id": row[4],
        "status": row[5],
        "impact_level": row[6],
        "affected_sections": sections_raw,
        "affected_sections_list": sections_list,
        "semantic_concepts": concepts_raw,
        "semantic_concepts_list": concepts_list,
        "url": row[9],
        "filed_date": row[10],
        "effective_date": row[11],
        "notes": row[12],
        "created_at": row[13],
        "updated_at": row[14],
    }
