"""Entity resolution: deduplicate contacts into canonical entities.

Resolves contact records into unique entities using a priority cascade:
  1. pts_agent_id  (building contacts only, high confidence)
  2. license_number  (all sources, medium confidence) — with license normalization
  2.5. Cross-source name matching on same permit (medium confidence)
  3. sf_business_license  (all sources, medium confidence)
  4. Fuzzy name matching  (remaining unresolved, low confidence)

Improvements in this version:
  - License normalization: strips leading zeros, normalizes type prefixes (C-10 → C10)
  - Cross-source matching: same normalized name on same permit across different sources
  - Name normalization: LAST FIRST reordering, punctuation stripping, lower threshold for trades
  - Multi-role entity tracking: populates `roles` column after resolution

Performance: Uses a mapping table + single bulk UPDATE per step to
minimize DuckDB column rewrites on the 1.8M-row contacts table.

Usage:
    python -m src.entities              # Run entity resolution
    python -m src.entities --db PATH    # Use custom database path
"""

from __future__ import annotations

import re
import time
from collections import Counter

from src.db import get_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_license(lic: str | None) -> str | None:
    """Normalize a contractor license number for consistent matching.

    Transformations applied:
    - Strip whitespace; return None for empty/None input
    - Normalize type prefixes: "C-10" → "C10", "c-10" → "C10" (uppercase, remove dash)
    - Strip leading zeros from numeric-only license numbers

    Examples:
        "0012345"  → "12345"
        "C-10"     → "C10"
        "c-10"     → "C10"
        "c10"      → "C10"
        "B-12345"  → "B12345"
        None       → None
        ""         → None
        "  "       → None
    """
    if lic is None:
        return None
    lic = lic.strip()
    if not lic:
        return None

    # Normalize license type prefixes (e.g., "C-10", "c-10", "c10" → "C10")
    # Pattern: one or more letters, optional dash, digits (possibly with more dashes/digits)
    prefix_match = re.match(r'^([A-Za-z]+)-?(\d.*)$', lic)
    if prefix_match:
        prefix = prefix_match.group(1).upper()
        rest = prefix_match.group(2)
        # Strip leading zeros from the numeric part after the prefix
        # But only if it's purely digits (don't strip "10" from "C10" sub-licenses)
        # For the prefix pattern we just join them
        return prefix + rest

    # Pure numeric: strip leading zeros
    if re.match(r'^\d+$', lic):
        return str(int(lic))  # int() strips leading zeros naturally

    # Mixed or other formats: just uppercase and return
    return lic.upper()


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


