"""Tool: search_entity — Search for a person or company across all permit contact data.

Returns expediter-friendly output: headline info, portfolio summary,
recent permits, and network connections — prioritized by what matters
for decision-making.
"""

from __future__ import annotations

from src.db import get_connection, BACKEND
from src.validate import search_entity as _search_entity


def _get_portfolio_stats(conn, entity_id: int) -> dict:
    """Pull rich portfolio stats for a single entity.

    Returns neighborhoods, project types, timeline metrics, revision rate,
    recent permits, and last active date.
    """
    stats: dict = {
        "neighborhoods": [],
        "common_types": [],
        "avg_timeline_days": None,
        "last_active": None,
        "recent_permits": [],
        "active_count": 0,
        "cost_range": None,
    }

    if BACKEND == "postgres":
        _portfolio_postgres(conn, entity_id, stats)
    else:
        _portfolio_duckdb(conn, entity_id, stats)

    return stats


def _portfolio_postgres(conn, entity_id: int, stats: dict):
    """Pull portfolio stats from Postgres."""
    with conn.cursor() as cur:
        # Neighborhoods and project types (aggregated)
        cur.execute("""
            SELECT
                p.neighborhood,
                p.permit_type_definition,
                COUNT(*) as cnt,
                MAX(p.filed_date) as last_filed
            FROM contacts c
            JOIN permits p ON c.permit_number = p.permit_number
            WHERE c.entity_id = %s
            AND p.neighborhood IS NOT NULL
            GROUP BY p.neighborhood, p.permit_type_definition
            ORDER BY cnt DESC
        """, (entity_id,))
        rows = cur.fetchall()

    neighborhoods: dict[str, int] = {}
    types: dict[str, int] = {}
    last_active = None

    for hood, ptype, cnt, last_filed in rows:
        if hood:
            neighborhoods[hood] = neighborhoods.get(hood, 0) + cnt
        if ptype:
            types[ptype] = types.get(ptype, 0) + cnt
        if last_filed and (not last_active or str(last_filed) > str(last_active)):
            last_active = last_filed

    stats["neighborhoods"] = sorted(neighborhoods, key=neighborhoods.get, reverse=True)[:5]
    stats["common_types"] = sorted(types, key=types.get, reverse=True)[:5]
    stats["last_active"] = str(last_active) if last_active else None

    # Recent permits (last 5 by filed_date)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                p.permit_number,
                p.status,
                COALESCE(p.street_number, '') || ' ' || COALESCE(p.street_name, '') || ' ' || COALESCE(p.street_suffix, '') AS address,
                p.description,
                p.estimated_cost,
                p.filed_date,
                p.neighborhood
            FROM contacts c
            JOIN permits p ON c.permit_number = p.permit_number
            WHERE c.entity_id = %s
            ORDER BY p.filed_date DESC NULLS LAST
            LIMIT 5
        """, (entity_id,))
        recent = cur.fetchall()

    recent_cols = ["permit_number", "status", "address", "description",
                   "estimated_cost", "filed_date", "neighborhood"]
    stats["recent_permits"] = [dict(zip(recent_cols, r)) for r in recent]

    # Active permits count
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM contacts c
            JOIN permits p ON c.permit_number = p.permit_number
            WHERE c.entity_id = %s
            AND p.status NOT IN ('complete', 'expired', 'withdrawn', 'cancelled',
                                 'disapproved', 'revoked', 'suspended')
        """, (entity_id,))
        row = cur.fetchone()
    stats["active_count"] = row[0] if row else 0

    # Avg timeline from timeline_stats
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                AVG(days_to_issuance::INTEGER) as avg_days,
                COUNT(*) as sample
            FROM timeline_stats ts
            WHERE ts.permit_number IN (
                SELECT c.permit_number FROM contacts c WHERE c.entity_id = %s
            )
            AND days_to_issuance IS NOT NULL
            AND days_to_issuance::INTEGER > 0
            AND days_to_issuance::INTEGER < 2000
        """, (entity_id,))
        row = cur.fetchone()
    if row and row[0]:
        stats["avg_timeline_days"] = round(float(row[0]))

    # Cost range (p25/p75)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY p.estimated_cost),
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY p.estimated_cost)
            FROM contacts c
            JOIN permits p ON c.permit_number = p.permit_number
            WHERE c.entity_id = %s
            AND p.estimated_cost > 0
        """, (entity_id,))
        row = cur.fetchone()
    if row and row[0] and row[1]:
        stats["cost_range"] = (round(float(row[0])), round(float(row[1])))


