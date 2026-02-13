"""Validation and anomaly detection for the SF permits network.

Searches for known bad actors, detects anomalous patterns in entity
relationships, and provides network traversal utilities over the
DuckDB-backed permit graph.

Usage as CLI:
    python -m src.validate [command] [options]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from statistics import median

from src.db import get_connection


# ---------------------------------------------------------------------------
# 1. search_entity
# ---------------------------------------------------------------------------

def search_entity(name: str, db_path=None) -> list[dict]:
    """Search entities by name (case-insensitive LIKE match).

    Returns entity details, their permit count, and the top 5
    co-occurring entities (by shared_permits weight).
    """
    conn = get_connection(db_path)
    pattern = f"%{name}%"

    entities = conn.execute(
        """
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
        WHERE lower(canonical_name) LIKE lower(?)
           OR lower(canonical_firm) LIKE lower(?)
        ORDER BY permit_count DESC
        """,
        [pattern, pattern],
    ).fetchall()

    columns = [
        "entity_id", "canonical_name", "canonical_firm", "entity_type",
        "pts_agent_id", "license_number", "sf_business_license",
        "resolution_method", "resolution_confidence", "contact_count",
        "permit_count", "source_datasets",
    ]

    results = []
    for row in entities:
        entity = dict(zip(columns, row))
        eid = entity["entity_id"]

        co_occurring = conn.execute(
            """
            SELECT
                CASE WHEN r.entity_id_a = ? THEN r.entity_id_b
                     ELSE r.entity_id_a END AS other_id,
                e.canonical_name,
                e.canonical_firm,
                e.entity_type,
                r.shared_permits,
                r.permit_numbers,
                r.neighborhoods
            FROM relationships r
            JOIN entities e
              ON e.entity_id = CASE WHEN r.entity_id_a = ? THEN r.entity_id_b
                                    ELSE r.entity_id_a END
            WHERE r.entity_id_a = ? OR r.entity_id_b = ?
            ORDER BY r.shared_permits DESC
            LIMIT 5
            """,
            [eid, eid, eid, eid],
        ).fetchall()

        co_cols = [
            "entity_id", "canonical_name", "canonical_firm",
            "entity_type", "shared_permits", "permit_numbers",
            "neighborhoods",
        ]
        entity["top_co_occurring"] = [dict(zip(co_cols, r)) for r in co_occurring]
        results.append(entity)

    conn.close()
    return results


# ---------------------------------------------------------------------------
# 2. entity_network
# ---------------------------------------------------------------------------

def entity_network(entity_id: int, hops: int = 1, db_path=None) -> dict:
    """Return the N-hop network around an entity.

    Returns a dict with:
      - nodes: list of entity dicts
      - edges: list of relationship dicts
    """
    conn = get_connection(db_path)

    visited_nodes: set[int] = set()
    frontier: set[int] = {entity_id}
    all_edges: list[dict] = []
    edge_seen: set[tuple[int, int]] = set()

    for _ in range(hops):
        if not frontier:
            break
        placeholders = ", ".join("?" for _ in frontier)
        frontier_list = list(frontier)

        rows = conn.execute(
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
               OR entity_id_b IN ({placeholders})
            """,
            frontier_list + frontier_list,
        ).fetchall()

        edge_cols = [
            "entity_id_a", "entity_id_b", "shared_permits",
            "permit_numbers", "permit_types", "date_range_start",
            "date_range_end", "total_estimated_cost", "neighborhoods",
        ]

        next_frontier: set[int] = set()
        for row in rows:
            edge = dict(zip(edge_cols, row))
            a, b = edge["entity_id_a"], edge["entity_id_b"]
            key = (min(a, b), max(a, b))
            if key not in edge_seen:
                edge_seen.add(key)
                all_edges.append(edge)
            if a not in visited_nodes:
                next_frontier.add(a)
            if b not in visited_nodes:
                next_frontier.add(b)

        visited_nodes.update(frontier)
        frontier = next_frontier - visited_nodes

    visited_nodes.update(frontier)

    if not visited_nodes:
        conn.close()
        return {"nodes": [], "edges": []}

    placeholders = ", ".join("?" for _ in visited_nodes)
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
            contact_count,
            permit_count,
            source_datasets
        FROM entities
        WHERE entity_id IN ({placeholders})
        """,
        list(visited_nodes),
    ).fetchall()

    node_cols = [
        "entity_id", "canonical_name", "canonical_firm", "entity_type",
        "pts_agent_id", "license_number", "sf_business_license",
        "contact_count", "permit_count", "source_datasets",
    ]
    nodes = [dict(zip(node_cols, r)) for r in node_rows]

    conn.close()
    return {"nodes": nodes, "edges": all_edges}


# ---------------------------------------------------------------------------
# 3. inspector_contractor_links
# ---------------------------------------------------------------------------

def inspector_contractor_links(inspector_name: str, db_path=None) -> dict:
    """Trace an inspector's connections through the permit network.

    Finds all inspections by the given inspector, extracts the permit
    numbers, then finds every entity linked to those permits and how
    many permits each entity shares with the inspector's portfolio.
    """
    conn = get_connection(db_path)
    pattern = f"%{inspector_name}%"

    inspection_rows = conn.execute(
        """
        SELECT DISTINCT
            reference_number,
            inspector,
            scheduled_date,
            result,
            inspection_description,
            neighborhood
        FROM inspections
        WHERE lower(inspector) LIKE lower(?)
          AND reference_number_type = 'permit'
        ORDER BY scheduled_date DESC
        """,
        [pattern],
    ).fetchall()

    if not inspection_rows:
        conn.close()
        return {
            "inspector": inspector_name,
            "found": False,
            "permit_count": 0,
            "inspections": 0,
            "linked_entities": [],
        }

    inspector_actual = inspection_rows[0][1]
    permit_numbers = list({row[0] for row in inspection_rows})

    if not permit_numbers:
        conn.close()
        return {
            "inspector": inspector_actual,
            "found": True,
            "permit_count": 0,
            "inspections": len(inspection_rows),
            "linked_entities": [],
        }

    placeholders = ", ".join("?" for _ in permit_numbers)

    linked = conn.execute(
        f"""
        SELECT
            e.entity_id,
            e.canonical_name,
            e.canonical_firm,
            e.entity_type,
            e.permit_count AS total_permits,
            COUNT(DISTINCT c.permit_number) AS shared_with_inspector,
            LIST(DISTINCT c.permit_number ORDER BY c.permit_number) AS shared_permit_numbers,
            LIST(DISTINCT c.role ORDER BY c.role) AS roles
        FROM contacts c
        JOIN entities e ON e.entity_id = c.entity_id
        WHERE c.permit_number IN ({placeholders})
          AND c.entity_id IS NOT NULL
        GROUP BY e.entity_id, e.canonical_name, e.canonical_firm,
                 e.entity_type, e.permit_count
        ORDER BY shared_with_inspector DESC
        """,
        permit_numbers,
    ).fetchall()

    linked_cols = [
        "entity_id", "canonical_name", "canonical_firm", "entity_type",
        "total_permits", "shared_with_inspector", "shared_permit_numbers",
        "roles",
    ]

    conn.close()
    return {
        "inspector": inspector_actual,
        "found": True,
        "permit_count": len(permit_numbers),
        "inspections": len(inspection_rows),
        "linked_entities": [dict(zip(linked_cols, r)) for r in linked],
    }


# ---------------------------------------------------------------------------
# 4. find_clusters
# ---------------------------------------------------------------------------

def find_clusters(
    min_size: int = 3, min_edge_weight: int = 5, db_path=None
) -> list[dict]:
    """Find tightly connected clusters in the entity network.

    Builds a subgraph of relationships where shared_permits >= min_edge_weight,
    then finds connected components using BFS. Returns clusters with
    size >= min_size, sorted by descending size.
    """
    conn = get_connection(db_path)

    edges = conn.execute(
        """
        SELECT
            entity_id_a,
            entity_id_b,
            shared_permits,
            total_estimated_cost,
            neighborhoods
        FROM relationships
        WHERE shared_permits >= ?
        """,
        [min_edge_weight],
    ).fetchall()

    adjacency: dict[int, list[tuple[int, int, float | None, str | None]]] = defaultdict(list)
    for a, b, weight, cost, hoods in edges:
        adjacency[a].append((b, weight, cost, hoods))
        adjacency[b].append((a, weight, cost, hoods))

    all_node_ids = set(adjacency.keys())

    entity_lookup: dict[int, dict] = {}
    if all_node_ids:
        placeholders = ", ".join("?" for _ in all_node_ids)
        ent_rows = conn.execute(
            f"""
            SELECT
                entity_id,
                canonical_name,
                canonical_firm,
                entity_type,
                permit_count
            FROM entities
            WHERE entity_id IN ({placeholders})
            """,
            list(all_node_ids),
        ).fetchall()
        for eid, cname, cfirm, etype, pcount in ent_rows:
            entity_lookup[eid] = {
                "entity_id": eid,
                "canonical_name": cname,
                "canonical_firm": cfirm,
                "entity_type": etype,
                "permit_count": pcount,
            }

    conn.close()

    visited: set[int] = set()
    clusters: list[dict] = []

    for start_node in all_node_ids:
        if start_node in visited:
            continue
        component_nodes: list[int] = []
        component_edges: list[dict] = []
        edge_seen: set[tuple[int, int]] = set()
        queue = deque([start_node])
        visited.add(start_node)

        while queue:
            current = queue.popleft()
            component_nodes.append(current)
            for neighbor, weight, cost, hoods in adjacency[current]:
                key = (min(current, neighbor), max(current, neighbor))
                if key not in edge_seen:
                    edge_seen.add(key)
                    component_edges.append({
                        "entity_id_a": current,
                        "entity_id_b": neighbor,
                        "shared_permits": weight,
                        "total_estimated_cost": cost,
                        "neighborhoods": hoods,
                    })
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        if len(component_nodes) >= min_size:
            total_edge_weight = sum(e["shared_permits"] for e in component_edges)
            total_cost = sum(
                e["total_estimated_cost"]
                for e in component_edges
                if e["total_estimated_cost"] is not None
            )
            clusters.append({
                "size": len(component_nodes),
                "edge_count": len(component_edges),
                "total_shared_permits": total_edge_weight,
                "total_estimated_cost": total_cost,
                "members": [
                    entity_lookup.get(nid, {"entity_id": nid})
                    for nid in component_nodes
                ],
                "edges": component_edges,
            })

    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters


# ---------------------------------------------------------------------------
# 5. anomaly_scan
# ---------------------------------------------------------------------------

def anomaly_scan(min_permits: int = 10, db_path=None) -> dict:
    """Flag entities and permits with unusual patterns.

    Anomaly categories:
      - high_permit_volume: entities with permit_count > 3x the median
        for their entity_type
      - inspector_concentration: contractors whose inspected permits have
        50%+ inspected by a single inspector
      - geographic_concentration: entities with 80%+ of permits in the
        same neighborhood
      - fast_approvals: permits filed-to-issued < 7 days with
        estimated_cost > $100,000
    """
    conn = get_connection(db_path)
    anomalies: dict[str, list] = {
        "high_permit_volume": [],
        "inspector_concentration": [],
        "geographic_concentration": [],
        "fast_approvals": [],
    }

    # --- High permit volume ---------------------------------------------------
    type_medians_rows = conn.execute(
        """
        SELECT entity_type, MEDIAN(permit_count) AS med
        FROM entities
        WHERE permit_count IS NOT NULL
          AND entity_type IS NOT NULL
        GROUP BY entity_type
        """
    ).fetchall()
    type_medians = {row[0]: row[1] for row in type_medians_rows}

    if type_medians:
        cases = " ".join(
            f"WHEN entity_type = '{etype}' THEN {med * 3}"
            for etype, med in type_medians.items()
            if med is not None and med > 0
        )
        if cases:
            high_vol = conn.execute(
                f"""
                SELECT
                    entity_id,
                    canonical_name,
                    canonical_firm,
                    entity_type,
                    permit_count,
                    CASE {cases} ELSE NULL END AS threshold
                FROM entities
                WHERE permit_count >= ?
                  AND permit_count > CASE {cases} ELSE 999999999 END
                ORDER BY permit_count DESC
                """,
                [min_permits],
            ).fetchall()
            vol_cols = [
                "entity_id", "canonical_name", "canonical_firm",
                "entity_type", "permit_count", "threshold",
            ]
            anomalies["high_permit_volume"] = [
                dict(zip(vol_cols, r)) for r in high_vol
            ]

    # --- Inspector concentration -----------------------------------------------
    inspector_conc = conn.execute(
        """
        WITH entity_permits AS (
            SELECT DISTINCT c.entity_id, c.permit_number
            FROM contacts c
            JOIN entities e ON e.entity_id = c.entity_id
            WHERE e.permit_count >= ?
              AND c.entity_id IS NOT NULL
        ),
        entity_inspections AS (
            SELECT
                ep.entity_id,
                i.inspector,
                COUNT(DISTINCT ep.permit_number) AS permits_by_inspector
            FROM entity_permits ep
            JOIN inspections i
              ON i.reference_number = ep.permit_number
             AND i.reference_number_type = 'permit'
            WHERE i.inspector IS NOT NULL
            GROUP BY ep.entity_id, i.inspector
        ),
        entity_totals AS (
            SELECT
                entity_id,
                SUM(permits_by_inspector) AS total_inspected
            FROM entity_inspections
            GROUP BY entity_id
        )
        SELECT
            ei.entity_id,
            e.canonical_name,
            e.canonical_firm,
            e.entity_type,
            ei.inspector,
            ei.permits_by_inspector,
            et.total_inspected,
            ROUND(ei.permits_by_inspector * 100.0 / et.total_inspected, 1) AS pct
        FROM entity_inspections ei
        JOIN entity_totals et ON et.entity_id = ei.entity_id
        JOIN entities e ON e.entity_id = ei.entity_id
        WHERE et.total_inspected >= 4
          AND ei.permits_by_inspector * 100.0 / et.total_inspected >= 50.0
        ORDER BY pct DESC, ei.permits_by_inspector DESC
        """,
        [min_permits],
    ).fetchall()

    ic_cols = [
        "entity_id", "canonical_name", "canonical_firm", "entity_type",
        "inspector", "permits_by_inspector", "total_inspected",
        "concentration_pct",
    ]
    anomalies["inspector_concentration"] = [
        dict(zip(ic_cols, r)) for r in inspector_conc
    ]

    # --- Geographic concentration -----------------------------------------------
    geo_conc = conn.execute(
        """
        WITH entity_neighborhoods AS (
            SELECT
                c.entity_id,
                p.neighborhood,
                COUNT(DISTINCT c.permit_number) AS cnt
            FROM contacts c
            JOIN permits p ON p.permit_number = c.permit_number
            JOIN entities e ON e.entity_id = c.entity_id
            WHERE e.permit_count >= ?
              AND c.entity_id IS NOT NULL
              AND p.neighborhood IS NOT NULL
            GROUP BY c.entity_id, p.neighborhood
        ),
        entity_totals AS (
            SELECT entity_id, SUM(cnt) AS total
            FROM entity_neighborhoods
            GROUP BY entity_id
        )
        SELECT
            en.entity_id,
            e.canonical_name,
            e.canonical_firm,
            e.entity_type,
            en.neighborhood,
            en.cnt AS permits_in_neighborhood,
            et.total AS total_permits,
            ROUND(en.cnt * 100.0 / et.total, 1) AS pct
        FROM entity_neighborhoods en
        JOIN entity_totals et ON et.entity_id = en.entity_id
        JOIN entities e ON e.entity_id = en.entity_id
        WHERE et.total >= ?
          AND en.cnt * 100.0 / et.total >= 80.0
        ORDER BY pct DESC, en.cnt DESC
        """,
        [min_permits, min_permits],
    ).fetchall()

    geo_cols = [
        "entity_id", "canonical_name", "canonical_firm", "entity_type",
        "neighborhood", "permits_in_neighborhood", "total_permits",
        "concentration_pct",
    ]
    anomalies["geographic_concentration"] = [
        dict(zip(geo_cols, r)) for r in geo_conc
    ]

    # --- Fast approvals ---------------------------------------------------------
    fast = conn.execute(
        """
        SELECT
            p.permit_number,
            p.permit_type,
            p.permit_type_definition,
            p.status,
            p.filed_date,
            p.issued_date,
            p.estimated_cost,
            p.street_number || ' ' || p.street_name || ' ' || COALESCE(p.street_suffix, '') AS address,
            p.neighborhood,
            DATEDIFF('day', p.filed_date::DATE, p.issued_date::DATE) AS days_to_issue
        FROM permits p
        WHERE p.filed_date IS NOT NULL
          AND p.issued_date IS NOT NULL
          AND p.estimated_cost > 100000
          AND DATEDIFF('day', p.filed_date::DATE, p.issued_date::DATE) < 7
          AND DATEDIFF('day', p.filed_date::DATE, p.issued_date::DATE) >= 0
        ORDER BY days_to_issue ASC, p.estimated_cost DESC
        """
    ).fetchall()

    fast_cols = [
        "permit_number", "permit_type", "permit_type_definition", "status",
        "filed_date", "issued_date", "estimated_cost", "address",
        "neighborhood", "days_to_issue",
    ]
    anomalies["fast_approvals"] = [dict(zip(fast_cols, r)) for r in fast]

    conn.close()

    summary = {k: len(v) for k, v in anomalies.items()}
    return {"summary": summary, "anomalies": anomalies}


# ---------------------------------------------------------------------------
# 6. run_ground_truth
# ---------------------------------------------------------------------------

def _trace_inspector(conn, name: str) -> dict:
    """Search inspections for an inspector name and trace connections."""
    pattern = f"%{name}%"
    inspections = conn.execute(
        """
        SELECT
            inspector,
            COUNT(*) AS inspection_count,
            COUNT(DISTINCT reference_number) AS permit_count,
            MIN(scheduled_date) AS earliest,
            MAX(scheduled_date) AS latest,
            LIST(DISTINCT neighborhood ORDER BY neighborhood) AS neighborhoods,
            LIST(DISTINCT result ORDER BY result) AS results
        FROM inspections
        WHERE lower(inspector) LIKE lower(?)
          AND reference_number_type = 'permit'
        GROUP BY inspector
        """,
        [pattern],
    ).fetchall()

    if not inspections:
        return {"name": name, "found": False, "search_type": "inspector"}

    inspector_actual = inspections[0][0]
    info = {
        "name": name,
        "found": True,
        "search_type": "inspector",
        "inspector_name": inspector_actual,
        "inspection_count": inspections[0][1],
        "permit_count": inspections[0][2],
        "date_range": [inspections[0][3], inspections[0][4]],
        "neighborhoods": inspections[0][5],
        "results": inspections[0][6],
    }

    permit_rows = conn.execute(
        """
        SELECT DISTINCT reference_number
        FROM inspections
        WHERE lower(inspector) LIKE lower(?)
          AND reference_number_type = 'permit'
        """,
        [pattern],
    ).fetchall()
    permit_numbers = [r[0] for r in permit_rows]

    if permit_numbers:
        placeholders = ", ".join("?" for _ in permit_numbers)
        linked = conn.execute(
            f"""
            SELECT
                e.entity_id,
                e.canonical_name,
                e.canonical_firm,
                e.entity_type,
                e.permit_count,
                COUNT(DISTINCT c.permit_number) AS shared_permits,
                LIST(DISTINCT c.role ORDER BY c.role) AS roles
            FROM contacts c
            JOIN entities e ON e.entity_id = c.entity_id
            WHERE c.permit_number IN ({placeholders})
              AND c.entity_id IS NOT NULL
            GROUP BY e.entity_id, e.canonical_name, e.canonical_firm,
                     e.entity_type, e.permit_count
            ORDER BY shared_permits DESC
            LIMIT 20
            """,
            permit_numbers,
        ).fetchall()

        linked_cols = [
            "entity_id", "canonical_name", "canonical_firm", "entity_type",
            "permit_count", "shared_permits", "roles",
        ]
        info["linked_entities"] = [dict(zip(linked_cols, r)) for r in linked]
    else:
        info["linked_entities"] = []

    return info


def _trace_contact(conn, name: str) -> dict:
    """Search contacts by name or firm_name and trace connections."""
    pattern = f"%{name}%"

    contact_rows = conn.execute(
        """
        SELECT
            c.entity_id,
            c.name,
            c.firm_name,
            c.role,
            c.permit_number,
            c.phone,
            c.address,
            c.license_number,
            c.pts_agent_id,
            c.sf_business_license
        FROM contacts c
        WHERE lower(c.name) LIKE lower(?)
           OR lower(c.firm_name) LIKE lower(?)
        ORDER BY c.permit_number
        """,
        [pattern, pattern],
    ).fetchall()

    if not contact_rows:
        return {"name": name, "found": False, "search_type": "contact"}

    permit_numbers = list({r[4] for r in contact_rows if r[4]})
    entity_ids = list({r[0] for r in contact_rows if r[0] is not None})
    roles = list({r[3] for r in contact_rows if r[3]})
    names_found = list({r[1] for r in contact_rows if r[1]})
    firms_found = list({r[2] for r in contact_rows if r[2]})

    info = {
        "name": name,
        "found": True,
        "search_type": "contact",
        "names_matched": names_found,
        "firms_matched": firms_found,
        "contact_count": len(contact_rows),
        "permit_count": len(permit_numbers),
        "roles": roles,
        "entity_ids": entity_ids,
    }

    if entity_ids:
        placeholders = ", ".join("?" for _ in entity_ids)
        entity_rows = conn.execute(
            f"""
            SELECT
                entity_id,
                canonical_name,
                canonical_firm,
                entity_type,
                permit_count,
                source_datasets
            FROM entities
            WHERE entity_id IN ({placeholders})
            """,
            entity_ids,
        ).fetchall()

        ent_cols = [
            "entity_id", "canonical_name", "canonical_firm",
            "entity_type", "permit_count", "source_datasets",
        ]
        info["entities"] = [dict(zip(ent_cols, r)) for r in entity_rows]

        all_connected = conn.execute(
            f"""
            SELECT
                CASE WHEN r.entity_id_a IN ({placeholders}) THEN r.entity_id_b
                     ELSE r.entity_id_a END AS other_id,
                e.canonical_name,
                e.canonical_firm,
                e.entity_type,
                r.shared_permits,
                r.neighborhoods
            FROM relationships r
            JOIN entities e
              ON e.entity_id = CASE WHEN r.entity_id_a IN ({placeholders})
                                    THEN r.entity_id_b
                                    ELSE r.entity_id_a END
            WHERE r.entity_id_a IN ({placeholders})
               OR r.entity_id_b IN ({placeholders})
            ORDER BY r.shared_permits DESC
            LIMIT 20
            """,
            entity_ids * 4,
        ).fetchall()

        conn_cols = [
            "entity_id", "canonical_name", "canonical_firm",
            "entity_type", "shared_permits", "neighborhoods",
        ]
        info["connected_entities"] = [dict(zip(conn_cols, r)) for r in all_connected]
    else:
        info["entities"] = []
        info["connected_entities"] = []

    return info


def run_ground_truth(db_path=None) -> dict:
    """Search for known bad actors and trace their network connections.

    Targets:
      - Rodrigo Santos (inspector — may not be in current dataset)
      - Florence Kong (inspector — may not be in current dataset)
      - Bernard Curran (inspector — 7500+ inspections)
    """
    conn = get_connection(db_path)

    findings = {
        "rodrigo_santos": _trace_inspector(conn, "Rodrigo Santos"),
        "florence_kong": _trace_inspector(conn, "Florence Kong"),
        "bernard_curran": _trace_inspector(conn, "Bernard Curran"),
    }

    conn.close()

    found_count = sum(1 for f in findings.values() if f.get("found"))
    findings["summary"] = {
        "targets_searched": len(findings) - 1,
        "targets_found": found_count,
    }

    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_json(data, indent=2):
    """Pretty-print a data structure as JSON, handling non-serializable types."""

    def default_serializer(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        return str(obj)

    print(json.dumps(data, indent=indent, default=default_serializer))


def main():
    parser = argparse.ArgumentParser(
        prog="python -m src.validate",
        description="Validation and anomaly detection for SF permits network.",
    )
    parser.add_argument(
        "--db", default=None,
        help="Path to DuckDB database (default: SF_PERMITS_DB env or data/sf_permits.duckdb)",
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # search_entity
    p_search = sub.add_parser("search", help="Search entities by name")
    p_search.add_argument("name", help="Name to search for")

    # entity_network
    p_net = sub.add_parser("network", help="Get N-hop entity network")
    p_net.add_argument("entity_id", type=int, help="Entity ID")
    p_net.add_argument("--hops", type=int, default=1, help="Number of hops (default: 1)")

    # inspector_contractor_links
    p_insp = sub.add_parser("inspector", help="Trace inspector-contractor links")
    p_insp.add_argument("name", help="Inspector name to search")

    # find_clusters
    p_clust = sub.add_parser("clusters", help="Find tightly connected clusters")
    p_clust.add_argument("--min-size", type=int, default=3, help="Minimum cluster size (default: 3)")
    p_clust.add_argument("--min-weight", type=int, default=5, help="Minimum edge weight (default: 5)")

    # anomaly_scan
    p_anom = sub.add_parser("anomalies", help="Run anomaly scan")
    p_anom.add_argument("--min-permits", type=int, default=10, help="Minimum permit threshold (default: 10)")

    # run_ground_truth
    sub.add_parser("ground-truth", help="Search for known bad actors")

    # all
    sub.add_parser("all", help="Run all checks (ground-truth + anomalies + clusters)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    db = args.db

    if args.command == "search":
        results = search_entity(args.name, db_path=db)
        print(f"Found {len(results)} matching entities:\n")
        _print_json(results)

    elif args.command == "network":
        result = entity_network(args.entity_id, hops=args.hops, db_path=db)
        print(f"Network: {len(result['nodes'])} nodes, {len(result['edges'])} edges\n")
        _print_json(result)

    elif args.command == "inspector":
        result = inspector_contractor_links(args.name, db_path=db)
        if result["found"]:
            print(f"Inspector: {result['inspector']}")
            print(f"Permits inspected: {result['permit_count']}")
            print(f"Linked entities: {len(result['linked_entities'])}\n")
        else:
            print(f"Inspector '{args.name}' not found in inspection records.\n")
        _print_json(result)

    elif args.command == "clusters":
        results = find_clusters(
            min_size=args.min_size, min_edge_weight=args.min_weight, db_path=db,
        )
        print(f"Found {len(results)} clusters:\n")
        for i, c in enumerate(results):
            print(f"  Cluster {i + 1}: {c['size']} members, "
                  f"{c['edge_count']} edges, "
                  f"{c['total_shared_permits']} total shared permits")
        print()
        _print_json(results)

    elif args.command == "anomalies":
        result = anomaly_scan(min_permits=args.min_permits, db_path=db)
        print("Anomaly scan summary:")
        for category, count in result["summary"].items():
            print(f"  {category}: {count} flagged")
        print()
        _print_json(result)

    elif args.command == "ground-truth":
        result = run_ground_truth(db_path=db)
        print("Ground truth search:")
        for key, finding in result.items():
            if key == "summary":
                continue
            status = "FOUND" if finding.get("found") else "NOT FOUND"
            print(f"  {finding['name']}: {status}")
        print()
        _print_json(result)

    elif args.command == "all":
        print("=" * 60)
        print("SF PERMITS VALIDATION REPORT")
        print("=" * 60)

        print("\n--- Ground Truth: Known Bad Actors ---\n")
        gt = run_ground_truth(db_path=db)
        for key, finding in gt.items():
            if key == "summary":
                continue
            status = "FOUND" if finding.get("found") else "NOT FOUND"
            label = finding["name"]
            print(f"  {label}: {status}")
            if finding.get("found"):
                if finding["search_type"] == "inspector":
                    print(f"    Inspections: {finding.get('inspection_count', 0)}")
                    print(f"    Permits: {finding.get('permit_count', 0)}")
                    linked = finding.get("linked_entities", [])
                    print(f"    Linked entities: {len(linked)}")
                elif finding["search_type"] == "contact":
                    print(f"    Contact records: {finding.get('contact_count', 0)}")
                    print(f"    Permits: {finding.get('permit_count', 0)}")
                    connected = finding.get("connected_entities", [])
                    print(f"    Connected entities: {len(connected)}")

        print("\n--- Anomaly Scan ---\n")
        anom = anomaly_scan(db_path=db)
        for category, count in anom["summary"].items():
            print(f"  {category}: {count} flagged")

        print("\n--- Cluster Detection ---\n")
        clusters = find_clusters(db_path=db)
        print(f"  Found {len(clusters)} clusters (min_size=3, min_edge_weight=5)")
        for i, c in enumerate(clusters[:10]):
            print(f"  Cluster {i + 1}: {c['size']} members, "
                  f"{c['total_shared_permits']} shared permits, "
                  f"${c['total_estimated_cost']:,.0f} est. cost")

        print("\n" + "=" * 60)
        print("Full results written to stdout as JSON below.")
        print("=" * 60 + "\n")

        _print_json({
            "ground_truth": gt,
            "anomalies": anom,
            "clusters": clusters,
        })


if __name__ == "__main__":
    main()