def _normalize_name(name: str) -> str:
    """Normalize a contact name for fuzzy matching.

    Transformations:
    - Strip whitespace and UPPERCASE
    - Strip punctuation (commas, periods, dashes)
    - Detect LAST FIRST pattern (exactly 2 tokens, common in DBI data)
      and produce canonical "FIRST LAST" form for token comparison

    The token SET similarity is order-independent, so reordering doesn't
    change the similarity score. This function is mainly for preprocessing
    before blocking.
    """
    if not name:
        return ""
    # Uppercase and strip whitespace
    normalized = name.upper().strip()
    # Remove punctuation: commas, periods, dashes, apostrophes
    normalized = re.sub(r"[,.\-']+", " ", normalized)
    # Collapse multiple spaces
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


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

    For license_number matching, applies license normalization before lookup.
    Handles merging into existing entities where the key already has one.
    Returns (next_entity_id, entities_created).
    """
    apply_license_norm = (key_column == "license_number")

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
    # For license_number, normalize the stored key for matching
    existing_map: dict[str, int] = {}
    existing_rows = conn.execute(f"""
        SELECT {key_column}, entity_id FROM entities
        WHERE {key_column} IS NOT NULL
    """).fetchall()
    for er in existing_rows:
        raw_key = er[0]
        norm_key = _normalize_license(raw_key) if apply_license_norm else raw_key
        if norm_key and norm_key not in existing_map:
            existing_map[norm_key] = er[1]

    # Separate into merge (existing entity) and create (new entity)
    merge_pairs = []  # (contact_id, existing_entity_id)
    new_groups: dict[int, list[int]] = {}  # entity_id -> [contact_ids]
    # Track which normalized keys map to which new entity_id
    new_key_to_eid: dict[str, int] = {}
    entity_id = next_entity_id

    for row in unresolved_groups:
        key_val = row[0]
        contact_ids = row[1]

        norm_key = _normalize_license(key_val) if apply_license_norm else key_val

        if norm_key in existing_map:
            target_eid = existing_map[norm_key]
            for cid in contact_ids:
                merge_pairs.append((cid, target_eid))
        elif norm_key in new_key_to_eid:
            # Another raw key normalized to the same value → merge into same new entity
            target_eid = new_key_to_eid[norm_key]
            new_groups[target_eid].extend(contact_ids)
        else:
            new_groups[entity_id] = list(contact_ids)
            existing_map[norm_key] = entity_id
            new_key_to_eid[norm_key] = entity_id
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


def _resolve_by_cross_source_name(conn, next_entity_id: int) -> tuple[int, int]:
    """Step 2.5: Match contacts with same normalized name on same permit across sources.

    Two contacts on the same permit with the same (normalized) name but
    different source datasets are almost certainly the same person —
    e.g. "JOHN'S ELECTRIC" appearing on both a building contact list and
    an electrical permit for the same permit_number.

    Uses UPPER + punctuation-stripped name comparison in SQL, then merges
    matching groups in Python.

    Returns (next_entity_id, entities_created).
    """
    # Find unresolved contacts grouped by (normalized_name, permit_number)
    # where multiple sources are present.
    # Note: DuckDB regex character class — use explicit characters, not escape sequences
    # that get mis-parsed. Period, dash, and single-quote handled as separate alternatives.
    groups = conn.execute("""
        SELECT
            UPPER(REGEXP_REPLACE(REGEXP_REPLACE(TRIM(name), '[,.-]+', ' '), E'\\'', ' ')) AS norm_name,
            permit_number,
            LIST(id) AS contact_ids,
            LIST(DISTINCT source) AS sources
        FROM contacts
        WHERE entity_id IS NULL
          AND name IS NOT NULL
          AND TRIM(name) != ''
          AND permit_number IS NOT NULL
        GROUP BY norm_name, permit_number
        HAVING COUNT(DISTINCT source) > 1
           AND COUNT(*) > 1
    """).fetchall()

    if not groups:
        return next_entity_id, 0

    # Build mapping: contact_id -> entity_id
    # We also need to handle the case where multiple groups point to the same
    # person across different permits (use norm_name as a secondary grouping key)
    name_to_eid: dict[str, int] = {}
    merge_pairs: list[tuple[int, int]] = []  # (contact_id, entity_id)
    new_groups: dict[int, list[int]] = {}  # entity_id -> [contact_ids]

    entity_id = next_entity_id

    for row in groups:
        norm_name = row[0]
        # permit_number = row[1]  # not used but present for context
        contact_ids = row[2]

        if norm_name in name_to_eid:
            # This person was already seen — merge into existing entity
            target_eid = name_to_eid[norm_name]
            # Some of these contacts may already be assigned to that entity
            for cid in contact_ids:
                new_groups.setdefault(target_eid, []).append(cid)
        else:
            # New entity
            name_to_eid[norm_name] = entity_id
            new_groups[entity_id] = list(contact_ids)
            entity_id += 1

    # Flatten to (contact_id, entity_id) pairs, filtering already-assigned contacts
    all_pairs = []
    for eid, cids in new_groups.items():
        for cid in cids:
            all_pairs.append((cid, eid))

    if not all_pairs:
        return next_entity_id, 0

    # Apply via VALUES temp table
    values = ",".join(f"({cid},{eid})" for cid, eid in all_pairs)
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE _cross_source_map AS
        SELECT * FROM (VALUES {values}) AS t(contact_id, entity_id)
    """)
    conn.execute("""
        UPDATE contacts SET entity_id = _cross_source_map.entity_id
        FROM _cross_source_map
        WHERE contacts.id = _cross_source_map.contact_id
          AND contacts.entity_id IS NULL
    """)
    conn.execute("DROP TABLE IF EXISTS _cross_source_map")

    # Determine which entity IDs were actually used (contacts may have been
    # pre-filtered if already assigned)
    used_eids = set()
    for eid, cids in new_groups.items():
        if eid >= next_entity_id:
            used_eids.add(eid)

    if not used_eids:
        return next_entity_id, 0

    eid_min = next_entity_id
    eid_max = entity_id - 1

    # Create entity records for the new entities
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
            'cross_source_name',
            'medium',
            COUNT(*),
            COUNT(DISTINCT c.permit_number),
            STRING_AGG(DISTINCT c.source, ',' ORDER BY c.source)
        FROM contacts c
        WHERE c.entity_id >= {eid_min} AND c.entity_id <= {eid_max}
        GROUP BY c.entity_id
        HAVING COUNT(*) > 0
    """)

    created = entity_id - next_entity_id
    return entity_id, created


def _resolve_by_fuzzy_name(conn, next_entity_id: int) -> tuple[int, int]:
    """Step 4: Fuzzy name matching for remaining unresolved contacts.

    Uses blocking on the first 3 characters of normalized name to limit
    comparisons.  Within each block, clusters contacts whose names have
    token-set Jaccard similarity >= threshold.

    Improvements over original:
    - Names are normalized (UPPER, punctuation stripped) before blocking
    - LAST FIRST pattern detection: "SMITH JOHN" → tokens {"SMITH","JOHN"}
      (token-set similarity is already order-independent, so this mainly
       helps with blocking key consistency)
    - Lower similarity threshold for trade contacts (0.67 vs 0.75) to
      catch variations like "SMITH JOHN" vs "JOHN SMITH ELECTRIC"

    Blocks larger than MAX_BLOCK_SIZE are skipped (contacts become singletons
    in step 5) because the O(n^2) pairwise comparison is too expensive and
    the match quality in very large blocks (common name prefixes) is low.

    Returns (next_entity_id, entities_created).
    """
    SIMILARITY_THRESHOLD = 0.67  # Lowered from 0.75 for better trade contact matching
    MAX_BLOCK_SIZE = 500

    # Trade roles that warrant the lower threshold
    TRADE_ROLES = {"electrical", "plumbing", "mechanical", "contractor", "engineer"}

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

    # Build blocking index: first 3 chars of normalized name -> list of contacts
    blocks: dict[str, list[tuple]] = {}
    normalized_names: dict[int, str] = {}  # contact_id -> normalized name

    for row in unresolved:
        raw_name = row[1]
        norm = _normalize_name(raw_name)
        normalized_names[row[0]] = norm
        block_key = norm[:3] if len(norm) >= 3 else norm
        if block_key not in blocks:
            blocks[block_key] = []
        blocks[block_key].append(row)

    # Pre-compute token sets for all unresolved contacts (using normalized names)
    token_cache: dict[int, frozenset[str]] = {}
    for row in unresolved:
        norm = normalized_names[row[0]]
        token_cache[row[0]] = frozenset(norm.split()) if norm else frozenset()

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

            # Choose threshold based on role
            role_a = (contact_a[3] or "").lower()
            threshold = SIMILARITY_THRESHOLD if any(t in role_a for t in TRADE_ROLES) else 0.75

            for j in range(i + 1, len(block_contacts)):
                contact_b = block_contacts[j]
                cid_b = contact_b[0]
                if cid_b in assigned or cid_b in block_assigned:
                    continue

                tokens_b = token_cache[cid_b]
                if not tokens_b:
                    continue

                # Use the lower of the two thresholds if either is a trade contact
                role_b = (contact_b[3] or "").lower()
                pair_threshold = SIMILARITY_THRESHOLD if any(t in role_b for t in TRADE_ROLES) else threshold

                intersection = len(tokens_a & tokens_b)
                if intersection == 0:
                    continue
                union = len(tokens_a | tokens_b)
                if intersection / union >= pair_threshold:
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


def _resolve_planning_contacts(conn, next_entity_id: int) -> tuple[int, int]:
    """Step 2.75: Merge planning contacts into existing building entities by name.

    Planning contacts have LOWER priority than building/electrical/plumbing.
    If a planning contact name matches an existing entity's canonical_name,
    the planning contact is assigned to that existing entity (additive-only).
    Planning contacts that don't match any existing entity are left unresolved
    for later steps (fuzzy name or singleton).

    Returns (next_entity_id, merged_count) — note: no new entities are created.
    """
    # Find unresolved planning contacts
    planning_contacts = conn.execute("""
        SELECT id, name
        FROM contacts
        WHERE source = 'planning'
          AND entity_id IS NULL
          AND name IS NOT NULL
          AND TRIM(name) != ''
    """).fetchall()

    if not planning_contacts:
        return next_entity_id, 0

    # Build a lookup of normalized existing entity names -> entity_id
    existing_entities = conn.execute("""
        SELECT entity_id, canonical_name
        FROM entities
        WHERE canonical_name IS NOT NULL
    """).fetchall()

    name_to_eid: dict[str, int] = {}
    for eid, cname in existing_entities:
        norm = _normalize_name(cname)
        if norm and norm not in name_to_eid:
            name_to_eid[norm] = eid

    # Match planning contacts to existing entities
    merge_pairs: list[tuple[int, int]] = []  # (contact_id, entity_id)
    for contact_id, name in planning_contacts:
        norm = _normalize_name(name)
        if norm in name_to_eid:
            merge_pairs.append((contact_id, name_to_eid[norm]))

    if not merge_pairs:
        return next_entity_id, 0

    # Apply merge assignments via VALUES temp table
    values = ",".join(f"({cid},{eid})" for cid, eid in merge_pairs)
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE _planning_merge_map AS
        SELECT * FROM (VALUES {values}) AS t(contact_id, entity_id)
    """)
    conn.execute("""
        UPDATE contacts SET entity_id = _planning_merge_map.entity_id
        FROM _planning_merge_map
        WHERE contacts.id = _planning_merge_map.contact_id
          AND contacts.entity_id IS NULL
    """)
    conn.execute("DROP TABLE IF EXISTS _planning_merge_map")

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

    return next_entity_id, len(merge_pairs)


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