def _portfolio_duckdb(conn, entity_id: int, stats: dict):
    """Pull portfolio stats from DuckDB."""
    rows = conn.execute("""
        SELECT
            p.neighborhood,
            p.permit_type_definition,
            COUNT(*) as cnt,
            MAX(p.filed_date) as last_filed
        FROM contacts c
        JOIN permits p ON c.permit_number = p.permit_number
        WHERE c.entity_id = ?
        AND p.neighborhood IS NOT NULL
        GROUP BY p.neighborhood, p.permit_type_definition
        ORDER BY cnt DESC
    """, [entity_id]).fetchall()

    neighborhoods: dict[str, int] = {}
    types: dict[str, int] = {}
    last_active = None

    for hood, ptype, cnt, last_filed in rows:
        if hood:
            neighborhoods[hood] = neighborhoods.get(hood, 0) + cnt
        if ptype:
            types[ptype] = types.get(ptype, 0) + cnt
        if last_filed and (not last_active or str(last_filed) > str(last_active)):
            last_active = last_filed

    stats["neighborhoods"] = sorted(neighborhoods, key=neighborhoods.get, reverse=True)[:5]
    stats["common_types"] = sorted(types, key=types.get, reverse=True)[:5]
    stats["last_active"] = str(last_active) if last_active else None

    # Recent permits
    recent = conn.execute("""
        SELECT
            p.permit_number,
            p.status,
            COALESCE(p.street_number, '') || ' ' || COALESCE(p.street_name, '') || ' ' || COALESCE(p.street_suffix, '') AS address,
            p.description,
            p.estimated_cost,
            p.filed_date,
            p.neighborhood
        FROM contacts c
        JOIN permits p ON c.permit_number = p.permit_number
        WHERE c.entity_id = ?
        ORDER BY p.filed_date DESC NULLS LAST
        LIMIT 5
    """, [entity_id]).fetchall()

    recent_cols = ["permit_number", "status", "address", "description",
                   "estimated_cost", "filed_date", "neighborhood"]
    stats["recent_permits"] = [dict(zip(recent_cols, r)) for r in recent]

    # Active permits count
    row = conn.execute("""
        SELECT COUNT(*)
        FROM contacts c
        JOIN permits p ON c.permit_number = p.permit_number
        WHERE c.entity_id = ?
        AND p.status NOT IN ('complete', 'expired', 'withdrawn', 'cancelled',
                             'disapproved', 'revoked', 'suspended')
    """, [entity_id]).fetchone()
    stats["active_count"] = row[0] if row else 0

    # Avg timeline
    row = conn.execute("""
        SELECT
            AVG(CAST(days_to_issuance AS INTEGER)) as avg_days
        FROM timeline_stats ts
        WHERE ts.permit_number IN (
            SELECT c.permit_number FROM contacts c WHERE c.entity_id = ?
        )
        AND days_to_issuance IS NOT NULL
        AND CAST(days_to_issuance AS INTEGER) > 0
        AND CAST(days_to_issuance AS INTEGER) < 2000
    """, [entity_id]).fetchone()
    if row and row[0]:
        stats["avg_timeline_days"] = round(float(row[0]))

    # Cost range
    row = conn.execute("""
        SELECT
            QUANTILE_CONT(estimated_cost, 0.25),
            QUANTILE_CONT(estimated_cost, 0.75)
        FROM (
            SELECT p.estimated_cost
            FROM contacts c
            JOIN permits p ON c.permit_number = p.permit_number
            WHERE c.entity_id = ?
            AND p.estimated_cost > 0
        )
    """, [entity_id]).fetchone()
    if row and row[0] and row[1]:
        stats["cost_range"] = (round(float(row[0])), round(float(row[1])))


def _format_cost(amount: float) -> str:
    """Format a dollar amount compactly: $85K, $1.2M, etc."""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"${amount / 1_000:.0f}K"
    else:
        return f"${amount:,.0f}"


def _status_icon(status: str | None) -> str:
    """Return a status indicator for a permit."""
    if not status:
        return ""
    s = status.lower()
    if s in ("complete", "issued"):
        return "complete"
    elif s in ("approved",):
        return "approved"
    elif s in ("filed", "plancheck", "reinstated"):
        return "in review"
    elif s in ("expired", "withdrawn", "cancelled", "disapproved", "revoked", "suspended"):
        return "closed"
    return status


