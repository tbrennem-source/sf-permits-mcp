"""Reviewer-entity interaction graph — Tier 0 operational edges.

Builds and queries reviewer↔entity interaction edges from addenda routing
data. Unlike the co-occurrence graph (entities sharing permits), this tracks
which DBI plan reviewers have reviewed which applicants/contractors' permits.

Use cases:
- "Which reviewer at BLDG typically reviews Amy Lee's permits?"
- "Has this reviewer seen this type of project before?"
- "Which reviewers have the most experience with restaurant TIs?"
- RAG chunks: reviewer expertise profiles for AI guidance

Architecture:
- reviewer_interactions table: reviewer_name → entity_id aggregations
- Built from addenda.plan_checked_by JOIN contacts.entity_id
- Refreshed nightly after station_velocity (depends on same addenda data)
- PostgreSQL only (prod); DuckDB skips (reviewer graph not needed in dev)
"""

from __future__ import annotations

import logging
from datetime import date

from src.db import BACKEND, query, execute_write

logger = logging.getLogger(__name__)


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


def _ensure_reviewer_table() -> None:
    """Create reviewer_interactions table if it doesn't exist."""
    if BACKEND != "postgres":
        return
    execute_write("""
        CREATE TABLE IF NOT EXISTS reviewer_interactions (
            reviewer_name       TEXT NOT NULL,
            entity_id           INTEGER NOT NULL,
            entity_name         TEXT,
            entity_type         TEXT,
            entity_firm         TEXT,
            interaction_count   INTEGER NOT NULL DEFAULT 0,
            permit_count        INTEGER NOT NULL DEFAULT 0,
            stations            TEXT,
            result_summary      TEXT,
            first_review_date   TEXT,
            last_review_date    TEXT,
            computed_date       DATE NOT NULL DEFAULT CURRENT_DATE,
            PRIMARY KEY (reviewer_name, entity_id, computed_date)
        )
    """)
    # Index for querying by reviewer
    try:
        execute_write(
            "CREATE INDEX IF NOT EXISTS idx_reviewer_int_name "
            "ON reviewer_interactions (reviewer_name)"
        )
        execute_write(
            "CREATE INDEX IF NOT EXISTS idx_reviewer_int_entity "
            "ON reviewer_interactions (entity_id)"
        )
    except Exception:
        pass


def refresh_reviewer_interactions() -> dict:
    """Recompute reviewer↔entity interaction edges from addenda + contacts.

    Joins addenda.plan_checked_by with contacts.entity_id via
    addenda.application_number = contacts.permit_number.

    Returns dict with reviewer_count, edge_count for logging.
    """
    if BACKEND != "postgres":
        logger.info("Reviewer interactions refresh skipped (requires PostgreSQL)")
        return {"reviewers": 0, "edges": 0}

    _ensure_reviewer_table()

    sql = """
        INSERT INTO reviewer_interactions
            (reviewer_name, entity_id, entity_name, entity_type, entity_firm,
             interaction_count, permit_count, stations, result_summary,
             first_review_date, last_review_date, computed_date)
        SELECT
            a.plan_checked_by,
            c.entity_id,
            e.canonical_name,
            e.entity_type,
            e.canonical_firm,
            COUNT(*) AS interaction_count,
            COUNT(DISTINCT a.application_number) AS permit_count,
            STRING_AGG(DISTINCT a.station, ',' ORDER BY a.station) AS stations,
            STRING_AGG(DISTINCT a.review_results, ',' ORDER BY a.review_results)
                FILTER (WHERE a.review_results IS NOT NULL AND a.review_results != '')
                AS result_summary,
            MIN(CAST(a.finish_date AS TEXT)) AS first_review_date,
            MAX(CAST(a.finish_date AS TEXT)) AS last_review_date,
            CURRENT_DATE
        FROM addenda a
        JOIN contacts c ON a.application_number = c.permit_number
        JOIN entities e ON c.entity_id = e.entity_id
        WHERE a.plan_checked_by IS NOT NULL
          AND a.plan_checked_by != ''
          AND a.finish_date IS NOT NULL
          AND c.entity_id IS NOT NULL
        GROUP BY a.plan_checked_by, c.entity_id,
                 e.canonical_name, e.entity_type, e.canonical_firm
        HAVING COUNT(*) >= 2
        ON CONFLICT (reviewer_name, entity_id, computed_date) DO UPDATE SET
            entity_name = EXCLUDED.entity_name,
            entity_type = EXCLUDED.entity_type,
            entity_firm = EXCLUDED.entity_firm,
            interaction_count = EXCLUDED.interaction_count,
            permit_count = EXCLUDED.permit_count,
            stations = EXCLUDED.stations,
            result_summary = EXCLUDED.result_summary,
            first_review_date = EXCLUDED.first_review_date,
            last_review_date = EXCLUDED.last_review_date
    """
    try:
        execute_write(sql)
    except Exception:
        logger.error("Reviewer interactions refresh failed", exc_info=True)
        return {"reviewers": 0, "edges": 0}

    # Get stats
    try:
        rows = query(
            "SELECT COUNT(DISTINCT reviewer_name), COUNT(*) "
            "FROM reviewer_interactions WHERE computed_date = CURRENT_DATE"
        )
        reviewer_count = rows[0][0] if rows else 0
        edge_count = rows[0][1] if rows else 0
    except Exception:
        reviewer_count, edge_count = 0, 0

    logger.info("Reviewer interactions: %d reviewers, %d edges", reviewer_count, edge_count)
    return {"reviewers": reviewer_count, "edges": edge_count}


