"""Team member lookup via fuzzy entity search.

Phase 1: Post-submit fuzzy matching against the entities table.
  - Uses pg_trgm similarity() on Postgres for high-quality fuzzy matching.
  - Falls back to LIKE matching on DuckDB (local dev).

Phase 2: Typeahead autocomplete (frontend calls an API endpoint as user types).
"""

from __future__ import annotations

from src.db import get_connection, BACKEND


def _normalize_name(name: str) -> str:
    """Strip common business suffixes and normalize whitespace."""
    suffixes = [
        " inc", " inc.", " llc", " llc.", " corp", " corp.",
        " co", " co.", " ltd", " ltd.", " lp", " l.p.",
        " company", " corporation", " incorporated",
    ]
    normalized = " ".join(name.strip().split())  # collapse whitespace
    lower = normalized.lower()
    for suffix in suffixes:
        if lower.endswith(suffix):
            normalized = normalized[: len(normalized) - len(suffix)].strip()
            break
    return normalized


def lookup_entity(
    name: str,
    role: str = "any",
    limit: int = 3,
) -> list[dict]:
    """Fuzzy match a name against the entities table.

    Returns up to `limit` matches sorted by relevance (similarity score
    on Postgres, permit count on DuckDB).

    Each match is a dict with:
        name, entity_id, entity_type, canonical_firm,
        permit_count, contact_count, resolution_confidence
    """
    if not name or not name.strip():
        return []

    clean = _normalize_name(name)

    conn = get_connection()
    try:
        if BACKEND == "postgres":
            return _lookup_postgres(conn, clean, role, limit)
        else:
            return _lookup_duckdb(conn, clean, role, limit)
    finally:
        conn.close()


