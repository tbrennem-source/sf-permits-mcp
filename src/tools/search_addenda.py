"""Tool: search_addenda — Search permit plan review routing by permit, station, or reviewer."""

import logging
from src.db import get_connection, BACKEND

logger = logging.getLogger(__name__)

_PH = "%s" if BACKEND == "postgres" else "?"


def _exec(conn, sql, params=None):
    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    else:
        return conn.execute(sql, params or []).fetchall()


async def search_addenda(
    permit_number: str | None = None,
    station: str | None = None,
    reviewer: str | None = None,
    department: str | None = None,
    review_result: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> str:
    """Search building permit plan review routing data.

    Searches the local database of 3.9M+ addenda routing records. Provide at least one filter:
    - permit_number: exact permit/application number
    - station: review station (e.g., 'BLDG', 'SFFD-HQ', 'CP-ZOC', 'MECH-E')
    - reviewer: plan checker name (partial match, LAST FIRST format)
    - department: department code (DBI, CPC, PUC, DPW, SFFD)
    - review_result: filter by outcome (Approved, Issued Comments, Administrative)
    - date_from / date_to: filter by finish_date range (YYYY-MM-DD)
    - limit: max results (default 50, max 200)

    Returns routing timeline showing each review step with station, reviewer,
    result, and any hold/comment descriptions.
    """
    conditions = []
    params = []

    if permit_number:
        conditions.append(f"application_number = {_PH}")
        params.append(permit_number.strip())
    if station:
        conditions.append(f"UPPER(station) = UPPER({_PH})")
        params.append(station.strip())
    if reviewer:
        conditions.append(f"UPPER(plan_checked_by) LIKE UPPER({_PH})")
        params.append(f"%{reviewer.strip()}%")
    if department:
        conditions.append(f"UPPER(department) = UPPER({_PH})")
        params.append(department.strip())
    if review_result:
        conditions.append(f"UPPER(review_results) LIKE UPPER({_PH})")
        params.append(f"%{review_result.strip()}%")
    if date_from:
        conditions.append(f"finish_date >= {_PH}")
        params.append(date_from)
    if date_to:
        conditions.append(f"finish_date <= {_PH}")
        params.append(date_to)

    if not conditions:
        return "Please provide at least one filter: permit_number, station, reviewer, department, review_result, or date range."

    # Exclude erroneous far-future dates from upstream SODA data (e.g., year 2200+)
    # Only applied when the caller hasn't set an explicit upper date bound.
    if not date_to:
        conditions.append(f"(finish_date IS NULL OR finish_date <= '2030-12-31')")

    fetch_limit = min(limit, 200)
    where = " AND ".join(conditions)

    conn = get_connection()
    try:
        sql = f"""
            SELECT application_number, addenda_number, step, station,
                   plan_checked_by, review_results, finish_date, hold_description,
                   department, arrive, start_date, addenda_status, title
            FROM addenda
            WHERE {where}
            ORDER BY application_number, addenda_number, step
            LIMIT {fetch_limit}
        """
        rows = _exec(conn, sql, params)

        if not rows:
            return "No addenda routing records found matching your criteria."

        return _format_addenda_results(rows, len(rows), fetch_limit)
    finally:
        conn.close()


def _format_addenda_results(rows: list[tuple], count: int, limit: int) -> str:
    """Format addenda search results as markdown."""
    lines = [
        f"# Plan Review Routing Results\n",
        f"Found **{count}** routing records{' (capped at ' + str(limit) + ')' if count >= limit else ''}.\n",
        "| Permit | Rev | Station | Reviewer | Result | Finish | Dept |",
        "|--------|-----|---------|----------|--------|--------|------|",
    ]

    for r in rows:
        app = r[0] or "---"
        rev = str(r[1]) if r[1] is not None else "---"
        station = r[3] or "---"
        reviewer = r[4] or "---"
        result = r[5] or "---"
        finish = (r[6] or "---")[:10] if r[6] else "---"
        dept = r[8] or "---"

        lines.append(f"| {app} | {rev} | {station} | {reviewer} | {result} | {finish} | {dept} |")

    # Show hold descriptions for rows that have them
    notes = [(r[0], r[3], r[7]) for r in rows if r[7]]
    if notes:
        lines.append("\n### Review Notes\n")
        for app, station, desc in notes[:10]:
            truncated = desc[:200] + "..." if len(desc) > 200 else desc
            lines.append(f"- **{app}** ({station}): {truncated}")
        if len(notes) > 10:
            lines.append(f"\n*Showing 10 of {len(notes)} notes.*")

    lines.append(f"\n---\n*Source: sfpermits.ai local database ({BACKEND}) — 3.9M addenda routing records*")
    return "\n".join(lines)