def get_reviewer_profile(reviewer_name: str) -> dict | None:
    """Get a reviewer's interaction profile — who they review, what stations.

    Returns dict with:
        name, total_interactions, total_permits, stations, top_entities, active_period
    """
    if BACKEND != "postgres":
        return None

    ph = _ph()
    try:
        rows = query(
            f"SELECT entity_id, entity_name, entity_type, entity_firm, "
            f"       interaction_count, permit_count, stations, result_summary, "
            f"       first_review_date, last_review_date "
            f"FROM reviewer_interactions "
            f"WHERE reviewer_name = {ph} "
            f"  AND computed_date = (SELECT MAX(computed_date) FROM reviewer_interactions) "
            f"ORDER BY interaction_count DESC "
            f"LIMIT 20",
            (reviewer_name,),
        )
    except Exception:
        logger.debug("get_reviewer_profile(%s) failed", reviewer_name, exc_info=True)
        return None

    if not rows:
        return None

    total_interactions = sum(r[4] for r in rows)
    total_permits = sum(r[5] for r in rows)
    all_stations = set()
    for r in rows:
        if r[6]:
            all_stations.update(s.strip() for s in r[6].split(","))

    first_dates = [r[8] for r in rows if r[8]]
    last_dates = [r[9] for r in rows if r[9]]

    return {
        "name": reviewer_name,
        "total_interactions": total_interactions,
        "total_permits": total_permits,
        "stations": sorted(all_stations),
        "active_from": min(first_dates) if first_dates else None,
        "active_to": max(last_dates) if last_dates else None,
        "top_entities": [
            {
                "entity_id": r[0],
                "name": r[1],
                "type": r[2],
                "firm": r[3],
                "interactions": r[4],
                "permits": r[5],
            }
            for r in rows[:10]
        ],
    }


def get_entity_reviewers(entity_id: int) -> list[dict]:
    """Get all reviewers who have reviewed a given entity's permits.

    Returns list of reviewer dicts sorted by interaction_count DESC.
    """
    if BACKEND != "postgres":
        return []

    ph = _ph()
    try:
        rows = query(
            f"SELECT reviewer_name, interaction_count, permit_count, stations, "
            f"       result_summary, first_review_date, last_review_date "
            f"FROM reviewer_interactions "
            f"WHERE entity_id = {ph} "
            f"  AND computed_date = (SELECT MAX(computed_date) FROM reviewer_interactions) "
            f"ORDER BY interaction_count DESC "
            f"LIMIT 15",
            (entity_id,),
        )
    except Exception:
        logger.debug("get_entity_reviewers(%s) failed", entity_id, exc_info=True)
        return []

    return [
        {
            "reviewer": r[0],
            "interactions": r[1],
            "permits": r[2],
            "stations": r[3].split(",") if r[3] else [],
            "results": r[4],
            "first_review": r[5],
            "last_review": r[6],
        }
        for r in rows
    ]


def get_top_reviewers(station: str | None = None, limit: int = 20) -> list[dict]:
    """Get most active reviewers, optionally filtered by station.

    Returns list of reviewer summary dicts.
    """
    if BACKEND != "postgres":
        return []

    ph = _ph()
    try:
        if station:
            rows = query(
                f"SELECT reviewer_name, "
                f"       SUM(interaction_count) as total_int, "
                f"       SUM(permit_count) as total_permits, "
                f"       COUNT(DISTINCT entity_id) as entity_count "
                f"FROM reviewer_interactions "
                f"WHERE computed_date = (SELECT MAX(computed_date) FROM reviewer_interactions) "
                f"  AND stations LIKE {ph} "
                f"GROUP BY reviewer_name "
                f"ORDER BY total_int DESC "
                f"LIMIT {ph}",
                (f"%{station}%", limit),
            )
        else:
            rows = query(
                f"SELECT reviewer_name, "
                f"       SUM(interaction_count) as total_int, "
                f"       SUM(permit_count) as total_permits, "
                f"       COUNT(DISTINCT entity_id) as entity_count "
                f"FROM reviewer_interactions "
                f"WHERE computed_date = (SELECT MAX(computed_date) FROM reviewer_interactions) "
                f"GROUP BY reviewer_name "
                f"ORDER BY total_int DESC "
                f"LIMIT {int(limit)}",
            )
    except Exception:
        logger.debug("get_top_reviewers failed", exc_info=True)
        return []

    return [
        {
            "reviewer": r[0],
            "total_interactions": r[1],
            "total_permits": r[2],
            "entity_count": r[3],
        }
        for r in rows
    ]
