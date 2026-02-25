"""Tool: recommend_consultants — Score and rank land use consultants for a project.

Composite tool querying DuckDB entities/relationships tables and the
permit-consultants-registry JSON to find and rank the best consultants
for a specific project profile.

Scoring (100 pts max + bonuses):
  - Permit volume:             0-25
  - Residential specialization: 0-25
  - Neighborhood match:         0-20
  - Recency:                    0-15
  - Network quality:            0-15
  - Bonus: complaint resolution  +10
  - Bonus: planning coordination +10
  - Bonus: ethics registration   +5
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.db import get_connection, BACKEND

logger = logging.getLogger(__name__)

# Path to permit consultants registry
_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "knowledge", "tier1", "permit-consultants-registry.json",
)

# Cache for the registry
_registry_cache: dict | None = None


def _load_registry() -> dict:
    """Load and cache the permit consultants registry."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache
    try:
        with open(_REGISTRY_PATH) as f:
            _registry_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Could not load permit consultants registry: %s", e)
        _registry_cache = {"consultants": [], "metadata": {}}
    return _registry_cache


def _get_registered_names() -> set[str]:
    """Get set of registered consultant names (lowercased)."""
    registry = _load_registry()
    names = set()
    for c in registry.get("consultants", []):
        name = c.get("name", "").strip().lower()
        if name:
            names.add(name)
    return names


@dataclass
class ScoredConsultant:
    """A land use consultant with scoring breakdown."""
    entity_id: int
    name: str
    firm: str
    permit_count: int
    score: float = 0.0
    breakdown: dict = field(default_factory=dict)
    neighborhoods: list[str] = field(default_factory=list)
    date_range_end: str = ""
    network_size: int = 0
    is_registered: bool = False
    contact_info: dict = field(default_factory=dict)


