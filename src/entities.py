"""Entity resolution: deduplicate contacts into canonical entities.

Resolves contact records into unique entities using a priority cascade:
  1. pts_agent_id  (building contacts only, high confidence)
  2. license_number  (all sources, medium confidence)
  3. sf_business_license  (all sources, medium confidence)
  4. Fuzzy name matching  (remaining unresolved, low confidence)

Performance: Uses a mapping table + single bulk UPDATE per step to
minimize DuckDB column rewrites on the 1.8M-row contacts table.

Usage:
    python -m src.entities              # Run entity resolution
    python -m src.entities --db PATH    # Use custom database path
"""

from __future__ import annotations

import time
from collections import Counter

from src.db import get_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pick_canonical_name(names: list[str | None]) -> str | None:
    """Return the longest non-null name as the canonical representative."""
    valid = [n for n in names if n]
    if not valid:
        return None
    return max(valid, key=len)


def _pick_canonical_firm(firms: list[str | None]) -> str | None:
    """Return the longest non-null firm name as the canonical representative."""
    valid = [f for f in firms if f]
    if not valid:
        return None
    return max(valid, key=len)


def _most_common_role(roles: list[str | None]) -> str | None:
    """Return the most frequently occurring role in the list."""
    valid = [r for r in roles if r]
    if not valid:
        return None
    counter = Counter(valid)
    return counter.most_common(1)[0][0]