def _lookup_postgres(conn, name: str, role: str, limit: int) -> list[dict]:
    """Use pg_trgm similarity() for high-quality fuzzy matching."""
    # Search both canonical_name and canonical_firm
    sql = """
        SELECT
            entity_id,
            canonical_name,
            canonical_firm,
            entity_type,
            permit_count,
            contact_count,
            resolution_confidence,
            GREATEST(
                similarity(canonical_name, %s),
                COALESCE(similarity(canonical_firm, %s), 0)
            ) AS score
        FROM entities
        WHERE
            similarity(canonical_name, %s) > 0.2
            OR similarity(canonical_firm, %s) > 0.2
        ORDER BY score DESC, permit_count DESC
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (name, name, name, name, limit))
        rows = cur.fetchall()

    results = []
    for row in rows:
        results.append({
            "entity_id": row[0],
            "name": row[1],
            "firm": row[2],
            "entity_type": row[3],
            "permit_count": int(row[4]) if row[4] else 0,
            "contact_count": int(row[5]) if row[5] else 0,
            "confidence": row[6],
            "score": float(row[7]),
        })
    return results


def _lookup_duckdb(conn, name: str, role: str, limit: int) -> list[dict]:
    """Fallback: LIKE + contains matching on DuckDB."""
    # Try exact match first, then contains
    sql = f"""
        SELECT
            entity_id,
            canonical_name,
            canonical_firm,
            entity_type,
            permit_count,
            contact_count,
            resolution_confidence
        FROM entities
        WHERE
            LOWER(canonical_name) LIKE ?
            OR LOWER(canonical_firm) LIKE ?
        ORDER BY
            CASE
                WHEN LOWER(canonical_name) = ? THEN 0
                WHEN LOWER(canonical_name) LIKE ? THEN 1
                ELSE 2
            END,
            CAST(permit_count AS INTEGER) DESC
        LIMIT ?
    """
    pattern = f"%{name.lower()}%"
    exact = name.lower()
    starts = f"{name.lower()}%"
    rows = conn.execute(sql, [pattern, pattern, exact, starts, limit]).fetchall()

    results = []
    for row in rows:
        results.append({
            "entity_id": row[0],
            "name": row[1],
            "firm": row[2],
            "entity_type": row[3],
            "permit_count": int(row[4]) if row[4] else 0,
            "contact_count": int(row[5]) if row[5] else 0,
            "confidence": row[6],
            "score": None,  # No similarity score on DuckDB
        })
    return results


def _get_entity_stats(conn, entity_id: str) -> dict:
    """Pull detailed stats for a matched entity from permits + contacts."""
    stats = {
        "neighborhoods": [],
        "common_types": [],
        "avg_timeline_days": None,
        "correction_rate": None,
        "last_active": None,
    }

    if BACKEND == "postgres":
        _get_stats_postgres(conn, entity_id, stats)
    else:
        _get_stats_duckdb(conn, entity_id, stats)

    return stats


def _get_stats_postgres(conn, entity_id: str, stats: dict):
    """Pull entity stats from Postgres."""
    with conn.cursor() as cur:
        # Neighborhoods and project types
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
        if last_filed and (not last_active or last_filed > last_active):
            last_active = last_filed

    stats["neighborhoods"] = sorted(neighborhoods, key=neighborhoods.get, reverse=True)[:5]
    stats["common_types"] = sorted(types, key=types.get, reverse=True)[:5]
    stats["last_active"] = last_active

    # Average timeline from timeline_stats
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
        stats["avg_timeline_days"] = round(float(row[0]), 0)


def _get_stats_duckdb(conn, entity_id: str, stats: dict):
    """Pull entity stats from DuckDB."""
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
        if last_filed and (not last_active or last_filed > last_active):
            last_active = last_filed

    stats["neighborhoods"] = sorted(neighborhoods, key=neighborhoods.get, reverse=True)[:5]
    stats["common_types"] = sorted(types, key=types.get, reverse=True)[:5]
    stats["last_active"] = last_active

    # Average timeline
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
        stats["avg_timeline_days"] = round(float(row[0]), 0)


def generate_team_profile(
    contractor: str | None = None,
    architect: str | None = None,
    expediter: str | None = None,
) -> str:
    """Generate a 'Your Team' markdown section for the report.

    Looks up each provided name and returns formatted profile summaries.
    """
    if not any([contractor, architect, expediter]):
        return ""

    sections: list[str] = []
    sections.append("# Your Team\n")

    for label, name, role in [
        ("General Contractor", contractor, "contractor"),
        ("Architect / Engineer", architect, "architect"),
        ("Permit Expediter", expediter, "expediter"),
    ]:
        if not name or not name.strip():
            continue

        matches = lookup_entity(name, role=role, limit=3)

        if not matches:
            sections.append(f"## {label}: {name}")
            sections.append(
                f"We didn't find **{name}** in SF permit records. "
                "They may be new to SF or operating under a different business name.\n"
            )
            continue

        best = matches[0]
        display_name = best["firm"] or best["name"]

        # Get detailed stats for the best match
        conn = get_connection()
        try:
            stats = _get_entity_stats(conn, best["entity_id"])
        finally:
            conn.close()

        sections.append(f"## {label}: {display_name}")

        # Summary line
        permit_count = best["permit_count"]
        sections.append(f"**{permit_count:,} SF permits** on file")

        if stats["neighborhoods"]:
            hoods = ", ".join(stats["neighborhoods"][:3])
            sections.append(f"- **Active neighborhoods:** {hoods}")

        if stats["common_types"]:
            types = ", ".join(stats["common_types"][:3])
            sections.append(f"- **Common project types:** {types}")

        if stats["avg_timeline_days"]:
            days = int(stats["avg_timeline_days"])
            sections.append(
                f"- **Avg time to issuance:** {days} days "
                f"({days // 7} weeks)"
            )

        if stats["last_active"]:
            sections.append(f"- **Last filed:** {stats['last_active']}")

        # Confidence note
        if best.get("score") and best["score"] < 0.5:
            sections.append(
                f"\n*Note: Match confidence is moderate ({best['score']:.0%}). "
                f"Verify this is the right \"{name}\".*"
            )

        # Multiple matches note
        if len(matches) > 1:
            alt_names = [
                (m["firm"] or m["name"])
                for m in matches[1:]
                if (m["firm"] or m["name"]) != display_name
            ]
            if alt_names:
                sections.append(
                    f"\n*Other possible matches: {', '.join(alt_names)}*"
                )

        sections.append("")  # blank line

    return "\n".join(sections)
