"""Tool: entity_network — Get the relationship network around an entity."""

from src.validate import entity_network as _entity_network


async def entity_network(entity_id: str, hops: int = 1) -> str:
    """Get the relationship network around an entity.

    Returns connected entities with edge weights and shared permit details.
    Uses the local DuckDB database of resolved entities and co-occurrence
    relationships.

    Args:
        entity_id: The entity ID to center the network on (from search_entity results)
        hops: Number of relationship hops to traverse (1 = direct connections,
              2 = connections of connections). Max 3.

    Returns:
        Formatted network visualization with nodes and edges.
    """
    hops = min(max(hops, 1), 3)

    try:
        eid = int(entity_id)
    except (ValueError, TypeError):
        return f"Invalid entity_id '{entity_id}'. Must be a number (use search_entity to find IDs)."

    network = _entity_network(eid, hops=hops)

    if not network:
        return f"No entity found with ID {eid}."

    nodes = network.get("nodes", [])
    edges = network.get("edges", [])

    # Find the center node from the nodes list
    center = next((n for n in nodes if n.get("entity_id") == eid), {})
    center_name = center.get("canonical_name", "Unknown")

    lines = [
        f"# Network for: {center_name}",
        f"**Entity ID:** {eid}",
        f"**Type:** {center.get('entity_type', 'unknown')}",
        f"**Hops:** {hops}",
        f"**Nodes:** {len(nodes)} | **Edges:** {len(edges)}",
        "",
    ]

    if len(nodes) <= 1:
        lines.append("No connections found for this entity.")
        return "\n".join(lines)

    lines.append("## Connected Entities\n")

    # For display, pair each non-center node with its edge weight to center
    # Build a lookup of edge weights
    edge_weights = {}
    for e in edges:
        a, b = e.get("entity_id_a"), e.get("entity_id_b")
        weight = e.get("shared_permits", 0)
        edge_weights[(a, b)] = weight
        edge_weights[(b, a)] = weight

    other_nodes = [n for n in nodes if n.get("entity_id") != eid]
    # Sort by edge weight to center, falling back to permit_count
    other_nodes.sort(
        key=lambda n: edge_weights.get((eid, n.get("entity_id")), n.get("permit_count", 0)),
        reverse=True,
    )

    for node in other_nodes[:30]:
        nid = node.get("entity_id")
        weight = edge_weights.get((eid, nid), "indirect")
        lines.append(
            f"- **{node.get('canonical_name', 'Unknown')}** "
            f"(#{nid}, {node.get('entity_type', '?')}) — "
            f"{weight} shared permits"
        )

    if len(other_nodes) > 30:
        lines.append(f"\n_Showing 30 of {len(other_nodes)} connected entities._")

    return "\n".join(lines)