async def recommend_consultants(
    address: str | None = None,
    block: str | None = None,
    lot: str | None = None,
    permit_type: str | None = None,
    neighborhood: str | None = None,
    has_active_complaint: bool = False,
    needs_planning_coordination: bool = False,
    limit: int = 5,
    entity_type: str | None = None,
) -> str:
    """Recommend top land use consultants for a project based on scoring criteria.

    Args:
        address: Property street name (e.g., 'ROBIN HOOD')
        block: Assessor block number (e.g., '2920')
        lot: Assessor lot number (e.g., '020')
        permit_type: Type of permit (e.g., 'additions alterations or repairs')
        neighborhood: Target neighborhood for matching
        has_active_complaint: Whether property has active complaints (enables +10 bonus)
        needs_planning_coordination: Whether project needs planning dept coordination (+10 bonus)
        limit: Number of recommendations (default 5, max 20)
        entity_type: Optional entity type filter. Defaults to 'consultant'.
            Supported values: 'consultant', 'contractor', 'architect', 'engineer',
            'electrician', 'plumber', 'owner', 'agent', 'designer'.
            Trade types ('electrician', 'plumber') will search for matching
            contractor entities in the database.

    Returns:
        Formatted ranked list of recommended consultants with scores.
    """
    limit = min(max(1, limit), 20)

    # Normalize entity_type: map trade names to DB entity types
    # A7: Support contractor/trade types in addition to 'consultant'
    _TRADE_TYPE_MAP = {
        "electrician": "contractor",
        "plumber": "contractor",
        "electrical": "contractor",
        "plumbing": "contractor",
    }
    # Supported DB entity types (as stored in entities.entity_type)
    _VALID_ENTITY_TYPES = {
        "consultant", "contractor", "architect", "engineer",
        "owner", "agent", "designer",
    }
    if entity_type:
        entity_type_normalized = _TRADE_TYPE_MAP.get(entity_type.lower(), entity_type.lower())
        if entity_type_normalized not in _VALID_ENTITY_TYPES:
            entity_type_normalized = "consultant"  # Graceful fallback
    else:
        entity_type_normalized = "consultant"  # Default

    conn = get_connection()
    try:
        # Step 1: Get all entities of the requested type with minimum activity
        ph = "?" if BACKEND == "duckdb" else "%s"
        consultants = _query_consultants(conn, min_permits=20, entity_type=entity_type_normalized)

        if not consultants:
            return "No consultants found in the database with sufficient activity."

        # Step 2: Get max permit count for normalization
        max_permits = max(e["permit_count"] for e in consultants)

        # Step 3: Get relationships for each consultant
        entity_ids = [e["entity_id"] for e in consultants]

        # Step 4: Score each consultant
        registered_names = _get_registered_names()
        scored: list[ScoredConsultant] = []

        for exp in consultants:
            s = ScoredConsultant(
                entity_id=exp["entity_id"],
                name=exp["canonical_name"],
                firm=exp["canonical_firm"] or "",
                permit_count=exp["permit_count"],
            )

            # -- Volume score (0-25) --
            volume_score = (exp["permit_count"] / max_permits) * 25 if max_permits > 0 else 0
            s.breakdown["volume"] = round(volume_score, 1)
            s.score += volume_score

            # -- Get relationships for specialization + neighborhood + network --
            rels = _query_relationships(conn, exp["entity_id"])

            # -- Residential specialization (0-25) --
            # Count permits that are residential alterations
            total_rel_permits = 0
            residential_permits = 0
            all_neighborhoods = set()
            latest_date = ""
            network_partners = 0

            for r in rels:
                shared = r["shared_permits"]
                total_rel_permits += shared
                ptypes = (r["permit_types"] or "").lower()
                if "a" in ptypes.split(",") or "additions" in ptypes:
                    residential_permits += shared
                if r["neighborhoods"]:
                    for n in r["neighborhoods"].split(","):
                        n = n.strip()
                        if n:
                            all_neighborhoods.add(n)
                if r["date_range_end"] and r["date_range_end"] > latest_date:
                    latest_date = r["date_range_end"]
                if shared >= 3:
                    network_partners += 1

            s.neighborhoods = sorted(all_neighborhoods)
            s.date_range_end = latest_date
            s.network_size = network_partners

            if total_rel_permits > 0:
                res_ratio = residential_permits / total_rel_permits
                spec_score = res_ratio * 25
            else:
                spec_score = 12.5  # neutral
            s.breakdown["specialization"] = round(spec_score, 1)
            s.score += spec_score

            # -- Neighborhood match (0-20) --
            if neighborhood:
                target_lower = neighborhood.lower()
                hood_match = any(
                    target_lower in n.lower() or n.lower() in target_lower
                    for n in all_neighborhoods
                )
                hood_score = 20 if hood_match else 0
            else:
                hood_score = 10  # neutral when no neighborhood specified
            s.breakdown["neighborhood"] = round(hood_score, 1)
            s.score += hood_score

            # -- Recency (0-15) --
            recency_score = 0
            if latest_date:
                try:
                    end_date = date.fromisoformat(latest_date[:10])
                    today = date.today()
                    months_ago = (today - end_date).days / 30
                    if months_ago <= 6:
                        recency_score = 15
                    elif months_ago <= 12:
                        recency_score = 10
                    elif months_ago <= 24:
                        recency_score = 5
                except (ValueError, TypeError):
                    pass
            s.breakdown["recency"] = round(recency_score, 1)
            s.score += recency_score

            # -- Network quality (0-15) --
            # Score based on distinct co-occurring professionals (shared_permits >= 3)
            if network_partners >= 10:
                network_score = 15
            elif network_partners >= 5:
                network_score = 10
            elif network_partners >= 2:
                network_score = 5
            else:
                network_score = 0
            s.breakdown["network"] = round(network_score, 1)
            s.score += network_score

            # -- Bonus: complaint resolution (+10) --
            if has_active_complaint:
                # Check if consultant has worked at addresses with complaints
                # (simplified: give bonus if consultant has high volume in diverse neighborhoods)
                if exp["permit_count"] >= 50 and len(all_neighborhoods) >= 3:
                    s.breakdown["complaint_bonus"] = 10
                    s.score += 10

            # -- Bonus: planning coordination (+10) --
            if needs_planning_coordination:
                # Check if consultant co-occurs with planning-related contacts
                # (simplified: give bonus if consultant has strong network)
                if network_partners >= 5:
                    s.breakdown["planning_bonus"] = 10
                    s.score += 10

            # -- Bonus: ethics registration (+5) --
            name_lower = exp["canonical_name"].lower()
            if name_lower in registered_names:
                s.is_registered = True
                s.breakdown["ethics_bonus"] = 5
                s.score += 5

                # Also grab contact info from registry
                registry = _load_registry()
                for c in registry.get("consultants", []):
                    if c.get("name", "").strip().lower() == name_lower:
                        s.contact_info = {
                            "email": c.get("email", ""),
                            "phone": c.get("phone", ""),
                            "firm": c.get("firm", ""),
                        }
                        break

            scored.append(s)

    finally:
        conn.close()

    # Sort by score descending
    scored.sort(key=lambda x: x.score, reverse=True)
    top = scored[:limit]

    return _format_recommendations(
        top, neighborhood, has_active_complaint, needs_planning_coordination,
        entity_type=entity_type_normalized,
    )