async def search_entity(name: str, entity_type: str | None = None) -> str:
    """Search for a person or company across all permit contact data.

    Returns expediter-friendly output with portfolio summary, recent
    permits, and network connections.

    Args:
        name: Name to search for (person or company, case-insensitive)
        entity_type: Optional filter by type: 'contractor', 'architect',
                     'engineer', 'owner', 'agent', 'expediter', 'designer'

    Returns:
        Formatted markdown with entity profiles.
    """
    results = _search_entity(name)

    if not results:
        return f"No entities found matching '{name}'."

    # Filter by type if specified
    if entity_type:
        results = [r for r in results if r.get("entity_type") == entity_type]
        if not results:
            return f"No {entity_type} entities found matching '{name}'."

    # Enrich top results with portfolio stats (cap at 5 to limit DB load)
    conn = get_connection()
    try:
        for entity in results[:5]:
            entity["stats"] = _get_portfolio_stats(conn, entity["entity_id"])
    finally:
        conn.close()

    lines: list[str] = []

    if len(results) == 1:
        lines.append(f"# {results[0].get('canonical_name') or name}\n")
    else:
        lines.append(f"Found {len(results)} matches for '{name}':\n")

    for i, entity in enumerate(results[:5]):
        _format_entity(entity, lines, is_single=(len(results) == 1))

    if len(results) > 5:
        lines.append(
            f"\n*Showing top 5 of {len(results)} results. "
            f"Refine your search for more specific results.*"
        )

    return "\n".join(lines)


def _format_entity(entity: dict, lines: list[str], is_single: bool = False):
    """Format a single entity result as expediter-friendly markdown."""
    name = entity.get("canonical_name") or "Unknown"
    firm = entity.get("canonical_firm")
    etype = entity.get("entity_type", "unknown")
    permit_count = entity.get("permit_count", 0) or 0
    stats = entity.get("stats", {})

    # --- Headline ---
    if not is_single:
        lines.append(f"### {name}")

    # Type + firm + permit count headline
    headline_parts = [f"**{etype.title()}**"]
    if firm and firm.lower() != name.lower():
        headline_parts.append(f"at {firm}")
    headline_parts.append(f"· {permit_count:,} SF permits")
    if stats.get("active_count"):
        headline_parts.append(f"({stats['active_count']} active)")
    lines.append(" ".join(headline_parts))

    # Credentials line
    creds = []
    if entity.get("license_number"):
        creds.append(f"License #{entity['license_number']}")
    if entity.get("pts_agent_id"):
        creds.append(f"PTS Agent #{entity['pts_agent_id']}")
    if creds:
        lines.append(f"_{' · '.join(creds)}_")

    # Last active
    if stats.get("last_active"):
        lines.append(f"Last active: {stats['last_active']}")

    lines.append("")

    # --- Portfolio Summary ---
    if stats.get("neighborhoods") or stats.get("common_types") or stats.get("avg_timeline_days"):
        lines.append("**Portfolio**")

        if stats.get("neighborhoods"):
            hoods = ", ".join(stats["neighborhoods"][:3])
            lines.append(f"- **Top areas:** {hoods}")

        if stats.get("common_types"):
            types_str = ", ".join(stats["common_types"][:3])
            lines.append(f"- **Common projects:** {types_str}")

        if stats.get("avg_timeline_days"):
            days = int(stats["avg_timeline_days"])
            weeks = days // 7
            lines.append(f"- **Avg time to issuance:** {days} days ({weeks} weeks)")

        if stats.get("cost_range"):
            low, high = stats["cost_range"]
            lines.append(f"- **Typical project size:** {_format_cost(low)} – {_format_cost(high)}")

        lines.append("")

    # --- Recent Permits ---
    recent = stats.get("recent_permits", [])
    if recent:
        lines.append("**Recent Permits**")
        lines.append("")
        lines.append("| Permit | Address | Status | Cost | Filed |")
        lines.append("|--------|---------|--------|------|-------|")
        for p in recent[:5]:
            pnum = p.get("permit_number", "?")
            addr = (p.get("address") or "").strip()
            status = _status_icon(p.get("status"))
            cost = _format_cost(float(p["estimated_cost"])) if p.get("estimated_cost") else "—"
            filed = p.get("filed_date") or "—"
            # Truncate description for address column if address is empty
            if not addr or addr.strip() == "":
                addr = (p.get("description") or "")[:40]
            lines.append(f"| {pnum} | {addr} | {status} | {cost} | {filed} |")
        lines.append("")

    # --- Network ---
    neighbors = entity.get("top_co_occurring", [])
    if neighbors:
        lines.append("**Frequent Collaborators**")
        for n in neighbors[:5]:
            n_name = n.get("canonical_name") or n.get("canonical_firm") or "Unknown"
            n_type = n.get("entity_type", "?")
            shared = n.get("shared_permits", 0)
            lines.append(f"- {n_name} ({n_type}) — {shared} shared permits")
        lines.append("")

    lines.append("---\n")
