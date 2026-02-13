"""Tool: search_entity — Search for a person or company across all permit contact data."""

from src.validate import search_entity as _search_entity


async def search_entity(name: str, entity_type: str | None = None) -> str:
    """Search for a person or company across all permit contact data.

    Searches the local DuckDB database of resolved entities built from
    1.8M+ SF permit contact records. Returns entity details, permit history,
    and co-occurring entities.

    Args:
        name: Name to search for (person or company, case-insensitive)
        entity_type: Optional filter by type: 'contractor', 'architect',
                     'engineer', 'owner', 'agent', 'expediter', 'designer'

    Returns:
        Formatted results with entity details and network connections.
    """
    results = _search_entity(name)

    if not results:
        return f"No entities found matching '{name}'."

    # Filter by type if specified
    if entity_type:
        results = [r for r in results if r.get("entity_type") == entity_type]
        if not results:
            return f"No {entity_type} entities found matching '{name}'."

    lines = [f"Found {len(results)} entities matching '{name}':\n"]

    for entity in results[:10]:  # Cap at 10 results
        lines.append(f"### Entity #{entity['entity_id']}: {entity['canonical_name'] or 'Unknown'}")
        if entity.get("canonical_firm"):
            lines.append(f"**Firm:** {entity['canonical_firm']}")
        lines.append(f"**Type:** {entity.get('entity_type', 'unknown')}")
        lines.append(f"**Permits:** {entity.get('permit_count', 0)}")
        lines.append(f"**Resolution:** {entity.get('resolution_method', 'unknown')} ({entity.get('resolution_confidence', 'unknown')} confidence)")
        lines.append(f"**Sources:** {entity.get('source_datasets', 'unknown')}")

        if entity.get("license_number"):
            lines.append(f"**License:** {entity['license_number']}")
        if entity.get("pts_agent_id"):
            lines.append(f"**PTS Agent ID:** {entity['pts_agent_id']}")

        # Show co-occurring entities
        neighbors = entity.get("top_co_occurring", [])
        if neighbors:
            lines.append("\n**Top co-occurring entities:**")
            for n in neighbors[:5]:
                lines.append(
                    f"- {n.get('canonical_name', 'Unknown')} "
                    f"({n.get('entity_type', '?')}) — "
                    f"{n.get('shared_permits', 0)} shared permits"
                )
        lines.append("")

    if len(results) > 10:
        lines.append(f"\n_Showing 10 of {len(results)} results. Refine your search for more specific results._")

    return "\n".join(lines)