def _query_consultants(conn, min_permits: int = 20, entity_type: str = "consultant") -> list[dict]:
    """Query entities table for active professionals of the specified type.

    A7: Now accepts entity_type parameter to support consultant, contractor,
    architect, engineer, etc. Defaults to 'consultant' for backward compatibility.
    """
    if BACKEND == "duckdb":
        rows = conn.execute(
            "SELECT entity_id, canonical_name, canonical_firm, permit_count "
            "FROM entities "
            "WHERE entity_type = ? "
            "AND permit_count >= ? "
            "ORDER BY permit_count DESC "
            "LIMIT 200",
            (entity_type, min_permits),
        ).fetchall()
        return [
            {"entity_id": r[0], "canonical_name": r[1], "canonical_firm": r[2], "permit_count": r[3]}
            for r in rows
        ]
    else:
        # Postgres path
        from src.db import query
        rows = query(
            "SELECT entity_id, canonical_name, canonical_firm, permit_count "
            "FROM entities "
            "WHERE entity_type = %s "
            "AND permit_count >= %s "
            "ORDER BY permit_count DESC "
            "LIMIT 200",
            (entity_type, min_permits),
        )
        return [
            {"entity_id": r[0], "canonical_name": r[1], "canonical_firm": r[2], "permit_count": r[3]}
            for r in rows
        ]


def _query_relationships(conn, entity_id: int) -> list[dict]:
    """Get relationships for a specific entity."""
    if BACKEND == "duckdb":
        rows = conn.execute(
            "SELECT entity_id_a, entity_id_b, shared_permits, permit_types, "
            "date_range_start, date_range_end, neighborhoods "
            "FROM relationships "
            "WHERE (entity_id_a = ? OR entity_id_b = ?) "
            "AND shared_permits >= 2 "
            "ORDER BY shared_permits DESC "
            "LIMIT 50",
            (entity_id, entity_id),
        ).fetchall()
        return [
            {
                "entity_id_a": r[0], "entity_id_b": r[1], "shared_permits": r[2],
                "permit_types": r[3], "date_range_start": r[4],
                "date_range_end": r[5], "neighborhoods": r[6],
            }
            for r in rows
        ]
    else:
        from src.db import query
        rows = query(
            "SELECT entity_id_a, entity_id_b, shared_permits, permit_types, "
            "date_range_start, date_range_end, neighborhoods "
            "FROM relationships "
            "WHERE (entity_id_a = %s OR entity_id_b = %s) "
            "AND shared_permits >= 2 "
            "ORDER BY shared_permits DESC "
            "LIMIT 50",
            (entity_id, entity_id),
        )
        return [
            {
                "entity_id_a": r[0], "entity_id_b": r[1], "shared_permits": r[2],
                "permit_types": r[3], "date_range_start": r[4],
                "date_range_end": r[5], "neighborhoods": r[6],
            }
            for r in rows
        ]


def _format_recommendations(
    scored: list[ScoredConsultant],
    neighborhood: str | None,
    has_active_complaint: bool,
    needs_planning_coordination: bool,
    entity_type: str = "consultant",
) -> str:
    """Format scored consultants as readable markdown."""
    entity_label = entity_type.title() + "s"
    if not scored:
        return f"No qualified {entity_label.lower()} found matching your criteria."

    lines = [f"# Top {len(scored)} Recommended {entity_label}\n"]

    if entity_type != "consultant":
        lines.append(f"**Entity type:** {entity_type}")
    if neighborhood:
        lines.append(f"**Target neighborhood:** {neighborhood}")
    if has_active_complaint:
        lines.append("**Active complaint bonus:** enabled (+10 pts)")
    if needs_planning_coordination:
        lines.append("**Planning coordination bonus:** enabled (+10 pts)")
    lines.append("")

    for rank, s in enumerate(scored, 1):
        lines.append(f"## {rank}. {s.name}")
        if s.firm:
            lines.append(f"**Firm:** {s.firm}")
        lines.append(f"**Score:** {s.score:.0f}/100+")
        lines.append(f"**Permits:** {s.permit_count}")

        if s.is_registered:
            lines.append("**SF Ethics Registration:** Yes")
            if s.contact_info.get("email"):
                lines.append(f"**Email:** {s.contact_info['email']}")
            if s.contact_info.get("phone"):
                lines.append(f"**Phone:** {s.contact_info['phone']}")

        if s.neighborhoods:
            top_hoods = s.neighborhoods[:5]
            lines.append(f"**Active neighborhoods:** {', '.join(top_hoods)}")

        if s.date_range_end:
            lines.append(f"**Most recent activity:** {s.date_range_end[:10]}")

        lines.append(f"**Professional network:** {s.network_size} regular collaborators")

        # Score breakdown
        breakdown_parts = []
        for key, val in s.breakdown.items():
            label = key.replace("_", " ").title()
            breakdown_parts.append(f"{label}: {val}")
        lines.append(f"*Score breakdown: {' | '.join(breakdown_parts)}*")
        lines.append("")

    return "\n".join(lines)
