"""Co-occurrence graph: build and query entity relationship edges from permit data.

Entities that appear on the same permit are connected. Edge weight = number of
shared permits.  All heavy lifting is done in SQL (self-join on contacts,
joined to permits for enrichment) so we never pull million-row tables into
Python.

Usage:
    python -m src.graph              # Build the full graph
    python -m src.graph --neighbors 42   # 1-hop neighbors of entity 42
    python -m src.graph --network 42     # 2-hop network of entity 42
    python -m src.graph --network 42 --hops 3
"""

import time
import sys

from src.db import get_connection


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_graph(db_path: str | None = None) -> dict:
    """Build the co-occurrence relationship graph from resolved contacts.

    For every pair of distinct entities that share at least one permit, we
    compute aggregate edge attributes (shared permit count, permit numbers,
    types, date range, total cost, neighborhoods) and store them in the
    ``relationships`` table.

    All computation is pushed into DuckDB via a single INSERT ... SELECT
    with a self-join on the ``contacts`` table, joined to ``permits`` for
    enrichment.  Entity pairs are canonically ordered (entity_id_a < entity_id_b).

    Returns a stats dict with counts of edges inserted and timing info.
    """
    start = time.time()
    conn = get_connection(db_path)

    # --- 0. Pre-flight counts for progress reporting ---
    resolved_contacts = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    distinct_entities = conn.execute(
        "SELECT COUNT(DISTINCT entity_id) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    distinct_permits = conn.execute(
        "SELECT COUNT(DISTINCT permit_number) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]

    print("=== Building Co-occurrence Graph ===")
    print(f"  Resolved contacts : {resolved_contacts:,}")
    print(f"  Distinct entities : {distinct_entities:,}")
    print(f"  Distinct permits  : {distinct_permits:,}")

    # --- 1. Clear existing edges ---
    conn.execute("DELETE FROM relationships")
    print("  Cleared relationships table")

    # --- 2. Build edges with a single INSERT ... SELECT ---
    #
    # Strategy:
    #   - Self-join contacts (aliased a, b) on permit_number where both have
    #     entity_id set and a.entity_id < b.entity_id (canonical ordering,
    #     avoids duplicates and self-loops).
    #   - LEFT JOIN permits for cost/date/type/neighborhood enrichment.
    #   - GROUP BY the entity pair to aggregate edge attributes.
    #
    # permit_numbers is capped at 20 entries via list_slice on the sorted
    # array aggregate.  permit_types and neighborhoods are stored as
    # comma-separated distinct values.

    print("  Computing edges (self-join + aggregation) ...")
    t0 = time.time()

    conn.execute("""
        INSERT INTO relationships (
            entity_id_a,
            entity_id_b,
            shared_permits,
            permit_numbers,
            permit_types,
            date_range_start,
            date_range_end,
            total_estimated_cost,
            neighborhoods
        )
        SELECT
            a.entity_id                                    AS entity_id_a,
            b.entity_id                                    AS entity_id_b,

            -- shared permit count
            COUNT(DISTINCT a.permit_number)                AS shared_permits,

            -- first 20 permit numbers, comma-separated
            array_to_string(
                list_slice(
                    list_sort(list(DISTINCT a.permit_number)),
                    1, 20
                ),
                ','
            )                                              AS permit_numbers,

            -- distinct permit types, comma-separated
            array_to_string(
                list_sort(list(DISTINCT p.permit_type)),
                ','
            )                                              AS permit_types,

            -- date range
            MIN(COALESCE(p.filed_date, p.issued_date))     AS date_range_start,
            MAX(COALESCE(p.completed_date,
                         p.issued_date,
                         p.filed_date))                    AS date_range_end,

            -- total estimated cost across shared permits
            SUM(DISTINCT CASE
                WHEN p.estimated_cost IS NOT NULL
                THEN p.estimated_cost
                ELSE 0
            END)                                           AS total_estimated_cost,

            -- distinct neighborhoods, comma-separated
            array_to_string(
                list_sort(list(DISTINCT p.neighborhood)),
                ','
            )                                              AS neighborhoods

        FROM contacts a
        JOIN contacts b
            ON  a.permit_number = b.permit_number
            AND a.entity_id < b.entity_id
        LEFT JOIN permits p
            ON a.permit_number = p.permit_number
        WHERE a.entity_id IS NOT NULL
          AND b.entity_id IS NOT NULL
        GROUP BY a.entity_id, b.entity_id
    """)

    join_elapsed = time.time() - t0
    print(f"  Edge computation: {join_elapsed:.1f}s")

    # --- 3. Stats ---
    edge_count = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    max_weight = conn.execute(
        "SELECT MAX(shared_permits) FROM relationships"
    ).fetchone()[0] or 0
    avg_weight = conn.execute(
        "SELECT AVG(shared_permits) FROM relationships"
    ).fetchone()[0] or 0

    # Entity degree distribution (how many edges per entity)
    max_degree = conn.execute("""
        SELECT MAX(deg) FROM (
            SELECT COUNT(*) AS deg FROM (
                SELECT entity_id_a AS eid FROM relationships
                UNION ALL
                SELECT entity_id_b AS eid FROM relationships
            ) GROUP BY eid
        )
    """).fetchone()[0] or 0

    elapsed = time.time() - start

    stats = {
        "edges": edge_count,
        "resolved_contacts": resolved_contacts,
        "distinct_entities": distinct_entities,
        "distinct_permits": distinct_permits,
        "max_weight": max_weight,
        "avg_weight": round(avg_weight, 2),
        "max_degree": max_degree,
        "elapsed_seconds": round(elapsed, 1),
    }

    print(f"\n  Edges inserted    : {edge_count:,}")
    print(f"  Max edge weight   : {max_weight:,}")
    print(f"  Avg edge weight   : {avg_weight:.2f}")
    print(f"  Max entity degree : {max_degree:,}")
    print(f"  Total time        : {elapsed:.1f}s")
    print("=" * 50)

    conn.close()
    return stats


# ---------------------------------------------------------------------------
# Build: reviewer-entity interaction edges
# ---------------------------------------------------------------------------

def build_reviewer_edges(db_path: str | None = None) -> dict:
    """Build edges between reviewers and architects/consultants from addenda data.

    When a reviewer (plan_checked_by from addenda) reviews a permit, and an
    architect/consultant is on that same permit, create an edge between them.
    Uses a dedicated edge_type='reviewer_interaction' to distinguish from
    standard co-occurrence edges.

    Returns stats dict with counts.
    """
    start = time.time()
    conn = get_connection(db_path)

    # Check if addenda table exists
    try:
        conn.execute("SELECT 1 FROM addenda LIMIT 1")
    except Exception:
        conn.close()
        return {"reviewer_edges": 0, "elapsed_seconds": 0, "note": "addenda table not found"}

    print("=== Building Reviewer-Entity Interaction Edges ===")

    # Find distinct reviewers and their permit numbers
    reviewer_permits = conn.execute("""
        SELECT DISTINCT plan_checked_by, application_number
        FROM addenda
        WHERE plan_checked_by IS NOT NULL
          AND TRIM(plan_checked_by) != ''
          AND application_number IS NOT NULL
    """).fetchall()

    if not reviewer_permits:
        conn.close()
        print("  No reviewer data found in addenda")
        return {"reviewer_edges": 0, "elapsed_seconds": round(time.time() - start, 1)}

    print(f"  Found {len(reviewer_permits):,} reviewer-permit pairs")

    # Build a mapping of permit_number -> list of entity_ids (architects/consultants)
    # We only care about entities with roles that indicate they're professionals
    professional_roles = ('architect', 'engineer', 'consultant', 'designer', 'agent')
    role_conditions = " OR ".join(f"LOWER(c.role) LIKE '%{r}%'" for r in professional_roles)

    permit_entities = conn.execute(f"""
        SELECT DISTINCT c.permit_number, c.entity_id
        FROM contacts c
        WHERE c.entity_id IS NOT NULL
          AND c.permit_number IS NOT NULL
          AND ({role_conditions})
    """).fetchall()

    permit_to_entities: dict[str, set[int]] = {}
    for pnum, eid in permit_entities:
        permit_to_entities.setdefault(pnum, set()).add(eid)

    # Build a mapping of reviewer name -> set of entity_ids they interacted with
    reviewer_entity_pairs: dict[tuple[str, int], int] = {}  # (reviewer, entity_id) -> count

    for reviewer, permit_num in reviewer_permits:
        entities = permit_to_entities.get(permit_num, set())
        for eid in entities:
            key = (reviewer, eid)
            reviewer_entity_pairs[key] = reviewer_entity_pairs.get(key, 0) + 1

    if not reviewer_entity_pairs:
        conn.close()
        print("  No reviewer-entity interactions found")
        return {"reviewer_edges": 0, "elapsed_seconds": round(time.time() - start, 1)}

    print(f"  Found {len(reviewer_entity_pairs):,} reviewer-entity interaction pairs")

    # Store the reviewer interaction data in a new table
    conn.execute("DROP TABLE IF EXISTS reviewer_interactions")
    conn.execute("""
        CREATE TABLE reviewer_interactions (
            reviewer_name TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            interaction_count INTEGER DEFAULT 1,
            edge_type TEXT DEFAULT 'reviewer_interaction'
        )
    """)

    batch = [
        (reviewer, eid, count, 'reviewer_interaction')
        for (reviewer, eid), count in reviewer_entity_pairs.items()
    ]
    conn.executemany(
        "INSERT INTO reviewer_interactions VALUES (?, ?, ?, ?)",
        batch,
    )

    elapsed = time.time() - start
    stats = {
        "reviewer_edges": len(batch),
        "unique_reviewers": len({r for r, _ in reviewer_entity_pairs.keys()}),
        "unique_entities": len({e for _, e in reviewer_entity_pairs.keys()}),
        "elapsed_seconds": round(elapsed, 1),
    }

    print(f"  Reviewer interaction edges: {stats['reviewer_edges']:,}")
    print(f"  Unique reviewers:           {stats['unique_reviewers']:,}")
    print(f"  Unique entities:            {stats['unique_entities']:,}")
    print(f"  Time: {elapsed:.1f}s")

    conn.close()
    return stats


# ---------------------------------------------------------------------------
# Query: 1-hop neighbors
# ---------------------------------------------------------------------------

def get_neighbors(entity_id: int, db_path: str | None = None) -> list[dict]:
    """Return the 1-hop neighbors of *entity_id* with edge attributes.

    Each dict in the returned list contains:
        - entity_id:  the neighbor's entity id
        - canonical_name, canonical_firm, entity_type: from entities table
        - shared_permits: edge weight
        - permit_numbers, permit_types, neighborhoods: edge detail strings
        - date_range_start, date_range_end: edge date range
        - total_estimated_cost: sum of permit costs on shared permits
    """
    conn = get_connection(db_path)

    rows = conn.execute("""
        SELECT
            CASE
                WHEN r.entity_id_a = ? THEN r.entity_id_b
                ELSE r.entity_id_a
            END                        AS neighbor_id,
            e.canonical_name,
            e.canonical_firm,
            e.entity_type,
            e.permit_count             AS neighbor_permit_count,
            r.shared_permits,
            r.permit_numbers,
            r.permit_types,
            r.date_range_start,
            r.date_range_end,
            r.total_estimated_cost,
            r.neighborhoods
        FROM relationships r
        JOIN entities e
            ON e.entity_id = CASE
                WHEN r.entity_id_a = ? THEN r.entity_id_b
                ELSE r.entity_id_a
            END
        WHERE r.entity_id_a = ? OR r.entity_id_b = ?
        ORDER BY r.shared_permits DESC
    """, [entity_id, entity_id, entity_id, entity_id]).fetchall()

    columns = [
        "entity_id", "canonical_name", "canonical_firm", "entity_type",
        "neighbor_permit_count", "shared_permits", "permit_numbers",
        "permit_types", "date_range_start", "date_range_end",
        "total_estimated_cost", "neighborhoods",
    ]

    conn.close()
    return [dict(zip(columns, row)) for row in rows]


# ---------------------------------------------------------------------------
# Query: N-hop network
# ---------------------------------------------------------------------------

def get_network(
    entity_id: int,
    hops: int = 1,
    db_path: str | None = None,
) -> dict:
    """Return the N-hop ego network around *entity_id*.

    Returns a dict with:
        - nodes: list of dicts (entity info for every entity in the network)
        - edges: list of dicts (every edge where both endpoints are in the
                 node set)
        - center: the seed entity_id
        - hops: depth used

    The algorithm expands the frontier hop by hop using SQL set operations,
    keeping the full traversal in DuckDB via a temporary table.
    """
    conn = get_connection(db_path)

    # --- Collect node ids layer by layer ---
    # We use a Python set for the frontier but all heavy data stays in SQL.
    visited: set[int] = {entity_id}
    frontier: set[int] = {entity_id}

    for _hop in range(hops):
        if not frontier:
            break

        # Find all neighbors of the current frontier that we haven't visited
        placeholders = ",".join("?" for _ in frontier)
        frontier_list = list(frontier)

        new_neighbors_a = conn.execute(
            f"""
            SELECT DISTINCT entity_id_b
            FROM relationships
            WHERE entity_id_a IN ({placeholders})
            """,
            frontier_list,
        ).fetchall()

        new_neighbors_b = conn.execute(
            f"""
            SELECT DISTINCT entity_id_a
            FROM relationships
            WHERE entity_id_b IN ({placeholders})
            """,
            frontier_list,
        ).fetchall()

        next_frontier: set[int] = set()
        for (nid,) in new_neighbors_a:
            if nid not in visited:
                next_frontier.add(nid)
        for (nid,) in new_neighbors_b:
            if nid not in visited:
                next_frontier.add(nid)

        visited |= next_frontier
        frontier = next_frontier

    if not visited:
        conn.close()
        return {"nodes": [], "edges": [], "center": entity_id, "hops": hops}

    # --- Fetch node data ---
    placeholders = ",".join("?" for _ in visited)
    visited_list = list(visited)

    node_rows = conn.execute(
        f"""
        SELECT
            entity_id,
            canonical_name,
            canonical_firm,
            entity_type,
            pts_agent_id,
            license_number,
            sf_business_license,
            resolution_method,
            resolution_confidence,
            contact_count,
            permit_count,
            source_datasets
        FROM entities
        WHERE entity_id IN ({placeholders})
        ORDER BY entity_id
        """,
        visited_list,
    ).fetchall()

    node_columns = [
        "entity_id", "canonical_name", "canonical_firm", "entity_type",
        "pts_agent_id", "license_number", "sf_business_license",
        "resolution_method", "resolution_confidence", "contact_count",
        "permit_count", "source_datasets",
    ]
    nodes = [dict(zip(node_columns, row)) for row in node_rows]

    # --- Fetch edges (only those where both endpoints are in the node set) ---
    edge_rows = conn.execute(
        f"""
        SELECT
            entity_id_a,
            entity_id_b,
            shared_permits,
            permit_numbers,
            permit_types,
            date_range_start,
            date_range_end,
            total_estimated_cost,
            neighborhoods
        FROM relationships
        WHERE entity_id_a IN ({placeholders})
          AND entity_id_b IN ({placeholders})
        ORDER BY shared_permits DESC
        """,
        visited_list + visited_list,
    ).fetchall()

    edge_columns = [
        "entity_id_a", "entity_id_b", "shared_permits", "permit_numbers",
        "permit_types", "date_range_start", "date_range_end",
        "total_estimated_cost", "neighborhoods",
    ]
    edges = [dict(zip(edge_columns, row)) for row in edge_rows]

    conn.close()

    return {
        "nodes": nodes,
        "edges": edges,
        "center": entity_id,
        "hops": hops,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for graph building and querying."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build and query entity co-occurrence graph"
    )
    parser.add_argument(
        "--db", type=str, default=None, help="Custom database path"
    )
    parser.add_argument(
        "--neighbors", type=int, default=None, metavar="ENTITY_ID",
        help="Show 1-hop neighbors of an entity",
    )
    parser.add_argument(
        "--network", type=int, default=None, metavar="ENTITY_ID",
        help="Show N-hop network of an entity",
    )
    parser.add_argument(
        "--hops", type=int, default=2,
        help="Number of hops for --network (default: 2)",
    )
    args = parser.parse_args()

    if args.neighbors is not None:
        neighbors = get_neighbors(args.neighbors, db_path=args.db)
        print(f"\nNeighbors of entity {args.neighbors} ({len(neighbors)} found):\n")
        for n in neighbors:
            name = n["canonical_name"] or n["canonical_firm"] or "(unknown)"
            print(
                f"  [{n['entity_id']:>6}] {name:<40} "
                f"shared={n['shared_permits']:>4}  "
                f"type={n['entity_type'] or '?':<12} "
                f"cost=${n['total_estimated_cost'] or 0:>14,.0f}"
            )
            if n["permit_types"]:
                print(f"           permit types: {n['permit_types']}")
            if n["neighborhoods"]:
                print(f"           neighborhoods: {n['neighborhoods']}")
        if not neighbors:
            print("  (no neighbors found)")

    elif args.network is not None:
        net = get_network(args.network, hops=args.hops, db_path=args.db)
        print(
            f"\n{args.hops}-hop network around entity {args.network}: "
            f"{len(net['nodes'])} nodes, {len(net['edges'])} edges\n"
        )
        print("Nodes:")
        for node in net["nodes"]:
            name = node["canonical_name"] or node["canonical_firm"] or "(unknown)"
            marker = " *" if node["entity_id"] == args.network else ""
            print(
                f"  [{node['entity_id']:>6}] {name:<40} "
                f"type={node['entity_type'] or '?':<12} "
                f"permits={node['permit_count'] or 0}{marker}"
            )
        print(f"\nEdges (top 30 by weight):")
        for edge in net["edges"][:30]:
            print(
                f"  {edge['entity_id_a']:>6} <-> {edge['entity_id_b']:<6} "
                f"shared={edge['shared_permits']:>4}  "
                f"cost=${edge['total_estimated_cost'] or 0:>14,.0f}"
            )
        if len(net["edges"]) > 30:
            print(f"  ... and {len(net['edges']) - 30} more edges")

    else:
        # Default: build the graph
        stats = build_graph(db_path=args.db)
        print(f"\nFinal stats: {stats}")


if __name__ == "__main__":
    main()