def _token_set_similarity(a: str, b: str) -> float:
    """Compute token-set Jaccard similarity between two strings.

    Tokenizes on whitespace after upper-casing, then computes
    |intersection| / |union|.  Returns 0.0 if either string is empty.
    """
    tokens_a = set(a.upper().split())
    tokens_b = set(b.upper().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Resolution steps — all use pure SQL where possible
# ---------------------------------------------------------------------------

def _resolve_by_pts_agent_id(conn, next_entity_id: int) -> tuple[int, int]:
    """Step 1: Group building contacts by pts_agent_id using pure SQL.

    Uses DENSE_RANK to assign entity_ids, then a single bulk UPDATE.
    Returns (next_entity_id, entities_created).
    """
    # Count distinct groups first
    group_count = conn.execute("""
        SELECT COUNT(DISTINCT pts_agent_id) FROM contacts
        WHERE source = 'building'
          AND pts_agent_id IS NOT NULL
          AND TRIM(pts_agent_id) != ''
          AND entity_id IS NULL
    """).fetchone()[0]

    if group_count == 0:
        return next_entity_id, 0

    # Step 1a: Create a mapping of pts_agent_id -> entity_id using DENSE_RANK
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE _step1_map AS
        SELECT pts_agent_id,
               {next_entity_id} + DENSE_RANK() OVER (ORDER BY pts_agent_id) - 1 AS entity_id
        FROM (
            SELECT DISTINCT pts_agent_id FROM contacts
            WHERE source = 'building'
              AND pts_agent_id IS NOT NULL
              AND TRIM(pts_agent_id) != ''
              AND entity_id IS NULL
        )
    """)

    # Step 1b: Assign entity_ids to contacts in one UPDATE
    conn.execute("""
        UPDATE contacts SET entity_id = m.entity_id
        FROM _step1_map m
        WHERE contacts.pts_agent_id = m.pts_agent_id
          AND contacts.source = 'building'
          AND contacts.entity_id IS NULL
    """)

    # Step 1c: Create entity records from grouped contacts
    conn.execute(f"""
        INSERT INTO entities (
            entity_id, canonical_name, canonical_firm, entity_type,
            pts_agent_id, license_number, sf_business_license,
            resolution_method, resolution_confidence,
            contact_count, permit_count, source_datasets
        )
        SELECT
            c.entity_id,
            MAX(c.name) AS canonical_name,
            MAX(c.firm_name) AS canonical_firm,
            MODE(c.role) AS entity_type,
            c.pts_agent_id,
            FIRST(c.license_number) FILTER (WHERE c.license_number IS NOT NULL),
            FIRST(c.sf_business_license) FILTER (WHERE c.sf_business_license IS NOT NULL),
            'pts_agent_id',
            'high',
            COUNT(*) AS contact_count,
            COUNT(DISTINCT c.permit_number) AS permit_count,
            STRING_AGG(DISTINCT c.source, ',' ORDER BY c.source) AS source_datasets
        FROM contacts c
        WHERE c.entity_id IS NOT NULL
          AND c.entity_id >= {next_entity_id}
          AND c.entity_id < {next_entity_id + group_count}
        GROUP BY c.entity_id, c.pts_agent_id
    """)

    conn.execute("DROP TABLE IF EXISTS _step1_map")

    return next_entity_id + group_count, group_count


def _resolve_by_key(conn, next_entity_id: int, key_column: str,
                     method: str, confidence: str) -> tuple[int, int]:
    """Generic step for resolving by a key column (license_number or sf_business_license).

    Handles merging into existing entities where the key already has one.
    Returns (next_entity_id, entities_created).
    """
    # Find unresolved contacts with this key, excluding already-resolved
    unresolved_groups = conn.execute(f"""
        SELECT {key_column},
               LIST(id) AS contact_ids
        FROM contacts
        WHERE {key_column} IS NOT NULL
          AND TRIM({key_column}) != ''
          AND entity_id IS NULL
        GROUP BY {key_column}
    """).fetchall()

    if not unresolved_groups:
        return next_entity_id, 0

    # Build lookup of existing entities by this key
    existing_map = {}
    existing_rows = conn.execute(f"""
        SELECT {key_column}, entity_id FROM entities
        WHERE {key_column} IS NOT NULL
    """).fetchall()
    for er in existing_rows:
        existing_map[er[0]] = er[1]

    # Separate into merge (existing entity) and create (new entity)
    merge_pairs = []  # (contact_id, existing_entity_id)
    new_groups = {}  # entity_id -> [contact_ids]
    entity_id = next_entity_id

    for row in unresolved_groups:
        key_val = row[0]
        contact_ids = row[1]

        if key_val in existing_map:
            target_eid = existing_map[key_val]
            for cid in contact_ids:
                merge_pairs.append((cid, target_eid))
        else:
            new_groups[entity_id] = contact_ids
            existing_map[key_val] = entity_id
            entity_id += 1

    # Apply merge assignments via VALUES temp table
    if merge_pairs:
        values = ",".join(f"({cid},{eid})" for cid, eid in merge_pairs)
        conn.execute(f"""
            CREATE OR REPLACE TEMP TABLE _merge_map AS
            SELECT * FROM (VALUES {values}) AS t(contact_id, entity_id)
        """)
        conn.execute("""
            UPDATE contacts SET entity_id = _merge_map.entity_id
            FROM _merge_map
            WHERE contacts.id = _merge_map.contact_id
        """)
        conn.execute("DROP TABLE IF EXISTS _merge_map")

        # Update counts for merged entities
        merged_eids = list({eid for _, eid in merge_pairs})
        eid_list = ",".join(str(e) for e in merged_eids)
        conn.execute(f"""
            UPDATE entities SET
                contact_count = sub.cnt,
                permit_count = sub.pcnt,
                source_datasets = sub.srcs
            FROM (
                SELECT entity_id,
                       COUNT(*) AS cnt,
                       COUNT(DISTINCT permit_number) AS pcnt,
                       STRING_AGG(DISTINCT source, ',' ORDER BY source) AS srcs
                FROM contacts
                WHERE entity_id IN ({eid_list})
                GROUP BY entity_id
            ) sub
            WHERE entities.entity_id = sub.entity_id
        """)

    # Assign new entity_ids via VALUES temp table
    if new_groups:
        pairs = []
        for eid, cids in new_groups.items():
            for cid in cids:
                pairs.append((cid, eid))

        values = ",".join(f"({cid},{eid})" for cid, eid in pairs)
        conn.execute(f"""
            CREATE OR REPLACE TEMP TABLE _new_map AS
            SELECT * FROM (VALUES {values}) AS t(contact_id, entity_id)
        """)
        conn.execute("""
            UPDATE contacts SET entity_id = _new_map.entity_id
            FROM _new_map
            WHERE contacts.id = _new_map.contact_id
        """)
        conn.execute("DROP TABLE IF EXISTS _new_map")

        # Create entity records for new groups
        new_eid_min = next_entity_id
        new_eid_max = entity_id - 1
        conn.execute(f"""
            INSERT INTO entities (
                entity_id, canonical_name, canonical_firm, entity_type,
                pts_agent_id, license_number, sf_business_license,
                resolution_method, resolution_confidence,
                contact_count, permit_count, source_datasets
            )
            SELECT
                c.entity_id,
                MAX(c.name),
                MAX(c.firm_name),
                MODE(c.role),
                FIRST(c.pts_agent_id) FILTER (WHERE c.pts_agent_id IS NOT NULL),
                FIRST(c.license_number) FILTER (WHERE c.license_number IS NOT NULL),
                FIRST(c.sf_business_license) FILTER (WHERE c.sf_business_license IS NOT NULL),
                '{method}',
                '{confidence}',
                COUNT(*),
                COUNT(DISTINCT c.permit_number),
                STRING_AGG(DISTINCT c.source, ',' ORDER BY c.source)
            FROM contacts c
            WHERE c.entity_id >= {new_eid_min} AND c.entity_id <= {new_eid_max}
            GROUP BY c.entity_id
        """)

    created = entity_id - next_entity_id
    return entity_id, created


def _resolve_by_fuzzy_name(conn, next_entity_id: int) -> tuple[int, int]:
    """Step 4: Fuzzy name matching for remaining unresolved contacts.

    Uses blocking on the first 3 characters of upper(name) to limit
    comparisons.  Within each block, clusters contacts whose names have
    token-set Jaccard similarity >= 0.75.

    Blocks larger than MAX_BLOCK_SIZE are skipped (contacts become singletons
    in step 5) because the O(n^2) pairwise comparison is too expensive and
    the match quality in very large blocks (common name prefixes) is low.

    Returns (next_entity_id, entities_created).
    """
    SIMILARITY_THRESHOLD = 0.75
    MAX_BLOCK_SIZE = 500

    # Fetch unresolved contacts that have a name
    unresolved = conn.execute("""
        SELECT id, name, firm_name, role, permit_number, source,
               pts_agent_id, license_number, sf_business_license
        FROM contacts
        WHERE entity_id IS NULL
          AND name IS NOT NULL
          AND TRIM(name) != ''
        ORDER BY name
    """).fetchall()

    if not unresolved:
        return next_entity_id, 0

    print(f"    {len(unresolved):,} named contacts to fuzzy match", flush=True)

    # Build blocking index: first 3 chars of UPPER(name) -> list of contacts
    blocks: dict[str, list[tuple]] = {}
    for row in unresolved:
        name_upper = row[1].upper().strip()
        block_key = name_upper[:3] if len(name_upper) >= 3 else name_upper
        if block_key not in blocks:
            blocks[block_key] = []
        blocks[block_key].append(row)

    # Pre-compute token sets for all unresolved contacts
    token_cache: dict[int, frozenset[str]] = {}
    for row in unresolved:
        token_cache[row[0]] = frozenset(row[1].upper().split()) if row[1] else frozenset()

    assigned: set[int] = set()
    clusters: list[list[tuple]] = []
    skipped_contacts = 0

    total_blocks = len(blocks)
    processed_blocks = 0

    for block_key, block_contacts in blocks.items():
        processed_blocks += 1
        if processed_blocks % 1000 == 0:
            print(f"    Fuzzy matching: {processed_blocks:,}/{total_blocks:,} blocks, {len(clusters):,} clusters", flush=True)

        if len(block_contacts) > MAX_BLOCK_SIZE:
            skipped_contacts += len(block_contacts)
            continue

        block_assigned: set[int] = set()
        for i, contact_a in enumerate(block_contacts):
            cid_a = contact_a[0]
            if cid_a in assigned or cid_a in block_assigned:
                continue

            cluster = [contact_a]
            block_assigned.add(cid_a)
            tokens_a = token_cache[cid_a]
            if not tokens_a:
                continue

            for j in range(i + 1, len(block_contacts)):
                contact_b = block_contacts[j]
                cid_b = contact_b[0]
                if cid_b in assigned or cid_b in block_assigned:
                    continue

                tokens_b = token_cache[cid_b]
                if not tokens_b:
                    continue

                intersection = len(tokens_a & tokens_b)
                if intersection == 0:
                    continue
                union = len(tokens_a | tokens_b)
                if intersection / union >= SIMILARITY_THRESHOLD:
                    cluster.append(contact_b)
                    block_assigned.add(cid_b)

            clusters.append(cluster)
            assigned.update(block_assigned & {c[0] for c in cluster})
        assigned.update(block_assigned)

    if skipped_contacts > 0:
        oversized = sum(1 for b in blocks.values() if len(b) > MAX_BLOCK_SIZE)
        print(f"    Skipped {skipped_contacts:,} contacts in {oversized} oversized blocks (>{MAX_BLOCK_SIZE})", flush=True)

    # Build mapping and entity records
    pairs = []
    entity_rows = []
    entity_id = next_entity_id

    for cluster in clusters:
        contact_ids = [c[0] for c in cluster]
        names = [c[1] for c in cluster]
        firms = [c[2] for c in cluster]
        roles = [c[3] for c in cluster]
        permits = list({c[4] for c in cluster if c[4]})
        sources = sorted({c[5] for c in cluster if c[5]})

        for cid in contact_ids:
            pairs.append((cid, entity_id))

        pts_agent_id = next((c[6] for c in cluster if c[6]), None)
        license_number = next((c[7] for c in cluster if c[7]), None)
        sf_business_license = next((c[8] for c in cluster if c[8]), None)

        entity_rows.append((
            entity_id, _pick_canonical_name(names), _pick_canonical_firm(firms),
            _most_common_role(roles),
            pts_agent_id, license_number, sf_business_license,
            "fuzzy_name", "low",
            len(contact_ids), len(permits), ",".join(sources),
        ))
        entity_id += 1

    print(f"    Writing {len(entity_rows):,} fuzzy entities, {len(pairs):,} contact mappings...", flush=True)

    # Batch insert entities
    if entity_rows:
        conn.executemany("""
            INSERT INTO entities (
                entity_id, canonical_name, canonical_firm, entity_type,
                pts_agent_id, license_number, sf_business_license,
                resolution_method, resolution_confidence,
                contact_count, permit_count, source_datasets
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, entity_rows)

    # Batch update contacts via VALUES temp table (in chunks to avoid SQL size limits)
    CHUNK = 200_000
    for i in range(0, len(pairs), CHUNK):
        chunk = pairs[i:i + CHUNK]
        values = ",".join(f"({cid},{eid})" for cid, eid in chunk)
        conn.execute(f"""
            CREATE OR REPLACE TEMP TABLE _fuzzy_map AS
            SELECT * FROM (VALUES {values}) AS t(contact_id, entity_id)
        """)
        conn.execute("""
            UPDATE contacts SET entity_id = _fuzzy_map.entity_id
            FROM _fuzzy_map
            WHERE contacts.id = _fuzzy_map.contact_id
        """)
    conn.execute("DROP TABLE IF EXISTS _fuzzy_map")

    created = entity_id - next_entity_id
    return entity_id, created


def _resolve_remaining_singletons(conn, next_entity_id: int) -> tuple[int, int]:
    """Create singleton entities for any contacts still unresolved.

    Uses pure SQL INSERT...SELECT and UPDATE with window functions.
    Returns (next_entity_id, entities_created).
    """
    count = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NULL"
    ).fetchone()[0]

    if count == 0:
        return next_entity_id, 0

    # Assign entity_ids using ROW_NUMBER in a temp table, then join-update
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE _singleton_map AS
        SELECT id AS contact_id,
               {next_entity_id} + ROW_NUMBER() OVER (ORDER BY id) - 1 AS entity_id
        FROM contacts
        WHERE entity_id IS NULL
    """)

    conn.execute("""
        UPDATE contacts SET entity_id = _singleton_map.entity_id
        FROM _singleton_map
        WHERE contacts.id = _singleton_map.contact_id
    """)

    # Create entity records from the now-assigned contacts
    conn.execute(f"""
        INSERT INTO entities (
            entity_id, canonical_name, canonical_firm, entity_type,
            pts_agent_id, license_number, sf_business_license,
            resolution_method, resolution_confidence,
            contact_count, permit_count, source_datasets
        )
        SELECT
            c.entity_id,
            CASE WHEN c.name IS NOT NULL AND TRIM(c.name) != '' THEN c.name ELSE NULL END,
            CASE WHEN c.firm_name IS NOT NULL AND TRIM(c.firm_name) != '' THEN c.firm_name ELSE NULL END,
            c.role,
            c.pts_agent_id,
            c.license_number,
            c.sf_business_license,
            'singleton',
            'low',
            1,
            CASE WHEN c.permit_number IS NOT NULL THEN 1 ELSE 0 END,
            COALESCE(c.source, '')
        FROM contacts c
        WHERE c.entity_id >= {next_entity_id}
          AND c.entity_id < {next_entity_id + count}
    """)

    conn.execute("DROP TABLE IF EXISTS _singleton_map")
    return next_entity_id + count, count


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def resolve_entities(db_path: str | None = None) -> dict:
    """Run entity resolution pipeline. Returns stats dict."""
    start = time.time()
    conn = get_connection(db_path)

    total_contacts = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    print(f"\n{'=' * 60}", flush=True)
    print(f"Entity Resolution Pipeline", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"Total contacts to resolve: {total_contacts:,}", flush=True)

    if total_contacts == 0:
        print("No contacts found. Run ingestion first (python -m src.ingest).", flush=True)
        conn.close()
        return {
            "total_contacts": 0,
            "pts_agent_id": 0,
            "license_number": 0,
            "sf_business_license": 0,
            "fuzzy_name": 0,
            "singleton": 0,
            "total_entities": 0,
        }

    # Step 0: Clear existing resolution
    print("\n[0/5] Clearing existing entities and resetting contact assignments...", flush=True)
    conn.execute("DELETE FROM entities")
    conn.execute("UPDATE contacts SET entity_id = NULL")

    next_eid = 1
    stats: dict[str, int] = {}

    # Step 1: pts_agent_id (pure SQL)
    print("\n[1/5] Resolving by pts_agent_id (building contacts)...", flush=True)
    t = time.time()
    next_eid, count = _resolve_by_pts_agent_id(conn, next_eid)
    resolved_contacts = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    stats["pts_agent_id"] = count
    print(f"  Created {count:,} entities ({resolved_contacts:,}/{total_contacts:,} contacts resolved) [{time.time() - t:.1f}s]", flush=True)

    # Step 2: license_number
    print("\n[2/5] Resolving by license_number (all sources)...", flush=True)
    t = time.time()
    next_eid, count = _resolve_by_key(conn, next_eid, "license_number", "license_number", "medium")
    resolved_contacts = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    stats["license_number"] = count
    print(f"  Created {count:,} new entities ({resolved_contacts:,}/{total_contacts:,} contacts resolved) [{time.time() - t:.1f}s]", flush=True)

    # Step 3: sf_business_license
    print("\n[3/5] Resolving by sf_business_license (all sources)...", flush=True)
    t = time.time()
    next_eid, count = _resolve_by_key(conn, next_eid, "sf_business_license", "sf_business_license", "medium")
    resolved_contacts = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    stats["sf_business_license"] = count
    print(f"  Created {count:,} new entities ({resolved_contacts:,}/{total_contacts:,} contacts resolved) [{time.time() - t:.1f}s]", flush=True)

    # Step 4: Fuzzy name matching
    print("\n[4/5] Resolving by fuzzy name matching (remaining unresolved)...", flush=True)
    unresolved_before = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NULL"
    ).fetchone()[0]
    print(f"  {unresolved_before:,} contacts remaining to match", flush=True)
    t = time.time()
    next_eid, count = _resolve_by_fuzzy_name(conn, next_eid)
    resolved_contacts = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    stats["fuzzy_name"] = count
    print(f"  Created {count:,} new entities ({resolved_contacts:,}/{total_contacts:,} contacts resolved) [{time.time() - t:.1f}s]", flush=True)

    # Step 5: Singletons
    print("\n[5/5] Creating singleton entities for remaining unresolved contacts...", flush=True)
    t = time.time()
    next_eid, count = _resolve_remaining_singletons(conn, next_eid)
    stats["singleton"] = count
    print(f"  Created {count:,} singleton entities [{time.time() - t:.1f}s]", flush=True)

    # Final verification
    unresolved_final = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NULL"
    ).fetchone()[0]
    total_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]

    elapsed = time.time() - start
    stats["total_contacts"] = total_contacts
    stats["total_entities"] = total_entities

    print(f"\n{'=' * 60}", flush=True)
    print(f"Entity Resolution Complete [{elapsed:.1f}s]", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Total contacts:       {total_contacts:,}", flush=True)
    print(f"  Total entities:       {total_entities:,}", flush=True)
    print(f"  Unresolved contacts:  {unresolved_final:,}", flush=True)
    print(f"  Dedup ratio:          {total_contacts / total_entities:.2f}x" if total_entities > 0 else "  Dedup ratio: N/A", flush=True)
    print(f"\n  Entities by resolution method:", flush=True)
    print(f"    pts_agent_id:       {stats['pts_agent_id']:,}", flush=True)
    print(f"    license_number:     {stats['license_number']:,}", flush=True)
    print(f"    sf_business_license:{stats['sf_business_license']:,}", flush=True)
    print(f"    fuzzy_name:         {stats['fuzzy_name']:,}", flush=True)
    print(f"    singleton:          {stats['singleton']:,}", flush=True)
    print(f"{'=' * 60}", flush=True)

    conn.close()
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for entity resolution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Resolve contacts into deduplicated entities"
    )
    parser.add_argument("--db", type=str, help="Custom database path")
    args = parser.parse_args()

    resolve_entities(db_path=args.db)


if __name__ == "__main__":
    main()