def _enrich_multi_role_entities(conn) -> int:
    """Post-resolution: populate the `roles` column for multi-role entities.

    After all resolution steps, entities that appear in contacts with
    different role values get their `roles` column set to a comma-separated
    list of all observed roles. The `entity_type` column retains the MODE
    (most common) role.

    Returns the count of entities updated.
    """
    # Ensure roles column exists (DuckDB supports ADD COLUMN IF NOT EXISTS)
    try:
        conn.execute("ALTER TABLE entities ADD COLUMN IF NOT EXISTS roles VARCHAR")
    except Exception:
        # Column may already exist (e.g. in tests using a manually-created schema)
        pass

    conn.execute("""
        UPDATE entities SET roles = sub.all_roles
        FROM (
            SELECT entity_id,
                   STRING_AGG(DISTINCT role, ',' ORDER BY role) AS all_roles
            FROM contacts
            WHERE role IS NOT NULL
              AND entity_id IS NOT NULL
            GROUP BY entity_id
            HAVING COUNT(DISTINCT role) > 1
        ) sub
        WHERE entities.entity_id = sub.entity_id
    """)

    updated = conn.execute(
        "SELECT COUNT(*) FROM entities WHERE roles IS NOT NULL"
    ).fetchone()[0]

    return updated


# ---------------------------------------------------------------------------
# Entity quality scoring (Sprint 65-D)
# ---------------------------------------------------------------------------

def compute_entity_quality(entity_id: int, conn=None) -> dict:
    """Compute a quality confidence score (0-100) for an entity.

    Scores based on:
    - Number of sources (0-25 points): more source datasets = higher confidence
    - Name consistency (0-25 points): consistent naming across contacts
    - Activity recency (0-25 points): recent activity = higher confidence
    - Number of relationships (0-25 points): more connections = higher confidence

    Args:
        entity_id: The entity to score
        conn: Optional DB connection (creates one if not provided)

    Returns:
        Dict with total score, component scores, and explanation.
    """
    from src.db import get_connection as _get_conn

    own_conn = conn is None
    if own_conn:
        conn = _get_conn()

    try:
        # Get entity info
        entity = conn.execute("""
            SELECT entity_id, canonical_name, source_datasets, contact_count, permit_count
            FROM entities WHERE entity_id = ?
        """, [entity_id]).fetchone()

        if not entity:
            return {"entity_id": entity_id, "score": 0, "error": "Entity not found"}

        source_datasets = entity[2] or ""
        contact_count = entity[3] or 0
        permit_count = entity[4] or 0

        # --- Component 1: Number of sources (0-25) ---
        sources = [s.strip() for s in source_datasets.split(",") if s.strip()]
        source_count = len(sources)
        if source_count >= 4:
            source_score = 25
        elif source_count >= 3:
            source_score = 20
        elif source_count >= 2:
            source_score = 15
        elif source_count >= 1:
            source_score = 10
        else:
            source_score = 0

        # --- Component 2: Name consistency (0-25) ---
        names = conn.execute("""
            SELECT DISTINCT name FROM contacts
            WHERE entity_id = ? AND name IS NOT NULL AND TRIM(name) != ''
        """, [entity_id]).fetchall()

        name_count = len(names)
        if name_count == 0:
            name_score = 0
        elif name_count == 1:
            name_score = 25  # Perfect consistency
        elif name_count == 2:
            # Check similarity of the two names
            norm_names = [_normalize_name(n[0]) for n in names]
            sim = _token_set_similarity(norm_names[0], norm_names[1])
            name_score = round(25 * sim)
        else:
            # Multiple names — check pairwise similarity with canonical
            canonical = entity[1] or ""
            norm_canonical = _normalize_name(canonical)
            sims = []
            for (n,) in names:
                sim = _token_set_similarity(norm_canonical, _normalize_name(n))
                sims.append(sim)
            avg_sim = sum(sims) / len(sims) if sims else 0
            name_score = round(25 * avg_sim)

        # --- Component 3: Activity recency (0-25) ---
        recent_row = conn.execute("""
            SELECT MAX(from_date) FROM contacts
            WHERE entity_id = ? AND from_date IS NOT NULL
        """, [entity_id]).fetchone()

        recency_score = 0
        if recent_row and recent_row[0]:
            try:
                from datetime import date as _date
                # Parse date (handles various formats)
                date_str = str(recent_row[0])[:10]
                parts = date_str.split("-")
                if len(parts) == 3:
                    last_active = _date(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_ago = (_date.today() - last_active).days
                    if days_ago <= 365:
                        recency_score = 25
                    elif days_ago <= 730:
                        recency_score = 20
                    elif days_ago <= 1825:  # 5 years
                        recency_score = 15
                    else:
                        recency_score = 5
            except (ValueError, IndexError):
                recency_score = 10  # Can't parse, give moderate score

        # --- Component 4: Number of relationships (0-25) ---
        rel_count_row = conn.execute("""
            SELECT COUNT(*) FROM relationships
            WHERE entity_id_a = ? OR entity_id_b = ?
        """, [entity_id, entity_id]).fetchone()

        rel_count = rel_count_row[0] if rel_count_row else 0
        if rel_count >= 20:
            rel_score = 25
        elif rel_count >= 10:
            rel_score = 20
        elif rel_count >= 5:
            rel_score = 15
        elif rel_count >= 2:
            rel_score = 10
        elif rel_count >= 1:
            rel_score = 5
        else:
            rel_score = 0

        total = source_score + name_score + recency_score + rel_score

        return {
            "entity_id": entity_id,
            "score": total,
            "components": {
                "source_diversity": source_score,
                "name_consistency": name_score,
                "activity_recency": recency_score,
                "relationship_count": rel_score,
            },
            "details": {
                "source_count": source_count,
                "sources": sources,
                "distinct_names": name_count,
                "contact_count": contact_count,
                "permit_count": permit_count,
                "relationship_count": rel_count,
            },
        }
    finally:
        if own_conn:
            conn.close()


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
            "cross_source_name": 0,
            "planning_name_match": 0,
            "sf_business_license": 0,
            "fuzzy_name": 0,
            "singleton": 0,
            "total_entities": 0,
            "multi_role_entities": 0,
        }

    # Step 0: Clear existing resolution
    print("\n[0/6] Clearing existing entities and resetting contact assignments...", flush=True)
    conn.execute("DELETE FROM entities")
    conn.execute("UPDATE contacts SET entity_id = NULL")

    next_eid = 1
    stats: dict[str, int] = {}

    # Step 1: pts_agent_id (pure SQL)
    print("\n[1/6] Resolving by pts_agent_id (building contacts)...", flush=True)
    t = time.time()
    next_eid, count = _resolve_by_pts_agent_id(conn, next_eid)
    resolved_contacts = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    stats["pts_agent_id"] = count
    print(f"  Created {count:,} entities ({resolved_contacts:,}/{total_contacts:,} contacts resolved) [{time.time() - t:.1f}s]", flush=True)

    # Step 2: license_number (with normalization)
    print("\n[2/6] Resolving by license_number (all sources, with normalization)...", flush=True)
    t = time.time()
    next_eid, count = _resolve_by_key(conn, next_eid, "license_number", "license_number", "medium")
    resolved_contacts = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    stats["license_number"] = count
    print(f"  Created {count:,} new entities ({resolved_contacts:,}/{total_contacts:,} contacts resolved) [{time.time() - t:.1f}s]", flush=True)

    # Step 2.5: Cross-source name matching on same permit
    print("\n[2.5/6] Resolving by cross-source name match on same permit...", flush=True)
    t = time.time()
    next_eid, count = _resolve_by_cross_source_name(conn, next_eid)
    resolved_contacts = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    stats["cross_source_name"] = count
    print(f"  Created {count:,} new entities ({resolved_contacts:,}/{total_contacts:,} contacts resolved) [{time.time() - t:.1f}s]", flush=True)

    # Step 2.75: Planning contact name matching (additive-only, lower priority)
    print("\n[2.75/6] Merging planning contacts into existing entities by name...", flush=True)
    t = time.time()
    next_eid, count = _resolve_planning_contacts(conn, next_eid)
    resolved_contacts = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    stats["planning_name_match"] = count
    print(f"  Merged {count:,} planning contacts into existing entities ({resolved_contacts:,}/{total_contacts:,} contacts resolved) [{time.time() - t:.1f}s]", flush=True)

    # Step 3: sf_business_license
    print("\n[3/6] Resolving by sf_business_license (all sources)...", flush=True)
    t = time.time()
    next_eid, count = _resolve_by_key(conn, next_eid, "sf_business_license", "sf_business_license", "medium")
    resolved_contacts = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NOT NULL"
    ).fetchone()[0]
    stats["sf_business_license"] = count
    print(f"  Created {count:,} new entities ({resolved_contacts:,}/{total_contacts:,} contacts resolved) [{time.time() - t:.1f}s]", flush=True)

    # Step 4: Fuzzy name matching
    print("\n[4/6] Resolving by fuzzy name matching (remaining unresolved)...", flush=True)
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
    print("\n[5/6] Creating singleton entities for remaining unresolved contacts...", flush=True)
    t = time.time()
    next_eid, count = _resolve_remaining_singletons(conn, next_eid)
    stats["singleton"] = count
    print(f"  Created {count:,} singleton entities [{time.time() - t:.1f}s]", flush=True)

    # Step 6: Multi-role entity enrichment
    print("\n[6/6] Enriching multi-role entities (populating `roles` column)...", flush=True)
    t = time.time()
    multi_role_count = _enrich_multi_role_entities(conn)
    stats["multi_role_entities"] = multi_role_count
    print(f"  Updated {multi_role_count:,} entities with multi-role data [{time.time() - t:.1f}s]", flush=True)

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
    print(f"    cross_source_name:  {stats['cross_source_name']:,}", flush=True)
    print(f"    planning_name_match:{stats.get('planning_name_match', 0):,}", flush=True)
    print(f"    sf_business_license:{stats['sf_business_license']:,}", flush=True)
    print(f"    fuzzy_name:         {stats['fuzzy_name']:,}", flush=True)
    print(f"    singleton:          {stats['singleton']:,}", flush=True)
    print(f"    multi_role_entities:{stats['multi_role_entities']:,}", flush=True)
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
